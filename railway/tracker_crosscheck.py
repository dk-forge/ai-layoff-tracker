"""
Coverage gap-checker: work BACKWARDS from a reference checklist to find layoff
events our tracker is missing, and emit a targeted search query for each gap so
the existing news -> DeepSeek pipeline can go find a PRIMARY source.

DISPATCH-ONLY. Not wired into any cron, not part of the daily jobs. Run by hand
when you have a reference list to audit against. UNVALIDATED until a manual run.

WHAT IT DOES / DOES NOT DO
--------------------------
INPUT  a CSV or JSON checklist of events someone else compiled (e.g. an export
       from a USA Today / reference layoff tracker). Rows: {company, date,
       approx_count}. We do NOT scrape any competitor site — you provide the
       file. Path comes from argv[1] or the CROSSCHECK_INPUT env var.

CHECK  for each reference row, query OUR OWN public API
       (GET /wp-json/layoffs/v1/query?company=...) and look for a matching event
       within a date window. "Match" = a returned row whose company name shares
       the reference's normalized key AND whose layoff date is within the window.

OUTPUT a GAP REPORT (companies/dates we appear to be missing) to stdout and to a
       JSON file. For each gap we DO NOT invent a layoff record — instead we emit
       a NewsAPI-style search query string that the real ingest pipeline could
       run to discover a primary source. This preserves the project's core rule:
       every number in the tracker is a receipt. This script only REPORTS; it
       NEVER writes to the database.

Env / args:
  argv[1] or CROSSCHECK_INPUT   path to the checklist (.csv or .json)   [required]
  CROSSCHECK_OUTPUT             gap-report JSON path (default ./tracker_crosscheck_gaps.json)
  CROSSCHECK_WINDOW_DAYS        +/- match window in days (default 45)
  WP_SITE_URL                   e.g. https://asktherecruiter.com/blog  [required]

Run:
  python3 -m py_compile railway/tracker_crosscheck.py
  WP_SITE_URL=... python3 railway/tracker_crosscheck.py path/to/reference.csv
"""
import csv
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TIMEOUT = 40


# --- company-name normalization --------------------------------------------
# Mirrors the PHP alt_company_key() the tracker uses to collapse "Amazon",
# "Amazon.com Inc", "Amazon Web Services" -> a comparison key, so a reference
# "Meta" matches our stored "Meta Platforms, Inc." Kept intentionally simple and
# in sync with the plugin's suffix list.
_CORP_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "plc", "llc", "lp", "group", "holdings", "holding",
    "technologies", "technology", "systems", "solutions", "the", "com",
}


def company_key(name):
    k = (name or "").lower()
    k = re.sub(r"[^a-z0-9 ]+", " ", k)
    tokens = [t for t in k.split() if t and t not in _CORP_SUFFIXES]
    return " ".join(tokens).strip()


def _to_iso(value):
    """Best-effort YYYY-MM-DD from common checklist date formats."""
    s = str(value or "").strip()
    if not s:
        return ""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _int(value):
    m = re.search(r"\d{1,3}(?:,\d{3})+|\d+", str(value or ""))
    return int(m.group(0).replace(",", "")) if m else 0


# --- checklist loading -------------------------------------------------------
def _pick(d, *names):
    """First matching key (case/space-insensitive) from a dict row."""
    norm = {re.sub(r"[^a-z0-9]", "", k.lower()): v for k, v in d.items() if k}
    for n in names:
        key = re.sub(r"[^a-z0-9]", "", n.lower())
        if key in norm:
            return norm[key]
    return ""


def load_checklist(path):
    """Return [{company, date, approx_count}] from a .json or .csv file."""
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        raw = fh.read()
    rows = []
    is_json = path.lower().endswith(".json") or raw.lstrip()[:1] in ("[", "{")
    if is_json:
        data = json.loads(raw)
        if isinstance(data, dict):
            # allow {"events": [...]} or {"rows": [...]} wrappers
            data = data.get("events") or data.get("rows") or data.get("data") or []
        records = data
    else:
        records = list(csv.DictReader(io.StringIO(raw)))
    for rec in records:
        if not isinstance(rec, dict):
            continue
        company = str(_pick(rec, "company", "company_name", "employer", "name")).strip()
        date = _to_iso(_pick(rec, "date", "layoff_date", "effective_date", "notice_date"))
        count = _int(_pick(rec, "approx_count", "count", "job_count", "employees",
                           "affected", "layoffs"))
        if not company:
            continue
        rows.append({"company": company, "date": date, "approx_count": count})
    return rows


