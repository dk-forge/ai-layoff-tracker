"""The TALENT section's Indeed "jobs in" backdrop and its count-meaning honesty,
added 2026-08-26.

WHAT THIS ADDS. The talent section already reports OUR hiring signals. This
pairs them with the whole-market hiring backdrop - Indeed Hiring Lab's US Job
Postings Index and AI-role share - reusing the SAME alt_digest_indeed_block()
the monthly layoff edition uses, because the talent section is about hiring and
Indeed is the market context for hiring.

WHAT THESE TESTS HOLD:

  1. THE BACKDROP RENDERS in the talent section on the daily/weekly cadences,
     shows the index level, the AI share and the month-on-month change exactly
     as the fixture carries them, names the source, the licence and the two "as
     of" dates, and says it is external context not counted in our totals.

  2. THE BACKDROP IS WALLED OFF AS EXTERNAL CONTEXT - a third distinct unit from
     a cut and a hiring signal - and appears exactly ONCE in the section.

  3. THE BACKDROP DEGRADES GRACEFULLY. With no Indeed data the block is omitted
     whole and the rest of the talent section still renders (the iron rule: no
     fabricated figure).

  4. THE MONTHLY EDITION DEFERS THE BACKDROP to the layoff section, which
     carries the identical block on that tier. This is the whole dedup story:
     one home per edition, so a combined monthly email to a dual-list subscriber
     never prints the backdrop twice. The count-meaning honesty stays on every
     cadence, monthly included.

  5. THE COUNT-MEANING HONESTY is stated in words: a hiring-signal count
     includes job-board scans, where a rise means more active postings than our
     previous scan, not confirmed new openings. /talent/v1/aggregate exposes no
     machine-readable split by signal type (include=fresh returns only scalars),
     so this is one honest sentence and never an invented breakdown.

The composers are PHP, so these drive them through
tests/fixtures/digest_compose_harness.php. Without php on PATH the tests SKIP,
which is not a pass.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")


# The Indeed backdrop, in the exact shape tit_indeed_index_data() returns. The
# numbers are the same worked example the monthly-edition test uses, so a
# reader can eyeball the two side by side.
INDEED = {
    "national": {
        "index": 101.79,
        "vs_baseline": 1.79,
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


def talent_fixture(**over):
    """A weekly talent window with the Indeed backdrop present."""
    data = {
        "from": "2026-08-10",
        "to": "2026-08-16",
        "compose": "talent",
        "indeed": INDEED,
        "talent": {"total": 1387, "companies": 1335, "verified": 141},
        "talent_ytd": {"total": 22670, "companies": 9100, "verified": 3400},
        "talent_q": {"rows": [
            {"company": "Vantage Health",
             "headline": "Vantage Health adds 2,200 roles",
             "published_date": "2026-08-12", "headcount": 2200,
             "source_name": "Dallas Business Journal",
             "confidence": "verified", "pillar": "company_development"},
        ]},
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
    out = json.loads(run.stdout)
    if out.get("null"):
        raise AssertionError("the composer returned nothing for this fixture")
    return out


@unittest.skipIf(PHP is None, "php is not on PATH, so the composers could not "
                              "be run. UNKNOWN, not a pass.")
class TheTalentBackdropRenders(unittest.TestCase):
    def setUp(self):
        self.section = compose(talent_fixture())

    def test_the_talent_section_itself_is_present(self):
        # The backdrop is an ADDITION to the talent section, never a
        # replacement: our own signals still lead.
        self.assertIn("Talent Intelligence Tracker", self.section["html"])
        # The unit paragraph, whose NOUN is derived from the window's measured
        # hiring share since 2026-08-29 (alt_digest_talent_signal_noun). This
        # fixture supplies no direction reading, so the mix is UNKNOWN and the
        # neutral noun is the one that is true either way. What this test is
        # about is that the section renders its own figure at all, so it asks
        # for the paragraph rather than for a particular word in it.
        self.assertIn('<p data-alt="unit">new ', self.section["html"])
        self.assertIn(" signals</p>", self.section["html"])

    def test_the_block_heading_is_present_once(self):
        html = self.section["html"]
        self.assertIn("<h3>Jobs in: US hiring demand</h3>", html)
        # Exactly once: the section must never print the backdrop twice.
        self.assertEqual(html.count("Jobs in: US hiring demand"), 1)

    def test_the_index_level_and_change_are_shown(self):
        html = self.section["html"]
        self.assertIn("101.79", html)
        self.assertIn("up 0.34 index points from a month earlier", html)
        self.assertIn("100 = February 1, 2020", html)
        self.assertIn("as of August 14, 2026", html)

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
        # The wall that stops a reader adding a whole-market index level to our
        # signal counts. It is a THIRD distinct unit and the copy says so.
        self.assertIn("not counted in the totals above",
                      self.section["html"])

    def test_the_block_is_in_the_text_part_too(self):
        text = self.section["text"]
        self.assertIn("Jobs in: US hiring demand", text)
        self.assertIn("101.79", text)
        self.assertIn("6.28%", text)


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheBackdropDegradesGracefully(unittest.TestCase):
    def test_no_indeed_data_omits_the_block_whole(self):
        # No `indeed` key: the harness leaves tit_indeed_index_data() undefined,
        # which is the real talent-plugin-absent path. The rest of the talent
        # section still renders.
        fx = talent_fixture()
        fx.pop("indeed", None)
        section = compose(fx)
        self.assertNotIn("Jobs in: US hiring demand", section["html"])
        self.assertIn("Talent Intelligence Tracker", section["html"])

    def test_an_empty_national_block_omits_it(self):
        fx = talent_fixture()
        fx["indeed"] = {"ai": INDEED["ai"]}  # no national index at all
        self.assertNotIn("Jobs in: US hiring demand", compose(fx)["html"])


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheMonthlyEditionDefersTheBackdrop(unittest.TestCase):
    """On the monthly edition the layoff section already carries the identical
    Indeed block, so the talent section must NOT render it - otherwise a
    combined monthly email to a dual-list subscriber would print it twice. This
    is the whole dedup mechanism: one home per edition, no per-recipient pass."""

    def test_a_monthly_talent_section_does_not_carry_the_backdrop(self):
        fx = talent_fixture()
        fx["freq"] = "monthly"
        html = compose(fx)["html"]
        self.assertNotIn("Jobs in: US hiring demand", html)
        # The talent section itself still renders on the monthly edition.
        self.assertIn("Talent Intelligence Tracker", html)

    def test_daily_and_weekly_do_carry_it(self):
        for freq in ("daily", "weekly", ""):
            fx = talent_fixture()
            fx["freq"] = freq
            html = compose(fx)["html"]
            self.assertIn("Jobs in: US hiring demand", html,
                          f"the {freq or 'unspecified'} tier must carry it")


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheCountMeaningHonestyIsStated(unittest.TestCase):
    """A reader must not read a job-board posting-scan delta as confirmed
    hiring. /talent/v1/aggregate exposes no machine-readable split by signal
    type (include=fresh returns only scalars), so this is one honest sentence,
    consistent with the sibling plugin's merged "opened roles" wording, and
    never an invented breakdown."""

    def setUp(self):
        self.section = compose(talent_fixture())

    def test_the_scan_caveat_is_in_the_html(self):
        html = self.section["html"]
        self.assertIn("job-board scans", html)
        self.assertIn("more active postings than our previous scan", html)
        self.assertIn("not that it confirmed new openings", html)

    def test_the_scan_caveat_is_in_the_text_too(self):
        self.assertIn("more active postings than our previous scan",
                      self.section["text"])

    def test_it_is_a_sentence_not_a_fabricated_breakdown(self):
        # The honesty is prose, never a count. Nothing here claims "N of the
        # signals are scans" - that number is not measured and must not be
        # invented. The unit note keeps the original framing intact.
        # The noun the sentence DEFINES is derived (2026-08-29): it has to be
        # the same word the figure above it just wore, or the note defines a
        # term the reader was never shown. The clause after it - the part this
        # test is actually about - is unchanged.
        html = self.section["html"]
        self.assertIn(" signal is one sourced employer update, not one job",
                      html)
        self.assertNotRegex(html, r"\d+ of the [\d,]+ signals are scans")

    def test_the_honesty_survives_the_monthly_defer(self):
        # The backdrop moves to the layoff section on monthly; the count-meaning
        # sentence is about OUR signals and stays on every cadence.
        fx = talent_fixture()
        fx["freq"] = "monthly"
        html = compose(fx)["html"]
        self.assertIn("more active postings than our previous scan", html)


if __name__ == "__main__":
    unittest.main()
