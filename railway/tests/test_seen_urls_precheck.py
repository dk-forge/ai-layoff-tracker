"""The /seen-urls pre-check may only ever save money, never coverage.

Three invariants:
  1. Same-URL entries the server reports as seen are dropped (the saving).
  2. Any error - HTTP failure, exception, missing config - fails OPEN:
     every entry goes to the extractor exactly as before the optimization.
  3. Entries without a source_url are never dropped.
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.modules.setdefault("openai", types.ModuleType("openai"))
sys.modules["openai"].OpenAI = lambda *a, **k: None
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cron  # noqa: E402


def _entries():
    return [
        {"source_url": "https://x.test/a", "raw_text": "a"},
        {"source_url": "https://x.test/b", "raw_text": "b"},
        {"raw_text": "no-url entry"},
    ]


class SeenUrlsPrecheckTests(unittest.TestCase):
    def setUp(self):
        os.environ["WP_SITE_URL"] = "https://example.test/blog"
        os.environ["WP_API_KEY"] = "k"

    def test_drops_only_urls_the_server_has_seen(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"seen": ["https://x.test/a"]}
        fake = mock.Mock(); fake.post.return_value = resp
        with mock.patch.object(cron, "requests", fake):
            kept = cron.filter_already_seen(_entries())
        self.assertEqual([e.get("source_url") for e in kept],
                         ["https://x.test/b", None])

    def test_http_error_fails_open(self):
        fake = mock.Mock(); fake.post.return_value = mock.Mock(status_code=500)
        with mock.patch.object(cron, "requests", fake):
            kept = cron.filter_already_seen(_entries())
        self.assertEqual(len(kept), 3)

    def test_exception_fails_open(self):
        fake = mock.Mock(); fake.post.side_effect = OSError("net down")
        with mock.patch.object(cron, "requests", fake):
            kept = cron.filter_already_seen(_entries())
        self.assertEqual(len(kept), 3)

    def test_missing_config_fails_open(self):
        os.environ["WP_API_KEY"] = ""
        kept = cron.filter_already_seen(_entries())
        self.assertEqual(len(kept), 3)


if __name__ == "__main__":
    unittest.main()
