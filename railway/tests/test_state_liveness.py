"""A mechanism that stopped running does not raise; it stops changing its file.

These pin `railway/state_liveness.py`. The properties that matter are not "does
it find things" but "does it stay quiet about the things that are FINE" --
because the first cut of that module called `alert_outbox.json` STALE at nine
days, and nine quiet days in the undeliverable-alert outbox is the single best
thing it could report. A check that manufactures an alarm out of good news gets
widened until it says nothing, which is the disease it was written to cure.
"""
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import state_liveness as sl  # noqa: E402


TODAY = date(2026, 8, 28)


def days_ago(n):
    return TODAY - timedelta(days=n)


class AMechanismThatNeverRan(unittest.TestCase):
    """The loudest signal, and the one that needs no history."""

    def test_one_commit_past_the_grace_is_NEVER_USED(self):
        row = sl.judge_file("railway/x.json",
                            [days_ago(sl.GRACE_DAYS + 1)], today=TODAY)
        self.assertEqual(row["state"], sl.NEVER_USED)

    def test_one_commit_inside_the_grace_is_UNKNOWN_not_a_pass(self):
        row = sl.judge_file("railway/x.json", [days_ago(1)], today=TODAY)
        self.assertEqual(row["state"], sl.UNKNOWN)
        self.assertNotEqual(row["state"], sl.LIVE)

    def test_NEVER_USED_is_the_only_state_a_human_must_act_on(self):
        rows = [
            sl.judge_file("railway/dead.json", [days_ago(40)], today=TODAY),
            sl.judge_file("railway/thin.json", [days_ago(1), days_ago(2)], today=TODAY),
        ]
        self.assertEqual([r["path"] for r in sl.problems(rows)], ["railway/dead.json"])

    def test_an_event_driven_file_can_still_be_NEVER_USED(self):
        # Quiet is healthy there, but never having run at all is not quiet.
        path = next(iter(sl.EVENT_DRIVEN))
        row = sl.judge_file(path, [days_ago(40)], today=TODAY)
        self.assertEqual(row["state"], sl.NEVER_USED)


class SilenceIsHealthyForAnEventDrivenFile(unittest.TestCase):
    """THE false alarm this module shipped with, and must never ship again."""

    def test_a_long_quiet_outbox_is_LIVE_not_STALE(self):
        dates = [days_ago(9), days_ago(10), days_ago(11), days_ago(12), days_ago(13)]
        row = sl.judge_file("railway/alert_outbox.json", dates, today=TODAY)
        self.assertEqual(row["state"], sl.LIVE,
                         "nine quiet days in the undeliverable-alert outbox means "
                         "nothing failed, which is good news, not staleness")

    def test_every_event_driven_file_is_exempt_from_staleness(self):
        dates = [days_ago(30 + i) for i in range(6)]
        for path in sl.EVENT_DRIVEN:
            with self.subTest(path=path):
                self.assertEqual(sl.judge_file(path, dates, today=TODAY)["state"],
                                 sl.LIVE)

    def test_the_event_driven_set_is_not_empty(self):
        # A future edit that empties it would silently restore the false alarm.
        self.assertTrue(sl.EVENT_DRIVEN)


class AHeartbeatFileIsJudgedOnItsOwnCadence(unittest.TestCase):
    def test_a_writer_that_stopped_is_STALE(self):
        dates = [days_ago(20 + i) for i in range(8)]  # daily, then nothing for 20d
        row = sl.judge_file("railway/spend_jobs.json", dates, today=TODAY)
        self.assertEqual(row["state"], sl.STALE)

    def test_one_skipped_run_is_not_STALE(self):
        # A twice-daily file has a ~1d gap history; without MIN_STALE_DAYS a
        # single skipped run would read as a fault.
        dates = [days_ago(2 + i) for i in range(10)]
        row = sl.judge_file("railway/spend_jobs.json", dates, today=TODAY)
        self.assertEqual(row["state"], sl.LIVE)

    def test_the_floor_is_what_holds_that(self):
        self.assertGreaterEqual(sl.MIN_STALE_DAYS, 4)

    def test_too_few_commits_is_UNKNOWN_never_LIVE(self):
        dates = [days_ago(1), days_ago(3), days_ago(5)]
        row = sl.judge_file("railway/spend_jobs.json", dates, today=TODAY)
        self.assertEqual(row["state"], sl.UNKNOWN)

    def test_no_history_at_all_is_UNKNOWN_never_LIVE(self):
        row = sl.judge_file("railway/spend_jobs.json", [], today=TODAY)
        self.assertEqual(row["state"], sl.UNKNOWN)


class ExemptionIsDECLAREDByAHuman(unittest.TestCase):
    """Mirrors source_state's UNAVAILABLE: exempt because someone said why."""

    def test_a_declared_manual_file_never_alarms(self):
        path = next(iter(sl.MANUAL_FILES))
        row = sl.judge_file(path, [days_ago(90)], today=TODAY)
        self.assertEqual(row["state"], sl.MANUAL)
        self.assertEqual(sl.problems([row]), [])

    def test_every_declaration_carries_a_reviewer_a_date_and_a_reason(self):
        for path, entry in sl.MANUAL_FILES.items():
            with self.subTest(path=path):
                for field in ("reviewer", "date", "reason"):
                    self.assertTrue(str(entry.get(field, "")).strip(),
                                    f"{path} is exempt with no {field}")

    def test_an_undeclared_file_is_NOT_exempt(self):
        row = sl.judge_file("railway/undeclared.json", [days_ago(40)], today=TODAY)
        self.assertEqual(row["state"], sl.NEVER_USED)


class TheRegistryItselfIsChecked(unittest.TestCase):
    def test_the_watch_list_is_not_empty(self):
        self.assertTrue(sl.WATCHED_FILES)

    def test_test_fixtures_are_not_reported_as_mechanism_state(self):
        # A frozen fixture is supposed to be frozen; reporting one is noise,
        # and noise is how a real finding gets scrolled past.
        for path in sl.unregistered_state_files():
            self.assertNotIn("/tests/", path)

    def test_the_live_repo_has_no_NEVER_USED_state_file(self):
        # The end-to-end read. If this fails, a mechanism in THIS repo shipped
        # and has never once written its own state.
        rows = sl.collect()
        dead = [r["path"] for r in sl.problems(rows)]
        self.assertEqual(dead, [], f"mechanism(s) that never ran: {dead}")


if __name__ == "__main__":
    unittest.main()
