"""The sending half of the email digest.

The signup half was already complete and is covered by
tests/test_digest_subscription.py. These are the guards on putting a message
on the wire, and they are written against a FAKE transport rather than against
one vendor, because the promises are properties of the MESSAGE:

  * nothing sends without a transport credential, and that state exits 0;
  * no tracking pixel or remote fetch can appear in a rendered digest, and a
    message carrying one is refused rather than cleaned up;
  * the RFC 8058 one-click unsubscribe headers are present and correctly
    shaped, and the link is reachable in both bodies;
  * a plain text part exists;
  * a figure the live endpoints cannot supply is OMITTED, never invented;
  * one recipient's failure never loses the rest of the run;
  * no address reaches a log line, an error message, or a URL.

Swapping provider must not be able to break any of these, so the policy check
lives in the base class rather than in a provider.
"""
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from html import unescape
from unittest import mock

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
PLUGIN = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_layout as layout          # noqa: E402
import digest_send                      # noqa: E402
import digest_transport as dt           # noqa: E402


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    from shutil import which
    return which("php")


UNSUB = "https://asktherecruiter.com/blog/wp-admin/admin-post.php?action=alt_digest_unsub&t=" + "a" * 64


def _payload(**over):
    base = {
        "available": True,
        "freq": "weekly",
        "send_id": 7,
        "from": "2026-08-07",
        "to": "2026-08-14",
        "subject": "[AskTheRecruiter] Weekly tracker digest",
        "sections": {
            "layoff": {
                "html": "<h2>AI Layoff Tracker</h2><p>12 verified entries.</p>",
                "text": "AI Layoff Tracker\n12 verified entries.\n",
            },
        },
        "recipients": [
            {"id": 1, "email": "reader@example.com", "unsub_url": UNSUB,
             "lists": ["layoff"]},
        ],
    }
    base.update(over)
    return base


