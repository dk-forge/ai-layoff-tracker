"""The monthly AI-layoffs report: ready on the first business day, with a pitch.

Owner scope 2026-09-24, item 4. The report page itself (?period=YYYY-MM) is
rendered live; what this module adds is the TIMING and the PRESS KIT around
it, in includes/monthly-report.php:

- alt_mr_first_business_day(): the first weekday of a month that is not a US
  federal holiday that can land in days 1-7 (New Year's Day and its Monday
  observance, Labor Day). The national job-cuts announcement survey publishes
  around the first Thursday; ours is published on or before that day.
- alt_mr_latest_period(): the newest month whose report is "released", i.e.
  the previous month once today reaches this month's first business day.
- alt_mr_pitch(): the press-release summary built ONLY from figures passed in.
  A missing figure produces no sentence rather than a zero or a guess.
- a daily WP-cron tick stores the latest release + pitch in an option, so the
  press page and the press-list sender read one frozen text.

Nothing here emails anybody. Journalist outreach is admin-click only (see
test_press_list.py).
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "monthly-report.php"
MAIN = PLUGIN / "ai-layoff-tracker.php"
REPORT = PLUGIN / "templates" / "page-report.php"
PRESS = PLUGIN / "templates" / "page-press.php"

PURE = ("alt_mr_first_business_day", "alt_mr_latest_period", "alt_mr_pitch")


def _php(body, *args):
    src = MOD.read_text(encoding="utf-8")
    chunks = []
    for name in PURE:
        m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
        assert m, f"{name} is missing"
        chunks.append(m.group(0))
    code = "\n".join(chunks) + "\n" + body
    p = subprocess.run(["php", "-r", code, "--", *args], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Timing(unittest.TestCase):
    def fbd(self, y, m):
        return int(_php(f"echo alt_mr_first_business_day({y}, {m});"))

    def test_weekday_first(self):
        self.assertEqual(self.fbd(2026, 10), 1)   # Thu 1 Oct 2026

    def test_weekend_rolls_to_monday(self):
        self.assertEqual(self.fbd(2026, 11), 2)   # Sun 1 Nov -> Mon 2

    def test_new_year(self):
        self.assertEqual(self.fbd(2026, 1), 2)    # Thu 1 Jan holiday -> Fri 2
        self.assertEqual(self.fbd(2023, 1), 3)    # Sun 1 Jan, observed Mon 2 -> Tue 3

    def test_labor_day(self):
        self.assertEqual(self.fbd(2025, 9), 2)    # Mon 1 Sep 2025 Labor Day -> Tue 2

    def test_never_after_the_first_thursday(self):
        import datetime as dt
        for y in range(2024, 2031):
            for m in range(1, 13):
                d = dt.date(y, m, 1)
                first_thu = 1 + (3 - d.weekday()) % 7
                if m == 1 and first_thu == 1:
                    continue  # New Year's Day is itself the first Thursday
                self.assertLessEqual(self.fbd(y, m), first_thu, (y, m))

    def test_latest_period(self):
        got = lambda today: _php(f"echo alt_mr_latest_period('{today}');").strip()
        self.assertEqual(got("2026-11-01"), "2026-09")   # Sunday: Oct not yet out
        self.assertEqual(got("2026-11-02"), "2026-10")
        self.assertEqual(got("2026-01-01"), "2025-11")
        self.assertEqual(got("2026-01-02"), "2025-12")


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Pitch(unittest.TestCase):
    FIG = {
        "label": "August 2026", "prior_label": "July 2026",
        "verified_jobs": 41234, "prior_verified_jobs": 38000,
        "ai_verified_jobs": 5200, "entries": 812,
        "top_companies": [["Acme Corp", 9000], ["Globex", 4000]],
        "top_states": [["CA", 8000], ["TX", 6000]],
        "top_countries": [["United States", 30000], ["Germany", 4000]],
        "report_url": "https://asktherecruiter.com/blog/ai-layoff-tracker/report/?period=2026-08",
        "csv_url": "https://asktherecruiter.com/blog/wp-admin/admin-post.php?action=alt_export_csv",
        "contact_url": "https://asktherecruiter.com/blog/contact/",
    }

    def pitch(self, fig):
        return _php("echo alt_mr_pitch(json_decode($argv[1], true));", json.dumps(fig))

    def test_carries_the_headline_figures(self):
        text = self.pitch(self.FIG)
        for needle in ("August 2026", "41,234", "up 9%", "July 2026", "5,200", "13%",
                       "Acme Corp", "CA", "Germany", "812", "period=2026-08",
                       "alt_export_csv", "/contact/"):
            self.assertIn(needle, text)

    def test_missing_figures_say_nothing(self):
        fig = dict(self.FIG, prior_verified_jobs=0, top_states=[], top_companies=[])
        text = self.pitch(fig)
        self.assertNotIn("up ", text)
        self.assertNotIn("down ", text)
        self.assertNotIn("Acme", text)
        self.assertNotIn("US states", text)

    def test_no_long_dashes(self):
        text = self.pitch(self.FIG)
        self.assertNotIn("—", text)
        self.assertNotIn("–", text)


class Wiring(unittest.TestCase):
    def test_module_loaded_with_race_guard(self):
        src = MAIN.read_text(encoding="utf-8")
        self.assertIn("'monthly-report.php'", src)
        self.assertIn("is_readable(ALT_PLUGIN_DIR . 'includes/' . $alt_growth_file)", src)

    def test_daily_cron_is_scheduled(self):
        src = MOD.read_text(encoding="utf-8")
        self.assertIn("wp_schedule_event(", src)
        self.assertIn("'alt_monthly_report_tick'", src)
        self.assertIn("update_option('alt_monthly_report_latest'", src)

    def test_report_page_monthly_extras(self):
        src = REPORT.read_text(encoding="utf-8")
        for needle in ("alt_mr_figures(", "alt-mr-press-summary", "alt_mr_pitch(",
                       "alt_mr_csv_url(", "Press contact"):
            self.assertIn(needle, src)

    def test_press_page_latest_monthly_section(self):
        src = PRESS.read_text(encoding="utf-8")
        self.assertIn('id="alt-latest-monthly"', src)
        self.assertIn("alt_monthly_report_latest", src)


if __name__ == "__main__":
    unittest.main()
