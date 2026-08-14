"""Bounded role-category backfill from already-stored source evidence.

Most rows' freeform ``roles`` text is blank because sources rarely put the
affected teams in a headline — the statement usually sits in the stored
excerpt. This worker re-reads ONLY text the tracker already retains for a row
(roles, excerpt, exact AI quote, announcement evidence) — it makes no external
page fetch — and asks the model to map explicitly stated roles onto the fixed
category vocabulary. Rows whose stored evidence does not state the roles are
marked ``unknown`` (checked, nothing stated) so the bounded daily queue drains
instead of re-reading the same rows forever. It never guesses, never
overwrites an existing category, and cannot change counts, dates, sources or
AI labels (the keyed endpoint only fills blank role_categories).

Env: WP_SITE_URL, WP_API_KEY, OPENROUTER_API_KEY.
Optional: ROLES_BATCH (default 40; largest events first so high-impact rows
are categorized early). ROLES_DEADLINE_SECONDS (default 900) stops safely
between rows so a slow model call cannot consume the GitHub Actions limit.

SAFE TO DEFER, and this is why: the queue is server-side and bounded, nothing
is marked until the single POST at the end, and a row this run never reached is
simply still queued tomorrow. Running it tomorrow is running it today. On
2026-08-12 one 503 from `/enrich-roles` killed the run and emailed the owner —
almost certainly WordPress in maintenance mode while an FTPS deploy of this repo
landed, i.e. the tracker paging its owner about its own deploy.
"""
import os
import sys
import time

import requests

import host_call
from extractor import (
    extract_role_categories, CreditsExhaustedError,
    spend_deferral_count, spend_deferred_since,
)
import spend
from reclassify_legacy_ai import UA

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "enrich-roles"

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(200, int(os.environ.get("ROLES_BATCH", "40"))))
DEADLINE_SECONDS = max(60, min(1100, int(os.environ.get("ROLES_DEADLINE_SECONDS", "900"))))


def build_passage(row):
    """Concatenate the row's already-retained text; no external fetches."""
    parts = []
    for key in ("roles", "excerpt", "ai_language", "announcement_evidence"):
        value = (row.get(key) or "").strip()
        if value:
            parts.append(value)
    return "\n".join(parts)


def report_health(status, entries=0, detail=""):
    try:
        requests.post(
            f"{SITE}/wp-json/layoffs/v1/source-health",
            json={"source": "role_enrichment", "status": status, "entries": entries, "detail": detail},
            headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=30,
        ).raise_for_status()
    except Exception as exc:
        print(f"role-enrichment health report failed: {exc}")


def main():
    if not (SITE and KEY and os.environ.get("OPENROUTER_API_KEY")):
        print("WP_SITE_URL / WP_API_KEY / OPENROUTER_API_KEY required")
        return 1
    report_health("running", detail="Extracting role categories from stored evidence")
    try:
        payload = host_call.get_json(
            f"{SITE}/wp-json/layoffs/v1/query",
            params={"roles_missing": "1", "per_page": BATCH, "page": 1, "sort": "job_count", "dir": "desc"},
            headers={"User-Agent": UA}, timeout=60,
        )
        rows = payload.get("data", [])
        if not rows:
            report_health("ok", 0, "No rows pending role-category extraction")
            print("No rows pending role-category extraction")
            return 0
        items, checked, stated, model_failures = [], 0, 0, 0
        deferred = 0
        started_at = time.monotonic()
        for row in rows:
            # Stopping between rows changes no fact; unchecked rows simply
            # stay queued for tomorrow's bounded run.
            if time.monotonic() - started_at >= DEADLINE_SECONDS:
                print(f"Reached ROLES_DEADLINE_SECONDS={DEADLINE_SECONDS}; stopping safely after {checked} row(s)")
                break
            if not spend.paid_reads_enabled():
                # "No discretionary headroom left in the month" is the guard
                # working, not the model failing. These rows were never read,
                # so they stay queued and a later run reads them; counting them
                # as model failures used to exit 1 and page the owner.
                deferred = len(rows) - checked
                print(f"paid reads are OFF for budget: deferring the remaining "
                      f"{deferred} row(s) unread to a later run")
                break
            checked += 1
            passage = build_passage(row)
            if not passage:
                # The queue filter requires stored text, so this is defensive.
                items.append({"id": row["id"], "categories": ["unknown"], "evidence": ""})
                continue
            before = spend_deferral_count()
            result = extract_role_categories(passage)
            if result is None and spend_deferred_since(before):
                checked -= 1
                deferred = len(rows) - checked
                print(f"paid reads went off mid-row: deferring {deferred} "
                      f"unread row(s) to a later run")
                break
            if result is None:
                # Model/parse failure: leave the row queued rather than
                # mislabelling a transient outage as "roles not stated".
                model_failures += 1
                continue
            if result["categories"]:
                stated += 1
                items.append({"id": row["id"], "categories": result["categories"], "evidence": result["evidence"]})
            else:
                items.append({"id": row["id"], "categories": ["unknown"], "evidence": ""})
            time.sleep(0.25)
        updated = marked_unknown = rejected = 0
        if items:
            result = host_call.post_json(
                f"{SITE}/wp-json/layoffs/v1/enrich-roles", {"items": items},
                headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=60,
            )
            updated = len(result.get("updated", []))
            marked_unknown = len(result.get("marked_unknown", []))
            rejected = len(result.get("rejected", []))
        detail = (
            f"queue={payload.get('total', 0)} checked={checked} stated={stated} "
            f"marked_unknown={marked_unknown} rejected={rejected} "
            f"model_failures={model_failures} deferred_on_spend={deferred}"
        )
        report_health("ok", updated, detail)
        print(f"{detail} updated={updated}")
        if deferred:
            spend.note_truncated(f"{deferred} row(s) left unread: paid reads "
                                 f"were off for budget")
            print(f"::notice::enrich-roles SKIPPED {deferred} row(s) for "
                  f"budget. Nobody read them, they stay queued, and a later "
                  f"run reads them. This run exits 0.")
        spend.record_job_run(items=checked, changed=updated)
        host_call.clear(JOB)
        # A run where every attempted row failed at the model must be a
        # visible failure, not a quiet no-op that looks like a clean pass.
        # `checked` counts rows a model was actually ASKED about: deferred rows
        # are excluded above, so a budget stop exits 0 and a real model outage
        # still exits 1.
        return 1 if checked and model_failures == checked else 0
    except host_call.Deferred as exc:
        # The host never answered. Nothing was marked, so the identical queue
        # is waiting for tomorrow's run; the ledger counts this and the THIRD
        # in a row goes red like any other broken job.
        return host_call.defer(JOB, str(exc))
    except CreditsExhaustedError as exc:
        # BILLING, not code: provider out of credits. Distinct, actionable state
        # and exit 0 so it does not page as a code failure every run; the weekly
        # digest surfaces it until topped up. The circuit breaker already stopped
        # the batch after the first 402.
        report_health("degraded", 0, "OpenRouter credits exhausted (HTTP 402) - top up at "
                      "https://openrouter.ai/settings/credits; no rows enriched")
        print(f"::warning::enrich_roles halted: {exc} (billing, not a code failure)")
        return 0
    except Exception as exc:
        report_health("degraded", detail=str(exc))
        raise


if __name__ == "__main__":
    sys.exit(main())
