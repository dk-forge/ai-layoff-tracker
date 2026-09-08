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
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import dedupe_llm as d


class PairWindowTest(unittest.TestCase):
    def test_identical_large_counts_get_wide_window(self):
        # The VW case: two identical 50,000 figures. Exact matches now get the
        # widest (EXACT) window so a cumulative figure restated years apart is
        # still adjudicated by the model.
        self.assertEqual(d.pair_window_days(50000, 50000), d.EXACT_WINDOW_DAYS)

    def test_near_identical_large_counts_get_wide_window(self):
        # 9,600 vs 10,000 -> 96% similar, both material.
        self.assertEqual(d.pair_window_days(9600, 10000), d.WIDE_WINDOW_DAYS)

    def test_exact_small_counts_get_wide_window(self):
        # Commonwealth Bank 300 in Jan and again in July (196 days): exact match
        # at a material size (>=100) must cluster so the model can judge it.
        self.assertEqual(d.pair_window_days(300, 300), d.EXACT_WINDOW_DAYS)

    def test_micro_exact_counts_keep_tight_window(self):
        # Below the 100-worker floor, exact tiny counts stay tight (noise).
        self.assertEqual(d.pair_window_days(50, 50), d.WINDOW_DAYS)

    def test_near_identical_moderate_counts_get_wide_window(self):
        # 420 vs 430 -> ~98% similar, mid-size: a same-event re-report rounded
        # differently, months apart. Must get the wide window (floor lowered
        # from 1,000 to 250) so the model sees the pair instead of it slipping
        # past the tight 120-day window.
        self.assertEqual(d.pair_window_days(420, 430), d.WIDE_WINDOW_DAYS)

    def test_near_identical_below_floor_keeps_tight_window(self):
        # 200 vs 205 -> similar but below the 250 material floor: stays tight so
        # small-number churn does not over-merge distinct rounds.
        self.assertEqual(d.pair_window_days(200, 205), d.WINDOW_DAYS)

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

    def _row(self, rid, count, dt, name="Volkswagen Group", **overrides):
        row = {"id": rid, "company_name": name, "job_count": count,
               "layoff_date": dt, "source_name": "x", "source_type": "news",
               "source_url": "https://example.test/report", "country": ""}
        row.update(overrides)
        return row

    def test_identical_large_pair_125_days_clusters(self):
        rows = [self._row(1, 50000, "2026-03-10"), self._row(2, 50000, "2026-07-13")]
        clusters = d.candidate_clusters(rows)
        self.assertEqual(len(clusters), 1)
        self.assertEqual({r["id"] for r in clusters[0]}, {1, 2})

    def test_identical_small_pair_125_days_does_not_cluster(self):
        rows = [self._row(1, 50, "2026-03-10", "Tiny Co"),
                self._row(2, 50, "2026-07-13", "Tiny Co")]
        self.assertEqual(d.candidate_clusters(rows), [])

    def test_federal_monthly_rif_rows_never_cluster(self):
        """OPM rows are agency-month observations, not outlet re-reports."""
        rows = [
            self._row(177395, 16, "2026-04-01", "Treasury",
                      source_type="federal_rif", country="United States"),
            self._row(177083, 15, "2026-06-01", "Treasury",
                      source_type="federal_rif", country="United States"),
        ]
        self.assertEqual(d.candidate_clusters(rows), [])

    def test_specific_different_countries_never_cluster(self):
        """Dow Germany 110 and Dow Spain 138 are different facilities/events."""
        rows = [
            self._row(61050, 110, "2026-06-04", "Dow",
                      source_type="erm", country="Germany",
                      source_url="https://apps.eurofound.europa.eu/restructuring-events/detail/300539"),
            self._row(176859, 138, "2026-08-01", "Dow",
                      country="Spain", source_url="https://example.test/tarragona"),
        ]
        self.assertEqual(d.candidate_clusters(rows), [])

    def test_distinct_erm_factsheets_never_cluster(self):
        """Eurofound assigns one factsheet ID per restructuring event."""
        rows = [
            self._row(62020, 200, "2025-05-07", "Stellantis",
                      source_type="erm", country="Italy",
                      source_url="https://apps.eurofound.europa.eu/restructuring-events/detail/202770"),
            self._row(61941, 265, "2025-06-11", "Stellantis",
                      source_type="erm", country="Italy",
                      source_url="https://apps.eurofound.europa.eu/restructuring-events/detail/202925"),
        ]
        self.assertEqual(d.candidate_clusters(rows), [])

    def test_erm_and_news_for_same_plan_remain_eligible(self):
        rows = [
            self._row(1, 121, "2026-02-24", "Sprava zeleznic",
                      source_type="erm", country="Czechia",
                      source_url="https://apps.eurofound.europa.eu/restructuring-events/detail/204292"),
            self._row(2, 100, "2026-02-24", "Sprava zeleznic",
                      source_type="news", country="Czechia",
                      source_url="https://example.test/sprava-news"),
        ]
        clusters = d.candidate_clusters(rows)
        self.assertEqual([{r["id"] for r in group} for group in clusters], [{1, 2}])

    def test_unknown_geography_does_not_hide_a_possible_duplicate(self):
        rows = [
            self._row(1, 500, "2026-04-01", "Acme", country="Multiple countries"),
            self._row(2, 500, "2026-04-02", "Acme", country="France"),
        ]
        clusters = d.candidate_clusters(rows)
        self.assertEqual([{r["id"] for r in group} for group in clusters], [{1, 2}])

    def test_unknown_geography_cannot_bridge_two_specific_countries(self):
        rows = [
            self._row(1, 500, "2026-04-01", "Acme", country="Multiple countries"),
            self._row(2, 500, "2026-04-02", "Acme", country="France"),
            self._row(3, 500, "2026-04-03", "Acme", country="Germany"),
        ]
        clusters = d.candidate_clusters(rows)
        self.assertEqual(len(clusters), 1)
        self.assertNotEqual({r["id"] for r in clusters[0]}, {1, 2, 3})

    def test_fetch_never_requests_federal_rif_rows(self):
        requested = []
        def fake_api(path):
            requested.append(path)
            return {"data": [], "total": 0}
        with mock.patch.object(d, "api", fake_api):
            self.assertEqual(d.fetch_all(), [])
        self.assertEqual(len(requested), 1)
        self.assertNotIn("federal_rif", requested[0])


if __name__ == "__main__":
    unittest.main()
