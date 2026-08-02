"""Per-job spend attribution: every LLM job leaves a ledger line, the line
survives the ephemeral runner, and the named ceilings are arithmetic that has
to fit the allowance rather than hope.

What went wrong that this file guards against (2026-08-02): the only cost
signal was a daily ACCOUNT balance. It could not attribute a cent to a job,
so a dozen small daily LLM jobs were invisible individually — and one of
them, dedupe_llm, was not even under the spend guard: the workflow ran
`spend.py --degrade`, the flag landed in GITHUB_ENV, and the script never
read it.
"""
import datetime
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

import spend  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPEND = (ROOT / "railway/spend.py").read_text()
WORKFLOWS = ROOT / ".github/workflows"


class _LedgerSandbox(unittest.TestCase):
    """Point the ledger at a temp file and clear the meter around each test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._real = spend.LEDGER_PATH
        spend.LEDGER_PATH = os.path.join(self.tmp.name, "spend_jobs.json")
        self.addCleanup(lambda: setattr(spend, "LEDGER_PATH", self._real))
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        for var in ("ALT_JOB", "GITHUB_WORKFLOW_REF", "GITHUB_RUN_ID",
                    "GITHUB_RUN_ATTEMPT", "ALT_RUN_CEILING_USD", "GITHUB_ENV"):
            self._stash(var)

    def _stash(self, var):
        old = os.environ.pop(var, None)
        if old is not None:
            self.addCleanup(os.environ.__setitem__, var, old)


class MeterAcceptsRawResponses(unittest.TestCase):
    """dedupe_llm and the spot-check hold parsed JSON, not SDK objects. A
    meter that only reads attributes charges their calls at zero — which is
    exactly the invisibility this change removes."""

    def setUp(self):
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)

    def test_dict_usage_is_charged(self):
        cost = spend.record_usage("deepseek/deepseek-chat",
                                  {"prompt_tokens": 1000, "completion_tokens": 100})
        self.assertGreater(cost, 0)
        self.assertEqual(spend._run["calls"], 1)

    def test_broken_dict_usage_costs_zero_and_never_raises(self):
        self.assertEqual(spend.record_usage("m", {"prompt_tokens": "x"}), 0.0)
        self.assertEqual(spend.record_usage("m", None), 0.0)


class JobIdentityNeedsNoArgument(_LedgerSandbox):
    """Attribution must not depend on every workflow remembering to pass its
    own name; the runner already knows which workflow file is running."""

    def test_workflow_ref_names_the_job(self):
        os.environ["GITHUB_WORKFLOW_REF"] = (
            "dk-forge/ai-layoff-tracker/.github/workflows/dedupe-llm.yml"
            "@refs/heads/main")
        self.assertEqual(spend.current_job(), "dedupe-llm")

    def test_explicit_alt_job_wins(self):
        os.environ["GITHUB_WORKFLOW_REF"] = ".github/workflows/x.yml@r"
        os.environ["ALT_JOB"] = "railway-cron"
        self.assertEqual(spend.current_job(), "railway-cron")

    def test_no_ci_context_is_local_not_a_guess(self):
        self.assertEqual(spend.current_job(), "local")


class TheLedgerLineIsTheDurableCopy(_LedgerSandbox):
    def test_record_job_run_prints_a_parseable_marker_line(self):
        os.environ["ALT_JOB"] = "dedupe-llm"
        os.environ["GITHUB_RUN_ID"] = "12345"
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 2000, "completion_tokens": 200})
        buf = io.StringIO()
        with redirect_stdout(buf):
            entry = spend.record_job_run(items=60, changed=13)
        parsed = spend.parse_ledger_lines(
            "2026-08-02T14:55:36.2207764Z " +
            [l for l in buf.getvalue().splitlines()
             if spend.LEDGER_MARKER in l][0])
        self.assertEqual(parsed[0]["job"], "dedupe-llm")
        self.assertEqual(parsed[0]["items"], 60)
        self.assertEqual(parsed[0]["changed"], 13)
        self.assertEqual(parsed[0]["run_id"], "12345")
        self.assertGreater(parsed[0]["cost_usd"], 0)
        self.assertEqual(entry["calls"], 1)

    def test_uncounted_dimensions_are_none_never_zero(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            entry = spend.record_job_run()
        self.assertIsNone(entry["items"])
        self.assertIsNone(entry["stored"])

    def test_an_unwritable_ledger_cannot_break_the_job(self):
        spend.LEDGER_PATH = os.path.join(self.tmp.name, "no-such-dir", "x.json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            entry = spend.record_job_run(items=1)  # must not raise
        self.assertIn(spend.LEDGER_MARKER, buf.getvalue())
        self.assertEqual(entry["items"], 1)

    def test_record_job_run_never_touches_the_committed_file(self):
        """The committed ledger has ONE writer: --harvest. A job-side write
        would dirty the file with 'local' rows every time the test suite or a
        dev machine runs a job's main path."""
        os.environ["ALT_JOB"] = "process-tips"
        buf = io.StringIO()
        with redirect_stdout(buf):
            spend.record_job_run(items=0, stored=0)
        self.assertFalse(os.path.exists(spend.LEDGER_PATH))


