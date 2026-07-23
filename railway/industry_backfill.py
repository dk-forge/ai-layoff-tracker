"""Bounded daily industry-classification backfill for blank-industry rows.

A large share of rows carry no `industry` — every structured WARN notice does,
plus older news/8K rows whose extraction never resolved a sector — so the
industry filter dropdown and the "by industry" aggregates under-represent them.
This worker classifies those rows into the FIXED industry vocabulary using ONLY
each row's own company name + STORED excerpt — it never re-fetches a source
page and never touches counts, dates, stages, sources or AI labels.

Safety model (matches the /industry-backfill endpoint's guarantees):
- Blank-only: the endpoint fills a row ONLY while its industry is still '',
  and `alt_db_upsert` no longer blanks a set industry, so the daily WARN
  re-import cannot erase a fill. Rows are NOT pinned — a purge-reload simply
  returns the row to the visible backlog, so this is honest enrichment, not a
  permanent override.
- Closed vocabulary: the model must answer with exactly one label from
  `extractor.INDUSTRY_VOCABULARY` or "unknown"; anything else collapses to a
  skip. The endpoint re-validates against `alt_industry_vocabulary()` and
  rejects any label outside it (a rejection here is treated as vocabulary
  drift and fails loudly).
- Double-confirmed: each row is classified by TWO independent model passes and
  written only when both agree on the same non-empty label. A disagreement or
  an "unknown" from either pass leaves the row untouched in the backlog. This
  is the "double-confirmed by two model passes" the endpoint records in its
  corrections trail.

Env: WP_SITE_URL, WP_API_KEY; OPENROUTER_API_KEY for the model path.
Optional: INDUSTRY_BACKFILL_BATCH (rows/run, default 40),
INDUSTRY_BACKFILL_DEADLINE_SECONDS (default 900, stops safely between rows),
INDUSTRY_BACKFILL_DRY_RUN=1 (classify + print, no writes, no health reports),
INDUSTRY_BACKFILL_SINGLE_PASS=1 (disable the second confirmation pass — for
manual spot checks only; the scheduled job always double-confirms).

The slice over the queue rotates deterministically by SIX-HOUR block (the
reason_backfill / enrich_context pattern, stepped up because this job now runs
4x/day), so rows the model honestly leaves "unknown" cannot permanently stall
the head of the queue, and the four daily runs work on four different slices.
"""
import os
import re
import sys
import time
from datetime import date, datetime, timezone

import requests

from extractor import classify_industry, INDUSTRY_VOCABULARY
from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(200, int(os.environ.get("INDUSTRY_BACKFILL_BATCH", "40"))))
DEADLINE_SECONDS = max(60, min(1800, int(os.environ.get("INDUSTRY_BACKFILL_DEADLINE_SECONDS", "900"))))
DRY_RUN = os.environ.get("INDUSTRY_BACKFILL_DRY_RUN", "").lower() in {"1", "true", "yes"}
SINGLE_PASS = os.environ.get("INDUSTRY_BACKFILL_SINGLE_PASS", "").lower() in {"1", "true", "yes"}

# Shard support: several backfill jobs run in parallel, each striding a
# DISJOINT set of scan pages. Striding (rather than each shard scanning
# everything) means N shards do N times the work for the SAME total request
# load on the shared host, which matters because it was host load that produced
# the 500s in the first place.
SHARDS = max(1, int(os.environ.get("INDUSTRY_SHARDS") or "1"))
SHARD = max(0, min(SHARDS - 1, int(os.environ.get("INDUSTRY_SHARD") or "0")))

PAGE_SIZE = 200
MAX_PAGES = 300  # hard bound on the scan (300 * 200 = 60K rows)
WRITE_BATCH = 200  # the endpoint accepts up to 2000 items; stay well under


_TRANSIENT = {408, 429, 500, 502, 503, 504, 520, 521, 522, 524}


