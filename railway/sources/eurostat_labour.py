"""Eurostat job vacancy rate + unemployment rate by country: reference data, MACRO CONTEXT.

WHAT THIS IS
------------
Two series from the Eurostat dissemination API (JSON-stat 2.0, keyless,
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/):

* `jvs_q_nace2` - job vacancy rate (indic_em=JVR), industry, construction and
  services (NACE B-S), all size classes, not seasonally adjusted, quarterly.
* `une_rt_m`    - unemployment rate, % of the labour force (LFS-based),
  total age and sex, seasonally adjusted, monthly.

One row per (country, period) for the EU27 aggregate, each EU member state and
the EFTA countries Eurostat publishes, over a trailing window.

IMPORTANT LABELING
------------------
Vacancies are hiring demand and unemployment is a labour-market stock. Neither
is a layoff count; they are never added to the tracker's rows, and a change
here does not show that AI caused it.

SHAPE: datasets.vacancy_rate / datasets.unemployment = [[geo, period, value]];
quarterly periods are stored as "YYYY-Qn". `latest` uses the last month of the
newest period (YYYY-MM) for reference_freshness. Stdlib only; parsing is pure
and tested offline. Licence: Eurostat reuse policy, CC BY 4.0.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SOURCE = "eurostat_labour"
BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
WINDOW_YEARS = 3
FIELDS = ["geo", "period", "value"]

#: EU27 aggregate, the 27 member states (Eurostat codes: EL = Greece) and EFTA.
GEOS = ("EU27_2020", "BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR",
        "HR", "IT", "CY", "LV", "LT", "LU", "HU", "MT", "NL", "AT", "PL", "PT",
        "RO", "SI", "SK", "FI", "SE", "IS", "LI", "NO", "CH")

#: dataset key -> (Eurostat code, fixed filters)
QUERIES = {
    "vacancy_rate": ("jvs_q_nace2", {"nace_r2": "B-S", "sizeclas": "TOTAL",
                                     "indic_em": "JVR", "s_adj": "NSA"}),
    "unemployment": ("une_rt_m", {"s_adj": "SA", "age": "TOTAL", "sex": "T",
                                  "unit": "PC_ACT"}),
}

ATTRIBUTION = ("Source: Eurostat, job vacancy statistics (jvs_q_nace2) and "
               "unemployment by sex and age, monthly data (une_rt_m), "
               "https://ec.europa.eu/eurostat. Reused under the Eurostat reuse "
               "policy, CC BY 4.0.")
LICENCE = "CC BY 4.0 (Eurostat reuse policy), attribution required"
NOTE = ("Job vacancies measure hiring demand and unemployment is a labour-market "
        "rate. Neither is a layoff count, neither is added to the tracker's "
        "counts, and a change here does not show that AI caused it.")


def parse_jsonstat(doc) -> list:
    """[(geo, period, value)] from a JSON-stat 2.0 dataset whose other
    dimensions are fixed to one category each. Malformed input gives []."""
    try:
        ids, sizes = doc["id"], doc["size"]
        dims = doc["dimension"]
        if "geo" not in ids or "time" not in ids:
            return []
        cats = []
        for d in ids:
            idx = dims[d]["category"]["index"]
            if isinstance(idx, list):
                idx = {k: i for i, k in enumerate(idx)}
            cats.append({i: k for k, i in idx.items()})
        values = doc.get("value") or {}
        if isinstance(values, list):
            values = {str(i): v for i, v in enumerate(values)}
    except (KeyError, TypeError, AttributeError):
        return []
    gi, ti = ids.index("geo"), ids.index("time")
    out = []
    for flat, v in values.items():
        if v is None:
            continue
        try:
            n = int(flat)
            v = float(v)
        except (TypeError, ValueError):
            continue
        pos = [0] * len(sizes)
        for k in range(len(sizes) - 1, -1, -1):
            pos[k] = n % sizes[k]
            n //= sizes[k]
        geo, period = cats[gi].get(pos[gi]), cats[ti].get(pos[ti])
        if geo and period:
            out.append((geo, period, v))
    return out


def keep_rows(rows, start_period: str) -> list:
    return sorted([g, p, v] for g, p, v in rows if g in GEOS and p >= start_period)


def period_month(p: str) -> str:
    """'2026-Q2' -> '2026-06'; '2026-08' -> '2026-08'."""
    if "-Q" in p:
        y, q = p.split("-Q")
        return f"{y}-{int(q) * 3:02d}"
    return p[:7]


def build_payload(docs: dict, today=None, errors=None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    y0 = today.year - WINDOW_YEARS
    starts = {"vacancy_rate": f"{y0}-Q1", "unemployment": f"{y0}-01"}
    datasets, latest = {}, {}
    for key in QUERIES:
        rows = keep_rows(parse_jsonstat(docs.get(key) or {}), starts[key])
        datasets[key] = rows
        eu = [r[1] for r in rows if r[0] == "EU27_2020"] or [r[1] for r in rows]
        if eu:
            latest[key] = period_month(max(eu))
    return {
        "source": SOURCE,
        "updated": datetime.now(timezone.utc).isoformat(),
        "fields": FIELDS,
        "datasets": datasets,
        "rows": sum(len(v) for v in datasets.values()),
        "geos": {k: sorted({r[0] for r in v}) for k, v in datasets.items()},
        "latest": latest,
        "attribution": ATTRIBUTION,
        "licence": LICENCE,
        "note": NOTE,
        "errors": list(errors or []),
    }


def url_for(key: str, since: str) -> str:
    code, filters = QUERIES[key]
    q = [("format", "JSON"), ("lang", "EN"), ("sinceTimePeriod", since)]
    q += sorted(filters.items())
    return BASE + code + "?" + urllib.parse.urlencode(q)


def fetch(url, opener=urllib.request.urlopen, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with opener(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def pull(today=None, opener=urllib.request.urlopen):
    today = today or datetime.now(timezone.utc).date()
    y0 = today.year - WINDOW_YEARS
    since = {"vacancy_rate": f"{y0}-Q1", "unemployment": f"{y0}-01"}
    docs, errors = {}, []
    for key in QUERIES:
        try:
            docs[key] = fetch(url_for(key, since[key]), opener)
        except Exception as exc:  # network: record and let should_store refuse
            errors.append(f"{key}: {type(exc).__name__}: {str(exc)[:200]}")
            docs[key] = {}
    return build_payload(docs, today, errors)
