"""
AI Layoff Tracker — Main Cron Script
Runs 2x daily: 9 AM ET + 5 PM ET (see railway.toml for the schedule)
"""
from datetime import datetime, timedelta, timezone

from sources.edgar import pull_edgar_filings
from sources.gdelt import pull_gdelt_between
from sources.newsapi import pull_news_articles
from extractor import extract_layoff_data
from deduplicator import is_duplicate
from wp_poster import post_to_wordpress


def run():
    entries = []

    # Pull from sources — one source failing must not kill the run
    try:
        entries += pull_edgar_filings()
    except Exception as e:
        print(f"EDGAR source failed: {e}")
    try:
        entries += pull_news_articles()
    except Exception as e:
        print(f"NewsAPI source failed: {e}")
    try:
        # Worldwide press coverage (Europe/Asia/everywhere) via GDELT. 36h
        # window overlaps the twice-daily runs; dedup drops the repeats.
        now = datetime.now(timezone.utc)
        entries += pull_gdelt_between(now - timedelta(hours=36), now)
    except Exception as e:
        print(f"GDELT source failed: {e}")

    print(f"Pulled {len(entries)} raw entries")

    results = []
    posted = skipped_dupes = skipped_not_layoff = failed = 0

    for raw in entries:
        try:
            # DeepSeek extracts structured data
            extracted = extract_layoff_data(raw)
            if not extracted:
                skipped_not_layoff += 1
                continue

            # Skip duplicates
            if is_duplicate(extracted["dedup_hash"]):
                skipped_dupes += 1
                continue

            # Post to WordPress
            status = post_to_wordpress(extracted)
            if status == "posted":
                posted += 1
            elif status == "duplicate":
                skipped_dupes += 1
            else:
                failed += 1
            results.append({"entry": extracted["company_name"], "success": status == "posted"})
        except Exception as e:
            failed += 1
            print(f"Unexpected error processing entry {raw.get('source_url')}: {e}")

    print(
        f"Run complete: {len(entries)} pulled, {posted} posted, "
        f"{skipped_dupes} duplicates skipped, {skipped_not_layoff} non-events skipped, "
        f"{failed} failed"
    )
    return results


if __name__ == "__main__":
    run()
