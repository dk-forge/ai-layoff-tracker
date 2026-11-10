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


class ExtraEvidenceTests(unittest.TestCase):
    """--extra-urls: a session that found more reports hands them to the referees."""

    def test_extra_sources_are_labelled_and_appended(self):
        pages = {"https://a/arch": "cited text", "https://x/1": "one", "https://x/2": ""}
        with mock.patch.object(adj, "fetch_evidence", side_effect=lambda u, *a, **k: pages.get(u, "")):
            text, read = adj.gather_evidence({"archived_url": "https://a/arch"},
                                             ["https://x/1", "https://x/2"])
        self.assertIn("cited text", text)
        self.assertIn("ADDITIONAL SOURCE https://x/1", text)
        self.assertIn("one", text)
        self.assertNotIn("https://x/2", text, "an unreadable page is not presented as evidence")
        self.assertEqual(read, ["https://a/arch", "https://x/1"])

    def test_no_extra_keeps_the_old_behaviour(self):
        with mock.patch.object(adj, "fetch_evidence", side_effect=lambda u, *a, **k: "t" if u == "https://s" else ""):
            text, read = adj.gather_evidence({"archived_url": "", "source_url": "https://s"}, [])
        self.assertEqual(text, "t")
        self.assertEqual(read, ["https://s"])

    def test_the_cap_still_holds(self):
        with mock.patch.object(adj, "fetch_evidence", return_value="z" * adj.EVIDENCE_CAP):
            text, _ = adj.gather_evidence({"archived_url": "https://a"}, ["https://b", "https://c"])
        self.assertLessEqual(len(text), adj.EVIDENCE_CAP * 2)


class PromptDateTests(unittest.TestCase):
    """2026-11-10: a referee called a 2026-10-23 row "in the future" because the
    prompt never said what day it is (runs 42882097733, 42882103025)."""

    def test_prompt_states_today(self):
        prompt = adj.build_prompt({"id": 1}, "text", today="2026-11-10")
        self.assertIn("Today is 2026-11-10", prompt)


class DuplicateOfTests(unittest.TestCase):
    """--duplicate-of: the question is whether THE ROW re-reports another row's event."""

    def test_prompt_shows_the_other_row_and_asks_the_duplicate_question(self):
        prompt = adj.build_prompt({"id": 183025}, "text", today="2026-11-10",
                                  other={"id": 183026, "company_name": "Volvo Cars"})
        self.assertIn("THE OTHER ROW", prompt)
        self.assertIn("183026", prompt)
        self.assertIn("same_event_as_other_row", prompt)

    def test_no_other_row_keeps_the_old_question(self):
        prompt = adj.build_prompt({"id": 1}, "text", today="2026-11-10")
        self.assertNotIn("THE OTHER ROW", prompt)

    def test_duplicate_trash_moves_the_source_to_the_keeper_first(self):
        calls = []

        def fake_main():
            calls.append(list(sys.argv))
            return 0

        with mock.patch.object(adj.apply_correction, "main", fake_main):
            rc = adj.apply_duplicate({"id": 183025, "company_name": "Volvo",
                                      "source_url": "https://bi/x"},
                                     {"id": 183026}, "two-model: dup", apply=False)
        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][calls[0].index("--action") + 1], "move-sources")
        fields = json.loads(calls[0][calls[0].index("--fields") + 1])
        self.assertEqual(fields, {"to_id": 183026, "urls": ["https://bi/x"]})
        self.assertEqual(calls[1][calls[1].index("--action") + 1], "trash")
        self.assertEqual(calls[1][calls[1].index("--ids") + 1], "183025")

    def test_failed_move_never_trashes(self):
        calls = []

        def fake_main():
            calls.append(list(sys.argv))
            return 1

        with mock.patch.object(adj.apply_correction, "main", fake_main):
            rc = adj.apply_duplicate({"id": 2, "source_url": "u"}, {"id": 3}, "r", apply=True)
        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), 1)


class DuplicateAgreementTests(unittest.TestCase):
    def test_both_must_say_same_event(self):
        yes = dict(_v("trash"), same_event_as_other_row=True)
        no = dict(_v("trash"), same_event_as_other_row=False)
        self.assertTrue(adj.duplicate_agreed({A: yes, B: yes}))
        self.assertFalse(adj.duplicate_agreed({A: yes, B: no}))
        self.assertFalse(adj.duplicate_agreed({A: yes, B: None}))
