"""Guards for the extraction A/B scorer.

The scorer decides whether a model swap ships. Three ways it could quietly lie,
each pinned here: charging a model for a window defect, counting a failed call
as a miss, and counting a posted-but-wrong number as a success.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ab_extraction_models import score

MODELS = ("incumbent/a", "candidate/b")


def _row(gold_in_window, per_model):
    return {"filer": "X", "gold_count": 100,
            "gold_count_in_window": gold_in_window, "by_model": per_model}


def _accepted(correct, cost=0.001):
    return {"verdict": "accepted", "stage": "accepted", "count": 100 if correct else 7,
            "count_matches_gold": correct,
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": cost}}


def _dropped(stage="count_not_verbatim_in_window"):
    return {"verdict": "dropped", "stage": stage,
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.001}}


def _unknown(stage="llm_error"):
    return {"verdict": "unknown", "stage": stage}


class ScorerTests(unittest.TestCase):
    def test_item_whose_gold_count_never_entered_the_window_is_not_a_model_miss(self):
        rows = [
            _row(True, {"incumbent/a": _accepted(True), "candidate/b": _accepted(True)}),
            _row(False, {"incumbent/a": _dropped(), "candidate/b": _dropped()}),
        ]
        s = score(rows, MODELS)
        for m in MODELS:
            self.assertEqual(s[m]["scorable"], 1)
            self.assertEqual(s[m]["accepted"], 1)
            self.assertEqual(s[m]["correct"], 1)

    def test_excluded_item_still_bills_its_tokens(self):
        rows = [_row(False, {"incumbent/a": _dropped(), "candidate/b": _dropped()})]
        s = score(rows, MODELS)
        self.assertEqual(s["incumbent/a"]["calls"], 1)
        self.assertAlmostEqual(s["incumbent/a"]["cost"], 0.001)

    def test_a_failed_call_is_unknown_and_never_a_miss(self):
        rows = [_row(True, {"incumbent/a": _accepted(True), "candidate/b": _unknown()})]
        s = score(rows, MODELS)
        self.assertEqual(s["candidate/b"]["unknown"], 1)
        self.assertEqual(s["candidate/b"]["accepted"], 0)
        self.assertEqual(s["candidate/b"]["correct"], 0)
        self.assertEqual(s["candidate/b"]["wrong_count"], 0)

    def test_a_posted_but_wrong_count_is_not_scored_as_correct(self):
        rows = [_row(True, {"incumbent/a": _accepted(True),
                            "candidate/b": _accepted(False)})]
        s = score(rows, MODELS)
        self.assertEqual(s["candidate/b"]["accepted"], 1)
        self.assertEqual(s["candidate/b"]["correct"], 0)
        self.assertEqual(s["candidate/b"]["wrong_count"], 1)

    def test_a_budget_stop_is_unknown_not_a_model_failure(self):
        rows = [_row(True, {"incumbent/a": _accepted(True),
                            "candidate/b": _unknown("budget_stop")})]
        s = score(rows, MODELS)
        self.assertEqual(s["candidate/b"]["unknown"], 1)
        self.assertEqual(s["candidate/b"]["wrong_count"], 0)
        self.assertNotIn("budget_stop", s["candidate/b"]["stages"])

    def test_stage_tally_covers_known_verdicts_only(self):
        rows = [
            _row(True, {"incumbent/a": _dropped("model_said_not_a_layoff_event"),
                        "candidate/b": _unknown()}),
            _row(True, {"incumbent/a": _dropped("model_said_not_a_layoff_event"),
                        "candidate/b": _accepted(True)}),
        ]
        s = score(rows, MODELS)
        self.assertEqual(s["incumbent/a"]["stages"],
                         {"model_said_not_a_layoff_event": 2})
        self.assertEqual(s["candidate/b"]["stages"], {"accepted": 1})


if __name__ == "__main__":
    unittest.main()
