"""A deferral must CLOSE the running note it opened.

Jobs that start with `require_running_note` write `running` to the health ledger
before they touch anything. When the host then does not answer, `host_call.defer`
records the deferral and exits 0 — correctly, a host that never answered is not a
job that failed. But it used to exit without ever answering its own note.

The health ledger keeps only the LATEST note per source, and a `running` row
carries a FRESH `checked_at`. So a deferred collector sat there looking healthy
AND refreshing its own staleness clock until the next day's run overwrote it.
Nothing could see it: section [2] read `running` as OK, and `source_freshness`
asks whether a source is publishing, not whether its run finished.

That is not hypothetical. enrich-roles deferred on 2026-08-17 (HTTP 503 from the
host) and the stranded note surfaced four days later as an unexplained orphan in
`run_completion`, alongside a crashed run (2026-08-13) and a cancelled one
(2026-08-11).

The row is `degraded`, because the work did not happen — and deliberately NOT an
ops_status [2] action item, because [4d] already counts deferrals and goes red on
the third in a row. One transient 503 must not raise the same alarm twice.
"""
import os
import sys
import unittest

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import host_call  # noqa: E402
import ops_status  # noqa: E402


class _Recorder:
    """Stands in for source_health, which imports requests.

    Injected rather than mocked so this file is stdlib-only and runs anywhere,
    including a checkout with no dependencies installed. defer() imports
    source_health INSIDE the function precisely because source_health imports
    host_call, so replacing the module in sys.modules is the honest seam.
    """

    def __init__(self, boom=None):
        self.calls = []
        self.boom = boom

    def report_source_health(self, source, status, entries=0, detail=""):
        if self.boom:
            raise self.boom
        self.calls.append((source, status, entries, detail))
        return True


import contextlib  # noqa: E402
import types  # noqa: E402


@contextlib.contextmanager
def _stub_health(boom=None):
    rec = _Recorder(boom)
    mod = types.ModuleType("source_health")
    mod.report_source_health = rec.report_source_health
    saved = sys.modules.get("source_health")
    sys.modules["source_health"] = mod
    try:
        yield rec
    finally:
        if saved is None:
            sys.modules.pop("source_health", None)
        else:
            sys.modules["source_health"] = saved


class DeferralClosesTheNote(unittest.TestCase):

    def setUp(self):
        self.tmp = os.path.join(RAILWAY, "tests", "_throwaway_deferrals.json")
        self.addCleanup(lambda: os.path.exists(self.tmp) and os.remove(self.tmp))

    def _defer(self, **kw):
        with _stub_health() as rec:
            code = host_call.defer("enrich-roles", "HTTP 503 from the host",
                                   ledger=self.tmp, envelope="", **kw)
        return code, rec

    def test_a_deferral_with_a_source_writes_a_terminal_note(self):
        code, rec = self._defer(source="role_enrichment")
        self.assertEqual(code, 0, "a deferral is still exit 0")
        self.assertEqual(len(rec.calls), 1,
                         "the running note this job opened was never answered")
        args = rec.calls[0]
        self.assertEqual(args[0], "role_enrichment")
        self.assertEqual(args[1], "degraded",
                         "the work did not happen, so this is not `ok` — and it "
                         "must not stay `running`, which reads as healthy")

    def test_the_note_says_why_and_carries_the_reason(self):
        _code, rec = self._defer(source="role_enrichment")
        detail = rec.calls[0][3]
        self.assertTrue(detail.startswith(host_call.DEFERRED_DETAIL[:40]), detail)
        self.assertIn("HTTP 503", detail, "a session must see what the host said")
        self.assertLessEqual(len(detail), 240, "the endpoint truncates at 240")

    def test_no_source_means_no_note_rather_than_a_wrong_one(self):
        """Callers that never opened a running note must not invent a row."""
        _code, rec = self._defer()
        self.assertEqual(rec.calls, [])

    def test_a_failed_health_write_never_turns_a_deferral_into_a_red_run(self):
        with _stub_health(boom=RuntimeError("host down")):
            code = host_call.defer("enrich-roles", "HTTP 503", ledger=self.tmp,
                                   envelope="", source="role_enrichment")
        self.assertEqual(code, 0,
                         "a bookkeeping failure must not fail a deferral; that is "
                         "how an outage manufactures red runs")


class DeferralDoesNotAlarmTwice(unittest.TestCase):
    """[4d] already escalates deferrals. [2] must not duplicate it."""

    def test_ops_status_treats_a_deferral_row_as_non_actionable(self):
        detail = f"{host_call.DEFERRED_DETAIL} (HTTP 503 from the host)"
        self.assertTrue(ops_status._is_deferral(detail))

    def test_an_ordinary_degraded_row_is_still_actionable(self):
        for detail in ("feed broke: economynext_lk: HTTP 202",
                       "google_news returned 0 items",
                       "OpenRouter credits exhausted (HTTP 402)"):
            with self.subTest(detail=detail):
                self.assertFalse(ops_status._is_deferral(detail))

    def test_the_marker_has_one_definition(self):
        """ops_status must read host_call's constant, not a copied string."""
        with open(os.path.join(RAILWAY, "ops_status.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("host_call.DEFERRED_DETAIL", src,
                      "_is_deferral must import the marker from host_call; a "
                      "copied string drifts the moment the wording changes")


class EveryRunningNoteOpenerClosesOnDefer(unittest.TestCase):
    """A job that opens a running note must pass `source` when it defers."""

    def test_callers_pass_a_source(self):
        offenders = []
        for name in os.listdir(RAILWAY):
            if not name.endswith(".py"):
                continue
            path = os.path.join(RAILWAY, name)
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            if "require_running_note" not in body:
                continue
            if "def require_running_note" in body:
                continue
            for n, line in enumerate(body.splitlines(), 1):
                if "host_call.defer(" in line and "source=" not in line:
                    offenders.append(f"{name}:{n}")
        self.assertEqual(offenders, [],
                         "these jobs open a running note and defer without "
                         "closing it, stranding the collector at `running`: "
                         + ", ".join(offenders))


if __name__ == "__main__":
    unittest.main()
