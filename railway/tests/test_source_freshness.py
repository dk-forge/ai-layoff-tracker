"""The freshness tripwire, proved by MUTATION rather than by going green.

This project has shipped three guards that passed while the bug they existed
for was live, so the first test in this file is not "the new check works". It
is: FREEZE a real state's real data, show the OLD check calls it healthy, and
show the NEW check calls it dark. A test that cannot fail is not a test.

The fixture is not invented. `data/warn_state_dates_2026-08-19.json` holds the
actual WARN effective dates the live table returned on 2026-08-19 for the six
states a measurement run found silently dark, plus the controls that matter:
North Dakota (216 days quiet and legitimately so), Montana, Texas (dense enough
to trip a naive test every weekend), Arizona (a rolling-window portal) and
Oklahoma (publishes notices with no headcount, so it has no rows at all).
"""
import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import source_freshness as SF          # noqa: E402
import warn_import as W                # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                       "warn_state_dates_2026-08-19.json")
MEASURED_ON = datetime.date(2026, 8, 19)

# What the measurement run reported, verbatim, as the last effective date each
# dark state had published. Asserted here so a fixture edit cannot quietly move
# the ground the calibration stands on.
DARK_ON_2026_08_19 = {
    "KS": ("2026-05-01", 110),
    "MI": ("2026-05-30", 81),
    "MN": ("2026-07-01", 49),
    "NE": ("2026-06-26", 54),
    "IN": ("2026-07-21", 29),
    "MS": ("2026-06-30", 50),
}


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def verdict_for(state, fixture=None, today=MEASURED_ON):
    fixture = fixture or load_fixture()
    profile = SF.cadence_profile(fixture[state], today=today)
    return SF.judge(profile, today=today), profile


class TheFixtureIsTheRealThing(unittest.TestCase):
    def test_dates_match_the_measurement(self):
        fx = load_fixture()
        for st, (last, dark) in DARK_ON_2026_08_19.items():
            self.assertEqual(max(fx[st]), last, f"{st} last effective date")
            self.assertEqual((MEASURED_ON - datetime.date.fromisoformat(last)).days,
                             dark, f"{st} days dark")


class MutationTheOldCheckPassesWhereTheNewOneFails(unittest.TestCase):
    """The point of the whole change, in one test.

    Kansas's collector re-reads a frozen archive: it returns its FULL history on
    every run, so its count matches its own high-water floor exactly. The count
    floor therefore reports a clean bill of health, and did for 110 days.
    """

    def setUp(self):
        self.fx = load_fixture()

    def test_the_count_floor_calls_a_frozen_archive_healthy(self):
        for state in ("MI", "MN"):
            with self.subTest(state=state):
                frozen = len(self.fx[state])
                # The floor the ratchet would have learned from a healthy run,
                # and the count a frozen archive keeps returning: identical.
                counts = {state: frozen}
                floors = {state: float(frozen)}
                self.assertEqual(
                    W.detect_generic_state_drift(counts, [state], floors,
                                                 peer_min_frac=0.0,
                                                 peer_min_total=1),
                    [], f"the OLD count check should PASS {state} — that is the bug")
                # And the ratchet records it as a healthy run, forever.
                ledger = {}
                W.ratchet_state_baselines(ledger, "generic", counts, [state])
                self.assertEqual(ledger["generic"][state], float(frozen))

    def test_the_freshness_check_fails_the_same_frozen_archive(self):
        for state in ("MI", "MN"):
            with self.subTest(state=state):
                verdict, _ = verdict_for(state, self.fx)
                self.assertEqual(verdict["verdict"], SF.FAIL,
                                 f"{state}: {verdict.get('reason')}")

    def test_advancing_the_frontier_clears_it(self):
        """The mutation in the other direction: same state, data that moved.

        Without this, a check that returned FAIL unconditionally would pass the
        test above.
        """
        for state in ("MI", "MN"):
            with self.subTest(state=state):
                fresh = dict(self.fx)
                fresh[state] = self.fx[state] + [MEASURED_ON.isoformat()]
                verdict, _ = verdict_for(state, fresh)
                self.assertEqual(verdict["verdict"], SF.PASS, verdict.get("reason"))


