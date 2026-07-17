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
from enrich_context import query_params, rotating_page
from source_registry import MARKETS, coverage_manifest, discovery_terms
from sources.press_releases import _items
from sources.gdelt import _retry_delay
from sources.edgar import FORMS
from dedupe_llm import select_candidate_clusters


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

    def test_edgar_includes_foreign_issuer_disclosures(self):
        self.assertEqual(FORMS, ("8-K", "6-K"))

    def test_candidate_sources_are_not_presented_as_live_coverage(self):
        canada = MARKETS["CA"]
        self.assertEqual(canada.status, "discovery_only")
        self.assertIn("SEDAR+", canada.candidate_official_sources)
        self.assertNotIn("SEDAR+", canada.live_sources)
        manifest = {row["country"]: row for row in coverage_manifest()}
        self.assertEqual(manifest["CA"]["live_sources"],
                         ["worldwide news", "reviewed company IR feeds"])

    def test_dedupe_queue_rotates_smaller_clusters_instead_of_starving_them(self):
        clusters = [
            [{"id": 1, "job_count": 100, "layoff_date": "2026-01-01"},
             {"id": 2, "job_count": 110, "layoff_date": "2026-01-02"},
             {"id": 3, "job_count": 120, "layoff_date": "2026-01-03"}],
            [{"id": 10, "job_count": 20000, "layoff_date": "2026-02-01"},
             {"id": 11, "job_count": 20000, "layoff_date": "2026-03-06"}],
            [{"id": 20, "job_count": 300, "layoff_date": "2026-01-10"},
             {"id": 21, "job_count": 400, "layoff_date": "2026-01-11"}],
        ]
        selected = select_candidate_clusters(clusters, limit=2)
        selected_ids = {row["id"] for group in selected for row in group}
        # Exact-count repeat is always in the priority quarter of the queue.
        self.assertTrue({10, 11}.issubset(selected_ids))

    def test_context_priority_is_narrow_and_rotates_batches(self):
        params = query_params(5, "challenger_priority")
        self.assertEqual(params["country"], "United States")
        self.assertEqual(params["stage"], "announced")
        self.assertEqual(params["ai"], "1")
        self.assertEqual(params["sort"], "job_count")
        self.assertEqual(rotating_page(11, 5, today=__import__("datetime").date(2026, 1, 1)), 1)
        self.assertEqual(rotating_page(11, 5, today=__import__("datetime").date(2026, 1, 2)), 2)

    def test_gdelt_retry_delay_honors_retry_after_floor(self):
        response = SimpleNamespace(headers={"Retry-After": "90"})
        self.assertGreaterEqual(_retry_delay(response, 0), 90)


if __name__ == "__main__":
    unittest.main()
