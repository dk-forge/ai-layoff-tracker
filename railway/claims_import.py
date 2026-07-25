"""Fetch the US unemployment-claims backdrop and store it in WordPress.

Runs the keyless FRED puller (sources/claims.py: national ICSA/CCSA + all 50
states + DC) and POSTs the built payload to the /claims-ingest endpoint, which
caches it for the public /claims endpoint. This is LABELED MACRO CONTEXT (BLS/
DOL jobless claims) — economy-wide joblessness from all causes, never summed
into or conflated with the tracker's verified layoff counts. Weekly is plenty
(DOL releases Thursdays); a daily run just keeps it fresh. Fail-soft: an empty
FRED pull never overwrites the good cached payload.

Env: WP_SITE_URL, WP_API_KEY. No LLM, no cost.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests

from sources.claims import build_claims_payload

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")


def main():
    if not (SITE and KEY):
        print("WP_SITE_URL and WP_API_KEY required")
        return 1
    payload = build_claims_payload(months_back=36, include_states=True)
    if not (payload.get("national", {}).get("initial")):
        # FRED unreachable / empty — do NOT overwrite the cached payload.
        print(f"claims payload empty (errors={payload.get('errors')}); leaving cache intact")
        return 1
    try:
        r = requests.post(f"{SITE}/wp-json/layoffs/v1/claims-ingest",
                          json=payload, headers={"X-Layoff-API-Key": KEY, **UA}, timeout=60)
    except requests.RequestException as exc:
        print(f"claims-ingest POST failed: {exc}")
        return 1
    print(f"claims-ingest -> HTTP {r.status_code}: {r.text[:300]}")
    r.raise_for_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
