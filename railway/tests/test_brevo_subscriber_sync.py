"""The Brevo contact mirror of digest subscribers (owner decision 2026-09-24).

wp_alt_subscribers is the source of truth; Brevo is a copy. These tests RUN
the real subscribe / confirm / unsubscribe handlers plus includes/brevo-sync.php
through tests/fixtures/brevo_sync_harness.php, with the Brevo API replaced by a
recording fake, and assert on the calls that would have left the site.

Held here: a pending (double opt-in not yet clicked) row never reaches Brevo;
a confirmed row lands on exactly the lists it took (monthly -> the weekly list,
by owner decision); unsubscribe unlinks everything and never creates a
contact; the separate partner-offers consent is unticked by default, linked
only when ticked AND confirmed, unlinked when unticked; an API failure of any
kind leaves the flow untouched; a Brevo marketing-campaign unsubscribe unlinks
the lists but does NOT stop digests.
"""
import json
import os
import subprocess
import unittest
from shutil import which

HERE = os.path.dirname(__file__)
INC = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker", "includes"))
HARNESS = os.path.join(HERE, "fixtures", "brevo_sync_harness.php")
PHP = which("php")

LAYOFF_DAILY, LAYOFF_WEEKLY, TALENT_DAILY, TALENT_WEEKLY, PARTNERS = 15, 16, 17, 18, 20
ALL = {LAYOFF_DAILY, LAYOFF_WEEKLY, TALENT_DAILY, TALENT_WEEKLY, PARTNERS}


def _posted_lists(calls):
    posts = [c for c in calls if c["method"] == "POST"]
    return set(posts[0]["body"].get("listIds", [])) if posts else None


def _unlinked(calls):
    puts = [c for c in calls if c["method"] == "PUT"]
    return set(puts[-1]["body"]["unlinkListIds"]) if puts else set()


def _run_harness():
    proc = subprocess.run(
        [PHP, HARNESS, os.path.join(INC, "subscribe.php"),
         os.path.join(INC, "digest-api.php"), os.path.join(INC, "brevo-sync.php")],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


@unittest.skipUnless(PHP, "php not installed")
class BrevoMirror(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.o = _run_harness()

    def test_pending_is_never_sent_to_brevo(self):
        self.assertEqual(self.o["pending_signup"], "check")
        self.assertEqual(self.o["pending_calls"], [])

    def test_confirmed_is_added_with_the_right_lists(self):
        calls = self.o["confirm_calls"]
        self.assertEqual(self.o["confirm_a"], "confirmed")
        self.assertEqual(calls[0]["url"], "https://api.brevo.com/v3/contacts")
        self.assertTrue(calls[0]["body"]["updateEnabled"])
        self.assertEqual(_posted_lists(calls), {LAYOFF_DAILY})
        self.assertEqual(_unlinked(calls), ALL - {LAYOFF_DAILY})
        self.assertTrue(all(c["timeout"] <= 5 for c in calls))

    def test_monthly_maps_to_the_weekly_list(self):
        self.assertEqual(_posted_lists(self.o["b_confirm_calls"]), {TALENT_WEEKLY, PARTNERS})

    def test_unsubscribe_unlinks_everything_and_creates_nothing(self):
        calls = self.o["unsub_calls"]
        self.assertEqual(self.o["unsub_a"], "unsubscribed")
        self.assertFalse([c for c in calls if c["method"] == "POST"])
        self.assertEqual(_unlinked(calls), ALL)

    def test_api_failure_never_breaks_the_flow(self):
        for name in ("http", "transport", "throw"):
            self.assertEqual(self.o["fail_" + name], ["confirmed", "confirmed"], name)
        self.assertEqual(self.o["status_option"]["last_result"], "failed")
        self.assertFalse(self.o["logs_have_address"],
                         "the mirror status must hold counts, never an address")

    def test_no_key_is_a_silent_noop_with_a_marker(self):
        self.assertEqual(self.o["nokey_confirm"], "confirmed")
        self.assertEqual(self.o["nokey_calls"], [])
        self.assertEqual(self.o["nokey_status"], "unconfigured")

    def test_backfill_is_confirmed_only_and_batched(self):
        b1, b2 = self.o["backfill"]
        self.assertEqual(b1["processed"], 2)
        self.assertIsNotNone(b1["next_after_id"])
        self.assertGreater(b2["next_after_id"] or 10**9, b1["next_after_id"])
        self.assertEqual(self.o["backfill_posts"], b1["synced"] + b2["synced"])

    def test_campaign_unsubscribe_unlinks_but_keeps_digests(self):
        self.assertEqual(self.o["camp_unsub_status"], "confirmed",
                         "a Brevo marketing unsubscribe must not stop digests")
        self.assertEqual(self.o["camp_unsub_resp"]["stopped"], 0)
        self.assertEqual(_unlinked(self.o["camp_unsub_calls"]), ALL)
        self.assertEqual(_posted_lists(self.o["after_optout_calls"]), set(),
                         "a later preference change must not relink an opted-out contact")


@unittest.skipUnless(PHP, "php not installed")
class PartnerConsent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.o = _run_harness()

    def test_partner_box_exists_and_is_unticked_by_default(self):
        self.assertTrue(self.o["form_has_partner_box"])
        self.assertFalse(self.o["form_partner_box_checked"])
        self.assertTrue(self.o["form_mentions_partners_in_privacy"])

    def test_not_ticked_means_not_on_the_partner_list(self):
        self.assertEqual(self.o["pending_partner_col"], 0)
        self.assertNotIn(PARTNERS, _posted_lists(self.o["confirm_calls"]))
        self.assertIn(PARTNERS, _unlinked(self.o["confirm_calls"]))

    def test_ticked_and_confirmed_is_linked_with_a_consent_stamp(self):
        self.assertEqual(self.o["b_pending_partner_col"], 1)
        self.assertIn(PARTNERS, _posted_lists(self.o["b_confirm_calls"]))
        self.assertTrue(self.o["b_partner_stamp"])

    def test_untick_unlinks_and_clears_the_stamp(self):
        self.assertNotIn(PARTNERS, _posted_lists(self.o["b_untick_calls"]))
        self.assertIn(PARTNERS, _unlinked(self.o["b_untick_calls"]))
        self.assertEqual(self.o["b_after_untick"], [0, None])


if __name__ == "__main__":
    unittest.main()
