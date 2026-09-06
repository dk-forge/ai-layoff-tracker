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
from datetime import date, timedelta

import requests

from sources.newsapi import pull_news_articles
from extractor import extract_layoff_data
import spend
from wp_poster import post_to_wordpress
from source_health import report_source_health
from own_api import require_site_url

SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
BATCH = max(1, int(os.environ.get("WATCHLIST_BATCH", "60")))
# NewsAPI's free plan only serves ~30 days; a longer window is silently rejected.
# 28 days + the ~weekly rotation gives heavy overlapping coverage, so a new cut
# at any watchlisted company surfaces within days. (Backfilling OLDER misses is a
# separate path — GDELT / direct add — since free NewsAPI can't reach them.)
DAYS_BACK = max(7, min(28, int(os.environ.get("WATCHLIST_DAYS_BACK", "28"))))
# Clamped to 5100s (85min) against company-watchlist.yml's 90 minute
# timeout-minutes; see ai_evidence_sweep.py for why the ceiling exists.
DEADLINE = max(60, min(5100, int(os.environ.get("WATCHLIST_DEADLINE_SECONDS", "900"))))
# HOW MANY COMPANY-TARGETED NEWS QUERIES ONE RUN MAY SEND.
#
# One query per company is what this collector is FOR, and it is also the
# constraint that decides how big a sweep can honestly be: NewsAPI's Developer
# plan gives the whole key 100 requests/day, and the twice-daily cron spends 6
# of them on the discovery set that is the tracker's primary AI-attribution
# channel. A watchlist run that sends 150 company queries does not sweep 150
# companies - it exhausts the day's quota and 429s the cron.
#
# So the honest ceiling on a company-targeted pass is ~90 companies/day on this
# plan, not the 9,504-name universe. `already_have()` costs nothing against
# this budget (it reads our own API), so the universe can still be WALKED at
# full speed; it is only the companies with no current-year entry that cost a
# request. Default 40 leaves the cron's 6 and most of the day's headroom
# untouched.
NEWS_BUDGET = max(0, int(os.environ.get("WATCHLIST_NEWS_BUDGET", "40")))
DRY_RUN = os.environ.get("WATCHLIST_DRY_RUN", "").lower() in {"1", "true", "yes"}
WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "company_watchlist.csv")

_STOP = {"inc", "corp", "co", "ltd", "plc", "llc", "lp", "group", "holdings", "the", "sa", "se", "ag", "nv"}


