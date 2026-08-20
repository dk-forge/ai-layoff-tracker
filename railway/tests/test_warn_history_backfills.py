"""Offline regression tests for the 2026-07-18 state WARN history backfills:
OH per-year archive CSVs, LA per-year PDFs (incl. the pre-2025 5-column
vintage now served via Wayback), NC archive PDFs (gridded 2018+ and the
2015-2017 headerless text vintage), and the retired NY database.

Fixtures are verbatim captures from the real state files — no network.
"""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Parser-only tests: never import real HTTP clients (matches the other guards).
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources import warn_custom as wc

FIX = Path(__file__).parent / "fixtures"


class OhioArchiveCsvTests(unittest.TestCase):
    def test_2020_archive_csv_parses_through_metadata_rows(self):
        # Real head of the 2020 DAM CSV: 2 renderer-metadata rows, then a
        # header with a DUPLICATED "Company" column, then data.
        text = (FIX / "oh_2020_warn_notice.csv").read_text(encoding="utf-8")
        entries = wc._oh_entries_from_csv(text)
        self.assertEqual(len(entries), 3)
        first = entries[0]
        self.assertEqual(first["company_name"], "The Fiesta Tableware Company")
        self.assertEqual(first["job_count"], 80)
        self.assertEqual(first["layoff_date"], "2021-02-11")  # layoff over received
        self.assertEqual(first["state"], "OH")
        # City/County splits on the slash; only the city half is kept
        self.assertEqual(first["excerpt"].count("East Liverpool"), 1)
        self.assertNotIn("Columbiana", first["excerpt"])

    def test_headerless_blob_yields_nothing(self):
        self.assertEqual(wc._oh_entries_from_csv("just,some,noise\n1,2,3"), [])

    def test_dam_csv_regex_matches_both_2026_url_shapes(self):
        # The site rebuild added f_auto/q_auto/v<nnn> segments; the versionless
        # fallback pattern must keep matching too.
        versioned = ("https://dam.assets.ohio.gov/raw/upload/f_auto/q_auto/"
                     "v1776259430/jfs.ohio.gov/2026/2024_warn_notice.csv")
        versionless = ("https://dam.assets.ohio.gov/raw/upload/"
                       "jfs.ohio.gov/2026/2026-warn-notice.csv")
        page = f'<a href="{versioned}">csv</a> <a href="{versionless}">csv</a>'
        self.assertEqual(wc._OH_CSV_RE.findall(page), [versioned, versionless])

    def test_archive_pages_start_at_2020(self):
        # 2015-2019 slugs 404 on jfs.ohio.gov (verified 2026-07-18) — probing
        # them would just add noise to every run.
        self.assertEqual(wc._OH_ARCHIVE_START, 2020)


class LouisianaPdfTests(unittest.TestCase):
    # Verbatim pdfplumber rows from WarnNotices2015.pdf (Wayback copy).
    LA_2015 = [
        ["Company Name", "Notice Date", "Layoff\nDate", "E m p loyees\nAffected", "Industry"],
        ["Albertson’s Store #2814\n3450 U.S. Highway 190\nMandeville, LA 70471",
         "1/6/2015", "2/7/2015", "83", "Supermarkets and Other\nGrocery (except\nConvenience) Stores"],
        ["McDermott Inc.\n2317 Louisiana Highway",
         "2/19/2015", "4/21/2015 – 5/4/2015", "6", "Shipbuilding"],
    ]

    def test_2015_five_column_vintage_parses(self):
        entries = wc._la_entries_from_tables([self.LA_2015], "http://x/2015.pdf")
        self.assertEqual(len(entries), 2)  # header skipped
        self.assertEqual(entries[0]["job_count"], 83)
        self.assertEqual(entries[0]["layoff_date"], "2015-02-07")
        self.assertTrue(entries[0]["company_name"].startswith("Albertson"))
        # Date ranges resolve to the lower bound
        self.assertEqual(entries[1]["layoff_date"], "2015-04-21")
        self.assertEqual(entries[1]["source_url"], "http://x/2015.pdf")

    def test_2026_six_column_vintage_still_parses(self):
        table = [
            ["Company", "Address", "Notice Date", "Layoff Date", "Affected", "Industry"],
            ["Acme Refining", "1 Main St", "1/5/2026", "3/1/2026", "120", "Oil"],
        ]
        entries = wc._la_entries_from_tables([table], "http://x/2026.pdf")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["job_count"], 120)
        self.assertEqual(entries[0]["layoff_date"], "2026-03-01")


