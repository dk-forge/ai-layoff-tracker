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
import sys

from source_health import report_source_health
from sources.warn_hi_ocr import fetch_hi_ocr
import warn_import  # reuse post_bulk + the FAILED_BATCHES loud-fail counter
import spend


def main():
    report_source_health("warn_hi_ocr", "running", 0, "Hawaii WARN OCR import in progress")
    try:
        entries = fetch_hi_ocr()
    except Exception as exc:
        report_source_health("warn_hi_ocr", "degraded", 0, f"OCR pull failed: {exc}")
        raise
    if not entries:
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
    report_source_health("warn_hi_ocr", "ok", upserted,
                         "Hawaii WARN notices (OCR-recovered affected counts)")


if __name__ == "__main__":
    main()
