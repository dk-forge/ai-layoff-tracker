"""Operational mail leaves through Resend, and dedup did not pay for it.

TWO SEPARATE PROMISES ARE UNDER TEST HERE.

THE FIRST IS THE SPLIT. CI alerts and subscriber digests shared one Brevo free
tier of 300 emails a day. One bad afternoon of red CI could have eaten the
allowance the readers depend on, and a send that hits a provider ceiling mid-run
can mark a subscriber as sent when they were not. Operations moved to Resend,
whose ~100 a day is ample for alarms and useless for a mailing list. The reader
digest keeps Brevo and is not touched by any of this.

THE SECOND IS THE BIGGER ONE. `/alert` was a route on the WordPress host the
alerts are ABOUT. On 2026-07-31 Bluehost 504'd and the sibling tracker's alerter
failed four times saying "HTTP 504 from /alert", mute at exactly the moment it
was needed, and the host went down twice again on 2026-08-19. Resend removes the
coupling outright.

AND THE PRICE THAT MUST NOT BE PAID. The open/resolved state used to live in the
endpoint. It now lives in a committed file, and a committed file read at
checkout and written at push has a race a server-side option did not. Every scar
in CLAUDE.md that the old design earned is re-asserted below against the new one:
one cause is one email, RECOVERED fires once, a live-data incident is one alarm
across branches, two slices stay two alarms, and an undeliverable alert is held
rather than lost and never reddens its own run.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import alert_state
import ci_alert
import opsmail

REPO = Path(__file__).resolve().parents[2]


def _code_strings(path):
    """Every string literal a module actually EVALUATES, docstrings excluded.

    Prose is not behaviour. `ci_alert.py` must go on describing the /alert route
    it used to post to, because that history is why the current design exists;
    what it must never do again is build a request to it.
    """
    import ast
    tree = ast.parse(Path(path).read_text())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


def _run_lines(path):
    """Workflow lines that are not comments."""
    return [ln for ln in Path(path).read_text().splitlines()
            if not ln.strip().startswith("#")]


class _Ledger:
    """A real alert_state.json in a temp dir, driven by the real code."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "alert_state.json"
        self._old = os.environ.get("ALERT_STATE_PATH")
        os.environ["ALERT_STATE_PATH"] = str(self.path)
        return self

    def __exit__(self, *exc):
        if self._old is None:
            os.environ.pop("ALERT_STATE_PATH", None)
        else:
            os.environ["ALERT_STATE_PATH"] = self._old
        self._tmp.cleanup()

    def open_keys(self):
        return sorted((alert_state.load(self.path).get("open") or {}))


def _sent(sends):
    """A stub Resend that records what it was asked to send."""
    def once(subject, body, idem=""):
        sends.append({"subject": subject, "body": body, "idem": idem})
        return True, "emailed the owner", False
    return once


