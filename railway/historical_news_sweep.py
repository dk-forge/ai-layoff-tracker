"""One success-anchored, rate-limit-safe GDELT historical recovery window."""
import os
import sys
import time
from datetime import date, timedelta

import requests

import gdelt_backfill

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
WINDOW_DAYS = 7

#: Bluehost 504s that outlive these retries are an OUTAGE, and the outage
#: already has an owner: the sibling repo's host-watch opens one issue per
#: sustained outage. This script's job is only to not lose data over it.
TRANSIENT = {500, 502, 503, 504}


def _api(path, method="GET", payload=None, attempts=3, sleep=None):
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        raise RuntimeError("WP_SITE_URL / WP_API_KEY required")
    # Retried in-run for transient 5xx, because on 2026-07-29 (run
    # 30482640840) the whole window succeeded and then a single 504 on the
    # cursor save turned a healthy sweep into a red run. Every OTHER call to
    # this host in the sweep already fails soft; the cursor was the only hard
    # raise left.
    last = None
    for attempt in range(attempts):
        try:
            response = requests.request(
                method, f"{site}/wp-json/layoffs/v1/{path}", json=payload,
                headers={"X-Layoff-API-Key": key, "User-Agent": UA}, timeout=30)
            if response.status_code in TRANSIENT:
                last = requests.HTTPError(f"HTTP {response.status_code} from {path}",
                                          response=response)
            else:
                response.raise_for_status()
                return response.json()
        except requests.RequestException as exc:
            last = exc
        if attempt + 1 < attempts:
            # Resolved at call time so a test can stub `time.sleep` on this
            # module rather than wait out real backoff.
            (sleep or time.sleep)(5 * (attempt + 1))
    raise last


def main():
    try:
        cursor = _api("historical-gdelt-cursor")
    except requests.RequestException as exc:
        # Nothing ran yet, nothing is lost: the identical window is attempted
        # on the next daily schedule. A host outage is host-watch's action
        # item (sibling repo), not this run's, so this is a notice and a
        # green exit rather than a red run that emails the owner.
        print(f"::notice::historical sweep deferred: could not read the cursor ({exc}); "
              "the same window retries on the next schedule")
        return 0
    today = date.today()
    override = os.environ.get("HISTORICAL_START_OVERRIDE", "").strip()
    start = date.fromisoformat(override or cursor.get("next_start") or "2017-01-01")
    if start > today:
        print("Historical GDELT recovery is caught up; live GDELT handles recent coverage.")
        return 0
    override_end = os.environ.get("HISTORICAL_END_OVERRIDE", "").strip()
    end = date.fromisoformat(override_end) if override_end else min(start + timedelta(days=WINDOW_DAYS - 1), today)
    if end < start or end - start >= timedelta(days=WINDOW_DAYS):
        raise RuntimeError("Historical GDELT sweep must cover a 1–7 day window")
    os.environ["BACKFILL_START"] = start.isoformat()
    os.environ["BACKFILL_END"] = end.isoformat()
    print(f"Success-anchored historical GDELT window: {start} to {end}")
    try:
        gdelt_backfill.run()
    except RuntimeError as exc:
        # GDELT's shared public endpoint can explicitly throttle a healthy
        # client. The backfill already recorded this as degraded, and because
        # the cursor is not advanced the identical window will retry later.
        # Treat it as a visible deferred condition, not a red repository/code
        # failure that floods the owner with email. Other exceptions still
        # fail loudly for investigation.
        if "HTTP 429" in str(exc):
            print("GDELT historical recovery deferred by upstream rate limit; cursor retained for retry.")
            return 0
        raise
    if not override:
        try:
            _api("historical-gdelt-cursor", "POST",
                 {"next_start": (end + timedelta(days=1)).isoformat()})
            print("Historical GDELT cursor advanced after successful window.")
        except requests.RequestException as exc:
            # The window itself SUCCEEDED; only the bookkeeping write was
            # refused (2026-07-29: a ~6-minute Bluehost 504 landed exactly
            # here). An unadvanced cursor means the next run repeats the same
            # window and dedup absorbs it — self-healing, zero human action —
            # so this is a notice, not a red run.
            print(f"::notice::cursor save deferred ({exc}); the next scheduled "
                  "run repeats this window and dedup absorbs the overlap")
    else:
        print("Manual override completed; historical cursor unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
