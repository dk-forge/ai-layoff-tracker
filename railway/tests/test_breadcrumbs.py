"""Visible breadcrumbs (owner request 2026-10-12).

The visible trail and the BreadcrumbList JSON-LD come from ONE trail, so a
reader and a crawler can never be told different paths. Ancestors are links,
the current page is plain text with aria-current, and no section crumb points
at a URL that 404s (/state-layoffs/ etc. do not exist).
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "breadcrumbs.php"

STUBS = r"""
define('ABSPATH', '/');
function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function esc_url($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function wp_json_encode($v, $f = 0){ return json_encode($v, $f); }
function home_url($p = '/'){ return 'https://example.org/blog' . $p; }
function add_filter(){}
function add_action(){}
"""


def _php(expr):
    src = MOD.read_text(encoding="utf-8").replace("<?php", "", 1)
    p = subprocess.run(["php", "-r", STUBS + src + "\n" + expr], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Trail(unittest.TestCase):
    FACET = "$d = array('dim' => 'state', 'url' => 'https://example.org/blog/state-layoffs/texas/');" \
            "$t = alt_breadcrumbs_facet_trail($d, 'Layoffs in Texas');"

    def test_visible_matches_jsonld(self):
        html = _php(self.FACET + "echo alt_breadcrumbs_html($t);")
        ld = json.loads(re.search(r">(\{.*\})</script>", _php(self.FACET + "echo alt_breadcrumbs_jsonld($t);")).group(1))
        names = [i["name"] for i in ld["itemListElement"]]
        self.assertEqual(names, ["Blog", "AI Layoff Tracker", "US states", "Layoffs in Texas"])
        for n in names:
            self.assertIn(n, html)
        hrefs = re.findall(r'<a href="([^"]+)"', html)
        self.assertEqual(hrefs, [i["item"] for i in ld["itemListElement"]][:-1])

    def test_markup(self):
        html = _php(self.FACET + "echo alt_breadcrumbs_html($t);")
        self.assertIn('<nav class="alt-breadcrumbs" aria-label="Breadcrumb">', html)
        self.assertIn('<span aria-current="page">Layoffs in Texas</span>', html)
        self.assertNotIn('href="https://example.org/blog/state-layoffs/texas/"', html)
        self.assertIn("flex-wrap:wrap", html)

    def test_no_section_crumb_links_to_a_missing_index(self):
        for dim in ("state", "country", "industry"):
            out = _php("$t = alt_breadcrumbs_facet_trail(array('dim' => '%s', 'url' => 'u'), 'X');"
                       "echo json_encode($t);" % dim)
            for c in json.loads(out)[:-1]:
                self.assertNotRegex(c["url"], r"/(state|country|industry)-layoffs/")

    def test_escapes(self):
        out = _php("echo alt_breadcrumbs_html(alt_breadcrumbs_company_trail('<b>A&B</b> layoffs', 'u'));")
        self.assertIn("&lt;b&gt;A&amp;B&lt;/b&gt;", out)

    def test_single_item_renders_nothing(self):
        self.assertEqual(_php("echo alt_breadcrumbs_html(array(array('name' => 'x', 'url' => 'y')));"), "")


class Wiring(unittest.TestCase):
    def test_jsonld_emitters_use_the_shared_trail(self):
        for f, fn in (("facet-pages.php", "alt_breadcrumbs_facet_trail"),
                      ("company-directory.php", "alt_breadcrumbs_company_trail")):
            src = (PLUGIN / "includes" / f).read_text(encoding="utf-8")
            self.assertIn("alt_breadcrumbs_jsonld(" + fn, src, f)
            self.assertNotIn("'@type'    => 'BreadcrumbList'", src, f)

    def test_templates_render_the_trail(self):
        for name in ("page-facet.php", "page-company-directory.php", "page-company-index.php", "single-layoff.php"):
            self.assertIn("alt_breadcrumbs_render(", (PLUGIN / "templates" / name).read_text(encoding="utf-8"), name)

    def test_blog_trail_never_adds_jsonld(self):
        src = MOD.read_text(encoding="utf-8")
        start = src.index("function alt_breadcrumbs_blog_html")
        body = src[start:src.index("\nfunction ", start + 1)]
        self.assertNotIn("alt_breadcrumbs_jsonld", body)


if __name__ == "__main__":
    unittest.main()


class EveryPage(unittest.TestCase):
    """2026-10-12 follow-up: shortcode pages (sources, methodology, ai-quotes,
    press, publisher tools, health, US WARN registry), the email archive,
    author, search and 404 had no visible trail; tracker routes carried Rank
    Math's one-item "Home" BreadcrumbList beside ours."""

    def test_fallbacks_exist(self):
        src = MOD.read_text(encoding="utf-8")
        self.assertIn("add_filter('the_content', 'alt_breadcrumbs_content_fallback', 12)", src)
        self.assertIn("add_filter('rank_math/json_ld'", src)
        for cond in ("is_author()", "is_search()", "is_404()"):
            self.assertIn(cond, src)

    def test_editions_render_and_emit_the_trail(self):
        self.assertIn("alt_breadcrumbs_render(alt_breadcrumbs_edition_trail(",
                      (PLUGIN / "templates" / "page-editions.php").read_text(encoding="utf-8"))
        src = MOD.read_text(encoding="utf-8")
        self.assertIn("alt_edition_is_index_request", src)

    @unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
    def test_insert_inside_alt_wrap(self):
        out = _php("echo alt_breadcrumbs_insert('<main class=\"alt-wrap x\"><h1>T</h1></main>', '<nav>B</nav>');")
        self.assertEqual(out, '<main class="alt-wrap x"><nav>B</nav><h1>T</h1></main>')
        self.assertEqual(_php("echo alt_breadcrumbs_insert('<p>x</p>', '<nav>B</nav>');"), "<nav>B</nav><p>x</p>")

    @unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
    def test_in_content_rank_math_trail_is_removed(self):
        html = ('<p>a</p><nav aria-label="breadcrumbs" class="rank-math-breadcrumb"><p><a href="h">Home</a>'
                '<span class="last">X</span></p></nav><p>b</p>')
        self.assertEqual(_php("echo alt_breadcrumbs_strip_content_trail(%s);" % json.dumps(html)), "<p>a</p><p>b</p>")

    @unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
    def test_rank_math_list_dropped_only_when_ours(self):
        d = ("$d = array('BreadcrumbList' => array('@type' => 'BreadcrumbList'),"
             " 'WebPage' => array('@type' => 'WebPage', 'breadcrumb' => array('@id' => 'b')));")
        out = json.loads(_php(d + "echo json_encode(alt_breadcrumbs_strip_rank_math($d, true));"))
        self.assertNotIn("BreadcrumbList", out)
        self.assertNotIn("breadcrumb", out["WebPage"])
        self.assertIn("BreadcrumbList", json.loads(_php(d + "echo json_encode(alt_breadcrumbs_strip_rank_math($d, false));")))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class ShortcodePageFallback(unittest.TestCase):
    """The sources page (and every shortcode page) has no title block, so the
    trail must come from the content fallback, once, inside alt-wrap."""
    WP = ("function is_admin(){return false;} function is_feed(){return false;} function is_singular($t=null){return $t===null;}"
          " function is_front_page(){return false;} function get_the_ID(){return 7;} function get_queried_object_id(){return 7;}"
          " function rank_math_get_breadcrumbs(){return '<nav aria-label=\"breadcrumbs\" class=\"rank-math-breadcrumb\"><p>"
          "<a href=\"h\">Home</a><span class=\"last\">Data Sources</span></p></nav>';}")

    def test_sources_page_gets_one_trail(self):
        out = _php(self.WP + "$c = '<main class=\"alt-wrap alt-sources-page\"><h1>Data Sources</h1></main>';"
                   "$a = alt_breadcrumbs_content_fallback($c); echo $a, '|', alt_breadcrumbs_content_fallback($c);")
        first, second = out.split("|")
        self.assertTrue(first.startswith('<main class="alt-wrap alt-sources-page"><nav aria-label="breadcrumbs"'))
        self.assertIn('aria-current="page">Data Sources', first)
        self.assertEqual(second.count("rank-math-breadcrumb\">"), 0)
