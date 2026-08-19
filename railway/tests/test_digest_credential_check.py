"""Can the digest still authenticate? Answered without sending anybody an email.

THE INCIDENT THIS ANSWERS, 2026-08-19.

The armed Brevo credential had been rejected with `535 5.7.8 Authentication
failed` since 2026-08-17, and nothing said so for three days. Not because the
signal was ignored - because it was never produced. The credential path is only
walked when there is a message in hand, every scheduled run had nobody due, and
`0 sent of 0 eligible` is a true, complete and green description of such a run.
The mailer's health row read `ok`. The only two runs that touched the relay were
manual test sends, which stay out of the health ledger on purpose, so the whole
of the evidence was a red workflow_dispatch nobody watches.

So there are two guards here, and they are different guards:

  * a LOGIN with no message after it, so a run with an empty list still learns
    whether it could have sent;
  * a health row that carries the credential state beside the send counts, so
    "nobody was due" can never again be recorded in the same words as "the
    relay accepts us".

And FOUR states, kept apart. A missing key is ABSENT and exits 0, because the
sender is dormant by design and a red run for an unset secret is how red runs
stop meaning anything. A refused key is REJECTED and is a fault. Everything
else is UNKNOWN, which is not a pass.
"""
import os
import smtplib
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_send                      # noqa: E402
import digest_transport as dt           # noqa: E402
import ops_status                       # noqa: E402


class FakeSmtp:
    """A relay that answers LOGIN however the test says, and counts messages.

    Counting the messages is the point of half these tests: a credential check
    that sends anything is not a credential check, it is a send.
    """

    def __init__(self, host, port, timeout=None, raises=None):
        self.host = host
        self.logins = []
        self.sent = []
        self.quit_called = False
        self.raises = raises

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.quit_called = True
        return False

    def login(self, user, password):
        self.logins.append(user)
        if self.raises is not None:
            raise self.raises

    def send_message(self, mail):
        self.sent.append(mail)


def _smtp(raises=None, user="brevo-user", password="pw"):
    holder = {}

    def factory(host, port, timeout=None):
        holder["client"] = FakeSmtp(host, port, timeout, raises)
        return holder["client"]

    transport = dt.SmtpTransport("smtp.example.test", 587, user, password,
                                 factory=factory)
    return transport, holder


REJECTED_535 = smtplib.SMTPAuthenticationError(
    535, b"5.7.8 Authentication failed")


class TheSmtpCheck(unittest.TestCase):

    def test_a_refused_login_is_a_fault_and_says_which_secrets(self):
        transport, holder = _smtp(raises=REJECTED_535)
        check = transport.verify()
        self.assertEqual(check.state, dt.REJECTED)
        self.assertTrue(check.is_fault)
        self.assertFalse(check.is_pass)
        self.assertIn("DIGEST_SMTP_PASSWORD", check.detail)
        self.assertIn("535", check.detail)
        # It hung up, and it never built a message.
        self.assertTrue(holder["client"].quit_called)
        self.assertEqual(holder["client"].sent, [])

    def test_an_accepted_login_sends_nothing(self):
        transport, holder = _smtp()
        check = transport.verify()
        self.assertEqual(check.state, dt.OK)
        self.assertTrue(check.is_pass)
        self.assertEqual(holder["client"].logins, ["brevo-user"])
        self.assertEqual(holder["client"].sent, [],
                         "a credential check that puts a message on the wire "
                         "is a send, whatever it is called")
        self.assertTrue(holder["client"].quit_called)

    def test_a_temporary_refusal_is_unknown_rather_than_a_rotation(self):
        """A 4xx is the relay asking us to come back, not a wrong password.

        Reading it as REJECTED would send the owner to rotate a secret that was
        never broken, and the rotation is the one step no code here can do.
        """
        transport, _ = _smtp(raises=smtplib.SMTPAuthenticationError(
            454, b"4.7.0 Temporary authentication failure"))
        check = transport.verify()
        self.assertEqual(check.state, dt.UNKNOWN)
        self.assertFalse(check.is_fault)
        self.assertFalse(check.is_pass)

    def test_an_unreachable_relay_is_unknown_and_not_a_fault(self):
        transport, _ = _smtp(raises=OSError("connection reset"))
        check = transport.verify()
        self.assertEqual(check.state, dt.UNKNOWN)
        self.assertFalse(check.is_fault)

    def test_no_user_means_there_is_no_login_to_prove(self):
        transport, _ = _smtp(user="")
        check = transport.verify()
        self.assertEqual(check.state, dt.UNKNOWN)
        self.assertIn("DIGEST_SMTP_USER", check.detail)

    def test_the_check_dials_the_relay_the_same_way_the_send_does(self):
        """One connection routine, so a check cannot pass on a path a send
        never takes."""
        transport, holder = _smtp()
        transport.verify()
        first = holder["client"].host
        transport._connect()
        self.assertEqual(holder["client"].host, first)

    def test_an_address_in_the_relays_error_never_reaches_the_detail(self):
        transport, _ = _smtp(raises=smtplib.SMTPAuthenticationError(
            535, b"5.7.8 rejected for sender@asktherecruiter.com"))
        check = transport.verify()
        self.assertNotIn("sender@asktherecruiter.com", check.detail)
        self.assertIn("[address]", check.detail)


