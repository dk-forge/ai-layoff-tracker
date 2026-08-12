"""The company watchlist must actually query the companies.

WHAT THIS GUARDS (2026-08-12). `sources.newsapi.pull_news_articles` took a
`queries` argument, documented it as the company-watchlist's override, and then
looped over `DISCOVERY_QUERIES + _segment_queries_for_now()` regardless. So the
watchlist's entire premise - a company-TARGETED query, because "the broad daily
net misses cuts it doesn't name, that's exactly how HP/Intel slipped through" -
never reached the API. Every run re-pulled the same broad set the twice-daily
cron had already pulled, once per 20-company chunk, and paid to re-extract it:
run 31512613030 spent $0.0301 over 112 model calls and stored nothing.

The failure was invisible because the log line printed the DEFAULT query count
whatever the loop had done, so "6 queries" appeared under a call that had asked
for twenty. Both properties are asserted here: the queries have to be sent, and
the log has to report what was sent.

The third assertion is the budget. One query per company meets a key that
allows 100 requests/day for the whole tracker, 6 of which the cron needs for
the primary AI-attribution channel. An unbounded company sweep is not a big
sweep, it is an outage of the news path.
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Stub only `requests` (never a sources.* module — see
# tests/test_warn_generic_drift.py for why faking those hides real breakage).
if "requests" not in sys.modules:
    _stub = types.ModuleType("requests")
    _stub.RequestException = Exception
    _stub.get = lambda *a, **k: None
    sys.modules["requests"] = _stub


class _Resp:
    status_code = 200

    def __init__(self, articles):
        self._articles = articles

    def json(self):
        return {"status": "ok", "articles": self._articles}


def _fake_get(sent):
    def _get(url, params=None, timeout=None):
        sent.append((params or {}).get("q"))
        return _Resp([{"title": "T", "url": f"https://x/{len(sent)}",
                       "description": "d", "content": "c",
                       "source": {"name": "Reuters"},
                       "publishedAt": "2026-08-01T00:00:00Z"}])
    return _get


class CallerQueriesAreSentTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"NEWSAPI_KEY": "k"}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def _pull(self, **kwargs):
        from sources import newsapi
        sent = []
        with mock.patch.object(newsapi.requests, "get", _fake_get(sent)):
            newsapi.pull_news_articles(**kwargs)
        return sent, newsapi

    def test_caller_supplied_queries_are_the_ones_sent(self):
        wanted = ['"Acme Corp" AND layoffs', '"Beta Ltd" AND layoffs']
        sent, _ = self._pull(days_back=28, queries=wanted)
        self.assertEqual(sent, wanted,
                         "the watchlist's company-targeted queries must reach "
                         "the API; sending the broad discovery set instead is "
                         "the bug this test exists for")

    def test_default_set_is_unchanged_when_no_queries_are_passed(self):
        from sources import newsapi
        sent, _ = self._pull(days_back=4)
        self.assertEqual(sent[:len(newsapi.DISCOVERY_QUERIES)],
                         list(newsapi.DISCOVERY_QUERIES),
                         "the daily cron path must be byte-identical")
        self.assertGreater(len(sent), len(newsapi.DISCOVERY_QUERIES),
                           "the rotating segment queries must still be added")

    def test_the_log_reports_what_was_sent_not_the_default_count(self):
        sent, newsapi = self._pull(days_back=28, queries=['"A" AND layoffs'])
        self.assertEqual(newsapi.pull_news_articles.requests_sent, len(sent))
        self.assertEqual(newsapi.pull_news_articles.requests_sent, 1)

    def test_budget_caps_the_requests_and_says_how_many_were_unsent(self):
        wanted = [f'"C{i}" AND layoffs' for i in range(25)]
        with mock.patch.dict(os.environ, {"NEWSAPI_MAX_REQUESTS": "10"}):
            sent, newsapi = self._pull(days_back=28, queries=wanted)
        self.assertEqual(len(sent), 10)
        self.assertEqual(newsapi.pull_news_articles.budget_truncated, 15,
                         "unsent queries are deferred work and must be counted, "
                         "not silently dropped into a clean-looking zero")


if __name__ == "__main__":
    unittest.main()
