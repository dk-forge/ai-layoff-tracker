"""Daily import of Hawaii WARN notices (OCR path).

Hawaii posts each notice as an image-scan PDF, so the affected-employee count is
OCR-only. This crawls the WDC per-year pages, OCRs each notice, extracts the
affected count with a calibrated, skip-don't-guess extractor (see
sources/warn_hi_ocr.py), and posts via the bulk table endpoint (like every WARN
source, it skips the LLM). Reuses warn_import.post_bulk (batching, transient-5xx
retry, loud-fail). Idempotent: the dedup hash matches warn.py, so re-runs upsert
in place. Required secret: WP_API_KEY. Needs tesseract (installed in the
workflow, not the shared requirements).
"""
import os
import sys

from source_health import report_source_health
from sources.warn_hi_ocr import fetch_hi_ocr
import sources.warn_hi_ocr as warn_hi_ocr
import warn_import  # reuse post_bulk + the FAILED_BATCHES loud-fail counter
import spend

#: THIS RUN'S OWN WALL CLOCK, and it must stay below the workflow's
#: `timeout-minutes: 30`. The run of 2026-09-16 was killed by the runner at
#: 30m0s: everything OCR'd in those thirty minutes was thrown away, nothing
#: was upserted, and the terminal health note was never posted. A job that
#: stops ITSELF finishes the notice in hand, posts what it has and exits 0.
#:
#: Clamped rather than a bare env read, so an operator raising
#: HI_DEADLINE_SECONDS cannot push it past the kill;
#: tests/test_deadline_below_workflow_timeout.py reads this ceiling straight
#: out of the AST and fails if it ever stops clearing the runner's kill by the
#: 60s a clean stop needs.
DEADLINE_SECONDS = max(60, min(1500, int(os.environ.get("HI_DEADLINE_SECONDS") or "1500")))


def main():
    report_source_health("warn_hi_ocr", "running", 0, "Hawaii WARN OCR import in progress")
    try:
        entries = fetch_hi_ocr(deadline_seconds=DEADLINE_SECONDS)
    except Exception as exc:
        report_source_health("warn_hi_ocr", "degraded", 0, f"OCR pull failed: {exc}")
        raise
    if not entries:
        # Two different zeros, and they must not share a message. A run the
        # deadline stopped before it reached a countable notice has learned
        # NOTHING about the page or the OCR, and saying "page changed or OCR
        # broke" would send a human hunting a defect that is not there.
        if warn_hi_ocr.DEADLINE_TRUNCATED:
            report_source_health("warn_hi_ocr", "degraded", 0,
                                 f"stopped at its own {DEADLINE_SECONDS}s deadline "
                                 f"before any notice was countable; the crawl is "
                                 f"cumulative so the next run re-reads it")
            print("warn_hi_ocr: deadline reached with nothing countable yet")
            sys.exit(1)
        # The crawl returns the full cumulative set each run, so 0 means the WDC
        # page layout changed or OCR/deps broke — report degraded so it is visible.
        report_source_health("warn_hi_ocr", "degraded", 0,
                             "0 Hawaii notices parsed (page changed or OCR broke)")
        print("warn_hi_ocr: nothing to upsert")
        sys.exit(1)
    upserted = warn_import.post_bulk(entries)
    print(f"Hawaii WARN OCR import done: {upserted} upserted from {len(entries)} notices")
    spend.record_job_run(items=len(entries), stored=upserted)
    if warn_import.FAILED_BATCHES:
        report_source_health("warn_hi_ocr", "degraded", upserted,
                             f"{warn_import.FAILED_BATCHES} batch(es) rejected by the API")
        sys.exit(1)
    if warn_hi_ocr.DEADLINE_TRUNCATED:
        # A PARTIAL sweep is not a full one, and "ok" on a truncated run is the
        # started-not-finished shape: it would reset the staleness clock while
        # part of the register went unread.
        report_source_health("warn_hi_ocr", "degraded", upserted,
                             f"partial sweep: stopped at its own "
                             f"{DEADLINE_SECONDS}s deadline. The crawl is "
                             f"cumulative and the upsert idempotent, so the "
                             f"next run re-reads what this one did not reach")
        return
    report_source_health("warn_hi_ocr", "ok", upserted,
                         "Hawaii WARN notices (OCR-recovered affected counts)")


if __name__ == "__main__":
    main()