def load_watchlist():
    names, seen = [], set()

    def _add(name):
        name = (name or "").strip()
        if name and not name.startswith("#") and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)

    try:
        with open(WATCHLIST_PATH, newline="") as f:
            for row in csv.DictReader(f):
                _add(row.get("company"))
    except FileNotFoundError:
        print(f"watchlist not found: {WATCHLIST_PATH}")

    # Auto-grow (dormant): merge live index constituents at RUN TIME so the list
    # self-maintains and stays geography-balanced without a git commit. Point
    # WATCHLIST_INDEX_URLS (comma-separated) at CSV/JSON lists of company names
    # (e.g. S&P 500 / STOXX 600 constituents). Unset -> just the seed file.
    for url in [u.strip() for u in (os.environ.get("WATCHLIST_INDEX_URLS") or "").split(",") if u.strip()]:
        try:
            r = requests.get(url, headers={"User-Agent": "AiLayoffTracker/1.0"}, timeout=30)
            if r.status_code != 200:
                continue
            body = r.text
            if body.lstrip()[:1] in ("[", "{"):
                import json as _json
                data = _json.loads(body)
                rows = data if isinstance(data, list) else (data.get("data") or [])
                for x in rows:
                    _add(x.get("company") or x.get("name") or x.get("Security") if isinstance(x, dict) else x)
            else:
                for row in csv.DictReader(__import__("io").StringIO(body)):
                    _add(row.get("company") or row.get("Name") or row.get("Security") or row.get("name"))
        except Exception as exc:
            print(f"watchlist index merge failed ({url[:40]}...): {exc}")

    # Self-grow from our OWN captured data: every company we've ever ingested
    # (WARN/SEC/news) becomes one we keep monitoring for its NEXT round — repeat
    # layoffs are common (Amazon/Meta/Google cut multiple times). Uses only our
    # own DB, so it's fully brand-safe and compounds with every capture. Bounded
    # to recent captures (3y). Toggle off with WATCHLIST_SELF_GROW=0.
    if os.environ.get("WATCHLIST_SELF_GROW", "1") != "0" and SITE:
        try:
            since = (date.today() - timedelta(days=365 * 3)).isoformat()
            resp = requests.get(f"{SITE}/wp-json/layoffs/v1/companies",
                                params={"since": since, "limit": 20000}, headers=UA, timeout=45)
            got = resp.json().get("companies", []) if resp.status_code == 200 else []
            for c in got:
                _add(c)
            print(f"watchlist self-grow: merged {len(got)} companies from our own captures")
        except Exception as exc:
            print(f"watchlist self-grow failed (non-fatal): {exc}")
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
    never triggers a blind re-add; the poster's dedup is the final backstop.

    An UNSET `WP_SITE_URL` is not a lookup failure and is raised as itself
    (`own_api.SiteNotConfigured`) BEFORE any request: with it inside the try,
    an empty host was requested, the exception was swallowed, and the caller
    read a configuration fault as "our own API did not answer"."""
    site = require_site_url()
    try:
        resp = requests.get(
            f"{site}/wp-json/layoffs/v1/query",
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

    # Bound the run by the news-request budget BEFORE spending any of it, and
    # record the shortfall as a truncation. A sweep that queried 40 of 53
    # missing companies has not swept the slice, and its "0 posted" must not be
    # readable as "these 53 companies have no cuts".
    unqueried = 0
    if NEWS_BUDGET and len(missing) > NEWS_BUDGET:
        unqueried = len(missing) - NEWS_BUDGET
        missing = missing[:NEWS_BUDGET]
        why = (f"news-request budget {NEWS_BUDGET}/run reached; {unqueried} "
               f"missing compan{'y' if unqueried == 1 else 'ies'} were not queried")
        print(f"::warning::watchlist: {why}. They are deferred, not cleared.")
        spend.note_truncated(why)
    os.environ.setdefault("NEWSAPI_MAX_REQUESTS", str(NEWS_BUDGET or 0))

    posted = ai = extract_fail = 0
    started = time.monotonic()
    for i in range(0, len(missing), 20):
        if time.monotonic() - started > DEADLINE:
            print(f"deadline hit after {i} companies; remaining resume next run")
            spend.note_truncated(f"wall-clock deadline {DEADLINE}s reached after "
                                 f"{i} of {len(missing)} companies")
            break
        chunk = missing[i:i + 20]
        try:
            entries = pull_news_articles(days_back=DAYS_BACK, queries=[query_for(c) for c in chunk])
            try:
                from seen_urls import filter_already_seen
                entries = filter_already_seen(entries)
            except Exception:
                pass
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

    detail = (f"checked {len(todays)} watchlist companies, {len(missing)} queried"
              + (f" ({unqueried} over budget, deferred)" if unqueried else "")
              + f", {posted} posted ({ai} AI-attributed), {extract_fail} extract fails")
    print("watchlist sweep:", detail)
    # `items` is companies actually QUERIED, not companies in the slice. The
    # slice size was what this job used to report, and it is the number that
    # made "0 rows from 150 companies" look like evidence about 150 companies.
    spend.record_job_run(items=len(missing), stored=posted)
    if not DRY_RUN and not report_source_health("company_watchlist", "ok", posted, detail):
        # Completion telemetry: the sweep already finished, so a failed health
        # write is a warning, never a reason to fail the run and page the owner.
        print("::warning::company_watchlist completed but the health-ledger write failed (data is fine)")


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
