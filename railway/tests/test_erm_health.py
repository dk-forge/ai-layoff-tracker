"""Eurofound ERM is a live, source-linked collector and must report health."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("requests", SimpleNamespace())

import erm_import


class _Response:
    status_code = 200
    text = ""

    @staticmethod
    def json():
        return {"ok": True}


class ErmHealthTests(unittest.TestCase):
    def test_success_reports_running_then_source_linked_completion(self):
        reports = []
        row = {
            "Id": "123", "Announcement date": "2026-07-01", "Country": "France",
            "Company": "Example SA", "Sector": "Information / Computing",
            "Restructuring type": "Restructuring", "Employment Change": "-250",
        }
        with patch.dict(os.environ, {"WP_SITE_URL": "https://example.test", "WP_API_KEY": "key"}, clear=False), \
             patch.object(erm_import, "report_source_health", side_effect=lambda *args: (reports.append(args) or True)), \
             patch.object(erm_import, "fetch_events", return_value=[row]), \
             patch.object(erm_import.requests, "post", return_value=_Response(), create=True):
            entries = erm_import.run()

        self.assertEqual(len(entries), 1)
        self.assertEqual(reports[0], ("eurofound_erm", "running", 0, "daily Eurofound ERM import in progress"))
        self.assertEqual(reports[-1], ("eurofound_erm", "ok", 1, "1 source-linked ERM announcement event(s) imported"))

    def test_collection_error_is_visible_and_propagates(self):
        reports = []
        with patch.dict(os.environ, {"WP_SITE_URL": "https://example.test", "WP_API_KEY": "key"}, clear=False), \
             patch.object(erm_import, "report_source_health", side_effect=lambda *args: (reports.append(args) or True)), \
             patch.object(erm_import, "fetch_events", side_effect=RuntimeError("upstream unavailable")):
            with self.assertRaisesRegex(RuntimeError, "upstream unavailable"):
                erm_import.run()

        self.assertEqual(reports[-1], ("eurofound_erm", "degraded", 0, "ERM import failed: upstream unavailable"))


if __name__ == "__main__":
    unittest.main()
