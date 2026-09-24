"""Follow a company or a US state; matching new rows ride in the digest.

Owner scope 2026-09-24, item 5. The subscriber system is untouched in shape:
a follow is a row in its own table (wp_alt_follows) tied to a subscriber id,
and it reuses the EXISTING double opt-in and unsubscribe flows rather than
growing a second consent path:

- The follow form calls alt_digest_signup(), which sends the one confirmation
  email the digest already sends. A follow is stored `pending` and becomes
  `active` only on that confirmation (the `alt_digest_confirmed` action fired
  from alt_digest_confirm()). A stranger typing someone's address activates
  nothing.
- Only ACTIVE follows of CONFIRMED subscribers are read, so unsubscribing
  stops follow mail with everything else; orphaned follows are purged daily.
- Matching rows are composed by the SITE (figures never come from the relay)
  and handed per recipient as `follow_section`; both senders append it after
  the consented sections, only for readers on the layoff list.
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "follows.php"
SUB = PLUGIN / "includes" / "subscribe.php"
API = PLUGIN / "includes" / "digest-api.php"
MAIN = PLUGIN / "ai-layoff-tracker.php"
sys.path.insert(0, str(ROOT / "railway"))
import digest_send  # noqa: E402


def _src(p=MOD):
    return p.read_text(encoding="utf-8")


def _fn(name, p=MOD):
    src = _src(p)
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
    assert m, f"{name} is missing"
    return m.group(0)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class SectionComposer(unittest.TestCase):
    def run_php(self, rows):
        code = ("function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
                "function esc_url($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
                + _fn("alt_follow_section")
                + "\necho json_encode(alt_follow_section(json_decode($argv[1], true)));")
        p = subprocess.run(["php", "-r", code, "--", json.dumps(rows)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    ROWS = [{"follow": "Acme <Corp>", "company": "Acme <Corp>", "jobs": 120, "date": "2026-09-20",
             "place": "TX", "url": "https://asktherecruiter.com/blog/company-layoffs/acme/"},
            {"follow": "Texas", "company": "Globex", "jobs": 0, "date": "2026-09-19",
             "place": "TX", "url": "https://asktherecruiter.com/blog/state-layoffs/texas/"}]

    def test_empty_is_nothing(self):
        self.assertIsNone(self.run_php([]))

    def test_rows_are_listed_and_escaped(self):
        out = self.run_php(self.ROWS)
        self.assertIn("What you follow", out["text"])
        self.assertIn("Acme <Corp>", out["text"])
        self.assertIn("Acme &lt;Corp&gt;", out["html"])
        self.assertNotIn("<Corp>", out["html"])
        self.assertIn("120 jobs", out["text"])
        self.assertNotIn(", 0 jobs", out["text"])
        self.assertIn('href="https://asktherecruiter.com/blog/state-layoffs/texas/"', out["html"])


class Consent(unittest.TestCase):
    def test_follow_submit_goes_through_the_existing_double_opt_in(self):
        body = _fn("alt_follow_submit")
        self.assertIn("alt_digest_signup(", body)
        self.assertIn("INSERT IGNORE INTO", body)
        self.assertIn("'pending'", body)
        self.assertNotIn("'active'", body)

    def test_activation_only_on_confirmation(self):
        src = _src()
        self.assertIn("add_action('alt_digest_confirmed'", src)
        self.assertIn("do_action('alt_digest_confirmed', (int) $row['id'])", _fn("alt_digest_confirm", SUB))
        self.assertEqual(src.count("'status' => 'active'"), 1)
        self.assertIn("'status' => 'active'", _fn("alt_follows_activate"))

    def test_only_confirmed_subscribers_active_follows_are_read(self):
        body = _fn("alt_follows_matches")
        self.assertIn("f.status = 'active'", body)
        self.assertIn("s.status = 'confirmed'", body)

    def test_orphans_are_purged_daily(self):
        src = _src()
        self.assertIn("'alt_follows_cleanup'", src)
        self.assertIn("wp_schedule_event(", src)
        self.assertIn("s.status <> 'confirmed'", _fn("alt_follows_cleanup"))

    def test_validates_the_target(self):
        body = _fn("alt_follow_submit")
        self.assertIn("in_array($kind, array('company', 'state'), true)", body)


class Delivery(unittest.TestCase):
    def test_relay_payload_carries_it_for_layoff_readers(self):
        src = _src(API)
        self.assertIn("'follow_section'", src)
        self.assertIn("alt_follows_section_for(", src)

    def test_wp_mail_fallback_appends_it_too(self):
        body = _fn("alt_digest_send", SUB)
        self.assertIn("alt_follows_section_for(", body)

    def test_module_loaded_guarded(self):
        self.assertIn("'follows.php'", _src(MAIN))

    def payload(self):
        return {"freq": "weekly", "from": "2026-09-14", "to": "2026-09-20",
                "sections": {"layoff": {"html": "<p>Layoffs</p>", "text": "Layoffs"}},
                "manage_url": "", "recipients": []}

    def recipient(self, lists, follow=True):
        r = {"email": "reader@example.com", "lists": lists,
             "unsub_url": "https://asktherecruiter.com/blog/ai-layoff-tracker/unsubscribe/x/"}
        if follow:
            r["follow_section"] = {"html": "<h2>What you follow</h2><p>FOLLOWROW</p>",
                                   "text": "What you follow\nFOLLOWROW"}
        return r

    def test_relay_appends_the_follow_part(self):
        msg = digest_send.build_message(self.payload(), self.recipient(["layoff"]),
                                        "a@example.com", "b@example.com")
        self.assertIn("FOLLOWROW", msg.html)
        self.assertIn("FOLLOWROW", msg.text)
        self.assertLess(msg.text.index("Layoffs"), msg.text.index("FOLLOWROW"))

    def test_relay_ignores_it_for_non_layoff_readers(self):
        p = self.payload()
        p["sections"]["talent"] = {"html": "<p>Talent</p>", "text": "Talent"}
        msg = digest_send.build_message(p, self.recipient(["talent"]),
                                        "a@example.com", "b@example.com")
        self.assertNotIn("FOLLOWROW", msg.text)

    def test_follow_alone_is_not_a_reason_to_send(self):
        p = self.payload()
        p["sections"] = {}
        self.assertIsNone(digest_send.build_message(p, self.recipient(["layoff"]),
                                                    "a@example.com", "b@example.com"))


if __name__ == "__main__":
    unittest.main()
