#!/usr/bin/env python3
"""NATIONAL DENOMINATORS — coverage measured against counts we do not construct.

READ `railway/rolling_recall.py` FIRST, then `railway/country_coverage.py`.
This is the THIRD module of one framework, not a second framework:

    rolling_recall     measures ONE slice exactly (US SEC Item 2.05), and owns
                       the vocabulary: MEASURED / NOT_MEASURABLE / UNKNOWN, a
                       BAND rather than a point where no editor adjudicated, an
                       assessment that carries a DATE and EXPIRES, and the rule
                       that a declared slice which cannot be computed says so
                       instead of dropping out of an average.
    country_coverage   classifies every country in the corpus into
                       regime-with-aggregate / regime-no-aggregate / no-regime /
                       refused / unassessed. It says WHERE a denominator exists.
    THIS MODULE        goes and gets the ones that exist, and turns them into a
                       measured coverage figure per country.

Every state constant, the Wilson interval and the freshness ceiling come from
those modules by import. Nothing here is a second copy of a rule that lives
there — this repo has been bitten repeatedly by a second copy drifting.

WHAT A DENOMINATOR HERE IS, AND WHAT IT IS NOT
-----------------------------------------------
Each series below is a count of collective-redundancy notifications published by
the authority that RECEIVES them. That is the same property that makes Item 2.05
measurable: the publisher enumerates its own universe, so the denominator is not
a sample and not ours. A figure computed this way is falsifiable by anyone who
downloads the same file.

It is NOT a count of job losses in the country. A notification regime has a
threshold; everything under it is invisible to the series and to any coverage
figure built on it. So the honest sentence is always of the form "of the N
workers whose redundancy was notified to <authority> in <period>, we hold M" —
never "we cover X% of layoffs in <country>".

DENOMINATORS ARE NOT COMPARABLE ACROSS COUNTRIES, AND THE CODE ENFORCES IT
--------------------------------------------------------------------------
Directive 98/59/EC lets each member state pick between two different threshold
formulations and go lower still; Sweden's floor is five workers, Norway's ten,
Croatia's twenty. Some series count workers, some count employers, some count
procedures, Taiwan counts PLANTS (廠場) so one company filing for four sites
counts four times. Adding two of those together produces a number that means
nothing and looks authoritative.

`combine()` therefore refuses any pair that does not agree on BOTH the unit and
the period, and raises `IncomparableSeries` rather than returning a sum.
`railway/tests/test_national_denominators.py` asserts the refusal. There is no
worldwide total in this module and there must not be one.

THE BAND, AND WHY IT IS THE OTHER WAY UP FROM rolling_recall's
--------------------------------------------------------------
rolling_recall bands because a machine must not promote its own recall. Here the
uncertainty is different and lives in OUR numerator: a multi-country cut is
stored with country "Multiple countries" and its jobs are not attributable to
any one country, so

    LOWER   country=<X>                    strict job location. Excludes every
                                           global cut that hit X — biased DOWN.
    UPPER   country=<X>&country_basis=any  unions job location with employer
                                           domicile, so a global cut touching X
                                           contributes its WHOLE total — biased
                                           UP, and by construction it cannot be
                                           biased down.

The true figure is inside. Reporting the midpoint would be inventing a number
nobody could re-derive, which is the defect the private benchmark exists to
catch one floor down.

THE WILSON INTERVAL MEASURES THE SMALL THING
---------------------------------------------
Reported for the lower end, treating each notified worker as a trial. It bounds
SAMPLING noise only. It does NOT bound the definitional mismatch between what
the authority counts and what we store, and that mismatch is much larger than
the interval at every denominator in this file. It is printed because a ratio
over 300 workers and a ratio over 300,000 should not look alike, not because it
is the dominant uncertainty. Never quote it as the error bar on coverage.

RATIOS ABOVE 1.0 ARE A RESULT, NOT A BUG
-----------------------------------------
Our rows are not a subset of the notified population: we hold events below the
threshold, events an employer announced but never notified, and (on the upper
basis) global cuts counted whole. A ratio above 1.0 therefore means the
numerator has left the denominator's universe, and the slice reports
OVER_UNIVERSE rather than a coverage figure. Clamping it to 100% would publish a
number we know to be a category error.

COST: $0.00. Every source here is a free public file or a keyless API, and the
numerator is the tracker's own public /aggregate. No model is called on any
path and none should ever be added — see rolling_recall on why a measurement
that spends money is a measurement that gets switched off in a lean month.

ROBOTS. Read BEFORE the first content request on every host, and recorded per
series in `robots`. A refusal is recorded as a refusal and stays refused; this
project does not rename an agent to get around a block aimed at the agent.

USAGE
    python3 railway/national_denominators.py            # measure, print
    python3 railway/national_denominators.py --write    # ...and commit it
    python3 railway/national_denominators.py --offline  # registry only, no net

Env: WP_SITE_URL, ND_CACHE (downloaded-file cache dir).
"""
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from base64 import b64decode
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recall_goldset import PASS, UNKNOWN, wilson  # noqa: E402
from rolling_recall import (MEASURED, NOT_MEASURABLE, SETTLE_DAYS,  # noqa: E402
                            _days_since, _utc_now_iso)

HERE = Path(__file__).resolve().parent
MEASUREMENT_PATH = HERE / "national_denominators_measurement.json"

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
SITE = (os.environ.get("WP_SITE_URL") or "https://asktherecruiter.com/blog").rstrip("/")
_CACHE = Path(os.environ.get("ND_CACHE")
              or (Path(os.environ.get("TMPDIR", "/tmp")) / "national-denominators-cache"))
MAX_BYTES = 12_000_000

# Refreshed weekly by national-denominators.yml. Same ceiling and same reasoning
# as rolling_recall.MAX_MEASUREMENT_AGE_DAYS — a 2-day ceiling on a weekly job
# is permanent noise that hides real breakage.
MAX_MEASUREMENT_AGE_DAYS = 9

# A standing "not measurable" that nobody revisits is a stale claim wearing a
# permanent exemption. Same 183 days as rolling_recall's WARN assessment and
# country_coverage's register, for the same reason: ministries start and stop
# publishing.
MAX_ASSESSMENT_AGE_DAYS = 183

# ---------------------------------------------------------------------------
# UNITS. The whole point of naming them is that two series with different units
# may never be added, and the code must be able to tell.
# ---------------------------------------------------------------------------
WORKERS = "workers"                 # persons whose redundancy was notified
EMPLOYERS = "employers"             # distinct employers filing
ESTABLISHMENTS = "establishments"   # 廠場 / plants — one company, several counts
PROCEDURES = "procedures"           # notification procedures opened
UNITS = (WORKERS, EMPLOYERS, ESTABLISHMENTS, PROCEDURES)

