#!/usr/bin/env python3
"""Is a collector still bringing back NEW data, judged against its own cadence.

THE DEFECT THIS EXISTS FOR
--------------------------
Every WARN tripwire in this repo asked one question: "did the scraper return
notices?" `detect_generic_state_drift` compares a count against a committed
high-water floor, and `ratchet_state_baselines` records that floor. Both are
COUNT floors, and a count floor cannot see the failure that actually happens to
an archive-publishing register: the collector keeps re-reading a FROZEN archive,
returns its full history every single run, clears every floor, and reports
healthy forever.

Measured 2026-08-19 against the live table: Kansas last published an effective
date of 2026-05-01 and had looked green for 110 days. Michigan 81 days,
Minnesota 49, Indiana 29. Every WARN tier read `ok` throughout. This is the same
shape as `credential=ABSENT`, as `0 sent of 0 eligible`, and as an alert outbox
that could not drain: a signal that is true, complete, and says nothing.

So the question here is the other one: **did it return anything NEWER than last
time?**

WHY THE THRESHOLD CANNOT BE A NUMBER OF DAYS
--------------------------------------------
CLAUDE.md: "a staleness ceiling must match the job's REAL cadence — a 2-day
ceiling on a weekly job is permanent noise that hides real breakage." The same
measurement that found Kansas found North Dakota 216 days quiet and Montana 29,
both entirely legitimate: they file 4.5 and 6.4 notices a year. Any calendar
ceiling that catches Kansas at 110 days condemns North Dakota at 216.

So each source is judged against ITS OWN history, through two gates that must
BOTH agree before anything is called dark:

  1. RARITY (Poisson). With that source's own RECENT rate, how likely is a
     quiet stretch this long by chance?
     P(0 arrivals) = exp(-rate_per_day * days_dark), read against two
     thresholds, because quiet and broken are different states (see below).

  2. CADENCE (the source's own observed gaps). days_dark must exceed
     CADENCE_MARGIN times the source's own 90th-percentile gap between
     consecutive publication dates.

Gate 2 is what handles a lumpy publisher without a hard-coded exemption list.
Mississippi publishes quarterly; its own gap distribution therefore contains
quarterly gaps, so its 50-day silence is ordinary BY ITS OWN DATA and never
reaches the alarm. A hard-coded "MS is quarterly, skip it" would be how a
genuinely broken quarterly state hides forever; a measured cadence expires on
its own the moment the state's real gaps grow past it. Gate 2 is also the only
thing standing between the alarm and Texas, whose 226/yr rate makes a nine-day
lull read p=0.0038 on gate 1 alone.

Gate 1 is what stops gate 2 crying wolf about a genuinely sparse source: North
Dakota's 216 days DOES exceed 1.25x its 118-day gap ceiling, and gate 1 (p=0.071)
is what correctly holds it back.

Neither gate is redundant. Both were needed on the real 2026-08-19 data.

QUIET AND BROKEN ARE DIFFERENT STATES, AND CONFLATING THEM COST A FALSE POSITIVE
-------------------------------------------------------------------------------
The first cut of this module called Kansas dark with apparent certainty. It was
wrong, and the way it was wrong is worth more than the four states it got right.

Kansas's register holds 910 rows, newest 2026-05-01, and a collector audit found
we already hold every notice in the fetch window. Nothing was missing. Kansas
had simply not filed since May. The certainty came from the DENOMINATOR: a rate
averaged over years reads 33/yr and makes 110 days of silence look impossible,
while the rate over the last year reads 12.5/yr and makes it a 2.3% event —
uncommon, and entirely possible.

Filing rates drift. Economic cycles, statutory changes, an employment base
moving. A long-run average will keep flagging states that have genuinely slowed,
and every one of those is a false alarm that teaches the owner to ignore the
channel — the exact failure this module exists to prevent, arriving from the
other direction. So:

  * the RATE is fitted over the trailing 365 days ending at the last
    observation, not over all history. It is the drifting quantity, so it is
    measured recently.
  * the CADENCE is fitted over 1095 days, because a gap distribution needs
    samples and a low-volume state does not produce enough of them in a year.
    Burstiness is a stable property of how a register publishes; the rate is
    not.
  * `rate_per_year` is reported alongside `rate_long_run_per_year` so a
    SLOWDOWN is visible as itself. "This state has slowed" is useful and it is
    NOT the same finding as "this collector is broken".

Two thresholds, therefore, not one:

  ALPHA_DARK  = 0.01  -> FAIL. Broken. Opens an incident and emails the owner.
  ALPHA_QUIET = 0.05  -> QUIET. Advisory. Printed and digested, never emailed
                         as a breakage, never recorded BROKEN.

CALIBRATION (all figures measured, 2026-08-19, 48 US states from the live table)
--------------------------------------------------------------------------------
Against the six states a measurement run called dark, on their real dates and a
trailing rate:

  MI  81d  72.2/yr  p=1.1e-07  FAIL   (and its collector is genuinely broken)
  MN  49d  76.6/yr  p=3.4e-05  FAIL   (older templates parse to zero)
  KS 110d  12.5/yr  p=0.023    QUIET  (audited: nothing missing, just no filings)
  IN  29d  42.2/yr  p=0.035    QUIET
  MS  50d  22.0/yr  p=0.049    PASS   (quarterly; held by the cadence gate)
  NE  54d  12.1/yr  p=0.166    PASS

and on NOTHING else in 45 judged states, at either threshold. ALPHA_QUIET is not
raised to 0.10 because that costs North Dakota (p=0.0714), which files 4.5
notices a year and is publishing perfectly normally.

MIN_DARK_DAYS = 14 is load-bearing and not decoration. California (1436/yr) and
Texas (226/yr) file so densely that an ordinary weekend clears the rarity gate,
and Texas at 9 days clears the cadence gate as well. Nothing may be called dark
on less than a fortnight of silence.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
`days_dark` is measured from the newest effective date the collector has
returned, CLAMPED AT ZERO, because WARN notices are advance notices and a
healthy register routinely carries effective dates months in the future (on
2026-08-19: WA 2026-12-31, LA 2027-03-31, OR 2027-02-28). For those states the
tripwire is INSENSITIVE until the future dates pass — a state that went dark
today with a notice on file for next March is not detectable here until March.
That is a known ceiling, stated rather than hidden. It is not a hole the other
direction: a future date can only DELAY the alarm, never manufacture one.

A source with too little history to fit a rate is UNKNOWN. Never a pass.
"""
import argparse
import datetime
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_STATE_LEDGER = os.path.join(HERE, "source_state.json")

