"""Percent-only 8-Ks become a LABELLED estimate (owner ruling 2026-11-05).

Most Item 2.05 8-Ks state only a share of the workforce (FICO ~15%, HubSpot
~7%), and the extractor refuses a percentage as a count by design. The owner
ruled "yes estimates": show pct x the employee count the company reported in
its latest 10-K, labelled "estimate" with the formula and the source, and keep
the filing's own reported figure (the percentage) beside it.
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

FICO_TEXT = ("Item 2.05 Costs Associated with Exit or Disposal Activities. On "
             "October 20, 2026, the Board approved a restructuring plan that "
             "will reduce the Company's global workforce by approximately 15%.")
URL = "https://www.sec.gov/Archives/edgar/data/814547/000081454726000050/x8k.htm"


def lookup(cik):
    assert cik == "814547"
    return {"employees": 3586, "fiscal_year_end": "2025-09-30",
            "form": "10-K", "accession": "0000814547-25-000040",
            "source_url": "https://www.sec.gov/Archives/edgar/data/814547/x10k.htm",
            "basis": "dei:EntityNumberOfEmployees"}


class Percent(unittest.TestCase):
    def test_reads_workforce_percent_shapes(self):
        cases = {
            FICO_TEXT: 15.0,
            "a reduction of approximately 7% of the Company's workforce": 7.0,
            "eliminating about 12 percent of its employees": 12.0,
            "will affect roughly 4.5% of our global headcount": 4.5,
        }
        for text, pct in cases.items():
            self.assertEqual(he.workforce_percent(text)[0], pct, text)

    def test_ignores_percentages_that_are_not_workforce(self):
        for text in ("revenue fell 15% year over year",
                     "a charge of approximately 15% of annual operating expense",
                     "the stock rose 7%"):
            self.assertIsNone(he.workforce_percent(text), text)

    def test_reads_the_filers_own_possessive(self):
        """Workday 8-K 0001327811-26-000048 (2026-09-29): "a reduction of
        approximately 2.5% of Workday's current workforce" was refused because
        the owner word was only its/our/the company's."""
        text = ("These actions include a reduction of approximately 2.5% of "
                "Workday\u2019s current workforce, primarily within Product.")
        self.assertEqual(he.workforce_percent(text, company="Workday, Inc.")[0], 2.5)
        self.assertEqual(he.workforce_percent(text.replace("\u2019", "'"),
                                              company="WORKDAY INC")[0], 2.5)

    def test_another_companys_possessive_is_not_the_filers_workforce(self):
        text = "a reduction of approximately 10% of Acme's workforce"
        self.assertIsNone(he.workforce_percent(text, company="Workday, Inc."))
        self.assertIsNone(he.workforce_percent(text))
        self.assertIsNone(he.workforce_percent(
            "about 20% of the industry's workforce", company="Workday, Inc."))

    def test_fico_positions_sentence(self):
        """FICO 8-K 0001193125-26-415732 (2026-10-06)."""
        text = ("This plan involves the elimination of approximately 15% of "
                "positions across the Company.")
        self.assertEqual(he.workforce_percent(text, company="FAIR ISAAC CORP")[0], 15.0)

    def test_cik_from_archive_url(self):
        self.assertEqual(he.cik_from_url(URL), "814547")
        self.assertIsNone(he.cik_from_url("https://example.com/x"))


