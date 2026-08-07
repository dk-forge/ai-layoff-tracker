#!/usr/bin/env python3
"""Live DATA-INTEGRITY invariants — one definition, three consumers.

WHY THIS EXISTS (the gap it closes, 2026-07-30)
-----------------------------------------------
`ops_status.py` is the tool CLAUDE.md tells every session to run FIRST, and its
whole job is to say what needs a human. It reported source STALENESS only. On
2026-07-30 `tests/test_dedup_live.py` caught a real live defect — Spirit Airlines
reading 11,069 US-2026 jobs instead of ~7,069, because a news row stopped being
recognised as a subset of the WARN notices for the same layoff and started
stacking on top of them — and CI went red five times, while ops_status printed:

    ACTION NEEDED: 1 item(s) -> newsapi stale

A session could read "1 item needs attention", fix the stale source and walk
away from a company overstated by 4,000 jobs on the live site. Source health
answers "did the collectors run?". It cannot answer "is what they produced
correct?". This module answers the second question, and ops_status now asks it.

WHY THIS SHAPE, AND NOT THE ALTERNATIVES
----------------------------------------
Three designs were on the table. This module is (c), and the other two are
rejected for reasons that are load-bearing enough to write down:

(a) SHELL OUT TO PYTEST / `python -m unittest tests.test_dedup_live`.
    Rejected. ops_status is documented as fast, read-only, dependency-free
    (stdlib only), key-free and usable offline and in an egress-blocked cloud
    session — those properties are why it is the first thing a session runs.
    Spawning the suite drags in `railway/requirements.txt` (requests, etc.),
    which need not be installed, and costs seconds. Worse, it is WRONG on the
    semantics: unittest collapses "could not check" into a green run via
    `skipTest`. test_dedup_live skips on network failure by design — correct for
    CI, fatal for a dashboard, because a skipped guard would render as a clean
    bill of health. See (3) below.

(b) READ THE LAST CI CONCLUSION for that test file (`gh run list`).
    Rejected, and this is the important one. It needs the `gh` CLI, network to
    GitHub, and auth — so it fails exactly in the offline/egress-blocked case
    ops_status is built for. But the real objection is that it reports a CACHED
    VERDICT ABOUT A PAST STATE OF THE DATA. The data here changes without a
    commit: WARN imports land daily, `reconcile-supersets` runs at 12:40 ET, and
    the Spirit defect appeared because a running SUM crossed a threshold — no
    code changed on the day it broke. A green tick from the last push is not
    evidence about the data now. This is precisely the failure the sibling repo
    hit when its ops tool read a stale local file and printed "Nothing queued,
    nothing lost" while 15 runs had been destroyed. We check the live data.

(c) EXTRACT THE INVARIANTS so the test and the dashboard call the SAME code.
    Chosen. The bounds live here once. `tests/test_dedup_live.py` imports them,
    `ops_status.py` imports them, `health_digest.py` imports them. A bound can
    never drift between the guard that fails CI and the dashboard that tells a
    session everything is fine — which would be the same class of bug as the one
    this whole module exists to catch, just one level up.

HONEST DEGRADATION (requirement 3, and the thing to never regress)
------------------------------------------------------------------
Every check resolves to exactly one of three states, never two:

    PASS     we fetched a number and it is inside its bound.
    FAIL     we fetched a number and it is outside its bound.
    UNKNOWN  we did not get a number. Network down, egress-blocked, HTTP error,
             non-JSON body, deploy-maintenance 503.

UNKNOWN is NEVER folded into PASS. `Report.verdict` is "fail" if anything failed,
else "unknown" if anything is unknown, else "pass" — a confirmed defect outranks
an unverifiable one, and an unverifiable one outranks silence. Absence of a
signal is not a pass.

WHY THE WEEKLY DIGEST IS NOT ENOUGH
-----------------------------------
`health_digest.py` also reports this (so the owner sees it in email without
reading CI), but the digest runs MONDAYS 12:00 UTC. A live data regression
misleads every reader of the tracker, the press page and the API from the moment
it lands — up to SEVEN DAYS before that email. The digest is the backstop for an
unattended week. The FAST path is ops_status, run at the top of every session,
plus `tests.yml` on every push. Do not move this signal to the digest alone.

TWO KINDS OF CHECK LIVE HERE (added 2026-07-31)
-----------------------------------------------
The original four are NAMED-EVENT tripwires: Coinbase, Spirit, Tyson, AT&T. Each
knows about one duplicate that has already bitten. They are exact, and they are
finite — they say nothing at all about the row that lands tomorrow, and every
incident in the log was a row nobody had a tripwire for yet.

So there are now three SHAPE guards over the same live data, aimed at the
pattern those incidents share rather than at their names:

    headline_concentration     no single row may carry a published headline
    headline_movement          no headline may move in a way the rows do not
                               explain
    dedup_denominator_scoped   the reconciler cannot compute a plausibility test
                               against an all-time cumulative sum, because it
                               cannot compute a sum at all

The third is not a test of behaviour; it asserts that the STRUCTURE which makes
that bug unwritable is still in db.php. The distinction matters: a magnitude
check would never have caught the Spirit defect, because every row in it was
correct and the comparison was not.

A THIRD KIND, ADDED 2026-08-01: IS A NUMBER MISSING?
----------------------------------------------------
Everything above asks whether a published number is WRONG. None of them can see
an event that never arrived, and until now nothing could: recall_precision.py
printed a recall percentage and returned 0 whatever it printed.

    recall_floor    at least MATCHED_FLOOR of a frozen, independently
                    assembled gold set of 57 SEC Item 2.05 workforce
                    reductions is still in the published data

It is the only check here that reads a committed file rather than the live API,
and the reason is in its own docstring. Its bound lives in
railway/recall_goldset.py so the workflow's exit code, this dashboard and the
tests all read one definition.

USAGE
-----
    from data_integrity import check_all
    report = check_all()          # stdlib only, no keys, ~1 round trip
    report.verdict                # "pass" | "fail" | "unknown"
    report.one_line()             # dashboard/ledger summary

    python3 railway/data_integrity.py            # print + exit 0/2/3
    python3 railway/data_integrity.py --report   # also POST to the health ledger
                                                 # (needs WP_SITE_URL + WP_API_KEY)
    python3 railway/data_integrity.py --record-baseline
                                                 # advance headline_baseline.json
                                                 # (never over a FAILING slice)
"""
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
# Day-over-day observations of the published headlines. Committed, because the
# thing being watched changes without a commit and a baseline that lives only in
# a runner is a baseline that resets every night. Written by data-integrity.yml.
BASELINE_PATH = HERE / "headline_baseline.json"
DB_PHP = REPO_ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "includes" / "db.php"


class Invariant:
    """One assertion about the LIVE published data.

    Bounds are deliberately loose. They are TRIPWIRES, not the expected number:
    the true figure moves every day as new notices land, so a tight bound would
    cry wolf. Each bound sits just above the value that a specific, already-seen
    double-counting bug produces — so a breach means that bug is back, not that
    the company had a big week. Keep the bound; do not "update" it to whatever
    the site currently says.
    """

    # Every check declares whether it reads the LIVE site. The degradation
    # contract tests assert "a dead network can never produce a pass", and that
    # claim is only about the checks that ask the network — a structural guard
    # over the source in this checkout is correct to pass with no network at all.
    reads_live_data = True

    def __init__(self, key, label, params, max_jobs, regression, min_jobs=1):
        self.key = key
        self.label = label
        self.params = params
        self.max_jobs = max_jobs
        self.min_jobs = min_jobs
        self.regression = regression   # what a breach MEANS, in one line

    def run(self, ctx):
        return _check(self, ctx.fetch, ctx.timeout, ctx.cachebust)


