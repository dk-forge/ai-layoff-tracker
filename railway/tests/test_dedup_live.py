"""Live regression guard for the superset/exact-count dedup (db.php
alt_reconcile_supersets, applied daily via reconcile-supersets.yml).

The dedup logic lives in PHP with no PHP unit harness, so this asserts the
DEPLOYED behavior against the live API: known duplicate events must count ONCE.
If the daily reconcile stops running or a change breaks a pass, these revert to
double-counted and this test fails loudly.

Skips cleanly when the site is unreachable (offline / CI without network), so it
never produces a false failure — run it in a networked nightly job or by hand.
Covers the three dedup passes:
  - news-vs-news exact-count across time  (Coinbase 700 on May 5 + Jul 24 -> 700)
  - news-vs-WARN company-total on site rows (Spirit counts once, not news+WARN)
  - within-WARN revision                   (Tyson 1,761 Amarillo x2 -> once)

WHERE THE BOUNDS LIVE (changed 2026-07-30)
------------------------------------------
They are NOT in this file any more. They live once, in `railway/data_integrity.py`,
because `ops_status.py` and `health_digest.py` now report the same invariants and
a bound that drifted between this guard and the dashboard would be the same class
of bug this guard exists to catch. Add a new live invariant to
data_integrity.INVARIANTS and `test_every_registered_invariant_is_asserted` will
fail until it is asserted here too.

Not every registered invariant is asserted in THIS file, and `InvariantCoverage`
at the bottom is what makes that safe. Live bounds are claimed here, by a
`self._assert("key")` call it reads back out of the source. Invariants whose
subject is what the page RENDERS are claimed by name against the test case that
exercises them, and that claim is verified by mutation: the invariant is blinded
to an unconditional PASS and the named test case must go red. A claim that points
at a test which does not really exercise its invariant fails there.
"""
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity
from data_integrity import INVARIANTS, FAIL, PASS, UNKNOWN


def tearDownModule():
    """Publish whether the live invariants were EVALUATED at all.

    A skip below is invisible to everything downstream: the run is green, and
    `ci_alert.py` used to read a green run of this workflow as "the live-data
    incident is over" and mail RECOVERED. On 2026-08-14 it did exactly that on a
    run where every live check had skipped on the site's 503 maintenance window,
    then mailed RED again seven minutes later. Three emails, one number, nothing
    changed.

    So the verdict leaves this process by a channel a separate workflow can read:
    a file, which the `Live-data invariants were evaluated` step in tests.yml
    turns into a step conclusion, which the alerter reads from the jobs API for
    one cheap call. Absent env var (every local run) — writes nothing.
    """
    path = os.environ.get(data_integrity.VERDICT_FILE_ENV)
    report = getattr(DedupLiveRegression, "_report", None)
    if not path:
        return
    if report is None:
        state, detail = (data_integrity.NOT_EVALUATED,
                         "the live invariants were never fetched in this run")
    else:
        state, detail = data_integrity.live_data_state(report)
    Path(path).write_text(f"{state}\n{detail}\n", encoding="utf-8")


def _inv(key):
    for i in INVARIANTS:
        if i.key == key:
            return i
    raise AssertionError(f"unknown invariant {key!r} — see data_integrity.INVARIANTS")


