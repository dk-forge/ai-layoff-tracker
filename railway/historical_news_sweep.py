"""One success-anchored, rate-limit-safe GDELT historical recovery window."""
import os
import sys
from datetime import date, timedelta

import requests

import gdelt_backfill

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
WINDOW_DAYS = 7


def _api(path, method="GET", payload=None):
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        raise RuntimeError("WP_SITE_URL / WP_API_KEY required")
    response = requests.request(method, f"{site}/wp-json/layoffs/v1/{path}", json=payload,
                                headers={"X-Layoff-API-Key": key, "User-Agent": UA}, timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    cursor = _api("historical-gdelt-cursor")
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
    gdelt_backfill.run()
    if not override:
        _api("historical-gdelt-cursor", "POST", {"next_start": (end + timedelta(days=1)).isoformat()})
        print("Historical GDELT cursor advanced after successful window.")
    else:
        print("Manual override completed; historical cursor unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
