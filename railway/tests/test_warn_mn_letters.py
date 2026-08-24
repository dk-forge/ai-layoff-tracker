"""The Minnesota per-company WARN LETTER collector.

Proves the four things that make it safe to run in the twice-daily pipeline:
  1. discovery matches per-company letters and NOT the monthly report PDFs
     (those are fetch_mn's job and would double-count),
  2. it never writes a row itself — it only builds raw dicts with raw_text set,
     which the standard gate -> extract -> post path then processes,
  3. only letters dated AFTER the newest monthly report are emitted, so a letter
     and its monthly-report twin cannot both be counted,
  4. the notice date is read from the letter (first date by position), in both
     the 'Month DD, YYYY' and numeric 'M/D/YYYY' shapes.
"""
import os
import sys
import unittest
from datetime import date

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

from sources import warn_mn_letters as MNL  # noqa: E402


class DiscoveryMatchesLettersNotMonthlyReports(unittest.TestCase):
    def test_the_letter_regex_accepts_both_id_shapes(self):
        for url in (
            "https://mn.gov/deed/assets/warn-2026-pearsons-candy-company_tcm1045-762217.pdf",
            "https://mn.gov/deed/assets/2026-warn-wabash-national-services-lp_tcm1045-718209.pdf",
        ):
            self.assertRegex(url, MNL._LETTER_RX)

    def test_the_letter_regex_rejects_the_monthly_report_pdfs(self):
        # These belong to fetch_mn's table path; matching them here would ingest
        # the same notices twice, once as a letter and once as a table row.
        for url in (
            "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-2026-june_tcm1045-758364.pdf",
            "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-report-2023_tcm1045-663809.pdf",
        ):
            self.assertNotRegex(url, MNL._LETTER_RX)


class TheNoticeDateIsReadFromTheLetter(unittest.TestCase):
    def test_month_name_form(self):
        self.assertEqual(MNL._letter_date("July 30, 2026\nDear Commissioner"),
                         date(2026, 7, 30))

    def test_zero_padded_day(self):
        self.assertEqual(MNL._letter_date("August 03, 2026 Mayor Frey"),
                         date(2026, 8, 3))

    def test_numeric_form(self):
        self.assertEqual(MNL._letter_date("4/22/2026 CareerForce Marshall MN"),
                         date(2026, 4, 22))

    def test_first_date_by_position_wins_not_the_earliest_value(self):
        # A fresh letter that cites an older date lower down must keep its own
        # (leading) notice date, or it would be wrongly dropped below the cutoff.
        txt = "August 5, 2026\nAs we told you on January 2, 2026, we will close."
        self.assertEqual(MNL._letter_date(txt), date(2026, 8, 5))

    def test_no_date_returns_none(self):
        self.assertIsNone(MNL._letter_date("No date anywhere in this text."))


class OnlyLettersPastTheMonthlyCutoffAreEmitted(unittest.TestCase):
    def setUp(self):
        # Pin the cutoff deterministically instead of depending on the live seed.
        os.environ["MN_LETTER_MIN_DATE"] = "2026-07-01"
        self.addCleanup(os.environ.pop, "MN_LETTER_MIN_DATE", None)
        self._old_discover = MNL.discover_letter_urls
        self._old_pdf = MNL._pdf_text
        self._texts = {
            "https://mn.gov/deed/assets/warn-2026-fresh_tcm1045-900001.pdf":
                "August 5, 2026\nRe: Fresh Co WARN Notice. 40 employees affected.",
            "https://mn.gov/deed/assets/warn-2026-stale_tcm1045-700001.pdf":
                "March 3, 2026\nRe: Stale Co WARN Notice. 12 employees affected.",
            "https://mn.gov/deed/assets/warn-2026-undated_tcm1045-900002.pdf":
                "Re: Undated Co WARN Notice with no header date. 7 employees.",
        }
        MNL.discover_letter_urls = lambda: sorted(self._texts)
        MNL._pdf_text = lambda url: self._texts[url]

    def tearDown(self):
        MNL.discover_letter_urls = self._old_discover
        MNL._pdf_text = self._old_pdf

    def test_stale_letter_is_dropped_fresh_and_undated_are_kept(self):
        rows = MNL.pull_mn_warn_letters(_report=False)
        urls = {r["source_url"] for r in rows}
        self.assertIn("https://mn.gov/deed/assets/warn-2026-fresh_tcm1045-900001.pdf", urls)
        self.assertIn("https://mn.gov/deed/assets/warn-2026-undated_tcm1045-900002.pdf", urls)
        self.assertNotIn("https://mn.gov/deed/assets/warn-2026-stale_tcm1045-700001.pdf", urls)

    def test_every_row_carries_raw_text_and_the_collector_tag(self):
        # cpt.php alt_allowed_source_types(): a type outside this set is silently
        # coerced to 'news' on /add, so the collector must send an allowlisted
        # one or the WARN provenance is lost.
        allowed = {"8K", "warn", "press_release", "news", "erm", "federal_rif"}
        for r in MNL.pull_mn_warn_letters(_report=False):
            self.assertTrue(r["raw_text"].strip())
            self.assertEqual(r["_collector"], "mn_warn_letters")
            self.assertIn(r["source_type"], allowed)
            self.assertEqual(r["state"], "MN")


class TheCollectorNeverWritesARowItself(unittest.TestCase):
    def test_module_does_not_reach_the_posting_pipeline(self):
        # By CONSTRUCTION, not by prose: it must not import the poster, must not
        # POST anywhere, and must not name a write endpoint in a call. (The
        # docstring is free to explain the pipeline it feeds.)
        with open(MNL.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for forbidden in ("import wp_poster", "from wp_poster",
                          "post_to_wordpress(", "requests.post",
                          "wp-json/layoffs"):
            self.assertNotIn(forbidden, src,
                             f"letters collector must not post directly ({forbidden})")


if __name__ == "__main__":
    unittest.main()
