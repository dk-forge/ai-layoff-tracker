"""Focused guards for the inactive EDINET discovery-only foundation."""
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

from sources.edinet import EdinetApiError, list_documents_for_date, next_cursor_after_success


class _Response:
    def __init__(self, status_code=200, payload=None, error=None):
        self.status_code = status_code
        self._payload = payload
        self._error = error

    def json(self):
        if self._error:
            raise self._error
        return self._payload


class EdinetDiscoveryTests(unittest.TestCase):
    def test_list_keeps_statuses_and_public_viewer_link_without_event_fields(self):
        calls = []

        def get(*args, **kwargs):
            calls.append((args, kwargs))
            return _Response(payload={"results": [{
                "docID": "S100ABCD", "filerName": "Example Co", "formCode": "030000",
                "docDescription": "Extraordinary report", "withdrawalStatus": "0",
                "docInfoEditStatus": "0", "disclosureStatus": "1", "legalStatus": "1",
            }]})

        result = list_documents_for_date("2026-07-01", "secret", http_get=get)
        self.assertEqual(result.requested_date, "2026-07-01")
        self.assertEqual(len(result.documents), 1)
        row = result.documents[0]
        self.assertEqual(row["withdrawal_status"], "0")
        self.assertIn("docID=S100ABCD", row["source_url"])
        self.assertNotIn("job_count", row)
        self.assertNotIn("employer_country", row)
        self.assertEqual(calls[0][1]["params"]["type"], "2")
        self.assertEqual(calls[0][1]["params"]["date"], "2026-07-01")
        self.assertEqual(calls[0][1]["params"]["Subscription-Key"], "secret")

    def test_rate_limit_is_bounded_and_does_not_produce_cursor(self):
        sleeps = []
        response = _Response(status_code=429)
        with self.assertRaisesRegex(EdinetApiError, "rate limited") as caught:
            list_documents_for_date("2026-07-01", "secret", http_get=lambda *_, **__: response,
                                    sleep=sleeps.append)
        self.assertEqual(caught.exception.kind, "rate_limited")
        self.assertEqual(len(sleeps), 2)
        self.assertIsNone(next_cursor_after_success("2026-07-01", object()))

    def test_cursor_advances_only_for_the_matching_successful_day(self):
        result = list_documents_for_date(
            "2026-07-01", "secret",
            http_get=lambda *_, **__: _Response(payload={"results": []}),
        )
        self.assertEqual(next_cursor_after_success("2026-07-01", result), "2026-07-02")
        self.assertIsNone(next_cursor_after_success("2026-07-02", result))


if __name__ == "__main__":
    unittest.main()
