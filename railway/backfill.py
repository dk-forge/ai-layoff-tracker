"""
Historical backfill from SEC EDGAR.

Walks monthly windows from BACKFILL_START to BACKFILL_END, pulls 8-K filings
with layoff language, runs them through the same DeepSeek extractor + dedup +
WordPress poster as the daily cron, and posts the verified ones.

Idempotent: the dedup guard (Railway pre-check + server-side 409) prevents
re-posting, so this is safe to re-run or resume.

Two modes:
  * Explicit range  — set BACKFILL_START/END for a one-shot window.
  * Rotating sweep  — set BACKFILL_ROTATE=1 and a daily cron backfills ONE month
    per run, deterministically walking the whole [BACKFILL_ANCHOR_YEAR..now]
    range and wrapping, so every past AND current-year month (2025, 2026, ...)
    keeps getting re-verified and any gap self-fills with no server-side cursor.
    Mirrors industry_backfill.rotating_slice.

Env:
  OPENROUTER_API_KEY, WP_SITE_URL, WP_API_KEY, EDGAR_USER_AGENT  (as usual)
  BACKFILL_ROTATE        1 => rotating single-month sweep (ignores START/END)
  BACKFILL_ANCHOR_YEAR   int (default 2015) — oldest year the sweep walks
  BACKFILL_START   YYYY-MM-DD  (default 2024-01-01; used when not rotating)
  BACKFILL_END     YYYY-MM-DD  (default today, UTC; used when not rotating)
  BACKFILL_LIMIT   int         (optional cap on posts — use for a test run)
"""
import os
from datetime import datetime, timedelta, timezone


def rotating_window(anchor_year, now=None):
    """Deterministic single-month [start, end] that advances one month per
    calendar day and wraps — so a daily cron walks the entire history and keeps
    re-verifying it. No persisted cursor: the date IS the cursor."""
    now = now or datetime.now(timezone.utc)
    months = []
    y, m = anchor_year, 1
    while (y, m) <= (now.year, now.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    wy, wm = months[now.toordinal() % len(months)]
    start = datetime(wy, wm, 1, tzinfo=timezone.utc)
    nxt = datetime(wy + 1, 1, 1, tzinfo=timezone.utc) if wm == 12 \
        else datetime(wy, wm + 1, 1, tzinfo=timezone.utc)
    return start, min(nxt - timedelta(seconds=1), now)

from sources.edgar import pull_edgar_filings_between
from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health


def _parse_date(value, default):
    if not value:
        return default
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def month_windows(start, end):
    """Yield (window_start, window_end) for each calendar month in [start, end]."""
    cur = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    while cur <= end:
        if cur.month == 12:
            nxt = datetime(cur.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            nxt = datetime(cur.year, cur.month + 1, 1, tzinfo=timezone.utc)
        yield max(cur, start), min(nxt - timedelta(seconds=1), end)
        cur = nxt


def run():
    if os.environ.get("BACKFILL_ROTATE"):
        anchor = int(os.environ.get("BACKFILL_ANCHOR_YEAR") or 2015)
        start, end = rotating_window(anchor)
        print(f"EDGAR rotating sweep (anchor {anchor}): this run backfills "
              f"{start.strftime('%Y-%m')}")
    else:
        start = _parse_date(os.environ.get("BACKFILL_START"),
                            datetime(2024, 1, 1, tzinfo=timezone.utc))
        end = _parse_date(os.environ.get("BACKFILL_END"), datetime.now(timezone.utc))
    limit = int(os.environ.get("BACKFILL_LIMIT") or 0) or None

    print(f"Backfill {start.date()} → {end.date()}"
          + (f" (limit {limit})" if limit else ""))

    posted = dupes = skipped = failed = 0
    for w_start, w_end in month_windows(start, end):
        label = w_start.strftime("%Y-%m")
        try:
            entries = pull_edgar_filings_between(w_start, w_end)
            report_source_health("edgar_historical", "ok", len(entries), f"window {label}")
        except Exception as e:
            report_source_health("edgar_historical", "degraded", 0, f"window {label}: {e}")
            print(f"[{label}] EDGAR pull failed: {e}")
            continue
        print(f"[{label}] {len(entries)} candidate filings")

        for raw in entries:
            if limit and posted >= limit:
                print(f"Reached BACKFILL_LIMIT={limit}; stopping early.")
                _summary(posted, dupes, skipped, failed)
                return
            try:
                extracted = extract_layoff_data(raw)
                if not extracted:
                    skipped += 1
                    continue
                status = post_to_wordpress(extracted)
                if status == "posted":
                    posted += 1
                elif status == "duplicate":
                    dupes += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                print(f"[{label}] error on {raw.get('source_url')}: {e}")

        print(f"[{label}] totals so far — posted {posted}, dupes {dupes}, "
              f"non-events {skipped}, failed {failed}")

    _summary(posted, dupes, skipped, failed)


def _summary(posted, dupes, skipped, failed):
    print(f"Backfill complete: {posted} posted, {dupes} duplicates, "
          f"{skipped} non-events skipped, {failed} failed")


if __name__ == "__main__":
    run()
