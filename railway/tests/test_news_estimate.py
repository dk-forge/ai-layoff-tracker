"""Percent-only NEWS headlines become a LABELLED estimate (owner ruling 2026-11-13).

The 2026-11-05 ruling covered 8-Ks only. The benchmark misses Trade Desk
("cuts 15% of its global workforce", 2026-09-04) and the like are headlines
that state a share and no count, so the extractor refused them. The owner
ruled on 2026-11-13: extend estimates to news, labelled. The row carries
pct x the employee count from the company's latest 10-K, the formula, the
10-K it came from and the report's own sentence verbatim, stays provisional
and bronze. Nothing here guesses: no percentage in total-workforce context, no
single SEC match for the company, or no 10-K headcount means no estimate and
the item stays refused. Fixtures are synthetic.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import headcount_estimate as he  # noqa: E402
import extractor  # noqa: E402

TITLE = "The Trade Desk cuts 15% of its global workforce as it restructures"
URL = "https://news.google.com/rss/articles/CBMiSYNTHETIC"
TICKERS = {
    "0": {"cik_str": 1671933, "ticker": "TTD", "title": "Trade Desk, Inc."},
    "1": {"cik_str": 1671933, "ticker": "TTDX", "title": "Trade Desk, Inc."},   # 2nd share class
    "2": {"cik_str": 2, "ticker": "ACM", "title": "Acme Corp"},
    "3": {"cik_str": 3, "ticker": "ACMH", "title": "Acme Holdings Inc"},        # ambiguous with 2
    "4": {"cik_str": 4, "ticker": "CPB", "title": "CAMPBELL'S CO"},
}


def tickers_json(url=None):
    return TICKERS


def lookup(cik):
    return ({"employees": 3000, "fiscal_year_end": "2025-12-31", "form": "10-K",
             "accession": "0001671933-26-000010", "basis": "dei:EntityNumberOfEmployees",
             "source_url": "https://www.sec.gov/x"} if str(cik) == "1671933" else None)


class Percent(unittest.TestCase):
    def test_reads_the_headline_shapes(self):
        for text in (TITLE, "Trade Desk Sheds 15% of Staff on Heels of Lackluster Q2",
                     "Trade Desk cuts headcount by 15% as walled gardens close in"):
            self.assertEqual(he.workforce_percent(text, company="The Trade Desk")[0], 15.0, text)

    def test_a_qualified_workforce_is_not_the_total(self):
        """Campbell's: 13% of its SALARIED workforce. Applying 13% to every
        employee would overstate the cut, so no estimate."""
        self.assertIsNone(he.workforce_percent(
            "Campbell's says salaried workforce has been reduced by 13%", company="Campbell's"))
        self.assertIsNone(he.workforce_percent(
            "cut 13% of its salaried workforce", company="Campbell's"))


class CompanyToCik(unittest.TestCase):
    def test_unique_match_through_suffixes_the_and_share_classes(self):
        self.assertEqual(he.cik_for_company("The Trade Desk", fetch_json=tickers_json), "1671933")
        self.assertEqual(he.cik_for_company("Campbell's", fetch_json=tickers_json), "4")

    def test_ambiguous_or_absent_is_none_never_a_guess(self):
        self.assertIsNone(he.cik_for_company("Acme", fetch_json=tickers_json))
        self.assertIsNone(he.cik_for_company("Nonexistent Widgets", fetch_json=tickers_json))
        self.assertIsNone(he.cik_for_company("", fetch_json=tickers_json))

    def test_unreadable_index_is_none(self):
        self.assertIsNone(he.cik_for_company("Trade Desk", fetch_json=lambda u: None))


class Estimate(unittest.TestCase):
    def _est(self, text=TITLE, company="The Trade Desk", source_type="news", **kw):
        return he.estimate_for_filing(
            {"source_type": source_type, "source_url": URL}, text, lookup=lookup,
            company=company, cik_finder=lambda n: he.cik_for_company(n, fetch_json=tickers_json), **kw)

    def test_news_estimate_is_pct_times_employees_and_says_it_is_a_report(self):
        e = self._est()
        self.assertEqual(e["job_count"], 450)
        self.assertEqual(e["origin"], "news")
        self.assertEqual(e["formula"], "15% x 3,000 employees = 450 (rounded)")
        head = he.label_excerpt(e)
        self.assertTrue(head.startswith("Estimate: 15% x 3,000"))
        self.assertIn("Report states:", head)
        self.assertNotIn("Filing states", head)

    def test_other_source_types_never_estimate(self):
        for st in ("warn", "WARN", "", "newsapi_x"):
            self.assertIsNone(self._est(source_type=st), st)

    def test_no_estimate_when_the_company_is_not_in_the_text(self):
        self.assertIsNone(self._est(text="Retailers cut 15% of their workforce this year"))

    def test_no_estimate_without_a_single_sec_match_or_headcount(self):
        self.assertIsNone(self._est(company="Acme"))
        self.assertIsNone(self._est(company="Nonexistent Widgets"))

    def test_8k_path_is_unchanged(self):
        e = he.estimate_for_filing(
            {"source_type": "8K", "company_name": "Fair Isaac Corp",
             "source_url": "https://www.sec.gov/Archives/edgar/data/1671933/0001/x.htm"},
            "the Board approved a plan to reduce its workforce by approximately 15%.",
            lookup=lookup)
        self.assertEqual(e["job_count"], 450)
        self.assertNotEqual(e.get("origin"), "news")


class Finalize(unittest.TestCase):
    def _final(self, job_count=None, text=TITLE, company="The Trade Desk",
               lk=lookup, finder=None):
        orig = (he.default_lookup, he.default_cik_finder)
        he.default_lookup = lk
        he.default_cik_finder = finder or (lambda n: he.cik_for_company(n, fetch_json=tickers_json))
        try:
            return extractor.finalize_extraction(
                {"is_layoff_event": True, "job_count": job_count, "company_name": company,
                 "layoff_date": "2026-09-04", "excerpt": TITLE, "confidence": 80},
                {"source_type": "news", "source_url": URL, "source_name": "Google News",
                 "verification_level": "bronze"}, text)
        finally:
            he.default_lookup, he.default_cik_finder = orig

    def test_percent_only_headline_posts_a_labelled_estimate(self):
        row = self._final()
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 450)
        self.assertTrue(row["job_count_is_estimate"])
        self.assertEqual(row["headcount_estimate"]["label"], "estimate")
        self.assertTrue(row["excerpt"].startswith("Estimate: "))
        self.assertIn("15% of its global workforce", row["excerpt"])
        self.assertLessEqual(row["confidence"], 60)
        self.assertEqual(row["review_status"], "provisional")
        self.assertEqual(row["verification_level"], "bronze")

    def test_a_model_that_returns_the_percent_as_the_count_still_gets_the_estimate(self):
        """Intuit's shape: "17% of its staff" read as 17 jobs. Previously a
        rejection; now the percent becomes a labelled estimate."""
        row = self._final(job_count=15)
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 450)

    def test_without_a_headcount_the_item_is_still_refused(self):
        self.assertIsNone(self._final(lk=lambda cik: None))
        self.assertIsNone(self._final(job_count=15, lk=lambda cik: None))

    def test_without_a_company_match_the_item_is_still_refused(self):
        self.assertIsNone(self._final(finder=lambda n: None))

    def test_a_stated_count_is_never_replaced_by_an_estimate(self):
        text = "The Trade Desk cuts 500 jobs, about 15% of its global workforce"
        row = self._final(job_count=500, text=text)
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 500)
        self.assertFalse(row.get("job_count_is_estimate"))


if __name__ == "__main__":
    unittest.main()
