"""Fetch OECD monthly unemployment by sex and age and store it in WordPress.

One keyless SDMX request (sources/oecd_unemployment.py) for the trailing
WINDOW_MONTHS, POSTed to /reference-ingest/oecd_unemployment and served at
/reference/oecd_unemployment. Same shape as bls_import.py and claims_import.py:
LABELED MACRO CONTEXT, never summed into layoff counts, and fail-soft: a failed
or empty pull never overwrites the stored document. CC BY 4.0, the attribution
travels inside the payload.

Prints one `::notice title=oecd-import::` line with the row count.
Env: WP_SITE_URL, WP_API_KEY. No LLM, no cost.

SAFE TO DEFER: the payload is rebuilt in full on every run and the endpoint
replaces the stored document wholesale.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import oecd_unemployment as oecd

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "oecd-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")

#: A pull with fewer countries than this is partial; do not store it. The
#: dataflow carries ~38 members plus aggregates.
MIN_COUNTRIES = 25


def should_store(payload) -> tuple:
    if not payload.get("rows"):
        return False, "no rows parsed"
    if len(payload.get("countries") or ()) < MIN_COUNTRIES:
        return False, f"only {len(payload.get('countries') or ())} countries (min {MIN_COUNTRIES})"
    return True, ""


def main():
    if not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    try:
        rows = oecd.parse_csv(oecd.fetch_csv(oecd.window_start()))
    except Exception as exc:
        print(f"::error title=oecd-import::OECD request failed ({exc}); stored data left intact")
        return 1
    payload = oecd.build_payload(rows)
    ok, why = should_store(payload)
    if not ok:
        print(f"::error title=oecd-import::{why}; stored data left intact")
        return 1
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{oecd.SOURCE}",
                                     payload, headers={"X-Layoff-API-Key": KEY, **UA},
                                     timeout=90)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    print(f"::notice title=oecd-import::rows={payload['rows']} countries={len(payload['countries'])} "
          f"latest={payload['latest']} stored={str(result)[:200]}")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
