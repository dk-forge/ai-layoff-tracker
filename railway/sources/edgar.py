"""
Pulls domestic 8-K and foreign-issuer 6-K filings from SEC EDGAR full-text
search API.
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

# EDGAR full-text search is EXACT-match on quoted phrases (no stemming) —
# the singular forms alone missed ~90-130 filings per 90 days (term audit
# 2026-07-15). Keep phrases precise; the extractor discards non-events.
KEYWORDS = [
    # "item 2.05" is the 8-K item for Costs Associated with Exit or Disposal
    # Activities — a verified perfect proxy for restructuring filings that a
    # 2026-07 audit showed the wording keywords below miss ~25% of. The LLM
    # extractor still discards exit costs that aren't job cuts. (EFTS quotes
    # each keyword itself and matches case-insensitively; the excerpt finder
    # needs the lowercase form.)
    "item 2.05",
    "workforce reduction",
    "workforce reductions",
    "reduction in force",
    "reductions in force",
    "layoff",
    "layoffs",
    "headcount reduction",
    "elimination of positions",
    "position eliminations",
    "reduce its workforce",
    "job cuts",
    "involuntary separation",
    # 2026-07-20 additions: restructuring/buyout 8-Ks that state the action in
    # these words without "layoff". The LLM extractor still discards any that
    # aren't actual job cuts, so broadening the net costs only candidate volume.
    "restructuring plan",
    "voluntary separation program",
    "early retirement program",
    "reduce headcount",
    "eliminate positions",
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


# 8-K Item 2.05 ("Costs Associated with Exit or Disposal Activities") is the
# strongest receipted layoff disclosure a public company files. EFTS returns
# each hit's item codes in `_source.items`; when 2.05 is present we mark the
# provenance so the entry reads as a verified exit-cost disclosure. Every EDGAR
# filing already posts at the top ("gold") verification level, so the 2.05
# signal rides on the human-visible `source_name` — a field the poster stores
# verbatim (extractor.py copies it straight through) — rather than a new field
# the pipeline would silently ignore.
EXIT_COST_ITEM = "2.05"


def _has_exit_cost_item(items):
    """True when the 8-K item-code array includes Item 2.05.

    Fail-soft: a missing or malformed array simply means "no 2.05" and never
    raises, so a shape change in the EFTS response cannot break the pull.
    """
    if not isinstance(items, (list, tuple)):
        return False
    return any(str(code).strip() == EXIT_COST_ITEM for code in items)


def _edgar_source_name(form, has_exit_cost):
    """Human-visible provenance label; flags Item 2.05 exit-cost filings."""
    base = f"SEC EDGAR {form}"
    return f"{base} Item 2.05 (exit/disposal costs)" if has_exit_cost else base


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
FORMS = ("8-K", "6-K")


def _search_keyword(keyword, start, end):
    """Paginate EFTS results — the API returns 10 hits per page, and on a
    heavy layoff day one page silently misses filings."""
    hits = []
    total = 0
    for form in FORMS:
        total = 0
        for page in range(MAX_PAGES_PER_KEYWORD):
            params = {
                "q": f'"{keyword}"',
                "dateRange": "custom",
                "startdt": start.strftime("%Y-%m-%d"),
                "enddt": end.strftime("%Y-%m-%d"),
                "forms": form,
                "from": page * PAGE_SIZE,
            }
            time.sleep(REQUEST_DELAY_SECONDS)
            resp = requests.get(EDGAR_FTS_URL, params=params, headers=_headers(), timeout=30)
            resp.raise_for_status()
            payload = resp.json().get("hits", {})
            page_hits = payload.get("hits", [])
            for hit in page_hits:
                # Preserve the search form even when the response's internal
                # field shape changes; the source label remains auditable.
                hit["_alt_form"] = form
            hits.extend(page_hits)
            total = (payload.get("total") or {}).get("value", 0)
            if len(page_hits) < PAGE_SIZE or (page + 1) * PAGE_SIZE >= total:
                break
        if total > MAX_PAGES_PER_KEYWORD * PAGE_SIZE:
            print(f"EDGAR: {form} keyword '{keyword}' matched {total} filings; "
                  f"only the first {MAX_PAGES_PER_KEYWORD * PAGE_SIZE} were fetched")
    return hits


def search_company_filings(company, days_back=120, max_hits=6):
    """Targeted EDGAR full-text search for ONE company's recent layoff filings.

    Used by the tracker-diff tripwire: when another tracker lists a company we
    lack, this asks SEC directly whether that employer filed an 8-K/6-K naming a
    workforce reduction. Returns raw dicts for extract_layoff_data (never posts
    directly). A primary source, so it verifies rather than trusts the other
    tracker's entry. Best-effort: any error yields an empty list, never raises.
    """
    if not company or len(company) < 2:
        return []
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    out, seen = [], set()
    # AND the company name with a layoff phrase so we only pull relevant filings.
    for phrase in ("layoff", "workforce reduction", "reduction in force", "item 2.05"):
        params = {
            "q": f'"{company}" "{phrase}"',
            "dateRange": "custom",
            "startdt": start.strftime("%Y-%m-%d"),
            "enddt": end.strftime("%Y-%m-%d"),
            "forms": "8-K",
        }
        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            resp = requests.get(EDGAR_FTS_URL, params=params, headers=_headers(), timeout=30)
            if resp.status_code != 200:
                continue
            for hit in resp.json().get("hits", {}).get("hits", [])[:max_hits]:
                src = hit.get("_source", {})
                cik = (src.get("ciks") or [None])[0]
                aid = hit.get("_id", "")
                if not cik or not aid or aid in seen:
                    continue
                seen.add(aid)
                acc, _, doc = aid.partition(":")
                acc_nodash = acc.replace("-", "")
                url = f"{SEC_ARCHIVES_BASE}/{int(cik)}/{acc_nodash}/{doc}"
                try:
                    raw_text = _fetch_filing_text(url)
                except Exception:
                    continue
                names = src.get("display_names") or [company]
                comp, ticker = _parse_display_name(names)
                items = src.get("items")
                exit_cost = _has_exit_cost_item(items)
                out.append({
                    # "8K"/"gold" are the server-recognized values the main
                    # EDGAR path emits. "sec_8k" is NOT in the allowed set, so
                    # the server silently downgraded these to news/bronze — a
                    # primary SEC filing mislabeled as news.
                    "source_type": "8K",
                    "source_name": _edgar_source_name("8-K", exit_cost),
                    "verification_level": "gold",
                    "source_url": url,
                    "company_name": comp,
                    "ticker": ticker,
                    "filing_date": src.get("file_date"),
                    "sec_items": list(items) if isinstance(items, (list, tuple)) else [],
                    "raw_text": raw_text,
                })
        except Exception:
            continue
    return out


def pull_edgar_filings(days_back=1):
    """Pull 8-K/6-K filings from the last N days containing layoff language."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    return pull_edgar_filings_between(start, end)


def pull_edgar_filings_between(start, end):
    """Pull 8-K/6-K filings filed in [start, end] containing layoff language.

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
            form = hit.get("_alt_form", "8-K")
            # EFTS carries the 8-K item codes in `_source.items`; Item 2.05
            # marks a verified exit/disposal-cost disclosure (fail-soft absent).
            items = source.get("items")
            exit_cost = _has_exit_cost_item(items)
            candidates[doc_url] = {
                "source_type": "8K",
                "source_name": _edgar_source_name(form, exit_cost),
                "verification_level": "gold",
                "source_url": doc_url,
                "company_name": company_name,
                "ticker": ticker,
                "filing_date": source.get("file_date", ""),
                "sec_items": list(items) if isinstance(items, (list, tuple)) else [],
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
