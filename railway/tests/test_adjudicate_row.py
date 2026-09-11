"""Two-referee adjudication (railway/adjudicate_row.py): the decision rule.

Hermetic: no network, no key, no spend. The paid calls are behind
``ask_referee``; these tests exercise ``decide``, the evidence reader's
failure path and the apply path's argument shape, which is where a wrong
correction would come from.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import adjudicate_row as adj  # noqa: E402

A, B = adj.REFEREES


def _v(action, fields=None, conf=90):
    return {"event_is_new_on_layoff_date": action == "keep",
            "count_supported_by_source": action == "keep",
            "employer_attributed_to_ai": False,
            "recommended_action": action, "edit_fields": fields,
            "confidence": conf, "reasoning": "x"}


class DecideTests(unittest.TestCase):
    def test_agreement_on_trash_applies(self):
        self.assertEqual(adj.decide({A: _v("trash"), B: _v("trash")}), ("agree", "trash", None))

    def test_agreement_on_keep_changes_nothing(self):
        self.assertEqual(adj.decide({A: _v("keep"), B: _v("keep")}), ("agree", "keep", None))

    def test_disagreement_is_left_for_a_human(self):
        self.assertEqual(adj.decide({A: _v("trash"), B: _v("keep")}), ("disagree", "keep", None))

    def test_edit_needs_identical_fields(self):
        same = adj.decide({A: _v("edit", {"layoff_date": "2025-10-28"}),
                           B: _v("edit", {"layoff_date": "2025-10-28"})})
        self.assertEqual(same, ("agree", "edit", {"layoff_date": "2025-10-28"}))
        diff = adj.decide({A: _v("edit", {"layoff_date": "2025-10-28"}),
                           B: _v("edit", {"job_count": 16000})})
        self.assertEqual(diff[0], "disagree")

    def test_one_referee_failing_is_unknown_not_a_verdict(self):
        self.assertEqual(adj.decide({A: _v("trash"), B: None})[0], "unknown")
        self.assertEqual(adj.decide({A: None, B: None})[0], "unknown")


class EvidenceTests(unittest.TestCase):
    def test_unreadable_page_is_empty_never_raises(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertEqual(adj.fetch_evidence("https://example.invalid/x"), "")

    def test_blank_url_is_empty(self):
        self.assertEqual(adj.fetch_evidence(""), "")


class ApplyPathTests(unittest.TestCase):
    def test_apply_goes_through_apply_correction_with_the_row_id_and_reason(self):
        seen = {}

        def fake_main():
            seen["argv"] = list(sys.argv)
            return 0

        with mock.patch.object(adj.apply_correction, "main", fake_main):
            rc = adj.apply_via_machinery({"id": 179276, "company_name": "Amazon"},
                                         "trash", None, "two-model adjudication: x", apply=False)
        self.assertEqual(rc, 0)
        argv = seen["argv"]
        self.assertIn("--ids", argv)
        self.assertEqual(argv[argv.index("--ids") + 1], "179276")
        self.assertEqual(argv[argv.index("--action") + 1], "trash")
        self.assertNotIn("--apply", argv)

    def test_spec_file_records_both_verdicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(adj, "SPEC_DIR", tmp):
                path = adj.write_spec(1, "disagree", {A: _v("trash"), B: _v("keep")}, {"cost_usd": 0.01})
            data = json.load(open(path, encoding="utf-8"))
        self.assertEqual(data["status"], "disagree")
        self.assertEqual(set(data["verdicts"]), {A, B})


if __name__ == "__main__":
    unittest.main()
