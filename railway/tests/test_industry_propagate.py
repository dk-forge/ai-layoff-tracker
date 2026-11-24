"""Propagation decisions with synthetic rows and no writes or HTTP."""
from collections import Counter
import unittest
from unittest.mock import patch
from railway import industry_propagate as worker


class PropagationDecisions(unittest.TestCase):
    def run_worker(self, tagged, blanks, *, dry=False, cap=5000):
        with patch.object(worker, "scan", return_value=(tagged, blanks)), patch.object(worker, "_post", return_value={"filled": []}) as post, patch.object(worker, "KEY", "fixture-only"), patch.object(worker, "DRY", dry), patch.object(worker, "MAX_WRITE", cap), patch("builtins.print"):
            self.assertEqual(worker.main(), 0)
            return post.call_args_list

    def test_majority_threshold_and_unknown_employers(self):
        calls = self.run_worker({"accepted": Counter({"Software": 3, "Other": 1}), "mixed": Counter({"Software": 2, "Other": 1})}, [(1, "accepted"), (2, "mixed"), (3, "unknown")])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args, ("industry-backfill", {"items": [{"id": 1, "industry": "Software"}]}))

    def test_dry_run_never_posts(self):
        self.assertEqual(self.run_worker({"example": Counter({"Software": 1})}, [(1, "example")], dry=True), [])

    def test_caps_rows_and_batches_at_two_hundred(self):
        calls = self.run_worker({"example": Counter({"Software": 1})}, [(i, "example") for i in range(450)], cap=401)
        batches = [c.args[1]["items"] for c in calls]
        self.assertEqual([len(batch) for batch in batches], [200, 200, 1])
        self.assertEqual([r["id"] for batch in batches for r in batch], list(range(401)))
