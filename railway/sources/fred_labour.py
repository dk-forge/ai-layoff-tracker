"""FRED (St. Louis Fed) labour trend series: reference data, MACRO CONTEXT.

WHAT THIS IS
------------
A puller for the FRED API (https://fred.stlouisfed.org/docs/api/fred/),
`/fred/series/observations`, for a small curated set of labour series used as
trend lines: unemployment rate, payrolls (USINFO is the CES information
supersector, so CES5000000001 is not a FRED id and is not requested), weekly initial and continued
jobless claims, JOLTS layoffs, information-sector employment, private
average hourly earnings and unemployment for bachelor's degree holders. One
request per series, trailing WINDOW_YEARS. Needs `FRED_API_KEY` (a free key);
the key travels only in the request URL and is scrubbed from every message.

IMPORTANT LABELING
------------------
Labelled macro context, like sources/bls_jolts_cps.py and
sources/oecd_unemployment.py. Never summed into, blended with or compared
one-to-one against the tracker's layoff rows; nothing here touches ingest or
event classification.

SHAPE (flat rows so a display layer can filter on every field)
-----
datasets.observations = [[series_id, date, value, label, category, frequency], ...]
with `fields` naming the columns; GET /reference/fred_labour accepts any field
as a query parameter (e.g. ?series_id=ICSA, ?category=claims).

Stdlib only. Parsing is pure and tested offline.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

SOURCE = "fred_labour"
API = "https://api.stlouisfed.org/fred/series/observations"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
WINDOW_YEARS = 10

ATTRIBUTION = ("Source: Federal Reserve Bank of St. Louis, FRED (Federal Reserve "
               "Economic Data), https://fred.stlouisfed.org/, series as named. "
               "Underlying data from the U.S. Bureau of Labor Statistics and the "
               "U.S. Employment and Training Administration (public domain).")
LICENCE = "Public domain (U.S. government data via FRED); cite FRED"

#: series_id -> (human label, category, frequency, units)
SERIES = {
    "UNRATE": ("Unemployment rate", "unemployment", "monthly", "percent"),
    "LNS14027662": ("Unemployment rate, bachelor's degree and higher (25+)",
                    "unemployment", "monthly", "percent"),
    "PAYEMS": ("All employees, total nonfarm", "employment", "monthly", "thousands of persons"),
    "USINFO": ("All employees, information sector", "employment", "monthly", "thousands of persons"),
    "JTSLDL": ("JOLTS layoffs and discharges, total nonfarm", "layoffs", "monthly",
               "thousands"),
    "ICSA": ("Initial jobless claims", "claims", "weekly", "number"),
    "CCSA": ("Continued jobless claims", "claims", "weekly", "number"),
}

FIELDS = ["series_id", "date", "value", "label", "category", "frequency"]


def scrub(text: str, key: str) -> str:
    """Never let the key reach a log line."""
    text = str(text)
    return text.replace(key, "***") if key else text


def url(series_id: str, key: str, start: str) -> str:
    q = urllib.parse.urlencode({"series_id": series_id, "api_key": key,
                                "file_type": "json", "observation_start": start})
    return f"{API}?{q}"


def window_start(today=None, years=WINDOW_YEARS) -> str:
    today = today or date.today()
    return f"{today.year - years:04d}-01-01"


def parse(series_id: str, body: str) -> list:
    """FRED observations JSON -> [row] in FIELDS order; '.' (missing) dropped."""
    label, cat, freq, _units = SERIES[series_id]
    out = []
    for o in (json.loads(body).get("observations") or []):
        d = str(o.get("date") or "")
        try:
            v = float(o.get("value"))
        except (TypeError, ValueError):
            continue
        if len(d) != 10:
            continue
        out.append([series_id, d, round(v, 3), label, cat, freq])
    return out


def build_payload(rows, errors=(), now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    rows = sorted(rows, key=lambda r: (r[0], r[1]))
    latest = {}
    for r in rows:
        latest[r[5]] = max(latest.get(r[5], ""), r[1][:7])
    present = sorted({r[0] for r in rows})
    return {
        "source": SOURCE,
        "updated": now.isoformat(),
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "url": "https://fred.stlouisfed.org/",
        "label": ("Macro context: official U.S. labour statistics via FRED. Not "
                  "layoffs we verified; never summed into tracker counts."),
        "fields": FIELDS,
        "series": {s: {"label": v[0], "category": v[1], "frequency": v[2], "units": v[3]}
                   for s, v in SERIES.items()},
        "latest": latest,
        "rows": len(rows),
        "series_present": present,
        "datasets": {"observations": rows},
        "errors": list(errors),
    }


def fetch(series_id: str, key: str, start: str, timeout=60, opener=None) -> str:
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(url(series_id, key, start),
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    with opener(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def describe(exc) -> str:
    """An HTTPError's body says WHY (e.g. an unregistered api_key); keep it."""
    msg = str(exc)
    try:
        body = exc.read().decode("utf-8", "replace")  # urllib HTTPError only
        msg += " " + (json.loads(body).get("error_message") or body)[:150]
    except Exception:
        pass
    return msg


def pull(key: str, start: str, opener=None) -> dict:
    rows, errors = [], []
    for sid in SERIES:
        try:
            rows.extend(parse(sid, fetch(sid, key, start, opener=opener)))
        except Exception as exc:  # one bad series must not sink the rest
            errors.append(f"{sid}: {scrub(describe(exc), key)[:200]}")
    return build_payload(rows, errors)
