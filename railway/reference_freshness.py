#!/usr/bin/env python3
"""Is each stored reference dataset (BLS, OECD...) still being refreshed?

The same question as ingest_silence.py, asked of reference data: a collector
that keeps failing soft (it deliberately never overwrites good data with a bad
pull) leaves yesterday's document in place and looks healthy forever. So this
reads the public GET /reference/<source> and judges two ages:

  * COLLECTOR age: `updated` (when the collector last stored a pull). Over
    `collector_days` means the job itself stopped landing.
  * DATA age: days from the END of the newest reference month to today, per
    dataset. Over that dataset's ceiling means the publisher's release is
    later than its real lag plus our collection cadence plus a margin.

Each ceiling is derived from the publisher's real release calendar, not a
round number (see SPECS). Exit 0 fresh, 1 stale, 3 unknown (unreadable is
never a pass). One `::notice`/`::error` line per source.

Stdlib only; read-only public GET.
"""
from __future__ import annotations

import calendar
import json
import sys
import urllib.request
import uuid
from datetime import date, datetime, timezone

BASE = "https://asktherecruiter.com/blog"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# DERIVATIONS (days after the end of the newest month before we call it stale)
#   JOLTS: month M publishes ~5 weeks after M ends, so just before the next
#     release the newest month is ~65 days old; +7 weekly collection; +13
#     margin for a slipped release date = 85.
#   CPS: month M publishes the first Friday of M+1, so just before the next
#     release the newest month is ~38 days old; +7 weekly; +5 margin = 50.
#   OECD monthly unemployment: month M publishes mid M+2, so just before
#     the next release the newest month (max over countries) is ~75 days
#     old; +7 weekly collection; +13 margin = 95.
#   FRED monthly series: the slowest is JOLTS layoffs (JTSLDL), same 65-day
#     lag as JOLTS above -> 85. FRED weekly claims (ICSA/CCSA): week ending
#     Sat publishes the next Thursday (CCSA a week later), stored as the
#     month of the newest week; month end can be ~2 weeks before the next
#     newest week + 7 weekly + 6 margin = 30 (generous for a holiday slip).
#   Census QWI: quarter Q publishes roughly 9-10 months after Q ends and
#     releases quarterly, so just before the next release the newest
#     quarter is ~300+92 days old; +7 weekly; +31 margin = 430.
#   Collector: weekly job (7) + 3 days for a deferred host call or late
#     runner = 10, so one missed weekly run alarms.
SPECS = {
    "bls_jolts_cps": {"collector_days": 10, "datasets": {"jolts": 85, "cps": 50}},
    "oecd_unemployment": {"collector_days": 10, "datasets": {"monthly": 95}},
    "fred_labour": {"collector_days": 10, "datasets": {"monthly": 85, "weekly": 30}},
    "census_qwi": {"collector_days": 10, "datasets": {"quarterly": 430}},
}


def month_end(ym: str) -> date:
    y, m = int(ym[:4]), int(ym[5:7])
    return date(y, m, calendar.monthrange(y, m)[1])


def verdict(source: str, doc, today=None) -> tuple:
    """(ok, line) for one stored document."""
    today = today or datetime.now(timezone.utc).date()
    spec = SPECS[source]
    if not isinstance(doc, dict) or not doc.get("updated"):
        return False, f"{source} STALE: nothing stored at /reference/{source}"
    problems, parts = [], []
    try:
        upd = datetime.fromisoformat(str(doc["updated"]).replace("Z", "+00:00")).date()
        age = (today - upd).days
        parts.append(f"collected {age}d ago")
        if age > spec["collector_days"]:
            problems.append(f"collector last stored {age}d ago (limit {spec['collector_days']}d)")
    except ValueError:
        problems.append("unparseable `updated`")
    latest = doc.get("latest") or {}
    for ds, limit in spec["datasets"].items():
        ym = latest.get(ds)
        if not ym:
            problems.append(f"{ds}: no data")
            continue
        age = (today - month_end(ym)).days
        parts.append(f"{ds} {ym} ({age}d)")
        if age > limit:
            problems.append(f"{ds} newest month {ym} is {age}d past month end (limit {limit}d)")
    if problems:
        return False, f"{source} STALE: " + "; ".join(problems)
    return True, f"{source} fresh: " + ", ".join(parts)


def _fetch(source):
    url = f"{BASE}/wp-json/layoffs/v1/reference/{source}?cb={uuid.uuid4()}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.load(resp)


def main(argv=None):
    code = 0
    for source in SPECS:
        try:
            doc = _fetch(source)
        except Exception as exc:
            print(f"::warning title=reference-freshness::{source} UNKNOWN: could not read ({exc})")
            code = max(code, 3) if code != 1 else 1
            continue
        ok, line = verdict(source, doc)
        print(f"::{'notice' if ok else 'error'} title=reference-freshness::{line}")
        if not ok:
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
