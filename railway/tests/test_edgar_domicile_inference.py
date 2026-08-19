"""Offline guards for the EDGAR filer-record domicile basis.

The rows this covers are the ones the 2026-08-18 measurement found: 109 rows
with a blank job-location `country`, ALL of which also had a blank
`employer_country`, which is what actually made them unreachable by any country
filter (`country_basis=any` matches `country OR employer_country`).

Twenty-seven of them are SEC filings. `legacy_row_repair` would have written
"United States" onto all 27 because `www.sec.gov` ends in `.gov`. The rule
here reads the opposite direction: the domicile comes from the filing ENTITY's
own EDGAR company record, so the five foreign private issuers among them come
out foreign. The records below are copied verbatim from data.sec.gov on
2026-08-18, so this is a pin on real filers, not on invented shapes.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from employer_domicile_backfill import (  # noqa: E402
    build_edgar_items, edgar_cik, edgar_domicile,
)


def record(business_code=None, business_desc=None, inc_code="", inc_desc=""):
    addresses = {}
    if business_code is not None or business_desc is not None:
        addresses["business"] = {
            "stateOrCountry": business_code,
            "stateOrCountryDescription": business_desc,
        }
    return {
        "addresses": addresses,
        "stateOfIncorporation": inc_code,
        "stateOfIncorporationDescription": inc_desc,
    }


#: id -> (company, EDGAR record as returned live, expected employer_country).
#: The five foreign issuers are the five the old host test would have got wrong.
LIVE_FILERS = {
    176872: ("Klarna Group plc", record("X0", "United Kingdom", "X0", "United Kingdom"),
             "United Kingdom"),
    176777: ("ING GROEP NV", record("P7", "Netherlands", "P7", "Netherlands"),
             "Netherlands"),
    176871: ("Vasta Platform Ltd", record("D5", "Brazil", "E9", "Cayman Islands"),
             "Brazil"),
    177155: ("Brightstar Lottery PLC", record(None, None, "X0", "United Kingdom"),
             "United Kingdom"),
    177159: ("SLB LIMITED/NV", record("TX", "TX", "P8", "Netherlands Antilles"),
             "United States"),
    177340: ("BILL Holdings, Inc.", record("CA", "CA", "", ""), "United States"),
    177222: ("SunPower Inc.", record("UT", "UT", "DE", "DE"), "United States"),
    176607: ("HARLEY-DAVIDSON, INC.", record("WI", "WI", "WI", "WI"), "United States"),
}


class CikExtraction(unittest.TestCase):
    def test_cik_comes_only_from_an_sec_host(self):
        self.assertEqual(
            edgar_cik("https://www.sec.gov/Archives/edgar/data/1786352/000162828026032064/bill-20260507.htm"),
            1786352)
        self.assertEqual(edgar_cik("https://sec.gov/Archives/edgar/data/72162/x.htm"), 72162)

    def test_a_lookalike_path_on_another_host_is_refused(self):
        # The whole lesson of the .gov defect is that a URL test satisfiable by
        # some other host eventually is satisfied by one.
        for url in ("https://example.com/Archives/edgar/data/1786352/x.htm",
                    "https://sec.gov.evil.test/Archives/edgar/data/1786352/x.htm",
                    "https://www.sec.gov/news/press-release-2026-1.htm",
                    "", None):
            self.assertIsNone(edgar_cik(url), url)


class DomicileFromTheFilersOwnRecord(unittest.TestCase):
    def test_every_live_filer_resolves_to_its_own_domicile(self):
        for row_id, (company, rec, expected) in LIVE_FILERS.items():
            resolved = edgar_domicile(rec)
            self.assertIsNotNone(resolved, f"{row_id} {company}")
            self.assertEqual(resolved[0], expected, f"{row_id} {company}")

    def test_the_five_foreign_issuers_are_not_placed_in_the_united_states(self):
        # The exact write `legacy_row_repair --apply --only country` would have
        # made before the 2026-08-18 source_type gate.
        for row_id in (176872, 176777, 176871, 177155):
            company, rec, _ = LIVE_FILERS[row_id]
            self.assertNotEqual(edgar_domicile(rec)[0], "United States", company)

    def test_business_address_beats_a_letterbox_incorporation(self):
        # Vasta is Cayman-incorporated and Brazil-seated. Reading the
        # incorporation would put a shell jurisdiction on a public page.
        self.assertEqual(edgar_domicile(LIVE_FILERS[176871][1])[0], "Brazil")
        self.assertEqual(edgar_domicile(LIVE_FILERS[177159][1])[0], "United States")

    def test_incorporation_fallback_refuses_letterbox_jurisdictions(self):
        for seat in ("Cayman Islands", "Bermuda", "British Virgin Islands",
                     "Netherlands Antilles", "Jersey", "Marshall Islands"):
            self.assertIsNone(edgar_domicile(record(None, None, "E9", seat)), seat)

    def test_no_usable_evidence_returns_none_rather_than_a_default(self):
        for rec in (None, {}, record(None, None, "", ""), record("", "", "", "")):
            self.assertIsNone(edgar_domicile(rec))


class BuildItems(unittest.TestCase):
    def _rows(self):
        return [
            {"id": row_id, "company_name": company, "source_type": "8K",
             "employer_country": "",
             "source_url": f"https://www.sec.gov/Archives/edgar/data/{row_id}/x.htm"}
            for row_id, (company, _, _) in LIVE_FILERS.items()
        ]

    def _fetcher(self, ids):
        by_cik = {row_id: rec for row_id, (_, rec, _) in LIVE_FILERS.items()}
        return lambda cik: by_cik.get(cik)

    def test_items_carry_country_and_a_naming_evidence_string(self):
        rows = self._rows()
        items, unresolved = build_edgar_items(rows, fetcher=self._fetcher(LIVE_FILERS))
        self.assertEqual(len(items), len(LIVE_FILERS))
        self.assertEqual(unresolved, [])
        by_id = {item["id"]: item for item in items}
        for row_id, (_, _, expected) in LIVE_FILERS.items():
            self.assertEqual(by_id[row_id]["employer_country"], expected)
            evidence = by_id[row_id]["employer_country_evidence"]
            # /enrich-context refuses evidence shorter than 12 characters.
            self.assertGreaterEqual(len(evidence), 12)
            self.assertIn("EDGAR", evidence)
            self.assertIn(f"CIK {row_id:010d}", evidence)

    def test_a_non_sec_source_type_is_never_read_from_edgar(self):
        # The gate is the row's own source_type, matching the fix applied to
        # legacy_row_repair. A news story that happens to cite sec.gov is not
        # an SEC filing.
        rows = self._rows()
        for row in rows:
            row["source_type"] = "news"
        items, unresolved = build_edgar_items(rows, fetcher=self._fetcher(LIVE_FILERS))
        self.assertEqual(items, [])
        self.assertEqual(unresolved, [])

    def test_a_filled_domicile_is_never_overwritten(self):
        rows = self._rows()
        for row in rows:
            row["employer_country"] = "Ireland"
        items, _ = build_edgar_items(rows, fetcher=self._fetcher(LIVE_FILERS))
        self.assertEqual(items, [])

    def test_an_unreachable_edgar_record_leaves_the_row_blank(self):
        rows = self._rows()
        items, unresolved = build_edgar_items(rows, fetcher=lambda cik: None)
        self.assertEqual(items, [])
        self.assertEqual(len(unresolved), len(rows))

    def test_the_job_location_country_is_never_among_the_written_fields(self):
        items, _ = build_edgar_items(self._rows(), fetcher=self._fetcher(LIVE_FILERS))
        for item in items:
            self.assertEqual(set(item), {"id", "employer_country", "employer_country_evidence"})


if __name__ == "__main__":
    unittest.main()
