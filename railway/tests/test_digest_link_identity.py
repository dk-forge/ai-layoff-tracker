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

    def test_the_legacy_unsubscribe_url_still_unsubscribes(self):
        self.assertEqual(self.routes["legacy_unsub_result"], "unsubscribed")
        self.assertEqual(self.routes["legacy_unsub_status"], "unsubscribed")

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

    def test_the_public_path_unsubscribes_by_get(self):
        self.assertEqual(self.routes["public_unsub_get_result"], "unsubscribed")
        self.assertEqual(self.routes["public_unsub_get_status"], "unsubscribed")

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