class TheResendCheck(unittest.TestCase):

    def _transport(self, opener):
        return dt.ResendTransport("re_key", opener=opener)

    def test_a_rejected_key_is_a_fault(self):
        import urllib.error

        def opener(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 401, "no", {}, None)

        check = self._transport(opener).verify()
        self.assertEqual(check.state, dt.REJECTED)
        self.assertIn("RESEND_API_KEY", check.detail)

    def test_a_server_error_says_nothing_about_the_key(self):
        import urllib.error

        def opener(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 503, "later", {}, None)

        self.assertEqual(self._transport(opener).verify().state, dt.UNKNOWN)

    def test_the_check_is_a_get_and_is_not_the_send_endpoint(self):
        seen = {}

        class Response:
            def read(self, n=None):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def opener(request, timeout=None):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            return Response()

        check = self._transport(opener).verify()
        self.assertEqual(check.state, dt.OK)
        self.assertEqual(seen["method"], "GET")
        self.assertNotEqual(seen["url"], dt.RESEND_ENDPOINT)


class TheOtherTwoStates(unittest.TestCase):

    def test_nothing_armed_is_absent_and_is_not_a_fault(self):
        transport, _ = dt.resolve_transport({})
        check = transport.verify()
        self.assertEqual(check.state, dt.ABSENT)
        self.assertFalse(check.is_fault)
        self.assertFalse(check.is_pass, "dormant is not a passing credential")

    def test_a_provider_with_no_check_inherits_unknown_not_a_pass(self):
        """A transport added in five years must not get a pass for free."""

        class NewProvider(dt.Transport):
            name = "newprovider"
            sends = True

        check = NewProvider().verify()
        self.assertEqual(check.state, dt.UNKNOWN)
        self.assertFalse(check.is_pass)


class TheHealthRow(unittest.TestCase):
    """`0 eligible` and `credential rejected` may never read the same."""

    def _reading(self, state, sends=True, details=("daily: 0 sent of 0 eligible",),
                 failed=0):
        credential = dt.CredentialCheck(state, "smtp", "because")
        transport = mock.Mock(sends=sends)
        return digest_send.health_reading(credential, transport, list(details), failed)

    def test_a_quiet_run_now_says_the_credential_was_accepted(self):
        status, detail = self._reading(dt.OK)
        self.assertEqual(status, "ok")
        self.assertIn("credential=OK", detail)
        self.assertIn("0 eligible", detail)

    def test_a_refused_credential_is_degraded_even_with_nobody_due(self):
        status, detail = self._reading(dt.REJECTED)
        self.assertEqual(status, "degraded")
        self.assertIn("credential=REJECTED", detail)

    def test_an_unestablished_credential_does_not_resolve_to_a_pass(self):
        status, detail = self._reading(dt.UNKNOWN)
        self.assertEqual(status, "degraded")
        self.assertIn("credential=UNKNOWN", detail)

    def test_a_dormant_sender_stays_green_and_says_why(self):
        status, detail = self._reading(dt.ABSENT, sends=False)
        self.assertEqual(status, "ok")
        self.assertIn("credential=ABSENT", detail)
        self.assertIn("dormant", detail)

    def test_the_two_facts_are_not_merged(self):
        """A row must never let a send count stand in for the credential."""
        _, quiet = self._reading(dt.OK)
        _, broken = self._reading(dt.REJECTED)
        self.assertNotEqual(quiet, broken,
                            "a rejected credential and an empty list produced "
                            "the same health row for three days")


def _env(**over):
    env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k",
           "DIGEST_FREQ": "daily"}
    env.update(over)
    return env


