"""BLS JOLTS + CPS reference collector: offline, against a recorded response.

tests/fixtures/bls_v1_response.json is a real BLS API v1 response recorded by
the depth-source probe on 2026-10-05 (PR #468). No test opens a connection.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

# The suite's one `requests` installer: the real module when it is installed
# (CI), a complete offline stub otherwise. Called before importing the
# collector so a later module's partial stub cannot take the slot first.
from tests import _requests_stub  # noqa: E402

_requests_stub.install()

import bls_archive  # noqa: E402
import bls_import  # noqa: E402
import reference_freshness as rf  # noqa: E402
from sources import bls_jolts_cps as bls  # noqa: E402

FIXTURE = os.path.join(RAILWAY, "tests", "fixtures", "bls_v1_response.json")
REPO = os.path.dirname(RAILWAY)


def recorded():
    with open(FIXTURE) as fh:
        return json.load(fh)


class FakeResp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


class SeriesCatalogueTest(unittest.TestCase):
    def test_jolts_ids_are_21_chars_and_match_published_ids(self):
        self.assertEqual(bls.jolts_id("LD"), "JTS000000000000000LDL")
        self.assertEqual(bls.jolts_id("LD", "540099"), "JTS540099000000000LDL")
        self.assertEqual(bls.jolts_id("JO", "000000", "NE"), "JTS000000NE0000000JOL")
        for sid, meta in bls.SERIES.items():
            if meta["dataset"] == "jolts":
                self.assertEqual(len(sid), 21, sid)

    def test_covers_three_elements_by_industry_and_region_and_cps_groups(self):
        measures = {m["measure"] for m in bls.SERIES.values() if m["dataset"] == "jolts"}
        self.assertEqual(measures, {"layoffs_discharges", "openings", "quits"})
        dims = {m["dim"] for m in bls.SERIES.values() if m["dataset"] == "cps"}
        self.assertEqual(dims, {"total", "sex", "age", "race", "education"})

    def test_request_budget_stays_well_under_keyless_limit(self):
        # Weekly run; keyless v1 allows 25/day. Keep a full refresh tiny.
        self.assertLessEqual(bls.request_count(), 4)
        self.assertTrue(all(len(b) <= 25 for b in bls.batches()))
        self.assertEqual(sum(len(b) for b in bls.batches()), len(bls.SERIES))


class ParseTest(unittest.TestCase):
    def test_recorded_response_parses_ascending_with_preliminary_flag(self):
        pts, errs = bls.parse_response(recorded())
        self.assertEqual(errs, [])
        ld = pts["JTS000000000000000LDL"]
        self.assertEqual(ld[-1], ["2026-08", 1641, "P"])
        self.assertEqual([p[0] for p in ld], sorted(p[0] for p in ld))
        self.assertEqual(pts["LNS14000002"][-1][:2], ["2026-09", 4.0])

    def test_annual_average_and_dash_values_are_skipped(self):
        pts = bls.parse_series({"data": [
            {"year": "2025", "period": "M13", "value": "4.1"},
            {"year": "2025", "period": "M12", "value": "-"},
            {"year": "2025", "period": "M11", "value": "4.2", "footnotes": [{}]}]})
        self.assertEqual(pts, [["2025-11", 4.2, ""]])

    def test_threshold_reply_is_an_error_not_data(self):
        pts, errs = bls.parse_response({"status": "REQUEST_NOT_PROCESSED",
                                        "message": ["daily threshold reached"]})
        self.assertEqual(pts, {})
        self.assertIn("REQUEST_NOT_PROCESSED", errs[0])


class FetchTest(unittest.TestCase):
    def test_fetch_batches_requests_and_builds_payload(self):
        calls = []

        def post(url, data, headers, timeout):
            calls.append(json.loads(data))
            return FakeResp(recorded())

        p = bls.fetch(post=post, today=date(2026, 10, 5))
        self.assertEqual(len(calls), bls.request_count())
        self.assertEqual(calls[0]["startyear"], "2017")
        self.assertEqual(calls[0]["endyear"], "2026")
        self.assertEqual(p["latest"], {"jolts": "2026-08", "cps": "2026-09"})
        self.assertGreater(p["rows"], 200)
        self.assertEqual(p["failed_requests"], 0)
        self.assertIn("Bureau of Labor Statistics", p["attribution"])
        self.assertIn("Public domain", p["licence"])
        ok, _ = bls_import.should_store(p)
        self.assertTrue(ok)

    def test_failed_request_blocks_overwrite(self):
        def post(url, data, headers, timeout):
            return FakeResp({}, status=503)

        p = bls.fetch(post=post, today=date(2026, 10, 5))
        ok, why = bls_import.should_store(p)
        self.assertFalse(ok)
        self.assertIn("failed", why)


class FreshnessTest(unittest.TestCase):
    def doc(self, updated, jolts, cps):
        return {"updated": updated, "latest": {"jolts": jolts, "cps": cps}}

    def test_current_data_is_fresh(self):
        ok, line = rf.verdict("bls_jolts_cps", self.doc("2026-10-01T14:00:00+00:00",
                                                         "2026-08", "2026-09"),
                              today=date(2026, 10, 5))
        self.assertTrue(ok, line)

    def test_month_end_is_last_calendar_day(self):
        self.assertEqual(rf.month_end("2024-02"), date(2024, 2, 29))

    def test_worst_normal_case_just_before_release_is_still_fresh(self):
        # Day before the November JOLTS release: Aug is still newest.
        ok, line = rf.verdict("bls_jolts_cps", self.doc("2026-11-03T00:00:00",
                                                         "2026-08", "2026-09"),
                              today=date(2026, 11, 5))
        self.assertTrue(ok, line)

    def test_stopped_collector_alarms(self):
        ok, line = rf.verdict("bls_jolts_cps", self.doc("2026-09-20T00:00:00+00:00",
                                                         "2026-08", "2026-09"),
                              today=date(2026, 10, 5))
        self.assertFalse(ok)
        self.assertIn("collector", line)

    def test_publisher_lag_past_margin_alarms(self):
        ok, line = rf.verdict("bls_jolts_cps", self.doc("2026-12-01T00:00:00",
                                                         "2026-08", "2026-10"),
                              today=date(2026, 12, 1))
        self.assertFalse(ok)
        self.assertIn("jolts", line)

    def test_nothing_stored_alarms(self):
        ok, _ = rf.verdict("bls_jolts_cps", [], today=date(2026, 10, 5))
        self.assertFalse(ok)


class ArchiveTest(unittest.TestCase):
    def test_listing_keeps_jolts_and_only_the_ln_alldata_file(self):
        html = ('<A HREF="/pub/time.series/ln/ln.series">ln.series</A>'
                '<A HREF="/pub/time.series/ln/ln.data.1.AllData">x</A>'
                '<A HREF="/pub/time.series/ln/ln.data.10.Unemployment">x</A>'
                '<A HREF="/pub/time.series/">[To Parent Directory]</A>')
        self.assertEqual(bls_archive.listing_names(html, "ln"),
                         ["ln.data.1.AllData", "ln.series"])
        html = '<a href="/pub/time.series/jt/jt.data.1.AllItems">x</a>'
        self.assertEqual(bls_archive.listing_names(html, "jt"), ["jt.data.1.AllItems"])

    def test_archive_workflow_uses_a_release_not_a_commit(self):
        with open(os.path.join(REPO, ".github", "workflows", "bls-archive.yml")) as fh:
            wf = fh.read()
        self.assertIn("gh release", wf)
        self.assertNotIn("git push", wf)
        self.assertNotIn("git commit", wf)


class EndpointTest(unittest.TestCase):
    def test_php_allows_only_named_sources(self):
        with open(os.path.join(REPO, "wordpress-plugin", "ai-layoff-tracker",
                               "includes", "reference-data.php")) as fh:
            php = fh.read()
        self.assertIn("'bls_jolts_cps' => 'alt_ref_bls_jolts_cps'", php)
        self.assertIn("alt_api_permission", php)

    def test_every_freshness_source_has_an_endpoint(self):
        with open(os.path.join(REPO, "wordpress-plugin", "ai-layoff-tracker",
                               "includes", "reference-data.php")) as fh:
            php = fh.read()
        for src in rf.SPECS:
            self.assertIn(f"'{src}' =>", php, src)


if __name__ == "__main__":
    unittest.main()
