"""Probe classification uses fake tracker and discovery answers only."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uk_recall_probe as probe

EVENT = {"employer_aliases": ["Example"], "match_window": ["2026-01-01", "2026-03-01"], "announcement_date": "2026-02-01"}


class RecallProbeClassification(unittest.TestCase):
    def test_domain_normalisation_and_missing_value(self):
        self.assertEqual(probe._domain({"domain": "EXAMPLE.INVALID"}), "example.invalid")
        self.assertEqual(probe._domain({}), "")

    def test_known_tracker_row_finishes_before_any_lookup(self):
        rows = [{"event_id": 1, "company": "Example"}]
        with patch.object(probe, "_loose_tracker_probe") as loose, patch.object(probe, "_gdelt") as gdelt:
            result = probe.classify(EVENT, lambda _: False, None, tracker_rows=rows)
        self.assertEqual(result, {"stage": probe.STORED_UNMATCHED, "tracker_rows": rows})
        loose.assert_not_called(); gdelt.assert_not_called()

    def test_unreadable_tracker_is_unknown_not_missing(self):
        with patch.object(probe, "_loose_tracker_probe", return_value=None), patch.object(probe, "_gdelt") as gdelt:
            result = probe.classify(EVENT, lambda _: False, None)
        self.assertEqual(result["stage"], probe.UNKNOWN)
        self.assertIn("could not be read", result["why"])
        gdelt.assert_not_called()

    def test_intentionally_unrun_discovery_does_not_claim_no_source(self):
        with patch.object(probe, "_loose_tracker_probe", return_value=[]), patch.object(probe, "_gdelt") as gdelt:
            result = probe.classify(EVENT, lambda _: False, None, skip_gdelt=True)
        self.assertEqual(result["stage"], probe.UNKNOWN)
        self.assertIn("UNMEASURED", result["why"])
        gdelt.assert_not_called()

    def test_empty_discovery_and_failed_discovery_have_distinct_verdicts(self):
        with patch.object(probe, "_loose_tracker_probe", return_value=[]), patch.object(probe, "_gdelt", return_value=([], None)):
            self.assertEqual(probe.classify(EVENT, lambda _: False, None)["stage"], probe.NO_SOURCE)
        with patch.object(probe, "_loose_tracker_probe", return_value=[]), patch.object(probe, "_gdelt", return_value=(None, "fixture offline")):
            result = probe.classify(EVENT, lambda _: False, None)
        self.assertEqual(result["stage"], probe.UNKNOWN)
        self.assertIn("fixture offline", result["why"])