def _get_with_retry(url, params, attempts=3):
    """GET that survives the shared host's intermittent 5xx.

    Returns the response, or None when every attempt failed transiently. A
    deep-offset page of the blank-industry scan reliably 500s while a large
    WARN import is running; that single blip used to abort the entire backfill
    (the run died at page 76 of 140 having filled nothing), which is why the
    backlog was not draining.
    """
    for attempt in range(attempts):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60)
            if r.status_code not in _TRANSIENT:
                return r          # success, or a real error the caller must raise on
            if attempt < attempts - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return None           # still transient after the last attempt
        except requests.RequestException:
            if attempt < attempts - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return None
    return None


def fetch_candidates():
    """Page through blank-industry rows that carry something to classify.

    A row with neither a company name nor an excerpt has no evidence to read,
    so it never enters the queue (it would only ever resolve to a skip)."""
    candidates = []
    page = 1 + SHARD           # this shard's first page
    while page <= MAX_PAGES:
        # Newest layoffs first: the current-year rows drive the live sector
        # numbers (and the benchmark), so they should be tagged before the
        # decade-old backlog. Pagination/dedup are order-independent.
        params = {"industry_missing": "1", "sort": "layoff_date", "dir": "desc",
                  "per_page": PAGE_SIZE, "page": page}
        response = _get_with_retry(f"{SITE}/wp-json/layoffs/v1/query", params)
        if response is None and page == 1:
            # No data at all: that is a real outage, not a blip. Fail loudly
            # rather than reporting a successful run that classified nothing.
            raise RuntimeError(
                "industry backfill: /query unreachable (transient errors on page 1 "
                "after retries) - the run classified nothing")
        if response is None:
            # The shared host answered 5xx on this page even after retries
            # (usually because a big WARN import is loading it at the same
            # time). Losing one page of a 140-page scan is not a reason to
            # throw away the whole run: the deterministic pre-pass can still
            # fill thousands of rows from the pages we DID get, and the rest
            # comes back on the next rotation. Only a page-1 failure, i.e. no
            # data at all, is treated as a real outage (raised below).
            print(f"  scan: page {page} still failing after retries, "
                  f"continuing with {len(candidates)} candidate(s) already collected")
            break
        # WP returns 404 for a page past the last row. Between our sequential
        # page requests the candidate set shrinks (rows get filled) or `total`
        # is under-reported, so the final page can 404 even though the scan
        # succeeded. That is end-of-data, not a failure — stop with what we
        # have. A 404 on page 1 is a real endpoint problem and still raises.
        if response.status_code == 404 and page > 1:
            break
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", [])
        for row in rows:
            if (row.get("industry") or "").strip():  # belt to the industry_missing filter
                continue
            company = (row.get("company_name") or "").strip()
            excerpt = (row.get("excerpt") or "").strip()
            if not company and not excerpt:
                continue
            candidates.append(row)
        if len(rows) < PAGE_SIZE or page * PAGE_SIZE >= payload.get("total", 0):
            break
        page += SHARDS         # stride past the pages other shards own
    return candidates


def rotating_slice(rows, batch, day_ordinal):
    """Deterministic rotating slice so skipped ("unknown") rows cannot stall the
    queue. NB the caller passes a SIX-HOURLY ordinal, not a daily one: the job
    runs 4x/day, and a day-based ordinal made all four runs target the same
    region of the queue, wasting three of them."""
    if not rows or batch <= 0:
        return []
    pages = (len(rows) + batch - 1) // batch
    start = (day_ordinal % pages) * batch
    return rows[start:start + batch]


def classify_confirmed(company, excerpt):
    """Two-pass agreement gate.

    Returns (label, status) where status is one of:
    - 'confirmed'  -> both passes returned the SAME non-empty vocabulary label
    - 'unconfirmed'-> passes disagreed, or one/both said "unknown"/empty (skip)
    - 'failed'     -> a model/transport error (retry on a later rotation)
    """
    first = classify_industry(company, excerpt)
    if first is None:
        return "", "failed"
    label = first.get("industry", "")
    if not label:
        return "", "unconfirmed"
    if SINGLE_PASS:
        return label, "confirmed"
    second = classify_industry(company, excerpt)
    if second is None:
        return "", "failed"
    if second.get("industry", "") == label:
        return label, "confirmed"
    return "", "unconfirmed"


