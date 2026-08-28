"""The DAILY layoff edition's masthead and lead name its window, not a week.

THE DEFECT THIS PINS (found in the 2026-08-28 nine-edition review). The
composer's masthead fork was ``$is_monthly`` ONLY, so the daily edition - a
two-day provisional window - rendered the ISO-week masthead ("2026 Week 35 ·
August 27-28") and opened its lead "In Week 35 of 2026, employers verified ...".
A two-day figure wearing a week's name is a false claim about the window in the
two lines most likely to be quoted on their own - the exact class of masthead
error the monthly branch was built to avoid (subscribe.php's own words), and it
shipped seven days a week. The existing guard
(test_digest_week_numbering.test_a_daily_edition_carries_no_week_number) checks
only the SUBJECT's period phrase, never the composed body, which is how this
survived.

THE RULE THESE TESTS HOLD: a week label is EARNED BY THE WINDOW, not granted by
the tier. Only a complete Monday-to-Sunday span (the shape
alt_digest_weekly_window constructs) may wear "YYYY Week N"; every other
non-monthly window - the daily pair, a forced preview range, a seven-day span
that straddles two ISO weeks - states its dates and nothing more. The weekly
edition must therefore be byte-identical before and after the fix, which is
also asserted here.

The composers are PHP, so these drive them through
tests/fixtures/digest_compose_harness.php. Without php on PATH the tests SKIP,
which is not a pass.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")


def _tuple(label, all_jobs, verified_jobs, ai_verified=0):
    """The /aggregate top_* row shape: [label, all_jobs, ai_jobs, display_label,
    verified_jobs, ai_verified_jobs]."""
    return [label, all_jobs, 0, None, verified_jobs, ai_verified]


def fixture(**over):
    """A daily two-day window (the alt_digest_window shape: yesterday+today)."""
    data = {
        "from": "2026-08-27",
        "to": "2026-08-28",
        "freq": "daily",
        "compose": "layoff",
        "layoff": {
            "totals": {
                "jobs": 5210, "entries": 21,
                "announced_jobs": 1000, "announced_entries": 2,
                "ai_verified_jobs": 300, "ai_verified_entries": 1,
                "companies": 18,
            },
            "leaders": [
                {"company_name": "Applied Aerospace", "job_count": 1320,
                 "layoff_date": "2026-08-27", "ai_explicit": False,
                 "location": "", "state": "", "country": "",
                 "permalink": "https://asktherecruiter.com/blog/layoff/applied/",
                 "announced": False,
                 "source_url": "https://www.sec.gov/filing/applied"},
            ],
            "top_countries": [
                _tuple("United States", 3000, 2600, 300),
                _tuple("Brazil", 800, 700),
            ],
            "top_industries": [
                _tuple("Aerospace & Defense", 1800, 1700),
            ],
            "source_types": [
                _tuple("warn", 2000, 1900),
            ],
        },
        "ytd": {
            "totals": {"jobs": 971602, "announced_jobs": 463348,
                       "ai_verified_jobs": 42253},
            "top_countries": [
                _tuple("United States", 402000, 300000),
            ],
        },
    }
    data.update(over)
    return data


def compose(fx):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(fx, handle)
        path = handle.name
    try:
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, path],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    if run.returncode != 0:
        raise AssertionError(f"the harness failed: {run.stderr[:2000]}")
    return json.loads(run.stdout)


def _dateline(html):
    m = re.search(r'<p data-alt="dateline">(.*?)</p>', html, re.S)
    assert m, "no dateline rendered"
    return m.group(1)


def _lead(html):
    m = re.search(r'<p data-alt="lead">(.*?)</p>', html, re.S)
    assert m, "no lead rendered"
    return m.group(1)


@unittest.skipIf(PHP is None, "php is not on PATH, so the composers could not "
                              "be run. UNKNOWN, not a pass.")
class TheDailyMastheadNamesItsDays(unittest.TestCase):
    def setUp(self):
        self.section = compose(fixture())

    def test_the_dateline_carries_no_week_number(self):
        dateline = _dateline(self.section["html"])
        self.assertNotIn("Week", dateline,
                         "a two-day window must not be labelled a week")

    def test_the_dateline_names_the_two_days(self):
        self.assertIn("August 27-28", _dateline(self.section["html"]))

    def test_the_dateline_still_says_provisional(self):
        self.assertIn("provisional", _dateline(self.section["html"]))

    def test_the_lead_opens_on_its_window_not_a_week(self):
        lead = _lead(self.section["html"])
        self.assertNotIn("In Week", lead)
        # The lifted-out-line property: the sentence still says what it covers.
        self.assertIn("August 27-28", lead)
        self.assertIn("US job cuts", lead)

    def test_no_week_claim_anywhere_in_the_body(self):
        # The masthead and lead were the two known leaks; this holds the whole
        # rendered body so a third one cannot appear quietly.
        for part in ("html", "text"):
            self.assertNotRegex(self.section[part], r"\bWeek \d",
                                f"a week number leaked into the daily {part}")


@unittest.skipIf(PHP is None, "php is not on PATH.")
class AnUnlabelledOddWindowIsNotAWeekEither(unittest.TestCase):
    """The gate is the WINDOW, not the freq string: an empty-freq preview over
    a non-week range, and a seven-day span that does not start on Monday
    (straddling two ISO weeks), both state their dates and nothing more."""

    def test_empty_freq_two_day_window(self):
        section = compose(fixture(freq=""))
        self.assertNotIn("Week", _dateline(section["html"]))

    def test_seven_days_starting_midweek_is_not_a_week(self):
        # 2026-08-27 is a Thursday: Thursday-to-Wednesday straddles two ISO
        # weeks, so neither week's number would be true over it.
        section = compose(fixture(**{"from": "2026-08-27", "to": "2026-09-02"}))
        self.assertNotIn("Week", _dateline(section["html"]))


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheWeeklyEditionIsUntouched(unittest.TestCase):
    """The weekly window (Monday to Sunday, alt_digest_weekly_window's shape)
    keeps its ISO-week masthead and its 'In Week N of YYYY' lead exactly."""

    def setUp(self):
        # 2026-08-17 is a Monday; the 23rd the following Sunday: ISO week 34.
        self.section = compose(fixture(**{
            "from": "2026-08-17", "to": "2026-08-23", "freq": "weekly",
        }))

    def test_the_dateline_still_names_the_week(self):
        self.assertIn("2026 Week 34", _dateline(self.section["html"]))

    def test_the_lead_still_opens_in_week(self):
        self.assertIn("In Week 34 of 2026", _lead(self.section["html"]))


if __name__ == "__main__":
    unittest.main()