class NorthCarolinaGridTests(unittest.TestCase):
    # Verbatim rows from the real archive PDFs (cells keep their \n wraps).
    NC_2019 = [
        ["", "", "", "", "", "", "", "", ""],
        ["County/Parish", "WARN No.", "Notice\nDate", "Received\nDate",
         "Effective\nDate", "Company", "Layoff/Closure", "No. Of\nEmployees", "Address"],
        ["Durham County", "20190001", "01/09/2019", "1/9/2019", "03/11/2019",
         "Seterus, Inc. a subsidiary of\nIBM", "Closure\nPermanent", "310",
         "3039 Cornwallis Road Durham NC\n27709"],
    ]
    NC_2023_P1 = [
        ["WARN Summary by County/Parish\nAs of 2024-01-03", None, None, None,
         None, None, None, None, None, None, None, None, None],
        ["", "County", "Warn\nNumber", "Date of\nNotice", "Date\nReceived by\nNC",
         "Effective\nDate", "WARN Notice: WARN Notice Name", "WARN\nnotice\ntype",
         "Type of layoff\nor closure", "Number affected\nat this location",
         "Address 1", "City", ""],
        ["", "N/A", "202300001", "1/4/2023", "1/5/2023", "3/5/2023",
         "Monitronics International Inc. dba Brinks Home", "Layoff", "Permanent",
         "4", "1990 Wittington Place", "Dallas TX", ""],
    ]
    NC_2023_P2 = [  # continuation page: NO header row
        ["", "Wake County", "202300041", "7/30/2023", "8/1/2023", "7/30/2023",
         "Yellow Corporation", "Closure", "Permanent", "55",
         "1305 Kirkland Road", "Raleigh", ""],
    ]

    def test_2019_vintage_header_names_map(self):
        entries = wc._nc_grid_entries([self.NC_2019], "http://x/2019.pdf")
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["company_name"], "Seterus, Inc. a subsidiary of IBM")
        self.assertEqual(e["job_count"], 310)
        self.assertEqual(e["layoff_date"], "2019-03-11")  # effective over notice

    def test_2022_vintage_columns_persist_onto_headerless_pages(self):
        entries = wc._nc_grid_entries([self.NC_2023_P1, self.NC_2023_P2],
                                      "http://x/2023.pdf")
        self.assertEqual([e["company_name"] for e in entries],
                         ["Monitronics International Inc. dba Brinks Home",
                          "Yellow Corporation"])
        self.assertEqual(entries[1]["job_count"], 55)
        self.assertEqual(entries[1]["layoff_date"], "2023-07-30")
        self.assertIn("Raleigh", entries[1]["excerpt"])

    def test_rows_before_any_header_are_dropped(self):
        entries = wc._nc_grid_entries([self.NC_2023_P2], "http://x/frag.pdf")
        self.assertEqual(entries, [])


class NorthCarolinaTextVintageTests(unittest.TestCase):
    """Real pdfplumber words from page 1 of WARN-report-2015.pdf (no grid)."""

    @classmethod
    def setUpClass(cls):
        words = json.loads((FIX / "nc_2015_p1_words.json").read_text())
        cls.entries = wc._nc_text_rows(words, "http://x/2015.pdf")

    def test_rows_parse_with_company_city_count_kind(self):
        macys = [e for e in self.entries if "Macy" in e["company_name"]]
        self.assertEqual(len(macys), 1)
        self.assertEqual(macys[0]["job_count"], 77)
        self.assertEqual(macys[0]["layoff_date"], "2015-03-21")
        self.assertIn("Greensboro", macys[0]["excerpt"])
        self.assertTrue(macys[0]["excerpt"].startswith("Closure at"))

    def test_wrapped_company_lines_merge_into_previous_row(self):
        aramark = [e for e in self.entries if "Aramark" in e["company_name"]]
        self.assertEqual(len(aramark), 1)
        self.assertEqual(aramark[0]["company_name"],
                         "Aramark (Morehead Memorial Hospital)")
        self.assertEqual(aramark[0]["job_count"], 49)

    def test_summary_blocks_never_become_entries(self):
        for e in self.entries:
            self.assertNotRegex(e["company_name"], r"Month|Total|Sum of|Notices")
            # the monthly "Sum of # Employees Affected: 1,753" style totals
            # must not leak in as fake counts
            self.assertLess(e["job_count"], 1000)


class NewYorkRetiredDatabaseTests(unittest.TestCase):
    def test_listing_rows_from_real_2023_archive_markup(self):
        html = (FIX / "ny_2023_listing.html").read_text(encoding="utf-8")
        rows = wc._ny_listing_rows(html)
        self.assertEqual(len(rows), 4)
        company, url, notice_text = rows[1]
        self.assertEqual(company, "Pfizer Inc.")
        self.assertEqual(url, "https://dol.ny.gov/warn-pfizer-hudson-valley-2023-0169-12-22-2023")
        self.assertEqual(notice_text, "12/14/2023")
        # header row (th cells) must not be returned
        self.assertTrue(all(r[0] != "Company Name" for r in rows))

    def test_notice_fields_from_real_pfizer_pdf_text(self):
        # 'February\n12, 2024' wraps across lines in the raw text layer
        jobs, date = wc._ny_fields_from_text(
            (FIX / "ny_notice_pfizer.txt").read_text(encoding="utf-8"))
        self.assertEqual(jobs, 285)
        self.assertEqual(date, "2024-02-12")

    def test_amended_notice_keeps_original_count_and_start_date(self):
        # MV Transportation: '251 • Amended to 565' and a multi-site layout
        jobs, date = wc._ny_fields_from_text(
            (FIX / "ny_notice_mv.txt").read_text(encoding="utf-8"))
        self.assertEqual(jobs, 251)
        self.assertEqual(date, "2025-02-10")

    def test_date_of_notice_is_the_fallback(self):
        jobs, date = wc._ny_fields_from_text(
            "Total Number of Affected Workers: 40\nDate of Notice: December 14, 2023")
        self.assertEqual((jobs, date), (40, "2023-12-14"))

    def test_ny_is_wired_into_the_dispatch_map(self):
        self.assertIs(wc.CUSTOM_STATES.get("NY"), wc.fetch_ny_history)
        # and the pre-existing states are untouched
        for st in ("TX", "FL", "GA", "OH", "MI", "CO", "ID", "LA", "NC", "NV", "MN", "MA"):
            self.assertIn(st, wc.CUSTOM_STATES)


if __name__ == "__main__":
    unittest.main()
