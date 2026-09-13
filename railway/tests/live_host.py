"""The one door a test goes through to read the DEPLOYED site.

WHY, 2026-09-13. asktherecruiter.com went down twice in twelve hours under
load. Every PHP request timed out at ten seconds, account wide, across both
trackers on the shared ChemiCloud account. A measurable share of that load was
this repository's own test suite, which runs on every push and every pull
request across four parallel legs, and which fetched the production website
fifty times a run.

Measured under `netblock.py` on the tree before this change:

    test_dedup_live                      24 connections to asktherecruiter.com
    test_secondary_surface_consistency   21
    test_subscriber_routes_live           5

None of those fifty is a mistake in the ordinary sense. Each of those three
modules is deliberately about live data: what the deployed PHP dedup actually
returns, what the deployed pages actually put in an <h1>, whether the
subscriber routes actually answer. They cannot be stubbed without becoming a
different test. The defect is that they ran by DEFAULT, on every push, from
every machine, forever.

(A fourth module, test_headline_containment, was a genuine accident: sixteen
offline unit tests reached the live /corrections endpoint out of an invariant's
FAIL branch. That is fixed upstream of this file, in `Ctx.disclosed`, by not
reading the live log when the run is reading an injected transport.)

SO THEY BECOME OPT IN, AND OPTING OUT IS NOT A PASS. `require()` skips with a
message that begins "UNKNOWN, NOT RUN", which is the register this repository
already uses everywhere a check could not be taken: PASS, FAIL and UNKNOWN are
three states and the absence of a signal is never a pass. The scheduled job
that DOES set ALT_LIVE_TESTS is `live-surface-check.yml`, four times a day, not
four times a push.

DO NOT ANSWER A QUIET LIVE CHECK BY DEFAULTING THIS ON. The reason the site
fell over is that a check which costs a request ran on a trigger that fires
hundreds of times a day. If a live surface needs watching more closely, give
that one surface its own scheduled job with its own cadence; do not hand the
whole suite the network back.
"""
import os

ENV = "ALT_LIVE_TESTS"

# EVERY test module entitled to open a connection to the deployed site, and
# the reason it cannot be answered offline. `test_offline_suite_is_offline.py`
# reads this registry: a module in it must gate on `require()`, and a module
# NOT in it must reach no host at all. Adding a name here is a deliberate act
# that shows up in a diff.
LIVE_MODULES = {
    "test_dedup_live":
        "the superset/exact-count dedup lives in PHP with no PHP unit harness, "
        "so the only thing that can be asserted is what the deployed API "
        "returns",
    "test_secondary_surface_consistency":
        "the browser tab title is built from wp_posts, which no checkout can "
        "read, so the deployed page is the only place the migration is "
        "provable",
    "test_subscriber_routes_live":
        "a subscriber-facing 404 exists only on the deployed site; the source "
        "half of this module is offline and stays in the default suite",
}


# THE INDIRECT DOORS, and why a scan for `urlopen` alone is not enough.
#
# Two of the three modules above contain neither the hostname nor a request:
# `test_dedup_live` calls `data_integrity.check_all()` and
# `test_subscriber_routes_live` calls `subscriber_routes.check()`, and the
# connection is opened three modules deeper. A detector that only reads test
# source for a fetch would have called both of them clean while they were
# making twenty nine connections a run, which is the blind spot that lets the
# next one in.
#
# So a live door is named here as well. The rule matches the one the
# containment fix established upstream: a call with NO injected transport is
# reading production; the same call with `fetch=` is reading a stub, and is
# exactly how the offline tests in those same modules already work.
# Dotted call names, matched against the END of the name actually called. A
# call to one of these WITH NO ARGUMENTS reads production; the same call with
# `fetch=` injected is a replay against a stub, which is how the offline tests
# in these same modules already work, so arity is what separates them.
LIVE_DOORS = (
    "data_integrity.check_all",
    "subscriber_routes.check",
    "reader_freshness.check",
    "reader_freshness.main",
)


def enabled():
    """True when this run is entitled to read the deployed site.

    Anything other than the exact string "1" is off, INCLUDING the empty
    string that a GitHub Actions `env:` block writes when its expression
    evaluates to nothing. A gate that reads truthiness would be armed by
    `ALT_LIVE_TESTS=false`.
    """
    return os.environ.get(ENV, "") == "1"


def require(case, what):
    """Skip `case` loudly unless this run may read the deployed site.

    The message says NOT RUN rather than "skipped" because a reader scanning a
    suite summary for the word "ok" has to be able to see, in the line itself,
    that a live surface went unchecked rather than checked and found well.
    """
    if enabled():
        return
    case.skipTest(
        "UNKNOWN, NOT RUN: %s reads the DEPLOYED site, and this run is not "
        "entitled to. Nothing about the live surface was checked here and "
        "nothing is cleared by this skip. Set %s=1 to run it, or read the "
        "live-surface-check workflow, which does." % (what, ENV))
