"""ops_status.py [4e] — the visibility half of the alert-routing change.

From 2026-08-20 a pull-request failure on a branch that is not main is ROUTED
to ops_status instead of the owner's inbox. That is only defensible while the
routed thing is genuinely visible, because silence and INVISIBILITY are
different things and this repo has already paid for confusing them.

These assertions are about the LISTING. The routing decision itself is pinned
in test_ci_alert.py::BranchFailuresAreRoutedNotSilenced. Offline, no network.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_alert
import ops_status


def _run(name, branch, conclusion, created, event="pull_request",
         status="completed"):
    return {"name": name, "headBranch": branch, "conclusion": conclusion,
            "createdAt": created, "event": event, "status": status,
            "url": f"https://github.com/dk-forge/ai-layoff-tracker/actions/runs/{abs(hash(created)) % 10**8}"}


def _with(runs):
    return mock.patch.object(ops_status, "_gh",
                             return_value=(True, json.dumps(runs), ""))


class RoutedFailuresAreListed(unittest.TestCase):

    def test_a_routed_failure_is_listed_with_its_age(self):
        """Not sent, but not invisible. This is the whole bargain."""
        with _with([_run("Plugin version collision", "claude/kind-matsumoto-2c6fdd",
                         "failure", "2026-08-19T22:14:00Z")]):
            lines, unknown = ops_status._routed_branch_failures()
        self.assertFalse(unknown)
        body = "\n".join(lines)
        self.assertIn("Plugin version collision", body)
        self.assertIn("claude/kind-matsumoto-2c6fdd", body)
        self.assertRegex(body, r"\(\d+\.\d+[hd] ago\)")

    def test_a_branch_that_was_fixed_is_not_an_open_item(self):
        """Only the NEWEST run per workflow+branch counts. Listing every
        historical red run rebuilds the wall of noise this change removes."""
        with _with([_run("Tests", "claude/side", "success", "2026-08-20T03:00:00Z"),
                    _run("Tests", "claude/side", "failure", "2026-08-19T22:00:00Z")]):
            lines, unknown = ops_status._routed_branch_failures()
        self.assertFalse(unknown)
        self.assertIn("none", "\n".join(lines).lower())

    def test_main_and_scheduled_runs_are_not_listed_here(self):
        """They were mailed. Listing them here would say they were suppressed."""
        with _with([_run("Tests", "main", "failure", "2026-08-19T22:00:00Z",
                         event="push"),
                    _run("Data quality report", "claude/side", "failure",
                         "2026-08-19T22:00:00Z", event="schedule")]):
            lines, unknown = ops_status._routed_branch_failures()
        self.assertFalse(unknown)
        self.assertIn("none", "\n".join(lines).lower())

    def test_an_in_flight_run_is_not_a_failure(self):
        with _with([_run("Tests", "claude/side", None, "2026-08-19T22:00:00Z",
                         status="in_progress")]):
            lines, unknown = ops_status._routed_branch_failures()
        self.assertIn("none", "\n".join(lines).lower())

    def test_gh_being_unavailable_is_UNKNOWN_and_never_a_pass(self):
        """Absence of a signal is not a pass. Three states, not two."""
        with mock.patch.object(ops_status, "_gh",
                               return_value=(False, "", "gh is not installed")):
            lines, unknown = ops_status._routed_branch_failures()
        self.assertTrue(unknown)
        self.assertIn("UNKNOWN", "\n".join(lines))
        self.assertNotIn("none", "\n".join(lines).lower())

    def test_the_listing_never_contributes_to_the_exit_code(self):
        """A session's own branch being red is not a call for the owner. If
        this ever starts appending to `issues`, ops_status exits 2 on somebody
        else's work in progress and stops being read."""
        source = (Path(__file__).resolve().parents[1] / "ops_status.py").read_text()
        start = source.index("[4e] ROUTED BRANCH FAILURES")
        section = source[start:source.index("# 4c. The audience", start)]
        code = [ln.strip() for ln in section.splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
        self.assertFalse([ln for ln in code if "issues.append" in ln],
                         "[4e] must never make ops_status exit non-zero")

    def test_the_two_modules_agree_on_what_a_red_run_is(self):
        """One vocabulary. Two components reading one event with two of them is
        how the healer went blind to self-timeouts (TECHLOG 2026-08-18)."""
        self.assertEqual(set(ops_status._ROUTED_CONCLUSIONS), set(ci_alert.ALERTABLE))


if __name__ == "__main__":
    unittest.main()
