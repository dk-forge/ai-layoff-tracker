"""DC WARN: read the current-year DOES page ourselves.

2026-10-20: the open warn-scraper DC module died with MissingSchema on
'/page/rapid-response'. DOES replaced the year-link list it walked with
relative "Rapid Response" links, so the scraper raised before parsing the
current year's table, which is still on the page. DC went dark in the generic
tier (warn_us DEGRADED: "generic-tier state(s) went dark ... DC"). `requests.get`
is patched on the module object; nothing is stubbed into sys.modules.
"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import warn_dc  # noqa: E402
from sources import warn_new_states  # noqa: E402

YEAR = datetime.now().year
PAGE = f"""<html><div class="field-items"><a href="/page/rapid-response">Rapid Response</a></div>
<table><tr><th>Notice Date</th><th>Organization Name</th><th>Number toEmployees Affected</th>
<th>Effective Layoff Date</th><th>Code Type</th></tr>
<tr><td>February 2, {YEAR}</td><td>Example Foods LLC</td><td>76</td><td>June 30, {YEAR}</td><td>1</td></tr>
<tr><td>September 14, {YEAR}</td><td>Example Committee</td><td>TBD</td><td>November 13, {YEAR}</td><td>1</td></tr>
<tr><td>October 1, {YEAR}</td><td>Example Hotel Inc.</td><td>120</td><td></td><td>2</td></tr>
</table></html>"""


class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


class FetchDc(unittest.TestCase):
    def setUp(self):
        self._get = warn_dc.requests.get
        self.urls = []

    def tearDown(self):
        warn_dc.requests.get = self._get

    def _serve(self, pages):
        def get(url, **kw):
            self.urls.append(url)
            for key, body in pages.items():
                if url.endswith(key):
                    return _Resp(200, body)
            return _Resp(404)
        warn_dc.requests.get = get

    def test_reads_the_current_year_table(self):
        self._serve({f"-{YEAR}": PAGE})
        out = {e["company_name"]: e for e in warn_dc.fetch_dc()}
        self.assertEqual(set(out), {"Example Foods LLC", "Example Hotel Inc."})
        self.assertEqual(out["Example Foods LLC"]["layoff_date"], f"{YEAR}-06-30")
        self.assertEqual(out["Example Foods LLC"]["job_count"], 76)
        self.assertEqual(out["Example Foods LLC"]["state"], "DC")
        # no effective date: the notice date stands in, like the generic tier
        self.assertEqual(out["Example Hotel Inc."]["layoff_date"], f"{YEAR}-10-01")

    def test_relative_links_are_never_followed(self):
        self._serve({f"-{YEAR}": PAGE})
        warn_dc.fetch_dc()
        self.assertTrue(all(u.startswith("https://") for u in self.urls))
        self.assertFalse(any("rapid-response" in u for u in self.urls))

    def test_hash_matches_the_generic_tier_shape(self):
        self._serve({f"-{YEAR}": PAGE})
        e = [x for x in warn_dc.fetch_dc() if x["company_name"] == "Example Foods LLC"][0]
        from sources.warn_custom import _entry
        self.assertEqual(e["dedup_hash"],
                         _entry("DC", "Example Foods LLC", 76, f"{YEAR}-06-30")["dedup_hash"])

    def test_previous_year_page_is_read_too(self):
        self._serve({f"-{YEAR}": PAGE, f"-{YEAR - 1}": PAGE.replace(str(YEAR), str(YEAR - 1))})
        years = {e["layoff_date"][:4] for e in warn_dc.fetch_dc()}
        self.assertEqual(years, {str(YEAR), str(YEAR - 1)})

    def test_no_page_served_raises_so_it_reads_as_errored(self):
        self._serve({})
        with self.assertRaises(RuntimeError):
            warn_dc.fetch_dc()

    def test_registered_as_a_custom_state(self):
        self.assertIs(warn_new_states.NEW_CUSTOM_STATES.get("DC"), warn_dc.fetch_dc)


if __name__ == "__main__":
    unittest.main()
