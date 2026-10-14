"""Server-rendered "Related" link row on every tracker shortcode page (#446 item 4).

Owner ruling 2026-10-14: ONE map in code. Dashboard -> Methodology, Data
Sources, Tracker; Registry -> Tracker; Tracker -> Dashboard, Registry,
Methodology; every page -> Data Sources (except the Sources page itself, which
cannot link to itself). The row is plain HTML from alt_template(), so a crawler
and a no-JS reader both see it.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "related-links.php"
SHORTCODES = PLUGIN / "includes" / "shortcodes.php"
MAIN = PLUGIN / "ai-layoff-tracker.php"

BASE = "https://example.org/blog/"


def _php(call, *args):
    src = MOD.read_text(encoding="utf-8")
    funcs = re.findall(r"\nfunction alt_related_[a-z_]+\s*\(.*?\n\}", src, re.S)
    code = ("function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function esc_url($s){ return (string)$s; }\n"
            + "\n".join(funcs) + "\n" + call)
    p = subprocess.run(["php", "-r", code, "--", *[json.dumps(a) for a in args]],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return p.stdout


def links(template):
    out = _php("echo alt_related_links_html(json_decode($argv[1]), json_decode($argv[2]));", template, BASE)
    return re.findall(r'<a href="([^"]+)">([^<]+)</a>', out), out


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class OwnerMap(unittest.TestCase):
    def hrefs(self, template):
        return [h for h, _ in links(template)[0]]

    def test_dashboard(self):
        self.assertEqual(self.hrefs("page-dashboard.php"), [
            BASE + "ai-layoff-tracker/methodology/",
            BASE + "ai-layoff-tracker/sources/",
            BASE + "ai-layoff-tracker/"])

    def test_registry(self):
        self.assertEqual(self.hrefs("page-us-registry.php"), [
            BASE + "ai-layoff-tracker/", BASE + "ai-layoff-tracker/sources/"])

    def test_tracker(self):
        self.assertEqual(self.hrefs("page-tracker.php"), [
            BASE + "ai-layoffs-dashboard/",
            BASE + "ai-layoff-tracker/us-warn-registry/",
            BASE + "ai-layoff-tracker/methodology/",
            BASE + "ai-layoff-tracker/sources/"])

    def test_every_mapped_page_links_sources_except_sources(self):
        mapped = json.loads(_php("echo json_encode(alt_related_links_map());"))
        self.assertGreaterEqual(len(mapped), 11)
        for tpl in mapped:
            hrefs = self.hrefs(tpl)
            with self.subTest(tpl=tpl):
                self.assertTrue(hrefs, "every mapped page renders a row")
                self.assertEqual(len(hrefs), len(set(hrefs)), "no duplicate links")
                if tpl == "page-sources.php":
                    self.assertNotIn(BASE + "ai-layoff-tracker/sources/", hrefs)
                else:
                    self.assertIn(BASE + "ai-layoff-tracker/sources/", hrefs)

    def test_every_secondary_page_is_mapped(self):
        mapped = json.loads(_php("echo json_encode(alt_related_links_map());"))
        for tpl in re.findall(r"=> array\('(page-[a-z-]+\.php)'", SHORTCODES.read_text(encoding="utf-8")):
            self.assertIn(tpl, mapped)

    def test_markup_is_a_labelled_nav_with_no_em_dash(self):
        _, out = links("page-dashboard.php")
        self.assertRegex(out, r'<nav class="alt-related" aria-label="Related pages"')
        self.assertIn(">Methodology<", out)
        self.assertIn(">Data Sources<", out)
        self.assertNotIn("—", out)

    def test_unmapped_template_renders_nothing(self):
        self.assertEqual(links("page-widget.php")[1].strip(), "")

    def test_insert_lands_inside_main_or_appends(self):
        out = _php("echo alt_related_insert('<main class=\"alt-wrap\">x</main>', '<nav>R</nav>');")
        self.assertEqual(out, '<main class="alt-wrap">x<nav>R</nav></main>')
        out = _php("echo alt_related_insert('<div>x</div>', '<nav>R</nav>');")
        self.assertEqual(out, '<div>x</div><nav>R</nav>')


class Wiring(unittest.TestCase):
    def test_template_funnel_appends_the_row_and_module_is_loaded(self):
        self.assertIn("alt_related_links_template", SHORTCODES.read_text(encoding="utf-8"))
        self.assertIn("includes/related-links.php", MAIN.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