# Slice-level extra state, on top of the three inherited ones. It is NOT a
# fourth verdict — it resolves to UNKNOWN in `judge` — but the reader needs to
# know that the figure failed by leaving the denominator's universe rather than
# by a broken fetch.
OVER_UNIVERSE = "over_universe"

# Cadence -> how stale the publisher's own latest period may be before the
# series is UNKNOWN (the publisher stopped, or moved the file). Sized on each
# series' REAL cadence plus its observed lag: a 2-day ceiling on an annual
# series is permanent noise that hides real breakage.
MAX_SERIES_LAG_DAYS = {
    "monthly": 100,     # ~1 month cadence + up to ~2 months of publication lag
    "annual": 550,      # Taiwan runs ~6 months behind; 18 months is a real stop
}


class IncomparableSeries(Exception):
    """Raised by `combine()`. Never caught to produce a sum anyway."""


class TlsChainRejected(Exception):
    """The local TLS stack rejected the publisher's chain. An environment fact."""


_TLS_FAULT = TlsChainRejected


def _reraise_tls(exc):
    """urllib buries a certificate failure inside URLError, so a plain
    `except ssl.SSLCertVerificationError` never fires and a laptop's OpenSSL
    ends up reported as a publisher outage. Unwrapped here, once."""
    inner = getattr(exc, "reason", None)
    if isinstance(exc, ssl.SSLCertVerificationError):
        raise TlsChainRejected(str(exc)) from exc
    if isinstance(inner, ssl.SSLCertVerificationError):
        raise TlsChainRejected(str(inner)) from exc
    raise exc


# ---------------------------------------------------------------------------
# transport — stdlib only, one request per call, everything free
# ---------------------------------------------------------------------------

def _get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(MAX_BYTES)
    except (urllib.error.URLError, ssl.SSLError) as exc:
        _reraise_tls(exc)


def fetch_bytes(url, get=None, cache=True):
    """One request. Cached on disk so a re-run in the same day does not re-hit a
    statistics office that is doing us a favour by publishing at all."""
    get = get or _get
    if not cache:
        return get(url)
    _CACHE.mkdir(parents=True, exist_ok=True)
    path = _CACHE / (date.today().isoformat() + "-"
                     + urllib.parse.quote(url, safe="")[-150:])
    if path.exists():
        return path.read_bytes()
    body = get(url)
    path.write_bytes(body)
    return body


def fetch_json(url, get=None):
    return json.loads(fetch_bytes(url, get=get).decode("utf-8", "replace"))


# ---------------------------------------------------------------------------
# a stdlib .xlsx reader
# ---------------------------------------------------------------------------
# Deliberately NOT openpyxl. `railway/requirements.lock` is hash-pinned and two
# locks exist precisely so a health job does not install a spreadsheet stack; a
# measurement module is the last place to widen that surface. What is needed
# here is small and boring: an xlsx is a zip of XML, and these workbooks are
# flat tables of numbers and shared strings.
_XL = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_XLR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_R = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Excel's 1900 date system, with its deliberate 1900-02-29 bug: serial 1 is
# 1900-01-01 and serial 60 is a day that never existed, so the usual epoch for
# anything after 1900-03-01 is 1899-12-30. Every series here starts after 2005.
_EXCEL_EPOCH = date(1899, 12, 30)


def excel_date(serial):
    """Excel serial -> date. None for anything not a plain positive integer —
    a header cell must not silently become 1899."""
    try:
        n = int(str(serial).strip())
    except (TypeError, ValueError):
        return None
    if n < 61 or n > 80000:
        return None
    return _EXCEL_EPOCH + timedelta(days=n)


