"""Guards for the count-scaled dedup window.

The flat 120-day cluster window let an identical large figure re-reported months
apart escape the deep scan entirely (VW "50,000" appeared twice, 125 days apart
— 5 days past the window — so the model never got to judge it). The window is
now widened ONLY for near-identical material counts; this test pins both the
widening and its conservatism (dissimilar or tiny counts keep the tight window).
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

import dedupe_llm as d


class PairWindowTest(unittest.TestCase):
    def test_identical_large_counts_get_wide_window(self):
        # The VW case: two identical 50,000 figures.
        self.assertEqual(d.pair_window_days(50000, 50000), d.WIDE_WINDOW_DAYS)

    def test_near_identical_large_counts_get_wide_window(self):
        # 9,600 vs 10,000 -> 96% similar, both material.
        self.assertEqual(d.pair_window_days(9600, 10000), d.WIDE_WINDOW_DAYS)

    def test_exact_small_counts_get_wide_window(self):
        # Commonwealth Bank 300 in Jan and again in July (196 days): exact match
        # at a material size (>=50) must cluster so the model can judge it.
        self.assertEqual(d.pair_window_days(300, 300), d.WIDE_WINDOW_DAYS)

    def test_micro_exact_counts_keep_tight_window(self):
        # Below the 100-worker floor, exact tiny counts stay tight (noise).
        self.assertEqual(d.pair_window_days(50, 50), d.WINDOW_DAYS)

    def test_dissimilar_counts_keep_tight_window(self):
        # 4,000 vs 5,000 -> 80% similar: clusterable, but not "obviously the
        # same figure", so no widening.
        self.assertEqual(d.pair_window_days(4000, 5000), d.WINDOW_DAYS)

    def test_zero_hi_is_safe(self):
        self.assertEqual(d.pair_window_days(0, 0), d.WINDOW_DAYS)

    def test_vw_pair_now_within_window(self):
        gap = d.days_between("2026-03-10", "2026-07-13")
        self.assertEqual(gap, 125)
        self.assertLessEqual(gap, d.pair_window_days(50000, 50000))
        # ...and would NOT have clustered under the old flat window.
        self.assertGreater(gap, d.WINDOW_DAYS)


class CandidateClusterWindowTest(unittest.TestCase):
    """End-to-end through candidate_clusters: the VW pair clusters now."""

    def _row(self, rid, count, dt, name="Volkswagen Group"):
        return {"id": rid, "company_name": name, "job_count": count,
                "layoff_date": dt, "source_name": "x", "source_type": "news"}

    def test_identical_large_pair_125_days_clusters(self):
        rows = [self._row(1, 50000, "2026-03-10"), self._row(2, 50000, "2026-07-13")]
        clusters = d.candidate_clusters(rows)
        self.assertEqual(len(clusters), 1)
        self.assertEqual({r["id"] for r in clusters[0]}, {1, 2})

    def test_identical_small_pair_125_days_does_not_cluster(self):
        rows = [self._row(1, 50, "2026-03-10", "Tiny Co"),
                self._row(2, 50, "2026-07-13", "Tiny Co")]
        self.assertEqual(d.candidate_clusters(rows), [])


if __name__ == "__main__":
    unittest.main()
