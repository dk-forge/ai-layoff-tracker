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
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
PLUGIN = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

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
        self.assertIn("tracking must be OFF", notice)

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
        self.assertIn("no tracking pixels", message.text)

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
        names = [n for n, _, _ in digest_send.usable_sections(payload, ["talent"])]
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
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call", side_effect=OSError("504")):
            code = digest_send.main()
        self.assertEqual(code, 0)


class RunWiring(unittest.TestCase):
    def test_a_dry_run_never_claims_a_send(self):
        """A dry run that recorded a delivery would make the next real run skip
        every person it merely printed."""
        env = {"WP_SITE_URL": "https://x.test/blog", "WP_API_KEY": "k",
               "DIGEST_DRY_RUN": "1"}
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(digest_send, "_call") as call, \
                mock.patch.object(digest_send, "_record_health"), \
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

    def test_auto_frequency_mirrors_the_sites_own_cron(self):
        import datetime
        monday = datetime.date(2026, 8, 10)
        self.assertEqual(digest_send.resolve_freq({}, monday), "weekly")
        self.assertEqual(digest_send.resolve_freq({}, monday + datetime.timedelta(days=1)),
                         "daily")
        self.assertEqual(digest_send.resolve_freq({"DIGEST_FREQ": "daily"}, monday), "daily")

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
        self.assertIn("last_sent_at IS NULL OR last_sent_at < %s", due)

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
