"""Does an ERM row's stored country still agree with the one it was imported with?

WHY THIS EXISTS. On 2026-08-08 the published "United States jobs, all time"
headline rose 92,686 while the worldwide headline, of which the US slice is a
strict subset, rose 13,264. No arriving row can do that; something already in
the corpus started being counted as US. `updated_at` did not exist yet, so
docs/US_HEADLINE_MOVEMENT_FORENSICS_2026_08.md could not name the rows and
returned UNKNOWN.

It did not need `updated_at`. `erm_import.py` builds each row's excerpt as

    f"{rtype} at {company} ({country}): {jobs:,} announced job losses. "

so every ERM row carries, in its own published text, the country it was
IMPORTED with. That text is written once and never rewritten. Comparing it to
the stored `country` column asks "has this row been re-scored since it was
imported?" without any history table, any snapshot, and any timestamp — and it
answers for rows that changed long before the schema learned to record when.

Run against the live site it found exactly three contradictions in 19,494 ERM
rows (114335 Citigroup 52,000, 113529 General Motors 47,000, 64351 Cinemaworld
45,000), all three re-scored from "Multiple countries" to "United States", all
three `edited: true`, and all three carrying `Country: World` on their own cited
Eurofound factsheet. 144,000 jobs.

WHAT IT CANNOT DO. It sees ERM rows only, because ERM is the one importer that
writes its country into the excerpt. It cannot see a re-scoring that also
rewrote the excerpt, and it cannot date the change — it says the row disagrees
with its own provenance, not when it started to. A legitimate editorial
correction of a genuinely wrong country will also show up here; that is the
right behaviour for a check that exists to surface silent re-scoring, and the
correction should say so in the corrections log rather than be hidden by
loosening this.

Read-only against the site: it calls /query, which is public, and changes no
row. `--write` writes ONE local file, the committed measurement below.

    python3 railway/erm_provenance_check.py
    python3 railway/erm_provenance_check.py --json
    python3 railway/erm_provenance_check.py --write   # + erm_provenance_measurement.json

WHY THE DASHBOARD READS A COMMITTED MEASUREMENT AND NOT THIS SCAN
-----------------------------------------------------------------
/query has no source_type filter, so answering this question at all means
paging the WHOLE published corpus — 63,620 rows at 200 a page, 319 requests,
and MEASURED AT ~25 MINUTES against the live host on 2026-08-12. `check_all()`
is on the critical path of every session's first command and is documented as
about one round trip; putting a 25-minute scan inside it would stop anybody
running ops_status, which is the one habit every other guard here depends on.

So this follows the shape RecallFloorInvariant already uses for the same
reason: a scheduled job re-measures and COMMITS the result, and
data_integrity.ErmProvenanceInvariant reads the committed file. The cost is
stated rather than hidden — a silent re-scoring is caught within a WEEK, not
within a day. That is the cadence erm-provenance-check.yml actually runs at,
and a ceiling a job cannot meet is not a monitor, it is noise that hides real
breakage.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = "https://asktherecruiter.com/blog"
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
PER_PAGE = 200
TIMEOUT = 120

HERE = Path(__file__).resolve().parent
# Committed, for the same reason as railway/headline_baseline.json and
# railway/recall_measurement.json: the thing being watched changes without a
# commit, so a result that lives only in a runner resets every night.
MEASUREMENT_PATH = HERE / "erm_provenance_measurement.json"

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"

# erm-provenance-check.yml runs WEEKLY. 7 + 2 days of slack for a missed or
# failed run, matching recall_goldset.MAX_MEASUREMENT_AGE_DAYS and the rule in
# CLAUDE.md: a staleness ceiling must match the job's real cadence.
MAX_MEASUREMENT_AGE_DAYS = 9

# An ERM row whose excerpt cannot be parsed is UNCHECKED, and this check has no
# way to say anything about it. The live measurement is 0 of 19,497, because
# EXCERPT_COUNTRY_RX was fixed to read the company names that carry their own
# brackets — so any unreadable row means erm_import.py's excerpt sentence has
# changed shape and this check has quietly stopped covering part of the corpus.
# That is UNKNOWN, which is a third state, not a pass.
UNREADABLE_CEILING = 0

# The country the importer wrote, read back out of the sentence it wrote it
# into. Anchored on "): <n> announced job losses" and not on the first
# parenthesis in the string, because company names carry their own brackets
# ("Zespol Elektrowni Patnow-Adamow-Konin (ZE PAK) (Poland): 700 announced job
# losses"). Anchoring on the first one silently failed to parse 459 of 19,494
# rows, and a check that cannot parse a row must not quietly call it clean.
EXCERPT_COUNTRY_RX = re.compile(r"\(([^()]+)\):\s+[\d,]+\s+announced job losses")


def excerpt_country(excerpt):
    """The country an ERM excerpt was written with, or None if it cannot be read."""
    m = EXCERPT_COUNTRY_RX.search(str(excerpt or ""))
    return m.group(1).strip() if m else None


def contradictions(rows):
    """Rows whose stored country disagrees with their own import-time excerpt.

    Returns (contradictions, unreadable). `unreadable` is every ERM row whose
    excerpt could not be parsed at all: those are UNCHECKED, not clean, and the
    caller has to see them as their own number.
    """
    bad, unreadable = [], []
    for r in rows:
        if (r.get("source_type") or "") != "erm":
            continue
        imported = excerpt_country(r.get("excerpt"))
        if imported is None:
            unreadable.append(r)
            continue
        stored = str(r.get("country") or "").strip()
        if imported != stored:
            bad.append({"id": r.get("id"), "company": r.get("company_name"),
                        "jobs": int(r.get("job_count") or 0),
                        "imported_country": imported, "stored_country": stored,
                        "edited": bool(r.get("edited"))})
    bad.sort(key=lambda x: -x["jobs"])
    return bad, unreadable


def _get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=TIMEOUT).read())
        except Exception as e:                                  # noqa: BLE001
            last = e
            time.sleep(2 + 3 * i)
    raise RuntimeError(f"{url} :: {last}")


def fetch_rows(site=SITE):
    """Every published row, one page at a time. /query has no source_type filter."""
    base = site.rstrip("/") + "/wp-json/layoffs/v1/query?"
    head = _get(base + urllib.parse.urlencode({"per_page": 1, "page": 1, "cb": "erm0"}))
    total = int(head.get("total") or 0)
    out = []
    for page in range(1, (total + PER_PAGE - 1) // PER_PAGE + 1):
        d = _get(base + urllib.parse.urlencode(
            {"per_page": PER_PAGE, "page": page, "cb": f"erm{page}"}))
        out.extend(d.get("data") or [])
    return out


def load_measurement(path=None):
    try:
        return json.loads(Path(path or MEASUREMENT_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _days_since(stamp, now=None):
    if not stamp:
        return None
    try:
        when = datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return max(0.0, ((now or datetime.now(timezone.utc)) - when).total_seconds() / 86400.0)


def judge(measurement, now=None):
    """(state, detail) for one measurement. The single definition of the bound.

    Imported by data_integrity.ErmProvenanceInvariant and by this module's own
    exit code, so what reddens CI and what the dashboard prints cannot drift
    apart. PASS / FAIL / UNKNOWN, never two of them.
    """
    if not isinstance(measurement, dict):
        return UNKNOWN, ("no ERM provenance measurement has been written yet — whether "
                         "any published ERM row still agrees with the country it was "
                         "imported with is UNMEASURED, not fine. erm-provenance-check.yml "
                         "writes railway/erm_provenance_measurement.json weekly; run "
                         "`python3 railway/erm_provenance_check.py --write` to seed it")
    rows = measurement.get("erm_rows")
    unreadable = measurement.get("unreadable")
    bad = measurement.get("contradictions")
    if not isinstance(rows, int) or not isinstance(unreadable, int) or not isinstance(bad, list):
        return UNKNOWN, f"unreadable ERM provenance measurement: {measurement!r}"

    age = _days_since(measurement.get("measured_at"), now)
    if age is None:
        return UNKNOWN, (f"measurement has no readable timestamp: "
                         f"{measurement.get('measured_at')!r}")
    if age > MAX_MEASUREMENT_AGE_DAYS:
        return UNKNOWN, (f"the ERM provenance measurement is {age:.0f} days old (max "
                         f"{MAX_MEASUREMENT_AGE_DAYS}) — either this checkout is behind "
                         f"main or erm-provenance-check.yml has stopped. ERM provenance "
                         f"is UNVERIFIED, not passing")
    if rows <= 0:
        return FAIL, ("0 ERM rows were found in the published data — 19,000+ rows do not "
                      "vanish legitimately, so either the ERM corpus is gone or /query "
                      "stopped labelling them")
    if unreadable > UNREADABLE_CEILING:
        return UNKNOWN, (f"{unreadable:,} of {rows:,} ERM excerpts could not be parsed "
                         f"(ceiling {UNREADABLE_CEILING}) — those rows are UNCHECKED, not "
                         f"clean. erm_import.py's excerpt sentence has probably changed "
                         f"shape; re-read EXCERPT_COUNTRY_RX before trusting this check "
                         f"again")
    if bad:
        jobs = sum(int(x.get("jobs") or 0) for x in bad)
        who = "; ".join(f"row {x.get('id')} {x.get('company')} {int(x.get('jobs') or 0):,} "
                        f"imported as {x.get('imported_country')!r}, now stored as "
                        f"{x.get('stored_country')!r}" for x in bad[:4])
        return FAIL, (f"{len(bad)} published ERM row(s) carrying {jobs:,} jobs disagree with "
                      f"the country written into their OWN import-time excerpt — they were "
                      f"re-scored after publication. {who}. Check the corrections log and "
                      f"the last daily_classification_spotcheck run; this is the shape of "
                      f"the 2026-08-08 US headline incident")
    return PASS, (f"all {rows:,} published ERM rows still carry the country they were "
                  f"imported with (0 unreadable)")


def measurement_from(rows):
    """The committed record, from one full pass over the published rows."""
    erm = [r for r in rows if (r.get("source_type") or "") == "erm"]
    bad, unreadable = contradictions(rows)
    return {
        "note": ("Does each published ERM row's stored country still agree with the "
                 "country erm_import.py wrote into that row's own excerpt? Written by "
                 "erm-provenance-check.yml, read by data_integrity.ErmProvenanceInvariant. "
                 "Committed because the data changes without a commit."),
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "erm_rows": len(erm),
        "unreadable": len(unreadable),
        "contradictions": bad,
        "jobs": sum(x["jobs"] for x in bad),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true",
                    help="also write railway/erm_provenance_measurement.json")
    ap.add_argument("--measurement-path", default=None)
    ap.add_argument("--site", default=SITE)
    a = ap.parse_args(argv)

    rows = fetch_rows(a.site)
    record = measurement_from(rows)
    erm = [r for r in rows if (r.get("source_type") or "") == "erm"]
    bad, unreadable = contradictions(rows)
    jobs = record["jobs"]

    if a.write:
        path = Path(a.measurement_path or MEASUREMENT_PATH)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        print(f"measurement written: {path}")

    if a.json:
        print(json.dumps({"erm_rows": len(erm), "contradictions": bad,
                          "unreadable": len(unreadable), "jobs": jobs}, indent=2))
    else:
        print(f"ERM rows checked : {len(erm):,}")
        print(f"unreadable       : {len(unreadable):,} (UNCHECKED, not clean)")
        print(f"contradictions   : {len(bad):,}  carrying {jobs:,} jobs")
        for x in bad:
            print(f"    id={x['id']} {x['jobs']:>8,}  imported as "
                  f"{x['imported_country']!r}, now stored as {x['stored_country']!r}"
                  f"  ({x['company']}, edited={x['edited']})")

    # Through judge(), so this exit code and the dashboard's verdict are the
    # same sentence. 0 pass / 2 fail / 3 unknown, matching data_integrity.py —
    # an UNKNOWN run has not verified anything and must not exit clean.
    state, detail = judge(record)
    print(f"{state.upper()}: {detail}")
    return {PASS: 0, FAIL: 2, UNKNOWN: 3}[state]


if __name__ == "__main__":
    sys.exit(main())
