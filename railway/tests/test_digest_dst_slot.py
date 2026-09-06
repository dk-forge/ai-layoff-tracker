"""The digest's schedule must be the same WALL CLOCK all year round.

The owner asked for the daily digest at 6:00 AM Eastern and the weekly
look-back at 7:30 AM Eastern on Mondays. GitHub cron is UTC and has no notion
of daylight saving, so a single fixed line is right for eight months and an
hour early for the other four, with nothing anywhere reporting the drift.

Both candidate UTC ticks are scheduled and railway/digest_slot.py decides which
one is real today. A guard nobody tested across the boundary is the bug with
extra steps, so the boundary is tested here, on real dates, from BOTH sides:

  2026-10-31  EDT is still in force. 10:00 UTC sends, 11:00 UTC skips.
  2026-11-02  EST is in force (the change is 2026-11-01). 11:00 UTC sends,
              10:00 UTC skips. It is also a Monday, so both weekly ticks are
              asserted the same way.

Every assertion below states both sides. "The right one fires" is half a test:
a guard that let both fire would pass it and mail everybody twice.
"""
import datetime
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import digest_send  # noqa: E402
import digest_slot  # noqa: E402

DAILY_EDT = "0 10 * * *"
DAILY_EST = "0 11 * * *"
WEEKLY_EDT = "30 11 * * 1"
WEEKLY_EST = "30 12 * * 1"
MONTHLY_EDT = "0 13 1 * *"
MONTHLY_EST = "0 14 1 * *"
ALL_CRONS = (DAILY_EDT, DAILY_EST, WEEKLY_EDT, WEEKLY_EST, MONTHLY_EDT, MONTHLY_EST)

# The six lines exactly as digest-send.yml carries them. If that file changes,
# this list has to change with it and the parity test below says so.
WORKFLOW = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", ".github", "workflows", "digest-send.yml"))


def tier(cron, iso_date):
    y, m, d = (int(p) for p in iso_date.split("-"))
    return digest_slot.tier_for_cron(cron, datetime.date(y, m, d))[0]


class TheWorkflowSchedulesBothCandidatesForEverySlot(unittest.TestCase):
    def test_all_six_cron_lines_are_present(self):
        import re
        text = open(WORKFLOW, encoding="utf-8").read()
        crons = re.findall(r"^\s*-\s*cron:\s*'([^']+)'", text, re.M)
        self.assertEqual(sorted(crons), sorted(ALL_CRONS),
                         "the DST guard only works if BOTH candidate ticks for "
                         "each slot are actually scheduled. One of them missing "
                         "means no digest at all for half the year.")

    def test_every_scheduled_line_resolves_to_a_tier_on_some_day_of_the_year(self):
        """No cron line may be dead. A tick that never matches is a typo."""
        day = datetime.date(2026, 1, 1)
        for cron in ALL_CRONS:
            hits = sum(1 for i in range(365)
                       if digest_slot.tier_for_cron(cron, day + datetime.timedelta(days=i))[0])
            self.assertGreater(hits, 0, f"cron '{cron}' never sends anything")


