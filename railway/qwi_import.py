"""Fetch Census QWI hires/separations by state and store them in WordPress.

Six requests (sources/census_qwi.py: by sector, age, sex, education, race,
ethnicity), latest KEEP_QUARTERS quarters, POSTed to
/reference-ingest/census_qwi and served at /reference/census_qwi. Same shape
as bls_import.py and oecd_import.py: LABELED MACRO CONTEXT, never summed into
layoff counts, and fail-soft: a failed or partial pull never overwrites the
stored document.

Prints one `::notice title=qwi-import::` line with the row count.
Env: WP_SITE_URL, WP_API_KEY, CENSUS_API_KEY (never printed). No LLM, no cost.

SAFE TO DEFER: the payload is rebuilt in full on every run and the endpoint
replaces the stored document wholesale.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import census_qwi as qwi

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "qwi-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
CENSUS_KEY = os.environ.get("CENSUS_API_KEY", "").strip()

#: 50 states + DC; a few may be suppressed in a quarter, not this many.
MIN_STATES = 45
MAX_BYTES = 2_800_000


def should_store(payload) -> tuple:
    if not payload.get("rows"):
        return False, "no rows parsed"
    missing = sorted(set(qwi.QUERIES) - {k for k, v in (payload.get("datasets") or {}).items() if v})
    if missing:
        return False, f"breakdowns missing: {', '.join(missing)}"
    if len(payload.get("states") or ()) < MIN_STATES:
        return False, f"only {len(payload.get('states') or ())} states (min {MIN_STATES})"
    size = len(json.dumps(payload))
    if size > MAX_BYTES:
        return False, f"payload {size} B over {MAX_BYTES} B"
    return True, ""


def main():
    if not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    if not CENSUS_KEY:
        print("::error title=qwi-import::CENSUS_API_KEY secret is missing or empty; stored data left intact")
        return 1
    payload = qwi.pull(CENSUS_KEY)
    ok, why = should_store(payload)
    if not ok:
        detail = "; ".join(payload.get("errors") or [])[:800]
        print(f"::error title=qwi-import::{why}; stored data left intact. {qwi.scrub(detail, CENSUS_KEY)}")
        return 1
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{qwi.SOURCE}",
                                     payload, headers={"X-Layoff-API-Key": KEY, **UA},
                                     timeout=120)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    print(f"::notice title=qwi-import::rows={payload['rows']} states={len(payload['states'])} "
          f"quarters={payload['quarters'][0]}..{payload['quarters'][-1]} "
          f"bytes={len(json.dumps(payload))} stored={str(result)[:200]}")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
