"""A removal that suppresses nothing is undone by the next import.

WRITTEN FROM A LIVE INSTANCE. Row 177216 (4,320 "jobs" read out of an Adjusted
EBITDA reconciliation headed "in thousands, except percentages") was removed on
2026-09-07 and is live again today, unedited, with a permalink.

THE MECHANISM IS IN THE HANDLER'S OWN SHAPE. `alt_api_trash` accepts three id
spaces and only ONE of them suppressed the removed row's dedup hash. The daily
imports re-scrape the same source data, so anything removed through the other
two comes back on the next run. The response said nothing: it carried
`suppressed: 0`, which is also what a legitimate removal of a hashless row
reports, so an unprotected removal and an ordinary one were indistinguishable
from outside.

These tests run the REAL handler, lifted out of db.php, against stubs for the
three things it touches (the row store, the option store, wp_trash_post). They
are about which rows reach the suppression list, so the stubs record calls and
decide nothing.

Without php on PATH the whole module SKIPS, which is UNKNOWN and not a pass.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes", "db.php")
PHP = shutil.which("php")

LIFT = ("alt_trash_suppress", "alt_api_trash")


def _lift(name):
    src = open(DB, encoding="utf-8").read()
    start = src.index("function %s(" % name)
    i = src.index("{", start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise AssertionError("unbalanced braces in " + name)


HARNESS = r"""<?php
// The three things the handler touches, and nothing else. Each records what it
// was asked to do and decides nothing.
$ROWS = json_decode($argv[1], true);
$SUPPRESSED = array();
$TRASHED_POSTS = array();

class FakeWpdb {
    public $rows;
    function __construct($rows) { $this->rows = $rows; }
    function prepare($sql, ...$a) { return array($sql, $a); }
    function get_row($q) {
        list($sql, $a) = $q;
        foreach ($this->rows as $r) {
            if (strpos($sql, 'WHERE post_id =') !== false) {
                if ((int) $r['post_id'] === (int) $a[0]) return (object) $r;
            } elseif (strpos($sql, 'post_id IS NULL') !== false) {
                if ((int) $r['id'] === (int) $a[0] && !$r['post_id']) return (object) $r;
            } elseif ((int) $r['id'] === (int) $a[0]) {
                return (object) $r;
            }
        }
        return null;
    }
    function get_var($q) { $r = $this->get_row($q); return $r ? $r->job_count : null; }
    function delete($t, $where) {
        foreach ($this->rows as $k => $r) {
            if ((int) $r['id'] === (int) $where['id']) {
                if (array_key_exists('post_id', $where) && $where['post_id'] === null
                    && $r['post_id']) return 0;
                unset($this->rows[$k]);
                return 1;
            }
        }
        return 0;
    }
}
$wpdb = new FakeWpdb($ROWS);

function alt_db_table() { return 'wp_alt_layoffs'; }
function alt_suppress_hash($h, $reason) { global $SUPPRESSED; $SUPPRESSED[$h] = $reason; }
function wp_trash_post($pid) { global $TRASHED_POSTS, $wpdb; $TRASHED_POSTS[] = (int) $pid;
    foreach ($wpdb->rows as $k => $r) if ((int) $r['post_id'] === (int) $pid) unset($wpdb->rows[$k]); }
function get_post_type($pid) { return 'layoffs'; }
function alt_cleanup_orphan_event($eid) { return false; }
function alt_log_correction(...$a) {}
function rest_ensure_response($x) { return $x; }

class WP_REST_Request {
    public $p;
    function __construct($p) { $this->p = $p; }
    function get_param($k) { return $this->p[$k] ?? null; }
}

%s

$out = alt_api_trash(new WP_REST_Request(json_decode($argv[2], true)));
echo json_encode(array('out' => $out, 'suppressed' => $SUPPRESSED,
                       'trashed_posts' => $TRASHED_POSTS));
