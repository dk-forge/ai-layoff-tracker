"""
Eurofound European Restructuring Monitor (ERM) importer — Europe's closest
analogue to US WARN notices: per-company restructuring announcements for the
EU27 + Norway (UK historically), curated since 2002 by Eurofound's network of
national correspondents screening ~58 business media titles daily.

License: Eurofound authorizes reuse for commercial and non-commercial purposes
with source acknowledgement (eurofound.europa.eu/en/legal-information) — every
entry's excerpt credits "European Restructuring Monitor (Eurofound)" and links
to its factsheet.

Data notes:
  - CSV export: https://apps.eurofound.europa.eu/restructuring-events/factsheetscsv
    (whole DB unparameterized, ~2.8 MB; accepts date-from/date-to for windows).
  - Columns: Id, Announcement date, Country, Company, Sector,
    Restructuring type, Employment Change (negative = announced job losses).
  - Inclusion threshold: >=100 jobs, or >=10% of a 250+ site — small events
    are absent by design (disclosed in the tracker methodology).
  - dedup_hash = md5('erm{Id}'): the factsheet id is the natural key, so
    Eurofound's own revisions to a count UPDATE our row instead of duplicating
    (unlike WARN, where the count is part of the hash).

Usage:
  ERM_MODE=daily   (default) — last 14 days, for the daily cron
  ERM_MODE=full    — entire history >= 2015-01-01 (initial backfill)
Requires WP_SITE_URL + WP_API_KEY in the environment (same as warn_import).
"""
import csv
import hashlib
import io
import os
import sys
from datetime import date, timedelta

import requests

from source_health import report_source_health

CSV_URL = "https://apps.eurofound.europa.eu/restructuring-events/factsheetscsv"
DETAIL_URL = "https://apps.eurofound.europa.eu/restructuring-events/detail/{id}"
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
BATCH = 500
# Eurofound curates ERM back to 2002 — the one source with reliable, structured
# pre-2015 data (US state WARN sites purge old years; pre-2015 news dates are
# extraction errors, so those floors stay). Overridable via ERM_MIN_DATE to
# scope a run. Lowered from 2015 to pull the full EU/UK restructuring history.
MIN_DATE = os.environ.get("ERM_MIN_DATE") or "2002-01-01"

# ERM's 20-sector scheme -> the tracker's fixed industry taxonomy
SECTOR_MAP = {
    "Information / Computing": "Technology",
    "Financial services": "Finance",
    "Health / Social work": "Healthcare",
    "Education": "Education",
    "Retail": "Retail",
    "Manufacturing": "Manufacturing",
    "Transport / Storage": "Transportation",
    "Hotel / Restaurant": "Hospitality",
    "Construction": "Construction",
    "Energy": "Energy",
    "Media / Publishing": "Media",
    "Telecommunications": "Technology",
    "Agriculture / Fishing": "Agriculture",
    "Public administration": "Government",
}

COUNTRY_FIX = {"World": "Multiple countries", "European Union": "Multiple countries"}


def fetch_events():
    mode = (os.environ.get("ERM_MODE") or "daily").lower()
    params = {}
    if mode != "full":
        params = {"date-from": (date.today() - timedelta(days=14)).isoformat(),
                  "date-to": date.today().isoformat()}
    resp = requests.get(CSV_URL, params=params, headers=UA, timeout=120)
    resp.raise_for_status()
    resp.encoding = "utf-8"  # server omits charset; requests then guesses latin-1
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    print(f"ERM CSV: {len(rows)} rows ({mode})")
    return rows


def to_entry(r):
    try:
        change = int(str(r.get("Employment Change") or "0").replace(",", ""))
    except ValueError:
        return None
    if change >= 0:  # job creation / unknown — not layoff events
        return None
    jobs = -change
    if jobs > 100000:  # single-event sanity cap, same as WARN
        return None
    d = (r.get("Announcement date") or "").strip()
    if not d or d < MIN_DATE:
        return None
    company = (r.get("Company") or "").strip()
    erm_id = (r.get("Id") or "").strip()
    if not company or not erm_id:
        return None
    country = COUNTRY_FIX.get((r.get("Country") or "").strip(), (r.get("Country") or "").strip())
    rtype = (r.get("Restructuring type") or "Restructuring").strip()
    excerpt = (f"{rtype} at {company} ({country}): {jobs:,} announced job losses. "
               f"Recorded by the European Restructuring Monitor (Eurofound), "
               f"factsheet {erm_id}.")
    return {
        "source_type": "erm",
        "source_name": "European Restructuring Monitor (Eurofound)",
        "verification_level": "silver",
        # ERM figures are "as originally announced" — announcement-stage by
        # definition (Cineworld's 45K/Lufthansa's 39K COVID-era announcements
        # would otherwise pollute the verified floor exactly the way we
        # criticize announcement surveys for). The Announced tier shows them
        # separately, each linked to its official factsheet.
        "announced": True,
        "company_name": company,
        "ticker": None,
        "job_count": jobs,
        "layoff_date": d,
        "industry": SECTOR_MAP.get((r.get("Sector") or "").strip(), (r.get("Sector") or "").strip()),
        "country": country,
        "state": None,
        "roles": None,
        "excerpt": excerpt,
        "reason_tags": [],
        "ai_explicit": False,
        "ai_language": None,
        "source_url": DETAIL_URL.format(id=erm_id),
        "dedup_hash": hashlib.md5(f"erm{erm_id}".encode("utf-8")).hexdigest(),
        "is_layoff_event": True,
    }


def run():
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not site or not key:
        raise RuntimeError("WP_SITE_URL / WP_API_KEY missing")
    if not report_source_health("eurofound_erm", "running", 0, "daily Eurofound ERM import in progress"):
        raise RuntimeError("Could not publish Eurofound ERM running health status")
    try:
        entries = [e for e in (to_entry(r) for r in fetch_events()) if e]
        print(f"ERM: {len(entries)} job-loss events >= {MIN_DATE} "
              f"({sum(e['job_count'] for e in entries):,} jobs)")

        failed = 0
        for i in range(0, len(entries), BATCH):
            batch = entries[i:i + BATCH]
            resp = requests.post(
                f"{site}/wp-json/layoffs/v1/bulk",
                json={"entries": batch},
                headers={**UA, "X-Layoff-API-Key": key, "Content-Type": "application/json"},
                timeout=180)
            if resp.status_code != 200:
                failed += 1
                print(f"batch {i // BATCH + 1} FAILED: {resp.status_code} {resp.text[:300]}")
            else:
                print(f"batch {i // BATCH + 1}: {resp.json()}")
        if failed:  # data jobs fail loudly (house rule)
            raise RuntimeError(f"Eurofound ERM import had {failed} failed batch(es)")
        detail = f"{len(entries)} source-linked ERM announcement event(s) imported"
        if not report_source_health("eurofound_erm", "ok", len(entries), detail):
            raise RuntimeError("Could not publish Eurofound ERM completion health status")
        return entries
    except Exception as exc:
        # A failed source attempt is a material coverage condition, not an
        # empty successful pull. Preserve the failure in the public health
        # ledger before the workflow exits non-zero.
        report_source_health("eurofound_erm", "degraded", 0, f"ERM import failed: {exc}")
        raise


def main():
    run()


if __name__ == "__main__":
    main()
