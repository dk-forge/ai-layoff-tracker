"""
Pulls layoff news from credible outlets via NewsAPI.

Free (Developer) tier caveats that bite silently:
  - articles are delayed ~24 hours, so days_back=1 can return nothing;
    the default here is 4 days (covers the ~24h index delay + a weekend
    publish gap) and the deduplicator drops repeats
  - `content` is truncated to ~200 chars; title + description carry most signal
  - 100 requests/day
Production tier ($449/mo) removes the delay and truncation.
"""
import os
from datetime import datetime, timedelta, timezone

import requests

NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Every domain here is also in the GDELT trusted-source allowlist (sources/
# gdelt.py), so this is the SAME editorial bar applied to the NewsAPI channel —
# not a looser one. The additions matter for the "announced" tier specifically:
# the newswires (PR Newswire / Business Wire / GlobeNewswire) are the channel
# companies use to ANNOUNCE cuts (the same feed announcement-surveys monitor),
# and the trade/metro outlets catch mid-size US employers a general-news ranking
# buries. Widening `domains` costs no extra requests (same call count).
TRUSTED_DOMAINS = (
    "reuters.com,bloomberg.com,wsj.com,ft.com,apnews.com,"
    "techcrunch.com,cnbc.com,theguardian.com,cbsnews.com,npr.org,axios.com,"
    "bbc.com,theverge.com,arstechnica.com,fortune.com,businessinsider.com,"
    # newswires — the corporate-announcement channel
    "prnewswire.com,businesswire.com,globenewswire.com,"
    # national business / markets
    "marketwatch.com,forbes.com,"
    # regional & trade press (mid-size US employers)
    "bizjournals.com,crainsnewyork.com,geekwire.com,"
    "hrdive.com,retaildive.com,bankingdive.com,healthcaredive.com,ciodive.com,"
    "variety.com,deadline.com,"
    # global tech / startup press — the biggest remaining gap vs tech-event
    # trackers is non-US, non-English, and startup tech layoffs that mainstream
    # US outlets miss. All already vetted in the GDELT trusted list.
    "theinformation.com,techinasia.com,restofworld.org,inc42.com,"
    "theregister.com,calcalistech.com"
)

# Keep the general layoffs sweep separate from a targeted AI/automation sweep.
# Both remain discovery only: the extractor still needs source text that
# supports a count, date and causal classification before an event is posted.
# Two queries per twice-daily run are comfortably inside NewsAPI's 100/day
# developer allowance and recover announcement wording that a broad result
# ranking can otherwise bury.
DISCOVERY_QUERIES = (
    'layoffs OR "job cuts" OR "workforce reduction" OR "reduction in force"',
    '(layoffs OR "job cuts" OR "workforce reduction") AND (AI OR "artificial intelligence" OR automation)',
)

# Rotating narrow sweeps: broad ranking buries smaller state/industry/country
# announcements, so each run adds a couple of segment queries chosen by
# deterministic daily rotation (full matrix covered every ~9 days at
# twice-daily cadence). Two extra requests per run stays far inside the
# 100/day developer allowance. 0 disables.
SEGMENT_TERMS = (
    '"California"', '"New York"', '"Texas"', '"Washington state"', '"Florida"',
    '"Illinois"', '"Massachusetts"', '"Georgia"', '"Michigan"', '"Ohio"',
    '"manufacturing"', '"software"', '"banking"', '"retail"', '"healthcare"',
    '"automotive"', '"media"', '"logistics"', '"insurance"', '"telecom"',
    '"United Kingdom"', '"Canada"', '"India"', '"Germany"', '"Australia"',
    '"replaced by AI"', '"AI restructuring"', '"automation" AND "job cuts"',
    # global tech / startup segments — close the tech-event-tracker gap
    '"startup"', '"Israel"', '"Singapore"', '"tech company"',
)
SEGMENT_QUERIES_PER_RUN = max(0, min(6, int(os.environ.get("NEWSAPI_SEGMENT_QUERIES", "4"))))


def _segment_queries_for_now():
    if not SEGMENT_QUERIES_PER_RUN:
        return []
    now = datetime.now(timezone.utc)
    run_of_day = 0 if now.hour < 17 else 1
    start = ((now.timetuple().tm_yday * 2 + run_of_day) * SEGMENT_QUERIES_PER_RUN) % len(SEGMENT_TERMS)
    picked = [SEGMENT_TERMS[(start + i) % len(SEGMENT_TERMS)] for i in range(SEGMENT_QUERIES_PER_RUN)]
    return [f'(layoffs OR "job cuts" OR "workforce reduction") AND {term}' for term in picked]


def pull_news_articles(days_back=4, queries=None):
    """Pull layoff coverage from trusted outlets. `queries` overrides the
    standard discovery/segment set — the company-watchlist sweep passes
    company-targeted queries here to reuse all of this fetch/domain/shaping
    logic. When None, the daily broad discovery set is used."""
    api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        print("NewsAPI: no NEWSAPI_KEY found, skipping")
        return []

    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    results, seen_urls = [], set()
    for query in tuple(DISCOVERY_QUERIES) + tuple(_segment_queries_for_now()):
        params = {
            "q": query,
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
                # A quota/rate limit applies to the whole API key, so another
                # query in this run cannot safely recover it.
                print("NewsAPI: rate limited (429) — stopping this run")
                break
            data = resp.json()
            if data.get("status") != "ok":
                print(f"NewsAPI error response: {data.get('code')} — {data.get('message')}")
                continue
            for article in data.get("articles", []):
                title = article.get("title") or ""
                url = article.get("url") or ""
                # NewsAPI substitutes '[Removed]' placeholders for retracted items.
                if not url or url in seen_urls or title == "[Removed]":
                    continue
                seen_urls.add(url)
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
        except Exception as e:
            # Preserve a usable result from the other bounded query, but make
            # this source attempt visibly degraded to the cron caller.
            print(f"NewsAPI query error: {e}")
    print(f"NewsAPI: {len(results)} unique articles pulled across "
          f"{len(DISCOVERY_QUERIES) + len(_segment_queries_for_now())} queries (incl. rotating segments)")
    return results
