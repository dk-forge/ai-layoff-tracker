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

    def test_consecutive_days_advance_exactly_one_month(self):
        from backfill import rotating_window
        base = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)
        starts = [rotating_window(2015, base + timedelta(days=d))[0]
                  for d in range(4)]
        for earlier, later in zip(starts, starts[1:]):
            months = (later.year - earlier.year) * 12 + later.month - earlier.month
            self.assertEqual(months, 1,
                             f"{earlier:%Y-%m} -> {later:%Y-%m} is not one month")


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

    def test_historical_news_sweep_documents_why_it_is_hourly(self):
        text = (ROOT / ".github/workflows/historical-news-sweep.yml").read_text()
        self.assertIn("40 * * * *", text,
                      "historical-news-sweep was reverted to a slower cadence; "
                      "that is a real decision, but update this test and the "
                      "header's remaining-work numbers together.")
        self.assertIn("historical-gdelt-cursor", text,
                      "the justification for hourly is that this job's cursor "
                      "is server-side and advances per RUN; the header must "
                      "keep naming the endpoint that makes that checkable.")

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
