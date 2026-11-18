"""todo#1853 AI search: /blog/ai-layoff-tracker/llms.txt carries quotable
figures with an "as of" date and a source page, taken from the press page's
own cached bundle, never computed a third way."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "ai-layoff-tracker.php"
STUBS = (
    "function home_url($p = '') { return 'https://example.org/blog' . $p; }\n"
    "function alt_atr_cta_url($c) { return 'https://asktherecruiter.com/resume-score?utm_source=ai-layoff-tracker&utm_campaign=' . $c; }\n"
    "function rest_url($p = '') { return 'https://example.org/blog/wp-json/' . $p; }\n"
)
PS = {"split": {"year": 2026, "as_of": "Nov 18, 2026", "to_date": 77526, "calendar": 90000, "later": 12474},
      "tiers": {"t1": 1000, "t2": 2345, "t3": 50, "box": 4000, "year": 2026}}


def _fn(name):
    src = MAIN.read_text()
    m = re.search(r"\nfunction %s\(.*?\n}\n" % name, src, re.S)
    assert m, name
    return m.group(0)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class TrackerLlms(unittest.TestCase):
    def _php(self, expr):
        src = STUBS + "".join(_fn(n) for n in ("alt_llms_txt_content", "alt_llms_is_tracker_request",
                                                "alt_tracker_llms_txt_content"))
        p = subprocess.run(["php", "-r", src + expr], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        return p.stdout

    def _txt(self, ps):
        return self._php("echo alt_tracker_llms_txt_content(json_decode(%s, true));" % json.dumps(json.dumps(ps)))

    def test_quotable_figures_have_date_number_and_source(self):
        out = self._txt(PS)
        self.assertIn("## Quotable figures (as of Nov 18, 2026)", out)
        self.assertIn("documents 77,526 verified job cuts that took effect in 2026 so far, "
                      "counted by the date each cut takes effect", out)
        self.assertIn("Source: https://example.org/blog/ai-layoff-tracker/press/\n", out)
        # no anchor that the press page only renders sometimes
        self.assertNotIn("#alt-press-period", out)
        # the AI tiers are a calendar-year count on another definition: linked, not restated
        self.assertNotIn("attributed to AI", out)
        self.assertIn("resume-score?utm_source=ai-layoff-tracker&utm_campaign=llms_txt", out)
        for line in out.splitlines():
            if line.startswith("- As of"):
                self.assertIn("Source: https://", line)

    def test_cold_cache_prints_no_figures(self):
        for ps in (False, {}, {"split": {"as_of": "", "to_date": 5}},
                   {"split": {"as_of": "Nov 18, 2026", "to_date": 5}}):  # no year: never "in 0"
            out = self._txt(ps)
            self.assertNotIn("Quotable figures", out)
            self.assertIn("# AI Layoff Tracker", out)

    def test_cold_cache_falls_back_to_the_last_good_dated_split(self):
        body = _fn("alt_serve_llms_txt")
        self.assertIn("get_option('alt_llms_press_figures')", body)
        press = (ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "templates" / "page-press.php").read_text()
        self.assertIn("update_option('alt_llms_press_figures', array('split' => $alt_ps['split']), false);", press)

    def test_only_the_tracker_path_gets_the_tracker_file(self):
        for uri, want in (("/blog/ai-layoff-tracker/llms.txt", "true"), ("/blog/llms.txt", "false"),
                          ("/blog/talent-intelligence-tracker/llms.txt", "false"), ("/llms.txt", "false"),
                          ("/blog/x/ai-layoff-tracker/llms.txt", "false"),
                          ("/blog/talent-intelligence-tracker/ai-layoff-tracker/llms.txt", "false")):
            self.assertEqual(self._php("var_export(alt_llms_is_tracker_request(%s));" % json.dumps(uri)), want, uri)


class TrackerLlmsIsServedNotWritten(unittest.TestCase):
    """The tracker file is answered by PHP, never written to disk (Codex P2 on #695).

    Measured 2026-11-18: /blog/ai-layoff-tracker/llms.txt reaches PHP on
    production (200, X-Robots-Tag: noindex and charset=utf-8, which only
    alt_serve_llms_txt sends; the static root file carries neither). Writing a
    file there would create a real ai-layoff-tracker/ directory in the WordPress
    root, the hub page's own slug, and the `!-d` rewrite condition would then
    stop WordPress from routing the tracker page at all.
    """

    def test_static_writer_targets_only_root_files(self):
        body = _fn("alt_write_static_files")
        self.assertNotIn("ai-layoff-tracker/", body)
        self.assertNotIn("alt_tracker_llms_txt_content", body)
        self.assertNotIn("ai-layoff-tracker/", _fn("alt_llms_sync"))

    def test_handler_answers_the_tracker_path_first(self):
        body = _fn("alt_serve_llms_txt")
        self.assertLess(body.index("alt_llms_is_tracker_request($uri)"), body.index("echo alt_llms_txt_published();"))


if __name__ == "__main__":
    unittest.main()
