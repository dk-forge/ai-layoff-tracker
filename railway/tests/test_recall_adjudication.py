"""The gate that lets a HUMAN move the published recall figure, and nothing else.

`recall_goldset.measure()` counts an event only where the manifest says
`matched`, because "a machine must not promote its own recall". That sentence is
only true while the ONLY way to write `matched` is a person on the record. These
tests pin the four properties that make that so, by DRIVING main() against a
temp manifest and reading what was stored — not by inspecting the parser, which
is how `--rows` silently kept one of three ids on 2026-08-12.

    1. a decision is REVERSIBLE, byte for byte, including the absence of a key;
    2. it is ATTRIBUTED — no reviewer or no reason is REFUSED with nothing written;
    3. no event can read `matched` without a named decision behind it (--verify),
       and that runs against the REAL manifest here so a hand-edit reddens CI;
    4. running the same decision twice writes once.

Plus the one this repo has already been bitten by: `--event-ids 149625 149911`
typed the way a person types it must record BOTH.
"""
import io
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

import recall_adjudicate as ra  # noqa: E402
import recall_goldset as rg     # noqa: E402


PENDING_ID = "sec-205-0001193125-25-163439"        # Cibus
OTHER_ID = "sec-205-0001289308-25-000025"          # EnerSys, July 2025

MANIFEST = {
    "reference_set_id": "sec-item-205-us-2025-07_2026-06",
    "reference_events": [
        {"reference_row_id": PENDING_ID, "filer": "Cibus, Inc.",
         "filing_date": "2025-07-23", "stated_job_count": 34,
         "accession": "0001193125-25-163439", "cik": "0001705843",
         "official_source_url": "https://www.sec.gov/x.htm",
         "employer_aliases": ["Cibus"], "excluded_name_prefixes": [],
         "match_window": ["2025-04-24", "2026-04-19"],
         "match_decision": "not_matched",
         "match_notes": "No Cibus row.",
         "rejected_candidate_event_ids": []},
        {"reference_row_id": OTHER_ID, "filer": "EnerSys",
         "filing_date": "2025-07-22", "stated_job_count": 575,
         "accession": "0001289308-25-000025", "cik": "0001289308",
         "official_source_url": "https://www.sec.gov/y.htm",
         "employer_aliases": ["EnerSys"], "excluded_name_prefixes": [],
         "match_window": ["2025-04-23", "2026-04-18"],
         "match_decision": "not_matched",
         "match_notes": "Only an undated ERM record.",
         "rejected_candidate_event_ids": []},
    ],
}

PACK = {
    "built_at": "2026-08-12T18:00:54Z",
    "pending": 2,
    "entries": [
        {"reference_row_id": PENDING_ID, "filer": "Cibus, Inc.",
         "filing_date": "2025-07-23", "stated_job_count": 34,
         "proposed_tracker_event_ids": [149909],
         "rows": [{"flags": []}]},
        {"reference_row_id": OTHER_ID, "filer": "EnerSys",
         "filing_date": "2025-07-22", "stated_job_count": 575,
         "proposed_tracker_event_ids": [149625, 149911],
         "rows": [{"flags": ["COUNT differs by -101"]}]},
    ],
}


class Harness(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.manifest_path = base / "goldset.json"
        self.ledger_path = base / "ledger.json"
        self.pack_path = base / "pack.json"
        self.manifest_path.write_text(json.dumps(MANIFEST, indent=1), encoding="utf-8")
        self.pack_path.write_text(json.dumps(PACK, indent=1), encoding="utf-8")

    def run_cli(self, *argv, now=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = ra.main(list(argv), manifest_path=self.manifest_path,
                           ledger_path=self.ledger_path, pack_path=self.pack_path,
                           now=now)
        return code, buf.getvalue()

    def manifest(self):
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def event(self, rid):
        return next(e for e in self.manifest()["reference_events"]
                    if e["reference_row_id"] == rid)

    def ledger(self):
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))


