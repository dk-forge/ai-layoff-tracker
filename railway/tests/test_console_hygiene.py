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


class NinetyDayLabel(unittest.TestCase):
    def test_d90_says_what_it_is(self):
        m = re.search(r'data-dp="d90">([^<]+)<', TPL)
        self.assertEqual(m.group(1), "Last 90 days")


if __name__ == "__main__":
    unittest.main()
