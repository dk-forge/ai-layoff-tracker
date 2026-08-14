"""Spend guard: the ceiling degrades, it never halts, and free ingest survives.

The bug this file exists to prevent is the one that shipped in the sibling
tracker: a monthly allowance enforced against OpenRouter's LIFETIME usage
figure, which trips permanently once lifetime spend passes one month's budget
and kills autonomous collection silently. The second bug is halting a whole
collect job to protect a budget that most of the job does not spend.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Unit tests exercise pure guardrails and never build an API client.
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

import spend  # noqa: E402
import extractor  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CRON = (ROOT / "railway/cron.py").read_text()
EXTRACTOR = (ROOT / "railway/extractor.py").read_text()
SPEND = (ROOT / "railway/spend.py").read_text()


class MonthToDateIsADelta(unittest.TestCase):
    """month_delta must never enforce against a lifetime figure."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._real = spend.SNAPSHOT_PATH
        spend.SNAPSHOT_PATH = os.path.join(self.tmp.name, "spend_month.json")
        self.addCleanup(lambda: setattr(spend, "SNAPSHOT_PATH", self._real))

    def test_first_run_of_a_month_snapshots_and_reports_zero(self):
        spent, month, persisted = spend.month_delta(842.17, "abc123")
        self.assertEqual(spent, 0.0, "a huge LIFETIME figure must not read as "
                                     "this month's spend")
        self.assertTrue(persisted)
        self.assertRegex(month, r"^\d{4}-\d{2}$")

    def test_later_runs_report_only_the_delta(self):
        spend.month_delta(842.17, "abc123")
        spent, _, _ = spend.month_delta(845.17, "abc123")
        self.assertAlmostEqual(spent, 3.0, places=6)

    def test_lifetime_spend_far_past_the_allowance_does_not_trip_the_guard(self):
        """The exact regression: lifetime >> allowance must still be in budget."""
        lifetime = spend.MONTHLY_ALLOWANCE_USD * 500
        spend.month_delta(lifetime, "abc123")
        spent, _, _ = spend.month_delta(lifetime + 0.02, "abc123")
        self.assertLess(spent, spend.MONTHLY_ALLOWANCE_USD * spend.STOP_AT_FRACTION)

    def test_two_keys_each_carry_their_own_month_start(self):
        """Actions and Railway bill one account with two keys. One shared
        snapshot would make each key's spend look like the other's."""
        spend.month_delta(100.0, "actions_fp")
        spend.month_delta(5.0, "railway_fp")
        a, _, _ = spend.month_delta(101.0, "actions_fp")
        r, _, _ = spend.month_delta(5.5, "railway_fp")
        self.assertAlmostEqual(a, 1.0, places=6)
        self.assertAlmostEqual(r, 0.5, places=6)

    def test_snapshot_holds_no_secret(self):
        spend.month_delta(1.0, spend.key_fingerprint("sk-or-v1-SUPERSECRET"))
        blob = Path(spend.SNAPSHOT_PATH).read_text()
        self.assertNotIn("SUPERSECRET", blob)
        self.assertNotIn("sk-or", blob)

    def test_corrupt_snapshot_undercounts_rather_than_halting(self):
        Path(spend.SNAPSHOT_PATH).write_text("{not json")
        spent, _, persisted = spend.month_delta(50.0, "abc123")
        self.assertEqual(spent, 0.0)
        self.assertTrue(persisted)

    def test_unwritable_snapshot_reports_not_persisted(self):
        """Railway cannot write the snapshot. That makes month-to-date UNKNOWN,
        and the caller must be able to tell UNKNOWN from a measured zero."""
        spend.SNAPSHOT_PATH = os.path.join(self.tmp.name, "nope", "x.json")
        spent, _, persisted = spend.month_delta(50.0, "abc123")
        self.assertEqual(spent, 0.0)
        self.assertFalse(persisted, "an unwritable snapshot must not read as a "
                                    "measured, persisted zero")


class TheKeyFingerprintIsOneWay(unittest.TestCase):
    def test_fingerprint_is_not_the_key(self):
        key = "sk-or-v1-abcdef0123456789"
        fp = spend.key_fingerprint(key)
        self.assertEqual(len(fp), 12)
        self.assertNotIn(fp, key)
        self.assertNotEqual(fp, key[:12])

    def test_different_keys_differ(self):
        self.assertNotEqual(spend.key_fingerprint("a"), spend.key_fingerprint("b"))


