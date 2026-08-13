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


def _window_at(text, idx):
    """RAW_TEXT_LIMIT characters of `text` around `idx`, with 500 of lead-in.

    500 is not decoration: the extractor's verbatim-count guard and the model
    both need the sentence the number sits in, and a window that starts ON the
    match loses the subject of that sentence.
    """
    start = max(0, idx - 500)
    return text[start:start + RAW_TEXT_LIMIT]


# A headcount as a filing states one: a number immediately governing a
# people-noun. Used for exactly two jobs, both narrow:
#   * deciding whether a primary document states a count at all (below), and
#   * centring an exhibit's window on the count rather than on nothing.
# It is NOT a replacement for extractor._count_in_text — it does not know which
# number is the layoff, and it never decides what gets published. Its only job
# is to point the reading window at the paragraph a human would read.
HEADCOUNT_ANCHOR = re.compile(
    r"(?<![\d.,])\d{1,3}(?:[.,   ]\d{3})*(?![\d])"
    r"(?:\s+\S+){0,2}\s+"
    r"(?:employees|positions|jobs|roles|workers|staff|personnel|colleagues|"
    r"associates|people)\b",
    re.I)


def _headcount_index(text):
    """Offset of the first headcount-shaped statement, or None."""
    found = HEADCOUNT_ANCHOR.search(text or "")
    return found.start() if found else None


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
            return _window_at(text, idx)
    return text[:RAW_TEXT_LIMIT]


# ---------------------------------------------------------------------------
# EX-99.1 fallback: the count that is not in the 8-K
#
# An Item 2.05 8-K is often a two-sentence legal wrapper — "the Company
# committed to a plan", "the Company expects to incur $X in charges" — that
# furnishes the headcount by reference: the press release filed as EX-99.1 in
# the SAME accession. Measured on the frozen SEC Item 2.05 gold set
# (2026-08-01, re-probed 2026-08-12): Codexis 2025-11-06 (46) and PLAYSTUDIOS
# 2026-03-16 (177) state their count NOWHERE in the stripped primary document.
# The extractor then correctly refuses a number it cannot see, and a filing we
# reached, fetched and read is lost at the last step.
#
# WHY THIS IS GATED AND NOT UNCONDITIONAL. Fetching every exhibit of every
# filing would multiply this collector's bytes and its LLM candidates for the
# sake of a handful of events: the EX-99.1 press releases here are 92KB and
# 367KB against 37KB and 33KB primaries, and every extra candidate is an extra
# paid extraction against a per-run spend ceiling the cron already hits. So the
# exhibit is read only when the primary document states NO headcount at all,
# which costs one index request plus one document request on the small minority
# of filings that need it, and nothing on the rest.
#
# The window is anchored on the headcount, not on a KEYWORD. That matters and
# was measured: neither exhibit contains a single phrase from KEYWORDS ("in
# November 2025, Codexis eliminated 46 positions"; "Eliminating 177
# positions"), so the keyword anchor falls through to text[:RAW_TEXT_LIMIT] and
# the counts, at offsets 3,766 and 7,582 of the stripped text, are truncated
# away before the extractor ever sees them — the EnerSys failure mode exactly,
# one document further along. Anchored, both land ~500 characters into a
# 3,000-character window, inside extractor.RAW_TEXT_LIMIT by construction.
# ---------------------------------------------------------------------------

# Press-release exhibit types, most specific first. Deliberately short: EX-99.1
# is where a restructuring announcement goes. Widening this is a cost decision,
# not a formatting one.
EXHIBIT_TYPES = ("EX-99.1", "EX-99.01", "EX-99")

_ROW_RX = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
_CELL_RX = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")
_HREF_RX = re.compile(r"""(?is)<a[^>]+href=["']([^"']+\.(?:htm|html|txt))["']""")


def _filing_index_url(doc_url):
    """The accession's filing index, derived from the document path.

    An Archives document URL ends `/<18-digit accession>/<file>`, and the index
    is `<accession with dashes>-index.htm` in the same directory. Derived rather
    than passed so every call site gets it right by construction.
    """
    match = re.match(r"(?i)^(.*/(\d{18}))/[^/]+$", doc_url or "")
    if not match:
        return None
    base, nodash = match.group(1), match.group(2)
    dashed = f"{nodash[:10]}-{nodash[10:12]}-{nodash[12:]}"
    return f"{base}/{dashed}-index.htm"


def _exhibit_urls(index_url):
    """Absolute URLs of the press-release exhibits listed in a filing index.

    Returns them in EXHIBIT_TYPES order so the most specific type is read first.
    """
    time.sleep(REQUEST_DELAY_SECONDS)
    resp = requests.get(index_url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    origin = re.match(r"(?i)^(https?://[^/]+)", index_url)
    origin = origin.group(1) if origin else ""
    by_type = {}
    for row in _ROW_RX.findall(resp.text):
        href = _HREF_RX.search(row)
        if not href:
            continue
        cells = [_strip_html(c).upper() for c in _CELL_RX.findall(row)]
        for wanted in EXHIBIT_TYPES:
            if wanted in cells:
                link = html.unescape(href.group(1))
                by_type.setdefault(wanted, link if link.startswith("http")
                                    else origin + link)
                break
    return [by_type[t] for t in EXHIBIT_TYPES if t in by_type]


def _fetch_exhibit_text(url):
    """A press-release exhibit's window, centred on the headcount it states.

    Falls back to the keyword anchor and then to the head of the document, so a
    layoff exhibit that phrases its count in a way this does not recognise is
    still read — just not centred.
    """
    time.sleep(REQUEST_DELAY_SECONDS)
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    text = _strip_html(resp.text[:MAX_DOC_BYTES])
    idx = _headcount_index(text)
    if idx is not None:
        return _window_at(text, idx)
    lowered = text.lower()
    for keyword in KEYWORDS:
        found = lowered.find(keyword)
        if found != -1:
            return _window_at(text, found)
    return text[:RAW_TEXT_LIMIT]


def fetch_document_window(doc_url):
    """(text, url) for one filing: the primary document, or its EX-99.1.

    The primary document is always read. The exhibit is read ONLY when the
    primary states no headcount, and the exhibit is used ONLY when it states
    one — so this can add a candidate's count, never remove or dilute it. The
    returned URL is the document the text actually came from, because a row
    must cite the document whose sentence it quotes.

    Exhibit lookup is best-effort: any failure leaves the primary untouched.
    """
    text = _fetch_filing_text(doc_url)
    if _headcount_index(text) is not None:
        return text, doc_url
    index_url = _filing_index_url(doc_url)
    if not index_url:
        return text, doc_url
    try:
        for exhibit_url in _exhibit_urls(index_url):
            exhibit_text = _fetch_exhibit_text(exhibit_url)
            if _headcount_index(exhibit_text) is not None:
                return exhibit_text, exhibit_url
    except Exception as exc:                                   # noqa: BLE001
        print(f"EDGAR exhibit lookup skipped for {doc_url}: {exc}")
    return text, doc_url


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
                    raw_text, url = fetch_document_window(url)
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
            entry["raw_text"], entry["source_url"] = fetch_document_window(doc_url)
        except Exception as e:
            print(f"EDGAR document fetch error for {doc_url}: {e}")
            continue
        if entry["raw_text"]:
            results.append(entry)

    print(f"EDGAR: {len(results)} filings pulled")
    return results
