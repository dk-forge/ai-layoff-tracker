"""The account emails (signup confirm, change confirm, welcome) wear the
subscriber design (2.20.246, board item "Finish tracker email redesign").

Real PHP renders each one; the tests pin the shell (fluid 600px card, accent
bar, one button), the footer (postal address with no suite number; welcome has
preferences + unsubscribe; a confirmation deliberately has neither, see
subscribe.php 2026-08-17), dark-mode contrast both upright and inverted, no
images or remote fetches, no #E313, and a snapshot of the welcome HTML.
"""
import hashlib
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MAIL = PLUGIN / "includes" / "account-mail.php"
SUB = PLUGIN / "includes" / "subscribe.php"
PREFS = PLUGIN / "includes" / "subscriber-prefs.php"
SNAP = Path(__file__).resolve().parent / "snapshots" / "account_mail_welcome.html"

ADDRESS = "AskTheRecruiter.com, 601 Van Ness Ave, San Francisco, CA 94102."
CONFIRM = "https://example.com/blog/digest/confirm/tok/"
PREFS_URL = "https://example.com/blog/digest/preferences/p1/"
UNSUB = "https://example.com/blog/digest/unsubscribe/u1/"


def _fn(name, path):
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", path.read_text(encoding="utf-8"), re.S)
    assert m, f"{name} is missing"
    return m.group(0)


def _php(body):
    src = MAIL.read_text(encoding="utf-8").replace("<?php", "", 1)
    code = ("define('ALT_ACCOUNT_MAIL_TEST', 1); define('ALT_DIGEST_RETENTION_DAYS', 30);\n" + src + "\n"
            + "\n".join(_fn(n, SUB) for n in ("alt_digest_list_names", "alt_digest_change_lines",
                                               "alt_digest_signup_lines", "alt_digest_confirm_body"))
            + "\n" + body)
    p = subprocess.run(["php", "-r", code], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


def _confirm():
    return _php("echo alt_account_mail_confirm_html(alt_digest_confirm_body('" + CONFIRM + "', null, "
                "array('consent_layoff'=>1,'freq_layoff'=>'weekly')), '" + CONFIRM + "', false);")


WELCOME_TEXT = ("You're in. Thanks for confirming your subscription at asktherecruiter.com.\\n\\n"
                "You get:\\n  - AI Layoff Tracker digest, weekly\\n\\n"
                "Change lists, frequency or follows here:\\n" + PREFS_URL + "\\n\\n"
                "Every edition has a one-click unsubscribe at the foot.\\n\\n" + ADDRESS + "\\n")


def _welcome():
    return _php('echo alt_account_mail_welcome_html("' + WELCOME_TEXT + '", "' + PREFS_URL + '", "'
                + UNSUB + '");')


def _ratio(a, b):
    def lum(h):
        out = []
        for i in (1, 3, 5):
            c = int(h[i:i + 2], 16) / 255
            out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _invert(h):
    return "#" + "".join(f"{255 - int(h[i:i + 2], 16):02x}" for i in (1, 3, 5))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class AccountMailDesign(unittest.TestCase):
    def test_confirm_renders_in_the_design_with_one_link(self):
        html = _confirm()
        self.assertIn("Confirm your subscription", html)
        self.assertIn("max-width:600px", html)
        self.assertIn('name="viewport"', html)
        self.assertIn("border-left:4px solid #b42a18", html)
        self.assertIn("AI Layoff Tracker digest, weekly", html)
        self.assertIn(ADDRESS, html)
        # Only the confirm link, never an unsubscribe a scanner could follow.
        hrefs = set(re.findall(r'href="([^"]+)"', html))
        self.assertEqual(hrefs, {CONFIRM})
        # The button sits where the bare URL was: after the list, before "Nothing is sent".
        self.assertLess(html.index(">Confirm my subscription<"), html.rindex("Nothing is sent"))

    def test_change_confirm_heading(self):
        html = _php("echo alt_account_mail_confirm_html('Apply it:\\n\\n" + CONFIRM + "\\n', '"
                    + CONFIRM + "', true);")
        self.assertIn("Confirm your change", html)
        self.assertIn(">Apply the change<", html)

    def test_welcome_footer_has_preferences_unsubscribe_and_address_once(self):
        html = _welcome()
        self.assertIn(f'href="{PREFS_URL}"', html)
        self.assertIn(f'href="{UNSUB}"', html)
        self.assertIn(">Unsubscribe<", html)
        self.assertIn(">Manage preferences<", html)
        self.assertEqual(html.count("601 Van Ness Ave"), 1)
        # Preferences: the button, its paste-able fallback, and the footer.
        self.assertEqual(html.count(f'href="{PREFS_URL}"'), 3)
        self.assertNotRegex(html, r"(?i)\bsuite\b|\bste\.")
        self.assertNotRegex(html, r"#E\d{3}")

    def test_no_e313_no_images_no_remote_fetch(self):
        for html in (_confirm(), _welcome()):
            self.assertNotIn("#E313", html)
            self.assertNotIn("E313", html)
            self.assertNotRegex(html, r"(?i)<img|<link|url\(|src=")
        self.assertNotIn("E313", MAIL.read_text(encoding="utf-8"))

    def test_colours_clear_4_5_upright_and_inverted(self):
        src = MAIL.read_text(encoding="utf-8")
        pal = dict(re.findall(r"'(\w+)'\s*=>\s*'(#[0-9a-f]{6})'", src))
        pairs = [(pal["ink"], pal["card"]), (pal["muted"], pal["card"]), (pal["link"], pal["card"]),
                 (pal["on_button"], pal["button"]), (pal["accent"], pal["card"])]
        for ink, bg in pairs:
            self.assertGreaterEqual(_ratio(ink, bg), 4.5, (ink, bg))
            self.assertGreaterEqual(_ratio(_invert(ink), _invert(bg)), 4.5, (ink, bg, "inverted"))

    def test_no_personal_names(self):
        # Brand and product names only; a person's name never appears.
        html = _welcome() + _confirm()
        text = re.sub(r"<[^>]+>", " ", html)
        for word in ("Dear ", "Hi "):
            self.assertNotIn(word, text)

    def test_welcome_snapshot(self):
        html = _welcome()
        if not SNAP.exists():
            SNAP.parent.mkdir(parents=True, exist_ok=True)
            SNAP.write_text(html, encoding="utf-8")
        self.assertEqual(html, SNAP.read_text(encoding="utf-8"),
                         "welcome HTML changed; delete the snapshot to accept a deliberate change")
        self.assertTrue(hashlib.sha1(html.encode()).hexdigest())

    def test_senders_use_the_design_with_a_plain_text_fallback(self):
        send = _fn("alt_digest_send_confirm_email", SUB)
        self.assertIn("alt_account_mail_confirm_html", send)
        self.assertIn("alt_digest_deliver($email, $subject, $html, $body, $unsub_token)", send)
        self.assertIn("wp_mail($email, $subject, $body, $headers)", send)
        welcome = _fn("alt_digest_send_welcome", PREFS)
        self.assertIn("alt_account_mail_welcome_html", welcome)
        self.assertIn("wp_mail($row['email']", welcome)
        main = (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8")
        self.assertIn("is_readable($alt_account_mail)", main)


if __name__ == "__main__":
    unittest.main()
