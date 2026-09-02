"""The blank-country census sorts rows by cause and never places by outlet.

The rows below are the live 2026-09-02 blank rows, verbatim in the fields the
census reads. The pin that matters is negative: a news row whose excerpt names
one country because the OUTLET is from there (Times of Suriname on an Amazon
cut) is `suggestive`, counted, and never in the deterministic bucket, on any
host and with any ccTLD. `legacy_row_repair._infer_country` is imported, so
the deterministic bucket is the same judgement that tool applies.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import blank_country_census as census  # noqa: E402


def row(row_id, company, source_type, url, excerpt="", employer_country="", state=""):
    return {"id": row_id, "company_name": company, "source_type": source_type,
            "source_url": url, "excerpt": excerpt,
            "employer_country": employer_country, "state": state}


LIVE = [
    row(176688, "Amazon", "news", "https://news.google.com/rss/articles/CBMi...",
        "Amazon confirms 16,000 job cuts after accidental email - Times of Suriname.",
        employer_country="United States"),
    row(178694, "African Tech", "news", "https://news.google.com/rss/articles/CBMj...",
        "African Tech sees 2,421 layoffs in 2025 profit push - Business News Nigeria."),
    row(70805, "WB Games Montreal", "news", "https://www.digitaltrends.com/gaming/wb-games-montreal-layoffs/",
        "According to Radio-Canada, WB Games Montreal laid off 99 people just this morning."),
    row(178900, "DEUTSCHE BANK AKTIENGESELLSCHAFT", "8K",
        "https://www.sec.gov/Archives/edgar/data/1159508/000115950825000005/db20250130991.htm",
        "Deutsche Bank to cut around 2,000 jobs in Germany in 2025."),
    row(177335, "Kurum", "news", "https://news.google.com/rss/articles/CBMk...",
        '"Kurum" lays off 250 employees, dismissal after the agreement with unions Euronews Albania'),
]

#: Not live: the one shape the deterministic bucket exists for. No blank WARN
#: row was on the site on 2026-09-02, which is the point of counting.
WARN = row(1, "Acme Plant", "warn", "https://www.dllr.state.md.us/employment/warn.shtml", state="MD")


def named(excerpt):
    """Stand-in for the extractor's reader (which needs the openai package)."""
    table = {"Suriname": "Suriname", "Nigeria": "Nigeria", "Albania": "Albania",
             "Germany": "Germany", "Canada": "Canada"}
    return {v for k, v in table.items() if k in (excerpt or "")}


class Classification(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(census, "_countries_named", side_effect=named)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_live_news_row_is_deterministic(self):
        for r in LIVE:
            self.assertNotEqual(census.classify(r)["cause"], "deterministic", r["company_name"])

    def test_the_outlets_country_is_suggestive_and_left_blank(self):
        amazon = census.classify(LIVE[0])
        self.assertTrue(amazon["suggestive"])
        self.assertIsNone(amazon["deterministic_country"])
        self.assertEqual(amazon["cause"], "news_unreadable")
        self.assertTrue(amazon["findable"])            # employer_country is filled

    def test_a_google_redirect_is_unreadable_and_a_publisher_url_is_readable(self):
        self.assertEqual(census.classify(LIVE[1])["cause"], "news_unreadable")
        self.assertEqual(census.classify(LIVE[2])["cause"], "news_readable")

    def test_a_filing_is_never_placed_from_its_venue_or_its_excerpt(self):
        db = census.classify(LIVE[3])
        self.assertEqual(db["cause"], "filing")
        self.assertIsNone(db["deterministic_country"])
        self.assertTrue(db["suggestive"])              # "Germany" is named, and not written

    def test_a_us_state_code_is_the_deterministic_signal(self):
        warn = census.classify(WARN)
        self.assertEqual(warn["cause"], "deterministic")
        self.assertEqual(warn["deterministic_country"], "United States")

    def test_a_government_host_places_only_a_warn_row(self):
        # The same gate legacy_row_repair carries: sec.gov ends in .gov.
        fake = dict(WARN, state="", source_type="8K",
                    source_url="https://www.sec.gov/Archives/edgar/data/1/x.htm")
        self.assertEqual(census.classify(fake)["cause"], "filing")
        warn_no_state = dict(WARN, state="")
        self.assertEqual(census.classify(warn_no_state)["cause"], "deterministic")

    def test_the_census_sums_to_the_rows_and_names_only_deterministic_ids(self):
        c = census.census(LIVE + [WARN])
        self.assertEqual(c["rows"], 6)
        self.assertEqual(sum(c["by_cause"].values()), 6)
        self.assertEqual(c["by_cause"], {"deterministic": 1, "filing": 1,
                                         "news_readable": 1, "news_unreadable": 3})
        self.assertEqual(c["findable"], 1)
        self.assertEqual(c["invisible"], 5)
        self.assertEqual(c["suggestive"], 5)              # Radio-Canada names Canada too
        self.assertEqual(c["deterministic_ids"], [(1, "United States")])

    def test_the_report_has_no_em_dash_and_says_what_it_refuses(self):
        text = census.report(census.census(LIVE + [WARN]))
        self.assertNotIn("—", text)
        self.assertIn("refused as a placement", text)
        self.assertIn("id=1 -> United States", text)


class UnknownIsNotZero(unittest.TestCase):
    def test_an_unavailable_country_reader_reports_unknown_not_zero(self):
        with mock.patch.object(census, "_countries_named", return_value=None):
            c = census.census(LIVE)
            self.assertEqual(c["suggestive"], 0)
            self.assertEqual(c["suggestive_unknown"], len(LIVE))
            self.assertIn("UNKNOWN", census.report(c))


if __name__ == "__main__":
    unittest.main()