# ---------------------------------------------------------------------------
# SCOPES: what a number describes, carried with the number
# ---------------------------------------------------------------------------
# The Spirit defect of 2026-07-30 was not a wrong row. Every row was right. The
# comparison was wrong: a numerator describing ±45 days was tested against a
# denominator describing six years. No magnitude check catches that, because
# both numbers are individually correct and individually plausible. The only
# thing that catches it is knowing what each number DESCRIBES.
#
# So in this module a bare int is never compared to a bare int. A quantity
# carries its Scope, and the two comparison helpers below refuse the shapes that
# produced the bug:
#
#   share_of(part, whole)            same scope required. Unbounded is FINE —
#                                    "what fraction of the published all-time
#                                    total is this one row" is a real question.
#   plausibility_ratio(cand, denom)  same scope required AND the denominator must
#                                    be bounded. "Is this plausibly the same
#                                    thing as that" measured against a running
#                                    cumulative sum is the bug itself, and it is
#                                    an exception here, not a judgement call.
#
# The PHP side is guarded structurally too (alt_dedup_window /
# alt_dedup_subset_verdict in db.php, asserted by the
# `dedup_denominator_scoped` invariant below), because that is where the
# reconciler lives. This is the same rule expressed where new checks get written.

UNBOUNDED = None


class ScopeMismatch(Exception):
    """Two quantities describing different filter sets were compared."""


class UnboundedDenominator(Exception):
    """A plausibility test was measured against an all-time cumulative sum.

    This is the 2026-07-30 Spirit defect. It is not a warning."""


class Scope:
    """The filter set, and the time span, a number describes."""

    __slots__ = ("params", "window_days")

    def __init__(self, params=None, window_days=UNBOUNDED):
        self.params = tuple(sorted((str(k), str(v)) for k, v in (params or {}).items()))
        self.window_days = window_days

    @property
    def is_unbounded(self):
        return self.window_days is UNBOUNDED

    def __eq__(self, other):
        return (isinstance(other, Scope) and self.params == other.params
                and self.window_days == other.window_days)

    def __hash__(self):
        return hash((self.params, self.window_days))

    def __repr__(self):
        span = "all time" if self.is_unbounded else f"{self.window_days}d"
        return f"Scope({dict(self.params)}, {span})"


class Quantity:
    """A number that knows what it describes."""

    __slots__ = ("value", "scope", "name")

    def __init__(self, value, scope, name=""):
        self.value = value
        self.scope = scope
        self.name = name

    def __repr__(self):
        return f"Quantity({self.name}={self.value}, {self.scope!r})"


def share_of(part, whole):
    """part / whole, for two quantities describing the SAME thing."""
    if part.scope != whole.scope:
        raise ScopeMismatch(
            f"{part.name or 'part'} describes {part.scope!r} but "
            f"{whole.name or 'whole'} describes {whole.scope!r} — a share of two "
            f"different populations is not a share of anything")
    if not whole.value:
        return 0.0
    return part.value / float(whole.value)


def plausibility_ratio(candidate, denominator):
    """'Is this number plausibly the same thing as that one?'

    Refuses an unbounded denominator outright. If you want to ask this question,
    you must first say over what span the comparison is meant to hold — which is
    exactly the sentence nobody wrote in the reconciler, and it cost 64 companies
    double-counting 60,367 jobs and 43 companies suppressed to zero.
    """
    if denominator.scope.is_unbounded:
        raise UnboundedDenominator(
            f"{denominator.name or 'denominator'} is an all-time cumulative sum "
            f"({denominator.scope!r}). A cumulative sum only grows, so a test "
            f"against it passes until the day it silently does not. Scope it.")
    if candidate.scope != denominator.scope:
        raise ScopeMismatch(
            f"{candidate.name or 'candidate'} describes {candidate.scope!r} but "
            f"{denominator.name or 'denominator'} describes {denominator.scope!r}")
    if not denominator.value:
        return 0.0
    return candidate.value / float(denominator.value)


# ---------------------------------------------------------------------------
# HEADLINES: the published aggregates these guards watch
# ---------------------------------------------------------------------------
class Headline:
    """One published aggregate, and the two bounds that guard it.

    max_share  the largest share of this headline ONE row may carry. Set from
               the observed live maximum with real headroom, so a genuinely big
               event does not trip it but a misparse does. Recorded live figures
               (2026-07-31) are in each entry.
    move_floor jobs per elapsed day below which a movement is not interesting.
    mean_factor how many multiples of the slice's own mean job count each NET
               NEW entry is allowed to carry before the movement counts as
               unexplained by the rows that arrived.
    """

    def __init__(self, name, label, params, max_share, move_floor=0,
                 mean_factor=12, watch_movement=True, note=""):
        self.name = name
        self.label = label
        self.params = params
        self.max_share = max_share
        self.move_floor = move_floor
        self.mean_factor = mean_factor
        self.watch_movement = watch_movement
        self.note = note

    def scope(self):
        return Scope(self.params)


HEADLINES = (
    Headline(
        name="worldwide_recent_90d",
        label="Worldwide, trailing 90 days",
        params={"trailing_days": 90},          # resolved to from=/to= at fetch time
        max_share=0.20,                        # live 2026-07-31: 3.44% (9,891 of 287,562)
        watch_movement=False,                  # the window slides daily; not comparable day over day
        note="The sharp one. A fresh bad row lands here first and the denominator is "
             "small enough to see it: the RI 98,912 misparse would have read 34%, the "
             "AT&T 78,788 test notice 27%, the Coal India by-2050 projection 25%. A "
             "real 50,000-job announcement reads 17% and passes.",
    ),
    Headline(
        name="ai_all_time",
        label="AI-attributed jobs, all time",
        params={"ai": "1"},
        max_share=0.25,                        # live 2026-07-31: 9.85% (21,000 of 213,085)
        move_floor=8000,                       # ~3.8% of the headline. See the tuning note.
        mean_factor=6,
        note="The flagship claim, and the most fragile number on the site: all time it "
             "rests on fewer than 100 rows, so one wrong AI flag on a big cut moves it "
             "by a fifth.",
    ),
    Headline(
        name="worldwide_all_time",
        label="Worldwide jobs, all time",
        params={},
        max_share=0.01,                        # live 2026-07-31: 0.30% (60,000 of 20,191,558)
        move_floor=25000,
        note="The number quoted in the meta description, the FAQ and the press page.",
    ),
    Headline(
        name="us_all_time",
        label="United States jobs, all time",
        params={"country": "United States", "country_basis": "any"},
        max_share=0.02,                        # live 2026-07-31: 0.86% (60,000 of 6,939,141)
        move_floor=20000,
        note="country_basis=any is the documented union of job location and employer "
             "domicile — the same basis the reader's own filter uses.",
    ),
)

# A baseline older than this cannot bound a daily movement, so the movement
# check reports UNKNOWN rather than stretching its budget to fit.
MAX_BASELINE_AGE_DAYS = 14

# The other end of the same rule, and it was missing until 2026-08-02.
#
# A baseline is captured ONCE a day, by data-integrity.yml at 17:30 UTC, 50
# minutes after the reconciler. That is the pairing MovementInvariant is
# calibrated for: two readings a whole ingest cycle apart, so the rows that
# arrived between them are a day's worth of rows. But tests.yml runs the same
# live check on EVERY push, at any hour, and therefore routinely compares a
# reading taken PART WAY through a cycle against a baseline taken at the end of
# the previous one. A partial cycle is not a small day. The rows inside it are
# whatever collector happened to be mid-batch, and collectors differ by an order
# of magnitude in how many jobs a row carries: state WARN rows are hundreds,
# EDGAR and news rows are thousands.
#
# THE INCIDENT. 2026-08-02T03:33Z, SHA 73b2606, worldwide_all_time:
#   +63,899 jobs over 1.0d on +16 entries (20,186,665 -> 20,250,564). The rows
#   that changed carry at most 61,211 and the largest single row is 60,000.
# Twenty minutes later, SHA 11bc4ce at 03:53Z, the same check passed. Nothing
# had been done to it: the committed baseline blob was byte-identical in both
# checkouts (039a0fad) and record_baseline had refused nothing, because the
# recorder had not run in between at all. What was running was `Historical
# backfill (EDGAR)`, 02:39:27Z -> 07:40:04Z — a five-hour writer. Both reads
# landed inside it. At 03:33 the 16 rows that had arrived carried 3,994 jobs
# each, measured against a model built from the standing population's mean of
# 319; by 03:53 more rows had landed and the ratio fell back inside. The verdict
# was a function of where in a batch the sampler happened to land, which is a
# race with the writers, not a finding about the data.
#
# So: below this span, the numerator and the denominator of the plausibility
# test do not describe the same thing, and this check does not render that
# verdict. It reports UNKNOWN — a third state, never a pass — and the daily run,
# which by construction spans a whole cycle, judges the move in full.
#
# What is NOT excused, because no later arrival can undo it: a headline of zero,
# and a headline that moved while the row population stood still. Δentries == 0
# with jobs moving means already-published rows were re-scored, and that is true
# at the instant it is observed regardless of what arrives afterwards. It is
# also the condition this guard was actually built for.
#
# This is deliberately NOT a raised move_floor. The floor is untouched; a bigger
# floor would have been fitted to one afternoon's move and would have gone quiet
# for real defects of the same size at every other hour of the day.
MIN_CYCLE_SPAN_DAYS = 0.95

