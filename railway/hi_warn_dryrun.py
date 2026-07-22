"""Dry-run the Hawaii WARN OCR path — prints extracted counts, posts NOTHING.

Run this (locally with tesseract installed, or via the `hi-warn-dryrun` GitHub
workflow which installs it) to eyeball OCR accuracy before the source goes live.

    HI_DRYRUN_YEARS=2025,2026 HI_DRYRUN_LIMIT=15 python hi_warn_dryrun.py

Env (all optional):
    HI_DRYRUN_YEARS  comma-separated years to crawl (default: last/this/next).
    HI_DRYRUN_LIMIT  stop after N successful extractions (default: no limit).
"""
import os
import sys


def main():
    from sources.warn_hi_ocr import fetch_hi_ocr

    years = None
    raw = os.environ.get("HI_DRYRUN_YEARS", "").strip()
    if raw:
        try:
            years = sorted({int(y) for y in raw.split(",") if y.strip()})
        except ValueError:
            print(f"bad HI_DRYRUN_YEARS={raw!r}")
            return 1
    limit = None
    if os.environ.get("HI_DRYRUN_LIMIT", "").strip().isdigit():
        limit = int(os.environ["HI_DRYRUN_LIMIT"])

    entries = fetch_hi_ocr(years=years, limit=limit, dry_run=True)
    print(f"\nRESULT: {len(entries)} countable Hawaii notice(s) would be posted "
          f"(DRY-RUN — nothing was sent to the site).")
    # Non-zero exit only on a hard OCR-stack failure, not on a legitimately empty
    # crawl, so a manual dispatch is easy to read.
    return 0


if __name__ == "__main__":
    sys.exit(main())
