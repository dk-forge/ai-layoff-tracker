"""Checklist parsing uses invented events and temporary local files."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tracker_crosscheck as crosscheck


class ChecklistHelpers(unittest.TestCase):
    def test_company_keys_ignore_common_suffixes_and_punctuation(self):
        self.assertEqual(crosscheck.company_key("The Example, Inc."), "example")
        self.assertEqual(crosscheck.company_key(None), "")
        self.assertEqual(crosscheck.company_key(""), "")

    def test_supported_dates_and_counts_are_normalised(self):
        for value in ["2026-1-2", "January 2, 2026", "01/02/2026"]:
            self.assertEqual(crosscheck._to_iso(value), "2026-01-02")
        self.assertEqual(crosscheck._to_iso("not a date"), "")
        self.assertEqual(crosscheck._int("About 1,234 jobs"), 1234)
        self.assertEqual(crosscheck._int(None), 0)

    def test_json_and_csv_aliases_resolve_to_the_same_checklist(self):
        expected = [{"company": "Example", "date": "2026-01-02", "approx_count": 3}]
        with tempfile.TemporaryDirectory() as directory:
            for name, text in [("input.json", json.dumps({"events": [{"employer": "Example", "effective_date": "2026-01-02", "employees": 3}, {"employer": ""}]})), ("input.csv", "Company,Date,Count\nExample,2026-01-02,3\n")]:
                path = Path(directory) / name; path.write_text(text)
                self.assertEqual(crosscheck.load_checklist(str(path)), expected)

    def test_missing_checklist_raises_and_empty_json_has_no_events(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                crosscheck.load_checklist(str(Path(directory) / "missing.json"))
            path = Path(directory) / "empty.json"; path.write_text("[]")
            self.assertEqual(crosscheck.load_checklist(str(path)), [])

    def test_api_failure_is_distinct_from_an_empty_result(self):
        from unittest.mock import Mock
        with patch.dict(crosscheck.os.environ, {"WP_SITE_URL": "https://example.invalid/blog"}), patch.object(crosscheck.blog_reads, "get", return_value=Mock(status_code=200, json=lambda: {"data": []})):
            self.assertEqual(crosscheck.query_our_tracker("Example", "", ""), [])
        with patch.object(crosscheck.blog_reads, "get", side_effect=OSError("fixture offline")):
            self.assertIsNone(crosscheck.query_our_tracker("Example", "", ""))
