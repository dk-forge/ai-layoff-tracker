"""
Historical/global news backfill via GDELT. Walks monthly windows from
BACKFILL_START to BACKFILL_END, pulls AI-related layoff coverage from trusted
outlets worldwide, and runs each through the same extractor + dedup + poster.

Idempotent (dedup guard). Env:
  OPENROUTER_API_KEY, WP_SITE_URL, WP_API_KEY
  BACKFILL_START  YYYY-MM-DD (default 2024-01-01)
  BACKFILL_END    YYYY-MM-DD (default today, UTC)
  BACKFILL_LIMIT  int        (optional cap on posts — for a test run)
  BACKFILL_MAX_ARTICLES int  (optional cap on model candidates; use for schedules)
  BACKFILL_DEADLINE_SECONDS int (optional wall-time budget; scheduled safety)
"""
import os
import time
from datetime import datetime, timedelta, timezone

from sources.gdelt import pull_gdelt_between
from extractor import extract_layoff_data
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


def _is_upstream_throttle(exc):
    """True when the third party throttled or timed out on us, rather than the
    collector being broken."""
    text = str(exc).lower()
    return any(m in text for m in ("429", "rate limit", "too many requests",
                                   "timed out", "timeout", "503", "502", "504"))


def run():
    start = _parse(os.environ.get("BACKFILL_START"),
                  datetime(2024, 1, 1, tzinfo=timezone.utc))
    end = _parse(os.environ.get("BACKFILL_END"), datetime.now(timezone.utc))
    limit = int(os.environ.get("BACKFILL_LIMIT") or 0) or None
    max_articles = int(os.environ.get("BACKFILL_MAX_ARTICLES") or 0) or None
    deadline_seconds = int(os.environ.get("BACKFILL_DEADLINE_SECONDS") or 0) or None
    started_at = time.monotonic()
    print(f"GDELT backfill {start.date()} → {end.date()}"
          + (f" (post limit {limit})" if limit else "")
          + (f" (candidate cap {max_articles})" if max_articles else ""))

    posted = dupes = skipped = failed = ai = considered = 0
    for w_start, w_end in week_windows(start, end):
        label = w_start.strftime("%Y-%m-%d")
        try:
            report_source_health("gdelt_historical", "running", 0, f"window {label}: collection in progress")
            remaining = max_articles - considered if max_articles else 250
            # The collection phase (rotating GDELT sweeps against a shared,
            # sometimes-throttled endpoint) used to have no clock of its own —
            # only the extraction loop below checked BACKFILL_DEADLINE_SECONDS
            # — so a throttled run could burn the whole timeout-minutes budget
            # before a single article was considered (run 33094996142,
            # 2026-08-27). Same run-wide deadline, passed to the phase that
            # actually blocks.
            deadline = (started_at + deadline_seconds) if deadline_seconds else None
            entries = pull_gdelt_between(w_start, w_end, max_records=min(250, remaining),
                                          deadline=deadline)
            # Same-URL re-reads cost LLM tokens and yield nothing new; the
            # shared pre-check drops them before extraction (fails open).
            try:
                from seen_urls import filter_already_seen
                entries = filter_already_seen(entries)
            except Exception:
                pass
            report_source_health("gdelt_historical", "ok", len(entries), f"window {label}")
        except Exception as exc:
            report_source_health("gdelt_historical", "degraded", 0, f"window {label}: {exc}")
            # An upstream THROTTLE is not our failure. GDELT answers 429 under
            # load and the collector already backs off 5 times; turning that
            # into a red run emails a breakage that no human can act on, and
            # contradicts the health ledger, which classifies gdelt_historical
            # as expected-transient. Nothing is half-written (the window either
            # returns articles or none) and the cursor only advances on a
            # completed window, so stopping here loses no coverage: the same
            # window is retried next run. Any OTHER error still raises, so a
            # genuinely broken parser cannot hide behind this.
            if _is_upstream_throttle(exc):
                print(f"::warning::[{label}] upstream rate limit ({exc}); "
                      f"stopping this run with progress kept, window retries next run")
                _summary(posted, ai, dupes, skipped, failed, considered)
                return
            raise
        print(f"[{label}] {len(entries)} articles")
        for raw in entries:
            if deadline_seconds and time.monotonic() - started_at >= deadline_seconds:
                print(f"Reached BACKFILL_DEADLINE_SECONDS={deadline_seconds}; stopping safely.")
                _summary(posted, ai, dupes, skipped, failed, considered)
                return
            if max_articles and considered >= max_articles:
                print(f"Reached BACKFILL_MAX_ARTICLES={max_articles}; stopping.")
                _summary(posted, ai, dupes, skipped, failed, considered)
                return
            considered += 1
            if limit and posted >= limit:
                print(f"Reached BACKFILL_LIMIT={limit}; stopping.")
                _summary(posted, ai, dupes, skipped, failed, considered)
                return
            try:
                extracted = extract_layoff_data(raw)
                if not extracted:
                    skipped += 1
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

    _summary(posted, ai, dupes, skipped, failed, considered)


def _summary(posted, ai, dupes, skipped, failed, considered):
    print(f"GDELT backfill complete: {posted} posted ({ai} AI-cited), "
          f"{dupes} duplicates, {skipped} non-events, {failed} failed, "
          f"{considered} candidates considered")


if __name__ == "__main__":
    run()
