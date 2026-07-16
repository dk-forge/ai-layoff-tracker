"""Resumable migration of legacy canonical rows into event/source-report tables.

No LLM calls, no deletes, and no changes to published totals: each existing
row becomes a one-source canonical event; new duplicate reports join that event
after deployment. Run repeatedly until ``remaining`` is zero.
"""
import os
import sys
import requests

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
LIMIT = max(1, min(1000, int(os.environ.get("EVENT_MIGRATE_BATCH", "500"))))
MAX_BATCHES = max(1, min(200, int(os.environ.get("EVENT_MIGRATE_MAX_BATCHES", "20"))))


def main():
    if not (SITE and KEY):
        print("WP_SITE_URL / WP_API_KEY required")
        return 1
    after = 0
    for _ in range(MAX_BATCHES):
        response = requests.post(
            f"{SITE}/wp-json/layoffs/v1/event-migrate",
            json={"after_id": after, "limit": LIMIT},
            headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        print(data)
        if not data.get("processed") or not data.get("remaining"):
            return 0
        after = int(data["last_id"])
    print("Batch cap reached; next scheduled run resumes safely.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"canonical event migration failed: {exc}")
        sys.exit(1)
