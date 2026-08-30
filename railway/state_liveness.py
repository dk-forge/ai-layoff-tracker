"""Is each committed state file still being WRITTEN? A mechanism that stopped
running does not raise; it just stops changing its file.

WHY THIS EXISTS. 104 of the 225 incidents in docs/TECHLOG.md share one shape:
something stopped working and no surface said so. The repo answers that shape
well, but one instrument at a time and always AFTER the incident --
`run_completion.py` pairs a start with a finish, `source_inventory.py` diffs
declared against reporting, `benchmark_freshness.py` reads ages. Each was built
because a specific thing had already been silently dead for weeks.

2026-08-28 supplied the generalisation. The GDELT work ledger was committed
once, the day its feature shipped, and held ZERO slots from then on while
production abandoned 7 of 12 windows a run. The mechanism was inert for its
entire life. Nothing reported it, because "the file did not change" is not an
error anywhere -- and yet it is visible, cheaply, in git:

    gdelt_work_ledger.json    1 commit ever
    alert_state.json         85 commits
    alert_outbox.json        59 commits
    spend_jobs.json          25 commits

A committed state file that never changes is a mechanism that never ran.

WHAT THIS WOULD AND WOULD NOT HAVE CAUGHT, stated plainly because a guard
oversold is a guard trusted wrongly. It would NOT have caught the GDELT ledger
any sooner: that feature shipped 2026-08-26, so on the day the bug was found by
hand the file was two days old and well inside GRACE_DAYS. This check would
have raised it on 2026-09-05 instead of never, which is the honest claim -- it
converts a permanent silence into a ten-day one, and it is worth having for
that and not for more. What it catches WELL is the older shape: a mechanism
that shipped months ago, stopped, and has been quietly dead since.

WHY IT IS NOT A SIMPLE STALENESS RULE. `curated_probe_state.json` also has one
commit, and that is CORRECT: the curated probe is hand-fed by the owner and
deliberately has no workflow ("There is no workflow and there must not be" --
a runner that could read the worklist is the leak). A flat "unchanged for N
days" rule would cry wolf there, and a rule that cries wolf gets widened until
it says nothing. So, exactly as `source_freshness.py` judges each SOURCE
against its own history rather than one global threshold, this judges each FILE
against its own commit cadence.

FOUR STATES, because two is what produced the defect:

  LIVE       changing about as often as it always has.
  NEVER_USED exactly one commit -- the one that ADDED it -- and older than
             GRACE_DAYS. The loudest signal, and the one that needed no history:
             a mechanism that shipped and has never once written its own state.
  STALE      its gap exceeds its own CADENCE_QUANTILE gap times CADENCE_MARGIN.
             Advisory. A slow week is not a fault.
  UNKNOWN    too few commits to have a cadence. NOT a pass -- absence of a
             signal is not evidence of health.

MANUAL is a fifth state and only a HUMAN sets it, in MANUAL_FILES below, with a
reason. That mirrors source_state's UNAVAILABLE: a file is exempt because
someone decided it is hand-run and said why, never because a check quietly
skipped it. Do not answer a STALE by adding a file here.
"""
import json
import os
import subprocess
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# A file with one commit is only NEVER_USED once it has had a fair chance to
# run. Sized above the slowest scheduled writer here (the weekly backup).
GRACE_DAYS = 10

CADENCE_QUANTILE = 0.90        # judge against the file's own 90th-percentile gap
CADENCE_MARGIN = 1.5           # ... times this, so an ordinary slow week is fine
MIN_COMMITS_TO_JUDGE = 4       # fewer than this has no cadence worth trusting

LIVE, NEVER_USED, STALE, UNKNOWN, MANUAL = (
    "LIVE", "NEVER_USED", "STALE", "UNKNOWN", "MANUAL")

