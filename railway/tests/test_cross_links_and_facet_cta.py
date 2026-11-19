"""todo#1881 items 1 and 5: a sign-up line on every facet page, and links to
the same company, country or sector in the hiring tracker (navigation only)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
DATA = json.loads((PLUGIN / "data" / "cross-links.json").read_text())
SRC = (PLUGIN / "includes" / "cross-links.php").read_text()
CTA = (PLUGIN / "includes" / "atr-signup-cta.php").read_text()
FACET = (PLUGIN / "templates" / "page-facet.php").read_text()
COMPANY = (PLUGIN / "templates" / "page-company-directory.php").read_text()
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text()


class Data(unittest.TestCase):
    def test_ambiguous_slugs_are_left_out(self):
        for slug in ("one", "coop", "bull", "nec", "pandora", "toast"):
            self.assertNotIn(slug, DATA["companies"])

    def test_known_overlaps_are_present(self):
        for slug in ("amazon", "hsbc", "microsoft"):
            self.assertIn(slug, DATA["companies"])
        for slug in ("germany", "united-kingdom", "india"):
            self.assertIn(slug, DATA["countries"])

    def test_industry_targets_are_tit_slugs_with_labels(self):
        for alt_slug, targets in DATA["industries"].items():
            for slug, label in targets:
                self.assertRegex(slug, r"^[a-z0-9-]+$")
                self.assertTrue(label)


class NoPairedFigures(unittest.TestCase):
    def test_link_text_carries_no_number(self):
        html_fn = SRC[SRC.index("function alt_cross_links_html"):]
        self.assertNotRegex(html_fn, r"number_format|\bjobs\b|cut")

    def test_wired_guarded(self):
        self.assertIn("is_readable($alt_cross_links)", MAIN)
        self.assertIn("function_exists('alt_cross_links_html')", FACET)
        self.assertIn("function_exists('alt_cross_links_html')", COMPANY)


class FacetCta(unittest.TestCase):
    def test_facet_page_prints_the_contextual_line(self):
        self.assertIn("alt_atr_cta_facet_html($alt_f['dim'], $alt_f['display'])", FACET)

    def test_contextual_line_names_the_place_and_tags_it(self):
        fn = CTA[CTA.index("function alt_atr_cta_facet_html"):]
        fn = fn[:fn.index("\n}\n")]
        self.assertIn("Affected by a layoff", fn)
        self.assertIn("utm_content", fn)
        self.assertIn("alt_atr_cta_url('facet_' . $dim)", fn)
        self.assertIn("Free, no card.", fn)

    @unittest.skipUnless(shutil.which("php"), "php CLI not installed: UNKNOWN, NOT RUN")
    def test_renders(self):
        php = r'''
define("ABSPATH", 1); define("ALT_PLUGIN_DIR", "%s/");
function esc_html($s){return htmlspecialchars($s);} function esc_url($s){return $s;}
function sanitize_title($s){return trim(preg_replace('/[^a-z0-9]+/','-',strtolower($s)),'-');}
function home_url($p=''){return 'https://asktherecruiter.com/blog'.$p;}
function add_query_arg($a,$b=null,$c=null){ if(is_array($a)){return $b.'?'.http_build_query($a);} return $c.'&'.$a.'='.$b; }
function alt_resume_cta_base(){return 'https://asktherecruiter.com';} function add_action(){}
require "%s/includes/cross-links.php"; require "%s/includes/atr-signup-cta.php";
echo alt_cross_links_html('company','amazon','Amazon'),"\n";
echo alt_cross_links_html('company','one','One'),"|\n";
echo alt_cross_links_html('industry','healthcare-pharma','Healthcare & pharma'),"\n";
echo alt_atr_cta_facet_html('country','Germany'),"\n";
''' % (PLUGIN, PLUGIN, PLUGIN)
        out = subprocess.run(["php", "-r", php], capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertIn('href="https://asktherecruiter.com/blog/talent-intelligence-tracker/company/amazon/"', out[0])
        self.assertEqual(out[1], "|")
        self.assertIn("industry/healthcare/", out[2])
        self.assertIn("industry/pharma-and-biotech/", out[2])
        self.assertIn("Affected by a layoff in Germany?", out[3])
        self.assertIn("utm_source=ai-layoff-tracker", out[3])
        self.assertIn("utm_content=germany", out[3])


if __name__ == "__main__":
    unittest.main()
