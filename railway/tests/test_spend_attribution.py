"""Attribution, cost per stored row, and earned cadence.

THE BUG THIS FILE EXISTS FOR (measured 2026-08-04). `spend.harvest()` asked
GitHub for `.../actions/runs?created=>SINCE&per_page=100` and read the answer as
if it were the whole window. The API answers newest-first and pages at 100. On
that date the 2-day window held 414 completed runs, so one page reached back
about seven hours. The balance job harvests at 13:00 UTC, so every job scheduled
after 13:00 emitted its SPEND_LEDGER_V1 line into a log the harvester never
opened.

The visible damage was not an empty file, which somebody would have noticed. It
was a ledger that showed $0.0269 of a day whose Actions jobs actually cost
$0.1644 -- 16% -- so the tracker read an order of magnitude cheaper than it was
and the rest got written off as unattributable spend.

Every test below fails on the pre-fix tree.
"""
import datetime
import os
import tempfile
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

import spend  # noqa: E402


def _ledger(entries):
    return {"v": 1, "entries": entries}


def _day(offset):
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=offset)).strftime("%Y-%m-%d")


class HarvestPaginationTests(unittest.TestCase):
    """The harvester must read the WHOLE window, not the first page of it."""

    def _api_over(self, total_runs):
        """A fake GitHub that holds `total_runs` runs and pages at 100."""
        runs = [{"id": i, "path": ".github/workflows/dedupe-llm.yml"}
                for i in range(total_runs)]
        seen_pages = []

        def api(path):
            page = 1
            if "&page=" in path:
                page = int(path.rsplit("&page=", 1)[1])
            seen_pages.append(page)
            lo = (page - 1) * 100
            return {"workflow_runs": runs[lo:lo + 100]}

        return api, seen_pages

    def test_a_window_larger_than_one_page_is_read_whole(self):
        # 414 is the measured 2-day volume of this repo on 2026-08-04.
        api, pages = self._api_over(414)
        runs, complete = spend.list_runs_in_window(api, "o/r", "2026-08-02")
        self.assertTrue(complete)
        self.assertEqual(len(runs), 414,
                         "the harvester read only part of the window, so every job "
                         "outside the newest 100 runs is silently unattributed")
        self.assertEqual(pages, [1, 2, 3, 4, 5])

    def test_a_short_window_stops_after_one_page(self):
        """A partial page means the window ran out: do not keep crawling."""
        api, pages = self._api_over(37)
        runs, complete = spend.list_runs_in_window(api, "o/r", "2026-08-02")
        self.assertTrue(complete)
        self.assertEqual(len(runs), 37)
        self.assertEqual(pages, [1])

    def test_hitting_the_page_cap_reports_incomplete_rather_than_lying(self):
        """UNKNOWN is not a pass: a truncated read must say it was truncated."""
        api, _ = self._api_over(100 * spend.HARVEST_MAX_PAGES + 1)
        _, complete = spend.list_runs_in_window(api, "o/r", "2026-08-02")
        self.assertFalse(complete)


class CostPerStoredRowTests(unittest.TestCase):
    """The funnel metric has to be readable back out of the ledger, or a
    regression is only ever visible as a surprise on the balance."""

    def test_rate_counts_changed_rows_not_just_stored_ones(self):
        # reason-backfill edits rows in place and stores none. Counting only
        # `stored` would report the repo's cheapest job as pure waste.
        led = _ledger([{"job": "reason-backfill", "date": _day(1), "cost_usd": 0.005,
                        "calls": 34, "stored": None, "changed": 400}])
        stats = spend.job_row_costs(ledger=led)["reason-backfill"]
        self.assertEqual(stats["rows"], 400)
        self.assertAlmostEqual(stats["usd_per_row"], 0.005 / 400)

    def test_a_run_that_counted_no_rows_is_unknown_not_zero(self):
        led = _ledger([{"job": "process-tips", "date": _day(1), "cost_usd": 0.004,
                        "calls": 3, "stored": None, "changed": None}])
        stats = spend.job_row_costs(ledger=led)["process-tips"]
        self.assertIsNone(stats["usd_per_row"])
        self.assertFalse(stats["rows_known"])
        self.assertIn("UNKNOWN", spend.row_cost_report(ledger=led))

    def test_a_job_that_cost_nothing_is_not_reported_as_waste(self):
        led = _ledger([{"job": "process-tips", "date": _day(1), "cost_usd": 0.0,
                        "calls": 0, "stored": 0, "changed": None}])
        report = spend.row_cost_report(ledger=led)
        self.assertIn("no spend", report)
        self.assertNotIn("BOUGHT NOTHING", report)

    def test_a_job_that_spends_and_buys_nothing_is_named(self):
        # Measured: company-watchlist, $0.0606 over 101 calls, 0 rows, 2 days.
        led = _ledger([{"job": "company-watchlist", "date": _day(i), "cost_usd": 0.03,
                        "calls": 50, "stored": 0, "changed": None} for i in (3, 2, 1)])
        stats = spend.job_row_costs(ledger=led)["company-watchlist"]
        self.assertEqual(stats["barren_streak"], 3)
        self.assertIsNone(stats["usd_per_row"])

    def test_a_free_run_does_not_count_as_a_barren_run(self):
        """process-tips finds nothing most days and costs $0.00 doing it. That
        is a working job, not waste, and must not be reported as one."""
        led = _ledger([{"job": "process-tips", "date": _day(i), "cost_usd": 0.0,
                        "calls": 0, "stored": 0, "changed": None} for i in (3, 2, 1)])
        self.assertEqual(spend.job_row_costs(ledger=led)["process-tips"]["barren_streak"], 0)

    def test_producing_again_resets_the_streak(self):
        led = _ledger([
            {"job": "industry-backfill", "date": _day(3), "cost_usd": 0.02,
             "calls": 200, "stored": None, "changed": 0},
            {"job": "industry-backfill", "date": _day(2), "cost_usd": 0.02,
             "calls": 200, "stored": None, "changed": 0},
            {"job": "industry-backfill", "date": _day(1), "cost_usd": 0.02,
             "calls": 200, "stored": None, "changed": 13},
        ])
        self.assertEqual(spend.job_row_costs(ledger=led)["industry-backfill"]["barren_streak"], 0)


