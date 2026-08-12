"""The two ceilings have to BIND, not merely be declared.

Written 2026-08-11, from an ops_status ACTION NEEDED line that named the defect
exactly: `ai-evidence-sweep spent $0.020 in one run, past its $0.015 named
ceiling`. A named limit that a run sails past is the same family as a coverage
guard satisfiable by typing strings — it reports a limit while enforcing
nothing.

Three properties, each of which was FALSE before this file existed:

  1. A job's NAMED per-run ceiling binds inside the job's own process, from the
     table, with no workflow step required to export it. Before: the ceiling was
     `RUN_CEILING_USD`, read from ALT_RUN_CEILING_USD once at import, and that
     variable was only ever set by `spend.py --degrade` writing $GITHUB_ENV. Any
     run without that step — a manual dispatch, a local run, a workflow whose
     guard step failed to write the file — silently got the $0.20 global
     default, i.e. 13x ai-evidence-sweep's named $0.015.

  2. A run that STOPPED EARLY does not record as a clean one. PASS / FAIL /
     UNKNOWN are three states in this repo and a truncated run is not a pass.

  3. A paid job REFUSES TO START when the month's measured spend is at the
     allowance. Before: the monthly cap was a printed warning in a separate
     step, enforced only through an env var that step may or may not have
     written, and never consulted by the job itself.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

import spend  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class _SpendCase(unittest.TestCase):
    """Isolate the module's process-global state and the committed snapshot."""

    def setUp(self):
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        self._env = {k: os.environ.get(k) for k in
                     ("ALT_JOB", "ALT_RUN_CEILING_USD", "ALT_PAID_READS",
                      "OPENROUTER_API_KEY", "GITHUB_WORKFLOW_REF",
                      "ALT_RUN_SPEND_FILE", "GITHUB_RUN_ID")}
        for k in self._env:
            os.environ.pop(k, None)
        self.addCleanup(self._restore_env)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._snap = spend.SNAPSHOT_PATH
        spend.SNAPSHOT_PATH = os.path.join(self.tmp.name, "spend_month.json")
        self.addCleanup(lambda: setattr(spend, "SNAPSHOT_PATH", self._snap))
        # $1 per token, so a test can spend an exact amount without a network
        # price lookup.
        spend._prices_fetched = True
        spend._price_cache["test/dollar-a-token"] = (1.0, 1.0)
        self.addCleanup(lambda: spend._price_cache.pop("test/dollar-a-token", None))

    def _restore_env(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _spend_usd(self, usd):
        spend.record_usage("test/dollar-a-token",
                           SimpleNamespace(prompt_tokens=0, completion_tokens=0,
                                           cost=usd))


class TheNamedPerJobCeilingBinds(_SpendCase):

    def test_the_named_ceiling_binds_with_no_workflow_step_to_export_it(self):
        """THE DEFECT. ai-evidence-sweep's ceiling is $0.015 in the table. A run
        that has spent $0.016 must not be allowed a further paid call, whether
        or not a `--degrade` step happened to write ALT_RUN_CEILING_USD."""
        os.environ["ALT_JOB"] = "ai-evidence-sweep"
        self.assertTrue(spend.paid_reads_enabled())
        self._spend_usd(0.016)
        self.assertFalse(
            spend.paid_reads_enabled(),
            "ai-evidence-sweep has spent $0.0160 against its named $0.015 "
            "ceiling and paid reads are still ON — the named ceiling is a "
            "label, not a brake")

    def test_the_effective_ceiling_is_the_named_one_not_the_global_default(self):
        os.environ["ALT_JOB"] = "ai-evidence-sweep"
        self.assertAlmostEqual(spend.effective_run_ceiling_usd(), 0.015, places=6)

    def test_an_explicit_operator_override_still_wins(self):
        os.environ["ALT_JOB"] = "ai-evidence-sweep"
        os.environ["ALT_RUN_CEILING_USD"] = "0.05"
        self.assertAlmostEqual(spend.effective_run_ceiling_usd(), 0.05, places=6)

    def test_an_unnamed_job_keeps_the_global_default(self):
        """railway-cron is deliberately absent from the table: free ingest must
        not be re-throttled by this change."""
        os.environ["ALT_JOB"] = "railway-cron"
        self.assertAlmostEqual(spend.effective_run_ceiling_usd(),
                               spend.RUN_CEILING_USD, places=6)


class ATruncatedRunIsNotACleanRun(_SpendCase):

    def test_the_ledger_entry_records_that_the_run_stopped_early(self):
        os.environ["ALT_JOB"] = "ai-evidence-sweep"
        self._spend_usd(0.016)
        spend.paid_reads_enabled()          # trips the ceiling
        entry = spend.record_job_run(items=3, changed=1)
        self.assertFalse(entry.get("complete", True),
                         "a run stopped by its spend ceiling was recorded as a "
                         "complete run — the ledger cannot tell a finished job "
                         "from a truncated one")
        self.assertIn("ceiling", str(entry.get("truncated") or "").lower())

    def test_a_run_that_finished_records_as_complete(self):
        os.environ["ALT_JOB"] = "ai-evidence-sweep"
        self._spend_usd(0.001)
        entry = spend.record_job_run(items=3, changed=1)
        self.assertTrue(entry.get("complete"))
        self.assertIsNone(entry.get("truncated"))

    def test_a_caller_can_declare_its_own_truncation(self):
        """The wall-clock deadline truncates runs too, and that is equally not
        a clean run."""
        spend.note_truncated("wall-clock deadline reached with 6 event(s) unread")
        entry = spend.record_job_run(items=1)
        self.assertFalse(entry.get("complete", True))
        self.assertIn("deadline", entry["truncated"])


class TheMonthlyCapRefusesToStartPaidWork(_SpendCase):
    """One place knows month-to-date against the allowance, and every paid call
    site in the repo already routes through it (`paid_reads_enabled`)."""

    def _arm(self, usage_at_start):
        month = spend.datetime.datetime.now(
            spend.datetime.timezone.utc).strftime("%Y-%m")
        with open(spend.SNAPSHOT_PATH, "w") as fh:
            json.dump({spend.key_fingerprint("test-key"):
                       {"month": month, "usage_at_start": usage_at_start}}, fh)
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        spend.reset_month_gate()
        self.addCleanup(spend.reset_month_gate)

    def test_a_paid_job_refuses_to_start_when_the_month_is_spent(self):
        self._arm(100.0)
        self.addCleanup(setattr, spend, "fetch_key_state", spend.fetch_key_state)
        spend.fetch_key_state = lambda key: {"usage": 109.5}   # $9.50 this month
        blocked, why = spend.month_gate()
        self.assertTrue(blocked, f"month gate did not block: {why}")
        self.assertFalse(
            spend.paid_reads_enabled(),
            "month-to-date is $9.50 of a $10.00 hard cap and paid reads are "
            "still ON — the monthly cap is a report, not a stop")

    def test_a_month_inside_the_allowance_does_not_block(self):
        self._arm(100.0)
        self.addCleanup(setattr, spend, "fetch_key_state", spend.fetch_key_state)
        spend.fetch_key_state = lambda key: {"usage": 101.0}
        self.assertTrue(spend.paid_reads_enabled())

    def test_an_unmeasurable_month_is_UNKNOWN_and_says_so(self):
        """No armed snapshot = month-to-date is not known here. UNKNOWN must
        not read as a pass, and must not halt the free collectors either: it is
        reported, and the per-run ceiling is what enforces."""
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        spend.reset_month_gate()
        self.addCleanup(spend.reset_month_gate)
        blocked, why = spend.month_gate()
        self.assertFalse(blocked)
        self.assertIn("UNKNOWN", why)

    def test_the_gate_never_rebaselines_the_month_to_zero(self):
        """month_delta() WRITES a fresh baseline when it finds none, and returns
        0.0 as a measured figure. On an ephemeral runner that write is thrown
        away, so a lost snapshot would make every job read '$0.00 spent this
        month' forever. The gate reads only; it never arms."""
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        spend.reset_month_gate()
        self.addCleanup(spend.reset_month_gate)
        spend.month_gate()
        self.assertFalse(os.path.exists(spend.SNAPSHOT_PATH),
                         "the month gate armed a snapshot as a side effect, so "
                         "an absent snapshot silently becomes a measured zero")

    def test_the_allowance_cannot_be_raised_from_the_environment(self):
        """The cap is the owner's, and it is a policy in a diff."""
        src = (ROOT / "railway/spend.py").read_text()
        self.assertNotIn("ALT_MONTHLY_ALLOWANCE", src)
        self.assertEqual(spend.MONTHLY_ALLOWANCE_USD, 10.0)


class TheSweepCannotMistakeABudgetStopForAVerdict(unittest.TestCase):
    """ai_evidence_sweep decides 'keep-untagged' when the model finds no
    employer AI quote. A paid call that was never made must not land in that
    branch: that would publish 'we looked and found nothing' about a row nobody
    looked at."""

    def setUp(self):
        os.environ["ALT_PAID_READS"] = "off"
        self.addCleanup(lambda: os.environ.pop("ALT_PAID_READS", None))

    def test_a_gated_quote_read_returns_not_asked_not_no_quote(self):
        sys.modules.setdefault("openai", SimpleNamespace(OpenAI=None))
        import ai_evidence_sweep as sweep
        self.assertIsNone(
            sweep._ai_quote("Acme", "Acme said AI let it cut 300 roles."),
            "_ai_quote returned '' (a verdict of 'no employer AI quote') for a "
            "call it never made — a budget stop must be distinguishable from a "
            "finding")

    def test_a_gated_confirmation_returns_not_asked(self):
        import ai_evidence_sweep as sweep
        self.assertIsNone(sweep._second_pass_agrees("Acme", "some quote"))


if __name__ == "__main__":
    unittest.main()
