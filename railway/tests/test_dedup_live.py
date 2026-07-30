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
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity
from data_integrity import INVARIANTS, FAIL, PASS, UNKNOWN


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

    def test_every_registered_invariant_is_asserted(self):
        # Adding an invariant to the shared registry must not silently skip CI.
        asserted = {"coinbase_news_vs_news", "spirit_news_vs_warn",
                    "tyson_warn_revision", "att_no_fake_outlier"}
        missing = {i.key for i in INVARIANTS} - asserted
        self.assertFalse(missing, (
            f"data_integrity.INVARIANTS gained {sorted(missing)} with no test method here. "
            f"ops_status would report it but CI would not fail on it — add a test_ method."))


class DegradationContract(unittest.TestCase):
    """Offline unit tests for the honest-degradation rules. These need no
    network, so they still run (and still protect the contract) in the CI job
    that has no egress."""

    def test_unreachable_is_unknown_never_pass(self):
        def dead(url, timeout):
            raise OSError("Network is unreachable")
        report = data_integrity.check_all(fetch=dead)
        self.assertEqual(report.verdict, UNKNOWN)
        self.assertEqual(report.passed, [])
        self.assertTrue(all(r.transport for r in report.unknown))

    def test_empty_payload_is_unknown_not_pass(self):
        # The sibling repo's failure mode in miniature: a response that carries
        # no answer must never be scored as a good answer.
        report = data_integrity.check_all(fetch=lambda url, timeout: b"{}")
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


if __name__ == "__main__":
    unittest.main()