def post_fills(items):
    """POST /industry-backfill in bounded batches; any HTTP failure raises.

    A `rejected` id means the endpoint refused a label its own
    `alt_industry_vocabulary()` does not contain — i.e. the worker's
    INDUSTRY_VOCABULARY has drifted from the PHP map. That is never papered
    over; it fails loudly (the parity test exists to prevent it landing)."""
    filled, skipped, not_found = [], [], []
    for start in range(0, len(items), WRITE_BATCH):
        chunk = items[start:start + WRITE_BATCH]
        response = requests.post(
            f"{SITE}/wp-json/layoffs/v1/industry-backfill",
            json={"items": [{"id": i["id"], "industry": i["industry"]} for i in chunk]},
            headers={**UA, "X-Layoff-API-Key": KEY},
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        filled.extend(result.get("filled", []))
        skipped.extend(result.get("skipped_not_blank", []))
        not_found.extend(result.get("not_found", []))
        if result.get("rejected"):
            raise RuntimeError(
                f"/industry-backfill rejected ids {result['rejected']}: "
                "industry vocabulary drift between the worker and the plugin?")
    return filled, skipped, not_found


# --- deterministic pre-classifier -----------------------------------------
# A company's sector is usually a fact readable from its name, so most of the
# blank-industry backlog can be filled instantly and for free, reserving the
# 2-pass LLM for genuinely ambiguous names. Every label MUST be in
# INDUSTRY_VOCABULARY; a returned label is re-checked against it before use, so
# vocabulary drift can only under-fill (safe), never mis-post.
_DET_KNOWN = {
    "oracle": "Technology", "dell": "Technology", "meta": "Technology",
    "microsoft": "Technology", "google": "Technology", "alphabet": "Technology",
    "intel": "Technology", "cisco": "Technology", "ibm": "Technology",
    "salesforce": "Technology", "workday": "Technology", "netapp": "Technology",
    "autodesk": "Technology", "intuit": "Technology", "snap": "Technology",
    "pinterest": "Technology", "linkedin": "Technology", "hewlett": "Technology",
    "hp inc": "Technology", "nvidia": "Technology", "qualcomm": "Technology",
    "paypal": "Finance & Insurance", "block": "Finance & Insurance",
    "robinhood": "Finance & Insurance", "coinbase": "Finance & Insurance",
    "wells fargo": "Finance & Insurance", "citigroup": "Finance & Insurance",
    "jpmorgan": "Finance & Insurance", "prudential": "Finance & Insurance",
    "tyson": "Food & Hospitality", "starbucks": "Food & Hospitality",
    "aramark": "Food & Hospitality", "canteen": "Food & Hospitality",
    "home depot": "Retail & E-commerce", "macy": "Retail & E-commerce",
    "kroger": "Retail & E-commerce", "walgreens": "Retail & E-commerce",
    "gamestop": "Retail & E-commerce", "albertsons": "Retail & E-commerce",
    "disney": "Media & Entertainment", "verizon": "Telecom", "t-mobile": "Telecom",
    "goodyear": "Manufacturing", "cleveland-cliffs": "Manufacturing",
    "harley": "Automotive", "lucid": "Automotive", "rivian": "Automotive",
    "electrolux": "Consumer Goods", "expeditors": "Logistics & Transport",
    "transdev": "Logistics & Transport", "american express": "Finance & Insurance",
    "general mills": "Food & Hospitality",
    "abbvie": "Healthcare & Pharma", "pfizer": "Healthcare & Pharma",
    "merck": "Healthcare & Pharma", "novartis": "Healthcare & Pharma",
    "takeda": "Healthcare & Pharma", "medtronic": "Healthcare & Pharma",
    "gilead": "Healthcare & Pharma", "baxter": "Healthcare & Pharma",
    "genentech": "Healthcare & Pharma", "bristol myers": "Healthcare & Pharma",
    "cigna": "Healthcare & Pharma",
}
_DET_KW = [
    (r"hospital|health system|healthcare|\bpharma|biotech|therapeutic|dental|medic(al|ine)|surgical|nursing|\bclinic", "Healthcare & Pharma"),
    (r"\bbank\b|bancorp|financial|insurance|\bcapital\b|mortgage|securities|\binvest(ment|ing)|savings|credit union", "Finance & Insurance"),
    (r"\bfoods?\b|restaurant|\bgrill\b|dairy|brewing|beverage|grocery|bakery|\bmeat\b|vending|catering|\bcafe|coffee|\bpizza\b|\bdeli\b|snack", "Food & Hospitality"),
    (r"\bmotors\b|automotive|auto parts", "Automotive"),
    (r"\bairlines?\b|\bhotels?\b|\bresort\b|\bcasino\b", "Airlines & Travel"),
    (r"\bschool district\b|universit|\bcollege\b|academy|\beducation\b|\binstitute\b|\bisd\b", "Education"),
    (r"aerospace|aviation|\bdefense\b|aircraft", "Aerospace & Defense"),
    (r"\bmedia\b|entertainment|\bstudios?\b|broadcast|publishing|\brecords\b|\bradio\b", "Media & Entertainment"),
    (r"telecom|wireless|communications", "Telecom"),
    (r"logistics|freight|trucking|distribution|\bwarehouse|shipping|\bcargo\b|fulfillment|\bexpress\b", "Logistics & Transport"),
    (r"manufactur|\bindustries\b|\bsteel\b|\bmetal(s|works)?\b|plastics|\bfactory\b|\bmills?\b|fabricat|foundry|machining|bottling", "Manufacturing"),
    (r"construction|\bbuilders\b|realty|real estate|properties", "Real Estate & Construction"),
    (r"\bfarms?\b|agricultur|\borchard|\bgrowers?\b", "Agriculture"),
    (r"\bcounty\b|city of |department of |municipal|nonprofit|non-profit|\bymca\b", "Government & Nonprofit"),
    (r"\benergy\b|petroleum|\bsolar\b|\boil (and|&) gas\b|electric power|power (company|generation|plant|utility)", "Energy"),
    (r"software|technolog|semiconductor|robotics|cybersecurity", "Technology"),
    (r"\bstores?\b|\bretail\b|\bmart\b|apparel|\boutfitters\b|\bboutique\b", "Retail & E-commerce"),
]


def classify_deterministic(name):
    """Return a valid INDUSTRY_VOCABULARY label for `name`, or None if unsure.
    Conservative on purpose: ambiguous names fall through to the LLM."""
    n = (name or "").lower()
    if not n.strip():
        return None
    for key, lab in _DET_KNOWN.items():
        if key in n:
            return lab if lab in INDUSTRY_VOCABULARY else None
    for pat, lab in _DET_KW:
        if re.search(pat, n):
            return lab if lab in INDUSTRY_VOCABULARY else None
    return None


def run():
    candidates = fetch_candidates()

    # Deterministic pre-pass: instant + free, fills the high-confidence bulk of
    # the backlog (blank-fill only, vocabulary re-validated) so the LLM only
    # spends its budget on genuinely ambiguous names. Bounded per run so a
    # single invocation stays inside the deadline; the rest drains next run.
    det_cap = max(0, int(os.environ.get("INDUSTRY_DET_MAX", "6000")))
    det_items, remaining = [], []
    for row in candidates:
        lab = classify_deterministic(row.get("company_name") or "") if len(det_items) < det_cap else None
        if lab:
            det_items.append({"id": int(row["id"]), "industry": lab})
        else:
            remaining.append(row)
    det_filled = []
    if det_items:
        if DRY_RUN:
            print(f"DRY RUN deterministic: would fill {len(det_items)} row(s); e.g.:")
            for it in det_items[:15]:
                print(f"  det id={it['id']}: {it['industry']}")
        else:
            det_filled, det_skip, det_nf = post_fills(det_items)
            print(f"deterministic pre-pass: {len(det_filled)} filled / {len(det_items)} matched "
                  f"(skipped_not_blank={len(det_skip)}, not_found={len(det_nf)})")
    # THREE-HOURLY ordinal: the job now runs 8x/day, so a six-hourly ordinal
    # pointed two consecutive runs at the same slice (and a daily one pointed
    # all eight there). The divisor must track the schedule.
    _now = datetime.now(timezone.utc)
    _ordinal = (date.today().toordinal() * 8 + (_now.hour // 3)) * SHARDS + SHARD
    queue = rotating_slice(remaining, BATCH, _ordinal)
    items, confirmed, unconfirmed, failures, checked = [], 0, 0, 0, 0
    started_at = time.monotonic()
    for row in queue:
        # Nothing is half-written per row, so stopping between rows is safe;
        # the next daily run resumes the rotation.
        if time.monotonic() - started_at >= DEADLINE_SECONDS:
            print(f"Reached INDUSTRY_BACKFILL_DEADLINE_SECONDS={DEADLINE_SECONDS}; "
                  f"stopping safely after {checked} row(s)")
            break
        checked += 1
        label, status = classify_confirmed(row.get("company_name") or "", row.get("excerpt") or "")
        if status == "failed":
            failures += 1
            print(f"  id={row['id']} ({row.get('company_name','')}): FAILED (retried on a later rotation)")
        elif status == "confirmed":
            confirmed += 1
            items.append({"id": int(row["id"]), "industry": label})
            print(f"  id={row['id']} ({row.get('company_name','')}): {label}")
        else:
            unconfirmed += 1
            print(f"  id={row['id']} ({row.get('company_name','')}): unconfirmed — left blank")
        time.sleep(0.2)

    print(f"blank_backlog={len(candidates)} queue={len(queue)} checked={checked} "
          f"confirmed={confirmed} unconfirmed={unconfirmed} failures={failures}")

    if DRY_RUN:
        for item in items:
            print(f"  would fill id={item['id']}: {item['industry']}")
        print("DRY RUN: no writes performed.")
        return {"filled": 0, "checked": checked, "failures": failures}

    filled, skipped, not_found = ([], [], [])
    remaining = None
    if items:
        filled, skipped, not_found = post_fills(items)
        print(f"filled={len(filled)} skipped_not_blank={len(skipped)} not_found={len(not_found)}")
        if not_found:
            # A vanished id means the row set changed mid-run (dedupe/purge);
            # visible, but the other applied fills remain valid.
            print(f"WARNING: ids not found: {not_found}")

    # A fully failed attempted pass must be visible in Actions rather than
    # reading as a quiet no-op day (reason_backfill / reclassify rule). The
    # deterministic pre-pass filling rows keeps a bad-LLM day from reading as
    # total failure.
    if checked and failures == checked and not items and not det_filled:
        raise RuntimeError(f"All {checked} attempted industry classifications failed")

    total_filled = len(det_filled) + len(filled)
    pending = max(0, len(candidates) - total_filled)
    detail = (f"{total_filled} industries filled ({len(det_filled)} deterministic + "
              f"{len(filled)} 2-pass LLM, fixed vocabulary, blank fields only); "
              f"{unconfirmed} left blank as unconfirmed/unknown; {failures} model "
              f"failures; ~{pending} blank-industry rows pending")
    if not report_source_health("industry_backfill", "ok", total_filled, detail):
        raise RuntimeError("Could not publish industry_backfill completion health status")
    return {"filled": total_filled, "checked": checked, "failures": failures}


def main():
    if not SITE or (not KEY and not DRY_RUN):
        print("WP_SITE_URL and WP_API_KEY are required (or set INDUSTRY_BACKFILL_DRY_RUN=1)")
        return 1
    if not INDUSTRY_VOCABULARY:
        print("INDUSTRY_VOCABULARY is empty — refusing to run")
        return 1
    if not DRY_RUN:
        if not report_source_health("industry_backfill", "running", 0,
                                    "bounded company+excerpt industry classification in progress"):
            raise RuntimeError("Could not publish industry_backfill running health status")
    try:
        run()
        return 0
    except Exception as exc:
        # A failed backfill attempt is a material condition, not a quiet retry:
        # record it in the public health ledger, then exit non-zero.
        if not DRY_RUN:
            report_source_health("industry_backfill", "degraded", 0, f"industry backfill failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