# --- the judgement constants. See the calibration note above. ----------------
REFERENCE_WINDOW_DAYS = 1095   # cadence: 3 years, enough gaps for a sparse state
RATE_WINDOW_DAYS = 365         # rate: trailing year. Filing rates DRIFT.
ALPHA_DARK = 0.01              # below this the source is BROKEN, and emailed
ALPHA_QUIET = 0.05             # below this it is QUIET: advisory, never emailed
CADENCE_QUANTILE = 0.90        # gate 2: the source's own 90th-percentile gap
CADENCE_MARGIN = 1.25          # gate 2: dark must exceed 1.25x that gap
MIN_DARK_DAYS = 14             # nothing is dark on less than a fortnight
MIN_OBSERVATIONS = 8           # below this a rate is not a rate
MIN_DISTINCT_DATES = 7         # below this a gap distribution is not one
MIN_SPAN_DAYS = 180            # a rate fitted to a few weeks is not a rate
MIN_RATE_OBSERVATIONS = 8      # too few in the trailing year -> use the long run
MIN_RATE_SPAN_DAYS = 120       # ditto
SLOWDOWN_RATIO = 0.6           # recent below this share of the long run = SLOWED
#: A rate-dependent PASS is only trustworthy if this run measured a history
#: comparable to the one the last reading used. Below this share of the previous
#: observation count the fit is not comparable and the verdict is UNKNOWN.
#: See _incomparable_history.
COMPARABLE_OBSERVATION_SHARE = 0.75

#: PASS and QUIET are both "not broken". QUIET says the source is quieter than
#: its own recent rate would predict but not past the evidence bar that opens an
#: incident, and it exists because Kansas was audited healthy at p=0.023.
PASS, QUIET, FAIL, UNKNOWN = "PASS", "QUIET", "FAIL", "UNKNOWN"

# --- the three-state model. See docs/RUNBOOK.md "a collector went dark". -----
# HEALTHY / BROKEN / UNAVAILABLE. Two states is what produced the defect: a
# source was either "ok" or it was nothing, so a source nobody could collect and
# a source nobody WAS collecting looked identical.
HEALTHY, BROKEN, UNAVAILABLE = "HEALTHY", "BROKEN", "UNAVAILABLE"

# --- how a BROKEN source is triaged. -----------------------------------------
# The classification is the whole point of the record: it says which failures a
# machine could plausibly repair and which need a person. It is NOT a licence to
# repair anything — this module only detects.
DRIFT = "drift"                  # runs, returns rows, none newer. Healable.
FORMAT_CHANGE = "format_change"  # returns rows, fewer parse than before.
HARD_FAILURE = "hard_failure"    # errors, 404, returns nothing. Escalate.
POLICY = "policy"                # not published / not public. Never attempt.


def _as_date(value):
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def today_utc():
    return datetime.datetime.now(datetime.timezone.utc).date()


