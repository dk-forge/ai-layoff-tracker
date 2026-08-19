"""The alerting path has to survive the host it alerts about.

2026-07-31, 00:48-00:55 UTC: Bluehost answered 504 for everything under /blog/.
In the sibling tracker — the same alerter design, the same host — jobs failed,
and then the CI failure alert failed four times reporting them, because /alert
is a route on the host that was down. It exited non-zero each time, so one
outage manufactured four extra red runs, each of which read as "the alerter is
broken" when the alerter was working perfectly.

This file pins the three properties that fix cost:

  1. an alert raised during an outage is HELD and eventually delivered,
  2. a delivery failure never becomes a new red run,
  3. the queue cannot quietly become its own problem.

No network anywhere. Offline, no keys.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import alert_drain
import alert_outbox
import ci_alert
import gh_fallback


def _held(key="tests:main:abc", scope="tests:main"):
    doc = alert_outbox.empty()
    alert_outbox.enqueue(doc, key=key, kind="alert", scope=scope,
                         payload={"subject": "CI RED: Tests", "body": "b",
                                  "dedupe_key": key},
                         reason="HTTP 504 from /alert")
    return doc


class HeldAlertsSurviveAndArrive(unittest.TestCase):
    def test_an_alert_held_during_an_outage_is_delivered_afterwards(self):
        doc = _held()
        orig = ci_alert.deliver
        ci_alert.deliver = lambda *a, **k: (True, "emailed the owner", False)
        try:
            delivered, remaining, _note, down = alert_drain.drain(
                doc, "https://x.invalid", "k")
        finally:
            ci_alert.deliver = orig
        self.assertEqual((delivered, remaining, down), (1, 0, False))

    def test_a_drain_against_a_still_down_host_keeps_everything(self):
        doc = _held()
        orig = ci_alert.deliver
        ci_alert.deliver = lambda *a, **k: (False, "HTTP 504", True)
        try:
            delivered, remaining, note, down = alert_drain.drain(
                doc, "https://x.invalid", "k")
        finally:
            ci_alert.deliver = orig
        self.assertEqual((delivered, remaining, down), (0, 1, True))
        self.assertIn("504", note)
        self.assertEqual(alert_outbox.pending(doc)[0]["attempts"], 2,
                         "the failed attempt has to be recorded, or a stuck "
                         "queue looks identical on every tick")

    def test_a_down_host_stops_the_drain_rather_than_being_hammered(self):
        doc = _held("a")
        alert_outbox.enqueue(doc, key="b", kind="alert", scope="s2",
                             payload={"subject": "second"}, reason="")
        tries = []

        def boom(*a, **k):
            tries.append(1)
            return False, "HTTP 504", True

        orig, ci_alert.deliver = ci_alert.deliver, boom
        try:
            alert_drain.drain(doc, "https://x.invalid", "k")
        finally:
            ci_alert.deliver = orig
        self.assertEqual(len(tries), 1,
                         "a down host learns nothing from the second POST")

    def test_the_outbox_survives_a_round_trip_through_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert_outbox.json"
            alert_outbox.save(_held(), path)
            self.assertEqual(
                json.loads(path.read_text())["entries"][0]["state"], "pending")
            self.assertEqual(len(alert_outbox.pending(alert_outbox.load(path))), 1)

    def test_an_empty_outbox_makes_no_request_at_all(self):
        """The normal case, and the reason this tick can run every 30 minutes
        against a host that has already shown its ceiling twice in one day."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert_outbox.json"
            alert_outbox.save(alert_outbox.empty(), path)

            def never(*a, **k):
                raise AssertionError("an empty outbox must not touch the host")

            orig, ci_alert.deliver = ci_alert.deliver, never
            try:
                os.environ.setdefault("RESEND_API_KEY", "k")
                self.assertEqual(alert_drain.main(["--outbox", str(path)]), 0)
            finally:
                ci_alert.deliver = orig


