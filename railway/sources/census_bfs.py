"""Census Business Formation Statistics (BFS): reference data, MACRO CONTEXT.

WHAT THIS IS
------------
The U.S. Census Bureau publishes Business Formation Statistics as one public
CSV, keyless: https://www.census.gov/econ/bfs/csv/bfs_monthly.csv (columns
sa, naics_sector, series, geo, year, jan..dec). We keep the SEASONALLY
ADJUSTED (`sa == "A"`), all-sector (`naics_sector == "TOTAL"`) rows of two
series:

* `BA_BA`  - business applications (all EIN applications)
* `BA_HBA` - high-propensity business applications (likely employers)

for every geography in the file (US, the states, DC and the census regions),
one value per month over a trailing window. "NA" and blank cells are skipped.

IMPORTANT LABELING
------------------
Business applications measure intent to start a business. They are not
layoffs, are never summed into, blended with or compared one-to-one against
the tracker's layoff rows, and nothing here says AI caused a change.

SHAPE: datasets.monthly = [[geo, series, month, value], ...], `fields` names
the columns; GET /reference/census_bfs?geo=CA&series=BA_BA filters rows.
Stdlib only; parsing is pure and tested offline.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from datetime import date, datetime, timezone

SOURCE = "census_bfs"
URL = "https://www.census.gov/econ/bfs/csv/bfs_monthly.csv"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
WINDOW_YEARS = 3
SERIES = ("BA_BA", "BA_HBA")
NATIONAL = "US"
FIELDS = ["geo", "series", "month", "value"]
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec")

ATTRIBUTION = ("Source: U.S. Census Bureau, Business Formation Statistics "
               "(https://www.census.gov/econ/bfs/). Seasonally adjusted business "
               "applications, all sectors.")
LICENCE = "Public domain (U.S. Government work); cite the U.S. Census Bureau"
NOTE = ("Business applications measure intent to start a business. They are not "
        "layoffs and are not added to the tracker's counts, and a change here does "
        "not show that AI caused it.")


def parse_csv(text, start):
    """[[geo, series, 'YYYY-MM', value], ...] for SA total rows on/after start."""
    out = []
    try:
        for r in csv.DictReader(io.StringIO(text or "")):
            if (r.get("sa") or "").strip() != "A":
                continue
            if (r.get("naics_sector") or "").strip() != "TOTAL":
                continue
            series = (r.get("series") or "").strip()
            geo = (r.get("geo") or "").strip()
            if series not in SERIES or not geo:
                continue
            try:
                year = int((r.get("year") or "").strip())
            except ValueError:
                continue
            for i, m in enumerate(MONTHS, start=1):
                if date(year, i, 1) < start:
                    continue
                try:
                    v = float((r.get(m) or "").replace(",", "").strip())
                except ValueError:
                    continue
                out.append([geo, series, f"{year:04d}-{i:02d}", int(v) if v.is_integer() else v])
    except csv.Error:
        return []
    return sorted(out, key=lambda x: (x[0], x[1], x[2]))


def window_start(today=None):
    today = today or datetime.now(timezone.utc).date()
    return date(today.year - WINDOW_YEARS, today.month, 1)


def build_payload(text, today=None, errors=None):
    rows = parse_csv(text, window_start(today))
    latest = max((r[2] for r in rows if r[0] == NATIONAL), default=None)
    return {
        "source": SOURCE,
        "updated": datetime.now(timezone.utc).isoformat(),
        "fields": FIELDS,
        "datasets": {"monthly": rows},
        "rows": len(rows),
        "geos": sorted({r[0] for r in rows}),
        "series": sorted({r[1] for r in rows}),
        "latest": {"monthly": latest} if latest else {},
        "attribution": ATTRIBUTION,
        "licence": LICENCE,
        "note": NOTE,
        "errors": list(errors or []),
    }


def fetch(opener=urllib.request.urlopen, timeout=90):
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with opener(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def pull(today=None, opener=urllib.request.urlopen):
    errors = []
    try:
        text = fetch(opener)
    except Exception as exc:  # network: record and let should_store refuse
        errors.append(f"bfs_monthly.csv: {type(exc).__name__}: {str(exc)[:200]}")
        text = ""
    return build_payload(text, today, errors)
