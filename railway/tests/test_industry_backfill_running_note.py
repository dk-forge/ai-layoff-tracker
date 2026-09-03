"""industry_backfill.main() must DEFER on a host that never answered its
`running` precondition write, never raise.

Before this fix, `main()` called the bool-returning `report_source_health`
directly and raised `RuntimeError` on ANY non-OK outcome, collapsing two very
different situations into one hard failure: a host that REFUSED the write
(wrong/missing key, settled, fails identically tomorrow) and a host that never
ANSWERED it (a transient 502/504, which every sibling job — reason_backfill,
archive_backfill — already treats as a deferral via
`source_health.require_running_note`). On 2026-09-03 the shared host 504'd on
`/source-health`, and the job raised on every one of its three CI retries with
nothing ever attempted, exactly the "collector started is not the collector
finished" shape CLAUDE.md warns about: an orphaned `running` note carries a
FRESH `checked_at` and reads as healthy while the job never ran.

This test proves the fix by mutation via the two branches that matter:
- a host that never answered -> exit 0 (deferred), run() never called
- a host that refused the write -> still raises, unchanged
"""
import os
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()
from types import SimpleNamespace  # noqa: E402
sys.modules.setdefault("openai", SimpleNamespace())

import http_retry  # noqa: E402
import host_call  # noqa: E402
import source_health  # noqa: E402
import industry_backfill  # noqa: E402


class _StubHealth:
    """Stands in for source_health.publish_source_health inside industry_backfill's
    own module namespace (it imported require_running_note, which in turn calls
    the live source_health.publish_source_health — patched at that source)."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def __call__(self, source, status, entries=0, detail=""):
        self.calls.append((source, status, entries, detail))
        return self.outcome


class RunningNoteDefersRatherThanRaises(unittest.TestCase):

    def setUp(self):
        os.environ["WP_SITE_URL"] = "https://example.test"
        os.environ["WP_API_KEY"] = "k"
        industry_backfill.SITE = "https://example.test"
        industry_backfill.KEY = "k"
        industry_backfill.DRY_RUN = False
        self._orig_publish = source_health.publish_source_health
        self._orig_run = industry_backfill.run
        self._orig_defer = host_call.defer
        self.tmp_ledger = os.path.join(
            os.path.dirname(__file__), "_throwaway_industry_deferrals.json")
        # require_running_note calls host_call.defer with the DEFAULT ledger
        # (the committed railway/deferral_ledger.json); pin it to a throwaway
        # file so this test cannot dirty a file the real jobs read.
        host_call.defer = lambda job, reason, **kw: self._orig_defer(
            job, reason, ledger=self.tmp_ledger, envelope="", **kw)
        # run() must never be reached in either branch below: a deferral means
        # nothing was attempted, and a raise happens before it too.
        industry_backfill.run = lambda: self.fail(
            "run() must not be called when the running note never landed")

    def tearDown(self):
        source_health.publish_source_health = self._orig_publish
        industry_backfill.run = self._orig_run
        host_call.defer = self._orig_defer
        if os.path.exists(self.tmp_ledger):
            os.remove(self.tmp_ledger)

    def test_a_host_that_never_answered_defers_not_raises(self):
        stub = _StubHealth(http_retry.DEFERRED)
        source_health.publish_source_health = stub
        try:
            rc = industry_backfill.main()
        except RuntimeError:
            self.fail("a transient (deferred) running-note write must not raise")
        self.assertEqual(rc, 0, "a deferral is exit 0, not a failure")
        self.assertEqual(stub.calls[0][:2], ("industry_backfill", "running"))

    def test_a_host_that_refused_the_write_still_raises(self):
        stub = _StubHealth(http_retry.FAILURE)
        source_health.publish_source_health = stub
        with self.assertRaises(RuntimeError):
            industry_backfill.main()


if __name__ == "__main__":
    unittest.main()