# TUNING THE MOVEMENT FLOORS — read this before changing one.
#
# max_share is measured: each bound sits well clear of the live reading recorded
# beside it, and test_headline_guards pins that headroom. move_floor could not be
# measured the same way, because nothing had ever recorded this site's day-over-
# day headline deltas — that history starts with headline_baseline.json. The
# floors below are reasoned from the failure modes, not fitted to observed noise.
#
# If one of them proves noisy in its first weeks: RAISE THE FLOOR AND SAY WHY, in
# the commit message and in TECHLOG. Do not delete the check, and do not widen it
# to whatever today's move happened to be — that is how a tripwire becomes a
# rubber stamp. The binding condition is not really the floor anyway: it is
# Δentries == 0, a headline moving while the row population sits still, and no
# amount of ordinary churn produces that.


def _headline_params(h, today=None):
    """Concrete query params. `trailing_days` becomes from=/to= at call time."""
    params = dict(h.params)
    days = params.pop("trailing_days", None)
    if days:
        end = today or datetime.now(timezone.utc).date()
        params["from"] = str(end - timedelta(days=int(days)))
        params["to"] = str(end)
    return params


def _excusable(err):
    """May the unit suite SKIP on this failure rather than redden the push?

    Yes when we never got an answer (offline laptop, egress-blocked runner) or
    when the answer was the deploy's own 503 maintenance window. NO for any other
    HTTP status: the site answered, and answered wrongly, on exactly the
    parameterised path a reader uses. Skipping that is the F27 failure — a guard
    that stays green forever.
    """
    if err is None:
        return False
    if isinstance(err, urllib.error.HTTPError):
        return err.code == 503
    return True


def _out(state, detail, observed=None, pending=False, suppressed=False):
    """One slice's verdict inside a multi-slice check.

    `suppressed` marks the one UNKNOWN that is standing in for a verdict this
    reading was not entitled to render — today, the partial-cycle case. The
    baseline recorder must not advance over it: doing so would let a reading
    that dodged its own FAIL become tomorrow's normal, which is the exact
    laundering record_baseline exists to prevent. It is NOT set for the other
    UNKNOWNs (no baseline, stale baseline, unreachable API), because those
    suppressed no verdict — there was none to render — and refusing to record
    them would freeze the guard permanently unarmed.
    """
    return {"state": state, "detail": detail, "observed": observed,
            "pending": pending, "suppressed": suppressed}


def _roll_up(inv, ctx, per_slice):
    """Collapse per-slice verdicts into one Result, worst state wins.

    FAIL outranks UNKNOWN outranks PASS — the same ordering Report.verdict uses,
    for the same reason: a confirmed defect is more urgent than an unverifiable
    one, and an unverifiable one is never silence. The detail names only the
    slices at the worst state, so an alert email leads with the actual problem.
    """
    states = [o["state"] for _, o in per_slice]
    worst = FAIL if FAIL in states else (UNKNOWN if UNKNOWN in states else PASS)
    shown = [(h, o) for h, o in per_slice if o["state"] == worst]
    detail = "; ".join(f"{h.label}: {o['detail']}" for h, o in shown)
    err = next((ctx.errors.get(h.name) for h, _ in per_slice
                if ctx.errors.get(h.name) is not None), None)
    # PENDING only if EVERY slice at the worst state is pending. One slice that
    # genuinely could not be judged must not be excused by another that is
    # merely waiting on a deploy.
    pending = worst == UNKNOWN and all(o["pending"] for _, o in shown)
    return Result(inv, worst, detail=detail, error=err, pending=pending)


def _fetch_aggregate(ctx, params):
    """(payload, Result-state-or-None, detail, error). Never raises."""
    q = dict(params)
    q["cb"] = ctx.cachebust
    url = BASE + "aggregate?" + urllib.parse.urlencode(q)
    try:
        return (json.loads(ctx.fetch(url, ctx.timeout)) or {}), None, "", None
    except urllib.error.HTTPError as e:
        why = ("site is in its deploy maintenance window (HTTP 503)" if e.code == 503
               else f"live API returned HTTP {e.code}")
        return None, UNKNOWN, why, e
    except Exception as e:                                  # noqa: BLE001 — any transport fault
        return None, UNKNOWN, f"could not reach the live API ({e})", e


class ConcentrationInvariant:
    """No single row may carry a published headline.

    WHAT IT ASSERTS. For each watched headline: the largest SINGLE row counted
    into that headline is below its share bound, and the row's own scope matches
    the headline's. Both numbers come from ONE /aggregate response, produced by
    one WHERE clause over the superset-deduped population (`concentration` block,
    plugin 2.19.235), so the numerator and the denominator cannot describe
    different populations — the mistake that is impossible to see by eye and is
    how every one of these got published.

    WHY A SHARE AND NOT A CEILING. A row-count ceiling has to be re-tuned every
    time the tracker grows, and a big real layoff is not a defect. A share asks
    the question a reader would: how much of this number is one line?

    MISSING DATA. If the `concentration` block is absent the deployed build
    predates 2.19.235 (or the block was removed) — UNKNOWN, never a pass, and the
    daily workflow exits non-zero on UNKNOWN so it cannot sit there quietly. If
    the block's own `headline_jobs` disagrees with `totals.jobs` that is a FAIL:
    the co-scoping this whole check rests on has broken.
    """

    key = "headline_concentration"
    label = "No single row carries a headline"
    reads_live_data = True

    def __init__(self, headlines=HEADLINES):
        self.headlines = tuple(headlines)

    def run(self, ctx):
        per = [(h, self._one(ctx, h)) for h in self.headlines]
        return _roll_up(self, ctx, per)

    def _one(self, ctx, h):
        payload, bad_state, why, err = _fetch_aggregate(ctx, _headline_params(h, ctx.today))
        if bad_state:
            ctx.errors[h.name] = err
            return _out(bad_state, why, pending=_excusable(err))
        conc = (payload or {}).get("concentration")
        totals = (payload or {}).get("totals") or {}
        if not isinstance(conc, dict):
            return _out(UNKNOWN,
                        "no `concentration` block in the response — the deployed plugin "
                        "predates 2.19.235, so one row's share of this headline is "
                        "UNMEASURED, not fine", pending=True)
        try:
            largest = int(conc.get("largest_row_jobs") or 0)
            stated = int(conc.get("headline_jobs") or 0)
            total = int(totals.get("jobs") or 0)
        except (TypeError, ValueError):
            return _out(UNKNOWN, f"non-numeric concentration figures: {conc!r}")
        if total <= 0:
            return _out(FAIL, "the headline is 0 jobs — the rows are gone or the filter path broke")
        if stated != total:
            return _out(FAIL,
                        f"the largest-row figure is scoped to {stated:,} jobs but the "
                        f"headline is {total:,} — numerator and denominator describe "
                        f"different populations, which is the whole failure mode")
        scope = h.scope()
        share = share_of(Quantity(largest, scope, "largest row"),
                         Quantity(total, scope, "headline"))
        who = (conc.get("largest_row_company") or "?").strip()
        row_id = conc.get("largest_row_id")
        shown = f"{share:.2%} ({largest:,} of {total:,}, {who}, row {row_id})"
        if share >= h.max_share:
            return _out(FAIL,
                        f"one row is {shown} — bound is {h.max_share:.0%}. Verify that row "
                        f"against its source before anything quotes this number")
        return _out(PASS, f"largest row {shown}, bound {h.max_share:.0%}")


