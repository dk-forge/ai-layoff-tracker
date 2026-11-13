"""Open roles now in the talent digest (owner ruling 2026-11-13, "yes, employer links").

The section is composed by the TALENT plugin (tit_open_roles_email_section in
talent-intelligence-tracker includes/open_roles.php). This plugin asks for it
per recipient, in their country and topic, and both senders append it for
talent-list readers only, daily and weekly only. Role links go straight to the
employer and are never click-tracked; only the CV button is.
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
MOD = PLUGIN / "includes" / "digest-open-roles.php"
SUB = PLUGIN / "includes" / "subscribe.php"
API = PLUGIN / "includes" / "digest-api.php"
PREFS = PLUGIN / "includes" / "subscriber-prefs.php"
DB = PLUGIN / "includes" / "db.php"
BACKUP = PLUGIN / "includes" / "subscriber-backup.php"
MAIN = PLUGIN / "ai-layoff-tracker.php"
sys.path.insert(0, str(ROOT / "railway"))
import digest_send  # noqa: E402


def _fn(name, p):
    src = p.read_text(encoding="utf-8")
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
    assert m, f"{name} is missing"
    return m.group(0)


class Source(unittest.TestCase):
    def test_file_is_loaded_guarded(self):
        self.assertIn("'digest-open-roles.php'", MAIN.read_text(encoding="utf-8"))

    def test_both_senders_attach_it_for_talent_readers(self):
        api = API.read_text(encoding="utf-8")
        self.assertIn("$recipient['open_roles_section']", api)
        self.assertRegex(api, r"in_array\('talent', \$lists, true\) && function_exists\('alt_open_roles_section_for'\)")
        sender = _fn("alt_digest_send", SUB)
        self.assertIn("alt_open_roles_section_for($row, $freq, $send_id)", sender)
        self.assertIn("(int) $row['consent_talent'] === 1", sender)

    def test_preferences_are_columns_and_are_backed_up(self):
        db = DB.read_text(encoding="utf-8")
        self.assertIn("talent_country CHAR(2) NULL", db)
        self.assertIn("talent_family VARCHAR(40) NULL", db)
        cols = _fn("alt_sbk_columns", BACKUP)
        self.assertIn("'talent_country'", cols)
        self.assertIn("'talent_family'", cols)

    def test_settings_form_and_save(self):
        self.assertIn("alt_open_roles_prefs_fieldset($row)", _fn("alt_prefs_form", PREFS))
        self.assertIn("alt_open_roles_prefs_from_post($_POST)", _fn("alt_prefs_handle", PREFS))

    def test_privacy_note_discloses_the_choice(self):
        self.assertIn("If you pick a country or topic", SUB.read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Composer(unittest.TestCase):
    STUBS = r"""
define('ABSPATH', '/');
function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function esc_attr($s){ return esc_html($s); }
$GLOBALS['calls'] = array();
function alt_digest_track_link($id, $u){ return 'https://asktherecruiter.com/blog/ai-layoff-tracker/c/' . $id . '?u=' . urlencode($u); }
function tit_open_roles_choices(){ return array('countries' => array('GB' => 'United Kingdom', 'US' => 'United States'),
                                                'families' => array('engineering' => 'Engineering')); }
function tit_open_roles_email_section($freq, $args){
    $GLOBALS['calls'][] = array($freq, $args['country'], $args['family']);
    $role = 'https://job-boards.greenhouse.io/acme/jobs/1';
    return array('html' => '<h2>Open roles now</h2><a href="' . $role . '">Engineer</a><a href="'
                 . call_user_func($args['link'], 'https://asktherecruiter.com/?utm_source=talent-tracker') . '">CV</a>',
                 'text' => "Open roles now\nEngineer " . $role, 'count' => 1);
}
"""

    def php(self, expr):
        src = MOD.read_text(encoding="utf-8").replace("<?php", "", 1)
        p = subprocess.run(["php", "-r", self.STUBS + src + "\n" + expr], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        return p.stdout

    def test_reader_choices_reach_the_composer(self):
        out = json.loads(self.php(
            "$s = alt_open_roles_section_for(array('talent_country' => 'gb', 'talent_family' => 'engineering'), 'daily', 7);"
            "echo json_encode(array($s, $GLOBALS['calls']));"))
        self.assertEqual(out[1], [["daily", "GB", "engineering"]])
        self.assertIn("Open roles now", out[0]["html"])

    def test_role_link_untracked_cv_button_tracked(self):
        html = json.loads(self.php("echo json_encode(alt_open_roles_section_for(array(), 'weekly', 7));"))["html"]
        self.assertIn('href="https://job-boards.greenhouse.io/acme/jobs/1"', html)
        self.assertEqual(html.count("/c/7?u="), 1)

    def test_monthly_and_bad_values_get_nothing_or_all(self):
        self.assertEqual(self.php("var_export(alt_open_roles_section_for(array(), 'monthly', 1));"), "NULL")
        out = json.loads(self.php(
            "alt_open_roles_section_for(array('talent_country' => 'USA', 'talent_family' => 'DROP TABLE'), 'daily', 1);"
            "echo json_encode($GLOBALS['calls']);"))
        self.assertEqual(out, [["daily", "", ""]])

    def test_settings_fieldset_and_post(self):
        html = self.php("echo alt_open_roles_prefs_fieldset(array('talent_country' => 'US'));")
        self.assertIn('<option value="US" selected>United States</option>', html)
        self.assertIn('<label for="alt_talent_country">Country</label>', html)
        saved = json.loads(self.php(
            "echo json_encode(alt_open_roles_prefs_from_post(array('alt_talent_country' => 'FR', 'alt_talent_family' => 'engineering')));"))
        self.assertEqual(saved, {"talent_country": None, "talent_family": "engineering"})   # FR is not a current choice
        self.assertEqual(self.php("var_export(alt_open_roles_prefs_from_post(array()));"), "NULL")


class Relay(unittest.TestCase):
    def payload(self):
        return {"freq": "daily", "from": "2026-11-12", "to": "2026-11-13",
                "sections": {"talent": {"html": "<p>Talent</p>", "text": "Talent"},
                             "layoff": {"html": "<p>Layoffs</p>", "text": "Layoffs"}},
                "manage_url": "", "recipients": []}

    def recipient(self, lists):
        return {"email": "reader@example.com", "lists": lists,
                "unsub_url": "https://asktherecruiter.com/blog/ai-layoff-tracker/unsubscribe/x/",
                "open_roles_section": {"html": "<h2>Open roles now</h2><p>ORROW</p>",
                                       "text": "Open roles now\nORROW"}}

    def test_talent_readers_get_it_after_the_talent_section(self):
        msg = digest_send.build_message(self.payload(), self.recipient(["talent"]), "a@example.com", "b@example.com")
        self.assertIn("ORROW", msg.html)
        self.assertLess(msg.text.index("Talent"), msg.text.index("ORROW"))

    def test_layoff_only_readers_do_not(self):
        msg = digest_send.build_message(self.payload(), self.recipient(["layoff"]), "a@example.com", "b@example.com")
        self.assertNotIn("ORROW", msg.text)


if __name__ == "__main__":
    unittest.main()
