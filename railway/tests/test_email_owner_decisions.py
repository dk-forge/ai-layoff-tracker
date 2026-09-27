"""Owner decisions 2026-09-27 on the email audit, each held by behaviour.

TECHLOG 2026-09-27 "Email audit" listed four owner calls. The owner ruled all
four in, before launch:

1. A welcome email the moment a subscriber confirms: lists, frequency, next
   send day, manage link, List-Unsubscribe + One-Click. Exactly once per
   confirmation, and inside a daily share of Brevo's 300/day.
2. A per-follow "stop" link in "What you follow": signed for that subscriber
   and that follow, and a GET never mutates (link scanners).
3. The wp_mail fallback digest carries a plain-text part. The Brevo plugin
   replaces wp_mail wholesale, so it now goes to Brevo's API with htmlContent
   AND textContent.
4. A preferences page behind a signed token: less mail applies at once, more
   mail goes through the existing confirm-by-email flow.

Plus the audit's note that the weekly masthead said "week ending Friday":
the real window always ends on a Sunday, held below.

Driven through the REAL handlers by tests/fixtures/email_prefs_harness.php
(SQLite $wpdb, WordPress stubs). Synthetic addresses only.
"""
import datetime
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INC = ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "includes"
HARNESS = Path(__file__).resolve().parent / "fixtures" / "email_prefs_harness.php"
sys.path.insert(0, str(ROOT / "railway"))
import digest_layout  # noqa: E402
import digest_send  # noqa: E402

_RUN = {}


def run():
    if "out" not in _RUN:
        p = subprocess.run(
            ["php", str(HARNESS), str(INC / "subscribe.php"), str(INC / "digest-api.php"),
             str(INC / "follows.php"), str(INC / "subscriber-prefs.php")],
            capture_output=True, text=True, timeout=120)
        assert p.returncode == 0 and p.stdout.strip().startswith("{"), p.stderr + p.stdout[-3000:]
        _RUN["out"] = json.loads(p.stdout)
    return _RUN["out"]


