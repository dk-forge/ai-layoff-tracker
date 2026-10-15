"""Fetch BLS CES average weekly hours + hourly earnings and store them in WordPress.

Keyless BLS API v1 (sources/bls_ces_hours.py; 2 requests of the 25/day keyless
budget), national, per supersector, monthly, POSTed to
/reference-ingest/bls_ces_hours and served at /reference/bls_ces_hours.
Same shape as bls_import.py: LABELED MACRO CONTEXT, never summed into layoff
counts, and fail-soft: a failed or partial pull never overwrites stored data.

`--dry-run` fetches and prints the diagnostic without posting (no WP env needed).

Env: WP_SITE_URL, WP_API_KEY. No LLM, no cost.

SAFE TO DEFER: the payload is rebuilt in full on every run and the endpoint
replaces the stored document wholesale.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import bls_ces_hours as ces

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "ces-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
MAX_BYTES = 2_800_000


def should_store(payload) -> tuple:
    """(ok, why). Never overwrite good data with a partial or empty pull."""
    if payload.get("failed_requests"):
        return False, f"{payload['failed_requests']} BLS request(s) failed"
    if not payload.get("rows"):
        return False, "no rows parsed"
    if payload.get("missing_series"):
        return False, f"{len(payload['missing_series'])} series missing"
    size = len(json.dumps(payload))
    if size > MAX_BYTES:
        return False, f"payload {size} B over {MAX_BYTES} B"
    return True, ""


def main(argv=None):
    dry = "--dry-run" in (argv if argv is not None else sys.argv[1:])
    if not dry and not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    payload = ces.fetch()
    ok, why = should_store(payload)
    if dry:
        print(f"dry-run: ok={ok} {why} rows={payload['rows']} series={payload['series_count']} "
              f"latest={payload['latest']} requests={payload['requests']} "
              f"missing={payload['missing_series']} errors={payload['errors'][:5]}")
        return 0 if ok else 1
    if not ok:
        print(f"::error title=ces-import::{why}; stored data left intact; "
              f"errors={payload.get('errors')[:5]}")
        return 1
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{ces.SOURCE}",
                                     payload, headers={"X-Layoff-API-Key": KEY, **UA},
                                     timeout=90)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    print(f"::notice title=ces-import::rows={payload['rows']} series={payload['series_count']} "
          f"latest={payload['latest']} requests={payload['requests']} stored={str(result)[:200]}")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
