"""Bounded employer-domicile backfill from deterministic public record.

Survey counts announced cuts by US-headquartered employer; the tracker's
`country` field is job location. Multi-country events (Oracle 21,000, Block
4,000, ...) therefore sit in 'Multiple countries' and are invisible to any
US-employer comparison. This worker fills ONLY the blank `employer_country`
field, never `country`.

TWO EVIDENCE BASES, both public record, neither of them a guess:
1. The committed curated registry of publicly verifiable HQ facts
   (seed_data/employer_domicile.json). Uncertain companies are absent from the
   registry and stay blank.
2. For SEC-sourced rows, the filing ENTITY's own EDGAR company record - its
   principal executive offices. Not the filing venue: a foreign private issuer
   files on EDGAR precisely because it is foreign, and reading `sec.gov` as
   "United States" is the exact defect found in `legacy_row_repair` on
   2026-08-18, which would have stamped Klarna, ING, Vasta, Brightstar and SLB
   American.

WHAT IT IS FOR, beyond the Survey comparison: a row with a blank `country` AND
a blank `employer_country` cannot be reached by ANY country filter, because
`country_basis=any` (the front-end default) matches
`country IN (...) OR employer_country IN (...)`. On 2026-08-18 all 109
blank-country rows in the corpus were in exactly that state - a Google layoff
that no reader filtering by country could find. Filling the domicile makes the
row findable while its job-location blank stays blank, which is the honest
answer when the source never said where the jobs were.

Safety properties, in line with the enrichment endpoint it reuses:
- /enrich-context fills blank fields only — re-runs are idempotent no-ops.
- It cannot alter job counts, dates, stages, sources or AI labels, so dedup
  hashes are untouched.
- Every write carries evidence text naming the registry, the HQ fact and an
  official reference, and the batch is labelled in the public corrections
  trail as a curated-registry backfill (not a source-page re-read).
- Era-guarded entries (`not_before`) are skipped for rows dated before the
  company's current domicile applied, and skipped entirely for undated rows.

SAFE TO DEFER, and the idempotence bullet above is the reason: /enrich-context
fills blank fields only, the item list is re-derived from the committed registry
every run, and a partly-applied batch simply means fewer items to derive next
time. Nothing here is a sequence.
"""
import json
import os
import re
import sys
import unicodedata
import urllib.parse
from datetime import date
from pathlib import Path

import requests

import host_call

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "employer-domicile-backfill"

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
        payload = host_call.get_json(site + "/wp-json/layoffs/v1/query",
                                     params=query, headers=UA, timeout=60)
        data = payload.get("data", [])
        rows.extend(data)
        if len(data) < PAGE_SIZE or page * PAGE_SIZE >= payload.get("total", 0):
            break
        page += 1
    return rows[:max_rows]


def fetch_blank_country_rows(site, max_rows):
    """Every row whose job-location `country` is blank.

    There is no `country=` value that selects a blank, so the blanks are
    reached the only way the public API allows: sorted ascending by country,
    where they sort first, stopping at the first placed row. That is one page
    of 200 for a population of ~109, and it is bounded by `max_rows` anyway.

    These rows are the reason this worker exists at all now. A blank `country`
    is often correct (the source does not say where the jobs were), but a row
    with BOTH fields blank is invisible under every country filter, because
    `country_basis=any` - the front-end default - matches
    `country IN (...) OR employer_country IN (...)`. Filling the domicile makes
    the row findable without making any claim about where the jobs were.
    """
    rows = []
    page = 1
    while len(rows) < max_rows:
        payload = host_call.get_json(
            site + "/wp-json/layoffs/v1/query",
            params={"per_page": PAGE_SIZE, "page": page, "sort": "country", "dir": "asc"},
            headers=UA, timeout=60)
        data = payload.get("data", [])
        blanks = [row for row in data if not str(row.get("country") or "").strip()]
        rows.extend(blanks)
        if len(blanks) < len(data) or len(data) < PAGE_SIZE:
            break            # reached the first placed row, or the last page
        page += 1
    return rows[:max_rows]


def era_allows(entry, row):
    """not_before entries need a row date on/after the domicile change."""
    not_before = entry.get("not_before")
    if not not_before:
        return True
    row_date = row.get("layoff_date") or row.get("announcement_date") or ""
    return bool(row_date) and row_date >= not_before


