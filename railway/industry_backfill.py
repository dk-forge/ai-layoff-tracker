"""Bounded daily industry-classification backfill for blank-industry rows.

A large share of rows carry no `industry` — every structured WARN notice does,
plus older news/8K rows whose extraction never resolved a sector — so the
industry filter dropdown and the "by industry" aggregates under-represent them.
This worker classifies those rows into the FIXED industry vocabulary using ONLY
each row's own company name + STORED excerpt — it never re-fetches a source
page and never touches counts, dates, stages, sources or AI labels.

Safety model (matches the /industry-backfill endpoint's guarantees):
- Blank-only: the endpoint fills a row ONLY while its industry is still '',
  and `alt_db_upsert` no longer blanks a set industry, so the daily WARN
  re-import cannot erase a fill. Rows are NOT pinned — a purge-reload simply
  returns the row to the visible backlog, so this is honest enrichment, not a
  permanent override.
- Closed vocabulary: the model must answer with exactly one label from
  `extractor.INDUSTRY_VOCABULARY` or "unknown"; anything else collapses to a
  skip. The endpoint re-validates against `alt_industry_vocabulary()` and
  rejects any label outside it (a rejection here is treated as vocabulary
  drift and fails loudly).
- Double-confirmed: each row is classified by TWO independent model passes and
  written only when both agree on the same non-empty label. A disagreement or
  an "unknown" from either pass leaves the row untouched in the backlog. This
  is the "double-confirmed by two model passes" the endpoint records in its
  corrections trail.

Env: WP_SITE_URL, WP_API_KEY; OPENROUTER_API_KEY for the model path.
Optional: INDUSTRY_BACKFILL_BATCH (rows/run, default 40),
INDUSTRY_BACKFILL_DEADLINE_SECONDS (default 900, stops safely between rows),
INDUSTRY_BACKFILL_DRY_RUN=1 (classify + print, no writes, no health reports),
INDUSTRY_BACKFILL_SINGLE_PASS=1 (disable the second confirmation pass — for
manual spot checks only; the scheduled job always double-confirms).

The daily slice over the queue rotates deterministically by date (the
reason_backfill / enrich_context pattern), so rows the model honestly leaves
"unknown" cannot permanently stall the head of the queue.
"""
import os
import sys
import time
from datetime import date

import requests

from extractor import classify_industry, INDUSTRY_VOCABULARY
from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(200, int(os.environ.get("INDUSTRY_BACKFILL_BATCH", "40"))))
DEADLINE_SECONDS = max(60, min(1800, int(os.environ.get("INDUSTRY_BACKFILL_DEADLINE_SECONDS", "900"))))
DRY_RUN = os.environ.get("INDUSTRY_BACKFILL_DRY_RUN", "").lower() in {"1", "true", "yes"}
SINGLE_PASS = os.environ.get("INDUSTRY_BACKFILL_SINGLE_PASS", "").lower() in {"1", "true", "yes"}

PAGE_SIZE = 200
MAX_PAGES = 300  # hard bound on the scan (300 * 200 = 60K rows)
WRITE_BATCH = 200  # the endpoint accepts up to 2000 items; stay well under


def fetch_candidates():
    """Page through blank-industry rows that carry something to classify.

    A row with neither a company name nor an excerpt has no evidence to read,
    so it never enters the queue (it would only ever resolve to a skip)."""
    candidates = []
    page = 1
    while page <= MAX_PAGES:
        params = {"industry_missing": "1", "sort": "id", "dir": "asc",
                  "per_page": PAGE_SIZE, "page": page}
        response = requests.get(f"{SITE}/wp-json/layoffs/v1/query", params=params, headers=UA, timeout=60)
        # WP returns 404 for a page past the last row. Between our sequential
        # page requests the candidate set shrinks (rows get filled) or `total`
        # is under-reported, so the final page can 404 even though the scan
        # succeeded. That is end-of-data, not a failure — stop with what we
        # have. A 404 on page 1 is a real endpoint problem and still raises.
        if response.status_code == 404 and page > 1:
            break
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", [])
        for row in rows:
            if (row.get("industry") or "").strip():  # belt to the industry_missing filter
                continue
            company = (row.get("company_name") or "").strip()
            excerpt = (row.get("excerpt") or "").strip()
            if not company and not excerpt:
                continue
            candidates.append(row)
        if len(rows) < PAGE_SIZE or page * PAGE_SIZE >= payload.get("total", 0):
            break
        page += 1
    return candidates


def rotating_slice(rows, batch, day_ordinal):
    """Deterministic daily slice so skipped ("unknown") rows cannot stall the queue."""
    if not rows or batch <= 0:
        return []
    pages = (len(rows) + batch - 1) // batch
    start = (day_ordinal % pages) * batch
    return rows[start:start + batch]


def classify_confirmed(company, excerpt):
    """Two-pass agreement gate.

    Returns (label, status) where status is one of:
    - 'confirmed'  -> both passes returned the SAME non-empty vocabulary label
    - 'unconfirmed'-> passes disagreed, or one/both said "unknown"/empty (skip)
    - 'failed'     -> a model/transport error (retry on a later rotation)
    """
    first = classify_industry(company, excerpt)
    if first is None:
        return "", "failed"
    label = first.get("industry", "")
    if not label:
        return "", "unconfirmed"
    if SINGLE_PASS:
        return label, "confirmed"
    second = classify_industry(company, excerpt)
    if second is None:
        return "", "failed"
    if second.get("industry", "") == label:
        return label, "confirmed"
    return "", "unconfirmed"