class TheAlarmNoLongerDependsOnTheThingItMonitors(unittest.TestCase):
    def test_the_send_path_never_builds_a_request_to_the_wordpress_host(self):
        """The 2026-07-31 defect, closed at the root rather than survived.

        The held outbox made delivery durable, which was the right fix for
        delivery and no fix at all for the dependency. This asserts the
        dependency itself is gone.
        """
        seen = []

        def spy(method, path, body=None, extra_headers=None):
            seen.append(f"{method} {opsmail.API}{path}")
            return 200, {"id": "re_1"}

        with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch.object(opsmail, "_request", spy):
            ok, note, _t = opsmail.send_once("s", "b")
        self.assertTrue(ok, note)
        self.assertEqual(seen, ["POST https://api.resend.com/emails"])
        for line in seen:
            self.assertNotIn("asktherecruiter.com", line)

    def test_the_alerter_builds_no_request_to_the_wordpress_host(self):
        """Prose about /alert is welcome and is why this design exists. A URL
        the code can still evaluate is not."""
        for mod in ("ci_alert.py", "alert_drain.py", "opsmail.py"):
            for literal in _code_strings(REPO / "railway" / mod):
                self.assertNotIn("wp-json/layoffs/v1/alert", literal,
                                 f"{mod} can still build a request to the host "
                                 "it reports about")
                self.assertNotIn("WP_API_KEY", literal,
                                 f"{mod} still reads the host's credential")

    def test_every_request_carries_a_real_user_agent(self):
        """Learned the hard way, twice.

        The WP host's ModSecurity blocks `python-requests`, which is an iron
        rule in CLAUDE.md. Resend's API sits behind Cloudflare, and the very
        first selftest run got `403 Error 1010: the site owner has banned your
        browser signature` for urllib's default `Python-urllib/3.12`. A 403 is a
        SETTLED refusal, so every alert would have been held and none would ever
        have arrived. Nothing else in this repo would have noticed.
        """
        seen = {}

        class _Resp:
            status = 200

            def read(self):
                return b'{"id":"re_1"}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def urlopen(req, timeout=None):
            seen.update(req.headers)
            return _Resp()

        with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch("urllib.request.urlopen", urlopen):
            opsmail.send_once("s", "b")
        agent = seen.get("User-agent") or seen.get("User-Agent") or ""
        self.assertTrue(agent, "no User-Agent: Cloudflare answers 403 to this")
        self.assertNotIn("urllib", agent.lower())
        self.assertNotIn("python", agent.lower())

    def test_the_key_is_never_printed_even_when_the_api_echoes_it(self):
        with mock.patch.dict(os.environ, {"RESEND_API_KEY": "re_supersecret"}), \
                mock.patch.object(opsmail, "_request",
                                  lambda *a, **k: (401, '{"message":"bad key re_supersecret"}')):
            ok, note, _t = opsmail.send_once("s", "b")
        self.assertFalse(ok)
        self.assertNotIn("re_supersecret", note)
        self.assertIn("<redacted>", note)

    def test_an_alert_never_looks_like_a_newsletter(self):
        """An alarm that arrives wearing the digest's From name is one the owner
        filters with the digest."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPS_MAIL_FROM", None)
            self.assertIn("Ops", opsmail.sender())
        digest = (REPO / "railway" / "digest_transport.py").read_text()
        self.assertNotIn(opsmail.DEFAULT_FROM, digest)


class DedupSurvivedTheMove(unittest.TestCase):
    """Every scar CLAUDE.md records, re-asserted against the committed ledger."""

    def _alert(self, sends, key="tests:main:abcdef", subject="CI RED: Tests"):
        payload = {"subject": subject, "body": "b", "dedupe_key": key}
        with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch.object(opsmail, "send_once", _sent(sends)), \
                redirect_stdout(io.StringIO()):
            ok, note, _t = ci_alert.post_alert("", "", payload)
        return ok, note

    def _resolve(self, sends, scope="tests:main"):
        payload = {"resolve_scope": scope, "subject": "RECOVERED: Tests",
                   "body": "green"}
        with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch.object(opsmail, "send_once", _sent(sends)), \
                redirect_stdout(io.StringIO()):
            ok, note, _t = ci_alert.post_alert("", "", payload)
        return ok, note

    def test_the_same_cause_eight_times_in_an_afternoon_is_one_email(self):
        """2026-07-30: one Spirit assertion reddened CI eight consecutive times.
        Eight identical emails is how an alert channel gets filtered."""
        sends = []
        with _Ledger():
            for _ in range(8):
                self._alert(sends)
        self.assertEqual(len(sends), 1, f"mailed {len(sends)} times, not once")

    def test_a_genuinely_different_cause_mails_immediately(self):
        sends = []
        with _Ledger():
            self._alert(sends, key="tests:main:aaaa")
            self._alert(sends, key="tests:main:bbbb")
        self.assertEqual(len(sends), 2,
                         "suppressing a DIFFERENT breakage is the failure mode "
                         "that lets a real defect stay live")

    def test_recovered_fires_once_and_only_when_something_was_open(self):
        sends = []
        with _Ledger() as ledger:
            self._alert(sends)
            self.assertEqual(len(ledger.open_keys()), 1)
            _ok, note = self._resolve(sends)
            self.assertEqual(len(sends), 2, "the RECOVERED notice did not fire")
            self.assertEqual(ledger.open_keys(), [])
            # Every subsequent green run of an already-green workflow.
            for _ in range(5):
                _ok, note = self._resolve(sends)
            self.assertEqual(len(sends), 2,
                             "a clear that mails on every green run is noise, "
                             "and noise is what gets a sender filtered")
            self.assertIn("nothing was open", note)

    def test_the_recovered_email_names_what_it_clears(self):
        sends = []
        with _Ledger():
            self._alert(sends, key="tests:main:aaaa", subject="CI RED: one")
            self._alert(sends, key="tests:main:bbbb", subject="CI RED: two")
            self._resolve(sends)
        self.assertIn("This clears 2 open alert(s)", sends[-1]["body"])
        self.assertIn("CI RED: one", sends[-1]["body"])
        self.assertIn("CI RED: two", sends[-1]["body"])

    def test_a_scope_clears_only_its_own_alarms(self):
        sends = []
        with _Ledger() as ledger:
            self._alert(sends, key="tests:main:aaaa")
            self._alert(sends, key="tests:live.data:bbbb")
            self._resolve(sends, scope="tests:main")
            self.assertEqual(ledger.open_keys(), ["tests:live.data:bbbb"],
                             "a green run on one branch just erased a live-data "
                             "incident nobody has looked at")

    def test_a_live_data_incident_is_one_alarm_whatever_branch_noticed(self):
        """2026-08-10/11: one open incident mailed six times in seven hours,
        because the scope carried the branch and every branch reads the same one
        wrong number."""
        sends = []
        cause = ("No headline moves without rows to explain it | "
                 "United States jobs, all time")
        with mock.patch.object(ci_alert, "live_data_identity", lambda c: cause):
            with _Ledger():
                for branch in ("main", "feat-one", "feat-two", "docs-three"):
                    _s, _b, key = ci_alert.build_alert(
                        repo="r", workflow="Tests", branch=branch, event="push",
                        run_url="u", run_id="1", cause=cause, context=[])
                    self._alert(sends, key=key)
        self.assertEqual(len(sends), 1,
                         "the branch is back in the key and one incident is "
                         "mailing once per branch again")

    def test_a_reminder_arrives_after_a_fortnight_and_not_before(self):
        """Total silence until a green run would mean a breakage the owner
        missed once is never mentioned again."""
        state = alert_state.empty()
        payload = {"subject": "CI RED: Tests", "body": "b",
                   "dedupe_key": "tests:main:aaaa"}
        now = 1_700_000_000
        alert_state.apply(state, alert_state.decide(state, payload, now), now)
        thirteen = now + 13 * 86400
        self.assertEqual(alert_state.decide(state, payload, thirteen).kind, "silent")
        fifteen = now + 15 * 86400
        later = alert_state.decide(state, payload, fifteen)
        self.assertEqual(later.kind, "raise")
        self.assertTrue(later.subject.startswith("STILL FAILING: "))

    def test_the_window_is_the_one_the_endpoint_used(self):
        self.assertEqual(alert_state.REMIND_AFTER_SECONDS, 14 * 24 * 3600)


class TheClaimIsCommittedBeforeTheSend(unittest.TestCase):
    """The one thing that keeps a committed ledger from being a downgrade.

    A server-side option's read-modify-write window is milliseconds. A file read
    at checkout and pushed thirty seconds later is not, and two runners that both
    read "nothing is open" would both mail. So the claim is written FIRST and the
    push is the compare-and-swap. A quota fix that costs the dedup guarantee is a
    bad trade, and this is the assertion that says it was not made.
    """

    def test_the_ledger_is_written_before_anything_is_sent(self):
        order = []

        def once(subject, body, idem=""):
            order.append("send")
            return True, "emailed the owner", False

        with _Ledger() as ledger:
            real_save = alert_state.save

            def spy(doc, path=alert_state.STATE):
                order.append("claim")
                return real_save(doc, path)

            with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                    mock.patch.object(alert_state, "save", spy), \
                    mock.patch.object(opsmail, "send_once", once), \
                    redirect_stdout(io.StringIO()):
                ci_alert.post_alert("", "", {"subject": "s", "body": "b",
                                             "dedupe_key": "tests:main:aaaa"})
            self.assertEqual(order, ["claim", "send"],
                             "the send happened before the claim, so a second "
                             "runner reading the old ledger would mail too")
            self.assertEqual(ledger.open_keys(), ["tests:main:aaaa"])

    def test_the_runner_that_loses_the_race_goes_quiet_rather_than_mailing(self):
        """The loser re-derives on the new main, finds the cause open, stops."""
        state = alert_state.empty()
        payload = {"subject": "s", "body": "b", "dedupe_key": "tests:main:aaaa"}
        now = 1_700_000_000
        winner = alert_state.decide(state, payload, now)
        self.assertTrue(winner.sends)
        alert_state.apply(state, winner, now)
        loser = alert_state.decide(state, payload, now + 5)
        self.assertFalse(loser.sends)
        self.assertIn("already open", loser.note)

    def test_resend_gets_an_idempotency_key_as_the_second_guard(self):
        sends = []
        with _Ledger(), \
                mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch.object(opsmail, "send_once", _sent(sends)), \
                redirect_stdout(io.StringIO()):
            ci_alert.post_alert("", "", {"subject": "s", "body": "b",
                                         "dedupe_key": "tests:main:aaaa"})
        # The key names the TRANSITION, not the cause. It was
        # `alt-raise-{cause}` until 2026-08-19, which reused one key across
        # every open/close cycle of a cause and answered a genuine re-raise
        # with HTTP 409 invalid_idempotent_request — five times in one day.
        # See AnIdempotencyKeyNamesATransitionNotACause below.
        idem = sends[0]["idem"]
        self.assertTrue(idem, "two runners that both got past the ledger would "
                              "send two emails without this")
        self.assertTrue(idem.startswith("alt-raise-tests:main:aaaa-"),
                        f"{idem} no longer identifies the cause it is about")
        self.assertNotEqual(idem, "alt-raise-tests:main:aaaa",
                            "a key that is only the cause cannot tell this "
                            "raise from the same cause reopening tomorrow")

    def test_the_commit_is_off_everywhere_except_the_workflows_that_set_it(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(alert_state.COMMIT_ENV, None)
            self.assertFalse(alert_state.commit_enabled())
        for name in ("ci-alert.yml", "ci-noise-report.yml"):
            yml = (REPO / ".github" / "workflows" / name).read_text()
            self.assertIn("ALERT_STATE_COMMIT", yml,
                          f"{name} sends alerts without claiming them durably")
            self.assertIn("git config user.email", yml,
                          f"{name} claims by committing and has no committer")


class AnUndeliverableAlertIsStillHeld(unittest.TestCase):
    """The outbox was built for a down host. A relay can be down too."""

    def _run(self, argv, **env):
        keys = ("RESEND_API_KEY", "ALERT_ENVELOPE", "ALERT_STATE_PATH")
        old = {k: os.environ.get(k) for k in keys}
        os.environ.update(env)
        for k in keys:
            if k not in env and k != "ALERT_STATE_PATH":
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

    def test_resend_being_down_holds_the_alert_and_keeps_the_run_green(self):
        with _Ledger(), tempfile.TemporaryDirectory() as tmp:
            envelope = f"{tmp}/held.json"
            with mock.patch.object(
                    opsmail, "send_once",
                    lambda *a, **k: (False, "HTTP 503 from Resend: busy", True)), \
                    mock.patch.object(ci_alert, "_BACKOFF", ()), \
                    mock.patch.object(ci_alert, "fetch_failed_log",
                                      lambda *a: "AssertionError: it broke"):
                code, out = self._run(
                    ["--run-id", "1", "--workflow", "Tests",
                     "--conclusion", "failure", "--envelope", envelope],
                    RESEND_API_KEY="k")
            self.assertEqual(code, 0,
                             "a relay outage must not manufacture a red run of "
                             "its own, which is what manufactures more alerts")
            self.assertIn("HELD", out)
            held = json.loads(Path(envelope).read_text())
        self.assertEqual(held["kind"], "alert")
        self.assertTrue(held["payload"]["subject"].startswith("CI RED:"))

    def test_the_only_red_left_is_could_neither_send_nor_hold(self):
        with _Ledger():
            with mock.patch.object(
                    opsmail, "send_once",
                    lambda *a, **k: (False, "HTTP 503 from Resend", True)), \
                    mock.patch.object(ci_alert, "_BACKOFF", ()), \
                    mock.patch.object(ci_alert, "fetch_failed_log",
                                      lambda *a: "AssertionError: it broke"):
                code, out = self._run(["--run-id", "1", "--workflow", "Tests",
                                       "--conclusion", "failure"],
                                      RESEND_API_KEY="k")
        self.assertEqual(code, 1)
        self.assertIn("nobody will be told", out.lower())

    def test_the_drain_does_not_re_rule_a_held_alert(self):
        """A held alert has already been claimed. Sending it through the ledger
        again would find its own cause open and swallow it."""
        import alert_drain
        import alert_outbox
        sends = []
        doc = alert_outbox.empty()
        alert_outbox.enqueue(doc, key="tests:main:aaaa", kind="alert",
                             scope="tests:main",
                             payload={"subject": "CI RED: Tests", "body": "b",
                                      "dedupe_key": "tests:main:aaaa"},
                             reason="HTTP 503 from Resend")
        with _Ledger() as ledger:
            # The alarm is already open, exactly as it would be after the claim.
            state = alert_state.load(ledger.path)
            state["open"]["tests:main:aaaa"] = {"first": 1, "last": 1,
                                                "subject": "CI RED: Tests"}
            alert_state.save(state, ledger.path)
            with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                    mock.patch.object(opsmail, "send_once", _sent(sends)), \
                    redirect_stdout(io.StringIO()):
                delivered, remaining, _n, _down = alert_drain.drain(doc)
        self.assertEqual((delivered, remaining), (1, 0))
        self.assertEqual(len(sends), 1,
                         "the drain ran the held alert back through the ledger "
                         "and the ledger suppressed it as a duplicate of itself")


class TheSubscriberDigestIsUntouched(unittest.TestCase):
    """Different budget, different failure domain, deliberately.

    Brevo's 300 a day is the larger allowance and that is where readers live.
    Resend's ~100 a day is ample for alarms and useless for a list, which is
    exactly why this is the right way round. If a later session ever routes the
    reader digest through the operations relay, this fails.
    """

    def test_the_reader_digest_still_sends_through_brevo(self):
        """ARMED on Brevo SMTP since 2026-08-16. `digest_transport.py` has
        offered a Resend seam all along and that is fine; what matters is which
        one the send workflow SELECTS, because the whole point of the split is
        that alarms cannot spend the readers' allowance."""
        yml = (REPO / ".github" / "workflows" / "digest-send.yml").read_text()
        self.assertIn("DIGEST_TRANSPORT: smtp", yml,
                      "the reader digest was moved onto the operations relay, "
                      "which puts alarms and readers back in one quota")

    def test_no_reader_path_imports_the_operations_sender(self):
        for name in ("digest_transport.py", "digest_send.py", "digest_layout.py"):
            path = REPO / "railway" / name
            if not path.exists():
                continue
            self.assertNotIn("import opsmail", path.read_text(),
                             f"{name} is a reader path and must not share the "
                             "operations sender or its failure domain")

    def test_the_operations_sender_does_not_reach_into_the_digest(self):
        src = (REPO / "railway" / "opsmail.py").read_text()
        self.assertNotIn("import digest_transport", src,
                         "two failure domains, deliberately: an alarm must not "
                         "be able to break by way of the reader relay")


