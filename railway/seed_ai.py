"""
Seed a curated set of verified, AI-attributed layoffs (seed_data/ai_layoffs.json)
into WordPress. Each record is already structured with an exact executive quote
and a real source URL, so no LLM extraction is needed — just dedup + post.

Idempotent (dedup guard). Env: WP_SITE_URL, WP_API_KEY.
"""
import hashlib
import json
import os

from deduplicator import is_duplicate
from wp_poster import post_to_wordpress

SEED_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "ai_layoffs.json")


def run():
    with open(SEED_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    print(f"Seeding {len(entries)} curated AI-attributed layoffs")

    posted = dupes = failed = 0
    for entry in entries:
        company = (entry.get("company_name") or "").strip()
        job_count = entry.get("job_count")
        if not company or not job_count:
            print(f"skip (missing company/count): {company}")
            failed += 1
            continue

        hash_input = f"{company.lower()}{entry.get('layoff_date') or ''}{job_count}"
        entry["dedup_hash"] = hashlib.md5(hash_input.encode("utf-8")).hexdigest()

        if is_duplicate(entry["dedup_hash"]):
            print(f"= already present: {company}")
            dupes += 1
            continue

        status = post_to_wordpress(entry)
        if status == "posted":
            posted += 1
        elif status == "duplicate":
            dupes += 1
        else:
            failed += 1

    print(f"Seed complete: {posted} posted, {dupes} duplicates, {failed} failed")


if __name__ == "__main__":
    run()
