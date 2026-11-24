"""The human review sheet stays undecided; public API reads are fake."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recall_uk_adjudication_pack as pack


class AdjudicationPack(unittest.TestCase):
    def test_empty_aliases_do_not_open_a_connection(self):
        with patch.object(pack.blog_reads, "urlopen") as get:
            self.assertEqual(pack._rows_for(None), {})
        get.assert_not_called()

    def test_alias_queries_merge_by_event_id_and_keep_first_evidence(self):
        responses = [io.BytesIO(json.dumps({"data": [{"event_id": 7, "company_name": "First"}]}).encode()), io.BytesIO(json.dumps({"data": [{"event_id": 7, "company_name": "Later"}, {"event_id": 8}]}).encode())]
        with patch.object(pack.blog_reads, "urlopen", side_effect=responses) as get:
            rows = pack._rows_for(["Example One", "Example Alias"])
        self.assertEqual(set(rows), {7, 8})
        self.assertEqual(rows[7]["company_name"], "First")
        self.assertIn("company=Example+One", get.call_args_list[0].args[0].full_url)
        self.assertEqual(get.call_args.kwargs["timeout"], 30)

    def test_lookup_failure_is_visible_as_an_error(self):
        with patch.object(pack.blog_reads, "urlopen", side_effect=OSError("fixture offline")):
            self.assertIn("OSError: fixture offline", pack._rows_for(["Example"])["_error"]["_error"])

    def test_empty_measurement_has_no_prefilled_decision(self):
        with patch.object(pack, "_rows_for") as get:
            text = pack.build({"reference_events": []}, {})
        get.assert_not_called()
        self.assertIn("nothing to adjudicate", text)
        self.assertNotIn("**Decision:**", text)

    def test_candidate_sheet_quotes_only_its_requested_row_and_leaves_the_ruling_blank(self):
        event = {"reference_row_id": "fixture", "employer": "Example", "announcement_date": "2026-01-01", "stated_job_count": 3, "count_evidence": "Synthetic count evidence", "publisher": "Fixture source", "citation_type": "primary", "official_source_url": "https://example.invalid/report", "match_window": "fixture", "employer_aliases": ["Example"]}
        with patch.object(pack, "_rows_for", return_value={7: {"company_name": "Example", "job_count": 3}, 8: {"company_name": "Unrequested"}}):
            text = pack.build({"reference_events": [event]}, {"candidates_needing_adjudication": [{"id": "fixture", "new_tracker_event_ids": [7, 9]}]})
        self.assertIn("Synthetic count evidence", text)
        self.assertNotIn("Unrequested", text)
        self.assertIn("not returned by /query", text)
        self.assertIn("**Decision:** _____________", text)
