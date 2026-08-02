"""A date-keyed rotating cursor must never be scheduled more than once a day.

Root cause this pins (2026-07-30): `backfill.rotating_window()` chooses its month
with `months[now.toordinal() % len(months)]`, and `datetime.toordinal()` is the
ordinal of the DATE — the hour is not part of it. So the walker advances exactly
one month per calendar day at ANY cron cadence, and every extra run inside a UTC
day re-sweeps the window the previous run already finished.

That coupling is invisible: the worker looks stateless and idempotent (it is
both), the runs are all green, and the DATA stays correct because dedup catches
the re-posts. Only the bill moves. `edgar-history-sweep.yml` sat at `20 * * * *`
for a week on the belief that hourly meant 24x the progress; measured, it meant
22 runs/day pulling identical filing sets (the 22:40Z and 23:41Z runs both swept
2020-09 and both pulled the same 194 filings) and ~5,150 full-prompt extraction
calls/day where ~234 did all the work.

Contrast `historical-news-sweep.yml`, deliberately left hourly: its cursor is
SERVER-side and success-anchored, so it advances one window per RUN and cadence
does map to progress. The distinction this file enforces is exactly that — where
the cursor lives — not "backfills are slow".
"""
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# workflow file -> why its cursor cannot be advanced by running more often.
# Add an entry here whenever a worker derives its slice from the calendar date.
DATE_KEYED_WORKFLOWS = {
    "edgar-history-sweep.yml":
        "backfill.rotating_window() keys on now.toordinal() (a DATE ordinal), "
        "so all runs in one UTC day sweep the identical month window.",
}

CRON_RX = re.compile(r"^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]", re.M)


def _crons(workflow_name):
    text = (ROOT / ".github/workflows" / workflow_name).read_text()
    # Ignore commented-out schedules (a dormant cron is not a live cadence).
    live = "\n".join(l for l in text.splitlines()
                     if not l.lstrip().startswith("#"))
    return CRON_RX.findall(live)


def _fires_at_most_once_a_day(expr):
    """True when a 5-field cron expression fires at most once per calendar day.

    Requires a single concrete minute AND a single concrete hour. Anything that
    widens either field ('*', a step, a list, a range) can fire twice in a day.
    """
    fields = expr.split()
    if len(fields) != 5:
        return False
    minute, hour = fields[0], fields[1]
    return all(f.isdigit() for f in (minute, hour))


class RotatingWindowIsDateKeyedTests(unittest.TestCase):
    """The property that makes the cadence rule necessary, asserted directly."""

    def test_every_hour_of_one_day_returns_the_same_window(self):
        from backfill import rotating_window
        windows = {rotating_window(2015, datetime(2026, 7, 29, h, 30,
                                                 tzinfo=timezone.utc))[0]
                   for h in range(24)}
        self.assertEqual(
            len(windows), 1,
            "rotating_window is expected to be DATE-keyed; if this now varies "
            "by hour, an hourly cron is no longer pure waste and the cadence "
            "rule below should be revisited rather than silently kept.")

    def test_one_calendar_day_advances_the_cursor_at_most_one_step(self):
        # The cadence rule needs the cursor to move with the DATE and only with
        # the date. It does not need "exactly one month later" — that was the
        # old walk's shape, and it is what starved the recent past (see
        # RotatingWindowReachesRecentMonthsTests below).
        from backfill import rotating_window
        base = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)
        starts = [rotating_window(2015, base + timedelta(days=d))[0]
                  for d in range(6)]
        self.assertEqual(len(set(starts)), len(starts),
                         "consecutive days must not re-sweep the same month; "
                         f"got {[f'{s:%Y-%m}' for s in starts]}")


class RotatingWindowReachesRecentMonthsTests(unittest.TestCase):
    """The sweep's whole promise is that any gap self-fills. Assert that.

    Measured 2026-08-01: the previous `months[now.toordinal() % len(months)]`
    had NEVER swept 2026-01..2026-06 in a three-year lookback, and 2025-11/12
    were 235 days stale — because `len(months)` grows by one each calendar
    month, so the moving wrap-point keeps jumping past the newest entries. The
    daily cron only searches a 2-day window, so this sweep is the ONLY way a
    past month is ever re-searched with an improved keyword list. When it never
    reaches the recent past, a coverage fix can never apply to it.
    """

    def _swept(self, days, anchor=2015, end=datetime(2026, 8, 1, tzinfo=timezone.utc)):
        from backfill import rotating_month
        return [rotating_month(anchor, end - timedelta(days=d))
                for d in range(days)]

    def test_every_recent_month_is_re_verified_within_a_bounded_window(self):
        # The window a regression would have to beat: a month that has been in
        # the rotation for a year must have been swept inside the last 120 days.
        swept = set(self._swept(120))
        end = datetime(2026, 8, 1, tzinfo=timezone.utc)
        expected = []
        y, m = end.year, end.month
        for _ in range(12):
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
            expected.append((y, m))
        missing = [f"{y}-{m:02d}" for y, m in expected if (y, m) not in swept]
        self.assertEqual(
            missing, [],
            f"the rotating sweep did not re-verify {missing} in 120 days. "
            f"Recent months are where new filings land and where a widened "
            f"search has to be replayed; starving them is how 29 verified SEC "
            f"Item 2.05 filings stayed missing for a year.")

    def test_the_deep_history_still_gets_walked(self):
        # Recency priority must not become recency-only: the anchor year has to
        # keep coming round, or "self-completing backfill" stops being true.
        swept = set(self._swept(500))
        self.assertTrue(
            any(y == 2015 for y, _ in swept),
            "no 2015 month swept in 500 days — the history walk has stalled")
        self.assertGreaterEqual(
            len(swept), 100,
            f"only {len(swept)} distinct months swept in 500 runs; the walk "
            f"should cover most of the rotation in that time")

    def test_the_month_chosen_is_always_inside_the_rotation(self):
        from backfill import rotating_month
        for d in range(400):
            now = datetime(2026, 8, 1, tzinfo=timezone.utc) - timedelta(days=d)
            y, m = rotating_month(2015, now)
            self.assertGreaterEqual((y, m), (2015, 1), f"{y}-{m} precedes anchor")
            self.assertLessEqual((y, m), (now.year, now.month),
                                 f"{y}-{m} is in the future for {now:%Y-%m-%d}")


