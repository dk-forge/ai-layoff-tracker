"""The two-tier US headline and the public monthly survey comparison.

Owner decision 2026-08-14, explicit yes, two public-surface changes:

1. Wherever a headline total is stated, the verified figure stays PRIMARY and
   an announced-inclusive companion is stated beside it, labeled with ONE plain
   sentence. The sentence is defined once (alt_announced_tier_sentence in
   db.php) and rendered verbatim by page-tracker.php (hero), page-press.php
   (statements and soundbites) and page-report.php (headline box), so the three
   surfaces cannot drift one edit at a time. The tier is a STAGE distinction:
   it does not change the basis of any surface, and the board deliberately
   still carries no third AI row (test_signal_board_periods pins that).

2. The month-by-month comparison against the national announcement survey is
   public, on the press page. Our side is re-derived live on render; the
   survey side is hand-entered constants in data/survey-monthly.json with the
   date they were read, shared with railway/monthly_us_comparison.py so the
   repo holds ONE copy of the comparator. Staleness is visible, not silent:
   the page prints an awaiting note for a released month with no constant, and
   the script reports STALE. Both use the same due window, pinned here.

The organization behind the survey is never named anywhere in the repo
(standalone-brand rule); the JSON carries figures and dates only.
"""
import json
import re
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
DB = (PLUGIN / "includes" / "db.php").read_text()
TRACKER = (PLUGIN / "templates" / "page-tracker.php").read_text()
PRESS = (PLUGIN / "templates" / "page-press.php").read_text()
REPORT = (PLUGIN / "templates" / "page-report.php").read_text()
JS = (PLUGIN / "assets" / "layoffs.js").read_text()
DATA = PLUGIN / "data" / "survey-monthly.json"
SCRIPT_PATH = ROOT / "railway" / "monthly_us_comparison.py"
SCRIPT = SCRIPT_PATH.read_text()

PHRASE = "including announced cuts"

# Same list test_no_surface_claims_direct_comparability holds for the tracker:
# a comparison table is exactly where the overclaim would creep back in.
DIRECT_COMPARABILITY = (
    "compares directly",
    "compare directly",
    "read straight against it",
    "read straight against each other",
    "directly comparable with a national",
    "the same as the national",
    "matches the national",
)


def tier_sentence():
    m = re.search(
        r"function alt_announced_tier_sentence\(\)\s*\{\s*return\s*'([^']+)';",
        DB)
    return m.group(1) if m else None


class TheAnnouncedTierIsStatedWhereTheTotalIs(unittest.TestCase):
    def test_db_defines_the_one_tier_sentence(self):
        s = tier_sentence()
        self.assertIsNotNone(
            s, "db.php does not define alt_announced_tier_sentence(), so each "
               "surface will type its own wording and they will drift")
        self.assertLessEqual(
            len(s.split()), 30,
            "the tier sentence breaks the 30-word ceiling: %r" % s)
        for dash in ("—", "–"):
            self.assertNotIn(dash, s, "the tier sentence carries a dash")
        self.assertTrue(s.endswith("."), "the tier label is not a sentence: %r" % s)

    def test_every_headline_surface_carries_the_phrase_and_the_helper(self):
        for name, src in (("page-tracker.php", TRACKER),
                          ("page-press.php", PRESS),
                          ("page-report.php", REPORT)):
            self.assertIn(
                PHRASE, src.lower(),
                "%s states a headline total with no announced-inclusive "
                "companion; the surface still reads verified-only" % name)
            self.assertIn(
                "alt_announced_tier_sentence(", src,
                "%s types its own tier wording instead of rendering the one "
                "shared sentence" % name)

    def test_the_verified_figure_stays_primary_in_the_hero(self):
        hero = TRACKER[TRACKER.index('<header class="alt-hero">'):]
        hero = hero[: hero.index("</header>")]
        self.assertIn('id="alt-hero-incl"', hero,
                      "the hero has no announced-inclusive companion figure")
        self.assertLess(
            hero.index('id="alt-hero-total"'), hero.index('id="alt-hero-incl"'),
            "the announced-inclusive figure sits above the verified figure; "
            "the verified figure must stay primary")

    def test_renderstats_keeps_the_companion_current(self):
        self.assertIn(
            "setText('alt-hero-incl'", JS,
            "renderStats() never writes alt-hero-incl, so the first filter "
            "change leaves a stale companion beside a fresh headline")
        self.assertIn(
            "alt-hero-incl-wrap", JS,
            "layoffs.js never hides the companion wrapper, so a view with no "
            "announced rows prints the same number twice under two labels")