#: The filing entity's OWN EDGAR company record is the second deterministic
#: domicile source. It is not an inference from the filing venue, which is the
#: error `legacy_row_repair` made on 2026-08-18: `www.sec.gov` ends in `.gov`,
#: so a bare host test read every foreign private issuer on EDGAR as American
#: and would have stamped Klarna, ING, Vasta, Brightstar and SLB "United
#: States". A foreign private issuer files on EDGAR precisely BECAUSE it is
#: foreign. What EDGAR does state, per filer, is the principal executive
#: offices - the same fact the curated registry records as `hq`.
EDGAR_SOURCE_TYPES = {"8K"}
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
EDGAR_UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com) info@asktherecruiter.com"}
_EDGAR_CIK_RX = re.compile(r"/edgar/data/(\d{1,10})[/-]")
_SEC_HOSTS = {"sec.gov", "www.sec.gov", "data.sec.gov"}
_US_STATE_CODES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'HI', 'IA', 'ID',
    'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC',
    'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD',
    'TN', 'TX', 'UT', 'VA', 'VT', 'WA', 'WI', 'WV', 'WY', 'PR', 'VI', 'GU', 'AS', 'MP',
}
#: Incorporation-only jurisdictions. The state of incorporation is consulted
#: ONLY when a filer has no business address on file, and these are the places
#: where a registered seat says nothing about where the employer actually is.
#: Vasta Platform Ltd is the live proof of the distinction: incorporated in the
#: Cayman Islands, principal offices in Brazil, and Brazil is the answer.
_LETTERBOX_JURISDICTIONS = {
    "cayman islands", "bermuda", "british virgin islands", "netherlands antilles",
    "marshall islands", "jersey", "guernsey", "isle of man", "curacao", "panama",
    "gibraltar", "liberia", "bahamas", "belize", "seychelles",
}


def edgar_cik(source_url):
    """The filer's CIK from a stored sec.gov archive URL, or None.

    Host-gated on purpose. The CIK pattern only appears in EDGAR paths, but the
    lesson of the `.gov` defect is that a URL test which can be satisfied by
    some other host eventually is.
    """
    url = str(source_url or "")
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return None
    if host.lower() not in _SEC_HOSTS:
        return None
    match = _EDGAR_CIK_RX.search(url)
    return int(match.group(1)) if match else None


def edgar_domicile(record):
    """``(country, basis, stated)`` from a filer's EDGAR record, or None.

    Primary basis is the filer's principal business address, which is what a
    registrant reports as its principal executive offices. A US state code
    there IS the United States; any other stated country is that country.

    The state of incorporation is a FALLBACK for filers with no business
    address on file, and only when it names somewhere that an employer is
    plausibly seated - never a letterbox jurisdiction. Anything else returns
    None and the row keeps its blank.
    """
    if not isinstance(record, dict):
        return None
    business = (record.get("addresses") or {}).get("business") or {}
    code = str(business.get("stateOrCountry") or "").strip().upper()
    described = str(business.get("stateOrCountryDescription") or "").strip()
    if code in _US_STATE_CODES:
        return "United States", "principal business address", described or code
    if code and described and described.upper() != code:
        return described, "principal business address", described

    inc_code = str(record.get("stateOfIncorporation") or "").strip().upper()
    inc = str(record.get("stateOfIncorporationDescription") or "").strip()
    if inc_code in _US_STATE_CODES:
        return "United States", "state of incorporation", inc or inc_code
    if inc and inc.upper() != inc_code and inc.lower() not in _LETTERBOX_JURISDICTIONS:
        return inc, "state of incorporation", inc
    return None


def fetch_edgar_record(cik, session=None):
    """One filer's EDGAR company record. Fail-soft: unreachable means blank."""
    try:
        getter = session.get if session is not None else requests.get
        response = getter(EDGAR_SUBMISSIONS.format(cik=cik), headers=EDGAR_UA, timeout=30)
        if response.status_code != 200:
            print(f"  EDGAR CIK {cik}: HTTP {response.status_code}; left blank")
            return None
        return response.json()
    except Exception as exc:
        print(f"  EDGAR CIK {cik}: {type(exc).__name__}; left blank")
        return None


def build_edgar_items(rows, fetcher=fetch_edgar_record):
    """Domicile items for SEC-sourced rows, read from each filer's own record.

    Gated on the row's `source_type`, not on the URL alone - the same gate the
    2026-08-18 repair-tool fix put on `legacy_row_repair`. A row that merely
    cites sec.gov from a news collector is not an SEC filing.
    """
    items, unresolved = [], []
    seen = {}
    for row in rows:
        row_id = int(row["id"])
        if row_id in seen:
            continue
        if (row.get("employer_country") or "").strip():
            continue
        if str(row.get("source_type") or "") not in EDGAR_SOURCE_TYPES:
            continue
        cik = edgar_cik(row.get("source_url"))
        if cik is None:
            unresolved.append((row_id, row.get("company_name", ""), "no CIK in source URL"))
            continue
        seen[row_id] = cik
        resolved = edgar_domicile(fetcher(cik))
        if resolved is None:
            unresolved.append((row_id, row.get("company_name", ""), "EDGAR record states no usable domicile"))
            continue
        country, basis, stated = resolved
        evidence = (
            f"SEC EDGAR company record for CIK {cik:010d} ({row['company_name']}) "
            f"gives the filer's {basis}: {stated}. Domicile read from the filing "
            f"ENTITY's own record, not from the filing venue - a foreign private "
            f"issuer files on EDGAR because it is foreign. The job-location "
            f"country field is unchanged."
        )
        items.append({
            "id": row_id,
            "employer_country": country,
            "employer_country_evidence": evidence,
        })
    return items, unresolved


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


