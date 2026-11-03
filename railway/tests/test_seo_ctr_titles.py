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


def _company(name, first, last, warn, jobs=263, timeline=None):
    src = [{"type": "warn" if warn else "news", "url": "u"}]
    if timeline is None:  # default: every job in the latest year
        timeline = [{"year": int(last[:4]), "jobs": jobs}] if last else []
    return {"company": {"display_name": name}, "first_date": first, "last_date": last,
            "events": [{"sources": src}], "total_jobs": jobs, "ai_events": 0, "timeline": timeline}


SEO = (PLUGIN / "includes" / "seo-titles.php").read_text().replace("<?php", "", 1)
NOW = 1793664000  # 2026-11-03 UTC


def _seo(call):
    return _php("define('ALT_SEO_TITLES_TEST', 1);" + SEO + "echo json_encode(" + call + ");")


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Titles(unittest.TestCase):
    def company_title(self, data):
        code = "define('ALT_SEO_TITLES_TEST', 1);" + SEO + _fn(DIR, "alt_company_directory_has_warn") \
            + _fn(DIR, "alt_company_directory_name") + _fn(DIR, "alt_company_directory_title_text") \
            + _fn(DIR, "alt_company_directory_description") \
            + "$d = json_decode('%s', true); echo json_encode([alt_company_directory_title_text($d, %d)," \
              " alt_company_directory_description($d, %d)]);" % (json.dumps(data), NOW, NOW)
        return _php(code)

    def test_current_year_leads_with_query_count_and_month(self):
        t, d = self.company_title(_company("Safelite", "2026-03-01", "2026-09-01", True))
        self.assertEqual(t, "Safelite layoffs 2026: 263 jobs cut so far, latest Sep 2026")
        self.assertTrue(d.startswith("Safelite layoffs 2026: 263 jobs cut so far, latest Sep 2026. 263 jobs across 1 recorded layoff since 2026 in total."), d)
        self.assertLessEqual(len(d), 155)

    def test_older_latest_year_says_history_never_this_year(self):
        t, d = self.company_title(_company("SALLIE MAE", "2008-01-01", "2020-09-01", True))
        self.assertEqual(t, "Sallie Mae layoffs: 263 jobs cut since 2008")
        self.assertNotIn("2026", t + d)
        self.assertNotIn("2008-2020", t)

    def test_future_dated_notice_counts_as_this_year_without_a_future_month(self):
        t, _ = self.company_title(_company("Acme", "2025-01-01", "2027-02-01", False,
                                           timeline=[{"year": 2026, "jobs": 40}, {"year": 2025, "jobs": 223}]))
        self.assertEqual(t, "Acme layoffs 2026: 40 jobs cut so far")

    def test_a_year_is_only_ever_next_to_that_years_count(self):
        # 2,000 all-time, 10 of them in 2026 (Innodata shape): the 2026 figure is 10.
        tl = [{"year": 2019, "jobs": 1990}, {"year": 2026, "jobs": 10}]
        t, d = self.company_title(_company("Innodata Services, LLC", "2019-03-01", "2026-02-10", True, jobs=2000, timeline=tl))
        self.assertTrue(t.startswith("Innodata Services layoffs 2026: 10 jobs cut so far"), t)
        self.assertLessEqual(len(t), 60)
        self.assertNotIn("2026: 2,000", t + d)
        self.assertIn("2,000 jobs across 1 recorded layoff since 2019 in total", d)
        # Notices dated ahead but nothing in 2026 itself: no year, all-time wording.
        tl = [{"year": 2024, "jobs": 263}]
        t, d = self.company_title(_company("Acme", "2024-01-01", "2027-02-01", False, timeline=tl))
        self.assertEqual(t, "Acme layoffs: 263 jobs cut since 2024")
        self.assertNotIn("2026", t + d)

    def test_missing_data_fallbacks(self):
        t, d = self.company_title(_company("Acme", "", "", False, jobs=0))
        self.assertEqual(t, "Acme layoffs: dates and timeline")
        self.assertTrue(d.startswith("Acme layoffs: 1 recorded layoff. "), d)
        self.assertNotIn(" 0 ", d)

    def test_warn_only_when_a_row_cites_one(self):
        t, d = self.company_title(_company("Acme", "2026-01-01", "2026-02-01", False, jobs=0))
        self.assertNotIn("WARN", t + d)

    def test_lengths_hold_for_long_names(self):
        for name in ("International Business Machines Corporation Holdings Worldwide Group Partners",
                     "The Clift Royal Sonesta Hotel", "Innodata Services, LLC"):
            for last in ("2026-02-01", "2019-02-01", ""):
                t, d = self.company_title(_company(name, "2010-01-01" if last else "", last, True, jobs=1234567))
                self.assertLessEqual(len(t), 60, t)
                self.assertLessEqual(len(d), 155, d)
                self.assertIn("layoffs", t)
                self.assertNotIn("\u2014", t + d)

    def test_display_name_casing_and_suffixes(self):
        cases = {"SALLIE MAE": "Sallie Mae", "Innodata Services, LLC": "Innodata Services",
                 "Safelite Glass Corp.": "Safelite Glass", "THE CLIFT ROYAL SONESTA HOTEL": "The Clift Royal Sonesta Hotel",
                 "IBM": "IBM", "AT&T INC": "AT&T", "eBay Inc.": "eBay", "HSBC BANK USA, N.A.": "HSBC Bank USA, N.A.",
                 "Medline": "Medline", "ACME HOLDINGS LTD": "Acme Holdings", "WAL-MART STORES, INC.": "Wal-Mart Stores",
                 "LLC": "LLC", "Pipedrive": "Pipedrive"}
        got = _seo("array_map('alt_seo_display_name', json_decode('%s', true))" % json.dumps(list(cases)))
        self.assertEqual(dict(zip(cases, got)), cases)

    def test_industry_title_and_description(self):
        # The live bug (2.20.292): all-time 2,065,487 was labelled 2026.
        t = _seo("alt_seo_layoff_title('Technology', '2027-01-15', 2065487, false, %d, 41200, '2002-01-01')" % NOW)
        self.assertEqual(t, "Technology layoffs 2026: 41,200 jobs cut so far")
        d = _seo("alt_seo_layoff_description('Technology', 4388, 2065487, '2026-10-30', true, 54, %d, ' at 2,207 employers', 41200, '2002-01-01')" % NOW)
        self.assertLessEqual(len(d), 155, d)
        self.assertTrue(d.startswith("Technology layoffs 2026: 41,200 jobs cut so far, latest Oct 2026. 2,065,487 jobs across 4,388"), d)
        self.assertNotIn("2026: 2,065,487", d)
        t = _seo("alt_seo_layoff_title('Technology', '2027-01-15', 2065487, false, %d, 0, '2002-01-01')" % NOW)
        self.assertEqual(t, "Technology layoffs: 2,065,487 jobs cut since 2002")
        y = _seo("alt_seo_year_jobs([['year'=>2025,'jobs'=>5],['year'=>2026,'jobs'=>7]], 2026)")
        self.assertEqual(y, 7)

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
        for src in (TRACKER, DIR, SEO):
            for line in src.splitlines():
                if "alt-intro" in line or "jobs cut" in line:
                    self.assertNotIn("—", line)
