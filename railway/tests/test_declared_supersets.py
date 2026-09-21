"""A reviewer-DECLARED superset membership survives the reconciler's clean slate.

THE GAP (TECHLOG 2026-09-21). `alt_reconcile_supersets()` zeroes the whole
`superset_of` column on every run and re-marks rows from its own rules, reading
only `edited = 0`. Two independent reviewers ruled that four rows are staged
announcements of ONE programme whose latest size is row 176911, and there was
nowhere to put that: 15,200 jobs stacked on the worldwide headline.

WHAT IS PINNED HERE
  - the pure rules (no chains, no cycles, one primary per member, both rows
    must exist, a trashed primary RELEASES its members and says so);
  - the reconciler itself, run for real against a fake $wpdb: the clean slate
    fires and the declared members come back, whatever `edited` says;
  - THE GUARD IS MUTATION-PROVEN IN THE SUITE: the same scenario is run against
    a copy of db.php with the re-application removed and must come out wrong.
    A guard whose failing branch has never run is a belief;
  - the `superset` action of apply_correction.py and the live invariant, both
    on injected transports. This module opens no connection.

The plugin is not booted: db.php, api.php and the new include load against a
dozen WordPress stubs. Without php on PATH the PHP half SKIPS, which is not a
pass.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "railway"))
PLUGIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker")
INC = os.path.join(PLUGIN, "includes")
PHP = shutil.which("php")

import apply_correction as ac  # noqa: E402
import data_integrity as di  # noqa: E402
from declared_supersets_check import (DeclaredSupersetsInvariant,  # noqa: E402
                                      declared_superset_findings)

HARNESS = r"""<?php
define('ABSPATH', '/'); define('ARRAY_A', 'ARRAY_A');
function add_action() {} function add_filter() {} function add_shortcode() {}
function register_rest_route() {} function register_activation_hook() {}
function delete_transient() {} function do_action() {}
$GLOBALS['opts'] = array();
function get_option($k, $d = false) { return $GLOBALS['opts'][$k] ?? $d; }
function update_option($k, $v) { $GLOBALS['opts'][$k] = $v; return true; }
class FakeDb {
    public $prefix = 'wp_'; public $rows = array(); public $slates = 0;
    function get_results($sql, $fmt = null) {
        $out = array();
        if (strpos($sql, 'edited = 0') !== false) {
            foreach ($this->rows as $r) if (!$r['edited'] && $r['company_key'] !== '' && $r['job_count'] > 0) $out[] = $r;
        } elseif (preg_match('/id IN \(([0-9,]+)\)/', $sql, $m)) {
            foreach (explode(',', $m[1]) as $id) if (isset($this->rows[(int) $id])) $out[] = $this->rows[(int) $id];
        }
        return $out;
    }
    function query($sql) {
        if (strpos($sql, 'SET superset_of = 0') !== false) { $this->slates++; foreach ($this->rows as &$r) $r['superset_of'] = 0; }
        return 1;
    }
    function update($t, $data, $where) {
        $id = (int) $where['id'];
        if (isset($this->rows[$id]) && isset($data['superset_of'])) $this->rows[$id]['superset_of'] = (int) $data['superset_of'];
        return 1;
    }
    function prepare($q) { return $q; } function get_var() { return null; } function get_col() { return array(); }
}
require INC_DB; require INC_DECL; require INC_API;
if (!function_exists('alt_flush_caches')) { function alt_flush_caches() {} }
$in = json_decode(file_get_contents('php://stdin'), true);
$out = array();
if ($in['op'] === 'resolve') {
    $out = alt_declared_supersets_resolve($in['mark'], $in['declared'], $in['live']);
} elseif ($in['op'] === 'validate') {
    $out = array('verdict' => alt_declared_supersets_validate($in['declared'], $in['member'], $in['primary'], $in['rows'], !empty($in['allow'])));
} elseif ($in['op'] === 'reconcile') {
    $wpdb = new FakeDb(); $GLOBALS['wpdb'] = $wpdb;
    foreach ($in['rows'] as $r) $wpdb->rows[(int) $r['id']] = $r;
    $GLOBALS['opts']['alt_declared_supersets'] = $in['declared'];
    $reports = array();
    for ($i = 0; $i < ($in['runs'] ?? 1); $i++) $reports[] = alt_reconcile_supersets(!empty($in['dry']), true);
    $marks = array();
    foreach ($wpdb->rows as $id => $r) $marks[$id] = (int) $r['superset_of'];
    $out = array('marks' => $marks, 'reports' => $reports, 'slates' => $wpdb->slates);
} elseif ($in['op'] === 'key') {
    $out = array('key' => alt_company_key($in['name']));
}
echo json_encode($out);
"""


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _php(payload, db_path=None):
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "h.php")
        src = (HARNESS.replace("INC_DB", json.dumps(db_path or os.path.join(INC, "db.php")))
               .replace("INC_DECL", json.dumps(os.path.join(INC, "declared-supersets.php")))
               .replace("INC_API", json.dumps(os.path.join(INC, "api.php"))))
        with open(script, "w") as fh:
            fh.write(src)
        run = subprocess.run([PHP, "-d", "display_errors=stderr", script],
                             input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    if run.returncode != 0:
        raise AssertionError("php failed: " + run.stderr[-1500:] + run.stdout[-500:])
    return json.loads(run.stdout)


def _row(id_, company, key, jobs, date, st="8K", edited=0, superset_of=0):
    return {"id": id_, "company": company, "company_key": key, "source_type": st,
            "job_count": jobs, "layoff_date": date, "ai_explicit": 0, "state": "",
            "superset_of": superset_of, "edited": edited}


def _programme():
    """The 2026-09-21 shape: an EDITED primary, members the rules cannot relate,
    stale marks the clean slate will erase, plus one automatic pair."""
    k = "estee lauder companies"
    return [
        _row(176911, "ESTEE LAUDER COMPANIES INC", k, 9000, "2026-05-01", edited=1),
        _row(178740, "ESTEE LAUDER COMPANIES INC", k, 5800, "2025-05-01", superset_of=176911),
        _row(178882, "ESTEE LAUDER COMPANIES INC", k, 1800, "2025-02-04", edited=1, superset_of=176911),
        _row(1, "Coinbase", "coinbase", 700, "2026-05-05", st="news"),
        _row(2, "Coinbase", "coinbase", 700, "2026-07-24", st="news"),
    ]


DECLARED = {"178740": {"primary_id": 176911, "reviewer": "two reviewers", "reason": "one programme"},
            "178882": {"primary_id": 176911, "reviewer": "two reviewers", "reason": "one programme"}}


@unittest.skipUnless(PHP, "UNKNOWN, NOT RUN: php is not on PATH")
class PureRules(unittest.TestCase):
    def test_declared_member_is_marked_whatever_the_rules_said(self):
        out = _php({"op": "resolve", "mark": {}, "declared": DECLARED,
                    "live": {"178740": True, "178882": True, "176911": True}})
        self.assertEqual(out["mark"], {"178740": 176911, "178882": 176911})
        self.assertEqual(out["released"], [])

    def test_a_trashed_primary_releases_its_members_and_says_so(self):
        out = _php({"op": "resolve", "mark": {}, "declared": DECLARED,
                    "live": {"178740": True, "178882": True}})
        self.assertEqual(out["mark"], [])
        self.assertEqual(len(out["released"]), 2)
        self.assertIn("primary row no longer exists", out["released"][0]["why"])

    def test_a_trashed_member_is_released_not_written(self):
        out = _php({"op": "resolve", "mark": {}, "declared": DECLARED,
                    "live": {"178740": True, "176911": True}})
        self.assertEqual(out["mark"], {"178740": 176911})
        self.assertIn("member row no longer exists", out["released"][0]["why"])

    def test_a_declared_primary_is_never_left_a_member(self):
        out = _php({"op": "resolve", "mark": {"176911": 5}, "declared": DECLARED,
                    "live": {"178740": True, "178882": True, "176911": True}})
        self.assertNotIn("176911", out["mark"])
        self.assertEqual(out["primary_unmarked"], [{"primary_id": 176911, "was_member_of": 5}])

    def test_an_automatic_mark_pointing_at_a_member_is_repointed_no_chain(self):
        out = _php({"op": "resolve", "mark": {"9": 178740}, "declared": DECLARED,
                    "live": {"178740": True, "178882": True, "176911": True}})
        self.assertEqual(out["mark"]["9"], 176911)

    def test_a_stored_chain_is_released_by_the_second_lock(self):
        declared = dict(DECLARED, **{"176911": {"primary_id": 5}})
        out = _php({"op": "resolve", "mark": {}, "declared": declared,
                    "live": {"178740": True, "178882": True, "176911": True, "5": True}})
        self.assertEqual(out["mark"], {"176911": 5})
        self.assertTrue(all("chain" in r["why"] for r in out["released"]))

    def _v(self, declared, member, primary, rows, allow=False):
        return _php({"op": "validate", "declared": declared, "member": member,
                     "primary": primary, "rows": rows, "allow": allow})["verdict"]

    def test_validation(self):
        rows = {"10": {"company_key": "a"}, "11": {"company_key": "a"},
                "12": {"company_key": "b"}, "13": {"company_key": "a"}}
        self.assertEqual(self._v({}, 10, 11, rows), "")
        self.assertIn("itself", self._v({}, 10, 10, rows))
        self.assertIn("does not exist", self._v({}, 99, 11, rows))
        self.assertIn("does not exist", self._v({}, 10, 99, rows))
        held = {"10": {"primary_id": 11}}
        self.assertEqual(self._v(held, 10, 11, rows), "unchanged")
        self.assertIn("already has primary 11", self._v(held, 10, 13, rows))
        self.assertIn("no chains", self._v(held, 13, 10, rows), "a member cannot become a primary")
        self.assertIn("no chains", self._v(held, 11, 13, rows), "a primary cannot become a member")
        self.assertIn("company keys differ", self._v({}, 12, 11, rows))
        self.assertEqual(self._v({}, 12, 11, rows, allow=True), "")

    def test_the_live_rows_really_do_key_differently(self):
        """Why the override exists at all: the accented spelling keys apart."""
        a = _php({"op": "key", "name": "ESTEE LAUDER COMPANIES INC"})["key"]
        b = _php({"op": "key", "name": "Estée Lauder"})["key"]
        self.assertNotEqual(a, b)


@unittest.skipUnless(PHP, "UNKNOWN, NOT RUN: php is not on PATH")
class TheReconcilerReappliesThem(unittest.TestCase):
    def test_clean_slate_then_declared_members_come_back(self):
        out = _php({"op": "reconcile", "rows": _programme(), "declared": DECLARED, "runs": 2})
        self.assertEqual(out["slates"], 2, "the clean slate must still run")
        m = out["marks"]
        self.assertEqual(m["178740"], 176911)
        self.assertEqual(m["178882"], 176911, "an EDITED member is re-applied too")
        self.assertEqual(m["176911"], 0)
        self.assertEqual(m["2"], 1, "the automatic rules are untouched")
        first, second = out["reports"]
        self.assertEqual(first["declared"]["jobs_excluded"], 7600)
        self.assertEqual(len(first["declared"]["applied"]), 2)
        self.assertEqual(second["changes"], 0, "idempotent")

    def test_dry_run_shows_an_edited_member_in_the_diff_and_writes_nothing(self):
        rows = _programme()
        for r in rows:
            r["superset_of"] = 0
        out = _php({"op": "reconcile", "rows": rows, "declared": DECLARED, "dry": True})
        self.assertEqual(out["slates"], 0)
        self.assertEqual(out["marks"]["178882"], 0)
        changed = {c["id"]: c["now"] for c in out["reports"][0]["changed"]}
        self.assertEqual(changed.get(178882), 176911)
        self.assertEqual(changed.get(178740), 176911)

    def test_a_trashed_primary_releases_and_the_report_names_it(self):
        rows = [r for r in _programme() if r["id"] != 176911]
        out = _php({"op": "reconcile", "rows": rows, "declared": DECLARED})
        self.assertEqual(out["marks"]["178740"], 0)
        self.assertEqual(out["marks"]["178882"], 0)
        released = out["reports"][0]["declared"]["released"]
        self.assertEqual({r["member_id"] for r in released}, {178740, 178882})

    def test_no_declarations_is_the_old_behaviour(self):
        out = _php({"op": "reconcile", "rows": _programme(), "declared": []})
        self.assertEqual(out["marks"]["178740"], 0)
        self.assertEqual(out["marks"]["2"], 1)

    def test_MUTATION_without_the_reapplication_this_suite_goes_red(self):
        """Remove the one line that hands the declared marks to the write loop
        and the scenario above must come out WRONG. If this ever passes on the
        mutant, the guard above is decoration."""
        src = _read(os.path.join(INC, "db.php"))
        needle = "$mark = $res['mark'];"
        self.assertEqual(src.count(needle), 1, "the re-application line moved; re-aim the mutation")
        with tempfile.TemporaryDirectory() as tmp:
            mutant = os.path.join(tmp, "db.php")
            with open(mutant, "w", encoding="utf-8") as fh:
                fh.write(src.replace(needle, ""))
            out = _php({"op": "reconcile", "rows": _programme(), "declared": DECLARED}, db_path=mutant)
        self.assertEqual(out["marks"]["178740"], 0, "the mutant must lose the member")
        self.assertEqual(out["marks"]["178882"], 0)


class Wiring(unittest.TestCase):
    def test_include_is_guarded_and_db_calls_it_behind_function_exists(self):
        entry = _read(os.path.join(PLUGIN, "ai-layoff-tracker.php"))
        self.assertIn("is_readable($alt_declared_supersets)", entry)
        db = _read(os.path.join(INC, "db.php"))
        body = db[db.index("function alt_reconcile_supersets("):db.index("function alt_api_reconcile_supersets(")]
        call = body.index("alt_declared_supersets_resolve(")
        self.assertIn("function_exists('alt_declared_supersets_resolve')", body)
        self.assertLess(body.index("within-WARN duplicate"), call, "declared memberships are applied LAST")
        self.assertLess(call, body.index("SET superset_of = 0"), "and before the single write loop")
        self.assertEqual(body.count("SET superset_of = 0"), 1)

    def test_write_route_is_keyed_and_defaults_to_a_dry_run(self):
        src = _read(os.path.join(INC, "declared-supersets.php"))
        route = src[src.index("'/declare-superset'"):src.index("'/declared-supersets'")]
        self.assertIn("alt_api_permission", route)
        self.assertIn("'__return_false'", route)
        self.assertIn("$apply  = (string) $r->get_param('apply') === '1';", src)

    def test_workflow_offers_the_action(self):
        wf = _read(os.path.join(ROOT, ".github", "workflows", "apply-correction.yml"))
        self.assertIn("restore-merged, superset]", wf)


ROWS = {"data": [
    {"id": 176911, "company_name": "ESTEE LAUDER COMPANIES INC", "job_count": 9000},
    {"id": 178740, "company_name": "ESTEE LAUDER COMPANIES INC", "job_count": 5800},
    {"id": 62215, "company_name": "Estée Lauder", "job_count": 5800},
]}


class _Resp:
    def __init__(self, body, status=200):
        self._b, self.status_code, self.text = body, status, json.dumps(body)
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._b


def _fake_get(url, params=None, **kw):
    assert "User-Agent" in kw.get("headers", {})
    if url.endswith("/query"):
        assert "q" in params and "company" not in params
        return _Resp(ROWS)
    if url.endswith("/aggregate"):
        return _Resp({"totals": {"jobs": 1000000, "entries": 500}})
    raise AssertionError("unexpected GET " + url)


class ToolAction(unittest.TestCase):
    def _run(self, ids, fields, apply, post, company="Lauder", key="k"):
        buf = io.StringIO()
        with mock.patch.object(ac.requests, "get", _fake_get), \
             mock.patch.object(ac.requests, "post", post), \
             mock.patch.object(ac.time, "sleep", lambda *_: None), redirect_stdout(buf):
            rc = ac.run_superset("https://x/blog", key, ids, fields, "ruling", company, apply)
        return rc, buf.getvalue()

    def test_dry_run_asks_the_server_with_apply_0(self):
        seen = {}

        def post(url, json=None, headers=None, **kw):
            seen.update(json=json, url=url, headers=headers)
            return _Resp({"dry_run": True, "declared": [178740], "unchanged": [], "rejected": [], "jobs_moved": 5800})
        rc, out = self._run([178740], {"primary": 176911}, False, post)
        self.assertEqual(rc, 0)
        self.assertEqual(seen["json"]["apply"], "0")
        self.assertEqual(seen["json"]["allow_key_mismatch"], "0")
        self.assertTrue(seen["url"].endswith("/declare-superset"))
        self.assertIn("X-Layoff-API-Key", seen["headers"])
        self.assertIn("-5,800", out)
        self.assertIn("DRY RUN", out)

    def test_a_typoed_id_never_reaches_the_server(self):
        rc, out = self._run([178741], {"primary": 176911}, True,
                            mock.Mock(side_effect=AssertionError("POSTed a typo")))
        self.assertEqual(rc, 1)
        self.assertIn("178741", out)

    def test_verify_company_is_required_and_primary_cannot_be_a_member(self):
        boom = mock.Mock(side_effect=AssertionError("POSTed"))
        self.assertEqual(self._run([178740], {"primary": 176911}, True, boom, company="")[0], 1)
        self.assertEqual(self._run([176911], {"primary": 176911}, True, boom)[0], 1)
        self.assertEqual(self._run([178740], {}, True, boom)[0], 1)

    def test_a_server_refusal_is_a_red_run(self):
        def post(*a, **kw):
            return _Resp({"dry_run": True, "declared": [], "rejected": [{"id": 62215, "reason": "company keys differ"}]})
        rc, out = self._run([62215], {"primary": 176911}, True, post)
        self.assertEqual(rc, 1)
        self.assertIn("company keys differ", out)

    def test_override_is_explicit_and_forwarded(self):
        seen = {}

        def post(url, json=None, **kw):
            seen.update(json)
            return _Resp({"dry_run": False, "declared": [62215], "unchanged": [], "rejected": [], "jobs_moved": 5800})
        rc, _ = self._run([62215], {"primary": 176911, "allow_key_mismatch": True}, True, post)
        self.assertEqual(rc, 0)
        self.assertEqual(seen["allow_key_mismatch"], "1")
        self.assertEqual(seen["apply"], "1")

    def test_apply_answered_as_dry_run_is_red(self):
        def post(*a, **kw):
            return _Resp({"dry_run": True, "declared": [178740], "rejected": [], "jobs_moved": 5800})
        self.assertEqual(self._run([178740], {"primary": 176911}, True, post)[0], 1)

    def test_an_unread_query_is_unknown_and_sends_nothing(self):
        buf = io.StringIO()
        with mock.patch.object(ac.requests, "get", mock.Mock(side_effect=OSError("down"))), \
             mock.patch.object(ac.requests, "post", mock.Mock(side_effect=AssertionError("POSTed"))), \
             redirect_stdout(buf):
            rc = ac.run_superset("https://x/blog", "k", [178740], {"primary": 176911}, "r", "Lauder", True)
        self.assertEqual(rc, 1)
        self.assertIn("UNKNOWN", buf.getvalue())


def _decl(member=178740, primary=176911, **over):
    d = {"member_id": member, "primary_id": primary, "member_exists": True, "primary_exists": True,
         "member_superset_of": primary, "primary_superset_of": 0, "member_job_count": 5800}
    d.update(over)
    return d


def _ctx(body=None, exc=None):
    def fetch(url, timeout):
        assert "declared-supersets?" in url and "cb=" in url
        if exc:
            raise exc
        return json.dumps(body).encode()
    return di.Ctx(fetch, 5, "cb1")


class Invariant(unittest.TestCase):
    inv = DeclaredSupersetsInvariant()

    def test_registered_once_in_the_one_registry(self):
        keys = [i.key for i in di.INVARIANTS]
        self.assertEqual(keys.count("declared_supersets_reflected"), 1)
        self.assertTrue(self.inv.reads_live_data)
        self.assertIs(di.declared_superset_findings, declared_superset_findings)

    def test_pass(self):
        r = self.inv.run(_ctx({"count": 1, "declarations": [_decl()]}))
        self.assertEqual(r.state, di.PASS)
        self.assertIn("5,800", r.detail)

    def test_fail_when_the_mark_is_missing(self):
        r = self.inv.run(_ctx({"count": 1, "declarations": [_decl(member_superset_of=0)]}))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("178740", r.detail)

    def test_fail_on_missing_primary_and_on_chain(self):
        for d in (_decl(primary_exists=False, member_superset_of=0), _decl(primary_superset_of=9),
                  _decl(member_exists=False, member_superset_of=None)):
            self.assertEqual(self.inv.run(_ctx({"count": 1, "declarations": [d]})).state, di.FAIL)

    def test_empty_store_passes_in_words(self):
        r = self.inv.run(_ctx({"count": 0, "declarations": []}))
        self.assertEqual(r.state, di.PASS)
        self.assertIn("0 declarations", r.detail)

    def test_no_read_is_unknown_never_a_pass(self):
        for ctx in (_ctx(exc=OSError("down")), _ctx({"nope": 1}), _ctx([]),
                    _ctx({"count": 2, "declarations": [_decl()]})):
            self.assertEqual(self.inv.run(ctx).state, di.UNKNOWN)
        err = urllib.error.HTTPError("u", 404, "nf", {}, None)
        r = self.inv.run(_ctx(exc=err))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertTrue(r.pending)


if __name__ == "__main__":
    unittest.main()
