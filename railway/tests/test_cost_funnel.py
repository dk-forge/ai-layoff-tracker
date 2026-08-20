"""Cost-funnel port for the Railway cron: per-source attribution, the cheap
pre-extraction gate (shadow by default), charged-cost metering, and the
tracker-meta round trip that finally makes the cron's spend harvestable.

Every test here was verified to FAIL on the pre-funnel tree (origin/main
4023592): the attribution/gate APIs did not exist, record_usage ignored the
charged cost, classify_ai_evidence sent the full extraction preamble, and
nothing persisted or harvested a Railway run record.
"""
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import spend
import extractor
import cron

REPO = Path(__file__).resolve().parents[2]


def _fake_response(content, usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=usage)


class _FakeCompletions:
    def __init__(self, content="{}", usage=None, exc=None):
        self.content, self.usage, self.exc = content, usage, exc
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return _fake_response(self.content, self.usage)


def _fake_client(completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


class ChargedCostMeterTests(unittest.TestCase):
    """The meter must be the bill when the bill is on the response."""

    def setUp(self):
        spend.reset_run_meter()
        spend._prices_fetched = True  # no network in tests

    def tearDown(self):
        spend.reset_run_meter()

    def test_charged_cost_preferred_over_price_table(self):
        usage = {"prompt_tokens": 1000, "completion_tokens": 100,
                 "cost": 0.000123}
        cost = spend.record_usage("deepseek/deepseek-chat", usage)
        self.assertAlmostEqual(cost, 0.000123)
        self.assertAlmostEqual(spend.run_cost_usd(), 0.000123)

    def test_charged_cost_read_from_sdk_object_too(self):
        usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=100,
                                cost=0.000321, prompt_tokens_details=None)
        self.assertAlmostEqual(
            spend.record_usage("deepseek/deepseek-chat", usage), 0.000321)

    def test_fallback_still_prices_tokens_when_no_charge_present(self):
        usage = {"prompt_tokens": 1000, "completion_tokens": 100}
        p, c = spend.price_for("deepseek/deepseek-chat")
        self.assertAlmostEqual(
            spend.record_usage("deepseek/deepseek-chat", usage),
            1000 * p + 100 * c)

    def test_cached_prompt_tokens_are_counted(self):
        usage = {"prompt_tokens": 1000, "completion_tokens": 10,
                 "prompt_tokens_details": {"cached_tokens": 600}}
        spend.record_usage("deepseek/deepseek-chat", usage)
        self.assertEqual(spend._run["cached_prompt_tokens"], 600)

    def test_gate_model_has_a_fallback_price(self):
        # The gate must be meterable even when the live price fetch is blocked.
        self.assertIn(extractor.GATE_MODEL, spend.FALLBACK_PRICES)


class PerSourceAttributionTests(unittest.TestCase):
    def setUp(self):
        spend.reset_run_meter()
        spend._prices_fetched = True

    def tearDown(self):
        spend.reset_run_meter()

    def test_calls_book_under_the_active_source_tag(self):
        spend.set_meter_context("gdelt")
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 10, "completion_tokens": 1,
                            "cost": 0.002})
        spend.set_meter_context("google_news")
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 10, "completion_tokens": 1,
                            "cost": 0.001})
        bd = spend.run_breakdown()
        self.assertAlmostEqual(bd["gdelt"]["cost_usd"], 0.002)
        self.assertAlmostEqual(bd["google_news"]["cost_usd"], 0.001)
        # The breakdown must sum to the run total or it is decoration.
        self.assertAlmostEqual(sum(v["cost_usd"] for v in bd.values()),
                               spend.run_cost_usd())

    def test_gate_outcomes_and_annotations_land_in_the_record(self):
        spend.set_meter_context("gdelt")
        spend.record_gate_outcome(True)
        spend.record_gate_outcome(False)
        spend.annotate_tag("gdelt", items=7, stored=2)
        entry = spend.record_job_run(items=7, stored=2, job="railway-cron",
                                     run_id="railway-test")
        self.assertEqual(entry["run_id"], "railway-test")
        src = entry["sources"]["gdelt"]
        self.assertEqual((src["kept"], src["dropped"]), (1, 1))
        self.assertEqual((src["items"], src["stored"]), (7, 2))

    def test_reset_clears_the_breakdown(self):
        spend.set_meter_context("gdelt")
        spend.record_gate_outcome(True)
        spend.reset_run_meter()
        self.assertEqual(spend.run_breakdown(), {})


