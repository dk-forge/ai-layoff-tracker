"""Monthly comparison inputs are synthetic; the clock and public reads are fake."""
import contextlib
import io
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import monthly_us_comparison as comparison


class MonthlyComparison(unittest.TestCase):
    def test_percentages_distinguish_unknown_and_missing_denominator(self):
        self.assertEqual(comparison.pct(3, 4), "75%")
        self.assertEqual(comparison.pct(0, 4), "0%")
        self.assertEqual(comparison.pct(None, 4), "UNKNOWN")
        self.assertEqual(comparison.pct(3, 0), "n/a")

    def test_effective_month_query_uses_the_whole_month(self):
        with patch.object(comparison, "fetch", return_value={"jobs": 3}) as fetch:
            self.assertEqual(comparison.month_totals("2026-03", "effective"), {"jobs": 3})
        fetch.assert_called_once_with({"country": "United States", "from": "2026-03-01", "to": "2026-03-31"})

    def test_notice_basis_is_explicit(self):
        with patch.object(comparison, "fetch", return_value=None) as fetch:
            self.assertIsNone(comparison.month_totals("2026-04", "notice"))
        self.assertEqual(fetch.call_args.args[0]["date_basis"], "notice")
        self.assertEqual(fetch.call_args.args[0]["to"], "2026-04-30")

    def test_survey_structure_and_read_date_are_required(self):
        good = {"total": {"2026-01": 3}, "read_date": "2026-02-03"}
        with patch.object(comparison.SURVEY_FILE.__class__, "read_text", return_value=json.dumps(good)):
            self.assertEqual(comparison.load_survey(), good)
        with patch.object(comparison.SURVEY_FILE.__class__, "read_text", return_value="{}"), contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(comparison.load_survey())

    def test_unreadable_survey_is_unknown(self):
        with patch.object(comparison.SURVEY_FILE.__class__, "read_text", side_effect=OSError("fixture offline")), contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(comparison.load_survey())

    def test_due_boundary_uses_the_injected_date(self):
        cutoff = date(2026, 1, 31) + timedelta(days=comparison.DUE_AFTER_DAYS)
        clock = Mock(wraps=date)
        with patch.object(comparison, "date", clock):
            clock.today.return_value = cutoff
            self.assertFalse(comparison.month_is_due("2026-01"))
            clock.today.return_value = cutoff + timedelta(days=1)
            self.assertTrue(comparison.month_is_due("2026-01"))
