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

from extractor import _percent_only_mention, _count_in_text
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


class CountInTextVerbatimGuardTests(unittest.TestCase):
    """The verbatim guard must reject a count that is only the PREFIX of a
    larger grouped number ("500" in "$500,000", "12" in "12,500") or a calendar
    year the model misread as a headcount, while still accepting every real
    count. (Adversarial finding 2026-07-24.)"""

    REJECT = [
        (500, "cut costs by $500,000 this year"),
        (5000, "a $5,000,000 charge"),
        (500, "reached 500,000 customers"),
        (12, "12,500 employees remain"),
        (12, "12.500 employees remain (EU)"),
        (500, "500 000 users"),
        (2026, "By 2026 the firm plans changes"),
        (2020, "founded in 2020, the company grew"),
        (2024, "in fiscal 2024 revenue fell"),
    ]
    ACCEPT = [
        (500, "laid off 500 workers"),
        (500, "cut 500, then reversed course"),
        (300, "300,000 sq ft closed, and cut 300 jobs"),
        (12000, "12,000 employees affected"),
        (12000, "12000 employees affected"),
        (12000, "about 12k staff let go"),
        (500000, "500,000 roles eliminated"),
        (500000, "500 000 roles eliminated"),
        (2000, "2,000 jobs cut"),
        (2000, "2000 employees laid off"),
        (2050, "eliminating 2,050 positions"),
        (2050, "2050 workers affected"),
        (1995, "1,995 jobs to go"),
        (2026, "2,026 employees will be let go"),
        (2026, "cutting 2026 jobs"),
        (40, "40 employees"),
        (150, "150 staff"),
    ]

    def test_rejects_prefix_of_larger_number_and_years(self):
        for n, text in self.REJECT:
            self.assertFalse(_count_in_text(n, text),
                             f"should REJECT {n} in {text!r}")

    def test_accepts_real_counts(self):
        for n, text in self.ACCEPT:
            self.assertTrue(_count_in_text(n, text),
                            f"should ACCEPT {n} in {text!r}")

class WhitespaceShapeGuardTests(unittest.TestCase):
    """Whitespace was the blind spot in both number guards (found 2026-07-30).

    Every fixture in the tables above is a single line separated by ASCII
    spaces, so neither guard was ever exercised against a line break, a tab, or
    a typographic space — which is exactly where the sibling tracker's
    "verbatim figure read as invented, record silently discarded" bug lived.
    Two real defects were found and fixed; these pin both.
    """

    NBSP = "\u00a0"      # no-break space
    NNBSP = "\u202f"     # narrow no-break space (French/Swiss/Canadian grouping)
    THIN = "\u2009"      # thin space (typeset sources)

    def test_every_typographic_thousands_separator_is_recognised(self):
        # `sep` in _count_in_text listed U+202F but `variants` never generated
        # it, so a French source's "12 000" was read as absent and the record
        # was thrown away with the number sitting right there in the text.
        for name, sep in (("ASCII", " "), ("NBSP", self.NBSP),
                          ("NNBSP", self.NNBSP), ("THIN", self.THIN)):
            text = f"Le groupe supprimera 12{sep}000 postes."
            self.assertTrue(_count_in_text(12000, text),
                            f"{name} separator ({sep!r}) not recognised")

    def test_widened_separators_still_reject_a_prefix_of_a_bigger_number(self):
        # Adding separators must not weaken the prefix guard: the new variants
        # are still exact literals fenced by the same lookarounds.
        for sep in (self.NBSP, self.NNBSP, self.THIN, " "):
            self.assertFalse(_count_in_text(12, f"12{sep}500 employees remain"),
                             f"12 wrongly accepted before {sep!r}500")

    def test_count_survives_surrounding_line_breaks_and_tabs(self):
        for text in ("Affected workers: 12,000\nEffective date: 2026-01-01",
                     "Affected: 12,000\r\nNext line",
                     "Acme\t12,000\tjobs",
                     "Total affected 12,000"):
            self.assertTrue(_count_in_text(12000, text), repr(text))

    def test_percent_gate_does_not_read_across_a_line_break(self):
        # `\s*` matches `\n`, so on any path that does not flatten whitespace
        # (PDF/OCR, tables) a headcount ending one line and a "Percent of
        # workforce" header starting the next read as one "17 percent" and the
        # record died — with the 17 verbatim in the source.
        raw = "Employees affected: 17\nPercent of workforce: 3\n"
        self.assertTrue(_count_in_text(17, raw), "17 is verbatim in the source")
        self.assertFalse(_percent_only_mention(17, raw),
                         "a count and a percent COLUMN are not '17 percent'")
        self.assertFalse(_percent_only_mention(17, "Cuts: 17\r\n% of staff: 3"))

    def test_percent_gate_still_catches_a_real_percentage(self):
        # The Intuit misread this guard exists for must keep failing.
        for text in ("Intuit said it would cut 17% of its staff.",
                     "The company is laying off 17 percent of employees.",
                     "A 17% reduction was announced.",
                     "cut 17 % of the workforce"):
            self.assertTrue(_percent_only_mention(17, text), repr(text))

    def test_percent_gate_still_passes_a_genuine_small_headcount(self):
        for text in ("The plant will lay off 17 workers in March.",
                     "Notice covers 17 employees; that is 3% of staff."):
            self.assertFalse(_percent_only_mention(17, text), repr(text))
