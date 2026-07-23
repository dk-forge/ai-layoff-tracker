"""Repair legacy rows that a re-import can no longer reach.

Two defects found by the 2026-07-23 full-dataset scan survive in rows whose
source page no longer carries them (a state scraper only fetches a recent
window, so re-running the importer cannot correct 2018 rows):

  1. The notice's SITE ADDRESS glued into the employer name, which fragments
     company identity ("Walmart (1345 Crossman Ave.)" never groups with
     "Walmart"). The import-boundary sanitizer fixes this going forward and for
     anything still in a scraper's window; everything older needs an edit.
  2. A blank country, which hides the row from every country filter and from
     the map even though it is counted in the totals.

Both are repaired through the keyed /edit path, so each change lands in the
PUBLIC corrections log rather than being applied silently.

Country is only ever inferred from DETERMINISTIC evidence:
  - a US state code on the row, or a US state government WARN source URL
Publisher nationality is deliberately NOT used. A BBC article is not evidence
that the layoff happened in the United Kingdom, and guessing from a news domain
would put invented geography into a dataset whose whole claim is that nothing
is invented. Rows we cannot resolve are reported and left alone.

    WP_SITE_URL=... WP_API_KEY=... python3 railway/legacy_row_repair.py
        --apply           actually write (default is a dry run)
        --max 500         cap the number of edits
        --only names|country
"""
import argparse
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from warn_import import _clean_company  # single source of truth for name cleaning
from http_retry import get_with_retry  # single source of truth for transient 5xx

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
PAGE = 200
TIMEOUT = 60

# US state WARN registries and other US government hosts. A row sourced from a
# state labor department is, by definition, a US notice.
_US_HOST_RX = re.compile(
    r"(\.gov\b|\.us\b|dol\.|dllr\.|edd\.ca\.gov|floridajobs|texas\.gov|"
    r"illinoisworknet|virginiaworks|jobs\.alaska|dwd\.wisconsin|labor\.hawaii)", re.I)
_US_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DC','DE','FL','GA','HI','IA','ID','IL','IN','KS',
    'KY','LA','MA','MD','ME','MI','MN','MO','MS','MT','NC','ND','NE','NH','NJ','NM','NV',
    'NY','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VA','VT','WA','WI','WV','WY',
}


def _fetch_all():
    """Every published row, page by page."""
    rows, page = [], 1
    while True:
        r = get_with_retry(f"{SITE}/wp-json/layoffs/v1/query",
                           params={"per_page": PAGE, "page": page, "cb": f"repair{page}"},
                           headers=UA, timeout=TIMEOUT)
        if r is None:
            if page == 1:
                raise RuntimeError("legacy repair: /query unreachable on page 1 after retries")
            # A blip on one page of a 300-page scan is not a reason to discard
            # the run: repair what we did read, the rest comes next run.
            print(f"  scan: page {page} still failing after retries, "
                  f"continuing with {len(rows):,} row(s) already read")
            break
        if r.status_code == 404 and page > 1:
            break
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            break
        rows.extend(data)
        if len(data) < PAGE:
            break
        page += 1
        if page > 400:            # hard bound; the table is ~63K rows
            break
    return rows


def _infer_country(row):
    """United States, or None. Deterministic evidence only."""
    state = str(row.get("state") or "").strip().upper()
    if state in _US_STATES:
        return "United States"
    if _US_HOST_RX.search(str(row.get("source_url") or "")):
        return "United States"
    return None


def _post_edits(edits, reason):
    r = requests.post(f"{SITE}/wp-json/layoffs/v1/edit",
                      json={"reason": reason, "edits": edits},
                      headers={"X-Layoff-API-Key": KEY, **UA}, timeout=TIMEOUT)
    if r.status_code != 200:
        print(f"::error::edit failed HTTP {r.status_code}: {r.text[:300]}")
        return None
    out = r.json()
    missed = list(out.get("not_found") or []) + list(out.get("rejected") or [])
    if missed:
        print(f"::error::ids not applied: {missed}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max", type=int, default=500)
    ap.add_argument("--only", choices=("names", "country", "both"), default="both")
    a = ap.parse_args()
    if not SITE:
        print("WP_SITE_URL required")
        return 1

    print("scanning published rows...")
    rows = _fetch_all()
    print(f"scanned {len(rows):,} rows")

    name_edits, country_edits, unresolved = [], [], 0
    for row in rows:
        rid = int(row.get("id") or 0)
        if not rid:
            continue
        if a.only in ("names", "both"):
            raw = str(row.get("company_name") or "")
            clean = _clean_company(raw)
            # Only act when cleaning actually changes something AND leaves a
            # usable name; never blank a row out.
            if clean and clean != raw and re.search(r"[A-Za-z0-9]", clean):
                name_edits.append({"id": rid, "fields": {"company": clean}})
        if a.only in ("country", "both"):
            if not str(row.get("country") or "").strip():
                inferred = _infer_country(row)
                if inferred:
                    country_edits.append({"id": rid, "fields": {"country": inferred}})
                else:
                    unresolved += 1

    print(f"\nname repairs      : {len(name_edits)}")
    for e in name_edits[:8]:
        print(f"    id={e['id']} -> {e['fields']['company']!r}")
    print(f"country repairs   : {len(country_edits)}  (deterministic evidence only)")
    for e in country_edits[:8]:
        print(f"    id={e['id']} -> {e['fields']['country']}")
    print(f"left alone        : {unresolved} blank-country row(s) with no deterministic "
          f"evidence (publisher nationality is not evidence of layoff location)")

    if not a.apply:
        print("\nDRY RUN. Re-run with --apply to write.")
        return 0
    if not KEY:
        print("WP_API_KEY required to apply")
        return 1

    applied = 0
    for label, edits, reason in (
        ("names", name_edits,
         "Legacy repair: the notice's site address was stored inside the employer name, "
         "which split the company from its own other rows. Name normalized; no count, "
         "date or source changed."),
        ("country", country_edits,
         "Legacy repair: country filled from deterministic evidence (a US state code on "
         "the row, or a US state government WARN source). Rows without such evidence were "
         "left blank rather than guessed."),
    ):
        if not edits:
            continue
        for i in range(0, min(len(edits), a.max), 100):
            chunk = edits[i:i + 100]
            out = _post_edits(chunk, reason)
            if out is None:
                return 1
            applied += len(out.get("edited") or [])
            print(f"  {label}: applied {len(out.get('edited') or [])} (batch {i // 100 + 1})")
    print(f"\napplied {applied} edit(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
