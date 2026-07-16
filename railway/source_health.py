"""Publish collector health after each autonomous source attempt.

Health is deliberately separate from row publication: an empty successful
response is visible as ``ok`` with zero entries, while exceptions are recorded
as ``degraded``. The public endpoint lets researchers see a coverage gap
instead of mistaking silence for zero layoffs.
"""
import os
import requests

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"


def report_source_health(source, status, entries=0, detail=""):
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        print("source-health skipped: WP_SITE_URL or WP_API_KEY missing")
        return False
    try:
        response = requests.post(
            f"{site}/wp-json/layoffs/v1/source-health",
            json={"source": source, "status": status, "entries": entries, "detail": detail[:240]},
            headers={"X-Layoff-API-Key": key, "User-Agent": UA},
            timeout=20,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        print(f"source-health report failed for {source}: {exc}")
        return False
