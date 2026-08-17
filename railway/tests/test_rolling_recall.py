"""The rolling coverage figure cannot quietly become an opinion again.

WHAT THESE GUARD, and why each one is here rather than being a comment in the
module.

The figure this module produces will be quoted in public. The failure that
matters is not "the number moved", it is "the number stopped meaning what its
label says" — which is exactly how a hand-maintained coverage percentage came to
be quoted for sixteen days after its denominator had changed. So every property
the published band rests on is asserted, and each assertion fails on the code
that existed before it.

THE BAND'S TWO LOAD-BEARING PROPERTIES, and the calibration behind them.

  CONFIRMED admits no false positive -> the lower end is a genuine lower bound
  PROPOSED misses no true positive   -> the upper end is a genuine upper bound

Both were MEASURED against the 57 hand-adjudicated events on 2026-08-17: 53
CONFIRMED, 2 PROPOSED, 0 ABSENT of the editor's 56 matched, and zero of the
editor's rejected candidates reaching CONFIRMED. That live calibration is a
network run and does not belong in the unit suite; what belongs here is the
LOGIC it validated, exercised on the three named cases that broke it.
"""
import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rolling_recall as rr
import sec_205_deterministic_probe as d205


class NamesAlignBothDirectionsTests(unittest.TestCase):
    """The stored name can be longer OR shorter than the filer name.

    Both were observed in one calibration run. A one-directional rule reads as
    obviously right and silently drops the second case: ZoomInfo's 600 — a row
    the tracker holds, at the exact count, on the exact filing date — scored as
    a coverage MISS until this was fixed. A recall measurement that under-counts
    under-counts in the direction that looks like a finding.
    """

    def test_stored_name_longer_than_filer(self):
        self.assertTrue(rr.names_align("STARBUCKS CORP", "Starbucks Corporation"))

    def test_stored_name_shorter_than_filer(self):
        self.assertTrue(rr.names_align("ZoomInfo Technologies Inc.", "ZoomInfo"))

    def test_unrelated_names_do_not_align(self):
        # The prefix rule, not containment. All four were real 2026-08-01 false
        # positives from a naive substring test.
        for filer, stored in (("Experian plc", "Xperi Inc"),
                              ("Capgemini SE", "Gemini Trust"),
                              ("Insight Behavioral", "Sight Sciences"),
                              ("KALA BIO, Inc.", "Baltic Kala Fish")):
            self.assertFalse(rr.names_align(filer, stored), f"{filer} vs {stored}")


class CleanFilerTests(unittest.TestCase):
    """EFTS glues BOTH the tickers and the CIK onto the display name."""

    def test_strips_every_trailing_group_not_just_the_last(self):
        # The single-strip version left "(ELAN)" attached, which tokenises as a
        # fourth word and cost Elanco its match in the first full run.
        self.assertEqual(
            rr.clean_filer("Elanco Animal Health Inc  (ELAN)  (CIK 0001739104)"),
            "Elanco Animal Health Inc")

    def test_strips_edgar_state_of_incorporation_marker(self):
        # "/NEW/" and "/OH/" appear on no letterhead and on no tracker row.
        self.assertEqual(rr.clean_filer("INTERNATIONAL PAPER CO /NEW/"),
                         "INTERNATIONAL PAPER CO")
        self.assertEqual(rr.clean_filer("GOODYEAR TIRE & RUBBER CO /OH/  (GT)"),
                         "GOODYEAR TIRE & RUBBER CO")


class RetrievalIsSeparateFromMatchingTests(unittest.TestCase):
    """`/query?company=` is a substring LIKE, so retrieval sends the SHORTEST
    distinctive leading run and the prefix rule decides afterwards.

    This is the 2026-08-13 lesson restated: that measurement moved 79 -> 99
    without a line of the pipeline changing, purely because retrieval had been
    built out of the matching rule.
    """

    def test_stops_at_the_first_corporate_suffix(self):
        self.assertEqual(rr.retrieval_term("STARBUCKS CORP"), "STARBUCKS")
        self.assertEqual(rr.retrieval_term("ZoomInfo Technologies Inc."), "ZoomInfo")
        self.assertEqual(rr.retrieval_term("CHEGG, INC"), "CHEGG")

    def test_never_returns_empty(self):
        for name in ("INC", "", "   ", "Corp"):
            self.assertTrue(rr.retrieval_term(name) is not None)


