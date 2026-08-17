"""US federal RIF separations (OPM EHRI) — executed Reduction-in-Force records.

OPM's Enterprise Human Resources Integration (EHRI) publishes federal separation
microdata via a keyless open API. We filter to `separation_category_code == 'SH'`
(REDUCTION IN FORCE (RIF)), group by agency and effective month, and post each
meaningful agency RIF wave.

WHAT COUNTS, AND WHAT DELIBERATELY DOES NOT
-------------------------------------------
This source publishes ONE thing: separations OPM has already coded `SH`, the
executed statutory Reduction in Force. That is the documented floor — an action
that legally happened, recorded by the employer of record.

It deliberately EXCLUDES three categories that are real but are not RIFs, and
that a survey-based tracker may well fold into one headline "federal cuts"
figure. Measured over the 2026-06 file set, effective-year 2025:

    SH  REDUCTION IN FORCE (RIF)     10,739   <- this source
    drp_indicator == 'Y'            138,074   Deferred Resignation Program
    SE  RETIREMENT - EARLY OUT       27,638   VERA/VSIP early-outs
    SJ  TERMINATION (EXPIRED APPT)   37,970   incl. probationary terminations

Deferred resignations are, on the record, voluntary separation agreements;
early-outs are incentivised retirements; expired-appointment terminations are
mostly ordinary term-appointment endings. Folding any of them into a "layoffs"
count would move the headline by two orders of magnitude on a definition change
alone, which is exactly the kind of number this tracker exists not to publish.
Announced-but-not-executed federal cuts, and the deferred-resignation waves,
reach the tracker through the NEWS pipeline where they carry a named report.
`pull_federal_drp_dryrun()` prints the DRP figures for review; it is DORMANT and
posts nothing. Widening this source is an owner decision, not a tuning knob.

HOW THE FILES ACTUALLY WORK (this was wrong until 2026-08-16)
-------------------------------------------------------------
List current files:  GET /api/v1/files/separations?current=true   (258 files,
one per month back to 2005), then assemble the Parquet path yourself — the
metadata carries no url field:
  GET /api/v1/files/separations/{year}/{month}/{version}/download

Each file is the batch of personnel actions REPORTED in that month. Its bulk
carries that month's own effective date, plus a long tail of late-reported
actions with earlier effective months. The files are INCREMENTAL, not snapshots,
so an effective month's true total is the SUM of its slices across every
reporting file. Verified: effective month 202509 appears as 119,807 separations
in file 202509 and then as 3,447 / 1,704 / 4,058 / 1,982 / 1,708 / 424 / 172 /
168 in the eight files after it — trickles, not repeats of the bulk.

This module previously read ONLY the newest file and its docstring asserted
"each monthly file is a ROLLING ~24-month window ... never sum across files
(double-counts)". Both halves were false, and the consequence was severe: the
collector saw each older month's late-reported trickle and never its bulk file,
so effective-year 2025 landed as 47 RIF separations against a true 10,739, and
the July 2025 wave (5,584) was absent entirely.

Because totals are summed across files, a run that cannot read every file in its
window computes a total that is too SMALL — and `/bulk` field-updates on hash
match, so posting it would OVERWRITE a correct larger count with a partial one.
Any download failure therefore raises rather than posting a partial sum.

For the same reason the window has a hard floor: effective months BEFORE the
window start are only partially covered by the files inside it, so they are
dropped rather than published short.

Structured government data -> route through /bulk (no LLM), like WARN. No paid
model call is made anywhere in this path.
"""
import hashlib
import io
import os

import requests

OPM_BASE = "https://data.opm.gov/api/v1/files"
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SOURCE_URL = "https://data.opm.gov/explore-data/analytics/workforce-changes"

# Earliest REPORTING file to read, and therefore the earliest effective month we
# are entitled to publish. Widen for a one-off backfill (FEDERAL_RIF_SINCE
# =2005-01 reads all 258 files); the monthly job keeps the short window so it
# stays a ~26MB download.
DEFAULT_SINCE = "2024-01"


