"""BLS CES average weekly hours + hourly earnings: reference collector, offline (#478 item 9).

Keyless BLS API v1, the same request and parser path as bls_jolts_cps.
"""
import json
import os
import sys
import unittest
from datetime import date

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import ces_import  # noqa: E402
import reference_freshness as rf  # noqa: E402
from sources import bls_ces_hours as ces  # noqa: E402
from sources import bls_jolts_cps as bls  # noqa: E402

REPO = os.path.dirname(RAILWAY)

# Recorded shape of a BLS v1 response (values trimmed).
BODY = {
    "status": "REQUEST_SUCCEEDED", "message": [],
    "Results": {"series": [
        {"seriesID": "CES0500000002", "data": [
            {"year": "2026", "period": "M09", "value": "34.2", "footnotes": [{"code": "P"}]},
            {"year": "2026", "period": "M08", "value": "34.3", "footnotes": [{}]},
            {"year": "2025", "period": "M13", "value": "34.3", "footnotes": [{}]},
            {"year": "2025", "period": "M12", "value": "-", "footnotes": [{}]},
        ]},
        {"seriesID": "CES5000000003", "data": [
            {"year": "2026", "period": "M09", "value": "50.12", "footnotes": [{}]},
        ]},
    ]},
}


class Catalogue(unittest.TestCase):
    def test_series_ids_and_budget(self):
        self.assertEqual(len(ces.SERIES), 26)
        self.assertIn("CES0500000002", ces.SERIES)
        self.assertIn("CES8000000003", ces.SERIES)
        self.assertTrue(all(len(s) == 13 and s.startswith("CES") for s in ces.SERIES))
        self.assertEqual(ces.request_count(), 2)
        self.assertEqual(ces.API_URL, bls.API_URL, "reuses the keyless v1 path")
        self.assertNotIn("registrationkey", json.dumps(ces.HEADERS).lower())


class Parsing(unittest.TestCase):
    def test_parse_and_payload(self):
        pts, errs = ces.parse_response(BODY)
        self.assertEqual(errs, [])
        self.assertEqual(pts["CES0500000002"], [["2026-08", 34.3, ""], ["2026-09", 34.2, "P"]])
        p = ces.build_payload(pts, errs)
        self.assertEqual(p["source"], "bls_ces_hours")
        self.assertEqual(p["latest"], {"ces": "2026-09"})
        self.assertEqual(p["rows"], 3)
        self.assertEqual(p["datasets"]["ces"]["CES5000000003"]["measure"], "avg_hourly_earnings")
        self.assertEqual(p["datasets"]["ces"]["CES5000000003"]["label"], "Information")
        self.assertIn("Public domain", p["licence"])
        self.assertIn("not layoffs", p["note"])
        self.assertEqual(len(p["missing_series"]), 24)

    def test_failed_status(self):
        pts, errs = ces.parse_response({"status": "REQUEST_NOT_PROCESSED", "message": ["threshold"]})
        self.assertEqual(pts, {})
        self.assertTrue(errs)

    def test_fetch_uses_post_and_counts_failures(self):
        class R:
            status_code = 200
            def json(self):
                return BODY
        calls = []
        def post(url, data, headers, timeout):
            calls.append((url, json.loads(data), headers))
            return R()
        p = ces.fetch(today=date(2026, 10, 15), post=post)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1]["startyear"], "2022")
        self.assertIn("AiLayoffTracker", calls[0][2]["User-Agent"])
        self.assertEqual(p["failed_requests"], 0)


class StoreGate(unittest.TestCase):
    def test_refuses_partial(self):
        self.assertFalse(ces_import.should_store({"rows": 0})[0])
        p = ces.build_payload(*ces.parse_response(BODY))
        p["failed_requests"] = 0
        ok, why = ces_import.should_store(p)
        self.assertFalse(ok)
        self.assertIn("missing", why)

    def test_accepts_full_and_fits(self):
        pts = {sid: [[f"{y}-{m:02d}", 34.5, ""] for y in range(2022, 2027) for m in range(1, 13)]
               for sid in ces.SERIES}
        p = ces.build_payload(pts, [])
        p["failed_requests"] = 0
        self.assertTrue(ces_import.should_store(p)[0])


class Wiring(unittest.TestCase):
    def test_freshness_spec(self):
        doc = {"updated": "2026-10-10", "latest": {"ces": "2026-09"}}
        self.assertTrue(rf.verdict("bls_ces_hours", doc, today=date(2026, 10, 15))[0])

    def test_registered_on_the_plugin(self):
        with open(os.path.join(REPO, "wordpress-plugin", "ai-layoff-tracker", "includes", "reference-data.php")) as fh:
            self.assertIn("'bls_ces_hours' => 'alt_ref_bls_ces_hours'", fh.read())

    def test_workflow_keyless_and_dispatchable(self):
        with open(os.path.join(REPO, ".github", "workflows", "ces-import.yml")) as fh:
            text = fh.read()
        self.assertIn("workflow_dispatch", text)
        self.assertIn("python ces_import.py", text)
        self.assertIn("--require-hashes", text)
        self.assertNotIn("secrets.", text.replace("secrets.WP_API_KEY", ""), "keyless source")


if __name__ == "__main__":
    unittest.main()
