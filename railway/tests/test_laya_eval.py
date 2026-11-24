"""Evaluation input/report tests replace the classifier and all source data."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import laya_eval as evaluation


class LocalEvaluation(unittest.TestCase):
    def fixture(self, root):
        (root / "ai-causation-2026-08.goldset.json").write_text(json.dumps({"labels": {"1": True, "2": False, "3": None}}))
        (root / "ai-causation-2026-08.sample.json").write_text(json.dumps({"items": [
            {"id": 1, "company_name": "Example One", "source_url": "https://example.invalid/one", "text": "Synthetic positive"},
            {"id": 2, "company_name": "Example Two", "text": ""}, {"id": 3}, {"id": 4}]}))

    def test_loads_only_adjudicated_rows_with_their_original_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            with patch.object(evaluation, "REF", root):
                rows = evaluation.load_items(10)
        self.assertEqual([r[2] for r in rows], [True, False])
        self.assertEqual(rows[0][1], "Synthetic positive")
        self.assertEqual(rows[1][1], "")

    def test_limit_and_zero_are_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            with patch.object(evaluation, "REF", root):
                self.assertEqual(len(evaluation.load_items(1)), 1)
                self.assertEqual(evaluation.load_items(0), [])

    def test_missing_input_is_not_treated_as_an_empty_gold_set(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(evaluation, "REF", Path(directory)):
            with self.assertRaises(FileNotFoundError):
                evaluation.load_items(1)

    def run_main(self, items, predict):
        router = Mock(predict=predict)
        with patch.object(evaluation, "load_items", return_value=items), patch.object(evaluation, "peak_rss_mb", return_value=12), patch.dict(sys.modules, {"laya": SimpleNamespace(Router=Mock(return_value=router))}), patch.dict(os.environ, {"LAYA_LIMIT": "10"}, clear=True), contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            result = evaluation.main()
        return result, out.getvalue(), router

    def test_reports_agreement_using_the_mock_classifier(self):
        predict = Mock(side_effect=[{"answers": {"ai_cause": {"noul": 0.5}}}, {"answers": {"ai_cause": {"noul": 0.2}}}])
        result, text, router = self.run_main([("Fixture One", "one", True), ("Fixture Two", "two", False)], predict)
        self.assertEqual(result, 0)
        self.assertIn("100.0%", text)
        self.assertEqual(router.predict.call_count, 2)
        router.predict.assert_any_call("one", evaluation.QUESTION)

    def test_all_failed_predictions_report_unknown_agreement_and_fail(self):
        result, text, _ = self.run_main([("Fixture", "synthetic", True)], Mock(side_effect=ValueError("fixture failure")))
        self.assertEqual(result, 1)
        self.assertIn("0 (errors 1)", text)
        self.assertIn("agreement | n/a", text)