REGISTRY_REASON = ("Curated employer-domicile registry backfill (deterministic public HQ "
                   "facts for the largest multi-country events)")
EDGAR_REASON = ("SEC EDGAR filer-record domicile backfill (each filer's own principal "
                "executive offices, not the filing venue)")


def post_items(site, api_key, items, reason=REGISTRY_REASON):
    updated, rejected, not_found = [], [], []
    for start in range(0, len(items), POST_BATCH):
        batch = items[start:start + POST_BATCH]
        result = host_call.post_json(
            site + "/wp-json/layoffs/v1/enrich-context",
            {
                "items": batch,
                "reason": reason,
            },
            headers={**UA, "X-Layoff-API-Key": api_key},
            timeout=120,
        )
        updated.extend(result.get("updated", []))
        rejected.extend(result.get("rejected", []))
        not_found.extend(result.get("not_found", []))
    return updated, rejected, not_found


def main():
    """Deferral boundary. Every write here is an idempotent blank-field fill."""
    try:
        code = _run()
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    host_call.clear(JOB)
    return code


def _run():
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
    # Third pass: the rows with NO job-location country at all. Those are the
    # only rows in the corpus that no country filter can reach, because
    # `country_basis=any` has neither field to match on.
    blank_country = fetch_blank_country_rows(site, max_rows)
    rows += blank_country

    items, skipped_era, unmatched = build_items(registry, exact, prefixes, rows)
    print(f"Rows examined: {len({int(r['id']) for r in rows})} · blank-domicile registry matches: {len(items)} "
          f"· era-guarded skips: {len(skipped_era)} · unmatched companies left blank: {len(set(unmatched))}")
    print(f"Blank-country rows examined: {len(blank_country)} (invisible to every country filter while both fields are blank)")

    # SEC filings carry their own domicile record, which the registry does not
    # need to duplicate company by company. Only blank-domicile rows reach the
    # fetcher, so a filled corpus makes no EDGAR requests at all.
    #
    # SCOPED TO THE BLANK-COUNTRY ROWS ON PURPOSE. Run over the whole 'Multiple
    # countries' bucket it also places Schlumberger, Weatherford and Aon, and
    # the registry's own policy note lists those as DELIBERATELY ABSENT because
    # incorporation and operations disagree. A generic rule must not quietly
    # reverse a curated human decision. In the blank-country set there is no
    # curated decision to reverse: the row is unreachable by any country filter
    # while both fields are blank, and that is the defect being repaired.
    registry_ids = {item["id"] for item in items}
    edgar_items, edgar_unresolved = build_edgar_items(
        [row for row in blank_country if int(row["id"]) not in registry_ids])
    print(f"EDGAR filer-record matches: {len(edgar_items)} · left blank: {len(edgar_unresolved)}")

    for item in items + edgar_items:
        print(f"  would set id={item['id']}: {item['employer_country']}" if dry_run
              else f"  setting id={item['id']}: {item['employer_country']}")
    if dry_run:
        print("DRY RUN: no writes performed.")
        return 0
    if not items and not edgar_items:
        print("Nothing to backfill (already filled or no registry match). This is the idempotent steady state.")
        return 0

    updated, rejected, not_found = [], [], []
    for batch_items, reason in ((items, REGISTRY_REASON), (edgar_items, EDGAR_REASON)):
        if not batch_items:
            continue
        # Each basis posts under its OWN reason so the public corrections trail
        # says which evidence placed the row: a curated HQ fact or the filer's
        # EDGAR record. One merged label would name the wrong source for half.
        part = post_items(site, api_key, batch_items, reason)
        updated += part[0]
        rejected += part[1]
        not_found += part[2]
    print(f"Updated: {len(updated)} · rejected (already filled): {len(rejected)} · not found: {len(not_found)}")
    if not_found:
        # A vanished id means the row set changed mid-run (dedupe/purge); it
        # must be visible, but the applied updates above remain valid.
        print(f"WARNING: ids not found: {not_found}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