class FederalRifIncomplete(RuntimeError):
    """A file in the window could not be read, so every total would be short."""


def _since():
    raw = (os.environ.get("FEDERAL_RIF_SINCE") or DEFAULT_SINCE).strip()
    parts = raw.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"FEDERAL_RIF_SINCE must be YYYY-MM, got {raw!r}")
    return f"{int(parts[0]):04d}{int(parts[1]):02d}"      # YYYYMM


def _current_files(since_yyyymm):
    """Current file metadata at or after since_yyyymm, oldest first."""
    r = requests.get(f"{OPM_BASE}/separations", params={"current": "true"},
                     headers=UA, timeout=60)
    r.raise_for_status()
    meta = r.json()
    if not isinstance(meta, list) or not meta:
        raise FederalRifIncomplete("OPM file listing was empty or not a list")
    out = []
    for f in meta:
        try:
            ym = f"{int(f['year']):04d}{int(f['month']):02d}"
        except Exception:
            continue
        if ym >= since_yyyymm:
            out.append(f)
    out.sort(key=lambda f: (str(f["year"]), str(f["month"]), int(f.get("version", 0) or 0)))
    return out


def _read_rif_counts(f, sums):
    """Add one reporting file's SH rows into sums[(yyyymm, agency)]."""
    import pandas as pd
    url = f"{OPM_BASE}/separations/{f['year']}/{f['month']}/{f['version']}/download"
    try:
        resp = requests.get(url, headers=UA, timeout=180)
        resp.raise_for_status()
        df = pd.read_parquet(io.BytesIO(resp.content), columns=[
            "count", "personnel_action_effective_date_yyyymm",
            "separation_category_code", "agency"])
    except Exception as e:
        raise FederalRifIncomplete(f"{f.get('filename')}: {e}") from e
    if "separation_category_code" not in df.columns:
        raise FederalRifIncomplete(f"{f.get('filename')}: no separation_category_code column")
    rif = df[df["separation_category_code"] == "SH"]
    if rif.empty:
        return 0
    n = 0
    counts = pd.to_numeric(rif["count"], errors="coerce").fillna(1).astype(int)
    for ym, agency, c in zip(rif["personnel_action_effective_date_yyyymm"],
                             rif["agency"], counts):
        ym = str(ym)
        if len(ym) != 6 or not ym.isdigit():
            continue
        sums[(ym, str(agency).strip().title())] += int(c)
        n += int(c)
    return n


def _entry(agency, jobs, date, yyyymm):
    if jobs <= 0 or jobs > 100000:
        return None
    if date < "2015-01-01" or date > "2028-12-31":
        return None
    excerpt = (f"Reduction in force at {agency} (US federal agency). {jobs:,} employees "
               f"separated via RIF, effective {date[:7]}. Source: OPM EHRI separations data.")
    hash_input = f"fedrif{agency.lower().strip()}{yyyymm}"   # excludes count: OPM revises months
    return {
        "source_type": "federal_rif",
        "source_name": "OPM EHRI federal RIF",
        "verification_level": "warn",
        "company_name": agency,
        "ticker": None,
        "job_count": jobs,
        "layoff_date": date,
        "industry": None,
        "country": "United States",
        "state": "",
        "roles": None,
        "excerpt": excerpt,
        "reason_tags": ["federal_workforce"],  # was restructuring; the Government/public-sector filter returned ZERO rows from the one collector built for it (F21). /bulk field-updates on hash match, so the next monthly import re-tags existing rows in place.,
        "ai_explicit": False,
        "ai_language": None,
        "source_url": SOURCE_URL,
        "dedup_hash": hashlib.md5(hash_input.encode("utf-8")).hexdigest(),
        "is_layoff_event": True,
    }