class TheQueueDoesNotBecomeItsOwnProblem(unittest.TestCase):
    def test_the_same_alert_twice_is_held_once(self):
        doc = alert_outbox.empty()
        for _ in range(8):
            alert_outbox.enqueue(doc, key="k", kind="alert", scope="s",
                                 payload={"subject": "x"}, reason="HTTP 504")
        held = alert_outbox.pending(doc)
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["attempts"], 8)

    def test_a_recovery_cancels_a_red_that_was_never_sent(self):
        """If Tests failed while the host was down and passed before the queue
        drained, the RED never went out — so there is nothing to clear and
        nothing to tell anyone. Otherwise one outage mails a failure and its
        recovery, both already stale on arrival."""
        doc = _held()
        outcome, _ = alert_outbox.enqueue(
            doc, key="resolve:tests:main", kind="resolve", scope="tests:main",
            payload={"resolve_scope": "tests:main"}, reason="HTTP 504")
        self.assertEqual(outcome, "cancelled")
        self.assertEqual(alert_outbox.pending(doc), [])

    def test_a_recovery_with_nothing_held_for_its_scope_is_still_queued(self):
        """The RED may have been delivered BEFORE the host went down, in which
        case the endpoint holds open state that only a resolve can clear."""
        doc = alert_outbox.empty()
        outcome, _ = alert_outbox.enqueue(
            doc, key="resolve:warn:main", kind="resolve", scope="warn:main",
            payload={"resolve_scope": "warn:main"}, reason="HTTP 504")
        self.assertEqual(outcome, "queued")

    def test_delivery_order_is_the_order_things_happened(self):
        doc = alert_outbox.empty()
        alert_outbox.enqueue(doc, key="first", kind="alert", scope="a",
                             payload={}, reason="")
        alert_outbox.enqueue(doc, key="second", kind="alert", scope="b",
                             payload={}, reason="")
        doc["entries"][0]["raised_at"] = "2026-07-31T00:48:00+00:00"
        doc["entries"][1]["raised_at"] = "2026-07-31T00:52:00+00:00"
        self.assertEqual([e["key"] for e in alert_outbox.pending(doc)],
                         ["first", "second"])

    def test_a_queue_that_never_drains_becomes_loud(self):
        doc = alert_outbox.empty()
        for _ in range(alert_outbox.FAIL_LOUD_ATTEMPTS):
            alert_outbox.enqueue(doc, key="k", kind="alert", scope="s",
                                 payload={}, reason="HTTP 401")
        self.assertTrue(alert_outbox.stuck(doc),
                        "a queue that quietly never drains is the original "
                        "silence with extra steps")

    def test_history_is_bounded_but_pending_work_never_is(self):
        doc = alert_outbox.empty()
        for i in range(alert_outbox.HISTORY_KEPT + 40):
            _, entry = alert_outbox.enqueue(doc, key=f"k{i}", kind="alert",
                                            scope="s", payload={}, reason="")
            alert_outbox.mark_delivered(entry)
        alert_outbox.enqueue(doc, key="live", kind="alert", scope="s",
                             payload={}, reason="")
        doc["entries"] = alert_outbox._trim(doc["entries"])
        self.assertEqual(len(alert_outbox.pending(doc)), 1)
        self.assertEqual(len(doc["entries"]), alert_outbox.HISTORY_KEPT + 1)

    def test_an_unreadable_outbox_is_an_empty_one_not_an_exception(self):
        """This is read from the FAILURE path of the alerter. A notifier that
        crashes while handling a failure has told nobody anything."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert_outbox.json"
            path.write_text("{not json")
            self.assertEqual(alert_outbox.load(path)["entries"], [])


class TheLogSaysWhatTheRunDoes(unittest.TestCase):
    """A drain that goes red must not have just said it was green.

    The host_down branch printed "This run is NOT failing" BEFORE attempting
    the host-independent fallback, and on the one path where that fallback also
    fails the run returns 1 — a red `Alert drain`, which ci-alert.yml turns into
    an email. The log is the only place a session can tell "the host was down
    and we kept the alert" from "the alerter is broken", so a green claim on a
    red run is not cosmetic. The behaviour is correct and is not what changed.
    """

    def _drain(self, fallback_ok):
        """(exit code, printed log) for a stuck queue against a down host."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert_outbox.json"
            doc = alert_outbox.empty()
            for _ in range(alert_outbox.FAIL_LOUD_ATTEMPTS):
                alert_outbox.enqueue(doc, key="k", kind="alert", scope="s",
                                     payload={"subject": "CI RED: Tests"},
                                     reason="HTTP 504 from /alert")
            alert_outbox.save(doc, path)
            buf = io.StringIO()
            orig_post, orig_open = ci_alert.deliver, gh_fallback.open_or_update
            ci_alert.deliver = lambda *a, **k: (False, "HTTP 504", True)
            gh_fallback.open_or_update = lambda *a, **k: (
                fallback_ok, "issue #1 updated" if fallback_ok else "no GH_TOKEN")
            try:
                with contextlib.redirect_stdout(buf):
                    out = alert_drain.main(["--outbox", str(path),
                                            "--site", "https://x.invalid"])
            finally:
                ci_alert.deliver = orig_post
                gh_fallback.open_or_update = orig_open
            return out, buf.getvalue()

    def setUp(self):
        # The credential is Resend's now: the drain stopped needing the host it
        # exists to survive.
        self._key = os.environ.get("RESEND_API_KEY")
        os.environ["RESEND_API_KEY"] = "k"

    def tearDown(self):
        if self._key is None:
            os.environ.pop("RESEND_API_KEY", None)
        else:
            os.environ["RESEND_API_KEY"] = self._key

    def test_a_held_queue_is_green_and_says_so(self):
        code, log = self._drain(fallback_ok=True)
        self.assertEqual(code, 0)
        self.assertIn("This run is NOT failing", log)

    def test_the_red_path_does_not_claim_the_run_is_green(self):
        code, log = self._drain(fallback_ok=False)
        self.assertEqual(code, 1, "nothing can reach the owner; red is correct")
        self.assertNotIn("This run is NOT failing", log)
        self.assertIn("THIS RUN IS FAILING", log)

    def test_the_documented_exit_codes_cover_the_red_path(self):
        # The docstring listed two causes for exit 1 and this was not one of
        # them, so the only written account of when this job goes red was
        # missing the case that actually fires during an outage.
        self.assertIn("fallback could not be used", alert_drain.__doc__)