class UnattributedRemainderTests(unittest.TestCase):
    """'The numbers do not add up' has to become a number, or it stays a
    shrug. The ledger structurally cannot see the Railway cron; saying so with
    a figure is the difference between a known blind spot and a mystery."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig = spend.BALANCE_PATH
        self.addCleanup(lambda: setattr(spend, "BALANCE_PATH", self._orig))

    def _balances(self, series):
        path = os.path.join(self._tmp.name, "bal.json")
        with open(path, "w") as fh:
            json.dump(series, fh)
        spend.BALANCE_PATH = path

    def test_the_gap_between_the_balance_and_the_ledger_is_named(self):
        self._balances([{"date": _day(2), "balance": 10.0},
                        {"date": _day(1), "balance": 9.0}])
        led = _ledger([{"job": "dedupe-llm", "date": _day(1), "cost_usd": 0.25,
                        "calls": 60, "stored": None, "changed": 9}])
        out = "\n".join(spend.unattributed_report(ledger=led))
        self.assertIn("UNATTRIBUTED REMAINDER $0.7500", out)
        self.assertIn("remainder, not a measurement", out)

    def test_a_top_up_is_not_counted_as_a_refund(self):
        """The balance rises when the owner adds credit. Netting that against
        the days it fell would report the month as nearly free."""
        self._balances([{"date": _day(3), "balance": 10.0},
                        {"date": _day(2), "balance": 9.0},
                        {"date": _day(1), "balance": 40.0}])  # topped up
        out = "\n".join(spend.unattributed_report(ledger=_ledger([])))
        self.assertIn("fell $1.0000", out)

    def test_an_unreadable_balance_file_is_unknown_not_zero(self):
        spend.BALANCE_PATH = os.path.join(self._tmp.name, "missing.json")
        out = "\n".join(spend.unattributed_report(ledger=_ledger([])))
        self.assertIn("UNKNOWN", out)
        self.assertNotIn("REMAINDER", out)


class EarnedCadenceTests(unittest.TestCase):
    """A source that produces nothing earns a slower schedule -- but only where
    slowing it cannot cost coverage."""

    def _barren(self, job, n):
        return _ledger([{"job": job, "date": _day(n - i), "cost_usd": 0.02,
                         "calls": 100, "stored": 0, "changed": None} for i in range(n)])

    def test_a_barren_queue_draining_job_earns_the_slow_lane(self):
        led = self._barren("industry-backfill", spend.EARNED_SLOW_AFTER_BARREN_RUNS)
        skips = [spend.earned_skip("industry-backfill",
                                   today=datetime.date.fromordinal(o).isoformat(),
                                   ledger=led)[0]
                 for o in range(739000, 739000 + 6)]
        self.assertTrue(any(skips), "a barren backfill never sits a run out")
        self.assertTrue(any(not s for s in skips),
                        "the slow lane must still run, or the queue never drains")

    def test_a_discovery_job_is_never_slowed_automatically(self):
        """Running a discovery job less often is a real chance of noticing an
        event later. That is the owner's call, not this module's."""
        for job in ("supplemental-news", "company-watchlist", "distress-watchlist",
                    "ai-evidence-sweep", "news-catchup", "railway-cron"):
            led = self._barren(job, 20)
            skip, why = spend.earned_skip(job, today="2026-08-04", ledger=led)
            self.assertFalse(skip, f"{job} is discovery and must not be auto-slowed")
            self.assertIn("coverage", why)

    def test_no_history_means_full_cadence(self):
        """Absence of evidence is not evidence of an empty queue."""
        skip, why = spend.earned_skip("enrich-roles", today="2026-08-04",
                                      ledger=_ledger([]))
        self.assertFalse(skip)
        self.assertIn("no ledger history", why)

    def test_a_productive_job_keeps_full_cadence(self):
        led = _ledger([{"job": "enrich-roles", "date": _day(i), "cost_usd": 0.005,
                        "calls": 40, "stored": None, "changed": 10} for i in (3, 2, 1)])
        skip, _ = spend.earned_skip("enrich-roles", today="2026-08-04", ledger=led)
        self.assertFalse(skip)


class RetryCannotBuyAFreshCeilingTests(unittest.TestCase):
    """The most expensive path in the repo was the failure path.

    Several jobs wrap their script in `for attempt in 1 2 3; do python x.py`.
    Each attempt is a new process, and the per-run ceiling lived in process
    memory, so attempt 2 started from $0.00 and a job that failed twice could
    spend 3x its named ceiling with nothing reporting a problem.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = os.path.join(self._tmp.name, "run.json")
        self._env = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._env)))
        os.environ["ALT_RUN_SPEND_FILE"] = self.state
        os.environ.pop(spend.PAID_READS_ENV, None)
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)

    def _spend(self, usd):
        """Meter `usd` of spend without touching the network."""
        # record_usage reads INTEGER token counts, so meter in micro-dollars.
        spend._price_cache["test/model"] = (1e-6, 0.0)
        spend._prices_fetched = True
        spend.record_usage("test/model",
                           {"prompt_tokens": round(usd * 1e6), "completion_tokens": 0})

    def test_a_later_attempt_starts_from_what_the_run_already_spent(self):
        self._spend(spend.RUN_CEILING_USD * 0.9)
        self.assertTrue(spend.paid_reads_enabled())
        # A new attempt: the process meter is fresh, the run is not.
        spend.reset_run_meter()
        self.assertAlmostEqual(spend.carried_run_cost_usd(),
                               spend.RUN_CEILING_USD * 0.9, places=6)
        self._spend(spend.RUN_CEILING_USD * 0.2)
        self.assertFalse(spend.paid_reads_enabled(),
                         "a retry bought itself a fresh per-run ceiling")

    def test_an_unwritable_state_file_falls_back_to_a_fresh_meter(self):
        """Best effort in both directions: bookkeeping must never halt a job."""
        os.environ["ALT_RUN_SPEND_FILE"] = os.path.join(
            self._tmp.name, "nope", "run.json")
        spend.reset_run_meter()
        self.assertEqual(spend.carried_run_cost_usd(), 0.0)
        self._spend(1)  # must not raise
        self.assertTrue(spend.run_cost_usd() > 0)

    def test_no_durable_scratch_means_no_state_file(self):
        """Railway has no RUNNER_TEMP and no GITHUB_RUN_ID; behaviour there is
        exactly what it was before."""
        os.environ.pop("ALT_RUN_SPEND_FILE", None)
        os.environ.pop("GITHUB_RUN_ID", None)
        os.environ.pop("RUNNER_TEMP", None)
        self.assertIsNone(spend._run_state_path())


