"""The ATR sign-up line on the employer index and company pages, and the phone bar.

Owner request 2026-11-17 ("go layoffs"): people reading the employer pages are
often just laid off, and the only route to the product was the header button,
which the legacy mobile CSS hides under 600px. So:

1. A one-line box near the top of /company-layoffs/ (campaign `directory`).
2. The same line on every company page, naming the employer (`company_entry`).
3. A small, dismissible sticky bar on phones, ONLY on those tracker pages.

Pinned here, each for a reason that fails silently otherwise:
- every link is UTM-tagged utm_source=layoff_tracker&utm_medium=cta, so a
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
        "function add_query_arg($a, $u) { return $u . (strpos($u, '?') === false ? '?' : '&') . http_build_query($a); }\n"
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
        self.assertEqual(q, {"utm_source": "layoff_tracker", "utm_medium": "cta",
                             "utm_campaign": "directory"})

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


class Placement(unittest.TestCase):

    def test_index_hub_carries_it_after_the_lede(self):
        src = INDEX.read_text(encoding="utf-8")
        self.assertIn("alt_atr_cta_line_html('directory')", src)
        self.assertLess(src.index("alt-company-index-lede"),
                        src.index("alt_atr_cta_line_html('directory')"))

    def test_company_page_carries_it_with_the_name(self):
        src = COMPANY.read_text(encoding="utf-8")
        self.assertIn("alt_atr_cta_line_html('company_entry', $alt_label)", src)
        self.assertLess(src.index("alt-company-summary"),
                        src.index("alt_atr_cta_line_html('company_entry'"))

    def test_calls_are_ftp_race_guarded(self):
        for path in (INDEX, COMPANY):
            self.assertIn("function_exists('alt_atr_cta_line_html')",
                          path.read_text(encoding="utf-8"), path.name)

    def test_main_file_loads_it_guarded(self):
        src = MAIN.read_text(encoding="utf-8")
        self.assertIn("includes/atr-signup-cta.php", src)


if __name__ == "__main__":
    unittest.main()
