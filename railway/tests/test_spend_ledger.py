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
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

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
        """Clear `var` for this test and RESTORE IT EITHER WAY afterwards.

        It used to restore only when the variable had been set beforehand, so a
        test whose subject SETS one (apply_job_ceiling writes
        ALT_RUN_CEILING_USD) leaked that value into every test that ran after
        it. That was invisible while the per-run ceiling was a module constant
        frozen at import; once the ceiling became live (2026-08-11) the leak
        surfaced as an unrelated retry test failing only in a full run.
        """
        old = os.environ.pop(var, None)
        if old is not None:
            self.addCleanup(os.environ.__setitem__, var, old)
        else:
            self.addCleanup(os.environ.pop, var, None)


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
        """Ingest is MEASURED. The COMMITTED ceilings' worst case must leave
        that much headroom inside the allowance — if this fails, someone
        widened a ceiling (or named a new recurring job) without redoing the
        ladder.

        SCOPE NARROWED TO THE COMMITTED PATH (2026-08-13). It used to sum
        EVERY named ceiling, which made the ladder unsatisfiable the moment the
        allowance came down to a steady-state number: the backfills alone claim
        $7.35/month worst case. That sum is no longer a bound on anything,
        because a discretionary job's ceiling is now RATIONED at run time
        against the allowance actually left in the month
        (spend.discretionary_run_ceiling_usd) rather than taken from the table.
        What must still fit, and what this asserts, is the recurring path: the
        collectors are paid first, so their worst case has to be affordable
        before any catch-up work is even considered.
        `test_discretionary_claims_are_bounded_by_headroom_not_by_the_table`
        below covers the other half.

        THE RESERVE USED TO BE A LITERAL `- 3.0` (fixed 2026-08-12) while this
        docstring and the failure message both said the reserve was the ~$5.1
        MEASURED ingest. So the test permitted $7.00 of named ceilings on a $10
        allowance, i.e. $12.10 of claims inside $10, and reported that as green.
        The reserve is now `spend.MEASURED_INGEST_USD_PER_MONTH`, the same
        constant the module's ladder comment is written against, so the number
        the test enforces and the number the comment claims cannot drift apart
        again — and raising the allowance can no longer silently widen the
        ladder by more than it widened the budget.
        """
        total = 0.0
        for job, ceiling in spend.JOB_RUN_CEILINGS_USD.items():
            if spend.is_discretionary(job):
                continue
            total += ceiling * self.RUNS_PER_MONTH.get(job, 30)
        budget = spend.MONTHLY_ALLOWANCE_USD - spend.MEASURED_INGEST_USD_PER_MONTH
        self.assertLessEqual(
            total, budget,
            f"COMMITTED ceilings sum to ${total:.2f}/month worst case; with "
            f"ingest MEASURED at ~${spend.MEASURED_INGEST_USD_PER_MONTH:.2f} "
            f"that leaves ${budget:.2f} inside the "
            f"${spend.MONTHLY_ALLOWANCE_USD:.2f} allowance, so the recurring "
            f"path does not fit and a backfill is not the reason")

    def test_every_named_job_is_classified(self):
        """A job in neither set is treated as COMMITTED, which is the safe
        default but also a silent one. Every job with a ceiling must be an
        explicit choice, so a new paid job cannot join the recurring path by
        forgetting."""
        for job in spend.JOB_RUN_CEILINGS_USD:
            with self.subTest(job=job):
                self.assertTrue(
                    job in spend.COMMITTED_JOBS or job in spend.DISCRETIONARY_JOBS,
                    f"{job} has a named ceiling but is in neither "
                    f"COMMITTED_JOBS nor DISCRETIONARY_JOBS, so it silently "
                    f"defaults to being paid first")

    def test_the_two_classes_do_not_overlap(self):
        self.assertEqual(spend.COMMITTED_JOBS & spend.DISCRETIONARY_JOBS,
                         frozenset())

    def test_discretionary_claims_are_bounded_by_headroom_not_by_the_table(self):
        """The backfills' named ceilings x cadence exceed the whole allowance,
        and that is FINE — precisely because the table is no longer what binds
        them. This asserts both halves of that sentence, so nobody 'fixes' the
        over-subscription by cutting a ceiling that no longer decides anything.
        """
        claim = 0.0
        for job in spend.DISCRETIONARY_JOBS:
            runs = spend.DISCRETIONARY_RUNS_PER_MONTH.get(job, 30)
            claim += spend.JOB_RUN_CEILINGS_USD.get(
                job, spend.RUN_CEILING_USD) * runs
        # 2026-08-14: the allowance moved 7.00 -> 14.00 to pay for
        # local-language discovery, and this assertion's original subject went
        # with it -- the table claims $7.35/month, which now FITS. That is the
        # deliberate case its own failure message named, so the assertion is
        # inverted rather than deleted: the table must stay affordable, and if
        # a future session re-oversubscribes it the rationer becomes load
        # bearing again and somebody should have to say so in a diff.
        #
        # sources/local_news.py is the one to watch: armed at its cap it adds
        # $5.14/month, taking the claim to ~$12.49 against $14.00. Still fits,
        # with less room than this reads.
        self.assertLessEqual(
            claim, spend.MONTHLY_ALLOWANCE_USD,
            f"the discretionary table claims ${claim:.2f}/month against a "
            f"${spend.MONTHLY_ALLOWANCE_USD:.2f} allowance, so the named "
            "ceilings over-subscribe it again and only the rationer is "
            "stopping an overrun")
        # ...and on a month where the committed path has already claimed the
        # allowance, the rationer hands out nothing at all.
        ledger = {"v": 1, "entries": [
            {"job": "railway-cron", "date": "2026-09-01",
             "cost_usd": spend.MONTHLY_ALLOWANCE_USD}]}
        ceiling, why = spend.discretionary_run_ceiling_usd(
            "edgar-history-sweep", today=datetime.date(2026, 9, 20),
            ledger=ledger)
        self.assertEqual(ceiling, 0.0)
        self.assertIn("NO HEADROOM", why)

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
        """Through spend.metered_call, which meters what it lets through. A
        script holding its own client used to hand-roll create() +
        record_usage(), and the two halves drifted: process_tips' second pass
        was never metered at all."""
        for rel in self.SELF_CLIENT:
            with self.subTest(script=rel):
                self.assertIn("spend.metered_call(", (ROOT / rel).read_text(),
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


class ABackfillCannotStarveTheCollectors(_LedgerSandbox):
    """THE LOAD-BEARING TEST for the 2026-08-12/13 incident.

    Six dispatched edgar-history-sweep runs spent $0.884 in 26 hours. Under a
    $7.00 month that is 44 days of catch-up budget gone in one, and under the
    old flat per-run ceiling nothing anywhere could tell that apart from the
    Railway cron collecting today's layoffs. So: build a month where a backfill
    empties the allowance on DAY 2, then assert on DAY 20 that the recurring
    collectors are untouched and the backfill is the only thing that stopped.
    """

    def _lean_month(self):
        """Sept 2026: the committed path ticking over at its measured rate, and
        one catastrophic backfill on the 2nd."""
        entries = [{"job": "railway-cron", "date": f"2026-09-{d:02d}",
                    "cost_usd": 0.164} for d in range(1, 21)]
        entries.append({"job": "edgar-history-sweep", "date": "2026-09-02",
                        "cost_usd": spend.MONTHLY_ALLOWANCE_USD})
        return {"v": 1, "entries": entries}

    def test_the_recurring_collectors_still_have_their_full_budget_on_day_20(self):
        os.environ["ALT_JOB"] = "dedupe-llm"
        self.assertFalse(spend.is_discretionary("dedupe-llm"))
        self.assertEqual(spend.effective_run_ceiling_usd("dedupe-llm"),
                         spend.JOB_RUN_CEILINGS_USD["dedupe-llm"],
                         "a backfill emptied the month on day 2 and the daily "
                         "dedup was rationed for it — the collectors are "
                         "supposed to be paid first")
        os.environ["ALT_JOB"] = "railway-cron"
        self.assertEqual(spend.effective_run_ceiling_usd("railway-cron"),
                         spend.RUN_CEILING_USD)

    def test_the_backfill_is_the_thing_that_stopped(self):
        ceiling, why = spend.discretionary_run_ceiling_usd(
            "edgar-history-sweep", today=datetime.date(2026, 9, 20),
            ledger=self._lean_month())
        self.assertEqual(ceiling, 0.0)
        self.assertIn("NO HEADROOM", why)

    def test_a_zero_headroom_run_says_it_was_skipped_and_does_not_go_red(self):
        """Rule 4: a skipped discretionary job REPORTS and exits 0. A red run
        manufactures an alert, and this repo has already paid for that loop."""
        os.environ["ALT_JOB"] = "edgar-history-sweep"
        os.environ["ALT_RUN_CEILING_USD"] = "0"
        buf = io.StringIO()
        with redirect_stdout(buf):
            allowed = spend.paid_reads_enabled()
        self.assertFalse(allowed)
        out = buf.getvalue()
        self.assertIn("SKIPPED", out)
        self.assertIn("exits 0", out)
        self.assertIn("skipped", (spend.run_truncation() or "").lower())

    def test_a_truncated_run_says_what_it_dropped(self):
        """Rule: no silent caps. The ledger line a throttled run leaves must
        name the cause and must not read as complete."""
        os.environ["ALT_JOB"] = "edgar-history-sweep"
        os.environ["ALT_RUN_CEILING_USD"] = "0.010"
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 100000, "completion_tokens": 5000})
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertFalse(spend.paid_reads_enabled())
            entry = spend.record_job_run(items=800, stored=3)
        self.assertFalse(entry["complete"])
        self.assertIsNotNone(entry["truncated"])
        self.assertIn("ceiling", entry["truncated"])
        self.assertIn("TRUNCATED", buf.getvalue())

    def test_a_lean_month_slows_a_backfill_rather_than_stopping_it(self):
        """Day 2 vs day 25 of the SAME lean month: smaller, never zero, while
        any headroom is left. A backfill that stops loses coverage; a backfill
        that shrinks only delays it, and every one of them is resumable."""
        def month_to(day, sweep_per_day):
            # Scaled with the allowance when it moved 7.00 -> 14.00 on
            # 2026-08-14. "Lean" is a RATIO, not a dollar figure: the fixture
            # has to keep consuming most of the month for the throttle to be
            # the thing under test. Left at the old absolute numbers it simply
            # stopped being a lean month and the test passed by not applying.
            rows = []
            for d in range(1, day + 1):
                rows.append({"job": "railway-cron", "date": f"2026-09-{d:02d}",
                             "cost_usd": 0.328})
                rows.append({"job": "edgar-history-sweep",
                             "date": f"2026-09-{d:02d}",
                             "cost_usd": sweep_per_day})
            return {"v": 1, "entries": rows}

        named = spend.JOB_RUN_CEILINGS_USD["edgar-history-sweep"]
        for day in (2, 25):
            ceiling, why = spend.discretionary_run_ceiling_usd(
                "edgar-history-sweep", today=datetime.date(2026, 9, day),
                ledger=month_to(day, 0.14))
            with self.subTest(day=day):
                self.assertGreater(ceiling, 0.0,
                                   f"day {day}: the sweep was stopped, not slowed")
                self.assertLess(ceiling, named, f"day {day}: not throttled")
                self.assertIn("THROTTLED", why)

        # ...and the throttle is a function of what is LEFT, not of the date:
        # same day, more already spent on catch-up, tighter ceiling.
        thrifty, _ = spend.discretionary_run_ceiling_usd(
            "edgar-history-sweep", today=datetime.date(2026, 9, 25),
            ledger=month_to(25, 0.04))
        spendy, _ = spend.discretionary_run_ceiling_usd(
            "edgar-history-sweep", today=datetime.date(2026, 9, 25),
            ledger=month_to(25, 0.18))
        self.assertGreater(
            thrifty, spendy,
            "two months differing only in how much catch-up work was already "
            "bought got the same ceiling, so the rationer is not reading the "
            "allowance actually remaining")

    def test_an_override_cannot_outspend_the_month_but_is_never_silent(self):
        """The Aug 12/13 shape exactly: a dispatch input raising the ceiling.
        It still works, it is still honoured up to what is left, and the run
        log says what was clamped. Committed jobs are not clamped at all."""
        ledger = self._lean_month()
        self.assertEqual(
            spend.discretionary_headroom_usd(
                today=datetime.date(2026, 9, 20), ledger=ledger)[0], 0.0)
        src = (ROOT / "railway/spend.py").read_text()
        self.assertIn("is CLAMPED to", src)
        os.environ["ALT_JOB"] = "company-watchlist"   # committed
        os.environ["ALT_RUN_CEILING_USD"] = "0.90"
        self.assertEqual(spend.effective_run_ceiling_usd(), 0.90)


class TheOwnerCanSeeWhereTheMonthIsGoing(_LedgerSandbox):
    """Rule 5: one line, readable by someone who is not a developer."""

    def test_the_budget_line_names_spent_allowance_days_and_projection(self):
        ledger = {"v": 1, "entries": [
            {"job": "railway-cron", "date": f"2026-09-{d:02d}",
             "cost_usd": 0.10} for d in range(1, 11)]}
        line = spend.budget_line(today=datetime.date(2026, 9, 10),
                                 ledger=ledger)
        self.assertIn("$1.00 of $14.00 spent", line)
        self.assertIn("10/30 days", line)
        self.assertIn("$3.00 for 2026-09", line)   # 0.10/day x 30
        self.assertIn("on track", line)

    def test_the_budget_line_says_OVER_when_it_is(self):
        ledger = {"v": 1, "entries": [
            {"job": "railway-cron", "date": "2026-09-01", "cost_usd": 3.0}]}
        line = spend.budget_line(today=datetime.date(2026, 9, 1), ledger=ledger)
        self.assertIn("OVER", line)

    def test_ops_status_prints_it(self):
        self.assertIn("_spend.budget_line()",
                      (ROOT / "railway/ops_status.py").read_text())


if __name__ == "__main__":
    unittest.main()
