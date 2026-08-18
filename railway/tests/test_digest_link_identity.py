"""The two links inside an email, and the name they arrive under.

The confirmation email IS the funnel. Nobody receives a digest until they click
one link in it, so the shape of that link and the identity it comes from are
not cosmetics: they are the only two things a first-contact message offers a
stranger to judge it by.

Until 2.20.77 both links pointed at
`/blog/wp-admin/admin-post.php?action=alt_digest_confirm&t=<64 hex>`. A person
reads `wp-admin` in a first-contact email as an administrative or phishing
link, and corporate mail filters rewrite or strip admin paths. So the links now
carry a public path on the site the reader just visited.

THE PART THAT MATTERS MORE THAN THE PRETTY PATH: the old URLs sit in real
inboxes, sent to real addresses, and one of them is in the `List-Unsubscribe`
header of every digest already delivered. Gmail and Yahoo POST to that header
without a human present. A confirmation link that 404s because we prettified
the route is strictly worse than an ugly one that works. So both shapes reach
the same handler, forever, and that is what most of this file asserts.

Everything here runs the REAL handlers through tests/fixtures/digest_harness.php.
"""
import json
import os
import re
import subprocess
import unittest

HERE = os.path.dirname(__file__)
PLUGIN = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))
SUBSCRIBE = os.path.join(PLUGIN, "includes", "subscribe.php")
DIGEST_API = os.path.join(PLUGIN, "includes", "digest-api.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_harness.php")


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    from shutil import which
    return which("php")


@unittest.skipUnless(_php(), "php not installed")
class _Harness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE, DIGEST_API],
                              capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cls.o = json.loads(proc.stdout)
        cls.routes = cls.o["routes"]


class TheEmailedLinkIsAPublicUrl(_Harness):

    def test_the_confirm_link_is_not_a_wp_admin_url(self):
        url = self.routes["confirm_url"]
        self.assertNotIn(
            "wp-admin", url,
            "the confirmation link is %r. That is the only link in the only "
            "email a pending address ever receives, and wp-admin in a "
            "first-contact message reads as phishing to a person and as a bad "
            "shape to a filter." % url)
        self.assertNotIn("admin-post.php", url)

    def test_the_unsubscribe_link_is_not_a_wp_admin_url(self):
        url = self.routes["unsub_url"]
        self.assertNotIn(
            "wp-admin", url,
            "the unsubscribe link is %r, and it rides in the List-Unsubscribe "
            "header of every digest" % url)

    def test_both_links_sit_under_the_page_the_reader_just_visited(self):
        for name in ("confirm_url", "unsub_url"):
            url = self.routes[name]
            self.assertTrue(
                url.startswith("https://example.test/blog/ai-layoff-tracker/"),
                "%s is %r, which is not a path on the tracker the reader just "
                "used. The point of moving off admin-post.php is that the URL "
                "looks like somewhere they have been." % (name, url))

    def test_the_link_still_carries_the_token_and_never_the_address(self):
        for name in ("confirm_url", "unsub_url"):
            url = self.routes[name]
            self.assertRegex(url, r"[a-f0-9]{64}",
                             "%s carries no token: %r" % (name, url))
            self.assertNotIn("@", url.split("://", 1)[1])


class TheLegacyUrlsKeepWorkingForever(_Harness):
    """Sent, delivered, and sitting in inboxes. They do not get to break."""

    def test_the_legacy_confirm_url_still_confirms(self):
        self.assertEqual(
            self.routes["legacy_confirm_result"], "confirmed",
            "a confirmation link of the pre-2.20.77 shape "
            "(%s) did not confirm. Those links were emailed to real addresses "
            "and a reader who clicks one tomorrow must land on the same "
            "handler." % self.routes["legacy_confirm_url"])
        self.assertEqual(self.routes["legacy_confirm_status"], "confirmed")

    def test_the_legacy_unsubscribe_url_still_reaches_the_handler(self):
        """A GET on the old URL asks, exactly as a GET on the new one does.

        It must NOT unsubscribe. That URL sits in the List-Unsubscribe header
        of every digest already delivered, where a provider POSTs to it, and
        the POST path is unchanged.
        """
        self.assertEqual(self.routes["legacy_unsub_get_code"], 200)
        self.assertEqual(self.routes["legacy_unsub_status"], "pending",
                         "the legacy GET wrote the row")
        self.assertIn("Yes, unsubscribe me", self.routes["legacy_unsub_get_body"])

    def test_the_legacy_handlers_are_still_registered_on_admin_post(self):
        """The route survives because the hook survives, not because a comment
        says so. Both the logged-out and logged-in actions, since a subscriber
        may happen to be logged in to the site."""
        src = open(SUBSCRIBE, encoding="utf-8").read()
        for action in ("alt_digest_confirm", "alt_digest_unsub"):
            for hook in ("admin_post_", "admin_post_nopriv_"):
                self.assertIn(
                    "add_action('%s%s'" % (hook, action), src,
                    "%s%s is gone, so every %s link already in an inbox 404s"
                    % (hook, action, action))

    def test_the_legacy_url_builders_are_still_readable_from_php(self):
        """Kept as named functions so a test can exercise the old shape rather
        than a copy of it that drifts."""
        self.assertIn("admin-post.php", self.routes["legacy_confirm_url"])
        self.assertIn("action=alt_digest_confirm",
                      self.routes["legacy_confirm_url"])
        self.assertIn("action=alt_digest_unsub", self.routes["legacy_unsub_url"])


