"""Focused guards for the inactive OpenDART discovery-only foundation."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources.opendart import OpenDartApiError, list_disclosures, next_cursor_after_success


class _Response:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class OpenDartDiscoveryTests(unittest.TestCase):
    def test_paginates_official_metadata_without_creating_event_fields(self):
        calls = []
        payloads = [
            {"status": "000", "total_page": 2, "list": [{"rcept_no": "20260701000001", "corp_name": "예시", "report_nm": "Report"}]},
            {"status": "000", "total_page": 2, "list": [{"rcept_no": "20260701000002", "rm": "U"}]},
        ]
        def get(*args, **kwargs):
            calls.append((args, kwargs))
            return _Response(payloads.pop(0))
        result = list_disclosures("20260701", "20260701", "secret", http_get=get)
        self.assertTrue(result.complete)
        self.assertEqual(len(result.disclosures), 2)
        self.assertIn("rcpNo=20260701000001", result.disclosures[0]["source_url"])
        self.assertNotIn("job_count", result.disclosures[0])
        self.assertEqual(calls[1][1]["params"]["page_no"], "2")
        self.assertEqual(calls[0][1]["params"]["page_count"], "100")

    def test_empty_status_is_success_and_rate_limit_stays_unadvanced(self):
        empty = list_disclosures("20260701", "20260701", "secret", http_get=lambda *_, **__: _Response({"status": "013"}))
        self.assertEqual(empty.disclosures, ())
        sleeps = []
        with self.assertRaisesRegex(OpenDartApiError, "request limit") as caught:
            list_disclosures("20260701", "20260701", "secret", http_get=lambda *_, **__: _Response({"status": "020"}), sleep=sleeps.append)
        self.assertEqual(caught.exception.kind, "rate_limited")
        self.assertEqual(len(sleeps), 2)
        self.assertIsNone(next_cursor_after_success("20260701", object()))

    def test_cursor_requires_matching_complete_range(self):
        result = list_disclosures("20260701", "20260701", "secret", http_get=lambda *_, **__: _Response({"status": "013"}))
        self.assertEqual(next_cursor_after_success("20260701", result), "2026-07-02")
        self.assertIsNone(next_cursor_after_success("20260702", result))


if __name__ == "__main__":
    unittest.main()
