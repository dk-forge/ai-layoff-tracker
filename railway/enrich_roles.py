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
"""
import os
import sys
import time

import requests

from extractor import extract_role_categories, CreditsExhaustedError
import spend
from reclassify_legacy_ai import UA

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
        response = requests.get(
            f"{SITE}/wp-json/layoffs/v1/query",
            params={"roles_missing": "1", "per_page": BATCH, "page": 1, "sort": "job_count", "dir": "desc"},
            headers={"User-Agent": UA}, timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", [])
        if not rows:
            report_health("ok", 0, "No rows pending role-category extraction")
            print("No rows pending role-category extraction")
            return 0
        items, checked, stated, model_failures = [], 0, 0, 0
        started_at = time.monotonic()
        for row in rows:
            # Stopping between rows changes no fact; unchecked rows simply
            # stay queued for tomorrow's bounded run.
            if time.monotonic() - started_at >= DEADLINE_SECONDS:
                print(f"Reached ROLES_DEADLINE_SECONDS={DEADLINE_SECONDS}; stopping safely after {checked} row(s)")
                break
            checked += 1
            passage = build_passage(row)
            if not passage:
                # The queue filter requires stored text, so this is defensive.
                items.append({"id": row["id"], "categories": ["unknown"], "evidence": ""})
                continue
            result = extract_role_categories(passage)
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
            posted = requests.post(
                f"{SITE}/wp-json/layoffs/v1/enrich-roles", json={"items": items},
                headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=60,
            )
            posted.raise_for_status()
            result = posted.json()
            updated = len(result.get("updated", []))
            marked_unknown = len(result.get("marked_unknown", []))
            rejected = len(result.get("rejected", []))
        detail = (
            f"queue={payload.get('total', 0)} checked={checked} stated={stated} "
            f"marked_unknown={marked_unknown} rejected={rejected} model_failures={model_failures}"
        )
        report_health("ok", updated, detail)
        print(f"{detail} updated={updated}")
        spend.record_job_run(items=checked, changed=updated)
        # A run where every attempted row failed at the model must be a
        # visible failure, not a quiet no-op that looks like a clean pass.
        return 1 if checked and model_failures == checked else 0
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
