"""Planning helpers and fetch failure handling with no news requests."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_news_dryrun as planner


class LocalNewsPlanning(unittest.TestCase):
    def test_iterates_list_and_nested_mapping_records_only(self):
        row = {"fixture": 1}
        self.assertEqual(list(planner._iter_entries([row, None, "wrong"])), [row])
        self.assertEqual(list(planner._iter_entries({"one": row, "two": [row, None], "bad": 2})), [row, row])
        self.assertEqual(list(planner._iter_entries(None)), [])

    def test_numbers_are_coerced_and_missing_or_invalid_are_zero(self):
        self.assertEqual(planner._num("1.25"), 1.25)
        for value in [None, "", "wrong", {}]:
            self.assertEqual(planner._num(value), 0.0)

    def test_cost_uses_the_last_valid_synthetic_source_breakdown(self):
        data = [{"by_source": {"google_news": {"cost": 1, "items": 5}}}, {"sources": {"google_news": {"usd": 2, "candidates": 20}}}]
        with patch.object(planner.Path, "read_text", return_value=json.dumps(data)):
            cost, basis = planner._measured_cost_per_item()
        self.assertEqual(cost, 0.1)
        self.assertIn("20 candidates", basis)

    def test_unreadable_or_empty_cost_ledger_names_the_fallback(self):
        for content in ["not JSON", "{}", "[]"]:
            with patch.object(planner.Path, "read_text", return_value=content):
                cost, basis = planner._measured_cost_per_item()
            self.assertEqual(cost, planner.FALLBACK_COST_PER_ITEM)
            self.assertIn("fallback", basis)

    def test_offline_plan_does_not_pull_news(self):
        market = SimpleNamespace(tier=1, editions=[SimpleNamespace(queries=["fixture"])], anchors=[], publishers=[])
        with patch.dict(planner.mk.BY_COUNTRY, {"Fixtureland": market}), patch.object(planner.ln, "pull_local_news") as pull, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(planner.run(["Fixtureland"], offline=True, cost_per_item=0.1), 0)
        pull.assert_not_called()
        self.assertIn("OFFLINE plan", out.getvalue())
        self.assertIn("Fixtureland", out.getvalue())

    def test_network_failure_is_wrapped_without_a_real_connection(self):
        with patch.object(planner.blog_reads, "urlopen", side_effect=OSError("fixture offline")):
            with self.assertRaisesRegex(RuntimeError, "OSError: fixture offline"):
                planner._fetch("https://example.invalid/feed")
