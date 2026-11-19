"""todo#1881 item 3: the ALT hub's first screen on a phone (review B7)."""
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
TPL = (PLUGIN / "templates" / "page-tracker.php").read_text()
CSS = (PLUGIN / "assets" / "layoffs.css").read_text()
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text()
COOKIE = PLUGIN / "includes" / "cookie-banner-compact.php"


class FirstScreen(unittest.TestCase):
    def test_phone_cta_sits_before_the_headline_figure_and_is_tracked(self):
        i = TPL.index('class="alt-hero-cta-m"')
        self.assertLess(i, TPL.index('<p class="alt-hero-figure">'))
        self.assertIn("alt_atr_cta_url('tracker_home_fold')", TPL[i - 200:i + 200])

    def test_phone_cta_is_phone_only_and_44px(self):
        self.assertIn(".alt-hero-cta-m { display: none; }", CSS)
        self.assertIn("min-height: 44px", CSS[CSS.index(".alt-hero-cta-m a {"):])

    def test_decorative_mascot_and_duplicate_lines_hidden_on_phones(self):
        block = CSS[CSS.index("/* MOBILE FIRST SCREEN (todo 1881"):]
        self.assertIn(".alt-header .alt-roo-wrap { display: none !important; }", block)
        self.assertIn("#alt-next-pull", block)

    def test_theme_switcher_moves_to_the_end_on_phones(self):
        self.assertIn("if (narrow) host.appendChild(group); else host.insertBefore(group, host.firstChild);", MAIN)


class CookieBanner(unittest.TestCase):
    def test_wired_guarded(self):
        self.assertIn("is_readable($alt_cookie_compact)", MAIN)

    @unittest.skipUnless(shutil.which("php"), "php CLI not installed: UNKNOWN, NOT RUN")
    def test_accept_and_deny_stay_equal_and_44px(self):
        php = ('define("ABSPATH",1); function add_action(){} function is_admin(){return false;}'
               'require "%s"; alt_cookie_banner_compact_css();' % COOKIE)
        css = subprocess.run(["php", "-r", php], capture_output=True, text=True, check=True).stdout
        self.assertIn("@media (max-width:600px)", css)
        # One rule sizes every banner button, so Accept and Deny cannot differ.
        self.assertIn(".cmplz-cookiebanner .cmplz-buttons .cmplz-btn{flex:1 1 40%!important", css)
        self.assertIn("min-height:44px!important", css)
        self.assertNotIn("cmplz-deny{", css)
        self.assertNotIn("cmplz-accept{", css)


if __name__ == "__main__":
    unittest.main()