class TheDaylightSavingBoundary(unittest.TestCase):
    """2026-11-01 is when US Eastern falls back. Both sides, both ticks."""

    def test_the_saturday_before_the_change_is_still_edt(self):
        self.assertEqual(tier(DAILY_EDT, "2026-10-31"), "daily",
                         "10:00 UTC is 06:00 EDT on 2026-10-31 and must send")
        self.assertIsNone(tier(DAILY_EST, "2026-10-31"),
                          "11:00 UTC is 07:00 EDT on 2026-10-31 and must skip; "
                          "letting it through sends the digest twice")

    def test_the_monday_after_the_change_is_est(self):
        self.assertEqual(tier(DAILY_EST, "2026-11-02"), "daily",
                         "11:00 UTC is 06:00 EST on 2026-11-02 and must send")
        self.assertIsNone(tier(DAILY_EDT, "2026-11-02"),
                          "10:00 UTC is 05:00 EST on 2026-11-02 - an hour early, "
                          "which is exactly the silent drift this guard exists "
                          "to prevent - and must skip")

    def test_the_weekly_slot_crosses_the_boundary_the_same_way(self):
        # 2026-11-02 is a Monday, so both weekly ticks are live candidates.
        self.assertEqual(tier(WEEKLY_EST, "2026-11-02"), "weekly",
                         "12:30 UTC is 07:30 EST and must send the look-back")
        self.assertIsNone(tier(WEEKLY_EDT, "2026-11-02"),
                          "11:30 UTC is 06:30 EST - not the slot - and must skip")
        # 2026-10-26 is the Monday before the change, still EDT.
        self.assertEqual(tier(WEEKLY_EDT, "2026-10-26"), "weekly")
        self.assertIsNone(tier(WEEKLY_EST, "2026-10-26"))

    def test_the_monthly_slot_on_the_fall_back_day_itself(self):
        """2026-11-01 is BOTH the fall-back Sunday and the 1st of a month.

        The clocks go back at 02:00 local, so by 13:00 UTC New York is already
        on EST: 13:00 UTC is 08:00 EST (an hour early, must skip) and 14:00 UTC
        is 09:00 EST (the slot, must send). The 1st of October, still EDT, is
        the other way round. Both sides, both ticks, on the one date where the
        monthly slot meets the transition.
        """
        self.assertEqual(tier(MONTHLY_EST, "2026-11-01"), "monthly",
                         "14:00 UTC is 09:00 EST on 2026-11-01 and must send")
        self.assertIsNone(tier(MONTHLY_EDT, "2026-11-01"),
                          "13:00 UTC is 08:00 EST on 2026-11-01 - an hour early "
                          "- and must skip; letting it through mails the "
                          "monthly twice")
        self.assertEqual(tier(MONTHLY_EDT, "2026-10-01"), "monthly")
        self.assertIsNone(tier(MONTHLY_EST, "2026-10-01"))
        # 2027-03-01 is before the spring-forward (2027-03-14): EST.
        self.assertEqual(tier(MONTHLY_EST, "2027-03-01"), "monthly")
        self.assertIsNone(tier(MONTHLY_EDT, "2027-03-01"))
        # 2027-04-01 is after it: EDT.
        self.assertEqual(tier(MONTHLY_EDT, "2027-04-01"), "monthly")
        self.assertIsNone(tier(MONTHLY_EST, "2027-04-01"))

    def test_the_spring_boundary_too(self):
        """2027-03-14 is the spring-forward. The same pairing must hold."""
        self.assertEqual(tier(DAILY_EST, "2027-03-13"), "daily")
        self.assertIsNone(tier(DAILY_EDT, "2027-03-13"))
        self.assertEqual(tier(DAILY_EDT, "2027-03-15"), "daily")
        self.assertIsNone(tier(DAILY_EST, "2027-03-15"))


class ExactlyOneTickSendsOnEveryDayOfTheYear(unittest.TestCase):
    """The property that matters, swept rather than sampled.

    Two ticks firing is two emails to every subscriber, which is the fastest
    way onto a spam list. Zero ticks firing is an edition nobody receives. Both
    are checked here for every day of a year that contains both transitions.
    """

    def test_the_daily_slot_fires_exactly_once_a_day(self):
        day = datetime.date(2026, 6, 1)
        for i in range(400):
            d = day + datetime.timedelta(days=i)
            fired = [c for c in (DAILY_EDT, DAILY_EST)
                     if digest_slot.tier_for_cron(c, d)[0] == "daily"]
            self.assertEqual(len(fired), 1,
                             f"{d}: {len(fired)} daily tick(s) fired, want exactly 1")

    def test_the_weekly_slot_fires_exactly_once_on_a_monday_and_never_otherwise(self):
        day = datetime.date(2026, 6, 1)
        for i in range(400):
            d = day + datetime.timedelta(days=i)
            fired = [c for c in (WEEKLY_EDT, WEEKLY_EST)
                     if digest_slot.tier_for_cron(c, d)[0] == "weekly"]
            # The cron lines themselves are Monday-only, so on other days these
            # ticks do not exist; the guard must still refuse them if they did.
            want = 1 if d.isoweekday() == 1 else 0
            self.assertEqual(len(fired), want,
                             f"{d}: {len(fired)} weekly tick(s) fired, want {want}")

    def test_the_monthly_slot_fires_exactly_once_on_the_first_and_never_otherwise(self):
        """The 1st of every month, once; every other day of the month, never.

        The cron lines are day-of-month 1, so on other days these ticks do not
        exist; the guard must still refuse them if they did (a hand-set
        DIGEST_CRON, or a workflow edit that widened the day field).
        """
        day = datetime.date(2026, 6, 1)
        firsts = 0
        for i in range(400):
            d = day + datetime.timedelta(days=i)
            fired = [c for c in (MONTHLY_EDT, MONTHLY_EST)
                     if digest_slot.tier_for_cron(c, d)[0] == "monthly"]
            want = 1 if d.day == 1 else 0
            firsts += want
            self.assertEqual(len(fired), want,
                             f"{d}: {len(fired)} monthly tick(s) fired, want {want}")
        self.assertEqual(firsts, 14, "400 days from 2026-06-01 hold 14 firsts")

    def test_no_tick_resolves_to_another_slots_tier(self):
        day = datetime.date(2026, 6, 1)
        pairs = {"daily": (DAILY_EDT, DAILY_EST),
                 "weekly": (WEEKLY_EDT, WEEKLY_EST),
                 "monthly": (MONTHLY_EDT, MONTHLY_EST)}
        for i in range(400):
            d = day + datetime.timedelta(days=i)
            for own, crons in pairs.items():
                for c in crons:
                    got = digest_slot.tier_for_cron(c, d)[0]
                    self.assertIn(got, (own, None),
                                  f"{d}: cron '{c}' resolved to {got!r}, "
                                  f"which is not its own {own} slot")


