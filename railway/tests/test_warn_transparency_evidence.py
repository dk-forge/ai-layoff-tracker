"""Offline tests for the stage-1 WARN compliance-evidence builder.

Fixture rows only — no network, no API, no LLM. These tests pin the two
behaviours the register's legal posture depends on: gaps are pure arithmetic
on official fields, and nothing the builder emits is ever a verdict.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warn_transparency_evidence as wte


def row(**overrides):
    base = {
        "state": "CA",
        "employer": "Acme Corp",
        "notice_date": "2026-01-05",
        "effective_date": "2026-03-06",
        "source_name": "CA WARN notice",
        "source_url": "https://edd.ca.gov/en/jobs_and_training/warn/",
    }
    base.update(overrides)
    return base


class NoticeGapArithmeticTests(unittest.TestCase):
    def test_gap_is_plain_calendar_subtraction(self):
        self.assertEqual(wte.notice_gap_days("2026-01-05", "2026-03-06"), 60)
        self.assertEqual(wte.notice_gap_days("2026-01-01", "2026-02-28"), 58)
        self.assertEqual(wte.notice_gap_days("2026-01-01", "2026-01-01"), 0)

    def test_leap_day_counts_like_any_other_day(self):
        self.assertEqual(wte.notice_gap_days("2028-02-01", "2028-03-01"), 29)

    def test_missing_or_invalid_dates_yield_none_never_a_guess(self):
        for bad in ("", None, "TBD", "03/06/2026", "2026-1-5",
                    "2026-13-01", "2026-02-30", "March 6, 2026"):
            self.assertIsNone(wte.notice_gap_days(bad, "2026-03-06"), bad)
            self.assertIsNone(wte.notice_gap_days("2026-01-05", bad), bad)

    def test_dates_outside_plausible_warn_window_are_invalid(self):
        self.assertIsNone(wte.notice_gap_days("2014-12-31", "2015-03-01"))
        self.assertIsNone(wte.notice_gap_days("2028-12-01", "2029-01-30"))

    def test_negative_gap_is_returned_for_the_caller_to_exclude(self):
        self.assertEqual(wte.notice_gap_days("2026-03-06", "2026-01-05"), -60)


class ObservationLabelTests(unittest.TestCase):
    def test_under_60_days_is_a_candidate_not_a_finding(self):
        out = wte.build_compliance_evidence([
            row(notice_date="2026-01-05", effective_date="2026-02-20")])
        c = out["candidates"][0]
        self.assertEqual(c["notice_gap_days"], 46)
        self.assertEqual(c["observation"], "short_notice_candidate")

    def test_exactly_60_days_is_not_short_notice(self):
        # Matches the register writer: >= 60 takes the 60-plus label.
        out = wte.build_compliance_evidence([
            row(notice_date="2026-01-05", effective_date="2026-03-06")])
        c = out["candidates"][0]
        self.assertEqual(c["notice_gap_days"], 60)
        self.assertEqual(c["observation"], "notice_recorded_60_plus_days")

    def test_no_output_ever_contains_a_verdict_word(self):
        out = wte.build_compliance_evidence([
            row(effective_date="2026-01-10"),  # 5-day gap
            row(employer="Beta LLC")])
        import json
        flat = json.dumps(out["candidates"]).lower()
        for banned in ("violation", "non-compliant", "noncompliant",
                       "illegal", "unlawful"):
            self.assertNotIn(banned, flat)

    def test_statutory_context_travels_with_every_candidate(self):
        out = wte.build_compliance_evidence([
            row(), row(employer="Beta LLC", effective_date="2026-01-20")])
        for c in out["candidates"]:
            self.assertIn("60 days", c["statutory_context"])
            self.assertIn("exception", c["statutory_context"])
            self.assertIn("not a verdict", c["statutory_context"])
        methodology = out["methodology"]["statutory_context"]
        self.assertIn("faltering_company", methodology["recognized_exceptions"])
        self.assertIn("unforeseeable_business_circumstances",
                      methodology["recognized_exceptions"])
        self.assertIn("natural_disaster", methodology["recognized_exceptions"])


class ExclusionTests(unittest.TestCase):
    def test_missing_dates_are_excluded_and_counted_never_imputed(self):
        out = wte.build_compliance_evidence([
            row(notice_date=""), row(effective_date=None), row()])
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(out["excluded"]["missing_dates"], 2)

    def test_unparseable_dates_are_excluded_not_reinterpreted(self):
        out = wte.build_compliance_evidence([
            row(notice_date="01/05/2026"), row(effective_date="TBD")])
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["excluded"]["invalid_dates"], 2)

    def test_effective_before_notice_is_excluded_not_short_notice(self):
        out = wte.build_compliance_evidence([
            row(notice_date="2026-03-06", effective_date="2026-01-05")])
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["excluded"]["effective_precedes_notice"], 1)

    def test_rows_without_an_official_source_url_are_excluded(self):
        out = wte.build_compliance_evidence([row(source_url="")])
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["excluded"]["missing_source_url"], 1)


class AmendedNoticeTests(unittest.TestCase):
    def test_amendments_collapse_to_the_earliest_notice_date(self):
        original = row(notice_date="2026-01-02",
                       source_url="https://example.gov/warn/original")
        revised = row(notice_date="2026-01-20",
                      source_url="https://example.gov/warn/revised")
        out = wte.build_compliance_evidence([revised, original])
        self.assertEqual(len(out["candidates"]), 1)
        c = out["candidates"][0]
        self.assertEqual(c["notice_date"], "2026-01-02")
        self.assertEqual(c["notice_gap_days"],
                         wte.notice_gap_days("2026-01-02", "2026-03-06"))
        # Evidence cites the filing that recorded the governing earliest date.
        self.assertEqual(c["evidence"]["source_url"],
                         "https://example.gov/warn/original")
        self.assertEqual(c["amended_notice_dates"],
                         ["2026-01-02", "2026-01-20"])

    def test_earliest_notice_date_ignores_invalid_recordings(self):
        self.assertEqual(
            wte.earliest_notice_date(["TBD", "2026-01-20", "2026-01-02"]),
            "2026-01-02")
        self.assertIsNone(wte.earliest_notice_date(["", "n/a"]))

    def test_distinct_effective_dates_stay_separate_candidates(self):
        # Phased layoffs are separate notices, not amendments of each other.
        out = wte.build_compliance_evidence([
            row(effective_date="2026-03-06"),
            row(effective_date="2026-04-10")])
        self.assertEqual(len(out["candidates"]), 2)

    def test_grouping_is_case_and_whitespace_insensitive_on_employer(self):
        out = wte.build_compliance_evidence([
            row(employer="Acme  Corp", notice_date="2026-01-02"),
            row(employer="ACME CORP", notice_date="2026-01-20")])
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(out["candidates"][0]["notice_date"], "2026-01-02")


class OutputShapeTests(unittest.TestCase):
    def test_candidates_sort_deterministically(self):
        out = wte.build_compliance_evidence([
            row(state="TX", employer="Zeta"),
            row(state="CA", employer="beta"),
            row(state="CA", employer="Alpha")])
        keys = [(c["state"], c["employer"]) for c in out["candidates"]]
        self.assertEqual(keys, [("CA", "Alpha"), ("CA", "beta"),
                                ("TX", "Zeta")])

    def test_evidence_always_carries_the_official_source(self):
        out = wte.build_compliance_evidence([row()])
        ev = out["candidates"][0]["evidence"]
        self.assertTrue(ev["source_url"].startswith("https://"))
        self.assertEqual(ev["source_name"], "CA WARN notice")

    def test_empty_input_builds_an_empty_but_complete_report(self):
        out = wte.build_compliance_evidence([])
        self.assertEqual(out["candidates"], [])
        self.assertEqual(sorted(out["excluded"]),
                         ["effective_precedes_notice", "invalid_dates",
                          "missing_dates", "missing_source_url"])
        self.assertIn("statutory_context", out["methodology"])


if __name__ == "__main__":
    unittest.main()
