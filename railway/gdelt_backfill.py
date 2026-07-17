"""
Historical/global news backfill via GDELT. Walks monthly windows from
BACKFILL_START to BACKFILL_END, pulls AI-related layoff coverage from trusted
outlets worldwide, and runs each through the same extractor + dedup + poster.

Idempotent (dedup guard). Env:
  OPENROUTER_API_KEY, WP_SITE_URL, WP_API_KEY
  BACKFILL_START  YYYY-MM-DD (default 2024-01-01)
  BACKFILL_END    YYYY-MM-DD (default today, UTC)
  BACKFILL_LIMIT  int        (optional cap on posts — for a test run)
"""
import os
from datetime import datetime, timedelta, timezone

from sources.gdelt import pull_gdelt_between
from extractor import extract_layoff_data
from deduplicator import is_duplicate
from wp_poster import post_to_wordpress
from source_health import report_source_health


def _parse(value, default):
    if not value:
        return default
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def week_windows(start, end):
    # Weekly (was monthly): GDELT caps each call at 250 articles sorted
    # newest-first, and the general layoffs query (no AI clause) fills a busy
    # MONTH past the cap — which silently dropped the early weeks.
    cur = start
    while cur <= end:
        nxt = cur + timedelta(days=7)
        yield cur, min(nxt - timedelta(seconds=1), end)
        cur = nxt


def run():
    start = _parse(os.environ.get("BACKFILL_START"),
                  datetime(2024, 1, 1, tzinfo=timezone.utc))
    end = _parse(os.environ.get("BACKFILL_END"), datetime.now(timezone.utc))
    limit = int(os.environ.get("BACKFILL_LIMIT") or 0) or None
    print(f"GDELT backfill {start.date()} → {end.date()}"
          + (f" (limit {limit})" if limit else ""))

    posted = dupes = skipped = failed = ai = 0
    for w_start, w_end in week_windows(start, end):
        label = w_start.strftime("%Y-%m-%d")
        try:
            entries = pull_gdelt_between(w_start, w_end)
            report_source_health("gdelt_historical", "ok", len(entries), f"window {label}")
        except Exception as exc:
            report_source_health("gdelt_historical", "degraded", 0, f"window {label}: {exc}")
            raise
        print(f"[{label}] {len(entries)} articles")
        for raw in entries:
            if limit and posted >= limit:
                print(f"Reached BACKFILL_LIMIT={limit}; stopping.")
                _summary(posted, ai, dupes, skipped, failed)
                return
            try:
                extracted = extract_layoff_data(raw)
                if not extracted:
                    skipped += 1
                    continue
                if is_duplicate(extracted["dedup_hash"]):
                    dupes += 1
                    continue
                status = post_to_wordpress(extracted)
                if status == "posted":
                    posted += 1
                    if extracted.get("ai_explicit"):
                        ai += 1
                        print(f"  ★ AI-cited: {extracted.get('company_name')}")
                elif status == "duplicate":
                    dupes += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                print(f"[{label}] error {raw.get('source_url')}: {e}")
        print(f"[{label}] totals — posted {posted} ({ai} AI), dupes {dupes}, "
              f"non-events {skipped}, failed {failed}")

    _summary(posted, ai, dupes, skipped, failed)


def _summary(posted, ai, dupes, skipped, failed):
    print(f"GDELT backfill complete: {posted} posted ({ai} AI-cited), "
          f"{dupes} duplicates, {skipped} non-events, {failed} failed")


if __name__ == "__main__":
    run()