class TheOperationalWorkflowsCarryTheKey(unittest.TestCase):
    """A rewired sender that no workflow hands a credential is a silent alarm,
    and silence is the whole failure class this repo keeps closing."""

    CARRIERS = ("ci-alert.yml", "alert-drain.yml", "health-digest.yml",
                "ci-noise-report.yml", "opsmail-selftest.yml")

    def test_every_operational_sender_is_given_resend(self):
        for name in self.CARRIERS:
            yml = (REPO / ".github" / "workflows" / name).read_text()
            self.assertIn("secrets.RESEND_API_KEY", yml,
                          f"{name} sends operational mail with no way to send it")

    def test_the_alerting_path_installs_nothing(self):
        """Stdlib only. The one job whose purpose is to work when things are
        broken must not be breakable by dependency resolution."""
        for name in ("ci-alert.yml", "alert-drain.yml", "opsmail-selftest.yml"):
            path = REPO / ".github" / "workflows" / name
            for line in _run_lines(path):
                self.assertNotIn("pip install", line,
                                 f"{name} grew a pip install")
        for mod in ("opsmail", "alert_state"):
            src = (REPO / "railway" / f"{mod}.py").read_text()
            self.assertNotIn("import requests", src,
                             f"{mod}.py is on the notification path and must be "
                             "stdlib only")


