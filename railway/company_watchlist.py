"""Company watchlist sweep — automated "work backwards from the big employers".

Turns the manual agent loop (which big company are we missing? → search → verify
→ add) into a scheduled job that runs on OUR OWN news net (NewsAPI + trusted
outlets incl. Reuters/Bloomberg/FT, which cover big European cuts in English) —
NOT any metered web-search. For each watchlisted company we have no current-year
entry for, it fires a company-TARGETED query (the broad daily net misses cuts it
doesn't name — that's exactly how HP/Intel slipped through), runs the hits
through the same DeepSeek extractor + dedup + poster as the daily cron, and adds
the verified ones with their receipts.

Runs DAILY with rotation: a slice of the watchlist is checked each run so every
company is revisited ~weekly, while a fresh cut surfaces within a day. The
extractor still validates each candidate is a real layoff, so a company-targeted
article about earnings (not a cut) is dropped, never posted.

Env: WATCHLIST_BATCH (companies/run, default 60), WATCHLIST_DAYS_BACK (news
window, default 120), WATCHLIST_DEADLINE_SECONDS (default 900),
WATCHLIST_DRY_RUN=1 to log candidates without posting.
"""
import csv
import os
import re
import sys
import time
from datetime import date

import requests

from sources.newsapi import pull_news_articles
from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health

SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
BATCH = max(1, int(os.environ.get("WATCHLIST_BATCH", "60")))
DAYS_BACK = max(7, int(os.environ.get("WATCHLIST_DAYS_BACK", "120")))
DEADLINE = max(60, int(os.environ.get("WATCHLIST_DEADLINE_SECONDS", "900")))
DRY_RUN = os.environ.get("WATCHLIST_DRY_RUN", "").lower() in {"1", "true", "yes"}
WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "company_watchlist.csv")

_STOP = {"inc", "corp", "co", "ltd", "plc", "llc", "lp", "group", "holdings", "the", "sa", "se", "ag", "nv"}


def load_watchlist():
    names = []
    try:
        with open(WATCHLIST_PATH, newline="") as f:
            for row in csv.DictReader(f):
                name = (row.get("company") or "").strip()
                if name and not name.startswith("#"):
                    names.append(name)
    except FileNotFoundError:
        print(f"watchlist not found: {WATCHLIST_PATH}")
    return names


def _token(company):
    """First significant word, for a word-boundary presence check."""
    for w in re.split(r"[^A-Za-z0-9]+", company):
        if w and w.lower() not in _STOP:
            return w
    return company.strip()


def already_have(company):
    """Word-boundary check against our data — do we already carry a current-year
    entry for this company? A lookup failure returns True (skip), so an API blip
    never triggers a blind re-add; the poster's dedup is the final backstop."""
    try:
        resp = requests.get(
            f"{SITE}/wp-json/layoffs/v1/query",
            params={"company": company, "years": str(date.today().year), "per_page": 25},
            headers=UA, timeout=30)
        rows = resp.json().get("data", []) if resp.status_code == 200 else []
    except Exception:
        return True
    if not rows:
        return False
    pat = re.compile(r"\b" + re.escape(_token(company)) + r"\b", re.I)
    return any(pat.search(r.get("company_name") or "") for r in rows)


def query_for(company):
    return (f'"{company}" AND (layoffs OR "job cuts" OR "workforce reduction" '
            f'OR redundancies OR "laying off" OR "cut jobs")')


def run():
    companies = load_watchlist()
    if not companies:
        raise RuntimeError("watchlist is empty — nothing to sweep")

    # Daily rotation: each run checks one slice; the list cycles ~weekly.
    pages = max(1, (len(companies) + BATCH - 1) // BATCH)
    start = (date.today().toordinal() % pages) * BATCH
    todays = companies[start:start + BATCH]

    missing = [c for c in todays if not already_have(c)]
    print(f"watchlist: {len(companies)} total · checking {len(todays)} (slice {start}) · "
          f"{len(missing)} with no current-year entry")
    if not missing:
        report_source_health("company_watchlist", "ok", 0,
                             f"checked {len(todays)}, none missing this slice")
        return

    posted = ai = extract_fail = 0
    started = time.monotonic()
    for i in range(0, len(missing), 20):
        if time.monotonic() - started > DEADLINE:
            print(f"deadline hit after {i} companies; remaining resume next run")
            break
        chunk = missing[i:i + 20]
        try:
            entries = pull_news_articles(days_back=DAYS_BACK, queries=[query_for(c) for c in chunk])
        except Exception as exc:
            print(f"news fetch failed for a chunk: {exc}")
            continue
        for raw in entries:
            try:
                extracted = extract_layoff_data(raw)
            except Exception as exc:
                extract_fail += 1
                print(f"extract error: {exc}")
                continue
            if not extracted:
                continue
            if DRY_RUN:
                print(f"  DRY would add: {extracted.get('company_name')} "
                      f"{extracted.get('job_count')} ({extracted.get('layoff_date')})")
                continue
            try:
                if post_to_wordpress(extracted) == "posted":
                    posted += 1
                    if extracted.get("ai_explicit"):
                        ai += 1
                    print(f"  + {extracted.get('company_name')} {extracted.get('job_count')} "
                          f"({extracted.get('layoff_date')}) [{extracted.get('source_name')}]")
            except Exception as exc:
                print(f"post error: {exc}")
        time.sleep(1)

    detail = (f"checked {len(todays)} watchlist companies, {len(missing)} missing, "
              f"{posted} posted ({ai} AI-attributed), {extract_fail} extract fails")
    print("watchlist sweep:", detail)
    if not DRY_RUN and not report_source_health("company_watchlist", "ok", posted, detail):
        raise RuntimeError("could not publish company_watchlist health status")


def main():
    if not SITE:
        print("WP_SITE_URL is required")
        return 1
    if not DRY_RUN and not os.environ.get("WP_API_KEY"):
        print("WP_API_KEY is required (or set WATCHLIST_DRY_RUN=1)")
        return 1
    if not DRY_RUN:
        report_source_health("company_watchlist", "running", 0, "watchlist sweep in progress")
    try:
        run()
        return 0
    except Exception as exc:
        if not DRY_RUN:
            report_source_health("company_watchlist", "degraded", 0, f"watchlist sweep failed: {exc}")
        print(f"watchlist sweep FAILED: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
