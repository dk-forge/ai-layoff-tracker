"""Talent daily digest redesign (owner-approved 2026-10-12).

1. subject "Who's hiring today · N funding rounds, M leadership moves" from
   the real category counts; 2. "Top hiring today": up to 5 employers by roles
   named, ties broken toward US/UK/EU, the rest under "More"; 4. top 3 named
   items under Leadership moves / Funding / Pay; 5. the methodology moves to a
   short footnote at the bottom; 6. the hero number is not a link.
Without php these SKIP, which is UNKNOWN, not a pass.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
from test_digest_talent_activity import compose, PHP  # noqa: E402
import digest_layout as layout  # noqa: E402

EXTRAS = os.path.join(HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker",
                      "includes", "digest-extras.php")


def php(expr):
    run = subprocess.run([PHP, "-r", f"require $argv[1]; echo json_encode({expr});",
                          EXTRAS], capture_output=True, text=True, timeout=60)
    if run.returncode != 0:
        raise AssertionError(run.stderr[:800])
    return json.loads(run.stdout)


def row(co, jobs, country, day="2026-10-12", head=None):
    return {"company": co, "headline": head or f"{co} adds {jobs} roles",
            "published_date": day, "headcount": jobs, "country": country,
            "source_name": "Example Wire", "source_url": f"https://news.example.com/{co}",
            "confidence": "reported", "pillar": "company_development"}


def daily(**extra):
    base = {
        "from": "2026-10-11", "to": "2026-10-12", "freq": "daily",
        "compose": "talent",
        "talent": {"total": 45, "companies": 45, "verified": 0},
        "talent_ytd": {"total": 31697, "companies": 9100, "verified": 3400},
        "talent_q": {"rows": [
            row("Kodas", 100, "GA"), row("Acme UK", 100, "GB"),
            row("Bolt", 300, "US"), row("Delta", 50, "IN"), row("Echo", 40, "DE"),
            row("Fjord", 30, "NO"), row("Gamma", 20, "BR")]},
        "talent_cat_pillar_leadership_change": {"total": 14},
        "talent_cat_funding_1": {"total": 10},
        "talent_cat_pillar_rewards_comp": {"total": 4},
        "talent_q_pillar_leadership_change": {"rows": [
            row("Lead A", 0, "US", head="Lead A names new CEO"),
            row("Lead B", 0, "US", head="Lead B hires CFO"),
            row("Lead C", 0, "GB", head="Lead C appoints CTO"),
            row("Lead D", 0, "GB", head="Lead D board change")]},
        "talent_q_funding_1": {"rows": [row("Fund A", 0, "US", head="Fund A raises Series B")]},
    }
    base.update(extra)
    return base


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class SubjectMetric(unittest.TestCase):
    def test_pure_metric(self):
        self.assertEqual(php("alt_digest_talent_daily_metric(10, 14)"),
                         "Who's hiring today · 10 funding rounds, 14 leadership moves")
        self.assertEqual(php("alt_digest_talent_daily_metric(1, null)"),
                         "Who's hiring today · 1 funding round")
        self.assertEqual(php("alt_digest_talent_daily_metric(null, null)"), "")

    def test_daily_compose_uses_it(self):
        out = compose(daily())
        self.assertEqual(out["metric"],
                         "Who's hiring today · 10 funding rounds, 14 leadership moves")


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class TopHiringToday(unittest.TestCase):
    def setUp(self):
        self.out = compose(daily())
        self.text = self.out["text"]

    def test_five_by_roles_ties_to_audience_rest_under_more(self):
        top = self.text.split("Top hiring today", 1)[1].split("\nMore", 1)[0]
        order = [c for c in ("Bolt", "Acme UK", "Kodas", "Delta", "Echo") if c in top]
        self.assertEqual(order, ["Bolt", "Acme UK", "Kodas", "Delta", "Echo"])
        self.assertLess(top.index("Acme UK"), top.index("Kodas"),
                        "a UK employer naming the same roles should lead a Gabonese one")
        more = self.text.split("\nMore", 1)[1]
        self.assertIn("Fjord", more)
        self.assertIn("Gamma", more)

    def test_top_three_named_items_per_category(self):
        lead = self.text.split("Leadership moves", 1)[1]
        for name in ("Lead A", "Lead B", "Lead C"):
            self.assertIn(name, lead)
        self.assertNotIn("Lead D", self.text)
        self.assertIn("Fund A raises Series B", self.text)

    def test_method_is_a_footnote_at_the_bottom(self):
        self.assertNotIn("How to read these numbers", self.text)
        self.assertGreater(self.text.index("A talent and employer-activity signal is one"),
                           self.text.index("YTD"))

    def test_hero_is_not_a_link(self):
        self.assertNotRegex(self.out["html"], r'data-alt="stat"><a')


if __name__ == "__main__":
    unittest.main()
