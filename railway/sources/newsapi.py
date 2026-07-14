"""
Pulls layoff news from credible outlets via NewsAPI.

Free (Developer) tier caveats that bite silently:
  - articles are delayed ~24 hours, so days_back=1 can return nothing;
    the default here is 2 days and the deduplicator drops repeats
  - `content` is truncated to ~200 chars; title + description carry most signal
  - 100 requests/day
Production tier ($449/mo) removes the delay and truncation.
"""
import os
from datetime import datetime, timedelta, timezone

import requests

NEWSAPI_URL = "https://newsapi.org/v2/everything"

TRUSTED_DOMAINS = (
    "reuters.com,bloomberg.com,wsj.com,ft.com,apnews.com,"
    "techcrunch.com,cnbc.com,theguardian.com"
)


def pull_news_articles(days_back=2):
    api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        print("NewsAPI: no NEWSAPI_KEY found, skipping")
        return []

    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    params = {
        "q": 'layoffs OR "job cuts" OR "workforce reduction" OR "reduction in force"',
        "from": from_date,
        "domains": TRUSTED_DOMAINS,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100,
        "apiKey": api_key,
    }

    try:
        resp = requests.get(NEWSAPI_URL, params=params, timeout=30)

        if resp.status_code == 429:
            # Per error-handling requirements: log and skip, no retry this run
            print("NewsAPI: rate limited (429) — skipping this run")
            return []

        data = resp.json()
        if data.get("status") != "ok":
            print(f"NewsAPI error response: {data.get('code')} — {data.get('message')}")
            return []

        results = []
        for article in data.get("articles", []):
            title = article.get("title") or ""
            url = article.get("url") or ""
            # NewsAPI substitutes '[Removed]' placeholders for retracted items
            if not url or title == "[Removed]":
                continue
            results.append({
                "source_type": "news",
                "source_name": (article.get("source") or {}).get("name", "Unknown"),
                "verification_level": "bronze",
                "raw_text": " ".join(filter(None, [
                    title,
                    article.get("description") or "",
                    article.get("content") or "",
                ])),
                "source_url": url,
                "company_name": None,  # the extraction model fills this in
                "ticker": None,        # the extraction model fills this in
                "filing_date": (article.get("publishedAt") or "")[:10],
            })

        print(f"NewsAPI: {len(results)} articles pulled")
        return results

    except Exception as e:
        print(f"NewsAPI error: {e}")
        return []