class DedupLiveRegression(unittest.TestCase):
    def setUp(self):
        # One shared fetch of every invariant, so the four tests cost one round
        # trip instead of four.
        cls = type(self)
        if not hasattr(cls, "_report"):
            cls._report = data_integrity.check_all()

    def _assert(self, key):
        """Assert one registered invariant, mapping its three states onto
        unittest's two.

        The mapping is the whole reason this indirection is worth it, and it
        differs DELIBERATELY from ops_status:

          PASS    -> pass
          FAIL    -> fail loudly. A real dedup regression.
          UNKNOWN -> skip IF the site was never reached (offline CI, a transient
                     host blip, the deploy's own 503 maintenance window). But an
                     HTTP 4xx/5xx or a non-JSON body means the site ANSWERED and
                     answered wrongly on the parameterised path — exactly what
                     this guard exists to catch — so that FAILS. A blanket skip
                     would stay green forever (F27, audit 2026-07-28): setUp's
                     plain aggregate can succeed while q=/country_basis= is
                     broken.

        ops_status makes the opposite call on the skip case and reports UNKNOWN
        rather than green, because a dashboard that skips reads as a clean bill
        of health. A test suite that fails on every laptop without wifi gets
        ignored. Same data, two consumers, two correct answers.
        """
        result = next(r for r in self._report.results if r.inv.key == key)
        if result.state == PASS:
            return
        if result.state == FAIL:
            self.fail(f"{result.inv.label}: {result.detail}")
        if result.transport:
            self.skipTest(f"live API unreachable ({result.detail})")
        if "503" in result.detail:
            self.skipTest("site is in its deploy maintenance window (HTTP 503)")
        if getattr(result, "pending", False):
            # The site answered, but this reading is not one this guard is
            # entitled to judge: a build that predates the field, a baseline the
            # daily job has not written, or a baseline younger than one ingest
            # cycle (see MIN_CYCLE_SPAN_DAYS — a push-time check landing inside a
            # running backfill reads a batch, not a day). Reddening every push
            # for the two minutes an FTPS deploy takes, or for whichever
            # collector happens to be writing, would train people to ignore this
            # file. It is still UNKNOWN in ops_status [3], still UNKNOWN on the
            # health ledger, and data-integrity.yml still exits 3 (a red run,
            # which emails), so a guard that never arms cannot hide here.
            self.skipTest(f"UNKNOWN, NOT passing: {result.detail}")
        self.fail(f"{result.inv.label}: {result.detail} — server regression, not a blip")

    def test_coinbase_counts_once(self):
        # Two news reports of the same 700 cut (May 5 + Jul 24) must sum to 700,
        # not 1,400. Allow the primary's 700; fail if it doubles.
        self._assert("coinbase_news_vs_news")

    def test_spirit_counts_once(self):
        # The May-5 news 4,000 must not stack on top of the ~6-7k May-2 WARN sites.
        #
        # 2026-07-30: this bound did its job. Spirit went 7,069 -> 11,069, exactly
        # +4,000, and the cause was real: alt_reconcile_supersets asked "is there a
        # WARN row within 45 days" per row but ran its >=50% plausibility test
        # against the company's ALL-TIME WARN sum. Spirit's news 4,000 covers 6,109
        # jobs of May-2026 WARN sites, but was measured against 8,922 jobs of Spirit
        # WARN notices going back to 2020; the day that all-time sum crossed 8,000
        # the news row stopped being a subset and started stacking. Fixed in
        # 2.19.227 by scoping both the test and the marking to the +/-45-day window.
        # The bound stays at 11,000 - it is the guard, not the number.
        self._assert("spirit_news_vs_warn")

    def test_tyson_amarillo_not_doubled(self):
        # The identical 1,761 Amarillo WARN filed twice must count once.
        self._assert("tyson_warn_revision")

    def test_no_fake_att_outlier(self):
        # The trashed+suppressed FL test notice (AT&T 78,788) must stay gone.
        self._assert("att_no_fake_outlier")

    def test_no_single_row_carries_a_headline(self):
        # The shape guard the four above cannot be: they know four events by
        # name, this one knows none and asks the question anyway — how much of
        # this published number is one line? The RI 98,912 misparse, the AT&T
        # 78,788 test notice and the Coal India by-2050 projection each read
        # 25-34% of the trailing-90-day headline.
        self._assert("headline_concentration")

    def test_no_headline_moves_without_rows_to_explain_it(self):
        # A published total that moves when the row population did not is
        # something re-scoring already-published rows: a mass re-mark, a bad
        # purge-reload, an unannounced correction.
        self._assert("headline_movement")

    def test_dedup_cannot_use_an_all_time_denominator(self):
        # Structural, and offline: asserts db.php still makes the 2026-07-30
        # Spirit comparison unwritable (no local sum in the reconciler; the
        # denominator can only come from alt_dedup_window(); the verdict throws
        # on anything not window-scoped).
        self._assert("dedup_denominator_scoped")

    def test_gold_set_recall_has_not_fallen(self):
        # The other half of the question every check above asks. They all test
        # whether a published number is WRONG; none of them can see an event
        # that never arrived. This one reads the committed measurement of the
        # frozen SEC Item 2.05 gold set and fails when the tracker has lost
        # events an editor confirmed it held.
        self._assert("recall_floor")

    def test_archive_recheck_promise_is_kept(self):
        # Every listing surface prints "No archive snapshot yet. We re-check
        # weekly; next check by <date>." beside an un-archived source. This
        # fails when the live /archive-coverage shows the oldest un-archived
        # URL's last attempt is older than the promised cadence plus slack —
        # a typed promise the crons keep, or a red build.
        self._assert("archive_recheck_cadence")

    def test_every_registered_invariant_is_asserted(self):
        # Adding an invariant to the shared registry must not silently skip CI.
        # Delegated to InvariantCoverage below, which does not take the answer
        # on trust — see the note there.
        InvariantCoverage.assert_every_key_is_claimed(self)


LIVE_ONLY = tuple(i for i in INVARIANTS if getattr(i, "reads_live_data", True))


