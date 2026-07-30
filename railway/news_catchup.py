"""
Weekly news catch-up: pull the last N days of layoff coverage from credible
outlets (NewsAPI) and post the verified events. Runs Mondays 09:30 UTC via
.github/workflows/news-catchup.yml, and by hand on dispatch.

Reuses the same extractor + dedup + poster as the daily cron. Idempotent.

WHY THIS REPORTS AS "news_catchup" AND NOT "newsapi" (fixed 2026-07-30)
----------------------------------------------------------------------
The `newsapi` COLLECTOR was retired 2026-07-25 (dropped from cron.py's loop,
replaced by keyless Google News RSS; see alt_retired_sources() in db.php). This
module was the step that got missed: it kept POSTing health under the retired
`newsapi` id every Monday. Two things broke as a result, for five weeks:

  1. The retirement was silently VOIDED. alt_retired_sources() only masks a row
     whose last run predates the retirement date — deliberately, so a collector
     switched back on is never hidden. A fresh Monday `checked_at` is always
     after 2026-07-25, so the coercion was skipped and the public health page
     kept advertising `newsapi` as a live "Twice daily · Worldwide" collector.
  2. It generated PERMANENT NOISE. `newsapi` carried a 2-day staleness ceiling
     (it was a twice-daily collector), but the only surviving job runs WEEKLY.
     So it read STALE five days out of every seven, forever. ops_status.py led
     with "ACTION NEEDED: 1 item(s) -> newsapi stale" on almost every session —
     an alarm that can never be cleared, which is an alarm nobody reads. On
     2026-07-30 that permanent amber was the ONLY thing ops_status reported
     while Spirit Airlines was live and overstated by 4,000 jobs.

This module still USES sources/newsapi.py (the key works, the code is fine) —
what was retired is the twice-daily collector identity, not the library. So it
reports under its own name, at its own weekly cadence, and `newsapi` gets no
further posts and finally masks as retired.

RULE for the next retirement: removing a source from cron.py and adding it to
alt_retired_sources() is only steps 1 and 2. Step 3 is stopping EVERY remaining
path that posts health under that id — otherwise step 2 does nothing.

Env:
  NEWSAPI_KEY, OPENROUTER_API_KEY, WP_SITE_URL, WP_API_KEY  (as usual)
  NEWS_DAYS_BACK   int   how far back to pull (default 28; NewsAPI free tier
                         caps history at ~30 days)
"""
import os

from sources.newsapi import pull_news_articles
from extractor import extract_layoff_data
from source_health import report_source_health
from wp_poster import post_to_wordpress

# The health-ledger id for THIS job. Deliberately not "newsapi" — see the
# module docstring. Its staleness ceiling lives in ops_status.MAX_AGE and
# health_digest.MAX_AGE_DAYS and must match this job's WEEKLY cadence.
HEALTH_ID = "news_catchup"


def run():
    days = int(os.environ.get("NEWS_DAYS_BACK") or 28)
    print(f"News catch-up: pulling last {days} days of layoff coverage")

    # This weekly run is a real collector attempt. Record it through the same
    # public health channel as every other collector so the health dashboard's
    # "last pull" is not misleadingly stale after a successful catch-up.
    if not report_source_health(HEALTH_ID, "running", 0, f"{days}-day catch-up in progress"):
        raise RuntimeError("Could not publish news catch-up health status")
    try:
        entries = pull_news_articles(days_back=days)
    except Exception as exc:
        report_source_health(HEALTH_ID, "degraded", 0, f"{days}-day catch-up failed: {exc}")
        raise
    print(f"NewsAPI returned {len(entries)} articles")

    posted = dupes = skipped = failed = ai = 0
    for raw in entries:
        try:
            extracted = extract_layoff_data(raw)
            if not extracted:
                skipped += 1
                continue
            status = post_to_wordpress(extracted)
            if status == "posted":
                posted += 1
                if extracted.get("ai_explicit"):
                    ai += 1
                    print(f"  ★ AI-attributed: {extracted.get('company_name')} — "
                          f"\"{(extracted.get('ai_language') or '')[:80]}\"")
            elif status == "duplicate":
                dupes += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"error on {raw.get('source_url')}: {e}")

    print(f"News catch-up complete: {posted} posted ({ai} AI-attributed), "
          f"{dupes} duplicates, {skipped} non-events, {failed} failed")
    if not report_source_health(
        HEALTH_ID,
        "ok",
        len(entries),
        f"{days}-day catch-up: {posted} posted, {dupes} duplicates, "
        f"{skipped} non-events, {failed} processing failures",
    ):
        raise RuntimeError("Could not publish news catch-up health result")


if __name__ == "__main__":
    run()
