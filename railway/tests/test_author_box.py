"""Named author / about box with Person schema, invisible until the owner fills it.

Owner scope 2026-09-24. The bio is the owner's words, not ours, so the one
constant ships EMPTY and marked TODO_OWNER_BIO. Empty means no box and no
Person node at all: a placeholder on a live page, or a Person with no name in
structured data, is worse than nothing.
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


def _render(profile):
    src = MOD.read_text(encoding="utf-8")
    m = re.search(r"\nfunction alt_author_box_html\s*\(.*?\n\}", src, re.S)
    assert m
    code = ("function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function esc_url($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function esc_attr($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function wp_json_encode($v, $f = 0){ return json_encode($v, $f); }\n"
            + m.group(0) + "\necho alt_author_box_html(json_decode($argv[1], true));")
    p = subprocess.run(["php", "-r", code, "--", json.dumps(profile)], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return p.stdout


class TheConstant(unittest.TestCase):
    def test_one_constant_marked_todo_and_empty(self):
        src = MOD.read_text(encoding="utf-8")
        self.assertEqual(src.count("define('ALT_AUTHOR_PROFILE'"), 1)
        self.assertIn("TODO_OWNER_BIO", src)
        block = src[src.index("define('ALT_AUTHOR_PROFILE'"):]
        block = block[:block.index(");")]
        self.assertIn("'bio'      => ''", block)
        self.assertIn("'name'     => ''", block)

    def test_on_every_surface_the_owner_named(self):
        for name in TEMPLATES:
            self.assertIn("alt_author_box(", (PLUGIN / "templates" / name).read_text(encoding="utf-8"), name)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Rendering(unittest.TestCase):
    def test_empty_renders_nothing(self):
        self.assertEqual(_render({"name": "", "bio": ""}).strip(), "")
        self.assertEqual(_render({"name": "Pat Example", "bio": ""}).strip(), "")

    def test_filled_renders_box_and_person(self):
        out = _render({"name": "Pat Example", "job_title": "Editor", "bio": "Writes <b>about</b> hiring.",
                       "url": "https://asktherecruiter.com/about/", "same_as": ["https://example.org/pat"]})
        self.assertIn('class="alt-author-box"', out)
        self.assertIn("Writes &lt;b&gt;about&lt;/b&gt; hiring.", out)
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', out, re.S)
        data = json.loads(ld.group(1))
        self.assertEqual(data["@type"], "Person")
        self.assertEqual(data["name"], "Pat Example")
        self.assertEqual(data["sameAs"], ["https://example.org/pat"])
        self.assertNotIn("</script><", ld.group(1))


if __name__ == "__main__":
    unittest.main()
