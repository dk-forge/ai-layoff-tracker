"""Autonomously re-check legacy AI flags against their linked sources.

The worker fetches only rows that were previously tagged AI and remain
``legacy_unreviewed``. It never removes a record or changes the original
source/count/date. A fetched source is reclassified only after DeepSeek returns
an exact evidence quote for any causal AI claim; inaccessible sources remain
plainly marked legacy/unreviewed for a later retry.

Env: WP_SITE_URL, WP_API_KEY, OPENROUTER_API_KEY.
Optional: RECLASSIFY_BATCH (default 10). The scheduled batch is deliberately
small because each row may require a slow publisher fetch and a model call.
"""
import html
import os
import re
import sys
import time

import requests

from extractor import classify_ai_evidence

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(100, int(os.environ.get("RECLASSIFY_BATCH", "10"))))


def clean_html(content):
    text = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\\1>", " ", content)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\\s+", " ", html.unescape(text)).strip()


def fetch_text(url):
    if not url.startswith(("http://", "https://")):
        return ""
    response = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    response.raise_for_status()
    return clean_html(response.content[:2_000_000].decode(response.encoding or "utf-8", errors="replace"))


def api_get(path, params=None):
    response = requests.get(f"{SITE}/wp-json/layoffs/v1/{path}", params=params, headers={"User-Agent": UA}, timeout=60)
    response.raise_for_status()
    return response.json()


def post_updates(items):
    response = requests.post(
        f"{SITE}/wp-json/layoffs/v1/reclassify", json={"items": items},
        headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main():
    if not (SITE and KEY and os.environ.get("OPENROUTER_API_KEY")):
        print("WP_SITE_URL / WP_API_KEY / OPENROUTER_API_KEY required")
        return 1
    data = api_get("query", {"ai": "1", "review_status": "legacy_unreviewed", "per_page": BATCH, "page": 1, "sort": "id", "dir": "asc"})
    rows = data.get("data", [])
    if not rows:
        print("No legacy AI rows pending reclassification")
        return 0
    updates, unreadable, model_failures = [], 0, 0
    for row in rows:
        try:
            text = fetch_text(row.get("source_url") or "")
            if not text:
                unreadable += 1
                continue
            result = classify_ai_evidence(text)
            if not result:
                model_failures += 1
                continue
            updates.append({"id": row["id"], **result})
            time.sleep(0.25)
        except Exception as exc:
            unreadable += 1
            print(f"unreadable id {row['id']}: {exc}")
    if updates:
        result = post_updates(updates)
        print(f"reclassified={len(result.get('updated', []))} rejected={len(result.get('rejected', []))}")
    print(f"checked={len(rows)} queued={len(updates)} unreadable={unreadable} model_failures={model_failures}")
    # A total failure should be visible in Actions rather than silently looking
    # like a successful historical clean-up.
    return 1 if not updates and len(rows) and unreadable + model_failures == len(rows) else 0


if __name__ == "__main__":
    sys.exit(main())
