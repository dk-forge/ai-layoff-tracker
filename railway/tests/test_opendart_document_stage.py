"""Guards for the evidence-only OpenDART document stage and probe-window timing."""
import io
import sys
import unittest
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources.opendart import (
    OpenDartApiError,
    fetch_document_evidence,
    latest_complete_list_date,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _Response:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


def _archive(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, raw in members.items():
            zf.writestr(name, raw)
    return buffer.getvalue()


def _xml(text: str, encoding: str) -> bytes:
    return f'<?xml version="1.0"?><DOCUMENT><BODY>{text}</BODY></DOCUMENT>'.encode(
        encoding, "replace")


class OpenDartDocumentStageTests(unittest.TestCase):
    def test_real_filing_text_produces_a_candidate_with_excerpts_only(self):
        text = (FIXTURES / "opendart_kr_20260714000459_kookminbank_prospectus.txt").read_text()
        content = _archive({"20260714000459.xml": _xml(text, "utf-8")})
        calls = []

        def get(url, **kwargs):
            calls.append((url, kwargs))
            return _Response(content=content)

        evidence = fetch_document_evidence("20260714000459", "secret", http_get=get)
        self.assertTrue(evidence.is_review_candidate)
        self.assertIn("희망퇴직", {m.term for m in evidence.matches})
        self.assertIn("rcpNo=20260714000459", evidence.source_url)
        self.assertIn("no tracker event", evidence.scope)
        url, kwargs = calls[0]
        self.assertEqual(url, "https://opendart.fss.or.kr/api/document.xml")
        self.assertEqual(kwargs["params"]["rcept_no"], "20260714000459")
        self.assertEqual(kwargs["params"]["crtfc_key"], "secret")
        self.assertFalse(hasattr(evidence, "job_count"))
        self.assertFalse(hasattr(evidence, "company_name"))

    def test_legacy_euc_kr_document_bodies_are_decoded(self):
        text = (FIXTURES / "opendart_kr_20260714000427_lbsemicon_registration.txt").read_text()
        content = _archive({"20260714000427.xml": _xml(text, "cp949")})
        evidence = fetch_document_evidence(
            "20260714000427", "secret", http_get=lambda *_, **__: _Response(content=content))
        self.assertTrue(evidence.is_review_candidate)
        self.assertIn("희망퇴직", {m.term for m in evidence.matches})

    def test_restructuring_noise_without_a_workforce_event_is_refused(self):
        text = (FIXTURES / "opendart_kr_20260716000545_hanjin_negative.txt").read_text()
        content = _archive({"20260716000545.xml": _xml(text, "utf-8")})
        evidence = fetch_document_evidence(
            "20260716000545", "secret", http_get=lambda *_, **__: _Response(content=content))
        self.assertFalse(evidence.is_review_candidate)
        self.assertIn("구조조정", {m.term for m in evidence.matches})

    def test_xml_error_body_is_classified_not_scanned(self):
        body = b'<?xml version="1.0"?><result><status>013</status><message>none</message></result>'
        with self.assertRaises(OpenDartApiError) as caught:
            fetch_document_evidence(
                "20260101000001", "secret", http_get=lambda *_, **__: _Response(content=body))
        self.assertEqual(caught.exception.kind, "not_found")

    def test_rate_limit_error_body_retries_then_classifies(self):
        sleeps = []
        body = b"<result><status>020</status></result>"
        with self.assertRaises(OpenDartApiError) as caught:
            fetch_document_evidence("20260101000001", "secret",
                                    http_get=lambda *_, **__: _Response(content=body),
                                    sleep=sleeps.append)
        self.assertEqual(caught.exception.kind, "rate_limited")
        self.assertEqual(len(sleeps), 2)

    def test_invalid_receipt_number_never_makes_a_request(self):
        def get(*_, **__):
            raise AssertionError("no request may be sent for a malformed number")
        with self.assertRaises(ValueError):
            fetch_document_evidence("not-a-number", "secret", http_get=get)


class OpenDartProbeWindowTests(unittest.TestCase):
    def test_evening_run_probes_the_just_closed_kst_day(self):
        # 13:00 UTC == 22:00 KST: DART reception closed at 19:00 KST, so
        # today (KST) is complete and must be probed instead of yesterday.
        now = datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc)
        self.assertEqual(latest_complete_list_date(now), date(2026, 7, 18))

    def test_morning_run_rechecks_the_previous_kst_day(self):
        now = datetime(2026, 7, 18, 22, 0, tzinfo=timezone.utc)
        self.assertEqual(latest_complete_list_date(now), date(2026, 7, 18))

    def test_completeness_boundary_is_20_00_kst(self):
        self.assertEqual(
            latest_complete_list_date(datetime(2026, 7, 18, 10, 59, tzinfo=timezone.utc)),
            date(2026, 7, 17))
        self.assertEqual(
            latest_complete_list_date(datetime(2026, 7, 18, 11, 0, tzinfo=timezone.utc)),
            date(2026, 7, 18))


if __name__ == "__main__":
    unittest.main()