def _quantile(sorted_values, q):
    """The q-quantile of an already-sorted list, nearest-rank.

    Nearest-rank (not interpolated) on purpose: these are whole days, and a
    fractional gap between two publication dates is not a thing that exists.
    """
    if not sorted_values:
        return 0
    idx = int(math.ceil(q * len(sorted_values))) - 1
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def cadence_profile(dates, today=None, window_days=REFERENCE_WINDOW_DAYS):
    """Fit a source's own publication cadence. Returns a dict, always.

    The reference window ENDS at the newest observation, not at today. That is
    deliberate and it is the difference between a working detector and one that
    talks itself out of an alarm: a window ending at today would fold the dark
    stretch itself into the rate, so the longer a source stayed dark the more
    normal its silence would look. Kansas at 110 days dark reads 15.3/yr on a
    window ending at its last notice, and would read 11/yr on one ending today.

    ``insufficient`` is set when the history cannot support a rate. The caller
    must report that as UNKNOWN. It is never a pass.
    """
    today = today or today_utc()
    parsed = sorted(d for d in (_as_date(x) for x in (dates or [])) if d)
    if not parsed:
        return {"insufficient": "no observations", "observations": 0,
                "max_effective": None}
    newest = parsed[-1]
    floor = newest - datetime.timedelta(days=window_days)
    window = [d for d in parsed if d >= floor]
    distinct = sorted(set(window))
    profile = {
        "max_effective": newest.isoformat(),
        "observations": len(window),
        "distinct_dates": len(distinct),
        "window_days": window_days,
    }
    if len(window) < MIN_OBSERVATIONS or len(distinct) < MIN_DISTINCT_DATES:
        profile["insufficient"] = (f"only {len(window)} observation(s) on "
                                   f"{len(distinct)} distinct date(s) in the "
                                   f"{window_days}d window")
        return profile
    span = (distinct[-1] - distinct[0]).days
    profile["span_days"] = span
    if span < MIN_SPAN_DAYS:
        profile["insufficient"] = (f"history spans only {span}d "
                                   f"(need {MIN_SPAN_DAYS}d)")
        return profile
    gaps = sorted((b - a).days for a, b in zip(distinct, distinct[1:]))
    profile["cadence_days"] = _quantile(gaps, CADENCE_QUANTILE)
    profile["max_gap_days"] = gaps[-1]

    # The long-run rate, kept only so a SLOWDOWN is visible as itself.
    long_run = round((len(window) - 1) / span * 365.0, 2)
    profile["rate_long_run_per_year"] = long_run

    # The rate that JUDGES is the trailing one. A long-run average is the wrong
    # denominator for a quantity that drifts: Kansas reads 33/yr over its whole
    # history and 12.5/yr over the last year, and the difference between those
    # two numbers is the difference between "impossible" and "a 2% event".
    recent = [d for d in window
              if d >= newest - datetime.timedelta(days=RATE_WINDOW_DAYS)]
    recent_distinct = sorted(set(recent))
    recent_span = ((recent_distinct[-1] - recent_distinct[0]).days
                   if len(recent_distinct) > 1 else 0)
    if (len(recent) >= MIN_RATE_OBSERVATIONS
            and recent_span >= MIN_RATE_SPAN_DAYS):
        profile["rate_per_year"] = round((len(recent) - 1) / recent_span * 365.0, 2)
        profile["rate_basis_days"] = recent_span
    else:
        # Too thin a trailing year to fit a rate of its own. Fall back to the
        # long run and SAY SO, rather than inventing precision from four rows.
        profile["rate_per_year"] = long_run
        profile["rate_basis_days"] = span
        profile["rate_fell_back"] = True
    if long_run > 0 and profile["rate_per_year"] < SLOWDOWN_RATIO * long_run:
        profile["slowed"] = True
    return profile


def days_dark(profile, today=None):
    """Days since the newest observation, clamped at 0 (see the module note)."""
    today = today or today_utc()
    newest = _as_date(profile.get("max_effective"))
    if newest is None:
        return None
    return max(0, (today - newest).days)


def _incomparable_history(profile, prior):
    """Why this run's history cannot be compared with the last one, or None.

    A rate is a count over a window, and every verdict except "it published
    recently" is a statement about that rate. So a run that measured a SMALLER
    history than the previous reading is not a fresher opinion about the same
    question: it is a different, weaker question, and it is biased in exactly
    one direction. p0 = exp(-(rate/365) * dark), so halving the fitted rate can
    only raise p0, which can only move a verdict TOWARDS a pass.

    warn:MN paid for this on 2026-09-01. It had been BROKEN since 2026-08-28
    with nothing new since 2026-08-07. That run measured 30 observations over
    204 days where the run before it and the run after it both measured 87 over
    366; the fitted rate fell from 86.18/yr to 51.89/yr; p0 rose from 0.00346 to
    0.02861, crossing ALPHA_QUIET; the verdict read PASS, and a PASS is the one
    verdict that closes an open incident. Nothing had arrived. The next day it
    was BROKEN again at p=0.00216. Six days of a real outage were reported as a
    recovery and a fresh break, and the only thing that changed was how much of
    Minnesota's own history the collector happened to bring back.

    This is the Kansas lesson pointed the other way. There the certainty came
    from the denominator; here the reprieve does. Note what this is NOT: it does
    not widen a threshold, move a state, or silence anything. It refuses to read
    a shrunken denominator as good news, and UNKNOWN already never clears
    BROKEN (see record()).
    """
    if not prior:
        return None
    try:
        was = int(prior.get("observations") or 0)
        now = int(profile.get("observations") or 0)
    except (TypeError, ValueError):
        return None
    if was < MIN_OBSERVATIONS or now >= was * COMPARABLE_OBSERVATION_SHARE:
        return None
    return (f"history shrank: this run measured {now} observation(s) over "
            f"{profile.get('span_days')}d where the last reading used {was} over "
            f"{prior.get('span_days')}d. A rate fitted to a smaller history can "
            f"only move the verdict towards a pass, so this is UNKNOWN, not a "
            f"clean bill")


