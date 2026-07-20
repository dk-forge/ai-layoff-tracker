"""Bounded daily reason-tag backfill for rows with no recorded reason.

Most announced-tier rows (Eurofound ERM imports and older news rows) carry no
`reason_tags`, so the Reasons chart/filter under-represents them. This worker
tags them from the FIXED vocabulary only, using each row's STORED
excerpt/evidence — it never re-fetches a source page and never touches counts,
dates, stages, sources or AI labels.

Two evidence paths:
- ERM rows carry our own generated template excerpt whose lead is Eurofound's
  recorded "Restructuring type" field. The three types with an honest
  vocabulary equivalent map deterministically (Internal restructuring ->
  restructuring, Merger/acquisition -> merger_acquisition,
  Offshoring/delocalisation -> offshoring). The rest (Closure, Bankruptcy,
  Outsourcing, Relocation, ...) name no vocabulary reason and stay untagged —
  no model call is spent re-reading our own template.
  Set REASON_BACKFILL_LLM_ONLY=1 to force every row through the model instead.
- Freeform excerpts (news/8K/press_release) go to DeepSeek with a strict-JSON
  prompt; ai_automation additionally requires the employer's exact quote in
  the excerpt (validated locally), and an excerpt naming no reason is a
  definitive skip that leaves the row untagged.

Writes go through the corrections /edit endpoint, which validates the
vocabulary server-side, pins each row (edited=1) so the daily ERM re-import
cannot revert the tags, and re-hashes + suppresses the original dedup hash.
That trade-off is accepted for news/ERM rows; WARN rows are excluded entirely
(the `sources` filter matches source_type, so source_type=warn can never be
selected) because WARN notices state no reasons.

Env: WP_SITE_URL, WP_API_KEY; OPENROUTER_API_KEY for the model path.
Optional: REASON_BACKFILL_BATCH (model rows/run, default 40),
REASON_BACKFILL_DETERMINISTIC_CAP (template rows/run, default 400),
REASON_BACKFILL_DEADLINE_SECONDS (default 900, stops safely between rows),
REASON_BACKFILL_DRY_RUN=1 (classify + print, no writes, no health reports),
REASON_BACKFILL_LLM_ONLY=1 (disable the deterministic ERM template path).

The daily slice over model rows rotates deterministically by date (the
enrich_context pattern), so rows the model honestly leaves untagged cannot
permanently stall the head of the queue.
"""
import os
import re
import sys
import time
from datetime import date

import requests

from extractor import classify_reason_tags
from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(200, int(os.environ.get("REASON_BACKFILL_BATCH", "40"))))
DETERMINISTIC_CAP = max(0, min(1000, int(os.environ.get("REASON_BACKFILL_DETERMINISTIC_CAP", "400"))))
DEADLINE_SECONDS = max(60, min(1800, int(os.environ.get("REASON_BACKFILL_DEADLINE_SECONDS", "900"))))
DRY_RUN = os.environ.get("REASON_BACKFILL_DRY_RUN", "").lower() in {"1", "true", "yes"}
LLM_ONLY = os.environ.get("REASON_BACKFILL_LLM_ONLY", "").lower() in {"1", "true", "yes"}

# `sources` matches verification tiers OR source_type values; these four are
# source_type-only, so WARN rows are excluded structurally, not by trust.
NON_WARN_SOURCES = "news,8K,press_release,erm"
PAGE_SIZE = 200
MAX_PAGES = 200  # hard bound on the scan (200 * 200 = 40K rows)
EDIT_BATCH = 40
EDIT_REASON = (
    "Reason-tag backfill: fixed-vocabulary tags classified only from the row's "
    "stored excerpt (ERM rows: Eurofound's own recorded restructuring type)"
)