class TheNewRouteReachesTheSameHandler(_Harness):

    def test_the_public_path_confirms(self):
        self.assertEqual(
            self.routes["public_confirm_result"], "confirmed",
            "GET %s did not confirm" % self.routes["confirm_url"])
        self.assertEqual(self.routes["public_confirm_status"], "confirmed")

    def test_a_get_asks_and_never_unsubscribes(self):
        """THE DEFECT, 2026-08-17. A GET wrote the row.

        The confirmation email carried this URL in its body, one line under
        the confirm URL, and Brevo rewrites every link at the relay. A
        corporate link scanner fetching the URLs in a delivered message
        therefore confirmed an address and then unsubscribed it, with nobody
        present. That reader never learns it happened and never complains.
        A GET must not mutate.
        """
        self.assertEqual(self.routes["public_unsub_get_status"], "pending",
                         "a GET unsubscribed somebody who pressed nothing")
        self.assertEqual(self.routes["public_unsub_get_code"], 200)

    def test_the_page_a_get_returns_is_one_button_and_no_javascript(self):
        body = self.routes["public_unsub_get_body"]
        self.assertIn("Yes, unsubscribe me", body)
        self.assertTrue(self.routes.get("public_unsub_form_is_post"),
                        "the button must POST")
        self.assertEqual(body.count("<form"), 1, "one form, one button")
        self.assertNotIn("<input type=\"text\"", body,
                         "nothing to fill in: no address, no login")
        for banned in ("<script", "javascript:", "onclick"):
            self.assertNotIn(banned, body.lower(),
                             "a reader may open this in a stripped down "
                             "client, so the only button must work without "
                             "any script")

    def test_pressing_that_button_unsubscribes(self):
        self.assertEqual(self.routes["public_unsub_button_status"], "unsubscribed",
                         "the confirmation page's own button did not work")
        self.assertEqual(self.routes["public_unsub_button_state"], "unsubscribed",
                         "a human who pressed the button must land on the "
                         "same panel every other terminal state uses")

    def test_a_query_string_cannot_forge_the_button(self):
        """The marker is read from $_POST alone, so no GET can dress up as a
        press of the button."""
        self.assertEqual(self.routes["forged_marker_get_status"], "pending")

    def test_a_second_get_says_it_is_already_done(self):
        self.assertEqual(self.routes["public_unsub_get_again_state"], "unsubscribed")

    def test_a_get_on_an_unknown_token_reads_as_it_always_has(self):
        self.assertEqual(self.routes["unknown_token_get_state"], "expired")

    def test_the_public_path_unsubscribes_by_post(self):
        """RFC 8058. A mailbox provider POSTs here with no human present."""
        self.assertEqual(self.routes["public_unsub_post_status"], "unsubscribed")

    def test_the_route_needs_no_rewrite_rule_and_no_flush(self):
        """FTP deploys bypass WordPress hooks, so a route that only exists once
        somebody remembered to flush the rewrite table is a route that 404s for
        an unknown window. This one reads REQUEST_URI directly."""
        src = open(SUBSCRIBE, encoding="utf-8").read()
        self.assertNotIn(
            "add_rewrite_rule", src,
            "subscribe.php registers a rewrite rule. The confirmation link is "
            "the whole funnel and it must not depend on a flushed rewrite "
            "table, because an FTP deploy runs no activation hook.")
        self.assertIn("REQUEST_URI", src)


class TheConfirmationEmailCarriesNoStopLink(_Harness):
    """Removed 2026-08-17, to make the scanner sequence impossible.

    The body used to carry the unsubscribe URL one line under the confirm
    URL. Brevo rewrites every link at the relay, so a scanner fetching the
    URLs in that one message confirmed an address and then unsubscribed it.
    A GET can no longer write the row, which makes that harmless. Cutting the
    link means the sequence cannot be attempted.
    """

    def test_the_body_carries_no_unsubscribe_url(self):
        body = self.routes["confirm_mail_body"]
        token = self.routes["confirm_mail_unsub_token"]
        self.assertNotIn(token, body,
                         "the confirmation email still carries the "
                         "unsubscribe token in its body")
        self.assertNotIn("unsubscribe", body.lower())

    def test_the_confirm_link_is_still_there(self):
        self.assertIn("/confirm/", self.routes["confirm_mail_body"],
                      "cutting the stop link must not cut the funnel")

    def test_the_list_unsubscribe_header_is_untouched(self):
        headers = " ".join(self.routes["confirm_mail_headers"])
        self.assertIn("List-Unsubscribe:", headers)
        self.assertIn("List-Unsubscribe-Post: List-Unsubscribe=One-Click", headers)
        self.assertIn(self.routes["confirm_mail_unsub_token"], headers,
                      "any client offering a stop button must still have one")


