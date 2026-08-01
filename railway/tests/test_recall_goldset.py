"""Offline guards for the recall floor — the check that had to be able to fail.

`recall_precision.py` printed a recall percentage for months and returned 0
whatever it printed, so a regression could not redden anything. These tests
protect the three properties that fix costs nothing unless they hold:

  1. the floor actually FAILS when the number drops
  2. missing / stale / unreachable resolve to UNKNOWN, never to a pass
  3. the committed manifest and the committed measurement still agree with each
     other and with the bound the invariant reads

They need no network and no keys.
"""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity
import recall_goldset
from recall_goldset import FAIL, PASS, UNKNOWN


def _stamp(days_ago=0):
    return (datetime.now(timezone.utc)
            - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _measurement(matched=24, total=57, unreachable=0, days_ago=0, floor=None):
    return {"reference_events": total, "matched": matched, "missed": total - matched,
            "unreachable": unreachable, "measured_at": _stamp(days_ago),
            "matched_floor": recall_goldset.MATCHED_FLOOR if floor is None else floor,
            "lost_since_adjudication": [], "missed_events": [],
            "candidates_needing_adjudication": []}


class WilsonIntervalTests(unittest.TestCase):
    def test_a_perfect_sample_is_not_certainty(self):
        # 53/53 must not read as "100%, no doubt". This is the whole reason the
        # module reports an interval rather than a percentage.
        p, lo, hi = recall_goldset.wilson(53, 53)
        self.assertEqual(p, 1.0)
        self.assertEqual(hi, 1.0)
        self.assertLess(lo, 0.95)
        self.assertGreater(lo, 0.90)

    def test_a_small_sample_is_a_wide_interval(self):
        _, lo_small, hi_small = recall_goldset.wilson(6, 12)
        _, lo_big, hi_big = recall_goldset.wilson(60, 120)
        self.assertGreater(hi_small - lo_small, (hi_big - lo_big) * 2)

    def test_an_empty_sample_has_no_rate(self):
        # Not 0.0 — a caller would render that as a measured zero.
        self.assertEqual(recall_goldset.wilson(0, 0), (None, None, None))
        self.assertIn("no sample", recall_goldset.format_interval(0, 0))

    def test_the_measured_figure_reproduces(self):
        _, lo, hi = recall_goldset.wilson(24, 57)
        self.assertAlmostEqual(lo, 0.302, places=2)
        self.assertAlmostEqual(hi, 0.550, places=2)


class NameMatchingTests(unittest.TestCase):
    """The live `company=` filter is a substring LIKE. Every pair below was
    returned by it on 2026-08-01 and would have been scored as a match by a
    containment test."""

    def test_prefix_not_substring(self):
        for alias, other in (("Xperi", "Experian"),
                             ("Gemini Space Station", "Capgemini"),
                             ("Sight Sciences", "Insight Behavioral Consulting"),
                             ("KALA BIO", "Hiiu Kalatoostus"),
                             ("SOBR Safe", "Sobrinca, Brinquedos e Cia"),
                             ("GoPro", "Belgoprocess")):
            self.assertFalse(recall_goldset.name_matches(alias, other),
                             f"{alias!r} must not match {other!r}")

    def test_real_employer_names_still_match(self):
        for alias, row in (("Alector", "Alector LLC"),
                           ("International Paper", "International Paper Company(W. Chaplin)"),
                           ("Goodyear", "The Goodyear Tire & Rubber Company"),
                           ("FedEx", "FedEx Corporation Facility (Ft. Worth)"),
                           ("Coinbase", "Coinbase"),
                           ("Hyster-Yale", "Hyster-Yale Materials Handling, Inc.")):
            self.assertTrue(recall_goldset.name_matches(alias, row),
                            f"{alias!r} must match {row!r}")


class FloorJudgementTests(unittest.TestCase):
    def test_the_floor_can_fail(self):
        state, detail = recall_goldset.judge(
            _measurement(matched=recall_goldset.MATCHED_FLOOR - 1))
        self.assertEqual(state, FAIL)
        self.assertIn("floor", detail)

    def test_at_the_floor_it_passes(self):
        state, _ = recall_goldset.judge(_measurement(matched=recall_goldset.MATCHED_FLOOR))
        self.assertEqual(state, PASS)

    def test_a_missing_measurement_is_unknown_not_pass(self):
        state, detail = recall_goldset.judge(None)
        self.assertEqual(state, UNKNOWN)
        self.assertIn("UNMEASURED", detail)

    def test_a_stale_measurement_is_unknown_not_pass(self):
        state, detail = recall_goldset.judge(
            _measurement(days_ago=recall_goldset.MAX_MEASUREMENT_AGE_DAYS + 1))
        self.assertEqual(state, UNKNOWN)
        self.assertIn("days old", detail)

    def test_a_host_outage_cannot_manufacture_a_regression(self):
        # The 2026-07-31 lesson, applied here: if the site was unreachable for
        # much of the set, the answer is "we do not know", not "recall fell".
        state, detail = recall_goldset.judge(
            _measurement(matched=0, unreachable=recall_goldset.UNREACHABLE_CEILING + 1))
        self.assertEqual(state, UNKNOWN)
        self.assertIn("NOT a recall regression", detail)

    def test_a_few_unreachable_still_judges(self):
        state, _ = recall_goldset.judge(
            _measurement(unreachable=recall_goldset.UNREACHABLE_CEILING))
        self.assertEqual(state, PASS)


class MeasurementContractTests(unittest.TestCase):
    def test_the_numerator_only_counts_editor_confirmed_events(self):
        """A machine must not promote its own recall.

        The loose alias/window rule scored 31 of 57 against the editor's 24 on
        2026-08-01 — it accepted a Georgia WARN filed ten weeks before the
        announcement it was meant to represent. So a row that satisfies the rule
        for a NOT-matched event is reported for adjudication, never counted.
        """
        manifest = {"reference_events": [
            {"reference_row_id": "confirmed", "filer": "Acme", "filing_date": "2026-01-01",
             "stated_job_count": 10, "employer_aliases": ["Acme"],
             "excluded_name_prefixes": [], "match_window": ["2025-10-01", "2026-09-01"],
             "match_decision": "matched", "rejected_candidate_event_ids": []},
            {"reference_row_id": "rejected-before", "filer": "Beta", "filing_date": "2026-01-01",
             "stated_job_count": 10, "employer_aliases": ["Beta"],
             "excluded_name_prefixes": [], "match_window": ["2025-10-01", "2026-09-01"],
             "match_decision": "not_matched", "rejected_candidate_event_ids": [99]},
        ]}

        def fetch(url, timeout=30):
            name = "Acme" if "Acme" in url else "Beta"
            eid = 1 if name == "Acme" else 99
            return json.dumps({"data": [{"id": eid, "event_id": eid, "company_name": name,
                                         "layoff_date": "2026-02-01"}]}).encode()

        out = recall_goldset.measure(fetch=fetch, manifest=manifest, sleep=lambda _s: None)
        self.assertEqual(out["matched"], 1)
        self.assertEqual(out["missed"], 1)
        # The Beta row was already looked at and rejected, so it stays silent
        # rather than reappearing as a candidate every single week.
        self.assertEqual(out["candidates_needing_adjudication"], [])

    def test_a_new_row_for_a_missed_event_is_flagged_not_counted(self):
        manifest = {"reference_events": [
            {"reference_row_id": "missed", "filer": "Beta", "filing_date": "2026-01-01",
             "stated_job_count": 10, "employer_aliases": ["Beta"],
             "excluded_name_prefixes": [], "match_window": ["2025-10-01", "2026-09-01"],
             "match_decision": "not_matched", "rejected_candidate_event_ids": []},
        ]}

        def fetch(url, timeout=30):
            return json.dumps({"data": [{"id": 7, "event_id": 7, "company_name": "Beta",
                                         "layoff_date": "2026-02-01"}]}).encode()

        out = recall_goldset.measure(fetch=fetch, manifest=manifest, sleep=lambda _s: None)
        self.assertEqual(out["matched"], 0)
        self.assertEqual(len(out["candidates_needing_adjudication"]), 1)
        self.assertEqual(out["candidates_needing_adjudication"][0]["new_tracker_event_ids"], [7])

    def test_a_failed_lookup_is_unreachable_not_a_miss(self):
        manifest = {"reference_events": [
            {"reference_row_id": "x", "filer": "Acme", "filing_date": "2026-01-01",
             "stated_job_count": 10, "employer_aliases": ["Acme"],
             "excluded_name_prefixes": [], "match_window": ["2025-10-01", "2026-09-01"],
             "match_decision": "matched", "rejected_candidate_event_ids": []},
        ]}

        def dead(url, timeout=30):
            raise OSError("Network is unreachable")

        out = recall_goldset.measure(fetch=dead, manifest=manifest, sleep=lambda _s: None)
        self.assertEqual(out["unreachable"], 1)
        self.assertEqual(out["matched"], 0)
        self.assertEqual(out["missed"], 0)


class CommittedArtefactTests(unittest.TestCase):
    """The manifest and the measurement are committed, so they can drift. These
    assert they have not."""

    def setUp(self):
        self.manifest = recall_goldset.load_manifest()
        self.measurement = recall_goldset.load_measurement()

    def test_the_manifest_is_a_complete_adjudicated_set(self):
        events = self.manifest["reference_events"]
        self.assertEqual(len(events), 57)
        for e in events:
            self.assertIn(e["match_decision"],
                          ("matched", "not_matched", "ambiguous_not_matched"))
            self.assertTrue(e["match_notes"])
            self.assertTrue(e["count_evidence"])
            self.assertIsInstance(e["stated_job_count"], int)
            self.assertTrue(e["official_source_url"].startswith(
                "https://www.sec.gov/Archives/edgar/data/"))
            self.assertIn("2.05", e["sec_items"])
            self.assertTrue(e["employer_aliases"])

    def test_the_manifest_says_what_it_cannot_support(self):
        # A future session cannot judge 42% without this, and the number is
        # exactly the kind that gets quoted out of context.
        self.assertIn("n=57", self.manifest["what_it_can_and_cannot_support"])
        self.assertIn("never be quoted", self.manifest["what_it_can_and_cannot_support"])
        self.assertIn("NOT independent of the tracker's DESIGN",
                      self.manifest["why_this_is_independent"])

    def test_the_manifest_is_not_published_as_a_public_benchmark(self):
        # docs/RECALL_BENCHMARK_PROTOCOL.md reserves /benchmarks/recall for a
        # sample that has been through three distinct reviewers. This one has
        # not, and must not be posted there.
        self.assertEqual(self.manifest["publication_status"],
                         "internal_regression_reference_not_published_to_benchmarks_recall")
        self.assertNotIn("sample_recall", self.manifest)

    def test_no_competitor_or_aggregator_source(self):
        blob = json.dumps(self.manifest).lower()
        for banned in ("layoffs.fyi", "trueup", "challenger", "warntracker", "intellizence"):
            self.assertNotIn(banned, blob)

    def test_the_committed_measurement_matches_the_manifest(self):
        self.assertIsNotNone(self.measurement, "railway/recall_measurement.json is missing")
        self.assertEqual(self.measurement["reference_events"],
                         len(self.manifest["reference_events"]))
        confirmed = sum(1 for e in self.manifest["reference_events"]
                        if e["match_decision"] == "matched")
        # The committed measurement may lag the manifest by real change, but it
        # can never claim MORE than the editor confirmed.
        self.assertLessEqual(self.measurement["matched"], confirmed)
        self.assertEqual(self.measurement["matched_floor"], recall_goldset.MATCHED_FLOOR)

    def test_the_floor_leaves_headroom_but_is_not_a_rubber_stamp(self):
        confirmed = sum(1 for e in self.manifest["reference_events"]
                        if e["match_decision"] == "matched")
        self.assertLess(recall_goldset.MATCHED_FLOOR, confirmed,
                        "a floor at or above the measurement fires on the first run")
        self.assertGreater(recall_goldset.MATCHED_FLOOR, confirmed * 0.6,
                           "a floor this far below the measurement is not a tripwire")


class InvariantWiringTests(unittest.TestCase):
    def test_the_registry_carries_the_recall_floor(self):
        keys = [i.key for i in data_integrity.INVARIANTS]
        self.assertIn("recall_floor", keys)

    def test_it_does_not_touch_the_network(self):
        # ops_status runs at the top of every session against a host that has
        # 504'd; the recall check must not add ~60 requests to that path.
        inv = next(i for i in data_integrity.INVARIANTS if i.key == "recall_floor")
        self.assertFalse(inv.reads_live_data)

        def explode(url, timeout):
            raise AssertionError("recall_floor must not query the live API")

        ctx = data_integrity.Ctx(explode, 5, "cb")
        self.assertIn(inv.run(ctx).state, (PASS, FAIL, UNKNOWN))

    def test_a_missing_measurement_reads_unknown_and_pending(self):
        inv = data_integrity.RecallFloorInvariant(
            measurement_path=Path("/nonexistent/recall_measurement.json"))
        result = inv.run(data_integrity.Ctx(lambda u, t: b"{}", 5, "cb"))
        self.assertEqual(result.state, UNKNOWN)
        self.assertTrue(result.pending)


if __name__ == "__main__":
    unittest.main()
