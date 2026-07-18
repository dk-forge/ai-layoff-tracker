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
        # Transcription review, matching pass and publication review all
        # completed 2026-07-18 by three distinct actors. The manifest is ready
        # to retain, but it still records no recall measurement itself: the
        # numerator/denominator are posted to the keyed endpoint, which
        # computes and labels sample_recall.
        self.assertEqual(draft["publication_status"],
                         "publication_reviewed_ready_to_retain")
        self.assertEqual(draft["reference_basis"], "independent_manual_sample")
        self.assertEqual(len(draft["reference_events"]), 12)
        self.assertRegex(draft["reference_set"]["document_sha256"], r"^[a-f0-9]{64}$")
        self.assertNotIn("sample_recall", draft)
        self.assertNotIn("matched_events", draft)
        matched, unmatched = 0, 0
        for event in draft["reference_events"]:
            self.assertIn("PDF text page marker", event["official_document_location"])
            self.assertIn(event["match_decision"],
                          ("matched_canonical_event", "no_matching_tracker_event"))
            self.assertTrue(event["matching_evidence"])
            if event["match_decision"] == "matched_canonical_event":
                matched += 1
                self.assertIsInstance(event["canonical_event_id_or_null"], int)
            else:
                unmatched += 1
                self.assertIsNone(event["canonical_event_id_or_null"])
        # The reviewed sample retains its no-match row; matched IDs are unique
        # (canonical dedup means one event cannot satisfy two reference rows).
        self.assertEqual((matched, unmatched), (11, 1))
        ids = [e["canonical_event_id_or_null"] for e in draft["reference_events"]
               if e["match_decision"] == "matched_canonical_event"]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("publication_review", draft)

    def test_california_candidate_has_an_explicit_publication_blocker(self):
        path = Path(__file__).resolve().parents[2] / "docs" / "recall-reference-sets" / "CA_US_2026_06_PUBLICATION_CHECKLIST.md"
        checklist = path.read_text()
        self.assertIn("blocked — no recall metric may be posted yet", checklist)
        self.assertIn("second editor", checklist)
        self.assertIn("Every reference row receives exactly one", checklist)
        self.assertIn("not a completeness or accuracy measure", checklist)


if __name__ == "__main__":
    unittest.main()