class TheRunMeterIsExact(unittest.TestCase):
    def setUp(self):
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        # Pin prices so the test does not depend on the network or on a
        # provider's live price list.
        spend._prices_fetched = True
        spend._price_cache["test/model"] = (1e-6, 2e-6)
        self.addCleanup(lambda: spend._price_cache.pop("test/model", None))

    def test_cost_comes_from_the_charged_token_counts(self):
        spend.record_usage("test/model",
                           SimpleNamespace(prompt_tokens=1000, completion_tokens=500))
        self.assertAlmostEqual(spend.run_cost_usd(), 1000 * 1e-6 + 500 * 2e-6)

    def test_a_broken_usage_object_costs_zero_and_never_raises(self):
        """A meter must not be able to break the pipeline it measures."""
        spend.record_usage("test/model", None)
        spend.record_usage("test/model", SimpleNamespace(prompt_tokens="x"))
        self.assertEqual(spend.run_cost_usd(), 0.0)

    def test_run_summary_reports_cost_per_stored_row(self):
        spend.record_usage("test/model",
                           SimpleNamespace(prompt_tokens=1000, completion_tokens=0))
        self.assertIn("per stored row", spend.run_summary(rows_stored=4))

    def test_run_summary_says_so_when_a_run_bought_nothing(self):
        spend.record_usage("test/model",
                           SimpleNamespace(prompt_tokens=1000, completion_tokens=0))
        self.assertIn("bought nothing", spend.run_summary(rows_stored=0))

    def test_unknown_model_is_priced_dearer_than_deepseek(self):
        """Being wrong in the expensive direction trips the guard early, which
        is the safe way to be wrong about a price."""
        p_unknown, c_unknown = spend.price_for("some/model-nobody-listed")
        p_ds, c_ds = spend.FALLBACK_PRICES["deepseek/deepseek-chat"]
        self.assertGreater(p_unknown, p_ds)
        self.assertGreater(c_unknown, c_ds)


class TheGateDegrades(unittest.TestCase):
    def setUp(self):
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        self._env = os.environ.get(spend.PAID_READS_ENV)
        self.addCleanup(lambda: os.environ.__setitem__(
            spend.PAID_READS_ENV, self._env) if self._env is not None
            else os.environ.pop(spend.PAID_READS_ENV, None))
        os.environ.pop(spend.PAID_READS_ENV, None)

    def test_paid_reads_on_by_default(self):
        self.assertTrue(spend.paid_reads_enabled())

    def test_env_off_disables_paid_reads(self):
        os.environ[spend.PAID_READS_ENV] = "off"
        self.assertFalse(spend.paid_reads_enabled())

    def test_per_run_ceiling_disables_paid_reads_without_any_stored_state(self):
        """The only brake that works on Railway, which has no persistence."""
        spend._prices_fetched = True
        spend._price_cache["test/model"] = (1.0, 1.0)   # $1 per token
        self.addCleanup(lambda: spend._price_cache.pop("test/model", None))
        spend.record_usage("test/model",
                           SimpleNamespace(prompt_tokens=int(spend.RUN_CEILING_USD) + 1,
                                           completion_tokens=0))
        self.assertFalse(spend.paid_reads_enabled())

    def test_degrade_sets_the_flag_in_this_process(self):
        """cron.py degrades in-process; a $GITHUB_ENV-only write would miss it."""
        spend.degrade(True)
        self.assertEqual(os.environ.get(spend.PAID_READS_ENV), "off")
        self.assertFalse(spend.paid_reads_enabled())

    def test_degrade_when_not_over_leaves_paid_reads_on(self):
        spend.degrade(False)
        self.assertTrue(spend.paid_reads_enabled())


