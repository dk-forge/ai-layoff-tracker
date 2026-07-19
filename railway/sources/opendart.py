"""Discovery-only OpenDART disclosure-list client plus an evidence-only document stage.

This adapter uses the official OpenDART list API and, for a single
already-listed disclosure, can download the original filing body via the
official ``document.xml`` endpoint and scan it for the reviewable Korean
layoff vocabulary in ``sources.layoff_language``.  Neither stage classifies a
disclosure, posts a tracker event, reports live source health, or changes the
market registry: the document stage returns candidates-with-excerpts for a
human/agent review gate (docs/PROMOTION_REVIEW.md).  A future connector must
still add a persisted replay cursor and per-run source health before it can
become a coverage claim.
"""
from __future__ import annotations

import io
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote

import requests

from sources import layoff_language


API_URL = "https://opendart.fss.or.kr/api/list.json"
DOCUMENT_API_URL = "https://opendart.fss.or.kr/api/document.xml"
VIEWER_URL = "https://englishdart.fss.or.kr/dsbh001/main.do?rcpNo="
USER_AGENT = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
MAX_ATTEMPTS = 3
PAGE_SIZE = 100  # Official documented maximum.

# DART's reception system runs 07:30-19:00 KST on business days (filings after
# 18:00 are stamped for the next day), so a calendar day's disclosure list is
# complete shortly after 19:00 KST.  20:00 KST is the conservative threshold
# used by ``latest_complete_list_date``.
KST = timezone(timedelta(hours=9))
LIST_COMPLETE_HOUR_KST = 20

# Defensive bounds for the evidence-only document stage.
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_TEXT_CHARS = 800_000


class OpenDartApiError(RuntimeError):
    """Classified, secret-free OpenDART request failure."""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


@dataclass(frozen=True)
class OpenDartDisclosureList:
    start_date: str
    end_date: str
    retrieved_at: str
    disclosures: tuple[dict[str, Any], ...]
    complete: bool


def _valid_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value or "")
    if not re.fullmatch(r"\d{8}", text):
        raise ValueError("date must be YYYYMMDD")
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("date must be a real calendar date") from exc
    return text


def viewer_url(receipt_number: str) -> str:
    value = str(receipt_number or "").strip()
    if not re.fullmatch(r"\d{14}", value):
        raise ValueError("receipt_number must be a 14-digit OpenDART filing number")
    return VIEWER_URL + quote(value, safe="")


def _candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    receipt = str(row.get("rcept_no") or "").strip()
    if not receipt:
        return None
    return {
        "filing_number": receipt,
        "corporation_code": str(row.get("corp_code") or ""),
        "corporation_name": str(row.get("corp_name") or ""),
        "stock_code": str(row.get("stock_code") or ""),
        "report_name": str(row.get("report_nm") or ""),
        "filer_name": str(row.get("flr_nm") or ""),
        "filing_date": str(row.get("rcept_dt") or ""),
        "remarks": str(row.get("rm") or ""),
        "source_name": "OpenDART disclosure list",
        "source_url": viewer_url(receipt),
        "scope": "Discovery metadata only; filing body has not been retrieved or classified as a layoff event.",
    }


def _delay(attempt: int) -> float:
    return min(30.0, float(2 ** attempt))