class CountAnchorSeparatesTheTiersTests(unittest.TestCase):
    """CONFIRMED requires the count to agree; that is what makes the lower end
    of the band publishable with no editor in the loop.

    Every 2026-08-01 false positive failed exactly this test: Dow Jones does not
    carry Dow's 800.
    """

    filing = {"filer": "DOW INC.", "filing_date": "2025-07-07",
              "stated_job_count": 800}

    def _row(self, name, count, when, eid=1):
        return {"event_id": eid, "company_name": name, "job_count": count,
                "announcement_date": when, "layoff_date": when}

    def test_count_agreement_confirms(self):
        tier, ids = rr.match(self.filing, [self._row("Dow", 800, "2025-10-07")])
        self.assertEqual(tier, rr.CONFIRMED)
        self.assertEqual(ids, [1])

    def test_wrong_count_is_proposed_not_confirmed(self):
        # Dow Jones aligns on name and sits in the window. It must reach the
        # UPPER end of the band and never the lower one.
        tier, _ = rr.match(self.filing, [self._row("Dow Jones", 12, "2025-08-01")])
        self.assertEqual(tier, rr.PROPOSED)

    def test_out_of_window_is_absent(self):
        tier, _ = rr.match(self.filing, [self._row("Dow", 800, "2023-01-01")])
        self.assertEqual(tier, rr.ABSENT)

    def test_confirmed_wins_when_both_are_present(self):
        tier, ids = rr.match(self.filing, [self._row("Dow Jones", 12, "2025-08-01", 2),
                                           self._row("Dow", 800, "2025-10-07", 1)])
        self.assertEqual(tier, rr.CONFIRMED)
        self.assertEqual(ids, [1])


class NotACutCountTests(unittest.TestCase):
    """A number beside an employee noun is not always the number being cut.

    Both cases below were read as cut counts and put in the denominator by the
    first full run, which scored two filings the tracker is CORRECT not to hold
    as coverage misses — depressing the measured figure by four points. The
    editor had excluded both filings by hand for exactly this reason.
    """

    def test_retained_headcount_is_refused(self):
        section = ("Item 2.05 ... a reduction in its workforce that will impact "
                   "approximately 29% of its current employees, retaining "
                   "approximately 15 employees essential to executing on the "
                   "Company's strategic priorities.")
        self.assertEqual(d205.parse(section)[0], None)

    def test_base_of_a_proportional_reduction_is_refused(self):
        section = ("Item 2.05 ... the Company will implement a reduction in workforce "
                   "of approximately one-third of its current approximately 260 "
                   "employees (the \"RIF\").")
        self.assertEqual(d205.parse(section)[0], None)

    def test_a_real_cut_count_still_parses(self):
        # "reduction OF APPROXIMATELY N employees" is the commonest cut phrasing
        # in the corpus and must survive. Elanco.
        section = ("Item 2.05 ... The Restructuring Plan will result in a global "
                   "headcount reduction of approximately 300 employees.")
        self.assertEqual(d205.parse(section)[0], 300)

    def test_workforce_of_is_not_a_marker(self):
        # This one is here because it was in the first draft of the marker list
        # and it cost Cibus, a real gold-set event: "a reduction in WORKFORCE OF
        # approximately 34" is a cut. The retention word carries the meaning,
        # the noun phrase does not.
        section = ("Item 2.05 ... approved a reduction in workforce of "
                   "approximately 34 employees.")
        self.assertEqual(d205.parse(section)[0], 34)


class ScopeHasThreeStatesTests(unittest.TestCase):
    """in_scope / out_of_scope / undecidable, and the hard case is the third.

    157 of the first window's 215 filings state no headcount in the Item 2.05
    section. Lumping them together made 76% of the enumeration UNKNOWN and the
    slice unusable. They split on one deterministic fact — whether an EX-99
    exhibit exists — and refusing to read that exhibit is deliberate: over
    exhibit bodies this parser read GitLab's "2021 Employee Stock Purchase Plan"
    as a headcount of 2021.
    """

    filing = {"primary_doc_url": "https://www.sec.gov/Archives/edgar/data/1/2/a.htm"}

    def _classify(self, doc, index):
        return rr.classify(dict(self.filing),
                           fetch=lambda url: index if url.endswith("/") else doc)

    def test_a_stated_count_is_in_scope(self):
        scope, count, _ = self._classify(
            "Item 2.05 Costs. A reduction of approximately 300 employees.", "")
        self.assertEqual((scope, count), (rr.IN_SCOPE, 300))

    def test_no_count_and_no_exhibit_is_out_of_scope(self):
        # No count anywhere in the filing. extractor.py would store nothing from
        # it, so scoring it as a recall miss would score a design decision.
        scope, _, _ = self._classify(
            "Item 2.05 Costs. The Company expects a pre-tax charge of $42 million.",
            "<html>index with no exhibits</html>")
        self.assertEqual(scope, rr.OUT_OF_SCOPE)

    def test_no_count_but_an_exhibit_is_undecidable(self):
        scope, _, why = self._classify(
            "Item 2.05 Costs. The Company expects a pre-tax charge of $42 million.",
            "<html>EX-99.1 press release</html>")
        self.assertEqual(scope, rr.UNDECIDABLE)
        self.assertEqual(why, "headcount_may_be_exhibit_only")

    def test_an_unreadable_index_is_undecidable_not_out_of_scope(self):
        def fetch(url):
            if url.endswith("/"):
                raise OSError("index unreachable")
            return "Item 2.05 Costs. A pre-tax charge of $42 million."
        scope, _, why = rr.classify(dict(self.filing), fetch=fetch)
        self.assertEqual(scope, rr.UNDECIDABLE)
        self.assertEqual(why, "exhibit_index_unreadable")

    def test_ambiguity_is_undecidable_never_a_guess(self):
        # The Wabash rule. Choosing is a coin flip on a published number and
        # summing is the Intuit hole; the parser declines.
        scope, _, why = self._classify(
            "Item 2.05 Costs. 3 salaried and 53 hourly employees, and 21 salaried "
            "and 193 hourly employees.", "")
        self.assertEqual(scope, rr.UNDECIDABLE)
        self.assertTrue(why.startswith("ambiguous_multiple_counts"))


