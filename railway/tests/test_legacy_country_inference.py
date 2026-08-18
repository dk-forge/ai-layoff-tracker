"""A .gov source URL is not a US job location.

THE DEFECT, FOUND WHILE MEASURING THE UNPLACED SET, 2026-08-18.

`legacy_row_repair.py` fills a blank `country` from "deterministic evidence",
and its own docstring named that evidence exactly: a US state code on the row,
or a US STATE GOVERNMENT WARN source. The implementation did not match the
sentence. `_US_HOST_RX` opened with a bare `\\.gov\\b`, and `www.sec.gov` ends
in `.gov`.

WHY THAT WAS NOT THEORETICAL. Measured live the same day, the entire
blank-country population of the corpus was 109 rows, every one of them with an
empty `state` — so the state branch could place none of them and the host
branch decided all of them. 27 carried a `www.sec.gov` URL. One click of the
manual "Legacy row repair" workflow with `--apply --only country` would have
written "United States" onto all 27, including Klarna Group plc (6-K, Sweden),
ING GROEP NV (6-K, Netherlands), Vasta Platform Ltd (6-K, Brazil), Brightstar
Lottery PLC and SLB LIMITED/NV. EDGAR is a filing venue; a foreign private
issuer files there BECAUSE it is foreign.

AND THE WRITE STICKS. /edit sets `edited=1` and rewrites the dedup hash, so the
row is pinned against re-import, and the claim is published in the public
corrections log. An unplaced row is honest. A wrongly placed row is a wrong
number on a public page and inside every per-country figure someone may quote,
which is the one outcome this repair is not allowed to produce.

The fix gates the host test on the row's `source_type`, whitelisted to the two
types where a US government host really is the jurisdiction. These cases are
the live rows, kept verbatim so a future widening has to argue with the actual
data rather than with a hypothetical.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import legacy_row_repair as repair


#: Verbatim from the live corpus, 2026-08-18. Blank country, blank state, an
#: EDGAR URL, and a country that is not the United States or is not knowable
#: from the filing venue.
LIVE_SEC_ROWS = [
    {"id": 176872, "company_name": "Klarna Group plc", "source_type": "8K", "state": "",
     "source_url": "https://www.sec.gov/Archives/edgar/data/1994650/klarna-6k.htm"},
    {"id": 176777, "company_name": "ING GROEP NV", "source_type": "8K", "state": "",
     "source_url": "https://www.sec.gov/Archives/edgar/data/1039765/ing-6k.htm"},
    {"id": 176871, "company_name": "Vasta Platform Ltd", "source_type": "8K", "state": "",
     "source_url": "https://www.sec.gov/Archives/edgar/data/1836948/vasta-6k.htm"},
    {"id": 177155, "company_name": "Brightstar Lottery PLC", "source_type": "8K", "state": "",
     "source_url": "https://www.sec.gov/Archives/edgar/data/1636519/brightstar-6k.htm"},
    {"id": 177159, "company_name": "SLB LIMITED/NV", "source_type": "8K", "state": "",
     "source_url": "https://www.sec.gov/Archives/edgar/data/87347/slb-8k.htm"},
    {"id": 177194, "company_name": "Humacyte, Inc.", "source_type": "8K", "state": "",
     "source_url": "https://www.sec.gov/Archives/edgar/data/1818382/tm2622949d1_ex99-1.htm"},
]


class SecGovIsNotAJobLocation(unittest.TestCase):
    def test_no_sec_filing_row_is_placed_by_its_host(self):
        for row in LIVE_SEC_ROWS:
            with self.subTest(company=row["company_name"]):
                self.assertIsNone(
                    repair._infer_country(row),
                    "%s (id %d) was placed from its sec.gov URL. EDGAR is a filing "
                    "venue, not a job location, and this row's own filing is a foreign "
                    "private issuer's." % (row["company_name"], row["id"]))

    def test_a_news_row_is_never_placed_by_its_host(self):
        # The other 82 blank rows are news. Publisher nationality was already
        # ruled out in prose; this pins it against a .us/.gov news domain.
        for url in ("https://www.army.mil.gov/press",
                    "https://news.example.us/story",
                    "https://www.handelsblatt.com/mckinsey"):
            with self.subTest(url=url):
                self.assertIsNone(repair._infer_country(
                    {"source_type": "news", "state": "", "source_url": url}))


class TheEvidenceThatStillCounts(unittest.TestCase):
    def test_a_state_code_still_places_the_row_whatever_the_source(self):
        # The state branch is unchanged and is the one that carries the real
        # WARN backlog. It must not have been narrowed by the host gate.
        for source_type in ("warn", "news", "8K", "erm", "federal_rif"):
            with self.subTest(source_type=source_type):
                self.assertEqual("United States", repair._infer_country(
                    {"source_type": source_type, "state": "KY",
                     "source_url": "https://example.com/notice"}))

    def test_a_state_warn_registry_host_still_places_a_stateless_warn_row(self):
        for url in ("https://www.dllr.state.md.us/employment/warn.shtml",
                    "https://edd.ca.gov/en/jobs_and_training/warn",
                    "https://www.twc.texas.gov/news/warn-notices"):
            with self.subTest(url=url):
                self.assertEqual("United States", repair._infer_country(
                    {"source_type": "warn", "state": "", "source_url": url}))

    def test_a_federal_rif_row_on_a_us_government_host_still_places(self):
        self.assertEqual("United States", repair._infer_country(
            {"source_type": "federal_rif", "state": "",
             "source_url": "https://www.opm.gov/data/ehri-separations"}))

    def test_the_whitelist_is_a_whitelist(self):
        # A source type nobody has argued about must not be placeable by host.
        self.assertNotIn("8K", repair._HOST_INFERABLE_SOURCE_TYPES)
        self.assertNotIn("news", repair._HOST_INFERABLE_SOURCE_TYPES)
        self.assertNotIn("erm", repair._HOST_INFERABLE_SOURCE_TYPES)
        self.assertNotIn("press_release", repair._HOST_INFERABLE_SOURCE_TYPES)


if __name__ == "__main__":
    unittest.main()
