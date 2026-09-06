"""A rate fitted to a smaller history must not be read as good news.

Every source_freshness verdict except "it published recently" is a statement
about a fitted rate, and that rate is a count over a window the collector
brought back this run. Shrink the history and the rate falls; p0 is
exp(-(rate/365) * dark), so a falling rate can only RAISE p0, which can only
move the verdict towards a pass. A PASS is the one verdict that closes an open
incident. So a short scrape is a one-way door out of BROKEN, and nothing had to
go wrong at the source for it to open.

warn:MN walked through it on 2026-09-01, and the committed ledger holds the
whole thing. It had been BROKEN since 2026-08-28 with nothing newer than
2026-08-07. That day's run measured 30 observations over 204 days; the runs on
either side of it measured 87 over 366. rate 86.18/yr -> 51.89/yr, p0 0.00346 ->
0.02861, across ALPHA_QUIET, verdict PASS, incident closed. The next day: BROKEN
again at p=0.00216, nothing having arrived in between. Had warn-import.yml been
carrying RESEND_API_KEY at the time (it was not, which is the other half of this
branch), that would have been a RECOVERED email and then a fresh dark-source
alarm for an outage that never paused.

The guard does not widen a threshold, move a state, or silence a signal. It
refuses to compare two fits that measured different amounts of history, and
UNKNOWN already never clears BROKEN (source_freshness.record). The numbers below
are the real ones from the ledger.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import source_freshness as F  # noqa: E402

# The three readings of warn:MN, verbatim from railway/source_state.json's
# history at 8d1af8a (09-02), 644f998 (09-01) and a447874 (08-31).
FULL = {"max_effective": "2026-08-07", "rate_per_year": 86.18,
        "rate_long_run_per_year": 85.77, "cadence_days": 15,
        "observations": 87, "span_days": 366, "rate_basis_days": 360}
SHRUNK = {"max_effective": "2026-08-07", "rate_per_year": 51.89,
          "rate_long_run_per_year": 51.89, "cadence_days": 26,
          "observations": 30, "span_days": 204, "rate_basis_days": 204}
DAY = F._as_date("2026-09-01")


class TheShortScrapeThatClosedARealIncident(unittest.TestCase):
    def test_the_full_history_calls_it_broken(self):
        v = F.judge(FULL, today=DAY, prior={"observations": 87, "span_days": 366})
        self.assertEqual(v["verdict"], F.FAIL)

    def test_the_shrunken_history_alone_would_have_passed(self):
        """Without the guard this is the 2026-09-01 bug, exactly.

        Note WHICH gate let it through. p0 rose to 0.02861, still under
        ALPHA_QUIET, so the p0 gate did not pass it; the CADENCE gate did. The
        short history moved the 90th-percentile gap from 15d to 26d, and 25 days
        dark sits inside 1.25x of 26. Both fitted quantities shifted, which is
        why both rate-dependent branches carry the guard and not just the
        obvious one.
        """
        v = F.judge(SHRUNK, today=DAY, prior=None)
        self.assertEqual(v["verdict"], F.PASS)
        self.assertEqual(v["p0"], 0.028607)
        self.assertIn("cadence", v["reason"])
        self.assertLess(v["p0"], F.ALPHA_QUIET)

    def test_with_the_previous_reading_it_is_unknown_not_a_pass(self):
        v = F.judge(SHRUNK, today=DAY, prior=FULL)
        self.assertEqual(v["verdict"], F.UNKNOWN)
        self.assertIn("history shrank", v["reason"])
        self.assertIn("30", v["reason"])
        self.assertIn("87", v["reason"])

    def test_unknown_leaves_an_open_incident_open(self):
        """The guard is only worth anything because of this existing rule."""
        ledger = {"sources": {}}
        F.record(ledger, "warn:MN", profile=FULL, verdict=F.FAIL,
                 reason="dark", today=F._as_date("2026-08-31"), label="MN WARN")
        self.assertEqual(ledger["sources"]["warn:MN"]["state"], F.BROKEN)
        v = F.judge(SHRUNK, today=DAY, prior=ledger["sources"]["warn:MN"])
        F.record(ledger, "warn:MN", profile=SHRUNK, verdict=v["verdict"],
                 reason=v["reason"], today=DAY, label="MN WARN")
        self.assertEqual(ledger["sources"]["warn:MN"]["state"], F.BROKEN,
                         "a short scrape closed a real outage")

    def test_a_pass_that_does_not_consult_the_fit_is_never_blocked(self):
        """2026-09-04 was a REAL recovery and must survive the guard.

        MN's observation count halved again that day (87 -> 44), but the PASS
        came from a notice dated 2026-10-04: zero days dark, under the 14d
        floor, a branch that never reads the rate. Blocking that would be the
        guard silencing a true recovery, which is the failure it exists to
        avoid the mirror image of.
        """
        recovered = {"max_effective": "2026-10-04", "rate_per_year": 43.12,
                     "rate_long_run_per_year": 43.12, "cadence_days": 26,
                     "observations": 44, "span_days": 364, "rate_basis_days": 364}
        v = F.judge(recovered, today=F._as_date("2026-09-04"), prior=FULL)
        self.assertEqual(v["verdict"], F.PASS)
        self.assertEqual(v["days_dark"], 0)


class TheGuardDoesNotFireOnOrdinaryChurn(unittest.TestCase):
    def test_a_small_drop_is_still_comparable(self):
        """Observations age out of a trailing window every run. That is normal."""
        nearly = dict(FULL, observations=80, rate_per_year=20.0)
        v = F.judge(nearly, today=DAY, prior=FULL)
        self.assertEqual(v["verdict"], F.PASS, v["reason"])

    def test_a_growing_history_is_never_blocked(self):
        more = dict(FULL, observations=120, rate_per_year=20.0)
        self.assertEqual(F.judge(more, today=DAY, prior=FULL)["verdict"], F.PASS)

    def test_a_first_reading_has_nothing_to_compare_with(self):
        loose = dict(SHRUNK, rate_per_year=20.0)
        self.assertEqual(F.judge(loose, today=DAY, prior=None)["verdict"], F.PASS)
        self.assertEqual(F.judge(loose, today=DAY, prior={})["verdict"], F.PASS)

    def test_a_tiny_previous_history_is_not_a_baseline(self):
        """Below MIN_OBSERVATIONS the previous reading was not a rate either."""
        loose = dict(SHRUNK, rate_per_year=20.0, observations=2)
        v = F.judge(loose, today=DAY, prior={"observations": 5, "span_days": 60})
        self.assertEqual(v["verdict"], F.PASS)

    def test_a_fail_is_never_softened_by_the_guard(self):
        """The guard only ever blocks a PASS. A shrunken history that still
        reads FAIL stays FAIL: it is biased towards passing, so a FAIL through
        it is if anything understated."""
        v = F.judge(SHRUNK, today=F._as_date("2026-12-01"), prior=FULL)
        self.assertEqual(v["verdict"], F.FAIL)


if __name__ == "__main__":
    unittest.main()
