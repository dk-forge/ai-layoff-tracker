"""Eurofound ERM is a live, source-linked collector and must report health.

The `running` note is now published through `publish_source_health`, which
reports OK / DEFERRED / FAILURE rather than a bool: the note is a PRECONDITION
here, and a hard raise on a failed note made the health ledger's own
availability a precondition for the import (2026-08-12). The /bulk write goes
through `host_call.post_json`, which is stdlib urllib — so these stubs replace
that, not `requests.post`.
"""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import erm_import
import http_retry


class ErmHealthTests(unittest.TestCase):
    def test_success_reports_running_then_source_linked_completion(self):
        reports = []
        row = {
            "Id": "123", "Announcement date": "2026-07-01", "Country": "France",
            "Company": "Example SA", "Sector": "Information / Computing",
            "Restructuring type": "Restructuring", "Employment Change": "-250",
        }
        with patch.dict(os.environ, {"WP_SITE_URL": "https://example.test", "WP_API_KEY": "key"}, clear=False), \
             patch.object(erm_import, "publish_source_health",
                          side_effect=lambda *args: (reports.append(args) or http_retry.OK)), \
             patch.object(erm_import, "report_source_health", side_effect=lambda *args: (reports.append(args) or True)), \
             patch.object(erm_import, "fetch_events", return_value=[row]), \
             patch.object(erm_import.host_call, "post_json", lambda *a, **kw: {"ok": True}):
            entries = erm_import.run()

        self.assertEqual(len(entries), 1)
        self.assertEqual(reports[0], ("eurofound_erm", "running", 0, "daily Eurofound ERM import in progress"))
        self.assertEqual(reports[-1], ("eurofound_erm", "ok", 1, "1 source-linked ERM announcement event(s) imported"))

    def test_collection_error_is_visible_and_propagates(self):
        reports = []
        with patch.dict(os.environ, {"WP_SITE_URL": "https://example.test", "WP_API_KEY": "key"}, clear=False), \
             patch.object(erm_import, "publish_source_health",
                          side_effect=lambda *args: (reports.append(args) or http_retry.OK)), \
             patch.object(erm_import, "report_source_health", side_effect=lambda *args: (reports.append(args) or True)), \
             patch.object(erm_import, "fetch_events", side_effect=RuntimeError("upstream unavailable")):
            with self.assertRaisesRegex(RuntimeError, "upstream unavailable"):
                erm_import.run()

        self.assertEqual(reports[-1], ("eurofound_erm", "degraded", 0, "ERM import failed: upstream unavailable"))

    def test_a_running_note_the_host_never_answered_defers_it(self):
        """Before the CSV is fetched, nothing can be half-imported — so this is
        the one state where a bulk importer may legitimately stand down."""
        with patch.dict(os.environ, {"WP_SITE_URL": "https://example.test", "WP_API_KEY": "key"}, clear=False), \
             patch.object(erm_import, "publish_source_health",
                          return_value=http_retry.DEFERRED):
            with self.assertRaises(erm_import.host_call.Deferred):
                erm_import.run()

    def test_a_running_note_the_host_REFUSED_is_still_loud(self):
        """A wrong key is settled: it fails identically tomorrow."""
        with patch.dict(os.environ, {"WP_SITE_URL": "https://example.test", "WP_API_KEY": "key"}, clear=False), \
             patch.object(erm_import, "publish_source_health",
                          return_value=http_retry.FAILURE):
            with self.assertRaisesRegex(RuntimeError, "running health status"):
                erm_import.run()


if __name__ == "__main__":
    unittest.main()
