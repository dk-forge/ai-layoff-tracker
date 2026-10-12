"""OECD monthly unemployment rate by sex and age: reference data, MACRO CONTEXT.

WHAT THIS IS
------------
A keyless puller for the OECD Data Explorer SDMX REST API, dataflow
`OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0` (Infra-annual labour statistics,
monthly unemployment rates): the seasonally adjusted unemployment rate, as a
percent of the labour force in the same subgroup, for every reporting member
country (plus OECD/EU aggregates), by sex (total / men / women) and age band.

One request returns everything (empty REF_AREA, SEX and AGE dimensions are
wildcards). The collector keeps a trailing window in the stored document; the
monthly archive (oecd_archive.py) takes the full history into git.

IMPORTANT LABELING
------------------
Labelled macro context, like sources/claims.py and sources/bls_jolts_cps.py.
Never summed into, blended with or compared one-to-one against the tracker's
layoff rows; nothing here touches ingest or event classification.

LICENCE
-------
OECD data are CC BY 4.0 since 2024 (https://www.oecd.org/en/about/terms-conditions.html).
ATTRIBUTION is REQUIRED and travels with the data wherever it is served.

Stdlib only. Parsing is pure and tested offline against a recorded response.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from datetime import date, datetime, timezone

SOURCE = "oecd_unemployment"
DATAFLOW = "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0"
# REF_AREA.MEASURE.UNIT_MEASURE.TRANSFORMATION.ADJUSTMENT.SEX.AGE.ACTIVITY.FREQ
KEY = ".UNE_LF_M.._Z.Y..._Z.M"
API = f"https://sdmx.oecd.org/public/rest/data/{DATAFLOW}/{KEY}"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

LICENCE = "CC BY 4.0"
ATTRIBUTION = ("Source: OECD (2026), Infra-annual labour statistics, monthly "
               "unemployment rates (DF_IALFS_UNE_M), OECD Data Explorer. "
               "Licensed under CC BY 4.0.")
#: Trailing months kept in the stored (served) document.
WINDOW_MONTHS = 60

SEXES = {"_T": "total", "M": "men", "F": "women"}


def url(start: str | None = None) -> str:
    q = "format=csvfile"
    if start:
        q += f"&startPeriod={start}"
    return f"{API}?{q}"


def parse_csv(text: str) -> list:
    """SDMX csv -> sorted [(area, sex, age, "YYYY-MM", value)].

    Keeps monthly, seasonally adjusted, rate observations only; anything else
    (a blank value, a quarterly period) is dropped rather than guessed at.
    """
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("MEASURE") not in (None, "UNE_LF_M") or r.get("FREQ") not in (None, "M"):
            continue
        if r.get("ADJUSTMENT") not in (None, "Y"):
            continue
        per = (r.get("TIME_PERIOD") or "").strip()
        if not (len(per) == 7 and per[4] == "-" and per[:4].isdigit()
                and per[5:].isdigit() and 1 <= int(per[5:]) <= 12):
            continue
        try:
            val = float(r.get("OBS_VALUE") or "")
        except ValueError:
            continue
        area, sex, age = r.get("REF_AREA") or "", r.get("SEX") or "", r.get("AGE") or ""
        if not (area and sex and age):
            continue
        out.append((area, sex, age, per, round(val, 2)))
    out.sort()
    return out


def to_csv(rows) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ref_area", "sex", "age", "month", "unemployment_rate_pct"])
    w.writerows(rows)
    return buf.getvalue()


def build_payload(rows, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    areas = {}
    latest = ""
    for area, sex, age, per, val in rows:
        areas.setdefault(area, {}).setdefault(f"{sex}|{age}", []).append([per, val])
        latest = max(latest, per)
    countries = sorted(areas)
    return {
        "source": SOURCE,
        "updated": now.isoformat(),
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "url": "https://data-explorer.oecd.org/",
        "dataflow": DATAFLOW,
        "label": ("Macro context: official OECD unemployment rates (percent, "
                  "seasonally adjusted). Not layoffs we verified; never summed "
                  "into tracker counts."),
        "unit": "percent of labour force in the same subgroup",
        "series_key": "sex|age (sex: _T total, M men, F women; age e.g. Y_GE15, Y15T24, Y25T74)",
        "latest": {"monthly": latest} if latest else {},
        "rows": len(rows),
        "countries": countries,
        "datasets": {"monthly": areas},
        "errors": [],
    }


def window_start(today=None, months=WINDOW_MONTHS) -> str:
    today = today or date.today()
    idx = today.year * 12 + today.month - 1 - months
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def fetch_csv(start: str | None = None, timeout=180, opener=None) -> str:
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(url(start), headers={"User-Agent": UA,
                                                      "Accept": "text/csv,*/*"})
    with opener(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")
