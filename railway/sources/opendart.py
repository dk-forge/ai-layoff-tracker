"""Discovery-only OpenDART disclosure-list client.

This adapter uses the official OpenDART list API only. It does not download a
filing body, classify a disclosure, post a tracker event, report live source
health, or change the market registry. A future connector must add an
evidence-only document stage, a persisted replay cursor, Korean-language
fixtures and per-run source health before it can become a coverage claim.
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


API_URL = "https://opendart.fss.or.kr/api/list.json"
VIEWER_URL = "https://englishdart.fss.or.kr/dsbh001/main.do?rcpNo="
USER_AGENT = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
MAX_ATTEMPTS = 3
PAGE_SIZE = 100  # Official documented maximum.


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