class TheMonthlyComparisonIsPublicAndDated(unittest.TestCase):
    def section(self):
        i = PRESS.find('id="alt-press-vs-survey"')
        self.assertNotEqual(-1, i, "the press page has no monthly comparison "
                                   "section (id=alt-press-vs-survey)")
        j = PRESS.find("<h2 ", i)
        return PRESS[i: j if j != -1 else len(PRESS)]

    def test_the_press_page_renders_the_table_from_the_shared_constants(self):
        self.assertIn(
            "survey-monthly.json", PRESS,
            "the press page does not read data/survey-monthly.json; the "
            "comparator would be typed into the template and go stale silently")
        sec = self.section()
        for header in ("Ours, effective basis", "Ours, notice basis",
                       "National survey, announcement basis"):
            self.assertIn(
                header, sec,
                "the table does not name the basis on the table: %r missing"
                % header)

    def test_the_receiptless_categories_are_named_on_the_table(self):
        sec = self.section().lower()
        for token in ("federal", "buyout", "estimate"):
            self.assertIn(
                token, sec,
                "the comparison names no receiptless category (%r); without "
                "them the gap reads as a shortfall instead of a lens" % token)

    def test_the_above_100_months_are_explained(self):
        self.assertIn(
            "above 100 percent", self.section(),
            "nothing tells the reader why a month can run above 100 percent; "
            "the July months are the proof the difference is a lens")

    def test_no_direct_comparability_claim_in_the_section(self):
        sec = self.section()
        for phrase in DIRECT_COMPARABILITY:
            self.assertNotIn(phrase, sec, "the comparison section claims "
                                          "direct comparability: %r" % phrase)

    def test_the_constants_are_dated_and_well_formed(self):
        self.assertTrue(DATA.is_file(),
                        "data/survey-monthly.json does not exist")
        j = json.loads(DATA.read_text())
        datetime.strptime(j["read_date"], "%Y-%m-%d")
        months = sorted(j["total"])
        self.assertTrue(months, "the constants hold no months")
        for m in months:
            self.assertRegex(m, r"^\d{4}-\d{2}$")
            v = j["total"][m]
            self.assertTrue(v is None or (isinstance(v, int) and v > 0),
                            "%s holds a non-null non-positive total" % m)

    def test_the_script_reads_the_same_file(self):
        self.assertIn(
            "survey-monthly.json", SCRIPT,
            "monthly_us_comparison.py still carries its own copy of the "
            "comparator; two copies of a hand-entered constant will disagree")

    def test_the_page_and_the_script_share_the_due_window(self):
        m_py = re.search(r"DUE_AFTER_DAYS\s*=\s*(\d+)", SCRIPT)
        self.assertIsNotNone(m_py, "the script has no DUE_AFTER_DAYS")
        m_php = re.search(r"\$alt_mc_due_days\s*=\s*(\d+)", PRESS)
        self.assertIsNotNone(m_php, "the press page has no due window")
        self.assertEqual(
            m_py.group(1), m_php.group(1),
            "the page and the script disagree about when a missing survey "
            "month becomes stale, so one will report stale while the other "
            "reads clean")

    def test_staleness_is_visible_not_silent(self):
        self.assertIn(
            "awaiting", self.section().lower(),
            "the page prints nothing for a released month with no constant; "
            "a silent gap is the stale-percentage defect again")
        self.assertIn(
            "STALE", SCRIPT,
            "the script has no STALE verdict; a missing comparator month "
            "would resolve to a silent pass")


if __name__ == "__main__":
    unittest.main()
