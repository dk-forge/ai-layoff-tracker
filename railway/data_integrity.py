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

USAGE
-----
    from data_integrity import check_all
    report = check_all()          # stdlib only, no keys, ~1 round trip
    report.verdict                # "pass" | "fail" | "unknown"
    report.one_line()             # dashboard/ledger summary

    python3 railway/data_integrity.py            # print + exit 0/2/3
    python3 railway/data_integrity.py --report   # also POST to the health ledger
                                                 # (needs WP_SITE_URL + WP_API_KEY)
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"


class Invariant:
    """One assertion about the LIVE published data.

    Bounds are deliberately loose. They are TRIPWIRES, not the expected number:
    the true figure moves every day as new notices land, so a tight bound would
    cry wolf. Each bound sits just above the value that a specific, already-seen
    double-counting bug produces — so a breach means that bug is back, not that
    the company had a big week. Keep the bound; do not "update" it to whatever
    the site currently says.
    """

    def __init__(self, key, label, params, max_jobs, regression, min_jobs=1):
        self.key = key
        self.label = label
        self.params = params
        self.max_jobs = max_jobs
        self.min_jobs = min_jobs
        self.regression = regression   # what a breach MEANS, in one line


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
)


class Result:
    def __init__(self, inv, state, observed=None, detail="", error=None):
        self.inv = inv
        self.state = state
        self.observed = observed
        self.detail = detail
        self.error = error          # kept so a caller can classify egress blocks

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

    def one_line(self):
        n = len(self.results)
        if self.verdict == FAIL:
            return (f"{len(self.failed)}/{n} live data-integrity check(s) FAILING: "
                    + "; ".join(f"{r.inv.label} = {r.observed}" for r in self.failed))
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


def check_all(fetch=None, timeout=20, invariants=INVARIANTS):
    """Run every live invariant. Stdlib only, no keys, read-only GETs.

    Runs them concurrently so the whole set costs about one round trip — this is
    on the critical path of every session's first command, and a dashboard that
    is slow stops being run.
    """
    import uuid
    fetch = fetch or _default_fetch
    cachebust = uuid.uuid4().hex[:12]      # never let a CDN answer this check
    invs = list(invariants)
    if not invs:
        return Report([])
    with ThreadPoolExecutor(max_workers=min(8, len(invs))) as pool:
        results = list(pool.map(lambda i: _check(i, fetch, timeout, cachebust), invs))
    return Report(results)


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
    report = check_all()
    print("LIVE DATA-INTEGRITY CHECKS")
    for r in report.results:
        mark = {PASS: "PASS   ", FAIL: "FAIL   ", UNKNOWN: "UNKNOWN"}[r.state]
        print(f"  {mark} {r.inv.label}: {r.detail}")
    print(report.one_line())

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
