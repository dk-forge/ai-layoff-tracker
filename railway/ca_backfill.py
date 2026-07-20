"""
Backfill California WARN HISTORY from the EDD annual-report PDF archives.

DISPATCH-ONLY. This script is NOT wired into any cron and is NOT part of the
daily data jobs. Run it by hand (or via a manual GitHub "workflow_dispatch")
when you want to pull historical California notices. It is UNVALIDATED against
the live EDD PDFs until someone runs it once and eyeballs the parsed output —
EDD's annual filenames and in-PDF column layouts are inconsistent across fiscal
years, so treat the first run as a shake-out.

WHY THIS EXISTS
---------------
The regular WARN pipeline (warn_import.py -> sources/warn.py) reads California
from the live rolling spreadsheet
(edd.ca.gov/.../warn/warn_report1.xlsx), which only holds the CURRENT fiscal
year. Everything older rolls off. EDD separately publishes one PDF per closed
fiscal year (July 1 -> June 30), e.g.

    https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-2024-to-06-30-2025.pdf

This script parses those annual PDFs into the exact same entry shape (and exact
same dedup hash) as sources/warn.py via the shared `_entry("CA", ...)` factory,
then upserts them through the same POST /bulk path warn_import.py uses. Because
the hash is identical, re-imports (and overlap with the live xlsx for the
current year) upsert in place instead of duplicating.

CONSERVATIVE BY DESIGN: any row we cannot confidently parse (no company, no
usable date, non-numeric or absurd count) is skipped, never guessed.

Env:
  CA_BACKFILL_PDF_URLS  comma/newline-separated PDF URLs; OVERRIDES the built-in
                        list below when set (use it to add a newly published
                        fiscal-year report without editing this file)
  CA_BACKFILL_DRY_RUN   "1"/"true" -> parse + print counts, but DON'T POST
  WP_SITE_URL, WP_API_KEY   (same as warn_import.py; required unless dry-run)

Run:
  python3 -m py_compile railway/ca_backfill.py
  WP_SITE_URL=... WP_API_KEY=... python3 railway/ca_backfill.py
  CA_BACKFILL_DRY_RUN=1 python3 railway/ca_backfill.py   # parse only
"""
import io
import os
import re
import sys

import requests

# Reuse the exact normalized-entry factory + hash and the PDF helpers the custom
# WARN collectors use, so CA history entries are byte-identical to live ones.
from sources.warn_custom import _entry, _pdf_tables, _pdf_text, UA, TIMEOUT
from sources.warn import _count, _to_iso_date

# post_bulk (and its FAILED_BATCHES fail-loud counter) live in warn_import; import
# the module so we can both call it and read its failure count afterward. Per the
# task, warn_import.py itself is left untouched.
import warn_import


# --- Known EDD annual-report PDFs ------------------------------------------
# UPDATE THIS LIST as EDD publishes each new closed fiscal year (a report for
# FY 7/1/N -> 6/30/N+1 appears the following summer). EDD's filenames are NOT
# consistently formatted across years ("7-1" vs "07-01", "06-30" vs "6-30"),
# so every URL here should be VERIFIED against edd.ca.gov before trusting a run
# — a 404 is skipped and logged, never fatal on its own.
#
# Verified live (matches the pattern in EDD's current publishing scheme):
#   FY 2024-2025 (the example the pipeline was built from)
# Prior years follow the same slug pattern but are UNVERIFIED best-guesses; if
# one 404s, find the real filename on
#   https://edd.ca.gov/en/jobs_and_training/layoff_services_warn/
# and either fix it here or pass CA_BACKFILL_PDF_URLS.
_EDD_WARN_DIR = "https://edd.ca.gov/siteassets/files/jobs_and_training/warn"
KNOWN_EDD_ANNUAL_PDFS = [
    f"{_EDD_WARN_DIR}/warn-report-for-7-1-2024-to-06-30-2025.pdf",   # FY 2024-25 (verified pattern)
    f"{_EDD_WARN_DIR}/warn-report-for-7-1-2023-to-06-30-2024.pdf",   # FY 2023-24 (UNVERIFIED)
    f"{_EDD_WARN_DIR}/warn-report-for-7-1-2022-to-06-30-2023.pdf",   # FY 2022-23 (UNVERIFIED)
    f"{_EDD_WARN_DIR}/warn-report-for-7-1-2021-to-06-30-2022.pdf",   # FY 2021-22 (UNVERIFIED)
    f"{_EDD_WARN_DIR}/warn-report-for-7-1-2020-to-06-30-2021.pdf",   # FY 2020-21 (UNVERIFIED)
    f"{_EDD_WARN_DIR}/warn-report-for-7-1-2019-to-06-30-2020.pdf",   # FY 2019-20 (UNVERIFIED)
]


def _pdf_urls():
    override = (os.environ.get("CA_BACKFILL_PDF_URLS") or "").strip()
    if override:
        urls = [u.strip() for u in re.split(r"[,\n]", override) if u.strip()]
        print(f"CA backfill: using {len(urls)} URL(s) from CA_BACKFILL_PDF_URLS")
        return urls
    return list(KNOWN_EDD_ANNUAL_PDFS)


# --- Column mapping (template-agnostic, like the NC/MN custom collectors) ----
# EDD's annual PDFs are gridded tables, but the exact header wording and column
# order drift year to year. Rather than hardcode indexes, we find the header row
# inside each table and map columns by keyword. Effective date wins over
# received/notice date, matching the tracker's lower-bound convention.
def _norm(cell):
    return re.sub(r"\s+", " ", str(cell or "")).strip()


