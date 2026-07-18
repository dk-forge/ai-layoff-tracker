"""
One-off news catch-up: pull the last N days of layoff coverage from credible
outlets (NewsAPI) and post the verified events. This is where AI-attributed
layoffs live — companies rarely name AI in SEC filings, but news coverage does.

Reuses the same extractor + dedup + poster as the daily cron. Idempotent.

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


def run():
    days = int(os.environ.get("NEWS_DAYS_BACK") or 28)
    print(f"News catch-up: pulling last {days} days of layoff coverage")

    # A manually-dispatched recovery run is a real collector attempt.  Record
    # it through the same public health channel as the scheduled Railway
    # collector so the health dashboard's "last pull" is not misleadingly
    # stale after a successful catch-up.
    report_source_health("newsapi", "running", 0, f"manual {days}-day catch-up in progress")
    try:
        entries = pull_news_articles(days_back=days)
    except Exception as exc:
        report_source_health("newsapi", "degraded", 0, f"manual {days}-day catch-up failed: {exc}")
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
    report_source_health(
        "newsapi",
        "ok",
        len(entries),
        f"manual {days}-day catch-up: {posted} posted, {dupes} duplicates, "
        f"{skipped} non-events, {failed} processing failures",
    )


if __name__ == "__main__":
    run()
