"""/blog/llms.txt publishes the app's single llms.txt (owner 2026-11-02).

Runs the pure check under the php CLI and pins the wiring in the source.
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

MAIN = (Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker" / "ai-layoff-tracker.php").read_text()


def _fn(name):
    m = re.search(r"function " + re.escape(name) + r"\(.*?\n}\n", MAIN, re.S)
    assert m, name
    return m.group(0)


def _ok(code, body):
    php = _fn("alt_llms_remote_ok") + "echo json_encode(alt_llms_remote_ok(%d, %s));" % (code, json.dumps(body))
    p = subprocess.run(["php", "-r", php], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


GOOD = "# AskTheRecruiter\n\n> summary\n\n" + "x" * 300 + '\nAttribute to "the AI Layoff Tracker by AskTheRecruiter.com".\n'


class LlmsTxtProxy(unittest.TestCase):
    def test_accepts_the_app_file(self):
        self.assertTrue(_ok(200, GOOD))

    def test_rejects_redirects_errors_and_html(self):
        self.assertFalse(_ok(301, GOOD))
        self.assertFalse(_ok(502, GOOD))
        self.assertFalse(_ok(200, "<!doctype html>" + GOOD))
        self.assertFalse(_ok(200, GOOD.replace("AI Layoff Tracker by AskTheRecruiter.com", "x")))

    def test_source_is_the_unredirected_app_path_without_following_redirects(self):
        self.assertIn("define('ALT_LLMS_SOURCE_URL', 'https://asktherecruiter.com/.well-known/llms.txt');", MAIN)
        self.assertIn("'redirection' => 0", _fn("alt_llms_txt_published"))
        self.assertIn("return alt_llms_txt_content();", _fn("alt_llms_txt_published"))

    def test_disk_file_and_handler_publish_the_same_text(self):
        self.assertIn("'llms.txt'      => alt_llms_txt_published(),", _fn("alt_write_static_files"))
        self.assertIn("echo alt_llms_txt_published();", _fn("alt_serve_llms_txt"))
        self.assertIn("'hourly', 'alt_llms_sync_cron'", MAIN)

    def test_fallback_keeps_the_tracker_sections(self):
        body = _fn("alt_llms_txt_content")
        for line in ("## Key pages", "## Public API (same data, live)", "## Metric definitions", "## How to cite"):
            self.assertIn(line, body)


if __name__ == "__main__":
    unittest.main()