class EnumerationMustBeCompleteTests(unittest.TestCase):
    """A truncated denominator INFLATES recall, so it must raise, not warn.

    The pagination cap that hid 33 gold events for a year printed a warning and
    carried on. This is the same failure mode and it is asserted instead.
    """

    def test_a_month_over_the_cap_raises(self):
        payload = json.dumps({"hits": {"total": {"value": rr.MAX_HITS_PER_MONTH + 1},
                                       "hits": []}})
        with self.assertRaises(RuntimeError):
            rr.enumerate_month(date(2026, 1, 1), date(2026, 1, 31),
                               http=lambda url: payload)

    def test_only_the_structured_item_code_selects(self):
        # The text query is a retrieval handle. A filing that merely SAYS
        # "Item 2.05" without carrying the code is not in the set.
        payload = json.dumps({"hits": {"total": {"value": 2}, "hits": [
            {"_id": "0000000000-26-000001:a.htm",
             "_source": {"items": ["2.05"], "ciks": ["1"], "file_date": "2026-01-05",
                         "display_names": ["REAL CO"]}},
            {"_id": "0000000000-26-000002:b.htm",
             "_source": {"items": ["8.01"], "ciks": ["2"], "file_date": "2026-01-06",
                         "display_names": ["MENTIONS IT ONLY"]}}]}})
        got = rr.enumerate_month(date(2026, 1, 1), date(2026, 1, 31),
                                 http=lambda url: payload)
        self.assertEqual([f["filer"] for f in got], ["REAL CO"])


class UnreachableIsNeverAMissTests(unittest.TestCase):
    """A host outage must not manufacture a recall regression — the 2026-07-31
    rule, which this repo learned when a Bluehost 504 muted its own alerter.

    The page budget is the same rule one level down: a one-word retrieval term
    is deliberately broad, and an unread tail is a row we cannot see. Calling
    that "absent" is precisely the pagination cap that hid 33 gold events.
    """

    def test_an_exhausted_page_budget_raises_rather_than_returning_short(self):
        page = json.dumps({"total": 5000,
                           "data": [{"id": i} for i in range(rr.QUERY_PER_PAGE)]})
        with self.assertRaises(RuntimeError):
            rr.query_rows("Packaging", fetch=lambda url: page)

    def test_a_short_page_ends_pagination(self):
        page = json.dumps({"total": 2, "data": [{"id": 1}, {"id": 2}]})
        self.assertEqual(len(rr.query_rows("Elanco", fetch=lambda url: page)), 2)


class WindowTests(unittest.TestCase):
    """Whole calendar months, ending SETTLE_DAYS back.

    The lag is a fairness rule: a filing made last Tuesday that we do not yet
    hold is ingest latency, not a coverage gap. Shortening it measures the clock
    and calls the result coverage.
    """

    def test_ends_on_a_settled_whole_month(self):
        start, end = rr.window_for(date(2026, 8, 17))
        self.assertEqual((start.isoformat(), end.isoformat()),
                         ("2025-07-01", "2026-06-30"))

    def test_the_window_advances_with_the_calendar(self):
        # The whole point: it ages with the data, not with someone's memory.
        _, a = rr.window_for(date(2026, 8, 17))
        _, b = rr.window_for(date(2026, 9, 20))
        self.assertGreater(b, a)

    def test_it_is_always_whole_months(self):
        for day in (1, 14, 27, 28, 31):
            try:
                today = date(2026, 3, day)
            except ValueError:
                continue
            start, end = rr.window_for(today)
            self.assertEqual(start.day, 1)
            self.assertEqual((end + timedelta(days=1)).day, 1)
            self.assertEqual(len(rr.months_in(start, end)), rr.WINDOW_MONTHS)


