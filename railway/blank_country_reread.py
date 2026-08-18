"""Re-read the source bodies of rows that carry no job-location country.

The 2026-08-18 measurement found 109 such rows out of 64,245. The blank is
usually the strict rule working: `extractor.py` is told to return null when the
source does not state where the jobs were, and "Google axes 12,000 jobs" does
not state it. But the extractor read a stored EXCERPT, and an excerpt is not
the article. Where the article does say and the excerpt did not carry it, that
is a country we have and did not read - and this reads it.

It answers ONE question per row, through `extract_job_location_evidence`, which
requires an exact quote from the fetched body and returns nothing else. Rows
where the body does not state a location keep their blank, which is the correct
outcome and the expected one for most of the backlog. The field that makes such
a row FINDABLE is `employer_country`, and that is a different job
(`employer_domicile_backfill.py`) on deterministic public record, not this one.

MEASURED READABILITY, 2026-08-18: only 31 of the 82 news rows have a fetchable
body at all. Fifty of them cite a `news.google.com/rss/articles/...` redirect
that no longer resolves - every one returns an 11-byte page, and Wayback holds
no snapshot of an RSS redirect. That is a hard ceiling on this job, not a
tuning parameter, and no amount of spend moves it.

    WP_SITE_URL=... WP_API_KEY=... OPENROUTER_API_KEY=... \
        python3 railway/blank_country_reread.py
        --apply       write the recovered countries (default is a dry run)
        --max 200     cap the rows examined

A write here goes through /edit, which sets `edited=1`, rewrites the dedup hash
and publishes the change in the public corrections log. That is deliberate and
it is expensive: it is why nothing is written without a quote, and why the
dry run is the default.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

import spend
from employer_domicile_backfill import UA, fetch_blank_country_rows
from enrich_context import fetch_primary_or_snapshot, usable_article_text
from extractor import extract_job_location_evidence

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
EDIT_BATCH = 50
REASON = ("Source re-read: the cited article states where the cut jobs were, and the "
          "stored excerpt did not carry that sentence. Country filled from an exact quote "
          "in the source body; no count, date, source or AI label changed.")


def reread(rows):
    """``(recovered, unreadable, unstated, deferred)`` for a list of rows.

    One metered model call per readable row, and only for readable rows: a
    body we could not fetch is never paid for.
    """
    recovered, unreadable, unstated, deferred = [], [], [], []
    for row in rows:
        row_id = int(row["id"])
        label = f"{row_id} {row.get('company_name', '')}"
        try:
            text, snapshot = fetch_primary_or_snapshot(row.get("source_url") or "")
        except Exception as exc:
            unreadable.append((row_id, row.get("company_name", ""), type(exc).__name__))
            print(f"  unreadable  {label}: {type(exc).__name__}")
            continue
        if not usable_article_text(text):
            unreadable.append((row_id, row.get("company_name", ""), "no article body"))
            print(f"  unreadable  {label}: no article body ({len(text or '')} chars)")
            continue
        try:
            result = extract_job_location_evidence(text, row.get("company_name", ""))
        except spend.PaidReadsOff as exc:
            # UNDECIDED, never a verdict and never a red run. The row keeps its
            # blank and the next run reads it.
            deferred.append((row_id, row.get("company_name", ""), str(exc)))
            print(f"  deferred    {label}: {exc}")
            continue
        if result is None:
            unstated.append((row_id, row.get("company_name", "")))
            print(f"  no location {label}: the source does not state where the jobs were")
            continue
        result.update({"id": row_id, "company_name": row.get("company_name", ""),
                       "snapshot": snapshot})
        recovered.append(result)
        print(f"  RECOVERED   {label} -> {result['country']}")
        print(f"              quote: {result['country_evidence'][:160]!r}")
    return recovered, unreadable, unstated, deferred


def post_edits(recovered):
    edited, missed = [], []
    for start in range(0, len(recovered), EDIT_BATCH):
        batch = recovered[start:start + EDIT_BATCH]
        response = requests.post(
            f"{SITE}/wp-json/layoffs/v1/edit",
            json={"reason": REASON,
                  "edits": [{"id": item["id"], "fields": {"country": item["country"]}}
                            for item in batch]},
            headers={"X-Layoff-API-Key": KEY, **UA}, timeout=120)
        if response.status_code != 200:
            print(f"::error::edit failed HTTP {response.status_code}: {response.text[:300]}")
            return None, None
        out = response.json()
        edited.extend(out.get("edited") or [])
        missed.extend(list(out.get("not_found") or []) + list(out.get("rejected") or []))
    return edited, missed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max", type=int, default=200)
    args = parser.parse_args()
    if not SITE:
        print("WP_SITE_URL is required")
        return 1

    rows = fetch_blank_country_rows(SITE, args.max)
    print(f"blank-country rows: {len(rows)}")
    recovered, unreadable, unstated, deferred = reread(rows)

    print(f"\nrecovered country : {len(recovered)}")
    print(f"source silent     : {len(unstated)}  (correct: the article does not say where)")
    print(f"unreadable source : {len(unreadable)}  (never paid for)")
    print(f"deferred on spend : {len(deferred)}  (UNDECIDED, re-read next run)")
    print(f"spend this run    : ${spend.logical_run_cost_usd():.4f}")

    if not args.apply:
        print("\nDRY RUN. Re-run with --apply to write. /edit pins each row and "
              "publishes the change, so read the quotes above first.")
        return 0
    if not KEY:
        print("WP_API_KEY is required to apply")
        return 1
    if not recovered:
        print("Nothing to write.")
        return 0
    edited, missed = post_edits(recovered)
    if edited is None:
        return 1
    print(f"\nedited {len(edited)} row(s); not applied: {missed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
