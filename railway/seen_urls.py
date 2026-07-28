"""Shared seen-URL pre-check: drop entries whose EXACT source_url the site
already holds, BEFORE any LLM spend. Extracted from cron.py (2026-07-28) so the
satellite ingest scripts (gdelt_backfill, company_watchlist, supplemental_news)
stop re-paying for URLs the main cron already extracted - in cron alone this
check removes ~60% of daily extraction volume. Fails OPEN: a broken pre-check
may only ever cost a slightly higher LLM bill, never a missed layoff.
"""
import os

import requests


def filter_already_seen(entries):
    """Drop entries whose EXACT source_url is already in the record.

    Batched POSTs to the keyed /seen-urls endpoint (main rows + retained
    source reports). Only same-URL re-reads are dropped - a fresh outlet on
    the same event has a different URL and always goes to the extractor.
    Fails OPEN on any error: the worst outcome of a broken pre-check must be
    a slightly higher LLM bill, never a missed layoff.
    """
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    urls = [e.get("source_url") for e in entries if e.get("source_url")]
    if not (site and key and urls):
        return entries
    seen = set()
    try:
        for i in range(0, len(urls), 400):
            resp = requests.post(
                f"{site}/wp-json/layoffs/v1/seen-urls",
                json={"urls": urls[i:i + 400]},
                headers={"X-Layoff-API-Key": key,
                         "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"},
                timeout=30)
            if resp.status_code != 200:
                print(f"seen-urls pre-check HTTP {resp.status_code} - extracting everything (fail open)")
                return entries
            seen.update(resp.json().get("seen", []))
    except Exception as exc:
        print(f"seen-urls pre-check failed ({exc}) - extracting everything (fail open)")
        return entries
    kept = [e for e in entries if not (e.get("source_url") and e.get("source_url") in seen)]
    print(f"seen-urls pre-check: {len(entries) - len(kept)} same-URL re-read(s) skipped "
          f"before the extractor, {len(kept)} to process")
    return kept
