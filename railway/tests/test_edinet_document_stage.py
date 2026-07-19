"""Guards for the evidence-only EDINET document stage and probe-window timing."""
import io
import json
import sys
import unittest
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("requests", SimpleNamespace())

from sources.edinet import (
    EdinetApiError,
    fetch_document_evidence,
    latest_complete_list_date,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _Response:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


def _archive(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, text in members.items():
            zf.writestr(name, text.encode("utf-8"))
    return buffer.getvalue()


def _wrap(text: str) -> str:
    return f"<html><body><p>{text}</p></body></html>"


class EdinetDocumentStageTests(unittest.TestCase):
    def test_real_filing_text_produces_a_candidate_with_excerpts_only(self):
        text = (FIXTURES / "edinet_jp_S100X44W_jdi_extraordinary.txt").read_text()
        content = _archive({
            "XBRL/PublicDoc/0101010_honbun.htm": _wrap(text),
            "XBRL/AuditDoc/ignored.htm": _wrap("監査報告書"),
            "XBRL/PublicDoc/manifest.json": "{}",  # non-text member is skipped
        })
        calls = []

        def get(url, **kwargs):
            calls.append((url, kwargs))
            return _Response(content=content)

        evidence = fetch_document_evidence("S100X44W", "secret", http_get=get)
        self.assertTrue(evidence.is_review_candidate)
        self.assertTrue(evidence.text_extracted)
        self.assertIn("希望退職", {m.term for m in evidence.matches})
        self.assertIn("docID=S100X44W", evidence.source_url)
        self.assertIn("no tracker event", evidence.scope)
        # Only the official document endpoint, with type=1 and the key param.
        url, kwargs = calls[0]
        self.assertEqual(url, "https://api.edinet-fsa.go.jp/api/v2/documents/S100X44W")
        self.assertEqual(kwargs["params"]["type"], "1")
        self.assertEqual(kwargs["params"]["Subscription-Key"], "secret")
        # The evidence object exposes no event fields to accidentally publish.
        self.assertFalse(hasattr(evidence, "job_count"))
        self.assertFalse(hasattr(evidence, "company_name"))

    def test_governance_boilerplate_is_refused(self):
        text = (FIXTURES / "edinet_jp_S100YI8X_sanken_governance_negative.txt").read_text()
        content = _archive({"XBRL/PublicDoc/0101010_honbun.htm": _wrap(text)})
        evidence = fetch_document_evidence(
            "S100YI8X", "secret", http_get=lambda *_, **__: _Response(content=content))
        self.assertFalse(evidence.is_review_candidate)
        self.assertEqual({m.tier for m in evidence.matches}, {"context"})

    def test_json_error_body_is_classified_not_scanned(self):
        body = json.dumps({"metadata": {"status": "404"}}).encode()
        with self.assertRaises(EdinetApiError) as caught:
            fetch_document_evidence(
                "S100XXXX", "secret", http_get=lambda *_, **__: _Response(content=body))
        self.assertEqual(caught.exception.kind, "not_found")

    def test_oversized_archive_is_rejected(self):
        big = _Response(content=b"PK" + b"0" * (50 * 1024 * 1024 + 1))
        with self.assertRaises(EdinetApiError) as caught:
            fetch_document_evidence("S100XXXX", "secret", http_get=lambda *_, **__: big)
        self.assertEqual(caught.exception.kind, "malformed_response")

    def test_corrupt_archive_retries_then_classifies(self):
        sleeps = []
        broken = _Response(content=b"PK\x03\x04 not a real archive")
        with self.assertRaises(EdinetApiError) as caught:
            fetch_document_evidence("S100XXXX", "secret",
                                    http_get=lambda *_, **__: broken,
                                    sleep=sleeps.append)
        self.assertEqual(caught.exception.kind, "malformed_response")
        self.assertEqual(len(sleeps), 2)

    def test_missing_key_never_makes_a_request(self):
        def get(*_, **__):
            raise AssertionError("no request may be sent without a key")
        with self.assertRaises(EdinetApiError) as caught:
            fetch_document_evidence("S100XXXX", "", http_get=get)
        self.assertEqual(caught.exception.kind, "configuration")


class EdinetProbeWindowTests(unittest.TestCase):
    def test_evening_run_probes_the_just_closed_jst_day(self):
        # 13:00 UTC == 22:00 JST: submissions closed at 17:15 JST, so today
        # (JST) is complete and must be probed instead of always yesterday.
        now = datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc)
        self.assertEqual(latest_complete_list_date(now), date(2026, 7, 18))

    def test_morning_run_rechecks_the_previous_jst_day(self):
        # 22:00 UTC == 07:00 JST next day: the new day has no filings yet.
        now = datetime(2026, 7, 18, 22, 0, tzinfo=timezone.utc)
        self.assertEqual(latest_complete_list_date(now), date(2026, 7, 18))

    def test_completeness_boundary_is_18_00_jst(self):
        self.assertEqual(
            latest_complete_list_date(datetime(2026, 7, 18, 8, 59, tzinfo=timezone.utc)),
            date(2026, 7, 17))
        self.assertEqual(
            latest_complete_list_date(datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)),
            date(2026, 7, 18))


if __name__ == "__main__":
    unittest.main()