# Eurofound's recorded restructuring types with an honest fixed-vocabulary
# equivalent, keyed lowercase (the live CSV mixes casings: "Internal
# restructuring" but "Merger/Acquisition"). Absent types (Closure, Bankruptcy,
# Outsourcing, Relocation, Business expansion, Other) name no vocabulary
# reason: tagging them would be inference, so they deterministically stay
# untagged.
ERM_TYPE_TAGS = {
    "internal restructuring": ["restructuring"],
    "merger/acquisition": ["merger_acquisition"],
    "offshoring/delocalisation": ["offshoring"],
}
# Anchored on the full erm_import excerpt template (type, jobs sentence AND the
# Eurofound attribution tail) so a freeform news excerpt can never match.
ERM_TEMPLATE = re.compile(
    r"^\s*(?P<rtype>[A-Za-z /-]+?) at .+?: [\d,]+ announced job losses\. "
    r"Recorded by the European Restructuring Monitor \(Eurofound\), factsheet \d+\."
)


def erm_template_tags(row):
    """(matched, tags) for our own ERM excerpt template; tags may be empty."""
    if row.get("source_type") != "erm":
        return False, []
    match = ERM_TEMPLATE.match(row.get("excerpt") or "")
    if not match:
        return False, []
    return True, list(ERM_TYPE_TAGS.get(match.group("rtype").strip().lower(), []))


def fetch_candidates():
    """Page through non-WARN rows; keep untagged rows that carry evidence."""
    candidates = []
    page = 1
    while page <= MAX_PAGES:
        params = {"sources": NON_WARN_SOURCES, "sort": "id", "dir": "asc",
                  "per_page": PAGE_SIZE, "page": page}
        response = requests.get(f"{SITE}/wp-json/layoffs/v1/query", params=params, headers=UA, timeout=60)
        # WP returns 404 for a page past the last row; between our sequential
        # page requests the candidate set shrinks (rows get tagged), so the
        # final page can 404 even though the scan succeeded. End-of-data, not a
        # failure. A 404 on page 1 is a real endpoint problem and still raises.
        if response.status_code == 404 and page > 1:
            break
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", [])
        for row in rows:
            if row.get("source_type") == "warn":  # belt to the sources= filter
                continue
            if row.get("reason_tags"):
                continue
            if len((row.get("excerpt") or "").strip()) < 40:
                continue
            candidates.append(row)
        if len(rows) < PAGE_SIZE or page * PAGE_SIZE >= payload.get("total", 0):
            break
        page += 1
    return candidates


def rotating_slice(rows, batch, day_ordinal):
    """Deterministic daily slice so no-reason rows cannot stall the queue."""
    if not rows or batch <= 0:
        return []
    pages = (len(rows) + batch - 1) // batch
    start = (day_ordinal % pages) * batch
    return rows[start:start + batch]


