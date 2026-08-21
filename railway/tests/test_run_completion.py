"""A collector run that starts and never finishes must be visible.

The defect: `cron.py` posts `running` then a terminal note, but nothing checked
the pairing. The health ledger keeps only the LATEST note, so the next day's run
erases the evidence — and an orphaned `running` carries a fresh `checked_at`, so
a collector that died mid-flight looked healthy AND reset its staleness clock.

The fixtures below are the real 2026-08-16 and 2026-08-19 incidents, trimmed.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import run_completion as rc  # noqa: E402

NOW = datetime(2026, 8, 20, 23, 0, tzinfo=timezone.utc)


def note(source, status, at):
    return {"source": source, "status": status, "entries": 0, "detail": "",
            "attempted_at": at}


# 2026-08-19: gdelt posted `running` at 22:07 and nothing ever answered it. The
# next day's run started again. `spend_jobs.json` has no end-of-run record for
# that run, so the process died.
DIED_MID_GDELT = [
    note("gdelt", "running", "2026-08-18T16:07:20+00:00"),
    note("gdelt", "ok", "2026-08-18T16:14:52+00:00"),
    note("gdelt", "running", "2026-08-19T22:07:19+00:00"),
    note("gdelt", "running", "2026-08-20T22:05:51+00:00"),
    note("gdelt", "ok", "2026-08-20T22:13:36+00:00"),
]

# A wholly ordinary week: every attempt is a pair.
ALL_PAIRED = [
    note("edgar", "running", "2026-08-20T22:02:25+00:00"),
    note("edgar", "ok", "2026-08-20T22:03:10+00:00"),
    note("google_news", "running", "2026-08-20T22:03:11+00:00"),
    note("google_news", "ok", "2026-08-20T22:03:44+00:00"),
    note("national_feeds", "running", "2026-08-20T22:05:25+00:00"),
    note("national_feeds", "degraded", "2026-08-20T22:05:48+00:00"),
]


class Orphans(unittest.TestCase):

    def test_finds_the_run_that_never_finished(self):
        found = rc.orphans(DIED_MID_GDELT, now=NOW)
        self.assertEqual([f["source"] for f in found], ["gdelt"])
        self.assertEqual(found[0]["started_at"],
                         datetime(2026, 8, 19, 22, 7, 19, tzinfo=timezone.utc))
        self.assertEqual(found[0]["followed_by"], "running")

    def test_a_degraded_note_closes_a_run(self):
        """`degraded` is a FINISHED run that failed. It is not an orphan."""
        self.assertEqual(rc.orphans(ALL_PAIRED, now=NOW), [])

    def test_interleaved_sources_do_not_close_each_other(self):
        """cron runs collectors back to back; pairing is strictly per source.

        This is the 2026-08-16 shape: local_news started, never got its terminal
        note, and regional_feeds started 108 seconds later. A pairing that
        ignored the source name would read that as a clean pair.
        """
        runs = [
            note("local_news", "running", "2026-08-16T16:04:06+00:00"),
            note("regional_feeds", "running", "2026-08-16T16:05:54+00:00"),
            note("local_news", "running", "2026-08-17T14:04:01+00:00"),
            note("local_news", "ok", "2026-08-17T14:05:18+00:00"),
            note("regional_feeds", "running", "2026-08-17T14:05:18+00:00"),
            note("regional_feeds", "ok", "2026-08-17T14:06:25+00:00"),
        ]
        found = rc.orphans(runs, now=NOW)
        self.assertEqual(sorted(f["source"] for f in found),
                         ["local_news", "regional_feeds"])
        for f in found:
            self.assertEqual(f["started_at"].date(), datetime(2026, 8, 16).date())

    def test_a_run_in_flight_right_now_is_not_an_orphan(self):
        """gdelt takes 6-8 minutes. Convicting it at minute two is noise."""
        started = NOW - timedelta(minutes=4)
        runs = [note("gdelt", "running", started.isoformat())]
        self.assertEqual(rc.orphans(runs, now=NOW), [])

    def test_the_grace_period_does_expire(self):
        started = NOW - (rc.GRACE + timedelta(minutes=1))
        runs = [note("gdelt", "running", started.isoformat())]
        found = rc.orphans(runs, now=NOW)
        self.assertEqual(len(found), 1)
        self.assertIsNone(found[0]["followed_by"])

    def test_old_incidents_age_out(self):
        """An orphan is a past incident. Permanent red with nothing to do is
        exactly the noise that hid Spirit (see ops_status MAX_AGE)."""
        old = NOW - (rc.WINDOW + timedelta(days=3))
        runs = [note("gdelt", "running", old.isoformat()),
                note("gdelt", "running", (old + timedelta(days=1)).isoformat())]
        self.assertEqual(rc.orphans(runs, now=NOW), [])

    def test_the_window_edge_is_inclusive(self):
        """Pinned so the boundary is a decision, not an accident."""
        inside = NOW - (rc.WINDOW - timedelta(minutes=1))
        outside = NOW - (rc.WINDOW + timedelta(minutes=1))
        self.assertEqual(
            len(rc.orphans([note("gdelt", "running", inside.isoformat())], now=NOW)), 1)
        self.assertEqual(
            rc.orphans([note("gdelt", "running", outside.isoformat())], now=NOW), [])

    def test_unparseable_timestamps_are_dropped_not_crashed(self):
        runs = DIED_MID_GDELT + [note("gdelt", "running", "not-a-date"), "junk"]
        self.assertEqual(len(rc.orphans(runs, now=NOW)), 1)


class Verdict(unittest.TestCase):

    def test_absent_telemetry_is_unknown_not_a_pass(self):
        lines, issue = rc.verdict_lines([], now=NOW)
        self.assertTrue(any("UNKNOWN" in l for l in lines))
        self.assertIn("Not a pass", " ".join(lines))
        self.assertIsNone(issue)

    def test_a_clean_window_passes_and_raises_nothing(self):
        lines, issue = rc.verdict_lines(ALL_PAIRED, now=NOW)
        self.assertTrue(any("PASS" in l for l in lines))
        self.assertIsNone(issue)

    def test_an_orphan_names_the_discriminator(self):
        """A session must be told how to tell a dead process from lost telemetry."""
        lines, issue = rc.verdict_lines(DIED_MID_GDELT, now=NOW)
        self.assertIsNotNone(issue)
        text = " ".join(lines)
        self.assertIn("spend_jobs.json", text)
        self.assertIn("gdelt", text)
        self.assertIn("RUNBOOK", text)


class RunningIsNotHealthy(unittest.TestCase):
    """Section [2] of ops_status must stop counting `running` as OK."""

    def test_ops_status_does_not_treat_running_as_ok(self):
        with open(os.path.join(RAILWAY, "ops_status.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('status == "running"', src,
                      "ops_status section [2] must handle `running` explicitly; "
                      "an orphaned running note carries a FRESH checked_at, so "
                      "falling through to the OK branch makes a dead collector "
                      "look maximally healthy and reset its own staleness clock")


if __name__ == "__main__":
    unittest.main()