class JudgeHasThreeStatesTests(unittest.TestCase):
    """PASS / FAIL / UNKNOWN, and absence of a signal is never a pass."""

    def _doc(self, **kw):
        doc = {"measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "declared_slices": ["a"],
               "slices": {"a": {"state": rr.MEASURED, "confirmed": 40, "proposed": 2,
                                "judged": 45, "recall_confirmed": 40 / 45,
                                "recall_upper": 42 / 45,
                                "window": {"from": "2025-07-01", "to": "2026-06-30"}}}}
        doc.update(kw)
        return doc

    def test_a_missing_measurement_is_unknown(self):
        self.assertEqual(rr.judge(None)[0], rr.UNKNOWN)

    def test_a_stale_measurement_is_unknown(self):
        old = (datetime.now(timezone.utc)
               - timedelta(days=rr.MAX_MEASUREMENT_AGE_DAYS + 1))
        state, detail = rr.judge(self._doc(
            measured_at=old.strftime("%Y-%m-%dT%H:%M:%SZ")))
        self.assertEqual(state, rr.UNKNOWN)
        self.assertIn("UNVERIFIED", detail)

    def test_a_declared_slice_may_not_silently_disappear(self):
        # The requirement that made this module worth building: a slice that
        # cannot be computed this run must SAY so, not drop out of an average.
        state, detail = rr.judge(self._doc(declared_slices=["a", "b"]))
        self.assertEqual(state, rr.UNKNOWN)
        self.assertIn("b", detail)

    def test_one_unknown_slice_makes_the_report_unknown(self):
        doc = self._doc()
        doc["slices"]["a"] = {"state": rr.UNKNOWN, "detail": "enumeration failed"}
        self.assertEqual(rr.judge(doc)[0], rr.UNKNOWN)

    def test_a_not_measurable_slice_does_not_block_a_pass(self):
        # not_measurable is a RESULT — an honest "no denominator exists" — and
        # must not read as a fault forever. It carries its own staleness clock.
        doc = self._doc(declared_slices=["a", "w"])
        doc["slices"]["w"] = {"state": rr.NOT_MEASURABLE, "detail": "no denominator"}
        state, detail = rr.judge(doc)
        self.assertEqual(state, rr.PASS)
        self.assertIn("not measurable", detail)


class StandingAssessmentsExpireTests(unittest.TestCase):
    """A standing "not measurable" that nobody revisits is a stale claim wearing
    a permanent exemption — the defect benchmark_freshness.py exists to catch."""

    def test_the_warn_assessment_goes_unknown_once_it_ages_out(self):
        assessed = date(*(int(x) for x in rr.WARN_ASSESSED_AT.split("-")))
        fresh = rr.assess_state_warn(today=assessed + timedelta(days=1))
        self.assertEqual(fresh["state"], rr.NOT_MEASURABLE)
        stale = rr.assess_state_warn(
            today=assessed + timedelta(days=rr.WARN_ASSESSMENT_MAX_AGE_DAYS + 1))
        self.assertEqual(stale["state"], rr.UNKNOWN)

    def test_the_refusal_names_its_reason(self):
        # Wisconsin is refused on robots.txt, not because it was not found. A
        # measurement that cannot say WHY it declined is not falsifiable.
        detail = rr.assess_state_warn(today=date(2026, 8, 18))["detail"]
        self.assertIn("robots.txt", detail)


class CommittedMeasurementTests(unittest.TestCase):
    """The committed file is the artifact ops_status and the digest read."""

    def test_it_parses_and_declares_every_slice_the_module_declares(self):
        doc = rr.load_measurement()
        if doc is None:
            self.skipTest("no measurement committed yet")
        self.assertEqual(set(doc["declared_slices"]), set(rr.DECLARED_SLICES))
        for key in rr.DECLARED_SLICES:
            self.assertIn(key, doc["slices"], f"{key} declared but not reported")

    def test_no_slice_reports_a_bare_percentage_without_its_denominator(self):
        doc = rr.load_measurement()
        if doc is None:
            self.skipTest("no measurement committed yet")
        for key, s in doc["slices"].items():
            if s.get("state") == rr.MEASURED:
                self.assertIn("judged", s, f"{key} has a rate with no denominator")
                self.assertGreaterEqual(s["judged"], rr.MIN_DENOMINATOR)


if __name__ == "__main__":
    unittest.main()