def _message(**over):
    fields = {
        "to": "reader@example.com",
        "subject": "[AskTheRecruiter] Weekly tracker digest",
        "html": f'<p>12 verified entries.</p><p><a href="{UNSUB}">Unsubscribe</a></p>',
        "text": f"12 verified entries.\nUnsubscribe with one click:\n{UNSUB}\n",
        "from_addr": "Trackers <digest@asktherecruiter.com>",
        "reply_to": "info@asktherecruiter.com",
        "headers": {"List-Unsubscribe": f"<{UNSUB}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
    }
    fields.update(over)
    return dt.Message(**fields)


class FakeTransport(dt.Transport):
    """Stands in for every provider. Records what it was asked to deliver, so a
    test can assert that a refused message never reached the wire at all."""

    name = "fake"
    sends = True

    def __init__(self, fail_on=()):
        self.delivered = []
        self.attempts = []
        self.fail_on = set(fail_on)

    def _deliver(self, message):
        self.attempts.append(message.to)
        if message.to in self.fail_on:
            raise dt.TransportError("provider said no")
        self.delivered.append(message)
        return "fake-id"


# ---------------------------------------------------------------------------


class Dormancy(unittest.TestCase):
    """Nothing may send until the owner supplies a key, and that is not a fault."""

    def test_the_default_transport_sends_nothing(self):
        transport, notice = dt.resolve_transport({})
        self.assertIsInstance(transport, dt.DryRunTransport)
        self.assertFalse(transport.sends)
        self.assertIn("DORMANT", notice)

    def test_resend_without_its_key_falls_back_to_dry_run_and_names_the_secret(self):
        transport, notice = dt.resolve_transport({"DIGEST_TRANSPORT": "resend"})
        self.assertIsInstance(transport, dt.DryRunTransport)
        self.assertFalse(transport.sends)
        self.assertIn("RESEND_API_KEY", notice)
        self.assertIn("DORMANT", notice)

    def test_smtp_without_its_credential_falls_back_to_dry_run(self):
        transport, notice = dt.resolve_transport(
            {"DIGEST_TRANSPORT": "smtp", "DIGEST_SMTP_HOST": "smtp.example.test"})
        self.assertIsInstance(transport, dt.DryRunTransport)
        self.assertIn("DIGEST_SMTP_PASSWORD", notice)

    def test_a_typo_in_the_transport_name_sends_nothing(self):
        transport, notice = dt.resolve_transport({"DIGEST_TRANSPORT": "resnd"})
        self.assertFalse(transport.sends)
        self.assertIn("'resnd'", notice)

    def test_dry_run_beats_a_configured_provider(self):
        transport, notice = dt.resolve_transport(
            {"DIGEST_TRANSPORT": "resend", "RESEND_API_KEY": "re_live",
             "DIGEST_DRY_RUN": "1"})
        self.assertFalse(transport.sends)
        self.assertIn("DRY RUN", notice)

    def test_a_key_is_what_arms_it_and_only_a_key(self):
        transport, notice = dt.resolve_transport(
            {"DIGEST_TRANSPORT": "resend", "RESEND_API_KEY": "re_live"})
        self.assertIsInstance(transport, dt.ResendTransport)
        self.assertTrue(transport.sends)
        # The notice states what the dashboard is BELIEVED to be set to and
        # says it is a belief. It used to state a requirement ("must be OFF")
        # that stopped being the policy on 2026-08-16, and a stale requirement
        # in a run log reads like a passing check to whoever scans the output.
        # Asserted against the CONSTANT rather than against one spelling, so
        # changing the relay state does not redden this on wording alone. What
        # is actually pinned is that the log states the relay state and still
        # calls itself a belief. The off variant must ALSO say the click
        # totals survive, because "tracking is off" read alone would send the
        # next reader hunting for a regression that is not there.
        from digest_layout import RELAY_TRACKING_ON
        if RELAY_TRACKING_ON:
            self.assertIn("Relay tracking is ON", notice)
        else:
            self.assertIn("Relay tracking is OFF", notice)
            self.assertIn("first-party counter", notice)
        self.assertIn("not a passing check", notice)

    def test_a_dormant_run_exits_zero_and_puts_nothing_on_the_wire(self):
        """The whole point: a missing key is a state, not a red run."""
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k",
               "DIGEST_TRANSPORT": "resend", "DIGEST_FREQ": "weekly"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call") as call, \
                mock.patch.object(dt.ResendTransport, "_deliver") as deliver:
            call.return_value = _payload()
            code = digest_send.main()
        self.assertEqual(code, 0)
        deliver.assert_not_called()
        # And no send was claimed, so nothing is marked as delivered.
        self.assertEqual([c.args[0] for c in call.call_args_list],
                         ["digest-recipients"])


class ThePrivacyPromise(unittest.TestCase):
    """No open tracking, no remote fetch. Enforced on the message, so no
    provider can be the one that breaks it."""

    def test_a_clean_message_passes(self):
        dt.assert_message_is_clean(_message())

    def test_every_remote_fetching_tag_is_refused(self):
        for tag in ("img", "iframe", "picture", "video", "svg", "script",
                    "style", "link", "object", "embed"):
            html = (f'<p>hi</p><{tag} >x</{tag}>'
                    f'<p><a href="{UNSUB}">Unsubscribe</a></p>')
            with self.assertRaises(dt.DigestPolicyError) as ctx:
                dt.assert_message_is_clean(_message(html=html))
            self.assertIn(f"<{tag}>", str(ctx.exception))

    def test_a_pixel_smuggled_in_an_attribute_is_refused(self):
        for html in (
            f'<p background="https://evil.test/p.gif">x</p><a href="{UNSUB}">u</a>',
            f'<div src="https://evil.test/p.gif">x</div><a href="{UNSUB}">u</a>',
            f'<p style="background:url(https://evil.test/p.gif)">x</p><a href="{UNSUB}">u</a>',
        ):
            with self.assertRaises(dt.DigestPolicyError):
                dt.assert_message_is_clean(_message(html=html))

    def test_a_refused_message_never_reaches_the_transport(self):
        """A policy failure is not a degraded send. It is not a send."""
        transport = FakeTransport()
        html = f'<img src="https://evil.test/p.gif"><a href="{UNSUB}">u</a>'
        with self.assertRaises(dt.DigestPolicyError):
            transport.send(_message(html=html))
        self.assertEqual(transport.attempts, [],
                         "the provider was called with a message we promised not to send")

    def test_the_check_is_in_the_base_class_not_in_a_provider(self):
        """A provider added later must not be able to opt out by forgetting to
        call the checker, so `send` is not what a provider overrides."""
        source = open(os.path.join(RAILWAY, "digest_transport.py"), encoding="utf-8").read()
        self.assertIn("def send(self, message: Message) -> str:", source)
        for provider in ("DryRunTransport", "ResendTransport", "SmtpTransport"):
            block = source[source.index(f"class {provider}"):]
            block = block[:block.index("\nclass ") if "\nclass " in block else len(block)]
            self.assertNotIn("def send(", block,
                             f"{provider} overrides send() and so can skip the policy check")

    def test_the_real_composed_digest_carries_no_remote_anything(self):
        message = digest_send.build_message(
            _payload(), _payload()["recipients"][0],
            "Trackers <digest@asktherecruiter.com>", "info@asktherecruiter.com")
        self.assertIsNotNone(message)
        dt.assert_message_is_clean(message)
        self.assertNotIn("<img", message.html.lower())
        self.assertNotIn("url(", message.html.lower())
        # OUR message embeds nothing that fetches, and that is what the two
        # lines above check. What the FOOTER says about the relay is a separate
        # fact, and it is read from the module that composes it rather than
        # quoted here. Quoting it made this test a second definition of the
        # sentence, which is how it reddened on a rewording that broke nothing.
        # The old promise stays banned in every state: it was false from
        # 2026-08-16, and it would be false again the moment a provider is
        # swapped for one that measures.
        flat = " ".join(message.text.split())
        self.assertNotIn("no tracking pixels", flat)
        from digest_layout import TRACKING_SENTENCES
        for sentence in TRACKING_SENTENCES:
            self.assertIn(sentence, flat)

    def test_the_address_may_not_appear_in_the_body(self):
        leaky = _message(text=_message().text + "sent to reader@example.com\n")
        with self.assertRaises(dt.DigestPolicyError) as ctx:
            dt.assert_message_is_clean(leaky)
        self.assertIn("address appears in the message body", str(ctx.exception))

    def test_a_provider_error_carrying_an_address_is_scrubbed(self):
        self.assertEqual(dt._scrub("no mailbox reader@example.com here"),
                         "no mailbox [address] here")

    def test_a_log_label_is_never_the_address(self):
        label = _message().redacted()
        self.assertNotIn("reader@", label)
        self.assertTrue(label.startswith("r***@"))


class OneClickUnsubscribe(unittest.TestCase):
    """RFC 8058. A header that is nearly right buys nothing: providers only
    show the one-click button for the exact shape."""

    def test_both_headers_are_present_and_exact(self):
        message = digest_send.build_message(
            _payload(), _payload()["recipients"][0], "a@b.test", "c@d.test")
        self.assertEqual(message.headers["List-Unsubscribe"], f"<{UNSUB}>")
        self.assertEqual(message.headers["List-Unsubscribe-Post"],
                         "List-Unsubscribe=One-Click")

    def test_a_missing_header_is_refused(self):
        with self.assertRaises(dt.DigestPolicyError) as ctx:
            dt.assert_message_is_clean(_message(headers={}))
        self.assertIn("List-Unsubscribe header is missing", str(ctx.exception))

    def test_the_post_header_must_be_the_exact_rfc_value(self):
        headers = dict(_message().headers, **{"List-Unsubscribe-Post": "One-Click"})
        with self.assertRaises(dt.DigestPolicyError) as ctx:
            dt.assert_message_is_clean(_message(headers=headers))
        self.assertIn("List-Unsubscribe=One-Click", str(ctx.exception))

    def test_a_bare_or_insecure_url_is_refused(self):
        for value in (UNSUB, f"<http://{UNSUB[8:]}>", "<mailto:stop@x.test>"):
            headers = dict(_message().headers, **{"List-Unsubscribe": value})
            with self.assertRaises(dt.DigestPolicyError):
                dt.assert_message_is_clean(_message(headers=headers))

    def test_the_link_must_be_reachable_in_both_bodies(self):
        with self.assertRaises(dt.DigestPolicyError) as ctx:
            dt.assert_message_is_clean(_message(html="<p>no way out</p>"))
        self.assertIn("HTML part carries no unsubscribe link", str(ctx.exception))
        with self.assertRaises(dt.DigestPolicyError) as ctx:
            dt.assert_message_is_clean(_message(text="no way out at all, none"))
        self.assertIn("plain text part carries no unsubscribe link", str(ctx.exception))


class ThePlainTextPart(unittest.TestCase):
    def test_a_missing_text_part_is_refused(self):
        with self.assertRaises(dt.DigestPolicyError) as ctx:
            dt.assert_message_is_clean(_message(text="   "))
        self.assertIn("no usable plain text part", str(ctx.exception))

    def test_markup_in_the_text_part_is_refused(self):
        with self.assertRaises(dt.DigestPolicyError) as ctx:
            dt.assert_message_is_clean(_message(text=f"<p>hi</p> {UNSUB} and more text"))
        self.assertIn("markup", str(ctx.exception))

    def test_the_smtp_path_builds_a_real_multipart_alternative(self):
        transport = dt.SmtpTransport("smtp.test", 587, "u", "p")
        mail = transport._build(_message())
        self.assertTrue(mail.is_multipart())
        types = sorted(p.get_content_type() for p in mail.walk() if not p.is_multipart())
        self.assertEqual(types, ["text/html", "text/plain"])
        self.assertEqual(mail["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertEqual(mail["Reply-To"], "info@asktherecruiter.com")


class Identity(unittest.TestCase):
    def test_from_and_reply_to_default_to_the_verified_domain(self):
        from_addr, reply_to = dt.sender_identity({})
        self.assertIn("@asktherecruiter.com", from_addr)
        self.assertIn("@asktherecruiter.com", reply_to)

    def test_a_from_that_is_not_an_address_is_refused(self):
        with self.assertRaises(dt.DigestPolicyError) as ctx:
            dt.assert_message_is_clean(_message(from_addr="AskTheRecruiter"))
        self.assertIn("From is not a usable address", str(ctx.exception))


class OmittedNeverInvented(unittest.TestCase):
    """A figure the live endpoints cannot supply is left out. There is no
    branch anywhere that substitutes a zero or a previous period."""

    def test_a_section_the_site_could_not_compose_is_absent(self):
        payload = _payload(sections={})
        self.assertEqual(digest_send.usable_sections(payload, ["layoff"]), [])
        message = digest_send.build_message(
            payload, payload["recipients"][0], "a@b.test", "c@d.test")
        self.assertIsNone(message, "a digest with nothing true to say is not sent")

    def test_a_half_composed_section_is_dropped_rather_than_patched(self):
        for broken in ({"html": "<p>x</p>", "text": ""}, {"html": "", "text": "x"}):
            payload = _payload(sections={"layoff": broken})
            self.assertEqual(digest_send.usable_sections(payload, ["layoff"]), [])

    def test_a_reader_only_gets_the_sections_they_consented_to(self):
        payload = _payload(sections={
            "layoff": {"html": "<p>L</p>", "text": "L text"},
            "talent": {"html": "<p>T</p>", "text": "T text"}})
        names = [part[0] for part in digest_send.usable_sections(payload, ["talent"])]
        self.assertEqual(names, ["talent"])

    def test_the_run_says_so_out_loud_when_nothing_could_be_composed(self):
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k"}
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call", return_value=_payload(sections={})), \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch("sys.stdout", buf):
            code = digest_send.main()
        self.assertEqual(code, 0)
        self.assertIn("nothing true to say", buf.getvalue())

    def test_the_numbers_are_never_computed_here(self):
        """One definition of a headline number, on the site. A second one in
        this file is the defect this rules out, not a style preference."""
        source = open(os.path.join(RAILWAY, "digest_send.py"), encoding="utf-8").read()
        source = re.sub(r'""".*?"""', "", source, flags=re.S)
        source = re.sub(r"#.*", "", source)
        for banned in ("aggregate", "SELECT", "job_count", "sum(", "total ="):
            self.assertNotIn(banned, source,
                             f"{banned!r} suggests this file derives a figure of its own")


class FailureIsolation(unittest.TestCase):
    def test_one_refused_recipient_does_not_lose_the_others(self):
        payload = _payload(recipients=[
            {"id": 1, "email": "a@example.com", "unsub_url": UNSUB, "lists": ["layoff"]},
            {"id": 2, "email": "bad@example.com", "unsub_url": UNSUB, "lists": ["layoff"]},
            {"id": 3, "email": "c@example.com", "unsub_url": UNSUB, "lists": ["layoff"]},
        ])
        transport = FakeTransport(fail_on={"bad@example.com"})
        with mock.patch.object(digest_send.time, "sleep"):
            sent, failures = digest_send.send_all(payload, transport, "a@b.test", "c@d.test")
        self.assertEqual(sent, [1, 3])
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0][0], "b***@example.com")
        self.assertNotIn("bad@example.com", str(failures))

    def test_a_transport_failure_is_retried_once_then_counted(self):
        payload = _payload(recipients=[
            {"id": 1, "email": "a@example.com", "unsub_url": UNSUB, "lists": ["layoff"]}])
        transport = FakeTransport(fail_on={"a@example.com"})
        with mock.patch.object(digest_send.time, "sleep"):
            sent, failures = digest_send.send_all(payload, transport, "a@b.test", "c@d.test")
        self.assertEqual(sent, [])
        self.assertEqual(transport.attempts, ["a@example.com", "a@example.com"])

    def test_a_recipient_with_a_broken_unsubscribe_url_is_skipped_not_mailed(self):
        payload = _payload(recipients=[
            {"id": 1, "email": "a@example.com", "unsub_url": "", "lists": ["layoff"]}])
        transport = FakeTransport()
        sent, failures = digest_send.send_all(payload, transport, "a@b.test", "c@d.test")
        self.assertEqual((sent, failures, transport.attempts), ([], [], []))

    def test_everything_failing_is_a_red_run(self):
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k"}
        transport = FakeTransport(fail_on={"reader@example.com"})
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call", return_value=_payload()), \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(transport, "fake")), \
                mock.patch.object(digest_send.time, "sleep"):
            code = digest_send.main()
        self.assertEqual(code, 2)

    def test_an_unreachable_site_claims_nothing_and_is_not_a_red_run(self):
        """UNKNOWN (3), never FAIL (2). The workflow maps 3 to a green run.

        A host that cannot be reached claimed nothing and stamped nobody, so
        the next run repeats the period. What it must NOT do is redden: an
        outage that manufactures red runs manufactures CI alerts for a
        condition nobody can act on.
        """
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send.time, "sleep"), \
                mock.patch.object(digest_send, "_call", side_effect=OSError("504")):
            code = digest_send.main()
        self.assertEqual(code, 3)
        self.assertNotEqual(code, 2, "a host we could not reach is not a fault")


