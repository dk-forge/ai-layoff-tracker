"""THE BOARD AND THE DATE PRESETS COUNT THE SITE'S DAY, NOT THE BROWSER'S.

Owner report 2026-10-17 (seen on a phone, in the Netherlands): the at-a-glance
board's Today column read 0 and the week looked short, while /query returned
rows for the same windows.

Root cause, reproduced live on 2026-10-18 with a 390px headless render under a
browser time zone ahead of New York: layoffs.js built the board's six windows
and the Today / Last 7 days / ... presets from the BROWSER's calendar day. The
server counts in site time (America/New_York, alt_site_today()). For a reader in
Amsterdam that is a different date from 18:00 to 24:00 New York time, six hours
of every day. In those hours:

  * the server-inlined board mismatched (bootParamsMatch) and was thrown away;
  * the board re-fetched with from=to=TOMORROW-in-New-York, which holds no
    filings yet (Today = 0) or only WARN notices dated ahead;
  * This week lost its first real day and gained an empty one;
  * the "Today" preset filtered the table to that empty day, so rows went
    missing from the table as well.

The fix reads the calendar day in the SITE zone (Intl, zone from altData.siteTz
with America/New_York as the fallback, the same zone alt_site_timezone() names).
These tests run the real functions in node with the browser clock injected.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import jsrun  # noqa: E402

PRE = ("function pad2(n) { return (n < 10 ? '0' : '') + n; }\n"
       "var window = { altData: { siteTz: 'America/New_York' } };\n")


def site_day(utc_iso, tz):
    """The site day siteNow() reports for a UTC instant, under a browser TZ."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = tz
    try:
        return jsrun.run(
            ["siteNow", "isoDay"], PRE,
            "isoDay(siteNow(new Date('%s')))" % utc_iso)
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old


class SiteDayIsNewYorkWhateverTheBrowserZone(unittest.TestCase):

    def setUp(self):
        jsrun.require_node(self)

    def test_amsterdam_after_midnight_still_reads_new_york_today(self):
        # 2026-10-17 23:30 New York = 2026-10-18 05:30 Amsterdam.
        self.assertEqual(site_day("2026-10-18T03:30:00Z", "Europe/Amsterdam"),
                         "2026-10-17")

    def test_far_east_browser(self):
        self.assertEqual(site_day("2026-10-18T16:46:00Z", "Pacific/Kiritimati"),
                         "2026-10-18")

    def test_west_coast_browser_in_the_evening(self):
        # 2026-10-18 01:00 New York, still 2026-10-17 in Los Angeles.
        self.assertEqual(site_day("2026-10-18T05:00:00Z", "America/Los_Angeles"),
                         "2026-10-18")

    def test_a_new_york_browser_is_unchanged(self):
        self.assertEqual(site_day("2026-10-18T16:46:00Z", "America/New_York"),
                         "2026-10-18")


class TheBoardAndPresetsUseTheSiteDay(unittest.TestCase):
    """Source pins on the two call sites, backed by the behaviour above."""

    def setUp(self):
        self.src = jsrun.JS_PATH.read_text()

    def test_board_windows_are_built_from_site_now(self):
        body = jsrun.extract("updateNarrative", self.src)
        self.assertIn("boardWindows(now)", body)
        self.assertRegex(body, r"var now = siteNow\(\);")

    def test_date_presets_are_built_from_site_now(self):
        start = self.src.index("var DATE_PRESETS = {")
        block = self.src[start:self.src.index("};", start)]
        self.assertNotIn("new Date()", block)
        self.assertIn("siteNow()", block)

    def test_php_hands_the_site_zone_to_the_page(self):
        php = (jsrun.PLUGIN / "ai-layoff-tracker.php").read_text()
        self.assertIn("'siteTz'", php)


if __name__ == "__main__":
    unittest.main()
