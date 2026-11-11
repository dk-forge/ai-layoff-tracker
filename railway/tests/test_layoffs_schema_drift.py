"""wp_alt_layoffs must never silently drop a first listing (2.20.310).

2.20.306 added `created_at` and stamped it on INSERT in alt_db_upsert(). The
deploy-race guard alt_ensure_schema_once() only checked ONE sentinel column
(`updated_at`, pinned by a test), so a deploy whose dbDelta did not add
created_at was marked verified, every INSERT failed with Unknown column, and
$wpdb->insert() returning false was never looked at. Posts kept publishing and
no new row reached /query for over a day.

These tests run the SHIPPED db.php:
  * every column the INSERT writes is declared in the CREATE TABLE;
  * the guard compares the WHOLE declared column list with the live table;
  * a failed INSERT is recorded, repaired by ALTER, and retried once.
"""
import json
import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PLUGIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker")
DB_PHP = os.path.join(PLUGIN, "includes", "db.php")
MAIN_PHP = os.path.join(PLUGIN, "ai-layoff-tracker.php")
API_PHP = os.path.join(PLUGIN, "includes", "api.php")
HARNESS = os.path.join(HERE, "fixtures", "schema_drift_harness.php")
PHP = shutil.which("php")


def run(mode, live=""):
    out = subprocess.run([PHP, HARNESS, DB_PHP, mode, live], capture_output=True,
                         text=True, timeout=60)
    assert out.returncode == 0, out.stderr + out.stdout
    return json.loads(out.stdout.strip().splitlines()[-1])


@unittest.skipUnless(PHP, "php not installed")
class InsertMatchesSchema(unittest.TestCase):
    def test_every_inserted_column_is_declared(self):
        schema = set(run("schema"))
        self.assertIn("created_at", schema)
        written = set(run("insert", ",".join(sorted(schema))))
        self.assertEqual(set(), written - schema,
                         "alt_db_upsert writes a column the schema lacks")

    def test_missing_columns_reports_created_at(self):
        schema = run("schema")
        live = [c for c in schema if c != "created_at"]
        self.assertEqual(["created_at"], run("missing", ",".join(live)))
        self.assertEqual([], run("missing", ",".join(schema)))

    def test_failed_insert_is_recorded_repaired_and_retried(self):
        schema = run("schema")
        live = [c for c in schema if c != "created_at"]
        r = run("fail", ",".join(live))
        self.assertEqual(2, r["attempts"], "a failed INSERT must be retried once after repair")
        self.assertTrue(r["recorded"], "a failed INSERT must be recorded, not ignored")
        self.assertIn("Unknown column", r["recorded"]["error"])
        self.assertTrue(any("ADD COLUMN `created_at`" in q for q in r["alters"]), r["alters"])


class GuardChecksEveryColumn(unittest.TestCase):
    def test_schema_verified_uses_full_column_list(self):
        with open(MAIN_PHP, encoding="utf-8") as f:
            main = f.read()
        body = main[main.index("function alt_db_schema_verified"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("alt_db_missing_columns(", body,
                      "one sentinel column let created_at go missing in 2.20.306")

    def test_migrate_reports_schema_and_last_insert_error(self):
        with open(DB_PHP, encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("function alt_api_migrate"):]
        body = body[:body.index("\n}\n")]
        for key in ("missing_columns_before", "missing_columns_after", "last_insert_error"):
            self.assertIn(key, body)


class AddRejectsAnonymousEmployer(unittest.TestCase):
    def test_add_rejects_unknown_before_creating_a_post(self):
        with open(API_PHP, encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("function alt_api_add("):]
        body = body[:body.index("\n}\n")]
        gate = body.find("alt_is_anonymous_employer(")
        self.assertNotEqual(-1, gate, "/add must reject 'Unknown' and other non-employers")
        self.assertLess(gate, body.find("wp_insert_post("),
                        "the gate must run before a post is created")
        self.assertRegex(body[gate:gate + 400], r"WP_Error\(")