def judge(profile, today=None, prior=None):
    """PASS / FAIL / UNKNOWN for one source, plus the numbers that decided it.

    Takes a PROFILE, not raw dates, so that the run that fetches the data and a
    later session reading the committed ledger reach the SAME verdict from the
    SAME numbers. One definition, the way data_integrity.py is one definition.
    """
    today = today or today_utc()
    dark = days_dark(profile, today)
    out = {"verdict": UNKNOWN, "days_dark": dark, "p0": None,
           "rate_per_year": profile.get("rate_per_year"),
           "cadence_days": profile.get("cadence_days")}
    if profile.get("insufficient") or dark is None:
        out["reason"] = profile.get("insufficient") or "no observation recorded"
        return out
    rate = float(profile.get("rate_per_year") or 0.0)
    cadence = max(1, int(profile.get("cadence_days") or 1))
    if rate <= 0:
        out["reason"] = "measured rate is zero"
        return out
    p0 = math.exp(-(rate / 365.0) * dark)
    out["p0"] = round(p0, 6)
    cadence_bar = CADENCE_MARGIN * cadence
    if dark < MIN_DARK_DAYS:
        out["verdict"] = PASS
        out["reason"] = f"{dark}d quiet, under the {MIN_DARK_DAYS}d floor"
    elif p0 >= ALPHA_QUIET:
        # Both of the next two PASSes are RATE-DEPENDENT: one reads p0, the
        # other the cadence quantile, and both are fitted from this run's
        # history. If that history shrank, neither is comparable with the
        # reading it would be overturning. The "published recently" PASS above
        # is not guarded, because it does not consult the fit at all.
        incomparable = _incomparable_history(profile, prior)
        if incomparable:
            out["verdict"] = UNKNOWN
            out["reason"] = incomparable
            return out
        out["verdict"] = PASS
        out["reason"] = (f"{dark}d quiet is ordinary at its recent {rate}/yr "
                         f"(p={p0:.3f}, needs p<{ALPHA_QUIET})")
    elif dark <= cadence_bar:
        incomparable = _incomparable_history(profile, prior)
        if incomparable:
            out["verdict"] = UNKNOWN
            out["reason"] = incomparable
            return out
        out["verdict"] = PASS
        out["reason"] = (f"{dark}d quiet is within this source's own cadence "
                         f"({CADENCE_MARGIN}x its {cadence}d 90th-pct gap)")
    elif p0 >= ALPHA_DARK:
        # Uncommon, not impossible. Kansas sat here at p=0.023 with an audit
        # showing nothing missing, so this tier never opens an incident and
        # never sends an email. It is information, and it is worth having.
        out["verdict"] = QUIET
        out["reason"] = (f"{dark}d with no newer record: p={p0:.4f} at its "
                         f"recent {rate}/yr. Uncommon but not evidence of a "
                         f"break (that needs p<{ALPHA_DARK}); this source may "
                         f"simply not be filing")
    else:
        out["verdict"] = FAIL
        out["reason"] = (f"{dark}d with no newer record: p={p0:.5f} at its "
                         f"recent {rate}/yr, past {CADENCE_MARGIN}x its own "
                         f"{cadence}d 90th-pct gap")
    if profile.get("slowed"):
        out["slowed"] = True
        out["reason"] += (f" [SLOWED: recent {rate}/yr against a long-run "
                          f"{profile.get('rate_long_run_per_year')}/yr]")
    return out


def classify(verdict, *, errored=False, produced=0, count_collapsed=False):
    """Which KIND of broken this is, so triage does not have to re-derive it.

    Ordered most-certain first. A collector that raised or returned nothing is a
    hard failure whatever else is true; a count that collapsed against its own
    floor is a format change; a collector that answers with a full archive and
    nothing new is DRIFT, and drift is the dangerous one precisely because every
    count-based check reports green while it happens.
    """
    if errored or produced == 0:
        return HARD_FAILURE
    if count_collapsed:
        return FORMAT_CHANGE
    if verdict == FAIL:
        return DRIFT
    return DRIFT


