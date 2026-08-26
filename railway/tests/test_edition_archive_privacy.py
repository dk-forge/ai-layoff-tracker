"""An archived edition is PUBLIC. A mailed message is PER RECIPIENT.

THE FAILURE THIS EXISTS TO PREVENT. The digest archive publishes what the
composers produced for a window. The message a subscriber receives is that
content plus a footer built for them alone: their unsubscribe token, their
manage link, their address, the "you get this because you subscribed" line and
the tracking disclosure. Archiving a rendered message rather than the composed
content would publish a live one-click unsubscribe link, belonging to one named
person, on a page indexed by search engines. There is no recovering from that,
so it is held by an assertion rather than by care.

HOW THE GATE IS SHAPED, AND WHY IT IS AN ALLOWLIST. The same reason
assert_nameless in railway/tracker_diff.py is one: a denylist protects against
the leaks somebody thought of. alt_edition_public_safe() admits a URL only when
its path matches a frozen list of shapes and every one of its query keys is on
a frozen list of keys, so `t`, `s` and `l` are refused by being absent rather
than by being named. Two shapes that can appear outside a URL are refused
anywhere in the document: an address, and a run of 32+ hex characters (the
click hash is 32, an unsubscribe token is 64).

THE THIRD RULE IS ABOUT CORRECTNESS RATHER THAN PRIVACY, and it is here because
the archive is where a link outlives the reader's memory of the email. The
tracker page defaults to the FILING basis; every digest figure is counted on
the EFFECTIVE basis. A link that does not name `date_basis` lands on a page
showing a different number under the same label. tests/test_digest_link_basis.py
holds that on the email path; this holds it on the published one.

Every poisoned case below is built from the REAL composed section, so a passing
run proves the gate rejects the poison rather than that it rejects everything.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PLUGIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker")
SUBSCRIBE = os.path.join(PLUGIN, "includes", "subscribe.php")
ARCHIVE = os.path.join(PLUGIN, "includes", "digest-archive.php")
HARNESS = os.path.join(HERE, "fixtures", "edition_archive_harness.php")
PHP = shutil.which("php")

SITE = "https://asktherecruiter.com/blog"


def gate(docs, slugs=()):
    """Run the real gate over each document. Returns {name: {ok, rule}}."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    try:
        json.dump({"docs": docs, "slugs": list(slugs)}, handle)
        handle.close()
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, ARCHIVE, handle.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"harness failed: {run.stderr[:1500]}")
    return json.loads(run.stdout)


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def composed_section():
    """The REAL layoff section, from the composer, at send_id 0."""
    import test_digest_link_basis as basis
    return basis.compose(basis.fixture())


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheArchiveGate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        section = composed_section()
        cls.clean = section["html"] + "\n" + section["text"]

    def poison(self, extra):
        """The real section with one forbidden thing added to it."""
        return self.clean + extra

    # -- the baseline, so nothing below passes vacuously -------------------

    def test_a_real_composed_section_is_publishable(self):
        """If this fails, every rejection below proves nothing."""
        out = gate({"clean": self.clean})["docs"]["clean"]
        self.assertTrue(out["ok"], f"the real section was refused: {out['rule']}")

    def test_the_composer_at_send_id_zero_emits_no_click_url(self):
        """The property the whole design rests on, asserted rather than assumed.

        alt_digest_track_link() returns the plain destination when the send id
        is zero, so a section composed for the archive cannot carry a counter
        URL. If that ever stops being true the gate would still refuse it, but
        the archive would silently go empty instead, which is a worse failure
        to debug.
        """
        self.assertNotIn("/wp-json/layoffs/v1/click", self.clean)
        self.assertNotIn("?s=", self.clean)

    # -- recipient-scoped values -------------------------------------------

    def test_a_public_unsubscribe_url_is_refused(self):
        token = "a" * 64
        doc = self.poison(f'<p><a href="{SITE}/ai-layoff-tracker/unsubscribe/{token}/">'
                          f'Unsubscribe with one click</a></p>')
        self.assertFalse(gate({"d": doc})["docs"]["d"]["ok"])

    def test_an_admin_post_unsubscribe_url_is_refused(self):
        token = "b" * 64
        doc = self.poison(f'<p><a href="{SITE}/wp-admin/admin-post.php'
                          f'?action=alt_digest_unsub&amp;t={token}">Unsubscribe</a></p>')
        self.assertFalse(gate({"d": doc})["docs"]["d"]["ok"])

    def test_a_confirmation_url_is_refused(self):
        token = "c" * 64
        doc = self.poison(f'<p><a href="{SITE}/ai-layoff-tracker/confirm/{token}/">Confirm</a></p>')
        self.assertFalse(gate({"d": doc})["docs"]["d"]["ok"])

    def test_a_bare_token_with_no_url_around_it_is_refused(self):
        """The token does not need to be in a link to be a leak."""
        doc = self.poison("<p>Your reference: " + "d" * 64 + "</p>")
        out = gate({"d": doc})["docs"]["d"]
        self.assertFalse(out["ok"])
        self.assertIn("token", out["rule"])

    def test_a_recipient_address_is_refused(self):
        doc = self.poison("<p>Sent to reader@example.com because you subscribed.</p>")
        out = gate({"d": doc})["docs"]["d"]
        self.assertFalse(out["ok"])
        self.assertIn("address", out["rule"])

    def test_a_mailto_link_is_refused(self):
        doc = self.poison('<p><a href="mailto:reader@example.com">reader</a></p>')
        self.assertFalse(gate({"d": doc})["docs"]["d"]["ok"])

    # -- send-scoped values -------------------------------------------------

    def test_a_click_counter_url_is_refused(self):
        doc = self.poison(f'<p><a href="{SITE}/wp-json/layoffs/v1/click?s=7&amp;l='
                          f'{"e" * 32}">Open the tracker</a></p>')
        self.assertFalse(gate({"d": doc})["docs"]["d"]["ok"])

    def test_an_unknown_query_key_is_refused(self):
        """The allowlist's whole job: a key nobody thought about does not pass."""
        doc = self.poison(f'<p><a href="{SITE}/ai-layoff-tracker/?date_basis=effective'
                          f'&amp;subscriber_id=41">Tracker</a></p>')
        out = gate({"d": doc})["docs"]["d"]
        self.assertFalse(out["ok"])
        self.assertIn("query key", out["rule"])

    # -- destinations -------------------------------------------------------

    def test_an_off_site_link_is_refused(self):
        doc = self.poison('<p><a href="https://evil.example/x">elsewhere</a></p>')
        out = gate({"d": doc})["docs"]["d"]
        self.assertFalse(out["ok"])
        self.assertIn("host", out["rule"])

    def test_a_credentialled_host_is_refused(self):
        doc = self.poison('<p><a href="https://asktherecruiter.com@evil.example/x">x</a></p>')
        self.assertFalse(gate({"d": doc})["docs"]["d"]["ok"])

    # -- the basis rule -----------------------------------------------------

    def test_a_filtered_tracker_link_without_a_basis_is_refused(self):
        doc = self.poison(f'<p><a href="{SITE}/ai-layoff-tracker/?from=2026-08-10'
                          f'&amp;to=2026-08-16">5,000</a></p>')
        out = gate({"d": doc})["docs"]["d"]
        self.assertFalse(out["ok"])
        self.assertIn("date_basis", out["rule"])

    def test_an_entry_permalink_needs_no_basis(self):
        """One row's own page is not a filtered view, and must not be refused."""
        doc = self.poison(f'<p><a href="{SITE}/layoff/has-a-page/">Has A Page</a></p>')
        self.assertTrue(gate({"d": doc})["docs"]["d"]["ok"])

    # -- identity -----------------------------------------------------------

    def test_the_slug_is_the_iso_week_not_the_calendar_year(self):
        """The week of 28 December 2026 is 2026-W53, and its calendar year is
        wrong for two of its days. Reading the calendar year beside an ISO week
        ships silently and is found the following January."""
        out = gate({}, slugs=[
            ["weekly", "2026-08-10", "2026-08-16"],
            ["weekly", "2029-12-31", "2030-01-06"],
            ["daily", "2026-08-17", "2026-08-18"],
        ])["slugs"]
        self.assertEqual(out, ["2026-W33", "2030-W01", "2026-08-18"])


