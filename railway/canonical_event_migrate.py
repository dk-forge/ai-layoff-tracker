"""Resumable migration of legacy canonical rows into event/source-report tables.

No LLM calls, no deletes, and no changes to published totals: each existing
row becomes a one-source canonical event; new duplicate reports join that event
after deployment. Run repeatedly until ``remaining`` is zero.

DEFERRABLE ONLY BEFORE THE FIRST BATCH LANDS. This walks a cursor and each
batch is applied server-side, so "nothing happened, try tomorrow" is only true
until batch one is written. After that, a host that stops answering is the same
condition as the existing MAX_BATCHES cap, which the migration already declares
safe: stop, say so, and let the next scheduled run resume. Recording that as a
deferral would be a lie about what the run did.
"""
import os
import sys

import host_call

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "canonical-event-migrate"

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
    applied = 0
    for _ in range(MAX_BATCHES):
        try:
            data = host_call.post_json(
                f"{SITE}/wp-json/layoffs/v1/event-migrate",
                {"after_id": after, "limit": LIMIT},
                headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=90,
            )
        except host_call.Deferred as exc:
            if applied:
                # Batches DID land. This is the batch cap by another name.
                print(f"::notice::host stopped answering after {applied} batch(es) "
                      f"({exc}); the next scheduled run resumes from the cursor")
                return 0
            return host_call.defer(JOB, str(exc))
        applied += 1
        print(data)
        if not data.get("processed") or not data.get("remaining"):
            host_call.clear(JOB)
            return 0
        after = int(data["last_id"])
    print("Batch cap reached; next scheduled run resumes safely.")
    host_call.clear(JOB)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"canonical event migration failed: {exc}")
        sys.exit(1)
