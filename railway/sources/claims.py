"""
US unemployment-insurance (UI) claims puller, the MACRO CONTEXT layer.

WHAT THIS IS
------------
A free, keyless data puller for US unemployment-insurance claims, sourced from
the Federal Reserve Bank of St. Louis (FRED) public CSV download endpoint. It
backs a *background macro-context* layer on the AI Layoff Tracker: monthly bars
(new / initial claims) plus a line overlay (continued claims), nationally and by
state, drawn BEHIND our documented layoff counts.

Series pulled (all weekly, seasonally adjusted, published by US DOL/ETA):
  - ICSA: national INITIAL claims (a weekly FLOW: new filings that week)
  - CCSA: national CONTINUED claims (a weekly STOCK: people still claiming)
  - <ST>ICLAIMS: per-state initial claims where a keyless CSV resolves
                  (e.g. CAICLAIMS, TXICLAIMS, NYICLAIMS). NOTE: the state
                  ICLAIMS family on FRED is NOT seasonally adjusted (NSA).

WEEKLY -> MONTHLY AGGREGATION (the deliberate choice)
----------------------------------------------------
Claims are reported weekly; the tracker charts monthly. We collapse each series
to calendar months by the statistically correct reduction for its kind:
  - INITIAL claims are a FLOW (count of *new* filings). Flows over a period ADD
    up, so a month's "new claims" is the SUM of that month's weekly values.
  - CONTINUED claims are a STOCK (level of people still on benefits at a point
    in time). Stocks do NOT add across weeks (that would multiply-count the same
    people), so a month's figure is the AVERAGE of that month's weekly values.
A month is only emitted once every ISO week whose reporting date falls in that
calendar month is present, so the trailing partial month never shows an
artificially small bar. History is capped to a small trailing window to keep the
served payload tiny.

IMPORTANT LABELING
------------------
These numbers are macro CONTEXT only. UI claims measure economy-wide joblessness
from all causes; they are NOT layoffs we verified and are categorically NOT
attributed to AI. They must NEVER be summed into, blended with, or compared
one-to-one against the tracker's documented layoff counts. Keep them on their
own axis / visual layer with an explicit "context, not our data" label.

Dependencies: `requests` + stdlib only (csv, datetime, io). No API key, no
secrets. Fail-soft: network / parse errors are captured into an "errors" list
and the function returns whatever it managed to fetch; it never raises.
"""
import csv
import io
from datetime import datetime, timezone

import requests

# FRED's public graph CSV endpoint. No API key required; it is the same file a
# browser downloads from the "Download -> CSV" button on a FRED series page.
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# ModSecurity-style WAFs (and FRED itself, occasionally) reject the bare
# python-requests UA. Mirror the browser-ish UA discipline used site-wide.
HEADERS = {
    "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)",
    "Accept": "text/csv,text/plain,*/*",
}

# National series.
NATIONAL_SERIES = {
    "initial": "ICSA",   # seasonally adjusted weekly initial claims (FLOW)
    "continued": "CCSA",  # seasonally adjusted weekly continued claims (STOCK)
}

# Candidate state initial-claims series. FRED's per-state weekly initial-claims
# family is "<STATE_ABBR>ICLAIMS" (NOT seasonally adjusted). We attempt all 50 +
# DC and keep whichever actually resolve to a keyless CSV; unresolved ones are
# reported in "errors" and simply omitted, so a FRED rename never hard-fails.
STATE_ABBRS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
]

# Trailing window (months) to keep the served payload small.
DEFAULT_MONTHS_BACK = 36

# Per-request network timeout (seconds).
REQUEST_TIMEOUT = 30


