"""Supplemental news ingest — NewsData.io + Marketaux + Finnhub.

Widens the net beyond NewsAPI (US-heavy, English, ~30-day) into NON-ENGLISH and
broader global coverage — directly targeting the European miss the recall harness
measured. NewsData.io + Marketaux are keyword/search based; Finnhub is ticker
based (per-company news, sieved on a layoff keyword regex). Each provider runs
only if its key is present; all feed the SAME DeepSeek extractor + dedup +
poster, so nothing bypasses our verify rules.

Ships DORMANT per provider: no key -> that provider is skipped. Add the secret
(NEWSDATA_API_KEY / MARKETAUX_API_KEY / FINNHUB_API_KEY) to light it up.

Env: NEWSDATA_API_KEY, MARKETAUX_API_KEY, FINNHUB_API_KEY, SUPP_NEWS_DRY=1.
"""
import csv
import os
import re
import sys
import time
from datetime import date, timedelta

import requests

from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
DRY = os.environ.get("SUPP_NEWS_DRY", "").lower() in {"1", "true", "yes"}

# Native-language + English layoff terms so non-English outlets surface (the EU gap).
QUERY = ('layoffs OR "job cuts" OR redundancies OR Stellenabbau OR "plan social" '
         'OR licenciements OR despidos OR licenziamenti OR Entlassungen')

# Finnhub is TICKER-based (per-company news), so it sieves on a keyword regex
# rather than a search string. Reuses the earnings ticker list; rotates a slice
# each run so every company is revisited ~weekly while a fresh cut surfaces daily.
_SIEVE = re.compile(
    r"\b(layoff|laid off|job cuts?|headcount|redundanc|restructur|workforce reduc|"
    r"cut(ting)? \d|slash(ing)? jobs|role eliminat|right ?siz|severance)\w*", re.I)
TICKERS_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "earnings_tickers.csv")
FINNHUB_BATCH = max(1, int(os.environ.get("FINNHUB_BATCH", "60")))


def _load_tickers():
    out = []
    try:
        with open(TICKERS_PATH, newline="") as f:
            for row in csv.DictReader(f):
                t = (row.get("ticker") or "").strip().upper()
                if t and not t.startswith("#"):
                    out.append(t)
    except FileNotFoundError:
        pass
    return out


def _raw(source_name, title, url, content):
    return {"source_type": "news", "source_name": source_name or "news",
            "source_url": url, "title": title or "", "content": content or title or "",
            "text": content or title or ""}


def _ingest(label, articles):
    posted = ai = 0
    for a in articles:
        try:
            ex = extract_layoff_data(a)
        except Exception:
            continue
        if not ex:
            continue
        if DRY:
            print(f"  DRY [{label}] {ex.get('company_name')} {ex.get('job_count')}")
            continue
        if post_to_wordpress(ex) == "posted":
            posted += 1
            ai += 1 if ex.get("ai_explicit") else 0
            print(f"  + [{label}] {ex.get('company_name')} {ex.get('job_count')} ({ex.get('layoff_date')})")
    return posted, ai


def pull_newsdata():
    key = os.environ.get("NEWSDATA_API_KEY")
    if not key:
        return []
    out = []
    try:
        r = requests.get("https://newsdata.io/api/1/news",
                         params={"apikey": key, "q": QUERY, "category": "business",
                                 "language": "en,de,fr,es,it"}, headers=UA, timeout=30)
        for a in (r.json().get("results") or []) if r.status_code == 200 else []:
            out.append(_raw(a.get("source_id"), a.get("title"), a.get("link"),
                            a.get("description") or a.get("content")))
    except Exception as exc:
        print(f"newsdata fetch failed: {exc}")
    print(f"newsdata.io: {len(out)} article(s)")
    return out


def pull_marketaux():
    key = os.environ.get("MARKETAUX_API_KEY")
    if not key:
        return []
    out = []
    try:
        r = requests.get("https://api.marketaux.com/v1/news/all",
                         params={"api_token": key, "search": QUERY, "language": "en,de,fr,es,it",
                                 "filter_entities": "false", "limit": 50}, headers=UA, timeout=30)
        for a in (r.json().get("data") or []) if r.status_code == 200 else []:
            out.append(_raw(a.get("source"), a.get("title"), a.get("url"),
                            a.get("description") or a.get("snippet")))
    except Exception as exc:
        print(f"marketaux fetch failed: {exc}")
    print(f"marketaux: {len(out)} article(s)")
    return out


def pull_finnhub():
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        return []
    tickers = _load_tickers()
    if not tickers:
        return []
    pages = max(1, (len(tickers) + FINNHUB_BATCH - 1) // FINNHUB_BATCH)
    start = (date.today().toordinal() % pages) * FINNHUB_BATCH
    todays = tickers[start:start + FINNHUB_BATCH]
    frm = (date.today() - timedelta(days=28)).isoformat()
    to = date.today().isoformat()
    out = []
    for tk in todays:
        try:
            r = requests.get("https://finnhub.io/api/v1/company-news",
                             params={"symbol": tk, "from": frm, "to": to, "token": key},
                             headers=UA, timeout=30)
            items = r.json() if r.status_code == 200 else []
        except Exception as exc:
            print(f"finnhub {tk} failed: {exc}")
            continue
        for a in items if isinstance(items, list) else []:
            blob = f"{a.get('headline','')} {a.get('summary','')}"
            if _SIEVE.search(blob):
                out.append(_raw(a.get("source"), a.get("headline"), a.get("url"),
                                a.get("summary")))
        time.sleep(0.3)
    print(f"finnhub: {len(out)} layoff-relevant article(s) across {len(todays)} tickers")
    return out


def run():
    providers = []
    if os.environ.get("NEWSDATA_API_KEY"):
        providers.append(("newsdata", pull_newsdata))
    if os.environ.get("MARKETAUX_API_KEY"):
        providers.append(("marketaux", pull_marketaux))
    if os.environ.get("FINNHUB_API_KEY"):
        providers.append(("finnhub", pull_finnhub))
    if not providers:
        print("No NEWSDATA_API_KEY / MARKETAUX_API_KEY / FINNHUB_API_KEY set — supplemental news dormant.")
        return
    total_posted = total_ai = 0
    for label, fn in providers:
        posted, ai = _ingest(label, fn())
        total_posted += posted
        total_ai += ai
        time.sleep(1)
    detail = f"{[p[0] for p in providers]}: {total_posted} added ({total_ai} AI)"
    print("supplemental news:", detail)
    if not DRY:
        report_source_health("supplemental_news", "ok", total_posted, detail)


def main():
    if not os.environ.get("WP_SITE_URL"):
        print("WP_SITE_URL required")
        return 1
    try:
        run()
        return 0
    except Exception as exc:
        if not DRY:
            report_source_health("supplemental_news", "degraded", 0, f"supplemental news failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
