"""A failed deploy check has to say something a human can act on.

The owner was emailed twice about `Deploy WordPress plugin` and both mails
carried one line and nothing else:

    json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
    AssertionError

Both came from the same pipeline in deploy-plugin.yml, `curl --fail ... |
python3 -c '... json.load(sys.stdin); assert "canonical_events" in payload'`.
Neither names the endpoint, the HTTP status, the content type, or one byte of
what actually came back, and the alert body is what outlives the run's log
retention.

So this file pins the four answers an endpoint can give and asserts that each
produces a DISTINCT, NAMED verdict:

  * an empty 200                      -> FAIL, and it says the body was empty
  * an HTML 200                       -> FAIL, and it quotes the HTML
  * valid JSON missing the key        -> FAIL, and it names the key and the
                                         keys that were there instead
  * the right JSON                    -> PASS

and the third state on top of them: a host that never answered, or answered
through a gateway or through Cloudflare's 52x family, is UNKNOWN. PASS / FAIL
/ UNKNOWN are three states and absence of a signal is not a pass (CLAUDE.md).

It also pins the workflow itself, because a helper the workflow does not call
is decoration: no verification step may carry a bare `json.load(sys.stdin)` or
a bare `assert` again.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import endpoint_check
from endpoint_check import FAIL, PASS, UNKNOWN

REPO = Path(__file__).resolve().parents[2]
DEPLOY_YML = (REPO / ".github" / "workflows" / "deploy-plugin.yml").read_text(encoding="utf-8")

#: Comment lines are stripped before matching, so nothing below can pass or
#: fail because the string it looks for appears in the prose explaining why it
#: was removed. The step's own history quotes the very pipeline it replaced.
DEPLOY_CODE = "\n".join(line for line in DEPLOY_YML.splitlines()
                        if not line.lstrip().startswith("#"))

URL = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/integrity-status?deploy_check=1"
GOOD = b'{"canonical_events": 4211, "generated": "2026-09-09T00:00:00Z"}'
HTML = (b"<!DOCTYPE html>\n<html><head><title>503 Service Unavailable</title></head>\n"
        b"<body><h1>Briefly unavailable for scheduled maintenance.</h1></body></html>")


class FourBodiesFourVerdicts(unittest.TestCase):
    """The four cases the old one-liner collapsed into two useless strings."""

    def judge(self, body, ctype="application/json", status=200):
        return endpoint_check.judge(status, ctype, body,
                                    require=("canonical_events",), url=URL)

    def test_empty_body_is_a_named_fail(self):
        result = self.judge(b"", ctype="application/json")
        self.assertEqual(FAIL, result.verdict)
        self.assertIn("EMPTY body", result.detail)
        self.assertIn(URL, result.detail)
        self.assertIn("200", result.detail)
        # The old message for this exact case was the JSONDecodeError alone.
        self.assertNotEqual(result.detail.strip(),
                            "Expecting value: line 1 column 1 (char 0)")

    def test_html_body_is_a_fail_that_quotes_the_html(self):
        result = self.judge(HTML, ctype="text/html; charset=UTF-8")
        self.assertEqual(FAIL, result.verdict)
        self.assertIn("not JSON", result.detail)
        self.assertIn("text/html", result.detail)
        self.assertIn("<!DOCTYPE html>", result.detail)
        self.assertIn("503 Service Unavailable", result.detail)

    def test_json_missing_the_key_names_the_key_and_what_was_there(self):
        result = self.judge(b'{"generated": "2026-09-09", "rows": 0}')
        self.assertEqual(FAIL, result.verdict)
        self.assertIn("canonical_events", result.detail)
        self.assertIn("MISSING", result.detail)
        # The keys that WERE there is what tells an operator whether the route
        # changed shape or answered from somewhere else entirely.
        self.assertIn("generated", result.detail)
        self.assertIn("rows", result.detail)

    def test_the_right_body_passes(self):
        result = self.judge(GOOD)
        self.assertEqual(PASS, result.verdict)
        self.assertTrue(result.ok)
        self.assertIn("canonical_events", result.detail)

    def test_the_four_verdicts_are_four_distinct_sentences(self):
        details = {
            self.judge(b"").detail,
            self.judge(HTML, ctype="text/html").detail,
            self.judge(b'{"generated": "x"}').detail,
            self.judge(GOOD).detail,
        }
        self.assertEqual(4, len(details))


class UnknownIsNeitherPassNorFault(unittest.TestCase):

    def test_cloudflare_edge_errors_are_unknown(self):
        for status in (520, 521, 522, 523, 524):
            result = endpoint_check.judge(status, "text/html", b"error",
                                          require=("canonical_events",), url=URL)
            self.assertEqual(UNKNOWN, result.verdict, status)
            self.assertIn("NOT a verdict", result.detail)
            self.assertFalse(result.ok)

    def test_gateway_and_rate_limit_are_unknown(self):
        for status in (429, 502, 504):
            result = endpoint_check.judge(status, "text/html", b"",
                                          require=("canonical_events",), url=URL)
            self.assertEqual(UNKNOWN, result.verdict, status)

    def test_maintenance_503_is_unknown_because_this_deploy_causes_it(self):
        result = endpoint_check.judge(503, "text/html", HTML,
                                      require=("canonical_events",), url=URL)
        self.assertEqual(UNKNOWN, result.verdict)
        self.assertIn("maintenance", result.detail)

    def test_a_php_fatal_500_is_a_fail_not_an_unknown(self):
        """A 500 is PHP answering, and this deploy just uploaded that PHP."""
        result = endpoint_check.judge(500, "text/html", b"Fatal error: ...",
                                      require=("canonical_events",), url=URL)
        self.assertEqual(FAIL, result.verdict)
        self.assertIn("500", result.detail)
        self.assertIn("Fatal error", result.detail)

    def test_an_unreachable_host_is_unknown_and_names_the_url(self):
        def boom(url, timeout=None, cookie=""):
            raise OSError("Name or service not known")

        result = endpoint_check.check(URL, require=("canonical_events",),
                                      attempts=2, sleep=lambda _s: None,
                                      fetcher=boom)
        self.assertEqual(UNKNOWN, result.verdict)
        self.assertIn(URL, result.detail)
        self.assertIn("Name or service not known", result.detail)


class ExcerptIsSafeAndBounded(unittest.TestCase):

    def test_the_excerpt_is_truncated(self):
        body = b"x" * 5000
        text = endpoint_check.excerpt(body, limit=200)
        self.assertIn("truncated at 200", text)
        self.assertLess(len(text), 260)

    def test_control_characters_cannot_forge_a_workflow_annotation(self):
        text = endpoint_check.excerpt(b"a\x1b[31mred\x00\nb")
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\x00", text)
        self.assertNotIn("\n", text)

    def test_undecodable_bytes_do_not_lose_the_excerpt(self):
        self.assertIn("ok", endpoint_check.excerpt(b"ok \xff\xfe rest"))


class RetryOnlyWhatARetryCanChange(unittest.TestCase):

    def test_a_wrong_body_is_not_retried(self):
        calls = []

        def fetcher(url, timeout=None, cookie=""):
            calls.append(url)
            return 200, "text/html", HTML

        result = endpoint_check.check(URL, require=("canonical_events",),
                                      attempts=4, sleep=lambda _s: None,
                                      fetcher=fetcher)
        self.assertEqual(FAIL, result.verdict)
        self.assertEqual(1, len(calls), "a wrong body will be wrong again")

    def test_a_transient_status_is_retried_and_can_recover(self):
        answers = [(503, "text/html", HTML), (200, "application/json", GOOD)]

        def fetcher(url, timeout=None, cookie=""):
            return answers.pop(0)

        result = endpoint_check.check(URL, require=("canonical_events",),
                                      attempts=4, sleep=lambda _s: None,
                                      fetcher=fetcher)
        self.assertEqual(PASS, result.verdict)


class ExitCodesMatchTheRepoConvention(unittest.TestCase):
    """0 PASS, 2 FAIL, 3 UNKNOWN, the same as reader_freshness and
    subscriber_routes, because deploy-plugin.yml branches on those numbers."""

    def _main(self, verdict):
        original = endpoint_check.check
        endpoint_check.check = lambda *a, **k: endpoint_check.Result(verdict, "detail")
        try:
            return endpoint_check.main(["--url", URL, "--require", "canonical_events"])
        finally:
            endpoint_check.check = original

    def test_pass_is_zero(self):
        self.assertEqual(0, self._main(PASS))

    def test_fail_is_two(self):
        self.assertEqual(2, self._main(FAIL))

    def test_unknown_is_three(self):
        self.assertEqual(3, self._main(UNKNOWN))


class TheWorkflowActuallyUsesIt(unittest.TestCase):
    """A helper the workflow does not call is decoration."""

    def test_the_api_step_calls_the_helper(self):
        self.assertIn("railway/endpoint_check.py", DEPLOY_CODE)
        self.assertIn("--require canonical_events", DEPLOY_CODE)

    def test_no_verification_step_parses_json_bare_again(self):
        self.assertNotIn("json.load(sys.stdin)", DEPLOY_CODE)

    def test_no_bare_assert_survives_in_the_workflow(self):
        # re.MULTILINE, because `$` without it anchors to the END OF THE FILE:
        # the first version of this test matched nothing anywhere and passed a
        # deliberately re-injected bare assert. A guard has to be shown
        # catching one known instance before its clean zero means anything.
        bare = re.findall(r"assert [^;\n]*(?:;|$)", DEPLOY_CODE, re.MULTILINE)
        self.assertEqual([], bare, f"a bare assert is back in deploy-plugin.yml: {bare}")

    def test_fail_fails_the_deploy_and_unknown_does_not(self):
        step = DEPLOY_CODE.split("- name: Verify the deployed tracker API", 1)[1]
        step = step.split("- name:", 1)[0]
        self.assertIn('if [ "$STATUS" = "2" ]', step)
        self.assertIn("::error::", step)
        self.assertIn('if [ "$STATUS" = "3" ]', step)
        self.assertIn("UNKNOWN, not a pass", step)

    def test_the_verdict_travels_inside_the_annotation(self):
        """ci_alert mails the most specific line, and it ranks `::error::`
        annotations above ordinary output. An annotation that pointed at the
        log would BE the email, and the status, content type and excerpt would
        never leave the run."""
        step = DEPLOY_CODE.split("- name: Verify the deployed tracker API", 1)[1]
        step = step.split("- name:", 1)[0]
        self.assertIn('OUT="$(python3 railway/endpoint_check.py', step)
        for line in step.splitlines():
            if "::error::" in line or "::warning::" in line:
                self.assertIn("$ONE_LINE", line,
                              f"this annotation drops the verdict: {line.strip()}")

    def test_the_version_greps_cannot_die_silently(self):
        """An unmatched grep under `set -e` used to end the step with no line
        of output at all. Both now fall through to a named error."""
        self.assertEqual(2, DEPLOY_CODE.count("Could not read ALT_VERSION"))


if __name__ == "__main__":
    unittest.main()