def page(result):
    return result.get("die") or ""


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class WelcomeEmail(unittest.TestCase):
    def test_one_welcome_arrives_on_confirmation(self):
        o = run()
        self.assertEqual(o["mails_before_confirm"], 1)   # the confirmation only
        self.assertEqual(o["confirm1"], "confirmed")
        self.assertEqual(o["mails_after_confirm"], 2)

    def test_it_says_lists_frequency_next_send_and_manage_link(self):
        w = run()["welcome"]
        self.assertIn("AI Layoff Tracker digest, weekly", w["body"])
        self.assertIn("Occasional articles and product news", w["body"])
        self.assertRegex(w["body"], r"first edition is due Monday \d+ \w{3} \d{4}")
        self.assertIn(run()["welcome_prefs_url"], w["body"])
        self.assertIn("601 Van Ness Ave", w["body"])
        self.assertNotIn("<", w["body"])   # plain text

    def test_it_carries_one_click_unsubscribe_headers(self):
        heads = run()["welcome"]["headers"]
        self.assertTrue(any(h.startswith("List-Unsubscribe: <https://") for h in heads), heads)
        self.assertIn("List-Unsubscribe-Post: List-Unsubscribe=One-Click", heads)

    def test_a_reclick_does_not_resend(self):
        o = run()
        self.assertEqual(o["confirm_again"], "expired")
        self.assertEqual(o["mails_after_reclick"], 2)

    def test_the_confirm_claim_is_conditional_on_the_token(self):
        """Two racing clicks: only the request whose UPDATE still finds the
        token writes, and only it reaches the welcome."""
        src = (INC / "subscribe.php").read_text(encoding="utf-8")
        body = re.search(r"\nfunction alt_digest_confirm\(\).*?\n\}", src, re.S).group(0)
        self.assertIn("$claim['confirm_token'] = $row['confirm_token'];", body)
        self.assertIn("if (!$claimed) alt_digest_redirect('expired');", body)
        self.assertLess(body.index("$claimed ="), body.index("alt_digest_send_welcome("))

    def test_a_change_confirmation_is_not_welcomed_again(self):
        o = run()
        self.assertEqual(o["change_confirm"], "updated")
        self.assertEqual(o["mails_from_change_confirm"], 0)

    def test_the_brevo_budget_is_counted_and_respected(self):
        o = run()
        self.assertEqual(o["budget_after_one"]["welcome"], 1)
        self.assertEqual(o["capped_confirm"], "confirmed")
        self.assertEqual(o["capped_status"], "confirmed")
        self.assertEqual(o["capped_mails"], 1, "the cap was spent but a welcome went anyway")
        self.assertEqual(o["capped_budget"]["welcome_skipped"], 1)
        self.assertLess(o["capped_budget"]["welcome_cap"], 300)
        self.assertEqual(o["stats_welcome"]["welcome_skipped"], 1)

    def test_next_send_follows_the_relay_schedule(self):
        n = run()["next"]   # from Saturday 26 Sep 2026, 11:00 New York
        self.assertEqual(n["weekly"], "Monday 28 Sep 2026")
        self.assertEqual(n["daily"], "Sunday 27 Sep 2026")
        self.assertEqual(n["monthly"], "Thursday 1 Oct 2026")
        self.assertEqual(n["daily_before_slot"], "Monday 28 Sep 2026")


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class PreferencesPage(unittest.TestCase):
    def test_get_shows_an_accessible_form_and_writes_nothing(self):
        o = run()
        html = page(o["prefs_get"])
        self.assertTrue(o["prefs_get_row_unchanged"])
        self.assertIn('<form method="post"', html)
        self.assertIn("<legend>Lists</legend>", html)
        self.assertIn("<legend>How often</legend>", html)
        # Every control sits inside its label.
        self.assertEqual(html.count("<input type=\"checkbox\""), html.count("<label><input type=\"checkbox\""))
        self.assertIn(":focus-visible", html)
        self.assertIn('name="alt_list_layoff" value="1" checked', html)
        self.assertIn('name="alt_list_talent" value="1">', html)

    def test_a_get_carrying_form_fields_still_writes_nothing(self):
        self.assertTrue(run()["prefs_get_with_fields_unchanged"])

    def test_bad_and_foreign_tokens_are_dead_links(self):
        o = run()
        for k in ("prefs_bad_token", "prefs_foreign_id", "prefs_unsubscribed"):
            self.assertIn("This link no longer works", page(o[k]), k)
            self.assertNotIn("<form", page(o[k]), k)

    def test_less_mail_applies_at_once_without_email(self):
        o = run()
        a = o["after_reduce"]
        self.assertEqual((a["consent_layoff"], a["consent_articles"]), (1, 0))
        self.assertEqual(a["freq_layoff"], "monthly")
        self.assertEqual(o["reduce_mails"], 0)

    def test_more_mail_waits_for_the_confirmation_click(self):
        o = run()
        a = o["after_add"]
        self.assertEqual(a["consent_talent"], 0, "an added list applied without double opt-in")
        self.assertEqual(a["freq_layoff"], "monthly", "a faster cadence applied without double opt-in")
        self.assertTrue(a["pending_prefs"])
        self.assertEqual(len(o["add_mails"]), 1)
        self.assertIn("Starting:", o["add_mails"][0]["body"])
        self.assertNotIn("Stopping:", o["add_mails"][0]["body"])
        self.assertIn("Check your inbox", page(o["prefs_add"]))
        c = o["after_add_confirmed"]
        self.assertEqual((c["consent_talent"], c["freq_layoff"]), (1, "daily"))

    def test_no_list_ticked_is_refused(self):
        o = run()
        self.assertTrue(o["prefs_none_unchanged"])
        self.assertIn('role="alert"', page(o["prefs_none"]))

    def test_follows_are_listed_and_untick_stops_them(self):
        o = run()
        self.assertIn("Texas", page(o["prefs_get_follows"]))
        self.assertTrue(o["prefs_untick_follow_gone"])

    def test_every_digest_footer_links_the_readers_own_page(self):
        api = (INC / "digest-api.php").read_text(encoding="utf-8")
        self.assertIn("$recipient['manage_url'] = alt_prefs_url($row)", api)
        payload = {"freq": "weekly", "from": "2026-09-14", "to": "2026-09-20", "sections": {
            "layoff": {"html": "<h2>AI Layoff Tracker</h2><p>1.</p>", "text": "AI Layoff Tracker\n1.\n"}}}
        mine = "https://asktherecruiter.com/blog/ai-layoff-tracker/preferences/7-" + "d" * 64 + "/"
        rcp = {"id": 7, "email": "reader@example.com", "lists": ["layoff"], "manage_url": mine,
               "unsub_url": "https://asktherecruiter.com/blog/ai-layoff-tracker/unsubscribe/" + "a" * 64 + "/"}
        msg = digest_send.build_message(payload, rcp, "A <n@asktherecruiter.com>", "i@asktherecruiter.com")
        self.assertIn(mine, msg.html)
        self.assertIn(mine, msg.text)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class StopOneFollow(unittest.TestCase):
    def test_the_section_carries_a_stop_link_in_both_parts(self):
        o = run()
        self.assertIn(o["stop_url_a"], o["section"]["html"])
        self.assertIn("Stop following Acme Corp: " + o["stop_url_a"], o["section"]["text"])
        self.assertIn("Stop following Texas", o["section"]["text"])

    def test_get_asks_and_never_stops(self):
        o = run()
        self.assertTrue(o["stop_get_follow_kept"])
        self.assertIn('<form method="post"', page(o["stop_get"]))
        self.assertIn("Yes, stop following Acme Corp", page(o["stop_get"]))

    def test_post_stops_that_follow_only_and_is_idempotent(self):
        o = run()
        self.assertTrue(o["stop_post_follow_gone"])
        self.assertTrue(o["stop_post_other_kept"])
        self.assertIn("Already stopped", page(o["stop_post_again"]))

    def test_tokens_are_scoped_to_subscriber_and_follow(self):
        o = run()
        self.assertTrue(o["stop_forged_follow_kept"])
        self.assertIn("This link no longer works", page(o["stop_forged"]))
        self.assertIn("This link no longer works", page(o["stop_with_prefs_token"]))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class FallbackPlainText(unittest.TestCase):
    def test_the_outgoing_message_carries_both_parts(self):
        o = run()
        self.assertEqual(o["fallback_wp_mail"], 0)
        self.assertTrue(o["fallback_http"])
        mine = [c for c in o["fallback_http"] if c["body"]["to"][0]["email"] == "prefs@example.com"]
        self.assertEqual(len(mine), 1)
        call = mine[0]
        self.assertEqual(call["url"], "https://api.brevo.com/v3/smtp/email")
        body = call["body"]
        self.assertIn("<", body["htmlContent"])
        text = body["textContent"]
        self.assertTrue(text.strip())
        self.assertNotIn("<h2", text)
        self.assertIn(o["fallback_unsub"], text)
        self.assertIn(o["fallback_prefs_url"], text)
        self.assertIn(o["fallback_prefs_url"], body["htmlContent"])
        self.assertEqual(body["headers"]["List-Unsubscribe"], "<" + o["fallback_unsub"] + ">")
        self.assertEqual(body["headers"]["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_without_a_key_it_still_sends_through_wp_mail(self):
        o = run()
        self.assertEqual(o["nokey_send"][0], o["nokey_wp_mail"])
        self.assertGreater(o["nokey_wp_mail"], 0)


class WeeklyMastheadEndsOnSunday(unittest.TestCase):
    """The audit saw "week ending Friday" beside the ISO Monday-Sunday note.
    That came from a synthetic sample whose `to` was a Friday. The real
    window (alt_digest_weekly_window) always ends on the Sunday; this holds
    both halves so the two lines can never disagree in a real edition."""

    def test_the_plugin_window_is_monday_to_sunday(self):
        if not shutil.which("php"):
            self.skipTest("UNKNOWN, NOT RUN: php not installed")
        src = (INC / "subscribe.php").read_text(encoding="utf-8")
        fn = re.search(r"\nfunction alt_digest_weekly_window\(.*?\n\}", src, re.S).group(0)
        code = ("define('DAY_IN_SECONDS', 86400);" + fn +
                "$o=array(); for($d=0;$d<60;$d++){ $o[] = alt_digest_weekly_window("
                "strtotime('2026-09-01 12:00:00 UTC') + $d*86400); } echo json_encode($o);")
        p = subprocess.run(["php", "-r", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        for start, end in json.loads(p.stdout):
            s = datetime.date.fromisoformat(start)
            e = datetime.date.fromisoformat(end)
            self.assertEqual(s.isoweekday(), 1)
            self.assertEqual(e.isoweekday(), 7)
            line = digest_layout.body_dateline({"freq": "weekly", "from": start, "to": end})
            self.assertTrue(line.startswith("week ending Sunday"), line)


if __name__ == "__main__":
    unittest.main()
