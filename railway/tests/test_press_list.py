"""The press list: admin-only journalist contacts, pitch sent ONLY on a click.

Owner addition 2026-09-24. What must hold, and why each would fail silently:

- ADMIN ONLY. The list holds personal contact data. Every screen and action
  checks manage_options and a nonce; the table is never exposed on the REST
  API or in an export.
- NO AUTOMATIC SEND. Nothing schedules the pitch. The only path to wp_mail is
  the admin-post handler behind the "Send" button, and a contact already
  pitched for the same period is skipped, so a double click is not two emails.
- OPT-OUT IS HONOURED. Every email carries an opt-out line with a per-contact
  token; opting out is recorded (status + timestamp) and an opted-out contact
  can never be selected or re-activated by a CSV re-import.
- CSV IMPORT VALIDATES. Bad addresses are rejected, not stored.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "press-list.php"

PURE = ("alt_press_parse_csv", "alt_press_email_body")


def _src():
    return MOD.read_text(encoding="utf-8")


def _fn(name):
    src = _src()
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
    assert m, f"{name} is missing"
    return m.group(0)


def _php(body, *args):
    stubs = (
        "function sanitize_text_field($s){ return trim(strip_tags((string)$s)); }\n"
        "function sanitize_email($s){ return trim((string)$s); }\n"
        "function is_email($s){ return (bool) filter_var($s, FILTER_VALIDATE_EMAIL); }\n"
        "function sanitize_textarea_field($s){ return trim((string)$s); }\n")
    code = stubs + "\n".join(_fn(n) for n in PURE) + "\n" + body
    p = subprocess.run(["php", "-r", code, "--", *args], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class CsvImport(unittest.TestCase):
    CSV = ("name,outlet,email,beat,consent_note\n"
           "Pat Reporter,Example Daily,pat@example.com,labor,met at conference\n"
           "Bad Row,Nowhere,not-an-email,tech,\n"
           "\"Lee, Jr.\",Example Wire,LEE@EXAMPLE.ORG,economy,public press address\n")

    def test_valid_rows_kept_invalid_rejected(self):
        out = json.loads(_php("echo json_encode(alt_press_parse_csv($argv[1]));", self.CSV))
        self.assertEqual([r["email"] for r in out["rows"]], ["pat@example.com", "lee@example.org"])
        self.assertEqual(out["rows"][1]["name"], "Lee, Jr.")
        self.assertEqual(len(out["rejected"]), 1)

    def test_header_is_required_so_columns_cannot_shift(self):
        out = json.loads(_php("echo json_encode(alt_press_parse_csv($argv[1]));",
                              "pat@example.com,Pat\n"))
        self.assertEqual(out["rows"], [])
        self.assertTrue(out["error"])


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class EmailBody(unittest.TestCase):
    def test_body_has_greeting_pitch_and_optout(self):
        body = _php("echo alt_press_email_body(array('name' => 'Pat Reporter'), 'PITCH TEXT', 'https://asktherecruiter.com/blog/?alt_press_optout=tok');")
        self.assertTrue(body.startswith("Hi Pat,"))
        self.assertIn("PITCH TEXT", body)
        self.assertIn("alt_press_optout=tok", body)
        self.assertIn("will not email you again", body)


class Safety(unittest.TestCase):
    def test_every_action_is_admin_and_nonce_gated(self):
        src = _src()
        for handler in ("alt_press_admin_import", "alt_press_admin_add", "alt_press_admin_send",
                        "alt_press_admin_import_signups"):
            body = _fn(handler)
            self.assertIn("current_user_can('manage_options')", body, handler)
            self.assertIn("check_admin_referer(", body, handler)
        self.assertIn("add_action('admin_post_alt_press_send'", src)
        self.assertNotIn("admin_post_nopriv_alt_press_send", src)
        self.assertNotIn("register_rest_route", src)

    def test_nothing_schedules_a_send(self):
        src = _src()
        self.assertNotIn("wp_schedule_event", src)
        self.assertNotIn("wp_schedule_single_event", src)
        # wp_mail is called from exactly one function, the click handler.
        self.assertEqual(src.count("wp_mail("), 1)
        self.assertIn("wp_mail(", _fn("alt_press_admin_send"))

    def test_send_skips_opted_out_and_already_pitched(self):
        body = _fn("alt_press_admin_send")
        self.assertIn("status = 'active'", body)
        self.assertIn("last_pitched_period <> %s", body)

    def test_optout_is_recorded_and_import_cannot_reactivate(self):
        src = _src()
        self.assertIn("'status' => 'opted_out'", src)
        self.assertIn("'opted_out_at'", src)
        self.assertIn("alt_press_upsert(", _fn("alt_press_admin_import"))
        up = _fn("alt_press_upsert")
        dup = up[up.index("ON DUPLICATE KEY UPDATE"):]
        dup = dup[:dup.index('",')]
        self.assertNotIn("status", dup)

    def test_optout_needs_a_post(self):
        body = _fn("alt_press_optout_route")
        self.assertIn("$_SERVER['REQUEST_METHOD']", body)
        self.assertIn("hash_equals(", body)


if __name__ == "__main__":
    unittest.main()
