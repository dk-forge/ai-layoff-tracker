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
# Open incidents. Also committed, and for a stronger reason than the baseline:
# an incident must outlive the condition that raised it. See INCIDENTS_PATH's
# own section below.
INCIDENTS_PATH = HERE / "headline_incidents.json"
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

    # The params that make a query pick rows BY DATE. Only a headline carrying
    # one of these has a date basis at all; see `date_windowed`.
    _DATE_PARAMS = ("trailing_days", "from", "to", "years", "quarters", "months")

    @property
    def date_windowed(self):
        """Does this headline select rows by date, and therefore have a basis?

        MEASURED, NOT ASSUMED, and the measurement is the reason three of the
        four headlines below need no basis wiring at all. `alt_db_where()` uses
        `alt_db_date_col()` in exactly one place: the block that applies
        from/to/years/quarters/months. A query carrying none of those adds no
        date predicate, so `date_basis` cannot change which rows it returns.
        Confirmed against the live API on 2026-08-11, effective vs notice:

            ai_all_time         215,065 jobs / 99 entries      identical
            worldwide_all_time  20,383,596 / 63,619            identical
            us_all_time         6,978,103 / 43,368             identical

        `worldwide_recent_90d` is the one that carries a window, and it is not
        identical: 326,218 jobs / 1,371 entries on the effective basis against
        293,826 / 1,178 on the page's own, with a DIFFERENT largest row in each
        (Aeternum Health 20,000 vs Dird Group 18,000).
        """
        return any(k in self.params for k in self._DATE_PARAMS)

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
             "real 50,000-job announcement reads 17% and passes. THE ONLY HEADLINE "
             "HERE WITH A DATE WINDOW, so the only one whose basis is read off the "
             "page (see `date_windowed` and `_page_date_basis`). On the effective "
             "basis this window could not see a notice filed today for a cut "
             "effective in four months — a fresh row, already inside every published "
             "total, invisible to the guard whose whole job is catching fresh rows.",
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
             "domicile — the same COUNTRY basis the reader's own table and exports "
             "use. That word was doing two jobs. The sentence was written before "
             "2.20.4 moved the page's DATE basis, and read as a claim that this slice "
             "matched the reader's view in every respect; it never named a date basis "
             "and does not need one, because this query carries no date filter at all "
             "and `date_basis` is a measured no-op on it (see `date_windowed`).",
    ),
)

# A baseline older than this cannot bound a daily movement, so the movement
# check reports UNKNOWN rather than stretching its budget to fit.
MAX_BASELINE_AGE_DAYS = 14

# ---------------------------------------------------------------------------
# STICKY INCIDENTS: a FAIL is closed by a human, never by the calendar
# ---------------------------------------------------------------------------
#
# THE DEFECT THIS EXISTS FOR, which was two correct guards agreeing to launder
# an open incident on a date nobody chose.
#
#   1. `record_baseline` refuses to advance a FAILING slice. Correct: recording
#      today's figure makes the defect tomorrow's normal. Consequence: the
#      failing slice's baseline is PINNED while the others advance daily.
#   2. A baseline older than MAX_BASELINE_AGE_DAYS returns UNKNOWN, `pending`,
#      and deliberately NOT `suppressed` (see `_out`) — because refusing to
#      record the other stale-baseline UNKNOWNs would freeze the guard
#      permanently unarmed. Also correct, on its own.
#   3. `record_baseline` skipped exactly two things: FAIL and `suppressed`.
#
# So on the fifteenth day the pinned baseline aged out, the slice stopped
# saying FAIL and started saying UNKNOWN-not-suppressed, the recorder wrote the
# FAILING figure as the new baseline, and the next day's comparison was green
# against it. The live us_all_time incident (baseline pinned 2026-08-07T18:23:51Z,
# recorder at ~18:00Z) was on course to erase itself on the 2026-08-22 run.
#
# Two more clocks were widening in the same direction while the baseline sat
# still, which is why "wait and see" was never going to hold either:
#   * `floor = move_floor * span` grows with the span. The live +93,210 US move
#     clears a 20,000/day floor at span 5.0d.
#   * `allowance = |Δentries| * base_mean * mean_factor` grows with every later
#     arrival. At base_mean 160.787 and mean_factor 12 it swallows +93,210 once
#     49 net new entries have landed — rows with nothing to do with the defect.
#
# THE RULE. A rendered FAIL opens an incident here, and from that moment the
# slice's verdict is FAIL, full stop: not by re-deriving it from a formula whose
# inputs keep moving, but because the incident is open. Time cannot close it,
# later rows cannot close it, a stale baseline cannot close it, and an
# unreachable API cannot close it. Only `close_incident` closes it, and it
# demands the three things a human resolution actually produces:
#
#   a reviewer, a reason, THE AFFECTED ROW IDs, and an explicit replacement
#   baseline — the figure the reviewer asserts is correct, stated on purpose
#   rather than inherited from whatever the site happened to read that minute.
#
# This weakens no bound. move_floor, mean_factor, max_share and
# MAX_BASELINE_AGE_DAYS are untouched; the stale-baseline UNKNOWN still records
# for every slice with no incident open, so the guard still cannot freeze
# unarmed. All this removes is the path from "unexplained move" to "normal"
# that had no human on it.

# A closing reason has to be a finding, not a shrug. Rejecting the one-word
# close is the cheapest part of this and the part most likely to be tested by a
# tired session at 2am.
MIN_CLOSE_REASON_CHARS = 40


class IncidentLedgerUnreadable(Exception):
    """The ledger exists and could not be parsed.

    Never degrades to "no incidents open" — that is indistinguishable from a
    laundered incident, and it would make `rm headline_incidents.json` a
    working way to clear a FAIL.
    """


