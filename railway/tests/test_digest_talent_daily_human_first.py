"""The talent DAILY is a scan-in-ten-seconds summary (owner, 2026-11-03).

The Nov 3 edition led with "132 talent and employer-activity signals", ranked
an announced plan (Cohere 1,500 roles, from press) beside job-board counts
(ZipRecruiter 8 roles, from Greenhouse) as if they measured one thing, printed
a regional table and a "Not recorded 39" row, and called a two-day window
"today". This pins the redesign:

- the subject names the top hiring development, never a raw signal count;
- hiring signals lead and the all-signal total is one line of context;
- announced plans and open listings are labelled and ranked separately, and
  a row of one type never appears in the other's ranking;
- at most five employer lines, one line each, then one "See all" link;
- the regions are one line plus a link, the detail sits under Notes;
- the window label names its dates.

Driven through the PHP harness. Without php on PATH these SKIP (UNKNOWN).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_talent_briefing import PHP, compose  # noqa: E402

FROM, TO = "2026-11-02", "2026-11-03"


def sig(i, company, country, headcount=None, city="", board=None,
        source="Reporter", direction="hiring"):
    row = {"signal_id": f"d{i}", "company": company, "country": country,
           "hq_country": "", "signal_direction": direction,
           "headcount": None if headcount is None else str(headcount),
           "industry": "technology", "city": city, "state": "",
           "source_name": board or source,
           "source_url": f"https://example.com/{i}", "materiality": "high"}
    if board:
        row["collector"] = "ats_boards"
    return row


def fixture():
    rows = [
        sig(1, "ZipRecruiter", "US", 8, board="Greenhouse job board"),
        sig(2, "HawkEye 360", "US", 7, board="Greenhouse job board"),
        sig(3, "NerdWallet", "US", 6, board="Ashby job board"),
        sig(4, "Cohere", "CA", 1500, city="Toronto", source="MobileSyrup"),
        sig(5, "Applegreen", "IE", 80, source="Business Plus"),
        sig(6, "Tower", "IL", 150, source="Globes"),
        sig(7, "Mondial Relay", "FR", None, source="20 Minutes"),
        sig(8, "Acme UK", "GB", direction="neutral"),
        sig(9, "Nowhere", "", direction="neutral"),
    ]
    agg = {"total": 9, "companies": 9, "stated_headcount": 6,
           "by_direction": [{"k": "hiring", "n": "7"}, {"k": "neutral", "n": "2"}],
           "by_country": [{"k": "US", "n": "3"}, {"k": "CA", "n": "1"},
                          {"k": "IE", "n": "1"}, {"k": "IL", "n": "1"},
                          {"k": "FR", "n": "1"}, {"k": "GB", "n": "1"}]}
    return {"from": FROM, "to": TO, "freq": "daily", "compose": "talent",
            "options": {"alt_digest_talent_briefing_tiers": "daily,weekly,monthly"},
            "talent": agg, "talent_q": {"total": 9, "rows": rows},
            "talent_ytd": agg, "talent_geo": agg}


def section(text, heading):
    """The lines under one heading, up to the next blank line."""
    body = text.split("\n" + heading + "\n", 1)[1]
    return body.split("\n\n", 1)[0]


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class DailyHumanFirst(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(fixture())
        cls.text = cls.out["text"]
        cls.html = cls.out["html"]

    def test_subject_leads_with_top_hiring_development(self):
        self.assertEqual(self.out["metric"],
                         "Who's hiring: Cohere plans 1,500 roles in Toronto + 6 more")
        self.assertNotIn("signal", self.out["metric"])

    def test_hiring_leads_and_total_is_one_context_line(self):
        lead = self.text.splitlines()[2]
        self.assertTrue(lead.startswith("7 hiring signals, led by Cohere"), lead)
        self.assertEqual(self.text.count("9 talent and employer-activity signals"), 1)
        self.assertLess(self.text.index("Announced hiring plans"),
                        self.text.index("In context: 9 talent"))

    def test_window_label_names_its_dates(self):
        self.assertIn("Latest hiring signals (Nov 2-3)", self.text)
        self.assertNotIn("today", self.text.lower())
        self.assertNotIn("daily briefing", self.text)

    def test_announced_plans_and_open_listings_are_never_mixed(self):
        plans = section(self.text, "Announced hiring plans")
        listings = section(self.text, "Open listings")
        for name in ("ZipRecruiter", "HawkEye 360", "NerdWallet"):
            self.assertNotIn(name, plans)
        for name in ("Cohere", "Tower", "Applegreen", "Mondial Relay"):
            self.assertNotIn(name, listings)
        self.assertNotIn("open listings", plans)
        self.assertNotIn("announced plan", listings)
        # Each list is ranked within its own type, largest first.
        self.assertLess(plans.index("Cohere"), plans.index("Tower"))
        self.assertLess(plans.index("Tower"), plans.index("Applegreen"))
        self.assertLess(listings.index("ZipRecruiter"), listings.index("HawkEye 360"))

    def test_one_compact_line_per_employer_capped_at_five(self):
        lines = re.findall(r"^  \S.*: .*(?:announced plan|open listings) · .*$",
                           self.text, re.M)
        self.assertEqual(len(lines), 5, lines)
        self.assertIn("  🇨🇦 Cohere: 1,500 roles, announced plan · Toronto, Canada · "
                      "MobileSyrup https://example.com/4", self.text)
        self.assertNotIn("📍", self.text + self.html)
        self.assertNotIn("Around the world", self.text)
        self.assertIn("See all 7 hiring signals", self.text)
        self.assertEqual(self.text.count("See all"), 1)

    def test_regions_are_one_line_and_detail_moves_to_notes(self):
        self.assertNotIn("By region:", self.text)
        self.assertNotIn("Not recorded:", self.text)
        notes = self.text.split("\nNotes\n", 1)[1]
        self.assertIn("Signals by region:", notes)
        self.assertIn("1 signal carries no country.", notes)
        body = self.text.split("\nNotes\n", 1)[0]
        self.assertEqual(len(re.findall(r"^By region, .* See where: ", body, re.M)), 1)

    def test_layout_puts_both_rankings_first(self):
        import digest_layout
        arranged = digest_layout.arrange_section(self.html, "Talent Intelligence Tracker")
        self.assertLess(arranged.index("Announced hiring plans"),
                        arranged.index("How we count"))
        self.assertIn("Open listings", digest_layout.ITEM_HEADINGS)
        self.assertIn("Announced hiring plans", digest_layout.ITEM_HEADINGS)

    def test_house_style(self):
        body = self.text + self.html + self.out["metric"]
        self.assertNotRegex(body, "[–—]")
        for word in ("bl" + "ind", "hon" + "est", "halluc" + "inat"):
            self.assertNotIn(word, body.lower())


if __name__ == "__main__":
    unittest.main()
