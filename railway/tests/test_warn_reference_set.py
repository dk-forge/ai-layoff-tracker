"""Offline guards for the US WARN reference set.

Three things this set must never do, each of which it could do silently:

  1. move the published SEC Item 2.05 figure — a second reference set is
     ADDITIVE, and the moment it can write recall_measurement.json or
     MATCHED_FLOOR the 53/57 the owner adjudicated is no longer the owner's;
  2. promote its own recall — every candidate must arrive `not_matched`, so the
     numerator counts only what an editor confirmed;
  3. score a query that was never sent as a miss — the defect that cost this
     set seven points on its first run and eleven of its sixteen apparent
     misses on its second.

No network, no keys.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warn_reference_set as W                                    # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def _manifest():
    return json.loads(W.MANIFEST_PATH.read_text(encoding="utf-8"))


class TheSecFigureIsNotThisSetsBusiness(unittest.TestCase):
    def test_no_warn_module_writes_a_sec_recall_file(self):
        # Anchored so this set's OWN warn_recall_measurement.json does not trip
        # a rule about the SEC one.
        forbidden = (r"(?<!warn_)recall_measurement\.json",
                     r"(?<!warn_)recall_adjudications\.json",
                     r"MATCHED_FLOOR", r"sec-item-205")
        for name in ("warn_reference_set.py", "warn_adjudication_pack.py",
                     "warn_adjudicate.py", "warn_pdf.py"):
            body = (W.HERE / name).read_text(encoding="utf-8")
            code = "\n".join(l for l in body.splitlines()
                             if not l.strip().startswith("#"))
            # The docstring mentions the SEC set by design; the CODE must not.
            code = re.sub(r'""".*?"""', "", code, flags=re.S)
            for token in forbidden:
                self.assertIsNone(re.search(token, code),
                                  f"{name} references {token!r} outside its docstring — "
                                  f"this set is additive and must not be able to move "
                                  f"the published SEC figure")

    def test_the_two_measurement_files_are_different_files(self):
        import recall_goldset
        self.assertNotEqual(W.MEASUREMENT_PATH, recall_goldset.MEASUREMENT_PATH)
        self.assertNotEqual(W.MANIFEST_PATH, recall_goldset.MANIFEST_PATH)


class NothingIsMatchedUntilAnEditorSaysSo(unittest.TestCase):
    def test_every_built_event_arrives_not_matched(self):
        rows = [{"state": "CA", "employer_published": "Acme, Inc.",
                 "notice_date": "2025-08-01", "effective_date": "2025-10-01",
                 "job_count": 60, "source_url": "https://example.invalid/x",
                 "source_locator": "row 1", "state_received_date": "2025-08-02",
                 "location": "", "notice_type": None, "industry": None}]
        events, excluded = W.build_events(rows)
        self.assertEqual(excluded, [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["match_decision"], "not_matched")

    def test_the_committed_manifest_has_no_self_awarded_match(self):
        man = _manifest()
        for ev in man["reference_events"] + man["large_event_census"]:
            if ev.get("match_decision") == "matched":
                self.assertTrue(ev.get("adjudicated_by"),
                                f"{ev['reference_row_id']} is matched with no "
                                f"adjudicator — only warn_adjudicate.py may set that")


class AQueryThatWasNeverSentIsNotAMiss(unittest.TestCase):
    GLUED = "Essendant 2405 Commerce Park Dr ORLANDO, FL, 32819"

    def test_address_cutting_never_empties_the_alias_list(self):
        # The original bug: _CITY_ST_ZIP's greedy head ate the employer too.
        self.assertEqual(W.aliases_for(self.GLUED), ["Essendant"])
        for name in ("Mattel, Inc.", "Raley's", "Frito-Lay, Inc 2000 Parks Oaks "
                     "Avenue ORLANDO, FL, 32808", "Amazon 27505 SW 132 Ave TMB8 "
                     "HOMESTEAD, FL, 33032"):
            self.assertTrue(W.aliases_for(name), f"{name!r} produced no alias")

    def test_query_terms_are_literal_substrings_of_the_published_name(self):
        # /query?company= is a substring LIKE. A punctuation-stripped alias is
        # not a substring of the stored name, so the row can never come back.
        for name in ("Mattel, Inc.", "Raley's", "Albertsons #4286 (W. Freeway)",
                     "Saks & Company LLC", "Frito-Lay, Inc"):
            for term in W.query_terms_for(name):
                self.assertIn(term, name,
                              f"query term {term!r} is not a substring of {name!r} — "
                              f"the endpoint could never return the row")

    def test_measure_refuses_to_score_an_event_it_could_not_query(self):
        manifest = {
            "reference_set_id": "test", "definition_document": "test",
            "frame_sizes": {s: 1 for s in W.STATES},
            "large_event_census": [],
            "reference_events": [{
                "reference_row_id": "x", "state": "CA", "employer_published": "x",
                "notice_date": "2025-08-01", "stated_job_count": 1, "size_band": "S",
                "employer_aliases": [], "query_terms": [],
                "match_window": ["2025-07-01", "2026-09-01"], "component_rows": [],
            }]}
        out = _measure_offline(manifest)
        self.assertEqual(out["unreachable"], 1)
        self.assertEqual(out["results"]["primary"], [])
        self.assertIn("no query was sent", out["unreachable_events"][0]["why"])


def _measure_offline(manifest):
    """Run measure() with the network stubbed out and nothing written to disk."""
    original_api, original_path = W._api, W.MEASUREMENT_PATH
    W._api = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no query may be sent"))
    W.MEASUREMENT_PATH = Path(__file__).resolve().parent / "_throwaway_measurement.json"
    try:
        return W.measure(manifest=manifest)
    finally:
        W._api, W.MEASUREMENT_PATH = original_api, original_path
        Path(__file__).resolve().parent.joinpath(
            "_throwaway_measurement.json").unlink(missing_ok=True)


class TheCollapseUnitIsTheOneTheDefinitionStates(unittest.TestCase):
    def test_same_employer_same_day_same_state_is_one_event(self):
        base = {"state": "CA", "notice_date": "2025-08-01",
                "effective_date": "2025-10-01", "source_url": "u",
                "source_locator": "l", "state_received_date": "2025-08-01",
                "location": "", "notice_type": None, "industry": None}
        rows = [{**base, "employer_published": "Blue Shield of California - Oakland",
                 "job_count": 70},
                {**base, "employer_published": "Blue shield of California - Town Center",
                 "job_count": 32}]
        events, _ = W.build_events(rows)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["stated_job_count"], 102)
        self.assertEqual(events[0]["published_rows"], 2)

    def test_a_different_notice_date_is_a_different_event(self):
        base = {"state": "CA", "employer_published": "Acme", "job_count": 60,
                "effective_date": "2025-10-01", "source_url": "u",
                "source_locator": "l", "state_received_date": None,
                "location": "", "notice_type": None, "industry": None}
        events, _ = W.build_events([{**base, "notice_date": "2025-08-01"},
                                    {**base, "notice_date": "2025-08-04"}])
        self.assertEqual(len(events), 2)

    def test_a_rescinded_notice_is_excluded_with_its_reason(self):
        rows = [{"state": "CA", "employer_published": "Acme (RESCINDED)",
                 "notice_date": "2025-08-01", "effective_date": "2025-10-01",
                 "job_count": 60, "source_url": "u", "source_locator": "l",
                 "state_received_date": None, "location": "", "notice_type": None,
                 "industry": None}]
        events, excluded = W.build_events(rows)
        self.assertEqual(events, [])
        self.assertIn("rescinded", excluded[0]["excluded_because"])


class TheSampleIsReproducible(unittest.TestCase):
    def test_the_draw_recorded_in_the_manifest_reproduces(self):
        man = _manifest()
        for st, draw in man["sample_draws"].items():
            self.assertEqual(draw["start"], _seed_start(st, draw),
                             f"{st}'s recorded start does not follow from its seed — "
                             f"the draw was re-rolled")

    def test_no_event_is_in_both_the_sample_and_the_census(self):
        man = _manifest()
        a = {e["reference_row_id"] for e in man["reference_events"]}
        b = {e["reference_row_id"] for e in man["large_event_census"]}
        self.assertEqual(a & b, set(),
                         "pooling a census with a systematic sample double-counts")


def _seed_start(state, draw):
    return W._seed(state) % draw["interval"] if draw["interval"] > 1 else 0


if __name__ == "__main__":
    unittest.main()
