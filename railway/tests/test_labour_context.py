"""Labour-market context: the stored BLS/OECD reference data on the page.

Renders the REAL includes/labour-context.php and its template through
tests/fixtures/labour_context_harness.php (WordPress stubs, no network, no DB).

Pinned:
  * empty or missing source -> its panel is hidden; all missing -> no section,
    and never a PHP error;
  * each chart names its source under the chart and carries a data-as-of line;
  * the section says these are official aggregates, not tracker counts, and no
    copy implies AI caused anything;
  * facet stat blocks appear only on an EXACT industry/country match;
  * styles are token-only (dark mode) with a phone-width rule, and the charts
    repaint on alt:themechange.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
HARNESS = Path(__file__).resolve().parent / "fixtures/labour_context_harness.php"
PHP = shutil.which("php")
CSS = (PLUGIN / "assets/layoffs.css").read_text()
JS = (PLUGIN / "assets/labour-context.js").read_text()
TEMPLATE = (PLUGIN / "templates/partials/labour-context.php").read_text()
MODULE = (PLUGIN / "includes/labour-context.php").read_text()

BLS = {
    "source": "bls_jolts_cps", "updated": "2026-10-04T12:00:00+00:00",
    "latest": {"jolts": "2026-08", "cps": "2026-09"}, "rows": 6, "attribution": "x",
    "datasets": {
        "jolts": {
            "JTS300000000000000LDL": {"measure": "layoffs_discharges", "unit": "thousands", "dim": "industry",
                                      "naics": "300000", "label": "Manufacturing", "geo": "US",
                                      "points": [["2026-07", 80, ""], ["2026-08", 92, "P"]]},
            "JTS300000000000000JOL": {"measure": "openings", "unit": "thousands", "dim": "industry",
                                      "naics": "300000", "label": "Manufacturing", "geo": "US",
                                      "points": [["2026-08", 400, "P"]]},
        },
        "cps": {
            "LNS14000000": {"measure": "unemployment_rate", "dim": "total", "label": "16 years and over",
                            "points": [["2026-09", 4.3, ""]]},
            "LNS14000001": {"measure": "unemployment_rate", "dim": "sex", "label": "Men, 16 years and over",
                            "points": [["2026-09", 4.4, ""]]},
        },
    },
}
OECD = {
    "source": "oecd_unemployment", "updated": "2026-10-03T00:00:00+00:00",
    "latest": {"monthly": "2026-08"}, "rows": 2, "attribution": "y",
    "datasets": {"monthly": {"DEU": {"_T|Y_GE15": [["2026-07", 3.6], ["2026-08", 3.7]]},
                             "USA": {"_T|Y_GE15": [["2026-08", 4.3]]}}},
}
OPTS = {"alt_ref_bls_jolts_cps": BLS, "alt_ref_oecd_unemployment": OECD}


@unittest.skipUnless(PHP, "php not installed")
class RenderTests(unittest.TestCase):
    def run_php(self, opts, *args):
        proc = subprocess.run([PHP, str(HARNESS), str(PLUGIN) + "/", json.dumps(opts), *args],
                              capture_output=True, text=True, timeout=60)
        out = json.loads(proc.stdout)
        self.assertNotIn("error", out, out.get("error"))
        return out["html"]

    def test_full_data_renders_three_panels_with_attribution_and_asof(self):
        html = self.run_php(OPTS, "section")
        for lc in ("jolts", "cps", "oecd"):
            self.assertIn(f'data-lc="{lc}"', html)
        self.assertEqual(html.count("Source: U.S. Bureau of Labor Statistics"), 2)
        self.assertIn("Source: OECD (CC BY 4.0)", html)
        self.assertIn("Data through August 2026", html)
        self.assertIn("Data through September 2026", html)
        self.assertIn("not the tracker's own counts", html)
        self.assertIn('<option value="Manufacturing">', html)
        self.assertIn('value="sex"', html)
        self.assertIn(">Germany<", html)

    def test_no_data_hides_the_section_without_error(self):
        html = self.run_php({}, "section")
        self.assertNotIn("<section", html)

    def test_malformed_or_empty_source_hides_only_its_panel(self):
        html = self.run_php({"alt_ref_bls_jolts_cps": "garbage", "alt_ref_oecd_unemployment": OECD}, "section")
        self.assertNotIn('data-lc="jolts"', html)
        self.assertNotIn('data-lc="cps"', html)
        self.assertIn('data-lc="oecd"', html)
        html = self.run_php({"alt_ref_bls_jolts_cps": BLS, "alt_ref_oecd_unemployment": {"datasets": {}}}, "section")
        self.assertIn('data-lc="jolts"', html)
        self.assertNotIn('data-lc="oecd"', html)

    def test_industry_stat_only_on_exact_match(self):
        html = self.run_php(OPTS, "stat", "industry", "Manufacturing")
        self.assertIn("92,000", html)
        self.assertIn("not our count", html)
        self.assertIn("United States only", html)
        self.assertEqual(self.run_php(OPTS, "stat", "industry", "Technology"), "")
        self.assertEqual(self.run_php(OPTS, "stat", "industry", "manufacturing"), "")
        self.assertEqual(self.run_php({}, "stat", "industry", "Manufacturing"), "")

    def test_country_stat_only_on_exact_match(self):
        html = self.run_php(OPTS, "stat", "country", "Germany")
        self.assertIn("3.7%", html)
        self.assertIn("August 2026", html)
        self.assertIn("Source: OECD (CC BY 4.0)", html)
        self.assertEqual(self.run_php(OPTS, "stat", "country", "France"), "")  # no data
        self.assertEqual(self.run_php(OPTS, "stat", "country", "Narnia"), "")
        self.assertEqual(self.run_php(OPTS, "stat", "state", "CA"), "")


class CopyAndSurfaceTests(unittest.TestCase):
    def test_no_causal_or_em_dash_copy(self):
        for text in (TEMPLATE, MODULE):
            self.assertNotIn("—", text)
            self.assertIsNone(re.search(r"\b(due to|because of|caused by|driven by) AI\b", text, re.I))
        self.assertIn("do not show that AI caused", TEMPLATE)

    def test_styles_are_token_only_with_a_phone_rule(self):
        block = CSS.split("/* Labour-market context")[1]
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,6}\b", block), "use --alt-* tokens so dark mode follows")
        self.assertIn("@media (max-width: 600px)", block)

    def test_charts_read_tokens_and_repaint_on_theme_change(self):
        self.assertIn("alt:themechange", JS)
        self.assertIn("'--alt-' + name", JS)

    def test_wired_into_sources_and_facet_pages(self):
        self.assertIn("alt_shortcode_labour_context()", (PLUGIN / "templates/page-sources.php").read_text())
        self.assertIn("alt_labour_context_stat(", (PLUGIN / "templates/page-facet.php").read_text())
        boot = (PLUGIN / "ai-layoff-tracker.php").read_text()
        self.assertIn("includes/labour-context.php", boot)
        self.assertIn("assets/labour-context.js", boot)


if __name__ == "__main__":
    unittest.main()