# The state files each mechanism writes. Adding a mechanism means adding its
# file here; a file absent from this list is not checked, which is the same
# "absent is not green" hole source_inventory.py exists to close -- so
# `unregistered_state_files()` reports anything on disk that nobody declared.
WATCHED_FILES = (
    "railway/alert_state.json",
    "railway/alert_outbox.json",
    "railway/source_state.json",
    "railway/spend_jobs.json",
    "railway/headline_incidents.json",
    "railway/tracker_learning_state.json",
    "railway/gdelt_work_ledger.json",
    "railway/backup_state.json",
    "railway/curated_probe_state.json",
    "railway/deferral_ledger.json",
    "railway/warn_state_baselines.json",
)

# STALENESS IS THE WRONG LENS FOR AN EVENT-DRIVEN FILE, and the first cut of
# this module got that wrong: it called `alert_outbox.json` STALE at 9 days.
# The outbox holds alerts that could not be delivered. Nine quiet days there
# means nothing failed -- the single best thing it could report -- and calling
# it stale would have manufactured an alarm out of good news, on the exact
# check written to reduce false quiet. Same for the alert ledger and the
# headline incidents: they are written WHEN SOMETHING HAPPENS, so silence is
# the healthy state and only NEVER_USED can apply.
#
# A HEARTBEAT file is written every run regardless of outcome, so for those a
# gap really does mean the writer stopped.
EVENT_DRIVEN = frozenset({
    "railway/alert_state.json",
    "railway/alert_outbox.json",
    "railway/headline_incidents.json",
    # A deferral is a host call that was never answered. Written only when one
    # happens, and again when it resolves -- so a long gap here means every
    # job got an answer, which is the best thing this file can report. Only
    # NEVER_USED can apply, exactly as for the outbox above.
    "railway/deferral_ledger.json",
})

# Never call a file stale below this, whatever its own history says. A file
# written twice a day has a 90th-percentile gap near 1.0d, and without a floor
# a single skipped run reads as a fault. `tracker_learning_state.json` also
# EARNS a slower cadence by design (it steps down to Mondays after three runs
# with no rule), so its own history is a moving target by intent.
MIN_STALE_DAYS = 8

# Human-declared hand-run files. reviewer + reason + date, like UNAVAILABLE.
MANUAL_FILES = {
    "railway/curated_probe_state.json": {
        "reviewer": "owner",
        "date": "2026-08-28",
        "reason": "the curated probe is hand-fed from a gitignored worklist and "
                  "deliberately has NO workflow -- a runner that could read the "
                  "worklist is the leak. Sparse commits are correct here.",
    },
}


