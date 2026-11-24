"""Company-column diagnostics use only synthetic parser results."""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nc_warn_check as checker


class NorthCarolinaCheck(unittest.TestCase):
    def test_company_words_are_not_flagged(self):
        for value in ["Example Manufacturing", "  Example   Works  ", "Example 42"]:
            with self.subTest(value=value):
                self.assertFalse(checker.suspect(value))

    def test_missing_numeric_date_and_single_letter_values_are_suspect(self):
        for value in [None, "", "  ", 42, "1,000", "2026-11-24", "A"]:
            with self.subTest(value=value):
                self.assertTrue(checker.suspect(value))

    def test_empty_fetch_is_clean_and_sends_nothing(self):
        fetch = Mock(return_value=[])
        with patch.dict(sys.modules, {"sources.warn_custom": SimpleNamespace(fetch_nc=fetch)}), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(checker.main(), 0)
        fetch.assert_called_once_with()
        self.assertIn("CLEAN", out.getvalue())

    def test_reports_misaligned_rows_without_changing_them(self):
        rows = [{"company_name": "0", "job_count": 3, "layoff_date": "2026-01-02"}]
        with patch.dict(sys.modules, {"sources.warn_custom": SimpleNamespace(fetch_nc=Mock(return_value=rows))}), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(checker.main(), 0)
        self.assertIn("suspect company rows: 1", out.getvalue())
        self.assertEqual(rows[0]["company_name"], "0")

    def test_source_error_returns_failure(self):
        fetch = Mock(side_effect=OSError("fixture source unavailable"))
        with patch.dict(sys.modules, {"sources.warn_custom": SimpleNamespace(fetch_nc=fetch)}), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(checker.main(), 1)
        self.assertIn("fetch_nc FAILED", out.getvalue())
