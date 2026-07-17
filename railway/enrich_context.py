"""Evidence-bounded legacy context enrichment.

Fetches a small batch of source-linked rows and fills only currently blank
employer domicile or public announcement date when exact source text supports
the value. It never changes count, layoff date, stage, source, or AI label.
"""
import os
import sys
from datetime import date

import requests

from extractor import extract_context_evidence
from reclassify_legacy_ai import UA, clean_html

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(50, int(os.environ.get("CONTEXT_ENRICH_BATCH", "5"))))
MODE = os.environ.get("CONTEXT_ENRICH_MODE", "default")


def query_params(batch, mode="default"):
    """Return a narrow, evidence-only candidate query for the selected mode."""
    params = {
        "context_missing": "1", "per_page": batch, "page": 1,
        "sort": "id", "dir": "asc",
    }
    if mode == "challenger_priority":
        # These are candidates for the strict US-announcement comparator, not
        # pre-judged US employers or AI-primary events. The worker still needs
        # exact source text before it can fill either context field.
        params.update({
            "ai": "1", "stage": "announced", "country": "United States",
            "sort": "job_count", "dir": "desc",
        })
    return params


def rotating_page(total, batch, today=None):
    """Rotate bounded batches so inaccessible sources cannot starve the queue."""
    pages = max(1, (max(0, int(total)) + batch - 1) // batch)
    day = (today or date.today()).toordinal()
    return 1 + (day % pages)


def report_health(status, entries=0, detail=""):
    try:
        requests.post(
            f"{SITE}/wp-json/layoffs/v1/source-health",
            json={"source": "context_enrichment", "status": status, "entries": entries, "detail": detail},
            headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=30,
        ).raise_for_status()
    except Exception as exc:
        print(f"context health report failed: {exc}")


def fetch_text(url):
    if not url.startswith(("http://", "https://")):
        return ""
    response = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    response.raise_for_status()
    return clean_html(response.content[:2_000_000].decode(response.encoding or "utf-8", errors="replace"))


def main():
    if not (SITE and KEY and os.environ.get("OPENROUTER_API_KEY")):
        print("WP_SITE_URL / WP_API_KEY / OPENROUTER_API_KEY required")
        return 1
    report_health("running", detail="Re-reading source evidence")
    try:
        params = query_params(BATCH, MODE)
        response = requests.get(
            f"{SITE}/wp-json/layoffs/v1/query",
            params=params,
            headers={"User-Agent": UA}, timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        page = rotating_page(payload.get("total", 0), BATCH)
        if page != 1:
            params["page"] = page
            response = requests.get(
                f"{SITE}/wp-json/layoffs/v1/query", params=params,
                headers={"User-Agent": UA}, timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        rows = payload.get("data", [])
        updates, unreadable = [], 0
        for row in rows:
            try:
                text = fetch_text(row.get("source_url") or "")
                result = extract_context_evidence(text) if text else None
                if result:
                    updates.append({"id": row["id"], **result})
                else:
                    unreadable += 1
            except Exception as exc:
                unreadable += 1
                print(f"unreadable id {row.get('id')}: {exc}")
        updated = 0
        if updates:
            posted = requests.post(
                f"{SITE}/wp-json/layoffs/v1/enrich-context", json={"items": updates},
                headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=60,
            )
            posted.raise_for_status()
            result = posted.json()
            updated = len(result.get("updated", []))
            print(f"enriched={updated} rejected={len(result.get('rejected', []))}")
        detail = f"mode={MODE} page={payload.get('page', 1)} checked={len(rows)} unsupported_or_unreadable={unreadable}"
        report_health("ok", updated, detail)
        print(f"{detail} queued={len(updates)}")
        return 0
    except Exception as exc:
        report_health("degraded", detail=str(exc))
        raise


if __name__ == "__main__":
    sys.exit(main())