def _fetch_series_csv(series_id, timeout=REQUEST_TIMEOUT):
    """Fetch one FRED series as a list of (date_str, raw_value_str) rows.

    Returns (rows, error). On any failure `rows` is [] and `error` is a short
    string; the caller decides whether that is fatal (national) or skippable
    (a single state). Never raises.
    """
    try:
        resp = requests.get(
            FRED_CSV_URL,
            params={"id": series_id},
            headers=HEADERS,
            timeout=timeout,
        )
    except Exception as e:  # network / DNS / timeout
        return [], f"{series_id}: request failed ({e})"

    if resp.status_code != 200:
        return [], f"{series_id}: HTTP {resp.status_code}"

    text = resp.text or ""
    # A missing/renamed series returns an HTML error page, not CSV. Guard on it
    # so we don't try to parse markup as data.
    head = text.lstrip()[:15].lower()
    if head.startswith("<!doctype") or head.startswith("<html"):
        return [], f"{series_id}: not a CSV (series likely does not exist)"

    rows = []
    try:
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header or len(header) < 2:
            return [], f"{series_id}: unexpected CSV header {header!r}"
        # FRED CSV columns are the date column ("observation_date" on the modern
        # endpoint, "DATE" on the legacy one) followed by the value column,
        # named after the series id. We read strictly by position.
        for row in reader:
            if len(row) < 2:
                continue
            rows.append((row[0].strip(), row[1].strip()))
    except Exception as e:
        return [], f"{series_id}: CSV parse error ({e})"

    if not rows:
        return [], f"{series_id}: empty series"
    return rows, None


