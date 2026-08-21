"""Did the collector FINISH, or only start? The health ledger cannot say.

`cron.py` posts a `running` note before each collector and a terminal `ok` /
`degraded` note after it, so every attempt should be a PAIR. Nothing checked the
pairing, and the two places that look like they would both cannot:

  * The health ledger (`/source-health`, `ops_status` section [2]) keeps only the
    LATEST note per source. Tomorrow's run overwrites an orphaned `running` with
    an `ok`, so the evidence is gone inside a day. Worse, section [2] read any
    status that was not `degraded` or `retired` as OK — and an orphaned `running`
    carries a FRESH `checked_at`, so a collector that died mid-flight looked
    maximally healthy and reset its own staleness clock while doing it.
  * `source_freshness.py` judges whether a source is PUBLISHING anything new. A
    run that dies before it queries publishes nothing and looks like a quiet day.

The append-only `/source-runs` telemetry is the only place the pair survives, and
until now nothing read it for pairing.

THIS IS NOT HYPOTHETICAL AND IT IS NOT RARE. Over 2026-05-23..2026-08-20, gdelt
alone shows three `running` notes with no terminal note ever (2026-07-22,
2026-08-02, 2026-08-19), and on 2026-08-16 the run died earlier still, stranding
`local_news` and `regional_feeds` and never reaching gdelt at all. Two of those
are provably dead PROCESSES rather than dropped telemetry: `_post_spend_record`
writes an end-of-run record to `/tracker-meta`, and `railway/spend_jobs.json` has
an entry for every scheduled run since 2026-08-05 except exactly 2026-08-16 and
2026-08-19 — the two whose notes stop mid-way.

WHAT THIS CAN AND CANNOT TELL YOU. An orphan means "we cannot prove this
collector finished". It does NOT distinguish a dead process from a health POST
that was dropped (`report_source_health` retries three times and then gives up
silently, by design — a telemetry write must never fail a completed job). Both
deserve a human, and the discriminator is `spend_jobs.json`, which is why the
verdict line names it. Do not "fix" a recurring orphan by widening GRACE: the
grace exists to avoid convicting a run that is still in flight, not to wait out
a collector that keeps dying.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

TERMINAL = ("ok", "degraded")
RUNNING = "running"

# How long after a `running` note we still believe the run might be in flight.
# DERIVATION: the slowest collector in the pipeline is gdelt at 6-8 minutes per
# run measured over 56 paired runs (2026-07-18..2026-08-20), and a whole cron
# run is ~20 minutes. One hour is ~8x the slowest single collector, so a live run
# is never convicted, and a run that died is reported on the same day rather than
# the next. This is a grace period, NOT a cadence: see the module docstring.
GRACE = timedelta(hours=1)

# How far back an orphan is worth reporting. An orphan is a past incident, not a
# present state, so it has to age out or it is permanent red with nothing to do.
# Two weeks is long enough that a session sees the same incident twice before it
# expires, and short enough that a cleared-up month goes quiet on its own.
WINDOW = timedelta(days=14)


def _parsed(runs):
    """(datetime, source, status) triples, oldest first, unparseable dropped."""
    out = []
    for r in runs or ():
        if not isinstance(r, dict):
            continue
        try:
            at = datetime.fromisoformat(
                str(r.get("attempted_at")).replace("Z", "+00:00"))
        except Exception:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        out.append((at, str(r.get("source") or ""), str(r.get("status") or "")))
    out.sort(key=lambda t: t[0])
    return out


def orphans(runs, now=None, grace=GRACE, window=WINDOW):
    """`running` notes that no terminal note ever answered.

    Pairs strictly per source and in time order: a `running` is closed by the
    next note for that SAME source when that note is terminal. A `running`
    followed by another `running` orphans the first — that is a run which
    started again without the previous one ever finishing.

    The most recent `running` for a source is exempt while it is younger than
    `grace`, because a run in flight has not failed at anything yet.
    """
    now = now or datetime.now(timezone.utc)
    per_source = {}
    for at, source, status in _parsed(runs):
        per_source.setdefault(source, []).append((at, status))

    found = []
    for source, notes in per_source.items():
        for i, (at, status) in enumerate(notes):
            if status != RUNNING:
                continue
            nxt = notes[i + 1] if i + 1 < len(notes) else None
            if nxt is not None and nxt[1] in TERMINAL:
                continue                      # answered: a complete pair
            if nxt is None and (now - at) < grace:
                continue                      # still plausibly in flight
            if (now - at) > window:
                continue                      # aged out; not actionable now
            found.append({
                "source": source,
                "started_at": at,
                "age_hours": round((now - at).total_seconds() / 3600, 1),
                # What came next tells a session which shape this was: another
                # `running` means the job started again, nothing means the
                # ledger simply stops there.
                "followed_by": (nxt[1] if nxt else None),
            })
    found.sort(key=lambda f: f["started_at"], reverse=True)
    return found


def verdict_lines(runs, now=None):
    """(lines, issue) for ops_status and the weekly digest to print verbatim.

    `issue` is None when there is nothing to act on. Absence of telemetry is
    UNKNOWN, never a pass — a ledger we could not read is not a clean ledger.
    """
    if not runs:
        return ([
            "UNKNOWN   no /source-runs telemetry in this window, so run completion",
            "          could not be checked. Not a pass.",
        ], None)

    found = orphans(runs, now=now)
    if not found:
        return (["PASS      every collector run in this window posted a terminal "
                 "note."], None)

    lines = [f"ORPHANED  {len(found)} collector run(s) started and never finished:"]
    for f in found[:8]:
        tail = (f"then {f['source']} started again"
                if f["followed_by"] == RUNNING else "the ledger stops there")
        lines.append(f"    {f['source']}: began {f['started_at']:%Y-%m-%d %H:%M}Z, "
                     f"{f['age_hours']}h ago, no ok/degraded note ({tail})")
    if len(found) > 8:
        lines.append(f"    ... and {len(found) - 8} more")
    lines.append("          The run died, or its terminal health POST was dropped.")
    lines.append("          Discriminate with railway/spend_jobs.json: a run that "
                 "reached")
    lines.append("          the end writes an end-of-run record there. No record = "
                 "the")
    lines.append("          process died. -> RUNBOOK 'a collector run never "
                 "finished'")
    return (lines, f"{len(found)} collector run(s) never finished")
