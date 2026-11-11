"""Owner feedback on the Nov 5 talent daily (2026-11-05).

1. "By region, North America led with 30 signals" sat above a Notes line
   reading "Europe 32 · North America 30". The lead picked the first region of
   a FIXED display order (alt_briefing_region_order), not the largest count.
   It must name the largest placed region from the same numbers Notes prints,
   never "Not recorded", and name both on a tie.
2. Each hiring row links to the employer's verified job board when the data
   holds one (an ats_boards row for the same employer), never an invented URL.
3. The "In context" line states the window it covers and says "distinct
   employers": /talent/v1/aggregate counts COUNT(DISTINCT company_key), an
   exact count, so "about" was wrong.

Driven through the PHP harness. Without php on PATH these SKIP (UNKNOWN).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_talent_briefing import PHP, compose  # noqa: E402

FROM, TO = "2026-11-04", "2026-11-05"
BOARD = "https://job-boards.greenhouse.io/braze"


def sig(i, company, country, headcount=None, direction="neutral", board=None,
        key=None, source="Reporter", url=None):
    row = {"signal_id": f"r{i}", "company": company,
           "company_key": key or company.lower(), "country": country,
           "hq_country": "", "signal_direction": direction,
           "headcount": None if headcount is None else str(headcount),
           "industry": "technology", "city": "", "state": "",
           "source_name": board or source,
           "source_url": url or f"https://example.com/{i}", "materiality": "high"}
    if board:
        row["collector"] = "ats_boards"
    return row


def fixture(counts, extra=()):
    rows = list(extra)
    i = 100
    for code, n in counts.items():
        for _ in range(n):
            i += 1
            rows.append(sig(i, f"Co{i}", code))
    by_country = {}
    for r in rows:
        if r["country"]:
            by_country[r["country"]] = by_country.get(r["country"], 0) + 1
    hiring = sum(1 for r in rows if r["signal_direction"] == "hiring")
    agg = {"total": len(rows), "companies": len({r["company_key"] for r in rows}),
           "stated_headcount": hiring,
           "by_direction": [{"k": "hiring", "n": str(hiring)},
                            {"k": "neutral", "n": str(len(rows) - hiring)}],
           "by_country": [{"k": k, "n": str(v)} for k, v in by_country.items()]}
    return {"from": FROM, "to": TO, "freq": "daily", "compose": "talent",
            "options": {"alt_digest_talent_briefing_tiers": "daily,weekly,monthly"},
            "talent": agg, "talent_q": {"total": len(rows), "rows": rows},
            "talent_ytd": agg, "talent_geo": agg}


# The Nov 5 counts: NA 30, Europe 32, APAC 25, ME 10, LatAm 4, Africa 5, none 31.
NOV5 = {"US": 30, "ES": 32, "AU": 25, "IL": 10, "BR": 4, "ZA": 5, "": 31}

HIRING = [
    sig(1, "Parfois", "PT", 300, "hiring", key="parfois", source="ABC Economia"),
    sig(2, "Braze", "GB", 16, "hiring", key="braze", board="Greenhouse job board", url=BOARD),
    sig(3, "Braze", "GB", 40, "hiring", key="braze", source="Press"),
    sig(4, "Toast", "IN", 12, "hiring", key="toast", source="Press"),
]


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class RegionLead(unittest.TestCase):

    def test_largest_region_leads_not_the_fixed_order(self):
        text = compose(fixture(NOV5))["text"]
        self.assertIn("By region, Europe led with 32 signals, followed by "
                      "North America with 30.", text)
        self.assertNotIn("North America led", text)
        notes = text.split("\nNotes\n", 1)[1]
        self.assertIn("Europe 32", notes)
        self.assertIn("North America 30", notes)

    def test_not_recorded_never_leads(self):
        text = compose(fixture({"US": 3, "ES": 2, "": 40}))["text"]
        # Owner review 2026-11-11: 40 unrecorded outnumber every region, so
        # no region is called leading and the share is stated instead.
        self.assertNotIn(" led with ", text)
        self.assertNotIn("Leading region", text)
        self.assertIn("Country not recorded: 40 of 45 signals (89%)", text)
        self.assertNotIn("Not recorded led", text)

    def test_tie_names_both(self):
        text = compose(fixture({"US": 30, "ES": 30, "AU": 5}))["text"]
        self.assertIn("By region, North America and Europe led with 30 signals each, "
                      "followed by Asia-Pacific with 5.", text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class JobBoardLinks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(fixture({"US": 2}, HIRING))
        cls.text, cls.html = cls.out["text"], cls.out["html"]

    def lines(self, name):
        return [l for l in self.text.splitlines() if f" {name}: " in l]

    def test_plan_row_links_to_the_employers_verified_board(self):
        (line,) = [l for l in self.lines("Braze") if "announced plan" in l]
        self.assertIn("Open roles " + BOARD, line)
        self.assertIn('href="' + BOARD + '"', self.html)

    def test_listing_row_links_to_its_board_once(self):
        (line,) = [l for l in self.lines("Braze") if "open listings" in l]
        self.assertEqual(line.count(BOARD), 1, line)

    def test_no_board_no_link_never_invented(self):
        for name in ("Parfois", "Toast"):
            for line in self.lines(name):
                self.assertNotIn("Open roles", line)
        self.assertNotIn("greenhouse.io/parfois", self.text + self.html)
        self.assertNotIn("greenhouse.io/toast", self.text + self.html)

    def test_each_row_stays_one_line(self):
        self.assertEqual(self.html.count('data-alt="item-line"'),
                         len([l for l in self.text.splitlines()
                              if "announced plan ·" in l or "open listings ·" in l]))


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class ContextPeriod(unittest.TestCase):

    def test_context_states_window_and_distinct_employers(self):
        text = compose(fixture(NOV5))["text"]
        # Reworded 2026-11-06; the window now sits in the glance heading.
        self.assertIn("Employer-activity signals: 137 from 137 employers", text)
        self.assertIn("At a glance (Nov 4-5)", text)
        self.assertNotIn("about 137", text)
