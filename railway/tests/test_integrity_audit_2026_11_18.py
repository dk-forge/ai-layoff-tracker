"""Analytics audit 2026-11-18: numbers that disagreed on one screen, and pages
with no sign-up path. Each check reads the shipped source."""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"


def _read(rel):
    return (PLUGIN / rel).read_text(encoding="utf-8")


class LargestEntryLinksSomewhere(unittest.TestCase):
    """'Largest entry: FirstFruits, LLC 1,200' linked to href="#"."""

    def test_no_hash_href_on_the_board(self):
        self.assertNotIn('href="#" data-company', _read("templates/page-tracker.php"))
        self.assertNotIn('href="#" data-company', _read("assets/layoffs.js"))

    def test_fallback_is_a_company_filter_url(self):
        self.assertIn("'&amp;company=' . esc_attr(rawurlencode($alt_lname))",
                      _read("templates/page-tracker.php"))
        self.assertIn("'&amp;company=' + escapeHtml(encodeURIComponent(name))",
                      _read("assets/layoffs.js"))


class ReportNamesItsBasis(unittest.TestCase):
    """October: 81,061 on the report (effective) vs 88,265 on home (filing)."""

    def test_report_hero_says_effective_date(self):
        self.assertIn("counted by effective date", _read("templates/page-report.php"))

    def test_report_sql_is_still_effective(self):
        self.assertIn("layoff_date BETWEEN", _read("templates/page-report.php"))

    def test_press_summary_says_effective_date(self):
        self.assertIn("dated by effective date", _read("includes/monthly-report.php"))


class DateModifiedIsTheDataChange(unittest.TestCase):
    def test_no_render_clock_in_date_modified(self):
        for rel in ("ai-layoff-tracker.php", "includes/page-freshness.php"):
            src = _read(rel)
            for line in src.splitlines():
                if "dateModified" in line and "=>" in line:
                    self.assertNotRegex(line, r"gmdate\('Y-m-d'\)|time\(\)|\$now", (rel, line))


class SignupPathOnHighTrafficPages(unittest.TestCase):
    def test_ai_quotes_and_reports_carry_the_block(self):
        self.assertIn("alt_atr_cta_line_html('ai_quotes')", _read("templates/page-ai-quotes.php"))
        rep = _read("templates/page-report.php")
        self.assertIn("alt_atr_cta_line_html(", rep)
        self.assertIn("'report_month'", rep)
        self.assertIn("'report_quarter'", rep)

    def test_one_utm_source_per_tracker(self):
        for path in PLUGIN.rglob("*"):
            if path.suffix in (".php", ".js"):
                self.assertNotRegex(path.read_text(encoding="utf-8", errors="ignore"),
                                    r"utm_source['\"=\s>]*layoff_tracker", str(path))


if __name__ == "__main__":
    unittest.main()


import shutil as _shutil  # noqa: E402
import sys as _sys  # noqa: E402
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import jsrun  # noqa: E402


class HeadlineAndYtdReconcileOnTheFilingBasis(unittest.TestCase):
    """959,944 (whole calendar year) over a 941,076 YTD column, both by filing
    date. The gap is headline verified minus the board's own YTD cell, never
    the aggregate's to_date_* (cut on the EFFECTIVE date; Codex, PR #691)."""

    SENTENCE = "jobs filed with a date after today; every column here stops at today."

    def test_server_uses_the_board_ytd_cell_not_to_date(self):
        tpl = _read("templates/page-tracker.php")
        self.assertIn("$alt_sv['total'] - (int) $alt_board['ytd']['totals']['jobs']", tpl)
        self.assertIn(self.SENTENCE, tpl)
        foot = tpl[tpl.index("alt-sb-foot-basis"):tpl.index("</ul>", tpl.index("alt-sb-foot-basis"))]
        self.assertNotIn("$alt_sv['later']", foot)
        self.assertNotIn("$alt_sv['to-date']", foot)

    def test_js_uses_the_board_ytd_cell_not_to_date(self):
        js = _read("assets/layoffs.js")
        body = jsrun.extract("laterNote")
        self.assertIn("BOARD_YTD.jobs", body)
        self.assertNotIn("to_date", body)
        self.assertIn(self.SENTENCE, jsrun.extract("laterSentence"))
        self.assertIn("BOARD_YTD = { jobs: D.ytd.t.jobs", js)

    @unittest.skipUnless(_shutil.which("node"), "UNKNOWN, NOT RUN: node not installed")
    def test_the_note_computes_the_gap_only_on_the_default_view(self):
        pre = ("var fmt=function(n){return Number(n).toLocaleString('en-US');};"
               "var DATE_BASIS='notice';"
               "var LAST_AGG={totals:{jobs:900000,announced_jobs:56}};"
               "var BOARD_YTD={jobs:881076,world:true,year:2026};"
               "var P={years:'2026',date_basis:'notice'};"
               "function currentParams(){return P;}\n")
        out = jsrun.run(["laterNote", "laterSentence"], pre, "laterNote()")
        self.assertIn("18,868 jobs filed with a date after today", out)
        filtered = jsrun.run(["laterNote", "laterSentence"],
                             pre + "P={years:'2026',date_basis:'notice',country:'Germany'};", "laterNote()")
        self.assertEqual(filtered, "")
        effective = jsrun.run(["laterNote", "laterSentence"],
                              pre + "DATE_BASIS='effective';", "laterNote()")
        self.assertEqual(effective, "")