class DateKeyedCronCadenceTests(unittest.TestCase):

    def test_date_keyed_workflows_run_at_most_once_a_day(self):
        for name, why in DATE_KEYED_WORKFLOWS.items():
            crons = _crons(name)
            self.assertTrue(crons, f"{name}: no live cron found to check")
            for expr in crons:
                self.assertTrue(
                    _fires_at_most_once_a_day(expr),
                    f"{name} is scheduled '{expr}', which can fire more than "
                    f"once a calendar day. {why} Extra runs buy zero additional "
                    f"coverage and re-spend the LLM budget on filings the "
                    f"earlier run already extracted. If a sprint genuinely "
                    f"needs to close faster, move the cursor off the calendar "
                    f"date first.")

    def test_helper_recognises_widened_minute_and_hour_fields(self):
        for expr in ("20 5 * * *", "0 13 1 * *", "0 15 7 1,4,7,10 *"):
            self.assertTrue(_fires_at_most_once_a_day(expr), expr)
        for expr in ("20 * * * *", "*/10 5 * * *", "20 5,17 * * *",
                     "20 */6 * * *", "20 0-6 * * *", "20 5 * *"):
            self.assertFalse(_fires_at_most_once_a_day(expr), expr)

    def test_commented_out_schedules_are_not_read_as_live(self):
        # foreign-filings.yml is deliberately retired with its cron commented
        # out; the parser must not resurrect it as a live cadence.
        self.assertEqual(_crons("foreign-filings.yml"), [])


class ServerCursorSweepStaysHourlyTests(unittest.TestCase):
    """Guards the deliberate exception, so a later cleanup does not "fix" it."""

    def test_historical_news_sweep_is_daily_and_says_what_bought_the_slowdown(self):
        """Reverted to daily on 2026-08-02, on YIELD rather than on cost.

        The hourly sprint was correctly designed and correctly cheap: the
        cursor is server-side, cadence maps 1:1 to progress, and the header's
        ~$0.18/day was about right. What nobody had counted was rows per call.
        Twelve consecutive runs spent 120 model extractions to store ONE row,
        so the remaining ~285 windows were ~2,850 calls for ~24 rows, proposed
        against an account with about three days of credit left.

        This pins the cadence AND the reasoning, because a bare cron line
        invites someone to "restore" the sprint from the old header without
        the measurement that retired it.
        """
        text = (ROOT / ".github/workflows/historical-news-sweep.yml").read_text()
        self.assertIn("40 5 * * *", text,
                      "historical-news-sweep is daily. Re-arming the hourly "
                      "sprint is a real decision, but measure stored rows per "
                      "extraction first and update this test, the cadence note "
                      "and the remaining-work numbers together.")
        self.assertNotIn("- cron: '40 * * * *'", text,
                         "the hourly schedule is retired, not commented beside "
                         "the daily one where a paste can revive it")
        self.assertIn("historical-gdelt-cursor", text,
                      "cadence maps 1:1 to progress only because the cursor is "
                      "server-side; the header must keep naming the endpoint "
                      "that makes that checkable, at any cadence.")
        self.assertIn("120 model extractions", text,
                      "the measurement that bought the slowdown has to stay "
                      "next to the schedule it changed")

    def test_dispatch_window_description_matches_the_scripts_limit(self):
        # historical_news_sweep raises unless (end - start) < WINDOW_DAYS, so the
        # form's own hint has to agree with that or a by-the-book dispatch fails.
        # Read the description VALUE, not the file: the surrounding comment
        # legitimately quotes the old wrong number, and an earlier version of
        # this assertion tripped on that comment.
        import historical_news_sweep as hns
        text = (ROOT / ".github/workflows/historical-news-sweep.yml").read_text()
        self.assertEqual(hns.WINDOW_DAYS, 7)
        descriptions = re.findall(r"^\s*description:\s*'([^']*)'", text, re.M)
        end_hints = [d for d in descriptions if "after start" in d]
        self.assertEqual(len(end_hints), 1, descriptions)
        self.assertIn(f"max {hns.WINDOW_DAYS - 1} days", end_hints[0])


if __name__ == "__main__":
    unittest.main()
