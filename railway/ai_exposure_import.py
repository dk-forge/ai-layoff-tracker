"""Fetch AI exposure by occupation and metro and store it in WordPress.

sources/ai_exposure.py joins the "GPTs are GPTs" exposure scores (MIT), O*NET
titles (CC BY 4.0), BLS OEWS employment and wages, and BLS Employment
Projections on the SOC code, then this POSTs one document to
/reference-ingest/ai_exposure, served at /reference/ai_exposure. Same shape
as qwi_import.py: LABELLED CONTEXT, never summed into layoff counts, and
fail-soft: a failed or partial pull never overwrites the stored document.

Prints one `::notice title=ai-exposure-import::` line ending `site=stored`.
Env: WP_SITE_URL, WP_API_KEY. No key for any source, no LLM, no cost.

SAFE TO DEFER: the payload is rebuilt in full on every run and the endpoint
replaces the stored document wholesale.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_call
from sources import ai_exposure as ax

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "ai-exposure-import"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")

#: Floors from the first real pull: ~800 scored codes, ~830 OEWS detailed
#: occupations, ~830 projection line items, ~390 metros. Well under these
#: means a source changed shape, not that the world changed.
MIN_OCCUPATIONS = 500
MIN_METROS = 40
MIN_WITH_GROWTH = 400
MAX_BYTES = 1_000_000


def should_store(pull) -> tuple:
    if pull.get("errors"):
        return False, "source errors: " + "; ".join(pull["errors"])[:600]
    p = pull["payload"]
    occ = p["datasets"]["occupations"]
    if len(occ) < MIN_OCCUPATIONS:
        return False, f"only {len(occ)} occupations joined (min {MIN_OCCUPATIONS})"
    with_growth = sum(1 for r in occ if r[5] is not None)
    if with_growth < MIN_WITH_GROWTH:
        return False, f"only {with_growth} occupations with projections (min {MIN_WITH_GROWTH})"
    if len(p["datasets"]["metros"]) < MIN_METROS:
        return False, f"only {len(p['datasets']['metros'])} metros (min {MIN_METROS})"
    if not all(k in p["latest"] for k in ("oews", "ep")):
        return False, "release dates missing"
    size = len(json.dumps(p))
    if size > MAX_BYTES:
        return False, f"payload {size} B over {MAX_BYTES} B"
    return True, ""


def main():
    if not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    pull = ax.pull()
    ok, why = should_store(pull)
    if not ok:
        print(f"::error title=ai-exposure-import::{why}; stored data left intact. counts={pull.get('counts')}")
        return 1
    p = pull["payload"]
    try:
        result = host_call.post_json(f"{SITE}/wp-json/layoffs/v1/reference-ingest/{ax.SOURCE}",
                                     p, headers={"X-Layoff-API-Key": KEY, **UA}, timeout=120)
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    stored = isinstance(result, dict) and result.get("stored") is True
    print(f"::notice title=ai-exposure-import::occupations={len(p['datasets']['occupations'])} "
          f"metros={len(p['datasets']['metros'])} oews={p['versions']['oews']} ep={p['versions']['ep']} "
          f"onet={p['versions']['onet']} bytes={len(json.dumps(p))} "
          f"site={'stored' if stored else 'NOT-STORED ' + str(result)[:200]}")
    if not stored:
        return 1
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
