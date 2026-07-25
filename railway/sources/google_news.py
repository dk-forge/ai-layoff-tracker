"""Free layoff-news discovery via Google News RSS — no API key, no cost.

Why this exists: NewsAPI's free tier is dev-only and its paid tier is ~$449/mo,
so it is effectively dead here (see sources/newsapi.py). Google News RSS needs no
account and no key, and its item TITLE almost always carries the layoff HEADCOUNT
even when the linked article is paywalled ("Oracle fires 21,000 employees",
"Meta to cut 8,000 jobs"). That is exactly the marquee-layoff gap the paywalled
sources created: GDELT could not read the number behind the paywall, so the event
was dropped. Here the number is right there in the headline.

How it plugs in (mirrors sources/newsapi.py): each RSS item becomes a raw dict
with raw_text set (title + snippet — the extractor reads ONLY raw_text), so it
flows through the SAME extract_layoff_data -> post_to_wordpress pipeline, and all
the usual guards (verbatim count, date bounds, dedup, normalization) apply once.

We do NOT fetch the article body: the item link is a Google redirect to the
(often paywalled) page, and the headcount is already in the title/snippet. The
Google News link is stored as the source_url — it resolves to the article in a
browser and is Wayback-archivable like any other source.

No key. Optional env: GOOGLE_NEWS_MAX (items/run cap, default 300),
GOOGLE_NEWS_GAP_SECONDS (polite gap between queries, default 1).
"""
import html
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

RSS = "https://news.google.com/rss/search"
# Google News serves python-requests fine, but a browser-ish UA is safest and
# matches the rest of the project's outbound calls.
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}

# Lean default (was 300) to hold the monthly LLM spend near the ~$5-10 target:
# Google News returns most-relevant first, so the marquee cuts are in the top
# slice; raise GOOGLE_NEWS_MAX if you later want deeper coverage over cost.
MAX_ITEMS = max(10, int(os.environ.get("GOOGLE_NEWS_MAX", "150")))
GAP = max(0.0, float(os.environ.get("GOOGLE_NEWS_GAP_SECONDS", "1")))

# Broad layoff sweeps + a dedicated AI/automation sweep, mirroring newsapi's
# intent. Google News handles OR/quotes in the q= param.
DISCOVERY_QUERIES = (
    '"layoffs" OR "job cuts" OR "lays off" OR "cutting jobs" OR "workforce reduction"',
    '("layoffs" OR "job cuts" OR "lays off") ("AI" OR "artificial intelligence" OR automation)',
    '"reduction in force" OR "restructuring" OR "redundancies" layoffs',
    # Corporate euphemisms that dodge the word "layoff" — paired with a headcount
    # signal so the results stay layoff-events, not macro/strategy noise. Budget-
    # neutral: the MAX_ITEMS cap holds total extraction flat across all queries.
    '("rightsizing" OR "workforce optimization" OR "role elimination" OR "voluntary separation" OR "organizational simplification") (jobs OR employees OR roles OR staff)',
    '"bankruptcy" OR "shuts down" OR "winding down" (layoffs OR "job cuts" OR employees)',
)


def _clean(text):
    """Strip tags/entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _rss_url(query):
    return f"{RSS}?" + urllib.parse.urlencode(
        {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})


def _iso_date(pubdate):
    """RFC-822 pubDate -> YYYY-MM-DD, or '' (the extractor also reads the date
    from the text; this is only a hint)."""
    if not pubdate:
        return ""
    try:
        return parsedate_to_datetime(pubdate).date().isoformat()
    except Exception:
        return ""


def _parse_items(xml_text):
    """Parse an RSS 2.0 body into a list of {title, link, description, source,
    published}. Never raises."""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out
    for item in root.iter("item"):
        def _t(tag):
            el = item.find(tag)
            return el.text if el is not None and el.text else ""
        src_el = item.find("source")
        out.append({
            "title": _t("title"),
            "link": _t("link"),
            "description": _t("description"),
            "published": _t("pubDate"),
            "source": (src_el.text if src_el is not None and src_el.text else ""),
        })
    return out


def pull_google_news(queries=None, company_names=None):
    """Return a list of raw dicts ready for extract_layoff_data.

    Fail-loud: on an HTTP/parse error, set pull_google_news.last_error so the
    cron caller can degrade the source instead of masking a dead feed as 'ok'."""
    pull_google_news.last_error = None
    qs = list(queries or DISCOVERY_QUERIES)
    # Company-targeted queries are the surgical fix for the exact miss list
    # (Google, HP, Accenture, SAP, Uber...): the watchlist supplies the names.
    # They go FIRST: MAX_ITEMS is a GLOBAL cap, and with the broad sweeps in
    # front the first two queries alone could exhaust it, so the targeted
    # queries (the whole point of a chase call) never fired (audit 2026-07-25).
    for c in (company_names or []):
        c = str(c or "").strip()
        if c:
            qs.insert(0, f'"{c}" (layoffs OR "job cuts" OR "lays off" OR restructuring)')

    results, seen = [], set()
    errors = 0
    # Per-query slice: every query gets a fair share of the global cap, so a
    # later query (the euphemism sweep, a company chase) can never be starved
    # by an earlier broad one returning ~100 items.
    per_q = max(15, MAX_ITEMS // max(1, len(qs)))
    for q in qs:
        if len(results) >= MAX_ITEMS:
            break
        taken_this_q = 0
        try:
            r = requests.get(_rss_url(q), headers=UA, timeout=30)
            if r.status_code != 200:
                errors += 1
                pull_google_news.last_error = f"HTTP {r.status_code}"
                continue
            items = _parse_items(r.text)
        except Exception as e:
            errors += 1
            pull_google_news.last_error = f"{type(e).__name__}: {e}"
            continue
        for it in items:
            link = (it.get("link") or "").strip()
            if not link or link in seen:
                continue
            seen.add(link)
            title = _clean(it.get("title"))
            desc = _clean(it.get("description"))
            source = (it.get("source") or "").strip()
            # The headcount lives in the title; the description is usually just a
            # link + outlet, but include it when it adds text. Name the outlet so
            # the extractor has attribution context.
            raw_text = (title + (". " + desc if desc and desc != title else "")).strip()
            if source and source.lower() not in raw_text.lower():
                raw_text = f"{raw_text} (via {source})"
            if not raw_text:
                continue
            results.append({
                "source_type": "news",
                "source_name": source or "Google News",
                "verification_level": "bronze",
                "raw_text": raw_text,
                "source_url": link,
                "company_name": None,   # the extractor fills this in
                "ticker": None,
                "filing_date": _iso_date(it.get("published")),
            })
            taken_this_q += 1
            if taken_this_q >= per_q or len(results) >= MAX_ITEMS:
                break
        time.sleep(GAP)

    # A run where every query errored (and nothing came back) is a real outage,
    # not a quiet day — surface it.
    if errors and errors == len(qs) and not results:
        pull_google_news.last_error = pull_google_news.last_error or "all queries failed"
    print(f"Google News: {len(results)} unique items across {len(qs)} queries"
          + (f" ({errors} query error(s))" if errors else ""))
    return results


if __name__ == "__main__":
    # Manual smoke test: python -m sources.google_news
    rows = pull_google_news()
    for r in rows[:10]:
        print(f"  [{r['source_name']}] {r['raw_text'][:90]}")
    print(f"total: {len(rows)}; last_error={getattr(pull_google_news,'last_error',None)}")
