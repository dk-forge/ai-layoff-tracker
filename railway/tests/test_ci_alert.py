"""Guards for railway/ci_alert.py — the CI-failure-to-email path.

The log fixtures below are REAL lines from the eight consecutive red runs of
2026-07-30 (the Spirit Airlines dedup regression), tab-prefixed exactly as
`gh run view --log-failed` emits them. Offline, no network, no keys.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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


class Behaviour(unittest.TestCase):
    def _run(self, argv, **env):
        import os
        old = {k: os.environ.get(k)
               for k in ("WP_SITE_URL", "WP_API_KEY", "ALERT_ENVELOPE")}
        os.environ.update({k: v for k, v in env.items()})
        for k in ("WP_SITE_URL", "WP_API_KEY", "ALERT_ENVELOPE"):
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

    def test_cancelled_is_not_alertable(self):
        """Runs are cancelled routinely by superseded pushes and concurrency
        groups. Mailing about those is the noise that gets a sender filtered."""
        code, out = self._run(["--run-id", "1", "--workflow", "Tests",
                               "--conclusion", "cancelled"])
        self.assertEqual(code, 0)
        self.assertIn("not alertable", out)

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
                    WP_SITE_URL="https://example.invalid", WP_API_KEY="k")
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
                                  WP_SITE_URL="https://example.invalid", WP_API_KEY="k")
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
            code, _ = self._run(["--run-id", "1", "--workflow", "Tests",
                                 "--conclusion", "success", "--branch", "main"],
                                WP_SITE_URL="https://example.invalid", WP_API_KEY="k")
        finally:
            ci_alert.post_alert = orig
        self.assertEqual(code, 0)
        self.assertEqual(calls[0]["resolve_scope"], "tests:main")
        self.assertNotIn("dedupe_key", calls[0])


if __name__ == "__main__":
    unittest.main()
