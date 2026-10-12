"""BLS JOLTS + CPS puller: reference data, the MACRO CONTEXT layer.

WHAT THIS IS
------------
A keyless puller for two official US Bureau of Labor Statistics surveys,
through the public BLS API v1 (https://api.bls.gov/publicAPI/v1/):

  * JOLTS (Job Openings and Labor Turnover Survey): monthly LEVELS, in
    thousands, of layoffs and discharges (LD), job openings (JO) and quits
    (QU), for total nonfarm, each NAICS supersector, and the four Census
    regions. Seasonally adjusted.
  * CPS (Current Population Survey): the monthly unemployment RATE (percent)
    by sex, age band, race / Hispanic ethnicity and educational attainment.
    Seasonally adjusted.

IMPORTANT LABELING
------------------
Like the jobless-claims backdrop (sources/claims.py), this is labelled macro
context. JOLTS layoffs are economy-wide separations from all causes, estimated
from a survey; they are NEVER summed into, blended with or compared one-to-one
against the tracker's documented layoff rows, and nothing here touches ingest
or event classification.

THE REQUEST BUDGET
------------------
Keyless v1 allows 25 requests per day per IP, 25 series per request and ten
years per request. SERIES below is batched 25 at a time, so a full refresh of
ten years is ceil(len(SERIES) / 25) requests (3 today). The collector runs
weekly, so it spends 3 of 25 once a week. `request_count()` is pinned by a test
so a later edit cannot quietly blow through the budget.

LICENCE
-------
BLS data are US Government works in the public domain (17 U.S.C. 105). No
permission is needed; BLS asks to be cited as the source, which ATTRIBUTION
does wherever the data is served.

Stdlib + `requests` only. Network code is thin; parsing is pure and tested
offline against a recorded API response.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
HEADERS = {
    "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)",
    "Content-Type": "application/json",
}

SOURCE = "bls_jolts_cps"
LICENCE = "Public domain (US Government work, 17 U.S.C. 105)"
ATTRIBUTION = ("Source: U.S. Bureau of Labor Statistics, Job Openings and Labor "
               "Turnover Survey (JOLTS) and Current Population Survey (CPS). "
               "Public domain.")

#: v1 limits (https://www.bls.gov/developers/api_faqs.htm).
MAX_SERIES_PER_REQUEST = 25
MAX_YEARS_PER_REQUEST = 10
DAILY_REQUEST_LIMIT = 25

# --------------------------------------------------------------------------
# Series catalogue
# --------------------------------------------------------------------------
# JOLTS id layout (since the 2020 redesign), 21 characters:
#   JT + S (seasonal) + industry(6) + state/region(2) + area(5) + size(2)
#      + data element(2) + rate/level(1)
JOLTS_ELEMENTS = {"LD": "layoffs_discharges", "JO": "openings", "QU": "quits"}

JOLTS_INDUSTRIES = {
    "000000": "Total nonfarm",
    "100000": "Total private",
    "110099": "Mining and logging",
    "230000": "Construction",
    "300000": "Manufacturing",
    "400000": "Trade, transportation, and utilities",
    "510000": "Information",
    "510099": "Financial activities",
    "540099": "Professional and business services",
    "600000": "Private education and health services",
    "700000": "Leisure and hospitality",
    "810000": "Other services",
    "900000": "Government",
}

JOLTS_REGIONS = {"NE": "Northeast", "SO": "South", "MW": "Midwest", "WE": "West"}


def jolts_id(element: str, industry: str = "000000", region: str = "00") -> str:
    return f"JTS{industry}{region}0000000{element}L"


def _jolts_series() -> dict:
    out = {}
    for el, measure in JOLTS_ELEMENTS.items():
        for ind, name in JOLTS_INDUSTRIES.items():
            out[jolts_id(el, ind)] = {"dataset": "jolts", "measure": measure,
                                      "unit": "thousands", "dim": "industry",
                                      "naics": ind, "label": name, "geo": "US"}
        for reg, name in JOLTS_REGIONS.items():
            out[jolts_id(el, "000000", reg)] = {"dataset": "jolts", "measure": measure,
                                                "unit": "thousands", "dim": "region",
                                                "naics": "000000", "label": name,
                                                "geo": f"US-{name}"}
    return out


# CPS (LN) unemployment rates, seasonally adjusted.
CPS_SERIES = {
    "LNS14000000": ("total", "16 years and over"),
    "LNS14000001": ("sex", "Men, 16 years and over"),
    "LNS14000002": ("sex", "Women, 16 years and over"),
    "LNS14000012": ("age", "16 to 19 years"),
    "LNS14000036": ("age", "20 to 24 years"),
    "LNS14000089": ("age", "25 to 34 years"),
    "LNS14000091": ("age", "35 to 44 years"),
    "LNS14000093": ("age", "45 to 54 years"),
    "LNS14024230": ("age", "55 years and over"),
    "LNS14000003": ("race", "White"),
    "LNS14000006": ("race", "Black or African American"),
    "LNS14032183": ("race", "Asian"),
    "LNS14000009": ("race", "Hispanic or Latino ethnicity"),
    "LNS14027659": ("education", "Less than a high school diploma, 25 years and over"),
    "LNS14027660": ("education", "High school graduates, no college, 25 years and over"),
    "LNS14027689": ("education", "Some college or associate degree, 25 years and over"),
    "LNS14027662": ("education", "Bachelor's degree and higher, 25 years and over"),
}


def _cps_series() -> dict:
    return {sid: {"dataset": "cps", "measure": "unemployment_rate", "unit": "percent",
                  "dim": dim, "label": label, "geo": "US"}
            for sid, (dim, label) in CPS_SERIES.items()}


SERIES = {**_jolts_series(), **_cps_series()}


def batches(ids=None, size=MAX_SERIES_PER_REQUEST):
    ids = list(SERIES if ids is None else ids)
    return [ids[i:i + size] for i in range(0, len(ids), size)]


def request_count() -> int:
    """Requests one full refresh spends against the keyless daily limit."""
    return len(batches())


# --------------------------------------------------------------------------
# Pure parsing
# --------------------------------------------------------------------------

def parse_series(raw: dict) -> list:
    """BLS v1 `series` object -> [["YYYY-MM", value, flag], ...] ascending.

    Skips annual averages (M13) and non-numeric values ("-" marks a value BLS
    did not publish). `flag` is "P" for preliminary, else "".
    """
    pts = []
    for d in raw.get("data") or ():
        period = str(d.get("period") or "")
        if not (period.startswith("M") and period[1:].isdigit()):
            continue
        month = int(period[1:])
        if not 1 <= month <= 12:
            continue
        try:
            val = float(str(d.get("value")).replace(",", ""))
        except ValueError:
            continue
        flag = ""
        for fn in d.get("footnotes") or ():
            if isinstance(fn, dict) and fn.get("code") == "P":
                flag = "P"
        if val.is_integer():
            val = int(val)
        pts.append([f"{int(d['year']):04d}-{month:02d}", val, flag])
    pts.sort(key=lambda p: p[0])
    return pts


def parse_response(body: dict) -> tuple:
    """One API response -> ({series_id: points}, [error strings])."""
    errors = []
    status = body.get("status")
    if status != "REQUEST_SUCCEEDED":
        msg = "; ".join(str(m) for m in body.get("message") or ())
        return {}, [f"BLS status {status}: {msg}"[:300]]
    for m in body.get("message") or ():
        errors.append(str(m)[:200])
    out = {}
    for s in (body.get("Results") or {}).get("series") or ():
        sid = s.get("seriesID")
        pts = parse_series(s)
        if sid and pts:
            out[sid] = pts
        elif sid:
            errors.append(f"{sid}: no data")
    return out, errors


def build_payload(series_points: dict, errors: list, now=None) -> dict:
    """Assemble the stored document from parsed points."""
    now = now or datetime.now(timezone.utc)
    datasets = {"jolts": {}, "cps": {}}
    latest = {}
    rows = 0
    for sid, pts in series_points.items():
        meta = SERIES.get(sid)
        if not meta or not pts:
            continue
        ds = meta["dataset"]
        datasets[ds][sid] = {**{k: v for k, v in meta.items() if k != "dataset"},
                             "points": pts}
        rows += len(pts)
        if pts[-1][0] > latest.get(ds, ""):
            latest[ds] = pts[-1][0]
    missing = sorted(set(SERIES) - set(series_points))
    return {
        "source": SOURCE,
        "updated": now.isoformat(),
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "url": "https://www.bls.gov/jlt/ ; https://www.bls.gov/cps/",
        "label": ("Macro context: official BLS survey estimates. Not layoffs we "
                  "verified; never summed into tracker counts."),
        "latest": latest,
        "rows": rows,
        "series_count": sum(len(v) for v in datasets.values()),
        "missing_series": missing,
        "datasets": datasets,
        "errors": list(errors),
    }


# --------------------------------------------------------------------------
# Network (thin)
# --------------------------------------------------------------------------

def fetch(years: int = MAX_YEARS_PER_REQUEST, today=None, post=None, timeout=60) -> dict:
    """Fetch every series, ceil(len/25) requests, and return the payload.

    A request that fails outright is recorded in `errors` and flagged in
    `failed_requests`; the caller decides not to overwrite stored data then.
    """
    if post is None:
        import requests
        post = requests.post
    today = today or date.today()
    end = today.year
    start = end - min(years, MAX_YEARS_PER_REQUEST) + 1
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
    payload["requests"] = len(batches())
    return payload
