"""A disclosed removal says which side of the US headline it left from.

The us_all_time incident opened 2026-11-09T17:36Z: the non-US complement
(worldwide minus US) fell 139,443 jobs on +1 entries. TECHLOG 2026-11-10 traced
136,000 of it to three signed trashes of NON-US rows (Microsoft 183020 60,000
country blank, Dax-Konzerne 182248 46,000 "Multiple countries", Bosch 183019
30,000 Germany), but the corrections log said only how many jobs each removal
took, never from which side of the boundary, so ContainmentInvariant could
narrow the FAIL and never place it. Every removal now records `us_jobs` (its
share inside country=United States, country_basis=any), the containment check
subtracts the non-US share from the complement, and one entry without the
figure leaves the FAIL standing.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import data_integrity as di  # noqa: E402
from corrections_reader import DisclosedRemovals  # noqa: E402
import test_corrections_log_job_counts as tcl  # noqa: E402

DB_PHP = tcl.DB_PHP
PHP = shutil.which("php")

# The incident's own readings (railway/headline_incidents.json, open.us_all_time).
BASE = {
    "worldwide_all_time": {"jobs": 20_000_000, "entries": 70000, "excluded_jobs": 0,
                           "excluded_entries": 0, "captured_at": "2026-11-08T17:35:00Z",
                           "recorded_in": "2026-11-08T17:36:13Z"},
    "us_all_time": {"jobs": 7445186, "entries": 47327, "excluded_jobs": 0,
                    "excluded_entries": 0, "captured_at": "2026-11-08T17:35:21Z",
                    "recorded_in": "2026-11-08T17:36:13Z"},
}
OBS = {"worldwide_all_time": {"jobs": 20_000_000 - 165953, "entries": 70006},
       "us_all_time": {"jobs": 7418676, "entries": 47332}}
AT = datetime(2026, 11, 9, 17, 36, 0, tzinfo=timezone.utc)
PAIR = (("us_all_time", "worldwide_all_time"),)

# The three non-US trashes plus the two US ones, as they would now be logged.
PLACED = [
    {"date": "2026-11-09", "action": "removed", "count": 1, "reason": "Microsoft",
     "jobs": 60000, "us_jobs": 0},
    {"date": "2026-11-09", "action": "removed", "count": 1, "reason": "Dax",
     "jobs": 46000, "us_jobs": 0},
    {"date": "2026-11-09", "action": "removed", "count": 1, "reason": "Bosch",
     "jobs": 30000, "us_jobs": 0},
    {"date": "2026-11-09", "action": "removed", "count": 2, "reason": "Nokia, Wells",
     "jobs": 14000, "us_jobs": 14000},
]


class _Ctx(di.Ctx):
    def __init__(self, fetch, disclosed):
        super().__init__(fetch, 5, "cb")
        self._d = disclosed

    def disclosed(self, since_iso):
        return self._d


def _judge(entries):
    d = DisclosedRemovals(consulted=True,
                          rows=sum(e["count"] for e in entries), entries=entries)
    tmp = Path(tempfile.mkdtemp()) / "b.json"
    tmp.write_text(json.dumps({"slices": BASE}), encoding="utf-8")
    from test_headline_containment import _feed
    ctx = _Ctx(_feed(OBS), d)
    return di.ContainmentInvariant(baseline_path=tmp, now=AT, pairs=PAIR).run(ctx)


class TheSplit(unittest.TestCase):
    def test_split_sums_each_side(self):
        d = DisclosedRemovals(consulted=True, rows=5, entries=PLACED)
        self.assertEqual(d.split_by_side("us_jobs"), (14000, 136000))

    def test_one_entry_without_the_share_makes_it_unknowable(self):
        entries = PLACED + [{"action": "merged", "count": 1, "jobs": 500}]
        d = DisclosedRemovals(consulted=True, rows=6, entries=entries)
        self.assertIsNone(d.split_by_side("us_jobs"))

    def test_a_share_larger_than_its_total_is_not_a_measurement(self):
        d = DisclosedRemovals(consulted=True, rows=1, entries=[
            {"action": "removed", "count": 1, "jobs": 10, "us_jobs": 11}])
        self.assertIsNone(d.split_by_side("us_jobs"))


class TheContainmentCheckPlacesThem(unittest.TestCase):
    def test_the_2026_11_09_incident_passes_once_removals_are_placed(self):
        r = _judge(PLACED)
        self.assertEqual(r.state, di.PASS, r.detail)
        self.assertIn("136,000", r.detail)

    def test_unplaced_removals_leave_the_fail_standing(self):
        """The entries as they were actually logged: jobs, no us_jobs."""
        legacy = [{k: v for k, v in e.items() if k != "us_jobs"} for e in PLACED]
        r = _judge(legacy)
        self.assertEqual(r.state, di.FAIL, r.detail)

    def test_removals_that_were_all_us_do_not_explain_a_complement_drop(self):
        wrong_side = [dict(e, us_jobs=e["jobs"]) for e in PLACED]
        r = _judge(wrong_side)
        self.assertEqual(r.state, di.FAIL, r.detail)


class EveryRemovingCallSitePlacesItsJobs(unittest.TestCase):
    def test_trash_undated_and_merge_pass_a_us_share(self):
        t = tcl.EveryRemovingCallSitePassesATotal()
        self.assertIn("$us_removed", t._call("alt_log_correction('removed', array_merge("))
        self.assertIn("$us_removed", t._call("alt_log_correction('removed', $removed,"))
        self.assertIn("$us_merged", t._call("alt_log_correction('merged',"))

    def test_the_us_rule_is_the_headline_rule(self):
        """us_all_time is country=United States, country_basis=any: job
        location OR employer domicile."""
        fn = tcl._php_fn("alt_row_in_us_headline")
        self.assertIn("$country === 'United States'", fn)
        self.assertIn("$employer_country === 'United States'", fn)
        self.assertEqual({h.name: h for h in di.HEADLINES}["us_all_time"].params,
                         {"country": "United States", "country_basis": "any"})


@unittest.skipUnless(PHP, "php is not installed; cannot execute db.php")
class TheWriterRecordsTheShare(unittest.TestCase):
    HARNESS = tcl.PHP_HARNESS.replace(
        "array_key_exists('jobs', $c) ? $c['jobs'] : null);",
        "array_key_exists('jobs', $c) ? $c['jobs'] : null,"
        " array_key_exists('us_jobs', $c) ? $c['us_jobs'] : null);")

    def _run(self, calls):
        bodies = "\n".join(tcl._php_fn(n) for n in
                           ("alt_log_correction", "alt_api_corrections"))
        env = dict(os.environ, ALT_TEST_CALLS=json.dumps(calls))
        proc = subprocess.run([PHP, "-r", (self.HARNESS % bodies).replace("<?php", "", 1)],
                              capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr)
        return json.loads(proc.stdout)

    def test_the_share_is_stored_and_served(self):
        out = self._run([{"action": "removed", "ids": [1], "reason": "r",
                          "jobs": 60000, "us_jobs": 0}])
        self.assertEqual(out["api"]["entries"][0]["us_jobs"], 0)

    def test_absent_share_is_absent_and_collapse_with_one_drops_it(self):
        out = self._run([{"action": "removed", "ids": [1], "reason": "r", "jobs": 5},
                         {"action": "removed", "ids": [2], "reason": "r", "jobs": 5,
                          "us_jobs": 5}])
        self.assertNotIn("us_jobs", out["api"]["entries"][0])

    def test_collapse_adds_shares(self):
        out = self._run([{"action": "removed", "ids": [1], "reason": "r", "jobs": 5,
                          "us_jobs": 2},
                         {"action": "removed", "ids": [2], "reason": "r", "jobs": 7,
                          "us_jobs": 7}])
        self.assertEqual(out["api"]["entries"][0]["us_jobs"], 9)


if __name__ == "__main__":
    unittest.main()
