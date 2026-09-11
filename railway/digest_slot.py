"""Which digest tier, if any, a scheduled tick is supposed to send.

WHY THIS FILE EXISTS AT ALL.

The owner asked for the daily digest at 6:00 AM Eastern every day and the
weekly look-back at 7:30 AM Eastern on Mondays. The monthly edition (armed
2026-09-06) goes out at 9:00 AM Eastern on the 1st of the month, the wall clock
reading of the signup's own promise "at the start of each month". GitHub cron
is UTC and knows
nothing about daylight saving, so a single fixed cron line is correct for
about eight months of the year and quietly an hour wrong for the other four.
On 2026-11-01 a `0 10 * * *` line stops being 6:00 AM in New York and becomes
5:00 AM, and nothing anywhere would say so: the run is green, the email goes
out, it is simply an hour earlier than the person who asked for it wanted.
A schedule that drifts silently is the same class of defect as a health check
that resolves to a silent pass.

THE MECHANISM.

Both candidate UTC hours are scheduled, and this module decides which of them
is the real one TODAY. 6:07 ET is 10:07 UTC under EDT and 11:07 UTC under EST;
7:37 ET is 11:37 UTC under EDT and 12:37 UTC under EST; 9:07 ET is 13:07 UTC
under EDT and 14:07 UTC under EST (the minute is off the hour on purpose; see
SEND_TIMES). Exactly one of each pair lands on the
intended wall clock on any given date, so exactly one tick sends and the other
exits 0 having done nothing at all. The monthly pair is day-of-month 1 in UTC,
and 13:07 or 14:07 UTC on the 1st is still the 1st in New York, so the UTC
cron date and the Eastern date this module judges never disagree for it.

IT JUDGES THE SCHEDULED TIME, NOT THE CLOCK, AND THAT IS THE WHOLE POINT.

The obvious implementation reads `datetime.now()` in New York and skips unless
the hour is 6. (`late_tick_line` below does compare the two clocks, but only
to PRINT the delay; it takes the start time as an argument and decides
nothing.) It is wrong, and wrong in the direction that loses an edition:
GitHub delays scheduled runs under load, routinely by minutes and occasionally
by more, so a 10:00 UTC tick that starts at 11:05 UTC would fail a
now()-based test, the 11:00 UTC tick would fail it too, and the day's digest
would silently not go out with two green runs to show for it.

So the input is `github.event.schedule` - the cron LINE that triggered this
run, which GitHub reports exactly as written in the workflow. The intended
instant is derived from that line, converted to New York time for today's
date, and matched against the wall clock the owner asked for. A run delayed
by an hour still knows which slot it is.

`zoneinfo` is stdlib and carries the IANA rules, so the EDT/EST boundary is
read from the tz database rather than from an offset somebody hardcoded. No
new dependency, and nothing to update in 2027.

WHAT IS DELIBERATELY NOT HERE.

No side effect of any kind. This module answers a question; the caller decides
what to do about it. The skip path in digest_send.py has to return before it
reads a recipient, builds a message, touches the relay or stamps a health row -
a no-op tick that stamped the mailer's row would mask a real miss, which is
the failure mode the split schedule is most exposed to.
"""
from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

# The one timezone the owner reads these times in. Not UTC, not the runner's.
ZONE_NAME = "America/New_York"
ZONE = ZoneInfo(ZONE_NAME)

# THE SCHEDULE, AS A WALL CLOCK, IN ONE PLACE.
#
#   (hour, minute) in New York -> (tier, required ISO weekday or None,
#                                   required day of month or None)
#
# Daily is SEVEN DAYS A WEEK on purpose. A day with no AI-attributed cuts still
# earns its send: the digest prints `AI-attributed cuts: 0`, which is a
# reading, and suppressing it would turn "nothing happened" into "we did not
# look" in the reader's inbox. Do not narrow this to weekdays.
#
# Weekly is Monday because the week it looks back over runs Monday to Sunday,
# so Monday morning is the first moment that week is complete. A Sunday send
# would review a week that is still running. 7:30 rather than 6:00 so that a
# subscriber who takes both tiers does not receive two emails in the same
# minute on a Monday.
#
# Monthly is THE 1ST OF THE MONTH because that is what the signup promises
# ("Monthly editions go out at the start of each month", subscribe.php
# alt_digest_cadence_sentence), and tests/test_digest_cadence_promises.py
# derives that sentence's truth from the day-of-month written here. 9:00
# rather than 6:00 or 7:30 for the weekly's own reason: a subscriber who takes
# every tier must not receive two editions in the same minute, and a 1st that
# falls on a Monday already carries the other two. The window it composes is
# the site's (alt_digest_monthly_window): the month the tick is in, to date.
#
# THE MINUTE IS :07 OR :37, NOT :00 OR :30 (2026-09-11). GitHub queues every
# repository's on-the-hour cron at once and documents that those are the most
# delayed; measured 2026-09-06 to 2026-09-11 the `0 10 * * *` tick started at
# 13:56 UTC each day and the Monday `30 11 * * 1` tick at 16:36. Seven minutes
# past lands in a quieter queue. The hours and days are the owner's; only the
# minute moved, and digest-send.yml carries the same six lines.
SEND_TIMES = {
    (6, 7): ("daily", None, None),
    (7, 37): ("weekly", 1, None),    # 1 = Monday, ISO
    (9, 7): ("monthly", None, 1),    # the 1st of the month
}

