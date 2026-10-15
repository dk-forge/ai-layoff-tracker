"""City follows ship switched off (owner ruling 2026-10-14, #478 roadmap).

The follow machinery (double opt-in, digest delivery, stop links) already
exists for companies and states. A city follow reuses all of it, and is OFF
until `alt_follow_city` / ALT_FOLLOW_CITY is set. While off: no form, the
submit handler refuses the kind, and stored city follows match nothing.
A city is matched only through alt_state_warn_city(), the same reader the state
pages use, never a bare substring of the excerpt.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "follows.php"
WARN = PLUGIN / "includes" / "state-warn.php"


def _fn(name, p=MOD):
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", p.read_text(encoding="utf-8"), re.S)
    assert m, f"{name} is missing"
    return m.group(0)


class SwitchedOff(unittest.TestCase):
    def test_default_is_off(self):
        body = _fn("alt_follow_city_enabled")
        self.assertIn("get_option('alt_follow_city', false)", body)

    def test_form_renders_nothing_when_off(self):
        self.assertIn("if ($kind === 'city' && !alt_follow_city_enabled()) return '';",
                      _fn("alt_follow_form_html"))

    def test_submit_refuses_city_when_off(self):
        body = _fn("alt_follow_submit")
        self.assertIn("$city_ok = ($kind === 'city' && alt_follow_city_enabled());", body)
        self.assertIn("in_array($kind, array('company', 'state'), true)", body)

    def test_resolve_and_match_are_gated(self):
        self.assertIn("alt_follow_city_enabled()", _fn("alt_follow_resolve"))
        self.assertIn("!alt_follow_city_enabled()", _fn("alt_follows_city_rows"))

    def test_city_match_goes_through_the_state_page_reader(self):
        body = _fn("alt_follows_city_rows")
        self.assertIn("alt_state_warn_city($r['excerpt'])", body)
        self.assertIn("superset_of = 0", body)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Behaviour(unittest.TestCase):
    def php(self, code, arg):
        p = subprocess.run(["php", "-r", code, "--", json.dumps(arg)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_parse(self):
        code = _fn("alt_follow_city_parse") + "\necho json_encode(array_map('alt_follow_city_parse', json_decode($argv[1], true)));"
        out = self.php(code, ["ca|San  Jose", "CA", "C|X", "TX|", "NY|" + "x" * 81])
        self.assertEqual(out, [["CA", "San Jose"], None, None, None, None])

    def test_option_off_and_on(self):
        for opt, want in ((False, False), (True, True)):
            code = ("function get_option($k, $d){ return json_decode($GLOBALS['argv'][1]); }\n"
                    + _fn("alt_follow_city_enabled")
                    + "\necho json_encode(alt_follow_city_enabled());")
            self.assertEqual(self.php(code, opt), want)

    def test_city_form_off_renders_nothing_on_lists_cities(self):
        stubs = ("function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
                 "function esc_attr($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
                 "function esc_url($s){ return (string)$s; }\n"
                 "function admin_url($s){ return '/wp-admin/' . $s; }\n"
                 "function get_option($k, $d){ return $GLOBALS['on']; }\n")
        body = _fn("alt_follow_city_enabled") + _fn("alt_follow_city_form_html")
        cities = [{"city": "San Jose"}, {"city": "A<b>"}]
        for on in (False, True):
            code = (stubs + "$GLOBALS['on'] = %s;\n" % ("true" if on else "false") + body
                    + "\necho json_encode(alt_follow_city_form_html('ca', json_decode($argv[1], true)));")
            html = self.php(code, cities)
            if not on:
                self.assertEqual(html, "")
            else:
                self.assertIn('value="CA|San Jose"', html)
                self.assertIn('name="alt_follow_kind" value="city"', html)
                self.assertNotIn("<b>", html)

    def test_reader_rejects_a_city_inside_a_company_name(self):
        code = _fn("alt_state_warn_city", WARN) + "\necho json_encode(array_map('alt_state_warn_city', json_decode($argv[1], true)));"
        out = self.php(code, ["Layoff at Acme in Springfield. 40 employees affected",
                              "Layoff at Acme (Store in Springfield) in Dayton. 40 employees affected"])
        self.assertEqual(out, ["Springfield", "Dayton"])


if __name__ == "__main__":
    unittest.main()