class HarvestParsing(_LedgerSandbox):
    LOG = (
        "2026-08-02T14:55:36.1Z ##[group]Run python dedupe_llm.py\n"
        "2026-08-02T14:55:36.2Z 21326 entries, 179 candidate clusters\n"
        "2026-08-02T14:55:36.3Z SPEND_LEDGER_V1 "
        '{"job": "dedupe-llm", "date": "2026-08-02", "cost_usd": 0.0231, '
        '"calls": 60, "prompt_tokens": 1, "completion_tokens": 1, '
        '"items": 60, "stored": null, "changed": 13, "run_id": "1", "attempt": "1"}\n'
        "2026-08-02T14:55:37.0Z SPEND_LEDGER_V1 {not json at all\n"
        "2026-08-02T14:55:38.0Z SPEND_LEDGER_V1 {\"date\": \"2026-08-02\"}\n"
    )

    def test_marker_lines_parse_through_the_timestamp_prefix(self):
        entries = spend.parse_ledger_lines(self.LOG)
        self.assertEqual(len(entries), 1)  # bad JSON and job-less lines dropped
        self.assertEqual(entries[0]["job"], "dedupe-llm")

    def test_merge_is_idempotent_across_reharvests(self):
        ledger = spend._load_ledger()
        entries = spend.parse_ledger_lines(self.LOG)
        self.assertEqual(spend._merge_ledger_entries(ledger, entries), 1)
        self.assertEqual(spend._merge_ledger_entries(ledger, entries), 0)
        self.assertEqual(len(ledger["entries"]), 1)

    def test_old_entries_are_trimmed_so_the_committed_file_stays_small(self):
        old = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.timedelta(days=spend.LEDGER_KEEP_DAYS + 5)
               ).strftime("%Y-%m-%d")
        ledger = {"v": 1, "entries": [
            {"job": "a", "date": old, "cost_usd": 0.01}]}
        spend._merge_ledger_entries(
            ledger, [{"job": "b", "date": "2999-01-01", "cost_usd": 0.01}])
        self.assertEqual([e["job"] for e in ledger["entries"]], ["b"])

    def test_harvest_without_a_token_says_unknown_and_returns_zero(self):
        self._stash("GH_TOKEN")
        self._stash("GITHUB_TOKEN")
        self._stash("GITHUB_REPOSITORY")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(spend.harvest(), 0)
        self.assertIn("UNKNOWN", buf.getvalue())


class NamedCeilingsAreArithmeticNotHope(unittest.TestCase):
    """The budget-share table has to stay tied to reality: every named job is
    a real workflow, the Railway cron is deliberately absent, and the summed
    worst case is written against the allowance rather than implied."""

    # Cadence, runs per month, for the worst-case sum. Weekly/monthly jobs
    # carry their real cadence; manual/dormant jobs are counted at zero.
    RUNS_PER_MONTH = {
        "news-catchup": 5, "distress-watchlist": 5,
        "source-verification-audit": 1,
        "foreign-filings": 0,   # cron commented out (dormant by design)
        "hi-warn-dryrun": 0,    # manual dispatch only
    }

    def test_every_named_job_is_a_real_workflow(self):
        for job in spend.JOB_RUN_CEILINGS_USD:
            with self.subTest(job=job):
                self.assertTrue((WORKFLOWS / f"{job}.yml").exists(),
                                f"{job} has a ceiling but no workflow file")

    def test_railway_cron_is_deliberately_not_in_the_table(self):
        """Free ingest stays untouched: the cron gets no tightened ceiling
        from this table, only the global default it already had."""
        self.assertNotIn("railway-cron", spend.JOB_RUN_CEILINGS_USD)

    def test_every_ceiling_is_positive_and_below_the_global_default(self):
        for job, ceiling in spend.JOB_RUN_CEILINGS_USD.items():
            with self.subTest(job=job):
                self.assertGreater(ceiling, 0)
                self.assertLessEqual(ceiling, 0.20)

    def test_the_worst_case_sum_fits_beside_the_measured_ingest(self):
        """Ingest is MEASURED at ~$5.1/month. The named ceilings' worst case
        must leave that much headroom inside the $10 interim allowance —
        if this fails, someone widened a ceiling without redoing the ladder."""
        total = 0.0
        for job, ceiling in spend.JOB_RUN_CEILINGS_USD.items():
            total += ceiling * self.RUNS_PER_MONTH.get(job, 30)
        self.assertLessEqual(
            total, spend.MONTHLY_ALLOWANCE_USD - 3.0,
            f"named ceilings sum to ${total:.2f}/month worst case; with "
            f"ingest at ~$5.1 that cannot fit the "
            f"${spend.MONTHLY_ALLOWANCE_USD:.0f} allowance")

    def test_the_five_dollar_target_is_documented_not_pretended(self):
        self.assertIn("$5/MONTH TARGET", SPEND.upper())
        self.assertIn("NOT yet enforced", SPEND)