class Estimate(unittest.TestCase):
    def test_estimate_is_pct_times_employees_with_label_formula_source(self):
        est = he.estimate_for_filing({"source_type": "8K", "source_url": URL},
                                     FICO_TEXT, lookup=lookup)
        self.assertEqual(est["job_count"], 538)          # round(0.15 * 3586)
        self.assertEqual(est["label"], "estimate")
        self.assertEqual(est["reported_percent"], 15.0)
        self.assertEqual(est["employees"], 3586)
        self.assertIn("15% x 3,586", est["formula"])
        self.assertIn("10-K", est["source"])
        self.assertIn("approximately 15%", est["reported_text"])

    def test_no_estimate_without_employee_count_or_for_news(self):
        self.assertIsNone(he.estimate_for_filing(
            {"source_type": "8K", "source_url": URL}, FICO_TEXT, lookup=lambda c: None))
        self.assertIsNone(he.estimate_for_filing(
            {"source_type": "news", "source_url": URL}, FICO_TEXT, lookup=lookup))

    def test_risk_factor_section_is_never_estimated(self):
        self.assertIsNone(he.estimate_for_filing(
            {"source_type": "8K", "source_url": URL,
             "sec_section": extractor.RISK_FACTORS_SECTION}, FICO_TEXT, lookup=lookup))

    def test_employees_from_companyfacts_picks_latest_10k(self):
        facts = {"facts": {"dei": {"EntityNumberOfEmployees": {"units": {"pure": [
            {"val": 3400, "form": "10-K", "fy": 2024, "end": "2024-09-30",
             "filed": "2024-11-08", "accn": "a1"},
            {"val": 3586, "form": "10-K", "fy": 2025, "end": "2025-09-30",
             "filed": "2025-11-07", "accn": "a2"},
            {"val": 9999, "form": "10-Q", "fy": 2026, "end": "2026-03-31",
             "filed": "2026-04-30", "accn": "a3"}]}}}}}
        got = he.employees_from_companyfacts(facts)
        self.assertEqual(got["employees"], 3586)
        self.assertEqual(got["accession"], "a2")

    def test_employees_from_10k_text(self):
        text = ("Human Capital. As of September 30, 2025, we had approximately "
                "3,586 full-time employees, of whom 1,200 were outside the U.S.")
        self.assertEqual(he.employees_from_10k_text(text), 3586)
        self.assertIsNone(he.employees_from_10k_text("no headcount here"))

    def test_employees_from_10k_text_reads_persons(self):
        """FICO's 10-K (fiscal 2026): "we employed 3,747 persons across 31
        countries". `persons` was not in the noun list, so the sentence that
        carries the count never matched."""
        text = ("HUMAN CAPITAL RESOURCES Our People As of September 30, 2026, "
                "we employed 3,747 persons across 31 countries.")
        self.assertEqual(he.employees_from_10k_text(text), 3747)

    def test_10k_text_fallback_reads_past_the_8k_window(self):
        """sec_lookup fell back to the 8-K window fetcher, which returns ~3,000
        characters around the first layoff keyword, so a filer with no
        dei:EntityNumberOfEmployees tag (FICO) could never be read. The text
        fetcher must hand back the whole stripped document: the sentence sits
        hundreds of thousands of characters in."""
        body = ("x " * 150_000) + "As of September 30, 2026, we employed 3,747 persons."
        calls = []

        def fetch_json(url):
            calls.append(url)
            if "submissions" in url:
                return {"filings": {"recent": {
                    "form": ["10-K"], "accessionNumber": ["0000814547-26-000042"],
                    "primaryDocument": ["fico.htm"], "reportDate": ["2026-09-30"]}}}
            return None  # companyfacts: no dei tag

        he._CACHE.clear()
        got = he.sec_lookup("0000814547", fetch_json=fetch_json,
                            fetch_text=lambda url: body)
        he._CACHE.clear()
        self.assertEqual(got["employees"], 3747)

    def test_default_text_fetcher_is_not_the_8k_window(self):
        from sources import edgar
        seen = {}
        orig_get, orig_win = edgar._get, edgar._fetch_filing_text
        edgar._get = lambda url: SimpleNamespace(
            status_code=200, raise_for_status=lambda: None,
            text="<p>" + ("y " * 5000) + "we employed 3,747 persons</p>")
        edgar._fetch_filing_text = lambda url: seen.setdefault("window", "short")
        try:
            text = he._fetch_text("https://www.sec.gov/Archives/edgar/data/1/2/x.htm")
        finally:
            edgar._get, edgar._fetch_filing_text = orig_get, orig_win
        self.assertNotIn("window", seen)
        self.assertIn("3,747 persons", text)


class FinalizeExtraction(unittest.TestCase):
    def _final(self, monkey_lookup):
        orig = he.default_lookup
        he.default_lookup = monkey_lookup
        try:
            return extractor.finalize_extraction(
                {"is_layoff_event": True, "job_count": None,
                 "company_name": "Fair Isaac Corp", "layoff_date": "2026-10-20",
                 "excerpt": None, "confidence": 80},
                {"source_type": "8K", "source_url": URL, "source_name": "SEC 8-K",
                 "verification_level": "gold", "filing_date": "2026-10-21"},
                FICO_TEXT)
        finally:
            he.default_lookup = orig

    def test_percent_only_8k_posts_a_labelled_estimate(self):
        row = self._final(lookup)
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 538)
        self.assertTrue(row["job_count_is_estimate"])
        self.assertEqual(row["headcount_estimate"]["label"], "estimate")
        self.assertTrue(row["excerpt"].startswith("Estimate: "))
        self.assertIn("approximately 15%", row["excerpt"])
        self.assertLessEqual(row["confidence"], 60)

    def test_percent_only_8k_without_10k_count_is_still_refused(self):
        self.assertIsNone(self._final(lambda cik: None))



class Poster(unittest.TestCase):
    def test_estimate_title_and_meta_are_labelled(self):
        import os
        from unittest.mock import patch
        import wp_poster
        sent = {}

        def post(url, json=None, headers=None, timeout=None):
            sent.update(json)

            class R:
                status_code = 201
                text = "{}"

                def json(self):
                    return {}
            return R()
        with patch.dict(os.environ, {"WP_SITE_URL": "https://x", "WP_API_KEY": "k"}), \
                patch.object(wp_poster.requests, "post", post):
            wp_poster.post_to_wordpress({"company_name": "FICO", "job_count": 538,
                                         "layoff_date": "2026-10-20",
                                         "job_count_is_estimate": True,
                                         "headcount_estimate": {"label": "estimate"}})
        self.assertIn("(estimate)", sent["title"])
        self.assertTrue(sent["meta"]["job_count_is_estimate"])
        self.assertEqual(sent["meta"]["headcount_estimate"]["label"], "estimate")


if __name__ == "__main__":
    unittest.main()
