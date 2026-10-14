"""Fetch the Indeed Hiring Lab job postings index and store it in WordPress.

Keyless (public GitHub CSVs, CC BY 4.0). Weekly series per sector plus the
national aggregate (sources/indeed_postings.py), POSTed to
/reference-ingest/indeed_postings and served at /reference/indeed_postings.
Same shape as fred_import.py: LABELED MACRO CONTEXT, never summed into layoff
counts, and fail-soft: a failed or partial pull never overwrites stored data.

Env: WP_SITE_URL, WP_API_KEY. No LLM, no cost.

SAFE TO DEFER: the payload is rebuilt in full on every run and the endpoint
replaces the stored document wholesale.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import indeed_postings as ind

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "indeed-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")

#: The reference endpoint's ceiling (ALT_REFERENCE_MAX_BYTES), with headroom.
MAX_BYTES = 2_800_000
#: Fewer sectors than this means the upstream file changed shape.
MIN_SECTORS = 20


def should_store(payload) -> tuple:
    if not payload.get("rows"):
        return False, "no rows parsed"
    sectors = payload.get("sectors") or []
    if ind.ALL_SECTORS not in sectors:
        return False, "aggregate series missing"
    if len(sectors) - 1 < MIN_SECTORS and len(sectors) > 3:
        return False, f"only {len(sectors) - 1} sectors parsed (expected {MIN_SECTORS}+)"
    size = len(json.dumps(payload))
    if size > MAX_BYTES:
        return False, f"payload {size} B over {MAX_BYTES} B"
    return True, ""


def main():
    if not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    payload = ind.pull()
    ok, why = should_store(payload)
    if not ok:
        print(f"::error title=indeed-import::{why}; stored data left intact. "
              f"{'; '.join(payload.get('errors') or [])[:600]}")
        return 1
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{ind.SOURCE}",
                                     payload, headers={"X-Layoff-API-Key": KEY, **UA},
                                     timeout=90)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    print(f"::notice title=indeed-import::rows={payload['rows']} sectors={len(payload['sectors'])} "
          f"latest={payload['latest']} stored={str(result)[:200]}")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
