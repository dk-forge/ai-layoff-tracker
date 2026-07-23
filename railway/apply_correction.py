"""Apply a signed-off editorial correction to specific published rows.

The audit protocol (docs/RUNBOOK.md "quarterly source-verification audit")
produces a short list of rows whose stored facts do not match their own cited
source. Published corrections governance says a numeric change ALWAYS needs a
human sign-off, so this is deliberately a manual, dispatch-only tool: it never
runs on a schedule and it refuses to do anything without a written reason.

Two actions, matching the two things an audit can conclude:

    trash  - the row's number is not supported by its source at all (the count
             belongs to a different event, or the source states no count). The
             row is removed and its dedup hash SUPPRESSED, so the nightly
             re-scrape of the same page cannot resurrect it.
    edit   - the row is real but a field is wrong. /edit pins the row and
             suppresses the original hash so an import cannot revert it.

Both paths fail loudly (non-zero exit) on any not-found or rejected id, so a
correction that silently did nothing can never be reported as applied.

    WP_SITE_URL=... WP_API_KEY=... python3 railway/apply_correction.py \
        --ids 70289 --action trash --reason "audit #1: source states no count" \
        --verify-company Starbucks

Add --apply to actually write; without it the run is a DRY RUN that only shows
what would change.
"""
import argparse
import json
import os
import sys

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TIMEOUT = 45


def _rows_for(site, company):
    """Current published rows for a company, keyed by table id."""
    if not company:
        return {}
    try:
        r = requests.get(f"{site}/wp-json/layoffs/v1/query",
                         params={"company": company, "per_page": 200},
                         headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return {}
        return {int(x["id"]): x for x in r.json().get("data", []) if x.get("id")}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="comma-separated table row ids")
    ap.add_argument("--action", required=True, choices=("trash", "edit"))
    ap.add_argument("--reason", required=True, help="why (recorded on the suppression list)")
    ap.add_argument("--fields", default="", help='edit only: JSON, e.g. {"job_count": 4500}')
    ap.add_argument("--verify-company", default="", help="company filter used to show before/after")
    ap.add_argument("--apply", action="store_true", help="actually write (otherwise dry run)")
    a = ap.parse_args()

    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not site:
        print("WP_SITE_URL required")
        return 1
    if not a.reason.strip():
        print("a written reason is required — corrections are never anonymous")
        return 1

    ids = [int(x) for x in a.ids.replace(" ", "").split(",") if x]
    fields = {}
    if a.action == "edit":
        try:
            fields = json.loads(a.fields or "{}")
        except ValueError as exc:
            print(f"--fields is not valid JSON: {exc}")
            return 1
        if not fields:
            print("--fields is required for an edit")
            return 1

    before = _rows_for(site, a.verify_company)
    print(f"{'APPLY' if a.apply else 'DRY RUN'}: {a.action} {ids} — {a.reason}")
    for i in ids:
        row = before.get(i)
        if row:
            print(f"  before  id={i}  {row.get('company_name')}  {row.get('job_count')} jobs  "
                  f"{row.get('layoff_date')}  {str(row.get('source_url'))[:70]}")
        else:
            print(f"  before  id={i}  (not visible under --verify-company; it may still exist)")
    if a.action == "edit":
        print(f"  would set: {fields}")

    if not a.apply:
        print("DRY RUN — nothing written. Re-run with --apply to commit.")
        return 0
    if not key:
        print("WP_API_KEY required to apply")
        return 1

    if a.action == "trash":
        payload = {"ids": ids, "reason": a.reason}
        url = f"{site}/wp-json/layoffs/v1/trash"
    else:
        payload = {"reason": a.reason, "edits": [{"id": i, "fields": fields} for i in ids]}
        url = f"{site}/wp-json/layoffs/v1/edit"

    r = requests.post(url, json=payload,
                      headers={"X-Layoff-API-Key": key, **UA}, timeout=TIMEOUT)
    if r.status_code != 200:
        print(f"FAILED: HTTP {r.status_code} {r.text[:400]}")
        return 1
    out = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    print("response:", json.dumps(out, indent=2)[:900])

    # Fail loudly: an id the API could not find or accept means the correction
    # did NOT happen, however healthy the HTTP status looked.
    missed = list(out.get("not_found") or []) + list(out.get("rejected") or [])
    if missed:
        print(f"::error:: ids not applied: {missed}")
        return 1

    after = _rows_for(site, a.verify_company)
    for i in ids:
        row = after.get(i)
        if a.action == "trash":
            print(f"  after   id={i}  {'STILL PRESENT (!)' if row else 'gone — correction applied'}")
            if row:
                return 1
        elif row:
            print(f"  after   id={i}  {row.get('company_name')}  {row.get('job_count')} jobs  "
                  f"{row.get('layoff_date')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
