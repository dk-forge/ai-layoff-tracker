"""Supplemental news ingest — NewsData.io + Marketaux.

Widens the net beyond NewsAPI (US-heavy, English, ~30-day) into NON-ENGLISH and
broader global coverage — directly targeting the European miss the recall harness
measured. Each provider runs only if its key is present; both feed the SAME
DeepSeek extractor + dedup + poster, so nothing bypasses our verify rules.

Ships DORMANT per provider: no key -> that provider is skipped. Add the secret
(NEWSDATA_API_KEY / MARKETAUX_API_KEY) to light it up.

Env: NEWSDATA_API_KEY, MARKETAUX_API_KEY, SUPP_NEWS_DRY=1.
"""
import os
import sys
import time

import requests

from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
DRY = os.environ.get("SUPP_NEWS_DRY", "").lower() in {"1", "true", "yes"}

# Native-language + English layoff terms so non-English outlets surface (the EU gap).
QUERY = ('layoffs OR "job cuts" OR redundancies OR Stellenabbau OR "plan social" '
         'OR licenciements OR despidos OR licenziamenti OR Entlassungen')


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


def run():
    providers = []
    if os.environ.get("NEWSDATA_API_KEY"):
        providers.append(("newsdata", pull_newsdata))
    if os.environ.get("MARKETAUX_API_KEY"):
        providers.append(("marketaux", pull_marketaux))
    if not providers:
        print("Neither NEWSDATA_API_KEY nor MARKETAUX_API_KEY set — supplemental news dormant.")
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
