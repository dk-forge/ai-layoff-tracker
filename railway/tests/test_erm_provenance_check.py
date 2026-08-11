"""Offline tests for railway/erm_provenance_check.py.

The check reads the country an ERM row was IMPORTED with out of the excerpt
`erm_import.py` wrote at import time, and compares it to the `country` column
as it stands now. A disagreement means an already-published row was re-scored.

These run with no network: every row is a literal dict of the shape /query
returns. The live figures they encode are the ones the check actually found on
2026-08-11.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import erm_provenance_check as epc


def _row(rid, jobs, imported, stored, company="Acme", edited=True, source_type="erm"):
    return {
        "id": rid, "job_count": jobs, "country": stored, "company_name": company,
        "source_type": source_type, "edited": edited,
        "excerpt": (f"Internal restructuring at {company} ({imported}): {jobs:,} "
                    f"announced job losses. Recorded by the European Restructuring "
                    f"Monitor (Eurofound), factsheet 1."),
    }


class ExcerptCountry(unittest.TestCase):
    def test_reads_the_country_the_importer_wrote(self):
        self.assertEqual(
            epc.excerpt_country("Internal restructuring at Citigroup (Multiple "
                                "countries): 52,000 announced job losses."),
            "Multiple countries")

    def test_a_company_name_carrying_its_own_brackets_still_parses(self):
        # 459 of 19,494 live ERM rows look like this. Anchoring on the FIRST
        # parenthesis reads the company's own abbreviation as the country and
        # then fails to parse, and an unparsed row must never be called clean.
        self.assertEqual(
            epc.excerpt_country("Internal restructuring at Zespol Elektrowni "
                                "Patnow-Adamow-Konin (ZE PAK) (Poland): 700 "
                                "announced job losses."),
            "Poland")

    def test_an_unreadable_excerpt_is_none_and_not_a_guess(self):
        self.assertIsNone(epc.excerpt_country("no country here at all"))
        self.assertIsNone(epc.excerpt_country(""))
        self.assertIsNone(epc.excerpt_country(None))


class Contradictions(unittest.TestCase):
    def test_the_three_live_rows_of_2026_08(self):
        rows = [
            _row(114335, 52000, "Multiple countries", "United States", "Citigroup"),
            _row(113529, 47000, "Multiple countries", "United States", "General Motors"),
            _row(64351, 45000, "Multiple countries", "United States", "Cinemaworld"),
            _row(110920, 30000, "Multiple countries", "Multiple countries",
                 "Bank of America", edited=False),
            _row(1, 700, "Poland", "Poland", "ZE PAK"),
        ]
        bad, unreadable = epc.contradictions(rows)
        self.assertEqual([x["id"] for x in bad], [114335, 113529, 64351])
        self.assertEqual(sum(x["jobs"] for x in bad), 144000)
        self.assertEqual(unreadable, [])
        self.assertEqual({x["stored_country"] for x in bad}, {"United States"})

    def test_biggest_first_so_the_headline_mover_leads(self):
        rows = [_row(2, 10, "France", "Spain"), _row(3, 9000, "France", "Spain")]
        bad, _ = epc.contradictions(rows)
        self.assertEqual([x["id"] for x in bad], [3, 2])

    def test_an_agreeing_row_is_not_reported(self):
        bad, unreadable = epc.contradictions([_row(4, 500, "Germany", "Germany")])
        self.assertEqual(bad, [])
        self.assertEqual(unreadable, [])

    def test_an_unreadable_row_is_its_own_state_never_a_pass(self):
        row = _row(5, 500, "Germany", "Germany")
        row["excerpt"] = "legacy text with no importer sentence"
        bad, unreadable = epc.contradictions([row])
        self.assertEqual(bad, [])
        self.assertEqual([r["id"] for r in unreadable], [5])

    def test_non_erm_rows_are_out_of_scope(self):
        # Only erm_import writes the country into the excerpt. Reading any other
        # source's excerpt the same way would invent findings.
        row = _row(6, 500, "Germany", "United States", source_type="news")
        bad, unreadable = epc.contradictions([row])
        self.assertEqual(bad, [])
        self.assertEqual(unreadable, [])


if __name__ == "__main__":
    unittest.main()