class KansasIsTheFalsePositiveThisModelHasToNotProduce(unittest.TestCase):
    """The single most valuable assertion in this file.

    The first cut called Kansas dark with apparent certainty. A collector audit
    then found its register holds 910 rows, newest 2026-05-01, and that we
    already hold every notice in the fetch window. Nothing was missing. Kansas
    had not filed since May.

    The certainty came from the DENOMINATOR. Kansas reads 33/yr averaged over
    its whole history and 12.5/yr over the trailing year, and that is the
    difference between "impossible" and "a 2.3% event". A detector that cannot
    produce a false positive on the one case we KNOW is a false positive has not
    been tested.
    """

    def test_kansas_is_quiet_and_is_not_called_broken(self):
        verdict, _ = verdict_for("KS")
        self.assertEqual(verdict["verdict"], SF.QUIET, verdict.get("reason"))
        self.assertNotEqual(verdict["verdict"], SF.FAIL)

    def test_the_long_run_rate_would_have_called_it_broken(self):
        """The mutation that proves the fix is the fix."""
        _verdict, profile = verdict_for("KS")
        long_run = dict(profile, rate_per_year=profile["rate_long_run_per_year"])
        self.assertGreater(long_run["rate_per_year"], profile["rate_per_year"])
        self.assertEqual(SF.judge(long_run, today=MEASURED_ON)["verdict"], SF.FAIL)

    def test_kansas_reads_about_two_percent_not_zero(self):
        verdict, _ = verdict_for("KS")
        self.assertGreater(verdict["p0"], SF.ALPHA_DARK)
        self.assertLess(verdict["p0"], SF.ALPHA_QUIET)

    def test_a_quiet_source_is_never_recorded_broken(self):
        ledger = {"sources": {}}
        profile = SF.cadence_profile(load_fixture()["KS"], today=MEASURED_ON)
        SF.record(ledger, "warn:KS", profile=profile, verdict=SF.QUIET,
                  reason="quiet", today=MEASURED_ON)
        self.assertEqual(ledger["sources"]["warn:KS"]["state"], SF.HEALTHY)
        self.assertEqual(SF.broken(ledger), [])
        self.assertEqual([r["key"] for r in SF.quiet(ledger)], ["warn:KS"])

    def test_a_quiet_reading_does_not_clear_an_open_incident(self):
        """Still no new data. Quiet is not recovery."""
        ledger = {"sources": {}}
        profile = SF.cadence_profile(load_fixture()["KS"], today=MEASURED_ON)
        SF.record(ledger, "warn:KS", profile=profile, verdict=SF.FAIL,
                  reason="dark", classification=SF.DRIFT, today=MEASURED_ON)
        SF.record(ledger, "warn:KS", profile=profile, verdict=SF.QUIET,
                  reason="quiet", today=MEASURED_ON)
        self.assertEqual(ledger["sources"]["warn:KS"]["state"], SF.BROKEN)


