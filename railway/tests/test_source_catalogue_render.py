"""The public publisher catalogue must match the committed research.

A catalogue edited but never rendered leaves a stale table on a public page
saying we hold something we do not, or omitting a refusal we measured. That
class of drift is exactly what the generated country-sources table exists to
prevent, so the catalogue gets the same guard: render it fresh and compare.
"""
import json
import sys
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

import generate_source_catalogue as gen  # noqa: E402


class CatalogueRenderTests(unittest.TestCase):
    def test_the_committed_partial_matches_a_fresh_render(self):
        data = json.loads(gen.SRC.read_text(encoding="utf-8"))
        self.assertTrue(gen.OUT.exists(),
                        "the catalogue partial has never been generated")
        self.assertEqual(gen.OUT.read_text(encoding="utf-8"), gen.render(data),
                         "railway/data/source_catalogue.json changed without "
                         "re-running generate_source_catalogue.py")

    def test_the_counts_block_matches_the_rows(self):
        data = json.loads(gen.SRC.read_text(encoding="utf-8"))
        rows = data["sources"]
        self.assertEqual(data["counts"]["total"], len(rows))
        for status in ("wired", "researched", "refused"):
            self.assertEqual(data["counts"][status],
                             sum(1 for r in rows if r["status"] == status),
                             f"the {status} count does not match the rows")

    def test_no_competitor_tally_product_is_listed_as_a_publisher(self):
        """The standing rule: a layoff-tally product is never a source, and
        never a row on a public page of ours either."""
        sys.path.insert(0, str(RAILWAY))
        from sources.local_news import is_aggregator
        data = json.loads(gen.SRC.read_text(encoding="utf-8"))
        for r in data["sources"]:
            with self.subTest(row=r["publisher"]):
                self.assertFalse(
                    is_aggregator(r.get("feed_url", ""), r["publisher"],
                                  r["publisher"]))

    def test_the_rendered_page_escapes_publisher_text(self):
        html = gen.render({"measured": "2026-08-14",
                           "counts": {"total": 1, "wired": 1, "researched": 0,
                                      "refused": 0},
                           "sources": [{"country": "Testland",
                                        "publisher": '<script>x</script>',
                                        "language": "en", "status": "wired",
                                        "evidence": "", "feed_url": ""}]})
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
