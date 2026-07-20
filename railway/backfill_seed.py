"""One-shot curated backfill: ingest a JSON of verified, source-linked named
layoff events (seed_data/backfill_2023_2024.json by default) via the same
idempotent, dedup-guarded path as seed_ai.py.

These are events forensic research found MISSING from the tracker vs the
Challenger benchmark for the thin historical years (2023-2024). Each carries a
real source URL; none is AI-attributed (verified separately), so this raises the
broad US all-cuts coverage only, never the AI line. Idempotent: re-running
re-posts nothing (company+date+count dedup hash is checked server-side).

Env: WP_SITE_URL, WP_API_KEY. Optional BACKFILL_SEED (path), BACKFILL_DRY_RUN=1.
"""
import hashlib
import json
import os
import sys

from wp_poster import post_to_wordpress

SEED_PATH = os.environ.get(
    "BACKFILL_SEED",
    os.path.join(os.path.dirname(__file__), "seed_data", "backfill_2023_2024.json"))
DRY_RUN = os.environ.get("BACKFILL_DRY_RUN", "").lower() in {"1", "true", "yes"}


def run():
    with open(SEED_PATH, encoding="utf-8") as fh:
        entries = json.load(fh)
    print(f"Backfill seed: {len(entries)} verified events, "
          f"{sum(int(e.get('job_count') or 0) for e in entries):,} jobs total")

    posted = dupes = failed = 0
    for entry in entries:
        company = (entry.get("company_name") or "").strip()
        job_count = entry.get("job_count")
        if not company or not job_count:
            print(f"  skip (missing company/count): {company}")
            failed += 1
            continue
        # Standard news-event dedup hash (company + date + count) — matches the
        # ingest pipeline so a later news pull of the same event dedups cleanly.
        entry["dedup_hash"] = hashlib.md5(
            f"{company.lower()}{entry.get('layoff_date') or ''}{job_count}".encode("utf-8")).hexdigest()
        if DRY_RUN:
            print(f"  DRY: would post {company} {job_count} {entry.get('layoff_date')}")
            continue
        status = post_to_wordpress(entry)
        print(f"  {status}: {company} {job_count} {entry.get('layoff_date')}")
        if status == "posted":
            posted += 1
        elif status == "duplicate":
            dupes += 1
        else:
            failed += 1

    if DRY_RUN:
        print("DRY RUN: nothing posted.")
        return
    print(f"Backfill complete: {posted} posted, {dupes} already present, {failed} failed")
    # Fail loudly only if EVERYTHING failed (a systemic problem); a few
    # individual dupes/failures are expected and non-fatal.
    if failed and not posted and not dupes:
        sys.exit(1)


if __name__ == "__main__":
    if not os.environ.get("WP_SITE_URL") or (not os.environ.get("WP_API_KEY") and not DRY_RUN):
        print("WP_SITE_URL and WP_API_KEY required (or set BACKFILL_DRY_RUN=1)")
        sys.exit(1)
    run()
