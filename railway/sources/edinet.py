"""Discovery-only EDINET document-list client plus an evidence-only document stage.

This module reads the official EDINET API v2 daily document list and, for a
single already-listed document, can download that filing body and scan it for
the reviewable Japanese layoff vocabulary in ``sources.layoff_language``.
Neither stage creates tracker events, posts to WordPress, or changes the
market registry: the document stage returns candidates-with-excerpts for a
human/agent review gate (docs/PROMOTION_REVIEW.md).  A future scheduled
connector must persist its own cursor only after the complete list call has
succeeded and must report source health around that work.

EDINET's terms direct automated collection to its API rather than scraping.
Published candidates retain an official viewer URL and document status fields;
they are not a claim that a filing is a layoff event.
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


API_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
DOCUMENT_API_URL = "https://api.edinet-fsa.go.jp/api/v2/documents/"
VIEWER_URL = "https://disclosure2.edinet-fsa.go.jp/WEEK0010.aspx?docID="
USER_AGENT = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
MAX_ATTEMPTS = 3

# EDINET accepts submissions on business days 9:00-17:15 JST, so a calendar
# day's document list is complete shortly after 17:15 JST.  18:00 JST is the
# conservative completeness threshold used by ``latest_complete_list_date``.
JST = timezone(timedelta(hours=9))
LIST_COMPLETE_HOUR_JST = 18

# Defensive bounds for the evidence-only document stage.  Real type=1 archives
# are a few MB; annual reports strip to a few hundred KB of text.
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_TEXT_CHARS = 800_000


class EdinetApiError(RuntimeError):
    """A classified, secret-free EDINET request failure."""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


@dataclass(frozen=True)
class EdinetDocumentList:
    requested_date: str
    retrieved_at: str
    documents: tuple[dict[str, Any], ...]


def _valid_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("requested date must be YYYY-MM-DD")
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("requested date must be a real calendar date") from exc
    return text


def viewer_url(doc_id: str) -> str:
    """Return the public EDINET viewer URL for a syntactically safe document ID."""
    value = str(doc_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", value):
        raise ValueError("doc_id must contain only letters, digits, _ or -")
    return VIEWER_URL + quote(value, safe="")


def _candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    doc_id = str(row.get("docID") or "").strip()
    if not doc_id:
        return None
    # Retain official metadata exactly enough to distinguish a later
    # correction/withdrawal from an original document.  No factual field is
    # interpreted as a job count, job location, industry, or employer domicile.
    return {
        "document_id": doc_id,
        "filer_name": str(row.get("filerName") or ""),
        "edinet_code": str(row.get("edinetCode") or ""),
        "securities_code": str(row.get("secCode") or ""),
        "form_code": str(row.get("formCode") or ""),
        "document_type_code": str(row.get("docTypeCode") or ""),
        "document_description": str(row.get("docDescription") or ""),
        "submitted_at": str(row.get("submitDateTime") or ""),
        "parent_document_id": str(row.get("parentDocID") or ""),
        "withdrawal_status": str(row.get("withdrawalStatus") or ""),
        "document_info_edit_status": str(row.get("docInfoEditStatus") or ""),
        "disclosure_status": str(row.get("disclosureStatus") or ""),
        "legal_status": str(row.get("legalStatus") or ""),
        "source_name": "EDINET document list",
        "source_url": viewer_url(doc_id),
        "scope": "Discovery metadata only; filing body has not been retrieved or classified as a layoff event.",
    }


def _retry_delay(attempt: int) -> float:
    return min(30.0, float(2 ** attempt))


def list_documents_for_date(
    requested_date: str | date,
    api_key: str | None = None,
    *,
    http_get: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> EdinetDocumentList:
    """Fetch one complete daily metadata list from the official API.

    ``type=2`` requests the document list and metadata.  The API key is passed
    only as the documented request parameter and is never included in errors
    or logs.  429/5xx errors retry a bounded number of times; callers receive
    a classified exception and therefore must not advance a persisted cursor.
    """
    day = _valid_date(requested_date)
    key = api_key or os.environ.get("EDINET_API_KEY_JP", "")
    if not key:
        raise EdinetApiError("configuration", "EDINET_API_KEY_JP is required")
    get = http_get or requests.get
    params = {"date": day, "type": "2", "Subscription-Key": key}
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = get(
                API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=30,
            )
        except Exception as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("network", "EDINET document-list request failed") from exc
        status = int(getattr(response, "status_code", 0) or 0)
        if status == 429:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("rate_limited", "EDINET document-list request was rate limited")
        if status in {401, 403}:
            raise EdinetApiError("authentication", "EDINET document-list authentication was rejected")
        if status >= 500:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("upstream", "EDINET document-list service failed")
        if status >= 400:
            raise EdinetApiError("request", f"EDINET document-list returned HTTP {status}")
        try:
            payload = response.json()
        except Exception as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("malformed_response", "EDINET document-list returned invalid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise EdinetApiError("malformed_response", "EDINET document-list omitted results")
        candidates = tuple(
            candidate for candidate in (_candidate(row) for row in payload["results"] if isinstance(row, dict))
            if candidate is not None
        )
        return EdinetDocumentList(
            requested_date=day,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            documents=candidates,
        )
    raise AssertionError("unreachable")


def next_cursor_after_success(requested_date: str | date, result: EdinetDocumentList) -> str | None:
    """Return the next daily cursor only for the matching successful result.

    A failed, partial, or mismatched list request returns ``None`` so a future
    scheduler must retry the same day instead of skipping coverage.
    """
    day = _valid_date(requested_date)
    if not isinstance(result, EdinetDocumentList) or result.requested_date != day:
        return None
    return (date.fromisoformat(day) + timedelta(days=1)).isoformat()


def latest_complete_list_date(now: datetime | None = None) -> date:
    """Most recent JST calendar day whose document list is already complete.

    EDINET submissions close at 17:15 JST, so after ``LIST_COMPLETE_HOUR_JST``
    the probe can safely request *today* (JST) instead of always yesterday.
    Before that hour the previous JST day is the newest complete list.  With
    the twice-daily cron (13:00/22:00 UTC = 22:00/07:00 JST) every JST day is
    probed once the same evening and re-checked the next morning.
    """
    moment = (now or datetime.now(timezone.utc)).astimezone(JST)
    if moment.hour >= LIST_COMPLETE_HOUR_JST:
        return moment.date()
    return moment.date() - timedelta(days=1)


@dataclass(frozen=True)
class EdinetDocumentEvidence:
    document_id: str
    retrieved_at: str
    source_url: str            # official public viewer URL
    text_extracted: bool       # False when the archive held no text members
    text_length: int           # characters scanned (post-markup-stripping)
    truncated: bool            # True when MAX_TEXT_CHARS clipped the body
    matches: tuple[layoff_language.TermMatch, ...]
    is_review_candidate: bool  # >=1 strong vocabulary match
    scope: str


def _document_text_from_archive(content: bytes) -> tuple[str, bool]:
    """Extract bounded plain text from a type=1 EDINET archive.

    Only ``XBRL/PublicDoc`` HTML/XBRL members are read, in filename order
    (EDINET numbers them in document order).  Returns the stripped text and
    whether the size cap truncated it.  Raises ``zipfile.BadZipFile`` for a
    corrupt archive so the caller can retry the download.
    """
    archive = zipfile.ZipFile(io.BytesIO(content))  # May raise BadZipFile.
    members = sorted(
        info for info in archive.infolist()
        if not info.is_dir()
        and info.filename.replace("\\", "/").split("/")[0] != ".."
        and "PublicDoc" in info.filename
        and info.filename.lower().endswith((".htm", ".html", ".xml"))
    , key=lambda info: info.filename)
    pieces: list[str] = []
    total = 0
    truncated = False
    for info in members:
        if info.file_size > MAX_MEMBER_BYTES:
            raise EdinetApiError("malformed_response",
                                 "EDINET document member exceeded the defensive size bound")
        text = layoff_language.strip_markup(archive.read(info.filename).decode("utf-8", "replace"))
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


def fetch_document_evidence(
    doc_id: str,
    api_key: str | None = None,
    *,
    http_get: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> EdinetDocumentEvidence:
    """Download one filing body (official ``type=1`` endpoint) and scan it.

    Evidence only: the result carries bounded excerpts around Japanese layoff
    vocabulary so a reviewer can judge the filing.  It never creates, posts,
    or upserts a tracker event, and callers must keep it behind the promotion
    review gate (docs/PROMOTION_REVIEW.md).  429/5xx and corrupt transfers
    retry a bounded number of times; failures raise classified exceptions.
    """
    url = DOCUMENT_API_URL + quote(str(doc_id or "").strip(), safe="")
    viewer = viewer_url(doc_id)  # Validates the ID shape before any request.
    key = api_key or os.environ.get("EDINET_API_KEY_JP", "")
    if not key:
        raise EdinetApiError("configuration", "EDINET_API_KEY_JP is required")
    get = http_get or requests.get
    params = {"type": "1", "Subscription-Key": key}
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = get(url, params=params,
                           headers={"User-Agent": USER_AGENT}, timeout=60)
        except Exception as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("network", "EDINET document request failed") from exc
        status = int(getattr(response, "status_code", 0) or 0)
        if status == 429:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("rate_limited", "EDINET document request was rate limited")
        if status in {401, 403}:
            raise EdinetApiError("authentication", "EDINET document authentication was rejected")
        if status == 404:
            raise EdinetApiError("not_found", "EDINET document is not available for download")
        if status >= 500:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("upstream", "EDINET document service failed")
        if status >= 400:
            raise EdinetApiError("request", f"EDINET document endpoint returned HTTP {status}")
        content = getattr(response, "content", None)
        if not isinstance(content, (bytes, bytearray)) or not content:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("malformed_response", "EDINET document response was empty")
        if len(content) > MAX_ARCHIVE_BYTES:
            raise EdinetApiError("malformed_response",
                                 "EDINET document exceeded the defensive size bound")
        if not bytes(content[:2]) == b"PK":
            # The API answers JSON metadata (e.g. status 404) instead of a ZIP
            # when the document cannot be served; never treat that as text.
            raise EdinetApiError("not_found", "EDINET returned no downloadable document body")
        try:
            text, truncated = _document_text_from_archive(bytes(content))
        except zipfile.BadZipFile as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise EdinetApiError("malformed_response",
                                 "EDINET document was not a readable archive") from exc
        matches = layoff_language.detect_layoff_language(text)
        return EdinetDocumentEvidence(
            document_id=str(doc_id).strip(),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            source_url=viewer,
            text_extracted=bool(text),
            text_length=len(text),
            truncated=truncated,
            matches=matches,
            is_review_candidate=layoff_language.is_review_candidate(matches),
            scope=("Evidence only: bounded excerpts for human/agent review; "
                   "no tracker event has been created or classified."),
        )
    raise AssertionError("unreachable")
