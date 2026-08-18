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
import re
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

    def test_a_cancellation_from_outside_the_job_is_never_healed(self):
        # A superseded push or a concurrency group produces `cancelled` with no
        # timeout line anywhere in the annotations, and nothing is wrong.
        for cause in ("", "The operation was canceled.",
                      "##[error]The operation was canceled."):
            heal, reason = self_heal.classify("Tests", "cancelled", cause)
            self.assertFalse(heal, cause)
            self.assertIn("OUTSIDE the job", reason)

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


class ASelfTimeoutReachesTheHealer(unittest.TestCase):
    """The blind spot of 2026-08-18, armed.

    A job killed by its own `timeout-minutes` is reported by GitHub as
    `cancelled`, not `timed_out` or `failure`. ci_alert.py knew that and mailed
    it as CI SELF-TIMEOUT; self_heal.py did not and skipped it. "Tests"
    self-killed at 15m0s on main (run 32099117561) and six Self-heal runs in the
    next half hour were `skipped` with no PR opened.

    Both halves are pinned here: a self-timeout IS healed, an ordinary
    cancellation is NOT, and the discrimination is ci_alert's ONE function
    rather than a second copy that can drift back apart.
    """

    # Verbatim shape of the annotation a self-killed job leaves behind.
    ANNOTATION = "The job has exceeded the maximum execution time of 15m0s"

    def test_the_annotation_a_self_killed_job_leaves_is_recognised(self):
        cause = ci_alert.self_timeout_cause(self.ANNOTATION)
        self.assertIsNotNone(cause)
        self.assertIn("15m0s", cause)

    def test_the_cause_line_round_trips_back_to_a_self_timeout_verdict(self):
        # The gate is handed the cause STRING, not the annotation, so the
        # verdict must survive the trip. It did not: the annotation says "has
        # exceeded" and the cause line says "it exceeded", so re-matching the
        # regex would have quietly answered "ordinary cancellation".
        cause = ci_alert.self_timeout_cause(self.ANNOTATION)
        self.assertTrue(ci_alert.is_self_timeout_cause(cause))
        self.assertFalse(ci_alert.is_self_timeout_cause(""))
        self.assertFalse(ci_alert.is_self_timeout_cause(
            "##[error]The operation was canceled."))

    def test_a_self_timeout_on_main_IS_healable(self):
        cause = ci_alert.self_timeout_cause(self.ANNOTATION)
        heal, reason = self_heal.classify("Tests", "cancelled", cause)
        self.assertTrue(heal, reason)
        self.assertIn("healable", reason)

    def test_a_self_timeout_on_a_branch_is_still_that_branch_s_problem(self):
        cause = ci_alert.self_timeout_cause(self.ANNOTATION)
        heal, reason = self_heal.classify(
            "Tests", "cancelled", cause, branch="claude/some-work")
        self.assertFalse(heal)
        self.assertIn("branch", reason)

    def test_a_self_timeout_of_the_alarm_channel_is_still_never_healed(self):
        cause = ci_alert.self_timeout_cause(self.ANNOTATION)
        for workflow in ("CI failure alert", "Alert drain", "Self-heal"):
            heal, _ = self_heal.classify(workflow, "cancelled", cause)
            self.assertFalse(heal, workflow)

    def test_the_discrimination_is_ci_alerts_and_is_not_copied(self):
        # ONE definition. self_heal must not carry its own timeout regex or its
        # own "exceeded the maximum execution time" string — that second copy
        # is exactly the drift that produced this bug in the first place.
        src = (ROOT / "railway" / "self_heal.py").read_text(encoding="utf-8")
        self.assertNotIn("exceeded the maximum", src)
        self.assertIn("ci_alert.is_self_timeout_cause", src)
        self.assertIn("ci_alert.self_timeout_of_run", src)

    def test_ci_alert_exports_the_shared_entry_point(self):
        self.assertTrue(callable(getattr(ci_alert, "self_timeout_of_run", None)))


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