def _without_open_incidents(invariants):
    """The same registry, with the movement guard pointed at an EMPTY ledger.

    An open incident in `railway/headline_incidents.json` makes its slice report
    FAIL *on purpose*, and deliberately without consulting the network — time,
    later rows and an unreachable API must not close an incident. The
    degradation tests below are claims about TRANSPORT: "a dead network can
    never produce a pass". Leaving a real standing incident in the registry
    would let a true statement about that incident answer a question nobody
    asked here, and the tests would go red the moment one is open.
    """
    empty = Path(__file__).with_name("no-such-incident-ledger.json")
    assert not empty.exists(), f"{empty} must not exist — it stands in for an empty ledger"
    return tuple(data_integrity.MovementInvariant(incidents_path=empty)
                 if isinstance(i, data_integrity.MovementInvariant) else i
                 for i in invariants)


class DegradationContract(unittest.TestCase):
    """Offline unit tests for the honest-degradation rules. These need no
    network, so they still run (and still protect the contract) in the CI job
    that has no egress.

    They are scoped to the invariants that READ THE LIVE SITE (`LIVE_ONLY`).
    "A dead network can never produce a pass" is a claim about those. The
    structural guard over db.php in this checkout is correct to pass with no
    network at all — including it here would turn a true statement about the
    network into a false one about the whole registry."""

    def test_unreachable_is_unknown_never_pass(self):
        def dead(url, timeout):
            raise OSError("Network is unreachable")
        report = data_integrity.check_all(fetch=dead,
                                          invariants=_without_open_incidents(LIVE_ONLY))
        self.assertEqual(report.verdict, UNKNOWN)
        self.assertEqual(report.passed, [])
        self.assertTrue(all(r.transport for r in report.unknown))

    def test_a_structural_guard_is_not_excused_by_a_dead_network(self):
        # The other half of the same rule: a network outage must not turn the
        # db.php guard into a skip. It reads a file; it answers either way.
        def dead(url, timeout):
            raise OSError("Network is unreachable")
        report = data_integrity.check_all(fetch=dead, invariants=INVARIANTS)
        structural = [r for r in report.results if r.inv.key == "dedup_denominator_scoped"]
        self.assertEqual(len(structural), 1)
        self.assertIn(structural[0].state, (PASS, FAIL))

    def test_empty_payload_is_unknown_not_pass(self):
        # The sibling repo's failure mode in miniature: a response that carries
        # no answer must never be scored as a good answer.
        report = data_integrity.check_all(fetch=lambda url, timeout: b"{}",
                                          invariants=_without_open_incidents(INVARIANTS))
        self.assertEqual(report.verdict, UNKNOWN)

    def test_a_confirmed_failure_outranks_an_unverifiable_one(self):
        import json as _json

        def mixed(url, timeout):
            if "Spirit" in url:
                return _json.dumps({"totals": {"jobs": 11069}}).encode()
            raise OSError("down")
        self.assertEqual(data_integrity.check_all(fetch=mixed).verdict, FAIL)

    def test_zero_jobs_is_a_failure_not_a_pass(self):
        # "Under the bound" must not be satisfiable by the rows vanishing.
        import json as _json
        report = data_integrity.check_all(
            fetch=lambda url, timeout: _json.dumps({"totals": {"jobs": 0}}).encode())
        self.assertEqual(report.verdict, FAIL)

    def test_ledger_status_never_reports_ok_for_an_unverified_run(self):
        def dead(url, timeout):
            raise OSError("down")
        status, _, _ = data_integrity.ledger_status(data_integrity.check_all(fetch=dead))
        self.assertNotEqual(status, "ok")


