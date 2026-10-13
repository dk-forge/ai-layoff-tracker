"""Every company / country / state / industry page shows when the data last
changed and how many distinct sources back it, and its Dataset node carries
dateModified plus a CSV distribution (SEO audit 2026-10-13, items 1 and 3).

The helper is pure, so it is executed under the local PHP binary when one is
present; the wiring checks are static, like test_facet_pages.py.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
HELPER = PLUGIN / "includes/page-freshness.php"


def _php(code):
    out = subprocess.run(["php", "-r", code], capture_output=True, text=True, check=True)
    return out.stdout


class WiringTests(unittest.TestCase):
    def test_helper_is_loaded(self):
        boot = (PLUGIN / "ai-layoff-tracker.php").read_text()
        self.assertIn("require_once ALT_PLUGIN_DIR . 'includes/page-freshness.php';", boot)

    def test_both_templates_render_the_line(self):
        for t in ("page-company-directory.php", "page-facet.php"):
            self.assertIn("alt_page_freshness_html(", (PLUGIN / "templates" / t).read_text(), t)

    def test_both_dataset_nodes_get_the_fields(self):
        for f in ("company-directory.php", "facet-pages.php"):
            self.assertIn("alt_page_dataset_freshness(", (PLUGIN / "includes" / f).read_text(), f)


class CreditTests(unittest.TestCase):
    def test_warn_scraper_is_credited_with_its_licence(self):
        for f in (PLUGIN / "templates/page-sources.php", ROOT / "README.md"):
            t = f.read_text()
            self.assertIn("github.com/biglocalnews/warn-scraper", t, f)
            self.assertIn("Big Local News", t, f)
            self.assertIn("Apache License 2.0", t, f)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: no php binary")
class BehaviourTests(unittest.TestCase):
    STUB = (
        "function esc_html($s){return htmlspecialchars($s);}"
        "function esc_url($s){return $s;}"
        "function admin_url($p){return 'https://x.example/blog/wp-admin/'.$p;}"
        "function get_option($k,$d=0){return 1760000000;}"
        "function alt_data_last_updated_label(){return 'Oct 9, 2025';}"
        f"require '{HELPER}';"
    )

    def test_counts_distinct_source_urls_only(self):
        code = self.STUB + (
            "$e=array(array('sources'=>array(array('url'=>'https://a.example/1'),array('url'=>'https://a.example/1'))),"
            "array('sources'=>array(array('url'=>'https://b.example/2'),array('url'=>''))),array());"
            "echo alt_page_source_count($e);"
        )
        self.assertEqual(_php(code), "2")

    def test_line_names_date_and_sources(self):
        code = self.STUB + "echo alt_page_freshness_html(array(array('sources'=>array(array('url'=>'https://a.example/1')))));"
        html = _php(code)
        self.assertIn("Last updated", html)
        self.assertIn("Oct 9, 2025", html)
        self.assertIn("1 source", html)
        self.assertNotIn("1 sources", html)
        self.assertNotIn("—", html)  # no em-dashes in UI copy

    def test_no_line_without_sources(self):
        self.assertEqual(_php(self.STUB + "echo alt_page_freshness_html(array());"), "")

    def test_dataset_fields(self):
        fields = json.loads(_php(self.STUB + "echo json_encode(alt_page_dataset_freshness());"))
        self.assertRegex(fields["dateModified"], r"^\d{4}-\d{2}-\d{2}$")
        dist = fields["distribution"][0]
        self.assertEqual(dist["@type"], "DataDownload")
        self.assertEqual(dist["encodingFormat"], "text/csv")
        self.assertIn("alt_export_csv", dist["contentUrl"])


if __name__ == "__main__":
    unittest.main()
