"""Fetch Eurostat job vacancy + unemployment rates by country and store them in WordPress.

Keyless (Eurostat dissemination API, JSON-stat, CC BY 4.0 under the Eurostat
reuse policy). Built by sources/eurostat_labour.py, POSTed to
/reference-ingest/eurostat_labour and served at /reference/eurostat_labour.
Same shape as indeed_import.py: LABELED MACRO CONTEXT, never summed into layoff
counts, and fail-soft: a failed or partial pull never overwrites stored data.

Env: WP_SITE_URL, WP_API_KEY. No LLM, no cost.
`--dry-run` fetches and prints the diagnostic without posting (no keys needed).

SAFE TO DEFER: the payload is rebuilt in full on every run and the endpoint
replaces the stored document wholesale.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import eurostat_labour as eu

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "eurostat-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")

#: The reference endpoint's ceiling (ALT_REFERENCE_MAX_BYTES), with headroom.
MAX_BYTES = 2_800_000
#: Fewer countries than this in either dataset means the upstream changed shape.
MIN_GEOS = 20


def should_store(payload) -> tuple:
    if not payload.get("rows"):
        return False, "no rows parsed"
    for key in eu.QUERIES:
        geos = (payload.get("geos") or {}).get(key) or []
        if "EU27_2020" not in geos:
            return False, f"{key}: EU27 aggregate missing"
        if len(geos) < MIN_GEOS:
            return False, f"{key}: only {len(geos)} countries parsed (expected {MIN_GEOS}+)"
    size = len(json.dumps(payload))
    if size > MAX_BYTES:
        return False, f"payload {size} B over {MAX_BYTES} B"
    return True, ""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv
    if not dry and not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    payload = eu.pull()
    ok, why = should_store(payload)
    diag = (f"rows={payload['rows']} "
            f"geos={ {k: len(v) for k, v in payload['geos'].items()} } "
            f"latest={payload['latest']} bytes={len(json.dumps(payload))}")
    if dry:
        print(f"DRY RUN {'OK' if ok else 'REFUSED: ' + why} {diag} "
              f"errors={payload.get('errors')}")
        return 0 if ok else 1
    if not ok:
        print(f"::error title=eurostat-import::{why}; stored data left intact. "
              f"{'; '.join(payload.get('errors') or [])[:600]}")
        return 1
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{eu.SOURCE}",
                                     payload, headers={"X-Layoff-API-Key": KEY, **UA},
                                     timeout=90)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    print(f"::notice title=eurostat-import::{diag} stored={str(result)[:200]}")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