class MovementInvariant:
    """A published headline may not move in a way the rows do not explain.

    WHAT IT ASSERTS, per watched headline, against the committed baseline in
    railway/headline_baseline.json:

        the move is under the floor                       -> fine
        or the rows that arrived or left can carry it     -> fine
        or ONE arriving row is the whole move             -> fine
        otherwise                                          -> FAIL

    "The rows that changed can carry it" is a plausibility test, and it is written
    through plausibility_ratio() above, so its denominator is scoped to the
    observation window by construction. Ask this question against an all-time
    mean and you get an UnboundedDenominator, not a wrong answer.

    WHAT IT CATCHES, honestly. A mass re-mark or a suppression that moves jobs
    with no matching change in the row population (Δentries ≈ 0 and jobs move —
    the Boeing-suppressed direction, a bad purge-reload, a dedup pass flipping en
    masse); an absurd single row (the NJ 2.4-trillion digit-concatenation would
    trip on the day it landed); a large correction nobody announced.

    WHAT IT DOES NOT CATCH, equally honestly. A 4,000-job un-match on ONE company
    on a day when normal ingest also lands — the Spirit defect itself. At
    headline scale that is inside the daily noise, and pretending otherwise would
    mean a bound that fires every day. Per-company un-matching is caught by the
    four bounded per-company invariants above, and by the reconciler's own
    `changes` diff. This check is for the step change; those are for the drift.

    MISSING DATA. No baseline entry, a baseline older than MAX_BASELINE_AGE_DAYS,
    or a live read that failed -> UNKNOWN. A missing baseline is never a pass,
    and the recorder deliberately refuses to advance a baseline over a FAILING
    slice, so a bad number cannot become tomorrow's normal.

    A BASELINE YOUNGER THAN ONE INGEST CYCLE (MIN_CYCLE_SPAN_DAYS) is the other
    end of that rule and was missing until 2026-08-02. The plausibility test
    models what an arriving row carries from the STANDING population's mean; part
    way through a cycle the rows that have arrived are whichever collector is
    mid-batch, so the verdict depends on when you sampled rather than on the
    data. In that state the plausibility verdict is not rendered at all: UNKNOWN,
    and the recorder refuses to advance over it too. A headline of zero and a
    headline moving on Δentries == 0 keep their FAIL at any span.
    """

    key = "headline_movement"
    label = "No headline moves without rows to explain it"
    reads_live_data = True

    def __init__(self, headlines=HEADLINES, baseline_path=None):
        self.headlines = tuple(h for h in headlines if h.watch_movement)
        self.baseline_path = baseline_path or BASELINE_PATH

    def run(self, ctx):
        base = load_baseline(self.baseline_path)
        slices = (base or {}).get("slices") or {}
        per = []
        for h in self.headlines:
            out = self._one(ctx, h, slices.get(h.name))
            ctx.observations[h.name] = (out["state"], out.get("observed"),
                                        out.get("suppressed", False))
            per.append((h, out))
        return _roll_up(self, ctx, per)

    def _one(self, ctx, h, prior):
        payload, bad_state, why, err = _fetch_aggregate(ctx, _headline_params(h, ctx.today))
        if bad_state:
            ctx.errors[h.name] = err
            return _out(bad_state, why, pending=_excusable(err))
        totals = (payload or {}).get("totals") or {}
        if "jobs" not in totals or "entries" not in totals:
            return _out(UNKNOWN, "the live API returned no totals for this slice")
        try:
            jobs = int(totals.get("jobs") or 0)
            entries = int(totals.get("entries") or 0)
        except (TypeError, ValueError):
            return _out(UNKNOWN, f"non-numeric totals: {totals!r}")
        observed = {"jobs": jobs, "entries": entries, "captured_at": _utc_now_iso()}
        if jobs <= 0:
            return _out(FAIL, "the headline is 0 jobs — the rows are gone or the filter "
                              "path broke", observed=observed)
        if not isinstance(prior, dict) or "jobs" not in prior or "entries" not in prior:
            return _out(UNKNOWN,
                        f"no recorded baseline for this slice ({jobs:,} jobs now) — movement "
                        f"is UNMEASURED until data-integrity.yml records one",
                        observed=observed, pending=True)
        days = _days_since(prior.get("captured_at"))
        if days is None:
            return _out(UNKNOWN,
                        f"baseline has no readable capture time: {prior.get('captured_at')!r}",
                        observed=observed, pending=True)
        if days > MAX_BASELINE_AGE_DAYS:
            return _out(UNKNOWN,
                        f"baseline is {days:.0f} days old (max {MAX_BASELINE_AGE_DAYS}) — too "
                        f"stale to bound a movement; either this checkout is behind main or "
                        f"the daily recorder has stopped",
                        observed=observed, pending=True)

        span = max(1.0, days)
        d_jobs = jobs - int(prior["jobs"])
        d_entries = entries - int(prior["entries"])
        base_mean = int(prior["jobs"]) / float(max(1, int(prior["entries"])))
        floor = h.move_floor * span
        if abs(d_jobs) <= floor:
            return _out(PASS, f"{d_jobs:+,} jobs over {span:.1f}d (floor {floor:,.0f})",
                        observed=observed)

        # Can the CHANGE IN THE ROW POPULATION carry this move? |Δentries| and
        # not max(0, Δentries): a row leaving explains a fall exactly as a row
        # arriving explains a rise, and the AI headline loses a row to a
        # correction often enough that treating removals as unexplained would
        # make this guard cry wolf within the week (observed twice in eight
        # minutes on 2026-08-01: 213,085/98 -> 210,485/97).
        #
        # The denominator is the observation window, never a running total —
        # plausibility_ratio() enforces that, which is the point of routing a
        # one-line division through it.
        window = Scope(_headline_params(h, ctx.today), window_days=max(1, round(span)))
        allowance = abs(d_entries) * base_mean * h.mean_factor
        if allowance:
            ratio = plausibility_ratio(
                Quantity(abs(d_jobs), window, "headline movement"),
                Quantity(allowance, window, "what the rows that changed can carry"))
            if ratio <= 1.0:
                return _out(PASS,
                            f"{d_jobs:+,} jobs on {d_entries:+,} entries over {span:.1f}d "
                            f"— within what the rows that changed carry", observed=observed)

        # One genuinely huge event is a legitimate explanation, but only if a row
        # actually arrived AND that row is itself within its concentration bound.
        # Without the arrival test this clause would excuse a mass re-mark simply
        # because a big row exists somewhere in the population.
        conc = (payload or {}).get("concentration") or {}
        try:
            largest = int(conc.get("largest_row_jobs") or 0)
        except (TypeError, ValueError):
            largest = 0
        one_row_ok = largest and (largest / float(jobs)) < h.max_share
        if d_entries >= 1 and one_row_ok and abs(d_jobs) <= largest * 1.05:
            return _out(PASS,
                        f"{d_jobs:+,} jobs over {span:.1f}d — one arriving row of "
                        f"{largest:,} accounts for it", observed=observed)

        # PARTIAL CYCLE -> UNKNOWN, never a quiet pass and never a FAIL the rest
        # of the day will erase. See MIN_CYCLE_SPAN_DAYS for the incident that
        # put this here. Δentries == 0 is exempt: a headline that moves while the
        # row population stands still is a re-scoring of already-published rows,
        # which is true at the instant it is read and is the defect class this
        # guard exists for, so it keeps its FAIL at any span.
        if days < MIN_CYCLE_SPAN_DAYS and d_entries != 0:
            return _out(UNKNOWN,
                        f"{d_jobs:+,} jobs on {d_entries:+,} entries, but the baseline is only "
                        f"{days * 24:.1f}h old — less than one ingest cycle, so the rows that "
                        f"would explain this move have not all arrived. UNJUDGED, not fine: "
                        f"the daily data-integrity run spans a whole cycle and judges it",
                        observed=observed, pending=True, suppressed=True)

        return _out(FAIL,
                    f"{d_jobs:+,} jobs over {span:.1f}d on {d_entries:+,} entries "
                    f"({int(prior['jobs']):,} -> {jobs:,}). The rows that changed carry at "
                    f"most {allowance:,.0f} and the largest single row is {largest:,}, so "
                    f"NO ROW EXPLAINS THIS. Something re-scored rows that were already "
                    f"published: check the last reconcile-supersets run, any /bulk-purge, "
                    f"and the corrections log", observed=observed)


