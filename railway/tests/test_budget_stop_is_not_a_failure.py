"""A budget stop is NOT ASKED. A model outage is FAILED. They are two states.

THE DEFECT, from a real red run on 2026-08-13. `industry-backfill` printed 200
lines of `FAILED (retried on a later rotation)`, raised "All 200 attempted
industry classifications failed", was retried three times by its workflow
wrapper and raised `::error::still failing after 3 attempts`. Its own log, six
lines earlier, said what had actually happened:

    spend: 'industry-backfill' is SKIPPED this run. NO HEADROOM ...
    the job exits 0 - a skipped backfill is not a broken one.

The guard had worked perfectly. `classify_industry` returns None both for a
model or transport error AND when paid reads are off for budget, and
`classify_confirmed` mapped None to "failed" while its own docstring promised
"'failed' -> a model/transport error". One None, two events, one status.

This repo had already learned the lesson one module over:
`tests/test_spend_ceilings_bind.py` pins `ai_evidence_sweep._ai_quote` returning
None rather than '' so a call nobody made cannot be read as a verdict of "we
looked and the employer did not name AI". It was never carried across.

BOTH HALVES ARE LOAD-BEARING and each test below is paired:
  * a budget stop reports DEFERRED, says how many rows went unread, and exits 0
    so the workflow wrapper never retries and never pages the owner;
  * a genuine model outage still counts as a FAILURE and still exits non-zero,
    because buying the quiet by silencing real failures is the failure mode
    CLAUDE.md records for the alert channel.
"""
import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())