class GateTests(unittest.TestCase):
    def setUp(self):
        spend.reset_run_meter()
        spend._prices_fetched = True
        self.entry = {"raw_text": "Acme Corp to lay off 500 workers",
                      "source_name": "Example Wire", "source_type": "news"}

    def tearDown(self):
        spend.reset_run_meter()

    def test_yes_and_no_verdicts(self):
        for content, want in (("YES", extractor.GATE_YES),
                              ("NO", extractor.GATE_NO),
                              ("No.", extractor.GATE_NO),
                              ("yes", extractor.GATE_YES)):
            fake = _FakeCompletions(content=content)
            with patch.object(extractor, "_get_client",
                              return_value=_fake_client(fake)):
                self.assertEqual(extractor.gate_verdict(self.entry), want,
                                 content)

    def test_gate_fails_open_on_error_and_on_empty_reply(self):
        fake = _FakeCompletions(exc=RuntimeError("provider down"))
        with patch.object(extractor, "_get_client",
                          return_value=_fake_client(fake)):
            self.assertEqual(extractor.gate_verdict(self.entry),
                             extractor.GATE_ERROR)
        fake = _FakeCompletions(content="")
        with patch.object(extractor, "_get_client",
                          return_value=_fake_client(fake)):
            self.assertEqual(extractor.gate_verdict(self.entry),
                             extractor.GATE_ERROR)

    def test_gate_never_spends_when_paid_reads_are_off(self):
        fake = _FakeCompletions(content="YES")
        with patch.object(spend, "paid_reads_enabled", return_value=False), \
             patch.object(extractor, "_get_client",
                          return_value=_fake_client(fake)):
            self.assertEqual(extractor.gate_verdict(self.entry),
                             extractor.GATE_ERROR)
        self.assertEqual(fake.calls, [])

    def test_gate_uses_the_gate_model_and_one_word_budget(self):
        fake = _FakeCompletions(content="YES")
        with patch.object(extractor, "_get_client",
                          return_value=_fake_client(fake)):
            extractor.gate_verdict(self.entry)
        call = fake.calls[0]
        self.assertEqual(call["model"], extractor.GATE_MODEL)
        self.assertLessEqual(call["max_tokens"], 8)
        self.assertEqual(call["messages"][0]["content"], extractor.GATE_SYSTEM)
        # The candidate text must be bounded: a gate that reads the full body
        # is a second extraction, not a gate.
        self.assertLessEqual(len(call["messages"][1]["content"]),
                             extractor.GATE_CHARS + 200)

    def test_gate_prompt_is_a_fraction_of_the_extraction_prompt(self):
        # The whole point: a reject must cost a small fraction of an
        # extraction. System prompts are the fixed part of each call.
        self.assertLess(len(extractor.GATE_SYSTEM),
                        len(extractor.SYSTEM_PROMPT) / 4)


class DeadPromptContextTests(unittest.TestCase):
    def setUp(self):
        spend.reset_run_meter()
        spend._prices_fetched = True

    def test_ai_causation_call_drops_the_extraction_preamble(self):
        fake = _FakeCompletions(
            content='{"ai_causation":"unknown","ai_language":null,"confidence":50}')
        with patch.object(extractor, "_get_client",
                          return_value=_fake_client(fake)):
            extractor.classify_ai_evidence("Acme cut 500 jobs citing costs.")
        call = fake.calls[0]
        self.assertEqual(call["messages"][0]["content"], extractor.MINI_SYSTEM)
        self.assertNotEqual(call["messages"][0]["content"],
                            extractor.SYSTEM_PROMPT)
        # Correctness-critical: the MODEL must stay the extraction model.
        self.assertEqual(call["model"], extractor.MODEL)

    def test_every_llm_call_requests_charged_usage_accounting(self):
        src = (REPO / "railway" / "extractor.py").read_text()
        creates = src.count("chat.completions.create(")
        self.assertGreaterEqual(creates, 7)
        self.assertEqual(src.count("extra_body=USAGE_ACCOUNTING"), creates,
                         "every chat.completions.create call must request "
                         "OpenRouter usage accounting (usage.cost)")


