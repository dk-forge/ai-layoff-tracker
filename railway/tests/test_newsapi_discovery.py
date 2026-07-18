"""Guards for the bounded, duplicate-safe NewsAPI discovery expansion."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("requests", SimpleNamespace())

from sources import newsapi


class _Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"status": "ok", "articles": []}

    def json(self):
        return self._payload


class NewsApiDiscoveryTests(unittest.TestCase):
    def test_two_queries_deduplicate_urls_without_relaxing_article_shape(self):
        queries = []
        article = {
            "title": "Example announces job cuts",
            "url": "https://example.test/article",
            "description": "A source-linked description",
            "content": "Source content",
            "publishedAt": "2026-07-18T00:00:00Z",
            "source": {"name": "Example News"},
        }

        def get(_url, *, params, timeout):
            queries.append(params["q"])
            return _Response(payload={"status": "ok", "articles": [article]})

        with patch.dict(os.environ, {"NEWSAPI_KEY": "test-key"}, clear=False), \
             patch.object(newsapi.requests, "get", side_effect=get, create=True):
            rows = newsapi.pull_news_articles(days_back=2)

        self.assertEqual(len(queries), len(newsapi.DISCOVERY_QUERIES))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_url"], article["url"])
        self.assertEqual(rows[0]["verification_level"], "bronze")

    def test_rate_limit_stops_remaining_queries(self):
        with patch.dict(os.environ, {"NEWSAPI_KEY": "test-key"}, clear=False), \
             patch.object(newsapi.requests, "get", return_value=_Response(status_code=429), create=True) as get:
            self.assertEqual(newsapi.pull_news_articles(), [])
        self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
