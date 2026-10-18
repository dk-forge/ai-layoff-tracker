"""Talent follows: a city or an employer on the sibling talent tracker.

Owner ruling 2026-10-18 (board item "City and company alerts"): this plugin's
subscriber list may hold talent follow preferences; weekly by default, daily
optional. It reuses the existing follow machinery (includes/follows.php)
exactly: the same table, the same double opt-in, the same stop links and the
same daily purge. What differs:

- kinds `talent_city` / `talent_company`, accepted only when the talent plugin
  answers `tit_follow_resolve()` in-process (both plugins share one install);
- following one opts the reader into the TALENT list (weekly unless they
  already chose a frequency), never the layoff list;
- the rows come from `tit_follow_rows()` and ride the TALENT section, as
  `talent_follow_section`, for talent-list readers only;
- at most ALT_FOLLOW_TALENT_MAX talent follows per subscriber.
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
PREFS = PLUGIN / "includes" / "subscriber-prefs.php"
sys.path.insert(0, str(ROOT / "railway"))
import digest_send  # noqa: E402


def _fn(name, p=MOD):
    src = p.read_text(encoding="utf-8")
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
    assert m, f"{name} is missing"
    return m.group(0)


class Source(unittest.TestCase):
    def test_talent_kinds_need_the_talent_plugin(self):
        resolve = _fn("alt_follow_resolve")
        self.assertIn("function_exists('tit_follow_resolve')", resolve)
        self.assertIn("alt_follow_is_talent(", _fn("alt_follow_submit"))

    def test_following_talent_opts_into_the_talent_list_not_layoff(self):
        body = _fn("alt_follow_submit")
        self.assertIn("$prefs['consent_talent'] = 1", body)
        self.assertRegex(body, r"if \(alt_follow_is_talent\(\$kind\)\)")

    def test_talent_follows_are_capped(self):
        self.assertIn("ALT_FOLLOW_TALENT_MAX", _fn("alt_follow_submit"))

    def test_matches_split_by_family(self):
        body = _fn("alt_follows_matches")
        self.assertIn("tit_follow_rows(", body)
        self.assertIn("$family", body)

    def test_senders_attach_talent_section_for_talent_readers(self):
        api = API.read_text(encoding="utf-8")
        self.assertIn("'talent_follow_section'", api)
        self.assertIn("alt_follows_section_for((int) $row['id'], $from_date, $to_date, 'talent')", api)
        self.assertIn("'talent')", _fn("alt_digest_send", SUB))

    def test_privacy_note_discloses_follows(self):
        self.assertIn("city or employer on the talent tracker", SUB.read_text(encoding="utf-8"))

    def test_stop_links_are_per_family(self):
        self.assertIn("$family", _fn("alt_follow_stop_links", PREFS))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Composer(unittest.TestCase):
    def run_php(self, rows, stops=()):
        code = ("function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
                "function esc_url($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
                + _fn("alt_follow_talent_section")
                + "\necho json_encode(alt_follow_talent_section(json_decode($argv[1], true), json_decode($argv[2], true)));")
        p = subprocess.run(["php", "-r", code, "--", json.dumps(rows), json.dumps(list(stops))],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    ROWS = [{"follow": "London", "follow_url": "https://example.com/city/london/", "company": "Acme <Ltd>",
             "headline": "Acme opens a London office", "source_url": "https://news.example.com/a",
             "date": "2026-10-12"}]

    def test_empty_is_nothing(self):
        self.assertIsNone(self.run_php([]))

    def test_rows_link_their_source_and_carry_no_figure_of_ours(self):
        out = self.run_php(self.ROWS, [["London", "https://example.com/stop/x/"]])
        self.assertIn("Hiring signals you follow", out["html"])
        self.assertIn('href="https://news.example.com/a"', out["html"])
        self.assertIn("Acme &lt;Ltd&gt;", out["html"])
        self.assertIn("12 Oct 2026", out["text"])
        self.assertIn("Stop following London", out["html"])
        self.assertNotIn("—", out["html"])


class Relay(unittest.TestCase):
    def payload(self):
        return {"freq": "weekly", "from": "2026-10-05", "to": "2026-10-11",
                "sections": {"talent": {"html": "<p>Talent</p>", "text": "Talent"},
                             "layoff": {"html": "<p>Layoffs</p>", "text": "Layoffs"}},
                "manage_url": "", "recipients": []}

    def recipient(self, lists):
        return {"email": "reader@example.com", "lists": lists,
                "unsub_url": "https://asktherecruiter.com/blog/ai-layoff-tracker/unsubscribe/x/",
                "talent_follow_section": {"html": "<h2>Hiring signals you follow</h2><p>TFROW</p>",
                                          "text": "Hiring signals you follow\nTFROW"}}

    def test_talent_readers_get_it_after_the_sections(self):
        msg = digest_send.build_message(self.payload(), self.recipient(["talent"]), "a@example.com", "b@example.com")
        self.assertIn("TFROW", msg.html)
        self.assertLess(msg.text.index("Talent"), msg.text.index("TFROW"))

    def test_layoff_only_readers_do_not(self):
        msg = digest_send.build_message(self.payload(), self.recipient(["layoff"]), "a@example.com", "b@example.com")
        self.assertNotIn("TFROW", msg.text)


if __name__ == "__main__":
    unittest.main()