class TheSixRealStates(unittest.TestCase):
    """Which of the six survive on their actual dates, and which were quiet.

    TWO are broken: MI and MN. Both were independently confirmed - Michigan's
    API caps its own window, Minnesota's older templates parse to zero.
    TWO are QUIET, an advisory tier that is never emailed as a breakage: KS
    (audited, nothing missing) and IN.
    TWO PASS outright: MS on its own quarterly cadence, NE on rarity.

    None of that is tuned. It is what a trailing rate says about real dates.
    """

    def test_only_mi_and_mn_are_called_broken(self):
        fx = load_fixture()
        fired = [s for s in DARK_ON_2026_08_19
                 if verdict_for(s, fx)[0]["verdict"] == SF.FAIL]
        self.assertEqual(sorted(fired), ["MI", "MN"])

    def test_ks_and_in_are_quiet_not_broken(self):
        fx = load_fixture()
        quiet = [s for s in DARK_ON_2026_08_19
                 if verdict_for(s, fx)[0]["verdict"] == SF.QUIET]
        self.assertEqual(sorted(quiet), ["IN", "KS"])

    def test_mississippi_passes_on_its_own_quarterly_cadence(self):
        verdict, profile = verdict_for("MS")
        self.assertEqual(verdict["verdict"], SF.PASS)
        # Not by an exemption: by its own measured gaps. The cadence bar alone
        # would hold it even if the rarity gate had fired.
        self.assertGreaterEqual(profile["cadence_days"], 40)
        self.assertGreater(SF.CADENCE_MARGIN * profile["cadence_days"],
                           verdict["days_dark"])

    def test_nebraska_is_a_pass_on_rarity_not_on_cadence(self):
        verdict, _ = verdict_for("NE")
        self.assertEqual(verdict["verdict"], SF.PASS)
        self.assertGreaterEqual(verdict["p0"], SF.ALPHA_QUIET)

    def test_a_slowdown_is_reported_as_itself(self):
        """"This source has slowed" is information, not a breakage."""
        busy = [f"{y}-{m:02d}-{d:02d}" for y in (2023, 2024)
                for m in range(1, 13) for d in (1, 11, 21)]
        slow = ([f"2025-{m:02d}-01" for m in range(6, 13)]
                + [f"2026-{m:02d}-01" for m in range(1, 6)])
        dates = busy + slow
        profile = SF.cadence_profile(dates, today=MEASURED_ON)
        self.assertTrue(profile.get("slowed"))
        self.assertLess(profile["rate_per_year"],
                        profile["rate_long_run_per_year"])


class TheControlsThatMustNotFire(unittest.TestCase):
    def test_north_dakota_216_days_quiet_is_legitimate(self):
        verdict, profile = verdict_for("ND")
        self.assertEqual(verdict["verdict"], SF.PASS, verdict.get("reason"))
        self.assertEqual(verdict["days_dark"], 216)
        self.assertLess(profile["rate_per_year"], 10)

    def test_montana_is_legitimate(self):
        self.assertEqual(verdict_for("MT")[0]["verdict"], SF.PASS)

    def test_texas_is_held_back_by_the_minimum_dark_window(self):
        """TX clears BOTH statistical gates at 9 days. The floor is load-bearing."""
        verdict, profile = verdict_for("TX")
        self.assertEqual(verdict["verdict"], SF.PASS)
        self.assertLess(verdict["p0"], SF.ALPHA_DARK)     # the rarity gate would fire
        self.assertLess(verdict["days_dark"], SF.MIN_DARK_DAYS)

    def test_a_rolling_window_portal_is_not_misread(self):
        """AZ publishes a rolling window, so its COUNT is meaningless as a floor
        (it is excluded from the ratchet). Its FRONTIER is not: a rolling window
        that is being refreshed keeps advancing, and AZ passes on that."""
        self.assertIn("AZ", W.ROLLING_WINDOW_STATES)
        verdict, _ = verdict_for("AZ")
        self.assertEqual(verdict["verdict"], SF.PASS, verdict.get("reason"))

    def test_a_future_dated_register_is_never_flagged_by_the_clamp(self):
        fx = load_fixture()
        fx["KS"] = fx["KS"] + ["2027-03-31"]     # a real advance-notice date
        verdict, _ = verdict_for("KS", fx)
        self.assertEqual(verdict["days_dark"], 0)
        self.assertEqual(verdict["verdict"], SF.PASS)