class OneClickUnsubscribeAnswersAMachine(_Harness):
    """List-Unsubscribe-Post means no browser, no session, no redirect."""

    def test_a_post_gets_a_2xx_and_not_a_redirect(self):
        self.assertEqual(
            self.routes["public_unsub_post_code"], 200,
            "the one-click POST answered %r. Gmail and Yahoo want a 2xx; a 302 "
            "to a page is a redirect a bot is not obliged to follow."
            % (self.routes["public_unsub_post_code"],))
        self.assertFalse(
            self.routes["public_unsub_post_redirected"],
            "the one-click POST issued a redirect")

    def test_an_unknown_token_posted_still_gets_a_2xx(self):
        """A provider POSTing a token we purged must not be told the request
        failed. It cannot act on the answer, and a 4xx there is recorded
        against the sending domain."""
        self.assertEqual(self.routes["post_unknown_token_code"], 200)
        self.assertFalse(self.routes["post_unknown_token_redirected"])

    def test_the_legacy_url_answers_a_post_the_same_way(self):
        self.assertEqual(self.routes["legacy_unsub_post_code"], 200)
        self.assertEqual(self.routes["legacy_unsub_post_status"], "unsubscribed")


class AStaleLinkSaysSoPlainly(_Harness):

    def test_a_used_confirm_token_is_not_reported_as_a_failure(self):
        self.assertEqual(
            self.routes["public_confirm_reuse_result"], "expired",
            "clicking a spent confirmation link must land on the 'expired' "
            "state, which reads as 'you are already confirmed'")

    def test_the_expired_copy_reads_as_success_not_error(self):
        src = open(SUBSCRIBE, encoding="utf-8").read()
        m = re.search(r"'expired'\s*=>\s*array\('(\w+)',\s*'([^']*)'", src)
        self.assertTrue(m, "the 'expired' message is no longer a single literal")
        kind, words = m.group(1), m.group(2)
        self.assertEqual(
            kind, "ok",
            "the stale-link message is styled as an error (%r). A confirm "
            "token is cleared the moment it is spent, so the overwhelming "
            "case for landing here is a link clicked twice." % kind)
        self.assertIn("already been used", words)

    def test_a_token_free_route_does_not_404(self):
        """A mail client that truncates the URL must reach the plain message,
        not a 404 page that tells the reader nothing."""
        self.assertEqual(self.routes["confirm_without_token_result"], "expired")


class TheFromLineNamesTheSender(_Harness):
    """WHAT WE HAND TO wp_mail, NOT WHAT THE READER SEES.

    Measured 2026-08-17 on 2.20.77: Brevo replaces the whole From line at the
    relay, so the received message carries a bare address whatever this
    function returns. These assertions are still worth holding, because the
    value becomes live the day the relay changes and because an unaligned
    address or an emoji would be wrong in either world. None of them may be
    rewritten to claim a reader sees this. See alt_digest_from_header()'s
    docblock and RUNBOOK "the confirmation email's From line".
    """


    def test_the_confirmation_carries_a_from_header(self):
        headers = self.routes["confirm_mail_headers"]
        froms = [h for h in headers if h.lower().startswith("from:")]
        self.assertEqual(
            len(froms), 1,
            "the confirmation email went out with %d From: headers: %r. "
            "wp_mail's default is 'WordPress <wordpress@...>', which beside a "
            "brand-led subject is a mixed signal in the one message that has "
            "to be trusted." % (len(froms), headers))

    def test_the_from_address_is_the_one_the_digest_already_sends_as(self):
        """DKIM and SPF alignment are the reason this is not a free-text field.
        The digest sends as newsletter@asktherecruiter.com through the mail
        provider; a confirmation from any other mailbox is a second identity to
        authenticate and a second thing for a reader to recognise."""
        line = self.routes["confirm_from_line"]
        self.assertIn("<newsletter@asktherecruiter.com>", line,
                      "the From line is %r" % line)

    def test_the_display_name_carries_no_emoji_or_graphics(self):
        """Gmail treats a graphical character in the display name as UI
        spoofing. It is the one placement with a documented hard block."""
        line = self.routes["confirm_from_line"]
        name = line.split(":", 1)[1].split("<")[0].strip()
        self.assertTrue(name, "the From line has no display name: %r" % line)
        for ch in name:
            self.assertLess(
                ord(ch), 0x2000,
                "the From display name %r carries the non-ASCII character %r"
                % (name, ch))

    def test_the_digest_send_uses_the_same_identity(self):
        """One sender for both messages, or the confirmation teaches a reader
        to recognise a name the digest does not use."""
        self.assertEqual(self.routes["confirm_from_line"],
                         self.routes["digest_from_line"])