class TheGuardIsJudgedOnTheSCHEDULEDTimeNotTheClock(unittest.TestCase):
    """A run GitHub delayed must still know which slot it is.

    GitHub delays scheduled runs, sometimes past the hour. A guard reading
    datetime.now() would reject a delayed 10:00 UTC tick AND the 11:00 UTC
    tick that fired on time, and the day's digest would silently not go out
    with two green runs behind it.
    """

    def test_the_decision_does_not_read_the_wall_clock(self):
        src = open(os.path.join(os.path.dirname(digest_slot.__file__),
                                "digest_slot.py"), encoding="utf-8").read()
        body = src.split('"""', 2)[-1]
        self.assertNotIn("datetime.now", body.replace(
            "datetime.datetime.now(datetime.timezone.utc).date()", ""),
            "the guard must derive the slot from the cron line it was given, "
            "not from the moment the runner happened to start")

    def test_a_delayed_run_still_resolves_its_own_slot(self):
        # Same cron, judged for the same UTC date, regardless of when the
        # process actually started. Both calls below are the delayed run.
        self.assertEqual(tier(DAILY_EDT, "2026-10-31"), "daily")
        self.assertEqual(tier(DAILY_EST, "2026-11-02"), "daily")


class TheSkipIsFreeAndGreen(unittest.TestCase):
    """A no-op tick must touch nothing at all, and must exit 0.

    Reading a recipient, proving the credential or stamping a health row on a
    tick that is not ours would make the extra schedule expensive, and the
    stamp would be worse than expensive: it would refresh `checked_at` daily
    and hide a sender that had stopped.
    """

    def _run(self, env):
        relay = mock.Mock(name="transport", sends=True)
        relay.verify.return_value = digest_send.CredentialCheck(
            digest_send.OK, "stub", "accepted")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(relay, "stub transport")) as transport, \
                mock.patch.object(digest_send, "sender_identity",
                                  return_value=("a@b.invalid", "")), \
                mock.patch.object(digest_send, "_record_health") as health, \
                mock.patch.object(digest_send, "_run_tier",
                                  return_value={"code": 0, "sent": 0, "failed": 0,
                                                "detail": "", "not_sent": "",
                                                "preview": False, "test": False,
                                                "halt": False}) as tier_pass, \
                mock.patch.object(digest_send, "_call") as call:
            code = digest_send.main()
        return code, transport, health, tier_pass, call

    def test_a_tick_that_is_not_ours_exits_zero_having_done_nothing(self):
        env = {"WP_SITE_URL": "https://example.invalid/blog", "WP_API_KEY": "k",
               "DIGEST_CRON": DAILY_EST}
        with mock.patch.object(digest_send, "_today",
                               return_value=datetime.date(2026, 10, 31)):
            code, transport, health, tier_pass, call = self._run(env)
        self.assertEqual(code, 0, "a skipped tick is the schedule working, not a failure")
        transport.assert_not_called()
        health.assert_not_called()
        tier_pass.assert_not_called()
        call.assert_not_called()

    def test_the_tick_that_IS_ours_gets_as_far_as_the_transport(self):
        env = {"WP_SITE_URL": "https://example.invalid/blog", "WP_API_KEY": "k",
               "DIGEST_CRON": DAILY_EDT}
        with mock.patch.object(digest_send, "_today",
                               return_value=datetime.date(2026, 10, 31)):
            code, transport, health, tier_pass, call = self._run(env)
        transport.assert_called()


