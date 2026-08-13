"""Offline guards for the UK reference set.

Three properties, each of which the US set learned the hard way and none of
which is allowed to be re-derived here:

  1. the matching rule is IMPORTED, not copied — one definition of
     "does this row represent this event", so the Xperi/Experian prefix bug
     cannot come back in a second place
  2. a machine cannot promote its own recall: a row that satisfies alias+window
     for a NOT-matched event lands in `candidates_needing_adjudication` and is
     never counted
  3. missing / stale / unreachable resolve to UNKNOWN, never to a pass — and so
     does "no floor has been armed yet", because a floor invented by the same
     run that produced the number is a rubber stamp

No network, no keys.
"""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import recall_goldset
import recall_uk_goldset
from recall_uk_goldset import FAIL, PASS, UNKNOWN

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (REPO_ROOT / "docs" / "recall-reference-sets"
            / "uk-hansard-2024-07_2026-06.goldset.json")


def _stamp(days_ago=0):
    return (datetime.now(timezone.utc)
            - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _measurement(matched=6, total=50, unreachable=0, days_ago=0, floor=None):
    return {"reference_events": total, "matched": matched, "missed": total - matched,
            "unreachable": unreachable, "measured_at": _stamp(days_ago),
            "matched_floor": floor, "lost_since_adjudication": [],
            "missed_events": [], "candidates_needing_adjudication": []}


class OneDefinitionTests(unittest.TestCase):
    """The discipline is shared with the US set by IMPORT, not by copy."""

    def test_the_matching_rule_is_the_same_object(self):
        self.assertIs(recall_uk_goldset.match_event, recall_goldset.match_event)
        self.assertIs(recall_uk_goldset.format_interval, recall_goldset.format_interval)
        self.assertIs(recall_uk_goldset.wilson, recall_goldset.wilson)

    def test_no_second_copy_of_the_prefix_matcher(self):
        source = (Path(recall_uk_goldset.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("def name_matches", source,
                         "the prefix matcher must be imported, never re-typed")
        self.assertNotIn("def wilson", source)


class JudgeTests(unittest.TestCase):
    def test_no_floor_is_unknown_not_pass(self):
        state, detail = recall_uk_goldset.judge(_measurement(floor=None))
        self.assertEqual(state, UNKNOWN)
        self.assertIn("No floor is armed", detail)

    def test_an_armed_floor_can_fail(self):
        state, _ = recall_uk_goldset.judge(_measurement(matched=3, floor=6))
        self.assertEqual(state, FAIL)

    def test_an_armed_floor_can_pass(self):
        state, _ = recall_uk_goldset.judge(_measurement(matched=8, floor=6))
        self.assertEqual(state, PASS)

    def test_a_missing_measurement_is_unknown(self):
        self.assertEqual(recall_uk_goldset.judge(None)[0], UNKNOWN)

    def test_a_stale_measurement_is_unknown(self):
        state, _ = recall_uk_goldset.judge(_measurement(days_ago=30, floor=6))
        self.assertEqual(state, UNKNOWN)

    def test_an_outage_is_unknown_not_a_regression(self):
        # 10% of 50 is 5; six unreachable must not be reported as five misses.
        state, detail = recall_uk_goldset.judge(
            _measurement(matched=1, unreachable=6, floor=6))
        self.assertEqual(state, UNKNOWN)
        self.assertIn("NOT a regression", detail)


class ManifestTests(unittest.TestCase):
    """The committed manifest has to keep the promises the doc makes for it."""

    @classmethod
    def setUpClass(cls):
        if not MANIFEST.exists():
            raise unittest.SkipTest("UK manifest not committed yet")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_it_is_never_published_to_the_public_endpoint(self):
        self.assertIn("not_published", self.manifest["publication_status"])

    def test_one_country_and_one_closed_period(self):
        self.assertEqual(self.manifest["country"], "United Kingdom")
        period = self.manifest["period"]
        self.assertLess(period["from"], period["to"])

    def test_every_event_carries_its_original_publisher(self):
        for event in self.manifest["reference_events"]:
            self.assertTrue(event.get("official_source_url", "").startswith("http"),
                            f"{event['reference_row_id']} has no primary citation")
            self.assertTrue(event.get("count_evidence"),
                            f"{event['reference_row_id']} has no verbatim count sentence")
            self.assertIsInstance(event.get("stated_job_count"), int)

    def test_no_event_is_cited_to_an_aggregator_or_to_ourselves(self):
        banned = ("asktherecruiter.com", "news.google.com", "gdelt")
        for event in self.manifest["reference_events"]:
            url = event["official_source_url"].lower()
            for token in banned:
                self.assertNotIn(token, url,
                                 f"{event['reference_row_id']} cites {token}")

    def test_the_enumeration_frame_is_not_one_of_our_sources(self):
        frame = json.dumps(self.manifest.get("how_it_was_assembled", "")).lower()
        for ours in ("gdelt", "google news", "eurofound", "newsapi"):
            self.assertNotIn(ours, frame,
                             "the frame must be independent of our collection")

    def test_every_event_has_a_decision(self):
        for event in self.manifest["reference_events"]:
            self.assertIn(event.get("match_decision"),
                          ("matched", "not_matched", "undecided"))


if __name__ == "__main__":
    unittest.main()