def pull_federal_rif(min_group=None, since=None):
    """Every current OPM file in the window -> SH totals by agency + effective month.

    min_group drops trivial agency-months (default 5) so only meaningful RIF
    waves post, not one- and two-person separations.

    Raises FederalRifIncomplete if any file in the window could not be read: a
    partial sum posted through /bulk would overwrite correct counts with short
    ones.
    """
    import collections
    if min_group is None:
        min_group = int(os.environ.get("FEDERAL_RIF_MIN", "5"))
    since_ym = since or _since()
    try:
        import pandas  # noqa: F401
    except Exception as e:
        raise FederalRifIncomplete(f"pandas/pyarrow unavailable ({e})") from e

    files = _current_files(since_ym)
    if not files:
        raise FederalRifIncomplete(f"no current OPM separations files at or after {since_ym}")

    sums = collections.defaultdict(int)
    for f in files:
        _read_rif_counts(f, sums)
    print(f"federal_rif: read {len(files)} reporting file(s) from {since_ym}")

    out, dropped_old, dropped_small = [], 0, 0
    for (yyyymm, agency), cnt in sorted(sums.items()):
        # Effective months before the window start are only partially covered by
        # the files inside it. Publishing them short is worse than not at all.
        if yyyymm < since_ym:
            dropped_old += 1
            continue
        if cnt < min_group:
            dropped_small += 1
            continue
        e = _entry(agency, int(cnt), f"{yyyymm[:4]}-{yyyymm[4:6]}-01", yyyymm)
        if e:
            out.append(e)
    print(f"federal_rif: {len(out)} agency-month RIF events (>= {min_group} people); "
          f"dropped {dropped_small} below the floor, {dropped_old} outside the window")
    return out


def pull_federal_drp_dryrun(since=None):
    """DORMANT diagnostic: what the Deferred Resignation Program would add.

    Prints only. DRP separations are voluntary agreements, not RIFs, so they are
    NOT part of this source (see the module docstring). This exists so the size
    of that decision is measurable without anyone guessing at it. Posting DRP
    would be an owner decision and needs its own source_type, not this one.
    """
    import collections
    import pandas as pd
    since_ym = since or _since()
    files = _current_files(since_ym)
    sums = collections.defaultdict(int)
    for f in files:
        url = f"{OPM_BASE}/separations/{f['year']}/{f['month']}/{f['version']}/download"
        resp = requests.get(url, headers=UA, timeout=180)
        resp.raise_for_status()
        df = pd.read_parquet(io.BytesIO(resp.content), columns=[
            "count", "personnel_action_effective_date_yyyymm", "drp_indicator", "agency"])
        drp = df[df["drp_indicator"] == "Y"]
        counts = pd.to_numeric(drp["count"], errors="coerce").fillna(1).astype(int)
        for ym, agency, c in zip(drp["personnel_action_effective_date_yyyymm"], drp["agency"], counts):
            sums[(str(ym)[:4], str(agency).strip().title())] += int(c)
    print(f"federal_drp DRY RUN ({len(files)} files from {since_ym}) — NOTHING IS POSTED")
    by_year = collections.Counter()
    for (yr, _a), c in sums.items():
        by_year[yr] += c
    for yr in sorted(by_year):
        print(f"  {yr}: {by_year[yr]:,} deferred-resignation separations")
    print("  top agencies:")
    for (yr, a), c in sorted(sums.items(), key=lambda x: -x[1])[:10]:
        print(f"    {c:>7,}  {yr}  {a}")
    return sums


if __name__ == "__main__":
    import sys
    if "--drp-dryrun" in sys.argv:
        pull_federal_drp_dryrun()
    else:
        entries = pull_federal_rif()
        for e in entries:
            print(f"  {e['job_count']:>6}  {e['layoff_date']}  {e['company_name']}")
        print(f"total jobs: {sum(e['job_count'] for e in entries):,}")