# ---------------------------------------------------------------------------
# THE COVERAGE GUARD
# ---------------------------------------------------------------------------
class InvariantCoverage(unittest.TestCase):
    """Every registered invariant is asserted somewhere, and the assertion works.

    WHAT WENT WRONG, AND WHY THE OLD GUARD COULD NOT HAVE CAUGHT IT
    ---------------------------------------------------------------
    This guard used to compare INVARIANTS against a hand-written set of key
    strings. That set was the whole mechanism, and it has exactly the failure
    mode it exists to prevent: it does not know anything, it is told. On
    2026-08-04 six published-figure invariants were registered, the string set
    was not updated, and the guard fired correctly. But the guard could equally
    have been silenced by typing six strings into the set, which would have
    restored precisely the blindness it was written to stop — a registry the
    dashboard reports on and CI cannot fail on.

    So the set is gone and there are two mechanisms, both of which check rather
    than trust:

      CLAIMED   every key in INVARIANTS is claimed by an entry below. This is the
                drift guard the old set was, and it still fails on a new
                invariant with nowhere to live.

      ARMED     every claim is VERIFIED, by mutation. For each delegated
                invariant, its run() is replaced with one that reports an
                unconditional PASS and the named test case is executed. If that
                test case does not go RED, it was not testing the invariant, and
                this fails. Six tests that assert True would satisfy any
                bookkeeping check ever written; they cannot survive this one.

    Live-data invariants are claimed HERE, by a `self._assert("key")` call in
    DedupLiveRegression, and the claim is verified by reading that class's own
    source rather than by taking a list's word for it. They are not
    mutation-tested because the check they drive needs the live site, and a unit
    suite that reaches the network on every push is a unit suite people delete.
    Their live reading is data-integrity.yml, daily, exit 2 on FAIL and 3 on
    UNKNOWN.
    """

    # key -> (test module, TestCase class) that proves the invariant arms.
    # Verified by mutation in test_every_delegated_claim_is_real.
    DELEGATED = {
        "figures_agree_with_api": ("test_published_figure_guards", "AgreementTest"),
        "figure_parts_reconcile": ("test_published_figure_guards", "ReconciliationTest"),
        "figure_drilldown_matches": ("test_published_figure_guards", "DrillDownTest"),
        "figure_basis_is_stated": ("test_published_figure_guards", "BasisTest"),
        "figures_agree_across_surfaces": ("test_published_figure_guards", "CrossSurfaceTest"),
        "comparison_basis_is_visible": ("test_published_figure_guards", "ComparisonBasisTest"),
        "headline_containment": ("test_headline_containment", "TheIncidentItWasWrittenFor"),
        "erm_provenance": ("test_erm_provenance_check", "WiredIntoTheOneRegistry"),
        "rolling_recall_fresh": ("test_rolling_recall", "WiredIntoTheOneRegistry"),
        "country_coverage_fresh": ("test_country_coverage", "WiredIntoTheOneRegistry"),
    }

    @staticmethod
    def _claimed_by_a_live_assertion():
        """Keys this file asserts against the live site, read out of the source.

        Introspection, not a list. A test method that stops calling _assert stops
        counting as coverage the moment it does, with no second place to update.
        """
        import inspect
        src = inspect.getsource(DedupLiveRegression)
        return set(re.findall(r'self\._assert\(\s*["\']([a-z0-9_]+)["\']\s*\)', src))

    @classmethod
    def assert_every_key_is_claimed(cls, case):
        claimed = cls._claimed_by_a_live_assertion() | set(cls.DELEGATED)
        missing = {i.key for i in INVARIANTS} - claimed
        case.assertFalse(missing, (
            f"data_integrity.INVARIANTS gained {sorted(missing)} with no test asserting it. "
            f"ops_status would report it but CI would not fail on it — either add a "
            f"self._assert(\"<key>\") to DedupLiveRegression for a live bound, or add the "
            f"key to InvariantCoverage.DELEGATED naming the test case that proves it arms."))

    def test_every_registered_invariant_is_claimed(self):
        self.assert_every_key_is_claimed(self)

    def test_no_claim_is_stale(self):
        # A claim for a key that no longer exists is a claim nobody will notice
        # is doing nothing.
        keys = {i.key for i in INVARIANTS}
        stale = sorted(set(self.DELEGATED) - keys)
        self.assertFalse(stale, f"DELEGATED claims keys not in INVARIANTS: {stale}")
        orphan = sorted(self._claimed_by_a_live_assertion() - keys)
        self.assertFalse(orphan, f"DedupLiveRegression asserts keys not in INVARIANTS: {orphan}")

    def test_every_delegated_claim_is_real(self):
        """Mutation: blind each invariant in turn, demand its test case redden.

        This is the assertion that makes the whole guard mean something. Nothing
        here reads what a test is named or how long it is; it breaks the thing
        the test claims to cover and insists the test notices.
        """
        import importlib
        pkg = __name__.rsplit(".", 1)[0] + "." if "." in __name__ else ""
        for key, (modname, clsname) in sorted(self.DELEGATED.items()):
            inv = _inv(key)
            try:
                mod = importlib.import_module(pkg + modname)
            except ImportError:
                mod = importlib.import_module(modname)
            case = getattr(mod, clsname, None)
            self.assertIsNotNone(
                case, f"{key} is delegated to {modname}.{clsname}, which does not exist")

            owner, real = type(inv), type(inv).run
            owner.run = lambda self, ctx: data_integrity.Result(
                self, PASS, detail="stubbed green by the coverage guard")
            try:
                suite = unittest.TestLoader().loadTestsFromTestCase(case)
                with open(os.devnull, "w") as quiet:
                    outcome = unittest.TextTestRunner(verbosity=0, stream=quiet).run(suite)
            finally:
                owner.run = real

            self.assertTrue(
                outcome.failures or outcome.errors,
                f"{key} is claimed by {modname}.{clsname}, but blinding that invariant "
                f"to an unconditional PASS left all {outcome.testsRun} of its tests "
                f"green. That test case does not actually exercise the invariant, so "
                f"CI would stay green while the check reported nothing.")


if __name__ == "__main__":
    unittest.main()
