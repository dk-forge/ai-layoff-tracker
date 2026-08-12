"""A host that never answered is not a job that failed — and not a job that passed.

THE DEFECT THIS CLOSES
----------------------
`ci_alert.py` learned on 2026-07-31 that an undeliverable message is HELD, not
lost, and that holding must not redden the run. The JOBS that talk to the same
host never learned it. They called `curl --fail-with-body` against a route on
Bluehost, so a 504 lasting six minutes killed the run, the red run fired the CI
alerter, and the alerter then had to reach `/alert` on the host that was down.
One outage manufactures red runs which manufacture alerts which also fail.

So a host call has THREE outcomes, and this file pins all three:

  1. the host answered and we got what we asked for            -> exit 0
  2. the host could not be reached at all (transport error, or
     a transient status that survived every retry)             -> DEFERRED, exit 0
  3. the host gave us a real answer we do not accept (401/403/
     404, any non-transient status, or a 2xx body that reports
     the work failed)                                          -> exit non-zero, loudly

And the property that stops (2) being "silently green", which is the failure
family this repo keeps digging out of: a deferral is COUNTED in a committed
ledger, shown by ops_status.py, and the THIRD consecutive one for a job stops
being an outage and goes red like any other broken job.

No network anywhere. Offline, no keys.
"""
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


class _Host:
    """A scripted stand-in for the WordPress host.

    Each entry is either an int status (with an optional body) or an exception
    to raise, so one test can say "504, 504, 504" and another "one blip then
    fine" without touching the network.
    """

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, data=None, headers=None, timeout=None):
        self.calls.append((method, url))
        item = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            return item
        return item, "{}"


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "deferral_ledger.json"
        self.output = Path(self._tmp.name) / "response.json"
        self._real_send = http_retry._send
        self._runs = 0
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(lambda: setattr(http_retry, "_send", self._real_send))
        # Each run_call is a SEPARATE workflow run, and must look like one. On
        # a runner these tests inherit the job's own GITHUB_RUN_ID, which made
        # three calls in one process share a run key: the ledger correctly
        # treated calls two and three as the rejected-push replay of call one,
        # the streak stayed at 1, and the escalation tests passed locally and
        # failed in CI. Give every call its own run id instead of unsetting the
        # variable, so the idempotence path stays exercised rather than skipped.
        patch = mock.patch.dict("os.environ", {"GITHUB_RUN_ID": "0",
                                               "GITHUB_RUN_ATTEMPT": "1"})
        patch.start()
        self.addCleanup(patch.stop)

    def run_call(self, *responses, job="test-job", extra=(), same_run=False):
        import os

        if not same_run:
            self._runs += 1
        os.environ["GITHUB_RUN_ID"] = str(self._runs)
        host = _Host(*responses)
        http_retry._send = host
        code = host_call.main([
            "--job", job,
            "--url", "https://asktherecruiter.com/blog/wp-json/layoffs/v1/thing",
            "--ledger", str(self.ledger),
            "--output", str(self.output),
            "--no-sleep",
            *extra,
        ])
        return code, host

    def ledger_doc(self):
        return deferral_ledger.load(self.ledger)


class AnUnreachableHostDefers(_Case):
    def test_504_throughout_defers_and_exits_zero(self):
        code, host = self.run_call(504)
        self.assertEqual(code, 0, "a host that 504'd is not a job that failed")
        self.assertGreater(len(host.calls), 1, "a transient status must be retried")
        entry = deferral_ledger.pending(self.ledger_doc())
        self.assertEqual([e["job"] for e in entry], ["test-job"])
        self.assertEqual(entry[0]["consecutive"], 1)

    def test_transport_error_defers(self):
        code, _ = self.run_call(http_retry.Unreachable("connection reset"))
        self.assertEqual(code, 0)
        self.assertEqual(len(deferral_ledger.pending(self.ledger_doc())), 1)

    def test_a_blip_then_an_answer_is_a_pass(self):
        code, host = self.run_call(504, (200, '{"ok": true}'))
        self.assertEqual(code, 0)
        self.assertEqual(len(host.calls), 2)
        self.assertEqual(deferral_ledger.pending(self.ledger_doc()), [])
        self.assertEqual(json.loads(self.output.read_text()), {"ok": True})

    def test_a_deferral_writes_no_response_file(self):
        """The downstream parse must never read a stale body from a previous run."""
        self.output.write_text('{"stale": true}')
        self.run_call(502)
        self.assertFalse(self.output.exists(),
                         "a deferred call must not leave a body for the parser")


class ARealAnswerStillFailsLoudly(_Case):
    def test_403_exits_non_zero(self):
        code, host = self.run_call((403, "forbidden"))
        self.assertNotEqual(code, 0, "a wrong key is a real answer, not an outage")
        self.assertEqual(len(host.calls), 1, "a settled refusal must not be retried")
        self.assertEqual(deferral_ledger.pending(self.ledger_doc()), [],
                         "a refusal is not a deferral")

    def test_404_exits_non_zero(self):
        code, _ = self.run_call((404, "no route"))
        self.assertNotEqual(code, 0)

    def test_a_body_reporting_a_failed_batch_exits_non_zero(self):
        code, _ = self.run_call((200, json.dumps({"ok": False, "failed": 3})))
        self.assertNotEqual(code, 0,
                            "the host answered and told us the work failed")
        self.assertEqual(deferral_ledger.pending(self.ledger_doc()), [])

    def test_a_body_with_an_error_key_exits_non_zero(self):
        code, _ = self.run_call((200, json.dumps({"error": "bad request"})))
        self.assertNotEqual(code, 0)


