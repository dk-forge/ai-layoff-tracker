"""
Imports US state WARN Act notices and posts them directly to WordPress.

WARN forms are already structured (company, headcount, date, location), so they
skip the LLM extractor entirely. Idempotent via the exact dedup hash, so it's
safe to re-run. Manually triggered / scheduled.

Env:
  WARN_STATES         comma list of state codes (default "CA")
  WARN_MIN_EMPLOYEES  drop notices below this headcount (default 100)
  WARN_START          YYYY-MM-DD lower bound on effective date (default "2024-01-01")
  WARN_LIMIT          max posts (blank = no cap)
  WP_SITE_URL, WP_API_KEY
"""
import os

from sources.warn import pull_warn
from wp_poster import post_to_wordpress


def main():
    states = [s.strip().upper() for s in (os.environ.get("WARN_STATES") or "CA").split(",") if s.strip()]
    min_emp = int(os.environ.get("WARN_MIN_EMPLOYEES") or 100)
    start = os.environ.get("WARN_START") or "2024-01-01"
    limit = int(os.environ.get("WARN_LIMIT") or 0) or None

    print(f"WARN import: states={states} min_employees={min_emp} start={start} limit={limit}")
    entries = pull_warn(states, min_employees=min_emp, start_date=start)
    entries.sort(key=lambda e: e["layoff_date"], reverse=True)
    if limit:
        entries = entries[:limit]
    print(f"WARN import: {len(entries)} candidate notices to post")

    posted = dup = failed = 0
    for e in entries:
        result = post_to_wordpress(e)
        if result == "posted":
            posted += 1
        elif result == "duplicate":
            dup += 1
        else:
            failed += 1

    print(f"WARN import done: {posted} posted, {dup} duplicate, {failed} failed")


if __name__ == "__main__":
    main()
