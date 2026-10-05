"""Fetch the curated FRED labour series and store them in WordPress.

One request per series (sources/fred_labour.py), trailing WINDOW_YEARS,
POSTed to /reference-ingest/fred_labour and served at /reference/fred_labour.
Same shape as bls_import.py and oecd_import.py: LABELED MACRO CONTEXT, never
summed into layoff counts, and fail-soft: a failed or partial pull never
overwrites the stored document.

Prints one `::notice title=fred-import::` line with the row count.
Env: WP_SITE_URL, WP_API_KEY, FRED_API_KEY (never printed). No LLM, no cost.

SAFE TO DEFER: the payload is rebuilt in full on every run and the endpoint
replaces the stored document wholesale.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import fred_labour as fred

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "fred-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()

#: The reference endpoint's ceiling (ALT_REFERENCE_MAX_BYTES), with headroom.
MAX_BYTES = 2_800_000


def should_store(payload) -> tuple:
    if not payload.get("rows"):
        return False, "no rows parsed" + (f" ({payload['errors'][0]})" if payload.get("errors") else "")
    missing = sorted(set(fred.SERIES) - set(payload.get("series_present") or ()))
    if missing:
        return False, f"series missing: {', '.join(missing)}"
    size = len(json.dumps(payload))
    if size > MAX_BYTES:
        return False, f"payload {size} B over {MAX_BYTES} B"
    return True, ""


def main():
    if not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    if not FRED_KEY:
        print("::error title=fred-import::FRED_API_KEY secret is missing or empty; stored data left intact")
        return 1
    payload = fred.pull(FRED_KEY, fred.window_start())
    ok, why = should_store(payload)
    if not ok:
        detail = "; ".join(payload.get("errors") or [])[:600]
        print(f"::error title=fred-import::{fred.scrub(why, FRED_KEY)}; stored data left intact. "
              f"{fred.scrub(detail, FRED_KEY)}")
        return 1
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{fred.SOURCE}",
                                     payload, headers={"X-Layoff-API-Key": KEY, **UA},
                                     timeout=90)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    print(f"::notice title=fred-import::rows={payload['rows']} series={len(payload['series_present'])} "
          f"latest={payload['latest']} stored={str(result)[:200]}")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
