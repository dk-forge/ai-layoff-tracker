"""`pull_google_news` must be interruptible mid-call by a caller's own
wall-clock deadline.

Incident: run 36892178511 (2026-10-01), "AI evidence sweep". Google News RSS
answered every attempt transiently (429/5xx/timeout) for a run's whole
duration. ai_evidence_sweep.py only checks its own `past_deadline()` BEFORE
and AFTER the entire `pull_google_news(...)` call for one event, never
DURING it, so one call that fanned out across 14 (query, edition) jobs — each
up to 3 attempts at a 30s timeout — ran for several minutes straight. The
script's own deadline (1320s) was overshot by 266s (reported "TRUNCATED ...
(1586s)"), which combined with ~40s of job setup pushed the whole run past
its workflow's 27-minute `timeout-minutes`, where GitHub Actions killed it
outright ("The operation was canceled") instead of letting it exit cleanly.

ai-evidence-sweep.yml's own comment sizes the 27-minute ceiling's headroom
on "the worst single in-flight operation past the last deadline check" being
ONE source fetch (135s) — not an entire multi-job pull_google_news() call.
`deadline_check` restores that invariant: pull_google_news checks it before
every (query, edition) job and stops the moment it is true, so the worst
overshoot past a caller's deadline is bounded by one in-flight job, not by
however many jobs a locale rotation happened to plan.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import http_retry  # noqa: E402
from sources import google_news  # noqa: E402

# Three English editions so an explicit-query call plans exactly one job per
# locale (no native-vocabulary fan-out to make the job count non-deterministic).
THREE_ENGLISH_LOCALES = [loc for loc in google_news.GOOGLE_NEWS_LOCALES
                         if loc[0] in ("US", "GB", "CA")]


class StopsMidCallOnTheCallersDeadline(unittest.TestCase):
    def _pull(self, deadline_after):
        """deadline_check returns False `deadline_after` times, then True."""
        calls = []
        state = {"n": 0}

        def deadline_check():
            state["n"] += 1
            return state["n"] > deadline_after

        def get(url, params=None, headers=None, timeout=None):
            calls.append(url)
            class _Resp:
                status_code = 429
                headers = {}
                text = ""
            return _Resp()

        with patch.object(google_news.requests, "get", get), \
             patch.object(http_retry, "_sleep", lambda s: None), \
             patch.object(google_news.time, "sleep", lambda s: None), \
             patch.object(google_news, "_locales_for_now",
                          lambda: THREE_ENGLISH_LOCALES):
            rows = google_news.pull_google_news(queries=["layoffs"],
                                                deadline_check=deadline_check)
        return rows, calls

    def test_three_planned_jobs_stop_after_two_when_the_deadline_falls_due(self):
        rows, calls = self._pull(deadline_after=2)
        # Each job retries 429 three times before giving up -- 2 jobs allowed
        # through means 6 requests.get() calls, never the 9 all three jobs
        # would cost.
        self.assertEqual(len(calls), 6)
        self.assertEqual(rows, [])

    def test_a_deadline_that_never_falls_due_runs_every_planned_job(self):
        rows, calls = self._pull(deadline_after=999)
        self.assertEqual(len(calls), 9)   # 3 jobs x 3 attempts, none skipped

    def test_no_deadline_check_is_unaffected_default_behaviour(self):
        calls = []

        def get(url, params=None, headers=None, timeout=None):
            calls.append(url)
            class _Resp:
                status_code = 429
                headers = {}
                text = ""
            return _Resp()

        with patch.object(google_news.requests, "get", get), \
             patch.object(http_retry, "_sleep", lambda s: None), \
             patch.object(google_news.time, "sleep", lambda s: None), \
             patch.object(google_news, "_locales_for_now",
                          lambda: THREE_ENGLISH_LOCALES):
            google_news.pull_google_news(queries=["layoffs"])
        self.assertEqual(len(calls), 9)


class AiEvidenceSweepWiresItsOwnDeadlineThrough(unittest.TestCase):
    """Regression guard: the call site must hand its own clock in, or this
    whole fix is dead code. A future edit that drops the kwarg must fail here,
    not silently reopen the incident."""

    def test_the_call_site_passes_its_own_deadline(self):
        text = (Path(__file__).resolve().parents[1] / "ai_evidence_sweep.py").read_text()
        self.assertIn("deadline_check=past_deadline", text)


if __name__ == "__main__":
    unittest.main()
