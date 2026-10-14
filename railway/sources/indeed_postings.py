"""Indeed Hiring Lab job postings index (US): reference data, MACRO CONTEXT.

WHAT THIS IS
------------
Indeed Hiring Lab publishes its job postings index on GitHub
(https://github.com/hiring-lab/job_postings_tracker), CC BY 4.0, keyless. The
index is 100 on 2020-02-01. We read two daily US files:

* `US/job_postings_by_sector_US.csv`  - total postings per occupational sector
* `US/aggregate_job_postings_US.csv`  - all postings, seasonally adjusted

and keep the LAST value of each ISO week per series over a trailing window,
dated by that observation (the week-ending date we have). Daily rows are ~12 MB;
weekly over WINDOW_YEARS is a few hundred KB.

IMPORTANT LABELING
------------------
Postings are demand for hiring, not layoffs. Never summed into, blended with or
compared one-to-one against the tracker's layoff rows, and nothing here says AI
caused a change.

SHAPE: datasets.weekly = [[sector, week_ending, index], ...], `fields` names
the columns; GET /reference/indeed_postings?sector=... filters rows.
Stdlib only; parsing is pure and tested offline.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from datetime import date, datetime, timezone

SOURCE = "indeed_postings"
BASE = "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/US/"
SECTOR_FILE = "job_postings_by_sector_US.csv"
AGGREGATE_FILE = "aggregate_job_postings_US.csv"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
WINDOW_YEARS = 3
ALL_SECTORS = "All postings (seasonally adjusted)"
FIELDS = ["sector", "week_ending", "index"]

ATTRIBUTION = ("Source: Indeed Hiring Lab, Job Postings Index "
               "(https://github.com/hiring-lab/job_postings_tracker), CC BY 4.0. "
               "Index, 1 February 2020 = 100.")
LICENCE = "CC BY 4.0, attribution required"
NOTE = ("Job postings measure hiring demand. They are not layoffs and are not "
        "added to the tracker's counts, and a change here does not show that AI caused it.")


def _rows(text, value_col, name_col=None):
    out = []
    try:
        for r in csv.DictReader(io.StringIO(text or "")):
            if (r.get("variable") or "").strip() != "total postings":
                continue
            try:
                d = date.fromisoformat((r.get("date") or "").strip())
                v = float(r.get(value_col) or "")
            except ValueError:
                continue
            name = (r.get(name_col) or "").strip() if name_col else ALL_SECTORS
            if name:
                out.append((name, d, v))
    except csv.Error:
        return []
    return out


def parse_sector_csv(text):
    return _rows(text, "indeed_job_postings_index", "display_name")


def parse_aggregate_csv(text):
    return _rows(text, "indeed_job_postings_index_SA")


def weekly_rows(rows, start):
    """Last observation per (series, ISO week) on or after `start`, sorted."""
    keep = {}
    for name, d, v in rows:
        if d < start:
            continue
        k = (name, d.isocalendar()[:2])
        if k not in keep or d > keep[k][0]:
            keep[k] = (d, v)
    return sorted(([n, d.isoformat(), v] for (n, _), (d, v) in keep.items()),
                  key=lambda r: (r[0], r[1]))


def window_start(today=None):
    today = today or datetime.now(timezone.utc).date()
    return date(today.year - WINDOW_YEARS, today.month, 1)


def build_payload(sector_text, aggregate_text, today=None, errors=None):
    start = window_start(today)
    rows = (weekly_rows(parse_aggregate_csv(aggregate_text), start)
            + weekly_rows(parse_sector_csv(sector_text), start))
    latest = max((r[1] for r in rows), default=None)
    return {
        "source": SOURCE,
        "updated": datetime.now(timezone.utc).isoformat(),
        "fields": FIELDS,
        "datasets": {"weekly": rows},
        "rows": len(rows),
        "sectors": sorted({r[0] for r in rows}),
        "latest": {"weekly": latest[:7]} if latest else {},
        "attribution": ATTRIBUTION,
        "licence": LICENCE,
        "note": NOTE,
        "errors": list(errors or []),
    }


def fetch(name, opener=urllib.request.urlopen, timeout=60):
    req = urllib.request.Request(BASE + name, headers={"User-Agent": UA})
    with opener(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def pull(today=None, opener=urllib.request.urlopen):
    texts, errors = {}, []
    for name in (SECTOR_FILE, AGGREGATE_FILE):
        try:
            texts[name] = fetch(name, opener)
        except Exception as exc:  # network: record and let should_store refuse
            errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:200]}")
            texts[name] = ""
    return build_payload(texts[SECTOR_FILE], texts[AGGREGATE_FILE], today, errors)