class AcceptRecordsWhoAndWhenTests(Harness):
    def test_accept_marks_matched_and_names_the_decider(self):
        code, out = self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D. Kotta",
                                 "--reason", "the filing states 34 and our row holds 34",
                                 "--event-ids", "149909", now="2026-08-12T19:00:00Z")
        self.assertEqual(code, 0, out)
        ev = self.event(PENDING_ID)
        self.assertEqual(ev["match_decision"], "matched",
                         "an accepted gold event must read `matched` — that is the field "
                         "recall_goldset.measure() counts")
        self.assertEqual(ev["adjudication"]["reviewed_by"], "D. Kotta")
        self.assertEqual(ev["adjudication"]["reviewed_at"], "2026-08-12T19:00:00Z")
        self.assertEqual(ev["adjudication"]["tracker_event_ids"], [149909])
        entry = self.ledger()["decisions"][-1]
        self.assertEqual(entry["reviewed_by"], "D. Kotta")
        self.assertEqual(entry["decision"], "accept")
        self.assertIn("34", entry["reason"])

    def test_the_frozen_reference_fields_are_never_rewritten(self):
        self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     "--event-ids", "149909")
        ev = self.event(PENDING_ID)
        for field in ("accession", "official_source_url", "stated_job_count",
                      "employer_aliases", "match_window", "filing_date"):
            self.assertEqual(ev[field], MANIFEST["reference_events"][0][field],
                             f"a decision rewrote the frozen reference field {field!r}; "
                             f"the gold set's denominator and evidence are not editable "
                             f"by an adjudication")

    def test_reject_records_the_ids_so_they_stop_resurfacing(self):
        code, out = self.run_cli("--reject", OTHER_ID, "--reviewed-by", "D",
                                 "--reason", "149625 is the March 2026 Tijuana plan",
                                 "--event-ids", "149625")
        self.assertEqual(code, 0, out)
        ev = self.event(OTHER_ID)
        self.assertEqual(ev["match_decision"], "not_matched")
        self.assertEqual(ev["rejected_candidate_event_ids"], [149625],
                         "a rejected candidate must be recorded so measure() stops "
                         "re-proposing it every week")


class AttributionIsRequiredTests(Harness):
    def test_no_reviewer_is_refused_and_writes_nothing(self):
        code, out = self.run_cli("--accept", PENDING_ID, "--reason", "r",
                                 "--event-ids", "149909")
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out)
        self.assertEqual(self.event(PENDING_ID)["match_decision"], "not_matched",
                         "an unattributed accept changed the manifest — that is the "
                         "machine promoting its own recall with extra steps")
        self.assertFalse(self.ledger_path.exists(),
                         "REFUSED must write nothing at all, ledger included")

    def test_no_reason_is_refused(self):
        code, out = self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D",
                                 "--event-ids", "149909")
        self.assertEqual(code, 2, out)
        self.assertIn("--reason is required", out)

    def test_no_event_ids_is_refused(self):
        code, out = self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D",
                                 "--reason", "r")
        self.assertEqual(code, 2, out)
        self.assertIn("--event-ids is required", out)

    def test_an_id_the_pack_does_not_propose_is_refused(self):
        code, out = self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D",
                                 "--reason", "r", "--event-ids", "149908")
        self.assertEqual(code, 2, out)
        self.assertIn("not proposed", out)
        self.assertEqual(self.event(PENDING_ID)["match_decision"], "not_matched")


class EventIdsTakesEveryValueTests(Harness):
    """`--rows 114335 113529 64351` recorded ONE id on 2026-08-12. Not again."""

    def test_space_separated_ids_are_all_recorded(self):
        code, out = self.run_cli("--reject", OTHER_ID, "--reviewed-by", "D",
                                 "--reason", "neither row is the July plan",
                                 "--event-ids", "149625", "149911")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(OTHER_ID)["rejected_candidate_event_ids"],
                         [149625, 149911],
                         "--event-ids kept only the first token; a decision that names one "
                         "of two rows asserts a finding nobody made, and exits zero")

    def test_ids_stop_at_the_next_flag(self):
        code, out = self.run_cli("--reject", OTHER_ID, "--event-ids", "149625", "149911",
                                 "--reviewed-by", "D", "--reason", "r")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(OTHER_ID)["adjudication"]["tracker_event_ids"],
                         [149625, 149911])