# A tick that starts more than this long after its scheduled minute is
# reported as LATE. It is a log line and nothing else: the slot is still
# judged from the cron string, so the edition still goes out.
LATE_AFTER = datetime.timedelta(minutes=60)


class UnreadableCron(ValueError):
    """The trigger did not look like a five field cron expression."""


def parse_cron(cron: str):
    """(hour, minute) in UTC from a cron line. Raises UnreadableCron."""
    fields = str(cron or "").split()
    if len(fields) != 5:
        raise UnreadableCron(f"expected five cron fields, got {len(fields)}: {cron!r}")
    minute, hour = fields[0], fields[1]
    if not (minute.isdigit() and hour.isdigit()):
        raise UnreadableCron(
            f"this guard can only read a cron with a single fixed hour and "
            f"minute; got minute={minute!r} hour={hour!r}")
    hour, minute = int(hour), int(minute)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise UnreadableCron(f"{hour:02d}:{minute:02d} is not a time of day")
    return hour, minute


def eastern_wall_clock(cron: str, on_date: datetime.date):
    """The New York datetime this cron line MEANS on `on_date` (a UTC date)."""
    hour, minute = parse_cron(cron)
    intended = datetime.datetime(on_date.year, on_date.month, on_date.day,
                                 hour, minute, tzinfo=datetime.timezone.utc)
    return intended.astimezone(ZONE)


def tier_for_cron(cron: str, on_date: datetime.date | None = None):
    """(tier, reason) for one scheduled tick. `tier` is None when it is not ours.

    `reason` is always a full sentence naming both clocks, because the log line
    of a run that deliberately did nothing has to be readable by somebody who
    is asking why no email arrived.
    """
    if on_date is None:
        on_date = datetime.datetime.now(datetime.timezone.utc).date()
    local = eastern_wall_clock(cron, on_date)
    hour, minute = parse_cron(cron)
    utc_txt = f"{hour:02d}:{minute:02d} UTC"
    local_txt = f"{local:%H:%M} {local.tzname()} ({local:%A})"

    entry = SEND_TIMES.get((local.hour, local.minute))
    if entry is None:
        wanted = ", ".join(f"{h:02d}:{m:02d}" for h, m in sorted(SEND_TIMES))
        return None, (
            f"this tick is not ours today: cron '{cron}' is {utc_txt}, which is "
            f"{local_txt} in {ZONE_NAME}, and the digest goes out at {wanted} "
            f"Eastern. The other scheduled tick is the one that sends today. "
            f"Nothing was read, built, sent or stamped.")

    tier, weekday, monthday = entry
    if weekday is not None and local.isoweekday() != weekday:
        return None, (
            f"this tick is not ours today: cron '{cron}' is {utc_txt}, which is "
            f"{local_txt} in {ZONE_NAME}, and the {tier} tier goes out on a "
            f"Monday. Nothing was read, built, sent or stamped.")
    if monthday is not None and local.day != monthday:
        # The cron line is already day-of-month 1, so this branch is only
        # reached by a hand-set DIGEST_CRON or a workflow edit; it refuses
        # rather than trusting that the line was right.
        return None, (
            f"this tick is not ours today: cron '{cron}' is {utc_txt}, which is "
            f"{local_txt} in {ZONE_NAME} on day {local.day} of the month, and "
            f"the {tier} tier goes out on the {monthday}st. Nothing was read, "
            f"built, sent or stamped.")

    return tier, (
        f"this tick is the {tier} slot: cron '{cron}' is {utc_txt}, which is "
        f"{local_txt} in {ZONE_NAME}, the wall clock this tier is scheduled for.")


def late_tick_line(cron: str, started_at: datetime.datetime,
                   late_after: datetime.timedelta = LATE_AFTER):
    """One log line when the runner started long after the slot, else None.

    THIS DECIDES NOTHING. The tick's identity comes from the cron string
    (tier_for_cron); this only makes the delay visible, because a run that is
    four hours late and green looks identical in the run list to one that was
    on time, and the 2026-09-06 to 2026-09-11 delays were only found by
    reading start times by hand. `started_at` is supplied by the caller
    (GITHUB_RUN_STARTED_AT, or the clock at process start) so this module
    still reads no clock of its own.
    """
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=datetime.timezone.utc)
    started_at = started_at.astimezone(datetime.timezone.utc)
    hour, minute = parse_cron(cron)
    scheduled = started_at.replace(hour=hour, minute=minute, second=0,
                                   microsecond=0)
    # A tick queued before midnight and started after it: the slot it was
    # scheduled for is the previous day's.
    if scheduled > started_at:
        scheduled -= datetime.timedelta(days=1)
    if started_at - scheduled <= late_after:
        return None
    return (f"LATE TICK: scheduled {scheduled:%H:%M} UTC, "
            f"started {started_at:%H:%M} UTC")