class TheDeployMaintenanceWindow(unittest.TestCase):
    """A 503 from this host is its deploy maintenance window, not a defect.

    THE DEFECT, run 32282266653 on 2026-08-19. A scheduled send landed while an
    FTPS deploy was mid-flight, read HTTP 503 from /digest-recipients, printed
    `::error::could not read the recipient list: HTTP 503` and exited 1. Nobody
    was mailed that day, the run went red, and a red run mails a CI alert for a
    condition that is brief, self-clearing and unactionable. Meanwhile nothing
    recorded that a digest had not gone out.

    503 is UNKNOWN, never FAIL, matching subscriber_routes.py,
    data_integrity.py and published_figures.py. And UNKNOWN is a third state,
    not a quiet pass: the skip names itself in the health row.
    """

    ENV = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k"}

    @staticmethod
    def _http(code):
        return urllib.error.HTTPError("https://x.test", code, "boom", {}, None)

    def _run(self, side_effect):
        rows = []
        buf = io.StringIO()
        with mock.patch.dict(os.environ, dict(self.ENV), clear=True), \
                mock.patch.object(digest_send, "_call", side_effect=side_effect), \
                mock.patch.object(digest_send, "_record_health",
                                  side_effect=lambda *a: rows.append(a)), \
                mock.patch.object(digest_send.time, "sleep"), \
                mock.patch("sys.stdout", buf):
            code = digest_send.main()
        return code, rows, buf.getvalue()

    def test_a_503_is_unknown_and_never_a_fault(self):
        code, _, out = self._run(self._http(503))
        self.assertEqual(code, 3, "a deploy maintenance window is UNKNOWN, not FAIL")
        self.assertNotIn("::error::", out, "a 503 must not redden the run")
        self.assertIn("maintenance window", out)

    def test_a_503_is_retried_before_anybody_is_skipped(self):
        """A deploy window is seconds to a couple of minutes, so try again."""
        calls = []
        waited = []

        def call(path, params=None, payload=None, timeout=45):
            calls.append(timeout)
            if len(calls) < 3:
                raise self._http(503)
            return _payload(recipients=[])

        with mock.patch.dict(os.environ, dict(self.ENV), clear=True), \
                mock.patch.object(digest_send, "_call", side_effect=call), \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send.time, "sleep",
                                  side_effect=waited.append), \
                mock.patch("sys.stdout", io.StringIO()):
            code = digest_send.main()
        self.assertEqual(code, 0, "the window closed, so nothing was skipped")
        self.assertGreaterEqual(len(calls), 3)
        self.assertTrue(waited, "the retries must be spaced, not hammered")

    def test_every_attempt_is_bounded_not_only_the_loop(self):
        """A hung socket must not eat the job. apt did exactly that tonight."""
        seen = []

        def call(path, params=None, payload=None, timeout=45):
            seen.append(timeout)
            raise self._http(503)

        with mock.patch.dict(os.environ, dict(self.ENV), clear=True), \
                mock.patch.object(digest_send, "_call", side_effect=call), \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send.time, "sleep"), \
                mock.patch("sys.stdout", io.StringIO()):
            digest_send.main()
        self.assertTrue(seen)
        for timeout in seen:
            self.assertLessEqual(timeout, 60, "each attempt carries its own bound")
        budget = (len(seen) * digest_send.RECIPIENT_TIMEOUT_S
                  + sum(digest_send.RECIPIENT_BACKOFF_S))
        self.assertLess(budget, 600, "one tier may not spend the workflow timeout")

    def test_a_skipped_send_is_visible_and_never_silent(self):
        """`0 sent of 0 eligible` said nothing for three days. Not again."""
        code, rows, _ = self._run(self._http(503))
        self.assertEqual(code, 3)
        self.assertTrue(rows, "a skipped send must still write the health row")
        status, entries, detail = rows[-1]
        self.assertEqual(status, "degraded", "a missed edition is not a pass")
        self.assertEqual(entries, 0)
        self.assertIn("NOT SENT", detail)
        self.assertIn("daily", detail)
        self.assertIn("credential=", detail,
                      "ops_status parses the credential state out of this row")

    def test_a_skip_does_not_read_like_a_quiet_run(self):
        skipped = self._run(self._http(503))[2]
        quiet = self._run(lambda *a, **k: _payload(recipients=[]))[2]
        self.assertNotEqual(skipped, quiet)
        self.assertNotIn("NOT SENT", quiet)

    def test_the_other_transient_host_conditions_go_the_same_way(self):
        """503 was not the only one. A gateway timeout is not a defect either."""
        for status in (408, 429, 502, 503, 504):
            with self.subTest(status=status):
                code, _, out = self._run(self._http(status))
                self.assertEqual(code, 3)
                self.assertNotIn("::error::", out)

    def test_a_status_the_host_did_not_choose_is_still_a_fault(self):
        """500 is PHP erroring inside our own route. Excusing it is the F27
        failure: a guard that stays green forever."""
        for status in (400, 401, 403, 500):
            with self.subTest(status=status):
                code, _, out = self._run(self._http(status))
                self.assertEqual(code, 2, "the site answered, and answered wrongly")
                self.assertIn("::error::", out)

    def test_a_missing_route_is_still_neither(self):
        code, rows, out = self._run(self._http(404))
        self.assertEqual(code, 0)
        self.assertIn("older than this job", out)
        self.assertEqual(rows, [], "an older plugin build is not a missed send")

    def test_a_fault_outranks_an_unknown_in_the_run_s_exit_code(self):
        self.assertEqual(digest_send._worst([3, 2]), 2)
        self.assertEqual(digest_send._worst([0, 3]), 3)
        self.assertEqual(digest_send._worst([0, 0]), 0)

    def test_a_retry_cannot_stamp_a_tier_it_did_not_send(self):
        """Attempt 1 leaves no last-sent stamp: only /digest-complete writes
        one, and it is called once, at the end, under send_id > 0."""
        calls = []

        def call(path, params=None, payload=None, timeout=45):
            calls.append(path)
            if len(calls) == 1:
                raise self._http(503)
            return _payload(recipients=[])

        with mock.patch.dict(os.environ, dict(self.ENV), clear=True), \
                mock.patch.object(digest_send, "_call", side_effect=call), \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send.time, "sleep"), \
                mock.patch("sys.stdout", io.StringIO()):
            digest_send.main()
        self.assertNotIn("digest-complete", calls,
                         "nothing was delivered, so no period may be claimed")


