"""Distress-signal watchlist feeder — CourtListener (US bankruptcy) + Companies
House (UK insolvency).

These filings signal a company in trouble but state NO job count, so they can't
become layoff entries directly. Instead they feed the SAME targeted-news +
DeepSeek-extractor + dedup + poster path as company_watchlist: a distressed
company gets a company-scoped news search, and only a real, sourced layoff with
a count is ever posted. This catches SMALLER distressed employers that never hit
the national news the daily net watches.

Ships DORMANT per source: no key -> that source is skipped. Both keys already
exist as GitHub secrets (COURTLISTENER_API_KEY, COMPANIES_HOUSE_API_KEY_UK).

Env: COURTLISTENER_API_KEY, COMPANIES_HOUSE_API_KEY_UK,
     DISTRESS_DAYS_BACK (default 30), DISTRESS_MAX (companies/run, default 40),
     DISTRESS_DRY=1 to log candidates without posting.
"""
import os
import re
import sys
import time
from datetime import date, timedelta

import requests

from company_watchlist import query_for, already_have
from sources.newsapi import pull_news_articles
from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
DAYS_BACK = max(7, min(90, int(os.environ.get("DISTRESS_DAYS_BACK", "30"))))
MAX_CO = max(1, min(200, int(os.environ.get("DISTRESS_MAX", "40"))))
# Hard wall-clock budget so the news-search phase can never hit the workflow's
# job timeout (which cancels mid-run and loses everything).
DEADLINE_SECONDS = max(120, min(1300, int(os.environ.get("DISTRESS_DEADLINE_SECONDS", "1000"))))
DRY = os.environ.get("DISTRESS_DRY", "").lower() in {"1", "true", "yes"}

# Caption noise to strip from a bankruptcy case name to recover the debtor.
_CAPTION = re.compile(
    r"^\s*in\s+re:?\s+|,?\s*debtors?\.?\s*$|,?\s*et\s+al\.?\s*$|\s*\(.*?\)\s*$",
    re.I)
_STOPWORD_ONLY = re.compile(r"^(the|a|an|inc|llc|corp|co|ltd|company)$", re.I)


def _clean_company(name):
    name = str(name or "").strip()
    prev = None
    while name and name != prev:
        prev = name
        name = _CAPTION.sub("", name).strip().strip(",")
    # Reject captions that are obviously not a company (individuals, empty).
    if not name or len(name) < 3 or _STOPWORD_ONLY.match(name):
        return ""
    return name


def courtlistener_debtors():
    """Recent US bankruptcy (Ch. 7/11) debtor names from CourtListener RECAP."""
    key = os.environ.get("COURTLISTENER_API_KEY")
    if not key:
        return []
    frm = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    out, seen = [], set()
    try:
        r = requests.get(
            "https://www.courtlistener.com/api/rest/v4/search/",
            params={"type": "r", "q": '"chapter 11" OR "chapter 7"',
                    "filed_after": frm, "order_by": "dateFiled desc"},
            headers={**UA, "Authorization": f"Token {key}"}, timeout=40)
        if r.status_code != 200:
            print(f"courtlistener HTTP {r.status_code}: {r.text[:180]}")
            return []
        results = r.json().get("results", [])
        print(f"courtlistener: {len(results)} recent bankruptcy dockets")
        for it in results:
            co = _clean_company(it.get("caseName") or it.get("case_name"))
            k = co.lower()
            if co and k not in seen:
                seen.add(k)
                out.append(co)
    except Exception as exc:
        print(f"courtlistener fetch failed: {exc}")
    return out


def companies_house_insolvent():
    """UK companies currently in administration/liquidation (distress signal)."""
    key = os.environ.get("COMPANIES_HOUSE_API_KEY_UK")
    if not key:
        return []
    out, seen = [], set()
    # Advanced search by status; HTTP Basic auth = key as username, blank password.
    for status in ("administration", "liquidation", "insolvency-proceedings"):
        try:
            r = requests.get(
                "https://api.company-information.service.gov.uk/advanced-search/companies",
                params={"company_status": status, "size": 100},
                auth=(key, ""), headers=UA, timeout=40)
            if r.status_code != 200:
                print(f"companies_house [{status}] HTTP {r.status_code}: {r.text[:150]}")
                continue
            items = r.json().get("items", [])
            print(f"companies_house [{status}]: {len(items)} companies")
            for it in items:
                co = _clean_company(it.get("company_name"))
                k = co.lower()
                if co and k not in seen:
                    seen.add(k)
                    out.append(co)
        except Exception as exc:
            print(f"companies_house [{status}] failed: {exc}")
        time.sleep(0.5)
    return out


def _sweep(companies, label, deadline):
    """Targeted news search + extractor + poster for each distressed company."""
    posted = ai = 0
    # Cap BEFORE the already_have probes so we never run hundreds of lookups
    # (Companies House can return 300); the daily rotation revisits the rest.
    companies = companies[:MAX_CO]
    todo = []
    for c in companies:
        if time.monotonic() > deadline:
            break
        if not already_have(c):
            todo.append(c)
    print(f"{label}: {len(companies)} distressed (capped), {len(todo)} with no current-year entry", flush=True)
    for i in range(0, len(todo), 20):
        if time.monotonic() > deadline:
            print(f"  deadline hit; remaining {label} companies resume next run", flush=True)
            break
        chunk = todo[i:i + 20]
        try:
            entries = pull_news_articles(days_back=DAYS_BACK, queries=[query_for(c) for c in chunk])
        except Exception as exc:
            print(f"  news fetch failed for a chunk: {exc}")
            continue
        for raw in entries:
            try:
                ex = extract_layoff_data(raw)
            except Exception:
                continue
            if not ex:
                continue
            if DRY:
                print(f"  DRY [{label}] {ex.get('company_name')} {ex.get('job_count')} ({ex.get('layoff_date')})")
                continue
            if post_to_wordpress(ex) == "posted":
                posted += 1
                ai += 1 if ex.get("ai_explicit") else 0
                print(f"  + [{label}] {ex.get('company_name')} {ex.get('job_count')} ({ex.get('layoff_date')})")
        time.sleep(1)
    return posted, ai


def run():
    sources = []
    if os.environ.get("COURTLISTENER_API_KEY"):
        sources.append(("courtlistener_bankruptcy", courtlistener_debtors))
    if os.environ.get("COMPANIES_HOUSE_API_KEY_UK"):
        sources.append(("companies_house_insolvency", companies_house_insolvent))
    if not sources:
        print("No COURTLISTENER_API_KEY / COMPANIES_HOUSE_API_KEY_UK set — distress feeder dormant.")
        return
    total_posted = total_ai = 0
    deadline = time.monotonic() + DEADLINE_SECONDS
    for label, fn in sources:
        companies = fn()
        if not companies:
            if not DRY:
                report_source_health(label, "ok", 0, "no distressed companies surfaced this run")
            continue
        posted, ai = _sweep(companies, label, deadline)
        total_posted += posted
        total_ai += ai
        if not DRY:
            report_source_health(label, "ok", posted,
                                 f"{len(companies)} distressed, {posted} layoffs posted ({ai} AI)")
    print(f"distress feeder: {total_posted} posted ({total_ai} AI)")


def main():
    if not os.environ.get("WP_SITE_URL"):
        print("WP_SITE_URL required")
        return 1
    if not DRY and not os.environ.get("WP_API_KEY"):
        print("WP_API_KEY required (or set DISTRESS_DRY=1)")
        return 1
    try:
        run()
        return 0
    except Exception as exc:
        if not DRY:
            report_source_health("distress_watchlist", "degraded", 0, f"distress feeder failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
