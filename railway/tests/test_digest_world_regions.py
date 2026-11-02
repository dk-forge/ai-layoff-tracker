"""Biggest cuts grouped by world region (owner request 2026-11-02).

The layoff edition's "Biggest cuts" list is grouped by region in a fixed
order (North America, Europe, Middle East, Asia-Pacific, Latin America,
Africa, Other) under one section title, then by country (flag + name), then
by US state where known, then by city (pin) when a city exists.

Pure functions are driven straight from includes/digest-regions.php; the
end-to-end cases go through the real composer harness. Without php on PATH
these SKIP, which is not a pass.
"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from test_digest_talent_activity import compose, PHP  # noqa: E402
from test_digest_dimension_blocks import layoff_fixture  # noqa: E402

REGIONS_PHP = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker", "includes",
    "digest-regions.php"))

_RUNNER = r"""
define('ABSPATH', '/tmp/');
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
require $argv[1];
$in = json_decode($argv[2], true);
$out = array();
foreach ($in['countries'] as $c) {
    $out['region'][] = alt_digest_world_region($c);
    $out['flag'][] = alt_digest_country_flag($c);
}
$groups = alt_digest_group_by_world_region($in['rows']);
$out['groups'] = $groups;
echo json_encode($out);
"""


def run_pure(countries=(), rows=()):
    run = subprocess.run(
        [PHP, "-r", _RUNNER, "--", REGIONS_PHP,
         json.dumps({"countries": list(countries), "rows": list(rows)})],
        capture_output=True, text=True, timeout=60)
    if run.returncode != 0:
        raise AssertionError(run.stderr[:1200] or run.stdout[:1200])
    return json.loads(run.stdout)


def row(label, country="", state="", city=""):
    return {"label": label, "geo": {"country": country, "state": state, "city": city}}


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class PureGrouping(unittest.TestCase):

    def test_region_of_each_bucket(self):
        got = run_pure(["United States", "Canada", "Germany", "United Kingdom",
                        "Israel", "India", "Brazil", "Nigeria", "Atlantis",
                        "", "Multiple countries", "Türkiye", "Mexico"])["region"]
        self.assertEqual(got, ["North America", "North America", "Europe", "Europe",
                               "Middle East", "Asia-Pacific", "Latin America",
                               "Africa", "Other", "Other", "Other", "Middle East",
                               "Latin America"])

    def test_flags(self):
        got = run_pure(["United States", "Germany", "United Kingdom", "Japan",
                        "Atlantis", ""])["flag"]
        self.assertEqual(got, ["\U0001F1FA\U0001F1F8", "\U0001F1E9\U0001F1EA",
                               "\U0001F1EC\U0001F1E7", "\U0001F1EF\U0001F1F5",
                               "", ""])

    def test_fixed_region_order_us_first_then_europe(self):
        rows = [row("Tokyo Co", "Japan"), row("Berlin Co", "Germany"),
                row("Nowhere Co"), row("Lagos Co", "Nigeria"),
                row("Austin Co", "United States", "TX", "Austin"),
                row("Dubai Co", "United Arab Emirates"), row("Rio Co", "Brazil")]
        groups = run_pure(rows=rows)["groups"]
        self.assertEqual([g["region"] for g in groups],
                         ["North America", "Europe", "Middle East", "Asia-Pacific",
                          "Latin America", "Africa", "Other"])

    def test_us_country_first_in_north_america_and_states_grouped(self):
        rows = [row("Toronto Co", "Canada", "", "Toronto"),
                row("A", "United States", "CA", "San Jose"),
                row("B", "United States", "TX", ""),
                row("C", "United States", "CA", "")]
        na = run_pure(rows=rows)["groups"][0]
        self.assertEqual([c["country"] for c in na["countries"]],
                         ["United States", "Canada"])
        us = na["countries"][0]
        self.assertEqual([s["state"] for s in us["states"]], ["CA", "TX"])
        ca_rows = us["states"][0]["rows"]
        self.assertEqual([r["label"] for r in ca_rows], ["A", "C"])

    def test_missing_city_and_state_kept(self):
        groups = run_pure(rows=[row("X", "Germany")])["groups"]
        country = groups[0]["countries"][0]
        self.assertEqual(country["states"][0]["state"], "")
        self.assertEqual(country["states"][0]["rows"][0]["label"], "X")

    def test_unknown_country_goes_to_other(self):
        groups = run_pure(rows=[row("Y", "Atlantis")])["groups"]
        self.assertEqual(groups[0]["region"], "Other")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class ComposedEmail(unittest.TestCase):

    def fixture(self):
        f = layoff_fixture()
        f["layoff"]["leaders"] = [
            {"company_name": "Berlin Werk", "job_count": 3000, "layoff_date": "2026-08-12",
             "location": "Berlin", "state": "", "country": "Germany", "permalink": "",
             "announced": False, "source_url": ""},
            {"company_name": "Texas Foods", "job_count": 900, "layoff_date": "2026-08-12",
             "location": "TX", "state": "TX", "country": "United States", "permalink": "",
             "announced": False, "source_url": ""},
            {"company_name": "Mystery Ltd", "job_count": 50, "layoff_date": "2026-08-12",
             "location": "", "state": "", "country": "", "permalink": "",
             "announced": False, "source_url": ""},
        ]
        return f

    def test_html_has_title_and_order(self):
        html = compose(self.fixture())["html"]
        self.assertIn("Around the world", html)
        html = html.split("Around the world", 1)[1]
        na = html.index("North America")
        eu = html.index("Europe", na)
        self.assertLess(na, eu)
        self.assertLess(html.index("Texas Foods"), html.index("Berlin Werk"))
        self.assertIn("\U0001F1E9\U0001F1EA Germany", html)
        self.assertIn("\U0001F4CD Berlin", html)
        self.assertIn("Other", html)

    def test_text_part_grouped_too(self):
        text = compose(self.fixture())["text"]
        self.assertIn("Around the world", text)
        block = text.split("Biggest cuts", 1)[1]
        self.assertLess(block.index("North America"), block.index("Europe"))
        self.assertLess(block.index("Texas Foods"), block.index("Berlin Werk"))
        self.assertIn("Texas", block)


if __name__ == "__main__":
    unittest.main()
