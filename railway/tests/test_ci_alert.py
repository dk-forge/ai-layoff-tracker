"""Guards for railway/ci_alert.py — the CI-failure-to-email path.

The log fixtures below are REAL lines from the eight consecutive red runs of
2026-07-30 (the Spirit Airlines dedup regression), tab-prefixed exactly as
`gh run view --log-failed` emits them. Offline, no network, no keys.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_alert


def _log(*content_lines):
    """Wrap bare content in the job/step/timestamp columns Actions prepends."""
    return "\n".join(
        f"railway-tests\tUNKNOWN STEP\t2026-07-30T20:55:34.930{i:04d}Z {line}"
        for i, line in enumerate(content_lines))


SPIRIT = _log(
    "======================================================================",
    "FAIL: test_spirit_counts_once (test_dedup_live.DedupLiveRegression.test_spirit_counts_once)",
    "----------------------------------------------------------------------",
    "Traceback (most recent call last):",
    '  File "/home/runner/work/ai-layoff-tracker/ai-layoff-tracker/railway/tests/test_dedup_live.py", line 96, in test_spirit_counts_once',
    '    self.assertTrue(0 < jobs < 11000, f"Spirit US-2026={jobs}: news-vs-WARN dedup regressed")',
    "AssertionError: False is not true : Spirit US-2026=11069: news-vs-WARN dedup regressed",
    "Ran 334 tests in 23.465s",
    "FAILED (failures=1)",
    # Real trailing stdout noise from the same run — none of it is the cause.
    "EDGAR warning: EDGAR_USER_AGENT is not set — SEC rejects anonymous requests",
    "GDELT 429 (attempt 1/3), retrying after 42s",
    "##[error]Process completed with exit code 1.",
    # Runner teardown, which must never be mistaken for diagnostic output.
    "Post job cleanup.",
    "[command]/usr/bin/git version",
    "Cleaning up orphan processes",
)


class CauseExtraction(unittest.TestCase):
    def test_pulls_the_assertion_that_carries_its_own_diagnosis(self):
        cause, context = ci_alert.extract_cause(SPIRIT)
        self.assertEqual(
            cause,
            "AssertionError: False is not true : Spirit US-2026=11069: "
            "news-vs-WARN dedup regressed")
        # The test's own name is worth carrying: the exception says what is
        # wrong, the header says where to look.
        self.assertTrue(any("test_spirit_counts_once" in c for c in context), context)

    def test_never_settles_for_the_useless_generic_line(self):
        """'Process completed with exit code 1' is true, useless, and is exactly
        the alert the owner already ignores."""
        for text in (SPIRIT, _log("some output", "##[error]Process completed with exit code 1.")):
            cause, _ = ci_alert.extract_cause(text)
            self.assertNotIn("Process completed with exit code", cause)

    def test_teardown_noise_is_never_the_cause(self):
        cause, _ = ci_alert.extract_cause(SPIRIT)
        for noise in ("orphan processes", "git version", "Post job cleanup"):
            self.assertNotIn(noise, cause)

    def test_falls_back_to_the_last_real_output_when_nothing_matches(self):
        """A shell job that just exits non-zero still beats 'a job failed'."""
        cause, _ = ci_alert.extract_cause(
            _log("uploading batch 3", "curl: (22) The requested URL returned 503",
                 "##[error]Process completed with exit code 22."))
        self.assertIn("503", cause)

    def test_an_empty_log_degrades_instead_of_crashing(self):
        self.assertEqual(ci_alert.extract_cause(""), ("", []))
        self.assertEqual(ci_alert.extract_cause(None), ("", []))


class DedupeByCause(unittest.TestCase):
    """The single most important property. Eight identical emails would train
    the owner to filter this sender, which recreates the original problem."""

    def _key(self, cause, workflow="Tests", branch="main"):
        return ci_alert.build_alert(
            repo="dk-forge/ai-layoff-tracker", workflow=workflow, branch=branch,
            event="push", run_url="", run_id=1, cause=cause, context=[])[2]

    def test_the_same_defect_with_a_drifting_number_is_one_cause(self):
        a = self._key("AssertionError: False is not true : Spirit US-2026=11069: news-vs-WARN dedup regressed")
        b = self._key("AssertionError: False is not true : Spirit US-2026=11071: news-vs-WARN dedup regressed")
        self.assertEqual(a, b, "a count that drifted by 2 must not mail twice")

    def test_a_genuinely_different_assertion_is_a_different_cause(self):
        a = self._key("AssertionError: False is not true : Spirit US-2026=11069: news-vs-WARN dedup regressed")
        b = self._key("AssertionError: ['data_integrity'] is not false : These collectors call home")
        self.assertNotEqual(a, b, "a second, separate breakage must not be swallowed")

    def test_the_same_cause_in_two_workflows_is_two_causes(self):
        a = self._key("AssertionError: boom", workflow="Tests")
        b = self._key("AssertionError: boom", workflow="WARN import")
        self.assertNotEqual(a, b)

    def test_timestamps_shas_and_runner_paths_normalise_away(self):
        base = "FileNotFoundError: /home/runner/work/ai-layoff-tracker/ai-layoff-tracker/x.json"
        self.assertEqual(
            ci_alert.normalise(base),
            ci_alert.normalise(
                "FileNotFoundError: /home/runner/work/ai-layoff-tracker/ai-layoff-tracker/x.json"))
        self.assertNotIn("2026-07-30T20:55:34", ci_alert.normalise("failed at 2026-07-30T20:55:34Z"))
        self.assertNotIn("a1b2c3d4e5", ci_alert.normalise("bad sha a1b2c3d4e5f6"))

    def test_resolve_scope_is_the_prefix_of_the_key_it_must_clear(self):
        """The load-bearing coupling. If these two drift, every failure alarm
        becomes permanent and every recovery email is lost — silently, because
        both halves keep returning 200."""
        key = self._key("AssertionError: boom", workflow="Tests", branch="main")
        scope = f"{ci_alert._slug('Tests')}:{ci_alert._slug('main', 32)}"
        self.assertTrue(key.startswith(scope + ":"),
                        f"{key!r} would never be cleared by resolve_scope {scope!r}")


# ---------------------------------------------------------------------------
# The six emails of 2026-08-10/11, and the real strings that caused them.
# ---------------------------------------------------------------------------
#
# Copied verbatim out of `gh run view <id> --log-failed` for the seven red runs
# below, which between them mailed the owner six times about ONE open incident.
# Invented strings would have proved nothing here: the whole defect lives in
# details of the real shape (the branch each run happened to be on, and a
# sentence that outgrew the extractor's 400-character cut), and every one of
# those details is easy to omit when you write the fixture yourself.
#
# The run id is kept beside each string so a later session can re-fetch it.

_US_INCIDENT_TAIL = (
    " (6,968,670 -> 7,061,{jobs_tail}). The rows that changed carry at most "
    "{largest} and the largest single row is 60,000, so NO ROW EXPLAINS THIS. "
    "Something re-scored rows that were already published: check the last "
    "reconcile-supersets run, any /bulk-purge, and the corrections log")

# run 31421971041 (main), 31421827146 (main), 31421748713 (docs/handoff-external-review)
REAL_US_93210 = (
    "AssertionError: No headline moves without rows to explain it: United States "
    "jobs, all time: +93,210 jobs over 3.0d on +18 entries"
    + _US_INCIDENT_TAIL.format(jobs_tail="880", largest="34,730"))

# run 31450792070 (main), 31450680641 (feat/filed-basis-default),
# 31448285345 (feat/changed-rows-endpoint) — a day later, every figure moved
REAL_US_93290 = (
    "AssertionError: No headline moves without rows to explain it: United States "
    "jobs, all time: +93,290 jobs over 3.3d on +19 entries"
    + _US_INCIDENT_TAIL.format(jobs_tail="960", largest="36,659"))

# run 31425792582 (claude/sticky-headline-incidents) — the sticky ledger's
# "opened Nd ago (<timestamp>)" prefix and its closing instructions take this to
# 741 characters, where the old 400-character cut fell in a different place.
REAL_US_STICKY = (
    "AssertionError: No headline moves without rows to explain it: United States "
    "jobs, all time: OPEN INCIDENT, opened 0d ago (2026-08-10T19:36:59Z): "
    "+93,210 jobs over 3.0d on +18 entries"
    + _US_INCIDENT_TAIL.format(jobs_tail="880", largest="34,730")
    + " | today's reading: unchanged | This stays FAIL until a human closes it: "
      "`python3 data_integrity.py --close-incident us_all_time --reviewed-by "
      "<who> --reason <what you found> --rows <ids> --replacement-jobs <n> "
      "--replacement-entries <n>`. Time, later rows and a stale baseline do not "
      "close it")

#: (cause, branch) exactly as each of the seven runs presented it.
REAL_SIX_EMAILS = (
    (REAL_US_93210, "docs/handoff-external-review"),
    (REAL_US_93210, "main"),
    (REAL_US_93210, "main"),
    (REAL_US_STICKY, "claude/sticky-headline-incidents"),
    (REAL_US_93290, "feat/changed-rows-endpoint"),
    (REAL_US_93290, "feat/filed-basis-default"),
    (REAL_US_93290, "main"),
)


def _key(cause, workflow="Tests", branch="main"):
    return ci_alert.build_alert(
        repo="dk-forge/ai-layoff-tracker", workflow=workflow, branch=branch,
        event="push", run_url="", run_id=1, cause=cause, context=[])[2]


class OneLiveIncidentIsOneAlarm(unittest.TestCase):
    """A live-data invariant reads the SITE, not the checkout. Every branch that
    runs the suite is looking at the same one wrong number, so the branch that
    happened to notice must not mint a second alarm."""

    def test_the_seven_real_runs_collapse_to_one_key(self):
        keys = {_key(cause, branch=branch) for cause, branch in REAL_SIX_EMAILS}
        self.assertEqual(
            len(keys), 1,
            "one open incident mailed the owner six times in seven hours; these "
            f"are the real strings and they still produce {len(keys)} keys: {sorted(keys)}")

    def test_the_key_carries_no_branch(self):
        """The actual root cause. `scope = workflow:branch` gave the SAME
        incident five keys across five branches while `normalise` was doing its
        job perfectly — the six real messages are byte-identical after it."""
        self.assertEqual(ci_alert.normalise(REAL_US_93210),
                         ci_alert.normalise(REAL_US_93290),
                         "the numbers were never the problem")
        for _cause, branch in REAL_SIX_EMAILS:
            self.assertNotIn(ci_alert._slug(branch, 32),
                             _key(REAL_US_93210, branch=branch).split(":")[1],
                             f"branch {branch!r} is still in the scope")

    def test_it_survives_the_sentence_growing_past_the_display_cut(self):
        """741 characters vs 396. The sticky-incident prefix moved the old
        400-char truncation point, so the tail differed and so did the hash."""
        self.assertGreater(len(REAL_US_STICKY), 400)
        self.assertEqual(_key(REAL_US_STICKY), _key(REAL_US_93210))

    # --- guard the guard: what must still be a SEPARATE email ---------------

    def test_a_different_slice_of_the_same_invariant_is_a_different_alarm(self):
        worldwide = REAL_US_93210.replace("United States jobs, all time",
                                          "Worldwide jobs, all time")
        self.assertNotEqual(_key(worldwide), _key(REAL_US_93210),
                            "a second headline going wrong is new information")

    def test_a_different_invariant_on_the_same_slice_is_a_different_alarm(self):
        other = REAL_US_93210.replace(
            "No headline moves without rows to explain it",
            "No single row carries a headline")
        self.assertNotEqual(_key(other), _key(REAL_US_93210))

    def test_a_second_slice_joining_the_first_is_a_different_alarm(self):
        """_roll_up joins every slice at the worst state with '; '. Two failing
        headlines must not hide behind the one that failed first."""
        both = (REAL_US_93210 + "; Worldwide jobs, all time: +200,000 jobs over "
                "1.0d on +2 entries")
        self.assertNotEqual(_key(both), _key(REAL_US_93210))

    def test_an_ordinary_code_failure_keeps_its_branch(self):
        """The narrowness that stops this becoming a catch-all. A test that
        fails only on one branch is that branch's defect, and folding it into
        main's alarm would hide it."""
        spirit = ("AssertionError: False is not true : Spirit US-2026=11069: "
                  "news-vs-WARN dedup regressed")
        self.assertNotEqual(_key(spirit, branch="main"),
                            _key(spirit, branch="feat/whatever"))

    def test_a_local_invariant_keeps_its_branch_too(self):
        """`reads_live_data = False` means the checkout decides it, so the
        branch is load-bearing. 'Gold-set recall has not fallen' is one."""
        recall = ("AssertionError: Gold-set recall has not fallen: 27/30 on the "
                  "SEC gold set, floor is 29")
        self.assertNotEqual(_key(recall, branch="main"),
                            _key(recall, branch="feat/whatever"))

    # --- the plumbing the key depends on ------------------------------------

    def test_the_key_is_one_the_endpoint_will_accept(self):
        key = _key(REAL_US_93210)
        self.assertRegex(key, ci_alert.KEY_SAFE)

    def test_a_green_run_clears_the_branch_free_scope_too(self):
        """The coupling: /alert clears by key PREFIX. If the resolve posted on a
        green run does not cover the scope the alarm was raised under, the alarm
        is permanent and the RECOVERED email never comes."""
        key = _key(REAL_US_93210, workflow="Tests")
        scope = ci_alert.live_data_scope("Tests")
        self.assertTrue(key.startswith(scope + ":"),
                        f"{key!r} would never be cleared by resolve_scope {scope!r}")
        printed = io.StringIO()
        with redirect_stdout(printed):
            ci_alert.main(["--run-id", "1", "--workflow", "Tests",
                           "--conclusion", "success", "--branch", "main",
                           "--dry-run"])
        self.assertIn(scope, printed.getvalue())

    def test_the_vocabulary_comes_from_data_integrity_not_a_copy(self):
        """A hand-copied label list goes stale in silence, and a stale one here
        means a renamed invariant quietly returns to mailing once per branch."""
        import data_integrity
        invariants, slices = ci_alert._live_data_vocabulary()
        self.assertIn("No headline moves without rows to explain it", invariants)
        self.assertIn("United States jobs, all time", slices)
        live = {i.label for i in data_integrity.INVARIANTS
                if getattr(i, "reads_live_data", False)}
        self.assertEqual(set(invariants), live)

    def test_the_alerter_reads_the_whole_sentence_but_prints_the_same_400(self):
        """Widening the DEFAULT would have reformatted two other surfaces —
        ops_status [4] and the weekly noise email both print this string raw —
        to fix a third. So the default is untouched and only the alerter asks
        for more."""
        log = _log(REAL_US_STICKY, "##[error]Process completed with exit code 1.")
        self.assertEqual(len(ci_alert.extract_cause(log)[0]), 400)
        wide, _ = ci_alert.extract_cause(log, limit=ci_alert.ALERT_CAUSE_LIMIT)
        self.assertEqual(wide, REAL_US_STICKY)
        self.assertEqual(_key(wide), _key(REAL_US_93210))
        # The email body is byte-for-byte what it was: still the first 400.
        _subject, body, _key_ = ci_alert.build_alert(
            repo="r", workflow="Tests", branch="main", event="push",
            run_url="", run_id=1, cause=wide, context=[])
        self.assertIn(REAL_US_STICKY[:400], body)
        self.assertNotIn(REAL_US_STICKY[:401], body)

    def test_an_unrecognised_message_is_not_a_live_data_incident(self):
        self.assertIsNone(ci_alert.live_data_identity("AssertionError: boom"))
        self.assertIsNone(ci_alert.live_data_identity(""))
        self.assertIsNone(ci_alert.live_data_identity(None))


