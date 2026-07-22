"""US federal RIF separations (OPM EHRI) — executed Reduction-in-Force records.

OPM's Enterprise Human Resources Integration (EHRI) publishes monthly federal
separation microdata via a keyless open API. We filter to
`separation_category_code == 'SH'` (Reduction in Force), group by agency and
effective month, and post each meaningful agency RIF wave.

This is the EXECUTED, documented federal-layoff count: authoritative but small
and lagged (OPM has already rolled the RIF nature-of-action into category SH).
The larger "hundreds of thousands" federal-cut figures in the news are deferred
resignations, probationary terminations and announced plans, not executed RIFs;
those reach the tracker through the news pipeline. This source is the
conservative floor, the official record of RIFs that actually happened.

Structured government data -> route through /bulk (no LLM), like WARN.

Download recipe (verified): list current files at
  GET https://data.opm.gov/api/v1/files/separations?current=true
then assemble the Parquet download path yourself (metadata has no url field):
  GET https://data.opm.gov/api/v1/files/separations/{year}/{month}/{version}/download
Each monthly file is a ROLLING ~24-month window, so pull only the latest file
and group by effective month; never sum across files (double-counts).
"""
import hashlib
import io
import os

import requests

OPM_BASE = "https://data.opm.gov/api/v1/files"
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SOURCE_URL = "https://data.opm.gov/explore-data/analytics/workforce-changes"


def _latest_file():
    try:
        meta = requests.get(f"{OPM_BASE}/separations", params={"current": "true"},
                            headers=UA, timeout=30).json()
    except Exception as e:
        print(f"federal_rif: metadata fetch failed: {e}")
        return None
    if not isinstance(meta, list) or not meta:
        return None
    meta.sort(key=lambda f: (str(f.get("year", "")), str(f.get("month", "")), int(f.get("version", 0) or 0)))
    return meta[-1]


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
        "reason_tags": ["restructuring"],
        "ai_explicit": False,
        "ai_language": None,
        "source_url": SOURCE_URL,
        "dedup_hash": hashlib.md5(hash_input.encode("utf-8")).hexdigest(),
        "is_layoff_event": True,
    }


def pull_federal_rif(min_group=None):
    """Latest OPM separations file -> RIF (SH) grouped by agency+effective month.

    min_group drops trivial single-person RIFs (default 5) so only meaningful
    agency RIF waves post, not individual separations.
    """
    if min_group is None:
        min_group = int(os.environ.get("FEDERAL_RIF_MIN", "5"))
    try:
        import pandas as pd
    except Exception as e:
        print(f"federal_rif: pandas/pyarrow unavailable ({e}); skipping")
        return []
    f = _latest_file()
    if not f:
        print("federal_rif: no separations files found")
        return []
    url = f"{OPM_BASE}/separations/{f['year']}/{f['month']}/{f['version']}/download"
    try:
        raw = requests.get(url, headers=UA, timeout=120).content
        df = pd.read_parquet(io.BytesIO(raw))
    except Exception as e:
        print(f"federal_rif: download/parse failed: {e}")
        return []
    if "separation_category_code" not in df.columns:
        print("federal_rif: schema changed (no separation_category_code); skipping")
        return []
    rif = df[df["separation_category_code"] == "SH"].copy()
    if rif.empty:
        print(f"federal_rif: 0 RIF rows in {f.get('filename')}")
        return []
    rif["count"] = pd.to_numeric(rif["count"], errors="coerce").fillna(1).astype(int)
    grp = rif.groupby(["personnel_action_effective_date_yyyymm", "agency"])["count"].sum()
    out = []
    for (yyyymm, agency), cnt in grp.items():
        cnt = int(cnt)
        if cnt < min_group:
            continue
        yyyymm = str(yyyymm)
        if len(yyyymm) != 6 or not yyyymm.isdigit():
            continue
        date = f"{yyyymm[:4]}-{yyyymm[4:6]}-01"
        agency = str(agency).strip().title()
        e = _entry(agency, cnt, date, yyyymm)
        if e:
            out.append(e)
    print(f"federal_rif: {len(out)} agency-month RIF events (>= {min_group}) from {f.get('filename')}")
    return out


if __name__ == "__main__":
    for e in pull_federal_rif():
        print(f"  {e['job_count']:>5}  {e['layoff_date']}  {e['company_name']}")
