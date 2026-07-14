"""
Pulls AI-related layoff coverage from GDELT — a free, keyless, global news index
(2017→present). GDELT returns article metadata (url/title/domain/date); we fetch
each article and extract the layoff details downstream via the same extractor.

This is the historical + global press layer: free, worldwide, back to 2024,
and it's where AI-attributed layoff language actually appears.
"""
import html
import re
import time
from datetime import timezone

import requests

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT space = AND, OR must be explicit. Bias toward AI-related layoff coverage.
QUERY = '(layoffs OR "job cuts" OR "cutting jobs" OR "lays off") (AI OR automation OR "artificial intelligence")'

TRUSTED_DOMAINS = {
    "reuters.com", "bloomberg.com", "cnbc.com", "techcrunch.com", "theverge.com",
    "wsj.com", "ft.com", "businessinsider.com", "forbes.com", "fortune.com",
    "apnews.com", "theguardian.com", "axios.com", "cnn.com", "nytimes.com",
    "engadget.com", "arstechnica.com", "fastcompany.com", "inc.com",
    "foxbusiness.com", "bbc.com", "bbc.co.uk", "aljazeera.com",
    "businessinsider.in", "business-standard.com", "theinformation.com",
}

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

REQUEST_DELAY = 1.2       # GDELT asks for gentle use
RAW_TEXT_LIMIT = 3000
MAX_DOC_BYTES = 400_000


def _strip_html(markup):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _domain(a):
    d = (a.get("domain") or "").lower()
    return d[4:] if d.startswith("www.") else d


def _is_trusted(dom):
    return any(dom == d or dom.endswith("." + d) for d in TRUSTED_DOMAINS)


def _seen_to_iso(seendate):
    s = re.sub(r"[^0-9]", "", seendate or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else ""


def _fetch_article(url):
    """Fetch an article and return a text window centered on the layoff mention."""
    resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=25)
    resp.raise_for_status()
    text = _strip_html(resp.text[:MAX_DOC_BYTES])
    lowered = text.lower()
    for kw in ("laid off", "layoff", "job cuts", "cutting jobs", "reduction in force"):
        idx = lowered.find(kw)
        if idx != -1:
            start = max(0, idx - 400)
            return text[start:start + RAW_TEXT_LIMIT]
    return text[:RAW_TEXT_LIMIT]


def pull_gdelt_between(start, end, max_records=250):
    """Return raw layoff-news entries (trusted domains) filed in [start, end]."""
    params = {
        "query": QUERY,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sortby": "datedesc",
        "sourcelang": "eng",
        "startdatetime": start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
    }
    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(GDELT_URL, params=params,
                            headers={"User-Agent": BROWSER_UA}, timeout=30)
        resp.raise_for_status()
        articles = resp.json().get("articles", []) or []
    except Exception as e:
        print(f"GDELT query error: {e}")
        return []

    results, seen = [], set()
    for a in articles:
        url = a.get("url")
        dom = _domain(a)
        if not url or url in seen or not _is_trusted(dom):
            continue
        seen.add(url)
        try:
            time.sleep(0.2)
            text = _fetch_article(url)
        except Exception as e:
            print(f"GDELT fetch error {url}: {e}")
            continue
        if not text.strip():
            continue
        results.append({
            "source_type": "news",
            "source_name": dom,
            "verification_level": "bronze",
            "raw_text": f"{a.get('title', '')} {text}",
            "source_url": url,
            "company_name": None,
            "ticker": None,
            "filing_date": _seen_to_iso(a.get("seendate")),
        })

    print(f"GDELT: {len(articles)} matched, {len(results)} from trusted domains")
    return results
