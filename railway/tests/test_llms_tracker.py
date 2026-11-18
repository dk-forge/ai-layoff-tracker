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
        self.assertIn("documents 77,526 verified job cuts that took effect in 2026 so far. "
                      "Source: https://example.org/blog/ai-layoff-tracker/press/#alt-press-period", out)
        self.assertIn("3,345 verified job cuts with effective dates in 2026 were attributed to AI", out)
        for line in out.splitlines():
            if line.startswith("- As of"):
                self.assertIn("Source: https://", line)

    def test_cold_cache_prints_no_figures(self):
        for ps in (False, {}, {"split": {"as_of": "", "to_date": 5}}):
            out = self._txt(ps)
            self.assertNotIn("Quotable figures", out)
            self.assertIn("# AI Layoff Tracker", out)

    def test_tiers_from_another_year_are_not_quoted(self):
        ps = json.loads(json.dumps(PS))
        ps["tiers"]["year"] = 2025
        self.assertNotIn("attributed to AI", self._txt(ps))

    def test_only_the_tracker_path_gets_the_tracker_file(self):
        for uri, want in (("/blog/ai-layoff-tracker/llms.txt", "true"), ("/blog/llms.txt", "false"),
                          ("/blog/talent-intelligence-tracker/llms.txt", "false"), ("/llms.txt", "false")):
            self.assertEqual(self._php("var_export(alt_llms_is_tracker_request(%s));" % json.dumps(uri)), want, uri)


if __name__ == "__main__":
    unittest.main()
