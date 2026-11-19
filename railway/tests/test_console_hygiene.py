"""todo#1881 item 8: the interactivity import map on virtual routes, and the 90-day label."""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text()
TPL = (PLUGIN / "templates" / "page-tracker.php").read_text()


def body(src, name):
    m = re.search(r"function %s\([^)]*\)\s*\{" % re.escape(name), src)
    i, depth = m.end(), 1
    while depth:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
    return src[m.end():i]


class TemplatePartsRenderBeforeTheImportMap(unittest.TestCase):
    def test_header_and_footer_render_before_wp_head(self):
        h = body(MAIN, "alt_render_page_header")
        wp_head = h.index("wp_head();")
        self.assertLess(h.index("block_template_part('header')"), wp_head)
        self.assertLess(h.index("block_template_part('footer')"), wp_head)
        self.assertIn("echo $alt_header_html;", h[wp_head:])

    def test_footer_prints_the_prerendered_part_once(self):
        f = body(MAIN, "alt_render_page_footer")
        self.assertIn("echo $GLOBALS['alt_prerendered_footer'];", f)
        self.assertIn("unset($GLOBALS['alt_prerendered_footer'])", f)
        self.assertLess(f.index("alt_prerendered_footer"), f.index("wp_footer();"))


JS = (PLUGIN / "assets" / "layoffs.js").read_text()


class HostLevel5xxIsRetried(unittest.TestCase):
    """The remaining 500s were the host's database-connection error page."""

    def test_html_5xx_and_cap_503_are_retried_json_errors_are_not(self):
        b = body(JS, "apiGet")
        self.assertIn("r.status === 503 && r.headers.get('Retry-After')", b)
        self.assertIn("Error establishing a database connection", b)  # only the DB page
        self.assertIn("r.clone().text()", b)
        self.assertIn("left <= 1) return Promise.resolve(0);", b)  # at most two host retries
        self.assertIn("Math.random()", b)


class NinetyDayLabel(unittest.TestCase):
    def test_d90_says_what_it_is(self):
        m = re.search(r'data-dp="d90">([^<]+)<', TPL)
        self.assertEqual(m.group(1), "Last 90 days")



class HeaderCtaUtm(unittest.TestCase):
    @unittest.skipUnless(__import__("shutil").which("php"), "php CLI not installed: UNKNOWN, NOT RUN")
    def test_header_cta_is_retagged_on_tracker_pages_only(self):
        import subprocess
        src = PLUGIN / "includes" / "header-cta-utm.php"
        php = ('define("ABSPATH", 1); function add_filter() {} require "%s";'
               'echo alt_header_cta_retag(\'<a href="https://asktherecruiter.com/resume-score?utm_source=blog&#038;utm_medium=nav&#038;utm_campaign=header-cta">\'), "\\n";'
               'echo alt_header_cta_retag(\'<a href="https://example.com/?utm_source=blog&amp;utm_medium=nav">\');' % src)
        out = subprocess.run(["php", "-r", php], capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertIn("utm_source=ai-layoff-tracker&#038;utm_medium=nav&#038;utm_campaign=header-cta", out[0])
        self.assertIn("utm_source=blog", out[1])
        text = src.read_text()
        self.assertIn("alt_page_needs_assets()", text)
        # Cheap test before the page predicate: the filter runs for every block.
        self.assertLess(text.index("strpos($block_content, 'utm_source=blog')"), text.index("alt_page_needs_assets()"))
        self.assertIn("$alt_header_html = alt_header_cta_retag($alt_header_html);", body(MAIN, "alt_render_page_header"))

if __name__ == "__main__":
    unittest.main()
