"""Four output-encoding defects, all defence in depth, all fixed together.

None of these is a live hole today: the values that reach them are normalised
through fixed vocabularies or are integers. Depth is the point, and each one
was a guard that already existed somewhere else and had not been applied here.

1. `alt_csv_guard` tested `$value[0]` only. Excel and LibreOffice STRIP leading
   whitespace before deciding what a cell is, so a leading TAB or CR carried a
   formula straight through the guard that was written to stop it.
2. The quarterly appendix export (`alt_quarterly_appendix_download`) had NO
   formula guard at all, on the one artifact designed to be opened in a
   spreadsheet and cited.
3. `health.js`'s `esc` escaped `& < >` and not the quotes, while interpolating
   into `class="..."` and `title="..."`. In an attribute, an angle-bracket-only
   escape is not an escape.
4. `page-chart-embed.php` and `page-widget.php` emitted their bootstrap JSON
   with bare `wp_json_encode`, while `page-tracker.php` uses the JSON_HEX_*
   flags. Those two are the templates that ship inside somebody else's page.
"""
import json
import os
import pathlib
import re
import subprocess
import unittest
from shutil import which

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
EXPORT = PLUGIN / "includes" / "export.php"
HEALTH_JS = PLUGIN / "assets" / "health.js"
TEMPLATES = PLUGIN / "templates"


def php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    return which("php")


class CsvFormulaGuard(unittest.TestCase):
    """Run the real function, do not assert on its source text."""

    def setUp(self):
        if not php():
            self.skipTest("php not installed")
        src = EXPORT.read_text()
        fn = src[src.index("function alt_csv_guard"):]
        self.fn = fn[:fn.index("\n}\n") + 3]

    def _guard(self, values):
        shim = self.fn + """
$in = json_decode(file_get_contents('php://stdin'), true);
$out = array();
foreach ($in as $v) { $out[] = alt_csv_guard($v); }
echo json_encode($out);
"""
        proc = subprocess.run([php(), "-r", shim], input=json.dumps(values),
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_leading_tab_or_cr_no_longer_smuggles_a_formula_past(self):
        """The whole defect in one assertion.

        Excel trims the tab, sees '=', and the cell is a formula. The old guard
        looked at position zero, found a tab, and called it safe.
        """
        payloads = ["\t=cmd|'/c calc'!A1", "\r=HYPERLINK(\"http://x\")",
                    "\t\t+1+1", "\n-2+3", " @SUM(1)", "\r\n=1+1"]
        for original, guarded in zip(payloads, self._guard(payloads)):
            with self.subTest(payload=repr(original)):
                self.assertTrue(guarded.startswith("'"),
                                f"{original!r} still reads as a formula")

    def test_the_plain_cases_still_work(self):
        for original, guarded in zip(["=1+1", "+1", "-1", "@x"],
                                     self._guard(["=1+1", "+1", "-1", "@x"])):
            self.assertEqual(guarded, "'" + original)

    def test_ordinary_values_are_left_exactly_alone(self):
        plain = ["Acme Corp", "", "1200", "United States", "a-b", "x@y.com",
                 "Bausch + Lomb"]
        self.assertEqual(self._guard(plain), plain,
                         "a guard that mangles ordinary cells is a data bug")


class QuarterlyAppendixIsGuardedToo(unittest.TestCase):
    def test_the_appendix_writer_runs_every_cell_through_the_guard(self):
        src = EXPORT.read_text()
        fn = src[src.index("function alt_quarterly_appendix_download"):]
        fn = fn[:fn.index("\n}\n") + 3]
        self.assertIn("fputcsv", fn)
        self.assertIn("alt_csv_guard", fn,
                      "the quarterly appendix is a spreadsheet artifact and had "
                      "no formula guard at all")
        # Every fputcsv of DATA (not the static header row) must be guarded.
        for line in fn.splitlines():
            if "fputcsv" not in line or "'section', 'metric_or_dimension'" in line:
                continue
            self.assertIn("alt_csv_guard", line,
                          f"unguarded appendix row write: {line.strip()}")


class HealthJsEscapesQuotes(unittest.TestCase):
    def test_esc_covers_the_characters_that_break_an_attribute(self):
        src = HEALTH_JS.read_text()
        line = next(l for l in src.splitlines() if "const esc" in l)
        for char, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                             ('"', "&quot;"), ("'", "&#39;")):
            with self.subTest(char=char):
                self.assertIn(entity, line,
                              f"esc does not escape {char!r}, and it is "
                              f"interpolated into HTML attributes")
        self.assertRegex(line, r"""\[&<>["']+\]""",
                         "the character class must include the quotes")

    def test_esc_is_in_fact_used_inside_attributes(self):
        """If this stops being true the test above stops mattering, so it is
        asserted rather than assumed."""
        src = HEALTH_JS.read_text()
        self.assertTrue(
            re.search(r'(class|title)="[^"\n]*\$\{esc\(', src),
            "expected esc() interpolated into an attribute value")


class BootstrapUsesHexFlags(unittest.TestCase):
    FLAGS = ("JSON_HEX_TAG", "JSON_HEX_AMP", "JSON_HEX_APOS", "JSON_HEX_QUOT")

    def test_every_template_that_inlines_json_into_a_script_tag_uses_them(self):
        for name in ("page-tracker.php", "page-chart-embed.php", "page-widget.php"):
            src = (TEMPLATES / name).read_text()
            for call in re.findall(r"<script>[^<]*wp_json_encode\(.*?\)", src, re.S):
                for flag in self.FLAGS:
                    with self.subTest(template=name, flag=flag):
                        self.assertIn(flag, call,
                                      f"{name} inlines JSON into a <script> "
                                      f"block without {flag}")

    def test_php_lints_clean_after_the_change(self):
        if not php():
            self.skipTest("php not installed")
        for name in ("page-chart-embed.php", "page-widget.php", "../includes/export.php"):
            proc = subprocess.run([php(), "-l", str(TEMPLATES / name)],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
