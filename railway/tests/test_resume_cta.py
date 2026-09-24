"""The "Laid off? Tailor your resume" call to action: ONE destination, tagged.

Owner-approved 2026-09-24: a quiet link to asktherecruiter.com on the report
pages, the company pages, the digest footer and the chart embeds. Three things
are pinned here, each for a reason that would fail silently otherwise.

1. ONE BASE URL. It lives in ALT_RESUME_CTA_DEFAULT_BASE (plugin) and is
   overridable by the `alt_resume_cta_base` option. The relay's footer has to
   know it too, so digest_layout mirrors the literal and this file fails on a
   difference, the same way the footer sentences are mirrored.
2. EVERY LINK IS UTM-TAGGED with the surface it came from, so the owner can see
   which surface converts. An untagged link is referral traffic nobody can
   attribute.
3. THE CITABLE CARD STAYS CLEAN. The report's PNG/PDF export captures
   #alt-report-card, and a screenshot quoted in the press must not carry an
   advert, so the call to action renders after that article closes.

State (facet) pages deliberately do NOT carry it: test_next_step_block.py pins
the product off those pages, and that ruling stands until the owner changes it.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
MAIN = PLUGIN / "ai-layoff-tracker.php"
REPORT = PLUGIN / "templates" / "page-report.php"
EMBED = PLUGIN / "templates" / "page-chart-embed.php"
DIGEST_API = PLUGIN / "includes" / "digest-api.php"
sys.path.insert(0, str(ROOT / "railway"))
import digest_layout as layout  # noqa: E402

FUNCS = ("alt_resume_cta_base", "alt_resume_cta_url", "alt_next_step_tool_url",
         "alt_resume_cta_lines", "alt_resume_cta_html")


def _run_php(body, option=None):
    """Run the plugin's own CTA functions with WordPress stubbed out."""
    src = MAIN.read_text(encoding="utf-8")
    const = re.search(r"define\('ALT_RESUME_CTA_DEFAULT_BASE', '[^']*'\);", src)
    assert const, "ALT_RESUME_CTA_DEFAULT_BASE is not defined"
    chunks = []
    for name in FUNCS:
        m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
        assert m, f"{name} is missing"
        chunks.append(m.group(0))
    opt = "null" if option is None else "'" + option + "'"
    runner = (
        "<?php\n" + const.group(0) + "\n"
        "function get_option($k, $d = false) { $v = " + opt + "; return $v === null ? $d : $v; }\n"
        "function apply_filters($n, $v) { return $v; }\n"
        "function esc_url($s) { return htmlspecialchars($s, ENT_QUOTES); }\n"
        "function esc_url_raw($s) { return $s; }\n"
        "function esc_html($s) { return htmlspecialchars($s, ENT_QUOTES); }\n"
        "function esc_attr($s) { return htmlspecialchars($s, ENT_QUOTES); }\n"
        "function wp_http_validate_url($u) { return filter_var($u, FILTER_VALIDATE_URL) ? $u : false; }\n"
        "function add_query_arg($a, $u) { return $u . (strpos($u, '?') === false ? '?' : '&') . http_build_query($a); }\n"
        + "\n".join(chunks) + "\n" + body)
    with tempfile.NamedTemporaryFile("w", suffix=".php", delete=False) as fh:
        fh.write(runner)
    try:
        p = subprocess.run(["php", fh.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(fh.name)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


class OneDestination(unittest.TestCase):
    def test_default_base_is_the_main_domain(self):
        src = MAIN.read_text(encoding="utf-8")
        self.assertIn("define('ALT_RESUME_CTA_DEFAULT_BASE', 'https://asktherecruiter.com');", src)

    def test_relay_mirrors_the_same_base(self):
        src = MAIN.read_text(encoding="utf-8")
        php = re.search(r"define\('ALT_RESUME_CTA_DEFAULT_BASE', '([^']*)'\);", src).group(1)
        self.assertEqual(layout.RESUME_CTA_DEFAULT_BASE, php)

    def test_no_template_hardcodes_the_destination(self):
        for path in (REPORT, EMBED):
            self.assertNotIn("utm_source", path.read_text(encoding="utf-8"), path.name)

    def test_sandbox_hostname_is_gone_from_the_plugin_link(self):
        m = re.search(r"\nfunction alt_next_step_tool_url\s*\(.*?\n\}",
                      MAIN.read_text(encoding="utf-8"), re.S)
        self.assertNotIn("railway.app", m.group(0))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class TaggedPerSurface(unittest.TestCase):
    def _q(self, url):
        parts = urllib.parse.urlsplit(url)
        return parts, dict(urllib.parse.parse_qsl(parts.query))

    def test_each_surface_is_tagged(self):
        for surface in ("report", "company", "state", "digest", "embed"):
            url = _run_php(f"echo alt_resume_cta_url('{surface}');")
            parts, q = self._q(url)
            self.assertEqual(parts.netloc, "asktherecruiter.com")
            self.assertEqual(q, {"utm_source": "ai-layoff-tracker",
                                 "utm_medium": "referral",
                                 "utm_campaign": surface})

    def test_company_block_link_is_tagged_company(self):
        _, q = self._q(_run_php("echo alt_next_step_tool_url();"))
        self.assertEqual(q["utm_campaign"], "company")

    def test_option_overrides_the_base(self):
        url = _run_php("echo alt_resume_cta_url('report');",
                       option="https://example.org/app/")
        self.assertTrue(url.startswith("https://example.org/app/?utm_source="), url)

    def test_a_junk_option_falls_back_to_the_default(self):
        for junk in ("javascript:alert(1)", "not a url", "http://"):
            url = _run_php("echo alt_resume_cta_url('report');", option=junk)
            self.assertTrue(url.startswith("https://asktherecruiter.com"), (junk, url))

    def test_the_line_is_not_layoff_only(self):
        """Owner 2026-09-24: job seekers, career changers, new grads and people
        returning to work are the audience too. The line rotates by page, and
        deterministically, so a cached page does not flip on every request."""
        seen = set()
        for i in range(60):
            seen.add(_run_php(f"echo alt_resume_cta_html('report', 'seed{i}');").split("</b>")[0])
        joined = " ".join(seen)
        for lead in ("Laid off?", "Changing jobs?", "Returning to work?", "New grad"):
            self.assertIn(lead, joined)
        a = _run_php("echo alt_resume_cta_html('report', 'same');")
        self.assertEqual(a, _run_php("echo alt_resume_cta_html('report', 'same');"))

    def test_the_html_block_is_a_link_not_a_popup(self):
        html = _run_php("echo alt_resume_cta_html('report');")
        self.assertIn("r&eacute;sum&eacute;", html)
        self.assertIn("utm_campaign=report", html)
        self.assertIn('rel="noopener nofollow"', html)
        for popup in ("<script", "onload", "position:fixed", "dialog"):
            self.assertNotIn(popup, html)


class Placement(unittest.TestCase):
    def test_report_renders_it_after_the_citable_card(self):
        src = REPORT.read_text(encoding="utf-8")
        self.assertTrue("alt_resume_cta_html('report'" in src)
        self.assertLess(src.rindex("</article>"), src.index("alt_resume_cta_html('report'"))

    def test_embed_carries_it(self):
        self.assertIn("alt_resume_cta_url('embed')", EMBED.read_text(encoding="utf-8"))

    def test_digest_payload_sends_the_tagged_url(self):
        self.assertIn("alt_resume_cta_url('digest')", DIGEST_API.read_text(encoding="utf-8"))


class DigestFooter(unittest.TestCase):
    UNSUB = "https://asktherecruiter.com/blog/digest-unsubscribe/?t=x"

    def test_default_footer_links_the_tagged_url(self):
        html = layout._footer(self.UNSUB, "")
        self.assertIn("utm_campaign=digest", html)
        self.assertIn("Tailor your résumé", html)
        self.assertNotIn("Laid off?", html, "the footer goes to every reader; keep it broad")

    def test_text_part_carries_it_too(self):
        text = layout.render_text([], kicker="", unsub_url=self.UNSUB, manage_url="")
        self.assertIn("utm_campaign=digest", text)

    def test_payload_override_must_be_https(self):
        good = "https://asktherecruiter.com/?utm_source=ai-layoff-tracker&utm_medium=referral&utm_campaign=digest"
        self.assertEqual(layout.resume_cta_url(good), good)
        self.assertEqual(layout.resume_cta_url("javascript:x"), layout.resume_cta_url(""))
        self.assertTrue(layout.resume_cta_url("").startswith(layout.RESUME_CTA_DEFAULT_BASE))


if __name__ == "__main__":
    unittest.main()
