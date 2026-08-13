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

TOLERANCE, AND ITS LIMIT. This is a data-changing bulk import, so the house
rule stands: any failed batch is loud. What changed on 2026-08-12 is only what
counts as a failed batch. A transient 5xx that clears on retry never was one,
and the retry now comes from the shared `http_retry` definition. Beyond that:

  * some batches landed and some never reached the host -> LOUD. A partly
    applied import is exactly the state the fail-loud rule protects.
  * NOTHING landed and nothing was refused, because the host answered no batch
    at all -> DEFERRED. There is no partial state to be loud about, and the
    same CSV window is re-imported on the next run (`dedup_hash` is the
    Eurofound factsheet id, so a re-import is an upsert, not a duplicate).
"""
import csv
import hashlib
import io
import os
import sys
from datetime import date, timedelta

import requests

import host_call
import http_retry
from source_health import publish_source_health, report_source_health

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "erm-import"

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
    # Eurofound, not our host — a blip here is not the deploy collision, but it
    # kills the run just as dead, and the retry definition is already shared.
    resp = http_retry.get_with_retry(CSV_URL, params=params, headers=UA, timeout=120)
    if resp is None:
        raise RuntimeError(f"Eurofound ERM CSV never answered: {CSV_URL}")
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
    # Before the CSV is even fetched, so nothing can be half-imported. A host
    # that never answered defers; a host that refused the write still raises.
    note = publish_source_health("eurofound_erm", "running", 0,
                                 "daily Eurofound ERM import in progress")
    if note == http_retry.DEFERRED:
        raise host_call.Deferred("the source-health ledger would not accept the "
                                 "'running' note; nothing was imported")
    if note != http_retry.OK:
        raise RuntimeError("Could not publish Eurofound ERM running health status")
    try:
        entries = [e for e in (to_entry(r) for r in fetch_events()) if e]
        print(f"ERM: {len(entries)} job-loss events >= {MIN_DATE} "
              f"({sum(e['job_count'] for e in entries):,} jobs)")

        failed = landed = never_asked = 0
        for i in range(0, len(entries), BATCH):
            batch = entries[i:i + BATCH]
            number = i // BATCH + 1
            try:
                result = host_call.post_json(
                    f"{site}/wp-json/layoffs/v1/bulk", {"entries": batch},
                    headers={**UA, "X-Layoff-API-Key": key}, timeout=180)
            except host_call.Deferred as exc:
                never_asked += 1
                print(f"batch {number} NEVER REACHED THE HOST: {exc}")
                continue
            except RuntimeError as exc:
                failed += 1
                print(f"batch {number} FAILED: {exc}")
                continue
            landed += 1
            print(f"batch {number}: {result}")
        if failed:  # data jobs fail loudly (house rule)
            raise RuntimeError(f"Eurofound ERM import had {failed} failed batch(es)")
        if never_asked and landed:
            # Partly applied. Loud, on purpose: this is precisely the state the
            # fail-loud rule exists for, and it does not get better by waiting.
            raise RuntimeError(
                f"Eurofound ERM import applied {landed} batch(es) but {never_asked} "
                f"never reached the host — the import is incomplete")
        if never_asked:
            raise host_call.Deferred(
                f"no /bulk batch reached the host ({never_asked} attempted)")
        detail = f"{len(entries)} source-linked ERM announcement event(s) imported"
        if not report_source_health("eurofound_erm", "ok", len(entries), detail):
            print("::warning::ERM import completed but the health-ledger write failed (data is fine)")
        host_call.clear(JOB)
        return entries
    except host_call.Deferred:
        # Nothing was applied, so there is nothing to call degraded: the
        # collector is fine and the host did not answer. The ledger holds it.
        raise
    except Exception as exc:
        # A failed source attempt is a material coverage condition, not an
        # empty successful pull. Preserve the failure in the public health
        # ledger before the workflow exits non-zero.
        report_source_health("eurofound_erm", "degraded", 0, f"ERM import failed: {exc}")
        raise


def main():
    try:
        run()
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
