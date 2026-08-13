"""The index line of the adjudication sheet must not describe an entry by its worst row.

The sheet is read twice: once as a 29-line table ("what is there to look at")
and once as 29 detail blocks. Where several tracker rows contest one gold
filing, the table line used to pool every row's flags into one sentence with no
row ids in it. On 2026-08-12 the Dow Inc entry therefore read

    two things may be conflated - COUNT differs by -4362: we hold 138, the
    filing states 4500; SOURCE is 'news'; the URL we cite is not an EDGAR
    archive path

which is true of row 149592 (a real 138-job Tarragona cut) and false of row
149616, which held the filing's exact 4,500 and cited the gold accession. The
detail block said so plainly; the line above it did not, and the event was
adjudicated as one we do not hold.

These tests pin the property that fixes it: in a contested entry every proposed
row is named by id, and a row with no discrepancy of its own is stated as such
rather than absorbed into the other row's flags.
"""
import sys
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

import recall_adjudication_pack as pack  # noqa: E402


GOLD = {
    "reference_row_id": "sec-205-0001751788-26-000009",
    "filer": "DOW INC.",
    "cik": "0001751788",
    "accession": "0001751788-26-000009",
    "filing_date": "2026-01-29",
    "stated_job_count": 4500,
    "official_source_url": ("https://www.sec.gov/Archives/edgar/data/1751788/"
                            "000175178826000009/dow-20260126.htm"),
    "employer_aliases": ["Dow"],
    "excluded_name_prefixes": [],
    "match_window": ["2025-10-31", "2026-10-26"],
    "match_decision": "not_matched",
}

NEWS_ROW = {
    "event_id": 149592, "id": 176859, "company_name": "Dow", "job_count": 138,
    "layoff_date": "2026-08-01", "announcement_date": "", "source_type": "news",
    "source_name": "APD Noticies",
    "source_url": "https://news.google.com/rss/articles/CBMigwJ?oc=5",
    "excerpt": "138 layoffs at Dow in Tarragona.", "verification_level": "bronze",
    "permalink": "",
}

FILING_ROW = {
    "event_id": 149616, "id": 176883, "company_name": "Dow", "job_count": 4500,
    "layoff_date": "2026-01-29", "announcement_date": "2026-01-29",
    "source_type": "8K", "source_name": "SEC EDGAR 8-K Item 2.05",
    "source_url": GOLD["official_source_url"],
    "excerpt": "a workforce reduction of approximately 4,500 roles globally",
    "verification_level": "gold", "permalink": "",
}


def entry_for(rows):
    compared = pack.compare(GOLD, rows, {"text": ""}, {})
    return {"rows": compared, "weight": sum(r["weight"] for r in compared)}


class ContestedEntrySummaryTests(unittest.TestCase):
    def test_every_contesting_row_is_named_by_id(self):
        line = pack.tier(entry_for([NEWS_ROW, FILING_ROW]))
        self.assertIn("149592", line)
        self.assertIn("149616", line)

    def test_the_clean_row_is_stated_as_clean_and_not_absorbed(self):
        line = pack.tier(entry_for([NEWS_ROW, FILING_ROW]))
        head, _, tail = line.partition("row 149616")
        # Everything said about the 138 row stays on the 138 row's side of the line.
        self.assertIn("COUNT differs by -4362", head)
        self.assertNotIn("COUNT differs", tail)
        self.assertNotIn("not the 8-K", tail)
        self.assertIn("NO discrepancy", tail)

    def test_order_of_the_rows_does_not_change_what_is_said_about_either(self):
        forward = pack.tier(entry_for([NEWS_ROW, FILING_ROW]))
        reverse = pack.tier(entry_for([FILING_ROW, NEWS_ROW]))
        for line in (forward, reverse):
            self.assertIn("row 149616: NO discrepancy", line)
            self.assertIn("row 149592: COUNT differs by -4362", line)

    def test_a_single_row_entry_is_unchanged(self):
        line = pack.tier(entry_for([NEWS_ROW]))
        self.assertTrue(line.startswith("**two things may be conflated**"), line)
        self.assertNotIn("rows contest", line)

    def test_a_clean_single_row_entry_is_still_the_quick_one(self):
        self.assertEqual(pack.tier(entry_for([FILING_ROW])),
                         "every fact lines up — count, dates, name, accession")


if __name__ == "__main__":
    unittest.main()
