"""Tracker-diff discovery tripwire — automated 'work backwards from other trackers'.

Takes a competitor company list, diffs it against our own data, and for anything
they list that we lack, fires a company-TARGETED primary-source query → the same
DeepSeek extractor + dedup + poster. We never cite the competitor: their list is a
discovery SIGNAL that points us at a primary source, which is what actually gets
stored. Company names arrive ONLY via a secret (never committed, per the
standalone-brand rule), and only counts/slice indices are logged — never the list.

Two ways to supply the list (use either or both):
  * COMPETITOR_FEED_URLS  — comma-separated URLs, each returning a JSON array of
    {company, date?, jobs?} objects (or {"data":[...]}/{"events":[...]}) OR a CSV
    with a `company`/`company_name`/`name` column.
  * COMPETITOR_COMPANIES  — the list pasted inline (comma- or newline-separated
    company names). Use this when the competitor has no machine feed but you can
    see their list: paste the names into this secret and the cron chases them.

Ships DORMANT: with neither set it logs and exits clean, so the repo carries zero
competitor data. The owner adds a secret to activate.

Each daily run chases a rotating slice (TRACKER_DIFF_MAX companies), so over a few
days the WHOLE list is walked — not just the first slice each time.

Env: COMPETITOR_FEED_URLS, COMPETITOR_COMPANIES (secrets), TRACKER_DIFF_MAX
(default 40 companies per run), TRACKER_DIFF_DRY=1 (log, don't post).
"""
import csv
import io
import json
import os
import re
import sys
import time
from datetime import date

import requests

from company_watchlist import already_have, query_for, DAYS_BACK
from sources.newsapi import pull_news_articles
from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
FEEDS = [u.strip() for u in (os.environ.get("COMPETITOR_FEED_URLS") or "").split(",") if u.strip()]
INLINE = [n.strip() for n in re.split(r"[,\n]", os.environ.get("COMPETITOR_COMPANIES") or "") if n.strip()]
MAX_CHASE = max(1, int(os.environ.get("TRACKER_DIFF_MAX", "40")))
DRY = os.environ.get("TRACKER_DIFF_DRY", "").lower() in {"1", "true", "yes"}


def _parse_feed(url, label):
    """Return a list of company names from a competitor feed (JSON or CSV).

    NEVER print the URL (it's a private competitor source in a secret; a URL
    substring can slip past GitHub's secret masking into a public Actions log).
    Reference the feed only by its index `label`.
    """
    try:
        r = requests.get(url, headers=UA, timeout=40)
        if r.status_code != 200:
            print(f"feed {label}: HTTP {r.status_code}")
            return []
        body = r.text
    except Exception as exc:
        print(f"feed {label}: fetch failed ({type(exc).__name__})")
        return []
    names = []
    body_strip = body.lstrip()
    if body_strip[:1] in ("[", "{"):
        try:
            data = json.loads(body)
            rows = data if isinstance(data, list) else (data.get("data") or data.get("events") or [])
            for r in rows:
                if isinstance(r, dict):
                    n = r.get("company") or r.get("company_name") or r.get("name")
                    if n:
                        names.append(str(n).strip())
        except Exception as exc:
            print(f"feed {label}: JSON parse failed ({type(exc).__name__})")
    else:
        try:
            for row in csv.DictReader(io.StringIO(body)):
                n = (row.get("company") or row.get("company_name") or row.get("name") or "").strip()
                if n:
                    names.append(n)
        except Exception as exc:
            print(f"feed {label}: CSV parse failed ({type(exc).__name__})")
    return names


def run():
    if not FEEDS and not INLINE:
        print("Neither COMPETITOR_FEED_URLS nor COMPETITOR_COMPANIES set — tripwire "
              "dormant, nothing to diff. Paste a competitor company list into the "
              "COMPETITOR_COMPANIES secret (or a feed URL into COMPETITOR_FEED_URLS) "
              "to activate; either stays out of the repo.")
        return
    by_key = {}
    for i, url in enumerate(FEEDS, 1):
        for n in _parse_feed(url, f"#{i}"):
            by_key.setdefault(n.lower(), n)
    for n in INLINE:
        by_key.setdefault(n.lower(), n)
    competitor_names = sorted(by_key.values(), key=str.lower)  # stable order for the rotating slice
    n_total = len(competitor_names)
    if not n_total:
        print("competitor list resolved to 0 companies — nothing to diff.")
        report_source_health("tracker_diff", "ok", 0, "0 competitor companies resolved")
        return

    # Walk a rotating slice each day so the WHOLE list gets covered over time,
    # not just the first MAX_CHASE every run. The calendar date is the cursor.
    n_slices = max(1, (n_total + MAX_CHASE - 1) // MAX_CHASE)
    slice_idx = date.today().toordinal() % n_slices
    window = competitor_names[slice_idx * MAX_CHASE:(slice_idx + 1) * MAX_CHASE]
    missing = [c for c in window if not already_have(c)]
    print(f"competitor list: {n_total} companies; slice {slice_idx + 1}/{n_slices} "
          f"({len(window)} examined); they list, we lack: {len(missing)}")
    posted = ai = 0
    for i in range(0, len(missing), 20):
        chunk = missing[i:i + 20]
        try:
            entries = pull_news_articles(days_back=DAYS_BACK, queries=[query_for(c) for c in chunk])
        except Exception as exc:
            print(f"news fetch failed: {exc}")
            continue
        for raw in entries:
            try:
                ex = extract_layoff_data(raw)
            except Exception:
                continue
            if not ex:
                continue
            if DRY:
                print(f"  DRY would add: {ex.get('company_name')} {ex.get('job_count')}")
                continue
            if post_to_wordpress(ex) == "posted":
                posted += 1
                ai += 1 if ex.get("ai_explicit") else 0
                print(f"  + {ex.get('company_name')} {ex.get('job_count')} ({ex.get('layoff_date')})")
        time.sleep(1)
    detail = (f"{n_total} listed; slice {slice_idx + 1}/{n_slices}; "
              f"{len(missing)} missing chased, {posted} added ({ai} AI)")
    print("tracker-diff:", detail)
    if not DRY:
        report_source_health("tracker_diff", "ok", posted, detail)


def main():
    if not (os.environ.get("WP_SITE_URL") and (DRY or os.environ.get("WP_API_KEY"))):
        print("WP_SITE_URL (and WP_API_KEY unless dry) required")
        return 1
    try:
        run()
        return 0
    except Exception as exc:
        if not DRY:
            report_source_health("tracker_diff", "degraded", 0, f"tracker-diff failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