class CronWiringTests(unittest.TestCase):
    """Behavioural: the gate in shadow mode must never cost a row."""

    def setUp(self):
        spend.reset_run_meter()
        spend._prices_fetched = True

    def tearDown(self):
        spend.reset_run_meter()

    def _run_cron(self, gate_mode, verdict, extracted):
        entry = {"raw_text": "Acme Corp to lay off 500 workers",
                 "source_url": "https://x.test/1", "source_type": "news",
                 "source_name": "Example Wire"}
        posted = []
        # EVERY source in cron.run()'s table must be stubbed here, including
        # any added later. When local_news was armed by committed default
        # (2026-08-14, 4931498) this harness did not stub it, so each of these
        # five tests ran a REAL 25-market, 87-query Google News RSS pull with a
        # 1s pacing sleep per query - about 90s per test when the RSS answered
        # instantly and unbounded when it throttled. Four Tests runs
        # self-cancelled on the 15-minute ceiling that afternoon; the suite
        # itself was ~6 minutes. The workflow's contract is offline and fast.
        #
        # ...AND IT HAPPENED AGAIN, because a comment is not a guard.
        # regional_feeds and national_feeds joined that table afterwards and
        # nobody added them here, so all seven of these tests ran the real
        # pullers and paid their per-feed pacing: 15.0s + 5.0s = 20.1s EACH,
        # 141s of pure sleep in every CI run, which is most of the distance
        # "Tests" travelled from 353s (2026-08-14) to self-killing at 15m0s on
        # 2026-08-18. Measured with sleeps neutralised, the same test is 0.1s.
        #
        # So the tripwire below is now the guard, and it is deliberately wider
        # than the miss: this harness may not SLEEP and may not RESOLVE A HOST.
        # A source added to cron's table without a stub here fails loudly on
        # the first one it tries, in the test that forgot it, instead of
        # quietly buying twenty seconds a run until the wall arrives.
        # It raises a BaseException, NOT an AssertionError, and that detail is
        # the whole guard. cron.run() wraps each collector in `except
        # Exception` precisely so one broken source cannot kill a run - which
        # means an ordinary assertion raised inside a source is caught,
        # reported as "errors=1", and the test goes green having proved
        # nothing. Verified: with an AssertionError the removed-stub fixture
        # still passed. BaseException walks straight out through every
        # `except Exception` in the chain and fails the test that forgot.
        class _WentOffline(BaseException):
            pass

        def _offline(*a, **k):
            raise _WentOffline(
                "cron.run() slept or reached the network inside this harness. "
                "Some source in cron.run()'s table is NOT stubbed below - it "
                "is running for real. Add it to this `with` block rather than "
                "letting the suite pay for it; see the comment above.")

        with patch("time.sleep", _offline), \
             patch("socket.getaddrinfo", _offline), \
             patch.object(cron, "GATE_MODE", gate_mode), \
             patch.object(cron, "_mark_phase"), \
             patch.object(cron, "_spend_preflight"), \
             patch.object(cron, "report_source_health"), \
             patch.object(cron, "_post_spend_record") as post_rec, \
             patch.object(cron, "pull_edgar_filings", return_value=[]), \
             patch.object(cron, "pull_google_news", return_value=[entry]), \
             patch.object(cron, "_pull_local_news_rows", return_value=[]), \
             patch.object(cron, "_pull_regional_feeds_rows", return_value=[]), \
             patch.object(cron, "_pull_national_feeds_rows", return_value=[]), \
             patch.object(cron, "pull_press_releases", return_value=[]), \
             patch.object(cron, "reviewed_feed_count", return_value=1), \
             patch.object(cron, "pull_gdelt_between", return_value=[]), \
             patch.object(cron, "filter_already_seen", side_effect=lambda e: e), \
             patch.object(extractor, "gate_verdict", return_value=verdict) as gate, \
             patch.object(cron, "extract_layoff_data",
                          return_value=extracted) as extract, \
             patch.object(cron, "post_to_wordpress",
                          side_effect=lambda x: posted.append(x) or "posted"):
            cron.run()
        return gate, extract, posted, post_rec

    def _default_gate_mode(self):
        """The module's own default, with ALT_GATE_MODE out of the way."""
        import importlib
        with patch.dict("os.environ", {}, clear=False):
            import os as _os
            _os.environ.pop("ALT_GATE_MODE", None)
            return importlib.reload(cron).GATE_MODE

    def test_default_mode_enforces_a_no_verdict(self):
        """Behavioural, not a constant check: on the SHIPPED default a NO
        verdict must cost an extraction.

        Shadow measured the gate at 103 NO verdicts / 0 false drops, so the
        default now enforces. This asserts the property that saves the money
        (and, under the per-run ceiling, buys the extra candidates) rather than
        the spelling of the mode, so it still holds if the mode is renamed.
        """
        gate, extract, posted, _ = self._run_cron(
            self._default_gate_mode(), extractor.GATE_NO, None)
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(extract.call_count, 0, "default mode extracted a gate NO")
        self.assertEqual(posted, [])

    def test_default_mode_still_fails_open_on_gate_error(self):
        """The default must never let a provider outage read as a quiet day."""
        extracted = {"company_name": "Acme", "job_count": 500}
        _, extract, posted, _ = self._run_cron(
            self._default_gate_mode(), extractor.GATE_ERROR, extracted)
        self.assertEqual(extract.call_count, 1)
        self.assertEqual(len(posted), 1)

    def test_shadow_gate_no_still_extracts_and_posts(self):
        extracted = {"company_name": "Acme", "job_count": 500}
        gate, extract, posted, _ = self._run_cron(
            "shadow", extractor.GATE_NO, extracted)
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(extract.call_count, 1)
        self.assertEqual(len(posted), 1)

    def test_live_gate_no_skips_extraction(self):
        gate, extract, posted, _ = self._run_cron(
            "live", extractor.GATE_NO, None)
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(extract.call_count, 0)
        self.assertEqual(posted, [])

    def test_live_gate_error_fails_open_to_extraction(self):
        extracted = {"company_name": "Acme", "job_count": 500}
        gate, extract, posted, _ = self._run_cron(
            "live", extractor.GATE_ERROR, extracted)
        self.assertEqual(extract.call_count, 1)
        self.assertEqual(len(posted), 1)

    def test_off_mode_makes_no_gate_calls(self):
        extracted = {"company_name": "Acme", "job_count": 500}
        gate, extract, posted, _ = self._run_cron(
            "off", extractor.GATE_YES, extracted)
        self.assertEqual(gate.call_count, 0)
        self.assertEqual(extract.call_count, 1)

    def test_run_posts_a_spend_record_with_source_breakdown(self):
        extracted = {"company_name": "Acme", "job_count": 500}
        _, _, _, post_rec = self._run_cron(
            "shadow", extractor.GATE_YES, extracted)
        self.assertEqual(post_rec.call_count, 1)
        rec = post_rec.call_args[0][0]
        self.assertEqual(rec["job"], "railway-cron")
        self.assertTrue(str(rec["run_id"]).startswith("railway-"))
        self.assertEqual(rec["gate_mode"], "shadow")
        self.assertIn("google_news", rec.get("sources", {}))
        self.assertEqual(rec["sources"]["google_news"]["items"], 1)
        self.assertEqual(rec["sources"]["google_news"]["stored"], 1)


