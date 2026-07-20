"""Bounded, curated employer-domicile backfill for multi-country events.

Survey counts announced cuts by US-headquartered employer; the tracker's
`country` field is job location. Multi-country events (Oracle 21,000, Block
4,000, ...) therefore sit in 'Multiple countries' and are invisible to any
US-employer comparison. This worker fills ONLY the blank `employer_country`
field for the largest 'Multiple countries' rows, from the committed curated
registry of deterministic, publicly verifiable HQ facts
(seed_data/employer_domicile.json). Uncertain companies are absent from the
registry and stay blank.

Safety properties, in line with the enrichment endpoint it reuses:
- /enrich-context fills blank fields only — re-runs are idempotent no-ops.
- It cannot alter job counts, dates, stages, sources or AI labels, so dedup
  hashes are untouched.
- Every write carries evidence text naming the registry, the HQ fact and an
  official reference, and the batch is labelled in the public corrections
  trail as a curated-registry backfill (not a source-page re-read).
- Era-guarded entries (`not_before`) are skipped for rows dated before the
  company's current domicile applied, and skipped entirely for undated rows.
"""
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
REGISTRY_PATH = Path(__file__).parent / "seed_data" / "employer_domicile.json"
PAGE_SIZE = 200
POST_BATCH = 40


def normalize_company(name):
    """ASCII-fold, lowercase, strip punctuation — the registry key space."""
    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


def load_registry(path=REGISTRY_PATH):
    registry = json.loads(Path(path).read_text(encoding="utf-8"))
    exact = {}
    prefixes = []
    for entry in registry["companies"]:
        if not entry.get("employer_country") or not entry.get("hq") or not entry.get("ref"):
            raise ValueError(f"Registry entry missing employer_country/hq/ref: {entry}")
        for key in entry["match"]:
            if key != normalize_company(key):
                raise ValueError(f"Registry match key is not in normalized form: {key!r}")
            if key in exact and exact[key] is not entry:
                raise ValueError(f"Duplicate registry match key: {key!r}")
            exact[key] = entry
        if entry.get("prefix"):
            prefixes.extend((key, entry) for key in entry["match"])
    return registry, exact, prefixes


def registry_lookup(exact, prefixes, company):
    key = normalize_company(company)
    if not key:
        return None
    if key in exact:
        return exact[key]
    for prefix, entry in prefixes:
        if key.startswith(prefix + " ") or key == prefix:
            return entry
    return None


def fetch_rows(site, params, max_rows):
    """Page through /query, bounded, fail-loud on any HTTP error."""
    rows = []
    page = 1
    while len(rows) < max_rows:
        query = {**params, "per_page": PAGE_SIZE, "page": page}
        response = requests.get(site + "/wp-json/layoffs/v1/query", params=query, headers=UA, timeout=60)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        rows.extend(data)
        if len(data) < PAGE_SIZE or page * PAGE_SIZE >= payload.get("total", 0):
            break
        page += 1
    return rows[:max_rows]


def era_allows(entry, row):
    """not_before entries need a row date on/after the domicile change."""
    not_before = entry.get("not_before")
    if not not_before:
        return True
    row_date = row.get("layoff_date") or row.get("announcement_date") or ""
    return bool(row_date) and row_date >= not_before


def build_items(registry, exact, prefixes, rows):
    items, skipped_era, unmatched = [], [], []
    seen_ids = set()
    for row in rows:
        row_id = int(row["id"])
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        if (row.get("employer_country") or "").strip():
            continue
        entry = registry_lookup(exact, prefixes, row.get("company_name", ""))
        if entry is None:
            unmatched.append(row.get("company_name", ""))
            continue
        if not era_allows(entry, row):
            skipped_era.append((row_id, row.get("company_name", "")))
            continue
        evidence = (
            f"Curated employer-domicile registry ({registry['revised']}): "
            f"{row['company_name']} is headquartered in {entry['hq']}. "
            f"Reference: {entry['ref']}. Deterministic public HQ fact; the "
            f"job-location country field is unchanged."
        )
        items.append({
            "id": row_id,
            "employer_country": entry["employer_country"],
            "employer_country_evidence": evidence,
        })
    return items, skipped_era, unmatched


def post_items(site, api_key, items):
    updated, rejected, not_found = [], [], []
    for start in range(0, len(items), POST_BATCH):
        batch = items[start:start + POST_BATCH]
        response = requests.post(
            site + "/wp-json/layoffs/v1/enrich-context",
            json={
                "items": batch,
                "reason": "Curated employer-domicile registry backfill (deterministic public HQ facts for the largest multi-country events)",
            },
            headers={**UA, "X-Layoff-API-Key": api_key},
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        updated.extend(result.get("updated", []))
        rejected.extend(result.get("rejected", []))
        not_found.extend(result.get("not_found", []))
    return updated, rejected, not_found


def main():
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        print("WP_SITE_URL is required")
        return 1
    dry_run = os.environ.get("DOMICILE_BACKFILL_DRY_RUN", "").lower() in {"1", "true", "yes"}
    api_key = os.environ.get("WP_API_KEY", "")
    if not api_key and not dry_run:
        print("WP_API_KEY is required (or set DOMICILE_BACKFILL_DRY_RUN=1)")
        return 1
    max_rows = int(os.environ.get("DOMICILE_BACKFILL_MAX_ROWS") or 400)

    registry, exact, prefixes = load_registry()
    # Two bounded passes over the ambiguity bucket: the largest events of all
    # time, plus every current-year row (the Survey-comparison year), so
    # small current-year AI events (BitGo 90, Kraken 150) are not crowded out
    # by decade-old giants.
    base = {"country": "Multiple countries", "sort": "job_count", "dir": "desc"}
    rows = fetch_rows(site, base, max_rows)
    rows += fetch_rows(site, {**base, "years": str(date.today().year)}, max_rows)

    items, skipped_era, unmatched = build_items(registry, exact, prefixes, rows)
    print(f"Rows examined: {len({int(r['id']) for r in rows})} · blank-domicile registry matches: {len(items)} "
          f"· era-guarded skips: {len(skipped_era)} · unmatched companies left blank: {len(set(unmatched))}")
    for item in items:
        print(f"  would set id={item['id']}: {item['employer_country']}" if dry_run
              else f"  setting id={item['id']}: {item['employer_country']}")
    if dry_run:
        print("DRY RUN: no writes performed.")
        return 0
    if not items:
        print("Nothing to backfill (already filled or no registry match). This is the idempotent steady state.")
        return 0

    updated, rejected, not_found = post_items(site, api_key, items)
    print(f"Updated: {len(updated)} · rejected (already filled): {len(rejected)} · not found: {len(not_found)}")
    if not_found:
        # A vanished id means the row set changed mid-run (dedupe/purge); it
        # must be visible, but the applied updates above remain valid.
        print(f"WARNING: ids not found: {not_found}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
