"""Apply a signed-off editorial correction to specific published rows.

The audit protocol (docs/RUNBOOK.md "quarterly source-verification audit")
produces a short list of rows whose stored facts do not match their own cited
source. Published corrections governance says a numeric change ALWAYS needs a
human sign-off, so this is deliberately a manual, dispatch-only tool: it never
runs on a schedule and it refuses to do anything without a written reason.

Four actions, matching the four things a review can conclude:

    trash        - the row's number is not supported by its source at all (the
                   count belongs to a different event, or the source states no
                   count). The row is removed and its dedup hash SUPPRESSED, so
                   the nightly re-scrape of the same page cannot resurrect it.
    edit         - the row is real but a field is wrong. /edit pins the row and
                   suppresses the original hash so an import cannot revert it.
    move-sources - the row is right and its ATTACHED EVIDENCE is wrong: source
                   links describing a different event were merged onto it (the
                   pre-2.20.161 count-blind fuzzy merge). /move-source-reports
                   moves the named links to the row whose event they describe
                   and appends to the public corrections log. --ids names the
                   ONE row the links leave; --fields {"to_id": N, "urls": [...]}.
    add          - a real event the ingest lost and cannot re-read (its URLs are
                   already held as source reports, so the seen-URL pre-check
                   skips them forever). The row goes through /add, the same door
                   every collector uses, so every server guard runs: exact hash,
                   suppression list, the count-aware fuzzy merge, the rebadge
                   guard. --fields is the entry JSON; the dedup hash is derived
                   here exactly as extractor.py derives it, never typed.

Every path fails loudly (non-zero exit) on any not-found or rejected id, so a
correction that silently did nothing can never be reported as applied.

    WP_SITE_URL=... WP_API_KEY=... python3 railway/apply_correction.py \
        --ids 70289 --action trash --reason "audit #1: source states no count" \
        --verify-company Starbucks

Add --apply to actually write; without it the run is a DRY RUN that only shows
what would change.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import uuid

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TIMEOUT = 45


def dedup_hash(company_name, layoff_date, job_count):
    """The extractor's dedup hash, byte for byte (extractor.py, "Dedup hash").

    Kept here rather than imported because extractor.py imports openai at
    module level and this tool runs on the minimal lock. tests pin the two
    formulas against each other by executing both.
    """
    hash_input = f"{company_name.lower().strip()}{layoff_date or ''}{int(job_count)}"
    return hashlib.md5(hash_input.encode("utf-8")).hexdigest()


def _rows_for(site, company):
    """Current published rows for a company, keyed by table id."""
    if not company:
        return {}
    try:
        # cb= is not optional: /query responses are cached, and a stale hit
        # made the first real correction report "STILL PRESENT" after the row
        # had in fact been trashed — a false alarm on a fail-loudly check.
        r = requests.get(f"{site}/wp-json/layoffs/v1/query",
                         params={"company": company, "per_page": 200,
                                 "cb": str(uuid.uuid4())},
                         headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return {}
        return {int(x["id"]): x for x in r.json().get("data", []) if x.get("id")}
    except Exception:
        return {}


def _event_sources(site, row_id):
    """Every retained source report on a row's event (public route), or None
    when the read failed - None is UNKNOWN and is printed as such, never as
    "no sources"."""
    try:
        r = requests.get(f"{site}/wp-json/layoffs/v1/event/{int(row_id)}/sources",
                         params={"cb": str(uuid.uuid4())}, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        return list(r.json().get("sources") or [])
    except Exception:
        return None


def _totals(site):
    """The published worldwide headline (jobs, entries), or None when unread."""
    try:
        r = requests.get(f"{site}/wp-json/layoffs/v1/aggregate",
                         params={"cb": str(uuid.uuid4())}, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        t = r.json().get("totals") or {}
        return int(t.get("jobs", 0)), int(t.get("entries", 0))
    except Exception:
        return None


def _print_sources(label, sources, moving=None):
    if sources is None:
        print(f"  {label}: UNKNOWN (the /event/<id>/sources read failed)")
        return
    print(f"  {label}: {len(sources)} source report(s)")
    for s in sources:
        url = str(s.get("source_url") or "")
        tag = ""
        if moving is not None:
            tag = "MOVE  " if url in moving else "stay  "
        print(f"    {tag}{s.get('source_name')}  {url[:90]}")
        ex = (s.get("excerpt") or "").replace("\n", " ")
        if ex:
            print(f"          \"{ex[:110]}\"")


def _fail(msg):
    print(f"::error:: {msg}")
    return 1


def run_move_sources(site, key, ids, fields, reason, apply):
    if len(ids) != 1:
        return _fail("move-sources takes exactly one id: the row the links leave")
    from_id = ids[0]
    to_id = int(fields.get("to_id") or 0)
    urls = [str(u).strip() for u in (fields.get("urls") or []) if str(u).strip()]
    if not to_id or to_id == from_id:
        return _fail("--fields must carry to_id, a different row than --ids")
    if not urls:
        return _fail("--fields must carry a non-empty urls list")

    before_from = _event_sources(site, from_id)
    before_to = _event_sources(site, to_id)
    print(f"{'APPLY' if apply else 'DRY RUN'}: move-sources {from_id} -> {to_id} — {reason}")
    _print_sources(f"before  row {from_id}", before_from, moving=set(urls))
    _print_sources(f"before  row {to_id}", before_to)
    if before_from is not None:
        held = {str(s.get("source_url") or "") for s in before_from}
        missing = [u for u in urls if u not in held]
        if missing:
            print(f"  {len(missing)} requested url(s) are NOT attached to row {from_id}:")
            for u in missing:
                print(f"    {u[:110]}")
            return _fail("refusing: every url must be a report currently held by the from-row")
    print(f"  would move {len(urls)} link(s); the rows' own facts (count, date, country) are untouched")

    if not apply:
        print("DRY RUN — nothing written. Re-run with --apply to commit.")
        return 0
    if not key:
        print("WP_API_KEY required to apply")
        return 1
    r = requests.post(f"{site}/wp-json/layoffs/v1/move-source-reports",
                      json={"from_id": from_id, "to_id": to_id, "urls": urls, "reason": reason},
                      headers={"X-Layoff-API-Key": key, **UA}, timeout=TIMEOUT)
    if r.status_code != 200:
        print(f"FAILED: HTTP {r.status_code} {r.text[:400]}")
        return 1
    out = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    print("response:", json.dumps(out, indent=2)[:1200])
    missed = list(out.get("not_found") or []) + list(out.get("refused") or [])
    if missed or len(out.get("moved") or []) != len(urls):
        return _fail(f"links not moved: {missed or 'count mismatch'}")

    time.sleep(3)
    _print_sources(f"after   row {from_id}", _event_sources(site, from_id))
    _print_sources(f"after   row {to_id}", _event_sources(site, to_id))
    return 0


ADD_REQUIRED = ("company_name", "job_count", "layoff_date", "source_url", "source_name")


def run_add(site, key, fields, reason, apply):
    for k in ADD_REQUIRED:
        if not fields.get(k):
            return _fail(f"add needs {', '.join(ADD_REQUIRED)}; missing {k}")
    entry = dict(fields)
    entry["job_count"] = int(entry["job_count"])
    entry.setdefault("source_type", "news")
    entry.setdefault("verification_level", "bronze")
    entry.setdefault("review_status", "provisional")
    entry["dedup_hash"] = dedup_hash(entry["company_name"], entry["layoff_date"], entry["job_count"])

    print(f"{'APPLY' if apply else 'DRY RUN'}: add — {reason}")
    print("  row as it will be sent to /add (server normalises country/industry through the fixed vocabularies):")
    for k, v in entry.items():
        print(f"    {k:26} {json.dumps(v, ensure_ascii=False)[:160]}")
    before = _totals(site)
    if before is None:
        print("  headline before: UNKNOWN (aggregate unread)")
    else:
        print(f"  headline before: worldwide {before[0]:,} jobs over {before[1]:,} entries")
        print(f"  headline after (if stored): worldwide {before[0] + entry['job_count']:,} jobs over {before[1] + 1:,} entries")
    peers = _rows_for(site, entry["company_name"])
    same = [p for p in peers.values() if str(p.get("layoff_date") or "")[:4] == str(entry["layoff_date"])[:4]]
    print(f"  same-company rows this year: {len(same)} (the count-aware fuzzy merge and the rebadge guard run server-side)")
    for p in same:
        print(f"    id={p['id']}  {p.get('company_name')}  {p.get('job_count')} jobs  {p.get('layoff_date')}  {p.get('country')}")

    if not apply:
        print("DRY RUN — nothing written. Re-run with --apply to commit.")
        return 0
    if not key:
        print("WP_API_KEY required to apply")
        return 1
    from wp_poster import post_to_wordpress   # the ONE poster every collector uses
    verdict = post_to_wordpress(entry)
    if verdict != "posted":
        return _fail(f"/add answered {verdict!r}; nothing stored (a 409 names the row that absorbed it above)")
    time.sleep(3)
    after_rows = _rows_for(site, entry["company_name"])
    new = [p for p in after_rows.values() if p.get("job_count") == entry["job_count"]
           and p.get("layoff_date") == entry["layoff_date"]]
    for p in new:
        print(f"  stored  id={p['id']}  {p.get('company_name')}  {p.get('job_count')} jobs  "
              f"{p.get('layoff_date')}  {p.get('country')}  {p.get('industry')}")
    if not new:
        return _fail("/add said posted but the row is not readable back under its company")
    after = _totals(site)
    if after is not None:
        print(f"  headline after: worldwide {after[0]:,} jobs over {after[1]:,} entries")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="comma-separated table row ids (0 for add)")
    ap.add_argument("--action", required=True, choices=("trash", "edit", "move-sources", "add"))
    ap.add_argument("--reason", required=True, help="why (recorded on the suppression list / corrections log)")
    ap.add_argument("--fields", default="", help='edit: JSON of fields; move-sources: {"to_id", "urls"}; add: the entry JSON')
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
    if a.action in ("edit", "move-sources", "add"):
        try:
            fields = json.loads(a.fields or "{}")
        except ValueError as exc:
            print(f"--fields is not valid JSON: {exc}")
            return 1
        if not fields:
            print(f"--fields is required for {a.action}")
            return 1
    if a.action == "move-sources":
        return run_move_sources(site, key, ids, fields, a.reason, a.apply)
    if a.action == "add":
        return run_add(site, key, fields, a.reason, a.apply)

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

    # Re-read a few times: the write is committed, but a cache layer can still
    # serve the pre-correction page for a moment.
    after = _rows_for(site, a.verify_company)
    if a.action == "trash" and any(i in after for i in ids):
        for _ in range(4):
            time.sleep(6)
            after = _rows_for(site, a.verify_company)
            if not any(i in after for i in ids):
                break
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
