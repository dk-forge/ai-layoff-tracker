"""Dry-run the West Virginia WARN OCR path — prints counts, posts NOTHING.

WorkForce WV's newest cumulative summary PDF stops at 2025-01-03. Everything
after that is an individual notice letter, and on 2026-08-13 twenty-one of the
twenty-seven post-cutoff letters were image-only scans with no text layer, so
their headcount exists only as pixels. `fetch_wv` therefore has an OCR tier,
gated behind WV_OCR=1 and dormant by default (it needs the tesseract system
binary, which the lean daily workflows do not install).

This is the gate's verification job, mirroring hi_warn_dryrun.py: it runs the
fetcher WITH OCR on and prints every row, so a human can judge the extracted
counts against the source PDFs before the tier is promoted to live. It posts
nothing and uses no WP_API_KEY.

    WV_OCR=1 python wv_warn_dryrun.py

Env (all optional):
    WV_DRYRUN_SINCE  only print rows on/after this ISO date (default 2025-01-04,
                     the day after the newest summary PDF's coverage ends —
                     i.e. exactly the span the OCR tier is responsible for).
"""
import os
import sys


def main():
    # The whole point of this job is the OCR tier, so turn it on rather than
    # silently dry-running the text-layer path and reporting a clean bill of
    # health for a tier that never ran.
    os.environ["WV_OCR"] = "1"
    try:
        import pytesseract  # noqa: F401
        pytesseract.get_tesseract_version()
    except Exception as exc:
        print(f"::error:: tesseract/pytesseract unavailable ({exc}). This job "
              f"cannot verify the OCR tier without them — that is UNKNOWN, not "
              f"a pass. Install tesseract-ocr and re-run.")
        return 1

    from sources.warn_new_states import fetch_wv

    since = os.environ.get("WV_DRYRUN_SINCE", "").strip() or "2025-01-04"
    rows = fetch_wv()
    recent = sorted((e for e in rows if (e.get("layoff_date") or "") >= since),
                    key=lambda e: e["layoff_date"])
    print(f"\nWV dry-run: {len(rows)} row(s) total, {len(recent)} on/after {since} "
          f"(the span the summary PDFs do not cover)\n")
    for e in recent:
        print(f"  {e['layoff_date']}  {e['job_count']:>6,}  {e['company_name']}")
        print(f"          {e['source_url']}")
    if not recent:
        print("  (none — every post-cutoff letter was skipped; read the ::notice:: "
              "lines above for the reason per notice)")
    # Never non-zero on "found nothing": this job reports, it does not gate.
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