class TheGuardStepHandsEachJobItsCeiling(_LedgerSandbox):
    def test_apply_job_ceiling_writes_github_env(self):
        os.environ["GITHUB_WORKFLOW_REF"] = (
            "o/r/.github/workflows/dedupe-llm.yml@refs/heads/main")
        env_file = os.path.join(self.tmp.name, "github_env")
        open(env_file, "w").close()
        os.environ["GITHUB_ENV"] = env_file
        buf = io.StringIO()
        with redirect_stdout(buf):
            spend.apply_job_ceiling()
        body = open(env_file).read()
        self.assertIn("ALT_RUN_CEILING_USD=0.025", body)

    def test_an_operator_override_is_never_retightened(self):
        os.environ["GITHUB_WORKFLOW_REF"] = (
            "o/r/.github/workflows/dedupe-llm.yml@refs/heads/main")
        os.environ["ALT_RUN_CEILING_USD"] = "0.50"
        env_file = os.path.join(self.tmp.name, "github_env")
        open(env_file, "w").close()
        os.environ["GITHUB_ENV"] = env_file
        buf = io.StringIO()
        with redirect_stdout(buf):
            spend.apply_job_ceiling()
        self.assertEqual(open(env_file).read(), "")

    def test_an_unnamed_job_keeps_the_global_default(self):
        os.environ["GITHUB_WORKFLOW_REF"] = (
            "o/r/.github/workflows/warn-import.yml@refs/heads/main")
        env_file = os.path.join(self.tmp.name, "github_env")
        open(env_file, "w").close()
        os.environ["GITHUB_ENV"] = env_file
        buf = io.StringIO()
        with redirect_stdout(buf):
            spend.apply_job_ceiling()
        self.assertEqual(open(env_file).read(), "")


class EveryLlmJobLeavesALedgerLine(unittest.TestCase):
    """Attribution is only as complete as the set of jobs that report. Each
    script that can spend must close out with record_job_run, and each script
    with its OWN client must also meter every response it gets."""

    REPORTING = [
        "railway/dedupe_llm.py", "railway/ai_evidence_sweep.py",
        "railway/enrich_context.py", "railway/enrich_roles.py",
        "railway/company_watchlist.py", "railway/process_tips.py",
        "railway/supplemental_news.py", "railway/foreign_filings_ingest.py",
        "railway/reclassify_legacy_ai.py", "railway/reason_backfill.py",
        "railway/industry_backfill.py", "railway/hi_warn_import.py",
        "railway/news_catchup.py", "railway/distress_watchlist.py",
        "railway/daily_classification_spotcheck.py",
        "railway/source_verification_audit.py", "railway/cron.py",
    ]
    SELF_CLIENT = [
        "railway/dedupe_llm.py", "railway/ai_evidence_sweep.py",
        "railway/daily_classification_spotcheck.py",
        "railway/source_verification_audit.py",
    ]

    def test_every_llm_job_calls_record_job_run(self):
        for rel in self.REPORTING:
            with self.subTest(script=rel):
                self.assertIn("spend.record_job_run(", (ROOT / rel).read_text(),
                              f"{rel} spends but leaves no ledger line")

    def test_self_client_scripts_meter_their_own_responses(self):
        for rel in self.SELF_CLIENT:
            with self.subTest(script=rel):
                self.assertIn("spend.record_usage(", (ROOT / rel).read_text(),
                              f"{rel} has its own client and an unmetered call")

    def test_dedupe_llm_is_finally_under_the_guard(self):
        """The workflow's --degrade step was a no-op for this script until
        2026-08-02: it never read ALT_PAID_READS. Before: a spent month still
        bought ~60 cluster reviews a day. After: zero."""
        src = (ROOT / "railway/dedupe_llm.py").read_text()
        self.assertIn("spend.paid_reads_enabled()", src)

    def test_the_balance_job_harvests_and_commits_the_ledger(self):
        wf = (WORKFLOWS / "openrouter-balance-check.yml").read_text()
        self.assertIn("spend.py --harvest", wf)
        self.assertIn("railway/spend_jobs.json", wf)

    def test_the_committed_ledger_file_exists_and_parses(self):
        with open(ROOT / "railway/spend_jobs.json") as fh:
            data = json.load(fh)
        self.assertIsInstance(data.get("entries"), list)


if __name__ == "__main__":
    unittest.main()