class TheArchiveIsWiredAndImmutable(unittest.TestCase):
    """Source-level rules that no fixture can exercise, held anyway.

    Both senders have to capture, both have to publish, and NOTHING may rewrite
    a stored section. The last one is the product promise: an edition states
    what was published at that moment, and a figure that is later revised gets
    a dated correction note beside the original rather than a quiet edit.
    """

    @classmethod
    def setUpClass(cls):
        cls.archive = _read(ARCHIVE)
        cls.subscribe = _read(SUBSCRIBE)
        cls.api = _read(os.path.join(PLUGIN, "includes", "digest-api.php"))

    def test_both_senders_capture_the_edition(self):
        """The relay path and the in-WordPress fallback both compose. An
        archive wired to only one of them would silently miss every edition
        sent by the other, and which one sends depends on the relay lease."""
        for name, src in (("subscribe.php", self.subscribe),
                          ("digest-api.php", self.api)):
            self.assertIn("alt_edition_capture(", src,
                          f"{name} composes a digest and does not archive it")

    def test_both_senders_publish_only_after_a_send(self):
        for name, src in (("subscribe.php", self.subscribe),
                          ("digest-api.php", self.api)):
            self.assertIn("alt_edition_publish(", src,
                          f"{name} records a send and never publishes the edition")

    def test_capture_composes_at_send_id_zero(self):
        """The one line the privacy design rests on.

        The THIRD argument - the send_id - must be 0, so a captured section can
        carry no click-counter URL and never sees a recipient. A FOURTH argument
        (the tier) was added 2026-08-25 for the monthly edition and is composed
        content, not recipient context, so it does not touch this invariant: the
        assertion pins the send_id at 0 while allowing the freq to ride after
        it."""
        body = self.archive[self.archive.index("function alt_edition_capture("):]
        body = body[:body.index("\nfunction ")]
        self.assertRegex(body, r"\$fn\(\$from, \$to, 0(?:, \$freq)?\)",
                         "the archive must re-compose at send_id 0, never reuse a "
                         "section composed for a send")

    def test_nothing_rewrites_a_stored_section(self):
        """Immutability, by shape. `sections` is written by capture and by
        nothing else; publishing writes a timestamp and a correction appends to
        its own column."""
        for line in self.archive.splitlines():
            stripped = line.strip()
            if stripped.startswith("*") or stripped.startswith("//"):
                continue
            if "SET" in stripped and "sections" in stripped:
                self.fail(f"a statement updates the stored sections: {stripped}")

    def test_the_indexing_split_is_one_setting(self):
        """Not something typed in three places. The robots filters, the
        canonical and the sitemap all read alt_edition_indexable()."""
        self.assertIn("function alt_edition_tier_indexable()", self.archive)
        self.assertGreaterEqual(self.archive.count("alt_edition_indexable("), 3)
        # The daily tier is out of the index on purpose: ~365 near-identical
        # pages a year is the profile Search Console is already declining to
        # crawl on this site.
        self.assertIn("'weekly' => true", self.archive)
        self.assertIn("'daily' => false", self.archive)


if __name__ == "__main__":
    unittest.main()
