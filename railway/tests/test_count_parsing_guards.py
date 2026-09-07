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
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Pure-guard tests do not create API clients or make network calls.
sys.modules.setdefault("openai", SimpleNamespace())
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from extractor import (
    _count_has_headcount_context,
    _count_in_text,
    _percent_only_mention,
    extract_layoff_data,
)
from sources.warn import _count_col

ROOT = Path(__file__).resolve().parents[2]
API_PHP = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/api.php").read_text()
PHP = shutil.which("php")


def _php_function(name):
    start = API_PHP.index("function %s(" % name)
    brace = API_PHP.index("{", start)
    depth = 0
    for i in range(brace, len(API_PHP)):
        if API_PHP[i] == "{":
            depth += 1
        elif API_PHP[i] == "}":
            depth -= 1
            if depth == 0:
                return API_PHP[start:i + 1]
    raise AssertionError("unbalanced PHP function %s" % name)


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


class SecHeadcountContextGuardTests(unittest.TestCase):
    """An SEC digit match is not a headcount receipt.

    Applied Aerospace's 2026-08-12 exhibit labelled its financial table "in
    thousands" and reported 4,320 as integration/restructuring COSTS. The old
    verbatim guard saw the digits and published 4,320 job cuts. These fixtures
    pin the semantic distinction the public source promise requires.
    """

    def test_rejects_applied_aerospace_restructuring_cost(self):
        excerpt = (
            "(in thousands, except percentages) Three Months Ended June 30, 2026. "
            "Integration and restructuring costs(2) $ 7,253 $ 1,234 $ 4,320 $ 806."
        )
        self.assertTrue(_count_in_text(4320, excerpt),
                        "the regression only exists because the digits are present")
        self.assertFalse(_count_has_headcount_context(4320, excerpt))

    def test_rejects_money_even_when_a_reduction_phrase_is_nearby(self):
        self.assertFalse(_count_has_headcount_context(
            4320, "A reduction in force produced restructuring costs of $ 4,320."))
        self.assertFalse(_count_has_headcount_context(
            500, "The workforce reduction resulted in costs of 500 million dollars."))

    def test_accepts_common_sec_headcount_wording(self):
        accepted = [
            (800, "The plan will affect approximately 800 roles."),
            (4000, "Workforce reductions of approximately 4,000 - 6,000 employees are expected."),
            (250, "The company expects to reduce its workforce by approximately 250."),
            (500, "The company will lay off 500."),
            (500, "The plan eliminates 500 salaried and hourly positions."),
            (46, "The action affects 46 team members."),
        ]
        for count, excerpt in accepted:
            self.assertTrue(_count_has_headcount_context(count, excerpt), excerpt)

    def test_rejects_unrelated_exact_numbers(self):
        rejected = [
            (2026, "The program is expected to conclude in 2026."),
            (500, "The company has 500 customers."),
            (300, "Revenue increased by 300 basis points."),
            (1200, "The facility contains 1,200 square feet."),
        ]
        for count, excerpt in rejected:
            self.assertFalse(_count_has_headcount_context(count, excerpt), excerpt)


class SecExtractorIntegrationTests(unittest.TestCase):
    """Exercise the production extraction decision, not only its helper."""

    @staticmethod
    def _response(count, excerpt):
        payload = {
            "is_layoff_event": True,
            "company_name": "Applied Aerospace & Defense, Inc.",
            "job_count": count,
            "job_count_max": count,
            "layoff_date": "2026-08-12",
            "excerpt": excerpt,
            "reason_tags": ["restructuring"],
            "ai_causation": "unknown",
            "ai_explicit": False,
            "confidence": 90,
            "announced": False,
        }
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(payload)))])

    def _extract(self, raw_text, count, excerpt):
        raw = {
            "raw_text": raw_text,
            "source_type": "8K",
            "source_name": "SEC EDGAR",
            "source_url": "https://www.sec.gov/Archives/edgar/data/example.htm",
            "filing_date": "2026-08-12",
            "verification_level": "gold",
        }
        with patch("extractor.spend.paid_reads_enabled", return_value=True), \
             patch("extractor.spend.metered_call",
                   return_value=self._response(count, excerpt)):
            return extract_layoff_data(raw)

    def test_production_extractor_rejects_the_applied_cost_row(self):
        excerpt = ("(in thousands, except percentages) Integration and "
                   "restructuring costs(2) $ 7,253 $ 1,234 $ 4,320 $ 806.")
        self.assertIsNone(self._extract(excerpt, 4320, excerpt))

    def test_production_extractor_accepts_a_verbatim_worker_count(self):
        excerpt = "The company expects the reduction to affect approximately 800 roles."
        out = self._extract(excerpt, 800, excerpt)
        self.assertIsNotNone(out)
        self.assertEqual(out["job_count"], 800)


@unittest.skipUnless(PHP, "php binary not available")
class WordpressSecHeadcountContextGuardTests(unittest.TestCase):
    """The receiving API must enforce the same invariant independently."""

    def _php_guard(self, count, excerpt):
        code = (_php_function("alt_count_has_headcount_context")
                + "\necho json_encode(alt_count_has_headcount_context(%d, %s));" %
                (count, json.dumps(excerpt)))
        proc = subprocess.run([PHP, "-r", code], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_api_guard_rejects_the_applied_aerospace_cost(self):
        excerpt = ("(in thousands, except percentages) Integration and "
                   "restructuring costs(2) $ 7,253 $ 1,234 $ 4,320 $ 806.")
        self.assertFalse(self._php_guard(4320, excerpt))

    def test_api_guard_accepts_real_headcount_evidence(self):
        for count, excerpt in (
            (800, "The plan will affect approximately 800 roles."),
            (250, "The company will reduce its workforce by approximately 250."),
            (500, "The company will lay off 500."),
        ):
            self.assertTrue(self._php_guard(count, excerpt), excerpt)

    def test_add_route_rejects_before_creating_a_post(self):
        body = _php_function("alt_api_add")
        gate = body.index("alt_count_has_headcount_context")
        insert = body.index("wp_insert_post")
        self.assertLess(gate, insert)
        self.assertIn("alt_count_evidence_missing", body)

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