class IdempotenceTests(Harness):
    def test_the_same_decision_twice_writes_once(self):
        self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     "--event-ids", "149909")
        code, out = self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D",
                                 "--reason", "r", "--event-ids", "149909")
        self.assertEqual(code, 0, out)
        self.assertIn("ALREADY RECORDED", out)
        self.assertEqual(len(self.ledger()["decisions"]), 1,
                         "a second identical run appended a second ledger entry; the audit "
                         "trail must show one decision, not one per invocation")

    def test_a_different_decision_is_refused_until_reverted(self):
        self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     "--event-ids", "149909")
        code, out = self.run_cli("--reject", PENDING_ID, "--reviewed-by", "D",
                                 "--reason", "changed my mind", "--event-ids", "149909")
        self.assertEqual(code, 2, out)
        self.assertIn("already adjudicated", out)
        self.assertEqual(self.event(PENDING_ID)["match_decision"], "matched",
                         "a contradicting decision overwrote the first silently; both "
                         "readings have to stay on the record")


class ReversibilityTests(Harness):
    def test_revert_restores_the_event_exactly_including_the_absent_key(self):
        before = self.event(PENDING_ID)
        self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     "--event-ids", "149909")
        code, out = self.run_cli("--revert", PENDING_ID, "--reviewed-by", "D",
                                 "--reason", "the row is a different facility")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(PENDING_ID), before,
                         "revert did not restore the event byte for byte; a decision that "
                         "cannot be undone exactly is not reversible")
        self.assertNotIn("adjudication", self.event(PENDING_ID),
                         "the `adjudication` key survived a revert of the decision that "
                         "created it")

    def test_revert_is_recorded_and_does_not_erase_the_original(self):
        self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D", "--reason", "first",
                     "--event-ids", "149909", now="2026-08-12T19:00:00Z")
        self.run_cli("--revert", PENDING_ID, "--reviewed-by", "E", "--reason", "second",
                     now="2026-08-12T20:00:00Z")
        decisions = self.ledger()["decisions"]
        self.assertEqual([d["decision"] for d in decisions], ["accept", "revert"],
                         "the ledger is append-only: a revert adds a finding, it does not "
                         "delete the one it reverses")
        self.assertEqual(decisions[1]["reverts"], decisions[0]["entry_id"])

    def test_after_a_revert_the_event_can_be_decided_again(self):
        self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     "--event-ids", "149909", now="2026-08-12T19:00:00Z")
        self.run_cli("--revert", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     now="2026-08-12T20:00:00Z")
        code, out = self.run_cli("--reject", PENDING_ID, "--reviewed-by", "D",
                                 "--reason", "different facility", "--event-ids", "149909",
                                 now="2026-08-12T21:00:00Z")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(PENDING_ID)["match_decision"], "not_matched")

    def test_revert_with_nothing_to_revert_is_refused(self):
        code, out = self.run_cli("--revert", PENDING_ID, "--reviewed-by", "D",
                                 "--reason", "r")
        self.assertEqual(code, 2, out)
        self.assertIn("no live adjudication", out)


