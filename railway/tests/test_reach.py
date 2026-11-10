"""Reach: feed discovery, GA4 funnel events, share buttons, page-weight budget.

Audit 2026-11-10 (owner approved the fixes the same day):
  * the layoffs RSS feed existed (/feed/layoffs/) but no <head> advertised it,
    so feed readers and Slack feed bots never found it;
  * the Google tag was loaded but no funnel event fired, so every ranking of
    what to build next rested on unknowns;
  * company and state pages had no share buttons;
  * nothing watched the flagship page's weight.

What is asserted, and why:
  * the include is GUARDED with is_readable (an FTP deploy can land the main
    file first; a hard require fatals the whole plugin);
  * the feed is advertised in <head> with rel=alternate + rss+xml and as a
    visible link on the tracker page;
  * every GA4 event goes through ONE sender that keeps only a fixed allow-list
    of short, non-personal parameters: an email address can never ride an event,
    even if a future caller passes one (run in node against the SHIPPED file);
  * share links are built from the page URL and title only, to LinkedIn and X
    intent URLs, with no third-party script anywhere;
  * the page-weight verdict (railway/page_weight.py) is RED over budget and
    UNKNOWN, never green, when a page could not be fetched.
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
MAIN_PHP = PLUGIN / "ai-layoff-tracker.php"
REACH_PHP = PLUGIN / "includes/reach.php"
REACH_JS = PLUGIN / "assets/reach.js"
CSS = PLUGIN / "assets/layoffs.css"
TRACKER = PLUGIN / "templates/page-tracker.php"
COMPANY = PLUGIN / "templates/page-company-directory.php"
FACET = PLUGIN / "templates/page-facet.php"
NODE = shutil.which("node")

sys.path.insert(0, str(ROOT / "railway"))


def _read(p):
    return p.read_text(encoding="utf-8")


class TheIncludeIsWiredSafely(unittest.TestCase):
    def test_main_file_requires_it_behind_is_readable(self):
        src = _read(MAIN_PHP)
        self.assertRegex(src, r"is_readable\(\$alt_reach\)\)\s*\{\s*require_once \$alt_reach;")

    def test_script_is_deferred_and_config_free(self):
        src = _read(REACH_PHP)
        self.assertIn("assets/reach.js", src)
        self.assertIn("'strategy' => 'defer'", src)
        self.assertNotIn("wp_localize_script", src)
        self.assertNotIn("wp_add_inline_script", src)


class TheFeedIsAdvertised(unittest.TestCase):
    def test_head_link_alternate(self):
        src = _read(REACH_PHP)
        self.assertIn("add_action('wp_head', 'alt_reach_feed_link'", src)
        self.assertIn('rel="alternate" type="application/rss+xml"', src)
        self.assertIn("home_url('/feed/layoffs/')", src)

    def test_visible_link_on_the_tracker_page(self):
        self.assertIn("alt_reach_feed_visible_link", _read(TRACKER))
        self.assertIn("RSS feed", _read(REACH_PHP))


class ShareButtons(unittest.TestCase):
    def test_on_company_and_facet_pages(self):
        for p in (COMPANY, FACET):
            self.assertIn("alt_share_buttons_html(", _read(p), p.name)

    def test_markup_is_native_buttons_with_labels(self):
        src = _read(REACH_PHP)
        self.assertIn("data-alt-share", src)
        self.assertIn('aria-label="Share this page"', src)
        for k in ("native", "copy", "linkedin", "x"):
            self.assertIn('data-alt-share-kind="%s"' % k, src)

    def test_no_third_party_script(self):
        for p in (REACH_PHP, REACH_JS):
            s = _read(p)
            self.assertNotIn("platform.twitter.com", s)
            self.assertNotIn("platform.linkedin.com", s)
            self.assertNotIn("<script src", s)

    def test_no_em_dash(self):
        for p in (REACH_PHP, REACH_JS):
            self.assertNotIn("—", _read(p), p.name)

    def test_css_44px_targets(self):
        css = _read(CSS).replace(" ", "")
        self.assertIn(".alt-share", css)
        self.assertRegex(css, r"\.alt-share[^{]*\{[^}]*min-height:44px")


class InNode(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest("UNKNOWN, NOT RUN: no node binary")

    def _run(self, expr):
        script = (
            "const vm=require('vm');const fs=require('fs');"
            "const ctx={};vm.createContext(ctx);"
            "vm.runInContext(fs.readFileSync(%s,'utf8'),ctx);"
            "const R=ctx.AltReach;globalThis.ctx=ctx;process.stdout.write(JSON.stringify(%s));"
        ) % (json.dumps(str(REACH_JS)), expr)
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_share_links(self):
        got = self._run("R.shareLinks('https://ex.com/a?b=1','Acme layoffs')")
        self.assertEqual(got["linkedin"],
                         "https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fex.com%2Fa%3Fb%3D1")
        self.assertEqual(got["x"],
                         "https://x.com/intent/post?url=https%3A%2F%2Fex.com%2Fa%3Fb%3D1&text=Acme%20layoffs")

    def test_params_are_allow_listed_and_never_personal(self):
        got = self._run("R.clean({surface:'facet',email:'a@b.com',kind:'me@x.org',chart:'alt-chart-weekly',"
                        "page_type:'company',junk:'z'})")
        self.assertEqual(got, {"surface": "facet", "chart": "alt-chart-weekly", "page_type": "company"})

    def test_event_names_are_the_fixed_five(self):
        self.assertEqual(self._run("R.EVENTS"),
                         ["digest_signup", "follow", "embed_copy", "cite_copy", "resume_prompt_click"])

    def test_send_without_gtag_is_a_no_op_and_unknown_events_are_dropped(self):
        self.assertEqual(self._run("[R.send('follow',{}),R.send('pageview_hack',{})]"), [False, False])
        got = self._run("(()=>{const c=[];ctx.gtag=(...a)=>c.push(a);R.send('follow',{kind:'state',email:'x@y.z'});"
                        "R.send('bogus',{});return c;})()")
        self.assertEqual(got, [["event", "follow", {"kind": "state"}]])

    def test_resume_campaign_from_link(self):
        self.assertEqual(self._run("R.resumeCampaign('https://asktherecruiter.com/?utm_source=ai-layoff-tracker&utm_medium=referral&utm_campaign=company')"), "company")
        self.assertIsNone(self._run("R.resumeCampaign('https://example.com/?utm_campaign=x')"))


class PageWeightBudget(unittest.TestCase):
    def test_verdicts(self):
        import page_weight as pw
        self.assertEqual(pw.verdict(400_000, 30), "OK")
        self.assertEqual(pw.verdict(pw.MAX_HTML_BYTES + 1, 30), "OVER")
        self.assertEqual(pw.verdict(1000, pw.MAX_SCRIPTS + 1), "OVER")
        self.assertEqual(pw.verdict(None, None), "UNKNOWN")

    def test_exit_codes(self):
        import page_weight as pw
        self.assertEqual(pw.exit_code(["OK", "OK"]), 0)
        self.assertEqual(pw.exit_code(["OK", "OVER"]), 2)
        self.assertEqual(pw.exit_code(["OK", "UNKNOWN"]), 3)

    def test_counts_scripts(self):
        import page_weight as pw
        self.assertEqual(pw.count_scripts("<script src=a></script><SCRIPT>x</SCRIPT><noscript>"), 2)


if __name__ == "__main__":
    unittest.main()
