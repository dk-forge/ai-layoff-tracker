"""One monotonic run counter, so a rotation cannot be coupled to a schedule.

WHY THIS EXISTS. Every rotating query set in this repo picked its slice with
some variant of::

    run_of_day = 0 if now.hour < 17 else 1     # "the two Railway cron slots"
    start = ((now.timetuple().tm_yday * 2 + run_of_day) * PER_RUN) % len(TERMS)

That `* 2` is a hardcoded runs-per-day. It is correct only while the cron fires
exactly twice a day, and NOTHING made it follow railway.toml. On 2026-08-14 the
schedule went to `0 16 * * *` and on 2026-08-18 to `0 22 * * *` (one run a day,
the owner's freshness-for-cost call). From that moment `run_of_day` was a
CONSTANT, so the index advanced by `2 * PER_RUN` per run while each run consumed
only `PER_RUN` terms, and the rotation walked the ring in strides of two.

THE CONSEQUENCE WAS NOT "SLOWER", IT WAS "NEVER". When the stride shares a
factor with the ring size, half the ring becomes unreachable — not swept less
often, never queried again. `EUPHEMISM_TERMS` is 16 terms taken 2 at a time, so
from 2026-08-14 exactly 8 of the 16 were dead, and the parity flip on 2026-08-18
swapped WHICH eight. `SEGMENT_TERMS` (117 taken 4) kept full coverage but its
sweep went from 15 days to 44. Nothing reported any of it: a rotation that never
issues a query produces no error, no health row and no log line.

The fix is to stop deriving a run counter from a guess. `run_index()` increments
by exactly ONE per scheduled run, so `start = run_index * per_run` steps by
exactly `per_run` and therefore tiles ANY ring at ANY cadence. The schedule is
read from railway.toml — the cron that actually runs, the same authority
`generate_ingest_schedule.py` already uses for the public "next update" promise.

FAILING SAFE IS DIRECTIONAL, and only one direction is safe. Overstating
runs-per-day makes the counter skip, which is the defect above. Understating it
makes two runs land on the same slice: one duplicated query, no lost coverage.
So when the schedule cannot be read we assume ONE run a day and repeat rather
than guess and skip.

`tests/test_rotation_covers_ring.py` fails on a ring that any supported cadence
cannot fully reach, and on a module that goes back to computing a slice index
from a hardcoded runs-per-day.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

# Where railway.toml sits depends on what got deployed. Railway builds this
# service from the `railway/` directory, so in the container the toml is beside
# this file; in a checkout it is also beside this file. The repo-root layout is
# kept as a second guess so a caller running from anywhere still resolves it.
_CANDIDATE_TOMLS = (
    Path(__file__).resolve().parent / "railway.toml",
    Path(__file__).resolve().parent.parent / "railway" / "railway.toml",
)

# Assumed when the schedule cannot be read. ONE, never two: see the module
# docstring — understating repeats a slice, overstating loses one for good.
FALLBACK_RUNS_PER_DAY = 1


def scheduled_utc_hours():
    """The UTC hours railway.toml actually fires on, or None if unreadable.

    None is a real answer and callers must treat it as "unknown", not as a
    default. It is never an exception: a rotation must not be able to take an
    ingest run down.
    """
    try:
        from generate_ingest_schedule import parse_cron_schedule
    except Exception:
        return None
    for toml in _CANDIDATE_TOMLS:
        try:
            text = toml.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            return list(parse_cron_schedule(text)["utc_hours"])
        except Exception:
            # A schedule shape the parser refuses to summarise (see
            # generate_ingest_schedule). Unknown, not one-a-day-by-assumption:
            # keep looking, then fall back.
            return None
    return None


def run_index(now=None):
    """A counter that goes up by exactly 1 per scheduled run.

    Built from the proleptic-Gregorian day number rather than `tm_yday`, which
    resets every 1 January and would hand two different runs the same index
    across a year boundary.
    """
    now = now or datetime.now(timezone.utc)
    hours = scheduled_utc_hours()
    if not hours:
        return now.toordinal() * FALLBACK_RUNS_PER_DAY
    hours = sorted(set(hours))
    # Which of today's slots is this? A run BEFORE the first scheduled hour (a
    # manual invocation, or a fire that drifted earlier) counts as slot 0, so it
    # repeats that slice instead of skipping one.
    slot = max(0, sum(1 for h in hours if h <= now.hour) - 1)
    return now.toordinal() * len(hours) + slot


def rotate(terms, per_run, now=None):
    """The `per_run` slice of `terms` belonging to this run.

    Steps by exactly `per_run` each run, so consecutive runs tile the ring and
    every term is reached whatever the cadence. Returns [] when the rotation is
    disabled (`per_run` of 0), which is how every caller switches it off.
    """
    terms = list(terms)
    if not per_run or not terms:
        return []
    start = (run_index(now) * per_run) % len(terms)
    return [terms[(start + i) % len(terms)] for i in range(per_run)]
