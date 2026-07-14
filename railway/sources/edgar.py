"""
Pulls 8-K filings from SEC EDGAR full-text search API.
Searches for workforce reduction language.

Spec deviation (the original spec would break silently): the spec's
"search-index" URL referenced response fields that the EDGAR full-text search
API does not return (`file_text`, `entity_id`, `file_path`). This module uses
the real EFTS response shape — hit `_id` is "<accession-no>:<filename>" and
`_source.ciks` holds the CIK — and fetches each filing document in a second
request to obtain its text, since full-text search returns no document body.

SEC fair-access policy: max 10 requests/second, and a descriptive User-Agent
is REQUIRED (requests without one are rejected). Set EDGAR_USER_AGENT.
"""
import html
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests

EDGAR_FTS_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

KEYWORDS = [
    "workforce reduction",
    "reduction in force",
    "layoff",
    "headcount reduction",
    "elimination of positions",
    "job cuts",
    "involuntary separation",
]

REQUEST_DELAY_SECONDS = 0.11  # stays under SEC's 10 req/s limit
RAW_TEXT_LIMIT = 3000
MAX_DOC_BYTES = 500_000  # bound tag-stripping work on huge filings


def _headers():
    user_agent = os.environ.get("EDGAR_USER_AGENT")
    if not user_agent:
        print("EDGAR warning: EDGAR_USER_AGENT is not set — SEC rejects anonymous requests")
        user_agent = "AiLayoffTracker unknown@example.com"
    return {"User-Agent": user_agent, "Accept": "application/json"}


def _parse_display_name(display_names):
    """EFTS display_names look like 'Apple Inc.  (AAPL)  (CIK 0000320193)'."""
    if not display_names:
        return "Unknown", None
    name = display_names[0]
    ticker_match = re.search(r"\(([A-Z][A-Z0-9.\-]{0,9})\)\s*\(CIK", name)
    ticker = ticker_match.group(1) if ticker_match else None
    company = re.sub(r"\s*\(CIK[^)]*\)\s*$", "", name)
    company = re.sub(r"\s*\([A-Z][A-Z0-9.\-]{0,9}\)\s*$", "", company).strip()
    return company or "Unknown", ticker


def _strip_html(markup):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_filing_text(url):
    """Fetch a filing document and return a text window centered on the first
    layoff keyword, so the relevant passage survives the length cap."""
    time.sleep(REQUEST_DELAY_SECONDS)
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    text = _strip_html(resp.text[:MAX_DOC_BYTES])
    lowered = text.lower()
    for keyword in KEYWORDS:
        idx = lowered.find(keyword)
        if idx != -1:
            start = max(0, idx - 500)
            return text[start:start + RAW_TEXT_LIMIT]
    return text[:RAW_TEXT_LIMIT]


PAGE_SIZE = 10  # EFTS fixed page size
MAX_PAGES_PER_KEYWORD = 3


def _search_keyword(keyword, start, end):
    """Paginate EFTS results — the API returns 10 hits per page, and on a
    heavy layoff day one page silently misses filings."""
    hits = []
    total = 0
    for page in range(MAX_PAGES_PER_KEYWORD):
        params = {
            "q": f'"{keyword}"',
            "dateRange": "custom",
            "startdt": start.strftime("%Y-%m-%d"),
            "enddt": end.strftime("%Y-%m-%d"),
            "forms": "8-K",
            "from": page * PAGE_SIZE,
        }
        time.sleep(REQUEST_DELAY_SECONDS)
        resp = requests.get(EDGAR_FTS_URL, params=params, headers=_headers(), timeout=30)
        resp.raise_for_status()
        payload = resp.json().get("hits", {})
        page_hits = payload.get("hits", [])
        hits.extend(page_hits)
        total = (payload.get("total") or {}).get("value", 0)
        if len(page_hits) < PAGE_SIZE or (page + 1) * PAGE_SIZE >= total:
            break

    if total > MAX_PAGES_PER_KEYWORD * PAGE_SIZE:
        print(f"EDGAR: keyword '{keyword}' matched {total} filings; "
              f"only the first {MAX_PAGES_PER_KEYWORD * PAGE_SIZE} were fetched")
    return hits


def pull_edgar_filings(days_back=1):
    """Pull 8-K filings from the last N days containing layoff language."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    return pull_edgar_filings_between(start, end)


def pull_edgar_filings_between(start, end):
    """Pull 8-K filings filed in [start, end] containing layoff language.

    Used by both the daily cron (recent window) and the historical backfill
    (monthly windows across 2024→now).
    """
    candidates = {}  # doc_url -> hit metadata, deduped across keywords
    for keyword in KEYWORDS:
        try:
            hits = _search_keyword(keyword, start, end)
        except Exception as e:
            print(f"EDGAR pull error for keyword '{keyword}': {e}")
            continue

        for hit in hits:
            source = hit.get("_source", {})
            accession, _, filename = (hit.get("_id") or "").partition(":")
            accession = source.get("adsh") or accession
            ciks = source.get("ciks") or []
            if not accession or not filename or not ciks:
                continue
            try:
                cik = str(int(ciks[0]))  # strip leading zeros
            except (ValueError, TypeError):
                continue

            doc_url = f"{SEC_ARCHIVES_BASE}/{cik}/{accession.replace('-', '')}/{filename}"
            if doc_url in candidates:
                continue

            company_name, ticker = _parse_display_name(source.get("display_names"))
            candidates[doc_url] = {
                "source_type": "8K",
                "source_name": "SEC EDGAR",
                "verification_level": "gold",
                "source_url": doc_url,
                "company_name": company_name,
                "ticker": ticker,
                "filing_date": source.get("file_date", ""),
            }

    results = []
    for doc_url, entry in candidates.items():
        try:
            entry["raw_text"] = _fetch_filing_text(doc_url)
        except Exception as e:
            print(f"EDGAR document fetch error for {doc_url}: {e}")
            continue
        if entry["raw_text"]:
            results.append(entry)

    print(f"EDGAR: {len(results)} filings pulled")
    return results