class TheSlotDecisionsPrecedence(unittest.TestCase):
    def test_an_explicit_freq_beats_the_cron_guard(self):
        """workflow_dispatch names a tier; a human asked, so nothing is skipped."""
        freqs, skip = digest_send.slot_decision(
            {"DIGEST_FREQ": "weekly", "DIGEST_CRON": DAILY_EST},
            datetime.date(2026, 10, 31))
        self.assertEqual(freqs, ("weekly",))
        self.assertFalse(skip)

    def test_no_cron_at_all_keeps_the_old_day_of_week_behaviour(self):
        monday = datetime.date(2026, 8, 17)
        self.assertEqual(digest_send.slot_decision({}, monday)[0], ("daily", "weekly"))
        self.assertEqual(
            digest_send.slot_decision({}, monday + datetime.timedelta(days=1))[0],
            ("daily",))

    def test_no_cron_on_the_first_adds_the_monthly_after_the_others(self):
        # 2026-06-01 is a Monday and the 1st: all three, in send order.
        self.assertEqual(digest_send.slot_decision({}, datetime.date(2026, 6, 1))[0],
                         ("daily", "weekly", "monthly"))
        # 2026-10-01 is a Thursday and the 1st.
        self.assertEqual(digest_send.slot_decision({}, datetime.date(2026, 10, 1))[0],
                         ("daily", "monthly"))

    def test_an_explicit_monthly_freq_forces_that_tier_on_any_day(self):
        freqs, skip = digest_send.slot_decision(
            {"DIGEST_FREQ": "monthly", "DIGEST_CRON": DAILY_EST},
            datetime.date(2026, 10, 31))
        self.assertEqual(freqs, ("monthly",))
        self.assertFalse(skip)

    def test_the_forceable_tiers_are_exactly_the_scheduled_ones(self):
        self.assertEqual(digest_send.TIERS, ("daily", "weekly", "monthly"))

    def test_an_unreadable_cron_falls_forward_and_never_skips(self):
        """An unreadable schedule must not become a missed edition.

        The per-period guard on the site absorbs a duplicate attempt; nothing
        absorbs an email that was never sent.
        """
        for bad in ("", "nonsense", "*/5 * * * *", "0 H * * *"):
            freqs, skip = digest_send.slot_decision(
                {"DIGEST_CRON": bad}, datetime.date(2026, 10, 31))
            self.assertFalse(skip, f"cron {bad!r} caused a silent skip")
            self.assertIn("daily", freqs)


