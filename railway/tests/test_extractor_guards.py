"""Fast regression tests for autonomous evidence guardrails."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Unit tests exercise pure guardrails and do not create an API client.
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

from extractor import _quote_is_supported
from source_registry import discovery_terms
from sources.press_releases import _items


class EvidenceGuardTests(unittest.TestCase):
    def test_quote_must_be_in_source(self):
        source = "The company said automation was a stated reason for the workforce reduction."
        self.assertTrue(_quote_is_supported("automation was a stated reason", source))
        self.assertFalse(_quote_is_supported("AI replaced 10,000 workers", source))

    def test_discovery_vocab_covers_common_layoff_language(self):
        terms = set(discovery_terms())
        self.assertTrue({"redundancy", "staff cuts", "downsizing", "RIF"}.issubset(terms))

    def test_official_feed_parser_handles_rss_link_and_summary(self):
        rss = b"""<rss><channel><item><title>Workforce reduction</title><link>https://example.test/release</link><description>Company announces job cuts.</description><pubDate>Tue, 14 Jul 2026 10:00:00 +0000</pubDate></item></channel></rss>"""
        self.assertEqual(list(_items(rss)), [("Workforce reduction", "https://example.test/release", "Company announces job cuts.", "Tue, 14 Jul 2026 10:00:00 +0000")])


if __name__ == "__main__":
    unittest.main()
