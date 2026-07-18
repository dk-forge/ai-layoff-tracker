"""Discovery-only EDINET document-list client.

This module reads one official EDINET API v2 daily document list.  It does not
download filing bodies, perform keyword extraction, create tracker events, or
change the market registry.  A future scheduled connector must persist its
own cursor only after the complete list call has succeeded and must report
source health around that work.

EDINET's terms direct automated collection to its API rather than scraping.
Published candidates retain an official viewer URL and document status fields;
they are not a claim that a filing is a layoff event.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote

import requests


API_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
VIEWER_URL = "https://disclosure2.edinet-fsa.go.jp/WEEK0010.aspx?docID="
USER_AGENT = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
MAX_ATTEMPTS = 3


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
