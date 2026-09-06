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
is the real one TODAY. 6:00 ET is 10:00 UTC under EDT and 11:00 UTC under EST;
7:30 ET is 11:30 UTC under EDT and 12:30 UTC under EST; 9:00 ET is 13:00 UTC
under EDT and 14:00 UTC under EST. Exactly one of each pair lands on the
intended wall clock on any given date, so exactly one tick sends and the other
exits 0 having done nothing at all. The monthly pair is day-of-month 1 in UTC,
and 13:00 or 14:00 UTC on the 1st is still the 1st in New York, so the UTC
cron date and the Eastern date this module judges never disagree for it.

IT JUDGES THE SCHEDULED TIME, NOT THE CLOCK, AND THAT IS THE WHOLE POINT.

The obvious implementation reads `datetime.now()` in New York and skips unless
the hour is 6. It is wrong, and wrong in the direction that loses an edition:
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
SEND_TIMES = {
    (6, 0): ("daily", None, None),
    (7, 30): ("weekly", 1, None),    # 1 = Monday, ISO
    (9, 0): ("monthly", None, 1),    # the 1st of the month
}


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