# --------------------------------------------------------------------------
# The committed ledger. Same pattern as alert_state.json / headline_incidents:
# a file in the repo, so it survives a run and any session can read it.
# --------------------------------------------------------------------------
def load_ledger(path=SOURCE_STATE_LEDGER):
    """Read the committed source-state ledger. Malformed -> UNKNOWN, not empty.

    A ledger that cannot be read is not a ledger saying nothing is wrong. The
    caller is told so it can say UNKNOWN rather than print a clean bill of
    health it cannot support.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("source-state ledger is not an object")
        data.setdefault("sources", {})
        if not isinstance(data["sources"], dict):
            raise ValueError("source-state ledger 'sources' is not an object")
        return data
    except FileNotFoundError:
        return {"sources": {}}
    except Exception as exc:
        raise RuntimeError(f"source-state ledger unreadable: {exc}")


def save_ledger(ledger, path=SOURCE_STATE_LEDGER):
    payload = {"sources": {k: ledger["sources"][k]
                           for k in sorted(ledger.get("sources", {}))}}
    for key in sorted(ledger):
        if key != "sources":
            payload[key] = ledger[key]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def record(ledger, key, *, profile, verdict, reason, classification=None,
           today=None, label="", p0=None):
    """Fold one observation into the ledger. Returns the entry.

    Three rules, and each of them is a bug this repo has already paid for:

    * A BROKEN source NEVER ages out. `first_detected` is written once and
      survives every later run, so its age climbs in public until somebody acts
      on it. The alert outbox held entries that could never drain while looking
      like they worked; a stale-dark register must not get the same silence.
    * An UNAVAILABLE source is never re-judged into BROKEN. Only a human moves a
      source in or out of UNAVAILABLE (`--classify-unavailable`), because a
      machine that may decide a source is permanently gone is a machine that can
      turn a real outage into a permanent hole.
    * UNKNOWN never clears BROKEN. A run that could not measure is not a run
      that found the source healthy.
    """
    today = (today or today_utc()).isoformat()
    entry = ledger.setdefault("sources", {}).setdefault(key, {})
    if label:
        entry["label"] = label
    entry["last_checked"] = today
    # WHICH READING THIS IS, in this entry's own lineage. It is the ordering
    # half of the `recorded_in` pattern the headline_containment baselines use:
    # a merge cannot tell a race from a routine re-merge by comparing states or
    # dates, but it can tell them apart by asking whether one side already SAW
    # the other. A run loads the committed ledger and increments, so a re-merge
    # against that same committed copy is always strictly ahead of it, while two
    # runners that both loaded seq N both write N+1 and are visibly level.
    # See merge_ledgers. Bump it on every observation, UNAVAILABLE included.
    entry["observation_seq"] = int(entry.get("observation_seq") or 0) + 1
    entry["max_effective"] = profile.get("max_effective")
    for field in ("rate_per_year", "rate_long_run_per_year", "cadence_days",
                  "observations", "span_days", "rate_basis_days", "slowed"):
        if profile.get(field) is not None:
            entry[field] = profile[field]
    entry["last_verdict"] = verdict
    entry["last_reason"] = reason
    if p0 is not None:
        entry["p0"] = p0

    if entry.get("state") == UNAVAILABLE:
        return entry

    prior_frontier = entry.get("frontier")
    frontier = profile.get("max_effective")
    if frontier and frontier != prior_frontier:
        if prior_frontier is None or frontier > prior_frontier:
            entry["frontier"] = frontier
            entry["frontier_advanced_at"] = today
        else:
            # The frontier RECEDED: the collector is answering with less history
            # than it used to. That is not freshness, it is loss, and the count
            # floors own it — but it must not be recorded as an advance.
            entry["frontier_receded_at"] = today

    if verdict == FAIL:
        if entry.get("state") != BROKEN:
            entry["state"] = BROKEN
            entry["first_detected"] = today
            entry["attempts"] = entry.get("attempts", 0)
            entry["tried"] = entry.get("tried", [])
        entry["classification"] = classification or entry.get("classification") or DRIFT
        entry["days_dark"] = days_dark(profile, _as_date(today))
    elif verdict == QUIET:
        # Not broken and not clean. It must NOT clear a BROKEN source (still no
        # new data) and must NOT open one (Kansas was audited healthy here).
        entry["advisory"] = "quiet"
        entry["days_dark"] = days_dark(profile, _as_date(today))
        if entry.get("state") != BROKEN:
            entry["state"] = HEALTHY
    elif verdict == PASS:
        was_broken = entry.get("state") == BROKEN
        entry.pop("advisory", None)
        # A PASS closes any open incident (FAIL) AND any quiet stretch (QUIET),
        # so none of the FAIL/QUIET-only fields may survive on it -- see
        # assert_self_consistent. The old code cleared these ONLY when
        # recovering FROM BROKEN, so a QUIET source (days_dark set, state
        # HEALTHY) that then read PASS kept a stale days_dark beside a
        # PASS/HEALTHY entry, a contradiction the well-formedness test rejects.
        for gone in ("days_dark", "classification", "first_detected"):
            entry.pop(gone, None)
        entry["state"] = HEALTHY
        if was_broken:
            entry["recovered_at"] = today
    else:  # UNKNOWN
        if entry.get("state") != BROKEN:
            entry["state"] = entry.get("state") or UNKNOWN
    return entry


#: The fields that describe ONE OBSERVATION: what a single run saw and what it
#: concluded from it. They travel as a SET, from one side or the other, and are
#: never unioned key-by-key. `dict.update()` cannot express a key the winning
#: side REMOVED, and the recovery branch of `record` removes three of these
#: (`first_detected`, `classification`, `days_dark`) precisely to say the
#: incident is over. Unioning put them back beside the PASS that closed them,
#: which is how `warn:MI` came to read BROKEN, `last_verdict: PASS`,
#: `days_dark: 82` and `recovered_at` all at once on 2026-08-20.
OBSERVATION_FIELDS = (
    "state", "last_verdict", "last_reason", "last_checked", "max_effective",
    "p0", "advisory", "days_dark", "classification", "first_detected",
    "recovered_at", "rate_per_year", "rate_long_run_per_year", "cadence_days",
    "observations", "span_days", "rate_basis_days", "slowed",
)


def _seq(entry):
    """Which reading this is in the entry's lineage. Absent reads as 0."""
    try:
        return int(entry.get("observation_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _evidence(entry):
    """The newest record this side actually saw. The empty string sorts first.

    This is what a verdict is a claim ABOUT. BROKEN says "nothing newer than
    this exists"; PASS says "something newer arrived". A side holding a LATER
    value has read data the other side never saw.
    """
    seen = [v for v in (entry.get("frontier"), entry.get("max_effective")) if v]
    return max(seen) if seen else ""


def merge_ledgers(mine, theirs):
    """Fold a concurrently-pushed ledger into this run's, losing nothing.

    Two runners can both write this file, so the commit step retries against
    origin/main and merges rather than overwriting. The rules are the ones the
    ledger itself enforces, applied to a race:

      * UNAVAILABLE is a human's judgement and always wins over either side's
        machine verdict.
      * The EARLIER first_detected survives, so a race cannot reset a BROKEN
        source's age and hand it a fresh clock. Ages that reset are how a
        problem stays permanently new and permanently ignorable.
      * The LATER frontier survives, because the frontier only ever advances.

    WHY A BROKEN SIDE DOES NOT SIMPLY WIN
    -------------------------------------
    It used to: `if cur.state == BROKEN or other.state == BROKEN: BROKEN`. That
    is right for the race it was written for and wrong for the call that
    actually happens. `warn-import.yml` passes `--merge-into origin/main` on
    EVERY run, so `theirs` is normally not a concurrent runner at all: it is the
    PREVIOUSLY COMMITTED state, which this run has already read and superseded.
    So once any source went BROKEN on main, every later run re-merged that
    BROKEN over its own fresh healthy observation and the source could never
    recover -- for any source, not only the one it was noticed on. That is the
    shape this repo has already paid for twice: the alert entry that could not
    clear, the outbox that could not drain. A state machine with no path out.

    Both properties have to hold at once, and either alone is trivial (keep
    BROKEN always; clear it always). They are separated by ORDER, not by state:

      1. `observation_seq` decides. A run loads the committed ledger and
         increments, so a routine re-merge is STRICTLY AHEAD of the copy it is
         merging, and the reading that already saw the other one wins. Two
         genuine racers both loaded seq N and both wrote N+1, so they are level
         and this rule stays silent -- which is the whole point of recording it.
      2. Level, but one side read a LATER record: that side saw data the other
         never did, so its verdict supersedes rather than races.
      3. Level on both: a true race on identical evidence. BROKEN wins, and a
         genuine break is never lost to a runner that finished second.

    The merged entry therefore carries exactly ONE run's self-consistent
    observation. It can never hold one run's verdict beside another's incident.

    REJECTED -- comparing `last_checked`: its resolution is a whole day, and
    two runners race within the same day, so it cannot see the case it would
    have to decide. REJECTED -- evidence recency ALONE: it repairs the ordinary
    recovery (the frontier advances when a source starts publishing again) but
    not an entry already poisoned by this defect, whose committed BROKEN sits
    on the advanced frontier and therefore ties forever. REJECTED -- ageing
    BROKEN out on a clock: CLAUDE.md, a headline incident is closed by a human
    and never by the calendar, and waiting is not neutral.
    """
    out = {"sources": dict((theirs or {}).get("sources") or {})}
    for key, other in ((mine or {}).get("sources") or {}).items():
        cur = out["sources"].get(key)
        if not cur:
            out["sources"][key] = other
            continue
        if cur.get("state") == UNAVAILABLE:
            continue
        if other.get("state") == UNAVAILABLE:
            out["sources"][key] = other
            continue

        # Everything that is NOT one run's observation -- the label, the
        # healer's attempt log, the frontier bookkeeping -- unions as before.
        merged = {k: v for k, v in cur.items() if k not in OBSERVATION_FIELDS}
        merged.update({k: v for k, v in other.items()
                       if k not in OBSERVATION_FIELDS})

        cur_seq, other_seq = _seq(cur), _seq(other)
        cur_ev, other_ev = _evidence(cur), _evidence(other)
        if cur_seq != other_seq:
            winner = cur if cur_seq > other_seq else other
        elif cur_ev != other_ev:
            winner = cur if cur_ev > other_ev else other
        elif cur.get("state") == BROKEN or other.get("state") == BROKEN:
            winner = cur if cur.get("state") == BROKEN else other
        else:
            winner = other
        merged.update({k: v for k, v in winner.items()
                       if k in OBSERVATION_FIELDS})
        if max(cur_seq, other_seq):
            merged["observation_seq"] = max(cur_seq, other_seq)

        # The frontier is a high-water mark, not an observation: it only ever
        # advances, so it takes the later of the two along with the stamp that
        # explains it.
        frontier_side = cur if (cur.get("frontier") or "") >= (
            other.get("frontier") or "") else other
        if frontier_side.get("frontier"):
            merged["frontier"] = frontier_side["frontier"]
            if frontier_side.get("frontier_advanced_at"):
                merged["frontier_advanced_at"] = \
                    frontier_side["frontier_advanced_at"]

        # A BROKEN source keeps the EARLIER first_detected and goes on ageing.
        # A source that is no longer BROKEN keeps no clock at all: carrying one
        # across is how a closed incident comes back wearing a PASS.
        first = [v for v in (cur.get("first_detected"),
                             other.get("first_detected")) if v]
        if merged.get("state") == BROKEN and first:
            merged["first_detected"] = min(first)
        elif merged.get("state") != BROKEN:
            merged.pop("first_detected", None)

        # The healer's bookkeeping is cumulative, so a race must not discard an
        # attempt the other side recorded.
        attempts = [v for v in (cur.get("attempts"), other.get("attempts"))
                    if isinstance(v, int)]
        if attempts:
            merged["attempts"] = max(attempts)
        tried = list(cur.get("tried") or [])
        for item in (other.get("tried") or []):
            if item not in tried:
                tried.append(item)
        if tried or "tried" in merged:
            merged["tried"] = tried

        # KEY ORDER IS PART OF THE ARTEFACT. This file is committed and read
        # by humans in diffs, so a merge that reshuffles 46 untouched entries
        # buries the one entry it actually changed. Emit the winner's own key
        # order -- which is `record`'s -- and append whatever only the other
        # side carried.
        order = [k for k in winner if k in merged]
        order += [k for k in cur if k in merged and k not in order]
        order += [k for k in other if k in merged and k not in order]
        order += [k for k in merged if k not in order]
        out["sources"][key] = {k: merged[k] for k in order}
    for key, value in (mine or {}).items():
        if key != "sources":
            out.setdefault(key, value)
    for key, value in (theirs or {}).items():
        if key != "sources":
            out[key] = value
    return out


def broken(ledger, today=None):
    """Every BROKEN source, oldest first. The one place the alarm reads."""
    today = today or today_utc()
    out = []
    for key, e in (ledger.get("sources") or {}).items():
        if e.get("state") != BROKEN:
            continue
        first = _as_date(e.get("first_detected"))
        out.append({"key": key, "age_days": (today - first).days if first else None,
                    **{k: e.get(k) for k in
                       ("label", "classification", "days_dark", "rate_per_year",
                        "p0", "last_reason", "first_detected", "attempts")}})
    out.sort(key=lambda r: (-(r["age_days"] or 0), r["key"]))
    return out


def quiet(ledger):
    """Sources publishing less than expected, but not past the evidence bar.

    Deliberately a separate list from `broken`: a quiet source is a fact about
    the register, not a defect in the collector, and mixing the two is what
    produced the Kansas false positive.
    """
    out = []
    for key, e in (ledger.get("sources") or {}).items():
        if e.get("advisory") == "quiet" and e.get("state") != UNAVAILABLE:
            out.append({"key": key, **{k: e.get(k) for k in
                                       ("label", "days_dark", "rate_per_year",
                                        "rate_long_run_per_year", "p0",
                                        "last_reason")}})
    out.sort(key=lambda r: -(r.get("days_dark") or 0))
    return out


def unavailable(ledger):
    return sorted(k for k, e in (ledger.get("sources") or {}).items()
                  if e.get("state") == UNAVAILABLE)


def unknown_sources(ledger):
    return sorted(k for k, e in (ledger.get("sources") or {}).items()
                  if e.get("state") not in (HEALTHY, BROKEN, UNAVAILABLE))


def describe(rows, limit=None):
    """One line naming the dark sources. Six at once is ONE finding.

    The brief that commissioned this said so explicitly and it is the right
    instinct: a backlog discovered on the first run is a backlog, not six
    incidents, and six emails is how an alert channel gets filtered.
    """
    shown = rows if limit is None else rows[:limit]
    parts = []
    for r in shown:
        bit = f"{r['key']} {r.get('days_dark')}d dark"
        if r.get("rate_per_year"):
            bit += f" (own rate {r['rate_per_year']}/yr, {r.get('classification')})"
        parts.append(bit)
    tail = "" if limit is None or len(rows) <= limit else f", +{len(rows) - limit} more"
    return ", ".join(parts) + tail


def fix_instruction(row):
    """The paste-ready line the weekly digest carries, per the RUNBOOK loop."""
    key = row["key"]
    kind = row.get("classification") or DRIFT
    if kind == HARD_FAILURE:
        what = ("its collector errored or returned nothing, so this is NOT a "
                "parser tweak: check the portal still exists at the URL we cite")
    elif kind == FORMAT_CHANGE:
        what = ("it still answers but fewer rows parse than its own floor, so "
                "compare the live markup against the parser's field mapping")
    else:
        what = ("it answers with its full archive and nothing NEW, so the "
                "listing/pagination/date column it reads has moved")
    return (f"{key} has published nothing new for {row.get('days_dark')} days "
            f"({what}). Fix the one collector: see docs/RUNBOOK.md "
            f"'a collector went dark'.")


# --------------------------------------------------------------------------
def _cli(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true",
                    help="print the committed ledger's BROKEN/UNAVAILABLE rows")
    ap.add_argument("--classify-unavailable", metavar="KEY",
                    help="a HUMAN records that this source cannot be collected")
    ap.add_argument("--reopen", metavar="KEY",
                    help="a HUMAN returns an UNAVAILABLE source to the queue")
    ap.add_argument("--reviewer", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--ledger", default=SOURCE_STATE_LEDGER)
    ap.add_argument("--merge-into", metavar="PATH",
                    help="merge PATH (a concurrently pushed copy) into --ledger")
    args = ap.parse_args(argv)

    try:
        ledger = load_ledger(args.ledger)
    except RuntimeError as exc:
        print(f"UNKNOWN: {exc}")
        return 3

    if args.merge_into:
        try:
            with open(args.merge_into, encoding="utf-8") as fh:
                theirs = json.load(fh)
        except FileNotFoundError:
            theirs = {"sources": {}}
        save_ledger(merge_ledgers(ledger, theirs), args.ledger)
        return 0

    if args.classify_unavailable or args.reopen:
        key = args.classify_unavailable or args.reopen
        if not (args.reviewer and args.reason):
            print("ERROR: --reviewer and --reason are required. A source only "
                  "becomes UNAVAILABLE, or leaves it, on a named human "
                  "judgement with a reason and a date.")
            return 1
        entry = ledger.setdefault("sources", {}).setdefault(key, {})
        if args.classify_unavailable:
            entry.update({"state": UNAVAILABLE, "classification": POLICY,
                          "unavailable_reason": args.reason,
                          "unavailable_reviewer": args.reviewer,
                          "unavailable_since": today_utc().isoformat()})
            for gone in ("first_detected", "days_dark"):
                entry.pop(gone, None)
            print(f"{key}: UNAVAILABLE, recorded by {args.reviewer}")
        else:
            entry.update({"state": UNKNOWN, "reopened_by": args.reviewer,
                          "reopened_reason": args.reason,
                          "reopened_at": today_utc().isoformat()})
            for gone in ("unavailable_reason", "unavailable_reviewer",
                         "unavailable_since"):
                entry.pop(gone, None)
            print(f"{key}: returned to the queue by {args.reviewer}")
        save_ledger(ledger, args.ledger)
        return 0

    rows = broken(ledger)
    for r in rows:
        print(f"BROKEN      {r['key']}: {r.get('days_dark')}d dark, "
              f"{r['age_days']}d in this state, {r.get('classification')}")
        print(f"            {r.get('last_reason')}")
    for key in unavailable(ledger):
        e = ledger["sources"][key]
        print(f"UNAVAILABLE {key}: {e.get('unavailable_reason')} "
              f"(recorded {e.get('unavailable_since')} by "
              f"{e.get('unavailable_reviewer')})")
    for r in quiet(ledger):
        print(f"QUIET       {r['key']}: {r.get('days_dark')}d with no new record, "
              f"recent {r.get('rate_per_year')}/yr vs long-run "
              f"{r.get('rate_long_run_per_year')}/yr. Advisory only: not "
              f"evidence of a break, and not emailed.")
    unk = unknown_sources(ledger)
    if unk:
        print(f"UNKNOWN     {len(unk)} source(s) with too little history to "
              f"judge: {', '.join(unk)}  (not a pass)")
    healthy = sum(1 for e in (ledger.get("sources") or {}).values()
                  if e.get("state") == HEALTHY)
    print(f"{healthy} source(s) HEALTHY ({len(quiet(ledger))} of them QUIET), "
          f"{len(rows)} BROKEN, {len(unavailable(ledger))} UNAVAILABLE, "
          f"{len(unk)} UNKNOWN.")
    # A backlog is a finding, not a failure: exit 0 so a normal morning does not
    # manufacture a red run. ops_status is what escalates it to a session.
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
