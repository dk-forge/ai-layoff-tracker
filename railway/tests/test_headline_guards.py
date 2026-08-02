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
    def _run(self, body, prior, headlines=ONE):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "baseline.json"
            path.write_text(json.dumps({"slices": {"one": prior}} if prior else {"slices": {}}))
            inv = di.MovementInvariant(headlines, baseline_path=path)
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
            ctx = _ctx(_agg(jobs=946_000, entries=5000, largest=900))
            report = di.check_all(fetch=_feed(_agg(jobs=946_000, entries=5000, largest=900)),
                                  invariants=(di.MovementInvariant(ONE, baseline_path=path),),
                                  ctx=ctx)
            self.assertEqual(report.verdict, di.FAIL)
            written, notes = di.record_baseline(ctx, report, path=path)
            self.assertTrue(written)
            after = json.loads(path.read_text())["slices"]["one"]
            self.assertEqual(after["jobs"], 1_000_000, "a failing slice was advanced")
            self.assertTrue(any("NOT advanced" in n for n in notes))

    def test_the_recorder_does_advance_a_passing_slice(self):
        prior = {"jobs": 1_000_000, "entries": 5000, "captured_at": _stamp(1)}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "baseline.json"
            path.write_text(json.dumps({"slices": {"one": prior}}))
            body = _agg(jobs=1_000_400, entries=5003, largest=400)
            ctx = _ctx(body)
            report = di.check_all(fetch=_feed(body),
                                  invariants=(di.MovementInvariant(ONE, baseline_path=path),),
                                  ctx=ctx)
            self.assertEqual(report.verdict, di.PASS)
            di.record_baseline(ctx, report, path=path)
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
            inv = di.MovementInvariant(self.WORLDWIDE, baseline_path=path)
            ctx = _ctx(body)
            report = di.check_all(fetch=_feed(body), invariants=(inv,), ctx=ctx)
            self.assertEqual(report.verdict, di.UNKNOWN)
            _, notes = di.record_baseline(ctx, report, path=path)
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
