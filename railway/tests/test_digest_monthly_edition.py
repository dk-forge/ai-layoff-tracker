"""The MONTHLY layoff edition, added 2026-08-25: the marquee "jobs out vs jobs
in" brief.

WHAT THIS TIER IS. Daily and weekly editions already existed. The monthly one
covers the current month MONTH TO DATE and adds one block the others do not: the
Indeed Hiring Lab "jobs in" backdrop, so a reader sees our verified cuts (jobs
out) beside the level of US hiring demand (jobs in). Everything else in the
section is the same composer over a month-to-date window.

WHAT THESE TESTS HOLD:

  1. THE MASTHEAD NAMES THE MONTH, not an ISO week. A 20-odd-day window labelled
     "Week 34" is a false claim about the window in the line above every figure,
     which is the exact class of masthead error the edition is built to avoid.

  2. THE OPENING AND DATELINE CARRY THE "SO FAR" / "MONTH TO DATE" SIGNAL, so a
     running month is never handed to a reader as a finished one.

  3. THE INDEED BACKDROP RENDERS on the monthly edition, shows the index level,
     the AI share and the month-on-month change exactly as the fixture carries
     them, and names the source and licence and the two "as of" dates.

  4. THE BACKDROP IS MONTHLY-ONLY. A weekly edition does not carry it even when
     the same Indeed data is present.

  5. THE BACKDROP DEGRADES GRACEFULLY. With no Indeed data the block is omitted
     whole, never a fabricated figure (the iron rule).

  6. THE ENUM IS COHERENT. valid_freq accepts monthly, the period is a little
     under a month, the last-sent column is its own, and the window is the
     current month from the 1st through the last complete day.

The composers are PHP, so these drive them through
tests/fixtures/digest_compose_harness.php. Without php on PATH the tests SKIP,
which is not a pass.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")

if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_layout as layout            # noqa: E402


def _tuple(label, all_jobs, verified_jobs, ai_verified=0):
    """The /aggregate top_* row shape: [label, all_jobs, ai_jobs, display_label,
    verified_jobs, ai_verified_jobs]."""
    return [label, all_jobs, 0, None, verified_jobs, ai_verified]


# The Indeed backdrop, in the exact shape tit_indeed_index_data() returns (read
# from the sibling plugin's shipped seed on 2026-08-25). The numbers are the
# task's own worked example, so a reader can eyeball the rendered brief.
INDEED = {
    "national": {
        "index": 101.79,
        "vs_baseline": 1.79,
        # The baseline NOTE the payload itself carries (build_indeed_index.py
        # writes it), so a rebased series renames its own baseline. The
        # composer renders THIS, with a typed fallback only for a pre-2026-08
        # seed that lacks the field.
        "baseline": "February 1, 2020 = 100",
        "as_of": "2026-08-14",
        "month_ago": {"date": "2026-07-15", "delta": 0.34, "index": 101.45},
        "source_name": "Indeed Hiring Lab",
        "source_url": "https://github.com/hiring-lab/job_postings_tracker",
    },
    "ai": {
        "share_pct": 6.28,
        "as_of": "2026-07-31",
        "month_ago": {"date": "2026-07-01", "delta": 0.33, "share_pct": 5.95},
        "source_url": "https://github.com/hiring-lab/job_postings_tracker",
    },
    "rule": "US job postings context from Indeed Hiring Lab.",
}


def monthly_fixture(**over):
    """A month-to-date window (August 1 through the 24th) at the monthly tier,
    with the Indeed backdrop present."""
    data = {
        "from": "2026-08-01",
        "to": "2026-08-24",
        "freq": "monthly",
        "compose": "layoff",
        "indeed": INDEED,
        "layoff": {
            "totals": {
                "jobs": 84210, "entries": 421,
                "announced_jobs": 12000, "announced_entries": 20,
                "ai_verified_jobs": 1500, "ai_verified_entries": 8,
                "companies": 388,
            },
            "leaders": [
                {"company_name": "Applied Aerospace", "job_count": 4320,
                 "layoff_date": "2026-08-12", "ai_explicit": False,
                 "location": "", "state": "", "country": "",
                 "permalink": "https://asktherecruiter.com/blog/layoff/applied/",
                 "announced": False,
                 "source_url": "https://www.sec.gov/filing/applied"},
            ],
            "top_countries": [
                _tuple("United States", 50000, 42000, 1500),
                _tuple("Brazil", 3000, 2500),
            ],
            "top_industries": [
                _tuple("Aerospace & Defense", 8000, 7200),
                _tuple("Retail & E-commerce", 6000, 5400),
            ],
            "source_types": [
                _tuple("warn", 30000, 28000),
                _tuple("8K", 20000, 19000),
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


def compose(fixture):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(fixture, handle)
        path = handle.name
    try:
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, path],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    if run.returncode != 0:
        raise AssertionError(f"the harness failed: {run.stderr[:2000]}")
    return json.loads(run.stdout)


@unittest.skipIf(PHP is None, "php is not on PATH, so the composers could not "
                              "be run. UNKNOWN, not a pass.")
class TheMonthlyMastheadNamesTheMonth(unittest.TestCase):
    def setUp(self):
        self.section = compose(monthly_fixture())

    def test_the_dateline_names_the_month_not_a_week(self):
        html = self.section["html"]
        m = re.search(r'<p data-alt="dateline">(.*?)</p>', html, re.S)
        self.assertTrue(m, "no dateline rendered")
        dateline = m.group(1)
        self.assertIn("August 2026", dateline)
        self.assertNotIn("Week", dateline,
                         "a month-to-date edition must not be labelled a week")

    def test_the_dateline_says_month_to_date(self):
        self.assertIn("month to date", self.section["html"])

    def test_the_lead_opens_on_the_month_so_far(self):
        m = re.search(r'<p data-alt="lead">(.*?)</p>', self.section["html"], re.S)
        self.assertTrue(m, "no lead rendered")
        self.assertIn("So far in August 2026", m.group(1))
        self.assertNotIn("In Week", m.group(1))


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheIndeedBackdropRenders(unittest.TestCase):
    def setUp(self):
        self.section = compose(monthly_fixture())

    def test_the_block_heading_is_present(self):
        self.assertIn("<h3>Jobs in: US hiring demand</h3>", self.section["html"])

    def test_the_index_level_and_change_are_shown(self):
        html = self.section["html"]
        self.assertIn("101.79", html)
        self.assertIn("up 0.34 index points from a month earlier", html)
        # The baseline note comes FROM THE DATA (national.baseline), not from a
        # typed literal that would silently lie if Hiring Lab rebased.
        self.assertIn("(February 1, 2020 = 100)", html)
        self.assertIn("as of August 14, 2026", html)

    def test_the_vs_baseline_figure_is_rendered_not_dead(self):
        # vs_baseline used to be fetched and never shown; now the reader sees
        # the change against the baseline the parenthetical just explained.
        self.assertIn("1.79 points above the baseline", self.section["html"])

    def test_the_ai_share_and_change_are_shown(self):
        html = self.section["html"]
        self.assertIn("6.28% of US postings", html)
        self.assertIn("up 0.33 points from a month earlier", html)
        self.assertIn("as of July 31, 2026", html)

    def test_the_source_and_licence_are_named(self):
        html = self.section["html"]
        self.assertIn("Indeed Hiring Lab", html)
        self.assertIn("CC BY 4.0", html)

    def test_the_block_says_it_is_external_and_uncounted(self):
        self.assertIn("not counted in the totals above",
                      self.section["html"])

    def test_the_block_is_in_the_text_part_too(self):
        text = self.section["text"]
        self.assertIn("Jobs in: US hiring demand", text)
        self.assertIn("101.79", text)
        self.assertIn("6.28%", text)


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheBackdropIsMonthlyOnly(unittest.TestCase):
    def test_a_weekly_edition_does_not_carry_it(self):
        # Same Indeed data present, but a weekly window and tier: the block must
        # not appear. The window is a complete seven days so the rest of the
        # weekly composer is happy.
        fx = monthly_fixture()
        fx["freq"] = "weekly"
        fx["from"] = "2026-08-10"
        fx["to"] = "2026-08-16"
        html = compose(fx)["html"]
        self.assertNotIn("Jobs in: US hiring demand", html)

    def test_an_unspecified_tier_does_not_carry_it(self):
        fx = monthly_fixture()
        fx.pop("freq", None)
        html = compose(fx)["html"]
        self.assertNotIn("Jobs in: US hiring demand", html)


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheBackdropDegradesGracefully(unittest.TestCase):
    def test_no_indeed_data_omits_the_block_whole(self):
        # No `indeed` key: the harness leaves tit_indeed_index_data() undefined,
        # which is the real talent-plugin-absent path. The rest of the monthly
        # edition still renders.
        fx = monthly_fixture()
        fx.pop("indeed", None)
        section = compose(fx)
        self.assertNotIn("Jobs in: US hiring demand", section["html"])
        self.assertIn("August 2026", section["html"])  # the edition still sends

    def test_an_empty_national_block_omits_it(self):
        fx = monthly_fixture()
        fx["indeed"] = {"ai": INDEED["ai"]}  # no national index at all
        self.assertNotIn("Jobs in: US hiring demand", compose(fx)["html"])

    def test_a_missing_ai_series_drops_only_the_ai_sentence(self):
        fx = monthly_fixture()
        fx["indeed"] = {"national": INDEED["national"]}  # no ai block
        html = compose(fx)["html"]
        self.assertIn("<h3>Jobs in: US hiring demand</h3>", html)
        self.assertIn("101.79", html)
        self.assertNotIn("of US postings", html)

    def test_a_seed_without_a_baseline_note_gets_the_documented_fallback(self):
        # A pre-2026-08 talent seed carries no national.baseline; the typed
        # literal is the FALLBACK for exactly that shape, never the first
        # choice. This is the accepted staleness risk, stated in the source.
        fx = monthly_fixture()
        national = dict(INDEED["national"])
        national.pop("baseline")
        fx["indeed"] = {"national": national, "ai": INDEED["ai"]}
        html = compose(fx)["html"]
        self.assertIn("(100 = February 1, 2020)", html)

    def test_the_baseline_note_is_not_gated_on_vs_baseline(self):
        # The old expression keyed the parenthetical on $vs_baseline - a
        # property of a DIFFERENT number - so an index without it printed an
        # unexplained level. The note must ride with the index itself.
        fx = monthly_fixture()
        national = dict(INDEED["national"])
        national.pop("baseline")
        national.pop("vs_baseline")
        fx["indeed"] = {"national": national, "ai": INDEED["ai"]}
        html = compose(fx)["html"]
        self.assertIn("(100 = February 1, 2020)", html)
        # And no invented delta clause: absence of the figure is absence.
        self.assertNotIn("points above the baseline", html)
        self.assertNotIn("points below the baseline", html)
        self.assertNotIn("level with the baseline", html)

    def test_a_below_baseline_reading_says_below(self):
        fx = monthly_fixture()
        national = dict(INDEED["national"])
        national["index"] = 97.4
        national["vs_baseline"] = -2.6
        fx["indeed"] = {"national": national, "ai": INDEED["ai"]}
        self.assertIn("2.60 points below the baseline", compose(fx)["html"])


# The subject-side helpers, lifted by name exactly as
# test_digest_subject_agreement.py lifts them, so a rename fails loudly
# rather than testing a stale copy.
_SUBJECT_FNS = ("alt_digest_date_range", "alt_digest_short_range",
                "alt_digest_valid_freq", "alt_digest_subject_period",
                "alt_digest_iso_week", "alt_digest_week_id",
                "alt_digest_edition_label", "alt_digest_month_edition_label",
                "alt_digest_period_phrase", "alt_digest_fallback_subject")

_SUBJECT_RUNNER = r"""
$src = file_get_contents($argv[1]);
foreach (explode(',', $argv[2]) as $name) {
    if (!preg_match('/\nfunction ' . preg_quote($name, '/') . '\s*\(.*?\n\}/s',
                    $src, $m)) {
        fwrite(STDERR, "could not extract $name from subscribe.php\n");
        exit(2);
    }
    eval($m[0]);
}
$in = json_decode($argv[3], true);
echo json_encode(array(
    'period'   => alt_digest_subject_period('monthly', $in['from'], $in['to']),
    'phrase'   => alt_digest_period_phrase($in['from'], $in['to'], 'monthly'),
    'fallback' => alt_digest_fallback_subject('monthly', $in['to']),
));
"""


def php_monthly_subject(frm, to):
    handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                         encoding="utf-8")
    try:
        handle.write("<?php\n" + _SUBJECT_RUNNER)
        handle.close()
        run = subprocess.run([PHP, handle.name, SUBSCRIBE,
                              ",".join(_SUBJECT_FNS),
                              json.dumps({"from": frm, "to": to})],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"php runner failed: {run.stderr[:1200]}")
    return json.loads(run.stdout)


class TheMonthlySubjectNamesTheWindow(unittest.TestCase):
    """The 2026-08-28 nine-edition review's FIX 1: the monthly SUBJECT named a
    single day ("Aug 26") for a month-to-date window (Aug 1-26). A monthly is
    a window tier like the weekly - the figures are a month-to-date sum, and
    one date on them is a false claim in the line most people only ever see.
    Both senders are pinned to the same strings here (the PHP wp_mail side by
    extraction, the Python relay side directly), and
    test_digest_subject_agreement.py drives the full subject-line port over
    monthly cases besides."""

    WINDOW = ("2026-08-01", "2026-08-24")
    PERIOD = "Aug 1-24"
    PHRASE = "August 2026 · August 1-24"
    FALLBACK = ("[AskTheRecruiter] Monthly tracker digest, "
                "August 2026 · August 1-24")

    def _payload(self):
        return {"from": self.WINDOW[0], "to": self.WINDOW[1],
                "freq": "monthly"}

    @unittest.skipIf(PHP is None, "php is not on PATH.")
    def test_the_php_subject_period_names_the_window(self):
        out = php_monthly_subject(*self.WINDOW)
        self.assertEqual(out["period"], self.PERIOD)

    @unittest.skipIf(PHP is None, "php is not on PATH.")
    def test_the_php_period_phrase_is_the_masthead_label(self):
        out = php_monthly_subject(*self.WINDOW)
        self.assertEqual(out["phrase"], self.PHRASE)

    @unittest.skipIf(PHP is None, "php is not on PATH.")
    def test_the_php_fallback_subject_names_the_window_too(self):
        # A fallback is still a subject somebody receives, and the monthly
        # window is derivable from $to alone (it always starts on the 1st).
        out = php_monthly_subject(*self.WINDOW)
        self.assertEqual(out["fallback"], self.FALLBACK)

    def test_the_python_subject_period_names_the_window(self):
        self.assertEqual(layout.subject_period(self._payload()), self.PERIOD)

    def test_the_python_period_phrase_is_the_masthead_label(self):
        self.assertEqual(layout.period_phrase(self._payload()), self.PHRASE)

    def test_the_python_month_label_matches_the_masthead_convention(self):
        # The same string alt_digest_month_edition_label produces: month named,
        # dates beside it, no year said twice.
        self.assertEqual(
            layout.month_edition_label(datetime.date(2026, 8, 1),
                                       datetime.date(2026, 8, 24)),
            self.PHRASE)

    def test_a_first_of_month_window_is_one_day_on_both_sides(self):
        # alt_digest_monthly_window on the 1st clamps to a one-day window; the
        # subject token for it is that day, not an inverted range.
        payload = {"from": "2026-09-01", "to": "2026-09-01", "freq": "monthly"}
        self.assertEqual(layout.subject_period(payload), "Sep 1")
        if PHP is not None:
            out = php_monthly_subject("2026-09-01", "2026-09-01")
            self.assertEqual(out["period"], "Sep 1")


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheMonthlyEnumIsCoherent(unittest.TestCase):
    def probe(self, now):
        return compose({"probe": True, "now": now,
                        "from": "2026-08-01", "to": "2026-08-24"})

    def test_valid_freq_accepts_monthly_and_rejects_junk(self):
        v = self.probe("2026-08-15")["valid"]
        self.assertEqual(v["monthly"], "monthly")
        self.assertEqual(v["bogus"], "weekly")  # unknown coerces to weekly

    def test_the_period_is_a_little_under_a_month(self):
        p = self.probe("2026-08-15")["period"]
        day = 86400
        self.assertEqual(p["monthly"], 25 * day)
        self.assertGreater(p["monthly"], p["weekly"])

    def test_the_last_sent_column_is_its_own(self):
        c = self.probe("2026-08-15")["column"]
        self.assertEqual(c["monthly"], "last_sent_monthly")
        self.assertNotEqual(c["monthly"], c["weekly"])
        self.assertNotEqual(c["monthly"], c["daily"])

    def test_the_window_is_the_month_through_the_last_complete_day(self):
        # On the 15th, the window is the 1st through the 14th (yesterday).
        w = self.probe("2026-08-15")
        self.assertEqual(w["window_monthly"], ["2026-08-01", "2026-08-14"])
        # The dispatcher agrees with the tier-specific function.
        self.assertEqual(w["window_dispatch"], w["window_monthly"])

    def test_the_first_of_month_window_does_not_invert(self):
        # On the 1st, yesterday is in the previous month; the clamp keeps `to`
        # at `from` rather than producing an inverted or empty range.
        w = self.probe("2026-09-01")["window_monthly"]
        self.assertEqual(w, ["2026-09-01", "2026-09-01"])


if __name__ == "__main__":
    unittest.main()