def load_incidents(path=None):
    """{"open": {slice: record}, "closed": [record, ...]}.

    A MISSING file is an empty ledger: this has to bootstrap. A file that is
    present and unparseable raises — see IncidentLedgerUnreadable.
    """
    p = Path(path or INCIDENTS_PATH)
    if not p.exists():
        return {"open": {}, "closed": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IncidentLedgerUnreadable(f"{p}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("open", {}), dict):
        raise IncidentLedgerUnreadable(f"{p}: not an incident ledger")
    return {"open": dict(data.get("open") or {}),
            "closed": list(data.get("closed") or [])}


LEDGER_NOTE = (
    "Open headline incidents, read by data_integrity.MovementInvariant. A slice "
    "listed under `open` reports FAIL regardless of what today's numbers say — "
    "that is the point: the movement formula's own inputs (elapsed span, arriving "
    "rows, baseline age) all widen over time, so an incident left to the calendar "
    "closes itself. Do not hand-edit this file. Close an incident with "
    "`python3 data_integrity.py --close-incident <slice> --reviewed-by ... "
    "--reason ... --rows ... --replacement-jobs ... --replacement-entries ...`, "
    "which is the only path that also writes the replacement baseline."
)


def save_incidents(ledger, path=None):
    p = Path(path or INCIDENTS_PATH)
    payload = {"note": LEDGER_NOTE,
               "written_at": _utc_now_iso(),
               "open": ledger.get("open") or {},
               "closed": ledger.get("closed") or []}
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def open_incident(ledger, name, label, detail, baseline, observed):
    """Record a FAIL as an open incident. Idempotent.

    Re-rendering the same FAIL tomorrow must not restamp `opened_at`: the age of
    an incident is the most useful thing about it, and a rolling one reads as
    fresh forever.
    """
    if name in (ledger.get("open") or {}):
        return False
    ledger.setdefault("open", {})[name] = {
        "slice": name,
        "label": label,
        "opened_at": _utc_now_iso(),
        "detail": detail,
        "baseline_at_open": baseline,
        "observed_at_open": observed,
    }
    return True


def close_incident(name, reviewed_by, reason, rows, replacement_jobs,
                   replacement_entries, path=None, baseline_path=None):
    """Close an incident and install the reviewer's replacement baseline.

    Every argument is a requirement, not a formality:

    `reviewed_by` / `reason`  someone looked, and said what they found. An
        incident closed with "fixed" is an incident nobody can audit later.
    `rows`  the affected row IDs. This is the difference between "the number
        looks fine now" and "these are the rows that moved it". If they cannot
        be named, the cause was not found and the incident is not resolved.
    `replacement_jobs` / `replacement_entries`  the figure the reviewer asserts
        is correct, typed out. Adopting whatever the live API happens to answer
        at closing time is the laundering with a human standing next to it.

    Raises ValueError on any of them, and writes NOTHING when it raises.
    Returns the closed record.
    """
    ledger = load_incidents(path)
    rec = (ledger.get("open") or {}).get(name)
    if not rec:
        raise ValueError(f"no open incident for {name!r} "
                         f"(open: {sorted((ledger.get('open') or {}))})")
    reviewed_by = (reviewed_by or "").strip()
    reason = (reason or "").strip()
    if not reviewed_by:
        raise ValueError("--reviewed-by is required: a closed incident names who reviewed it")
    if len(reason) < MIN_CLOSE_REASON_CHARS:
        raise ValueError(f"--reason must be at least {MIN_CLOSE_REASON_CHARS} characters "
                         f"of actual finding (got {len(reason)})")
    rows = [str(r).strip() for r in (rows or []) if str(r).strip()]
    if not rows:
        raise ValueError("--rows is required: name the row IDs this incident was about. "
                         "If they cannot be named, the cause has not been found")
    try:
        jobs = int(replacement_jobs)
        entries = int(replacement_entries)
    except (TypeError, ValueError):
        raise ValueError("--replacement-jobs and --replacement-entries must both be "
                         "integers: the reviewer states the correct figure explicitly") from None
    if jobs <= 0 or entries <= 0:
        raise ValueError("the replacement baseline must be positive on both axes")

    now = _utc_now_iso()
    closed = dict(rec)
    closed.update({"closed_at": now, "reviewed_by": reviewed_by, "reason": reason,
                   "affected_row_ids": rows,
                   "replacement_baseline": {"jobs": jobs, "entries": entries,
                                            "captured_at": now}})
    ledger.setdefault("closed", []).append(closed)
    ledger["open"].pop(name, None)

    bpath = Path(baseline_path or BASELINE_PATH)
    base = load_baseline(bpath) or {}
    slices = dict(base.get("slices") or {})
    # A close installs a replacement baseline for ONE slice, so it gets its own
    # epoch and any containment pair this slice belongs to reports UNKNOWN —
    # named, never a pass — until the next recorder run advances the whole group
    # together. That is the honest reading: the reviewer's figure and the other
    # half's pinned figure describe different instants, which is exactly the
    # condition that used to be subtracted anyway.
    slices[name] = {"jobs": jobs, "entries": entries, "captured_at": now,
                    BASELINE_EPOCH_KEY: f"close:{name}:{now}"}
    base["slices"] = slices
    base["written_at"] = now
    bpath.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    save_incidents(ledger, path)
    return closed

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


def _headline_params(h, today=None, date_basis=None):
    """Concrete query params. `trailing_days` becomes from=/to= at call time.

    `date_basis` is applied ONLY to a headline that selects rows by date, and it
    is never typed into this file — see `_page_date_basis` for where it comes
    from and why.
    """
    params = dict(h.params)
    days = params.pop("trailing_days", None)
    if days:
        end = today or datetime.now(timezone.utc).date()
        params["from"] = str(end - timedelta(days=int(days)))
        params["to"] = str(end)
    if date_basis and h.date_windowed:
        params["date_basis"] = str(date_basis)
    return params


def _page_date_basis(ctx):
    """(date_basis, problem) — the date basis the LIVE PAGE says it counts on.

    WHY THIS IS NOT A CONSTANT IN THIS FILE. These guards watch numbers a reader
    can see, and a guard on a different basis from the surface it guards is a
    guard that goes green over a wrong published number. On 2026-08-10 the
    page's default moved from the effective date to the filing date; the commit
    said the default "lives in four places and all four moved", and it has since
    been found in six, then seven. Every one of those was a HAND-COPIED default
    that did not get re-typed. Writing `"notice"` here would be the eighth copy,
    and it would be wrong on the day somebody moves the default again.

    So the basis is read from the stamp the page publishes beside its own
    figures (`window.ALT_BOOTSTRAP.aggregate_params`), through the mechanism
    published_figures.py already owns and validates. This deliberately takes
    ONLY `date_basis` from it:

      * `country_basis` is a per-headline decision here — `us_all_time` sets
        `any` on purpose, and blanket-applying the page's would overwrite a
        choice this file made for its own reasons;
      * the SCOPE is never taken. These headlines watch all time, the trailing
        90 days and the AI subset precisely because they are NOT the page's
        query, and `_home_stamp`'s allowlist already refuses to let a page
        narrow its way to green.

    THREE STATES, as everywhere. If the page cannot be reached or does not state
    a stamp, this returns `(None, problem)` and the caller reports UNKNOWN. It
    does NOT fall back to the effective basis: a silent fallback to the basis
    this change exists to stop reading is the same defect with a retry in front
    of it. Cached on ctx, and ctx.fetch is memoised anyway, so the page is
    fetched at most once per run however many slices ask.
    """
    cached = getattr(ctx, "_page_date_basis", None)
    if cached is None:
        import published_figures
        basis, problem = published_figures.home_basis(ctx)
        cached = (None, problem) if basis is None else (basis.get("date_basis"), None)
        ctx._page_date_basis = cached
    return cached


def _headline_query(ctx, h):
    """(params, problem). The query for one headline, on the page's own basis."""
    if not h.date_windowed:
        return _headline_params(h, ctx.today), None
    basis, problem = _page_date_basis(ctx)
    if basis is None and problem:
        return None, problem
    return _headline_params(h, ctx.today, date_basis=basis), None


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
        params, problem = _headline_query(ctx, h)
        if params is None:
            return _out(UNKNOWN,
                        f"{problem} — this headline is windowed by date, so without the "
                        f"page's own basis it is NOT being checked (reading it on the "
                        f"effective basis would guard a population the site does not "
                        f"publish)")
        payload, bad_state, why, err = _fetch_aggregate(ctx, params)
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

    def __init__(self, headlines=HEADLINES, baseline_path=None, incidents_path=None):
        self.headlines = tuple(h for h in headlines if h.watch_movement)
        self.baseline_path = baseline_path or BASELINE_PATH
        self.incidents_path = incidents_path or INCIDENTS_PATH

    def run(self, ctx):
        base = load_baseline(self.baseline_path)
        slices = (base or {}).get("slices") or {}
        try:
            open_incidents = load_incidents(self.incidents_path).get("open") or {}
        except IncidentLedgerUnreadable as exc:
            # We cannot tell an empty ledger from a destroyed one, so no slice
            # gets a verdict and none may be recorded. `suppressed`, because
            # this is a verdict we were not entitled to render — the same rule
            # as the partial cycle, for the same reason.
            per = [(h, _out(UNKNOWN,
                            f"the incident ledger could not be read ({exc}) — an open "
                            f"incident may be hidden, so nothing here is judged and "
                            f"nothing is recorded", pending=True, suppressed=True))
                   for h in self.headlines]
            for h, out in per:
                ctx.observations[h.name] = (out["state"], None, True)
            return _roll_up(self, ctx, per)
        per = []
        for h in self.headlines:
            out = self._one(ctx, h, slices.get(h.name), open_incidents.get(h.name))
            ctx.observations[h.name] = (out["state"], out.get("observed"),
                                        out.get("suppressed", False))
            ctx.details[h.name] = out.get("detail")
            per.append((h, out))
        return _roll_up(self, ctx, per)

    def _one(self, ctx, h, prior, incident=None):
        """The formula's verdict, then the incident's — and the incident wins.

        An open incident is not re-litigated against today's numbers. Every
        input the formula uses drifts in the forgiving direction while an
        incident sits open (the span widens the floor, later arrivals widen the
        allowance, the pinned baseline eventually ages into UNKNOWN), so
        re-deriving the verdict daily is exactly how the incident closes itself.
        """
        out = self._verdict(ctx, h, prior)
        if not incident:
            return out
        return _out(FAIL, self._sticky_detail(h, incident, out),
                    observed=out.get("observed"))

    @staticmethod
    def _sticky_detail(h, incident, out):
        age = _days_since(incident.get("opened_at"))
        aged = f"{age:.0f}d ago" if age is not None else "at an unrecorded time"
        now = out.get("detail") or "no reading this run"
        # The alert email is the main reader of this sentence, and on most days
        # today's reading is word-for-word the incident. Say so instead of
        # printing it twice.
        same = re.sub(r"[\d,.]+", "#", now) == \
            re.sub(r"[\d,.]+", "#", str(incident.get("detail") or ""))
        if same:
            now = "unchanged"
        return (f"OPEN INCIDENT, opened {aged} ({incident.get('opened_at')}): "
                f"{incident.get('detail')} | today's reading: {now} | This stays FAIL "
                f"until a human closes it: `python3 data_integrity.py --close-incident "
                f"{h.name} --reviewed-by <who> --reason <what you found> --rows <ids> "
                f"--replacement-jobs <n> --replacement-entries <n>`. Time, later rows "
                f"and a stale baseline do not close it")

    def _verdict(self, ctx, h, prior):
        params, problem = _headline_query(ctx, h)
        if params is None:
            return _out(UNKNOWN,
                        f"{problem} — this headline is windowed by date, so without the "
                        f"page's own basis its movement is NOT being checked")
        payload, bad_state, why, err = _fetch_aggregate(ctx, params)
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
        window = Scope(params, window_days=max(1, round(span)))
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


# ---------------------------------------------------------------------------
# CONTAINMENT: a subset headline may not move without its superset moving too
# ---------------------------------------------------------------------------
#
# THE DEFECT THIS EXISTS FOR, and why MovementInvariant could not see it.
#
# On 2026-08-08 "United States jobs, all time" rose 92,686 (93,210 by the
# 2026-08-10 reading) while "Worldwide jobs, all time" — of which the US slice
# is a strict subset — rose 14,911. The US movement guard judged that move
# against `allowance = |Δentries| * base_mean * mean_factor`, i.e. against how
# many rows ARRIVED. Nothing arrived: three already-published ERM rows were
# re-scored from "Multiple countries" to "United States". The 18 entries that
# did land bought 34,730 jobs of headroom for a movement they had nothing to do
# with, and at 49 net new entries the identical re-scoring would have bought
# 94,543 and passed in silence.
#
# So the allowance is measured on the wrong axis. This guard adds one that is
# measured on the right one, and it needs no entry counts at all.
#
# THE RULE. For a strict subset S of a superset T, the COMPLEMENT C = T - S is
# a real population, and its figures are exact by subtraction. In ANY
# population a row can only arrive with its jobs or leave with its jobs, so
#
#     Δjobs and Δentries always move in the SAME direction.
#
# When they do not — C loses jobs while gaining rows, or gains jobs while
# losing them — no arrival and no departure explains it. Jobs were re-scored
# across the boundary between two published slices. On 2026-08-10 the
# complement of the US slice read -78,299 jobs on +10 entries, which is that
# condition exactly, and it is that condition whatever the US slice's own entry
# count happened to be.
#
# WHY IT NEEDS NO PARTIAL-CYCLE EXEMPTION, unlike MovementInvariant. A row
# arriving mid-cycle pushes the complement TOWARDS agreement (it adds jobs and
# a row in the same direction), so a partial cycle can hide this verdict but
# can never manufacture one. That makes the FAIL true at the instant it is
# read, which is the same property that keeps Δentries == 0 exempt over there.
#
# WHAT IT DOES NOT CATCH, said plainly. It compares two published slices, so it
# is blind to anything that moves them together — including a move in the
# TOP-level slice itself, which has no superset. Worldwide fell 27,267 on
# 2026-08-11 while gaining 13 entries and passed its own guard because those 13
# entries bought a 50,054 allowance; if the US slice fell with it, this guard
# sees a contained pair and says nothing. What would catch that is the same
# sign rule applied to a slice's OWN movement (arriving rows may not explain
# departing jobs), which is a change to MovementInvariant's allowance clause
# and belongs in its own commit.

#: Declared pairs, subset first. Structurally verified by
#: `containment_problem` at run time and pinned by
#: tests/test_headline_containment.py, so a pair that stops nesting reports
#: UNKNOWN rather than comparing two populations that are not related.
CONTAINMENTS = (
    ("us_all_time", "worldwide_all_time"),
    ("ai_all_time", "worldwide_all_time"),
)

#: Jobs the complement may move against its own row direction before this is a
#: finding. It is worldwide's own `move_floor`, reused rather than reinvented,
#: because the complement IS worldwide minus one slice. Deliberately FLAT, not
#: scaled by the elapsed span: a re-scoring is a step change, not a rate, and
#: every clock in this module that widens with time is one the 2026-08 incident
#: had to be rescued from. Legitimate causes below it are editorial count
#: corrections on standing rows, which is what the corrections log is for.
CONTAINMENT_FLOOR_JOBS = 25000

# ---------------------------------------------------------------------------
# THE PAIR IS ONE OBSERVATION OR IT IS NOTHING
# ---------------------------------------------------------------------------
#
# A containment finding is a subtraction between two baselines. It is only a
# complement if both readings describe the same instant of the data. Until
# 2026-08-15 that was enforced by a TIME WINDOW — `MAX_PAIR_SKEW_DAYS = 1.0`,
# sized on the written assumption that "ordinary drift over that gap is a few
# thousand jobs against a 25,000 floor".
#
# THE DEFECT THAT ASSUMPTION HAS. On 2026-08-14 a signed-off editorial
# correction removed ~42,000 jobs from published rows between 05:06Z and
# 18:26Z. At the 18:26Z run the ai pair FAILED, which held both `ai_all_time`
# and `worldwide_all_time` at their pre-correction figures; the us pair passed
# UNDER ITS FLOOR (-20,159 against 25,000), so `us_all_time` alone advanced to
# the post-correction reading. The pair now straddled the correction: 13 hours
# of skew, inside the one-day window, so the check went right on subtracting
# and asserted -53,476 jobs of re-scoring, every run, forever. No incident could
# be closed against it (nothing opens under a SUPERSET) and the only exit was
# worldwide's baseline ageing past MAX_BASELINE_AGE_DAYS — fourteen days of red
# CI for a defect that did not exist. A magnitude assumption cannot be sized
# for a human correction; it is a step change, and one signed correction can be
# any size at all.
#
# THE RULE THAT REPLACED IT, which is an identity test rather than a bound:
# both baselines of a pair must carry the same `recorded_in` stamp — the id of
# the recorder run that wrote them. Same run, or the pair is not a complement
# and reports UNKNOWN naming both stamps. No correction, of any size, can defeat
# an equality check on a run id, and nothing here widens with the clock.
#
# It is one half of a mechanism; `containment_groups` below is the other. This
# half stops a straddled pair asserting a number. That half stops the recorder
# manufacturing a straddle in the first place, which is what keeps the UNKNOWN
# rare — one recorder cycle after a human close — instead of the check's normal
# resting state.
BASELINE_EPOCH_KEY = "recorded_in"


def containment_groups(pairs=CONTAINMENTS):
    """slice -> the set of slices whose baselines must advance TOGETHER.

    The connected components of the containment graph. `worldwide_all_time` is
    the superset of both declared pairs, so all three published slices are one
    group: holding worldwide for the ai pair's sake while the us slice advances
    is precisely how the 2026-08-14 straddle was manufactured, and a per-PAIR
    rule would have permitted it (the us pair was passing at the time).
    """
    groups = {}
    for a, b in pairs:
        merged = set(groups.get(a, {a})) | set(groups.get(b, {b}))
        for name in merged:
            groups[name] = merged
    return {name: frozenset(members) for name, members in groups.items()}


def containment_problem(sub, sup):
    """None if `sub` is structurally a subset of `sup`, else why it is not.

    Two conditions, and the second is the one a future edit is most likely to
    break:

    1. THE FILTERS NEST. Every param of the superset must appear, identically,
       on the subset; the subset then carries at least one more. `country` and
       `ai` are restrictions over the same table, so adding one can only ever
       remove rows.
    2. THE BASES AGREE. A subset counted on one date basis and a superset on
       another is not a containment relation, it is two different populations
       with a suggestive name. Both sides must be free of a date window — the
       measured no-op case documented on `Headline.date_windowed` — because a
       windowed slice's basis is read off the live page and a pair whose two
       halves could resolve it differently is not comparable.
    """
    if sub.date_windowed or sup.date_windowed:
        return (f"{sub.label} and/or {sup.label} selects rows by date, so the two "
                f"sides can resolve to different date bases and their difference "
                f"is not a complement")
    sub_p, sup_p = dict(sub.params), dict(sup.params)
    for k, v in sup_p.items():
        if sub_p.get(k) != v:
            return (f"{sup.label} filters on {k}={v!r} and {sub.label} does not, "
                    f"so {sub.label} is not inside it")
    if set(sub_p) <= set(sup_p):
        return (f"{sub.label} and {sup.label} carry the same filters, so neither "
                f"contains the other")
    return None


class ContainmentInvariant:
    """A subset headline may not move by more than its superset moved.

    WHAT IT ASSERTS, per declared pair, against the same committed baseline
    MovementInvariant reads: the COMPLEMENT (superset minus subset) did not
    move its jobs against the direction its own rows moved, by more than
    CONTAINMENT_FLOOR_JOBS.

    MISSING DATA. No baseline for either side, a baseline too old to bound a
    movement, two baselines written by different recorder runs (see
    BASELINE_EPOCH_KEY — a pair that straddles anything is UNJUDGED, not clean),
    a pair that does not structurally nest, or a live read that failed ->
    UNKNOWN, never a pass.

    IT CANNOT LAUNDER ITSELF. A FAIL names both slices to `record_baseline`,
    which refuses to advance either of them and opens the sticky incident under
    the subset — because the difference between the two readings is the finding,
    and recording either one makes that difference disappear.
    """

    key = "headline_containment"
    label = "No subset headline moves without its superset"
    reads_live_data = True

    def __init__(self, headlines=HEADLINES, pairs=CONTAINMENTS, baseline_path=None,
                 now=None):
        by_name = {h.name: h for h in headlines}
        self.pairs = tuple((by_name[a], by_name[b]) for a, b in pairs
                           if a in by_name and b in by_name)
        self.baseline_path = baseline_path or BASELINE_PATH
        self.now = now

    def run(self, ctx):
        slices = (load_baseline(self.baseline_path) or {}).get("slices") or {}
        per = []
        for sub, sup in self.pairs:
            out = self._one(ctx, sub, sup, slices)
            if out["state"] == FAIL:
                # Neither reading may become tomorrow's normal, and the subset
                # carries the incident: one finding, one incident.
                holds = getattr(ctx, "containment_holds", None)
                if holds is None:
                    holds = ctx.containment_holds = set()
                holds.update({sub.name, sup.name})
                incidents = getattr(ctx, "containment_incidents", None)
                if incidents is None:
                    incidents = ctx.containment_incidents = {}
                incidents[sub.name] = out["detail"]
            per.append((sub, out))
        return _roll_up(self, ctx, per)

    def _reading(self, ctx, h):
        """({jobs, entries}, None) or (None, _out(...)) for one side."""
        params, problem = _headline_query(ctx, h)
        if params is None:
            return None, _out(UNKNOWN, f"{h.label}: {problem}")
        payload, bad_state, why, err = _fetch_aggregate(ctx, params)
        if bad_state:
            ctx.errors[h.name] = err
            return None, _out(bad_state, f"{h.label}: {why}", pending=_excusable(err))
        totals = (payload or {}).get("totals") or {}
        try:
            return {"jobs": int(totals["jobs"]), "entries": int(totals["entries"])}, None
        except (KeyError, TypeError, ValueError):
            return None, _out(UNKNOWN, f"{h.label}: unusable totals {totals!r}")

    def _one(self, ctx, sub, sup, slices):
        problem = containment_problem(sub, sup)
        if problem:
            return _out(UNKNOWN,
                        f"the declared pair no longer nests ({problem}) — this pair is "
                        f"NOT being checked, which is not the same as clean")

        now = {}
        for h in (sub, sup):
            reading, bad = self._reading(ctx, h)
            if bad:
                return bad
            now[h.name] = reading

        priors = {}
        for h in (sub, sup):
            prior = slices.get(h.name)
            if not isinstance(prior, dict) or "jobs" not in prior or "entries" not in prior:
                return _out(UNKNOWN,
                            f"no recorded baseline for {h.label} — containment against "
                            f"{sup.label if h is sub else sub.label} is UNMEASURED until "
                            f"data-integrity.yml records one", pending=True)
            age = _days_since(prior.get("captured_at"), self.now)
            if age is None:
                return _out(UNKNOWN,
                            f"{h.label}'s baseline has no readable capture time: "
                            f"{prior.get('captured_at')!r}", pending=True)
            if age > MAX_BASELINE_AGE_DAYS:
                return _out(UNKNOWN,
                            f"{h.label}'s baseline is {age:.0f} days old (max "
                            f"{MAX_BASELINE_AGE_DAYS}) — too stale to bound a movement",
                            pending=True)
            priors[h.name] = prior

        epochs = {h.name: priors[h.name].get(BASELINE_EPOCH_KEY) for h in (sub, sup)}
        if not all(epochs.values()):
            missing = [h.label for h in (sub, sup) if not epochs[h.name]]
            whose = (f"neither baseline carries a recorder-run stamp"
                     if len(missing) == 2 else
                     f"{missing[0]}'s baseline carries no recorder-run stamp")
            return _out(UNKNOWN,
                        f"{whose}, so nothing here can tell whether these two readings "
                        f"describe the same instant of the data. This pair is UNJUDGED "
                        f"rather than clean; the next data-integrity.yml run stamps both "
                        f"and re-arms it", pending=True)
        if epochs[sub.name] != epochs[sup.name]:
            return _out(UNKNOWN,
                        f"the two baselines come from DIFFERENT recorder runs "
                        f"({sub.label} from {epochs[sub.name]}, {sup.label} from "
                        f"{epochs[sup.name]}), so anything applied to the data between them "
                        f"— an editorial correction is the measured case — sits inside their "
                        f"difference and their difference is not a complement. This pair is "
                        f"UNJUDGED rather than clean; the next run that advances both "
                        f"together re-arms it", pending=True)

        # The claim itself, before any arithmetic that assumes it.
        for when, sub_r, sup_r in (("now", now[sub.name], now[sup.name]),
                                   ("at the baseline", priors[sub.name], priors[sup.name])):
            if int(sub_r["jobs"]) > int(sup_r["jobs"]) or \
                    int(sub_r["entries"]) > int(sup_r["entries"]):
                return _out(FAIL,
                            f"{sub.label} is larger than {sup.label} {when} "
                            f"({int(sub_r['jobs']):,} jobs / {int(sub_r['entries']):,} entries "
                            f"against {int(sup_r['jobs']):,} / {int(sup_r['entries']):,}). It is "
                            f"published as a strict subset, so either the filter path broke or "
                            f"the two are not counting the same population")

        d_jobs = ((now[sup.name]["jobs"] - int(priors[sup.name]["jobs"]))
                  - (now[sub.name]["jobs"] - int(priors[sub.name]["jobs"])))
        d_entries = ((now[sup.name]["entries"] - int(priors[sup.name]["entries"]))
                     - (now[sub.name]["entries"] - int(priors[sub.name]["entries"])))
        shown = (f"{sup.label} minus {sub.label} moved {d_jobs:+,} jobs on "
                 f"{d_entries:+,} entries")

        if d_jobs == 0:
            return _out(PASS, f"{shown} — the complement's jobs did not move")
        same_direction = (d_jobs > 0) == (d_entries > 0) and d_entries != 0
        if same_direction:
            return _out(PASS, f"{shown} — jobs and rows moved together, so rows explain it")
        if abs(d_jobs) <= CONTAINMENT_FLOOR_JOBS:
            return _out(PASS, f"{shown}, under the {CONTAINMENT_FLOOR_JOBS:,} floor")
        moved_in = "into" if d_jobs < 0 else "out of"
        return _out(FAIL,
                    f"{shown}. A row can only arrive with its jobs or leave with its jobs, so "
                    f"nothing that arrived or left moved these {abs(d_jobs):,} jobs {moved_in} "
                    f"{sub.label}: rows that were ALREADY PUBLISHED were re-scored across the "
                    f"boundary between these two slices. This is true however many entries "
                    f"arrived, which is why the movement guard's allowance cannot see it. "
                    f"Check the last reconcile-supersets run, any country/AI relabel job, and "
                    f"the corrections log")


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


class RollingRecallInvariant:
    """The coverage figure is fresh, and it names the slices it could not compute.

    WHAT IT ASSERTS, AND WHAT IT DELIBERATELY DOES NOT. It asserts that
    railway/rolling_recall_measurement.json exists, is younger than
    rolling_recall.MAX_MEASUREMENT_AGE_DAYS, and reports every slice it
    declared. It does NOT assert a floor.

    That absence is the design, not an omission. RecallFloorInvariant already
    owns the tripwire, and it can own one because its denominator is FROZEN: a
    fall there cannot be sampling noise. This measurement's denominator is a
    rolling twelve months of SEC Item 2.05 filings and it changes every month,
    so a drop can be a quiet quarter of filings rather than a coverage loss. A
    floor over a moving denominator is a false-alarm generator, and this repo
    already knows what eight identical emails in one afternoon do to an alert
    channel.

    WHAT IT IS FOR, THEN. The failure it exists to catch is not "coverage fell",
    it is "the coverage number stopped being computed and nobody noticed" — the
    exact failure that left a hand-maintained comparison file 24 days stale
    while every check in the repo read green. A figure whose age cannot be read
    is UNKNOWN, and UNKNOWN is not a pass.

    A slice that could not be computed this run makes the whole check UNKNOWN
    rather than dropping out of an average. See rolling_recall.judge().
    """

    key = "rolling_recall_fresh"
    label = "The rolling coverage measurement is current"
    reads_live_data = False        # reads the committed measurement, not the site

    def __init__(self, measurement_path=None):
        self.measurement_path = measurement_path

    def run(self, ctx):
        try:
            import rolling_recall
        except ImportError:                                  # pragma: no cover - path fallback
            sys.path.insert(0, str(HERE))
            import rolling_recall
        measurement = rolling_recall.load_measurement(self.measurement_path)
        state, detail = rolling_recall.judge(measurement)
        return Result(self, state, detail=detail,
                      pending=(state == UNKNOWN and measurement is None))


class ErmProvenanceInvariant:
    """A published ERM row still carries the country it was imported with.

    WHAT IT ASSERTS. That the committed measurement in
    railway/erm_provenance_measurement.json found zero published ERM rows whose
    stored `country` disagrees with the country `erm_import.py` wrote into that
    row's OWN excerpt at import time, and zero rows it could not read. The
    reasoning, the regex and what the check cannot see live in
    railway/erm_provenance_check.py's docstring; the bound lives in its
    `judge()`, so this dashboard, that script's exit code and the tests read one
    definition.

    WHY THIS IS A CHECK AT ALL. Every other guard here watches a number. This
    one watches PROVENANCE: it answers "has an already-published row been
    re-scored since it was imported?" with no history table, no snapshot and no
    timestamp, because the answer is sitting in the row's own published text.
    It is the only thing in the repo that could have named the three rows behind
    the 2026-08 US headline incident on the day, and it was written during that
    incident and then held back until the correction landed — which made it a
    check nobody ran, which is the same as no check.

    WHY IT READS A FILE AND NOT THE LIVE API, like RecallFloorInvariant and
    unlike everything else here: /query has no source_type filter, so the
    measurement is a 319-request pass over the whole corpus that took ~25
    minutes on 2026-08-12. ops_status is the first command of every session and
    a dashboard that is slow stops being run. erm-provenance-check.yml
    re-measures weekly and commits; the consequence is stated rather than
    hidden — a silent re-scoring is caught within a week, not within a day.

    MISSING DATA. No measurement file, an unreadable one, one older than
    erm_provenance_check.MAX_MEASUREMENT_AGE_DAYS, or one with unparseable
    excerpts in it -> UNKNOWN, never a pass.
    """

    key = "erm_provenance"
    label = "ERM rows still carry the country they were imported with"
    reads_live_data = False        # reads the committed measurement, not the site

    def __init__(self, measurement_path=None):
        self.measurement_path = measurement_path

    def run(self, ctx):
        try:
            import erm_provenance_check
        except ImportError:                                  # pragma: no cover - path fallback
            sys.path.insert(0, str(HERE))
            import erm_provenance_check
        measurement = erm_provenance_check.load_measurement(self.measurement_path)
        state, detail = erm_provenance_check.judge(measurement)
        # Same rule as recall_floor: a measurement that has never been written
        # is PENDING — still UNKNOWN on the dashboard, in the ledger and in the
        # daily workflow's exit code, but the unit suite may skip rather than
        # redden a push on a checkout where the weekly job has not run yet.
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

    AND THE PROJECTION IS NOT ALLOWED TO OVERRULE A COMPLETED PASS (2026-08-14).
    `oldest_unarchived_checked_at` is a measurement of the achieved cycle: every
    un-archived URL was attempted within that many days. The projection is an
    inference from a 48-hour throughput sample, and it is sound only while
    throughput is CAPACITY-limited. It is not: re-checks sit behind
    ALT_ARCHIVE_RECHECK_DAYS, so they arrive in convoys and the server hands out
    nothing between them (run 31756911580 read "batch 2: 0 candidate URL(s)"
    against a 3,480 pool — finished, not slow). Sampling that trough gave
    "296/day, 11.7d cycle" for a pool whose own timestamps showed a full pass in
    3.9 days, and reddened CI for three days. So the projection may FAIL only
    while the direct reading does not already show the pool completing inside
    the same projected bound. No bound moved; the 2026-08-04 case it was written
    from (8.6d age) still fires, because 8.6 + 1 is past the 8d projected bound
    and nothing contradicts it.

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

        # THE PROJECTION IS AN INFERENCE. THE AGE IS A MEASUREMENT.
        #
        # `age` is the oldest last-attempt in the whole un-archived pool, so
        # "3.9d" says something the projection cannot: EVERY un-archived URL was
        # attempted within the last 3.9 days, i.e. a full pass over the pool
        # completed in 3.9 days. It is also starvation-proof — the 2026-08-02
        # defect where a freshly restamped top slice cycled every 72h while
        # everything below it starved forever shows up here as a growing oldest
        # age, which is exactly why this reading leads.
        #
        # `pool / (rechecked_recent / 48h)` is an inference, and it is only sound
        # while throughput is CAPACITY-limited. Re-checks are gated: a URL is
        # ineligible until ALT_ARCHIVE_RECHECK_DAYS after its last attempt, so
        # they arrive in convoys and the server hands out nothing in between. On
        # 2026-08-14 run 31756911580 processed its first batch and then read
        # "batch 2: 0 candidate URL(s)" against a pool of 3,480 — the run was not
        # slow, it was finished. Sampling that trough over a 48h window while the
        # cycle is ~4 days yields 296/day and "11.7d cycle", against a pool the
        # site's own timestamps prove was fully traversed in 3.9 days.
        #
        # A rate sampled over a window SHORTER than the cycle it is estimating
        # cannot overrule a completed pass. So the projection may only FAIL while
        # the direct reading does not already demonstrate the promise being kept
        # inside the same projected bound. NOTHING IS WIDENED: PROMISE_DAYS,
        # RUN_GRANULARITY_DAYS, PROJECTED_MAX_AGE_DAYS and MAX_AGE_DAYS are
        # untouched, and the 2026-08-04 reading this projection was written from
        # (8.6d age, ~500/day, 3,864 due) still FAILS on it — 8.6 + 1 = 9.6 is
        # past the 8d projected bound, so the direct reading contradicts nothing
        # and the early warning fires two days before the age bound, as designed.
        # The bound this trades against is the age one, which is unchanged and
        # still the thing that goes red if a real stall follows.
        direct_worst = age + self.RUN_GRANULARITY_DAYS
        measured_pass = direct_worst <= self.PROJECTED_MAX_AGE_DAYS
        window_h = int(payload.get("recheck_window_hours") or 0)

        gate_days = int(payload.get("recheck_days") or 0)
        if worst == float("inf"):
            # Zero re-checks in the window is only excusable while NOTHING WAS
            # DUE: every URL in the pool was attempted more recently than the
            # eligibility gate, so the server had nothing to hand out and the
            # run finished in five minutes on an empty batch. The moment the
            # oldest attempt is older than the gate there ARE overdue URLs, and
            # zero re-checks then is a stopped cron — caught within a day of the
            # gate rather than waiting out the 10d reading.
            if gate_days and age <= gate_days:
                return Result(self, PASS, observed=round(age, 1),
                              detail=f"{shown} — nothing was re-checked in the last {window_h}h "
                                     f"because nothing was DUE: the whole {pool:,}-URL pool was "
                                     f"attempted inside the {gate_days}d eligibility gate, and "
                                     f"the pass completed in {age:.1f}d")
            return Result(self, FAIL, observed=0,
                          detail=f"{shown}, but NOTHING was re-checked in the last "
                                 f"{window_h}h against a "
                                 f"pool of {pool:,} — the reading is only inside the bound "
                                 f"because the ageing has not caught up yet. The cron is "
                                 f"stopped; check archive-backfill.yml")
        rate = (f"{pool:,} due at a measured {per_day:,.0f}/day = "
                f"{worst - self.RUN_GRANULARITY_DAYS:.1f}d cycle, "
                f"{worst:.1f}d worst age")
        if worst > self.PROJECTED_MAX_AGE_DAYS and not measured_pass:
            return Result(self, FAIL, observed=round(worst, 1),
                          detail=f"{shown} — inside the {self.MAX_AGE_DAYS}d bound TODAY, but "
                                 f"{rate}, past the {self.PROJECTED_MAX_AGE_DAYS}d projected "
                                 f"bound ({self.PROMISE_DAYS}d promise + "
                                 f"{self.RUN_GRANULARITY_DAYS}d run granularity). The re-check "
                                 f"promise is about to become false and the slack is what is "
                                 f"hiding it; raise throughput in archive-backfill.yml")
        if worst > self.PROJECTED_MAX_AGE_DAYS:
            return Result(self, PASS, observed=round(age, 1),
                          detail=f"{shown}, so the whole pool completed a pass in {age:.1f}d "
                                 f"({direct_worst:.1f}d worst age, inside the "
                                 f"{self.PROJECTED_MAX_AGE_DAYS}d projected bound). The {window_h}h "
                                 f"throughput sample ({rate}) disagrees, and is not believed: a "
                                 f"rate sampled over {window_h / 24:.0f}d cannot measure a "
                                 f"{age:.1f}d cycle whose re-checks arrive in convoys behind the "
                                 f"eligibility gate")
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


def _days_since(stamp, now=None):
    """Age of an ISO stamp in days. `now` is injectable so a test that pins a
    real historical reading does not rot as the wall clock moves past it."""
    if not stamp:
        return None
    try:
        when = datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return max(0.0, ((now or datetime.now(timezone.utc)) - when).total_seconds() / 86400.0)


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
    # The movement guard measures a headline's move against how many ROWS
    # ARRIVED, and a re-scoring moves a headline while nothing arrives. This one
    # measures the same move against the slice that contains it, and needs no
    # entry counts at all. See the CONTAINMENT section above for the 2026-08
    # incident it is written from.
    ContainmentInvariant(),
    DenominatorProvenanceInvariant(),
    # The six above all ask "is a published number wrong?". This one asks the
    # other half of the question — "is a number MISSING?" — which nothing here
    # could ask before 2026-08-01, because recall_precision.py had no threshold
    # and returned 0 whatever it measured.
    RecallFloorInvariant(),
    # RecallFloorInvariant watches a FROZEN set, so it answers "have we lost
    # what an editor confirmed we held?" and cannot answer "what is coverage
    # NOW" — its window closed on 2026-06-30. This one watches the rolling
    # re-enumeration that does age with the data, and asserts only that the
    # figure is still being computed. No floor, on purpose: see the class.
    RollingRecallInvariant(),
    # And this one asks a third question neither of those can: has a row that is
    # ALREADY published been quietly re-scored since it was imported? It reads
    # each ERM row's own import-time excerpt back out of the published text, so
    # it needs no history table and no timestamp.
    ErmProvenanceInvariant(),
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
        self.details = {}         # slice name -> its sentence, so an incident records WHY

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


def record_baseline(ctx, report, path=None, incidents_path=None, headlines=HEADLINES):
    """Advance the committed baseline — but never over a FAILING slice.

    This is the anti-masking rule and it is the reason the recorder lives beside
    the check instead of in the workflow. If a headline moved in a way no row
    explains, recording today's figure would make tomorrow's comparison green
    against the wrong number, and the guard would have laundered the defect
    instead of catching it. A failing slice keeps yesterday's baseline and keeps
    failing until a human resolves it.

    A FAIL also OPENS A STICKY INCIDENT here, and an open incident is the second
    lock on the same door: the slice is refused whatever state it reports later.
    The first lock is MovementInvariant returning FAIL for an open incident at
    all, and one lock was demonstrably not enough — the guard that opened the
    door was the one that had been reasoned about least (a baseline aged past
    MAX_BASELINE_AGE_DAYS reports UNKNOWN, unsuppressed, and used to be
    recordable). Anything that stops rendering the sticky FAIL still cannot get
    a number past this loop.

    Returns (written, [notes]).
    """
    path = Path(path or BASELINE_PATH)
    current = load_baseline(path) or {}
    slices = dict(current.get("slices") or {})
    labels = {h.name: h.label for h in headlines}
    notes = []
    try:
        ledger = load_incidents(incidents_path)
    except IncidentLedgerUnreadable as exc:
        # No advance at all. An unreadable ledger cannot rule out an open
        # incident on any slice, and a baseline written in that state is a
        # baseline nobody can vouch for.
        return False, [f"the incident ledger could not be read ({exc}) — NO baseline "
                       f"was advanced; fix or restore railway/headline_incidents.json"]
    open_before = set(ledger.get("open") or {})
    ledger_changed = False
    # A containment FAIL is the third thing that stops a baseline advancing, and
    # it is the only one whose finding lives in the DIFFERENCE between two
    # slices rather than in either reading. Recording either side erases it, so
    # both are held; the incident opens under the subset, because one finding
    # gets one incident.
    c_holds = getattr(ctx, "containment_holds", None) or set()
    c_incidents = getattr(ctx, "containment_incidents", None) or {}
    # PASS 1: open the incidents this reading earns, and decide per slice
    # whether its own baseline may advance.
    held = {}
    for name, (state, observed, suppressed) in sorted(ctx.observations.items()):
        if name in c_incidents and observed is not None:
            if open_incident(ledger, name, labels.get(name, name), c_incidents[name],
                             slices.get(name), observed):
                ledger_changed = True
                notes.append(f"{name}: INCIDENT OPENED by the containment check — it "
                             f"moved further than the slice that contains it, and that "
                             f"is true however many rows arrived")
        if state == FAIL and observed is not None:
            detail = (getattr(ctx, "details", {}) or {}).get(name) \
                or f"{name} FAILED the headline movement check"
            if open_incident(ledger, name, labels.get(name, name), detail,
                             slices.get(name), observed):
                ledger_changed = True
                notes.append(f"{name}: INCIDENT OPENED — it now reports FAIL until a "
                             f"human closes it, not until the numbers drift back")
        if name in c_holds:
            held[name] = ("CONTAINMENT FAILED on a pair this slice is part of, "
                          "baseline deliberately NOT advanced (the finding is the "
                          "difference between the two readings; recording either "
                          "erases it)")
        elif name in open_before or name in (ledger.get("open") or {}):
            held[name] = (f"OPEN INCIDENT, baseline NOT advanced. Only "
                          f"`--close-incident {name}` (reviewer + reason + row IDs + an "
                          f"explicit replacement baseline) can advance it")
        elif observed is None:
            held[name] = "nothing observed, baseline untouched"
        elif state == FAIL:
            held[name] = ("FAILING, baseline deliberately NOT advanced "
                          "(recording it would make the defect tomorrow's normal)")
        elif suppressed:
            # An UNKNOWN that stood in for a verdict this reading was not
            # entitled to render (the partial-cycle case). Recording it would
            # launder exactly the number the check declined to judge, so it is
            # held to the same rule as a FAIL.
            held[name] = ("verdict SUPPRESSED, baseline deliberately NOT advanced "
                          "(recording an unjudged reading is the same laundering as "
                          "recording a failing one)")

    # PASS 2: a containment pair advances as ONE OBSERVATION or not at all.
    #
    # Whatever the reason one member is held for, advancing the others leaves
    # the pair's two baselines on opposite sides of it, and the difference
    # between two readings taken either side of an event is not a complement —
    # it is the -53,476 the check asserted for a day after the 2026-08-14
    # correction landed between a held worldwide baseline and an advanced US
    # one. The straddle is not detectable after the fact from the numbers, so
    # it is made unconstructible instead: the group moves together or waits
    # together. See containment_groups() for why the unit is the whole
    # connected component and not the pair.
    groups = containment_groups()
    spread = {}
    for name in list(held):
        for peer in groups.get(name, ()):            # peers of a held slice
            if peer in ctx.observations and peer not in held:
                spread[peer] = (f"HELD WITH ITS PAIR: {name} could not advance this run, "
                                f"and a containment pair whose halves are recorded on "
                                f"opposite sides of an event is not a complement. Both "
                                f"advance together on the first run that can advance "
                                f"{name}")
    held.update(spread)

    # PASS 3: write. Everything recorded in this call carries ONE epoch stamp,
    # which is what the containment check reads to know two readings were taken
    # together. It is deliberately not a timestamp comparison: run ids are equal
    # or they are not, and no correction of any size can blur that.
    epoch = _utc_now_iso()
    for name, (state, observed, suppressed) in sorted(ctx.observations.items()):
        if name in held:
            notes.append(f"{name}: {held[name]}")
            continue
        slices[name] = {"jobs": observed["jobs"], "entries": observed["entries"],
                        "captured_at": observed["captured_at"],
                        BASELINE_EPOCH_KEY: epoch}
        notes.append(f"{name}: recorded {observed['jobs']:,} jobs / "
                     f"{observed['entries']:,} entries")
    payload = {
        "note": ("Day-over-day observations of the published headlines, read by "
                 "data_integrity.MovementInvariant. Written by data-integrity.yml "
                 "after the checks run. A slice whose movement check FAILED is "
                 "deliberately left at its previous value — do not hand-edit this "
                 "file to clear a failing guard. `recorded_in` is the recorder run "
                 "that wrote the entry: headline_containment subtracts two slices "
                 "only when both carry the SAME stamp, so a pair whose halves were "
                 "written either side of an editorial correction reports UNKNOWN "
                 "instead of asserting the correction as a finding."),
        "written_at": _utc_now_iso(),
        "slices": slices,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if ledger_changed:
        save_incidents(ledger, incidents_path)
    return True, notes


#: Written by tests/test_dedup_live.py when this env var names a path, read by
#: the `Live-data invariants were evaluated` step in tests.yml. See
#: live_data_state below for the whole reason it exists.
VERDICT_FILE_ENV = "LIVE_DATA_VERDICT_FILE"

EVALUATED, NOT_EVALUATED = "evaluated", "unknown"


def live_data_state(report):
    """('evaluated'|'unknown', detail) for the invariants that read the SITE.

    THE DEFECT THIS CLOSES. A live-data incident is raised and cleared under a
    branch-free `<workflow>:live.data` scope, because every branch reads the same
    one wrong number (see railway/ci_alert.py). Clearing it is the half that had
    no evidence behind it: the alerter posted the resolve on any green run of the
    workflow, and `tests/test_dedup_live.py` turns an UNKNOWN live invariant into
    a SKIP — deliberately, so a laptop with no wifi and the two minutes an FTPS
    deploy spends in maintenance mode do not redden a push.

    So on 2026-08-14, between 23:37 and 00:10, the owner got three emails about
    ONE number: RED, then RECOVERED, then RED again. The RECOVERED came from run
    31755860626, in which every live check read `skipped 'site is in its deploy
    maintenance window (HTTP 503)'`. Nothing had recovered. A check that did not
    run is UNKNOWN, and UNKNOWN is not a pass — that rule was already written
    down for the dashboard and the digest, and the resolve path was the one
    reader still guessing.

    A report with no live invariant in it at all is 'unknown' too, not a vacuous
    'evaluated': the caller asked whether the site was checked, and it was not.
    """
    live = [r for r in report.results if getattr(r.inv, "reads_live_data", False)]
    if not live:
        return NOT_EVALUATED, "no invariant that reads the live site was checked"
    unresolved = [r for r in live if r.state == UNKNOWN]
    if unresolved:
        return NOT_EVALUATED, "; ".join(
            f"{r.inv.key}: {r.detail}" for r in unresolved)[:400]
    return EVALUATED, f"{len(live)} live invariant(s) resolved to pass or fail"


def ledger_status(report):
    """(status, entries, detail) for report_source_health / the health page.

    Deliberately maps UNKNOWN to 'degraded', not 'ok': the health page and the
    weekly digest must never show green for a check that did not run."""
    if report.verdict == FAIL:
        return "degraded", len(report.passed), report.one_line()[:240]
    if report.verdict == UNKNOWN:
        return "degraded", len(report.passed), report.one_line()[:240]
    return "ok", len(report.passed), report.one_line()[:240]


def _arg(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) \
        else default


def _multi_arg(argv, flag):
    """Every value after `flag` up to the next `--flag`, comma or space separated.

    `_arg` takes exactly one token, which is correct for --reason and --reviewed-by
    and silently lossy for a list. Both spellings a reviewer would reasonably
    type now mean the same thing:

        --rows 114335 113529 64351
        --rows 114335,113529,64351

    Splitting on commas AND whitespace keeps the old quoted form working, so a
    documented invocation from before this change still records what it says.
    """
    if flag not in argv:
        return []
    out = []
    for tok in argv[argv.index(flag) + 1:]:
        if tok.startswith("--"):
            break
        out.extend(p for p in tok.replace(",", " ").split() if p)
    return out


def _print_incidents(ledger):
    open_ = ledger.get("open") or {}
    if not open_:
        print("OPEN HEADLINE INCIDENTS: none")
        return
    print(f"OPEN HEADLINE INCIDENTS: {len(open_)}")
    for name, rec in sorted(open_.items()):
        age = _days_since(rec.get("opened_at"))
        print(f"  {name}  opened {rec.get('opened_at')}"
              f"{f' ({age:.0f}d ago)' if age is not None else ''}")
        print(f"    {rec.get('detail')}")
    print("  Close one with --close-incident <slice> --reviewed-by ... --reason ... "
          "--rows ... --replacement-jobs ... --replacement-entries ...")


def main(argv=None):
    argv = argv or sys.argv[1:]
    import uuid

    # Both of these are LOCAL and key-free, and neither may run the live checks:
    # closing an incident is a human act on a committed ledger, not a re-read of
    # a site whose current numbers are exactly what must not decide it.
    if "--incidents" in argv:
        _print_incidents(load_incidents())
        return 0
    if "--close-incident" in argv:
        # --rows TAKES EVERY VALUE UNTIL THE NEXT FLAG, and that is the fix.
        #
        # This read `_arg(argv, "--rows", "")`, which takes the single token
        # after the flag and then splits it on commas and spaces. Comma-joined
        # or quoted input worked; the natural `--rows 114335 113529 64351`
        # silently recorded ONLY 114335 and dropped the rest, with no error and
        # a zero exit. On 2026-08-12 that closed the us_all_time incident
        # naming one of the three ERM rows it was about.
        #
        # That is the worst possible field to truncate quietly. `--rows` exists
        # because "if they cannot be named, the cause has not been found" (see
        # close_incident), so a partial list is a closed incident asserting a
        # finding nobody made. Silence is the whole defect: the reviewer typed
        # three IDs, the ledger stored one, and the printed summary is the only
        # place the difference would ever have shown.
        rows = _multi_arg(argv, "--rows")
        try:
            closed = close_incident(
                _arg(argv, "--close-incident"),
                reviewed_by=_arg(argv, "--reviewed-by"),
                reason=_arg(argv, "--reason"),
                rows=rows,
                replacement_jobs=_arg(argv, "--replacement-jobs"),
                replacement_entries=_arg(argv, "--replacement-entries"))
        except (ValueError, IncidentLedgerUnreadable) as exc:
            print(f"REFUSED: {exc}")
            print("Nothing was written. An incident closes on a finding, not on a flag.")
            return 2
        rb = closed["replacement_baseline"]
        # `closed` is the stored record, which carries `label`, not `slice`: this
        # line raised KeyError on EVERY successful close, after the ledger and
        # the replacement baseline had already been written. So the one command
        # in this repo that a human is required to run printed a traceback and
        # exited non-zero on success, which reads as "it failed, run it again".
        # The slice name is the key the record was filed under, not a field
        # inside it, so it comes from the argument.
        print(f"CLOSED {_arg(argv, '--close-incident')} — reviewed by {closed['reviewed_by']}")
        print(f"  rows: {', '.join(closed['affected_row_ids'])}")
        print(f"  replacement baseline: {rb['jobs']:,} jobs / {rb['entries']:,} entries")
        print(f"  COMMIT both {INCIDENTS_PATH.name} and {BASELINE_PATH.name}.")
        return 0

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
