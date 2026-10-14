"""Indeed Hiring Lab job postings index: reference collector, offline (#478 item 1).

Keyless, CC BY 4.0. The upstream CSVs are daily; we store the last value of each
ISO week (week-ending date) per sector plus the national aggregate, over a
trailing window, so the document stays well under the reference ceiling.
"""
import json
import os
import sys
import unittest
from datetime import date

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import indeed_import  # noqa: E402
import reference_freshness as rf  # noqa: E402
from sources import indeed_postings as ind  # noqa: E402

REPO = os.path.dirname(RAILWAY)

SECTOR = """date,jobcountry,indeed_job_postings_index,variable,display_name
2026-09-21,US,90.0,total postings,Accounting
2026-09-21,US,50.0,new postings,Accounting
2026-09-25,US,91.5,total postings,Accounting
2026-09-27,US,92.0,total postings,Accounting
2026-09-28,US,93.0,total postings,Accounting
2026-09-28,US,120.0,total postings,Software Development
2019-01-01,US,80.0,total postings,Accounting
2026-09-29,US,,total postings,Accounting
"""
AGG = """date,jobcountry,indeed_job_postings_index_SA,indeed_job_postings_index_NSA,variable
2026-09-27,US,104.2,103.0,total postings
2026-09-27,US,60.0,61.0,new postings
2026-09-28,US,104.5,104.0,total postings
"""


class Parsing(unittest.TestCase):
    def test_weekly_last_value_per_iso_week_total_postings_only(self):
        rows = ind.weekly_rows(ind.parse_sector_csv(SECTOR), start=date(2025, 1, 1))
        acc = [r for r in rows if r[0] == "Accounting"]
        # Sep 21-27 2026 is one ISO week (keeps the 27th); Sep 28 starts the next.
        self.assertNotIn(["Accounting", "2026-09-21", 90.0], acc)
        self.assertIn(["Accounting", "2026-09-27", 92.0], acc)
        self.assertIn(["Accounting", "2026-09-28", 93.0], acc)
        self.assertNotIn(50.0, [r[2] for r in acc], "new postings excluded")
        self.assertFalse(any(r[1] < "2025" for r in rows), "window applied")
        self.assertEqual(len(acc), 2, "blank values skipped, one row per week")

    def test_aggregate_uses_seasonally_adjusted_total(self):
        rows = ind.weekly_rows(ind.parse_aggregate_csv(AGG), start=date(2025, 1, 1))
        self.assertEqual(rows, [[ind.ALL_SECTORS, "2026-09-27", 104.2],
                                [ind.ALL_SECTORS, "2026-09-28", 104.5]])

    def test_payload_shape(self):
        p = ind.build_payload(SECTOR, AGG, today=date(2026, 10, 5))
        self.assertEqual(p["source"], "indeed_postings")
        self.assertEqual(p["fields"], ["sector", "week_ending", "index"])
        self.assertEqual(p["latest"], {"weekly": "2026-09"})
        self.assertEqual(p["rows"], len(p["datasets"]["weekly"]))
        self.assertIn("Indeed Hiring Lab", p["attribution"])
        self.assertIn("CC BY 4.0", p["licence"])
        self.assertIn(ind.ALL_SECTORS, p["sectors"])
        self.assertIn("Software Development", p["sectors"])
        self.assertIn("not", p["note"].lower())

    def test_garbage_gives_no_rows(self):
        self.assertEqual(ind.build_payload("nope", "", today=date(2026, 10, 5))["rows"], 0)


class StoreGate(unittest.TestCase):
    def test_refuses_empty_or_missing_aggregate(self):
        self.assertFalse(indeed_import.should_store({"rows": 0})[0])
        p = ind.build_payload(SECTOR, "", today=date(2026, 10, 5))
        ok, why = indeed_import.should_store(p)
        self.assertFalse(ok)
        self.assertIn("aggregate", why)

    def test_accepts_full_payload(self):
        self.assertTrue(indeed_import.should_store(ind.build_payload(SECTOR, AGG, today=date(2026, 10, 5)))[0])

    def test_real_size_fits(self):
        # 48 series x 3 years of weeks, generously sized rows.
        n = 48 * 52 * ind.WINDOW_YEARS
        self.assertLess(len(json.dumps([["Loading & Stocking", "2026-09-28", 110.18]] * n)),
                        indeed_import.MAX_BYTES)


class Wiring(unittest.TestCase):
    def test_freshness_spec(self):
        self.assertIn("indeed_postings", rf.SPECS)
        doc = {"updated": "2026-10-04", "latest": {"weekly": "2026-09"}}
        self.assertTrue(rf.verdict("indeed_postings", doc, today=date(2026, 10, 5))[0])

    def test_registered_on_the_plugin(self):
        with open(os.path.join(REPO, "wordpress-plugin", "ai-layoff-tracker", "includes", "reference-data.php")) as fh:
            self.assertIn("'indeed_postings' => 'alt_ref_indeed_postings'", fh.read())

    def test_workflow_keyless_and_dispatchable(self):
        with open(os.path.join(REPO, ".github", "workflows", "indeed-import.yml")) as fh:
            text = fh.read()
        self.assertIn("workflow_dispatch", text)
        self.assertIn("python indeed_import.py", text)
        self.assertNotIn("secrets.", text.replace("secrets.WP_API_KEY", ""), "keyless source")


if __name__ == "__main__":
    unittest.main()
