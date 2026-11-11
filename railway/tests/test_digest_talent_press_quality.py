"""Owner review of the talent daily, 2026-11-11 (press quality).

1. Every employer line carries a marker: the country flag, or one neutral
   marker when no country is recorded (Moov Africa Tchad and Cloudflare had
   none while every other line had a flag).
2. No region is called "leading" when signals with no country outnumber it;
   the unrecorded share is stated plainly instead.
3. Announced plans lead with real numbers: plans with no stated role count
   are folded into one line, never listed one by one.
4. The employer-activity count is said once.

Driven through the PHP harness. Without php on PATH these SKIP (UNKNOWN).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_talent_briefing import PHP, compose  # noqa: E402
from test_digest_talent_daily_human_first import fixture, sig  # noqa: E402

NEUTRAL = "\U0001F310"


def rebuild(fx, rows):
    hiring = sum(1 for r in rows if r["signal_direction"] == "hiring")
    by_country = {}
    for r in rows:
        if r["country"]:
            by_country[r["country"]] = by_country.get(r["country"], 0) + 1
    for agg in (fx["talent"], fx["talent_ytd"], fx["talent_geo"]):
        agg["total"] = len(rows)
        agg["companies"] = len(rows)
        agg["by_direction"] = [{"k": "hiring", "n": str(hiring)},
                               {"k": "neutral", "n": str(len(rows) - hiring)}]
        agg["by_country"] = [{"k": k, "n": str(v)} for k, v in by_country.items()]
        agg["stated_headcount"] = sum(1 for r in rows if r["headcount"])
    fx["talent_q"]["total"] = len(rows)
    fx["talent_q"]["rows"] = rows
    return fx


def mostly_unplaced():
    fx = fixture()
    rows = list(fx["talent_q"]["rows"])
    rows.append(sig(30, "Moov Africa Tchad", "", None, source="Tchadinfos"))
    rows.append(sig(31, "Cloudflare", "", 12, board="Greenhouse job board"))
    for i in range(3):
        rows.append(sig(40 + i, f"Unstated{i}", "DE", None, source="Handelsblatt"))
    for i in range(8):
        rows.append(sig(60 + i, f"Anon{i}", "", direction="neutral"))
    return rebuild(fx, rows)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class PressQuality(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(mostly_unplaced())
        cls.text = cls.out["text"]
        cls.html = cls.out["html"]

    def lines(self):
        return re.findall(r"^  (\S.*?): .*(?:announced plan|open listings) · .*$", self.text, re.M)

    def test_every_line_has_a_flag_or_the_neutral_marker(self):
        leads = self.lines()
        self.assertTrue(leads)
        for lead in leads:
            first = lead.split(" ", 1)[0]
            is_flag = all(0x1F1E6 <= ord(c) <= 0x1F1FF for c in first) and len(first) == 2
            self.assertTrue(is_flag or first == NEUTRAL, lead)
        self.assertIn(NEUTRAL + " Cloudflare", self.text)
        self.assertIn("country not recorded", self.text)

    def test_no_leading_region_when_unrecorded_is_larger(self):
        self.assertNotIn("Leading region", self.text)
        self.assertNotIn(" led with ", self.text)
        self.assertRegex(self.text, r"Country not recorded: \d+ of \d+ signals \(\d+%\)")

    def test_unstated_plans_fold_into_one_line(self):
        self.assertNotIn("roles not stated, announced plan", self.text)
        self.assertRegex(self.text, r"Also announced, roles not stated: .*Unstated0")

    def test_employer_activity_said_once(self):
        counted = re.findall(r"(?i)\d[\d,]* employer-activity signal|employer-activity signals: \d", self.text)
        self.assertEqual(len(counted), 1, self.text)
        self.assertIn("Employer-activity signals: 10 from 10 employers", self.text)
        self.assertNotIn("Separately,", self.text)

    def test_house_style(self):
        self.assertNotRegex(self.text + self.html, "[–—]")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class PlacedLeads(unittest.TestCase):

    def test_leading_region_kept_when_it_outnumbers_unrecorded(self):
        text = compose(fixture())["text"]
        self.assertIn("Leading region: North America, 4 signals", text)


if __name__ == "__main__":
    unittest.main()