"""


def trash(rows, **params):
    params.setdefault("reason", "read from a dollar figure")
    runner = HARNESS % "\n".join(_lift(n) for n in LIFT)
    h = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                    encoding="utf-8")
    try:
        h.write(runner)
        h.close()
        res = subprocess.run([PHP, h.name, json.dumps(rows), json.dumps(params)],
                             capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            raise AssertionError("php failed: " + (res.stderr or "")[:2000])
        return json.loads(res.stdout)
    finally:
        os.unlink(h.name)


def row(rid, post_id=None, jobs=100, hash_="h%d"):
    return {"id": rid, "post_id": post_id, "event_id": 0, "job_count": jobs,
            "dedup_hash": (hash_ % rid) if "%" in hash_ else hash_}


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class EveryIdSpaceSuppresses(unittest.TestCase):
    """The three branches are one rule, and two of them did not follow it."""

    def test_the_table_id_space_suppresses(self):
        r = trash([row(1)], ids=[1])
        self.assertIn("h1", r["suppressed"])

    def test_the_post_id_space_suppresses(self):
        """This branch read the headcount and not the hash, so every removal
        through it was undone by the next import."""
        r = trash([row(2, post_id=900)], post_ids=[900])
        self.assertIn("h2", r["suppressed"])
        self.assertEqual(r["trashed_posts"], [900])

    def test_the_row_id_space_suppresses(self):
        r = trash([row(3)], row_ids=[3])
        self.assertIn("h3", r["suppressed"])
        self.assertEqual(r["out"]["deleted_rows"], [3])

    def test_the_hash_is_read_before_the_post_is_trashed(self):
        """wp_trash_post cascades and removes the row, so a read afterwards
        finds nothing to suppress. Order is the whole property here."""
        r = trash([row(4, post_id=901)], post_ids=[901])
        self.assertEqual(r["suppressed"].get("h4"),
                         "trashed: read from a dollar figure")

    def test_the_reason_travels_with_every_branch(self):
        for kw, rows in (({"ids": [5]}, [row(5)]),
                         ({"post_ids": [902]}, [row(6, post_id=902)]),
                         ({"row_ids": [7]}, [row(7)])):
            r = trash(rows, **kw)
            self.assertEqual(list(r["suppressed"].values()),
                             ["trashed: read from a dollar figure"], kw)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class WhatCannotBeSuppressedIsNamed(unittest.TestCase):
    """A count could not carry this, which is why it is a list of ids."""

    def test_a_row_with_no_hash_is_named_not_counted(self):
        r = trash([row(8, hash_="")], ids=[8])
        self.assertEqual(r["out"]["unsuppressed"], [8])
        self.assertEqual(r["out"]["suppressed"], 0)

    def test_a_protected_removal_names_nothing(self):
        r = trash([row(9)], ids=[9])
        self.assertEqual(r["out"]["unsuppressed"], [])
        self.assertEqual(r["out"]["suppressed"], 1)

    def test_the_two_are_told_apart_in_one_call(self):
        """The reason the count alone was not enough: a mixed call reported a
        number that was true and said nothing about which row was exposed."""
        r = trash([row(10), row(11, hash_="")], ids=[10, 11])
        self.assertEqual(r["out"]["suppressed"], 1)
        self.assertEqual(r["out"]["unsuppressed"], [11])

    def test_a_row_that_was_not_found_is_not_reported_as_unsuppressed(self):
        """not_found and unsuppressed are different states. A row that was
        never removed is not a row that will come back."""
        r = trash([], ids=[12])
        self.assertEqual(r["out"]["not_found"], [12])
        self.assertEqual(r["out"]["unsuppressed"], [])


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheRuleHasOnePlace(unittest.TestCase):

    def test_no_branch_calls_alt_suppress_hash_directly(self):
        """Three copies of a rule is how two of them drifted in the first
        place. `alt_trash_suppress` is the only caller inside the handler."""
        body = _lift("alt_api_trash")
        self.assertNotIn("alt_suppress_hash(", body)
        self.assertEqual(body.count("alt_trash_suppress("), 3)

    def test_the_helper_is_the_only_writer_of_unsuppressed(self):
        self.assertIn("$out['unsuppressed'][]", _lift("alt_trash_suppress"))
        self.assertNotIn("$out['unsuppressed'][]", _lift("alt_api_trash"))


if __name__ == "__main__":
    unittest.main()