class TheRun(unittest.TestCase):

    def _main(self, env, check):
        transport = mock.Mock(sends=True, name_="smtp")
        transport.name = "smtp"
        transport.describe.return_value = "smtp"
        transport.verify.return_value = check
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(transport, "notice")), \
                mock.patch.object(digest_send, "_call") as call, \
                mock.patch.object(digest_send, "_record_health") as health:
            call.return_value = {"available": True, "recipients": [],
                                 "sections": {}, "send_id": 0,
                                 "from": "2026-08-18", "to": "2026-08-19"}
            code = digest_send.main()
        return code, call, health

    def test_a_refused_credential_reddens_the_run_and_reads_no_recipient(self):
        code, call, health = self._main(
            _env(), dt.CredentialCheck(dt.REJECTED, "smtp", "535"))
        self.assertEqual(code, 2)
        call.assert_not_called()
        health.assert_called_once()
        self.assertIn("credential=REJECTED", health.call_args.args[2])
        self.assertEqual(health.call_args.args[0], "degraded")

    def test_a_missing_credential_is_still_not_a_red_run(self):
        code, _, health = self._main(
            _env(), dt.CredentialCheck(dt.ABSENT, "dryrun", "nothing armed"))
        self.assertEqual(code, 0)
        self.assertIn("credential=ABSENT", health.call_args.args[2])

    def test_an_unreachable_relay_is_not_a_red_run_either(self):
        code, call, health = self._main(
            _env(), dt.CredentialCheck(dt.UNKNOWN, "smtp", "timed out"))
        self.assertEqual(code, 0)
        call.assert_called()
        self.assertEqual(health.call_args.args[0], "degraded")

    def test_a_quiet_run_records_a_row_that_names_the_credential(self):
        code, _, health = self._main(
            _env(), dt.CredentialCheck(dt.OK, "smtp", "accepted"))
        self.assertEqual(code, 0)
        self.assertIn("credential=OK", health.call_args.args[2])

    def test_verify_only_stamps_nothing_and_touches_no_recipient(self):
        code, call, health = self._main(
            _env(DIGEST_VERIFY_ONLY="1"),
            dt.CredentialCheck(dt.REJECTED, "smtp", "535"))
        self.assertEqual(code, 2)
        call.assert_not_called()
        health.assert_not_called()

    def test_verify_only_on_a_good_credential_exits_zero(self):
        code, call, health = self._main(
            _env(DIGEST_VERIFY_ONLY="1"),
            dt.CredentialCheck(dt.OK, "smtp", "accepted"))
        self.assertEqual(code, 0)
        call.assert_not_called()
        health.assert_not_called()


class TheSessionStartView(unittest.TestCase):
    """ops_status is where a session learns this without reading a run log."""

    def _lines(self, detail):
        return ops_status.digest_credential_lines(
            {"digest_mailer": {"detail": detail}})

    def test_a_refused_credential_is_an_issue_a_human_must_clear(self):
        lines, bad = self._lines("credential=REJECTED - the relay refused us")
        self.assertTrue(bad)
        self.assertIn("RUNBOOK", " ".join(lines))

    def test_an_accepted_credential_is_not_an_issue(self):
        lines, bad = self._lines("credential=OK; daily: 0 sent of 0 eligible")
        self.assertFalse(bad)
        self.assertTrue(lines[0].startswith("credential OK"))

    def test_a_row_written_before_this_change_is_unknown_not_a_pass(self):
        lines, bad = self._lines("daily: 0 sent of 0 eligible via smtp, 0 failed")
        self.assertFalse(bad)
        self.assertTrue(lines[0].startswith("credential UNKNOWN"))

    def test_an_unreadable_health_endpoint_is_unknown_not_a_pass(self):
        lines, bad = ops_status.digest_credential_lines(None)
        self.assertTrue(lines[0].startswith("credential UNKNOWN"))
        self.assertFalse(bad)

    def test_a_dormant_sender_reads_as_dormant_rather_than_working(self):
        lines, bad = self._lines("credential=ABSENT (dormant, nothing armed)")
        self.assertFalse(bad)
        self.assertTrue(lines[0].startswith("credential DORMANT"))


class TheWorkflow(unittest.TestCase):

    def test_the_manual_credential_check_is_wired_and_stamps_nothing(self):
        body = open(os.path.join(REPO, ".github", "workflows", "digest-send.yml"),
                    encoding="utf-8").read()
        self.assertIn("verify_only:", body)
        self.assertIn("DIGEST_VERIFY_ONLY:", body)

    def test_no_em_or_en_dashes(self):
        for name in ("digest_send.py", "digest_transport.py"):
            body = open(os.path.join(RAILWAY, name), encoding="utf-8").read()
            for ch in ("—", "–"):
                self.assertNotIn(ch, body, f"{name} carries a long dash")


if __name__ == "__main__":
    unittest.main()
