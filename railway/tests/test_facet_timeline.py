"""Company, country and US state pages carry a year-by-year TIMELINE.

The 2026-09-24 growth audit found every other part of the brief already in
place on these pages (own canonical, title/meta, Dataset + BreadcrumbList on
indexable pages only, headline stat, sources, a thin-content floor with
noindex below it, a self-served sitemap: see test_facet_pages.py and the
company-directory guards). The one gap was a timeline, so a reader landing
from "<state> layoffs" sees whether the record is rising or falling.

alt_timeline_by_year() is pure and is exercised here with the real PHP. The
rules it holds:
- one bucket per year, oldest first, jobs and AI jobs summed;
- a month still in progress is counted AS OF TODAY (the aggregate's
  `to_date` block) so a notice for next week is not already history;
- the current year is flagged partial, so the template says "so far";
- dates before 2015 (outside the tracker's accepted range) are dropped.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
FACET = PLUGIN / "includes" / "facet-pages.php"
FACET_T = PLUGIN / "templates" / "page-facet.php"
COMPANY = PLUGIN / "includes" / "company-directory.php"
COMPANY_T = PLUGIN / "templates" / "page-company-directory.php"


def _timeline(points, year):
    src = FACET.read_text(encoding="utf-8")
    m = re.search(r"\nfunction alt_timeline_by_year\s*\(.*?\n\}", src, re.S)
    assert m, "alt_timeline_by_year is missing"
    code = m.group(0) + "\n$p = json_decode($argv[1], true);\necho json_encode(alt_timeline_by_year($p, (int) $argv[2]));\n"
    p = subprocess.run(["php", "-r", code, "--", json.dumps(points), str(year)],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return json.loads(p.stdout)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class TimelineMath(unittest.TestCase):
    def test_buckets_by_year_oldest_first(self):
        got = _timeline([
            {"date": "2025-03", "jobs": 100, "ai_jobs": 10},
            {"date": "2024-11-02", "jobs": 50, "ai_jobs": 0},
            {"date": "2025-07", "jobs": 25, "ai_jobs": 5},
        ], 2026)
        self.assertEqual([r["year"] for r in got], [2024, 2025])
        self.assertEqual(got[1]["jobs"], 125)
        self.assertEqual(got[1]["ai_jobs"], 15)
        self.assertFalse(got[1]["partial"])

    def test_in_progress_month_counts_to_date(self):
        got = _timeline([{"date": "2026-09", "jobs": 900, "ai_jobs": 90,
                          "to_date": {"jobs": 300, "ai_jobs": 30}}], 2026)
        self.assertEqual(got[0]["jobs"], 300)
        self.assertEqual(got[0]["ai_jobs"], 30)
        self.assertTrue(got[0]["partial"])

    def test_out_of_range_years_dropped(self):
        got = _timeline([{"date": "2001-01", "jobs": 5, "ai_jobs": 0},
                         {"date": "", "jobs": 5, "ai_jobs": 0},
                         {"date": "2016-01", "jobs": 5, "ai_jobs": 0}], 2026)
        self.assertEqual([r["year"] for r in got], [2016])


class Wiring(unittest.TestCase):
    def test_facet_asks_for_the_series_and_builds_a_timeline(self):
        src = FACET.read_text(encoding="utf-8")
        self.assertIn("$blocks[] = 'series';", src)
        self.assertIn("'timeline'", src)

    def test_company_builds_a_timeline(self):
        self.assertIn("'timeline'", COMPANY.read_text(encoding="utf-8"))

    def test_both_templates_render_it_before_the_record(self):
        for path, loop in ((FACET_T, "<ol"), (COMPANY_T, "<ol class=\"alt-company-event-list\"")):
            src = path.read_text(encoding="utf-8")
            self.assertTrue("partials/timeline.php" in src, path.name)
            self.assertLess(src.index("partials/timeline.php"), src.index(loop), path.name)
        partial = (PLUGIN / "templates" / "partials" / "timeline.php").read_text(encoding="utf-8")
        self.assertIn('class="alt-timeline"', partial)
        self.assertIn("count($alt_timeline) < 2", partial)


if __name__ == "__main__":
    unittest.main()
