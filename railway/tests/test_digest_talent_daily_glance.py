"""Owner asks on the talent daily (2026-11-06).

1. A glance box at the top: hiring signals N, employer-activity signals M,
   the biggest announced plan, the leading region.
2. The three types defined right under it, one line each, so "7 vs 2"
   cannot be misread.
3. "Reported signals, most not independently verified" sits next to the box,
   not at the bottom.
4. Up to 10 hiring signals in the compact list, then "N featured, see all M".
5. The context line reads "Separately, M employer-activity signals from E
   employers."
6. No duplicate date line: the window is stated once, in the glance heading.
The subject format is unchanged.

Driven through the PHP harness. Without php on PATH these SKIP (UNKNOWN).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_talent_briefing import PHP, compose  # noqa: E402
from test_digest_talent_daily_human_first import fixture, sig  # noqa: E402

LINE = r"^  \S.*: .*(?:announced plan|open listings) · .*$"


def big_fixture(n_plans=8, n_listings=6):
    fx = fixture()
    rows = fx["talent_q"]["rows"]
    for i in range(n_plans):
        rows.append(sig(100 + i, f"Plan{i}", "DE", 10 + i, source="Handelsblatt"))
    for i in range(n_listings):
        rows.append(sig(200 + i, f"List{i}", "US", 2 + i, board="Lever job board"))
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
    return fx


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class Glance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(fixture())
        cls.text = cls.out["text"]
        cls.html = cls.out["html"]

    def test_glance_box_leads_with_the_four_facts(self):
        self.assertIn('data-alt="glance"', self.html)
        head = self.text.split("Announced hiring plans", 1)[0]
        self.assertIn("At a glance (Nov 2-3)", head)
        self.assertIn("Hiring signals: 7", head)
        self.assertIn("Employer-activity signals: 2", head)
        self.assertIn("Biggest announced plan: Cohere, 1,500 roles in Toronto", head)
        self.assertIn("Leading region: North America, 4 signals", head)

    def test_three_types_defined_under_the_box(self):
        head = self.text.split("Announced hiring plans\n", 1)[0]
        for line in ("Announced hiring plans: roles an employer or report says it will add.",
                     "Open listings: roles live on career sites now.",
                     "Employer-activity signals: wider reports, not confirmed hiring."):
            self.assertIn(line, head)
        self.assertLess(head.index("Leading region"), head.index("Open listings: roles live"))

    def test_reported_signals_note_is_by_the_box_not_the_bottom(self):
        head = self.text.split("Announced hiring plans\n", 1)[0]
        self.assertIn("These are reported signals: most are not independently verified.", head)
        self.assertNotIn("not independently verified", self.text.split("\nNotes\n", 1)[1])

    def test_context_line_is_the_separately_sentence(self):
        self.assertIn("Separately, 2 employer-activity signals from 2 employers.", self.text)
        self.assertNotIn("In context:", self.text)

    def test_window_is_stated_once(self):
        self.assertNotIn('data-alt="dateline"', self.html)
        self.assertNotIn("Latest hiring signals", self.text)
        self.assertEqual(self.text.count("(Nov 2-3)"), 1)

    def test_subject_format_unchanged(self):
        self.assertEqual(self.out["metric"],
                         "Who's hiring: Cohere plans 1,500 roles in Toronto + 6 more")

    def test_all_shown_says_see_all(self):
        self.assertIn("See all 7 hiring signals", self.text)
        self.assertNotIn("featured", self.text)

    def test_house_style(self):
        self.assertNotRegex(self.text + self.html, "[–—]")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TenFeatured(unittest.TestCase):

    def test_up_to_ten_lines_and_featured_count(self):
        text = compose(big_fixture())["text"]
        lines = re.findall(LINE, text, re.M)
        self.assertEqual(len(lines), 10, lines)
        self.assertIn("10 featured, see all 21 hiring signals", text)
        self.assertEqual(text.count("see all"), 1)


if __name__ == "__main__":
    unittest.main()
