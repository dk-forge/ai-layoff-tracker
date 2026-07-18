"""
Imports US state WARN Act notices straight into the fast-query table.

WARN forms are already structured (company, headcount, date, location), so they
skip the LLM extractor. They're written via the bulk table endpoint (not the CPT
/add path) so 100K+ notices don't create 100K WordPress posts. Idempotent via the
exact dedup hash, so it's safe to re-run.

Env:
  WARN_STATES         comma list of state codes, or "all" (default "CA")
  WARN_MIN_EMPLOYEES  drop notices below this headcount (default 0 = keep all)
  WARN_START          YYYY-MM-DD lower bound on effective date (default "" = all)
  WARN_LIMIT          max notices (blank = no cap)
  WP_SITE_URL, WP_API_KEY
"""
import os
import sys
import time

import requests

from sources.warn import pull_warn
from sources.warn_custom import pull_warn_custom
from source_health import report_source_health

BATCH = 1000
FAILED_BATCHES = 0


def post_bulk(entries):
    global FAILED_BATCHES
    wp = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
    key = os.environ.get("WP_API_KEY")
    if not wp or not key:
        print("post_bulk error: WP_SITE_URL or WP_API_KEY not set")
        FAILED_BATCHES += 1
        return 0
    headers = {
        "X-Layoff-API-Key": key,
        "Content-Type": "application/json",
        "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)",
    }
    upserted = 0
    total_batches = (len(entries) + BATCH - 1) // BATCH
    # The shared host intermittently answers 5xx/timeouts under load (a
    # 2026-07-18 nationwide reload lost 5 batches to 504s). The upsert is
    # hash-idempotent, so retrying a batch is always safe; only a batch that
    # stays failed after the retries counts against the run.
    transient = {500, 502, 503, 504, 520, 521, 522, 524}
    for i in range(0, len(entries), BATCH):
        chunk = entries[i:i + BATCH]
        n = i // BATCH + 1
        for attempt in range(3):
            try:
                resp = requests.post(f"{wp}/wp-json/layoffs/v1/bulk",
                                     json={"entries": chunk}, headers=headers, timeout=180)
                if resp.status_code == 200:
                    got = resp.json().get("upserted", 0)
                    upserted += got
                    print(f"  batch {n}/{total_batches}: upserted {got}")
                    break
                if resp.status_code in transient and attempt < 2:
                    print(f"  batch {n}/{total_batches}: transient {resp.status_code}, retrying in 60s")
                    time.sleep(60)
                    continue
                FAILED_BATCHES += 1
                print(f"  batch {n}/{total_batches} FAILED: {resp.status_code} {resp.text[:200]}")
                break
            except Exception as e:
                if attempt < 2:
                    print(f"  batch {n}/{total_batches}: {e}; retrying in 60s")
                    time.sleep(60)
                    continue
                FAILED_BATCHES += 1
                print(f"  batch {n}/{total_batches} error: {e}")
                break
    return upserted


def main():
    raw_states = (os.environ.get("WARN_STATES") or "CA").strip()
    states = ["all"] if raw_states.lower() == "all" else [s.strip().upper() for s in raw_states.split(",") if s.strip()]
    min_emp = int(os.environ.get("WARN_MIN_EMPLOYEES") or 0)
    start = os.environ.get("WARN_START") or ""
    limit = int(os.environ.get("WARN_LIMIT") or 0) or None

    scope = "all supported states" if states == ["all"] else f"{len(states)} states"
    purge = (os.environ.get("WARN_PURGE") or "").lower() in ("1", "true", "yes")
    print(f"WARN import: {scope}, min_employees={min_emp}, start={start or 'all'}, limit={limit}, purge={purge}")

    # Purge deletes EVERY state's table-only WARN rows, so it may only pair
    # with a full nationwide reload — purging then importing one state would
    # silently drop the rest.
    if purge and states != ["all"]:
        print("ERROR: WARN_PURGE requires WARN_STATES=all (purge is global; a "
              "state-scoped reload would wipe the other states)")
        sys.exit(1)
    report_source_health("warn_us", "running", 0, f"WARN import in progress: {scope}")
    try:
        entries = pull_warn(states, min_employees=min_emp, start_date=start)
    except Exception as exc:
        report_source_health("warn_us", "degraded", 0, f"WARN scrape failed: {exc}")
        raise
    # Custom collectors cover the states whose sites broke the open scraper
    # (TX, FL, GA, OH, MI, CO, ID, LA).
    customs = pull_warn_custom(states)
    if min_emp:
        customs = [e for e in customs if e["job_count"] >= min_emp]
    if start:
        customs = [e for e in customs if e["layoff_date"] >= start]
    entries.extend(customs)
    entries.sort(key=lambda e: e["layoff_date"], reverse=True)
    if limit:
        entries = entries[:limit]
    print(f"WARN import: {len(entries)} notices to upsert (bulk)")

    # Purge only AFTER a successful scrape, and only when the scrape looks like
    # a real nationwide sweep — never leave the public table empty because the
    # state sites happened to be down today.
    if purge:
        if len(entries) < 5000:
            print(f"ERROR: refusing to purge — scrape returned only "
                  f"{len(entries)} notices (expected 20K+ nationwide); the "
                  f"replacement data is too small to swap in safely")
            sys.exit(1)
        wp = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
        key = os.environ.get("WP_API_KEY")
        try:
            resp = requests.post(f"{wp}/wp-json/layoffs/v1/bulk-purge", headers={
                "X-Layoff-API-Key": key,
                "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)",
            }, timeout=120)
            print(f"purge: HTTP {resp.status_code} {resp.text[:120]}")
            if resp.status_code != 200:
                print("ERROR: purge failed, aborting so stale rows aren't duplicated")
                sys.exit(1)
        except Exception as e:
            print(f"ERROR: purge failed ({e}), aborting")
            sys.exit(1)

    upserted = post_bulk(entries)
    print(f"WARN import done: {upserted} upserted from {len(entries)} notices")

    # A green run must mean the data actually landed — fail loudly if any
    # batch was rejected so the scheduled workflow shows red.
    if FAILED_BATCHES:
        print(f"ERROR: {FAILED_BATCHES} batch(es) failed to post")
        report_source_health("warn_us", "degraded", 0,
                             f"{FAILED_BATCHES} bulk batch(es) rejected by the API")
        sys.exit(1)
    report_source_health("warn_us", "ok", len(entries),
                         f"{scope}: {upserted} upserted from {len(entries)} notices")


if __name__ == "__main__":
    main()