class TheWorkflowsThatCarryThis(unittest.TestCase):
    """Properties that live only in YAML, where nothing else checks them."""

    def _wf(self, name):
        try:
            import yaml
        except ImportError:
            self.skipTest("pyyaml is not installed")
        return yaml.safe_load(
            (Path(__file__).resolve().parents[2] / ".github/workflows" / name).read_text())

    def test_the_drainer_is_armed(self):
        crons = [e["cron"] for e in self._wf("alert-drain.yml")[True]["schedule"]]
        self.assertTrue(crons, "a dormant drainer means a held alert is a lost one")

    def test_the_alerter_can_commit_what_it_could_not_send(self):
        wf = self._wf("ci-alert.yml")
        self.assertEqual(wf["permissions"]["contents"], "write",
                         "without write access an undeliverable alert has "
                         "nowhere to go")
        hold = next(s for s in wf["jobs"]["alert"]["steps"]
                    if "alert_outbox.py enqueue" in (s.get("run") or ""))
        run = hold["run"]
        self.assertIn("git reset --hard origin/main", run)
        self.assertLess(run.index("git reset --hard"),
                        run.index("alert_outbox.py enqueue"),
                        "the envelope is folded in before the reset, which "
                        "discards it")
        self.assertIn("for attempt in", run)
        self.assertIn("::error::", run)
        self.assertTrue(run.rstrip().endswith("exit 1"),
                        "an alert that reaches neither the owner nor the queue "
                        "must be loud")

    def test_the_hold_step_runs_even_when_the_alert_step_failed(self):
        wf = self._wf("ci-alert.yml")
        hold = next(s for s in wf["jobs"]["alert"]["steps"]
                    if "alert_outbox.py enqueue" in (s.get("run") or ""))
        self.assertIn("cancelled()", str(hold.get("if")),
                      "the default success gate would skip the hold on exactly "
                      "the path that needs it")

    def test_the_alerter_still_refuses_to_report_on_itself(self):
        """The recursion guard matters more now that a held alert leaves a
        GREEN run: a mail loop is not a failure mode worth discovering."""
        wf = self._wf("ci-alert.yml")
        self.assertIn("CI failure alert", wf["jobs"]["alert"]["if"])


