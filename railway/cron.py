"""
AI Layoff Tracker — Main Cron Script
Runs 2x daily: 9 AM ET + 5 PM ET (see railway.toml for the schedule)
"""
import os
from datetime import datetime, timedelta, timezone

import requests

from sources.edgar import pull_edgar_filings
from sources.gdelt import pull_gdelt_between
from sources.newsapi import pull_news_articles
from sources.press_releases import pull_press_releases
from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health


def _mark_phase(phase):
    """Tell the live badge the pipeline is working (best-effort)."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return
    try:
        requests.post(f"{site}/wp-json/layoffs/v1/status",
                      json={"phase": phase},
                      headers={"X-Layoff-API-Key": key,
                               "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"},
                      timeout=20)
    except Exception as e:
        print(f"phase ping failed: {e}")


def run():
    _mark_phase("refreshing")
    entries = []

    # Pull from sources — one source failing must not kill the run
    for source, collector in (
        ("edgar", pull_edgar_filings),
        ("newsapi", pull_news_articles),
        ("press_releases", pull_press_releases),
    ):
        try:
            report_source_health(source, "running", 0, "collection in progress")
            pulled = collector()
            entries += pulled
            report_source_health(source, "ok", len(pulled))
        except Exception as e:
            report_source_health(source, "degraded", 0, str(e))
            print(f"{source} source failed: {e}")
    try:
        # Worldwide press coverage (Europe/Asia/everywhere) via GDELT. 36h
        # window overlaps the twice-daily runs; dedup drops the repeats.
        now = datetime.now(timezone.utc)
        report_source_health("gdelt", "running", 0, "collection in progress")
        pulled = pull_gdelt_between(now - timedelta(hours=36), now)
        entries += pulled
        report_source_health("gdelt", "ok", len(pulled))
    except Exception as e:
        report_source_health("gdelt", "degraded", 0, str(e))
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

            # Always let WordPress perform authoritative deduplication. A 409
            # now retains this article as a corroborating source report on the
            # canonical event; pre-skipping here would throw that evidence away.
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