class TheWeeklySlotHasItsOwnLivenessRow(unittest.TestCase):
    """The price of splitting the schedule, and it must actually be paid.

    Once the daily tier has its own 6:00 slot it stamps `digest_mailer` every
    morning, so that row is green whatever the weekly tier does. A weekly slot
    that stopped firing is only visible through a row a weekly pass writes.
    """

    def test_a_completed_weekly_pass_stamps_digest_weekly(self):
        with mock.patch("source_health.report_source_health") as rep:
            digest_send._record_weekly_liveness(
                {"detail": "weekly: 12 sent of 12 eligible", "not_sent": "",
                 "code": 0, "sent": 12, "preview": False, "test": False})
        rep.assert_called_once()
        self.assertEqual(rep.call_args[0][0], "digest_weekly")
        self.assertEqual(rep.call_args[0][1], "ok")

    def test_a_weekly_pass_that_did_not_send_is_degraded_not_ok(self):
        with mock.patch("source_health.report_source_health") as rep:
            digest_send._record_weekly_liveness(
                {"detail": "", "not_sent": "weekly: NOT SENT, HTTP 503",
                 "code": 3, "sent": 0, "preview": False, "test": False})
        self.assertEqual(rep.call_args[0][1], "degraded")

    def test_a_preview_or_a_test_send_stamps_nothing(self):
        for flag in ("preview", "test"):
            with mock.patch("source_health.report_source_health") as rep:
                digest_send._record_weekly_liveness(
                    {"detail": "", "not_sent": "", "code": 0, "sent": 1,
                     "preview": flag == "preview", "test": flag == "test"})
            rep.assert_not_called()

    def test_ops_status_fails_on_a_stale_weekly_row(self):
        import ops_status
        stale = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=12)).isoformat()
        fresh = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=3)).isoformat()
        lines, bad = ops_status.weekly_digest_lines(
            {"digest_weekly": {"status": "ok", "checked_at": stale, "detail": "x"}})
        self.assertTrue(bad, "a weekly slot 12 days silent must raise an issue")
        self.assertIn("STALE", " ".join(lines))
        lines, bad = ops_status.weekly_digest_lines(
            {"digest_weekly": {"status": "ok", "checked_at": fresh, "detail": "x"}})
        self.assertFalse(bad)
        # Absence is UNKNOWN, never a pass and never a fault.
        for absent in ({}, None, {"digest_weekly": {"status": "ok"}}):
            lines, bad = ops_status.weekly_digest_lines(absent)
            self.assertFalse(bad)
            self.assertIn("UNKNOWN", " ".join(lines))

    def test_a_completed_monthly_pass_stamps_digest_monthly_and_nothing_else(self):
        with mock.patch("source_health.report_source_health") as rep:
            digest_send._record_monthly_liveness(
                {"detail": "monthly: 3 sent of 3 eligible", "not_sent": "",
                 "code": 0, "sent": 3, "preview": False, "test": False})
        rep.assert_called_once()
        self.assertEqual(rep.call_args[0][0], "digest_monthly")
        self.assertEqual(rep.call_args[0][1], "ok")
        for flag in ("preview", "test"):
            with mock.patch("source_health.report_source_health") as rep:
                digest_send._record_monthly_liveness(
                    {"detail": "", "not_sent": "", "code": 0, "sent": 1,
                     "preview": flag == "preview", "test": flag == "test"})
            rep.assert_not_called()

    def test_ops_status_fails_on_a_stale_monthly_row_and_absence_is_unknown(self):
        import ops_status
        stale = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=40)).isoformat()
        fresh = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=30)).isoformat()
        lines, bad = ops_status.monthly_digest_lines(
            {"digest_monthly": {"status": "ok", "checked_at": stale, "detail": "x"}})
        self.assertTrue(bad, "a monthly slot 40 days silent must raise an issue")
        self.assertIn("STALE", " ".join(lines))
        lines, bad = ops_status.monthly_digest_lines(
            {"digest_monthly": {"status": "ok", "checked_at": fresh, "detail": "x"}})
        self.assertFalse(bad, "a 30-day-old monthly row is a healthy month")
        for absent in ({}, None, {"digest_monthly": {"status": "ok"}}):
            lines, bad = ops_status.monthly_digest_lines(absent)
            self.assertFalse(bad)
            self.assertIn("UNKNOWN", " ".join(lines))

    def test_the_ceiling_matches_the_monthly_cadence_in_both_monitors(self):
        import ops_status
        import health_digest
        self.assertEqual(ops_status.MONTHLY_DIGEST_MAX_AGE_DAYS, 35)
        self.assertEqual(health_digest.MAX_AGE_DAYS["digest_monthly"], 35)
        self.assertGreater(health_digest.MAX_AGE_DAYS["digest_monthly"], 31,
                           "a ceiling tighter than the longest month is "
                           "permanent noise, not a monitor")

    def test_the_ceiling_matches_the_weekly_cadence_in_both_monitors(self):
        import ops_status
        import health_digest
        self.assertEqual(ops_status.WEEKLY_DIGEST_MAX_AGE_DAYS, 9)
        self.assertEqual(health_digest.MAX_AGE_DAYS["digest_weekly"], 9)
        self.assertGreater(health_digest.MAX_AGE_DAYS["digest_weekly"], 7,
                           "a ceiling tighter than the job's own cadence is "
                           "permanent noise, not a monitor")


if __name__ == "__main__":
    unittest.main()
