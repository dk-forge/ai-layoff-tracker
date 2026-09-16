"""A bot wall answering for the host is named as one, never as "JSON".

THE DEFECT THIS CLOSES (2026-09-13)
-----------------------------------
`archive-backfill.yml`, on a GitHub-hosted runner, called `host_call.get_json`
against `/archive-candidates` and died with

    requests.exceptions.JSONDecodeError: Expecting value: line 1 column 1

The host was up: this Mac got 200 JSON from the same route in the same minute.
What the runner got was ChemiCloud's Imunify360 bot protection standing in for
the answer, in one of three shapes:

  * an HTML interstitial ("One moment, please...") with a JS reload, on a 2xx
  * text/plain "Access denied by Imunify360 bot-protection ..." on a 403
  * text/plain "error code: 504" from the edge

None of the three is a host outage and none is a defect in the job, and the
morning's run said neither: it said "JSON". Worse, the 2xx interstitial passes
`raise_for_status`, so a caller that did not parse (the CLI path) would have
written an HTML page to its output file and exited 0.

So the shapes are detected BEFORE parsing and raised as ONE named exception,
`host_call.HostChallenged`, whose message says what happened and what a human
does about it. It is a `Deferred`: the run exits 0 and the deferral is counted,
because retrying tomorrow from the same blocked IP changes nothing and a red
run every day is alarm fatigue. It is NOT an ordinary deferral either: the
ledger reason starts with "challenged:", `[4d]` prints the word and points at
the RUNBOOK, and ops_status asks for a human on the first one.

No network anywhere. Offline, no keys.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deferral_ledger
import host_call
import http_retry
import ops_status

INTERSTITIAL = ("<!DOCTYPE html><html><head><title>One moment, please...</title>"
                "<script>setTimeout(function(){location.reload()},5000)</script>"
                "</head><body>Please wait while your request is being verified..."
                "</body></html>")
DENIED = ("Access denied by Imunify360 bot-protection. IPs used for automation "
          "should be whitelisted")
EDGE_504 = "error code: 504"
URL = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/archive-candidates"


class _Resp:
    """The slice of a `requests.Response` that `get_json` reads."""

    def __init__(self, status, body, content_type):
        self.status_code = status
        self.text = body
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.text)


def _get(status, body, content_type):
    return mock.patch.object(http_retry, "get_with_retry",
                             lambda *a, **k: _Resp(status, body, content_type))


class GetJsonNamesTheChallenge(unittest.TestCase):
    def assert_named(self, exc):
        text = str(exc)
        self.assertIn("challenged", text)
        self.assertIn("Imunify360", text)
        self.assertIn("whitelist", text.lower())

    def test_2xx_html_interstitial(self):
        with _get(200, INTERSTITIAL, "text/html; charset=UTF-8"):
            with self.assertRaises(host_call.HostChallenged) as ctx:
                host_call.get_json(URL)
        self.assert_named(ctx.exception)
        self.assertIn("One moment, please", str(ctx.exception))

    def test_403_plain_text_denial(self):
        with _get(403, DENIED, "text/plain"):
            with self.assertRaises(host_call.HostChallenged) as ctx:
                host_call.get_json(URL)
        self.assert_named(ctx.exception)

    def test_edge_error_code_body(self):
        with _get(200, EDGE_504, "text/plain"):
            with self.assertRaises(host_call.HostChallenged) as ctx:
                host_call.get_json(URL)
        self.assert_named(ctx.exception)
        self.assertIn("error code: 504", str(ctx.exception))

    def test_bare_html_where_json_was_expected(self):
        with _get(200, "<html><body>Just Checking</body></html>", "text/html"):
            with self.assertRaises(host_call.HostChallenged):
                host_call.get_json(URL)

    def test_a_challenge_is_a_deferral(self):
        """Every `except host_call.Deferred` in the workers must keep catching
        it, or a challenge is a red run in nine jobs at once."""
        self.assertTrue(issubclass(host_call.HostChallenged, host_call.Deferred))

    def test_plain_json_still_parses(self):
        with _get(200, '{"candidates": [1, 2]}', "application/json"):
            self.assertEqual(host_call.get_json(URL), {"candidates": [1, 2]})

    def test_a_real_decode_error_is_still_a_real_decode_error(self):
        """A route that returns garbage is OUR bug, and hiding it behind the
        new exception would be the exact softening this module forbids."""
        with _get(200, "not json at all", "application/json"):
            with self.assertRaises(ValueError) as ctx:
                host_call.get_json(URL)
        self.assertNotIsInstance(ctx.exception, host_call.HostChallenged)

    def test_a_settled_json_refusal_still_raises(self):
        with _get(403, '{"code":"rest_forbidden"}', "application/json"):
            with self.assertRaises(RuntimeError) as ctx:
                host_call.get_json(URL)
        self.assertNotIsInstance(ctx.exception, host_call.HostChallenged)


class PostJsonNamesTheChallenge(unittest.TestCase):
    def test_2xx_interstitial_on_a_post(self):
        with mock.patch.object(http_retry, "_send", lambda *a, **k: (200, INTERSTITIAL)):
            with self.assertRaises(host_call.HostChallenged):
                host_call.post_json(URL, {"x": 1})

    def test_403_denial_on_a_post(self):
        with mock.patch.object(http_retry, "_send", lambda *a, **k: (403, DENIED)):
            with self.assertRaises(host_call.HostChallenged):
                host_call.post_json(URL, {"x": 1})

    def test_a_real_refusal_still_raises(self):
        with mock.patch.object(http_retry, "_send",
                               lambda *a, **k: (403, '{"code":"rest_forbidden"}')):
            with self.assertRaises(RuntimeError) as ctx:
                host_call.post_json(URL, {"x": 1})
        self.assertNotIsInstance(ctx.exception, host_call.HostChallenged)


class CliDefersAndTheLedgerSaysChallenged(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ledger = Path(self._tmp.name) / "deferral_ledger.json"
        self.output = Path(self._tmp.name) / "response.json"
        patch = mock.patch.dict("os.environ", {"GITHUB_RUN_ID": "7",
                                               "GITHUB_RUN_ATTEMPT": "1"})
        patch.start()
        self.addCleanup(patch.stop)

    def _run(self, status, body):
        buf = io.StringIO()
        with mock.patch.object(http_retry, "_send", lambda *a, **k: (status, body)):
            with contextlib.redirect_stdout(buf):
                code = host_call.main(["--job", "test-job", "--url", URL,
                                       "--ledger", str(self.ledger),
                                       "--output", str(self.output), "--no-sleep"])
        return code, buf.getvalue()

    def test_interstitial_defers_and_writes_no_body(self):
        code, printed = self._run(200, INTERSTITIAL)
        self.assertEqual(code, 0)
        self.assertFalse(self.output.exists(),
                         "an HTML interstitial must never be written as the response")
        doc = json.loads(self.ledger.read_text())
        entry = deferral_ledger.pending(doc)[0]
        self.assertEqual(entry["job"], "test-job")
        self.assertTrue(entry["last_reason"].startswith(deferral_ledger.CHALLENGED_PREFIX))
        self.assertIn("Imunify360", entry["last_reason"])
        self.assertIn("challenged", printed)

    def test_403_denial_defers_rather_than_failing(self):
        code, _ = self._run(403, DENIED)
        self.assertEqual(code, 0)
        self.assertTrue(deferral_ledger.pending(json.loads(self.ledger.read_text())))

    def test_ledger_describe_says_challenged(self):
        self._run(200, INTERSTITIAL)
        lines = deferral_ledger.describe(json.loads(self.ledger.read_text()))
        joined = "\n".join(lines)
        self.assertIn("CHALLENGED", joined)
        self.assertIn("JSONDecodeError", joined)

    def test_ops_status_flags_a_challenge_for_a_human(self):
        self._run(200, INTERSTITIAL)
        with mock.patch.object(ops_status, "_DEFERRAL_LEDGER", self.ledger):
            lines = ops_status._report_deferrals()
            self.assertTrue(ops_status._deferrals_need_a_human())
        joined = "\n".join(lines)
        self.assertIn("CHALLENGED", joined)
        self.assertIn("whitelist", joined.lower())

    def test_ops_status_mirror_of_the_prefix_matches(self):
        self.assertEqual(ops_status._CHALLENGED_PREFIX, deferral_ledger.CHALLENGED_PREFIX)


if __name__ == "__main__":
    unittest.main()