def xlsx_sheets(blob):
    """{sheet name: [[cell, ...], ...]} for every worksheet in the workbook."""
    z = zipfile.ZipFile(__import__("io").BytesIO(blob))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        shared = ["".join(t.text or "" for t in si.iter(_XL + "t"))
                  for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
    rels = {}
    for rel in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
        rels[rel.get("Id")] = rel.get("Target").lstrip("/")
    out = {}
    for sheet in ET.fromstring(z.read("xl/workbook.xml")).iter(_XL + "sheet"):
        target = rels.get(sheet.get(_XLR + "id"))
        if not target:
            continue
        name = "xl/" + target if not target.startswith("xl/") else target
        if name not in z.namelist():
            continue
        rows = []
        for row in ET.fromstring(z.read(name)).iter(_XL + "row"):
            cells = []
            for c in row.iter(_XL + "c"):
                v = c.find(_XL + "v")
                if v is None:
                    inline = c.find(_XL + "is")
                    cells.append("".join(t.text or "" for t in inline.iter(_XL + "t"))
                                 if inline is not None else None)
                    continue
                cells.append(shared[int(v.text)] if c.get("t") == "s" else v.text)
            rows.append(cells)
        out[sheet.get("name")] = rows
    return out


def _int_or_none(value):
    """'[c]' (ONS confidential suppression), '' and None all become None. A
    suppressed cell is NOT a zero and must never be summed as one."""
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s or not re.fullmatch(r"-?\d+(\.0+)?", s):
        return None
    return int(float(s))


# ---------------------------------------------------------------------------
# 1. TAIWAN — 大量解僱通報 (Ministry of Labor open data)
# ---------------------------------------------------------------------------
# THE TRAP, WRITTEN DOWN BECAUSE IT IS A FACTOR-OF-43 ERROR AND IT LOOKS RIGHT.
# data.gov.tw carries TWO datasets with near-identical Chinese titles:
#
#   27505  大量解僱通報       art. 4 大量解僱勞工保護法 notifications.  THIS ONE.
#          Keyed on 民國年 (ROC years: 114 = 2025). 2025: 337 plants / 11,752.
#   27508  大量解僱預警通報   the WAGE-ARREARS EARLY-WARNING tripwire — a
#          different statute, a different population, keyed on WESTERN years.
#          2025: 6,579 / 503,386, which is ~43x larger.
#
# Building on 27508 would put half a million workers in the denominator and make
# our Taiwan coverage a rounding error that nobody could explain. The parser
# below therefore REFUSES a Western-year column outright rather than converting
# it, and test_national_denominators asserts that refusal against a fixture of
# 27508's own shape.
TW_REST = "https://apiservice.mol.gov.tw/OdService/rest/datastore/A17000000J-020115-aUA"
ROC_OFFSET = 1911


class TaiwanWrongDataset(Exception):
    """The rows are keyed on Western years, so this is not 27505."""


def parse_taiwan(payload):
    """[{'year': 2025, 'establishments': 337, 'workers': 11752}, ...], newest
    first, plus the publisher's own updateTime."""
    result = payload.get("result") or {}
    records = result.get("records") or []
    if not records:
        raise ValueError("no records in the MOL payload")

    def col(row, needle):
        for k, v in row.items():
            if needle in k:
                return v
        return None

    out = []
    for row in records:
        raw_year = col(row, "民國年")
        if raw_year is None:
            raise TaiwanWrongDataset(
                "no 民國年 column — dataset 27508 (the wage-arrears early-warning "
                "series) is keyed on Western years and is 43x larger. Refusing "
                "rather than guessing which series this is")
        year = int(str(raw_year).strip())
        if year >= 1900:
            raise TaiwanWrongDataset(
                f"year {year} is a Western year, but 27505 publishes ROC years "
                f"(114 = 2025). This is the 大量解僱預警通報 wage-arrears series, "
                f"a different statute and a ~43x larger population")
        out.append({
            "year": year + ROC_OFFSET,
            "establishments": _int_or_none(col(row, "家數")),
            "workers": _int_or_none(col(row, "人數")),
        })
    out.sort(key=lambda r: r["year"], reverse=True)
    return out, payload.get("updateTime")


def taiwan_series(get=None):
    payload = fetch_json(TW_REST, get=get)
    if not payload.get("success"):
        raise ValueError(f"MOL API reported success={payload.get('success')!r}")
    rows, update_time = parse_taiwan(payload)
    latest = rows[0]
    return {
        "period": {"kind": "year", "label": str(latest["year"]),
                   "from": f"{latest['year']}-01-01", "to": f"{latest['year']}-12-31"},
        "value": latest["workers"],
        "unit": WORKERS,
        "secondary": {"unit": ESTABLISHMENTS, "value": latest["establishments"]},
        "publisher_updated": update_time,
        "history": rows[:8],
    }


# ---------------------------------------------------------------------------
# 2. GREAT BRITAIN — HR1 potential redundancies (ONS, from Insolvency Service)
# ---------------------------------------------------------------------------
# The filename carries a date stamp and changes every month, so it is RESOLVED
# through the landing page's own /data JSON and never templated. Two hops:
# landing -> newest edition -> the edition's `downloads[0].file`.
ONS_HR1 = ("https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/"
           "employmentandemployeetypes/datasets/hr1potentialredundancies")
ONS_FILE = "https://www.ons.gov.uk/file?uri="

# Scheduled discontinuity, encoded rather than discovered later as an anomaly.
# Employment Rights Act 2025 s.195A regulations (expected 2027) widen the duty
# from one establishment to an employer's cuts across sites, which will step the
# HR1 volume up for reasons that have nothing to do with the labour market. A
# period on the far side of this must not be compared with one on this side.
GB_SERIES_BREAKS = [{
    "from": "2027-01-01",
    "why": ("Employment Rights Act 2025 s.195A regulations widen the collective "
            "consultation duty beyond a single establishment. Expect a definitional "
            "step-change in HR1 volumes — a series break, not an anomaly"),
}]


def gb_latest_workbook_url(get=None):
    landing = fetch_json(ONS_HR1 + "/data", get=get)
    editions = landing.get("datasets") or []
    if not editions:
        raise ValueError("ONS landing page listed no dataset editions")
    uri = editions[0].get("uri")
    edition = fetch_json("https://www.ons.gov.uk" + uri + "/data", get=get)
    downloads = edition.get("downloads") or []
    if not downloads or not downloads[0].get("file"):
        raise ValueError(f"ONS edition {uri} carries no download")
    release = (landing.get("description") or {}).get("releaseDate")
    return ONS_FILE + uri + "/" + downloads[0]["file"], release


def parse_gb_workbook(blob):
    """[{'month': date, 'workers': n|None, 'employers': n|None}, ...] oldest
    first, from worksheets 1a (potential redundancies) and 1b (employers)."""
    sheets = xlsx_sheets(blob)

    def table(name):
        rows = sheets.get(name) or []
        header = next((i for i, r in enumerate(rows)
                       if r and str(r[0]).strip().lower() == "month"), None)
        if header is None:
            raise ValueError(f"worksheet {name} has no 'Month' header row")
        try:
            gb = [str(c).strip() for c in rows[header]].index("GB")
        except ValueError:
            raise ValueError(f"worksheet {name} has no 'GB' column — the ONS "
                             f"layout changed and a positional guess would be a "
                             f"wrong denominator")
        out = {}
        for row in rows[header + 1:]:
            when = excel_date(row[0] if row else None)
            if when is None:
                continue
            out[when] = _int_or_none(row[gb]) if gb < len(row) else None
        return out

    workers, employers = table("1a"), table("1b")
    return [{"month": m, "workers": workers[m], "employers": employers.get(m)}
            for m in sorted(workers)]


def gb_series(today=None, get=None):
    url, release = gb_latest_workbook_url(get=get)
    rows = parse_gb_workbook(fetch_bytes(url, get=get))
    months = {r["month"]: {"workers": r["workers"], "employers": r["employers"]}
              for r in rows}
    out = window_from_months(months, today=today)
    out.update(publisher_updated=release, source_url=url,
               latest_published_period=max(months).strftime("%Y-%m"),
               series_breaks=GB_SERIES_BREAKS)
    return out


def _month_end(first_of_month):
    nxt = date(first_of_month.year + (first_of_month.month == 12),
               first_of_month.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


# A monthly series is measured over TWELVE settled months, not over the newest
# one. Two reasons, and the second is the one that matters:
#   * a single month of a small country is a denominator of a few hundred, and a
#     coverage figure over that swings tens of points on one notification.
#   * twelve months is the window rolling_recall already uses, so the two
#     figures describe comparable spans of time.
# ALL TWELVE must be present and unsuppressed. A partial sum shrinks the
# denominator and INFLATES coverage, which is the direction a broken
# measurement must never fail in — so a gap raises rather than sums.
WINDOW_MONTHS = 12


def window_from_months(months, today=None, unit_secondary=EMPLOYERS):
    """{date: {'workers': n, 'employers': n}} -> a 12-settled-month period dict.

    The window ends at the last month that CLOSED at least SETTLE_DAYS ago, so
    an event we have not ingested yet is ingest latency rather than a coverage
    gap — rolling_recall's fairness rule, imported rather than re-chosen.
    """
    cutoff = (today or date.today()) - timedelta(days=SETTLE_DAYS)
    settled = sorted(m for m in months if _month_end(m) <= cutoff)
    if len(settled) < WINDOW_MONTHS:
        raise ValueError(f"only {len(settled)} settled months, need {WINDOW_MONTHS}")
    window = settled[-WINDOW_MONTHS:]
    missing = [m.strftime("%Y-%m") for m in window
               if months[m].get("workers") is None]
    if missing:
        raise ValueError(
            f"months with no usable total in the window: {', '.join(missing)} — a "
            f"partial sum would shrink the denominator and INFLATE coverage")
    secondary = [months[m].get(unit_secondary) for m in window]
    return {
        "period": {"kind": "months_12", "label":
                   f"{window[0]:%Y-%m}..{window[-1]:%Y-%m}",
                   "from": window[0].isoformat(),
                   "to": _month_end(window[-1]).isoformat()},
        "value": sum(months[m]["workers"] for m in window),
        "unit": WORKERS,
        "secondary": ({"unit": unit_secondary, "value": sum(secondary),
                       "note": "summed over 12 months, so an employer filing in "
                               "two months counts twice"}
                      if all(v is not None for v in secondary) else None),
    }


# ---------------------------------------------------------------------------
# 3. ESTONIA — koondamisteated (Töötukassa, via avaandmed.eesti.ee)
# ---------------------------------------------------------------------------
# The distribution id is resolved through the catalogue API rather than pinned,
# because the publisher re-uploads the file. THE HISTORY IS RE-READ IN FULL
# EVERY RUN, on purpose: Töötukassa revises back to the start of the previous
# calendar year at every monthly release and revised the whole history in
# January 2025, so an append-only ingest would drift silently and there would be
# nothing in any log to see.
EE_DATASET = "https://avaandmed.eesti.ee/api/datasets?search=koondamised&limit=10"
EE_SLUG = "koondamised"
EE_DISTRIBUTION_TITLE = "Koondamisteate saajate ja tooandjate arv maakonna"
EE_ALL_COUNTIES = "Kõik maakonnad"

# WHICH NOTICE TYPE IS THE DENOMINATOR, AND WHY THE CHOICE IS SAFE.
# The workbook carries two codes, "Teade 1" and "Teade 2", and its own English
# sheet translates every other field and NOT these. Teade 2 runs at 84-89% of
# Teade 1 in every year from 2018 to 2026, which is the signature of a two-stage
# duty over one population rather than two disjoint populations — so they must
# NEVER be summed, and `combine()` would refuse to anyway.
# Teade 1 is taken because it is the WIDER of the two, which puts any error in
# the direction that CANNOT flatter our coverage. If the codes turn out to be
# the other way round, the denominator falls by ~15% and our measured coverage
# RISES; it can never be that we are quietly claiming more than we hold.
EE_NOTICE_TYPE = "Teade 1"


def parse_estonia(blob):
    """{month(date): {'workers': n, 'employers': n}} for EE_NOTICE_TYPE, all
    counties."""
    sheets = xlsx_sheets(blob)
    rows = next((v for v in sheets.values()
                 if v and str((v[0] or [""])[0]).strip().upper() == "KUU"), None)
    if rows is None:
        raise ValueError("no worksheet with a KUU (month) header")
    head = [str(c or "").strip() for c in rows[0]]
    try:
        i_county, i_type = head.index("Maakond"), head.index("Teate liik")
        i_workers = head.index("Koondamisteate saajate arv")
        i_employers = head.index("Tööandjate arv")
    except ValueError as exc:
        raise ValueError(f"Töötukassa column layout changed: {head} ({exc})")
    out = {}
    for row in rows[1:]:
        if len(row) <= max(i_county, i_type, i_workers, i_employers):
            continue
        if str(row[i_county]).strip() != EE_ALL_COUNTIES:
            continue
        if str(row[i_type]).strip() != EE_NOTICE_TYPE:
            continue
        when = excel_date(row[0])
        if when is None:
            continue
        out[when] = {"workers": _int_or_none(row[i_workers]),
                     "employers": _int_or_none(row[i_employers])}
    if not out:
        raise ValueError(f"no rows for {EE_ALL_COUNTIES} / {EE_NOTICE_TYPE}")
    return out


def estonia_series(today=None, get=None):
    catalogue = fetch_json(EE_DATASET, get=get)
    dataset = next((d for d in (catalogue.get("data") or [])
                    if d.get("slug") == EE_SLUG), None)
    if not dataset:
        raise ValueError("avaandmed.eesti.ee no longer lists the 'koondamised' dataset")
    detail = fetch_json("https://avaandmed.eesti.ee/api/datasets/" + dataset["id"],
                        get=get)
    dist = next((d for d in (detail.get("distributions") or [])
                 if (d.get("titleEt") or "").startswith(EE_DISTRIBUTION_TITLE)), None)
    if not dist or not dist.get("accessUrls"):
        raise ValueError("the koondamisteated distribution is no longer published")
    months = parse_estonia(fetch_bytes(dist["accessUrls"][0], get=get))
    out = window_from_months(months, today=today)
    out.update(publisher_updated=dist.get("updatedAt"),
               latest_published_period=max(months).strftime("%Y-%m"),
               notice_type=EE_NOTICE_TYPE, licence=dist.get("license"),
               source_url=dist["accessUrls"][0])
    return out


# ---------------------------------------------------------------------------
# 4. NORTHERN IRELAND — proposed redundancies (NISRA Labour Market Report)
# ---------------------------------------------------------------------------
# A SEPARATE REGIME, NOT A SUBSET OF GB. The Employment Rights (Northern
# Ireland) Order 1996 applies there and TULRCA 1992 s.193 does not, and the ONS
# HR1 series is explicitly GREAT BRITAIN. Substituting one for the other would
# drop Northern Ireland entirely; adding them is only legitimate where the
# periods align, which `combine()` checks and which the GB monthly / NI
# financial-year shapes currently do not.
#
# THE XLSX IS NOT FETCHED. The figures are read out of the HTML report, whose
# charts carry their data as base64 CSV data: URIs — the same numbers, on a host
# that does not disallow them.
NI_REPORT = ("https://datavis.nisra.gov.uk/economy-and-labour-market/"
             "labour-market-report-{month}-{year}.html")
NI_HEADER = '"Year","Proposed","Confirmed"'


def ni_report_url(today=None):
    """NISRA publishes one report per month, named for that month."""
    today = today or date.today()
    return NI_REPORT.format(month=today.strftime("%B").lower(), year=today.year)


def parse_ni(html):
    """[{'financial_year': '2024/25', 'proposed': n, 'confirmed': n}, ...].

    THE LAST ROW IS NOT A FINANCIAL YEAR. It is labelled like one and the
    report's own prose describes the same pair of numbers as "the twelve months
    to <report month>" — a rolling window wearing a financial year's label. It
    is returned with `rolling=True` and it is never measured against, because a
    denominator whose period cannot be stated is not a denominator.
    """
    for blob in re.findall(r'base64,([A-Za-z0-9+/=]{100,})"', html):
        try:
            body = b64decode(blob)
        except Exception:                          # noqa: BLE001
            continue
        if not body.startswith(NI_HEADER.encode()):
            continue
        rows = []
        for line in body.decode("utf-8", "replace").splitlines()[1:]:
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) < 3 or not re.fullmatch(r"\d{4}/\d{2}", parts[0]):
                continue
            rows.append({"financial_year": parts[0],
                         "proposed": _int_or_none(parts[1]),
                         "confirmed": _int_or_none(parts[2]),
                         "rolling": False})
        if rows:
            rows[-1]["rolling"] = True
            return rows
    raise ValueError("no redundancy series found in the NISRA report — the chart "
                     "no longer embeds its data, or the report moved")


def ni_series(today=None, get=None):
    url = ni_report_url(today)
    html = fetch_bytes(url, get=get).decode("utf-8", "replace")
    rows = [r for r in parse_ni(html) if not r["rolling"] and r["proposed"] is not None]
    if not rows:
        raise ValueError("every NISRA row is the rolling twelve-month window")
    latest = rows[-1]
    start = int(latest["financial_year"][:4])
    return {
        "period": {"kind": "financial_year_apr_mar", "label": latest["financial_year"],
                   "from": f"{start}-04-01", "to": f"{start + 1}-03-31"},
        "value": latest["proposed"],
        "unit": WORKERS,
        "secondary": {"unit": WORKERS, "value": latest["confirmed"],
                      "label": "confirmed redundancies (GB has no counterpart)"},
        "publisher_updated": None,
        "source_url": url,
        "rounding": "figures are rounded to the nearest 10; totals from fewer "
                    "than 3 businesses are suppressed",
    }


# ---------------------------------------------------------------------------
# THE REGISTRY
# ---------------------------------------------------------------------------
# `country` MUST be spelled as `alt_normalize_country` spells it, because it is
# sent to /aggregate as a filter. A country the vocabulary spells differently
# would silently return a zero numerator, which reads as a coverage disaster
# rather than as the typo it is.
SERIES = {
    "tw_mass_dismissal_notifications": {
        "country": "Taiwan",
        "label": "Taiwan 大量解僱通報 — plants and workers notified under the "
                 "Act for Worker Protection of Mass Dismissal, art. 4",
        "authority": "勞動部 (Ministry of Labor)",
        "cadence": "annual",
        "unit": WORKERS,
        "counts": "workers notified, annually, by ROC year",
        "collector": taiwan_series,
        "licence": "政府資料開放授權條款 (Open Government Data License), free reuse",
        "robots": ("apiservice.mol.gov.tw returns an F5 'Request Rejected' page for "
                   "/robots.txt itself, so no directive could be read. The data "
                   "endpoints answer 200 to our own identifying agent string under an "
                   "explicit open-data licence, and no block aimed at agents was "
                   "found. Recorded as PERMITTED WITH THE ROBOTS FILE UNREADABLE — "
                   "if that ever becomes a 403 to this agent it is a refusal and "
                   "stays one. statfy.mol.gov.tw was unreachable and its robots.txt "
                   "has never been read: treat as NOT permitted"),
        "caveats": [
            "家數 counts 廠場 (establishments/plants), so one company notifying for "
            "four sites counts four times — the establishment figure is NOT an "
            "employer count and must not be compared with GB's employer column",
            "annual only, ROC years, roughly a six-month lag",
        ],
    },
    "gb_hr1_potential_redundancies": {
        "country": "United Kingdom",
        "label": "Great Britain HR1 potential redundancies (TULRCA 1992 s.193)",
        "authority": "Insolvency Service, published by ONS",
        "cadence": "monthly",
        "unit": WORKERS,
        "counts": "potential redundancies on HR1 forms, by month of RECEIPT",
        "collector": gb_series,
        "licence": "Open Government Licence v3.0",
        "robots": "ons.gov.uk serves no robots.txt (404) — no directive to obey",
        "caveats": [
            "POTENTIAL redundancies at the date the HR1 was received, not actual job "
            "losses, and not the month the redundancies take effect — it runs on a "
            "different clock from anything we date by event",
            "GREAT BRITAIN ONLY. Northern Ireland is a separate regime and a separate "
            "slice. Our own country vocabulary has no GB/NI split, so this slice's "
            "NUMERATOR includes Northern Irish events while its denominator does not "
            "— a bias UPWARD on measured coverage, bounded by NI's small share",
            "proposals under 20 are out of scope of the duty; TUPE, pension and "
            "contract-variation filings are stripped; agriculture is excluded",
            "'[c]' marks confidential suppression and is read as MISSING, never 0",
            "official statistics in development, and revisable",
        ],
        "series_breaks": GB_SERIES_BREAKS,
    },
    "ee_collective_redundancy_notices": {
        "country": "Estonia",
        "label": "Estonia koondamisteated — recipients of collective redundancy "
                 "notices filed with Töötukassa",
        "authority": "Eesti Töötukassa",
        "cadence": "monthly",
        "unit": WORKERS,
        "counts": "persons named in redundancy notices (notice type 'Teade 1')",
        "collector": estonia_series,
        "licence": "CC BY-NC 3.0 — non-commercial. Used here to MEASURE, never "
                   "republished to a reader-facing surface",
        "robots": ("avaandmed.eesti.ee and andmed.eesti.ee both serve no robots.txt "
                   "(404). tootukassa.ee allows the statistics path with "
                   "Crawl-delay: 10, and is not fetched by this collector"),
        "caveats": [
            "the series is revised back to the start of the previous calendar year at "
            "every monthly release, and the whole history was revised in January 2025 "
            "— this collector re-reads the FULL history every run for that reason",
            "'Teade 1' vs 'Teade 2' is undefined in the file's own legend; Teade 2 "
            "runs at 84-89% of Teade 1 every year, so they are two stages of one duty "
            "and are never summed. The wider one is used, which cannot flatter us",
        ],
    },
    "ni_proposed_redundancies": {
        "country": "United Kingdom",
        "label": "Northern Ireland proposed redundancies (Employment Rights (NI) "
                 "Order 1996)",
        "authority": "NISRA, for the Department for the Economy",
        "cadence": "annual",
        "unit": WORKERS,
        "counts": "proposed redundancies, by financial year (April-March)",
        "collector": ni_series,
        # THE DENOMINATOR IS READABLE AND THE NUMERATOR IS NOT, which is a
        # different failure from every other row here and must not be smoothed
        # over. Our country vocabulary spells Northern Irish rows "United
        # Kingdom", so the only numerator available covers the whole UK and the
        # ratio came out at 177% on the first run — a number that says nothing
        # about coverage and everything about the mismatch. The denominator is
        # still fetched, recorded and freshness-checked every run, so the day a
        # region field exists this becomes a measurement by deleting one line.
        "numerator_available": False,
        "no_numerator_why": (
            "the denominator covers Northern Ireland alone and the tracker's country "
            "vocabulary has no NI split — every NI row is stored as 'United Kingdom'. "
            "A UK numerator over an NI denominator is not a coverage figure (it "
            "measured 177% on the first run). The denominator is read and kept fresh "
            "so that this becomes measurable the day rows carry a UK region"),
        "licence": "accredited official statistics, Open Government Licence",
        "robots": ("datavis.nisra.gov.uk serves no readable robots.txt. "
                   "nisra.gov.uk's wildcard block names admin paths only. The XLSX "
                   "is NOT fetched either way — the HTML report carries the same "
                   "figures and a previous assessment recorded an xlsx disallow"),
        "caveats": [
            "a SEPARATE regime from GB, never a substitute for it. NI is the only "
            "part of the UK that publishes CONFIRMED redundancies as well as "
            "proposed, so no UK-wide confirmed figure exists",
            "the final row of the published series is labelled as a financial year "
            "but is the rolling twelve months to the report month — it is excluded",
            "rounded to the nearest 10; totals from fewer than 3 businesses withheld",
            "our country vocabulary has no NI split, so this slice's numerator is "
            "the whole UK. It is reported as an UPPER-BOUND-ONLY comparison",
        ],
    },
}

# ---------------------------------------------------------------------------
# THE NEGATIVE FINDINGS — countries that publish a total we still cannot use
# ---------------------------------------------------------------------------
# These are worth as much as the four above, and more than an estimate would be.
# Each says what is published, what stops us, and when it was checked. They
# EXPIRE (MAX_ASSESSMENT_AGE_DAYS) so that a standing refusal cannot become a
# permanent exemption nobody revisits.
#
# THE LINE THEY SHARE, stated once: a denominator this project ASSEMBLES is not
# an independent denominator. Poland and Iceland publish their figures as prose
# on a page that carries only the current period and keeps no archive, so any
# history would exist only in our own file — we would be measuring ourselves
# against our own record-keeping and calling it an authority's count.
ASSESSED = "2026-08-18"
NOT_BUILDABLE = {
    "nl_collective_dismissal_notifications": {
        "country": "Netherlands",
        "label": "Netherlands WMCO collective dismissal notifications",
        "why": ("the current reports sit behind an Anubis proof-of-work interstitial on "
                "cao.minszw.nl. A proof-of-work wall is not a robots directive but it "
                "is equally not ours to solve, so it is refused rather than defeated. "
                "The UWV January press release carries the headline (355 notifications "
                "/ ~25,000 employees for 2025) as annual prose, which is a citation "
                "and not a series"),
    },
    "ro_collective_dismissal": {
        "country": "Romania",
        "label": "Romania ANOFM collective dismissal notifications",
        "why": ("published, and only inside an annual report PDF as a month-by-month "
                "table. Reading it needs a PDF dependency added to a hash-pinned lock "
                "for one country, and the lock exists because twenty workflows once "
                "installed unverified packages next to two API keys. Worth revisiting "
                "if a second PDF-only country becomes buildable at the same time"),
    },
    "lv_collective_redundancy": {
        "country": "Latvia",
        "label": "Latvia NVA collective redundancy notifications",
        "why": ("published as PROSE inside an annual PDF report, roughly six months "
                "behind. Same lock objection as Romania, and worse: prose rather than "
                "a table, so the parse would be brittle as well as costly"),
    },
    "pl_group_layoffs": {
        "country": "Poland",
        "label": "Poland GUS zwolnienia grupowe (establishments and workers)",
        "why": ("published monthly on ssgk.stat.gov.pl, and the page carries ONLY the "
                "current month with no archive: the figures are Polish prose rounded "
                "to the nearest 0.1 thousand ('3,1 tys.'). A series could only be "
                "built by accumulating our own captures, at which point the "
                "denominator is ours and not the publisher's — the one thing this "
                "framework must not do. stat.gov.pl allows everything; "
                "psz.praca.gov.pl names ClaudeBot and disallows all, and is never "
                "fetched"),
    },
    "is_hopuppsagnir": {
        "country": "Iceland",
        "label": "Iceland Vinnumálastofnun hópuppsagnir",
        "why": ("monthly, as a prose news post, 1-3 days after month end — and a month "
                "with no collective redundancies gets NO POST AT ALL. Absence is "
                "therefore not zero, and a collector could never tell 'no cuts' from "
                "'not published yet' or 'the post moved'. Combined with an unarchived "
                "prose format, that makes the series unusable as a denominator even "
                "though the underlying figure is real"),
    },
}


# ---------------------------------------------------------------------------
# THE NUMERATOR — what we hold, as a band
# ---------------------------------------------------------------------------

def _aggregate(params, get=None):
    url = SITE + "/wp-json/layoffs/v1/aggregate?" + urllib.parse.urlencode(params)
    body = fetch_bytes(url, get=get, cache=False)
    return (json.loads(body.decode("utf-8", "replace")) or {}).get("totals") or {}


def held(country, period, get=None):
    """(lower, upper, detail) jobs we hold for `country` over `period`.

    Two reads, and the difference between them is the whole band: strict job
    location, then `country_basis=any`, which additionally admits any row whose
    EMPLOYER is domiciled there — a global cut counted whole. See the module
    docstring.
    """
    base = {"country": country, "from": period["from"], "to": period["to"],
            "date_basis": "notice", "cb": os.urandom(5).hex()}
    strict = _aggregate(base, get=get)
    loose = _aggregate(dict(base, country_basis="any", cb=os.urandom(5).hex()), get=get)
    return (int(strict.get("jobs") or 0), int(loose.get("jobs") or 0),
            {"entries_strict": int(strict.get("entries") or 0),
             "entries_any": int(loose.get("entries") or 0)})


# ---------------------------------------------------------------------------
# THE SLICE
# ---------------------------------------------------------------------------

def measure_series(key, today=None, get=None, agg_get=None):
    spec = SERIES[key]
    slice_ = {"key": key, "country": spec["country"], "label": spec["label"],
              "authority": spec["authority"], "cadence": spec["cadence"],
              "unit": spec["unit"], "counts": spec["counts"],
              "licence": spec["licence"], "robots": spec["robots"],
              "caveats": spec["caveats"],
              "denominator_basis": "national_notification_aggregate"}
    if spec.get("series_breaks"):
        slice_["series_breaks"] = spec["series_breaks"]
    try:
        series = spec["collector"](today=today, get=get) if key != \
            "tw_mass_dismissal_notifications" else spec["collector"](get=get)
    except TaiwanWrongDataset as exc:
        slice_.update(state=UNKNOWN, detail=(
            f"REFUSED the fetched dataset: {exc}. No figure, because the wrong one "
            f"here is 43x too large and would read as near-zero coverage"))
        return slice_
    except _TLS_FAULT as exc:
        # NOT a publisher outage and NOT permission to stop verifying. Some of
        # these ministries serve a chain that newer OpenSSL rejects (Taiwan's
        # intermediate carries no Subject Key Identifier, which OpenSSL 3.6
        # treats as fatal and 3.0 does not), so the same URL verifies on the CI
        # runner and fails on a developer's laptop. It resolves to UNKNOWN from
        # the environment that could not check — never to a pass, and never by
        # passing an unverified context.
        slice_.update(state=UNKNOWN, detail=(
            f"TLS chain verification failed from THIS environment ({exc}) — the "
            f"publisher's certificate chain is rejected by the local OpenSSL, which is "
            f"an environment fact, not a coverage fact and not a source outage. "
            f"UNKNOWN from here, and the workflow run is the place to check before "
            f"treating it as a breakage. "
            f"Verification is never to be disabled to clear this"))
        return slice_
    except Exception as exc:                       # noqa: BLE001
        slice_.update(state=UNKNOWN, detail=(
            f"could not read the denominator ({type(exc).__name__}: {exc}) — the "
            f"publisher moved, changed layout or was unreachable. UNVERIFIED, not a "
            f"coverage regression"))
        return slice_

    slice_.update(period=series["period"], denominator=series["value"],
                  secondary=series.get("secondary"),
                  publisher_updated=series.get("publisher_updated"),
                  source_url=series.get("source_url"))
    if not series.get("value"):
        slice_.update(state=UNKNOWN, detail=(
            "the publisher's latest settled period carries no usable total "
            "(suppressed or empty) — UNKNOWN, never a zero denominator"))
        return slice_

    # Has the publisher stopped? Judged on the period we could measure, against
    # the cadence's real ceiling.
    lag = ((today or date.today()) - date(*(int(x) for x
                                            in series["period"]["to"].split("-")))).days
    ceiling = MAX_SERIES_LAG_DAYS.get(spec["cadence"], 550)
    slice_["period_age_days"] = lag
    if lag > ceiling:
        slice_.update(state=UNKNOWN, detail=(
            f"the newest settled period ends {lag} days ago (ceiling {ceiling} for a "
            f"{spec['cadence']} series) — the publisher has probably stopped or moved "
            f"the file. The denominator is STALE, so no coverage figure is reported"))
        return slice_

    if not spec.get("numerator_available", True):
        slice_.update(state=NOT_MEASURABLE, detail=(
            f"the denominator IS published and was read live "
            f"({series['value']:,} {spec['unit']}, {series['period']['label']}), and "
            f"no matching numerator exists: {spec['no_numerator_why']}"))
        return slice_

    try:
        lower, upper, detail = held(spec["country"], series["period"], get=agg_get)
    except Exception as exc:                       # noqa: BLE001
        slice_.update(state=UNKNOWN, detail=(
            f"the denominator was read but our own /aggregate could not be "
            f"({type(exc).__name__}: {exc}) — a host outage must never manufacture a "
            f"coverage regression"))
        return slice_

    n = series["value"]
    slice_.update(held_jobs_strict=lower, held_jobs_any=upper, held_detail=detail,
                  coverage_lower=lower / n, coverage_upper=upper / n)
    if upper > n:
        slice_.update(state=OVER_UNIVERSE, detail=(
            f"we hold {upper:,} jobs on the inclusive basis against a notified "
            f"{n:,} — the numerator has left the denominator's universe (events "
            f"below the notification threshold, announcements never notified, and "
            f"global cuts counted whole). The lower, strict-location figure is "
            f"{lower:,} = {lower / n:.1%}; the upper is NOT a coverage figure"))
        return slice_

    _, lo, hi = wilson(lower, n)
    slice_.update(state=MEASURED, confirmed_interval=[lo, hi], detail=(
        f"of the {n:,} {spec['unit']} notified to {spec['authority']} in "
        f"{series['period']['label']}, we hold between {lower:,} "
        f"({lower / n:.1%}) and {upper:,} ({upper / n:.1%}) jobs"))
    return slice_


def assess_not_buildable(key, today=None):
    spec = NOT_BUILDABLE[key]
    slice_ = {"key": key, "country": spec["country"], "label": spec["label"],
              "assessed_at": ASSESSED, "denominator_basis":
              "national_notification_aggregate"}
    age = ((today or date.today())
           - date(*(int(x) for x in ASSESSED.split("-")))).days
    if age > MAX_ASSESSMENT_AGE_DAYS:
        slice_.update(state=UNKNOWN, detail=(
            f"the 'published but not usable' assessment is {age} days old (max "
            f"{MAX_ASSESSMENT_AGE_DAYS}) — publishers change format and drop walls, so "
            f"this is UNVERIFIED rather than still true. Re-check per RUNBOOK 'is a "
            f"national denominator buildable yet?'"))
        return slice_
    slice_.update(state=NOT_MEASURABLE, detail=spec["why"])
    return slice_


# ---------------------------------------------------------------------------
# THE REPORT
# ---------------------------------------------------------------------------
# Declared here, not discovered at runtime, so a slice that fails to compute
# still APPEARS as UNKNOWN instead of vanishing. rolling_recall's rule.
DECLARED_SLICES = tuple(SERIES) + tuple(NOT_BUILDABLE)


def combine(slices):
    """Sum two or more measured slices — and refuse unless they agree on BOTH
    the unit and the period.

    This function exists to be refused. There is no worldwide denominator in
    this module and there must not be one: Directive 98/59/EC lets each member
    state pick its own threshold, establishments and enterprises are different
    objects, and Taiwan counts plants. Adding Sweden's five-worker floor to
    Croatia's twenty produces a number that means nothing and looks
    authoritative, which is worse than no number at all.
    """
    if not slices:
        raise IncomparableSeries("nothing to combine")
    units = {s.get("unit") for s in slices}
    if len(units) > 1:
        raise IncomparableSeries(
            f"these series do not count the same thing: {sorted(units)}. A sum over "
            f"different units is not a quantity")
    periods = {(s.get("period") or {}).get("kind") for s in slices}
    labels = {(s.get("period") or {}).get("label") for s in slices}
    if len(periods) > 1 or len(labels) > 1:
        raise IncomparableSeries(
            f"these series do not describe the same period: kinds={sorted(periods)}, "
            f"labels={sorted(labels)}. Two totals over different windows do not add")
    states = {s.get("state") for s in slices}
    if states != {MEASURED}:
        raise IncomparableSeries(
            f"only MEASURED slices may be combined; got {sorted(states)}")
    return sum(s["denominator"] for s in slices)


def measure(today=None, get=None, agg_get=None, progress=None):
    slices = {}
    for key in DECLARED_SLICES:
        try:
            if key in SERIES:
                if progress:
                    progress(f"measuring {key}")
                slices[key] = measure_series(key, today=today, get=get, agg_get=agg_get)
            else:
                slices[key] = assess_not_buildable(key, today=today)
        except Exception as exc:                   # noqa: BLE001 — a crash is UNKNOWN
            slices[key] = {"key": key, "state": UNKNOWN,
                           "detail": f"measurement raised {type(exc).__name__}: {exc}"}
    return {
        "note": ("Coverage against national collective-redundancy denominators the "
                 "tracker does not construct. Written by national-denominators.yml. "
                 "NEVER hand-edit a figure here — re-run the module. Every figure is a "
                 "BAND (strict job location .. inclusive employer basis) and describes "
                 "the NOTIFIED population only, never 'layoffs in the country'. These "
                 "denominators are NOT comparable across countries and must never be "
                 "summed — see combine()."),
        "measured_at": _utc_now_iso(),
        "declared_slices": list(DECLARED_SLICES),
        "slices": slices,
    }


def judge(measurement, now=None):
    """(state, detail) for the whole report. ONE definition, imported by
    ops_status and the tests.

    NO FLOOR, deliberately, and for a stronger reason than rolling_recall's: at
    these denominators a single large notification moves the ratio by tens of
    points, so any floor would be a false-alarm generator, and this repo already
    knows what eight identical emails in one afternoon do to an alert channel.
    What is enforced is that the figures EXIST, are FRESH, and name every slice
    they could not compute.
    """
    if not isinstance(measurement, dict):
        return UNKNOWN, ("no national-denominator measurement has been written yet — "
                         "coverage outside the US is UNMEASURED, not fine. Run "
                         "`python3 railway/national_denominators.py --write`")
    age = _days_since(measurement.get("measured_at"), now)
    if age is None:
        return UNKNOWN, (f"measurement has no readable timestamp: "
                         f"{measurement.get('measured_at')!r}")
    if age > MAX_MEASUREMENT_AGE_DAYS:
        return UNKNOWN, (f"the measurement is {age:.0f} days old (max "
                         f"{MAX_MEASUREMENT_AGE_DAYS}) — either this checkout is behind "
                         f"main or national-denominators.yml has stopped. UNVERIFIED, "
                         f"not passing")
    declared = measurement.get("declared_slices") or []
    slices = measurement.get("slices") or {}
    missing = [k for k in declared if k not in slices]
    if missing:
        return UNKNOWN, (f"declared slice(s) absent from the report: "
                         f"{', '.join(missing)} — a slice that cannot be computed must "
                         f"say so, not disappear")
    bad = [k for k, s in slices.items()
           if s.get("state") not in (MEASURED, NOT_MEASURABLE)]
    if bad:
        first = slices[bad[0]]
        return UNKNOWN, (f"{len(bad)} of {len(slices)} slice(s) not measured: "
                         f"{bad[0]} — {first.get('detail')}")
    parts = []
    for key in declared:
        s = slices[key]
        if s.get("state") == MEASURED:
            parts.append(f"{key}: {s['coverage_lower']:.1%}-{s['coverage_upper']:.1%} "
                         f"of {s['denominator']:,} ({s['period']['label']})")
        else:
            parts.append(f"{key}: not measurable")
    return PASS, "; ".join(parts)


def load_measurement(path=None):
    try:
        return json.loads(Path(path or MEASUREMENT_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_measurement(measurement, path=None):
    path = Path(path or MEASUREMENT_PATH)
    path.write_text(json.dumps(measurement, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------

def _render(measurement):
    lines = [f"NATIONAL DENOMINATORS  measured_at={measurement.get('measured_at')}"]
    for key in measurement.get("declared_slices") or []:
        s = (measurement.get("slices") or {}).get(key) or {
            "state": UNKNOWN, "detail": "absent from the report"}
        state = s.get("state", UNKNOWN)
        lines.append(f"  [{'MEASURED' if state == MEASURED else state.upper()}] "
                     f"{key}  ({s.get('country')})")
        lines.append(f"      {s.get('label', '')}")
        if state == MEASURED:
            lines.append(f"      {s['period']['label']}: {s['denominator']:,} "
                         f"{s['unit']} notified to {s['authority']}")
            lines.append(f"      we hold {s['held_jobs_strict']:,}..{s['held_jobs_any']:,}"
                         f"  =  {s['coverage_lower']:.1%}..{s['coverage_upper']:.1%}"
                         f"   (Wilson on the lower end: "
                         f"{s['confirmed_interval'][0]:.1%}-"
                         f"{s['confirmed_interval'][1]:.1%})")
        else:
            lines.append(f"      {s.get('detail')}")
    state, detail = judge(measurement)
    lines.append(f"  VERDICT {state.upper()}: {detail}")
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--offline" in argv:
        print(f"{len(SERIES)} collectors declared, {len(NOT_BUILDABLE)} assessed "
              f"not buildable, assessed {ASSESSED}")
        for key, spec in SERIES.items():
            print(f"  {key:38s} {spec['country']:16s} {spec['cadence']:8s} "
                  f"{spec['unit']}")
        for key, spec in NOT_BUILDABLE.items():
            print(f"  {key:38s} {spec['country']:16s} NOT MEASURABLE")
        return 0
    measurement = measure(progress=lambda m: print(f"  .. {m}", file=sys.stderr))
    if "--write" in argv:
        print(f"wrote {write_measurement(measurement)}", file=sys.stderr)
    print(_render(measurement))
    state, _ = judge(measurement)
    return {PASS: 0, UNKNOWN: 3}[state]


if __name__ == "__main__":
    sys.exit(main())