class DenominatorProvenanceInvariant:
    """The Spirit class of bug must stay unwritable, not merely fixed.

    2.19.227 corrected the reconciler's denominator. It did not stop the next
    author writing the same line, because the company's whole WARN history was
    still one variable away from the comparison. 2.19.235 removed the
    possibility: pass (1) cannot compute a sum at all. Its denominator can only
    come from `alt_dedup_window()`, whose constructor IS the window filter and
    which rejects an absent centre or a window wide enough to be an all-time sum
    in disguise; and the >=50% verdict exists only inside
    `alt_dedup_subset_verdict()`, which throws when handed anything not
    window-scoped.

    THIS CHECK ASSERTS THAT STRUCTURE IS STILL THERE — that nobody has quietly
    reintroduced a local sum or an inline share comparison into the reconciler.
    It reads db.php IN THIS CHECKOUT, so it answers "is the guard in the code you
    are standing in", not "is it deployed". The deployment question is answered
    by headline_concentration: if the live /aggregate carries no `concentration`
    block, the running build predates this work and that reads UNKNOWN.

    MISSING DATA. No db.php reachable from here (running the module outside the
    repo) -> UNKNOWN, never a pass.
    """

    key = "dedup_denominator_scoped"
    label = "Superset dedup cannot use an all-time denominator"
    reads_live_data = False        # reads db.php in this checkout, not the site

    # An inline `if ($x < $y * 0.5)` style plausibility comparison.
    SHARE_COMPARISON = re.compile(r"[<>]=?\s*\$\w+\s*\*\s*0*\.\d")
    # Any locally accumulated sum. The reconciler must not own one; sums come
    # out of the window constructor.
    LOCAL_SUM = re.compile(r"\$\w*sum\w*\s*(=[^=]|\+=)", re.IGNORECASE)

    def __init__(self, php_path=None):
        self.php_path = php_path or DB_PHP

    def run(self, ctx):
        try:
            src = Path(self.php_path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return Result(self, UNKNOWN, pending=True,
                          detail=f"could not read {self.php_path} ({exc}) — the dedup "
                                 f"denominator guard is UNVERIFIED, not fine")
        return self.judge(src)

    def judge(self, src):
        """Split out so a test can feed it a deliberately-broken source."""
        problems = []
        for fn in ("alt_dedup_window", "alt_dedup_subset_verdict"):
            if f"function {fn}(" not in src:
                problems.append(f"{fn}() is gone — the only window-scoped denominator "
                                f"constructor no longer exists")
        verdict_body = _php_function_body(src, "alt_dedup_subset_verdict")
        if verdict_body is not None:
            if "InvalidArgumentException" not in verdict_body or "scoped" not in verdict_body:
                problems.append("alt_dedup_subset_verdict() no longer refuses a denominator "
                                "that did not come from alt_dedup_window()")
        window_body = _php_function_body(src, "alt_dedup_window")
        if window_body is not None and "ALT_DEDUP_MAX_WINDOW_DAYS" not in window_body:
            problems.append("alt_dedup_window() no longer caps how wide a window may be, so "
                            "an all-time sum can be passed off as one")

        body = _php_function_body(src, "alt_reconcile_supersets")
        if body is None:
            problems.append("alt_reconcile_supersets() not found in db.php")
        else:
            if "alt_dedup_window(" not in body:
                problems.append("the reconciler no longer builds its denominator with "
                                "alt_dedup_window()")
            if "alt_dedup_subset_verdict(" not in body:
                problems.append("the reconciler no longer routes its plausibility test "
                                "through alt_dedup_subset_verdict()")
            hit = self.SHARE_COMPARISON.search(body)
            if hit:
                problems.append(f"an inline share comparison is back in the reconciler: "
                                f"{hit.group(0)!r} — that is the 2026-07-30 shape")
            hit = self.LOCAL_SUM.search(body)
            if hit:
                problems.append(f"the reconciler accumulates its own sum again "
                                f"({hit.group(0).strip()!r}); a denominator must come from "
                                f"the window constructor")
        if problems:
            return Result(self, FAIL, detail="; ".join(problems))
        return Result(self, PASS,
                      detail="pass (1) owns no sum; its denominator can only come from "
                             "alt_dedup_window(), and the verdict refuses anything else")


class RecallFloorInvariant:
    """Coverage may not silently fall — the recall claim has to be able to fail.

    WHAT IT ASSERTS. That the committed measurement in
    railway/recall_measurement.json still finds at least
    recall_goldset.MATCHED_FLOOR of the 57 frozen SEC Item 2.05 gold events in
    the published data. The gold set, how it was assembled, why it is
    independent and the per-row editor decisions live in
    docs/recall-reference-sets/sec-item-205-us-2025-07_2026-06.goldset.json.

    WHY IT READS A FILE AND NOT THE LIVE API, unlike every other check here.
    Re-measuring costs ~60 requests to a host that 504'd twice on 2026-07-31,
    and ops_status is on the critical path of every session's first command. So
    recall-precision.yml re-measures weekly and commits the result, and this
    check reads it. The consequence is stated rather than hidden: a recall
    regression is caught within a WEEK, not within a day. That is the cadence
    the measurement job actually runs at, and a ceiling a job cannot meet is not
    a monitor, it is noise that hides real breakage.

    WHAT IT DOES NOT DO. It does not turn 42% into a claim. 42% is recall
    against ONE source family over ONE window at n=57, and the interval around
    it is [30%, 55%]. The floor is a regression tripwire on a FROZEN set, not an
    estimate of coverage — see the module docstring for why those are different
    questions.

    MISSING DATA. No measurement file, an unreadable one, one older than
    recall_goldset.MAX_MEASUREMENT_AGE_DAYS, or one where too much of the set
    was unreachable -> UNKNOWN, never a pass.
    """

    key = "recall_floor"
    label = "Gold-set recall has not fallen"
    reads_live_data = False        # reads the committed measurement, not the site

    def __init__(self, measurement_path=None):
        self.measurement_path = measurement_path

    def run(self, ctx):
        try:
            import recall_goldset
        except ImportError:                                  # pragma: no cover - path fallback
            sys.path.insert(0, str(HERE))
            import recall_goldset
        measurement = recall_goldset.load_measurement(self.measurement_path)
        state, detail = recall_goldset.judge(measurement)
        # A measurement that has never been written is PENDING: still UNKNOWN on
        # the dashboard, on the ledger and in the daily workflow's exit code,
        # but the unit suite may skip rather than redden a push on a checkout
        # where the weekly job has not run yet.
        return Result(self, state, detail=detail,
                      pending=(state == UNKNOWN and measurement is None))


class ArchiveRecheckInvariant:
    """The pages' archive promise is kept, not just typed.

    Every listing surface prints, beside a row whose source has no Wayback
    snapshot yet: "No archive snapshot yet. We re-check weekly; next check by
    <date>." The date is DERIVED (db.php alt_archive_next_check_date) from the
    daily archive-backfill cron (05:25 UTC), the 72h 'pending' retry spacing and
    the 7-day 'unavailable' re-check. This check is what makes that sentence
    falsifiable: it reads the public /archive-coverage summary and FAILS when
    the OLDEST un-archived URL's last attempt is older than the promised
    cadence plus slack.

    THE CADENCE MATH. The slowest promised re-check is 7 days ('unavailable').
    A URL becomes eligible at day 7 and is handed out by the next daily run, so
    the worst honest age is 8 days. Two more days of slack cover a failed or
    missed daily run before a human is called:

        MAX_AGE_DAYS = 7 (promise) + 1 (daily-run granularity) + 2 (slack) = 10

    'queued' URLs (no attempt recorded yet) carry no timestamp to judge; their
    failure mode — the daily run not draining them — shows up here anyway,
    because the same dead cron lets the pending/unavailable pool age past the
    bound (3,900+ such URLs exist, so the pool is never empty in practice).

    TWO HALVES, AND THE SECOND IS THE ONE THAT IS ACTIONABLE.

    The age reading alone fails only once the published promise is ALREADY
    false. Measured here: on 2026-08-04 it read 8.6d and PASSED; on 2026-08-06
    it read 11.7d, and by then the pages had been promising a weekly re-check
    the cron was not delivering for days. Nothing in between could have been
    acted on, because nothing said the margin was 1.4 days wide.

    So the second half projects. The pool the cron must cycle is
    `unarchived_live` (distinct CITED URLs still awaiting a snapshot, join-
    filtered exactly like the candidate query, so orphans the cron correctly
    never retries cannot inflate it). The throughput is `rechecked_recent`
    over `recheck_window_hours` — MEASURED, not the batch size the workflow
    hopes for; those two disagreed by 3x here, because the run was stopping on
    its deadline long before its own limit. Divide:

        projected_cycle_days = unarchived_live / (measured re-checks per day)
        projected_worst_age  = projected_cycle_days + 1 (run granularity)

    and FAIL when the projection exceeds PROMISE_DAYS + 1 = 8, i.e. while the
    two days of slack are still intact. On the 2026-08-04 numbers (3,864 due,
    ~500/day) that is 8.7d projected against a bound of 8 -- it fires two days
    before the reading does, which is the entire point.

    NEITHER HALF WEAKENS THE OTHER. Both must hold. The age FAIL is unchanged;
    the projection can only add failures.

    MISSING DATA. No response, a non-JSON body, or a build that predates the
    coverage fields (plugin < 2.19.248) -> UNKNOWN, never a pass. A build that
    predates the MARGIN fields (plugin < 2.20.2) leaves the projection
    UNMEASURED, which is UNKNOWN too: a check that silently drops half of
    itself when the server is old is the defect this class exists to catch.
    """

    key = "archive_recheck_cadence"
    label = "Unarchived sources are re-checked on the promised cadence"
    reads_live_data = True

    MAX_AGE_DAYS = 10
    # The published sentence: "We re-check weekly". Plus one day of daily-run
    # granularity is the worst age the promise can honestly produce.
    PROMISE_DAYS = 7
    RUN_GRANULARITY_DAYS = 1
    PROJECTED_MAX_AGE_DAYS = PROMISE_DAYS + RUN_GRANULARITY_DAYS   # 8

    @staticmethod
    def _projection(payload):
        """(projected_worst_age_days, per_day, pool) or None if unmeasurable.

        None means the deployed plugin does not publish the margin fields, or
        publishes them as nonsense. It NEVER means "fine".
        """
        try:
            pool = int(payload["unarchived_live"])
            recent = int(payload["rechecked_recent"])
            window_h = int(payload["recheck_window_hours"])
        except (KeyError, TypeError, ValueError):
            return None
        if window_h <= 0 or pool < 0 or recent < 0:
            return None
        per_day = recent / (window_h / 24.0)
        if per_day <= 0:
            # Nothing was re-checked in the whole window. The cycle is not slow,
            # it is stopped; report it as unbounded rather than dividing by zero.
            return (float("inf"), 0.0, pool)
        cycle = pool / per_day
        return (cycle + ArchiveRecheckInvariant.RUN_GRANULARITY_DAYS, per_day, pool)

    def run(self, ctx):
        url = BASE + "archive-coverage?" + urllib.parse.urlencode({"cb": ctx.cachebust})
        try:
            payload = json.loads(ctx.fetch(url, ctx.timeout)) or {}
        except urllib.error.HTTPError as e:
            why = ("site is in its deploy maintenance window (HTTP 503)" if e.code == 503
                   else f"live API returned HTTP {e.code}")
            return Result(self, UNKNOWN, detail=why, error=e, pending=_excusable(e))
        except Exception as e:                                  # noqa: BLE001 — any transport fault
            return Result(self, UNKNOWN, error=e, pending=True,
                          detail=f"could not reach the live API ({e})")
        if not isinstance(payload, dict) or "oldest_unarchived_checked_at" not in payload:
            return Result(self, UNKNOWN, pending=True,
                          detail="no archive-cadence fields in /archive-coverage — the deployed "
                                 "plugin predates 2.19.248, so the re-check promise is "
                                 "UNMEASURED, not fine")
        try:
            pending_n = int(payload.get("pending") or 0)
            unavailable_n = int(payload.get("unavailable") or 0)
            archived_n = int(payload.get("archived") or 0)
        except (TypeError, ValueError):
            return Result(self, UNKNOWN, detail=f"non-numeric archive counts: {payload!r}")
        if archived_n <= 0:
            # 21k archived rows do not vanish legitimately; an empty index under
            # a live table is the archive store broken, not a clean slate.
            return Result(self, FAIL, observed=archived_n,
                          detail="archive index reports 0 archived source URLs — the index is "
                                 "gone or the coverage query broke")
        oldest = payload.get("oldest_unarchived_checked_at")
        if oldest in (None, ""):
            if pending_n == 0 and unavailable_n == 0:
                return Result(self, PASS,
                              detail=f"no URL is awaiting a snapshot (archived {archived_n:,}, "
                                     f"queued {int(payload.get('queued') or 0):,} for the next "
                                     f"daily run)")
            return Result(self, UNKNOWN,
                          detail=f"{pending_n + unavailable_n:,} URLs await a snapshot but no "
                                 f"last-attempt timestamp came back — cannot verify the cadence")
        try:
            when = datetime.strptime(str(oldest), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return Result(self, UNKNOWN,
                          detail=f"unparseable oldest_unarchived_checked_at: {oldest!r}")
        age = (datetime.now(timezone.utc) - when).total_seconds() / 86400.0
        shown = (f"oldest un-archived attempt {age:.1f}d ago "
                 f"({pending_n:,} pending, {unavailable_n:,} not yet in Wayback)")
        if age > self.MAX_AGE_DAYS:
            return Result(self, FAIL, observed=round(age, 1),
                          detail=f"{shown} — bound is {self.MAX_AGE_DAYS}d (7d promise + 1d run "
                                 f"granularity + 2d slack). The pages are promising a re-check "
                                 f"the cron is not delivering; check archive-backfill.yml")

        # The reading is inside the bound. That is not the same as the promise
        # being safe, so project the cycle before calling this a pass.
        projected = self._projection(payload)
        if projected is None:
            return Result(self, UNKNOWN, pending=True,
                          detail=f"{shown}, inside the {self.MAX_AGE_DAYS}d bound — but the "
                                 f"deployed plugin does not publish unarchived_live / "
                                 f"rechecked_recent, so the MARGIN is unmeasured. A reading "
                                 f"inside the bound with an unknown cycle time is how this "
                                 f"promise broke on 2026-08-06; deploy 2.20.2 or later")
        worst, per_day, pool = projected
        if worst == float("inf"):
            return Result(self, FAIL, observed=0,
                          detail=f"{shown}, but NOTHING was re-checked in the last "
                                 f"{int(payload.get('recheck_window_hours') or 0)}h against a "
                                 f"pool of {pool:,} — the reading is only inside the bound "
                                 f"because the ageing has not caught up yet. The cron is "
                                 f"stopped; check archive-backfill.yml")
        rate = (f"{pool:,} due at a measured {per_day:,.0f}/day = "
                f"{worst - self.RUN_GRANULARITY_DAYS:.1f}d cycle, "
                f"{worst:.1f}d worst age")
        if worst > self.PROJECTED_MAX_AGE_DAYS:
            return Result(self, FAIL, observed=round(worst, 1),
                          detail=f"{shown} — inside the {self.MAX_AGE_DAYS}d bound TODAY, but "
                                 f"{rate}, past the {self.PROJECTED_MAX_AGE_DAYS}d projected "
                                 f"bound ({self.PROMISE_DAYS}d promise + "
                                 f"{self.RUN_GRANULARITY_DAYS}d run granularity). The re-check "
                                 f"promise is about to become false and the slack is what is "
                                 f"hiding it; raise throughput in archive-backfill.yml")
        return Result(self, PASS,
                      detail=f"{shown}, bound {self.MAX_AGE_DAYS}d; {rate}, inside the "
                             f"{self.PROJECTED_MAX_AGE_DAYS}d projected bound")


def _php_function_body(src, name):
    """Source between `function name(` and the next top-level closing brace."""
    start = src.find(f"function {name}(")
    if start < 0:
        return None
    end = src.find("\n}\n", start)
    return src[start:end if end > 0 else len(src)]


def _utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_since(stamp):
    if not stamp:
        return None
    try:
        when = datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return max(0.0, (datetime.now(timezone.utc) - when).total_seconds() / 86400.0)


def load_baseline(path=None):
    try:
        return json.loads(Path(path or BASELINE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# The registry. Every entry here is checked by tests/test_dedup_live.py AND
# rendered by ops_status.py. Add a new live invariant here and both pick it up.
#
# All four query the same shape the tracker's own results list uses
# (country_basis=any — the documented union of job-location OR employer-HQ), so
# a breach is what a READER actually sees, not an artefact of an internal query.
INVARIANTS = (
    Invariant(
        key="coinbase_news_vs_news",
        label="Coinbase counts once (news vs news)",
        params={"q": "Coinbase", "country": "United States",
                "country_basis": "any", "years": "2026"},
        max_jobs=1400,
        regression="two news reports of the same 700-job cut (May 5 + Jul 24) are "
                   "summing to 1,400 — exact-count-across-time dedup regressed",
    ),
    Invariant(
        key="spirit_news_vs_warn",
        label="Spirit Airlines counts once (news vs WARN)",
        params={"q": "Spirit Airlines", "country": "United States",
                "country_basis": "any", "years": "2026"},
        max_jobs=11000,
        regression="the May-5 news 4,000 is stacking on top of the ~6-7k May-2 WARN "
                   "sites — news-vs-WARN superset dedup regressed",
    ),
    Invariant(
        key="tyson_warn_revision",
        label="Tyson Amarillo counts once (WARN filed twice)",
        params={"q": "Tyson", "country": "United States",
                "country_basis": "any", "years": "2026"},
        max_jobs=8945,
        regression="the identical 1,761 Amarillo WARN notice filed twice is counting "
                   "twice — within-WARN revision dedup regressed",
    ),
    Invariant(
        key="att_no_fake_outlier",
        label="No fake AT&T 78,788 outlier",
        params={"q": "AT&T", "country": "United States",
                "country_basis": "any", "years": "2026"},
        max_jobs=70000,
        regression="the trashed+suppressed Florida TEST notice (AT&T 78,788) is back "
                   "in the published data",
    ),
    # The four above are NAMED-EVENT tripwires: each one knows about a specific
    # duplicate that has already bitten. They are precise and they are finite —
    # they say nothing about the row that lands tomorrow. The three below are
    # SHAPE guards over the same live data, and between them they cover the
    # pattern all of these incidents share: one row, or one bad comparison,
    # moving a number the site publishes as fact.
    ConcentrationInvariant(),
    MovementInvariant(),
    DenominatorProvenanceInvariant(),
    # The six above all ask "is a published number wrong?". This one asks the
    # other half of the question — "is a number MISSING?" — which nothing here
    # could ask before 2026-08-01, because recall_precision.py had no threshold
    # and returned 0 whatever it measured.
    RecallFloorInvariant(),
    # The listing surfaces promise "we re-check weekly; next check by <date>"
    # beside every source without a Wayback snapshot. This one fails when the
    # live data shows that promise is not being kept.
    ArchiveRecheckInvariant(),
)

# ---------------------------------------------------------------------------
# THE PUBLISHED-FIGURE GUARDS (2026-08-04)
# ---------------------------------------------------------------------------
# Everything above watches the DATA. These watch what the reader is shown, which
# turned out to be a different question: on 2026-08-04 four numbers were wrong on
# the page while every check above passed, because each of them renders without
# erroring. A doughnut slice returning fourteen times what it displays is not a
# data defect at all — the rows are fine, the slice is fine, and the click lands
# somewhere else.
#
# The rule they add is one sentence: a number is published only if it can be
# INDEPENDENTLY RECOMPUTED and the two agree. They live in published_figures.py
# because the registry of figures is long and would bury the data invariants, but
# they are appended to INVARIANTS here, deliberately, so there is exactly ONE
# registry, ONE definition of pass/fail/unknown, and one door through which
# ops_status, the test suite and the weekly digest see all of it.
#
# Imported at the BOTTOM of the module, after Result/_out/_roll_up exist, because
# published_figures reads those primitives back out of here rather than keeping a
# second copy of them.
from published_figures import FIGURE_INVARIANTS      # noqa: E402

INVARIANTS = INVARIANTS + FIGURE_INVARIANTS


class Result:
    def __init__(self, inv, state, observed=None, detail="", error=None, pending=False):
        self.inv = inv
        self.state = state
        self.observed = observed
        self.detail = detail
        self.error = error          # kept so a caller can classify egress blocks
        # PENDING marks an UNKNOWN that this environment cannot answer yet — the
        # deployed build predates the field being read, or the committed baseline
        # has not been written. It is still UNKNOWN everywhere that matters (the
        # dashboard, the ledger, the daily workflow's exit code); it exists so
        # the unit suite can skip rather than redden a push for the two minutes
        # an FTPS deploy takes. It must NEVER be treated as a pass.
        self.pending = pending

    @property
    def transport(self):
        """True when we never got an HTTP answer (DNS/proxy/refused/timeout).

        ops_status uses this to tell 'this environment cannot reach the site'
        (an environment block, exit 3) from 'the site answered wrongly' (a real
        problem). An HTTPError means the site DID answer, so it is never
        transport — same reasoning as ops_status._is_egress_block."""
        return self.error is not None and not isinstance(self.error, urllib.error.HTTPError)


class Report:
    def __init__(self, results):
        self.results = results

    @property
    def failed(self):
        return [r for r in self.results if r.state == FAIL]

    @property
    def unknown(self):
        return [r for r in self.results if r.state == UNKNOWN]

    @property
    def passed(self):
        return [r for r in self.results if r.state == PASS]

    @property
    def verdict(self):
        # Order matters: a CONFIRMED defect outranks an unverifiable one, and an
        # unverifiable one outranks silence. UNKNOWN is never promoted to PASS.
        if self.failed:
            return FAIL
        if self.unknown:
            return UNKNOWN
        return PASS

    @staticmethod
    def _cause(r):
        """What FAILED, in the words that will land in the alert email.

        A bounded per-company invariant has one number and that number IS the
        cause ("Spirit = 11069"). A shape guard covers several slices and its
        cause is a sentence. Rendering the second as "= None" — which it did
        until 2026-07-31 — would hand ci_alert.py a subject line with the defect
        removed from it."""
        return (f"{r.inv.label} = {r.observed}" if r.observed is not None
                else f"{r.inv.label}: {r.detail}")

    def one_line(self):
        n = len(self.results)
        if self.verdict == FAIL:
            return (f"{len(self.failed)}/{n} live data-integrity check(s) FAILING: "
                    + "; ".join(self._cause(r) for r in self.failed))
        if self.verdict == UNKNOWN:
            return (f"{len(self.unknown)}/{n} live data-integrity check(s) UNVERIFIED "
                    f"(not checked, NOT passing): "
                    + ", ".join(r.inv.key for r in self.unknown))
        return f"{n}/{n} live data-integrity checks pass"


def _default_fetch(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _check(inv, fetch, timeout, cachebust):
    params = dict(inv.params)
    params["cb"] = cachebust
    url = BASE + "aggregate?" + urllib.parse.urlencode(params)
    try:
        totals = (json.loads(fetch(url, timeout)) or {}).get("totals") or {}
    except urllib.error.HTTPError as e:
        # 503 is WordPress's own maintenance response, raised deliberately for the
        # seconds the deploy workflow takes to upload the plugin. Not a data
        # regression — but not a pass either. UNKNOWN, explicitly.
        why = ("site is in its deploy maintenance window (HTTP 503)" if e.code == 503
               else f"live API returned HTTP {e.code}")
        return Result(inv, UNKNOWN, detail=why, error=e)
    except Exception as e:
        return Result(inv, UNKNOWN, detail=f"could not reach the live API ({e})", error=e)

    if "jobs" not in totals:
        return Result(inv, UNKNOWN, detail="live API returned no totals for this query")
    try:
        jobs = int(totals.get("jobs") or 0)
    except (TypeError, ValueError):
        return Result(inv, UNKNOWN, detail=f"non-numeric jobs total: {totals.get('jobs')!r}")

    if jobs < inv.min_jobs:
        # Zero is not "clean". Either the company genuinely vanished from the
        # published data (itself a defect) or the filter path broke — both need
        # a human, neither is a pass.
        return Result(inv, FAIL, observed=jobs,
                      detail=f"{jobs} jobs — expected at least {inv.min_jobs}; "
                             "the rows are missing or the filter path broke")
    if jobs >= inv.max_jobs:
        return Result(inv, FAIL, observed=jobs,
                      detail=f"{jobs} jobs (bound < {inv.max_jobs}): {inv.regression}")
    return Result(inv, PASS, observed=jobs, detail=f"{jobs} jobs (bound < {inv.max_jobs})")


class Ctx:
    """Everything a check needs, plus the two side-channels checks write to.

    `fetch` is memoised per run: the shape guards query the same few aggregate
    URLs, and this keeps the whole set at roughly one round trip per distinct
    slice however many checks read it.
    """

    def __init__(self, fetch, timeout, cachebust, today=None):
        self._fetch = fetch
        self._cache = {}
        self.timeout = timeout
        self.cachebust = cachebust
        self.today = today or datetime.now(timezone.utc).date()
        self.errors = {}          # slice name -> transport exception, for Result.transport
        self.observations = {}    # slice name -> (state, {jobs, entries, captured_at}, suppressed)

    def fetch(self, url, timeout):
        if url not in self._cache:
            self._cache[url] = self._fetch(url, timeout)
        return self._cache[url]


def check_all(fetch=None, timeout=20, invariants=INVARIANTS, ctx=None):
    """Run every live invariant. Stdlib only, no keys, read-only GETs.

    Runs them concurrently so the whole set costs about one round trip — this is
    on the critical path of every session's first command, and a dashboard that
    is slow stops being run.

    Pass `ctx` when the caller needs what the checks observed (the baseline
    recorder does); otherwise one is made here.
    """
    import uuid
    fetch = fetch or _default_fetch
    cachebust = uuid.uuid4().hex[:12]      # never let a CDN answer this check
    ctx = ctx or Ctx(fetch, timeout, cachebust)
    invs = list(invariants)
    if not invs:
        return Report([])
    with ThreadPoolExecutor(max_workers=min(8, len(invs))) as pool:
        results = list(pool.map(lambda i: i.run(ctx), invs))
    return Report(results)


def record_baseline(ctx, report, path=None):
    """Advance the committed baseline — but never over a FAILING slice.

    This is the anti-masking rule and it is the reason the recorder lives beside
    the check instead of in the workflow. If a headline moved in a way no row
    explains, recording today's figure would make tomorrow's comparison green
    against the wrong number, and the guard would have laundered the defect
    instead of catching it. A failing slice keeps yesterday's baseline and keeps
    failing until a human resolves it.

    Returns (written, [notes]).
    """
    path = Path(path or BASELINE_PATH)
    current = load_baseline(path) or {}
    slices = dict(current.get("slices") or {})
    notes = []
    for name, (state, observed, suppressed) in sorted(ctx.observations.items()):
        if observed is None:
            notes.append(f"{name}: nothing observed, baseline untouched")
            continue
        if state == FAIL:
            notes.append(f"{name}: FAILING, baseline deliberately NOT advanced "
                         f"(recording it would make the defect tomorrow's normal)")
            continue
        if suppressed:
            # An UNKNOWN that stood in for a verdict this reading was not
            # entitled to render (the partial-cycle case). Recording it would
            # launder exactly the number the check declined to judge, so it is
            # held to the same rule as a FAIL.
            notes.append(f"{name}: verdict SUPPRESSED, baseline deliberately NOT advanced "
                         f"(recording an unjudged reading is the same laundering as "
                         f"recording a failing one)")
            continue
        slices[name] = {"jobs": observed["jobs"], "entries": observed["entries"],
                        "captured_at": observed["captured_at"]}
        notes.append(f"{name}: recorded {observed['jobs']:,} jobs / "
                     f"{observed['entries']:,} entries")
    payload = {
        "note": ("Day-over-day observations of the published headlines, read by "
                 "data_integrity.MovementInvariant. Written by data-integrity.yml "
                 "after the checks run. A slice whose movement check FAILED is "
                 "deliberately left at its previous value — do not hand-edit this "
                 "file to clear a failing guard."),
        "written_at": _utc_now_iso(),
        "slices": slices,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True, notes


def ledger_status(report):
    """(status, entries, detail) for report_source_health / the health page.

    Deliberately maps UNKNOWN to 'degraded', not 'ok': the health page and the
    weekly digest must never show green for a check that did not run."""
    if report.verdict == FAIL:
        return "degraded", len(report.passed), report.one_line()[:240]
    if report.verdict == UNKNOWN:
        return "degraded", len(report.passed), report.one_line()[:240]
    return "ok", len(report.passed), report.one_line()[:240]


def main(argv=None):
    argv = argv or sys.argv[1:]
    import uuid
    ctx = Ctx(_default_fetch, 20, uuid.uuid4().hex[:12])
    report = check_all(ctx=ctx)
    print("LIVE DATA-INTEGRITY CHECKS")
    for r in report.results:
        mark = {PASS: "PASS   ", FAIL: "FAIL   ", UNKNOWN: "UNKNOWN"}[r.state]
        print(f"  {mark} {r.inv.label}: {r.detail}")
    print(report.one_line())

    if "--record-baseline" in argv:
        # Runs AFTER the checks on purpose: today's figure becomes the baseline
        # only once today's figure has been judged against yesterday's.
        written, notes = record_baseline(ctx, report)
        print(f"BASELINE {'written' if written else 'unchanged'}: {BASELINE_PATH}")
        for n in notes:
            print(f"  {n}")

    if "--report" in argv:
        # Posting to the ledger is what puts this on the PUBLIC health page and
        # into the weekly digest. It needs `requests` + a key, so the import is
        # local: `check_all` above must stay importable in a dependency-free,
        # key-free ops_status run.
        try:
            from source_health import report_source_health
            status, entries, detail = ledger_status(report)
            report_source_health("data_integrity", status, entries, detail)
        except Exception as exc:
            print(f"(ledger post skipped: {exc})")

    if report.verdict == FAIL:
        return 2
    if report.verdict == UNKNOWN:
        # Not a clean exit. A run that could not verify has not verified.
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
