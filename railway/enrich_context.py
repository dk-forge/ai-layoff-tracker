"""Evidence-bounded legacy context enrichment.

Fetches a small batch of source-linked rows and fills only currently blank
employer domicile or public announcement date when exact source text supports
the value. It never changes count, layoff date, stage, source, or AI label.
"""
import os
import sys

import requests

from extractor import extract_context_evidence
from reclassify_legacy_ai import UA, clean_html

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(50, int(os.environ.get("CONTEXT_ENRICH_BATCH", "10"))))


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
        response = requests.get(
            f"{SITE}/wp-json/layoffs/v1/query",
            params={"ai": "1", "context_missing": "1", "per_page": BATCH, "page": 1, "sort": "id", "dir": "asc"},
            headers={"User-Agent": UA}, timeout=60,
        )
        response.raise_for_status()
        rows = response.json().get("data", [])
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
        report_health("ok", updated, f"checked={len(rows)} unsupported_or_unreadable={unreadable}")
        print(f"checked={len(rows)} queued={len(updates)} unreadable_or_unsupported={unreadable}")
        return 0
    except Exception as exc:
        report_health("degraded", detail=str(exc))
        raise


if __name__ == "__main__":
    sys.exit(main())