def post_edits(items):
    """POST /edit in bounded batches; any HTTP failure raises (fail loudly)."""
    edited, not_found = [], []
    for start in range(0, len(items), EDIT_BATCH):
        chunk = items[start:start + EDIT_BATCH]
        response = requests.post(
            f"{SITE}/wp-json/layoffs/v1/edit",
            json={"reason": EDIT_REASON,
                  "edits": [{"id": i["id"], "fields": {"reason_tags": i["reason_tags"]}} for i in chunk]},
            headers={**UA, "X-Layoff-API-Key": KEY},
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        edited.extend(result.get("edited", []))
        not_found.extend(result.get("not_found", []))
        if result.get("rejected"):
            # /edit rejects an item only when no writable field survives —
            # with our single validated field that means vocabulary drift
            # between this worker and the plugin. Never paper over it.
            raise RuntimeError(f"/edit rejected ids {result['rejected']}: reason-tag vocabulary drift?")
    return edited, not_found


def run():
    candidates = fetch_candidates()
    deterministic, model_rows = [], []
    for row in candidates:
        matched, tags = (False, []) if LLM_ONLY else erm_template_tags(row)
        if matched:
            if tags:
                deterministic.append({"id": int(row["id"]), "reason_tags": tags})
            # A recognized template with no vocabulary equivalent stays
            # untagged at zero cost — it is re-derived, never re-modeled.
        else:
            model_rows.append(row)

    deterministic_backlog = len(deterministic)
    deterministic = deterministic[:DETERMINISTIC_CAP]

    items = list(deterministic)
    model_skips, model_failures, checked = 0, 0, 0
    queue = rotating_slice(model_rows, BATCH, date.today().toordinal())
    started_at = time.monotonic()
    for row in queue:
        # Nothing is half-written per row, so stopping between rows is safe;
        # the next daily run resumes the rotation.
        if time.monotonic() - started_at >= DEADLINE_SECONDS:
            print(f"Reached REASON_BACKFILL_DEADLINE_SECONDS={DEADLINE_SECONDS}; "
                  f"stopping safely after {checked} model row(s)")
            break
        checked += 1
        result = classify_reason_tags(row.get("excerpt") or "")
        if result is None:
            model_failures += 1
            print(f"  model id={row['id']}: FAILED (retried on a later rotation)")
            continue
        if result["reason_tags"]:
            items.append({"id": int(row["id"]), "reason_tags": result["reason_tags"]})
            print(f"  model id={row['id']}: {','.join(result['reason_tags'])}")
        else:
            model_skips += 1  # evidence names no reason — honestly left empty
            print(f"  model id={row['id']}: evidence names no reason — left untagged")
        time.sleep(0.25)

    print(f"candidates={len(candidates)} template_taggable={deterministic_backlog} "
          f"model_queue={len(model_rows)} model_checked={checked} "
          f"model_skips={model_skips} model_failures={model_failures} writes_queued={len(items)}")

    if DRY_RUN:
        for item in items:
            print(f"  would tag id={item['id']}: {','.join(item['reason_tags'])}")
        print("DRY RUN: no writes performed.")
        return {"tagged": 0, "checked": checked, "model_failures": model_failures}

    edited, not_found = ([], [])
    if items:
        edited, not_found = post_edits(items)
        print(f"edited={len(edited)} not_found={len(not_found)}")
        if not_found:
            # A vanished id means the row set changed mid-run (dedupe/purge);
            # visible, but the other applied edits remain valid.
            print(f"WARNING: ids not found: {not_found}")

    # A fully failed attempted model pass must be visible in Actions rather
    # than reading as a quiet no-op day (reclassify worker rule).
    if checked and model_failures == checked and not items:
        raise RuntimeError(f"All {checked} attempted model classifications failed")

    det_ids = {item["id"] for item in deterministic}
    det_edited = sum(1 for row_id in edited if row_id in det_ids)
    pending = (deterministic_backlog - det_edited) + (len(model_rows) - (len(edited) - det_edited))
    detail = (f"{len(edited)} tagged ({det_edited} from ERM recorded type, "
              f"{len(edited) - det_edited} model-classified); {model_skips} evidence-names-no-reason "
              f"skips; {model_failures} model failures; ~{max(0, pending)} untagged rows pending")
    if not report_source_health("reason_backfill", "ok", len(edited), detail):
        raise RuntimeError("Could not publish reason_backfill completion health status")
    return {"tagged": len(edited), "checked": checked, "model_failures": model_failures}


def main():
    if not SITE or (not KEY and not DRY_RUN):
        print("WP_SITE_URL and WP_API_KEY are required (or set REASON_BACKFILL_DRY_RUN=1)")
        return 1
    if not DRY_RUN:
        if not report_source_health("reason_backfill", "running", 0,
                                    "bounded stored-excerpt reason-tag backfill in progress"):
            raise RuntimeError("Could not publish reason_backfill running health status")
    try:
        run()
        return 0
    except Exception as exc:
        # A failed backfill attempt is a material condition, not a quiet
        # retry: record it in the public health ledger, then exit non-zero.
        if not DRY_RUN:
            report_source_health("reason_backfill", "degraded", 0, f"reason backfill failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