def _weekly_rows_to_monthly(rows, kind):
    """Collapse weekly (date, value) rows into monthly aggregates.

    kind == "initial"   -> SUM the weeks in each month (flow).
    kind == "continued" -> AVERAGE the weeks in each month (stock).

    Missing values in FRED CSV are ".". Rows with an unparseable date or value
    are skipped. The most recent calendar month is dropped unless it is fully
    populated relative to the months around it, to avoid a short partial bar.
    Returns a list of {"month": "YYYY-MM", "value": number} sorted ascending.
    """
    buckets = {}  # "YYYY-MM" -> list of float weekly values
    for date_str, value_str in rows:
        if not date_str or value_str in ("", "."):
            continue
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        try:
            v = float(value_str)
        except ValueError:
            continue
        buckets.setdefault(f"{d.year:04d}-{d.month:02d}", []).append(v)

    months = sorted(buckets.keys())
    if not months:
        return []

    # Drop a trailing partial month: FRED weekly series post one week at a time,
    # so the newest month often has fewer weeks than a full month (4-5). If the
    # last month has strictly fewer weeks than the median of the prior full
    # months, treat it as partial and exclude it from the flow SUM (a partial
    # sum would understate the bar). Continued (average) is robust to this, but
    # we apply the same rule for visual consistency across the two series.
    if len(months) >= 2:
        prior_counts = [len(buckets[m]) for m in months[:-1]]
        typical = sorted(prior_counts)[len(prior_counts) // 2]
        if len(buckets[months[-1]]) < typical:
            months = months[:-1]

    out = []
    for m in months:
        weeks = buckets[m]
        if not weeks:
            continue
        if kind == "initial":
            val = int(round(sum(weeks)))          # flow: total new filings
        else:
            val = int(round(sum(weeks) / len(weeks)))  # stock: month average
        out.append({"month": m, "value": val})
    return out


def _trim_to_window(monthly, months_back):
    """Keep only the last `months_back` monthly points."""
    if months_back and len(monthly) > months_back:
        return monthly[-months_back:]
    return monthly


def build_claims_payload(months_back=DEFAULT_MONTHS_BACK, include_states=True,
                         timeout=REQUEST_TIMEOUT):
    """Fetch UI claims from FRED and return the served macro-context structure.

    Shape:
    {
      "national": {
        "initial":   [{"month": "2026-01", "value": 1234567}, ...],  # monthly SUM
        "continued": [{"month": "2026-01", "value": 1890000}, ...],  # monthly AVG
      },
      "states": {
        "CA": [{"month": "2026-01", "value": 45678}, ...],  # monthly SUM (NSA)
        "TX": [...], ...
      },
      "updated": "2026-07-24T12:00:00+00:00",   # ISO8601 UTC of this fetch
      "source": "FRED (BLS/DOL)",
      "series": {"initial": "ICSA", "continued": "CCSA",
                 "state_pattern": "<ST>ICLAIMS"},
      "meta": {
        "label": "Macro context: US unemployment-insurance claims. "
                 "Not layoffs we verified; never summed into tracker counts.",
        "aggregation": {"initial": "monthly sum (flow)",
                        "continued": "monthly average (stock)"},
        "seasonal_adjustment": {"national": "SA", "states": "NSA"},
        "months_back": <int>,
        "states_resolved": ["CA", "TX", ...],
      },
      "errors": ["CCSA: HTTP 503", ...],   # empty list on a clean pull
    }

    Never raises: any failed series is recorded in "errors" and omitted from the
    payload. If ALL national series fail, "national" simply holds empty lists.
    """
    errors = []
    national = {}
    for key, series_id in NATIONAL_SERIES.items():
        rows, err = _fetch_series_csv(series_id, timeout=timeout)
        if err:
            errors.append(err)
            national[key] = []
            continue
        monthly = _weekly_rows_to_monthly(rows, kind=key)
        national[key] = _trim_to_window(monthly, months_back)

    states = {}
    states_resolved = []
    if include_states:
        for abbr in STATE_ABBRS:
            series_id = f"{abbr}ICLAIMS"
            rows, err = _fetch_series_csv(series_id, timeout=timeout)
            if err:
                errors.append(err)
                continue
            # State ICLAIMS are initial claims -> flow -> monthly SUM.
            monthly = _weekly_rows_to_monthly(rows, kind="initial")
            monthly = _trim_to_window(monthly, months_back)
            if monthly:
                states[abbr] = monthly
                states_resolved.append(abbr)

    return {
        "national": national,
        "states": states,
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "FRED (BLS/DOL)",
        "series": {
            "initial": NATIONAL_SERIES["initial"],
            "continued": NATIONAL_SERIES["continued"],
            "state_pattern": "<ST>ICLAIMS",
        },
        "meta": {
            "label": (
                "Macro context: US unemployment-insurance claims. "
                "Not layoffs we verified; never summed into tracker counts."
            ),
            "aggregation": {
                "initial": "monthly sum (flow)",
                "continued": "monthly average (stock)",
            },
            "seasonal_adjustment": {"national": "SA", "states": "NSA"},
            "months_back": months_back,
            "states_resolved": states_resolved,
        },
        "errors": errors,
    }


if __name__ == "__main__":
    # Live smoke test: fetch, then print the national monthly initial + continued
    # series (last 6 months) and how many state series resolved.
    print("Fetching US UI claims from FRED (keyless CSV)...")
    payload = build_claims_payload()

    nat = payload["national"]
    print("\nNational INITIAL claims (ICSA), monthly SUM, last 6 months:")
    for pt in nat.get("initial", [])[-6:]:
        print(f"  {pt['month']}: {pt['value']:>12,}")

    print("\nNational CONTINUED claims (CCSA), monthly AVG, last 6 months:")
    for pt in nat.get("continued", [])[-6:]:
        print(f"  {pt['month']}: {pt['value']:>12,}")

    resolved = payload["meta"]["states_resolved"]
    print(f"\nState series resolved: {len(resolved)} / {len(STATE_ABBRS)}")
    if resolved:
        print("  " + ", ".join(resolved))

    if payload["errors"]:
        print(f"\nErrors ({len(payload['errors'])}):")
        for e in payload["errors"][:10]:
            print(f"  - {e}")
        if len(payload["errors"]) > 10:
            print(f"  ... and {len(payload['errors']) - 10} more")

    print(f"\nupdated: {payload['updated']}")
    print(f"source:  {payload['source']}")