class DeferralsEscalate(_Case):
    def test_the_third_consecutive_deferral_goes_red(self):
        first, _ = self.run_call(504)
        second, _ = self.run_call(504)
        third, _ = self.run_call(504)
        self.assertEqual((first, second), (0, 0),
                         "one or two deferrals is an outage, not a defect")
        self.assertNotEqual(third, 0,
                            "three in a row is a job hiding behind the outage story")
        self.assertEqual(deferral_ledger.pending(self.ledger_doc())[0]["consecutive"], 3)

    def test_a_success_clears_the_streak(self):
        self.run_call(504)
        self.run_call(504)
        self.run_call((200, "{}"))
        self.assertEqual(deferral_ledger.pending(self.ledger_doc()), [])
        # ...and the next deferral starts from one again, so a job that defers
        # every other day never accumulates its way to a false escalation.
        code, _ = self.run_call(504)
        self.assertEqual(code, 0)
        self.assertEqual(deferral_ledger.pending(self.ledger_doc())[0]["consecutive"], 1)

    def test_jobs_are_counted_separately(self):
        self.run_call(504, job="a")
        self.run_call(504, job="a")
        code, _ = self.run_call(504, job="b")
        self.assertEqual(code, 0, "job b has deferred once, not three times")

    def test_one_run_calling_twice_is_one_deferral(self):
        """The end-to-end shape of the idempotence below: the commit loop can
        re-run host_call after resetting onto main, and that must not count."""
        self.run_call(504)
        code, _ = self.run_call(504, same_run=True)  # the SAME run, recorded again
        self.assertEqual(code, 0)
        self.assertEqual(deferral_ledger.pending(self.ledger_doc())[0]["consecutive"], 1)

    def test_replaying_the_same_run_does_not_double_count(self):
        """The commit loop re-derives on a rejected push. Re-recording the same
        deferral must not walk a job to escalation on retries alone."""
        doc = deferral_ledger.load(self.ledger)
        for _ in range(3):
            deferral_ledger.record_deferral(doc, job="j", reason="HTTP 504",
                                            key="run-1")
        self.assertEqual(deferral_ledger.pending(doc)[0]["consecutive"], 1)


class ACostFreeLedger(_Case):
    def test_a_healthy_job_writes_nothing_at_all(self):
        """`alert-drain.yml` makes NO request when the outbox is empty. The same
        rule here: a ledger nobody is deferring into costs nothing to keep."""
        self.run_call((200, "{}"))
        self.assertFalse(self.ledger.exists(),
                         "a clean run must not churn a committed file")


class ADeferralIsVisibleInOpsStatus(_Case):
    def _point_ops_status_at(self, path):
        real = ops_status._DEFERRAL_LEDGER
        ops_status._DEFERRAL_LEDGER = Path(path)
        self.addCleanup(lambda: setattr(ops_status, "_DEFERRAL_LEDGER", real))

    def test_silence_when_nothing_is_deferred(self):
        self._point_ops_status_at(self.ledger)
        self.assertIn("none", " ".join(ops_status._report_deferrals()).lower())
        self.assertFalse(ops_status._deferrals_need_a_human())

    def test_a_pending_deferral_is_named(self):
        self.run_call(504, job="reconcile-supersets")
        self._point_ops_status_at(self.ledger)
        text = " ".join(ops_status._report_deferrals())
        self.assertIn("reconcile-supersets", text)
        self.assertNotIn("none", text.lower())
        self.assertFalse(ops_status._deferrals_need_a_human(),
                         "one deferral is an outage, not an ACTION NEEDED item")

    def test_three_in_a_row_needs_a_human(self):
        for _ in range(3):
            self.run_call(504, job="reconcile-supersets")
        self._point_ops_status_at(self.ledger)
        self.assertTrue(ops_status._deferrals_need_a_human())
        self.assertIn("x3", " ".join(ops_status._report_deferrals()))


class OneRetryDefinition(unittest.TestCase):
    def test_the_post_path_uses_the_shared_transient_set(self):
        """http_retry exists because the retry once lived in one file and the
        next scan re-derived it and drifted. The POST sibling must not fork it."""
        self.assertIs(host_call.http_retry.TRANSIENT, http_retry.TRANSIENT)
        for status in (502, 503, 504):
            self.assertIn(status, http_retry.TRANSIENT)
        for status in (401, 403, 404):
            self.assertNotIn(status, http_retry.TRANSIENT)


class TheWorkflowsActuallyUseIt(unittest.TestCase):
    """A converted workflow that still shells out to `curl --fail-with-body`
    would pass every test above and defer nothing in production."""

    WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    CONVERTED = ("reconcile-supersets.yml", "announcement-lifecycle-review.yml")

    def test_converted_workflows_call_host_call(self):
        for name in self.CONVERTED:
            text = (self.WORKFLOWS / name).read_text()
            # Comments still discuss the curl this replaced, on purpose. Only
            # executable lines are the subject here.
            live = "\n".join(ln for ln in text.splitlines()
                             if not ln.lstrip().startswith("#"))
            with self.subTest(name):
                self.assertIn("host_call.py", live)
                self.assertNotIn("curl", live)

    def test_the_parse_step_is_gated_on_the_call_having_answered(self):
        """A deferral leaves no response body. A parse step that runs anyway
        turns a quiet deferral back into a red run for the wrong reason."""
        for name in self.CONVERTED:
            text = (self.WORKFLOWS / name).read_text()
            with self.subTest(name):
                self.assertIn("outputs.outcome == 'ok'", text)


if __name__ == "__main__":
    unittest.main()
