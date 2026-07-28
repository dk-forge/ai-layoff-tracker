"""Offline guards for the Kansas custom WARN fetcher (warn_new_states.fetch_ks).

KS moved off the generic warn-scraper on 2026-07-28: the open module walks the
entire kansasworks history and timed out (420s) on every run since ~May, leaving
Kansas dark. These tests pin the two pure parsers against captured markup so a
portal redesign fails loudly here instead of silently returning nothing.
Only `requests`/`pdfplumber` are stubbed (never fake sources.* modules).
"""
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for _m in ("requests", "pdfplumber"):
    if _m not in sys.modules:
        _st = types.ModuleType(_m)
        _st.RequestException = Exception
        sys.modules[_m] = _st

from sources.warn_new_states import _ks_listing_ids, _ks_detail_fields

LISTING = '''
<table><tr><td><a href="/search/warn_lookups/2300">First Brands Group, LLC (Hopkins)</a></td></tr>
<tr><td><a href="/search/warn_lookups/2301">Another Co</a></td></tr>
<tr><td><a href="/search/warn_lookups/2300">dup link</a></td></tr></table>
'''

DETAIL = '''
<h1>First Brands Group, LLC (Hopkins)</h1><h2>WARN Notice</h2>
<dt>Company Name</dt><dd>First Brands Group, LLC (Hopkins)</dd>
<dt>Address</dt><dd>428 Peyton St.</dd><dd>Emporia, Kansas 66801</dd>
<dt>Notice Date</dt><dd>Feb 23, 2026</dd>
<dt>Number of Employees Affected</dt><dd>130</dd>
<script>var Tawk_API = {};</script>
'''


class KsListingTests(unittest.TestCase):
    def test_ids_unique_and_ordered(self):
        self.assertEqual(_ks_listing_ids(LISTING), ["2300", "2301"])

    def test_empty_page_yields_nothing(self):
        self.assertEqual(_ks_listing_ids("<html>no notices</html>"), [])


class KsDetailTests(unittest.TestCase):
    def test_real_capture_shape_parses(self):
        company, city, date, jobs = _ks_detail_fields(DETAIL)
        self.assertEqual(company, "First Brands Group, LLC (Hopkins)")
        self.assertEqual(city, "Emporia")
        self.assertEqual(date, "2026-02-23")
        self.assertEqual(jobs, 130)

    def test_missing_count_yields_zero_not_guess(self):
        html = DETAIL.replace("<dt>Number of Employees Affected</dt><dd>130</dd>", "")
        _, _, _, jobs = _ks_detail_fields(html)
        self.assertEqual(jobs, 0)   # _entry() drops 0-count rows: skip, never guess

    def test_script_noise_never_parses_as_fields(self):
        _, _, _, jobs = _ks_detail_fields("<script>Number of Employees Affected 999</script>")
        self.assertEqual(jobs, 0)


if __name__ == "__main__":
    unittest.main()
