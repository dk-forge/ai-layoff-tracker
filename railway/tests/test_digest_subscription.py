"""Email digest subscriptions (includes/subscribe.php): the guards that make
storing a stranger's email address defensible.

This is the site's FIRST feature holding personal data, so the invariants are
consent invariants, and each one is exercised against the REAL PHP handlers
(via tests/fixtures/digest_harness.php: WordPress stubs + a SQLite wpdb),
not against a reimplementation:

  * DOUBLE OPT-IN: a pending address receives exactly one email ever (the
    confirmation); a digest run while pending sends nothing.
  * Zero boxes ticked is refused, and no row is stored.
  * Unsubscribe is one click, works twice (idempotent), and nothing sends
    afterwards.
  * Tokens are 64 hex chars of random_bytes output, unique per row, and not
    derivable from the address; the address never appears in a URL.
  * The purge cron hard-deletes exactly what the privacy note promises:
    unsubscribed + never-confirmed rows past the retention window, and never
    a confirmed subscriber.
  * The mailer stamps a source-health row on COMPLETION with counts only.
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
HARNESS = os.path.join(HERE, "fixtures", "digest_harness.php")


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    from shutil import which
    return which("php")


class StaticGuards(unittest.TestCase):
    """Facts that must be true of the source itself."""

    @classmethod
    def setUpClass(cls):
        cls.src = open(SUBSCRIBE, encoding="utf-8").read()

    def test_module_is_loaded_by_the_plugin(self):
        boot = open(os.path.join(PLUGIN, "ai-layoff-tracker.php"), encoding="utf-8").read()
        self.assertIn("require_once ALT_PLUGIN_DIR . 'includes/subscribe.php';", boot)

    def test_table_is_installed_with_the_layoffs_schema(self):
        db = open(os.path.join(PLUGIN, "includes", "db.php"), encoding="utf-8").read()
        self.assertIn("alt_subscribers", db)
        self.assertIn("UNIQUE KEY email (email)", db)
        for col in ("consent_layoff", "consent_talent", "consent_articles",
                    "freq_layoff", "freq_talent", "confirm_token", "unsub_token",
                    "unsubscribed_at"):
            self.assertIn(col, db, f"subscriber schema is missing {col}")

    def test_tokens_come_from_random_bytes_and_compare_constant_time(self):
        self.assertIn("hash_equals(", self.src)
        # The token factory is random_bytes and nothing else; in particular it
        # never sees the address, so a token cannot be derived from it.
        factory = self.src[self.src.index("function alt_digest_new_token"):]
        factory = factory[:factory.index("\n}")]
        self.assertIn("random_bytes(32)", factory)
        self.assertNotIn("email", factory)
        # And the token columns are only ever fed by that factory.
        for m in re.finditer(r"'(?:confirm_token|unsub_token)'\s*=>\s*([^,\n]+)", self.src):
            self.assertRegex(m.group(1).strip(), r"^(alt_digest_new_token\(\)|null|\$confirm)$",
                             f"token column fed by something other than the factory: {m.group(1)}")

    def test_form_starts_with_every_consent_box_unticked(self):
        boxes = re.findall(r'<input type="checkbox"[^>]*>', self.src)
        self.assertEqual(len(boxes), 3, "the form offers exactly three consent boxes")
        for box in boxes:
            self.assertNotIn("checked", box, f"pre-ticked consent is not consent: {box}")
        # The single frequency default is weekly.
        self.assertRegex(self.src, r'value="weekly" checked')

    def test_no_tracking_pixels_in_any_composed_email(self):
        self.assertNotIn("<img", self.src.lower())

    def test_list_unsubscribe_headers_are_attached(self):
        self.assertIn("List-Unsubscribe:", self.src)
        self.assertIn("List-Unsubscribe=One-Click", self.src)

    def test_no_em_or_en_dashes(self):
        for ch in ("—", "–"):
            self.assertNotIn(ch, self.src)

    def test_signup_is_rate_limited_per_ip(self):
        self.assertIn("alt_digest_rate_", self.src)
        self.assertIn("REMOTE_ADDR", self.src)

    def test_form_renders_on_the_tracker_page(self):
        tpl = open(os.path.join(PLUGIN, "templates", "page-tracker.php"), encoding="utf-8").read()
        self.assertIn("alt_digest_subscribe_form", tpl)

    def test_health_registry_knows_the_mailer(self):
        """A mailer that dies silently must go red: it needs a ceiling in BOTH
        staleness maps and a label on the public health page."""
        railway = os.path.abspath(os.path.join(HERE, ".."))
        ops = open(os.path.join(railway, "ops_status.py"), encoding="utf-8").read()
        dig = open(os.path.join(railway, "health_digest.py"), encoding="utf-8").read()
        js = open(os.path.join(PLUGIN, "assets", "health.js"), encoding="utf-8").read()
        self.assertRegex(ops, r'"digest_mailer":\s*3')
        self.assertRegex(dig, r'"digest_mailer":\s*3')
        self.assertIn("digest_mailer:", js)

    def test_health_is_stamped_on_completion_not_before(self):
        """checked_at must be written AFTER the sends and the purge, so a
        fatal mid-run leaves the row stale instead of freshly green."""
        cron = self.src[self.src.index("function alt_digest_cron_run"):]
        cron = cron[:cron.index("\n}")]
        send_pos = cron.index("alt_digest_send")
        purge_pos = cron.index("alt_digest_purge")
        stamp_pos = cron.index("alt_source_health_record")
        self.assertGreater(stamp_pos, send_pos)
        self.assertGreater(stamp_pos, purge_pos)

    def test_articles_consent_sends_nothing_and_says_so(self):
        """No article mechanism exists; the flag records consent only, and the
        code must say so where a future sender would be added."""
        self.assertIn("'articles' deliberately absent", self.src)
        sender = self.src[self.src.index("function alt_digest_send("):]
        sender = sender[:sender.index("\n}")]
        self.assertNotIn("consent_articles = 1", sender,
                         "nothing may send under the articles consent yet")


@unittest.skipUnless(_php(), "php not installed")
class BehaviouralGuards(unittest.TestCase):
    """Run the real handlers end to end through the harness."""

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cls.o = json.loads(proc.stdout)

    def test_zero_boxes_is_refused_and_stores_nothing(self):
        self.assertTrue(self.o["prefs_none_is_null"])
        self.assertEqual(self.o["submit_zero_boxes"], "lists")
        self.assertTrue(self.o["zero_row_absent"])
        self.assertEqual(self.o["zero_mails"], 0)

    def test_signup_stores_pending_and_sends_only_the_confirmation(self):
        self.assertEqual(self.o["submit_ok"], "check")
        self.assertEqual(self.o["status_after_signup"], "pending")
        self.assertEqual(self.o["consents"], [1, 0, 1])
        self.assertEqual(self.o["mails_after_signup"], 1)
        self.assertIn("Confirm", self.o["confirm_mail_subject"])
        self.assertTrue(self.o["confirm_mail_has_token"])

    def test_the_address_never_travels_in_a_url(self):
        self.assertFalse(self.o["confirm_mail_has_email_in_url"])

    def test_double_opt_in_nothing_sends_to_pending(self):
        sent, eligible, mails = self.o["send_while_pending"]
        self.assertEqual((sent, eligible), (0, 0))
        self.assertEqual(mails, 1, "the confirmation is the only mail a pending address gets")

    def test_confirm_flips_the_row_and_single_uses_the_token(self):
        self.assertEqual(self.o["confirm_redirect"], "confirmed")
        self.assertEqual(self.o["status_after_confirm"], "confirmed")
        self.assertTrue(self.o["confirm_token_cleared"])
        self.assertEqual(self.o["confirm_reuse"], "expired")

    def test_confirmed_subscriber_receives_the_digest_with_unsubscribe(self):
        self.assertEqual(self.o["send_after_confirm"], [1, 1])
        headers = " | ".join(self.o["digest_headers"])
        self.assertIn("List-Unsubscribe:", headers)
        self.assertIn("List-Unsubscribe=One-Click", headers)
        self.assertTrue(self.o["digest_has_unsub_link"])
        self.assertFalse(self.o["digest_has_img"], "no pixels, no images, deliberately")
        self.assertTrue(self.o["digest_mentions_layoff"])

    def test_frequency_is_honoured(self):
        self.assertEqual(self.o["digest_daily_none"][0], 0,
                         "a weekly subscriber gets no daily mail")

    def test_unsubscribe_is_one_click_and_idempotent(self):
        self.assertEqual(self.o["unsub1"], "unsubscribed")
        self.assertEqual(self.o["status_after_unsub"], "unsubscribed")
        self.assertEqual(self.o["unsub2"], "unsubscribed",
                         "a second click must land on the same calm page, not an error")
        self.assertTrue(self.o["unsub_idempotent_same_stamp"])
        self.assertEqual(self.o["send_after_unsub"], [0, 0],
                         "nothing may ever send after an unsubscribe")

    def test_tokens_are_unguessable(self):
        self.assertTrue(self.o["tokens_distinct"])
        self.assertEqual(self.o["tokens_hex64"], [True, True, True, True])
        self.assertTrue(self.o["token_not_derived_from_email"])

    def test_sixth_signup_from_one_ip_is_refused(self):
        self.assertEqual(self.o["rate_limit_codes"],
                         ["check", "check", "check", "check", "check", "rate"])

    def test_purge_deletes_exactly_what_the_privacy_note_promises(self):
        self.assertEqual(self.o["purged"], 2)
        left = [r["email"] for r in self.o["left_after_purge"]]
        self.assertEqual(left, ["confirmed-old@example.com",
                                "pending-fresh@example.com",
                                "unsub-fresh@example.com"])

    def test_health_stamp_holds_counts_never_an_address(self):
        row = self.o["health_row"]
        self.assertIsNotNone(row, "the cron must stamp a digest_mailer health row")
        self.assertEqual(row["status"], "ok")
        self.assertTrue(row.get("checked_at"))
        self.assertNotIn("@", row.get("detail", ""),
                         "health output carries counts only, never an address")

    def test_a_stranger_cannot_change_a_confirmed_subscribers_choices(self):
        self.assertEqual(self.o["prefs_unchanged_until_reconfirm"], [1, 0, "confirmed"])
        self.assertEqual(self.o["change_confirm_redirect"], "updated")
        self.assertEqual(self.o["prefs_after_reconfirm"], [0, 1, "daily", "confirmed"])


if __name__ == "__main__":
    unittest.main()