class Behaviour(unittest.TestCase):
    def _run(self, argv, **env):
        import os
        keys = ("WP_SITE_URL", "WP_API_KEY", "RESEND_API_KEY",
                "ALERT_ENVELOPE", "ALERT_STATE_PATH")
        old = {k: os.environ.get(k) for k in keys}
        os.environ.update({k: v for k, v in env.items()})
        for k in keys:
            if k not in env:
                os.environ.pop(k, None)
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                code = ci_alert.main(argv)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return code, buf.getvalue()

    def test_cancelled_by_something_else_is_still_not_alertable(self):
        """Runs are cancelled routinely by superseded pushes and concurrency
        groups. Mailing about those is the noise that gets a sender filtered,
        and admitting the self-timeout class must not cost that quiet."""
        with mock.patch.object(ci_alert, "fetch_annotations",
                               return_value="The operation was canceled."):
            code, out = self._run(["--run-id", "1", "--workflow", "Tests",
                                   "--conclusion", "cancelled"])
        self.assertEqual(code, 0)
        self.assertIn("outside the job", out)

    def test_a_self_timeout_is_alertable_even_though_it_reads_as_cancelled(self):
        """THE HOLE THIS CLOSES.

        A job killed by its own `timeout-minutes` concludes `cancelled`, not
        `timed_out`, so the blanket "cancelled is noise" rule made a whole class
        of permanent failure silent. Measured in this repo:

          * "Archive WARN sources to Wayback" (weekly, timeout-minutes: 20)
            died at 20m21s on 2026-07-27 and 20m19s on 2026-08-03 — every run
            it has ever had. It has never once completed, and no email fired.
          * "Data quality report" (daily, timeout-minutes: 10) died at 10m27s
            twice against a normal runtime of ~45 seconds.

        Meanwhile the archive re-check invariant sat at 8.6 days against a
        10-day bound: the promise the pages make to readers was one missed run
        from breaking, and the thing that would have broken it was reporting
        nothing at all.
        """
        annotations = ("The job has exceeded the maximum execution time of 20m0s\n"
                       "The operation was canceled.")
        with mock.patch.object(ci_alert, "fetch_annotations",
                               return_value=annotations):
            code, out = self._run(["--run-id", "1", "--workflow",
                                   "Archive WARN sources to Wayback",
                                   "--conclusion", "cancelled", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("CI SELF-TIMEOUT", out)
        self.assertIn("20m0s", out)
        self.assertIn("cancelled ITSELF", out)

    def test_the_self_timeout_marker_is_read_from_the_annotations(self):
        """It is NOT in the log. A self-killed job's log ends on a bare
        '##[error]The operation was canceled.', character-for-character what an
        externally cancelled job prints, and `--log-failed` returns nothing at
        all because a cancelled run has no failed STEP. Verified against run
        30799948006, whose annotations carry the line and whose log does not."""
        self.assertIsNone(ci_alert.self_timeout_cause(
            "2026-08-03T09:26:01.3465610Z ##[error]The operation was canceled."))
        self.assertIsNotNone(ci_alert.self_timeout_cause(
            "The job has exceeded the maximum execution time of 20m0s"))

    def test_a_self_timeout_clears_on_the_same_workflows_green_run(self):
        """The scope must not fork by class, or a workflow that starts passing
        again leaves its self-timeout alert open forever."""
        _s, _b, key = ci_alert.build_alert(
            repo="r", workflow="Archive WARN sources to Wayback", branch="main",
            event="schedule", run_url="", run_id="1",
            cause="the job cancelled ITSELF on timeout-minutes",
            context=[], label="CI SELF-TIMEOUT")
        scope = f"{ci_alert._slug('Archive WARN sources to Wayback')}:{ci_alert._slug('main', 32)}"
        self.assertTrue(key.startswith(scope + ":"))

    def test_the_listener_admits_cancelled_so_the_script_can_judge_it(self):
        """The filter and the script have to agree. A `cancelled` run screened
        out in YAML never reaches the annotation check at all, and the class
        goes back to being invisible with the code to handle it still present."""
        yml = (Path(__file__).resolve().parents[2] / ".github" / "workflows"
               / "ci-alert.yml").read_text()
        self.assertIn('"cancelled"', yml)
        self.assertIn("checks: read", yml,
                      "annotations need checks:read; without it the self-timeout "
                      "marker cannot be read and every cancellation reads as routine")

    def test_a_failure_with_no_credentials_is_loud_not_silent(self):
        """A quiet 'no key so I did nothing' is the same class of lie as a green
        run over destroyed work."""
        code, out = self._run(["--run-id", "1", "--workflow", "Tests",
                               "--conclusion", "failure", "--dry-run"])
        self.assertEqual(code, 0)  # dry-run is explicitly asked for
        code, out = self._run(["--run-id", "1", "--workflow", "Tests",
                               "--conclusion", "failure"])
        self.assertEqual(code, 1, "a missing key must redden this run")
        self.assertIn("::error::", out)

    def test_an_undeliverable_alert_is_held_and_does_not_redden_the_run(self):
        """THE 2026-07-31 DEFECT, in one assertion.

        Bluehost 504'd under /blog/ for seven minutes. In the sibling tracker —
        same alerter, same host — the alarm failed four times saying "HTTP 504
        from /alert", because /alert is a route on the host it reports about.
        Exiting 1 there turned one outage into four EXTRA red runs, each of
        which read as "the alerter is broken" when the alerter was working and
        the host was down.

        A held alert is a kept promise. It exits 0, and it says so loudly.
        """
        import json
        import tempfile

        calls = []

        def boom(site, key, payload, sleep=None):
            calls.append(payload)
            return False, "HTTP 504 from /alert", True

        with tempfile.TemporaryDirectory() as tmp:
            envelope = f"{tmp}/held.json"
            orig, ci_alert.post_alert = ci_alert.post_alert, boom
            try:
                code, out = self._run(
                    ["--run-id", "1", "--workflow", "Tests",
                     "--conclusion", "failure", "--envelope", envelope],
                    RESEND_API_KEY="k")
            finally:
                ci_alert.post_alert = orig
            self.assertEqual(code, 0,
                             "an outage must not manufacture a red run of its own")
            self.assertIn("::warning::", out)
            self.assertIn("HELD", out)
            with open(envelope) as fh:
                held = json.load(fh)
        self.assertEqual(held["key"], calls[0]["dedupe_key"])
        self.assertTrue(held["payload"]["subject"].startswith("CI RED:"))

    def test_an_undeliverable_alert_with_nowhere_to_go_is_red(self):
        """The one alerting failure still worth a red run: it could not be
        delivered AND could not be held, so nobody is going to be told."""
        def boom(site, key, payload, sleep=None):
            return False, "HTTP 504 from /alert", True

        orig, ci_alert.post_alert = ci_alert.post_alert, boom
        try:
            code, out = self._run(["--run-id", "1", "--workflow", "Tests",
                                   "--conclusion", "failure"],
                                  RESEND_API_KEY="k")
        finally:
            ci_alert.post_alert = orig
        self.assertEqual(code, 1)
        self.assertIn("::error::", out)
        self.assertIn("nobody will be told", out.lower())

    def test_transient_failures_are_retried_inside_the_run(self):
        """A single bad response from a shared host is not an outage. Retrying
        is the cheap half of the fix; the outbox is the half that survives one."""
        answers = [(False, "HTTP 503", True), (False, "HTTP 503", True),
                   (True, "emailed the owner", False)]
        orig, ci_alert._post_once = ci_alert._post_once, lambda *a, **k: answers.pop(0)
        try:
            ok, _note, _t = ci_alert.post_alert("https://x.invalid", "k", {},
                                                sleep=lambda _s: None)
        finally:
            ci_alert._post_once = orig
        self.assertTrue(ok)
        self.assertEqual(answers, [], "it stopped retrying before it succeeded")

    def test_a_settled_refusal_is_not_retried(self):
        tries = []

        def once(*a, **k):
            tries.append(1)
            return False, "HTTP 404", False

        orig, ci_alert._post_once = ci_alert._post_once, once
        try:
            ci_alert.post_alert("https://x.invalid", "k", {}, sleep=lambda _s: None)
        finally:
            ci_alert._post_once = orig
        self.assertEqual(len(tries), 1,
                         "retrying a settled no only makes the run longer")

    def test_success_posts_a_resolve_and_never_a_dedupe_key(self):
        calls = []

        def capture(site, key, payload, sleep=None):
            calls.append(payload)
            return True, "emailed the owner", False

        orig, ci_alert.post_alert = ci_alert.post_alert, capture
        try:
            # Hermetic ledger: this asserts the FIRST resolve is the branch
            # scope, which only holds when no live-data incident is open in the
            # real committed ledger (a stale one there reorders/renames the
            # posted resolves). The behaviour under test is scope selection, not
            # whatever incident happens to be open on the machine running it.
            with mock.patch.object(ci_alert, "live_data_was_evaluated",
                                   lambda *a: True), \
                    mock.patch.object(ci_alert.alert_state, "open_alarms",
                                      lambda: []):
                code, _ = self._run(["--run-id", "1", "--workflow", "Tests",
                                     "--conclusion", "success", "--branch", "main"],
                                    RESEND_API_KEY="k")
        finally:
            ci_alert.post_alert = orig
        self.assertEqual(code, 0)
        self.assertEqual(calls[0]["resolve_scope"], "tests:main")
        self.assertNotIn("dedupe_key", calls[0])


class ASkippedCheckIsNotARecovery(unittest.TestCase):
    """One number, three emails: RED, RECOVERED, RED, in 33 minutes.

    THE INCIDENT (2026-08-13/14). `archive_recheck_cadence` failed on main at
    23:37 and mailed under `tests:live.data:2e215caae5bac21b`. It failed again on
    fix/reader-freshness-content at 00:06 with the identical sentence — and the
    branch-free scope handled that exactly as designed: same key, and the alert
    endpoint suppressed it as already open. That half was never broken.

    What re-armed the alarm was the run in between. `Tests` went GREEN on main at
    00:00:28 (run 31755860626) with every live check reporting

        skipped 'site is in its deploy maintenance window (HTTP 503)'

    and the alerter posted `resolve tests:live.data`, which mailed RECOVERED for
    a number nobody had read. The next red re-raised the same key and mailed
    again. A check that did not run is UNKNOWN, not a pass — the rule the
    dashboard and the digest have followed for months, applied at last to the one
    reader that still inferred a pass from silence.
    """

    def _resolve_scopes(self, evaluated):
        calls = []

        def capture(site, key, payload, sleep=None):
            calls.append(payload["resolve_scope"])
            return True, "emailed the owner", False

        import os
        old = {k: os.environ.get(k) for k in ("RESEND_API_KEY",)}
        os.environ.update({"RESEND_API_KEY": "k"})
        orig, ci_alert.post_alert = ci_alert.post_alert, capture
        try:
            # Hermetic: this class tests SCOPE SELECTION (does a skipped vs
            # evaluated run clear the live.data scope), so it must not read the
            # real committed ledger — an open live-data incident there would make
            # _recovery_plan resolve that specific key and this assertion depend
            # on live state (and it did: a stale archive incident reddened it,
            # and because that reds main, main never went green to clear it).
            with mock.patch.object(ci_alert, "live_data_was_evaluated",
                                   lambda *a: evaluated), \
                    mock.patch.object(ci_alert.alert_state, "open_alarms",
                                      lambda: []), \
                    redirect_stdout(io.StringIO()) as out:
                ci_alert.main(["--run-id", "1", "--workflow", "Tests",
                               "--conclusion", "success", "--branch", "main"])
        finally:
            ci_alert.post_alert = orig
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return calls, out.getvalue()

    def test_a_run_whose_live_checks_skipped_does_not_clear_the_incident(self):
        scopes, printed = self._resolve_scopes(evaluated=False)
        self.assertNotIn(
            "tests:live.data", scopes,
            "a green run in which every live check SKIPPED just mailed "
            "RECOVERED about a number it never read")
        self.assertIn("tests:main", scopes,
                      "the branch-scoped recovery is unaffected: whatever failed "
                      "in THIS checkout really is green again")
        self.assertIn("UNKNOWN", printed)

    def test_a_run_that_really_checked_still_clears_it(self):
        scopes, _ = self._resolve_scopes(evaluated=True)
        self.assertEqual(scopes, ["tests:main", "tests:live.data"],
                         "an incident that nothing can clear earns a STILL "
                         "FAILING reminder a fortnight later")

    def test_a_workflow_that_publishes_no_verdict_is_unchanged(self):
        """Most workflows never read the live site. They keep today's behaviour;
        this change is narrow to the one state that was being guessed."""
        scopes, _ = self._resolve_scopes(evaluated=None)
        self.assertEqual(scopes, ["tests:main", "tests:live.data"])

    # -- the channel itself ------------------------------------------------

    def _jobs(self, *steps):
        payload = "\n".join(f"{conclusion}\t{name}" for conclusion, name in steps)
        return mock.patch("subprocess.run", lambda *a, **kw: mock.Mock(
            returncode=0, stdout=payload, stderr=""))

    def test_the_evaluated_step_reads_as_evaluated(self):
        with self._jobs(("success", "Run railway unit tests"),
                        ("success", ci_alert.LIVE_DATA_STEP)):
            self.assertIs(ci_alert.live_data_was_evaluated("r", "1"), True)

    def test_the_not_evaluated_step_reads_as_not_evaluated(self):
        with self._jobs(("success", "Run railway unit tests"),
                        ("skipped", ci_alert.LIVE_DATA_STEP),
                        ("success", ci_alert.LIVE_DATA_STEP_UNKNOWN)):
            self.assertIs(ci_alert.live_data_was_evaluated("r", "1"), False)

    def test_a_run_with_neither_step_is_unknown_not_false(self):
        with self._jobs(("success", "Deploy")):
            self.assertIsNone(ci_alert.live_data_was_evaluated("r", "1"))

    def test_an_unreadable_jobs_api_never_raises(self):
        with mock.patch("subprocess.run", side_effect=OSError("no gh")), \
                redirect_stdout(io.StringIO()):
            self.assertIsNone(ci_alert.live_data_was_evaluated("r", "1"))

    def test_the_workflow_runs_the_steps_the_alerter_looks_for(self):
        """The parity that makes the channel real. A rename on either side turns
        RECOVERED back into a mail sent on no evidence, silently."""
        yml = (Path(__file__).resolve().parents[2] / ".github" / "workflows"
               / "tests.yml").read_text(encoding="utf-8")
        for name in (ci_alert.LIVE_DATA_STEP, ci_alert.LIVE_DATA_STEP_UNKNOWN):
            self.assertIn(f"- name: {name}\n", yml,
                          f"tests.yml no longer runs a step named {name!r}, so "
                          f"ci_alert.py can never learn whether the live checks "
                          f"ran")
        self.assertIn("LIVE_DATA_VERDICT_FILE", yml,
                      "the suite is not being told where to write the verdict, "
                      "so the two steps above decide on an empty file")


class OneIncidentAcrossTwoBranches(unittest.TestCase):
    """The half that was NOT broken, pinned so it stays that way.

    Read off the real runs: `Tests` failed on main (31754238064) and on
    fix/reader-freshness-content (31756204615) with the same archive assertion
    and different numbers. Both produced `tests:live.data:2e215caae5bac21b`.
    """

    MAIN = ("Unarchived sources are re-checked on the promised cadence: oldest "
            "un-archived attempt 3.7d ago (177 pending, 3,381 not yet in Wayback) "
            "— inside the 10d bound TODAY, but 3,511 due at a measured 244/day = "
            "14.4d cycle, 15.4d worst age, past the 8d projected bound (7d promise "
            "+ 1d run granularity). The re-check promise is about to become false "
            "and the slack is what is hiding it; raise throughput in "
            "archive-backfill.yml")
    BRANCH = MAIN.replace("177 pending", "202 pending").replace(
        "3,511 due", "3,536 due").replace("244/day", "231/day").replace(
        "14.4d cycle, 15.4d", "15.3d cycle, 16.3d")

    def test_the_same_live_assertion_on_two_branches_is_one_alert(self):
        first = ci_alert.build_alert(
            repo="r", workflow="Tests", branch="main", event="push",
            run_url="u", run_id="1", cause=self.MAIN, context=[])[2]
        second = ci_alert.build_alert(
            repo="r", workflow="Tests", branch="fix/reader-freshness-content",
            event="push", run_url="u", run_id="2", cause=self.BRANCH, context=[])[2]
        self.assertEqual(first, second,
                         "the archive assertion is keyed per branch again — the "
                         "owner gets one email per branch that happens to notice "
                         "the same one wrong number")
        self.assertTrue(first.startswith("tests:live.data:"), first)


# ---------------------------------------------------------------------------
# A log marker is never a cause.
#
# REAL LINES from `collect` run 32307688627 (sibling tracker, main,
# 2026-08-19T22:48Z), tab-prefixed exactly as `gh run view --log-failed` emits
# them. That run mailed an alert whose entire WHAT FAILED section read
# "##[endgroup]": no bucket matched the log, so the fallback took the last
# non-empty body line, and the last non-empty body line was a log-group marker.
# ---------------------------------------------------------------------------

def _collect_log(*content_lines):
    return "\n".join(
        f"collect\tUNKNOWN STEP\t2026-08-19T22:48:43.76{i:02d}000Z {line}"
        for i, line in enumerate(content_lines))


ENDGROUP_RUN = _collect_log(
    "[sec_form_d] searching SEC filings",
    "[sec_form_d] 0 fetched, 0 filtered out, 0 going to the classifier",
    "[sec_form_d] found=0 stored=0 duplicate=0 rejected=0 deferred=0",
    "##[warning][guardrail] amount/3a2a9b08 Nvidia $150,000,000,000 - held back, never published, red in 139h",
    "##[warning][guardrail] amount/26c3c9ab Lovable $13,300,000,000 - held back, never published, red in 91h",
    "[guardrails] Answer them:  python3 guardrails.py",
    "",
    "[publish] sent=0 stored=0 duplicate=0 errors=0",
    "##[endgroup]",
    "##[error]Process completed with exit code 1.",
    "##[group]Run git config user.name  'talent-intel-bot'",
    "Cleaning up orphan processes",
)

#: The degenerate case: the failing step printed nothing but markers. There is
#: genuinely no cause to be had, and the only honest answer is to say so.
MARKERS_ONLY = _collect_log(
    "##[group]Run python3 run_collect.py",
    "##[endgroup]",
    "   ",
    "##[section]Finishing",
    "##[error]Process completed with exit code 1.",
    "Cleaning up orphan processes",
)


class AMarkerIsNeverACause(unittest.TestCase):

    def test_the_endgroup_run_no_longer_reports_a_log_marker(self):
        """The regression, on the log that shipped it."""
        cause, context = ci_alert.extract_cause(ENDGROUP_RUN)
        self.assertNotIn("##[", cause)
        self.assertTrue(ci_alert.is_cause_line(cause), repr(cause))
        # The documented fallback is unchanged: the last REAL output line still
        # beats "a job failed". Only formatting was ever the defect.
        self.assertEqual(cause, "[publish] sent=0 stored=0 duplicate=0 errors=0")
        for line in context:
            self.assertNotIn("##[", line)

    def test_a_step_that_printed_only_markers_extracts_nothing(self):
        cause, context = ci_alert.extract_cause(MARKERS_ONLY)
        self.assertEqual(cause, "")
        self.assertEqual(context, [])

    def test_markers_and_whitespace_are_refused_one_by_one(self):
        for line in ("##[endgroup]", "##[group]", "##[section]", "  ##[endgroup]  ",
                     # a fold's NAME says what was about to happen, not what broke
                     "##[group]Run python3 run_collect.py", "##[section]Finishing",
                     "##[debug]", "##[error]", "", "   ", "\t"):
            self.assertFalse(ci_alert.is_cause_line(line), repr(line))
        # ...and a marker that CARRIES a message is still a cause.
        for line in ("##[error]AssertionError: 3 != 4",
                     "##[warning]guardrail red in 139h",
                     "[publish] sent=0 stored=0"):
            self.assertTrue(ci_alert.is_cause_line(line), repr(line))

    def test_no_cause_mails_the_truth_instead_of_the_marker(self):
        """'I could not read a cause, here is the run' is actionable.
        '##[endgroup]' is not."""
        cause, context = ci_alert.extract_cause(MARKERS_ONLY)
        subject, body, key = ci_alert.build_alert(
            repo="dk-forge/x", workflow="collect", branch="main", event="schedule",
            run_url="https://github.com/dk-forge/x/actions/runs/32307688627",
            run_id=32307688627, cause=cause, context=context)
        self.assertNotIn("##[", subject)
        self.assertNotIn("##[", body)
        self.assertIn("no error line could be extracted", subject)
        self.assertIn("actions/runs/32307688627", body)
        self.assertIn("could be read out of this run's log", body)

    def test_a_marker_cause_can_no_longer_become_a_dedup_key(self):
        """The half of this defect that made no noise.

        `cause` is what build_alert fingerprints. When it was "##[endgroup]",
        every unrelated no-cause failure of one workflow+branch hashed to the
        SAME key, and the second one was suppressed as a duplicate of the
        first. One email per cause quietly became one email per workflow.
        The real failures below share nothing but the marker.
        """
        def key_for(*content):
            cause, context = ci_alert.extract_cause(_collect_log(*content))
            return ci_alert.build_alert(
                repo="dk-forge/x", workflow="collect", branch="main",
                event="schedule", run_url="u", run_id=1,
                cause=cause, context=context)[2]

        a = key_for("[publish] sent=0 stored=0 duplicate=0 errors=0",
                    "##[endgroup]", "##[error]Process completed with exit code 1.")
        b = key_for("[sec_edgar] DEGRADED: 11 candidates, none stored",
                    "##[endgroup]", "##[error]Process completed with exit code 1.")
        self.assertNotEqual(a, b, "two different failures collapsed onto one key")


class BranchFailuresAreRoutedNotSilenced(unittest.TestCase):
    """A pull-request failure on a side branch goes to ops_status [4e].

    Four categories must NEVER be routed, and each has its own assertion below,
    because every one of them is a way this change could quietly become the
    filtered alarm CLAUDE.md is written against.
    """

    # A real live-data invariant label, read from data_integrity's registry, so
    # a rename breaks this test rather than silently returning that class to
    # one email per branch.
    LIVE = ("Published breakdowns reconcile with their own headline "
            "| United States jobs, all time: recorded 1,234 jobs")

    # --- the one case that is routed -------------------------------------
    def test_a_pull_request_failure_on_a_side_branch_is_routed(self):
        routed, why = ci_alert.route_to_ops_status(
            event="pull_request", branch="claude/kind-matsumoto-2c6fdd",
            cause="plugin version collision: ALT_VERSION did not move")
        self.assertTrue(routed, why)

    # --- category 1: main, always ----------------------------------------
    def test_the_same_failure_on_main_still_pages(self):
        routed, why = ci_alert.route_to_ops_status(
            event="pull_request", branch="main",
            cause="plugin version collision: ALT_VERSION did not move")
        self.assertFalse(routed, why)

    def test_no_conclusion_or_cause_can_route_a_main_failure(self):
        """main is checked FIRST and unconditionally. Nothing below it applies."""
        for cause in ("", "##[endgroup]", self.LIVE, "AssertionError: 3 != 4"):
            for event in ("pull_request", "push", "schedule", "workflow_dispatch"):
                routed, why = ci_alert.route_to_ops_status(
                    event=event, branch="main", cause=cause)
                self.assertFalse(routed, f"{event} / {cause!r}: {why}")

    # --- category 2: live data, from ANY branch --------------------------
    def test_a_live_data_failure_pages_from_any_branch(self):
        """The one a naive branch check breaks.

        A branch reading asktherecruiter.com reads the same wrong number main
        does. That is why these raise under a branch-free scope in the first
        place, and routing must consult the same identity function rather than
        the branch name.
        """
        for branch in ("claude/confident-jepsen-455457",
                       "fix/reader-freshness-content", "docs/editorial-spec"):
            routed, why = ci_alert.route_to_ops_status(
                event="pull_request", branch=branch, cause=self.LIVE)
            self.assertFalse(routed, f"{branch}: {why}")
            # ...and for the LIVE-DATA reason, not incidentally for another one.
            self.assertIn("LIVE-DATA", why)
        # main is covered by its own test above and short-circuits earlier.
        self.assertFalse(ci_alert.route_to_ops_status(
            event="pull_request", branch="main", cause=self.LIVE)[0])

    def test_the_live_data_test_above_is_not_vacuous(self):
        """If the label ever stops being recognised, say so here rather than
        letting the assertion above pass for the wrong reason."""
        self.assertIsNotNone(ci_alert.live_data_identity(self.LIVE))

    # --- category 3: scheduled and cron runs, wherever they run ----------
    def test_a_scheduled_run_pages_from_a_non_main_ref(self):
        for event in ("schedule", "push", "workflow_dispatch", "repository_dispatch"):
            routed, why = ci_alert.route_to_ops_status(
                event=event, branch="claude/some-branch",
                cause="AssertionError: the nightly job broke")
            self.assertFalse(routed, f"{event}: {why}")

    # --- category 4: the ledger does not leak ----------------------------
    def test_a_routed_raise_writes_nothing_to_the_ledger(self):
        """No open cause means nothing to orphan and no RECOVERED owed."""
        calls = []
        with mock.patch.object(ci_alert, "fetch_failed_log",
                               return_value="AssertionError: a branch-only defect"), \
             mock.patch.object(ci_alert, "post_alert",
                               side_effect=lambda *a, **k: calls.append(a)), \
             mock.patch.object(ci_alert, "hold",
                               side_effect=lambda **k: calls.append(k)):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = ci_alert.main([
                    "--run-id", "1", "--workflow", "Tests", "--conclusion", "failure",
                    "--branch", "claude/side", "--event", "pull_request",
                    "--repo", "dk-forge/x", "--run-url", "https://example.invalid/1"])
            out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(calls, [], "a routed raise touched the alert ledger")
        self.assertIn("ops_status [4e]", out)
        self.assertIn("nothing written to the ledger", out)

    def test_a_green_run_still_clears_anything_that_did_raise(self):
        """RECOVERED is untouched. The resolve path runs before routing and is
        not reached by it."""
        posted = []

        def capture(site, key, payload, sleep=None):
            posted.append(payload)
            return True, "emailed the owner", False

        orig, ci_alert.post_alert = ci_alert.post_alert, capture
        try:
            with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                 mock.patch.object(ci_alert, "live_data_was_evaluated",
                                   lambda *a: True):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = ci_alert.main([
                        "--run-id", "1", "--workflow", "Tests",
                        "--conclusion", "success", "--branch", "claude/side",
                        "--event", "pull_request", "--repo", "dk-forge/x",
                        "--run-url", "https://example.invalid/1"])
        finally:
            ci_alert.post_alert = orig
        self.assertEqual(code, 0)
        self.assertTrue(posted, "a green run on a side branch posted no resolve")
        self.assertEqual(posted[0]["resolve_scope"], "tests:claude-side")

    # --- and the blast radius stays where it was -------------------------
    def test_a_non_pull_request_event_is_never_routed(self):
        routed, _ = ci_alert.route_to_ops_status(
            event="", branch="claude/side", cause="AssertionError: x")
        self.assertFalse(routed)


class ARecoveredMirrorsTheBrokenItCloses(unittest.TestCase):
    """The owner could not tell which failure a RECOVERED closed: the BROKEN
    subject was `CI SELF-TIMEOUT: Tests — ...` but the RECOVERED was the generic
    `RECOVERED: Tests is green again`. Now the RECOVERED carries the same
    `{label}: {workflow} — {headline}` tail so the two pair in an inbox."""

    def test_the_recovered_subject_mirrors_the_stored_heading(self):
        broken = ("CI SELF-TIMEOUT: Tests — the job cancelled ITSELF on "
                  "timeout-minutes: it exceeded the maximum execution time of 30m0s")
        rec = ci_alert.recovered_subject(broken, "Tests")
        self.assertTrue(rec.startswith("RECOVERED — "), rec)
        self.assertIn(broken, rec, "the RECOVERED does not carry the BROKEN tail")

    def test_a_missing_heading_falls_back_and_never_invents_one(self):
        self.assertEqual(ci_alert.recovered_subject("", "Tests"),
                         "RECOVERED: Tests is green again")
        self.assertEqual(
            ci_alert.recovered_subject(None, "Deploy WordPress plugin"),
            "RECOVERED: Deploy WordPress plugin is green again")

    def test_a_still_failing_prefix_is_stripped_from_the_mirror(self):
        """Defensive: apply() keeps the clean subject, but a pre-change ledger
        entry might carry the reminder prefix, and it must not leak into the
        pair."""
        rec = ci_alert.recovered_subject(
            "STILL FAILING: CI RED: Tests — boom", "Tests")
        self.assertNotIn("STILL FAILING", rec)
        self.assertEqual(rec, "RECOVERED — CI RED: Tests — boom")

    def test_the_plan_makes_one_resolve_per_open_cause(self):
        import json as _json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(_json.dumps({"version": 1, "open": {
                "tests:main:aaaa": {"first": 1, "last": 1,
                                    "subject": "CI RED: Tests — X"},
                "tests:main:bbbb": {"first": 2, "last": 2,
                                    "subject": "CI RED: Tests — Y"}}}))
            with mock.patch.dict(os.environ, {"ALERT_STATE_PATH": str(path)}):
                plan = ci_alert._recovery_plan(["tests:main"])
        self.assertEqual({t for t, _ in plan},
                         {"tests:main:aaaa", "tests:main:bbbb"})
        self.assertEqual(dict(plan)["tests:main:aaaa"], "CI RED: Tests — X")

    def test_the_plan_posts_a_scope_noop_when_nothing_is_open(self):
        import json as _json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(_json.dumps({"version": 1, "open": {}}))
            with mock.patch.dict(os.environ, {"ALERT_STATE_PATH": str(path)}):
                plan = ci_alert._recovery_plan(["tests:main", "tests:live.data"])
        self.assertEqual(plan, [("tests:main", ""), ("tests:live.data", "")],
                         "a scope with nothing open must still post one silent "
                         "resolve, or the branch-free live.data clear is lost")

    def test_a_live_data_key_is_not_swallowed_by_the_branch_scope(self):
        """The two scopes a green run clears must not overlap: a live.data key
        must be planned under live.data, never under the branch scope."""
        import json as _json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(_json.dumps({"version": 1, "open": {
                "tests:main:aaaa": {"first": 1, "last": 1, "subject": "S1"},
                "tests:live.data:bbbb": {"first": 2, "last": 2, "subject": "S2"}}}))
            with mock.patch.dict(os.environ, {"ALERT_STATE_PATH": str(path)}):
                plan = ci_alert._recovery_plan(["tests:main", "tests:live.data"])
        self.assertEqual(plan, [("tests:main:aaaa", "S1"),
                                ("tests:live.data:bbbb", "S2")])


if __name__ == "__main__":
    unittest.main()
