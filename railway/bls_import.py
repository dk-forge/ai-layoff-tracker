"""Fetch BLS JOLTS + CPS reference data and store it in WordPress.

Runs the keyless BLS v1 puller (sources/bls_jolts_cps.py; 3 API requests of a
25/day keyless budget) and POSTs the payload to /reference-ingest/bls_jolts_cps,
which keeps it in one option for the public GET /reference/bls_jolts_cps. Same
shape as claims_import.py: LABELED MACRO CONTEXT, never summed into or
compared one-to-one with the tracker's layoff rows, and fail-soft: a failed or
empty pull never overwrites the stored document.

Prints one `::notice title=bls-import::` line with the row count, so a run's
result is readable from check-run annotations without log access.

Env: WP_SITE_URL, WP_API_KEY. No LLM, no cost.

SAFE TO DEFER: the payload is rebuilt in full from BLS on every run and the
endpoint replaces the stored document wholesale.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import bls_jolts_cps as bls

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "bls-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")


def should_store(payload) -> tuple:
    """(ok, why). Never overwrite good data with a partial or empty pull."""
    if payload.get("failed_requests"):
        return False, f"{payload['failed_requests']} BLS request(s) failed"
    if not payload.get("rows"):
        return False, "no rows parsed"
    if not (payload["latest"].get("jolts") and payload["latest"].get("cps")):
        return False, "a dataset came back empty"
    return True, ""


def main():
    if not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    payload = bls.fetch()
    ok, why = should_store(payload)
    if not ok:
        print(f"::error title=bls-import::{why}; stored data left intact; "
              f"errors={payload.get('errors')[:5]}")
        return 1
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{bls.SOURCE}",
                                     payload, headers={"X-Layoff-API-Key": KEY, **UA},
                                     timeout=90)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    print(f"::notice title=bls-import::rows={payload['rows']} series={payload['series_count']} "
          f"latest={payload['latest']} requests={payload['requests']} "
          f"missing={payload['missing_series']} stored={str(result)[:200]}")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
