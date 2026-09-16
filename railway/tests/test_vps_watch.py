"""The VPS watchdog: a runner that is offline is a FAULT, not "no jobs ran".

Pinned here:
  * an offline (or absent) runner raises `vps:offline:<repo>`
  * an online runner clears that same key
  * a heartbeat older than the ceiling, or whose last completed run was red,
    raises `vps:heartbeat-stale`; a fresh green one clears it
  * a GitHub API error is UNKNOWN: nothing raised, nothing resolved, exit 3
  * the dedupe keys are stable strings the ledger accepts
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import alert_state  # noqa: E402
import vps_watch  # noqa: E402

NOW = 1_800_000_000.0


def _iso(epoch):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def runners(status="online", name="atr-runner-ai-layoff-tracker"):
    return {"runners": [{"name": name, "status": status}]}


def heartbeat(age_s=600, conclusion="success", status="completed"):
    return {"workflow_runs": [{
        "status": status, "conclusion": conclusion,
        "run_started_at": _iso(NOW - age_s), "html_url": "https://x/run/1",
    }]}


def fake_api(runner_payloads=None, hb=None, fail=()):
    """`fail` lists path substrings that answer (False, 'boom')."""
    def api(path):
        if any(f in path for f in fail):
            return False, "boom"
        if "/actions/runners" in path:
            repo = path.split("repos/")[1].split("/actions")[0]
            return True, (runner_payloads or {}).get(repo, runners())
        return True, hb if hb is not None else heartbeat()
    return api


class Sent:
    def __init__(self):
        self.calls = []

    def __call__(self, subject, body, **kw):
        self.calls.append((subject, kw))
        return True

    def raised(self):
        return sorted(kw["dedupe_key"] for _, kw in self.calls if "dedupe_key" in kw)

    def resolved(self):
        return sorted(kw["resolve_scope"] for _, kw in self.calls if "resolve_scope" in kw)


class RunnerJudgement(unittest.TestCase):
    def test_offline_runner_is_a_fault(self):
        r = vps_watch.judge_runner("dk-forge/ai-layoff-tracker", runners("offline"))
        self.assertEqual(r.state, "FAULT")
        self.assertEqual(r.key, "vps:offline:ai-layoff-tracker")
        self.assertIn("offline", r.detail)

    def test_absent_runner_is_a_fault_not_a_quiet_zero(self):
        r = vps_watch.judge_runner("dk-forge/ai-layoff-tracker", {"runners": []})
        self.assertEqual(r.state, "FAULT")

    def test_a_runner_with_another_name_does_not_count(self):
        r = vps_watch.judge_runner("dk-forge/ai-layoff-tracker",
                                   runners("online", name="somebody-elses-mac"))
        self.assertEqual(r.state, "FAULT")

    def test_online_runner_clears(self):
        r = vps_watch.judge_runner("dk-forge/ai-layoff-tracker", runners())
        self.assertEqual(r.state, "CLEAR")


class HeartbeatJudgement(unittest.TestCase):
    def test_fresh_green_heartbeat_clears(self):
        r = vps_watch.judge_heartbeat(heartbeat(), now=NOW)
        self.assertEqual((r.key, r.state), ("vps:heartbeat-stale", "CLEAR"))

    def test_heartbeat_older_than_two_hours_is_a_fault(self):
        r = vps_watch.judge_heartbeat(heartbeat(age_s=3 * 3600), now=NOW)
        self.assertEqual(r.state, "FAULT")
        self.assertIn("min ago", r.detail)

    def test_a_red_heartbeat_is_a_fault(self):
        r = vps_watch.judge_heartbeat(heartbeat(conclusion="failure"), now=NOW)
        self.assertEqual(r.state, "FAULT")
        self.assertIn("failure", r.detail)

    def test_never_ran_is_a_fault(self):
        r = vps_watch.judge_heartbeat({"workflow_runs": []}, now=NOW)
        self.assertEqual(r.state, "FAULT")

    def test_an_in_flight_run_with_nothing_completed_is_unknown(self):
        r = vps_watch.judge_heartbeat(heartbeat(status="in_progress", conclusion=None),
                                      now=NOW)
        self.assertEqual(r.state, "UNKNOWN")


class ReportingThroughTheLedger(unittest.TestCase):
    def test_offline_raises_once_and_online_clears_once(self):
        offline = {"dk-forge/ai-layoff-tracker": runners("offline")}
        sent = Sent()
        vps_watch.report(vps_watch.check(fake_api(offline), now=NOW), sent)
        self.assertEqual(sent.raised(), ["vps:offline:ai-layoff-tracker"])
        # The other two repos and the heartbeat are CLEAR -> resolve sent to
        # the ledger, which stays silent when nothing is open.
        self.assertIn("vps:offline:asktherecruiter-sandbox", sent.resolved())
        self.assertIn("vps:heartbeat-stale", sent.resolved())

        sent = Sent()
        vps_watch.report(vps_watch.check(fake_api(), now=NOW), sent)
        self.assertEqual(sent.raised(), [])
        self.assertEqual(sent.resolved(), sorted(vps_watch.ALL_KEYS))

    def test_api_error_is_unknown_never_a_pass_never_a_fault(self):
        api = fake_api(fail=("/actions/runners",))
        verdict = vps_watch.check(api, now=NOW)
        sent = Sent()
        vps_watch.report(verdict, sent)
        offline_keys = [k for k in vps_watch.ALL_KEYS if k.startswith("vps:offline:")]
        for k in offline_keys:
            self.assertNotIn(k, sent.raised(), "an API error must not raise")
            self.assertNotIn(k, sent.resolved(), "an API error must not resolve")
        self.assertEqual(len(verdict.unknowns), len(offline_keys))
        # The heartbeat read still succeeded and is still judged.
        self.assertIn("vps:heartbeat-stale", sent.resolved())

    def test_main_exits_3_on_unknown_and_0_on_fault(self):
        real_check = vps_watch.check
        with mock.patch.object(vps_watch, "check",
                               lambda: real_check(fake_api(fail=("runs",)), now=NOW)), \
                mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(vps_watch.main(["--dry-run"]), 3)
        offline = {"dk-forge/asktherecruiter-sandbox": runners("offline")}
        with mock.patch.object(vps_watch, "check",
                               lambda: real_check(fake_api(offline), now=NOW)), \
                mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(vps_watch.main(["--dry-run"]), 0)


class DedupeKeys(unittest.TestCase):
    def test_keys_are_stable_and_ledger_safe(self):
        self.assertEqual(vps_watch.key_offline("dk-forge/ai-layoff-tracker"),
                         "vps:offline:ai-layoff-tracker")
        self.assertEqual(vps_watch.KEY_HEARTBEAT, "vps:heartbeat-stale")
        for key in vps_watch.ALL_KEYS:
            self.assertRegex(key, alert_state.KEY_SAFE)

    def test_the_ledger_dedupes_a_repeat_and_clears_on_the_exact_key(self):
        state = alert_state.empty()
        key = vps_watch.key_offline("dk-forge/talent-intelligence-tracker")
        d1 = alert_state.decide(state, {"subject": "s", "body": "b", "dedupe_key": key}, now=100)
        alert_state.apply(state, d1, now=100)
        d2 = alert_state.decide(state, {"subject": "s", "body": "b", "dedupe_key": key}, now=200)
        self.assertEqual((d1.kind, d2.kind), ("raise", "silent"))
        d3 = alert_state.decide(state, {"subject": "r", "body": "b", "resolve_scope": key}, now=300)
        self.assertEqual(d3.kind, "resolve")
        self.assertEqual(d3.cleared, [key])


if __name__ == "__main__":
    unittest.main()