class VerifyRefusesAnUnsignedMatchTests(Harness):
    def test_a_hand_edited_match_fails_verification(self):
        doc = self.manifest()
        doc["reference_events"][0]["match_decision"] = "matched"
        self.manifest_path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        code, out = self.run_cli("--verify")
        self.assertEqual(code, 2, out)
        self.assertIn("no `adjudication` block", out)
        self.assertIn(PENDING_ID, out)

    def test_an_adjudication_block_with_no_ledger_entry_fails(self):
        doc = self.manifest()
        doc["reference_events"][0]["match_decision"] = "matched"
        doc["reference_events"][0]["adjudication"] = {
            "decision": "matched", "reviewed_by": "someone",
            "reviewed_at": "2026-08-12T19:00:00Z", "reason": "r",
            "tracker_event_ids": [149909], "entry_id": "made-up"}
        self.manifest_path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        code, out = self.run_cli("--verify")
        self.assertEqual(code, 2, out)
        self.assertIn("no live entry", out)

    def test_a_properly_recorded_accept_verifies_clean(self):
        self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     "--event-ids", "149909")
        code, out = self.run_cli("--verify")
        self.assertEqual(code, 0, out)

    def test_a_reverted_accept_leaves_nothing_claiming_matched(self):
        self.run_cli("--accept", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     "--event-ids", "149909", now="2026-08-12T19:00:00Z")
        self.run_cli("--revert", PENDING_ID, "--reviewed-by", "D", "--reason", "r",
                     now="2026-08-12T20:00:00Z")
        code, out = self.run_cli("--verify")
        self.assertEqual(code, 0, out)


class TheRealManifestTests(unittest.TestCase):
    """Runs against the committed files, so a hand-edit reddens CI rather than
    quietly raising the published recall figure."""

    def test_the_committed_manifest_and_ledger_verify(self):
        ok, problems = ra.verify()
        self.assertTrue(ok, "the committed gold set has a `matched` event with no named "
                            "decision behind it:\n  " + "\n  ".join(problems))

    def test_pre_tool_matched_is_exactly_the_events_adjudicated_before_the_ledger(self):
        manifest = ra.load_manifest()
        unsigned = {e["reference_row_id"] for e in manifest["reference_events"]
                    if e.get("match_decision") == "matched" and not e.get("adjudication")}
        self.assertLessEqual(
            unsigned, set(ra.PRE_TOOL_MATCHED),
            "PRE_TOOL_MATCHED is the frozen list of the 24 decided on 2026-08-01 and must "
            "not grow. An event outside it that reads `matched` with no adjudication block "
            "was written by hand")
        self.assertEqual(len(ra.PRE_TOOL_MATCHED), 24)

    def test_the_pack_covers_every_event_measure_would_ask_about(self):
        """The pack is the evidence behind a decision, so a decision the pack does
        not cover is refused. That is only safe while the pack is buildable."""
        pack = ra.load_pack()
        manifest_ids = {e["reference_row_id"] for e in ra.load_manifest()["reference_events"]}
        pack_ids = {e["reference_row_id"] for e in pack["entries"]}
        self.assertTrue(pack_ids <= manifest_ids,
                        f"the pack names events the gold set does not hold: "
                        f"{sorted(pack_ids - manifest_ids)}")
        self.assertTrue(all(e.get("proposed_tracker_event_ids") for e in pack["entries"]),
                        "a pack entry proposes no tracker event, so there is nothing to "
                        "decide about it")

    def test_the_numerator_still_counts_only_matched(self):
        """The gate itself. If measure() ever counted a candidate, this whole
        module would be decoration."""
        manifest = ra.load_manifest()
        events = manifest["reference_events"]
        rows = [{"id": 1, "event_id": 999, "company_name": events[0]["filer"],
                 "layoff_date": events[0]["filing_date"]}]
        fake = {"reference_events": [dict(e, match_decision="not_matched")
                                     for e in events]}
        result = rg.measure(fetch=lambda url, timeout=30: json.dumps({"data": rows}).encode(),
                            manifest=fake, sleep=lambda s: None)
        self.assertEqual(result["matched"], 0,
                         "measure() counted an event whose match_decision is not `matched`; "
                         "the adjudication gate has been bypassed and a machine is "
                         "promoting its own recall")
        self.assertEqual(result["missed"], len(events))


if __name__ == "__main__":
    unittest.main()
