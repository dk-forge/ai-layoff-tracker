"""BLS CES average weekly hours + average hourly earnings: reference data, MACRO CONTEXT.

WHAT THIS IS
------------
The Current Employment Statistics survey (CES, "the establishment survey")
publishes, for all employees on private nonfarm payrolls, the average weekly
hours worked and the average hourly earnings, monthly, nationally, per NAICS
supersector. Employers often cut hours before headcount, so a falling
workweek in a supersector is the earliest official signal that sits next to
the tracker's layoff rows ("hours cut before headcount", issue #478 item 9).

We read it through the SAME keyless BLS API v1 path as the JOLTS + CPS
collector (sources/bls_jolts_cps.py): same endpoint, same request shape, same
`parse_response`, so a BLS format change breaks one parser, not two. No key:
v1 is keyless (25 requests/day/IP, 25 series and 10 years per request) and no
BLS key is configured, so none is used.

Series id layout: CE + S (seasonally adjusted) + supersector/industry (8)
+ data type (2). Data type 02 = average weekly hours, 03 = average hourly
earnings, both "all employees". 13 supersectors x 2 = 26 series = 2 requests.

IMPORTANT LABELING
------------------
Hours and earnings are survey estimates for all payroll employees. They are
not layoffs, are never summed into or compared one-to-one with the tracker's
rows, and a change here does not show that AI caused it.

LICENCE: US Government work, public domain (17 U.S.C. 105); cite BLS.
Parsing is pure and tested offline against a recorded response shape.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sources import bls_jolts_cps as bls

SOURCE = "bls_ces_hours"
API_URL = bls.API_URL
HEADERS = bls.HEADERS
LICENCE = bls.LICENCE
ATTRIBUTION = ("Source: U.S. Bureau of Labor Statistics, Current Employment "
               "Statistics (CES), average weekly hours and average hourly "
               "earnings of all employees, seasonally adjusted. Public domain.")
NOTE = ("Hours and earnings are survey estimates for all payroll employees. They "
        "are not layoffs, are not added to the tracker's counts, and a change here "
        "does not show that AI caused it.")
URL = "https://www.bls.gov/ces/"

YEARS = 5

SUPERSECTORS = {
    "05000000": "Total private",
    "06000000": "Goods-producing",
    "08000000": "Private service-providing",
    "10000000": "Mining and logging",
    "20000000": "Construction",
    "30000000": "Manufacturing",
    "40000000": "Trade, transportation, and utilities",
    "50000000": "Information",
    "55000000": "Financial activities",
    "60000000": "Professional and business services",
    "65000000": "Private education and health services",
    "70000000": "Leisure and hospitality",
    "80000000": "Other services",
}

MEASURES = {"02": ("avg_weekly_hours", "hours"),
            "03": ("avg_hourly_earnings", "dollars")}


def ces_id(supersector: str, datatype: str) -> str:
    return f"CES{supersector}{datatype}"


SERIES = {ces_id(ss, dt): {"measure": m, "unit": u, "naics_supersector": ss,
                           "label": name, "geo": "US"}
          for dt, (m, u) in MEASURES.items()
          for ss, name in SUPERSECTORS.items()}


def batches(ids=None, size=bls.MAX_SERIES_PER_REQUEST):
    ids = list(SERIES if ids is None else ids)
    return [ids[i:i + size] for i in range(0, len(ids), size)]


def request_count() -> int:
    return len(batches())


def parse_response(body: dict) -> tuple:
    """Reuses the JOLTS/CPS parser: ({series_id: points}, [errors])."""
    return bls.parse_response(body)


def build_payload(series_points: dict, errors: list, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    ces, latest, rows = {}, "", 0
    for sid, pts in series_points.items():
        meta = SERIES.get(sid)
        if not meta or not pts:
            continue
        ces[sid] = {**meta, "points": pts}
        rows += len(pts)
        latest = max(latest, pts[-1][0])
    return {
        "source": SOURCE,
        "updated": now.isoformat(),
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "url": URL,
        "label": "Macro context: official BLS survey estimates. Not layoffs; never summed into tracker counts.",
        "note": NOTE,
        "latest": {"ces": latest} if latest else {},
        "rows": rows,
        "series_count": len(ces),
        "missing_series": sorted(set(SERIES) - set(ces)),
        "datasets": {"ces": ces},
        "errors": list(errors),
    }


def fetch(years: int = YEARS, today=None, post=None, timeout=60) -> dict:
    if post is None:
        import requests
        post = requests.post
    today = today or date.today()
    end = today.year
    start = end - min(years, bls.MAX_YEARS_PER_REQUEST) + 1
    points, errors, failed = {}, [], 0
    for chunk in batches():
        body = json.dumps({"seriesid": chunk, "startyear": str(start), "endyear": str(end)})
        try:
            r = post(API_URL, data=body, headers=HEADERS, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            got, errs = parse_response(r.json())
        except Exception as exc:  # network, JSON, HTTP
            failed += 1
            errors.append(f"request failed for {chunk[0]}..: {exc}"[:300])
            continue
        if not got and errs:
            failed += 1
        points.update(got)
        errors.extend(errs)
    payload = build_payload(points, errors)
    payload["failed_requests"] = failed
    payload["requests"] = request_count()
    return payload
