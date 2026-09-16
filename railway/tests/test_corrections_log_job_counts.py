"""The corrections log records how many JOBS left, and absent is never zero.

WHY THIS EXISTS. On 2026-09-12 `headline_movement` opened two incidents. The
worldwide all-time figure fell 87,685 jobs in a day and the AI figure fell
30,000. Both were fully explained by two deliberate, correct removals that the
site had already disclosed: an Amazon row of 30,000 (row 179276, removed by
two-model adjudication) and a Grupo Volkswagen row of 60,000, against +2,315
jobs of genuine new entries on +8 entries. -90,000 + 2,315 is exactly the
observed -87,685, with nothing left over.

The guard could not reach that conclusion, and said so in its own words:

    "the corrections log discloses 2 row(s) removed or merged in this window,
     which is a CANDIDATE explanation and not a verdict (the log records rows,
     never their job counts)"

So every branch went red, a merged PR was blocked, and a human was woken to run
a close command for a defect that did not exist. The log recorded an action, a
row COUNT, a reason and a detail, and never how many jobs the rows carried.

THE RULE THESE TESTS DEFEND, and the one that is easy to get wrong while
"fixing" the above: **an absent jobs figure means UNKNOWN, never zero.** A
reader that defaults a missing figure to 0 would "account for" a removal with
zero jobs and produce a confident WRONG verdict, which is worse than today's
honest refusal. Historical entries carry no figure and must stay UNKNOWN
forever; a window holding one of them is UNJUDGED, not clean.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity as di
from corrections_reader import DisclosedRemovals, entry_jobs, fetch_removals

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin/ai-layoff-tracker"
DB_PHP = (PLUGIN / "includes/db.php").read_text()
TRACKER_TPL = (PLUGIN / "templates/page-tracker.php").read_text()
PHP = shutil.which("php")


def _opener(payload):
    def _open(req, timeout=None):
        class _R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _R(json.dumps(payload).encode())

    return _open


#: The real 2026-09-12 window, as the log would carry it after this change.
THE_NIGHT = {
    "entries": [
        {"date": "2026-09-12", "action": "removed", "count": 1, "jobs": 30000,
         "reason": "Two-model adjudication: Amazon row overstated the announced cut"},
        {"date": "2026-09-12", "action": "removed", "count": 1, "jobs": 60000,
         "reason": "Two-model adjudication: Grupo Volkswagen row duplicated a group total"},
        {"date": "2026-09-12", "action": "enriched", "count": 200, "jobs": 0,
         "reason": "Automated industry classification"},
    ]
}


# ---------------------------------------------------------------------------
# THE READER: absent is UNKNOWN, zero is zero
# ---------------------------------------------------------------------------


class AbsentIsNeverZero(unittest.TestCase):

    def test_an_entry_with_no_jobs_key_is_unmeasured(self):
        """Mutation guard: `int(e.get("jobs") or 0)` makes this fail, because a
        historical entry would then read as a removal of nothing."""
        self.assertIsNone(entry_jobs({"action": "removed", "count": 3}))

    def test_an_entry_with_jobs_zero_is_measured_and_is_zero(self):
        """A removal of rows that carried no headcount is a real, measured 0.
        Collapsing it into the absent case would throw away a true reading."""
        self.assertEqual(entry_jobs({"action": "removed", "count": 3, "jobs": 0}), 0)

    def test_a_null_or_unparsable_jobs_figure_is_unmeasured(self):
        for bad in (None, "", "lots", -5, [1]):
            with self.subTest(bad=bad):
                self.assertIsNone(entry_jobs({"jobs": bad}))

    def test_measured_jobs_excludes_the_unmeasured_and_the_non_removing(self):
        r = fetch_removals("https://e.test/blog", "2026-09-12", opener=_opener(THE_NIGHT))
        self.assertEqual(r.rows, 2)
        self.assertEqual(r.measured_jobs, 90000,
                         "the 200 enriched rows are not a removal and carry no jobs out")
        self.assertEqual(r.unmeasured, [])
        self.assertTrue(r.jobs_accounted)

    def test_one_unmeasured_removal_makes_the_whole_window_unaccountable(self):
        log = {"entries": [
            dict(THE_NIGHT["entries"][0]),
            {"date": "2026-09-12", "action": "merged", "count": 4,
             "reason": "Daily cross-source dedup"},
        ]}
        r = fetch_removals("https://e.test/blog", "2026-09-12", opener=_opener(log))
        self.assertEqual(r.measured_jobs, 30000)
        self.assertEqual(len(r.unmeasured), 1)
        self.assertFalse(r.jobs_accounted,
                         "a partially measured window must not look complete")

    def test_an_unreachable_log_is_not_an_accounted_one(self):
        def _boom(req, timeout=None):
            raise urllib.error.URLError("no route to host")

        r = fetch_removals("https://e.test/blog", "2026-09-12", opener=_boom)
        self.assertFalse(r.jobs_accounted)
        self.assertEqual(r.measured_jobs, 0)

    def test_the_summary_states_the_jobs_when_it_has_them(self):
        text = fetch_removals("https://e.test/blog", "2026-09-12",
                              opener=_opener(THE_NIGHT)).summary()
        self.assertIn("90,000", text)

    def test_the_summary_says_unknown_when_a_figure_is_missing(self):
        log = {"entries": [{"date": "2026-09-12", "action": "merged", "count": 4,
                            "reason": "Daily cross-source dedup"}]}
        text = fetch_removals("https://e.test/blog", "2026-09-12", opener=_opener(log)).summary()
        self.assertIn("UNKNOWN", text)
        self.assertNotIn("0 job", text, "an unmeasured entry must not be worded as zero")


# ---------------------------------------------------------------------------
# THE ARITHMETIC: three outcomes, and a partial window is not one of them
# ---------------------------------------------------------------------------


def _disclosed(entries, consulted=True):
    rows = sum(max(0, int(e.get("count") or 0)) for e in entries)
    return DisclosedRemovals(consulted=consulted, rows=rows, entries=list(entries))


class TheAccounting(unittest.TestCase):
    """di.account_for_disclosures(disclosed, d_jobs, d_entries, floor, base_mean,
    mean_factor) -> (state, line); state None means the FAIL stands."""

    # The real numbers of 2026-09-12, worldwide all-time.
    D_JOBS, D_ENTRIES = -87685, 8
    FLOOR, BASE_MEAN, MEAN_FACTOR = 20000.0, 160.787, 12

    def _run(self, disclosed, d_jobs=None):
        return di.account_for_disclosures(
            disclosed, self.D_JOBS if d_jobs is None else d_jobs, self.D_ENTRIES,
            self.FLOOR, self.BASE_MEAN, self.MEAN_FACTOR)

    def test_the_night_of_2026_09_12_is_fully_accounted_for(self):
        state, line = self._run(_disclosed(THE_NIGHT["entries"][:2]))
        self.assertEqual(state, di.PASS)
        self.assertIn("90,000", line)
        self.assertIn("+2,315", line)

    def test_accounting_that_does_not_close_leaves_the_fail_standing(self):
        """The guard has to be able to still fail. Disclose only the Amazon row
        and 57,685 jobs are unexplained: that is a FAIL, not a rounding."""
        state, line = self._run(_disclosed(THE_NIGHT["entries"][:1]))
        self.assertIsNone(state, "a short disclosure must not clear the check")
        self.assertIn("57,685", line)

    def test_a_window_with_an_unmeasured_entry_is_unknown_not_pass(self):
        """The rule this whole change turns on. The two measured removals would
        settle the movement on their own; a third entry with NO jobs figure
        means the accounting cannot be completed, so the verdict is UNKNOWN and
        the unmeasured entry is named."""
        entries = THE_NIGHT["entries"][:2] + [
            {"date": "2026-09-12", "action": "merged", "count": 4,
             "reason": "Daily cross-source dedup"}]
        state, line = self._run(_disclosed(entries))
        self.assertEqual(state, di.UNKNOWN)
        self.assertIn("cross-source dedup", line)

    def test_an_unreachable_log_leaves_the_fail_standing(self):
        state, _ = self._run(DisclosedRemovals(consulted=False, error="unreachable: x"))
        self.assertIsNone(state)

    def test_an_empty_window_leaves_the_fail_standing(self):
        state, _ = self._run(_disclosed([]))
        self.assertIsNone(state)

    def test_a_removal_cannot_explain_a_rise(self):
        """Removals take jobs out. A headline that ROSE 87,685 while 90,000 jobs
        were removed is further from explained, not closer."""
        state, _ = self._run(_disclosed(THE_NIGHT["entries"][:2]), d_jobs=87685)
        self.assertIsNone(state)


class TheMovementGuardUsesIt(unittest.TestCase):
    """End to end through MovementInvariant, with the log injected."""

    HEADLINES = (di.Headline(name="one", label="One", params={}, max_share=0.90,
                             move_floor=20000, mean_factor=12),)

    def _run(self, disclosed, jobs=347942, prior_jobs=435627):
        body = json.dumps({
            "totals": {"jobs": jobs, "entries": 2716},
            "concentration": {"largest_row_jobs": 30000, "largest_row_company": "X",
                              "largest_row_id": 1, "headline_jobs": jobs,
                              "headline_entries": 2716},
        }).encode()
        ctx = di.Ctx(lambda url, timeout: body, 5, "cb")
        import tempfile
        from datetime import datetime, timedelta, timezone
        captured = (datetime.now(timezone.utc) - timedelta(days=1.0)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        with tempfile.TemporaryDirectory() as d:
            bp = Path(d) / "b.json"
            bp.write_text(json.dumps({"slices": {"one": {
                "jobs": prior_jobs, "entries": 2708, "captured_at": captured}}}))
            ip = Path(d) / "i.json"
            ip.write_text(json.dumps({"open": {}}))
            inv = di.MovementInvariant(self.HEADLINES, baseline_path=bp,
                                       incidents_path=ip,
                                       disclosed=lambda since: disclosed)
            return inv.run(ctx)

    def test_the_incident_of_2026_09_12_would_not_have_opened(self):
        r = self._run(_disclosed(THE_NIGHT["entries"][:2]))
        self.assertEqual(r.state, di.PASS, r.detail)

    def test_an_unexplained_move_still_fails(self):
        r = self._run(_disclosed([]))
        self.assertEqual(r.state, di.FAIL, r.detail)

    def test_an_unmeasured_entry_gives_unknown_and_records_nothing(self):
        r = self._run(_disclosed([
            {"date": "2026-09-12", "action": "merged", "count": 4,
             "reason": "Daily cross-source dedup"}]))
        self.assertEqual(r.state, di.UNKNOWN, r.detail)


# ---------------------------------------------------------------------------
# THE WRITER: executed, not grepped
# ---------------------------------------------------------------------------

PHP_HARNESS = r"""
<?php
$GLOBALS['OPTIONS'] = array();
function get_option($k, $d = false) { return $GLOBALS['OPTIONS'][$k] ?? $d; }
function update_option($k, $v, $a = false) { $GLOBALS['OPTIONS'][$k] = $v; return true; }
function rest_ensure_response($x) { return new AltTestResponse($x); }
class AltTestResponse { public $d; function __construct($d) { $this->d = $d; } function get_data() { return $this->d; } }
class WP_REST_Request { public $p; function __construct($p) { $this->p = $p; } function get_param($k) { return $this->p[$k] ?? null; } }
%s
foreach (json_decode(getenv('ALT_TEST_CALLS'), true) as $c) {
    alt_log_correction($c['action'], $c['ids'], $c['reason'], $c['detail'] ?? '',
        array_key_exists('jobs', $c) ? $c['jobs'] : null);
}
echo json_encode(array(
    'log' => $GLOBALS['OPTIONS']['alt_corrections_log'],
    'api' => alt_api_corrections(new WP_REST_Request(array('since' => '')))->get_data(),
));
"""


def _php_fn(name):
    needle = "function %s(" % name
    start = DB_PHP.find(needle)
    assert start != -1, "db.php has no `%s`" % needle
    i = DB_PHP.index("{", start)
    depth, j = 0, i
    while j < len(DB_PHP):
        if DB_PHP[j] == "{":
            depth += 1
        elif DB_PHP[j] == "}":
            depth -= 1
            if depth == 0:
                return DB_PHP[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


@unittest.skipUnless(PHP, "php is not installed; cannot execute db.php")
class TheWriterKeepsAbsentAbsent(unittest.TestCase):

    def _run(self, calls):
        bodies = "\n".join((_php_fn("alt_log_correction"), _php_fn("alt_api_corrections")))
        env = dict(os.environ, ALT_TEST_CALLS=json.dumps(calls))
        proc = subprocess.run([PHP, "-r", (PHP_HARNESS % bodies).replace("<?php", "", 1)],
                              capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise AssertionError("php failed:\n%s" % proc.stderr.strip())
        return json.loads(proc.stdout)

    def test_a_removal_records_the_jobs_it_took_out(self):
        out = self._run([{"action": "removed", "ids": [179276], "reason": "Amazon",
                          "jobs": 30000}])
        self.assertEqual(out["log"][0]["jobs"], 30000)
        self.assertEqual(out["api"]["entries"][0]["jobs"], 30000)

    def test_an_unmeasured_call_writes_no_jobs_key_at_all(self):
        """Not 0. The API must omit the field, so the reader reads UNKNOWN."""
        out = self._run([{"action": "enriched", "ids": [1, 2], "reason": "Industry"}])
        self.assertNotIn("jobs", out["log"][0])
        self.assertNotIn("jobs", out["api"]["entries"][0],
                         "an absent figure serialised as 0 is a confident wrong verdict")

    def test_a_measured_zero_survives_as_zero(self):
        out = self._run([{"action": "removed", "ids": [7], "reason": "no headcount",
                          "jobs": 0}])
        self.assertEqual(out["log"][0]["jobs"], 0)
        self.assertEqual(out["api"]["entries"][0]["jobs"], 0)

    def test_same_day_collapse_adds_the_jobs_up(self):
        calls = [{"action": "removed", "ids": [1], "reason": "dedupe", "jobs": 30000},
                 {"action": "removed", "ids": [2], "reason": "dedupe", "jobs": 60000}]
        out = self._run(calls)
        self.assertEqual(len(out["log"]), 1)
        self.assertEqual(out["log"][0]["count"], 2)
        self.assertEqual(out["log"][0]["jobs"], 90000)

    def test_collapsing_a_measured_entry_with_an_unmeasured_one_yields_unknown(self):
        """The collapse is the one place zero can be manufactured. A measured
        30,000 plus an unmeasured call is not 30,000 removed; it is unknown."""
        for calls in (
            [{"action": "removed", "ids": [1], "reason": "d", "jobs": 30000},
             {"action": "removed", "ids": [2], "reason": "d"}],
            [{"action": "removed", "ids": [1], "reason": "d"},
             {"action": "removed", "ids": [2], "reason": "d", "jobs": 30000}],
        ):
            with self.subTest(order=calls[0].get("jobs")):
                out = self._run(calls)
                self.assertEqual(len(out["log"]), 1)
                self.assertNotIn("jobs", out["log"][0])
                self.assertNotIn("jobs", out["api"]["entries"][0])


class EveryRemovingCallSitePassesATotal(unittest.TestCase):
    """Source-level, because the call sites live inside REST handlers that need
    a database. A removing call that passes nothing is the silent regression."""

    def _call(self, needle):
        i = DB_PHP.find(needle)
        self.assertNotEqual(i, -1, "db.php no longer has %r" % needle)
        depth, j, out = 0, DB_PHP.index("(", i), []
        while j < len(DB_PHP):
            out.append(DB_PHP[j])
            if DB_PHP[j] == "(":
                depth += 1
            elif DB_PHP[j] == ")":
                depth -= 1
                if depth == 0:
                    return "".join(out)
            j += 1
        raise AssertionError("unbalanced parens at %r" % needle)

    def test_the_trash_endpoint_discloses_its_job_total(self):
        call = self._call("alt_log_correction('removed', array_merge(")
        self.assertIn("jobs", call)

    def test_the_undated_cleanup_discloses_its_job_total(self):
        call = self._call("alt_log_correction('removed', $removed,")
        self.assertIn("jobs", call)

    def test_the_merge_endpoint_discloses_its_job_total(self):
        """As the ARGUMENT, not only inside the human-readable detail string.
        The detail has named net_jobs_removed since the endpoint shipped, and a
        sentence is not a field a guard can subtract."""
        call = self._call("alt_log_correction('merged',")
        self.assertTrue(call.rstrip().endswith("$out['net_jobs_removed'])"),
                        "the merged call must pass the job total last: %s" % call)

    def test_an_enrichment_pass_discloses_nothing(self):
        """Enrichment moves no jobs. Passing 0 there would be a measurement we
        never took."""
        call = self._call("alt_log_correction('reclassified',")
        self.assertNotIn("jobs", call)

    def test_the_undated_cleanup_reads_job_count_before_it_deletes(self):
        i = DB_PHP.find("function alt_dedup_undated_cleanup(")
        body = DB_PHP[i:i + 2000]
        self.assertIn("a.job_count", body,
                      "the rows are gone after the delete; the sum has to be taken first")


class AnOfflineRunNeverReadsTheLiveHost(unittest.TestCase):
    """Found while writing the above, and worth its own assertion.

    `ContainmentInvariant` called the live /corrections endpoint straight out of
    its FAIL branch, so nine OFFLINE unit tests issued real requests to
    asktherecruiter.com on every run of the suite, unattended, from every
    contributor's machine and every CI leg. Request volume from one machine is
    what tripped the host's bot protection in September. A ctx built on an
    injected transport now reports the log as NOT CONSULTED, which is the safe
    answer at both call sites: it is printed as UNKNOWN and it clears nothing.
    """

    def test_an_injected_transport_does_not_reach_for_the_production_log(self):
        ctx = di.Ctx(lambda url, timeout: b"{}", 5, "cb")
        d = ctx.disclosed("2026-09-12T00:00:00Z")
        self.assertFalse(d.consulted)
        self.assertFalse(d.jobs_accounted)
        self.assertIn("UNKNOWN", d.summary())

    def test_it_clears_nothing(self):
        ctx = di.Ctx(lambda url, timeout: b"{}", 5, "cb")
        state, _ = di.account_for_disclosures(
            ctx.disclosed("2026-09-12"), -87685, 8, 20000.0, 160.787, 12)
        self.assertIsNone(state, "an unconsulted log must leave the FAIL standing")


class TheReaderSurfaceIsHonest(unittest.TestCase):

    def test_the_page_only_prints_a_jobs_figure_when_there_is_one(self):
        i = TRACKER_TPL.find("alt-corrections-scroll")
        block = TRACKER_TPL[i:i + 4000]
        self.assertIn("array_key_exists('jobs'", block,
                      "the page must test for the key, not for truthiness: a "
                      "measured 0 is a figure and an absent one is not a 0")


if __name__ == "__main__":
    unittest.main()
