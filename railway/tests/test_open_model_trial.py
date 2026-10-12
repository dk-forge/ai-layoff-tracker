"""The open-model trial scores honestly and stays a dispatch-only experiment."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import open_model_trial as t  # noqa: E402

WF = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "open-model-trial.yml"


class Scoring(unittest.TestCase):
    def test_unparseable_answer_counts_as_wrong_not_dropped(self):
        res = t.scores([(True, True), (None, True), (False, False), (None, False)])
        self.assertEqual(res["n"], 4)
        self.assertEqual(res["json_ok"], 2)
        self.assertAlmostEqual(res["acc"], 0.5)
        self.assertAlmostEqual(res[True]["r"], 0.5)

    def test_gold_set_loads_with_truth_and_paid_answer(self):
        items = t.load_items()
        self.assertEqual(len(items), 200)
        self.assertTrue(all(isinstance(i["truth"], bool) for i in items))
        # The paid baseline is the production guard applied to frozen answers.
        self.assertGreater(t.scores([(i["paid"], i["truth"]) for i in items])["acc"], 0.8)

    def test_order_is_stratified_so_a_cut_short_run_holds_positives(self):
        head = t.ordered(t.load_items())[:30]
        self.assertEqual(len({i["stratum"] for i in head}), 3)


class WorkflowIsAnExperiment(unittest.TestCase):
    def test_dispatch_only_no_secrets_box2(self):
        text = WF.read_text(encoding="utf-8")
        self.assertNotIn("schedule:", text)
        self.assertNotIn("secrets.", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("runs-on: [self-hosted, box2]", text)
        self.assertIn("permissions: {}", text)

    def test_the_only_model_endpoint_is_loopback(self):
        """Why it is exempt from the metered_call sweep: it never reaches a paid API."""
        src = Path(t.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Authorization", src)
        self.assertIn('f"http://127.0.0.1:{port}/v1/chat/completions"', src)
        self.assertNotIn("OPENROUTER_API_KEY", WF.read_text(encoding="utf-8"))

    def test_models_are_hash_pinned(self):
        for m in t.MODELS.values():
            self.assertEqual(len(m["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
