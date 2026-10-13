"""NM and HI must not be run through the open warn-scraper modules.

Verified live 2026-10-13 against warn-scraper 1.2.143:
  * nm.py still reads https://www.dws.state.nm.us/ — that domain no longer
    resolves (New Mexico moved to dws.nm.gov). The module exits 0 and writes an
    EMPTY nm.csv, so the sweep silently gets nothing.
  * hi.py fetches through a Google web-cache prefix and follows Cloudflare
    `/cdn-cgi/l/email-protection` hrefs as if they were PDFs; it raises
    MissingSchema and writes no hi.csv.
Both states are served by our own collectors (warn_new_states.fetch_nm, and the
hi_ocr job), so the generic modules are dead weight that only adds noise.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources.warn import ALL_STATES, STATE_WARN_URL  # noqa: E402
from sources.warn_new_states import NEW_CUSTOM_STATES  # noqa: E402


class DeadGenericModulesTests(unittest.TestCase):
    def test_nm_served_by_custom_not_generic(self):
        self.assertIn("NM", NEW_CUSTOM_STATES)
        self.assertNotIn("NM", ALL_STATES)

    def test_hi_not_run_through_crashing_generic_module(self):
        self.assertNotIn("HI", ALL_STATES)

    def test_ms_not_double_run(self):
        # MS has a custom fetcher; adding it to ALL_STATES would scrape it twice.
        self.assertIn("MS", NEW_CUSTOM_STATES)
        self.assertNotIn("MS", ALL_STATES)

    def test_nd_in_generic_sweep(self):
        self.assertIn("ND", ALL_STATES)


class NmCitationTests(unittest.TestCase):
    def test_nm_fallback_link_is_on_the_live_domain(self):
        # dws.state.nm.us no longer resolves; NM rows citing it link nowhere.
        url = STATE_WARN_URL["NM"]
        self.assertNotIn("dws.state.nm.us", url)
        self.assertTrue(url.startswith("https://www.dws.nm.gov/"))



class HawaiiStillPublishedAsCoveredTests(unittest.TestCase):
    def test_hi_remains_in_public_jurisdiction_table(self):
        import generate_jurisdiction_table as gjt
        self.assertIn("HI", gjt.covered_warn_jurisdictions())


if __name__ == "__main__":
    unittest.main()