class TheMergeGateResolvesUnknownToDraft(unittest.TestCase):
    """The owner delegated the CLICK (2026-08-14), not the conditions."""

    def test_only_an_unambiguous_looks_sound_merges(self):
        marker = self_heal.VERDICT_MARKER
        self.assertEqual(self_heal.review_verdict(
            [f"{marker} LOOKS SOUND\nevidence..."]), "LOOKS SOUND")
        self.assertEqual(self_heal.review_verdict(
            [f"{marker} DO NOT MERGE\n..."]), "DO NOT MERGE")
        # no marker at all
        self.assertIsNone(self_heal.review_verdict(["lgtm!"]))
        # two markers in one comment is ambiguous, and ambiguous never merges
        self.assertIsNone(self_heal.review_verdict(
            [f"{marker} LOOKS SOUND\n{marker} DO NOT MERGE"]))

    def test_the_latest_verdict_wins(self):
        marker = self_heal.VERDICT_MARKER
        self.assertEqual(self_heal.review_verdict(
            [f"{marker} LOOKS SOUND\n...", f"{marker} NEEDS WORK\n..."]),
            "NEEDS WORK")

    def test_a_workflow_edit_is_never_automerged(self):
        ok, reason = self_heal.automergeable_paths(
            ["railway/extractor.py", ".github/workflows/tests.yml"])
        self.assertFalse(ok)
        self.assertIn(".github/workflows/tests.yml", reason)

    def test_a_forbidden_path_is_never_automerged(self):
        ok, _ = self_heal.automergeable_paths(["railway/spend.py"])
        self.assertFalse(ok)

    def test_an_empty_diff_is_never_automerged(self):
        ok, _ = self_heal.automergeable_paths([])
        self.assertFalse(ok)

    def test_a_source_and_test_diff_is_automergeable(self):
        ok, reason = self_heal.automergeable_paths(
            ["railway/extractor.py", "railway/tests/test_extractor.py",
             "wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php"])
        self.assertTrue(ok, reason)

    def test_suite_failures_reads_both_test_runners(self):
        out = (
            "FAIL: test_a (tests.test_x.C.test_a)\n"
            "ERROR: test_b (tests.test_y.D.test_b)\n"
            "FAILED tests/test_z.py::test_c - AssertionError\n"
            "Ran 100 tests\n")
        self.assertEqual(self_heal.suite_failures(out), {
            "test_a (tests.test_x.C.test_a)",
            "test_b (tests.test_y.D.test_b)",
            "tests/test_z.py::test_c"})

    def test_a_standing_red_is_subtracted_and_a_new_red_blocks(self):
        # The set semantics the gate runs on: preview ⊆ baseline merges,
        # anything new does not.
        baseline = {"live_data_incident"}
        self.assertEqual(({"live_data_incident"} - baseline), set())
        self.assertEqual(({"live_data_incident", "fresh_break"} - baseline),
                         {"fresh_break"})