class AbsenceOfASignalIsNotAPass(unittest.TestCase):
    def test_a_state_with_no_rows_is_unknown(self):
        verdict, profile = verdict_for("OK")
        self.assertEqual(verdict["verdict"], SF.UNKNOWN)
        self.assertIn("insufficient", profile)

    def test_a_thin_history_is_unknown_not_pass(self):
        thin = ["2026-01-0%d" % d for d in range(1, 5)]
        verdict = SF.judge(SF.cadence_profile(thin, today=MEASURED_ON),
                           today=MEASURED_ON)
        self.assertEqual(verdict["verdict"], SF.UNKNOWN)

    def test_a_short_span_is_unknown_even_with_many_rows(self):
        base = datetime.date(2026, 7, 1)
        dense = [(base + datetime.timedelta(days=i)).isoformat() for i in range(20)]
        verdict = SF.judge(SF.cadence_profile(dense, today=MEASURED_ON),
                           today=MEASURED_ON)
        self.assertEqual(verdict["verdict"], SF.UNKNOWN)

    def test_an_unreadable_ledger_raises_rather_than_reading_empty(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{ not json")
            path = fh.name
        try:
            with self.assertRaises(RuntimeError):
                SF.load_ledger(path)
        finally:
            os.unlink(path)


class TheCalibrationIsPinned(unittest.TestCase):
    """A later session may retune these, but not by accident.

    ALPHA sits at 0.05 because 0.10 buys no additional true positive on the
    2026-08-19 data and costs North Dakota as a false alarm (p=0.0714).
    """

    def test_alpha_relaxed_to_ten_percent_would_flag_north_dakota(self):
        verdict, _ = verdict_for("ND")
        self.assertLess(verdict["p0"], 0.10)
        self.assertGreater(verdict["p0"], SF.ALPHA_QUIET)

    def test_the_constants_are_what_the_calibration_used(self):
        self.assertEqual(SF.ALPHA_DARK, 0.01)
        self.assertEqual(SF.ALPHA_QUIET, 0.05)
        self.assertEqual(SF.CADENCE_QUANTILE, 0.90)
        self.assertEqual(SF.CADENCE_MARGIN, 1.25)
        self.assertEqual(SF.MIN_DARK_DAYS, 14)
        self.assertEqual(SF.REFERENCE_WINDOW_DAYS, 1095)
        self.assertEqual(SF.RATE_WINDOW_DAYS, 365)

    def test_the_rate_is_trailing_and_the_cadence_is_not(self):
        """The two quantities have different windows for a measured reason:
        rates drift, burstiness does not, and a gap distribution needs samples
        a low-volume state cannot produce in one year."""
        _v, profile = verdict_for("KS")
        self.assertLess(profile["rate_basis_days"], SF.REFERENCE_WINDOW_DAYS)
        self.assertNotEqual(profile["rate_per_year"],
                            profile["rate_long_run_per_year"])

    def test_the_reference_window_ends_at_the_last_notice_not_today(self):
        """A window ending at today would dilute the rate with the darkness."""
        fx = load_fixture()
        near = SF.cadence_profile(fx["KS"], today=MEASURED_ON)
        far = SF.cadence_profile(fx["KS"],
                                 today=MEASURED_ON + datetime.timedelta(days=400))
        self.assertEqual(near["rate_per_year"], far["rate_per_year"])


class ClassificationIsTriageReady(unittest.TestCase):
    def test_a_collector_that_errored_is_a_hard_failure(self):
        self.assertEqual(SF.classify(SF.FAIL, errored=True, produced=500),
                         SF.HARD_FAILURE)

    def test_a_collector_that_returned_nothing_is_a_hard_failure(self):
        self.assertEqual(SF.classify(SF.FAIL, produced=0), SF.HARD_FAILURE)

    def test_a_collapsed_count_is_a_format_change(self):
        self.assertEqual(SF.classify(SF.FAIL, produced=61, count_collapsed=True),
                         SF.FORMAT_CHANGE)

    def test_a_full_archive_with_nothing_new_is_drift(self):
        self.assertEqual(SF.classify(SF.FAIL, produced=799), SF.DRIFT)

    def test_the_fix_instruction_names_the_shape_of_the_break(self):
        for kind, needle in ((SF.DRIFT, "nothing NEW"),
                             (SF.HARD_FAILURE, "portal still exists"),
                             (SF.FORMAT_CHANGE, "fewer rows parse")):
            line = SF.fix_instruction({"key": "warn:KS", "days_dark": 110,
                                       "classification": kind})
            self.assertIn(needle, line)
            self.assertIn("warn:KS", line)


class TheLedgerIsPersistentAndStubborn(unittest.TestCase):
    def setUp(self):
        self.ledger = {"sources": {}}
        self.fx = load_fixture()
        self.profile = SF.cadence_profile(self.fx["KS"], today=MEASURED_ON)

    def _break_it(self, day=MEASURED_ON):
        SF.record(self.ledger, "warn:KS", profile=self.profile, verdict=SF.FAIL,
                  reason="dark", classification=SF.DRIFT, today=day)

    def test_a_broken_source_keeps_its_first_detected_and_ages(self):
        self._break_it()
        self._break_it(MEASURED_ON + datetime.timedelta(days=30))
        entry = self.ledger["sources"]["warn:KS"]
        self.assertEqual(entry["state"], SF.BROKEN)
        self.assertEqual(entry["first_detected"], MEASURED_ON.isoformat())
        rows = SF.broken(self.ledger, today=MEASURED_ON + datetime.timedelta(days=30))
        self.assertEqual(rows[0]["age_days"], 30)

    def test_unknown_never_clears_broken(self):
        self._break_it()
        SF.record(self.ledger, "warn:KS", profile={"insufficient": "thin"},
                  verdict=SF.UNKNOWN, reason="thin",
                  today=MEASURED_ON + datetime.timedelta(days=1))
        self.assertEqual(self.ledger["sources"]["warn:KS"]["state"], SF.BROKEN)

    def test_a_genuine_pass_recovers_it(self):
        self._break_it()
        SF.record(self.ledger, "warn:KS", profile=self.profile, verdict=SF.PASS,
                  reason="advanced", today=MEASURED_ON + datetime.timedelta(days=2))
        entry = self.ledger["sources"]["warn:KS"]
        self.assertEqual(entry["state"], SF.HEALTHY)
        self.assertNotIn("first_detected", entry)

    def test_unavailable_is_never_re_broken_by_a_machine(self):
        SF._cli(["--classify-unavailable", "warn:WY", "--reviewer", "owner",
                 "--reason", "not public by statute",
                 "--ledger", self._tmp_ledger()])
        ledger = SF.load_ledger(self._tmp_path)
        SF.record(ledger, "warn:WY", profile=self.profile, verdict=SF.FAIL,
                  reason="dark", classification=SF.DRIFT, today=MEASURED_ON)
        self.assertEqual(ledger["sources"]["warn:WY"]["state"], SF.UNAVAILABLE)
        self.assertNotIn("first_detected", ledger["sources"]["warn:WY"])

    def test_classifying_unavailable_requires_a_named_human_and_a_reason(self):
        self.assertEqual(SF._cli(["--classify-unavailable", "warn:WY",
                                  "--ledger", self._tmp_ledger()]), 1)
        self.assertEqual(SF.load_ledger(self._tmp_path).get("sources"), {})

    def _tmp_ledger(self):
        import tempfile
        fd, self._tmp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(self._tmp_path, "w", encoding="utf-8") as fh:
            fh.write('{"sources": {}}')
        self.addCleanup(lambda: os.path.exists(self._tmp_path) and os.unlink(self._tmp_path))
        return self._tmp_path

    def test_a_receding_frontier_is_recorded_but_never_as_an_advance(self):
        SF.record(self.ledger, "warn:KS", profile=self.profile, verdict=SF.PASS,
                  reason="ok", today=MEASURED_ON)
        shrunk = dict(self.profile, max_effective="2025-01-01")
        SF.record(self.ledger, "warn:KS", profile=shrunk, verdict=SF.PASS,
                  reason="ok", today=MEASURED_ON + datetime.timedelta(days=1))
        entry = self.ledger["sources"]["warn:KS"]
        self.assertEqual(entry["frontier"], self.profile["max_effective"])
        self.assertIn("frontier_receded_at", entry)


class TheCommittedLedgerIsWellFormed(unittest.TestCase):
    def test_the_seeded_unavailable_states_are_all_human_signed(self):
        ledger = SF.load_ledger()
        keys = SF.unavailable(ledger)
        for expected in ("warn:AR", "warn:NH", "warn:WY", "warn:PR",
                         "warn:GU", "warn:VI"):
            self.assertIn(expected, keys)
        for key in keys:
            entry = ledger["sources"][key]
            self.assertTrue(entry.get("unavailable_reason"), key)
            self.assertTrue(entry.get("unavailable_reviewer"), key)
            self.assertTrue(entry.get("unavailable_since"), key)
            self.assertEqual(entry.get("classification"), SF.POLICY, key)

    def test_no_state_with_a_public_register_is_seeded_unavailable(self):
        seeded = {k.split(":", 1)[1] for k in SF.unavailable(SF.load_ledger())}
        self.assertNotIn("KS", seeded)
        self.assertNotIn("MS", seeded)

    def test_one_finding_not_six(self):
        ledger = {"sources": {}}
        for st in ("KS", "MI", "MN", "IN"):
            SF.record(ledger, f"warn:{st}",
                      profile=SF.cadence_profile(load_fixture()[st], today=MEASURED_ON),
                      verdict=SF.FAIL, reason="dark", classification=SF.DRIFT,
                      today=MEASURED_ON)
        line = SF.describe(SF.broken(ledger, today=MEASURED_ON))
        for st in ("KS", "MI", "MN", "IN"):
            self.assertIn(f"warn:{st}", line)
        self.assertEqual(SF._cli(["--report"]), 0)   # a backlog is not a red run


class TheInventoryIsBuiltFromWhatShouldExist(unittest.TestCase):
    """The other bug: a collector that never reports at all.

    Freshness catches a source that lies. This catches a source nobody has ever
    looked at, which does not show up green because it does not show up. Every
    other guard in this repo iterates the health ledger, so a thing missing from
    it is invisible by construction.
    """

    def setUp(self):
        import source_inventory
        self.SI = source_inventory

    def test_all_56_us_jurisdictions_are_inventoried(self):
        self.assertEqual(len(self.SI.US_JURISDICTIONS), 56)
        for st in ("KS", "WY", "DC", "PR", "GU", "VI", "AS", "MP"):
            self.assertIn(st, self.SI.US_JURISDICTIONS)

    def test_the_collector_map_is_read_from_the_scrapers_own_registries(self):
        """So a state wired into a scraper later is watched the same day,
        without anybody remembering to add it here."""
        collectors = self.SI.warn_collectors()
        self.assertIn("KS", collectors)
        self.assertIn("CA", collectors)
        self.assertIn("HI", collectors)

    def test_a_jurisdiction_with_no_collector_is_named(self):
        missing = self.SI.uncollected_jurisdictions()
        for st in ("AR", "NH", "WY", "PR", "GU", "VI"):
            self.assertIn(st, missing)
        self.assertNotIn("KS", missing)

    def test_a_new_declared_collector_is_inventoried_the_moment_it_exists(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write("const meta = {\n"
                     "    brand_new_source: ['label', 'Daily', 'X', 'Y'],\n"
                     "    warn_us: ['label', 'Daily', 'X', 'Y'],\n"
                     "  };\n")
            path = fh.name
        try:
            self.assertIn("brand_new_source", self.SI.declared_collectors(path))
            self.assertEqual(
                self.SI.never_reported({"warn_us": {"status": "ok"}}, path),
                ("brand_new_source",))
        finally:
            os.unlink(path)

    def test_the_real_registry_parses(self):
        declared = self.SI.declared_collectors()
        self.assertGreater(len(declared), 20)
        for expected in ("warn_us", "gdelt", "edgar", "eurofound_erm"):
            self.assertIn(expected, declared)

    def test_an_unreadable_registry_is_an_error_not_an_empty_pass(self):
        with self.assertRaises(ValueError):
            self.SI.never_reported({}, "/nonexistent/health.js")
        summary = self.SI.summary({}, "/nonexistent/health.js")
        self.assertIsNone(summary["never_reported"])   # UNKNOWN, not []


class TheHealerMayNotEditTheJudge(unittest.TestCase):
    """A healer that resolves a dark source by moving the threshold is worse
    than no healer. The prompt is a request; the diff is a fact."""

    def test_the_judge_and_its_ledger_are_forbidden_paths(self):
        import self_heal
        for path in ("railway/source_freshness.py", "railway/source_state.json"):
            self.assertIn(path, self_heal.FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