class RunWiring(unittest.TestCase):
    def test_a_dry_run_never_claims_a_send(self):
        """A dry run that recorded a delivery would make the next real run skip
        every person it merely printed."""
        import datetime
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k",
               "DIGEST_DRY_RUN": "1"}
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call") as call, \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send, "_today",
                                  return_value=datetime.date(2026, 8, 18)), \
                mock.patch("sys.stdout", buf):
            call.return_value = _payload()
            digest_send.main()
        self.assertEqual([c.args[0] for c in call.call_args_list], ["digest-recipients"])
        self.assertIn("would send 1 of 1", buf.getvalue())

    def test_a_real_send_records_ids_and_never_addresses(self):
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k"}
        transport = FakeTransport()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call") as call, \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(transport, "fake")), \
                mock.patch.object(digest_send.time, "sleep"):
            call.side_effect = [_payload(), {"ok": True}]
            digest_send.main()
        recorded = call.call_args_list[1]
        self.assertEqual(recorded.args[0], "digest-complete")
        body = recorded.kwargs["payload"]
        self.assertEqual(body["sent_ids"], [1])
        self.assertNotIn("@", str(body), "the recording call must carry ids, never addresses")

    def test_the_dry_run_prints_the_exact_message_and_sends_nothing(self):
        buf = io.StringIO()
        transport = dt.DryRunTransport("test", buf)
        transport.send(_message())
        out = buf.getvalue()
        self.assertIn("DRY RUN, nothing sent", out)
        self.assertIn("List-Unsubscribe:", out)
        self.assertIn("PLAIN TEXT PART", out)
        self.assertIn("HTML PART", out)
        self.assertNotIn("reader@example.com", out,
                         "even a dry run prints a label, never the address")

    def test_monday_still_runs_the_daily_tier(self):
        """THE DEFECT, 2026-08-17. A Monday returned weekly INSTEAD OF daily.

        The workflow runs once a day and this function chose one tier, so
        every daily subscriber received nothing on a Monday, silently, every
        week. The docstring said "daily every day, weekly additionally on
        Mondays" the whole time. This asserts the docstring.
        """
        import datetime
        monday = datetime.date(2026, 8, 17)
        self.assertIn("daily", digest_send.resolve_freqs({}, monday),
                      "a daily subscriber must be mailed on a Monday too")

    def test_auto_frequency_mirrors_the_sites_own_cron(self):
        import datetime
        monday = datetime.date(2026, 8, 17)
        self.assertEqual(digest_send.resolve_freqs({}, monday), ("daily", "weekly"))
        self.assertEqual(
            digest_send.resolve_freqs({}, monday + datetime.timedelta(days=1)),
            ("daily",))
        # The manual dispatch input still forces exactly one tier, on any day.
        self.assertEqual(digest_send.resolve_freqs({"DIGEST_FREQ": "daily"}, monday),
                         ("daily",))
        self.assertEqual(digest_send.resolve_freqs({"DIGEST_FREQ": "weekly"}, monday),
                         ("weekly",))
        self.assertEqual(
            digest_send.resolve_freqs({"DIGEST_FREQ": "weekly"},
                                      monday + datetime.timedelta(days=1)),
            ("weekly",))

    def test_a_monday_run_asks_the_site_for_both_tiers(self):
        """Two passes inside ONE scheduled run, each with its own send row.

        The composer, the recipient query and the lease are all keyed by
        frequency on the server, so two passes is the shape that needs no
        new server concept. What it does need is that neither pass is
        skipped, which is what this reads.
        """
        import datetime
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k"}
        transport = FakeTransport()
        transport.sends = False
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call") as call, \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(transport, "fake")), \
                mock.patch.object(digest_send, "_today",
                                  return_value=datetime.date(2026, 8, 17)), \
                mock.patch("sys.stdout", io.StringIO()), \
                mock.patch.object(digest_send.time, "sleep"):
            call.side_effect = [_payload(freq="daily", send_id=11),
                                _payload(freq="weekly", send_id=12)]
            code = digest_send.main()
        self.assertEqual(code, 0)
        asked = [c.args[1]["freq"] for c in call.call_args_list
                 if c.args[0] == "digest-recipients"]
        self.assertEqual(asked, ["daily", "weekly"])

    def test_the_limit_is_one_ceiling_for_the_whole_run(self):
        """DIGEST_LIMIT exists for a first live send, so a Monday must not
        quietly double it by giving each tier its own allowance."""
        import datetime
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k",
               "DIGEST_LIMIT": "1"}
        transport = FakeTransport()
        two = [{"id": 1, "email": "one@example.com", "unsub_url": UNSUB,
                "lists": ["layoff"]},
               {"id": 2, "email": "two@example.com", "unsub_url": UNSUB,
                "lists": ["layoff"]}]
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call") as call, \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(transport, "fake")), \
                mock.patch.object(digest_send, "_today",
                                  return_value=datetime.date(2026, 8, 17)), \
                mock.patch("sys.stdout", io.StringIO()), \
                mock.patch.object(digest_send.time, "sleep"):
            call.side_effect = [_payload(freq="daily", send_id=11, recipients=two),
                                {"ok": True}]
            digest_send.main()
        self.assertEqual(len(transport.delivered), 1,
                         "one ceiling for the run, not one per tier")
        asked = [c.args[1]["freq"] for c in call.call_args_list
                 if c.args[0] == "digest-recipients"]
        self.assertEqual(asked, ["daily"],
                         "a spent allowance must not open the other tier's "
                         "send row for a message it cannot send")

    def test_an_install_without_the_table_reads_unknown_not_zero(self):
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k"}
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call",
                                  return_value={"available": False,
                                                "reason": "no subscriber table"}), \
                mock.patch("sys.stdout", buf):
            code = digest_send.main()
        self.assertEqual(code, 0)
        self.assertIn("not a zero subscriber count", buf.getvalue())


