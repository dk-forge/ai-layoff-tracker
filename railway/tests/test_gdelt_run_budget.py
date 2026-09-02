"""The daily gdelt collector must run under a clock.

`pull_gdelt_between` grew a `deadline` for a specific death - ten rotating
sweeps against a throttled public API, each patient with its own retry backoff
and no clock - and it was wired into gdelt_backfill.py only. cron.py, the
collector that actually feeds the tracker, kept calling it unbounded and kept
dying: no end-of-run record in spend_jobs.json on 2026-08-19, 2026-08-26 or
2026-08-27, and an orphaned `running` health note on each of those dates.

A killed run reports nothing, and a `running` note that is never superseded
carries a FRESH checked_at, so the collector counted as OK while losing whole
runs. That is why the clock matters more than the coverage it defers: a
deferred sweep stays a ledger slot the next run retries, but a dead run leaves
a lie on the health page.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import cron  # noqa: E402

CRON_SRC = (Path(__file__).resolve().parents[1] / "cron.py").read_text(encoding="utf-8")


class BudgetIsClamped(unittest.TestCase):
    def test_default_is_inside_the_clamp(self):
        self.assertEqual(cron._gdelt_run_budget_seconds(), 900)

    def test_an_absurd_budget_is_clamped_not_honoured(self):
        self.assertEqual(cron._gdelt_run_budget_seconds("999999"), 3600)
        self.assertEqual(cron._gdelt_run_budget_seconds("1"), 120)

    def test_a_junk_budget_falls_back_rather_than_raising(self):
        # An operator typo must not take the whole daily run down.
        for junk in ("", "abc", None if False else "12.5"):
            self.assertEqual(cron._gdelt_run_budget_seconds(junk), 900)


class TheDailyCollectorPassesADeadline(unittest.TestCase):
    def test_cron_passes_a_deadline_to_pull_gdelt_between(self):
        """Mutation target: drop the deadline= kwarg and this fails.

        Read from the source rather than by calling, because calling would
        make a live request. The assertion is on the CALL, which is the thing
        that regressed for months while the parameter existed.
        """
        tree = ast.parse(CRON_SRC)
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "pull_gdelt_between"
        ]
        self.assertTrue(calls, "cron.py no longer calls pull_gdelt_between")
        for call in calls:
            self.assertIn(
                "deadline", [kw.arg for kw in call.keywords],
                "the daily gdelt collector must pass a deadline; running it "
                "unbounded is what killed the runs of 2026-08-19/26/27")

    def test_the_deadline_is_derived_from_the_clamped_budget(self):
        self.assertIn("_gdelt_run_budget_seconds()", CRON_SRC)
        self.assertIn("time.monotonic()", CRON_SRC)


if __name__ == "__main__":
    unittest.main()
