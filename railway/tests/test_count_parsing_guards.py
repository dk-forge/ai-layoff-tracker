"""Regression guards for the three count mis-parses found 2026-07-18.

1. CT WARN: tier-1 "affected" matched the "affected_company" header, so job
   counts were parsed out of company NAMES (CT collection was effectively
   dead; the 313-worker CVS/Aetna notice was dropped).
2. IL WARN: "Expected Layoff" was preferred over "Revised Layoff", so
   in-place cumulative revisions never updated counts (Capital One/Discover
   Riverwoods: expected 215 vs revised 2,027).
3. Extractor: "17% of its staff" was stored as 17 jobs (Intuit).
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Pure-guard tests do not create API clients or make network calls.
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

from extractor import _percent_only_mention
from sources.warn import _count_col


class WarnCountColumnTests(unittest.TestCase):
    def test_ct_affected_company_is_never_the_count_column(self):
        # Shape of warn-scraper's flattened CT DOL blob-library row.
        row = {
            "affected_company": "CVS Health - Aetna",
            "number_of_impacted_workers": "313",
            "layoff_dates": "4/3/2026 - 7/31/2026",
            "town": "Hartford - Remote",
        }
        self.assertEqual(_count_col(row), "313")

    def test_ct_company_name_containing_digits_is_not_a_count(self):
        row = {
            "affected_company": "G2 Secure Staffing, LLC",
            "number_of_impacted_workers": "100",
        }
        self.assertEqual(_count_col(row), "100")

    def test_il_revised_layoff_supersedes_expected(self):
        # IL IEBS keeps one cumulative row per site event and revises it.
        row = {
            "company": "Capital One Financial Corporation",
            "approximate total # of full-time employees": "4500",
            "expected layoff": "215",
            "revised layoff": "2,027",
        }
        self.assertEqual(_count_col(row), "2,027")

    def test_il_zero_revised_falls_back_to_expected(self):
        row = {
            "company": "Legacy Employer",
            "expected layoff": "215",
            "revised layoff": "0",
        }
        self.assertEqual(_count_col(row), "215")


class ExtractorPercentGuardTests(unittest.TestCase):
    def test_percent_only_mention_is_rejected(self):
        self.assertTrue(_percent_only_mention(
            17, "Intuit is letting 17% of its staff go, or about 3,000 people."))

    def test_genuine_small_count_survives(self):
        self.assertFalse(_percent_only_mention(
            17, "The plant will lay off 17 workers next month."))

    def test_count_present_alongside_percent_survives(self):
        self.assertFalse(_percent_only_mention(
            80, "80 employees, roughly 80 percent of the office, lose their jobs; 80 layoffs confirmed."))

    def test_large_counts_are_never_second_guessed(self):
        self.assertFalse(_percent_only_mention(3000, "cutting 17% of staff, about 3,000 people"))


if __name__ == "__main__":
    unittest.main()
