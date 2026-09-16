"""No US WARN recall figure may be typed where it can be computed.

The precedent is `tests/test_cadence_is_derived.py`, and the incident behind it
is the same shape: the ingest cadence halved, the surfaces that COMPUTED their
copy followed, and every surface with the number typed into it went on saying
the old one -- live, on a methodology page that contradicted itself four lines
apart. Recall has exactly that exposure now that there are two waves and a
pooled figure that neither wave's own document can compute.

So the results document carries a GENERATED block, and this file fails when the
committed block disagrees with what the measurement files say.

**The staleness guard is proved by MUTATION, not by a clean run.** A checker
that has only ever seen agreement is itself untested; two guards in this repo
passed for months with a blind spot that made their clean zero worthless. The
test below edits a figure in a copy of the document and asserts the checker
catches it.

No network, no keys.
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warn_recall_pooled as P                                    # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


class TheCommittedBlocksAreNotStale(unittest.TestCase):
    def test_every_render_target_agrees_with_the_measurements(self):
        self.assertEqual(P.check(), 0,
                         "a committed figure block disagrees with the measurement "
                         "files; run python3 railway/warn_recall_pooled.py --render")

    def test_the_guard_catches_a_figure_edited_by_hand(self):
        """MUTATION. Without this, a clean run proves nothing."""
        target = P.RENDER_TARGETS[0]
        original = target.read_text(encoding="utf-8")
        block = P.render_block()
        digits = re.search(r"(\d+)/(\d+) = ", block)
        self.assertIsNotNone(digits, "the block carries no figure to mutate")
        with tempfile.TemporaryDirectory() as tmp:
            backup = Path(tmp) / "doc.md"
            shutil.copy2(target, backup)
            try:
                mutated = original.replace(
                    f"{digits.group(1)}/{digits.group(2)} = ",
                    f"{int(digits.group(1)) + 1}/{digits.group(2)} = ", 1)
                self.assertNotEqual(mutated, original, "the mutation did not apply")
                target.write_text(mutated, encoding="utf-8")
                self.assertEqual(P.check(), 1,
                                 "a hand-edited figure passed the staleness check, "
                                 "which means the check is not checking")
            finally:
                shutil.copy2(backup, target)
        self.assertEqual(target.read_text(encoding="utf-8"), original)
        self.assertEqual(P.check(), 0, "the mutation test did not restore the file")


class TheTwoBASESAreNeverConflated(unittest.TestCase):
    def test_the_block_labels_the_machine_figure_as_an_upper_bound(self):
        block = P.render_block()
        self.assertIn("Machine upper bound", block)
        self.assertIn("Editor-confirmed", block)

    def test_an_unadjudicated_wave_gets_an_explicit_callout(self):
        f = P.derive()
        block = P.render_block(f)
        if all(f["adjudicated_by_wave"].values()):
            self.skipTest("UNKNOWN, NOT RUN: every wave is adjudicated, so there "
                          "is no zero-by-construction numerator to explain")
        self.assertIn("zero BY CONSTRUCTION", block,
                      "a wave with an unadjudicated numerator is shown as 0% with "
                      "no explanation, which reads as a coverage collapse")

    def test_the_adjudicated_only_row_has_its_own_denominator(self):
        f = P.derive()
        all_states = f["pooled_equal_allocation"]["editor_confirmed"]["n"]
        adjudicated_only = f["pooled_adjudicated_sets_only"]["n"]
        self.assertLessEqual(adjudicated_only, all_states)
        if adjudicated_only != all_states:
            self.assertNotEqual(
                adjudicated_only, 0,
                "the adjudicated-only row exists so a reader can take ONE true "
                "number out of this block")

    def test_unknown_events_are_reported_and_never_folded_in(self):
        f = P.derive()
        self.assertIn("unknown_by_wave", f)
        self.assertIn("Unreachable / UNKNOWN", P.render_block(f))


class ItCannotReachAnotherSetsFiles(unittest.TestCase):
    def test_it_writes_only_its_render_targets(self):
        body = Path(P.__file__).read_text(encoding="utf-8")
        code = "\n".join(l for l in body.splitlines()
                         if not l.strip().startswith("#"))
        code = re.sub('"' * 3 + ".*?" + '"' * 3, "", code, flags=re.S)
        for token in ("MATCHED_FLOOR", "write_measurement", "recall_adjudications"):
            self.assertNotIn(token, code,
                             f"the derivation module references {token!r}; it "
                             f"reads measurements and writes documents, nothing else")

    def test_it_reads_a_wave_that_is_not_yet_committed_without_crashing(self):
        # Adding a wave to WAVES before its files exist must not break the two
        # that do -- an absent measurement is UNKNOWN, not a failure.
        original = P.WAVES
        try:
            P.WAVES = original + (
                ("wave 99", REPO_ROOT / "docs" / "nope.json",
                 REPO_ROOT / "railway" / "nope.json"),)
            figures = P.derive()
            self.assertNotIn("wave 99", figures["measured_at"])
        finally:
            P.WAVES = original


class TheDocumentSaysWhereItsNumbersCameFrom(unittest.TestCase):
    def test_the_results_document_names_the_generator(self):
        for target in P.RENDER_TARGETS:
            text = target.read_text(encoding="utf-8")
            self.assertIn("warn_recall_pooled.py", text)
            self.assertIn(P.BEGIN, text)
            self.assertIn(P.END, text)

    def test_the_miss_causes_file_uses_only_the_definitions_buckets(self):
        import warn_miss_causes as C
        if not C.CAUSES_PATH.exists():
            self.skipTest("UNKNOWN, NOT RUN: no causes file is committed")
        data = json.loads(C.CAUSES_PATH.read_text(encoding="utf-8"))
        for cause in data["causes"]:
            self.assertIn(cause["cause"], C.BUCKETS, cause["id"])
            self.assertTrue(cause["line"].strip(),
                            f"{cause['id']} has a bucket and no one-line cause, so "
                            f"the result is a score and not a worklist")

    def test_every_miss_cause_is_evidenced_or_says_it_is_not(self):
        import warn_miss_causes as C
        if not C.CAUSES_PATH.exists():
            self.skipTest("UNKNOWN, NOT RUN: no causes file is committed")
        data = json.loads(C.CAUSES_PATH.read_text(encoding="utf-8"))
        for cause in data["causes"]:
            if cause["cause"] == "stored_unmatched":
                self.assertIsNotNone(cause["evidence"].get("tracker_row_id"),
                                     f"{cause['id']} claims we hold the row and "
                                     f"does not name it")
            elif cause["cause"] == "UNKNOWN":
                self.assertIn("cannot", cause["line"].lower(),
                              f"{cause['id']} is UNKNOWN without saying what could "
                              f"not be established -- UNKNOWN is a verdict, not a "
                              f"bucket of convenience")


if __name__ == "__main__":
    unittest.main()
