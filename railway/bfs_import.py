"""Fetch Census Business Formation Statistics and store them in WordPress.

Keyless (one public Census CSV, public domain). Monthly seasonally adjusted
business applications, national and by state (sources/census_bfs.py), POSTed
to /reference-ingest/census_bfs and served at /reference/census_bfs. Same
shape as indeed_import.py: LABELED MACRO CONTEXT, never summed into layoff
counts, and fail-soft: a failed or partial pull never overwrites stored data.

Env: WP_SITE_URL, WP_API_KEY. No LLM, no cost.
`--dry-run` pulls and prints the diagnostic without touching WordPress.

SAFE TO DEFER: the payload is rebuilt in full on every run and the endpoint
replaces the stored document wholesale.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import census_bfs as bfs

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "bfs-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")

#: The reference endpoint's ceiling (ALT_REFERENCE_MAX_BYTES), with headroom.
MAX_BYTES = 2_800_000
#: Fewer geographies than this (US + 50 states + DC) means the file changed shape.
MIN_GEOS = 52


def should_store(payload) -> tuple:
    if not payload.get("rows"):
        return False, "no rows parsed"
    if bfs.NATIONAL not in (payload.get("geos") or []):
        return False, "national series missing"
    if set(payload.get("series") or []) != set(bfs.SERIES):
        return False, f"series {payload.get('series')} (expected {list(bfs.SERIES)})"
    n = len(payload.get("geos") or [])
    if n < MIN_GEOS:
        return False, f"only {n} geographies parsed (expected {MIN_GEOS}+)"
    size = len(json.dumps(payload))
    if size > MAX_BYTES:
        return False, f"payload {size} B over {MAX_BYTES} B"
    return True, ""


def main(argv=None):
    dry = "--dry-run" in (argv if argv is not None else sys.argv[1:])
    if not dry and not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    payload = bfs.pull()
    ok, why = should_store(payload)
    if dry:
        print(f"dry-run: rows={payload['rows']} geos={len(payload['geos'])} "
              f"latest={payload['latest']} store={'yes' if ok else 'no: ' + why} "
              f"errors={payload['errors']}")
        return 0 if ok else 1
    if not ok:
        print(f"::error title=bfs-import::{why}; stored data left intact. "
              f"{'; '.join(payload.get('errors') or [])[:600]}")
        return 1
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{bfs.SOURCE}",
                                     payload, headers={"X-Layoff-API-Key": KEY, **UA},
                                     timeout=90)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    print(f"::notice title=bfs-import::rows={payload['rows']} geos={len(payload['geos'])} "
          f"latest={payload['latest']} stored={str(result)[:200]}")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