import extractor  # noqa: E402
import host_call  # noqa: E402
import spend  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class _BudgetCase(unittest.TestCase):
    """Isolate the process-global spend meter, the deferral counter and env."""

    def setUp(self):
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        extractor._spend_deferrals = 0
        self.addCleanup(lambda: setattr(extractor, "_spend_deferrals", 0))
        self._env = {k: os.environ.get(k) for k in
                     ("ALT_JOB", "ALT_RUN_CEILING_USD", "ALT_PAID_READS",
                      "OPENROUTER_API_KEY", "GITHUB_WORKFLOW_REF",
                      "ALT_RUN_SPEND_FILE", "GITHUB_RUN_ID", "WP_SITE_URL",
                      "WP_API_KEY")}
        for k in self._env:
            os.environ.pop(k, None)
        self.addCleanup(self._restore_env)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._snap = spend.SNAPSHOT_PATH
        spend.SNAPSHOT_PATH = os.path.join(self.tmp.name, "spend_month.json")
        self.addCleanup(lambda: setattr(spend, "SNAPSHOT_PATH", self._snap))

    def _restore_env(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def paid_reads_off(self):
        """The state the 06:05 run was in: the guard has said no."""
        os.environ["ALT_PAID_READS"] = "off"
        self.assertFalse(spend.paid_reads_enabled())


# --------------------------------------------------------------------------
# The primitive: every paid call in extractor.py returns None for both events,
# so a caller needs a way to ask which one it was.
# --------------------------------------------------------------------------
class TheNotAskedSignalExists(_BudgetCase):

    def test_a_budget_stop_is_distinguishable_from_a_model_error(self):
        self.paid_reads_off()
        before = extractor.spend_deferral_count()
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(extractor.classify_industry("Acme Ltd", "cut 300 roles"))
        self.assertTrue(
            extractor.spend_deferred_since(before),
            "classify_industry returned None because paid reads are off, and "
            "spend_deferred_since() cannot tell — every caller that counts a "
            "None is then forced to guess, which is the whole defect")

    def test_a_model_error_is_not_reported_as_a_budget_stop(self):
        before = extractor.spend_deferral_count()
        self.assertFalse(extractor.spend_deferred_since(before))


# --------------------------------------------------------------------------
# industry_backfill: the module the red run came from.
# --------------------------------------------------------------------------
class _IndustryCase(_BudgetCase):

    def setUp(self):
        super().setUp()
        os.environ["ALT_JOB"] = "industry-backfill"
        import industry_backfill as ib
        self.ib = ib
        self.rows = [{"id": 1000 + n, "company_name": f"Zzqx Holdings {n}",
                      "excerpt": "The company said it would cut 40 roles."}
                     for n in range(20)]
        self._orig = {name: getattr(ib, name) for name in
                      ("fetch_candidates", "post_fills", "report_source_health",
                       "require_running_note", "classify_deterministic",
                       "classify_industry", "SITE", "KEY")}
        self.addCleanup(self._restore_module)
        # main() refuses to start without these; they are read at import.
        ib.SITE, ib.KEY = "https://example.invalid/blog", "k"
        ib.fetch_candidates = lambda: list(self.rows)
        # The deterministic pre-pass is free and must not mask the model path.
        ib.classify_deterministic = lambda name: None
        self.health = []
        ib.report_source_health = lambda *a, **k: self.health.append((a, k)) or True
        # main()'s precondition write, stubbed for the same reason
        # report_source_health is: these tests are about the budget guard, not
        # the health ledger or a live host. None means "the note landed".
        ib.require_running_note = lambda *a, **k: None
        real_clear = host_call.clear
        host_call.clear = lambda *a, **k: None
        self.addCleanup(lambda: setattr(host_call, "clear", real_clear))
        self.posted = []
        ib.post_fills = lambda items: (self.posted.extend(items)
                                       or ([i["id"] for i in items], [], []))

    def _restore_module(self):
        for name, value in self._orig.items():
            setattr(self.ib, name, value)

    def _run(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = self.ib.run()
        return result, buffer.getvalue()


class ABudgetStopIsDeferredNotFailed(_IndustryCase):

    def test_the_run_reports_deferred_and_never_failed(self):
        self.paid_reads_off()
        result, log = self._run()
        self.assertEqual(
            result["failures"], 0,
            "the spend guard turned paid reads off and the run still counted "
            "model failures - this is the 2026-08-13 red run, reproduced")
        self.assertEqual(result["deferred"], len(self.rows))
        self.assertNotIn("FAILED", log)

    def test_the_run_says_how_many_rows_it_did_not_read(self):
        """No silent caps: the count, and what becomes of those rows."""
        self.paid_reads_off()
        _, log = self._run()
        self.assertIn(f"deferring the remaining {len(self.rows)} row(s)", log)
        self.assertRegex(log, r"SKIPPED \d+ row\(s\) for\s+budget")
        self.assertIn("UNMARKED", log)

    def test_the_run_does_not_raise_so_the_wrapper_cannot_redden(self):
        """The workflow wrapper retries three times and raises ::error:: on any
        non-zero exit. It is exactly as honest as the script under it."""
        self.paid_reads_off()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.ib.main()
        self.assertEqual(code, 0, "a disclosed skip exited non-zero, so the "
                                  "wrapper retried it three times and paged "
                                  "the owner over a working budget guard")

    def test_the_health_ledger_names_the_unread_rows(self):
        self.paid_reads_off()
        self._run()
        details = " ".join(str(a) for a, _ in self.health)
        self.assertIn(f"{len(self.rows)} rows unread on the spend guard", details)

    def test_the_ledger_records_the_run_as_truncated_not_complete(self):
        self.paid_reads_off()
        self._run()
        self.assertIsNotNone(
            spend.run_truncation(),
            "a run that left rows unread recorded as a complete pass over the "
            "queue - PASS / FAIL / UNKNOWN are three states here")


class ARealModelOutageStillReddens(_IndustryCase):

    def test_a_model_error_still_counts_as_a_failure(self):
        self.ib.classify_industry = lambda company, excerpt: None
        with self.assertRaises(RuntimeError) as caught:
            self._run()
        self.assertIn("attempted industry classifications failed", str(caught.exception))

    def test_a_model_outage_still_exits_non_zero(self):
        self.ib.classify_industry = lambda company, excerpt: None
        buffer = io.StringIO()
        with self.assertRaises(RuntimeError), redirect_stdout(buffer):
            self.ib.main()

    def test_a_mid_row_ceiling_trip_defers_the_rest_rather_than_failing_it(self):
        """The ceiling can trip between two rows of the same run. Everything
        after it was not read, so none of it is a failure either."""
        seen = {"n": 0}

        def flaky(company, excerpt):
            seen["n"] += 1
            if seen["n"] > 4:
                os.environ["ALT_PAID_READS"] = "off"
                return extractor._defer_for_spend("industry classification")
            return {"industry": "Technology"}

        self.ib.classify_industry = flaky
        result, log = self._run()
        self.assertEqual(result["failures"], 0)
        self.assertGreater(result["deferred"], 0)
        self.assertIn("mid-row", log)


class TheTwoPassGateNamesTheFourthStatus(_BudgetCase):

    def test_classify_confirmed_returns_deferred_when_paid_reads_are_off(self):
        os.environ["ALT_JOB"] = "industry-backfill"
        self.paid_reads_off()
        import industry_backfill as ib
        with redirect_stdout(io.StringIO()):
            label, status = ib.classify_confirmed("Acme Ltd", "cut 300 roles")
        self.assertEqual((label, status), ("", "deferred"))

    def test_classify_confirmed_still_returns_failed_for_a_model_error(self):
        import industry_backfill as ib
        original = ib.classify_industry
        ib.classify_industry = lambda company, excerpt: None
        self.addCleanup(lambda: setattr(ib, "classify_industry", original))
        self.assertEqual(ib.classify_confirmed("Acme Ltd", "text"), ("", "failed"))

    def test_the_docstring_lists_all_four_statuses(self):
        import industry_backfill as ib
        doc = ib.classify_confirmed.__doc__ or ""
        for status in ("confirmed", "unconfirmed", "deferred", "failed"):
            self.assertIn(f"'{status}'", doc)


# --------------------------------------------------------------------------
# enrich_roles: the same collapse, reported as
# "no discretionary headroom left in the month" and exiting 1.
# --------------------------------------------------------------------------
class EnrichRolesTreatsABudgetStopAsASkip(_BudgetCase):

    def _load(self):
        os.environ["ALT_JOB"] = "enrich-roles"
        os.environ["WP_SITE_URL"] = "https://example.invalid/blog"
        os.environ["WP_API_KEY"] = "k"
        os.environ["OPENROUTER_API_KEY"] = "k"
        import importlib
        module = importlib.reload(__import__("enrich_roles"))
        rows = [{"id": 2000 + n, "excerpt": "It will cut 40 engineering roles.",
                 "company_name": f"Zzqx {n}"} for n in range(10)]
        module.host_call = SimpleNamespace(
            get_json=lambda *a, **k: {"data": rows, "total": len(rows)},
            post_json=lambda *a, **k: {"updated": [], "marked_unknown": [], "rejected": []},
            clear=lambda *a, **k: None,
            defer=lambda *a, **k: 0,
            Deferred=type("Deferred", (Exception,), {}),
        )
        module.report_health = lambda *a, **k: self.health.append((a, k))
        self.health = []
        return module, rows

    def test_a_budget_stop_exits_zero(self):
        self.paid_reads_off()
        module, rows = self._load()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = module.main()
        self.assertEqual(code, 0,
                         "enrich-roles reported 'no discretionary headroom left "
                         "in the month' as a failure and exited 1")
        self.assertIn(f"deferring the remaining {len(rows)} row(s)", buffer.getvalue())

    def test_a_real_model_outage_still_exits_non_zero(self):
        module, rows = self._load()
        module.extract_role_categories = lambda passage: None
        module.time = SimpleNamespace(monotonic=module.time.monotonic, sleep=lambda *_: None)
        with redirect_stdout(io.StringIO()):
            code = module.main()
        self.assertEqual(code, 1,
                         "every attempted row failed at the model and the job "
                         "exited 0 - a real outage must still go red")


# --------------------------------------------------------------------------
# The sweep, held open. A None from a paid call is a fork, not a value.
# --------------------------------------------------------------------------
class EveryConsumerOfAPaidCallAsksWhichNoneItGot(unittest.TestCase):
    """Structural net under the four modules the behavioural tests cover plus
    the one that never went red but published the same conflation.

    `enrich_context` counted unread rows into `unsupported_or_unreadable` on
    the PUBLIC health ledger, which is a claim that we fetched a source and
    could not use it. Nobody fetched it. A job that never exits non-zero can
    still report a budget stop as a failure."""

    MODULES = ("industry_backfill", "reason_backfill", "enrich_roles",
               "reclassify_legacy_ai", "enrich_context")

    def test_each_module_asks_before_counting_a_none(self):
        for name in self.MODULES:
            source = (ROOT / f"{name}.py").read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertIn(
                    "spend_deferred_since", source,
                    f"{name}.py counts a None back from a paid call without "
                    f"asking whether the call was ever made. A budget stop is "
                    f"NOT ASKED; only a call that happened can have failed.")
                self.assertIn(
                    "spend.paid_reads_enabled()", source,
                    f"{name}.py has no pre-check, so a run with paid reads off "
                    f"walks its whole queue making calls it knows will defer.")

    def test_each_module_reports_the_deferred_count(self):
        for name in self.MODULES:
            source = (ROOT / f"{name}.py").read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertTrue(
                    re.search(r"note_truncated\(", source),
                    f"{name}.py can leave rows unread without recording the "
                    f"run as truncated. CLAUDE.md: no silent caps.")

    def test_the_retry_wrappers_still_redden_on_a_real_failure(self):
        """Do not buy the quiet by making genuine failures silent."""
        workflows = Path(__file__).resolve().parents[2] / ".github" / "workflows"
        for name in ("industry-backfill.yml", "reclassify-legacy-ai.yml"):
            text = (workflows / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("::error::still failing after 3 attempts", text)
                self.assertIn("exit 1", text)


if __name__ == "__main__":
    unittest.main()
