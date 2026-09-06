"""A throttle is not an outage, and conflating them stalled the work queue.

MEASURED, 2026-09-06. `railway/gdelt_work_ledger.json` held 77 slots: 7
complete, 7 failed, and 63 QUEUED at `attempts=0`, none of them retried since
2026-08-28. Seven consecutive runs were byte-identical in shape: one broad slot
complete, one segment sweep failed, nine sweeps queued without an attempt
spent. The queued slots were ageing toward the 14-day horizon that drops them,
the oldest around 2026-09-11.

THE CAUSE was one flag with two meanings. `pull_gdelt_between` set `api_down`
on the first abandoned sweep, and `api_down` does two things: it queues the
remaining planned sweeps, and it SKIPS `_retry_pending_slots` entirely. So the
backlog could only drain on a run where nothing abandoned, and every run
abandoned. Self-reinforcing, and silent: a queued slot produces no error, no
health row and no log line anyone counts.

The diagnosis was wrong on the facts. 15 of 16 probes came back HTTP 429 "one
every 5 seconds", every response inside 20 seconds. The endpoint was answering
throughout. It was asking us to slow down, which is the opposite of being
unreachable, and `_collect_window` had carried that distinction all along;
`_run_sweep_slot` discarded it before the caller could see it.

WHAT IS DELIBERATELY UNCHANGED. A throttled sweep still queues the remaining
PLANNED sweeps. The wall-clock argument for that is untouched and correct: a
throttled-but-answering endpoint can burn the whole timeout budget one slow
request at a time, and that is what ran the 2026-08-27 sweep into its ceiling.
What changes is only that a throttle no longer claims the endpoint is dark, so
the pending-slot walk still runs while the deadline allows. Measured runs
finish with 400-700 seconds of a 900 second budget unused.

The walk's OWN brake is also unchanged and is not softened: inside the walk,
one abandoned slot stops it whatever the cause. Costing a day is fine; costing
the workflow ceiling is not.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import gdelt  # noqa: E402

_WS = datetime(2026, 1, 1, tzinfo=timezone.utc)
_WE = datetime(2026, 1, 2, tzinfo=timezone.utc)


class _Recorder:
    """Stands in for the sweep runner and records what the caller asked for."""

    def __init__(self, outcomes):
        # outcomes: list of (status, saw_rate_limit) returned in order
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, ledger, family, query, start, end, max_records,
                 collected, incomplete, deadline=None):
        self.calls += 1
        if self.outcomes:
            return self.outcomes.pop(0)
        return "complete", False


class _Harness(unittest.TestCase):
    def setUp(self):
        self.retried = []
        self._orig = {
            "_run_sweep_slot": gdelt._run_sweep_slot,
            "_retry_pending_slots": gdelt._retry_pending_slots,
            "_planned_sweeps": gdelt._planned_sweeps,
            "_collect_window": gdelt._collect_window,
            "_load_work_ledger": gdelt._load_work_ledger,
            "_save_work_ledger": gdelt._save_work_ledger,
            "_fetch_trusted": gdelt._fetch_trusted,
            "_record_slot": gdelt._record_slot,
        }
        # Three planned sweeps, so "the first abandons" leaves two to queue.
        gdelt._planned_sweeps = lambda: [
            ("segment", "q1"), ("native", "q2"), ("euro", "q3"),
        ]
        gdelt._retry_pending_slots = lambda *a, **k: self.retried.append(True)
        gdelt._load_work_ledger = lambda *a, **k: {"slots": {}}
        gdelt._save_work_ledger = lambda *a, **k: None
        gdelt._fetch_trusted = lambda collected, max_candidates=None: []
        gdelt._record_slot = lambda ledger, family, query, s, e, status, arts, **k: (
            f"{family}|{query}|{status}"
        )
        # The broad phase is not what this test is about; make it a no-op.
        gdelt._collect_window = lambda *a, **k: ([], "complete", False, None)

    def tearDown(self):
        for name, fn in self._orig.items():
            setattr(gdelt, name, fn)

    def _run(self, outcomes):
        rec = _Recorder(outcomes)
        gdelt._run_sweep_slot = rec
        gdelt.pull_gdelt_between(_WS, _WE)
        return rec


class ThrottleStillDrainsTheQueue(_Harness):
    def test_a_throttled_sweep_does_not_skip_the_pending_retry(self):
        """The whole defect, in one assertion.

        First sweep abandons WITH a rate-limit signal. The endpoint is
        answering, so the backlog must still be worked.
        """
        self._run([("abandoned", True)])
        self.assertTrue(
            self.retried,
            "a throttled sweep skipped _retry_pending_slots, which is the bug "
            "that left 63 slots unretried for nine days",
        )

    def test_a_silent_sweep_still_trips_the_outage_breaker(self):
        """The brake must survive. Abandoned with NO throttle signal means the
        endpoint really is dark, and the walk is correctly skipped."""
        self._run([("abandoned", False)])
        self.assertFalse(
            self.retried,
            "an unreachable endpoint must still skip the pending-slot walk; "
            "removing that brake is what ran a sweep into its workflow ceiling",
        )

    def test_a_throttled_sweep_still_queues_the_remaining_planned_sweeps(self):
        """Deliberately unchanged. The wall-clock argument for queueing is
        correct and independent of why the sweep abandoned."""
        rec = self._run([("abandoned", True)])
        self.assertEqual(
            rec.calls, 1,
            "after a throttled sweep the remaining planned sweeps must be "
            "QUEUED, not attempted; only the pending-slot walk resumes",
        )

    def test_a_clean_run_retries_pending_slots_as_before(self):
        self._run([("complete", False), ("complete", False), ("complete", False)])
        self.assertTrue(self.retried)


class TheSignalReachesTheCaller(unittest.TestCase):
    def test_run_sweep_slot_returns_the_rate_limit_flag(self):
        """`_collect_window` always carried this; `_run_sweep_slot` dropped it.

        Mutation guard: return a bare status again and this fails.
        """
        orig = gdelt._collect_window
        try:
            gdelt._collect_window = lambda *a, **k: (None, "abandoned", True, "429")
            out = gdelt._run_sweep_slot(
                {"slots": {}}, "segment", "q", _WS, _WE, 250, [], [],
            )
        finally:
            gdelt._collect_window = orig
        self.assertIsInstance(
            out, tuple,
            "_run_sweep_slot must return (status, saw_rate_limit); a bare "
            "status is what hid the throttle from the outage breaker",
        )
        self.assertEqual(out[0], "abandoned")
        self.assertTrue(out[1], "the throttle signal must survive the call")


if __name__ == "__main__":
    unittest.main()