def post_fills(items):
    """POST /industry-backfill in bounded batches; any HTTP failure raises.

    A `rejected` id means the endpoint refused a label its own
    `alt_industry_vocabulary()` does not contain — i.e. the worker's
    INDUSTRY_VOCABULARY has drifted from the PHP map. That is never papered
    over; it fails loudly (the parity test exists to prevent it landing)."""
    filled, skipped, not_found = [], [], []
    for start in range(0, len(items), WRITE_BATCH):
        chunk = items[start:start + WRITE_BATCH]
        response = requests.post(
            f"{SITE}/wp-json/layoffs/v1/industry-backfill",
            json={"items": [{"id": i["id"], "industry": i["industry"]} for i in chunk]},
            headers={**UA, "X-Layoff-API-Key": KEY},
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        filled.extend(result.get("filled", []))
        skipped.extend(result.get("skipped_not_blank", []))
        not_found.extend(result.get("not_found", []))
        if result.get("rejected"):
            raise RuntimeError(
                f"/industry-backfill rejected ids {result['rejected']}: "
                "industry vocabulary drift between the worker and the plugin?")
    return filled, skipped, not_found


def run():
    candidates = fetch_candidates()
    queue = rotating_slice(candidates, BATCH, date.today().toordinal())
    items, confirmed, unconfirmed, failures, checked = [], 0, 0, 0, 0
    started_at = time.monotonic()
    for row in queue:
        # Nothing is half-written per row, so stopping between rows is safe;
        # the next daily run resumes the rotation.
        if time.monotonic() - started_at >= DEADLINE_SECONDS:
            print(f"Reached INDUSTRY_BACKFILL_DEADLINE_SECONDS={DEADLINE_SECONDS}; "
                  f"stopping safely after {checked} row(s)")
            break
        checked += 1
        label, status = classify_confirmed(row.get("company_name") or "", row.get("excerpt") or "")
        if status == "failed":
            failures += 1
            print(f"  id={row['id']} ({row.get('company_name','')}): FAILED (retried on a later rotation)")
        elif status == "confirmed":
            confirmed += 1
            items.append({"id": int(row["id"]), "industry": label})
            print(f"  id={row['id']} ({row.get('company_name','')}): {label}")
        else:
            unconfirmed += 1
            print(f"  id={row['id']} ({row.get('company_name','')}): unconfirmed — left blank")
        time.sleep(0.2)

    print(f"blank_backlog={len(candidates)} queue={len(queue)} checked={checked} "
          f"confirmed={confirmed} unconfirmed={unconfirmed} failures={failures}")

    if DRY_RUN:
        for item in items:
            print(f"  would fill id={item['id']}: {item['industry']}")
        print("DRY RUN: no writes performed.")
        return {"filled": 0, "checked": checked, "failures": failures}

    filled, skipped, not_found = ([], [], [])
    remaining = None
    if items:
        filled, skipped, not_found = post_fills(items)
        print(f"filled={len(filled)} skipped_not_blank={len(skipped)} not_found={len(not_found)}")
        if not_found:
            # A vanished id means the row set changed mid-run (dedupe/purge);
            # visible, but the other applied fills remain valid.
            print(f"WARNING: ids not found: {not_found}")

    # A fully failed attempted pass must be visible in Actions rather than
    # reading as a quiet no-op day (reason_backfill / reclassify rule).
    if checked and failures == checked and not items:
        raise RuntimeError(f"All {checked} attempted industry classifications failed")

    pending = max(0, len(candidates) - len(filled))
    detail = (f"{len(filled)} industries filled (2-pass confirmed, fixed vocabulary, "
              f"blank fields only); {unconfirmed} left blank as unconfirmed/unknown; "
              f"{failures} model failures; ~{pending} blank-industry rows pending")
    if not report_source_health("industry_backfill", "ok", len(filled), detail):
        raise RuntimeError("Could not publish industry_backfill completion health status")
    return {"filled": len(filled), "checked": checked, "failures": failures}


def main():
    if not SITE or (not KEY and not DRY_RUN):
        print("WP_SITE_URL and WP_API_KEY are required (or set INDUSTRY_BACKFILL_DRY_RUN=1)")
        return 1
    if not INDUSTRY_VOCABULARY:
        print("INDUSTRY_VOCABULARY is empty — refusing to run")
        return 1
    if not DRY_RUN:
        if not report_source_health("industry_backfill", "running", 0,
                                    "bounded company+excerpt industry classification in progress"):
            raise RuntimeError("Could not publish industry_backfill running health status")
    try:
        run()
        return 0
    except Exception as exc:
        # A failed backfill attempt is a material condition, not a quiet retry:
        # record it in the public health ledger, then exit non-zero.
        if not DRY_RUN:
            report_source_health("industry_backfill", "degraded", 0, f"industry backfill failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
