"""The ATR sign-up line on the employer index and company pages, and the phone bar.

Owner request 2026-11-17 ("go layoffs"): people reading the employer pages are
often just laid off, and the only route to the product was the header button,
which the legacy mobile CSS hides under 600px. So:

1. A one-line box near the top of /company-layoffs/ (campaign `directory`).
2. The same line on every company page, naming the employer (`company_entry`).
3. A small, dismissible sticky bar on phones, ONLY on those tracker pages.

Pinned here, each for a reason that fails silently otherwise:
- every link is UTM-tagged utm_source=ai-layoff-tracker&utm_medium=referral, so a
  sign-up from these pages is countable;
- the destination is the free match check (/resume-score), whose price is 0 at
  every dial setting (it is deterministic, no model call). "2 minutes" is NOT
  claimed: the product itself says "up to a minute" for the read alone;
- the copy is a condition, never a statement about the reader or the employer;
- nofollow on our own product link, as on the next-step block;
- the bar is phones only, closable, reduced-motion safe and pads the page so
  it never covers the last line of content.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
MAIN = PLUGIN / "ai-layoff-tracker.php"
INC = PLUGIN / "includes" / "atr-signup-cta.php"
INDEX = PLUGIN / "templates" / "page-company-index.php"
TRACKER = PLUGIN / "templates" / "page-tracker.php"
SHORTCODES = PLUGIN / "includes" / "shortcodes.php"
COMPANY = PLUGIN / "templates" / "page-company-directory.php"

BANNED = ("blind", "honest", "hallucinat", "—", "–", "!",
          "you've been laid off", "you were laid off", "your layoff",
          "hurry", "act now", "limited")


def _run_php(body):
    main = MAIN.read_text(encoding="utf-8")
    const = re.search(r"define\('ALT_RESUME_CTA_DEFAULT_BASE', '[^']*'\);", main).group(0)
    base = re.search(r"\nfunction alt_resume_cta_base\s*\(.*?\n\}", main, re.S).group(0)
    inc = INC.read_text(encoding="utf-8")
    inc = inc.replace("<?php", "", 1).replace("if (!defined('ABSPATH')) exit;", "")
    runner = (
        "<?php\n" + const + "\n"
        "function get_option($k, $d = false) { return $d; }\n"
        "function apply_filters($n, $v) { return $v; }\n"
        "function add_action() {}\n"
        "function esc_url($s) { return htmlspecialchars($s, ENT_QUOTES); }\n"
        "function esc_html($s) { return htmlspecialchars($s, ENT_QUOTES); }\n"
        "function esc_attr($s) { return htmlspecialchars($s, ENT_QUOTES); }\n"
        "function wp_http_validate_url($u) { return filter_var($u, FILTER_VALIDATE_URL) ? $u : false; }\n"
        "function add_query_arg($a, $u, $url = null) { if ($url !== null) { $a = array($a => $u); $u = $url; } return $u . (strpos($u, '?') === false ? '?' : '&') . http_build_query($a); }\n"
        "function sanitize_title($s) { return strtolower($s); }\n"
        "$GLOBALS['alt_test_tracker'] = false;\n"
        "function alt_company_index_is_request() { return $GLOBALS['alt_test_tracker']; }\n"
        "function alt_company_directory_is_request() { return false; }\n"
        + base + "\n" + inc + "\n" + body)
    with tempfile.NamedTemporaryFile("w", suffix=".php", delete=False) as fh:
        fh.write(runner)
    try:
        p = subprocess.run(["php", fh.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(fh.name)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


def _hrefs(html):
    return [urllib.parse.unquote(h.replace("&amp;", "&"))
            for h in re.findall(r'href="([^"]+)"', html)]


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class TheLine(unittest.TestCase):

    def test_directory_line_copy_and_tags(self):
        html = _run_php("echo alt_atr_cta_line_html('directory');")
        self.assertIn("Affected by a layoff?", html)
        self.assertIn("Check how your resume fits your next role.", html)
        (url,) = _hrefs(html)
        parts = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(parts.query))
        self.assertEqual(parts.netloc, "asktherecruiter.com")
        self.assertEqual(parts.path, "/resume-score")
        self.assertEqual(q, {"utm_source": "ai-layoff-tracker", "utm_medium": "referral",
                             "utm_campaign": "directory", "utm_content": "inline"})

    def test_optional_content_is_sanitized_and_default_urls_stay_unchanged(self):
        default = _run_php("echo alt_atr_cta_url('x');")
        tagged = _run_php("echo alt_atr_cta_url('x', 'Bad Content<b>');")
        plain = urllib.parse.urlsplit(default)
        content = urllib.parse.urlsplit(tagged)
        self.assertEqual((plain.scheme, plain.netloc, plain.path),
                         (content.scheme, content.netloc, content.path))
        expected = {"utm_source": ["ai-layoff-tracker"], "utm_medium": ["referral"],
                    "utm_campaign": ["x"]}
        self.assertEqual(urllib.parse.parse_qs(plain.query), expected)
        self.assertEqual(urllib.parse.parse_qs(content.query),
                         dict(expected, utm_content=["badcontentb"]))

    def test_facet_keeps_its_single_place_content(self):
        html = _run_php("echo alt_atr_cta_facet_html('country', 'Germany');")
        (url,) = _hrefs(html)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["utm_content"], ["germany"])
        self.assertEqual(url.count("utm_content="), 1)

    def test_company_line_names_the_employer_as_a_condition(self):
        html = _run_php("echo alt_atr_cta_line_html('company_entry', 'Acme <b>Co</b>');")
        self.assertIn("Affected by a layoff at Acme &lt;b&gt;Co&lt;/b&gt;?", html)
        self.assertIn("utm_campaign=company_entry", html.replace("&amp;", "&"))

    def test_link_is_nofollow_and_copy_is_clean(self):
        for body in ("echo alt_atr_cta_line_html('directory');",
                     "echo alt_atr_cta_line_html('company_entry', 'Acme');",
                     "$GLOBALS['alt_test_tracker'] = true; alt_atr_cta_sticky_bar();"):
            html = _run_php(body)
            for tag in re.findall(r"<a\s[^>]*>", html):
                self.assertIn("nofollow", tag)
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
            text = re.sub(r"<[^>]+>", " ", text).lower()
            for word in BANNED:
                self.assertNotIn(word, text, word)

    def test_free_is_the_only_price_claim_and_no_time_claim(self):
        html = _run_php("echo alt_atr_cta_line_html('directory');").lower()
        self.assertIn("free", html)
        self.assertNotIn("minute", html)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class ThePhoneBar(unittest.TestCase):

    def test_renders_nothing_off_tracker_pages(self):
        self.assertEqual(_run_php("alt_atr_cta_sticky_bar();").strip(), "")

    def test_tracker_bar_has_its_own_placement(self):
        html = _run_php("$GLOBALS['alt_test_tracker'] = true; alt_atr_cta_sticky_bar();")
        (url,) = _hrefs(html)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query, {"utm_source": ["ai-layoff-tracker"],
                                "utm_medium": ["referral"],
                                "utm_campaign": ["sticky_bar"],
                                "utm_content": ["sticky_bar"]})

    def test_bar_is_phone_only_dismissible_and_accessible(self):
        html = _run_php("$GLOBALS['alt_test_tracker'] = true; alt_atr_cta_sticky_bar();")
        self.assertIn("Adapt my resume, free", html)
        self.assertIn("utm_campaign=sticky_bar", html.replace("&amp;", "&"))
        self.assertRegex(html, r"@media\s*\(min-width:\s*601px\)")
        self.assertIn("prefers-reduced-motion", html)
        self.assertRegex(html, r'<button[^>]*aria-label="Close"')
        self.assertIn('aria-label="Resume help"', html)
        # Pads the page so the bar never covers the last line of content.
        self.assertIn("padding-bottom", html)
        # Remembering the close must never throw in a private window.
        js = (PLUGIN / "assets" / "atr-bar.js").read_text(encoding="utf-8")
        for line in js.splitlines():
            if "localStorage" in line:
                self.assertIn("try{", line)
        self.assertIn("alt-atr-bar-on", js)
        # Target size: WCAG 2.2 AA 2.5.8 asks 24px; we give 44px.
        self.assertIn("min-height:44px", html.replace(" ", ""))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class EveryRoutedPage(unittest.TestCase):
    """Finish line 2026-11-18 (run 44386250165): methodology, sources, press,
    editions and the rest showed no sign-up route at 390px."""

    def test_routed_tracker_pages_count_as_tracker_pages(self):
        for uri in ("/blog/ai-layoff-tracker/methodology/", "/blog/ai-layoff-tracker/press/?x=1",
                    "/blog/country-layoffs/turkiye/", "/blog/state-layoffs/ohio/",
                    "/blog/industry-layoffs/retail/", "/blog/layoff/acme-2026/"):
            out = _run_php("echo alt_atr_cta_is_tracker_route(%r) ? 'Y' : 'N';" % uri)
            self.assertEqual(out.strip(), "Y", uri)

    def test_other_blog_pages_are_not(self):
        for uri in ("/blog/", "/blog/how-to-write-a-cv/", "/blog/talent-intelligence-tracker/",
                    "/blog/layoffs-explained/"):
            out = _run_php("echo alt_atr_cta_is_tracker_route(%r) ? 'Y' : 'N';" % uri)
            self.assertEqual(out.strip(), "N", uri)

    def test_bar_renders_on_a_routed_page(self):
        html = _run_php("$_SERVER['REQUEST_URI'] = '/blog/ai-layoff-tracker/sources/'; alt_atr_cta_sticky_bar();")
        self.assertIn("utm_campaign=sticky_bar", html.replace("&amp;", "&"))

    def test_standalone_logs_carry_the_line(self):
        src = (PLUGIN / "includes" / "public-logs.php").read_text(encoding="utf-8")
        self.assertIn("alt_atr_cta_line_html('public_log')", src)


class Placement(unittest.TestCase):

    def test_index_hub_carries_it_after_the_lede(self):
        src = INDEX.read_text(encoding="utf-8")
        self.assertIn("alt_atr_cta_line_html('directory')", src)
        self.assertLess(src.index("alt-company-index-lede"),
                        src.index("alt_atr_cta_line_html('directory')"))

    def test_company_page_carries_it_with_the_name(self):
        src = COMPANY.read_text(encoding="utf-8")
        # Since todo#2983 the company page carries the layoff-to-resume line
        # instead (tests/test_layoff_resume_loop.py pins its copy and tags).
        self.assertIn("alt_layoff_resume_line_html($alt_label", src)
        self.assertLess(src.index("alt-company-summary"),
                        src.index("alt_layoff_resume_line_html("))

    def test_main_tracker_page_carries_it_after_the_hero(self):
        # CLAUDE.md conversion rule (owner 2026-11-17): the flagship page, the
        # one most readers land on, had no tracked sign-up path at all.
        src = TRACKER.read_text(encoding="utf-8")
        self.assertIn("alt_atr_cta_line_html('tracker_home')", src)
        self.assertLess(src.index('class="alt-hero"'),
                        src.index("alt_atr_cta_line_html('tracker_home')"))

    def test_main_tracker_page_gets_the_phone_bar(self):
        inc = INC.read_text(encoding="utf-8")
        self.assertIn("$GLOBALS['alt_tracker_rendered']", inc)
        sc = SHORTCODES.read_text(encoding="utf-8")
        self.assertIn("function_exists('alt_atr_cta_enqueue')", sc)

    def test_calls_are_ftp_race_guarded(self):
        # COMPANY carries the layoff-to-resume line instead (test_layoff_resume_loop.py).
        for path in (INDEX, TRACKER):
            self.assertIn("function_exists('alt_atr_cta_line_html')",
                          path.read_text(encoding="utf-8"), path.name)

    def test_bar_markup_prints_before_footer_scripts(self):
        # WordPress prints enqueued footer scripts at wp_footer priority 20.
        # 2.20.332 hooked the bar at 20 too, after them, so atr-bar.js ran
        # before the bar existed and the bar never showed (live 2026-11-17).
        src = INC.read_text(encoding="utf-8")
        m = re.search(r"add_action\('wp_footer', 'alt_atr_cta_sticky_bar', (\d+)\)", src)
        self.assertTrue(m)
        self.assertLess(int(m.group(1)), 20)
        js = (PLUGIN / "assets" / "atr-bar.js").read_text(encoding="utf-8")
        self.assertIn("DOMContentLoaded", js)

    def test_bar_lifts_the_feedback_button_clear_of_its_close(self):
        # Live 2026-11-17: the fixed feedback button (roo-feedback.css,
        # bottom:16px, z 9990) sat on top of the bar's close button.
        src = INC.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("body.alt-atr-bar-on#alt-roo-feedback.alt-roo-btn{bottom:", src)
        self.assertIn("body.alt-atr-bar-on.alt-roo-dialog{bottom:", src)

    def test_main_file_loads_it_guarded(self):
        src = MAIN.read_text(encoding="utf-8")
        self.assertIn("includes/atr-signup-cta.php", src)


if __name__ == "__main__":
    unittest.main()
