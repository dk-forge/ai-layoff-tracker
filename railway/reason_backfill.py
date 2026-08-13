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
REASON_BACKFILL_DEADLINE_SECONDS (WHOLE-RUN budget, default 1260),
REASON_BACKFILL_WRITE_RESERVE_SECONDS (default 240, see below),
REASON_BACKFILL_DRY_RUN=1 (classify + print, no writes, no health reports),
REASON_BACKFILL_LLM_ONLY=1 (disable the deterministic ERM template path).

The daily slice over model rows rotates deterministically by date (the
enrich_context pattern), so rows the model honestly leaves untagged cannot
permanently stall the head of the queue.

THE RUN OWNS ITS OWN CLOCK (archive_backfill pattern). On 2026-08-11 run
31462430383 was killed by the workflow's timeout-minutes after five clean runs,
and a cancelled run's work is simply gone. The deadline used to cover only the
model loop -- the cheapest of the three phases. It is now a WHOLE-RUN budget
measured from process start and enforced in all three:

  1. the scan (fetch_candidates) checks it before each page,
  2. the model loop checks it before each row,
  3. post_edits checks it before starting each /edit chunk.

Phases 1 and 2 stop at DEADLINE - WRITE_RESERVE so there is always budget left
to write what was already decided. Nothing is half-written at any of those
points: an unwritten row is simply still untagged, and the next run finds it.
The deterministic (ERM) edits -- the bulk of a normal run's 400 writes -- are
flushed as soon as the scan produces them, BEFORE the model loop spends a
second, so a stall in the expensive phase can no longer discard the cheap one.
"""
import os
import re
import sys
import time
from datetime import date

import requests

import host_call
import http_retry
from extractor import classify_reason_tags, CreditsExhaustedError
import spend
from source_health import report_source_health, require_running_note

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
#: DEFERRABLE ONLY DURING THE SCAN. Once /edit has written a chunk the run did
#: real work, and the flush already knows how to leave the rest for tomorrow
#: (the write is idempotent and unwritten rows are re-found next run).
JOB = "reason-backfill"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(200, int(os.environ.get("REASON_BACKFILL_BATCH", "40"))))
DETERMINISTIC_CAP = max(0, min(1000, int(os.environ.get("REASON_BACKFILL_DETERMINISTIC_CAP", "400"))))
# MEASURED, 11 scheduled runs 2026-07-31..2026-08-10 (the "Tag stored-evidence
# reasons" step): median 331s, max 419s. The scan alone is 21,358 non-WARN rows
# / 200 per page = 107 pages at a measured 2.50s/page = 268s, i.e. ~80% of a
# healthy run. A 1.25x allowance over the max would leave only ~105s of slack
# for that scan, so a merely 2x-slow host would start truncating healthy work.
# 3 x 419s = 1257s, rounded up to the whole minute, absorbs a 3x-slow host end
# to end and is still far under the workflow ceiling derived from it.
DEADLINE_SECONDS = max(60, min(1800, int(os.environ.get("REASON_BACKFILL_DEADLINE_SECONDS", "1260"))))
# Budget held back from the scan and the model loop so the writes always run.
# A full deterministic flush is ceil(400 / EDIT_BATCH) = 10 chunks, measured at
# a few seconds total; 240s covers two chunks stalling to the 120s /edit
# timeout and still leaves the rest of the flush inside the deadline.
WRITE_RESERVE_SECONDS = max(30, min(600, int(os.environ.get("REASON_BACKFILL_WRITE_RESERVE_SECONDS", "240"))))
# Wall clock starts at process start, not at the model loop.
STARTED_AT = time.monotonic()
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


def elapsed():
    """Seconds since process start (the run-wide clock)."""
    return time.monotonic() - STARTED_AT


def past_deadline(reserve=0):
    """True once this run must stop starting new work of that phase."""
    return elapsed() >= DEADLINE_SECONDS - reserve


def erm_template_tags(row):
    """(matched, tags) for our own ERM excerpt template; tags may be empty."""
    if row.get("source_type") != "erm":
        return False, []
    match = ERM_TEMPLATE.match(row.get("excerpt") or "")
    if not match:
        return False, []
    return True, list(ERM_TYPE_TAGS.get(match.group("rtype").strip().lower(), []))


def fetch_candidates(stop=None):
    """Page through non-WARN rows; keep untagged rows that carry evidence.

    `stop` is a zero-arg predicate; when it returns True the scan stops and
    returns what it has so far. A short scan is safe, not silent: it only means
    fewer candidates were offered to this run, the rows are still there for the
    next one, and the caller prints the shortfall. Returns
    (candidates, pages_scanned, truncated).
    """
    stop = stop or (lambda: False)
    candidates = []
    page = 1
    truncated = False
    while page <= MAX_PAGES:
        # Checked BEFORE the request, so the scan cannot start a page it has no
        # budget to finish. This is the phase that used to run unbounded: 107
        # pages x up to (3 attempts x 60s + 15s backoff) is 5.8 hours, 7.7x the
        # workflow ceiling that eventually killed run 31462430383.
        if page > 1 and stop():
            truncated = True
            print(f"  scan stopped at the run deadline after {page - 1} page(s); "
                  f"the unscanned rows are offered to the next run")
            break
        params = {"sources": NON_WARN_SOURCES, "sort": "id", "dir": "asc",
                  "per_page": PAGE_SIZE, "page": page}
        # Retry transient host errors instead of aborting the whole scan. The
        # shared host 500s on a single page under load; industry_backfill was
        # failing DAILY for exactly this reason (one bad page killed the run
        # before any work) until it gained retries — reason_backfill had the
        # same fragility and hit it on 2026-07-25. Retry the page a few times,
        # then carry on with the pages we have; page 1 failing is a real outage
        # and still raises.
        # The retry itself now comes from http_retry, the ONE definition — this
        # loop used to hold its own copy of "which statuses are worth another
        # try", which is exactly the drift that module exists to prevent.
        response = http_retry.get_with_retry(f"{SITE}/wp-json/layoffs/v1/query",
                                             params=params, headers=UA, timeout=60)
        if response is None:
            if page > 1:
                print(f"  page {page}: the host stopped answering; continuing with "
                      f"{len(candidates)} candidate(s) already collected")
                break
            # Page one never answered: nothing was scanned, nothing classified,
            # nothing written. Safe to defer — the identical scan runs tomorrow.
            raise host_call.Deferred("/query never answered on page 1 of the scan")
        # WP returns 404 for a page past the last row; between our sequential
        # page requests the candidate set shrinks (rows get tagged), so the
        # final page can 404 even though the scan succeeded. End-of-data, not a
        # failure. A 404 on page 1 is a real endpoint problem and still raises.
        if response.status_code == 404 and page > 1:
            break
        if response.status_code >= 500 and page > 1:
            print(f"  page {page}: still HTTP {response.status_code} after retries; "
                  f"continuing with {len(candidates)} candidate(s) already collected")
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
    return candidates, page, truncated


def rotating_slice(rows, batch, day_ordinal):
    """Deterministic daily slice so no-reason rows cannot stall the queue."""
    if not rows or batch <= 0:
        return []
    pages = (len(rows) + batch - 1) // batch
    start = (day_ordinal % pages) * batch
    return rows[start:start + batch]


def post_edits(items, stop=None):
    """POST /edit in bounded batches; any HTTP failure raises (fail loudly).

    `stop` is the same predicate the scan and the model loop use, checked
    before each chunk so a stalled host cannot push the flush past the
    workflow ceiling. Returns (edited, not_found, unwritten): rows never sent
    stay untagged and are re-found next run, which is the whole reason the
    /edit write is idempotent.
    """
    stop = stop or (lambda: False)
    edited, not_found, unwritten = [], [], 0
    for start in range(0, len(items), EDIT_BATCH):
        if stop():
            unwritten = len(items) - start
            print(f"  write deadline reached; {unwritten} decided row(s) left "
                  f"unwritten for the next run")
            break
        chunk = items[start:start + EDIT_BATCH]
        try:
            result = host_call.post_json(
                f"{SITE}/wp-json/layoffs/v1/edit",
                {"reason": EDIT_REASON,
                 "edits": [{"id": i["id"], "fields": {"reason_tags": i["reason_tags"]}} for i in chunk]},
                headers={**UA, "X-Layoff-API-Key": KEY},
                timeout=120,
            )
        except host_call.Deferred as exc:
            # NOT a deferral of the run: earlier chunks may already be written,
            # and the flush already has an honest name for "decided but not
            # written". Same exit as a stalled host hitting the write deadline.
            unwritten = len(items) - start
            print(f"  the host stopped answering ({exc}); {unwritten} decided "
                  f"row(s) left unwritten for the next run")
            break
        edited.extend(result.get("edited", []))
        not_found.extend(result.get("not_found", []))
        if result.get("rejected"):
            # /edit rejects an item only when no writable field survives —
            # with our single validated field that means vocabulary drift
            # between this worker and the plugin. Never paper over it.
            raise RuntimeError(f"/edit rejected ids {result['rejected']}: reason-tag vocabulary drift?")
    return edited, not_found, unwritten


def run():
    # The scan and the model loop hold back WRITE_RESERVE_SECONDS; the flush
    # itself may use the full deadline. One clock, three phases.
    work_stop = lambda: past_deadline(WRITE_RESERVE_SECONDS)
    write_stop = lambda: past_deadline()

    candidates, pages, scan_truncated = fetch_candidates(stop=work_stop)
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

    # Flush the deterministic edits NOW, before the model loop spends a second
    # on them. They are ~400 of a normal run's ~402 writes and cost no model
    # call; holding them until the end is what made a killed run lose a whole
    # day of tagging. Nothing downstream depends on them being unwritten.
    edited, not_found, unwritten = [], [], 0
    if deterministic and not DRY_RUN:
        edited, not_found, unwritten = post_edits(deterministic, stop=write_stop)
        print(f"deterministic flush: edited={len(edited)} not_found={len(not_found)} "
              f"unwritten={unwritten} at {elapsed():.0f}s")

    items = list(deterministic)
    model_items = []
    model_skips, model_failures, checked = 0, 0, 0
    queue = rotating_slice(model_rows, BATCH, date.today().toordinal())
    for row in queue:
        # Nothing is half-written per row, so stopping between rows is safe;
        # the next daily run resumes the rotation.
        if work_stop():
            print(f"Reached REASON_BACKFILL_DEADLINE_SECONDS={DEADLINE_SECONDS} "
                  f"(less the {WRITE_RESERVE_SECONDS}s write reserve); "
                  f"stopping safely after {checked} model row(s)")
            break
        checked += 1
        result = classify_reason_tags(row.get("excerpt") or "")
        if result is None:
            model_failures += 1
            print(f"  model id={row['id']}: FAILED (retried on a later rotation)")
            continue
        if result["reason_tags"]:
            model_items.append({"id": int(row["id"]), "reason_tags": result["reason_tags"]})
            items.append({"id": int(row["id"]), "reason_tags": result["reason_tags"]})
            print(f"  model id={row['id']}: {','.join(result['reason_tags'])}")
        else:
            model_skips += 1  # evidence names no reason — honestly left empty
            print(f"  model id={row['id']}: evidence names no reason — left untagged")
        time.sleep(0.25)

    print(f"candidates={len(candidates)} pages_scanned={pages} "
          f"scan_truncated={int(scan_truncated)} template_taggable={deterministic_backlog} "
          f"model_queue={len(model_rows)} model_checked={checked} "
          f"model_skips={model_skips} model_failures={model_failures} "
          f"writes_queued={len(items)} elapsed={elapsed():.0f}s")

    if DRY_RUN:
        for item in items:
            print(f"  would tag id={item['id']}: {','.join(item['reason_tags'])}")
        print("DRY RUN: no writes performed.")
        return {"tagged": 0, "checked": checked, "model_failures": model_failures}

    if model_items:
        m_edited, m_not_found, m_unwritten = post_edits(model_items, stop=write_stop)
        edited, not_found = edited + m_edited, not_found + m_not_found
        unwritten += m_unwritten
    print(f"edited={len(edited)} not_found={len(not_found)} unwritten={unwritten}")
    if not_found:
        # A vanished id means the row set changed mid-run (dedupe/purge);
        # visible, but the other applied edits remain valid.
        print(f"WARNING: ids not found: {not_found}")
    spend.record_job_run(items=checked, changed=len(edited))

    # A fully failed attempted model pass must be visible in Actions rather
    # than reading as a quiet no-op day (reclassify worker rule).
    if checked and model_failures == checked and not items:
        raise RuntimeError(f"All {checked} attempted model classifications failed")

    det_ids = {item["id"] for item in deterministic}
    det_edited = sum(1 for row_id in edited if row_id in det_ids)
    pending = (deterministic_backlog - det_edited) + (len(model_rows) - (len(edited) - det_edited))
    # A short run must SAY it was short. A truncated scan means the pending
    # figure is a floor, not a count, and reading it as a count is how a
    # silently shrinking job looks healthy.
    short = ""
    if scan_truncated:
        short = (f"; run stopped early on its {DEADLINE_SECONDS}s deadline after "
                 f"{pages - 1} scanned page(s), so the pending figure is a floor")
    if unwritten:
        short += f"; {unwritten} decided row(s) deferred to the next run"
    detail = (f"{len(edited)} tagged ({det_edited} from ERM recorded type, "
              f"{len(edited) - det_edited} model-classified); {model_skips} evidence-names-no-reason "
              f"skips; {model_failures} model failures; ~{max(0, pending)} untagged rows pending"
              + short)
    if not report_source_health("reason_backfill", "ok", len(edited), detail):
        print("::warning::reason backfill completed but the health-ledger write failed (data is fine)")
    return {"tagged": len(edited), "checked": checked, "model_failures": model_failures}


def main():
    if not SITE or (not KEY and not DRY_RUN):
        print("WP_SITE_URL and WP_API_KEY are required (or set REASON_BACKFILL_DRY_RUN=1)")
        return 1
    if not DRY_RUN:
        # First thing the job does, before anything is scanned or written. A
        # host that never answered defers; a host that REFUSED the write still
        # raises, because a wrong key is settled and fails identically tomorrow.
        code = require_running_note(
            JOB, "reason_backfill",
            "bounded stored-excerpt reason-tag backfill in progress")
        if code is not None:
            return code
    try:
        run()
        host_call.clear(JOB)
        return 0
    except host_call.Deferred as exc:
        # Raised only from page one of the scan: nothing was read, classified
        # or written, so this is not a degraded collector.
        return host_call.defer(JOB, str(exc))
    except CreditsExhaustedError as exc:
        # BILLING, not code: the LLM provider is out of credits. Record a
        # distinct, actionable state and exit 0 so it does not page as a code
        # failure every run; the weekly health digest surfaces it until topped up.
        if not DRY_RUN:
            report_source_health("reason_backfill", "degraded", 0,
                                 "OpenRouter credits exhausted (HTTP 402) - top up at "
                                 "https://openrouter.ai/settings/credits; no rows classified")
        print(f"::warning::reason_backfill halted: {exc} (billing, not a code failure)")
        return 0
    except Exception as exc:
        # A failed backfill attempt is a material condition, not a quiet
        # retry: record it in the public health ledger, then exit non-zero.
        if not DRY_RUN:
            report_source_health("reason_backfill", "degraded", 0, f"reason backfill failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
