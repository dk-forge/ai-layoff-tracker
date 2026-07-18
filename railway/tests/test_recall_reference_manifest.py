"""Guard against publishing an empty recall-reference template as a result."""
import json
import unittest
from pathlib import Path


class RecallReferenceManifestTests(unittest.TestCase):
    def test_california_template_is_not_a_published_measurement(self):
        path = Path(__file__).resolve().parents[2] / "docs" / "recall-reference-sets" / "ca-us-2026-06.template.json"
        template = json.loads(path.read_text())
        self.assertEqual(template["publication_status"], "template_only_not_a_benchmark")
        self.assertEqual(template["country"], "United States")
        self.assertEqual(template["reference_events"], [])
        self.assertNotIn("sample_recall", template)
        self.assertNotIn("matched_events", template)

    def test_california_draft_has_source_citations_but_no_measurement(self):
        path = Path(__file__).resolve().parents[2] / "docs" / "recall-reference-sets" / "ca-us-2026-06.warn-draft.json"
        draft = json.loads(path.read_text())
        # The transcription review completed 2026-07-18; matching and
        # publication review remain open, so this is still not a measurement.
        self.assertEqual(draft["publication_status"],
                         "transcription_reviewed_pending_match_and_publication_review")
        self.assertEqual(len(draft["reference_events"]), 12)
        self.assertRegex(draft["reference_set"]["document_sha256"], r"^[a-f0-9]{64}$")
        self.assertNotIn("sample_recall", draft)
        self.assertNotIn("matched_events", draft)
        for event in draft["reference_events"]:
            self.assertIn("PDF text page marker", event["official_document_location"])
            self.assertEqual(event["match_decision"], "pending_independent_tracker_lookup")
            self.assertIsNone(event["canonical_event_id_or_null"])

    def test_california_candidate_has_an_explicit_publication_blocker(self):
        path = Path(__file__).resolve().parents[2] / "docs" / "recall-reference-sets" / "CA_US_2026_06_PUBLICATION_CHECKLIST.md"
        checklist = path.read_text()
        self.assertIn("blocked — no recall metric may be posted yet", checklist)
        self.assertIn("second editor", checklist)
        self.assertIn("Every reference row receives exactly one", checklist)
        self.assertIn("not a completeness or accuracy measure", checklist)


if __name__ == "__main__":
    unittest.main()