def _fetch_page(params: dict[str, str], get: Callable[..., Any], sleep: Callable[[float], None]) -> dict[str, Any]:
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = get(API_URL, params=params, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=30)
        except Exception as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise OpenDartApiError("network", "OpenDART disclosure-list request failed") from exc
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code in {401, 403}:
            raise OpenDartApiError("authentication", "OpenDART disclosure-list authentication was rejected")
        if status_code == 429 or status_code >= 500:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise OpenDartApiError("rate_limited" if status_code == 429 else "upstream", "OpenDART disclosure-list request could not complete")
        if status_code >= 400:
            raise OpenDartApiError("request", f"OpenDART disclosure-list returned HTTP {status_code}")
        try:
            payload = response.json()
        except Exception as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise OpenDartApiError("malformed_response", "OpenDART disclosure-list returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise OpenDartApiError("malformed_response", "OpenDART disclosure-list returned a non-object response")
        status = str(payload.get("status") or "")
        if status == "000":
            return payload
        if status == "013":  # Official "no data" response, not a failure.
            return {"status": status, "list": [], "total_page": 1}
        if status == "020":
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise OpenDartApiError("rate_limited", "OpenDART reported its request limit")
        if status in {"010", "011", "012", "901"}:
            raise OpenDartApiError("authentication", "OpenDART rejected the configured credential or caller")
        if status == "800":
            raise OpenDartApiError("maintenance", "OpenDART is under maintenance")
        raise OpenDartApiError("request", "OpenDART returned an unsuccessful API status")
    raise AssertionError("unreachable")


def list_disclosures(
    start_date: str | date,
    end_date: str | date,
    api_key: str | None = None,
    *,
    http_get: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> OpenDartDisclosureList:
    """Fetch all bounded pages for one requested date range without publishing data."""
    start, end = _valid_date(start_date), _valid_date(end_date)
    if end < start:
        raise ValueError("end_date cannot precede start_date")
    key = api_key or os.environ.get("OPENDART_API_KEY_KR", "")
    if not key:
        raise OpenDartApiError("configuration", "OPENDART_API_KEY_KR is required")
    get = http_get or requests.get
    rows: list[dict[str, Any]] = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        payload = _fetch_page({"crtfc_key": key, "bgn_de": start, "end_de": end, "page_no": str(page), "page_count": str(PAGE_SIZE)}, get, sleep)
        listed = payload.get("list")
        if not isinstance(listed, list):
            raise OpenDartApiError("malformed_response", "OpenDART successful response omitted disclosure list")
        total_pages = max(1, int(payload.get("total_page") or 1))
        if total_pages > 10000:  # Defensive bound against malformed responses.
            raise OpenDartApiError("malformed_response", "OpenDART reported an unreasonable page count")
        rows.extend(candidate for candidate in (_candidate(item) for item in listed if isinstance(item, dict)) if candidate is not None)
        page += 1
    return OpenDartDisclosureList(start, end, datetime.now(timezone.utc).isoformat(), tuple(rows), complete=True)


def next_cursor_after_success(end_date: str | date, result: OpenDartDisclosureList) -> str | None:
    """Advance only after a complete matching range; failures stay queued."""
    end = _valid_date(end_date)
    if not isinstance(result, OpenDartDisclosureList) or not result.complete or result.end_date != end:
        return None
    return (datetime.strptime(end, "%Y%m%d").date() + timedelta(days=1)).isoformat()


def latest_complete_list_date(now: datetime | None = None) -> date:
    """Most recent KST calendar day whose disclosure list is already complete.

    DART reception closes at 19:00 KST, so after ``LIST_COMPLETE_HOUR_KST``
    the probe can safely request *today* (KST) instead of always yesterday.
    Before that hour the previous KST day is the newest complete list.  With
    the twice-daily cron (13:00/22:00 UTC = 22:00/07:00 KST) every KST day is
    probed once the same evening and re-checked the next morning.
    """
    moment = (now or datetime.now(timezone.utc)).astimezone(KST)
    if moment.hour >= LIST_COMPLETE_HOUR_KST:
        return moment.date()
    return moment.date() - timedelta(days=1)


@dataclass(frozen=True)
class OpenDartDocumentEvidence:
    filing_number: str
    retrieved_at: str
    source_url: str            # official public viewer URL
    text_extracted: bool       # False when the archive held no text members
    text_length: int           # characters scanned (post-markup-stripping)
    truncated: bool            # True when MAX_TEXT_CHARS clipped the body
    matches: tuple[layoff_language.TermMatch, ...]
    is_review_candidate: bool  # >=1 strong vocabulary match
    scope: str


def _decode_member(raw: bytes) -> str:
    """Decode a DART XML member: UTF-8 first, then the legacy EUC-KR family."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp949", "replace")


def _document_text_from_archive(content: bytes) -> tuple[str, bool]:
    """Extract bounded plain text from a ``document.xml`` ZIP archive.

    Members are read in filename order; DART ships the original filing XML
    (and any corrected versions) inside one archive.  Returns the stripped
    text and whether the size cap truncated it.  Raises ``BadZipFile`` for a
    corrupt archive so the caller can retry the download.
    """
    archive = zipfile.ZipFile(io.BytesIO(content))  # May raise BadZipFile.
    members = sorted(
        (info for info in archive.infolist()
         if not info.is_dir() and info.filename.lower().endswith((".xml", ".xhtml", ".html", ".htm"))),
        key=lambda info: info.filename)
    pieces: list[str] = []
    total = 0
    truncated = False
    for info in members:
        if info.file_size > MAX_MEMBER_BYTES:
            raise OpenDartApiError("malformed_response",
                                   "OpenDART document member exceeded the defensive size bound")
        text = layoff_language.strip_markup(_decode_member(archive.read(info.filename)))
        if not text:
            continue
        remaining = MAX_TEXT_CHARS - total
        if remaining <= 0:
            truncated = True
            break
        if len(text) > remaining:
            text = text[:remaining]
            truncated = True
        pieces.append(text)
        total += len(text) + 1
    return " ".join(pieces), truncated


def _classify_error_body(content: bytes) -> OpenDartApiError:
    """Map a non-ZIP ``document.xml`` response (an XML error body) to an error."""
    text = _decode_member(bytes(content[:2000]))
    found = re.search(r"<status>\s*(\d{3})\s*</status>", text)
    status = found.group(1) if found else ""
    if status == "013":
        return OpenDartApiError("not_found", "OpenDART has no document for the requested filing number")
    if status == "020":
        return OpenDartApiError("rate_limited", "OpenDART reported its request limit")
    if status in {"010", "011", "012", "901"}:
        return OpenDartApiError("authentication", "OpenDART rejected the configured credential or caller")
    if status == "800":
        return OpenDartApiError("maintenance", "OpenDART is under maintenance")
    return OpenDartApiError("malformed_response", "OpenDART returned no downloadable document body")


def fetch_document_evidence(
    receipt_number: str,
    api_key: str | None = None,
    *,
    http_get: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> OpenDartDocumentEvidence:
    """Download one filing body (official ``document.xml`` endpoint) and scan it.

    Evidence only: the result carries bounded excerpts around Korean layoff
    vocabulary so a reviewer can judge the disclosure.  It never creates,
    posts, or upserts a tracker event, and callers must keep it behind the
    promotion review gate (docs/PROMOTION_REVIEW.md).  429/5xx and corrupt
    transfers retry a bounded number of times; failures raise classified
    exceptions.
    """
    source_url = viewer_url(receipt_number)  # Validates the number shape first.
    key = api_key or os.environ.get("OPENDART_API_KEY_KR", "")
    if not key:
        raise OpenDartApiError("configuration", "OPENDART_API_KEY_KR is required")
    get = http_get or requests.get
    params = {"crtfc_key": key, "rcept_no": str(receipt_number).strip()}
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = get(DOCUMENT_API_URL, params=params,
                           headers={"User-Agent": USER_AGENT}, timeout=60)
        except Exception as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise OpenDartApiError("network", "OpenDART document request failed") from exc
        status = int(getattr(response, "status_code", 0) or 0)
        if status in {401, 403}:
            raise OpenDartApiError("authentication", "OpenDART document authentication was rejected")
        if status == 429 or status >= 500:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise OpenDartApiError("rate_limited" if status == 429 else "upstream",
                                   "OpenDART document request could not complete")
        if status >= 400:
            raise OpenDartApiError("request", f"OpenDART document endpoint returned HTTP {status}")
        content = getattr(response, "content", None)
        if not isinstance(content, (bytes, bytearray)) or not content:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise OpenDartApiError("malformed_response", "OpenDART document response was empty")
        if len(content) > MAX_ARCHIVE_BYTES:
            raise OpenDartApiError("malformed_response",
                                   "OpenDART document exceeded the defensive size bound")
        if not bytes(content[:2]) == b"PK":
            error = _classify_error_body(bytes(content))
            if error.kind == "rate_limited" and attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise error
        try:
            text, truncated = _document_text_from_archive(bytes(content))
        except zipfile.BadZipFile as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_delay(attempt))
                continue
            raise OpenDartApiError("malformed_response",
                                   "OpenDART document was not a readable archive") from exc
        matches = layoff_language.detect_layoff_language(text)
        return OpenDartDocumentEvidence(
            filing_number=str(receipt_number).strip(),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            source_url=source_url,
            text_extracted=bool(text),
            text_length=len(text),
            truncated=truncated,
            matches=matches,
            is_review_candidate=layoff_language.is_review_candidate(matches),
            scope=("Evidence only: bounded excerpts for human/agent review; "
                   "no tracker event has been created or classified."),
        )
    raise AssertionError("unreachable")
