"""The author box names the research team, never a person.

Owner ruling 2026-11-11: the tracker author box must read "Ask The Recruiter
research team", and no personal name appears anywhere on asktherecruiter.com,
trackers included. This supersedes the 2026-09-24 scope (a named Person box the
owner would fill). So: one fixed team profile, an Organization node in its
JSON-LD, and no Person node or personal-name field anywhere in the module.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "author-box.php"
TEMPLATES = ["page-report.php", "page-company-directory.php", "page-facet.php",
             "page-methodology.php", "page-press.php"]
TEAM = "Ask The Recruiter research team"


def _render():
    src = MOD.read_text(encoding="utf-8")
    m = re.search(r"\nfunction alt_author_box_html\s*\(.*?\n\}", src, re.S)
    assert m
    code = ("function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function esc_url($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function wp_json_encode($v, $f = 0){ return json_encode($v, $f); }\n"
            + m.group(0) + "\necho alt_author_box_html();")
    p = subprocess.run(["php", "-r", code], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return p.stdout


class TheModule(unittest.TestCase):
    def test_no_person_and_no_owner_name_slot(self):
        src = MOD.read_text(encoding="utf-8")
        self.assertNotIn("Person", src)
        self.assertNotIn("TODO_OWNER_BIO", src)
        self.assertNotIn("ALT_AUTHOR_PROFILE", src)
        self.assertIn(TEAM, src)

    def test_on_every_surface(self):
        for name in TEMPLATES:
            self.assertIn("alt_author_box(", (PLUGIN / "templates" / name).read_text(encoding="utf-8"), name)

    def test_no_em_dash_in_reader_text(self):
        self.assertNotIn("—", _box_strings(MOD.read_text(encoding="utf-8")))


def _box_strings(src):
    return "".join(re.findall(r"'([^']*)'", src[src.index("function alt_author_box_html"):]))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Rendering(unittest.TestCase):
    def test_box_reads_the_team(self):
        out = _render()
        self.assertIn('class="alt-author-box"', out)
        self.assertIn(f"<b>{TEAM}</b>", out)

    def test_schema_is_an_organization(self):
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', _render(), re.S)
        data = json.loads(ld.group(1))
        self.assertEqual(data["@type"], "Organization")
        self.assertEqual(data["name"], TEAM)
        self.assertEqual(data["parentOrganization"]["name"], "AskTheRecruiter.com")


if __name__ == "__main__":
    unittest.main()