class EveryPaidCallIsGated(unittest.TestCase):
    """No paid function may reach the network while paid reads are off."""

    PAID = ("extract_layoff_data", "classify_ai_evidence", "extract_context_evidence",
            "classify_reason_tags", "classify_industry", "extract_role_categories")

    def setUp(self):
        os.environ[spend.PAID_READS_ENV] = "off"
        self.addCleanup(lambda: os.environ.pop(spend.PAID_READS_ENV, None))
        extractor._spend_deferrals = 0
        self.addCleanup(lambda: setattr(extractor, "_spend_deferrals", 0))

        def explode(*a, **k):
            raise AssertionError("a paid call was made while paid reads are OFF")

        self._real = extractor._get_client
        extractor._get_client = explode
        self.addCleanup(lambda: setattr(extractor, "_get_client", self._real))

    def test_every_paid_function_defers_and_never_calls_the_model(self):
        text = "Acme Corp said it will cut 300 jobs because of automation."
        calls = {
            "extract_layoff_data": lambda: extractor.extract_layoff_data(
                {"raw_text": text, "source_url": "https://example.com/a"}),
            "classify_ai_evidence": lambda: extractor.classify_ai_evidence(text),
            "extract_context_evidence": lambda: extractor.extract_context_evidence(text),
            "classify_reason_tags": lambda: extractor.classify_reason_tags(text),
            "classify_industry": lambda: extractor.classify_industry("Acme Corp", text),
            "extract_role_categories": lambda: extractor.extract_role_categories(text),
        }
        for name in self.PAID:
            with self.subTest(fn=name):
                self.assertIsNone(
                    calls[name](),
                    f"{name} must return None when deferred — None is the "
                    f"'retry later, row stays queued' value for every caller. "
                    f"A definitive empty result would write a wrong answer.")

    def test_a_deferral_is_never_an_exception(self):
        """An exception would land in each caller's failure counter and could
        trip cron.py's loud 'posted 0 with N failures' exit, turning a budget
        decision into a red data job."""
        try:
            extractor.extract_layoff_data({"raw_text": "x y z", "source_url": "u"})
        except Exception as exc:  # pragma: no cover - the assertion is the point
            self.fail(f"deferral raised {exc!r} instead of returning None")

    def test_source_says_every_paid_function_is_gated(self):
        """Source-level backstop: a future paid function added without a gate
        should fail here rather than quietly spend."""
        for name in self.PAID:
            with self.subTest(fn=name):
                body = EXTRACTOR.split(f"def {name}(", 1)[1].split("\ndef ", 1)[0]
                self.assertIn("spend.paid_reads_enabled()", body,
                              f"{name} makes a paid call with no spend gate")
                self.assertIn("spend.record_usage(", body,
                              f"{name} spends without metering it")


class TheClientItselfIsGated(unittest.TestCase):
    """Three modules call extractor._get_client() directly, past the public
    functions' gates. The client must refuse too, or they spend regardless."""

    DIRECT_CALLERS = ("railway/sources/warn_llm.py",
                      "railway/sources/warn_hi_ocr.py",
                      "railway/edgar_recall_probe.py")

    def setUp(self):
        os.environ[spend.PAID_READS_ENV] = "off"
        self.addCleanup(lambda: os.environ.pop(spend.PAID_READS_ENV, None))

    def test_get_client_refuses_when_paid_reads_are_off(self):
        with self.assertRaises(extractor.PaidReadsDisabled):
            extractor._get_client()

    def test_the_refusal_is_an_ordinary_exception(self):
        """All three direct callers catch bare `Exception` and degrade to a
        safe value. The gate must land in that handler, not escape it."""
        self.assertTrue(issubclass(extractor.PaidReadsDisabled, Exception))

    def test_direct_callers_still_degrade_safely(self):
        """warn_llm returns 0 so the WARN row still imports with its
        deterministic count; the recall probe returns 'unknown', never a pass."""
        for rel in self.DIRECT_CALLERS:
            with self.subTest(module=rel):
                src = (ROOT / rel).read_text()
                self.assertIn("except Exception", src)
                self.assertIn("spend.record_usage(", src,
                              f"{rel} spends without metering it")


