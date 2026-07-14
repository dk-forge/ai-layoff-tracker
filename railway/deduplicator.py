"""
Prevents duplicate entries via WordPress REST API check.
"""
import os

import requests


def is_duplicate(dedup_hash):
    """Check if this hash already exists in WordPress.

    On any failure we allow the entry through (better a duplicate than a
    missed entry) — the WordPress /add endpoint re-checks server-side, so
    a false negative here is caught anyway.
    """
    if not dedup_hash:
        return False

    wp_url = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
    api_key = os.environ.get("WP_API_KEY")
    if not wp_url or not api_key:
        print("Dedup check warning: WP_SITE_URL or WP_API_KEY not set — allowing entry through")
        return False

    try:
        resp = requests.get(
            f"{wp_url}/wp-json/layoffs/v1/check-duplicate",
            params={"hash": dedup_hash},
            headers={
                "X-Layoff-API-Key": api_key,
                # ModSecurity on the host blocks the default python-requests UA
                "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"Dedup check warning: HTTP {resp.status_code} — {resp.text[:200]} "
                  "— allowing entry through")
            return False
        return bool(resp.json().get("exists", False))
    except Exception as e:
        print(f"Dedup check error: {e} — allowing entry through")
        return False