if __name__ == "__main__":
    unittest.main()


class AHeldAlertCannotAgeOutOfSIGHT(unittest.TestCase):
    """The attempt count only moves when the drain RUNS.

    `stuck()` asked exactly one question — has this failed FAIL_LOUD_ATTEMPTS
    times? — and every held entry accrues attempts only when alert-drain.yml
    executes and manages to commit the result. Disable that workflow, break it,
    run out of Actions minutes, or let GitHub's inactivity rule stop the
    schedule, and an entry sits at `attempts: 1` for ever: nothing red, nothing
    stuck, `ops_status [4b]` printing "1 held (most-tried: x1)" and exiting 0.

    The dashboard got GREENER the more completely the delivery path had failed,
    which is the exact failure class this repository keeps finding. Age is the
    question the attempt count cannot answer.
    """

    def _aged(self, hours, attempts=1):
        doc = alert_outbox.empty()
        _, entry = alert_outbox.enqueue(doc, key="k", kind="alert", scope="s",
                                        payload={"subject": "CI RED: Tests"},
                                        reason="HTTP 504")
        entry["raised_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=hours)
        ).isoformat(timespec="seconds")
        entry["attempts"] = attempts
        return doc

    def test_an_alert_nobody_ever_retried_still_becomes_loud(self):
        doc = self._aged(alert_outbox.MAX_HELD_HOURS + 1, attempts=1)
        self.assertTrue(
            alert_outbox.overdue(doc),
            "held past the ceiling with one attempt is a drain that is not "
            "running, not an outage that will pass")
        self.assertTrue(
            alert_outbox.stuck(doc),
            "an entry nobody is even asking about is an alert nobody received")

    def test_the_ordinary_short_outage_still_does_not_page(self):
        """The design working must never look like the design failing."""
        doc = self._aged(0.2, attempts=2)
        self.assertFalse(alert_outbox.overdue(doc))
        self.assertFalse(alert_outbox.stuck(doc))

    def test_status_exits_non_zero_on_an_aged_entry(self):
        doc = self._aged(alert_outbox.MAX_HELD_HOURS + 3, attempts=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outbox.json"
            alert_outbox.save(doc, path)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = alert_outbox.main(["status", "--path", str(path)])
        self.assertEqual(code, 2, "an aged held alert must not exit 0")
        self.assertIn("not reaching the owner", buf.getvalue())

    def test_an_unparseable_raised_at_is_unknown_not_an_escalation(self):
        """PASS / FAIL / UNKNOWN are three states. An age that cannot be read
        is not evidence of lateness, and must not manufacture a page on its
        own — the attempt count still speaks for the entry."""
        doc = alert_outbox.empty()
        _, entry = alert_outbox.enqueue(doc, key="k", kind="alert", scope="s",
                                        payload={}, reason="")
        entry["raised_at"] = "not-a-date"
        self.assertEqual(alert_outbox._age_hours(entry), 0.0)
        self.assertFalse(alert_outbox.overdue(doc))
