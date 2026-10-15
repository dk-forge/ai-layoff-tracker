"""Census Business Formation Statistics: reference collector, offline (#478 item 5).

Keyless, public domain. One wide CSV (year x jan..dec); we keep seasonally
adjusted all-sector business applications (BA_BA, BA_HBA) per geography, one
value per month over a trailing window.
"""
import json
import os
import sys
import unittest
from datetime import date

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import bfs_import  # noqa: E402
import reference_freshness as rf  # noqa: E402
from sources import census_bfs as bfs  # noqa: E402

REPO = os.path.dirname(RAILWAY)

CSV = """sa,naics_sector,series,geo,year,jan,feb,mar,apr,may,jun,jul,aug,sep,oct,nov,dec
U,TOTAL,BA_BA,US,2026,547443,505240,534850,649160,498776,496832,634735,478274,582530,,,
A,TOTAL,BA_BA,US,2026,526115,496121,493792,506807,528929,533453,576264,532051,534947,,,
A,TOTAL,BA_HBA,US,2026,148127,146252,144970,147126,146983,149704,151566,145421,147331,,,
A,TOTAL,BA_BA,CA,2026,56976,49777,47121,48689,52447,52989,60921,55432,52974,,,
A,NAICS51,BA_BA,US,2026,1,2,3,4,5,6,7,8,9,,,
A,TOTAL,BF_BF4Q,US,2026,9,9,9,9,9,9,9,9,9,,,
A,TOTAL,BA_BA,PR,2026,NA,NA,NA,NA,NA,NA,NA,NA,NA,,,
A,TOTAL,BA_BA,US,2022,1,1,1,1,1,1,1,1,1,1,1,1
"""


class Parsing(unittest.TestCase):
    def setUp(self):
        self.rows = bfs.parse_csv(CSV, date(2023, 10, 1))

    def test_sa_total_two_series_only(self):
        us_ba = [r for r in self.rows if r[:2] == ["US", "BA_BA"]]
        self.assertEqual(us_ba[0], ["US", "BA_BA", "2026-01", 526115], "SA, not NSA")
        self.assertEqual(len(us_ba), 9, "blank months skipped")
        self.assertFalse(any(r[2] < "2023-10" for r in self.rows), "window applied")
        self.assertEqual({r[1] for r in self.rows}, {"BA_BA", "BA_HBA"})
        self.assertNotIn(1, [r[3] for r in self.rows], "sector rows excluded")
        self.assertFalse(any(r[0] == "PR" for r in self.rows), "NA skipped")

    def test_payload_shape(self):
        p = bfs.build_payload(CSV, today=date(2026, 10, 15))
        self.assertEqual(p["source"], "census_bfs")
        self.assertEqual(p["fields"], ["geo", "series", "month", "value"])
        self.assertEqual(p["latest"], {"monthly": "2026-09"})
        self.assertEqual(p["rows"], len(p["datasets"]["monthly"]))
        self.assertIn("Census Bureau", p["attribution"])
        self.assertIn("Public domain", p["licence"])
        self.assertEqual(p["geos"], ["CA", "US"])
        self.assertIn("not", p["note"].lower())

    def test_garbage_gives_no_rows(self):
        self.assertEqual(bfs.build_payload("nope", today=date(2026, 10, 15))["rows"], 0)

    def test_fetch_sends_user_agent(self):
        seen = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return CSV.encode()

        def opener(req, timeout):
            seen["ua"] = req.get_header("User-agent")
            seen["url"] = req.full_url
            return Resp()

        p = bfs.pull(today=date(2026, 10, 15), opener=opener)
        self.assertIn("AiLayoffTracker", seen["ua"])
        self.assertEqual(seen["url"], bfs.URL)
        self.assertGreater(p["rows"], 0)


class StoreGate(unittest.TestCase):
    def _full(self):
        geos = ["US"] + [f"S{i:02d}" for i in range(55)]
        rows = [[g, s, "2026-09", 1] for g in geos for s in bfs.SERIES]
        return {"rows": len(rows), "geos": geos, "series": list(bfs.SERIES),
                "datasets": {"monthly": rows}}

    def test_refuses_empty_missing_national_or_few_geos(self):
        self.assertFalse(bfs_import.should_store({"rows": 0})[0])
        p = self._full()
        p["geos"] = p["geos"][1:]
        self.assertIn("national", bfs_import.should_store(p)[1])
        ok, why = bfs_import.should_store(bfs.build_payload(CSV, today=date(2026, 10, 15)))
        self.assertFalse(ok)
        self.assertIn("geographies", why)

    def test_accepts_full_payload(self):
        self.assertTrue(bfs_import.should_store(self._full())[0])

    def test_real_size_fits(self):
        n = 60 * len(bfs.SERIES) * 12 * bfs.WINDOW_YEARS
        self.assertLess(len(json.dumps([["US", "BA_HBA", "2026-09", 1234567]] * n)),
                        bfs_import.MAX_BYTES)


class Wiring(unittest.TestCase):
    def test_freshness_spec(self):
        self.assertIn("census_bfs", rf.SPECS)
        doc = {"updated": "2026-10-14", "latest": {"monthly": "2026-09"}}
        self.assertTrue(rf.verdict("census_bfs", doc, today=date(2026, 10, 15))[0])

    def test_registered_on_the_plugin(self):
        with open(os.path.join(REPO, "wordpress-plugin", "ai-layoff-tracker", "includes", "reference-data.php")) as fh:
            self.assertIn("'census_bfs' => 'alt_ref_census_bfs'", fh.read())

    def test_workflow_keyless_and_dispatchable(self):
        with open(os.path.join(REPO, ".github", "workflows", "bfs-import.yml")) as fh:
            text = fh.read()
        self.assertIn("workflow_dispatch", text)
        self.assertIn("python bfs_import.py", text)
        self.assertNotIn("secrets.", text.replace("secrets.WP_API_KEY", ""), "keyless source")


if __name__ == "__main__":
    unittest.main()
