"""Guards for railway/self_heal.py — the draft-only self-healer's gate + guard.

Two promises are held here, offline, no network, no keys:

1. THE GATE SAYS NO to every known-expected class of red — the alarms that are
   working as designed and already have an owner. The live-data fixture is
   composed from data_integrity's OWN registries (the same ones
   ci_alert.live_data_identity reads), so a renamed invariant cannot quietly
   turn a needs-a-human failure back into something the healer thrashes on.

2. THE FORBIDDEN-PATH GUARD GOES RED on a violation. Red-before shape: the
   violation fixture must make `check` exit non-zero, and taking any single
   path off FORBIDDEN would flip the corresponding assertion.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_alert
import data_integrity
import self_heal

ROOT = Path(__file__).resolve().parents[2]


def _live_data_cause():
    """A realistic failing assertion for a live-data invariant, built from the
    registries rather than hard-coded, so it tracks renames."""
    invariant = next(i.label for i in data_integrity.INVARIANTS
                     if getattr(i, "reads_live_data", False))
    slice_label = data_integrity.HEADLINES[0].label
    return (f"AssertionError: False is not true : {invariant} | "
            f"{slice_label}: moved +93,210 with no explaining rows")


class GateSkipsTheKnownExpectedClasses(unittest.TestCase):
    """This week's real alarm classes, each refused with a reason that names
    the class — a skipped run's log must say WHY it skipped."""

    def test_a_live_data_invariant_fail_is_never_healed(self):
        heal, reason = self_heal.classify("Tests", "failure", _live_data_cause())
        self.assertFalse(heal)
        self.assertIn("LIVE-DATA", reason)
        self.assertIn("--close-incident", reason)

    def test_the_live_data_fixture_is_really_live_data(self):
        # If this fails, the fixture (or the registry) broke, and the test
        # above would be passing for the wrong reason.
        self.assertIsNotNone(ci_alert.live_data_identity(_live_data_cause()))

    def test_a_branch_failure_is_never_healed(self):
        # A red on a working branch (or a dependabot PR) has an author. The
        # healer exists for unattended breakage on main.
        heal, reason = self_heal.classify(
            "Tests", "failure", "AssertionError: something real",
            branch="feat/two-tier-headline-survey-table")
        self.assertFalse(heal)
        self.assertIn("main", reason)

    def test_a_slice_key_shaped_live_data_fail_is_never_healed(self):
        # Run 31828616421's real cause line: the invariant surfaced its snake
        # KEY, not its registry label, and the label-only match let it through.
        heal, reason = self_heal.classify(
            "Tests", "failure",
            "worldwide_all_time: CONTAINMENT FAILED on a pair this slice is "
            "part of, baseline deliberately NOT advanced")
        self.assertFalse(heal)
        self.assertIn("LIVE-DATA", reason)

    def test_any_red_of_the_live_data_workflow_is_never_healed(self):
        # Whatever the cause line looks like: that workflow's only job is
        # evaluating the live site.
        heal, reason = self_heal.classify(
            "Live data-integrity check", "failure",
            "KeyError: 'entries'")
        self.assertFalse(heal)
        self.assertIn("LIVE-DATA", reason)

    def test_a_self_timeout_is_never_healed(self):
        # Self-timeouts arrive as conclusion `cancelled` (see ci_alert
        # _SELF_TIMEOUT); the gate refuses everything that is not `failure`.
        heal, reason = self_heal.classify(
            "Archive WARN sources to Wayback", "cancelled",
            "the job cancelled ITSELF on timeout-minutes")
        self.assertFalse(heal)
        self.assertIn("cancelled", reason)

    def test_success_and_startup_failure_are_not_healed(self):
        for conclusion in ("success", "startup_failure", "timed_out", ""):
            heal, _ = self_heal.classify("Tests", conclusion, "whatever")
            self.assertFalse(heal, conclusion)

    def test_a_host_outage_shaped_failure_is_never_healed(self):
        for cause in (
            "HTTP 504 from /alert: <html>Gateway Time-out</html>",
            "curl: (22) The requested URL returned error: 503",
            "could not reach /alert: timed out",
            "urllib.error.URLError: <urlopen error [Errno 111] Connection refused>",
            "skipped 'site is in its deploy maintenance window (HTTP 503)'",
        ):
            heal, reason = self_heal.classify("WARN import", "failure", cause)
            self.assertFalse(heal, cause)
            self.assertIn("host-outage", reason)

    def test_the_alarm_channel_is_never_healed(self):
        for workflow in ("CI failure alert", "Alert drain", "Self-heal"):
            heal, _ = self_heal.classify(workflow, "failure",
                                         "AssertionError: something real")
            self.assertFalse(heal, workflow)

    def test_a_new_code_shaped_failure_IS_healable(self):
        heal, reason = self_heal.classify(
            "Tests", "failure",
            "AssertionError: False is not true : Spirit US-2026=11069: "
            "news-vs-WARN dedup regressed")
        self.assertTrue(heal)
        self.assertIn("healable", reason)

    def test_a_failure_with_no_cause_line_is_still_healable(self):
        # A missing log degrades the prompt's detail, never the decision to
        # look: the healer reads the run itself.
        heal, _ = self_heal.classify("Tests", "failure", "")
        self.assertTrue(heal)