class RailwayHarvestTests(unittest.TestCase):
    def test_harvest_railway_runs_maps_tracker_meta_records(self):
        meta = {"spend_runs": [
            {"date": "2026-08-04", "run_id": "railway-20260804T1300",
             "cost_usd": 0.0812, "calls": 101, "items": 240, "stored": 12,
             "sources": {"gdelt": {"cost_usd": 0.05, "calls": 60}},
             "gate_mode": "shadow"},
            {"bogus": True},
        ]}

        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch.dict("os.environ",
                        {"WP_SITE_URL": "https://example.test/blog",
                         "WP_API_KEY": "k"}), \
             patch("urllib.request.urlopen",
                   return_value=_Resp(json.dumps(meta).encode())):
            rows = spend.harvest_railway_runs()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["job"], "railway-cron")
        self.assertEqual(row["run_id"], "railway-20260804T1300")
        self.assertEqual(row["sources"]["gdelt"]["calls"], 60)
        # And the ledger merge keys the twice-daily runs apart by run_id.
        ledger = {"v": 1, "entries": []}
        second = dict(row, run_id="railway-20260804T2200")
        self.assertEqual(spend._merge_ledger_entries(ledger, [row, second]), 2)

    def test_harvest_railway_runs_is_unknown_not_silent_without_keys(self):
        with patch.dict("os.environ", {"WP_SITE_URL": "", "WP_API_KEY": ""}):
            self.assertEqual(spend.harvest_railway_runs(), [])


class SurfaceContractTests(unittest.TestCase):
    """Static pins on the PHP endpoint and the harvest workflow, so the
    Python half of the round trip cannot outlive the other half."""

    def test_tracker_meta_endpoint_accepts_and_bounds_spend_runs(self):
        php = (REPO / "wordpress-plugin" / "ai-layoff-tracker" / "includes"
               / "db.php").read_text()
        self.assertIn("add_spend_run", php)
        self.assertIn("spend_runs", php)
        self.assertIn("array_slice($meta['spend_runs'], -240)", php)

    def test_balance_workflow_harvest_step_can_reach_tracker_meta(self):
        yml = (REPO / ".github" / "workflows"
               / "openrouter-balance-check.yml").read_text()
        self.assertIn("Harvest per-job spend ledger lines", yml)
        harvest_step = yml.split("Harvest per-job spend ledger lines", 1)[1]
        harvest_step = harvest_step.split("- name:", 1)[0]
        self.assertIn("spend.py --harvest", harvest_step)
        self.assertIn("WP_API_KEY", harvest_step)
        self.assertIn("WP_SITE_URL", harvest_step)


if __name__ == "__main__":
    unittest.main()
