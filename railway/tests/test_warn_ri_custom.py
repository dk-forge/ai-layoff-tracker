"""Rhode Island WARN: a custom reader replaces the open warn-scraper module.

Hasbro's 587-job Pawtucket notice (WJAR, Providence Journal, 2026-10-13) never
reached the tracker because warn-scraper's ri.py raises
`UnboundLocalError: cannot access local variable 'headers'` on every run: it
only reads a link whose text contains "WARN Report", the page no longer has
one, so `headers` is never bound and the whole state writes nothing (warn_us
run 2026-11-13: "warn-scraper RI exited 1"). The newest RI row was 2026-08-28.
The module cannot tell a changed page from a missing one, so ours must read
whatever workbook the page links and fail LOUDLY, naming the links it saw.
Fixtures are synthetic.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _requests_stub import install as _install  # noqa: E402
_install()

from sources import warn_custom as wc  # noqa: E402
from sources.warn import ALL_STATES  # noqa: E402

PAGE_NEW = """<html><body>
<a href="/sites/dlt/files/2026-10/RI%20WARN%20Notices%20FY27.xlsx">Current WARN notices (Excel)</a>
<a href="/employers/layoff-resources">Layoff resources</a>
<a href="/sites/dlt/files/old/2024-warn.pdf">2024 archive</a>
</body></html>"""

PAGE_OLD = '<a href="/files/WARN-Report.xlsx">WARN Report</a>'
PAGE_NONE = '<a href="/a">Home</a><a href="/b.pdf">Guide</a>'


def _workbook(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


HEADER = ["Company Name", "Date of Notice", "Effective Date", "Number of Workers", "City"]
ROWS = [
    ["Rhode Island WARN Report", None, None, None, None],     # title row above the header
    HEADER,
    ["Acme Toys Inc", "2026-10-13", "2026-12-12", "587", "Pawtucket"],
    ["Remote Staffing LLC", "2026-07-01", "2026-07-01", "9,891 Remote Workers (2 from RI)", ""],
    ["Zero Row Co", "2026-10-01", "2026-11-01", "0", ""],
    [None, None, None, None, None],
]


class Links(unittest.TestCase):
    def test_finds_a_workbook_whatever_the_link_text(self):
        links = wc._ri_workbook_links(PAGE_NEW, "https://dlt.ri.gov")
        self.assertEqual(links, ["https://dlt.ri.gov/sites/dlt/files/2026-10/RI%20WARN%20Notices%20FY27.xlsx"])

    def test_old_link_text_still_works(self):
        self.assertEqual(wc._ri_workbook_links(PAGE_OLD, "https://dlt.ri.gov"),
                         ["https://dlt.ri.gov/files/WARN-Report.xlsx"])

    def test_no_workbook_is_empty_not_a_guess(self):
        self.assertEqual(wc._ri_workbook_links(PAGE_NONE, "https://dlt.ri.gov"), [])


class Rows(unittest.TestCase):
    def test_title_row_is_skipped_and_counts_use_the_first_number(self):
        out = wc._ri_entries_from_workbook(_workbook(ROWS), "https://dlt.ri.gov/x")
        by = {e["company_name"]: e for e in out}
        self.assertEqual(by["Acme Toys Inc"]["job_count"], 587)
        self.assertEqual(by["Acme Toys Inc"]["layoff_date"], "2026-12-12")
        self.assertEqual(by["Acme Toys Inc"]["state"], "RI")
        self.assertEqual(by["Remote Staffing LLC"]["job_count"], 9891)
        self.assertNotIn("Zero Row Co", by)
        self.assertEqual(len(out), 2)

    def test_excel_date_cells_are_read(self):
        import datetime
        rows = [HEADER, ["Dated Co", datetime.datetime(2026, 10, 13),
                         datetime.datetime(2026, 12, 12), 41, ""]]
        out = wc._ri_entries_from_workbook(_workbook(rows), "u")
        self.assertEqual((out[0]["job_count"], out[0]["layoff_date"]), (41, "2026-12-12"))

    def test_a_sheet_with_no_company_header_yields_nothing(self):
        self.assertEqual(wc._ri_entries_from_workbook(_workbook([["a", "b"], [1, 2]]), "u"), [])


class Fetch(unittest.TestCase):
    class _Resp:
        def __init__(self, body=b"", text="", status=200):
            self.content, self.text, self.status_code = body, text, status

    def test_fetch_reads_the_linked_workbook(self):
        xlsx = _workbook(ROWS)

        def get(url):
            return self._Resp(text=PAGE_NEW) if url.endswith("-warn") else self._Resp(body=xlsx)
        out = wc.fetch_ri(get=get)
        self.assertEqual({e["company_name"] for e in out}, {"Acme Toys Inc", "Remote Staffing LLC"})

    def test_no_link_fails_loudly_and_names_what_it_saw(self):
        with self.assertRaises(RuntimeError) as cm:
            wc.fetch_ri(get=lambda url: self._Resp(text=PAGE_NONE))
        self.assertIn("/b.pdf", str(cm.exception))

    def test_unreachable_page_is_not_reported_as_drift(self):
        with self.assertRaises(RuntimeError) as cm:
            wc.fetch_ri(get=lambda url: self._Resp(status=403))
        self.assertIn("403", str(cm.exception))


class Wiring(unittest.TestCase):
    def test_ri_is_custom_and_not_also_run_through_the_broken_module(self):
        self.assertIn("RI", wc.CUSTOM_STATES)
        self.assertNotIn("RI", ALL_STATES)


if __name__ == "__main__":
    unittest.main()