class CadenceIsActuallyWiredTests(unittest.TestCase):
    """A cadence decision nothing reads is a decision that never happens."""

    WORKFLOWS = Path(__file__).resolve().parents[2] / ".github/workflows"

    def test_every_queue_draining_workflow_asks_and_obeys(self):
        for job in sorted(spend.QUEUE_DRAINING_JOBS):
            src = (self.WORKFLOWS / f"{job}.yml").read_text()
            self.assertIn("spend.py --cadence", src, f"{job} never asks")
            self.assertIn("id: cadence", src, f"{job} cannot be referenced")
            self.assertIn("steps.cadence.outputs.skip != 'true'", src,
                          f"{job} asks and ignores the answer")

    def test_no_discovery_workflow_was_given_a_cadence_gate(self):
        for job in ("supplemental-news", "company-watchlist", "distress-watchlist",
                    "ai-evidence-sweep", "news-catchup"):
            src = (self.WORKFLOWS / f"{job}.yml").read_text()
            self.assertNotIn("--cadence", src,
                             f"{job} is discovery; slowing it is the owner's call")

    def test_the_spend_guard_still_runs_before_any_paid_step(self):
        """The cadence gate must not have displaced the degrade step."""
        for job in sorted(spend.QUEUE_DRAINING_JOBS):
            src = (self.WORKFLOWS / f"{job}.yml").read_text()
            self.assertIn("spend.py --degrade", src)
            self.assertLess(src.index("spend.py --cadence"),
                            src.index("spend.py --degrade"))


class DegradeStaysSoftTests(unittest.TestCase):
    """Guard the known past incident: --degrade turns paid reads off and exits
    0. Nothing added here may turn it back into a hard failure."""

    def test_degrade_and_cadence_never_exit_non_zero(self):
        src = (Path(__file__).resolve().parents[1] / "spend.py").read_text()
        self.assertIn("if args.degrade:", src)
        # The cadence branch returns 0 unconditionally.
        cadence = src.split("if args.cadence:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("return 0", cadence)
        self.assertNotIn("sys.exit(1)", cadence)


if __name__ == "__main__":
    unittest.main()
