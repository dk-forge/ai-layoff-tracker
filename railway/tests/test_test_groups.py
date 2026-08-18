"""The Tests workflow runs this suite as TWO parallel jobs. Prove the split
loses nothing.

A split suite has exactly one interesting failure mode: a module that falls
out of both halves and stops running while CI stays green. Nothing in a green
run would say so — the assertions it holds simply never execute. So the
properties pinned here are TOTALITY and DISJOINTNESS against the same glob
`unittest discover` uses, plus the two ends of the wiring: every group the
runner defines is actually invoked by the workflow, and the workflow does not
invoke a group the runner does not define.

The split itself is DERIVED (a module that imports `cdp` drives a real Chrome)
precisely so that it cannot drift. A new browser test lands in the browser job
on the day it is written, with nobody remembering to add it to a list.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_tests  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = Path(__file__).resolve().parent
WORKFLOW = (ROOT / ".github" / "workflows" / "tests.yml").read_text(
    encoding="utf-8")


class TheSplitLosesNothing(unittest.TestCase):

    def test_the_groups_cover_every_discovered_module(self):
        covered = []
        for group in run_tests.GROUPS:
            covered.extend(run_tests.modules_in(group))
        self.assertEqual(sorted(covered), run_tests.all_modules(),
                         "a module in neither group would stop running while "
                         "CI stayed green")

    def test_no_module_is_in_two_groups(self):
        covered = []
        for group in run_tests.GROUPS:
            covered.extend(run_tests.modules_in(group))
        self.assertEqual(len(covered), len(set(covered)))

    def test_all_modules_is_the_same_glob_discover_uses(self):
        # `unittest discover -s tests -p "test_*.py"`.
        on_disk = sorted(p.stem for p in TESTS_DIR.glob("test_*.py"))
        self.assertEqual(run_tests.all_modules(), on_disk)
        self.assertIn(Path(__file__).stem, on_disk)

    def test_neither_group_is_empty(self):
        for group in run_tests.GROUPS:
            self.assertTrue(run_tests.modules_in(group), group)

    def test_an_unknown_group_is_refused_rather_than_silently_empty(self):
        with self.assertRaises(SystemExit):
            run_tests.modules_in("browserr")

    def test_an_empty_group_exits_non_zero(self):
        # A runner that selects nothing and exits 0 is a green job that ran no
        # tests. Driven for real, with the module list emptied, because that is
        # the only way to know the exit code rather than believe it.
        with patch.object(run_tests, "all_modules", return_value=[]):
            self.assertEqual(run_tests.main(["--group", "rest"]), 2)


class TheSplitIsDerivedFromTheSource(unittest.TestCase):

    def test_a_module_that_imports_cdp_is_rendered(self):
        rendered = run_tests.modules_in("rendered")
        self.assertIn("test_rendered_contrast", rendered)
        self.assertIn("test_tap_targets", rendered)
        for stem in rendered:
            self.assertTrue(run_tests.drives_a_browser(stem), stem)

    def test_a_module_that_does_not_touch_cdp_is_not_rendered(self):
        for stem in run_tests.modules_in("rest"):
            self.assertFalse(run_tests.drives_a_browser(stem), stem)

    def test_a_mention_in_prose_does_not_move_a_module(self):
        # The match is anchored at statement position, so a docstring saying
        # "we do not import cdp here" does not silently reroute a module.
        self.assertIsNone(run_tests._IMPORTS_CDP.search(
            '"""This module deliberately does not import cdp."""\\n'))
        self.assertIsNone(run_tests._IMPORTS_CDP.search(
            "# import cdp would start a browser\\n"))
        self.assertIsNotNone(run_tests._IMPORTS_CDP.search(
            "from cdp import Browser\\n"))
        self.assertIsNotNone(run_tests._IMPORTS_CDP.search("    import cdp\\n"))


class TheWorkflowRunsBothHalves(unittest.TestCase):

    def test_every_group_is_actually_invoked(self):
        # One job definition, one matrix axis: the workflow runs whatever the
        # axis lists, so the axis is what has to equal GROUPS. A group missing
        # from the matrix is a group of tests that never runs, with nothing
        # red to say so.
        axis = re.search(r"^\s*group:\s*\[([^\]]*)\]", WORKFLOW, re.M)
        self.assertIsNotNone(axis, "the matrix no longer has a `group:` axis")
        listed = {g.strip().strip("'\"") for g in axis.group(1).split(",")}
        self.assertEqual(listed, set(run_tests.GROUPS))
        self.assertIn("run_tests.py --group ${{ matrix.group }}", WORKFLOW)

    def test_one_half_failing_does_not_cancel_the_other(self):
        # fail-fast would CANCEL the surviving job, turning one ordinary red
        # into a `cancelled` conclusion that ci_alert.py and self_heal.py then
        # have to interpret — noise on the channel reporting the red.
        self.assertRegex(WORKFLOW, r"fail-fast:\s*false")

    def test_the_live_data_verdict_steps_are_not_duplicated(self):
        # ci_alert.live_data_was_evaluated scans .jobs[].steps[] across the
        # WHOLE run. Two copies of these steps, in two jobs, would let the
        # half that does not run the live checks answer for the half that does.
        for step in ("Live-data invariants were evaluated",
                     "Live-data invariants were NOT evaluated"):
            self.assertEqual(WORKFLOW.count(f"name: {step}"), 1, step)

    def test_the_annotation_filter_covers_both_halves(self):
        # The sed that turns ::error:: into ;;error:: so a green run does not
        # annotate itself with a description of a simulated world. Both halves
        # print test output; the matrix gives them one shared step definition,
        # so ONE occurrence is the correct count — but it has to be on the step
        # that runs the tests, not somewhere else in the file.
        run_step = WORKFLOW.split("- name: Run railway unit tests", 1)
        self.assertEqual(len(run_step), 2, "the test-running step was renamed")
        body = run_step[1].split("- name:", 1)[0]
        self.assertIn("s/^([[:space:]]*)::(error|warning|notice)", body)
        self.assertIn("run_tests.py --group", body)


if __name__ == "__main__":
    unittest.main()
