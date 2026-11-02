"""The talent briefing (includes/digest-talent-briefing.php) and its checks.

Same contract as the layoff briefing: rule-based text, region rows that sum
to the total (unknowns included), links on the same window, and any claim
whose numbers do not reconcile is HELD (omitted and logged), never sent.

The country basis is the aggregate's own (signal country, else employer HQ):
Week 44 2026 read 91 US signals by `country` alone against 161 in
/talent/v1/aggregate, and a check now fails if the two ever disagree.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
import html as html_mod

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")
FROM, TO = "2026-10-26", "2026-11-01"


def sig(i, company, country="US", hq="", direction="hiring", headcount=None,
        industry="technology", city=""):
    return {"signal_id": f"s{i}", "company": company, "country": country,
            "hq_country": hq, "signal_direction": direction,
            "headcount": None if headcount is None else str(headcount),
            "industry": industry, "city": city, "state": "TX",
            "source_name": "Reporter", "source_url": "https://example.com/a",
            "materiality": "high"}


def fixture():
    rows = [sig(1, "Walmart", headcount=425, city="San Antonio"),
            sig(2, "Konza", country="KE", headcount=10000),
            sig(3, "Acme UK", country="GB", direction="neutral"),
            sig(4, "Dutch Co", country="NL", direction="neutral"),
            sig(5, "HQ Only", country="", hq="US", direction="neutral"),
            sig(6, "Nowhere", country="", hq="", direction="neutral")]
    agg = {"total": 6, "companies": 6, "stated_headcount": 2,
           "by_direction": [{"k": "hiring", "n": "2"}, {"k": "neutral", "n": "4"}],
           "by_country": [{"k": "US", "n": "2"}, {"k": "KE", "n": "1"},
                          {"k": "GB", "n": "1"}, {"k": "NL", "n": "1"}]}
    weeks = {}
    # The talent stub keys the window by `since`; earlier weeks answer from
    # talent_ytd, which is one payload for all seven.
    return {"from": FROM, "to": TO, "freq": "weekly", "compose": "talent",
            "options": {"alt_digest_talent_briefing_tiers": "daily,weekly,monthly"},
            "talent": agg, "talent_q": {"total": 6, "rows": rows},
            "talent_ytd": {"total": 5, "by_country": []}, "talent_geo": agg}


def compose(fx):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as h:
        json.dump(fx, h)
    try:
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, h.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(h.name)
    if run.returncode != 0:
        raise AssertionError(run.stderr[:1500])
    out = json.loads(run.stdout)
    out["stderr"] = run.stderr
    return out


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TalentBriefing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(fixture())
        cls.text = cls.out["text"]

    def test_checks_pass(self):
        self.assertEqual(self.out["held"], [])
        self.assertEqual(self.out["checks"]["countries_match_aggregate"], "PASS")

    def test_regions_sum_and_sub_lines(self):
        block = self.text.split("By region:")[1].split("Provisional")[0]
        rows = re.findall(r"^\s{4}(\S.*): ([\d,]+)$", block, re.M)
        self.assertEqual(sum(int(n) for _, n in rows), 6)
        self.assertIn("North America (US 2): 2", block)
        self.assertIn("Europe (UK 1 · Netherlands 1): 2", block)
        self.assertIn("Africa: 1", block)
        self.assertIn("Not recorded: 1", block)

    def test_sections_and_unit(self):
        for needle in ("Who's hiring", "This week at a glance", "Three things worth knowing",
                       "Biggest hiring this week (Oct 26 - Nov 1)", "Around the world",
                       "Last 8 weeks", "Explore the data"):
            self.assertIn(needle, self.text)
        self.assertIn("talent and employer-activity signals", self.out["metric"])
        self.assertNotIn(" jobs", self.text)

    def test_links_name_the_window(self):
        urls = [html_mod.unescape(u) for u in re.findall(r'href="([^"]+)"', self.out["html"])]
        urls = [u for u in urls if "/talent-intelligence-tracker/?" in u]
        self.assertTrue(urls)
        for u in urls:
            q = parse_qs(urlparse(u).query)
            self.assertEqual((q["since"], q["until"]), ([FROM], [TO]), u)

    def test_house_style(self):
        body = self.text + self.out["html"]
        self.assertNotRegex(body, "[\u2013\u2014]")
        for word in ("bl" + "ind", "hon" + "est", "halluc" + "inat"):
            self.assertNotIn(word, body.lower())


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TalentHolds(unittest.TestCase):

    def test_country_disagreement_holds_geography(self):
        fx = fixture()
        fx["talent"]["by_country"][0]["n"] = "9"
        out = compose(fx)
        self.assertEqual(out["checks"]["countries_match_aggregate"], "FAIL")
        self.assertNotIn("By region:", out["text"])
        self.assertIn("[alt-talent-briefing] held geography", out["stderr"])

    def test_row_count_mismatch_holds_geography(self):
        fx = fixture()
        fx["talent"]["total"] = 7
        out = compose(fx)
        self.assertEqual(out["checks"]["rows_reconcile"], "FAIL")
        self.assertNotIn("Biggest hiring", out["text"])

    def test_switch_off_keeps_the_old_composer(self):
        fx = fixture()
        fx["options"]["alt_digest_talent_briefing_tiers"] = "none"
        out = compose(fx)
        self.assertNotIn("Three things worth knowing", out.get("text", ""))


if __name__ == "__main__":
    unittest.main()
