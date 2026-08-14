"""The gate that lets a HUMAN move the US WARN figure, and the sheet they read.

Two halves, and they fail for different reasons.

THE RECORDER. `warn_reference_set.measure()` counts an event only where the
manifest says `matched`, which is only meaningful while the ONLY way to write
`matched` is a person on the record. The first WARN recorder had one of the four
properties that makes that so. These tests pin all four by DRIVING main()
against a temp manifest and reading what was stored — not by inspecting the
parser, which is how `--rows` silently kept one of three ids on 2026-08-12:

    1. REVERSIBLE, byte for byte, including the absence of a key;
    2. ATTRIBUTED — no reviewer, no reason or no row id is REFUSED with nothing
       written;
    3. NO SILENT MATCH — `--verify` fails on a hand-edited `match_decision`;
    4. IDEMPOTENT — running the same decision twice records it once.

Plus the one that is specific to this set: its manifest keeps events in TWO
lists, and a recorder that saw only the first would refuse the whole 500-plus
census.

THE SHEET. `warn_adjudication_pack` exists because of the Dow failure: a pooled
line described a co-proposed row and a correct row was rejected. So no line may
carry two rows' evidence, every row must be named by id, a clean row must be
SAID to be clean, and the event with no candidate row must not be filed as one
row among ninety-nine near-identical accepts.

No network, no keys.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

import warn_adjudicate as wa                                       # noqa: E402
import warn_adjudication_pack as wp                                # noqa: E402
import recall_adjudicate as ra                                     # noqa: E402

SAMPLE_ID = "warn-tx-2025-09-24-acme"
CENSUS_ID = "warn-ca-2025-08-01-census-co"
EMPTY_ID = "warn-tx-2025-11-18-nothing"


def _event(rid, employer, notice, total, components, effective, window):
    return {
        "reference_row_id": rid, "state": rid.split("-")[1].upper(),
        "employer_published": employer, "notice_date": notice,
        "stated_job_count": total,
        "component_rows": [{"employer_published": employer, "job_count": c,
                            "effective_date": effective, "location": "Somewhere",
                            "source_url": "https://example.invalid/warn",
                            "source_locator": "row 1"} for c in components],
        "employer_aliases": [employer], "query_terms": [employer],
        "official_source_url": "https://example.invalid/warn",
        "size_band": "M", "published_rows": len(components),
        "effective_date_min": effective, "effective_date_max": effective,
        "match_window": window, "match_decision": "not_matched",
        "match_notes": "NOT ADJUDICATED.", "rejected_candidate_event_ids": [],
        "stratum": "primary",
    }


MANIFEST = {
    "reference_set_id": "us-warn-test",
    "definition_document": "docs/recall-reference-sets/DEF.md",
    "reference_events": [
        _event(SAMPLE_ID, "Acme Industries", "2025-09-24", 70, [70], "2025-12-01",
               ["2025-08-25", "2026-10-29"]),
        _event(EMPTY_ID, "Nothing Held Inc.", "2025-11-18", 180, [180], "2025-01-05",
               ["2025-10-19", "2026-12-23"]),
    ],
    "large_event_census": [
        _event(CENSUS_ID, "Census Co", "2025-08-01", 600, [600], "2025-10-01",
               ["2025-07-02", "2026-09-05"]),
    ],
}


def _candidate(row_id, event_id, name, jobs, when, source="warn", state="TX"):
    return {"tier": "exact", "tracker_event_id": event_id, "tracker_row_id": row_id,
            "company_name": name, "job_count": jobs, "row_date": when,
            "state": state, "source_type": source, "source_name": f"{state} WARN notice",
            "source_url": "https://example.invalid/row", "flags": []}


MEASUREMENT = {
    "measured_at": "2026-08-13T06:50:31Z",
    "results": {
        "primary": [
            {"id": SAMPLE_ID, "state": "TX", "employer": "Acme Industries",
             "notice_date": "2025-09-24", "stated_job_count": 70, "size_band": "M",
             "match_decision": "not_matched", "machine_tier": "exact",
             "candidates": [
                 # The Dow shape: a wrong row proposed alongside the right one.
                 _candidate(900001, 5001, "Acme Industries", 12, "2025-11-02",
                            source="news"),
                 _candidate(900002, 5002, "Acme Industries", 70, "2025-12-01"),
             ]},
            {"id": EMPTY_ID, "state": "TX", "employer": "Nothing Held Inc.",
             "notice_date": "2025-11-18", "stated_job_count": 180, "size_band": "M",
             "match_decision": "not_matched", "machine_tier": "none",
             "candidates": []},
        ],
        "large_census": [
            {"id": CENSUS_ID, "state": "CA", "employer": "Census Co",
             "notice_date": "2025-08-01", "stated_job_count": 600, "size_band": "L",
             "match_decision": "not_matched", "machine_tier": "exact",
             "candidates": [_candidate(900003, 5003, "Census Co", 600, "2025-10-01",
                                       state="CA")]},
        ],
    },
}


def _pack():
    """The pack as the builder produces it, with no network."""
    _, measurement, entries, no_candidate = wp.build_pack(
        manifest=MANIFEST, measurement=MEASUREMENT, refetch=False)
    arith = wp.arithmetic(measurement, entries, no_candidate)
    return {"built_at": "2026-08-13T07:00:00Z", "entries": entries,
            "no_candidate": no_candidate, "arithmetic": arith}, measurement


# ---------------------------------------------------------------------------
# The recorder
# ---------------------------------------------------------------------------
class Harness(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.manifest_path = base / "goldset.json"
        self.ledger_path = base / "ledger.json"
        self.pack_path = base / "pack.json"
        self.manifest_path.write_text(json.dumps(MANIFEST, indent=2) + "\n",
                                      encoding="utf-8")
        pack, _ = _pack()
        self.pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")

    def run_cli(self, *argv, now=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = wa.main(list(argv), manifest_path=self.manifest_path,
                           ledger_path=self.ledger_path, pack_path=self.pack_path,
                           now=now)
        return code, buf.getvalue()

    def manifest(self):
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def event(self, rid):
        doc = self.manifest()
        for ev in doc["reference_events"] + doc["large_event_census"]:
            if ev["reference_row_id"] == rid:
                return ev
        raise AssertionError(f"{rid} vanished from the manifest")

    def ledger(self):
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))


class AcceptRecordsWhoAndWhenTests(Harness):
    def test_accept_marks_matched_and_names_the_decider_and_the_row(self):
        code, out = self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D. Kotta",
                                 "--reason", "the notice states 70 and row 900002 holds 70",
                                 "--row-ids", "900002", now="2026-08-13T19:00:00Z")
        self.assertEqual(code, 0, out)
        ev = self.event(SAMPLE_ID)
        self.assertEqual(ev["match_decision"], "matched",
                         "an accepted reference event must read `matched` — that is the "
                         "field warn_reference_set.measure() counts")
        self.assertEqual(ev["adjudication"]["reviewed_by"], "D. Kotta")
        self.assertEqual(ev["adjudication"]["reviewed_at"], "2026-08-13T19:00:00Z")
        self.assertEqual(ev["adjudication"]["tracker_row_ids"], [900002])
        self.assertEqual(ev["adjudicated_by"], "D. Kotta",
                         "the flat mirror the offline guards read was not written; a "
                         "matched event with no adjudicator is the assertion that "
                         "catches a machine promoting itself")
        entry = self.ledger()["decisions"][-1]
        self.assertEqual(entry["decision"], "accept")
        self.assertEqual(entry["tracker_row_ids"], [900002])

    def test_the_frozen_reference_fields_are_never_rewritten(self):
        self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D", "--reason", "r",
                     "--row-ids", "900002")
        ev = self.event(SAMPLE_ID)
        before = MANIFEST["reference_events"][0]
        for field in ("notice_date", "stated_job_count", "component_rows",
                      "employer_aliases", "match_window", "official_source_url",
                      "effective_date_min"):
            self.assertEqual(ev[field], before[field],
                             f"a decision rewrote the frozen reference field {field!r}; "
                             f"the set's denominator and evidence are not editable by "
                             f"an adjudication")

    def test_a_census_event_can_be_adjudicated_too(self):
        code, out = self.run_cli("--accept", CENSUS_ID, "--reviewed-by", "D",
                                 "--reason", "600 exact, effective date exact",
                                 "--row-ids", "900003")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(CENSUS_ID)["match_decision"], "matched",
                         "the manifest keeps events in two lists and the recorder saw "
                         "only the first; a third of the set would be un-adjudicable")

    def test_reject_records_the_row_ids_so_they_stop_resurfacing(self):
        code, out = self.run_cli("--reject", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "900001 is a different, smaller action",
                                 "--row-ids", "900001")
        self.assertEqual(code, 0, out)
        ev = self.event(SAMPLE_ID)
        self.assertEqual(ev["match_decision"], "not_matched")
        self.assertEqual(ev["rejected_candidate_event_ids"], [900001])


class AttributionIsRequiredTests(Harness):
    def test_no_reviewer_is_refused_and_writes_nothing(self):
        code, out = self.run_cli("--accept", SAMPLE_ID, "--reason", "r",
                                 "--row-ids", "900002")
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out)
        self.assertEqual(self.event(SAMPLE_ID)["match_decision"], "not_matched",
                         "an unattributed accept changed the manifest — that is the "
                         "machine promoting its own recall with extra steps")
        self.assertFalse(self.ledger_path.exists(),
                         "REFUSED must write nothing at all, ledger included")

    def test_no_reason_is_refused(self):
        code, out = self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D",
                                 "--row-ids", "900002")
        self.assertEqual(code, 2, out)
        self.assertIn("--reason is required", out)

    def test_no_row_ids_is_refused(self):
        code, out = self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "r")
        self.assertEqual(code, 2, out)
        self.assertIn("--row-ids is required", out)

    def test_a_row_the_pack_does_not_propose_is_refused(self):
        code, out = self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "r", "--row-ids", "900999")
        self.assertEqual(code, 2, out)
        self.assertIn("not proposed", out)
        self.assertEqual(self.event(SAMPLE_ID)["match_decision"], "not_matched")


class RowIdsTakesEveryValueTests(Harness):
    """`--rows 114335 113529 64351` recorded ONE id on 2026-08-12. Not again."""

    def test_space_separated_ids_are_all_recorded(self):
        code, out = self.run_cli("--reject", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "neither row is this notice",
                                 "--row-ids", "900001", "900002")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(SAMPLE_ID)["rejected_candidate_event_ids"],
                         [900001, 900002],
                         "--row-ids kept only the first token; a decision that names one "
                         "of two rows asserts a finding nobody made, and exits zero")

    def test_ids_stop_at_the_next_flag(self):
        code, out = self.run_cli("--reject", SAMPLE_ID, "--row-ids", "900001", "900002",
                                 "--reviewed-by", "D", "--reason", "r")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(SAMPLE_ID)["adjudication"]["tracker_row_ids"],
                         [900001, 900002])


class IdempotenceTests(Harness):
    def test_the_same_decision_twice_writes_once(self):
        self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D", "--reason", "r",
                     "--row-ids", "900002")
        code, out = self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "r", "--row-ids", "900002")
        self.assertEqual(code, 0, out)
        self.assertIn("ALREADY RECORDED", out)
        self.assertEqual(len(self.ledger()["decisions"]), 1,
                         "a second identical run appended a second ledger entry; the "
                         "audit trail must show one decision, not one per invocation")

    def test_a_different_decision_is_refused_until_reverted(self):
        self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D", "--reason", "r",
                     "--row-ids", "900002")
        code, out = self.run_cli("--reject", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "changed my mind", "--row-ids", "900002")
        self.assertEqual(code, 2, out)
        self.assertIn("already adjudicated", out)
        self.assertEqual(self.event(SAMPLE_ID)["match_decision"], "matched",
                         "a contradicting decision overwrote the first silently; both "
                         "readings have to stay on the record")


class ReversibilityTests(Harness):
    def test_revert_restores_the_event_exactly_including_the_absent_keys(self):
        before = self.event(SAMPLE_ID)
        self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D", "--reason", "r",
                     "--row-ids", "900002", now="2026-08-13T19:00:00Z")
        code, out = self.run_cli("--revert", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "the row is a different facility",
                                 now="2026-08-13T20:00:00Z")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(SAMPLE_ID), before,
                         "revert did not restore the event byte for byte; a decision "
                         "that cannot be undone exactly is not reversible")
        for key in ("adjudication", "adjudicated_by", "adjudicated_at",
                    "adjudicated_tracker_row_ids"):
            self.assertNotIn(key, self.event(SAMPLE_ID),
                             f"{key!r} survived a revert of the decision that created "
                             f"it — a mirror field outside the snapshot outlives its "
                             f"own reversal and keeps claiming an adjudicator")

    def test_revert_is_recorded_and_does_not_erase_the_original(self):
        self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D", "--reason", "first",
                     "--row-ids", "900002", now="2026-08-13T19:00:00Z")
        self.run_cli("--revert", SAMPLE_ID, "--reviewed-by", "E", "--reason", "second",
                     now="2026-08-13T20:00:00Z")
        decisions = self.ledger()["decisions"]
        self.assertEqual([d["decision"] for d in decisions], ["accept", "revert"],
                         "the ledger is append-only: a revert adds a finding, it does "
                         "not delete the one it reverses")
        self.assertEqual(decisions[1]["reverts"], decisions[0]["entry_id"])

    def test_revert_with_nothing_to_revert_is_refused(self):
        code, out = self.run_cli("--revert", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "r")
        self.assertEqual(code, 2, out)
        self.assertIn("no live adjudication", out)


class VerifyRefusesAnUnsignedMatchTests(Harness):
    def test_a_hand_edited_match_fails_verification(self):
        doc = self.manifest()
        doc["reference_events"][0]["match_decision"] = "matched"
        self.manifest_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        code, out = self.run_cli("--verify")
        self.assertEqual(code, 2, out)
        self.assertIn("no `adjudication` block", out)
        self.assertIn(SAMPLE_ID, out)

    def test_a_hand_edited_match_in_the_census_also_fails(self):
        doc = self.manifest()
        doc["large_event_census"][0]["match_decision"] = "matched"
        self.manifest_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        code, out = self.run_cli("--verify")
        self.assertEqual(code, 2, out)
        self.assertIn(CENSUS_ID, out)

    def test_a_properly_recorded_accept_verifies_clean(self):
        self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D", "--reason", "r",
                     "--row-ids", "900002")
        code, out = self.run_cli("--verify")
        self.assertEqual(code, 0, out)

    def test_a_reverted_accept_leaves_nothing_claiming_matched(self):
        self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D", "--reason", "r",
                     "--row-ids", "900002", now="2026-08-13T19:00:00Z")
        self.run_cli("--revert", SAMPLE_ID, "--reviewed-by", "D", "--reason", "r",
                     now="2026-08-13T20:00:00Z")
        code, out = self.run_cli("--verify")
        self.assertEqual(code, 0, out)


class TheSecFigureIsNotThisSetsBusinessTests(Harness):
    """A regex over this module's source proves it does not NAME the SEC files.
    This proves a real decision does not TOUCH them."""

    SEC_FILES = ("recall_measurement.json", "recall_adjudications.json")

    def _sec_bytes(self):
        out = {p: (RAILWAY / p).read_bytes() for p in self.SEC_FILES}
        out["manifest"] = ra.MANIFEST_PATH.read_bytes()
        return out

    def test_a_warn_decision_leaves_every_sec_file_byte_identical(self):
        before = self._sec_bytes()
        code, out = self.run_cli("--accept", SAMPLE_ID, "--reviewed-by", "D",
                                 "--reason", "r", "--row-ids", "900002")
        self.assertEqual(code, 0, out)
        self.assertEqual(self._sec_bytes(), before,
                         "a WARN adjudication changed a SEC file; this set is ADDITIVE "
                         "and the 56/57 the owner adjudicated is not its to move")

    def test_the_warn_profile_points_at_no_sec_path(self):
        for path in (wa.PROFILE.manifest_path, wa.PROFILE.ledger_path,
                     wa.PROFILE.pack_path):
            self.assertNotIn(path, (ra.MANIFEST_PATH, ra.LEDGER_PATH, ra.PACK_PATH),
                             f"the WARN profile points at {path}, a SEC file")
            self.assertIn("warn", path.name.lower(),
                          f"{path.name} is not a WARN file")


# ---------------------------------------------------------------------------
# The sheet
# ---------------------------------------------------------------------------
class Sheet(unittest.TestCase):
    def setUp(self):
        self.manifest = MANIFEST
        _, self.measurement, self.entries, self.no_candidate = wp.build_pack(
            manifest=MANIFEST, measurement=MEASUREMENT, refetch=False)
        self.arith = wp.arithmetic(self.measurement, self.entries, self.no_candidate)
        self.text = wp.render_sheet(self.manifest, self.measurement, self.entries,
                                    self.no_candidate, self.arith,
                                    "2026-08-13T07:00:00Z")


class NoLineDescribesTwoRowsTests(Sheet):
    """The Dow failure, as an assertion."""

    def test_no_rows_evidence_mentions_another_rows_id(self):
        for entry in self.entries:
            ids = {c["tracker_row_id"] for c in entry["candidates"]}
            for cand in entry["candidates"]:
                mine = cand["tracker_row_id"]
                blob = " ".join(cand["look_twice_reasons"]
                                + [cand["count_check"]["verdict"],
                                   cand["date_check"]["verdict"],
                                   cand["name_note"] or ""])
                for other in ids - {mine}:
                    self.assertNotIn(str(other), blob,
                                     f"row {mine}'s evidence names row {other}; that is "
                                     f"exactly the pooled line that lost the Dow match")

    def test_the_index_line_carries_only_the_lead_rows_evidence(self):
        entry = next(e for e in self.entries if e["reference_row_id"] == SAMPLE_ID)
        lead = entry["candidates"][0]
        self.assertEqual(lead["tracker_row_id"], 900002,
                         "the row that agrees on every field must lead; the row the "
                         "pooled line described was the wrong one")
        line = next(l for l in self.text.splitlines()
                    if l.startswith("|") and "`900002`" in l and "Acme" in l)
        self.assertNotIn("news", line,
                         "the index line for row 900002 carries row 900001's source "
                         "flag; no line may describe more than one row")
        self.assertIn("`900001`", line,
                      "row 900001 is invisible on the index line — the other candidates "
                      "must be NAMED, just without their evidence")

    def test_every_candidate_row_is_named_by_id_somewhere_in_the_sheet(self):
        for entry in self.entries:
            for cand in entry["candidates"]:
                self.assertIn(f"`{cand['tracker_row_id']}`", self.text,
                              f"candidate row {cand['tracker_row_id']} appears nowhere "
                              f"in the sheet by id")


class OneRowClaimedByTwoEventsTests(unittest.TestCase):
    """Spirit filed several FL notices on one day and we hold one row per site,
    so the same row can lead two reference events. At most one can be it."""

    def _entries(self):
        def cand(rid):
            return {"tracker_row_id": rid, "tracker_event_id": 1, "tier": "exact",
                    "row_date": "2026-05-02", "look": wp.CLEAN,
                    "look_twice_reasons": []}
        return [{"reference_row_id": "warn-fl-a", "candidates": [cand(135255)],
                 "lead_row_id": 135255, "lead_look": wp.CLEAN, "other_row_ids": []},
                {"reference_row_id": "warn-fl-b", "candidates": [cand(135255)],
                 "lead_row_id": 135255, "lead_look": wp.CLEAN, "other_row_ids": []},
                {"reference_row_id": "warn-fl-c", "candidates": [cand(999)],
                 "lead_row_id": 999, "lead_look": wp.CLEAN, "other_row_ids": []}]

    def test_both_claimants_are_told_and_neither_stays_clean(self):
        entries = self._entries()
        wp._mark_rows_claimed_twice(entries)
        for entry in entries[:2]:
            cand = entry["candidates"][0]
            self.assertEqual(cand["look"], wp.LOOK_TWICE,
                             "a row proposed for two reference events still read as "
                             "clean; accepting both counts one row twice")
            self.assertEqual(entry["lead_look"], wp.LOOK_TWICE)
        self.assertEqual(entries[0]["candidates"][0]["also_proposed_for"], ["warn-fl-b"])
        self.assertEqual(entries[1]["candidates"][0]["also_proposed_for"], ["warn-fl-a"])

    def test_the_statement_names_reference_events_not_another_candidate_row(self):
        entries = self._entries()
        wp._mark_rows_claimed_twice(entries)
        reason = entries[0]["candidates"][0]["look_twice_reasons"][0]
        self.assertIn("warn-fl-b", reason)
        self.assertNotIn("999", reason,
                         "the statement names another candidate ROW; it may name other "
                         "reference EVENTS only, or it is a pooled line again")

    def test_a_row_claimed_once_is_untouched(self):
        entries = self._entries()
        wp._mark_rows_claimed_twice(entries)
        self.assertEqual(entries[2]["candidates"][0]["look"], wp.CLEAN)
        self.assertEqual(entries[2]["candidates"][0]["look_twice_reasons"], [])


class ACleanRowIsSaidToBeCleanTests(Sheet):
    def test_a_row_with_nothing_wrong_says_so(self):
        entry = next(e for e in self.entries if e["reference_row_id"] == CENSUS_ID)
        cand = entry["candidates"][0]
        self.assertEqual(cand["look"], wp.CLEAN)
        self.assertEqual(cand["look_twice_reasons"], [])
        self.assertIn(f"nothing to look twice at on row `{cand['tracker_row_id']}`",
                      self.text,
                      "a clean row was left blank; an unremarked row is indistinguishable "
                      "from an unexamined one")

    def test_the_sheet_recommends_nothing(self):
        low = self.text.lower()
        for banned in ("recommend", "we suggest", "should be accepted",
                       "likely a match", "probably"):
            self.assertNotIn(banned, low,
                             f"the sheet contains {banned!r} — stating the evidence is "
                             f"the job; moving the gate from the human is not")


class CountsAndDatesAreStatedTests(Sheet):
    def test_an_exact_count_says_exact_and_a_difference_says_by_how_much(self):
        entry = next(e for e in self.entries if e["reference_row_id"] == SAMPLE_ID)
        right = next(c for c in entry["candidates"] if c["tracker_row_id"] == 900002)
        wrong = next(c for c in entry["candidates"] if c["tracker_row_id"] == 900001)
        self.assertTrue(right["count_check"]["exact"])
        self.assertEqual(right["count_check"]["delta_vs_notice_total"], 0)
        self.assertFalse(wrong["count_check"]["exact"])
        self.assertEqual(wrong["count_check"]["delta_vs_notice_total"], -58)
        self.assertIn("-58", wrong["count_check"]["verdict"],
                      "a count that differs must say by how much, not merely that it "
                      "differs")

    def test_a_date_difference_names_the_basis_it_is_measured_on(self):
        entry = next(e for e in self.entries if e["reference_row_id"] == SAMPLE_ID)
        right = next(c for c in entry["candidates"] if c["tracker_row_id"] == 900002)
        self.assertEqual(right["date_check"]["basis"], "effective")
        self.assertEqual(right["date_check"]["days_from_notice_date"], 68)
        self.assertIn("EFFECTIVE", right["date_check"]["verdict"],
                      "WARN publishes a notice date and an effective date and this repo "
                      "distinguishes them; a gap between them is not a mismatch and the "
                      "sheet must say which basis it is reading")


class EasyOnesComeFirstTests(Sheet):
    def test_entries_are_ordered_by_how_much_there_is_to_read(self):
        ranks = [wp.RANK[e["lead_look"]] for e in self.entries]
        self.assertEqual(ranks, sorted(ranks),
                         "an event with something to look twice at sorts above an event "
                         "where every field lines up; the owner's attention belongs on "
                         "what does not line up")

    def test_the_primary_sample_comes_before_the_census(self):
        strata = [0 if e["stratum"] == "primary" else 1 for e in self.entries]
        self.assertEqual(strata, sorted(strata))


class TheEventWithNoCandidateIsItsOwnDecisionTests(Sheet):
    def test_it_is_not_filed_among_the_others(self):
        ids = {e["reference_row_id"] for e in self.entries}
        self.assertNotIn(EMPTY_ID, ids,
                         "the event the rule proposes nothing for was filed as one row "
                         "among ninety-nine near-identical accepts; it is a different "
                         "question and the owner will skim past it")
        self.assertEqual([e["reference_row_id"] for e in self.no_candidate], [EMPTY_ID])

    def test_its_section_is_above_the_index(self):
        self.assertLess(self.text.index("The event with no candidate row"),
                        self.text.index("## The index"),
                        "the one event that needs a decision of its own is below the "
                        "list of ninety-nine that do not")

    def test_the_windowless_probe_widens_the_date_and_not_the_name(self):
        """`/query?company=` is a substring LIKE. Dropping the window without
        keeping the name test turned `Wood` into `Oakwood Worldwide`."""
        ev = MANIFEST["reference_events"][1]
        rows = {1: {"id": 1, "event_id": 9, "company_name": "Nothing Held Inc.",
                    "job_count": 180, "layoff_date": "2025-01-05", "state": "TX",
                    "source_type": "warn", "source_name": "TX WARN notice",
                    "source_url": "u", "excerpt": "x"},
                2: {"id": 2, "event_id": 8, "company_name": "Something Nothing Held Co",
                    "job_count": 1, "layoff_date": "2024-02-02", "state": "TX",
                    "source_type": "warn", "source_name": "TX WARN notice",
                    "source_url": "u", "excerpt": "x"}}
        entry = wp._no_candidate_entry(ev, "primary", rows, None)
        held = [r["tracker_row_id"] for r in entry["rows_for_this_employer_at_any_date"]]
        self.assertEqual(held, [1],
                         "a row for a different employer came back once the window "
                         "stopped excluding it; that reads as evidence and is not")
        self.assertFalse(entry["rows_for_this_employer_at_any_date"][0]
                         ["in_the_match_window"],
                         "the row we hold is outside the rule's window — that is the "
                         "whole reason this event has no candidate")

    def test_it_offers_both_decisions_and_prefers_neither(self):
        section = self.text.split("## The index")[0]
        self.assertIn(f"--accept {EMPTY_ID}", section)
        self.assertIn(f"--reject {EMPTY_ID}", section)


class TheRangeIsStatedBeforeTheFirstDecisionTests(Sheet):
    def test_the_four_arithmetics_are_all_present_and_bracket_the_figure(self):
        values = [k for _, k, _ in self.arith["rows"]]
        self.assertEqual(values, sorted(values, reverse=True),
                         "the arithmetics must run from everything accepted down to "
                         "nothing accepted, so the spread is legible at a glance")
        self.assertEqual(values[-1], self.arith["editor_confirmed_today"])
        self.assertLess(self.text.index("## The range, before you start"),
                        self.text.index("## The index"))


class NoCandidateEventsAreAdjudicableTests(Harness):
    """The sheet's no-candidate section prints accept/reject commands, so the
    recorder must honour them. Until 2026-08-14 `pack_entry` scanned only
    `entries`, and the one event the rule proposed nothing for (Wood Group) was
    Refused with 'not in the adjudication pack' — the exact decision the sheet
    asked the reviewer to make."""

    def _give_the_section_a_held_row(self, row_id):
        pack = json.loads(self.pack_path.read_text(encoding="utf-8"))
        for e in pack["no_candidate"]:
            if e["reference_row_id"] == EMPTY_ID:
                e["rows_for_this_employer_at_any_date"] = [
                    {"tracker_row_id": row_id, "company_name": "Nothing Held Inc.",
                     "job_count": 180, "layoff_date": "2025-01-05"}]
        self.pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")

    def test_accepting_a_row_the_section_shows_is_recorded(self):
        self._give_the_section_a_held_row(900500)
        code, out = self.run_cli(
            "--accept", EMPTY_ID, "--reviewed-by", "D",
            "--reason", "we hold the row at another date; the window could not reach it",
            "--row-ids", "900500")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.event(EMPTY_ID)["match_decision"], "matched")
        self.assertEqual(self.ledger()["decisions"][-1]["tracker_row_ids"], [900500])

    def test_a_row_the_section_does_not_show_is_still_refused(self):
        self._give_the_section_a_held_row(900500)
        code, out = self.run_cli(
            "--accept", EMPTY_ID, "--reviewed-by", "D", "--reason", "r",
            "--row-ids", "999999")
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out)
        self.assertEqual(self.event(EMPTY_ID)["match_decision"], "not_matched",
                         "a typed id the section's evidence does not cover must not "
                         "be recordable just because the event has no candidates")


class TheRealPackTests(unittest.TestCase):
    """Against the committed files, so a hand-edit or a stale rebuild reddens CI."""

    def test_the_committed_manifest_and_ledger_verify(self):
        ok, problems = wa.verify()
        self.assertTrue(ok, "the committed WARN set has a `matched` event with no named "
                            "decision behind it:\n  " + "\n  ".join(problems))

    def test_every_pack_entry_names_at_least_one_row(self):
        pack = wa.load_pack()
        for entry in pack["entries"]:
            self.assertTrue(entry.get("candidates"),
                            f"{entry['reference_row_id']} proposes no row, so there is "
                            f"nothing to decide about it here")

    def test_the_pack_names_only_events_the_manifest_holds(self):
        pack = wa.load_pack()
        manifest = wa.load_manifest()
        known = {e["reference_row_id"] for e in
                 manifest["reference_events"] + manifest["large_event_census"]}
        named = {e["reference_row_id"] for e in pack["entries"]} | \
                {e["reference_row_id"] for e in pack.get("no_candidate") or []}
        self.assertTrue(named <= known,
                        f"the pack names events the set does not hold: "
                        f"{sorted(named - known)}")


if __name__ == "__main__":
    unittest.main()
