"""The Hawaii OCR import stops ITSELF, instead of being killed by the runner.

THE DEFECT THIS CLOSES
----------------------
`Hawaii WARN OCR import` was cancelled by its own `timeout-minutes: 30` on
2026-09-16 at exactly 30m0s. A run killed that way loses everything: nothing
is upserted, no terminal health note is posted, and the alert arrives as
"CI SELF-TIMEOUT" naming the clock rather than the cause.

`warn_hi_ocr.fetch_hi_ocr` had no wall clock at all. Only per-request
timeouts, so it crawled every notice of three years and ran until the runner
stopped it. And because `tests/test_deadline_below_workflow_timeout.py`
derives its pairs from module-level DEADLINE* constants, a script with NO
deadline was not merely unchecked, it was invisible to the guard written for
exactly this: absence read as OK.

So the budget is declared in `hi_warn_import.DEADLINE_SECONDS`, where that
guard pairs it with the workflow's kill (mutation-proved: raise its ceiling to
1800 and the guard names both numbers), and it is enforced here.

WHY A PARTIAL RUN IS SAFE, and why it is still not "ok"
------------------------------------------------------
The crawl returns the full cumulative set every run and the upsert is
idempotent, so whatever a truncated run does not reach, the next one re-reads.
Nothing has to be remembered for tomorrow to be equivalent to today, which is
the bar the RUNBOOK sets for a job that may defer. But a partial sweep is
reported `degraded`, never `ok`: an `ok` on a short run is the
started-not-finished shape, and it would reset the staleness clock while part
of the register went unread.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

RAILWAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _requests_stub  # noqa: F401,E402
from sources import warn_hi_ocr as hi  # noqa: E402


class _Clock:
    """A fake monotonic clock that advances a fixed amount per reading."""

    def __init__(self, step):
        self.step = step
        self.t = 0.0

    def __call__(self):
        now = self.t
        self.t += self.step
        return now


def _notices(n):
    return [(f"2026-01-{i + 1:02d}", f"Employer {i}", f"https://example.gov/n{i}.pdf")
            for i in range(n)]


class _Resp:
    """A reply that is not a PDF, so each notice is skipped cheaply. The
    extraction path is not what these tests are about; the budget is."""
    status_code = 404
    content = b"no"
    headers = {}


class TheRunStopsItselfBeforeTheRunnerDoes(unittest.TestCase):

    def setUp(self):
        hi.DEADLINE_TRUNCATED = False

    def _run(self, *, notices, deadline, seconds_per_notice):
        calls = []

        def fake_get(url, **kw):
            calls.append(url)
            return _Resp()

        # Two clock readings per iteration (the guard reads once; the loop
        # start reads once), so halve the step to get the intended pace.
        clock = _Clock(seconds_per_notice)
        with mock.patch.object(hi, "_hi_notices", lambda years: iter(notices)), \
                mock.patch.object(hi.requests, "get", fake_get):
            out = hi.fetch_hi_ocr(deadline_seconds=deadline, now=clock)
        return out, calls

    def test_a_long_crawl_stops_early_instead_of_being_killed(self):
        """200 notices at 60s each cannot fit a 1500s budget. The loop must
        stop itself rather than run on until the runner kills it."""
        _, calls = self._run(notices=_notices(200), deadline=1500,
                             seconds_per_notice=60)
        self.assertTrue(hi.DEADLINE_TRUNCATED)
        self.assertLess(len(calls), 200,
                        "the budget did not stop the crawl")

    def test_it_stops_before_the_worst_case_would_overrun(self):
        """The check is made BEFORE the notice, against the worst case of the
        one about to start, so the run never begins work it cannot finish."""
        _, calls = self._run(notices=_notices(200), deadline=1500,
                             seconds_per_notice=60)
        spent_at_stop = len(calls) * 60
        self.assertLessEqual(spent_at_stop + hi.PER_NOTICE_WORST_CASE_SECONDS,
                             1500 + 60)

    def test_a_crawl_that_fits_is_not_truncated(self):
        """The budget must not fire on a run that comfortably completes."""
        _, calls = self._run(notices=_notices(3), deadline=1500,
                             seconds_per_notice=1)
        self.assertFalse(hi.DEADLINE_TRUNCATED)
        self.assertEqual(len(calls), 3)

    def test_no_deadline_keeps_the_previous_unbounded_behaviour(self):
        """`deadline_seconds=None` is the dry-run and library path, unchanged."""
        _, calls = self._run(notices=_notices(25), deadline=None,
                             seconds_per_notice=10_000)
        self.assertFalse(hi.DEADLINE_TRUNCATED)
        self.assertEqual(len(calls), 25)

    def test_the_flag_is_reset_per_call(self):
        """A truncated run must not make the next one look truncated."""
        self._run(notices=_notices(200), deadline=1500, seconds_per_notice=60)
        self.assertTrue(hi.DEADLINE_TRUNCATED)
        self._run(notices=_notices(2), deadline=1500, seconds_per_notice=1)
        self.assertFalse(hi.DEADLINE_TRUNCATED)

    def test_truncation_is_a_flag_and_never_an_invented_count(self):
        """The loop breaks without walking the rest of the crawl, so the number
        of notices left is not known. Reporting one would be a guess, and this
        repo does not publish guessed numbers."""
        self.assertIsInstance(hi.DEADLINE_TRUNCATED, bool)
        self.assertNotIn("DEFERRED_NOTICES", dir(hi))


if __name__ == "__main__":
    unittest.main()