class TheFingerprintIsTheBudgetLedger(unittest.TestCase):
    def test_drifting_numbers_are_one_cause_and_one_branch(self):
        a = self_heal.branch_name("Tests", "Spirit US-2026=11069: dedup regressed")
        b = self_heal.branch_name("Tests", "Spirit US-2026=11071: dedup regressed")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith(self_heal.BRANCH_PREFIX))

    def test_different_assertions_are_different_branches(self):
        a = self_heal.branch_name("Tests", "Spirit dedup regressed")
        b = self_heal.branch_name("Tests", "Boeing suppressed to zero")
        self.assertNotEqual(a, b)

    def test_the_same_cause_in_two_workflows_is_two_branches(self):
        a = self_heal.branch_name("Tests", "the same line")
        b = self_heal.branch_name("Data quality report", "the same line")
        self.assertNotEqual(a, b)


class TheForbiddenPathGuard(unittest.TestCase):
    """A prompt is a request; the diff check is the fact."""

    VIOLATIONS = [
        "railway/spend.py",
        "railway/headline_incidents.json",
        "railway/alert_outbox.json",
        "railway/requirements.lock",
        "railway/requirements-min.lock",
        "docs/HANDOFF.md",
        ".github/workflows/self-heal.yml",
    ]

    def test_every_forbidden_path_is_caught(self):
        for path in self.VIOLATIONS:
            self.assertEqual(self_heal.violations([path]), [path])

    def test_a_benign_fix_passes(self):
        self.assertEqual(self_heal.violations(
            ["railway/extractor.py", "railway/tests/test_extractor.py",
             "wordpress-plugin/ai-layoff-tracker/includes/api.php"]), [])

    def test_check_exits_red_on_the_violation_fixture(self):
        # The red-before shape: this is the exit code the guard job fails on.
        with redirect_stdout(io.StringIO()) as out:
            code = self_heal.main(["check", "--files",
                                   "railway/extractor.py", "railway/spend.py"])
        self.assertEqual(code, 1)
        self.assertIn("railway/spend.py", out.getvalue())

    def test_check_exits_green_on_a_benign_fixture(self):
        with redirect_stdout(io.StringIO()):
            code = self_heal.main(["check", "--files", "railway/extractor.py"])
        self.assertEqual(code, 0)

    def test_the_forbidden_list_names_real_paths(self):
        # A forbidden path that no longer exists is a guard rotting in place
        # (self-heal.yml itself is created alongside this test).
        for pattern in self_heal.FORBIDDEN:
            if any(ch in pattern for ch in "*?["):
                continue
            self.assertTrue((ROOT / pattern).exists(), pattern)


class TheWorkflowFileKeepsItsShape(unittest.TestCase):
    """Text-level pins on .github/workflows/self-heal.yml, matching how
    test_dependency_pinning reads workflows."""

    src = (ROOT / ".github" / "workflows" / "self-heal.yml").read_text(
        encoding="utf-8")

    def test_the_action_is_pinned_to_a_full_commit_sha(self):
        import re
        uses = re.findall(r"uses:\s*anthropics/claude-code-action@(\S+)", self.src)
        self.assertEqual(len(uses), 2, "one healer step and one reviewer step")
        for ref in uses:
            self.assertRegex(ref, r"^[0-9a-f]{40}$",
                             "the action must be pinned to a 40-hex commit SHA, "
                             "not a tag a maintainer can move")

    def test_one_healer_at_a_time(self):
        self.assertIn("concurrency:", self.src)
        self.assertIn("group: self-heal", self.src)
        self.assertIn("cancel-in-progress: false", self.src)

    def test_the_pr_is_a_draft_and_a_human_merges(self):
        self.assertIn("--draft", self.src)
        self.assertIn("gh pr ready", self.src)

    def test_the_kill_switch_exists(self):
        self.assertIn("SELF_HEAL_DISABLED", self.src)

    def test_the_dormant_notice_names_the_secret(self):
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", self.src)
        self.assertIn("DORMANT", self.src)

    def test_the_guard_runs_the_real_check(self):
        self.assertIn("self_heal.py check", self.src)

    def test_the_prompt_forbids_what_the_guard_forbids(self):
        # The prompt and FORBIDDEN must not drift apart: a path the guard
        # fails on must be one the healer was told about.
        for pattern in self_heal.FORBIDDEN:
            self.assertIn(pattern, self.src, pattern)


if __name__ == "__main__":
    unittest.main()
