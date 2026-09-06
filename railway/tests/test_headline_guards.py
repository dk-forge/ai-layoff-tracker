"""Offline tests for the three SHAPE guards in railway/data_integrity.py.

These are the guards that exist because every named-event tripwire is written
after the fact. The incidents they generalise:

  * a single row moving a published number     — RI 98,912 (a "9,891 … (2 from
    RI)" misparse), NJ 2.4 TRILLION (a digit-concatenated multi-county list),
    the AT&T 78,788 Florida TEST notice, Coal India 73,800 (a by-2050
    projection). Each was one row, each was live before anyone noticed.
  * a published total moving with nothing in the rows to explain it.
  * a plausibility test measured against an all-time cumulative sum — the
    2026-07-30 Spirit defect, where every row was CORRECT and the comparison was
    not. 64 companies double-counted 60,367 jobs; 43 companies had 113,786 real
    jobs suppressed to zero, including Boeing's genuine 17,000.

Everything here runs with no network and no keys: the live fetch is injected,
and the structural guard is fed source text directly.
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity as di


def _agg(jobs, entries=1000, largest=100, company="Acme", row_id=42, headline=None,
         concentration=True):
    """A minimal /aggregate body of the shape the guards read."""
    body = {"totals": {"jobs": jobs, "entries": entries}}
    if concentration:
        body["concentration"] = {
            "largest_row_jobs": largest,
            "largest_row_company": company,
            "largest_row_id": row_id,
            "headline_jobs": jobs if headline is None else headline,
            "headline_entries": entries,
        }
    return json.dumps(body).encode()


def _feed(body):
    return lambda url, timeout: body


def _ctx(body, today=None):
    return di.Ctx(_feed(body), 5, "cb", today=today)


def _stamp(days_ago):
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


ONE = (di.Headline(name="one", label="One", params={}, max_share=0.20,
                   move_floor=1000, mean_factor=4),)


class ScopeAlgebra(unittest.TestCase):
    """The Spirit defect expressed as a type error rather than a code review.

    The bug was not a wrong row and not a wrong bound. A ±45-day numerator was
    tested against a six-year denominator, and both numbers were individually
    right, so nothing about their magnitudes could have revealed it. What
    reveals it is the scope each number carries."""

    def test_a_share_of_two_different_populations_is_refused(self):
        a = di.Quantity(4000, di.Scope({"q": "Spirit"}), "news total")
        b = di.Quantity(8922, di.Scope({"q": "Spirit", "years": "2020"}), "WARN sum")
        with self.assertRaises(di.ScopeMismatch):
            di.share_of(a, b)

    def test_a_share_of_the_same_population_is_fine(self):
        s = di.Scope({"ai": "1"})
        self.assertAlmostEqual(
            di.share_of(di.Quantity(21000, s), di.Quantity(210000, s)), 0.1)

    def test_a_share_of_an_all_time_total_is_a_legitimate_question(self):
        # Unbounded is only forbidden as a PLAUSIBILITY denominator. "What
        # fraction of the published all-time total is this one row" is exactly
        # what the concentration guard asks, and it must stay askable.
        s = di.Scope({})                       # all time, by construction
        self.assertTrue(s.is_unbounded)
        self.assertAlmostEqual(
            di.share_of(di.Quantity(1, s), di.Quantity(4, s)), 0.25)

    def test_a_plausibility_test_against_a_cumulative_sum_raises(self):
        window = di.Scope({"q": "Spirit"}, window_days=45)
        all_time = di.Scope({"q": "Spirit"})           # the actual 2026-07-30 shape
        with self.assertRaises(di.UnboundedDenominator):
            di.plausibility_ratio(di.Quantity(4000, window, "news total"),
                                  di.Quantity(8922, all_time, "all-time WARN sum"))

    def test_a_plausibility_test_inside_one_window_is_allowed(self):
        w = di.Scope({"q": "Spirit"}, window_days=45)
        self.assertAlmostEqual(
            di.plausibility_ratio(di.Quantity(4000, w), di.Quantity(6109, w)),
            4000 / 6109.0)

    def test_two_different_windows_are_still_a_mismatch(self):
        with self.assertRaises(di.ScopeMismatch):
            di.plausibility_ratio(di.Quantity(1, di.Scope({}, window_days=45)),
                                  di.Quantity(1, di.Scope({}, window_days=90)))


class Concentration(unittest.TestCase):
    def _run(self, body, headlines=ONE):
        return di.ConcentrationInvariant(headlines).run(_ctx(body))

    def test_a_row_inside_its_bound_passes(self):
        r = self._run(_agg(jobs=287562, largest=9891))
        self.assertEqual(r.state, di.PASS)

    def test_the_ri_misparse_would_have_been_caught(self):
        # 9,891 workers filed as 98,912 by a count parser that stripped every
        # non-digit. Against a trailing-90-day headline that is 34%.
        r = self._run(_agg(jobs=287562 + 89021, largest=98912, company="RI notice"))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("98,912", r.detail)
        self.assertIn("RI notice", r.detail)

    def test_the_nj_digit_concatenation_would_have_been_caught(self):
        r = self._run(_agg(jobs=2_400_000_000_000, largest=2_400_000_000_000))
        self.assertEqual(r.state, di.FAIL)

    def test_a_headline_of_zero_is_a_failure_not_a_quiet_pass(self):
        r = self._run(_agg(jobs=0, largest=0))
        self.assertEqual(r.state, di.FAIL)

    def test_a_scope_mismatch_between_the_two_numbers_is_a_failure(self):
        # The block's own denominator disagreeing with totals.jobs means the
        # co-scoping this guard rests on has broken. That is not "unknown" —
        # it is a defect in the thing doing the measuring.
        r = self._run(_agg(jobs=1000, largest=10, headline=999))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("different populations", r.detail)

    def test_a_missing_block_is_unknown_and_pending_never_pass(self):
        r = self._run(_agg(jobs=1000, largest=10, concentration=False))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertTrue(r.pending)

    def test_an_http_error_is_unknown_but_NOT_excused(self):
        # The site answered, and answered wrongly on the parameterised path a
        # reader uses. Skipping that is how a guard stays green forever.
        import urllib.error

        def boom(url, timeout):
            raise urllib.error.HTTPError(url, 500, "nope", None, None)
        r = di.ConcentrationInvariant(ONE).run(di.Ctx(boom, 5, "cb"))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertFalse(r.pending)

    def test_a_deploy_maintenance_503_IS_excused(self):
        import urllib.error

        def boom(url, timeout):
            raise urllib.error.HTTPError(url, 503, "maintenance", None, None)
        r = di.ConcentrationInvariant(ONE).run(di.Ctx(boom, 5, "cb"))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertTrue(r.pending)

    def test_the_worst_slice_decides_and_is_the_one_reported(self):
        two = (di.Headline("a", "Slice A", {}, max_share=0.9),
               di.Headline("b", "Slice B", {"country": "United States"}, max_share=0.01))
        r = di.ConcentrationInvariant(two).run(_ctx(_agg(jobs=1000, largest=500)))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("Slice B", r.detail)
        self.assertNotIn("Slice A", r.detail)

    def test_every_shipped_headline_has_headroom_over_its_live_reading(self):
        # A bound set at or below what the site legitimately reads today is a
        # bound that fires on day one and gets deleted by the third person to
        # see it. Recorded live shares, 2026-07-31.
        observed = {"worldwide_recent_90d": 0.0344, "ai_all_time": 0.0985,
                    "worldwide_all_time": 0.0030, "us_all_time": 0.0086}
        for h in di.HEADLINES:
            self.assertIn(h.name, observed, f"{h.name} has no recorded live reading")
            self.assertGreater(h.max_share, observed[h.name] * 1.5,
                               f"{h.name}: bound {h.max_share} leaves no headroom over the "
                               f"observed {observed[h.name]}")


class Movement(unittest.TestCase):
    def _run(self, body, prior, headlines=ONE, incidents=None):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "baseline.json"
            path.write_text(json.dumps({"slices": {"one": prior}} if prior else {"slices": {}}))
            # Never the repo's own ledger: these tests would both read a real
            # open incident and write one of their own into it.
            ipath = Path(d) / "incidents.json"
            if incidents is not None:
                ipath.write_text(incidents if isinstance(incidents, str)
                                 else json.dumps(incidents))
            inv = di.MovementInvariant(headlines, baseline_path=path, incidents_path=ipath)
            ctx = _ctx(body)
            return inv.run(ctx), ctx

    def test_a_quiet_day_passes(self):
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        r, _ = self._run(_agg(jobs=1_000_400, entries=5003, largest=400), prior)
        self.assertEqual(r.state, di.PASS)

    def test_normal_ingest_passes_because_the_new_rows_carry_it(self):
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        # 40 new rows at roughly the slice's own mean (200) = 8,000 jobs.
        r, _ = self._run(_agg(jobs=1_008_000, entries=5040, largest=900), prior)
        self.assertEqual(r.state, di.PASS)

    def test_a_row_LEAVING_explains_a_fall_the_same_way(self):
        # Observed live twice in eight minutes on 2026-08-01: the AI headline
        # went 213,085/98 entries to 210,485/97 as a correction removed one row.
        # Counting only ARRIVING rows as an explanation would have made this
        # guard cry wolf inside a week, and a guard that cries wolf gets deleted.
        prior = {"jobs": 213_085, "entries": 98, "captured_at": _stamp(1)}
        r, _ = self._run(_agg(jobs=210_485, entries=97, largest=21_000), prior)
        self.assertEqual(r.state, di.PASS)

    def test_a_mass_re_mark_with_no_new_rows_fails(self):
        # The shape of a dedup pass flipping en masse, a bad purge-reload, or an
        # unannounced correction: the number moves, the row population does not.
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        r, _ = self._run(_agg(jobs=946_000, entries=5000, largest=900), prior)
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("NO ROW EXPLAINS THIS", r.detail)

    def test_one_genuinely_huge_arriving_event_is_a_legitimate_explanation(self):
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        r, _ = self._run(_agg(jobs=1_050_000, entries=5001, largest=50_000), prior)
        self.assertEqual(r.state, di.PASS)
        self.assertIn("one arriving row", r.detail)

    def test_a_big_row_that_did_not_arrive_excuses_nothing(self):
        # Without the "a row actually arrived" test, this clause would excuse a
        # mass re-mark simply because a large row exists somewhere in the data.
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        r, _ = self._run(_agg(jobs=1_050_000, entries=5000, largest=50_000), prior)
        self.assertEqual(r.state, di.FAIL)

    def test_a_single_absurd_row_is_not_excused_by_being_the_largest(self):
        # The NJ 2.4-trillion row IS the whole movement and IS the largest row,
        # so the one-row clause would excuse it — except that a row over its own
        # concentration bound is never allowed to be the explanation.
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        r, _ = self._run(_agg(jobs=2_400_000_000_000, entries=5001,
                              largest=2_400_000_000_000), prior)
        self.assertEqual(r.state, di.FAIL)

    def test_no_baseline_is_unknown_and_pending_never_pass(self):
        r, _ = self._run(_agg(jobs=1_000_000, entries=5000), None)
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertTrue(r.pending)
        self.assertIn("UNMEASURED", r.detail)

    def test_a_stale_baseline_cannot_bound_a_movement(self):
        prior = {"jobs": 1_000_000, "entries": 5000,
                 "captured_at": _stamp(di.MAX_BASELINE_AGE_DAYS + 1)}
        r, _ = self._run(_agg(jobs=9_000_000, entries=5000), prior)
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertIn("stale", r.detail)

    def test_a_headline_of_zero_fails(self):
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        r, _ = self._run(_agg(jobs=0, entries=0), prior)
        self.assertEqual(r.state, di.FAIL)

    def test_the_recorder_refuses_to_advance_a_failing_slice(self):
        """The anti-masking rule, and the reason record_baseline lives here.

        Record today's number over a FAILING slice and tomorrow's comparison is
        green against the wrong figure — the guard would launder the defect
        instead of catching it."""
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "baseline.json"
            path.write_text(json.dumps({"slices": {"one": prior}}))
            ipath = Path(d) / "incidents.json"
            ctx = _ctx(_agg(jobs=946_000, entries=5000, largest=900))
            report = di.check_all(fetch=_feed(_agg(jobs=946_000, entries=5000, largest=900)),
                                  invariants=(di.MovementInvariant(ONE, baseline_path=path,
                                                                   incidents_path=ipath),),
                                  ctx=ctx)
            self.assertEqual(report.verdict, di.FAIL)
            written, notes = di.record_baseline(ctx, report, path=path,
                                                incidents_path=ipath, headlines=ONE)
            self.assertTrue(written)
            after = json.loads(path.read_text())["slices"]["one"]
            self.assertEqual(after["jobs"], 1_000_000, "a failing slice was advanced")
            self.assertTrue(any("NOT advanced" in n for n in notes))

    def test_the_recorder_does_advance_a_passing_slice(self):
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "baseline.json"
            path.write_text(json.dumps({"slices": {"one": prior}}))
            ipath = Path(d) / "incidents.json"
            body = _agg(jobs=1_000_400, entries=5003, largest=400)
            ctx = _ctx(body)
            report = di.check_all(fetch=_feed(body),
                                  invariants=(di.MovementInvariant(ONE, baseline_path=path,
                                                                   incidents_path=ipath),),
                                  ctx=ctx)
            self.assertEqual(report.verdict, di.PASS)
            di.record_baseline(ctx, report, path=path, incidents_path=ipath, headlines=ONE)
            self.assertEqual(json.loads(path.read_text())["slices"]["one"]["jobs"], 1_000_400)

    # ---------------------------------------------------------------
    # A verdict that depends on WHEN you sampled is not a verdict.
    # 2026-08-02: worldwide_all_time FAILED on SHA 73b2606 at 03:33Z and
    # passed on 11bc4ce at 03:53Z with a byte-identical baseline
    # (039a0fad) and no recorder run in between. `Historical backfill
    # (EDGAR)` was running 02:39Z-07:40Z; both reads landed inside it.
    # ---------------------------------------------------------------
    WORLDWIDE = (di.Headline(name="one", label="One", params={}, max_share=0.01,
                             move_floor=25000, mean_factor=12),)

    def test_the_2026_08_02_partial_cycle_reading_is_unknown_not_a_failure(self):
        # The incident's own numbers. On the old code this returns FAIL.
        prior = {"jobs": 20_186_665, "entries": 63_319, "captured_at": _stamp(0.404)}
        r, _ = self._run(_agg(jobs=20_250_564, entries=63_335, largest=60_000),
                         prior, headlines=self.WORLDWIDE)
        self.assertEqual(r.state, di.UNKNOWN,
                         "a move judged part way through an ingest cycle is UNJUDGED")
        self.assertTrue(r.pending)
        self.assertIn("less than one ingest cycle", r.detail)

    def test_the_recorder_refuses_to_advance_over_a_suppressed_verdict(self):
        # The hole the fix would otherwise open: an UNKNOWN standing in for a
        # FAIL must be held to the same anti-masking rule, or the reading that
        # dodged its verdict becomes tomorrow's normal.
        prior = {"jobs": 20_186_665, "entries": 63_319, "captured_at": _stamp(0.404)}
        body = _agg(jobs=20_250_564, entries=63_335, largest=60_000)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "baseline.json"
            path.write_text(json.dumps({"slices": {"one": prior}}))
            ipath = Path(d) / "incidents.json"
            inv = di.MovementInvariant(self.WORLDWIDE, baseline_path=path,
                                       incidents_path=ipath)
            ctx = _ctx(body)
            report = di.check_all(fetch=_feed(body), invariants=(inv,), ctx=ctx)
            self.assertEqual(report.verdict, di.UNKNOWN)
            _, notes = di.record_baseline(ctx, report, path=path,
                                          incidents_path=ipath, headlines=self.WORLDWIDE)
            self.assertEqual(json.loads(path.read_text())["slices"]["one"]["jobs"],
                             20_186_665, "an unjudged reading was recorded as the baseline")
            self.assertTrue(any("SUPPRESSED" in n for n in notes))

    def test_a_headline_moving_on_no_new_rows_still_fails_inside_a_partial_cycle(self):
        # The condition this guard was actually built for is time-of-day
        # independent: jobs moved, the row population did not, so already
        # published rows were re-scored. No later arrival undoes that, and the
        # partial-cycle rule must not have bought quiet for it.
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(0.1)}
        r, _ = self._run(_agg(jobs=946_000, entries=5000, largest=900), prior)
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("NO ROW EXPLAINS THIS", r.detail)

    def test_a_zero_headline_still_fails_inside_a_partial_cycle(self):
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(0.1)}
        r, _ = self._run(_agg(jobs=0, entries=0), prior)
        self.assertEqual(r.state, di.FAIL)

    def test_a_full_cycle_keeps_the_full_verdict(self):
        # The daily run is unchanged: over a whole cycle an unexplained move is
        # still a FAIL, so the fix bought quiet only where the check was never
        # calibrated.
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        r, _ = self._run(_agg(jobs=1_100_000, entries=5001, largest=900), prior)
        self.assertEqual(r.state, di.FAIL)

    def test_the_sliding_window_slice_is_not_watched_for_movement(self):
        # Its from=/to= move every day, so day-over-day figures describe
        # different populations. Comparing them would be the very mistake the
        # scope algebra above exists to prevent.
        watched = {h.name for h in di.MovementInvariant().headlines}
        self.assertNotIn("worldwide_recent_90d", watched)


class StickyIncidents(unittest.TestCase):
    """An open incident is closed by a human, never by the calendar.

    THE DEFECT. Two individually correct guards combined into an automatic
    close on a fixed date. `record_baseline` refuses to advance a FAILING slice,
    so the failing slice's baseline is pinned. A baseline older than
    MAX_BASELINE_AGE_DAYS reports UNKNOWN with `suppressed` deliberately unset,
    so it IS recordable. Fifteen days after the FAIL the pinned baseline aged
    out, the recorder wrote the failing figure, and the incident was gone with
    no human involved — 2026-08-22, for the live us_all_time incident.

    Two more inputs widened in the same direction meanwhile, which is why
    re-deriving the verdict daily could never hold it either: the floor is
    `move_floor * span` and grows with the span, and the allowance is
    `|Δentries| * base_mean * mean_factor` and grows with every later arrival,
    whether or not those rows have anything to do with the defect.
    """

    # The live incident's own numbers, scaled to nothing: baseline 6,968,670
    # jobs over 43,341 entries, +93,210 jobs on +18 entries.
    US = (di.Headline(name="one", label="United States jobs, all time", params={},
                      max_share=0.02, move_floor=20000, mean_factor=12),)
    BASE = {"jobs": 6_968_670, "entries": 43_341}
    DAY_ONE = _agg(jobs=7_061_880, entries=43_359, largest=60_000)

    def _cycle(self, path, ipath, body, prior):
        """One daily run: check, then record. Returns (report, notes)."""
        path.write_text(json.dumps({"slices": {"one": prior}}))
        inv = di.MovementInvariant(self.US, baseline_path=path, incidents_path=ipath)
        ctx = _ctx(body)
        report = di.check_all(fetch=_feed(body), invariants=(inv,), ctx=ctx)
        _, notes = di.record_baseline(ctx, report, path=path, incidents_path=ipath,
                                      headlines=self.US)
        return report, notes

    def test_time_and_later_rows_cannot_close_an_open_incident(self):
        """THE REGRESSION TEST. Day one FAILs; day 20 must still FAIL.

        By day 20 all three escapes are open at once, and on the pre-fix tree
        this run returns UNKNOWN and the recorder adopts the failing figure:

          * the baseline is 20 days old -> past MAX_BASELINE_AGE_DAYS, so the
            slice reports UNKNOWN, `pending`, NOT `suppressed`, and
            record_baseline advances it;
          * span 20d puts the floor at 400,000, far over the 93,210 move;
          * 80 later entries put the allowance at ~154,000, also over it.

        None of those rows had anything to do with the defect. The verdict must
        be FAIL on the strength of the open incident alone.
        """
        with tempfile.TemporaryDirectory() as d:
            path, ipath = Path(d) / "baseline.json", Path(d) / "incidents.json"

            day_one = dict(self.BASE, captured_at=_stamp(3))
            report, notes = self._cycle(path, ipath, self.DAY_ONE, day_one)
            self.assertEqual(report.verdict, di.FAIL)
            self.assertIn("NO ROW EXPLAINS THIS", report.one_line())
            self.assertTrue(any("INCIDENT OPENED" in n for n in notes))
            self.assertEqual(json.loads(path.read_text())["slices"]["one"]["jobs"],
                             self.BASE["jobs"], "a failing slice was advanced on day one")

            # Day 20. The baseline is still pinned where day one left it, 80
            # unrelated entries have landed, and the span has quadrupled.
            pinned = dict(self.BASE, captured_at=_stamp(20))
            later = _agg(jobs=7_061_880 + 12_000, entries=43_359 + 80, largest=60_000)
            report, notes = self._cycle(path, ipath, later, pinned)

            self.assertEqual(report.verdict, di.FAIL,
                             "the incident closed itself — this is the 2026-08-22 laundering")
            self.assertIn("OPEN INCIDENT", report.one_line())
            self.assertEqual(json.loads(path.read_text())["slices"]["one"]["jobs"],
                             self.BASE["jobs"],
                             "the failing figure became the new baseline with no human")
            self.assertTrue(any("OPEN INCIDENT" in n for n in notes))

    def test_the_widened_formula_really_would_have_passed_on_its_own(self):
        """Proves the test above is testing stickiness and not a still-failing sum.

        Same day-20 reading, no incident open: the formula passes it. That is
        the whole hazard — nothing about the numbers themselves holds the FAIL.
        """
        prior = dict(self.BASE, captured_at=_stamp(5))
        r, _ = Movement()._run(_agg(jobs=7_061_880, entries=43_359, largest=60_000),
                               prior, headlines=self.US)
        self.assertEqual(r.state, di.PASS, "span 5d already puts the floor over this move")

    def test_an_incident_survives_a_reading_that_looks_perfectly_normal(self):
        # A quiet day is the most likely way an incident would be silently
        # dropped: nothing about today is wrong, so the formula says PASS.
        prior = dict(self.BASE, captured_at=_stamp(1))
        r, _ = Movement()._run(_agg(jobs=6_968_770, entries=43_342, largest=100),
                               prior, headlines=self.US,
                               incidents={"open": {"one": {
                                   "slice": "one", "label": "United States jobs, all time",
                                   "opened_at": _stamp(9), "detail": "+93,210 jobs, no row"}}})
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("OPEN INCIDENT", r.detail)
        self.assertIn("--close-incident", r.detail)

    def test_an_unreadable_ledger_is_unknown_and_suppressed_never_a_pass(self):
        # Deleting or corrupting the ledger must not be a way to clear a FAIL,
        # and the recorder must not advance while it cannot see the ledger.
        prior = dict(self.BASE, captured_at=_stamp(1))
        r, ctx = Movement()._run(_agg(jobs=6_968_770, entries=43_342, largest=100),
                                 prior, headlines=self.US, incidents="{not json")
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertEqual(ctx.observations["one"][2], True, "an unreadable ledger was recordable")

    def test_a_close_needs_a_reviewer_a_reason_row_ids_and_a_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            path, ipath = Path(d) / "baseline.json", Path(d) / "incidents.json"
            self._cycle(path, ipath, self.DAY_ONE, dict(self.BASE, captured_at=_stamp(3)))
            before = ipath.read_text()
            good = dict(name="one", reviewed_by="dak",
                        reason="reconcile-supersets un-matched 18 WARN rows; verified "
                               "against the state filings",
                        rows=["4411", "4412"], replacement_jobs=6_975_000,
                        replacement_entries=43_359, path=ipath, baseline_path=path)
            for missing in ("reviewed_by", "reason", "rows",
                            "replacement_jobs", "replacement_entries"):
                bad = dict(good)
                bad[missing] = [] if missing == "rows" else None
                with self.assertRaises(ValueError, msg=f"{missing} was optional"):
                    di.close_incident(**bad)
            # A one-word reason is a shrug, not a finding.
            with self.assertRaises(ValueError):
                di.close_incident(**dict(good, reason="fixed"))
            self.assertEqual(ipath.read_text(), before, "a refused close still wrote")
            self.assertEqual(json.loads(path.read_text())["slices"]["one"]["jobs"],
                             self.BASE["jobs"], "a refused close moved the baseline")

    def test_a_reviewed_close_clears_it_and_installs_the_stated_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            path, ipath = Path(d) / "baseline.json", Path(d) / "incidents.json"
            self._cycle(path, ipath, self.DAY_ONE, dict(self.BASE, captured_at=_stamp(3)))
            closed = di.close_incident(
                "one", reviewed_by="dak",
                reason="reconcile-supersets un-matched 18 WARN rows; verified against "
                       "the state filings and re-imported",
                rows=["4411", "4412"], replacement_jobs=6_975_000,
                replacement_entries=43_359, path=ipath, baseline_path=path)
            self.assertEqual(closed["affected_row_ids"], ["4411", "4412"])
            ledger = di.load_incidents(ipath)
            self.assertEqual(ledger["open"], {})
            self.assertEqual(len(ledger["closed"]), 1)
            # The REVIEWER's figure, not the live reading of 7,061,880.
            self.assertEqual(json.loads(path.read_text())["slices"]["one"]["jobs"], 6_975_000)
            # And the guard is armed again the next day, not stuck FAILING.
            r, _ = Movement()._run(_agg(jobs=6_975_400, entries=43_360, largest=400),
                                   dict(jobs=6_975_000, entries=43_359,
                                        captured_at=_stamp(1)), headlines=self.US)
            self.assertEqual(r.state, di.PASS)

    def test_the_shipped_ledger_is_readable_and_its_open_slices_are_real(self):
        # A typo in a slice name would make an incident silently unenforceable.
        ledger = di.load_incidents()
        names = {h.name for h in di.MovementInvariant().headlines}
        for name in ledger["open"]:
            self.assertIn(name, names, f"{name} is not a watched movement slice")


class DenominatorProvenance(unittest.TestCase):
    """Requirement: the Spirit comparison must be UNWRITABLE, not merely fixed.

    2.19.227 corrected the denominator. It left the company's whole WARN history
    one variable away from the comparison, so the same line could be written
    again by anyone who did not know the story. These tests pin the structure
    that removed the possibility."""

    def test_the_shipped_db_php_passes(self):
        r = di.DenominatorProvenanceInvariant().run(_ctx(b"{}"))
        self.assertEqual(r.state, di.PASS, r.detail)

    def test_php_actually_refuses_an_unwindowed_denominator(self):
        # Not a regex claim: the shipped helper's own guard clause, read out of
        # db.php. If the throw is ever softened to a return, this fails.
        src = di.DB_PHP.read_text(encoding="utf-8")
        body = di._php_function_body(src, "alt_dedup_subset_verdict")
        self.assertIsNotNone(body)
        self.assertIn("throw new InvalidArgumentException", body)
        self.assertIn("empty($window['scoped'])", body)

    def test_a_reintroduced_inline_share_comparison_fails(self):
        broken = di.DB_PHP.read_text(encoding="utf-8").replace(
            "$verdict = alt_dedup_subset_verdict($nc, $near);",
            "if ($nc < $warn_total * 0.5) continue;")
        r = di.DenominatorProvenanceInvariant().judge(broken)
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("2026-07-30 shape", r.detail)

    def test_a_reintroduced_local_sum_fails(self):
        broken = di.DB_PHP.read_text(encoding="utf-8").replace(
            "                $nc = (int) $nr['job_count'];",
            "                $nc = (int) $nr['job_count'];\n                $all_sum += 1;")
        r = di.DenominatorProvenanceInvariant().judge(broken)
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("accumulates its own sum", r.detail)

    def test_deleting_the_window_constructor_fails(self):
        broken = di.DB_PHP.read_text(encoding="utf-8").replace(
            "function alt_dedup_window(", "function alt_dedup_window_OLD(")
        r = di.DenominatorProvenanceInvariant().judge(broken)
        self.assertEqual(r.state, di.FAIL)

    def test_removing_the_window_width_cap_fails(self):
        src = di.DB_PHP.read_text(encoding="utf-8")
        body = di._php_function_body(src, "alt_dedup_window")
        broken = src.replace(body, body.replace("ALT_DEDUP_MAX_WINDOW_DAYS", "36500"))
        r = di.DenominatorProvenanceInvariant().judge(broken)
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("how wide a window may be", r.detail)

    def test_an_unreadable_source_is_unknown_never_pass(self):
        r = di.DenominatorProvenanceInvariant(php_path="/nonexistent/db.php").run(_ctx(b"{}"))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertTrue(r.pending)


class RegistryWiring(unittest.TestCase):
    def test_all_three_guards_are_registered(self):
        keys = {i.key for i in di.INVARIANTS}
        for k in ("headline_concentration", "headline_movement", "dedup_denominator_scoped"):
            self.assertIn(k, keys)

    def test_a_failing_shape_guard_makes_the_whole_report_fail(self):
        # It has to redden CI with the real assertion, or ci_alert.py has
        # nothing to extract and mail.
        report = di.check_all(fetch=_feed(_agg(jobs=1000, entries=10, largest=900)),
                              invariants=(di.ConcentrationInvariant(ONE),))
        self.assertEqual(report.verdict, di.FAIL)
        self.assertIn("One", report.one_line())

    def test_ledger_never_reports_ok_for_a_pending_guard(self):
        report = di.check_all(
            fetch=_feed(_agg(jobs=1000, entries=10, concentration=False)),
            invariants=(di.ConcentrationInvariant(ONE),))
        status, _, _ = di.ledger_status(report)
        self.assertNotEqual(status, "ok")

    def test_one_fetch_per_distinct_slice_however_many_guards_read_it(self):
        calls = []

        def counting(url, timeout):
            calls.append(url)
            return _agg(jobs=1_000_000, entries=5000, largest=900)
        ctx = di.Ctx(counting, 5, "cb")
        di.ConcentrationInvariant(ONE).run(ctx)
        di.MovementInvariant(ONE).run(ctx)
        self.assertEqual(len(set(calls)), 1)
        self.assertEqual(len(calls), 1, "the per-run fetch memo stopped working")


if __name__ == "__main__":
    unittest.main()


class TheClosedIncidentTrailIsBounded(unittest.TestCase):
    """Every committed ledger here has a cap or a horizon. This one had neither.

    alert_state keeps MAX_CLOSED=100, alert_outbox and deferral_ledger keep
    HISTORY_KEPT settled entries, spend trims to LEDGER_KEEP_DAYS=60.
    headline_incidents.json appended to `closed` and never cut. It grows slowly,
    because a close needs a reviewer, so this is a bound and not a rescue.

    The half that actually matters is the second test. `open` is a STICKY FAIL:
    a slice listed there reports FAIL until a human closes it, and it exists
    because two correct guards agreed to erase a real incident on 2026-08-22. A
    cap that could reach `open` would be that bug with a new cause, so the trim
    is pinned to the audit trail and tested away from the incidents themselves.
    """

    def _ledger(self, n_closed, n_open=0):
        return {"open": {f"slice-{i}": {"label": f"L{i}", "detail": "d",
                                        "baseline": {}, "observed": {}}
                         for i in range(n_open)},
                "closed": [{"name": f"c{i}", "closed_at": f"2026-01-{i % 28 + 1:02d}"}
                           for i in range(n_closed)]}

    def _roundtrip(self, ledger):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "incidents.json"
            di.save_incidents(ledger, path=path)
            return di.load_incidents(path=path)

    def test_the_closed_trail_stops_at_the_cap(self):
        cap = di.MAX_CLOSED_INCIDENTS
        back = self._roundtrip(self._ledger(cap + 40))
        self.assertEqual(len(back["closed"]), cap)

    def test_it_keeps_the_newest_closes_not_the_oldest(self):
        cap = di.MAX_CLOSED_INCIDENTS
        back = self._roundtrip(self._ledger(cap + 5))
        names = [c["name"] for c in back["closed"]]
        self.assertEqual(names[-1], f"c{cap + 4}")
        self.assertNotIn("c0", names, "the trim dropped the wrong end")

    def test_a_trail_under_the_cap_is_untouched(self):
        back = self._roundtrip(self._ledger(3))
        self.assertEqual(len(back["closed"]), 3)

    def test_no_cap_can_ever_reach_an_open_incident(self):
        """An open incident is a sticky FAIL. Nothing automatic may drop one."""
        cap = di.MAX_CLOSED_INCIDENTS
        back = self._roundtrip(self._ledger(cap * 3, n_open=cap * 2))
        self.assertEqual(len(back["open"]), cap * 2,
                         "the closed-history cap trimmed OPEN incidents")
