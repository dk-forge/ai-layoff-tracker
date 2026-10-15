"""SERP titles, descriptions and the hub's latest-report links (2.20.265).

Runs the PURE PHP functions themselves under the php CLI, so a test pins the
rendered string rather than a substring of the source.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
DIR = (PLUGIN / "includes" / "company-directory.php").read_text()
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text()
REPORT = (PLUGIN / "includes" / "report-seo.php").read_text()
TRACKER = (PLUGIN / "templates" / "page-tracker.php").read_text()


def _fn(src, name):
    m = re.search(r"function " + re.escape(name) + r"\(.*?\n}\n", src, re.S)
    assert m, name
    return m.group(0)


def _php(code):
    p = subprocess.run(["php", "-r", code], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def _company(name, first, last, warn):
    src = [{"type": "warn" if warn else "news", "url": "u"}]
    return {"company": {"display_name": name}, "first_date": first, "last_date": last,
            "events": [{"sources": src}], "total_jobs": 263, "ai_events": 0}


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Titles(unittest.TestCase):
    def company_title(self, data):
        code = _fn(DIR, "alt_company_directory_title_text") + \
            "echo json_encode(alt_company_directory_title_text(json_decode('%s', true)));" % json.dumps(data)
        return _php(code)

    def test_company_title_leads_with_query_and_years(self):
        t = self.company_title(_company("Safelite", "2026-03-01", "2026-09-01", True))
        self.assertEqual(t, "Safelite layoffs 2026: dates, job counts and WARN notices")

    def test_year_is_the_records_year_never_today(self):
        t = self.company_title(_company("Sallie Mae", "2008-01-01", "2020-05-01", True))
        self.assertTrue(t.startswith("Sallie Mae layoffs 2008-2020"), t)
        self.assertNotIn("2026", t)

    def test_warn_only_when_a_row_cites_one(self):
        t = self.company_title(_company("Acme", "2026-01-01", "2026-02-01", False))
        self.assertNotIn("WARN", t)

    def test_long_names_stay_within_60(self):
        t = self.company_title(_company("International Business Machines Corporation Holdings",
                                        "2019-01-01", "2026-02-01", True))
        self.assertLessEqual(len(t), 60)
        self.assertIn("layoffs", t)

    def test_hub_title(self):
        t = _php(_fn(MAIN, "alt_tracker_title_text") + "echo json_encode(alt_tracker_title_text(2026));")
        self.assertEqual(t, "AI Layoffs Tracker 2026: Live Job Cuts Tied to AI")
        self.assertLessEqual(len(t), 60)

    def test_latest_months_are_complete_months_newest_first(self):
        code = ("function alt_report_clean_url($k,$s){return '/report/'.$s.'/';}"
                + _fn(REPORT, "alt_report_period_label") + _fn(REPORT, "alt_report_latest_months")
                + "echo json_encode(alt_report_latest_months(3, gmmktime(0,0,0,10,15,2026)));")
        self.assertEqual(_php(code), [["/report/2026-09/", "September 2026"],
                                      ["/report/2026-08/", "August 2026"],
                                      ["/report/2026-07/", "July 2026"]])
        code = code.replace("10,15,2026", "1,2,2026")
        self.assertEqual(_php(code)[0], ["/report/2025-12/", "December 2025"])


class Wiring(unittest.TestCase):
    def test_hub_links_and_indexnow_use_the_helper(self):
        self.assertIn("alt_report_latest_months(3)", TRACKER)
        self.assertIn("alt_report_latest_months(2)", MAIN)

    def test_no_em_dash_in_new_copy(self):
        for src in (TRACKER, DIR):
            for line in src.splitlines():
                if "alt-intro" in line or "dates, job counts" in line:
                    self.assertNotIn("—", line)