if __name__ == "__main__":
    unittest.main()


class AnIdempotencyKeyNamesATransitionNotACause(unittest.TestCase):
    """HTTP 409 `invalid_idempotent_request`, five times on 2026-08-19.

    The key was `alt-raise-{cause}`, and a cause is not a transition. Measured
    from the committed ledger's own history that day:

        09:19 RAISE deploy-wordpress-plugin:main:973999a049809e5c
        09:24 CLEAR   "
        18:41 RAISE   "     same key, new run, new body  ->  HTTP 409

    The 18:41 raise was a genuine alarm about a genuine new red run and the
    ledger was right to send it. Resend refused it because the key had been
    spent at 09:19 on a different body. Resolves had the same shape: the key
    varied only by HOW MANY alerts were cleared, so clearing one alert twice in
    a day was one key and two bodies.

    Both obvious repairs are worse. Folding the body into the key means every
    run is a distinct key and Resend dedupes nothing. Making the body identical
    per cause means the key and payload AGREE — so Resend answers 200 with the
    original email's id, having sent nothing, and the 18:41 alarm disappears in
    silence instead of failing loudly.
    """

    def _decide(self, state, payload, now):
        return alert_state.decide(state, payload, now)

    def test_a_cause_that_reopens_is_a_new_key(self):
        payload = {"subject": "CI RED", "body": "run 1",
                   "dedupe_key": "deploy:main:973999a0"}
        state = {"open": {}}
        first = self._decide(state, payload, 1787119140)      # 09:19
        alert_state.apply(state, first, 1787119140)
        self.assertTrue(first.sends)

        clear = self._decide(state, {"subject": "RECOVERED", "body": "",
                                     "resolve_scope": "deploy:main"},
                             1787119440)                       # 09:24
        alert_state.apply(state, clear, 1787119440)

        payload2 = dict(payload, body="run 2")
        again = self._decide(state, payload2, 1787152860)      # 18:41
        self.assertTrue(again.sends, "the cause reopened; this is a real alarm")
        self.assertNotEqual(
            first.idempotency_key(), again.idempotency_key(),
            "a reopened cause reusing its old key is the 409 that held five "
            "alerts on 2026-08-19")

    def test_the_same_transition_keeps_one_key(self):
        """The guard has to still guard. A retry or a re-drain of the SAME
        decision must collapse at Resend rather than mail the owner twice."""
        state = {"open": {}}
        payload = {"subject": "CI RED", "body": "b", "dedupe_key": "tests:main:aa"}
        d = self._decide(state, payload, 1787119140)
        alert_state.apply(state, d, 1787119140)
        # Re-derived later from the ledger, as the STILL FAILING reminder is.
        later = self._decide(state, payload,
                             1787119140 + alert_state.REMIND_AFTER_SECONDS + 60)
        self.assertTrue(later.sends)
        self.assertEqual(d.idempotency_key(), later.idempotency_key(),
                         "one open alarm is one transition, however often it "
                         "is repeated")

    def test_clearing_the_same_scope_twice_in_a_day_is_two_keys(self):
        state = {"open": {"deploy:main:aa": {"first": 100, "last": 100,
                                             "subject": "s"}}}
        one = self._decide(state, {"subject": "RECOVERED", "body": "",
                                   "resolve_scope": "deploy:main"}, 200)
        alert_state.apply(state, one, 200)
        state["open"]["deploy:main:bb"] = {"first": 300, "last": 300,
                                           "subject": "s"}
        two = self._decide(state, {"subject": "RECOVERED", "body": "",
                                   "resolve_scope": "deploy:main"}, 400)
        self.assertTrue(one.sends and two.sends)
        self.assertEqual(len(one.cleared), len(two.cleared),
                         "the old key varied only by this count")
        self.assertNotEqual(one.idempotency_key(), two.idempotency_key(),
                            "two clears of one scope in a day is two emails, "
                            "and the old key made the second a 409")

    def test_an_undeduped_alert_carries_no_key_at_all(self):
        """The legacy shape has no cause, so there is nothing to dedup. A
        shared `alt-raise-` prefix would have collided every undeduped alert
        with every other one inside the same 24 hours — and where the bodies
        happened to match, Resend would have silently sent only the first."""
        d = alert_state.decide({"open": {}}, {"subject": "s", "body": "b"}, 1)
        self.assertTrue(d.sends)
        self.assertEqual(d.idempotency_key(), "")


