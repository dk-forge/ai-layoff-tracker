"""Dry-run arguments with the OCR source replaced before import."""
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hi_warn_dryrun as dryrun


class HawaiiDryRun(unittest.TestCase):
    def invoke(self, env, fetch):
        with patch.dict(os.environ, env, clear=True), patch.dict(sys.modules, {"sources.warn_hi_ocr": SimpleNamespace(fetch_hi_ocr=fetch)}), contextlib.redirect_stdout(io.StringIO()) as output:
            return dryrun.main(), output.getvalue()

    def test_defaults_are_a_dry_run_even_with_no_results(self):
        fetch = Mock(return_value=[])
        result, text = self.invoke({}, fetch)
        self.assertEqual(result, 0)
        fetch.assert_called_once_with(years=None, limit=None, dry_run=True)
        self.assertIn("0 countable Hawaii notice", text)

    def test_years_are_sorted_and_deduplicated_and_limit_is_numeric(self):
        fetch = Mock(return_value=[{}, {}])
        result, text = self.invoke({"HI_DRYRUN_YEARS": "2026,2025,2026,", "HI_DRYRUN_LIMIT": "2"}, fetch)
        self.assertEqual(result, 0)
        fetch.assert_called_once_with(years=[2025, 2026], limit=2, dry_run=True)
        self.assertIn("2 countable Hawaii notice", text)

    def test_bad_year_stops_before_fetching(self):
        fetch = Mock()
        result, _ = self.invoke({"HI_DRYRUN_YEARS": "not-a-year"}, fetch)
        self.assertEqual(result, 1)
        fetch.assert_not_called()

    def test_non_numeric_limit_is_not_forwarded(self):
        fetch = Mock(return_value=[])
        self.invoke({"HI_DRYRUN_LIMIT": "many"}, fetch)
        fetch.assert_called_once_with(years=None, limit=None, dry_run=True)

    def test_hard_ocr_failure_is_not_reported_as_success(self):
        with self.assertRaisesRegex(RuntimeError, "fixture OCR failure"):
            self.invoke({}, Mock(side_effect=RuntimeError("fixture OCR failure")))