def _header_map(cells):
    """Return {field: col_index} if `cells` looks like a header row, else None.
    Requires at least a company column and a count column to accept the row."""
    idx = {}
    for i, c in enumerate(cells):
        lc = _norm(c).lower()
        if not lc:
            continue
        if "company" in lc or "employer" in lc or "business" in lc:
            idx.setdefault("company", i)
        elif "no. of employees" in lc or "number of employees" in lc \
                or "employees affected" in lc or "affected" in lc \
                or ("employee" in lc and "count" in lc) or lc == "employees":
            idx.setdefault("jobs", i)
        elif "effective" in lc:
            idx.setdefault("eff", i)
        elif "received" in lc:
            idx.setdefault("recv", i)
        elif "notice date" in lc or lc == "notice" or "date of notice" in lc:
            idx.setdefault("notice", i)
        elif lc == "city" or "city" in lc:
            idx.setdefault("city", i)
        elif "county" in lc or "parish" in lc:
            idx.setdefault("county", i)
        elif "layoff/closure" in lc or "closure" in lc or "type" in lc \
                or "layoff or closure" in lc:
            idx.setdefault("kind", i)
    return idx if "company" in idx and "jobs" in idx else None


def _entries_from_pdf(content, url):
    """Parse one EDD annual PDF into CA entries. The column map persists across
    tables/pages because later pages often omit the repeated header."""
    out = []
    cols = None
    for table in _pdf_tables(content):
        for row in table:
            cells = [_norm(c) for c in row]
            hdr = _header_map(cells)
            if hdr:
                cols = hdr
                continue
            if not cols:
                continue

            def get(key):
                j = cols.get(key)
                return cells[j] if (j is not None and j < len(cells)) else ""

            company = get("company")
            jobs = _count(get("jobs"))
            # Effective date preferred, then received, then notice date.
            date = (_to_iso_date(get("eff")) or _to_iso_date(get("recv"))
                    or _to_iso_date(get("notice")))
            # Prefer city; fall back to county (the annual PDFs sometimes carry
            # only "County/Parish"). _entry treats it as a display location only.
            city = get("city") or get("county")
            kind = ""
            raw_kind = get("kind").lower()
            if "closure" in raw_kind:
                kind = "Closure"
            elif "layoff" in raw_kind:
                kind = "Layoff"

            # CONSERVATIVE: _entry itself rejects blank company, non-positive or
            # >100K counts, and out-of-window dates — returning None. We simply
            # skip anything it (or our own parse) can't stand behind.
            e = _entry("CA", company, jobs, date, city, kind=kind, detail_url=url)
            if e:
                out.append(e)
    return out


def _fetch(url):
    """Download a PDF; return bytes or None (fail-isolated, never fatal alone)."""
    try:
        resp = requests.get(url, headers=UA, timeout=max(TIMEOUT, 90))
    except Exception as exc:
        print(f"  {url.rsplit('/', 1)[-1]}: fetch error ({exc})")
        return None
    if resp.status_code != 200:
        print(f"  {url.rsplit('/', 1)[-1]}: HTTP {resp.status_code} (skipped)")
        return None
    if resp.content[:4] != b"%PDF":
        print(f"  {url.rsplit('/', 1)[-1]}: not a PDF (skipped)")
        return None
    return resp.content


def main():
    urls = _pdf_urls()
    dry_run = (os.environ.get("CA_BACKFILL_DRY_RUN") or "").lower() in ("1", "true", "yes")
    print(f"CA WARN backfill: {len(urls)} annual PDF(s), dry_run={dry_run}")

    all_entries = []
    parsed_ok = 0
    for url in urls:
        content = _fetch(url)
        if content is None:
            continue
        try:
            entries = _entries_from_pdf(content, url)
        except Exception as exc:
            print(f"  {url.rsplit('/', 1)[-1]}: parse failed ({exc})")
            continue
        parsed_ok += 1
        print(f"  {url.rsplit('/', 1)[-1]}: {len(entries)} notices kept")
        all_entries.extend(entries)

    # Collapse exact duplicates within this run (identical dedup hash) so we don't
    # ship the same notice twice when fiscal years or the live xlsx overlap.
    seen = set()
    deduped = []
    for e in all_entries:
        if e["dedup_hash"] in seen:
            continue
        seen.add(e["dedup_hash"])
        deduped.append(e)
    print(f"CA WARN backfill: {len(deduped)} unique notices from {parsed_ok} PDF(s)")

    # FAIL LOUD: if NOTHING parsed (every URL 404'd or every PDF was unreadable),
    # a green run would falsely look like "California has no history". Exit non-zero.
    if not deduped:
        print("ERROR: CA backfill produced 0 notices — all PDFs missing or unparseable")
        sys.exit(1)

    if dry_run:
        # Show a small sample so a manual validator can sanity-check the parse.
        for e in deduped[:5]:
            print(f"    sample: {e['company_name']} | {e['job_count']} | "
                  f"{e['layoff_date']} | {e['state']}")
        print("CA WARN backfill: DRY RUN — nothing posted")
        return

    upserted = warn_import.post_bulk(deduped)
    print(f"CA WARN backfill done: {upserted} upserted from {len(deduped)} notices")

    # A green run must mean the data actually landed. post_bulk records rejected
    # batches on warn_import.FAILED_BATCHES; surface them as a non-zero exit.
    if warn_import.FAILED_BATCHES:
        print(f"ERROR: {warn_import.FAILED_BATCHES} batch(es) failed to post")
        sys.exit(1)


if __name__ == "__main__":
    main()