class TheHealingLedger(unittest.TestCase):
    """Best-effort, append-only, newest-first — and never able to fail the
    heal (record returns 1 at worst; the workflow step warns and stays
    green)."""

    def _record(self, tmp, **over):
        import tempfile
        args = ["record", "--pr", "7", "--workflow", "Tests",
                "--merge-sha", "abc1234",
                "--run-url", "https://github.com/x/y/actions/runs/1",
                "--cause", "AssertionError: the real line",
                "--files", "railway/extractor.py",
                "--healing-log", str(tmp / "HEALING-LOG.md"),
                "--techlog", str(tmp / "TECHLOG.md")]
        with redirect_stdout(io.StringIO()):
            return self_heal.main(args)

    def test_it_creates_the_ledger_with_the_revert_header(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "TECHLOG.md").write_text("# Tech Log\n\n## old entry\n")
            self.assertEqual(self._record(tmp), 0)
            ledger = (tmp / "HEALING-LOG.md").read_text()
            self.assertIn("git revert", ledger)
            self.assertIn("SELF_HEAL_AUTOMERGE_DISABLED", ledger)
            self.assertIn("PR #7", ledger)
            self.assertIn("abc1234", ledger)

    def test_entries_go_newest_first_in_both_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "TECHLOG.md").write_text("# Tech Log\n\n## old entry\n")
            self._record(tmp)
            tech = (tmp / "TECHLOG.md").read_text()
            self.assertLess(tech.index("self-heal: auto-merged"),
                            tech.index("## old entry"))
            self._record(tmp)
            ledger = (tmp / "HEALING-LOG.md").read_text()
            self.assertEqual(ledger.count("- revert:"), 2,
                             "a second heal APPENDS; it never replaces the "
                             "first (keep-both is the conflict rule too)")

    def test_a_missing_docs_dir_is_a_warning_not_a_crash(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / "not" / "there"
            code = self._record(tmp)
            self.assertEqual(code, 1)  # the CALLER downgrades this to a warning


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

    def test_the_job_condition_admits_a_cancelled_run(self):
        # An expression cannot read check-run annotations, so the workflow must
        # let `cancelled` through to the gate STEP, which can. If this reverts
        # to `failure`-only, every self-timeout goes unhealed and silent again.
        self.assertIn("github.event.workflow_run.conclusion == 'cancelled'",
                      self.src)
        self.assertIn("github.event.workflow_run.conclusion == 'failure'",
                      self.src)

    def test_the_healer_is_told_not_to_answer_a_timeout_by_moving_the_wall(self):
        self.assertIn("RAISING THE CEILING IS NOT", self.src)

    def test_the_cli_transcript_is_kept_even_when_the_healer_declines(self):
        # The healer's commonest outcome is a green run that opened nothing.
        # `if: failure()` preserved nothing for exactly that case.
        self.assertIn(
            "if: always() && steps.gate.outputs.heal == 'yes'", self.src)
        self.assertIn("claude-execution-output.json", self.src)

    def test_every_job_condition_is_a_balanced_expression(self):
        """PyYAML is not a validator for these, and this cost a real outage.

        On 2026-08-18 the `heal` condition shipped with ONE closing paren too
        many. The file parsed as YAML - the condition is just a string to YAML -
        so every local check was green, and GitHub refused to load the whole
        workflow: no Self-heal run at all for fifteen minutes, on a healer that
        had just been fixed to catch more. An invalid workflow does not fail
        loudly; it stops existing.

        Balance is not full expression validation, but it is the class of
        mistake an editor of this file actually makes.
        """
        conditions = re.findall(r"^\s*if: >-\n((?:^\s{6,}.*\n)+)",
                                self.src, re.M)
        conditions += re.findall(r"^\s*if: (?!>-)(.+)$", self.src, re.M)
        self.assertGreaterEqual(len(conditions), 4,
                                "the `if:` conditions stopped being findable")
        for cond in conditions:
            depth = 0
            for ch in cond:
                depth += (ch == "(") - (ch == ")")
                self.assertGreaterEqual(depth, 0,
                                        f"closes a paren it never opened:\n{cond}")
            self.assertEqual(depth, 0, f"unbalanced parens:\n{cond}")

    def test_the_kill_switch_exists(self):
        self.assertIn("SELF_HEAL_DISABLED", self.src)

    def test_the_dormant_notice_names_the_secret(self):
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", self.src)
        self.assertIn("DORMANT", self.src)

    def test_the_guard_runs_the_real_check(self):
        self.assertIn("self_heal.py check", self.src)

    def test_the_workflow_parses_and_the_merge_is_gated_by_the_guard(self):
        """The wiring auto-merge depends on, asserted structurally rather
        than by grepping: `automerge` must NEED the guard and the review, or
        a fix could merge without either having run."""
        try:
            import yaml
        except ImportError:  # local runs without the full lock installed
            self.skipTest("pyyaml is in requirements.lock; CI asserts this")
        parsed = yaml.safe_load(self.src)
        jobs = parsed["jobs"]
        self.assertEqual(set(jobs), {"heal", "guard", "review", "automerge",
                                     "summary"})
        needs = jobs["automerge"]["needs"]
        for required in ("heal", "guard", "review"):
            self.assertIn(required, needs)
        gate = jobs["automerge"]["if"]
        self.assertIn("needs.guard.result == 'success'", gate)
        self.assertIn("needs.review.result == 'success'", gate)
        self.assertIn("SELF_HEAL_AUTOMERGE_DISABLED", gate)

    def test_the_automerge_kill_switch_is_separate_from_the_healer_switch(self):
        # Two switches on purpose: one keeps the drafts and returns the click
        # to a human, the other stops the healer entirely.
        self.assertIn("SELF_HEAL_AUTOMERGE_DISABLED", self.src)
        self.assertIn("SELF_HEAL_DISABLED", self.src)

    def test_the_owner_authorization_is_recorded_in_the_workflow(self):
        self.assertIn("2026-08-14", self.src)
        self.assertIn("owner", self.src.lower())

    def test_the_reviewer_is_asked_for_the_machine_readable_verdict(self):
        self.assertIn(self_heal.VERDICT_MARKER, self.src)

    def test_the_heal_is_recorded_in_the_ledgers(self):
        self.assertIn("self_heal.py record", self.src)
        self.assertIn("docs/HEALING-LOG.md", self.src)

    def test_the_prompt_forbids_what_the_guard_forbids(self):
        # The prompt and FORBIDDEN must not drift apart: a path the guard
        # fails on must be one the healer was told about.
        for pattern in self_heal.FORBIDDEN:
            self.assertIn(pattern, self.src, pattern)


if __name__ == "__main__":
    unittest.main()