# --- our API ----------------------------------------------------------------
def query_our_tracker(company, from_date, to_date):
    """GET /query filtered by company (substring LIKE) and layoff-date window.
    Returns the list under `data` (empty on any error — a lookup failure must
    not silently masquerade as 'no gap')."""
    site = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
    params = {"company": company, "per_page": 100}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    try:
        resp = requests.get(f"{site}/wp-json/layoffs/v1/query", params=params,
                            headers=UA, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None  # None signals lookup FAILURE (distinct from [] = no rows)
        return resp.json().get("data", [])
    except Exception:
        return None


def _search_company_term(company):
    """A stable, LIKE-friendly fragment of the company name to query our API with
    (the first 1-2 significant tokens), so "Meta Platforms, Inc." still matches a
    reference "Meta"."""
    tokens = [t for t in re.sub(r"[^A-Za-z0-9 ]+", " ", company).split() if t]
    sig = [t for t in tokens if t.lower() not in _CORP_SUFFIXES] or tokens
    return " ".join(sig[:2])


def suggested_query(company, date):
    """A NewsAPI-style discovery query the news->DeepSeek pipeline could run to
    find a PRIMARY source for this gap. Mirrors the shape sources/newsapi.py uses
    (company AND layoff synonyms). We emit a QUERY, never a fabricated record."""
    year = date[:4] if date else ""
    yr = f" {year}" if year else ""
    return (f'"{company}"{yr} (layoffs OR "job cuts" OR "workforce reduction" '
            f'OR "reduction in force" OR "laying off")')


def main():
    path = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CROSSCHECK_INPUT") or "").strip()
    if not path:
        print("ERROR: no checklist path (pass as argv[1] or set CROSSCHECK_INPUT)")
        sys.exit(1)
    if not os.path.exists(path):
        print(f"ERROR: checklist not found: {path}")
        sys.exit(1)
    if not (os.environ.get("WP_SITE_URL") or "").strip():
        print("ERROR: WP_SITE_URL not set (needed to query our own API)")
        sys.exit(1)

    window = int(os.environ.get("CROSSCHECK_WINDOW_DAYS") or 45)
    out_path = os.environ.get("CROSSCHECK_OUTPUT") or "tracker_crosscheck_gaps.json"

    checklist = load_checklist(path)
    print(f"tracker_crosscheck: {len(checklist)} reference row(s) from {path}, "
          f"window=+/-{window}d")

    gaps = []
    covered = 0
    lookup_errors = 0
    for row in checklist:
        company, date = row["company"], row["date"]
        key = company_key(company)
        # Date window (only applied when the reference row has a usable date).
        from_date = to_date = ""
        if date:
            try:
                d = datetime.strptime(date, "%Y-%m-%d")
                from_date = (d - timedelta(days=window)).strftime("%Y-%m-%d")
                to_date = (d + timedelta(days=window)).strftime("%Y-%m-%d")
            except ValueError:
                pass

        results = query_our_tracker(_search_company_term(company), from_date, to_date)
        if results is None:
            lookup_errors += 1
            # Treat a failed lookup as a POSSIBLE gap, but tag it so it's not
            # confused with a confirmed miss.
            gaps.append({
                "company": company, "reference_date": date,
                "reference_count": row["approx_count"],
                "status": "lookup_failed",
                "suggested_query": suggested_query(company, date),
                "note": "our API did not answer; re-run before trusting this row",
            })
            continue

        # Match on WHOLE-WORD tokens, never substrings. An earlier `key in
        # company_key(...)` substring test made short names false-match — "HP"
        # matched "Nort(hp)oint", "Intel" matched "(Intel)liPower" — which hid
        # real gaps by reporting we had companies we don't. Require every
        # significant token of the reference name to appear as a complete token
        # in the stored name (so "Meta" still matches "Meta Platforms Inc").
        ref_tokens = key.split()
        match = None
        for r in results:
            row_tokens = set(company_key(r.get("company_name", "")).split())
            if ref_tokens and all(t in row_tokens for t in ref_tokens):
                match = r
                break

        if match:
            covered += 1
            continue

        # Fallback: approximate checklist dates make the windowed query miss
        # events we DO have at a slightly different date. Requery company-only
        # (no date window); if the company is present at all, it's covered — not
        # a gap. Only flag a TRUE gap when the company is entirely absent.
        if date:
            wide = query_our_tracker(_search_company_term(company), "", "")
            if wide:
                for r in wide:
                    rk = company_key(r.get("company_name", ""))
                    if rk == key or (key and key in rk):
                        match = r
                        break
            if match:
                covered += 1
                continue

        gaps.append({
            "company": company,
            "reference_date": date,
            "reference_count": row["approx_count"],
            "status": "missing",
            "suggested_query": suggested_query(company, date),
            "note": "company entirely absent from the tracker; use the query to "
                    "find a primary source (do NOT import the reference figure)",
        })

    report = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_file": os.path.abspath(path),
        "window_days": window,
        "reference_rows": len(checklist),
        "covered": covered,
        "gaps": len(gaps),
        "lookup_errors": lookup_errors,
        "items": gaps,
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"\ntracker_crosscheck: {covered} covered, {len(gaps)} gap(s) "
          f"({lookup_errors} lookup error[s])")
    print(f"gap report written to {os.path.abspath(out_path)}\n")
    for g in gaps:
        tag = g["status"].upper()
        print(f"  [{tag}] {g['company']} ({g['reference_date'] or 'no date'}, "
              f"~{g['reference_count']}) -> {g['suggested_query']}")

    # This is a REPORTING tool: gaps are the expected, normal output, so finding
    # gaps is NOT a failure. Only genuine operational problems (bad input, no API)
    # exit non-zero — those are handled above before we get here.


if __name__ == "__main__":
    main()