def _git_commit_dates(path, repo=REPO):
    """Every commit date for one path, newest first. [] when git cannot answer."""
    try:
        out = subprocess.run(
            ["git", "log", "--format=%cI", "--", path],
            cwd=repo, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    dates = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            dates.append(datetime.fromisoformat(line).astimezone(timezone.utc).date())
        except ValueError:
            continue
    return dates


def _quantile(sorted_values, q):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def _gaps(dates_newest_first):
    """Days between consecutive commits, oldest-first."""
    ordered = sorted(dates_newest_first)
    return [(b - a).days for a, b in zip(ordered, ordered[1:])]


def judge_file(path, dates, today=None):
    """Classify one file from its commit dates. Never raises."""
    today = today or datetime.now(timezone.utc).date()
    manual = MANUAL_FILES.get(path)
    commits = len(dates)
    newest = max(dates) if dates else None
    age = (today - newest).days if newest else None
    base = {"path": path, "commits": commits, "last_change": newest,
            "days_since": age, "expected_gap": None}

    if manual:
        return {**base, "state": MANUAL,
                "detail": f"hand-run by declaration ({manual['reviewer']}, "
                          f"{manual['date']}): {manual['reason']}"}
    if not dates:
        return {**base, "state": UNKNOWN,
                "detail": "git returned no history for this path, so its liveness "
                          "could not be checked. UNKNOWN, not a pass."}
    if commits == 1:
        if age is not None and age >= GRACE_DAYS:
            return {**base, "state": NEVER_USED,
                    "detail": f"one commit ever ({newest}, {age}d ago) -- the one "
                              f"that ADDED it. The mechanism has never written "
                              f"its own state."}
        return {**base, "state": UNKNOWN,
                "detail": f"one commit ({newest}), still inside the {GRACE_DAYS}d "
                          f"grace. Too early to call, which is not a pass."}
    if commits < MIN_COMMITS_TO_JUDGE:
        return {**base, "state": UNKNOWN,
                "detail": f"only {commits} commits, too few for a cadence. "
                          f"Not evidence of health."}

    if path in EVENT_DRIVEN:
        # Quiet is the healthy state here; only NEVER_USED, above, can apply.
        return {**base, "state": LIVE,
                "detail": f"event-driven: {commits} commits, last {age}d ago. "
                          f"Silence means nothing happened, not that it stopped."}

    gaps = sorted(_gaps(dates))
    expected = _quantile(gaps, CADENCE_QUANTILE)
    base["expected_gap"] = expected
    if expected is not None:
        allowed = max(expected * CADENCE_MARGIN, MIN_STALE_DAYS)
        if age is not None and age > allowed:
            return {**base, "state": STALE,
                    "detail": f"unchanged for {age}d against its own "
                              f"{CADENCE_QUANTILE:.0%} gap of {expected:.1f}d "
                              f"(allowed {allowed:.1f}d). Advisory."}
    return {**base, "state": LIVE,
            "detail": f"{commits} commits, last {age}d ago"}


def unregistered_state_files(repo=REPO):
    """Committed *_state/ledger JSON under railway/ that WATCHED_FILES omits.

    Absent from a registry must not read as "no problem" -- that is the hole
    source_inventory.py exists to close, one level up.
    """
    try:
        out = subprocess.run(["git", "ls-files", "railway/*.json"],
                             cwd=repo, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    watched = set(WATCHED_FILES)
    found = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line or line in watched:
            continue
        # Test fixtures are not mechanism state; a frozen fixture is supposed
        # to be frozen, and reporting one would be pure noise.
        if "/tests/" in line:
            continue
        name = os.path.basename(line)
        if any(k in name for k in ("_state", "ledger", "outbox", "incidents")):
            found.append(line)
    return sorted(found)


def collect(repo=REPO, today=None):
    return [judge_file(p, _git_commit_dates(p, repo), today) for p in WATCHED_FILES]


def problems(rows=None):
    """States a human must act on. STALE and UNKNOWN are advisory, not failures."""
    rows = rows if rows is not None else collect()
    return [r for r in rows if r["state"] == NEVER_USED]


def render(rows=None, unregistered=None):
    rows = rows if rows is not None else collect()
    unregistered = (unregistered if unregistered is not None
                    else unregistered_state_files())
    lines = ["[2f] STATE LIVENESS  (is each mechanism still writing its own file?)"]
    order = {NEVER_USED: 0, STALE: 1, UNKNOWN: 2, MANUAL: 3, LIVE: 4}
    for row in sorted(rows, key=lambda r: (order.get(r["state"], 9), r["path"])):
        if row["state"] == LIVE:
            continue
        lines.append(f"    {row['state']:<10} {os.path.basename(row['path'])}: "
                     f"{row['detail']}")
    live = sum(1 for r in rows if r["state"] == LIVE)
    lines.append(f"    {live} of {len(rows)} state file(s) changing at their usual cadence.")
    for path in unregistered:
        lines.append(f"    UNREGISTERED {path}: looks like mechanism state but is in "
                     f"no registry, so nothing checks whether it is still written.")
    return "\n".join(lines)


if __name__ == "__main__":
    rows = collect()
    print(render(rows))
    raise SystemExit(2 if problems(rows) else 0)
