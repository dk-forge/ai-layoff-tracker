"""Evaluation bookkeeping only: no model client is imported or called."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_haiku55 as evaluation


class EvaluationBookkeeping(unittest.TestCase):
    def test_strata_are_interleaved_without_mutating_the_input(self):
        items = [{"stratum": "b", "id": 1}, {"stratum": "a", "id": 2}, {"stratum": "a", "id": 3}]
        self.assertEqual([r["id"] for r in evaluation.stratified(items, 3)], [2, 1, 3])
        self.assertEqual([r["id"] for r in items], [1, 2, 3])

    def test_empty_sample_zero_limit_and_missing_stratum(self):
        self.assertEqual(evaluation.stratified([], 3), [])
        self.assertEqual(evaluation.stratified([{"stratum": "a"}], 0), [])
        with self.assertRaises(KeyError):
            evaluation.stratified([{}], 1)

    def test_usage_accepts_mapping_or_object_and_defaults_missing_counters(self):
        self.assertEqual(evaluation._cost(SimpleNamespace()), (0.0, 0, 0))
        usage = {"cost": "0.05", "prompt_tokens": "8", "completion_tokens": 2}
        self.assertEqual(evaluation._cost(SimpleNamespace(usage=usage)), (0.05, 8, 2))
        self.assertEqual(evaluation._cost(SimpleNamespace(usage=SimpleNamespace(**usage))), (0.05, 8, 2))

    def test_confusion_counts_and_unmade_calls_remain_distinct(self):
        counts = evaluation.tally()
        evaluation.add(counts, True, True, 0.0, True, None)
        evaluation.add(counts, True, False, 0.0, True, None)
        evaluation.add(counts, False, True, 0.0, False, "budget_stop")
        self.assertEqual((counts["n"], counts["json_ok"], counts["tp"], counts["fp"], counts["errors"], counts["calls"]), (3, 2, 1, 1, 1, 2))

    def test_summary_handles_no_judgments_and_reports_scored_accuracy(self):
        self.assertIn("acc=0.0% (0/0)", evaluation.summary(evaluation.tally()))
        counts = evaluation.tally()
        evaluation.add(counts, True, True, 0.0, True, None)
        self.assertIn("acc=100.0% (1/1)", evaluation.summary(counts))
        self.assertIn("json_ok=1/1 errors=0", evaluation.summary(counts))

    def test_load_keeps_only_explicit_boolean_gold_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            sample, gold = Path(directory) / "sample.json", Path(directory) / "gold.json"
            sample.write_text(json.dumps({"items": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]}))
            gold.write_text(json.dumps({"labels": {"1": True, "2": False, "3": None}}))
            with patch.object(evaluation, "SAMPLE", sample), patch.object(evaluation, "GOLD", gold):
                self.assertEqual(evaluation.load_items(), [{"id": 1, "gold": True}, {"id": 2, "gold": False}])