class ServerSideGuards(unittest.TestCase):
    """includes/digest-api.php: the routes that hand out addresses."""

    @classmethod
    def setUpClass(cls):
        cls.api = open(os.path.join(PLUGIN, "includes", "digest-api.php"),
                       encoding="utf-8").read()
        cls.sub = open(os.path.join(PLUGIN, "includes", "subscribe.php"),
                       encoding="utf-8").read()

    def test_the_module_is_loaded_by_the_plugin(self):
        boot = open(os.path.join(PLUGIN, "ai-layoff-tracker.php"), encoding="utf-8").read()
        self.assertIn("require_once ALT_PLUGIN_DIR . 'includes/digest-api.php';", boot)

    def test_the_recipient_route_is_key_gated_and_fails_closed(self):
        block = self.api[self.api.index("'/digest-recipients'"):]
        block = block[:block.index("));")]
        self.assertIn("alt_api_permission", block)
        self.assertIn("__return_false", block)
        self.assertNotIn("__return_true", block,
                         "the only route that returns an address must never be public")

    def test_the_complete_route_is_key_gated(self):
        block = self.api[self.api.index("'/digest-complete'"):]
        block = block[:block.index("));")]
        self.assertIn("alt_api_permission", block)
        self.assertNotIn("__return_true", block)

    def test_the_webhook_fails_closed_without_a_signing_secret(self):
        verify = self.api[self.api.index("function alt_digest_webhook_verified"):]
        verify = verify[:verify.index("\n}")]
        self.assertIn("if ($secret === '') return false;", verify)
        self.assertIn("hash_equals(", verify)
        self.assertIn("abs(time() - (int) $ts) > 300", verify,
                      "an unbounded timestamp lets a captured request be replayed")

    def test_a_soft_bounce_removes_nobody(self):
        handler = self.api[self.api.index("function alt_api_digest_webhook"):]
        self.assertIn("permanent", handler)
        self.assertIn("A SOFT bounce", self.api)

    def test_both_senders_share_one_definition_of_who_is_due(self):
        """Two senders with two ideas of eligibility send some people twice."""
        self.assertIn("function alt_digest_due_rows", self.sub)
        sender = self.sub[self.sub.index("function alt_digest_send("):]
        sender = sender[:sender.index("\n}")]
        self.assertIn("alt_digest_due_rows($freq)", sender)
        self.assertNotIn("SELECT", sender,
                         "the built in sender must not carry its own recipient query")
        self.assertIn("alt_digest_due_rows($freq)", self.api)

    def test_a_row_already_sent_to_this_period_is_not_due(self):
        due = self.sub[self.sub.index("function alt_digest_due_rows"):]
        due = due[:due.index("\n}")]
        self.assertIn("$stamp IS NULL OR $stamp < %s", due)

    def test_the_period_guard_is_per_tier_and_not_one_shared_stamp(self):
        """Monday runs both tiers, so one shared stamp is one lost email.

        The first pass would mark the row, and the second pass would read it
        as already sent to. A subscriber taking one list daily and another
        weekly then got one email on a Monday instead of two.
        """
        due = self.sub[self.sub.index("function alt_digest_due_rows"):]
        due = due[:due.index("\n}")]
        self.assertIn("alt_digest_last_sent_column($freq)", due)
        self.assertNotIn("last_sent_at", due,
                         "the guard must not read the shared column")
        column = self.sub[self.sub.index("function alt_digest_last_sent_column"):]
        column = column[:column.index("\n}")]
        self.assertIn("last_sent_daily", column)
        self.assertIn("last_sent_weekly", column)
        self.assertIn("alt_digest_valid_freq($freq)", column,
                      "the tier must be validated before it names a column")
        # And the relay records against the same per tier column.
        complete = self.api[self.api.index("function alt_api_digest_complete"):]
        complete = complete[:complete.index("\n}")]
        self.assertIn("alt_digest_last_sent_column($freq)", complete)

    def test_both_new_columns_exist_in_the_schema(self):
        db = open(os.path.join(PLUGIN, "includes", "db.php"), encoding="utf-8").read()
        block = db[db.index("$subscribers = $wpdb->prefix"):]
        block = block[:block.index("$digest_sends")]
        self.assertIn("last_sent_daily DATETIME NULL", block)
        self.assertIn("last_sent_weekly DATETIME NULL", block)
        # A NULL after the migration would make every confirmed row due for
        # both tiers at once, which is a duplicate on the day of the repair.
        self.assertIn("SET last_sent_daily = last_sent_at", block)
        self.assertIn("SET last_sent_weekly = last_sent_at", block)

    def test_the_built_in_sender_stands_down_when_a_relay_claimed_the_tier(self):
        sender = self.sub[self.sub.index("function alt_digest_send("):]
        sender = sender[:sender.index("\n}")]
        self.assertIn("alt_digest_external_active($freq)", sender)
        # And the claim expires, so a dead relay hands sending back.
        self.assertIn("ALT_DIGEST_CLAIM_HOURS", self.api)

    def test_the_recording_route_takes_ids_and_has_no_address_column(self):
        complete = self.api[self.api.index("function alt_api_digest_complete"):]
        complete = complete[:complete.index("\n}")]
        self.assertIn("sent_ids", complete)
        self.assertNotIn("email", complete)

    def test_a_bounced_row_is_erased_on_the_same_retention_promise(self):
        purge = self.sub[self.sub.index("function alt_digest_purge"):]
        purge = purge[:purge.index("\n}")]
        self.assertIn("status IN ('unsubscribed', 'bounced')", purge)

    def test_no_composed_html_anywhere_on_the_server_side_carries_an_image(self):
        self.assertNotIn("<img", self.api.lower())
        self.assertNotIn("<img", self.sub.lower())

    @unittest.skipUnless(_php(), "php not installed")
    def test_the_new_php_parses(self):
        for path in ("includes/digest-api.php", "includes/subscribe.php"):
            proc = subprocess.run([_php(), "-l", os.path.join(PLUGIN, path)],
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class NoRedeclaredFunction(unittest.TestCase):
    """PHP fatals on a redeclared function, and a fatal in an include takes
    down every page on the site.

    This exists because it happened. 2.20.53 shipped `alt_digest_due_rows` and
    `alt_digest_period_seconds` in BOTH includes/subscribe.php and
    includes/digest-api.php, and asktherecruiter.com/blog returned 500 to every
    reader until it was reverted. Nothing caught it: `php -l` checks one file at
    a time, and the digest harness loads subscribe.php alone, so neither ever
    saw the two declarations in one process.

    So this reads EVERY plugin include the way PHP would: one namespace, and a
    name may be declared once in it. Not scoped to the digest files, because
    the defect is not about the digest.
    """

    def _declarations(self):
        import glob
        seen = {}
        for path in sorted(glob.glob(os.path.join(PLUGIN, "includes", "*.php"))
                           + [os.path.join(PLUGIN, "ai-layoff-tracker.php")]):
            body = open(path, encoding="utf-8").read()
            # Top level declarations only: a closure or a method is not a
            # global function and cannot collide with one.
            for name in re.findall(r"^function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
                                   body, re.M):
                seen.setdefault(name, []).append(os.path.basename(path))
        return seen

    def test_no_function_is_declared_in_two_plugin_files(self):
        clashes = {n: f for n, f in self._declarations().items() if len(f) > 1}
        self.assertEqual(
            clashes, {},
            "these functions are declared more than once, which is a PHP fatal "
            "on every request: "
            + "; ".join(f"{n} in {', '.join(f)}" for n, f in sorted(clashes.items())))

    def test_the_digest_api_uses_the_shared_definition_rather_than_its_own(self):
        api = open(os.path.join(PLUGIN, "includes", "digest-api.php"),
                   encoding="utf-8").read()
        self.assertNotIn("function alt_digest_due_rows", api)
        self.assertIn("alt_digest_due_rows($freq)", api,
                      "it must still CALL the shared definition")


class TheThirdList(unittest.TestCase):
    """The relay must be able to compose and count ALL THREE consent lists.

    alt_digest_lists() has offered three since the form shipped, but this file
    composed two and iterated two. Somebody who ticked ONLY "occasional
    articles and product news" confirmed their address, was never counted as a
    recipient, and received nothing, forever. A consent box with no sender
    behind it is a promise kept only in the database.
    """

    @classmethod
    def setUpClass(cls):
        cls.api = open(os.path.join(PLUGIN, "includes", "digest-api.php"),
                       encoding="utf-8").read()
        cls.sub = open(os.path.join(PLUGIN, "includes", "subscribe.php"),
                       encoding="utf-8").read()

    def _recipients_fn(self):
        body = self.api[self.api.index("function alt_api_digest_recipients"):]
        return body[:body.index("\n}")]

    def test_every_list_the_form_offers_has_a_composer(self):
        lists = self.sub[self.sub.index("function alt_digest_lists"):]
        lists = lists[:lists.index("\n}")]
        offered = set(re.findall(r"'(\w+)'\s*=>\s*array\('consent'", lists))
        self.assertEqual(offered, {"layoff", "talent", "articles"})
        for name in sorted(offered):
            self.assertIn(f"function alt_digest_compose_{name}(", self.sub,
                          f"the {name} consent box has no composer behind it")

    def test_the_relay_composes_all_three(self):
        fn = self._recipients_fn()
        for name in ("layoff", "talent", "articles"):
            self.assertRegex(fn, rf"'{name}'\s*=>\s*'alt_digest_compose_{name}'",
                             f"the relay never composes the {name} section")

    def test_the_relay_counts_an_articles_subscriber_as_a_recipient(self):
        """The eligibility loop is the half that decides who gets an email at
        all. A list missing HERE is an address that is never returned."""
        fn = self._recipients_fn()
        loop = fn[fn.index("foreach (alt_digest_due_rows"):]
        self.assertRegex(
            loop, r"array\('layoff',\s*'talent',\s*'articles'\)",
            "the eligibility loop does not iterate all three lists, so an "
            "articles-only subscriber can never become a recipient")

    def test_the_built_in_sender_composes_and_iterates_all_three(self):
        sender = self.sub[self.sub.index("function alt_digest_send("):]
        sender = sender[:sender.index("\n}")]
        self.assertIn("alt_digest_compose_articles(", sender)
        self.assertRegex(sender, r"array\('layoff',\s*'talent',\s*'articles'\)")


class ManageYourSubscriptions(unittest.TestCase):
    """Every digest offers a way to change what you get, not only a way to
    stop everything. One-click unsubscribe is a blunt instrument: a reader who
    wants one of three lists and gets three has exactly one button, and using
    it costs us the other two."""

    MANAGE = "https://asktherecruiter.com/blog/ai-layoff-tracker/#alt-digest"

    def _msg(self):
        payload = _payload(manage_url=self.MANAGE)
        return digest_send.build_message(
            payload, payload["recipients"][0],
            "Trackers <digest@asktherecruiter.com>", "info@asktherecruiter.com")

    def test_the_manage_link_is_in_both_body_parts(self):
        msg = self._msg()
        self.assertIn(self.MANAGE, msg.html,
                      "the HTML part offers no way to change preferences")
        self.assertIn(self.MANAGE, msg.text,
                      "the plain text part offers no way to change preferences")

    def test_it_sits_beside_the_unsubscribe_and_does_not_replace_it(self):
        msg = self._msg()
        self.assertIn(UNSUB, msg.html)
        self.assertIn(UNSUB, msg.text)
        dt.assert_message_is_clean(msg)

    def test_a_payload_without_one_omits_the_link_rather_than_guessing(self):
        """An older plugin build does not send the field. A guessed URL in a
        million inboxes is worse than no link."""
        payload = _payload()
        msg = digest_send.build_message(
            payload, payload["recipients"][0],
            "Trackers <digest@asktherecruiter.com>", "info@asktherecruiter.com")
        self.assertNotIn("To change what you get", msg.html)
        self.assertNotIn("To change what you get", msg.text)
        dt.assert_message_is_clean(msg)

    def test_a_manage_url_off_our_own_site_is_refused(self):
        payload = _payload(manage_url="https://evil.example/prefs")
        msg = digest_send.build_message(
            payload, payload["recipients"][0],
            "Trackers <digest@asktherecruiter.com>", "info@asktherecruiter.com")
        self.assertNotIn("evil.example", msg.html)
        self.assertNotIn("evil.example", msg.text)

    def test_the_server_side_sender_offers_it_too(self):
        """The fallback offers the link, and offers it from the shared blocks.

        The set-equality guard lives in TheTwoFootersAreOneDefinition below.
        This one only checks the fallback still has a manage link at all.
        """
        sub = open(os.path.join(PLUGIN, "includes", "subscribe.php"),
                   encoding="utf-8").read()
        self.assertIn("function alt_digest_manage_url", sub)
        self.assertIn("#alt-digest", sub)
        sender = _php_function(sub, "alt_digest_send")
        self.assertIn("alt_digest_manage_url()", sender)
        self.assertIn("alt_digest_footer_html(", sender)

    def test_the_route_hands_the_relay_the_url_rather_than_the_relay_building_it(self):
        api = open(os.path.join(PLUGIN, "includes", "digest-api.php"),
                   encoding="utf-8").read()
        self.assertIn("'manage_url'", api)
        send = open(os.path.join(RAILWAY, "digest_send.py"), encoding="utf-8").read()
        self.assertNotIn("asktherecruiter.com/blog/ai-layoff-tracker", send,
                         "the sender must not carry a hard coded site URL")


# ---------------------------------------------------------------------------
# Reading one function out of the plugin, and reading a rendered footer back
# down to the words a person sees. Both sides of the comparison below have to
# be reduced to sentences before they can be compared at all.
# ---------------------------------------------------------------------------
def _php_function(src, name):
    """The body of one PHP function, from `function name(` to its closing brace."""
    start = src.index(f"function {name}(")
    return src[start:src.index("\n}", start)]


def _php_sentences(src, name):
    """Every sentence literal inside one PHP function, in source order.

    A sentence is a single quoted literal ending in a full stop. The array
    keys, the anchors and the styles are none of those, so the filter needs no
    list of things to ignore and cannot go stale when one is added.
    """
    body = _php_function(src, name)
    return tuple(m.group(1) for m in re.finditer(r"'([^']*\.)'", body)
                 if " " in m.group(1))


def _visible(html):
    """The words a reader sees: tags dropped, entities resolved, space collapsed.

    A tag is removed rather than replaced by a space, because a link ending
    mid sentence would otherwise put one in front of the comma after it. Block
    ends get the space instead, which is where a reader sees one.
    """
    text = html.replace("</p>", "</p> ").replace("</td>", "</td> ")
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _sentences(text):
    """Split visible text into sentences, keeping the full stop."""
    return tuple(s.strip().rstrip(".") + "." for s in text.split(". ")
                 if s.strip())


class TheTwoFootersAreOneDefinition(unittest.TestCase):
    """A class of bug that survives for months because nothing fails.

    THE SHAPE. The digest footer is composed three times: the relay renders it
    twice (HTML and plain text, railway/digest_layout.py) and the wp_mail
    fallback renders it a third time in PHP. Which one a reader gets depends on
    whether an external relay has claimed the tier, so the reader's experience
    silently depends on infrastructure state.

    WHAT HAPPENED. On 2026-08-19 "Manage your subscriptions" was withdrawn
    because it named a preference centre that does not exist. The relay copy
    was corrected; the fallback kept the old wording and was caught by a grep.
    Its test asserted the fallback "offers it too", so it checked for the
    PRESENCE of a link and stayed green while the two senders told readers
    different things.

    WHY THESE TESTS AND NOT MORE ASSERTED SENTENCES. Asserting the current
    wording in both places closes one instance and leaves the class open: the
    next sentence to change drifts the same way and the assertions have to be
    hand-updated in two languages or they go stale. These compare the two
    definitions to EACH OTHER and compare each rendering to its own definition,
    so a sentence added to one side is red with nothing to remember.
    """

    UNSUB = "https://asktherecruiter.com/blog/digest-unsubscribe/?t=x"
    MANAGE = "https://asktherecruiter.com/blog/ai-layoff-tracker/#alt-digest"

    @classmethod
    def setUpClass(cls):
        cls.sub = open(os.path.join(PLUGIN, "includes", "subscribe.php"),
                       encoding="utf-8").read()

    def test_the_plugin_and_the_relay_define_the_same_sentences(self):
        """The mirror, the way ALT_RELAY_TRACKING is mirrored.

        The plugin is the authority: the manage URL and the signup form it
        points at live there. This fails on a sentence added, removed or
        reworded on either side.
        """
        php = _php_sentences(self.sub, "alt_digest_footer_blocks")
        py = layout.footer_sentences(True)
        self.assertEqual(php, py,
                         "the wp_mail fallback and the relay would tell a "
                         "reader different things about the same email")

    def test_the_fallback_sender_types_no_reader_facing_prose(self):
        """The structural half: prose that is not in the blocks cannot ship.

        alt_digest_send() renders alt_digest_footer_html() and writes no
        footer sentence of its own, so there is nowhere for a second wording
        to live.
        """
        sender = _php_function(self.sub, "alt_digest_send")
        for sentence in layout.footer_sentences(True):
            head = " ".join(sentence.split()[:4])
            self.assertNotIn(head, sender,
                             f"alt_digest_send types its own footer prose: {head!r}")
        # The withdrawn wording, checked where a reader could reach it. The
        # file still explains it in a comment, and it has to: a rule with its
        # reason deleted is a rule the next session talks itself out of.
        for name in ("alt_digest_footer_blocks", "alt_digest_footer_html"):
            self.assertNotIn("Manage your subscriptions",
                             _php_function(self.sub, name),
                             "the withdrawn preference centre wording is back")

    def test_the_rendered_html_footer_says_exactly_those_sentences(self):
        """No sentence reaches the HTML part that is not in the definition."""
        html = layout._footer(self.UNSUB, self.MANAGE)
        visible = _visible(html)
        for sentence in layout.TRACKING_SENTENCES:
            visible = visible.replace(sentence, "")
        self.assertEqual(_sentences(re.sub(r"\s+", " ", visible).strip()),
                         layout.footer_sentences(True))

    def test_the_plain_text_footer_says_the_same_sentences(self):
        """The text part is a real alternative, not an older version of one."""
        text = layout.render_text([], kicker="", unsub_url=self.UNSUB,
                                  manage_url=self.MANAGE)
        for sentence in layout.footer_sentences(True):
            flat = re.sub(r"\s+", " ", text)
            # A block that carries a link ends on a colon and the URL follows,
            # so the last sentence of one is compared without its full stop.
            self.assertTrue(flat.find(sentence) >= 0
                            or flat.find(sentence[:-1] + ":") >= 0,
                            f"the text footer never says: {sentence!r}")

    def test_a_missing_manage_url_drops_the_same_block_on_both_sides(self):
        """An older plugin build sends no manage URL. Neither side guesses."""
        html = layout._footer(self.UNSUB, "")
        for sentence in layout.footer_sentences(True):
            if sentence not in layout.footer_sentences(False):
                self.assertNotIn(sentence, _visible(html))
        blocks = _php_function(self.sub, "alt_digest_footer_blocks")
        self.assertIn("if ($manage_url)", blocks,
                      "the fallback would render a promise with nowhere to go")

    @unittest.skipUnless(_php(), "php is not installed. UNKNOWN, not a pass.")
    def test_the_two_renderings_read_identically_to_a_reader(self):
        """The end of the chain: both footers, rendered, word for word.

        The source-level mirror above cannot see a renderer that drops a
        sentence or links the wrong words. This runs the plugin's own renderer
        and compares what a person would read.
        """
        runner = (
            "<?php\n"
            "function esc_html($s){ return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }\n"
            "function esc_url($s){ return $s; }\n"
            "$src = file_get_contents($argv[1]);\n"
            "foreach (array('alt_digest_footer_blocks', 'alt_digest_footer_html') as $n) {\n"
            "  preg_match('/\\nfunction ' . $n . '\\s*\\(.*?\\n\\}/s', $src, $m);\n"
            "  eval($m[0]);\n"
            "}\n"
            "echo alt_digest_footer_html($argv[2], $argv[3]);\n")
        handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                             encoding="utf-8")
        try:
            handle.write(runner)
            handle.close()
            run = subprocess.run(
                [_php(), handle.name,
                 os.path.join(PLUGIN, "includes", "subscribe.php"),
                 self.UNSUB, self.MANAGE],
                capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(handle.name)
        self.assertEqual(run.returncode, 0, run.stderr[:800])

        relay = _visible(layout._footer(self.UNSUB, self.MANAGE))
        for sentence in layout.TRACKING_SENTENCES:
            relay = relay.replace(sentence, "")
        relay = re.sub(r"\s+", " ", relay).strip()
        self.assertEqual(_visible(run.stdout), relay)

        # And the link is on the same words, pointing at the same place.
        self.assertIn(f'<a href="{self.MANAGE}">re-enter your address on the '
                      f'signup form</a>', run.stdout)
        self.assertIn(f'<a href="{self.UNSUB}">Unsubscribe with one click</a>',
                      run.stdout)


class HouseStyle(unittest.TestCase):
    FILES = [
        os.path.join(RAILWAY, "digest_send.py"),
        os.path.join(RAILWAY, "digest_transport.py"),
        os.path.join(PLUGIN, "includes", "digest-api.php"),
        os.path.join(REPO, ".github", "workflows", "digest-send.yml"),
    ]

    def test_no_em_or_en_dashes(self):
        for path in self.FILES:
            body = open(path, encoding="utf-8").read()
            for ch in ("—", "–"):
                self.assertNotIn(ch, body, f"{os.path.basename(path)} carries a long dash")

    def test_the_workflow_installs_from_the_hash_pinned_lock(self):
        body = open(os.path.join(REPO, ".github", "workflows", "digest-send.yml"),
                    encoding="utf-8").read()
        self.assertIn("--require-hashes", body)
        self.assertIn("requirements-min.lock", body)

    def test_the_sender_needs_no_dependency_beyond_the_existing_lock(self):
        """Resend is plain HTTPS and SMTP is stdlib, so this feature adds no
        package to a runner that holds the site key."""
        for name in ("digest_send.py", "digest_transport.py"):
            body = open(os.path.join(RAILWAY, name), encoding="utf-8").read()
            self.assertNotIn("import requests", body)
            self.assertNotIn("import resend", body)
            self.assertNotIn("import boto3", body)


if __name__ == "__main__":
    unittest.main()


class TheLogSaysWhatActuallyWentOut(unittest.TestCase):
    """A log that cannot distinguish success from failure on the flag it is
    reporting is worse than no log.

    THE DEFECT. A test send with DIGEST_TEST_LISTS=talent printed "sections
    composed: articles, layoff, talent" and delivered talent alone. The filter
    worked; the log described COMPOSITION, which is upstream of the filter and
    identical either way. The only evidence available for that input reported
    the same string whether or not the input took effect, so it was read as
    proof the input was ignored and a bug was filed against working code.

    The run log is the whole verification surface for a workflow_dispatch, so
    it has to name what was INCLUDED.
    """

    def _lists_for(self, wanted):
        env = {"DIGEST_TEST_TO": "someone@example.com",
               "DIGEST_TEST_LISTS": wanted}
        return digest_send._test_lists(env, ["layoff", "talent", "articles"])

    def test_the_filter_keeps_only_what_was_named(self):
        self.assertEqual(self._lists_for("talent"), ["talent"])
        self.assertEqual(self._lists_for("talent, articles"),
                         ["talent", "articles"])

    def test_a_blank_input_means_everything(self):
        self.assertEqual(self._lists_for(""), ["layoff", "talent", "articles"])

    def test_the_site_order_is_kept_whatever_order_was_typed(self):
        """A test that reordered the sections would be showing a layout no
        subscriber receives."""
        self.assertEqual(self._lists_for("articles,layoff"),
                         ["layoff", "articles"])

    def test_the_message_carries_only_the_named_section(self):
        payload = {
            "from": "2026-08-10", "to": "2026-08-16", "freq": "weekly",
            "subject": "fallback", "send_id": 0,
            "sections": {
                "layoff": {"html": "<h2>AI Layoff Tracker</h2>",
                           "text": "AI Layoff Tracker\nx, August 10-16, 2026\n"},
                "talent": {"html": "<h2>Talent Intelligence Tracker</h2>",
                           "text": "Talent Intelligence Tracker\ny, August 10-16, 2026\n"},
            },
        }
        recipient = {"email": "someone@example.com",
                     "unsub_url": "https://asktherecruiter.com/blog/u/t/",
                     "lists": ["talent"]}
        message = digest_send.build_message(payload, recipient, "a@b.co", "a@b.co")
        self.assertIsNotNone(message)
        self.assertNotIn("AI Layoff Tracker", message.html)
        self.assertIn("Talent Intelligence Tracker", message.html)

    def test_the_log_line_names_what_is_included_and_not_only_what_composed(self):
        """The assertion that would have stopped the misread."""
        source = open(os.path.join(RAILWAY, "digest_send.py"),
                      encoding="utf-8").read()
        self.assertIn("sections included in what goes out", source,
                      "the run log reports composition only, so it reads the "
                      "same whether or not DIGEST_TEST_LISTS took effect")
        self.assertIn('for name in (r.get("lists") or [])', source,
                      "the included list must be read from the same field "
                      "build_message reads, or it can drift from the message")
