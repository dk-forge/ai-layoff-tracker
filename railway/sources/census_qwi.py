"""US Census Quarterly Workforce Indicators (QWI): reference data, MACRO CONTEXT.

WHAT THIS IS
------------
A puller for the Census Data API time series `timeseries/qwi/{sa,se,rh}`
(https://www.census.gov/data/developers/data-sets/qwi.html): stable hires
(HirA), separations (Sep) and end-of-quarter employment (EmpEnd), private
ownership (A05), not seasonally adjusted, for every state, latest
KEEP_QUARTERS quarters. Six requests, each one breakdown at a time so the
document stays small (cross-tabs would multiply it):

  by_sector       state x NAICS sector (ind_level S), all workers
  agegrp          state x age group,  all industries, both sexes  (sa)
  sex             state x sex,        all industries, all ages    (sa)
  education       state x education,  all industries, both sexes  (se)
  race            state x race,       all industries, all ethnicities (rh)
  ethnicity       state x ethnicity,  all industries, all races    (rh)

QWI is state-level (no national rollup in the API). Needs `CENSUS_API_KEY`;
the key travels only in the request URL and is scrubbed from every message.

IMPORTANT LABELING
------------------
Labelled macro context. Separations are ALL separations (quits, layoffs,
retirements...), never layoffs we verified, never summed into tracker counts;
nothing here touches ingest or event classification.

SHAPE (flat rows so a display layer can filter on every field)
-----
datasets.<breakdown> = [[breakdown, state, quarter, industry, sex, agegrp,
education, race, ethnicity, HirA, Sep, EmpEnd], ...] with `fields` naming the
columns and `codes` decoding them; the unconstrained dimension carries its
"all" code (industry 00, sex 0, agegrp A00, education E0, race A0, ethnicity
A0). GET /reference/census_qwi accepts any field as a query parameter
(e.g. ?state=06&industry=51, ?breakdown=education).

Stdlib only. Parsing is pure and tested offline.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

SOURCE = "census_qwi"
API = "https://api.census.gov/data/timeseries/qwi/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
METRICS = ["HirA", "Sep", "EmpEnd"]
KEEP_QUARTERS = 8
#: How far back the open-ended `time=from` predicate starts. QWI lags ~3
#: quarters, so 4 years always holds the newest KEEP_QUARTERS.
LOOKBACK_YEARS = 4

ATTRIBUTION = ("Source: U.S. Census Bureau, Quarterly Workforce Indicators "
               "(LEHD), Census Data API. This product uses the Census Bureau "
               "Data API but is not endorsed or certified by the Census Bureau.")
LICENCE = "Public domain (U.S. Census Bureau)"

FIELDS = ["breakdown", "state", "quarter", "industry", "sex", "agegrp",
          "education", "race", "ethnicity"] + METRICS
DEFAULTS = {"industry": "00", "sex": "0", "agegrp": "A00", "education": "E0",
            "race": "A0", "ethnicity": "A0"}

#: breakdown -> (endpoint, the dimension it varies, fixed predicates)
QUERIES = {
    "by_sector": ("sa", "industry", {"ind_level": "S", "sex": "0", "agegrp": "A00"}),
    "agegrp": ("sa", "agegrp", {"ind_level": "A", "sex": "0"}),
    "sex": ("sa", "sex", {"ind_level": "A", "agegrp": "A00"}),
    "education": ("se", "education", {"ind_level": "A", "sex": "0"}),
    "race": ("rh", "race", {"ind_level": "A", "ethnicity": "A0"}),
    "ethnicity": ("rh", "ethnicity", {"ind_level": "A", "race": "A0"}),
}

CODES = {
    "sex": {"0": "All", "1": "Male", "2": "Female"},
    "agegrp": {"A00": "All ages", "A01": "14-18", "A02": "19-21", "A03": "22-24",
               "A04": "25-34", "A05": "35-44", "A06": "45-54", "A07": "55-64",
               "A08": "65-99"},
    "education": {"E0": "All", "E1": "Less than high school", "E2": "High school",
                  "E3": "Some college or associate degree",
                  "E4": "Bachelor's degree or advanced degree",
                  "E5": "Not available (under 25)"},
    "race": {"A0": "All", "A1": "White alone", "A2": "Black alone",
             "A3": "American Indian or Alaska Native alone", "A4": "Asian alone",
             "A5": "Native Hawaiian or Other Pacific Islander alone",
             "A7": "Two or more races"},
    "ethnicity": {"A0": "All", "A1": "Not Hispanic or Latino", "A2": "Hispanic or Latino"},
    "industry": "2-digit NAICS sector (00 = all industries)",
    "state": "2-digit state FIPS",
}


def scrub(text, key: str) -> str:
    text = str(text)
    return text.replace(key, "***") if key else text


def time_from(today=None) -> str:
    today = today or date.today()
    return f"from {today.year - LOOKBACK_YEARS}-Q1"


def url(breakdown: str, key: str, today=None) -> str:
    ep, dim, fixed = QUERIES[breakdown]
    get = ",".join(METRICS + [dim])
    q = {"get": get, "for": "state:*", "time": time_from(today),
         "ownercode": "A05", "seasonadj": "U", **fixed}
    if key:
        q["key"] = key
    return API + ep + "?" + urllib.parse.urlencode(q)


def _num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def parse(breakdown: str, body: str) -> list:
    """Census array-of-arrays JSON -> [row] in FIELDS order."""
    try:
        table = json.loads(body)
    except ValueError:
        raise RuntimeError("response was not JSON: " + body.strip()[:120])
    if not table:
        return []
    hdr = table[0]
    ix = {h: i for i, h in enumerate(hdr)}
    out = []
    for rec in table[1:]:
        def g(name, default=None):
            return rec[ix[name]] if name in ix and rec[ix[name]] is not None else default
        per = str(g("time", ""))
        st = str(g("state", ""))
        if not (len(per) == 7 and per[4:6] == "-Q" and st):
            continue
        vals = [_num(g(m)) for m in METRICS]
        if all(v is None for v in vals):
            continue
        row = [breakdown, st, per] + [str(g(d, DEFAULTS[d])) for d in
                                      ("industry", "sex", "agegrp", "education", "race",
                                       "ethnicity")] + vals
        out.append(row)
    return out


def keep_latest(rows, n=KEEP_QUARTERS) -> list:
    qs = sorted({r[2] for r in rows})[-n:]
    keep = set(qs)
    return sorted((r for r in rows if r[2] in keep), key=lambda r: r[:9])


def quarter_end_month(q: str) -> str:
    return f"{q[:4]}-{int(q[6]) * 3:02d}"


def build_payload(by_breakdown: dict, errors=(), now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    allq = sorted({r[2] for rows in by_breakdown.values() for r in rows})
    total = sum(len(v) for v in by_breakdown.values())
    states = sorted({r[1] for rows in by_breakdown.values() for r in rows})
    return {
        "source": SOURCE,
        "updated": now.isoformat(),
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "url": "https://lehd.ces.census.gov/data/",
        "label": ("Macro context: official Census QWI hires and separations "
                  "(all causes). Not layoffs we verified; never summed into "
                  "tracker counts."),
        "fields": FIELDS,
        "metrics": {"HirA": "stable hires", "Sep": "separations (all causes)",
                    "EmpEnd": "end-of-quarter employment"},
        "codes": CODES,
        # month-of-quarter-end, so reference_freshness reads it like the others
        "latest": {"quarterly": quarter_end_month(allq[-1])} if allq else {},
        "latest_quarter": allq[-1] if allq else None,
        "quarters": allq,
        "rows": total,
        "states": states,
        "datasets": {k: v for k, v in by_breakdown.items()},
        "errors": list(errors),
    }


def describe(exc) -> str:
    msg = str(exc)
    try:
        msg += " " + exc.read().decode("utf-8", "replace").strip()[:150]
    except Exception:
        pass
    return msg


def fetch(breakdown: str, key: str, timeout=120, opener=None, today=None) -> str:
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(url(breakdown, key, today),
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    with opener(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def pull(key: str, opener=None, today=None, keep=KEEP_QUARTERS) -> dict:
    out, errors = {}, []
    for b in QUERIES:
        try:
            out[b] = keep_latest(parse(b, fetch(b, key, opener=opener, today=today)), keep)
        except Exception as exc:  # one bad breakdown must not sink the rest
            errors.append(f"{b}: {scrub(describe(exc), key)[:220]}")
    return build_payload(out, errors)
