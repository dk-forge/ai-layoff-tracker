"""The first-signup confirmation says what the click will start.

Email audit 2026-09-27: the signup body said only "the email digest", so a
reader who ticked two lists could not tell from the email what confirming
would begin. The change email already itemises; this pins the signup body to
the same standard, and pins that a caller passing no prefs still gets the old
body (an older caller must not break), and that the press pitch carries the
postal address the digest footer does.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
SUB = PLUGIN / "includes" / "subscribe.php"
PRESS = PLUGIN / "includes" / "press-list.php"


def _fn(name, path=SUB):
    src = path.read_text(encoding="utf-8")
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
    assert m, f"{name} is missing"
    return m.group(0)


def _php(body):
    code = ("define('ALT_DIGEST_RETENTION_DAYS', 30);\n"
            + "\n".join(_fn(n) for n in ("alt_digest_list_names", "alt_digest_change_lines",
                                         "alt_digest_signup_lines", "alt_digest_confirm_body"))
            + "\n" + body)
    p = subprocess.run(["php", "-r", code], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class SignupConfirmation(unittest.TestCase):
    def test_lists_and_cadence_are_restated(self):
        out = _php("echo alt_digest_confirm_body('https://example.com/c', null, array("
                   "'consent_layoff'=>1,'freq_layoff'=>'weekly','consent_talent'=>1,"
                   "'freq_talent'=>'daily','consent_articles'=>0,'freq_articles'=>'weekly'));")
        self.assertIn("You asked for:", out)
        self.assertIn("AI Layoff Tracker digest, weekly", out)
        self.assertIn("Talent Intelligence Tracker digest, daily", out)
        self.assertNotIn("Occasional articles", out)
        # Restated BEFORE the link, so it is read before the click.
        self.assertLess(out.index("You asked for:"), out.index("https://example.com/c"))

    def test_no_prefs_keeps_the_old_body(self):
        out = _php("echo alt_digest_confirm_body('https://example.com/c');")
        self.assertNotIn("You asked for:", out)
        self.assertIn("Nothing is sent until you confirm.", out)

    def test_signup_passes_its_prefs_through(self):
        self.assertIn("$delta, $prefs);", _fn("alt_digest_signup"))
        self.assertIn("alt_digest_confirm_body($confirm_url, $delta, $prefs)",
                      _fn("alt_digest_send_confirm_email"))


class PressPitchFooter(unittest.TestCase):
    def test_pitch_carries_the_postal_address(self):
        body = _fn("alt_press_email_body", PRESS)
        self.assertIn("601 Van Ness Ave, San Francisco, CA 94102", body)
        digest = SUB.read_text(encoding="utf-8")
        self.assertIn("AskTheRecruiter.com, 601 Van Ness Ave, San Francisco, CA 94102.", digest)
        # Owner 2026-09-29: the suite number is left out of every email.
        self.assertNotIn("#E313", body)
        self.assertNotIn("#E313", digest)


if __name__ == "__main__":
    unittest.main()
