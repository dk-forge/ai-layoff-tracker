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


class HeadlineAndYtdReconcile(unittest.TestCase):
    """959,944 (whole calendar year) over a 941,076 YTD column, 'same basis'."""

    SENTENCE = "jobs filed with a date after today; every column here stops at today."

    def test_server_and_js_print_the_computed_gap(self):
        tpl = _read("templates/page-tracker.php")
        self.assertIn("$alt_sv['later']", tpl)
        self.assertIn(self.SENTENCE, tpl)
        js = _read("assets/layoffs.js")
        self.assertIn("function laterNote()", js)
        self.assertIn(self.SENTENCE, js)


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
