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

import requests

from sources.warn import pull_warn

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
    for i in range(0, len(entries), BATCH):
        chunk = entries[i:i + BATCH]
        n = i // BATCH + 1
        try:
            resp = requests.post(f"{wp}/wp-json/layoffs/v1/bulk",
                                 json={"entries": chunk}, headers=headers, timeout=180)
            if resp.status_code == 200:
                got = resp.json().get("upserted", 0)
                upserted += got
                print(f"  batch {n}/{total_batches}: upserted {got}")
            else:
                FAILED_BATCHES += 1
                print(f"  batch {n}/{total_batches} FAILED: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            FAILED_BATCHES += 1
            print(f"  batch {n}/{total_batches} error: {e}")
    return upserted


def main():
    raw_states = (os.environ.get("WARN_STATES") or "CA").strip()
    states = ["all"] if raw_states.lower() == "all" else [s.strip().upper() for s in raw_states.split(",") if s.strip()]
    min_emp = int(os.environ.get("WARN_MIN_EMPLOYEES") or 0)
    start = os.environ.get("WARN_START") or ""
    limit = int(os.environ.get("WARN_LIMIT") or 0) or None

    scope = "all supported states" if states == ["all"] else f"{len(states)} states"
    print(f"WARN import: {scope}, min_employees={min_emp}, start={start or 'all'}, limit={limit}")
    entries = pull_warn(states, min_employees=min_emp, start_date=start)
    entries.sort(key=lambda e: e["layoff_date"], reverse=True)
    if limit:
        entries = entries[:limit]
    print(f"WARN import: {len(entries)} notices to upsert (bulk)")

    upserted = post_bulk(entries)
    print(f"WARN import done: {upserted} upserted from {len(entries)} notices")

    # A green run must mean the data actually landed — fail loudly if any
    # batch was rejected so the scheduled workflow shows red.
    if FAILED_BATCHES:
        print(f"ERROR: {FAILED_BATCHES} batch(es) failed to post")
        sys.exit(1)


if __name__ == "__main__":
    main()