class FreeIngestSurvivesDegradation(unittest.TestCase):
    """The property that makes degrading safe: WARN/SEC/ERM cost nothing and
    must keep running under every degraded state."""

    FREE_WORKERS = (
        "railway/warn_import.py",
        "railway/erm_import.py",
        "railway/hi_warn_import.py",
        "railway/federal_rif_import.py",
    )

    def test_the_free_importers_never_import_the_extractor(self):
        for rel in self.FREE_WORKERS:
            path = ROOT / rel
            if not path.exists():
                continue
            with self.subTest(worker=rel):
                src = path.read_text()
                self.assertNotIn("from extractor import", src,
                                 f"{rel} is supposed to be free of model calls")
                self.assertNotIn("chat.completions", src)

    def test_cron_collectors_run_before_any_paid_call(self):
        """Degrading must not skip collection: the free pulls and the health
        reporting all happen above the extraction loop."""
        collect = CRON.index("Pulled {len(entries)} raw entries")
        extract = CRON.index("extracted = extract_layoff_data(raw)")
        self.assertLess(collect, extract)
        for collector in ("pull_edgar_filings", "pull_google_news",
                          "pull_gdelt_between", "pull_press_releases"):
            with self.subTest(collector=collector):
                self.assertLess(CRON.index(collector), extract,
                                f"{collector} must run before any paid call so a "
                                f"degraded run still collects")

    def test_a_degraded_cron_run_cannot_fail_loudly(self):
        """Deferrals increment skipped_not_layoff, never `failed`, so the
        'posted 0 with N failures' loud exit cannot fire on a budget decision."""
        loop = CRON.split("for raw in entries:", 1)[1].split("print(", 1)[0]
        self.assertIn("skipped_not_layoff += 1", loop)
        self.assertIn("if len(entries) > 0 and posted == 0 and failed >= 3", CRON,
                      "the loud exit must still require real post failures")

    def test_deferred_candidates_are_left_unmarked(self):
        """seen_urls drops a URL only when the SITE already holds it. A deferred
        candidate writes no row, so it is re-pulled. Pin that the pre-check has
        no local 'already tried' memory that would strand it."""
        src = (ROOT / "railway/seen_urls.py").read_text()
        self.assertIn("seen-urls", src)
        for marker in ("open(", "json.dump", "pickle"):
            self.assertNotIn(marker, src,
                             "seen_urls must not persist attempted URLs locally, "
                             "or a deferred candidate would never come back")


class EveryPaidWorkflowIsGuarded(unittest.TestCase):
    """A guard that covers only some entry points leaves the largest consumer
    unguarded, which is exactly the situation on 2026-08-02: the Railway cron
    spent invisibly because every cost check lived in GitHub Actions."""

    # The balance reporter makes no paid calls; it OWNS the snapshot instead.
    EXEMPT = {"openrouter-balance-check.yml"}

    def test_every_workflow_holding_the_key_runs_the_degrade_step(self):
        wf = ROOT / ".github/workflows"
        paid = [p for p in sorted(wf.glob("*.yml"))
                if "OPENROUTER_API_KEY" in p.read_text() and p.name not in self.EXEMPT]
        self.assertGreater(len(paid), 20, "expected the full paid workflow set")
        for p in paid:
            with self.subTest(workflow=p.name):
                self.assertIn("spend.py --degrade", p.read_text(),
                              f"{p.name} can spend but runs no spend guard")

    def test_the_guard_never_uses_enforce_in_a_collecting_workflow(self):
        """--enforce halts. Halting a job whose free collectors cost nothing is
        the self-inflicted outage this design exists to avoid."""
        for p in sorted((ROOT / ".github/workflows").glob("*.yml")):
            with self.subTest(workflow=p.name):
                self.assertNotIn("spend.py --enforce", p.read_text())

    def test_the_snapshot_is_committed_by_the_balance_job(self):
        """An uncommitted snapshot is no snapshot: every runner is ephemeral, so
        month-to-date would restart at zero on every run and never enforce."""
        wf = (ROOT / ".github/workflows/openrouter-balance-check.yml").read_text()
        self.assertIn("railway/spend_month.json", wf)
        self.assertIn("git add", wf)

    def test_scripts_with_their_own_client_are_gated_too(self):
        """extractor.py's gate cannot cover a script that builds its own
        OpenAI client. These four do, so each needs its own check."""
        for rel in ("railway/ai_evidence_sweep.py", "railway/process_tips.py",
                    "railway/source_verification_audit.py",
                    "railway/daily_classification_spotcheck.py",
                    "railway/dedupe_llm.py"):
            with self.subTest(script=rel):
                src = (ROOT / rel).read_text()
                self.assertIn("spend.paid_reads_enabled()", src,
                              f"{rel} builds its own client and must gate itself")


