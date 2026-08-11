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

Read-only: it calls /query, which is public, and writes nothing.

    python3 railway/erm_provenance_check.py
    python3 railway/erm_provenance_check.py --json
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://asktherecruiter.com/blog"
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
PER_PAGE = 200
TIMEOUT = 120

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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--site", default=SITE)
    a = ap.parse_args(argv)

    rows = fetch_rows(a.site)
    erm = [r for r in rows if (r.get("source_type") or "") == "erm"]
    bad, unreadable = contradictions(rows)
    jobs = sum(x["jobs"] for x in bad)

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
    return 1 if (bad or unreadable) else 0


if __name__ == "__main__":
    sys.exit(main())