class TheDrainCarriesTheGuardItUsedToDrop(unittest.TestCase):
    """`alert_drain.drain()` calls `ci_alert.deliver(payload)` with no `idem`.

    So every alert that had ever been HELD was re-sent to Resend with no
    idempotency key on it — on the one path where the same decision genuinely
    is sent more than once. alert-drain.yml says so in its own failure text:
    "alerts delivered this run may be re-sent on the next tick" when it cannot
    commit the drained outbox. The key now travels inside the held payload, so
    the drain reproduces it months later.
    """

    def test_post_alert_stamps_the_key_into_the_payload_it_may_have_to_hold(self):
        payload = {"subject": "CI RED", "body": "b", "dedupe_key": "tests:main:aa"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            with mock.patch.dict(os.environ, {"ALERT_STATE_PATH": str(path)},
                                 clear=False), \
                    mock.patch.object(ci_alert, "deliver",
                                      lambda *a, **k: (False, "HTTP 504", True)):
                ci_alert.post_alert("", "", payload)
        self.assertTrue(payload.get("idempotency_key"),
                        "a held payload without its key is a held payload the "
                        "drain will send unguarded")

    def test_deliver_uses_the_key_the_held_payload_carries(self):
        seen = {}

        def _once(_site, _key, payload, idem):
            seen["idem"] = idem
            return True, "emailed the owner", False

        with mock.patch.object(ci_alert, "_post_once", _once):
            ci_alert.deliver({"subject": "s", "body": "b",
                              "idempotency_key": "alt-raise-tests:main:aa-99"})
        self.assertEqual(seen["idem"], "alt-raise-tests:main:aa-99")

    def test_an_explicit_key_still_wins_over_the_payload(self):
        seen = {}

        def _once(_site, _key, payload, idem):
            seen["idem"] = idem
            return True, "ok", False

        with mock.patch.object(ci_alert, "_post_once", _once):
            ci_alert.deliver({"idempotency_key": "from-payload"}, idem="explicit")
        self.assertEqual(seen["idem"], "explicit")

    def test_a_pre_migration_held_payload_still_delivers(self):
        """Everything currently in the committed outbox was held before this
        change and carries no key. It must still drain, not crash."""
        seen = {}

        def _once(_site, _key, payload, idem):
            seen["idem"] = idem
            return True, "ok", False

        with mock.patch.object(ci_alert, "_post_once", _once):
            ok, _note, _t = ci_alert.deliver({"subject": "s", "body": "b"})
        self.assertTrue(ok)
        self.assertEqual(seen["idem"], "")


class ADarkSourceUsesTheSameDedupContract(unittest.TestCase):
    """A collector that publishes nothing new mails through THIS machinery.

    Not a parallel channel: `source_alert` composes a payload and hands it to
    `alert_state.claim` and `ci_alert.deliver`, so every property the rest of
    this file pins applies to it unchanged. What is pinned here is the part
    specific to a dark source: the cause key must not carry the day count (it
    changes every morning and would defeat dedup entirely), a backlog is ONE
    email, and each source still recovers on its own.
    """

    ROWS = [
        {"key": "warn:KS", "days_dark": 110, "rate_per_year": 15.35,
         "p0": 0.0098, "classification": "drift", "last_reason": "110d dark"},
        {"key": "warn:MI", "days_dark": 81, "rate_per_year": 62.06,
         "p0": 0.0, "classification": "drift", "last_reason": "81d dark"},
    ]

    def setUp(self):
        import source_alert
        self.SA = source_alert

    def test_the_cause_key_ignores_the_day_count(self):
        a = self.SA.cause_key(dict(self.ROWS[0]))
        b = self.SA.cause_key(dict(self.ROWS[0], days_dark=111, p0=0.004))
        self.assertEqual(a, b)

    def test_two_sources_are_two_causes(self):
        self.assertNotEqual(self.SA.cause_key(self.ROWS[0]),
                            self.SA.cause_key(self.ROWS[1]))

    def test_the_reason_class_changes_the_cause(self):
        drifted = self.SA.cause_key(self.ROWS[0])
        hard = self.SA.cause_key(dict(self.ROWS[0], classification="hard_failure"))
        self.assertNotEqual(drifted, hard)

    def test_the_scope_prefixes_the_key_so_a_resolve_can_match_it(self):
        scope, key = self.SA.cause_key(self.ROWS[0])
        self.assertTrue(key.startswith(scope + ":"))
        self.assertTrue(alert_state.KEY_SAFE.match(key), key)

    def test_a_backlog_is_one_email_and_two_open_causes(self):
        sends = []
        with _Ledger() as ledger, mock.patch.object(opsmail, "send_once",
                                                    _sent(sends)):
            with mock.patch.object(alert_state, "commit_enabled",
                                   lambda: False):
                ok, claimed, _note = self.SA.announce(self.ROWS)
        self.assertTrue(ok)
        self.assertEqual(len(sends), 1, "six dark states must not be six emails")
        self.assertEqual(len(claimed), 2)
        for row in self.ROWS:
            self.assertIn(self.SA.identity(row["key"])[1], sends[0]["body"])

    def test_the_same_dark_source_is_not_mailed_twice(self):
        sends = []
        with _Ledger(), mock.patch.object(opsmail, "send_once", _sent(sends)):
            with mock.patch.object(alert_state, "commit_enabled", lambda: False):
                self.SA.announce(self.ROWS)
                ok, claimed, note = self.SA.announce(self.ROWS)
        self.assertEqual(len(sends), 1)
        self.assertFalse(ok)
        self.assertEqual(claimed, [])

    def test_recovery_clears_one_source_and_leaves_the_other_open(self):
        sends = []
        with _Ledger() as ledger, mock.patch.object(opsmail, "send_once",
                                                    _sent(sends)):
            with mock.patch.object(alert_state, "commit_enabled", lambda: False):
                self.SA.announce(self.ROWS)
                self.SA.announce_recovery("warn:KS")
                still_open = ledger.open_keys()
        self.assertEqual(len(sends), 2)
        self.assertTrue(any("Kansas" in s["subject"] for s in sends))
        self.assertEqual(len(still_open), 1)
        self.assertIn("warn:mi", still_open[0])

    def test_the_subject_leads_with_country_then_source(self):
        subject, _body = self.SA.build([self.ROWS[0]])
        self.assertTrue(subject.startswith("United States - Kansas WARN"),
                        subject)

    def test_the_paste_ready_line_comes_before_the_numbers(self):
        _subject, body = self.SA.build(self.ROWS)
        self.assertLess(body.index("Paste this into a Claude Code session"),
                        body.index("its own rate:"))

    def test_the_email_forbids_the_one_fix_that_would_be_worst(self):
        _subject, body = self.SA.build([self.ROWS[0]])
        self.assertIn("do not change the freshness threshold", body)

    def test_an_unavailable_source_never_reaches_the_mailer(self):
        """WY is not public by statute. Mailing about it monthly is how the
        whole channel gets filtered."""
        import source_freshness
        ledger = source_freshness.load_ledger()
        self.assertEqual(ledger["sources"]["warn:WY"]["state"],
                         source_freshness.UNAVAILABLE)
        self.assertEqual(
            [r["key"] for r in source_freshness.broken(ledger)], [])