class PolicyIsInTheDiffNotASecret(unittest.TestCase):
    def test_allowance_is_a_literal_constant(self):
        self.assertEqual(spend.MONTHLY_ALLOWANCE_USD, 7.0)
        self.assertIn("MONTHLY_ALLOWANCE_USD = 7.0", SPEND)

    def test_allowance_is_documented_as_interim(self):
        preamble = SPEND.split("MONTHLY_ALLOWANCE_USD = 7.0")[0][-2400:]
        self.assertIn("INTERIM", preamble.upper())

    def test_allowance_is_not_read_from_the_environment(self):
        self.assertNotIn('environ.get("ALT_MONTHLY_ALLOWANCE', SPEND)

    def test_spend_module_is_stdlib_only(self):
        """ops_status.py is stdlib-only by rule and the local test env has no
        `requests`. A guard that cannot be imported is not enforced."""
        self.assertNotIn("\nimport requests", SPEND)
        self.assertIn("urllib.request", SPEND)


class TheCronIsGuarded(unittest.TestCase):
    """The largest consumer had no guard at all until 2026-08-02."""

    def test_cron_runs_a_spend_preflight_before_collecting(self):
        self.assertIn("_spend_preflight()", CRON)
        self.assertLess(CRON.index("def _spend_preflight"),
                        CRON.index("def run():"))

    def test_preflight_failure_cannot_break_the_run(self):
        body = CRON.split("def _spend_preflight", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("except Exception", body)
        self.assertNotIn("raise", body)

    def test_cron_reports_what_the_run_cost(self):
        self.assertIn("spend.run_summary(rows_stored=posted)", CRON)

    def test_unknown_month_to_date_is_not_reported_as_within_budget(self):
        body = CRON.split("def _spend_preflight", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("UNKNOWN", body)


if __name__ == "__main__":
    unittest.main()


class BackfillBoundsWhatItCanSpend(unittest.TestCase):
    """backfill.py could make unbounded model calls and never trip its cap.

    Measured 2026-08-02: 5,044 filings read on 07-28 and 4,190 on 07-29, the
    two days the OpenRouter account fell $11.11 and $10.50. Two causes, both
    absent from the file and both present in its gdelt sibling:

      * no seen-URL pre-check, so the rotating sweep re-read filings the site
        already held -- and since only 8.5% of runs land on a month from the
        last twelve, it re-read the SAME deep history pass after pass
      * BACKFILL_LIMIT counts POSTS, so a window where nothing qualifies makes
        calls forever without the limit ever being reached
    """

    def test_the_seen_url_precheck_runs_before_the_extractor(self):
        src = (ROOT / "railway" / "backfill.py").read_text()
        self.assertIn("filter_already_seen", src,
                      "backfill.py must skip URLs the site already holds "
                      "before paying to read them, as gdelt_backfill.py does")
        pre = src.index("filter_already_seen")
        call = src.index("extract_layoff_data(raw)")
        self.assertLess(pre, call,
                        "the pre-check has to happen BEFORE the model call, "
                        "or it saves nothing")

    def test_the_precheck_fails_open(self):
        """An optimisation that cannot run must not skip unseen filings.

        Failing closed here would silently drop coverage to save money, which
        is the trade this project never makes.
        """
        src = (ROOT / "railway" / "backfill.py").read_text()
        seg = src[src.index("filter_already_seen") - 400:
                  src.index("extract_layoff_data(raw)")]
        self.assertIn("except", seg,
                      "a failing pre-check must fall back to reading all")

    def test_there_is_a_ceiling_on_calls_not_only_on_posts(self):
        src = (ROOT / "railway" / "backfill.py").read_text()
        self.assertIn("BACKFILL_MAX_CALLS", src,
                      "BACKFILL_LIMIT bounds a run's OUTPUT; only a call "
                      "ceiling bounds what it can spend")
        self.assertIn("calls >= call_limit", src)
        self.assertIn("calls += 1", src)
