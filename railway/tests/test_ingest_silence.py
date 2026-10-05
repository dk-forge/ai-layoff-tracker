"""Both ingest hosts off must not go silent for a week again.

2026-09: Railway's cron was retired and ALT_INGEST_ON_VPS was never set, so no
collector ran for seven days and every monitor stayed green, because a pipeline
that never starts leaves nothing to pair (run_completion) and nothing to judge
(source_freshness). These tests pin the alarm that asks "did anything run?".
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import ingest_silence as s  # noqa: E402

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def note(at, status="ok", source="gdelt"):
    return {"source": source, "status": status, "attempted_at": at}


class IngestSilenceTest(unittest.TestCase):
    def test_no_runs_at_all_is_an_alarm_not_a_pass(self):
        ok, line = s.verdict([], now=NOW)
        self.assertFalse(ok)
        self.assertIn("ALT_INGEST_ON_VPS", line)

    def test_seven_day_gap_like_the_incident_alarms(self):
        ok, _ = s.verdict([note("2026-09-28T22:05:00Z")], now=NOW)
        self.assertFalse(ok)

    def test_just_over_two_days_alarms(self):
        at = (NOW - timedelta(days=2, minutes=1)).isoformat()
        self.assertFalse(s.verdict([note(at)], now=NOW)[0])

    def test_last_nights_run_is_fine(self):
        ok, _ = s.verdict([note("2026-10-04T22:07:00Z")], now=NOW)
        self.assertTrue(ok)

    def test_an_orphaned_running_note_still_counts_as_activity(self):
        # A run that started is not silence; run_completion owns orphans.
        self.assertTrue(s.verdict([note("2026-10-04T22:07:00Z", "running")], now=NOW)[0])

    def test_newest_wins_and_garbage_rows_are_ignored(self):
        rows = ["junk", {"attempted_at": "not a date"},
                note("2026-09-20T22:00:00Z"), note("2026-10-04T22:00:00Z")]
        self.assertEqual(s.newest_run(rows), datetime(2026, 10, 4, 22, 0, tzinfo=timezone.utc))
        self.assertTrue(s.verdict(rows, now=NOW)[0])

    def test_threshold_is_two_days(self):
        self.assertEqual(s.MAX_SILENCE, timedelta(days=2))


if __name__ == "__main__":
    unittest.main()
