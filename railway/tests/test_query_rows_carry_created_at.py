"""Every /query row says when the tracker first listed it.

2.20.304 added `created_at` to alt_entry_to_array(), the CPT path, and its
release note said "every row in the public API now carries created_at". The
table the public API actually reads is wp_alt_layoffs, shaped by
alt_db_row_to_array(), and on 2026-11-10 the live /query rows carried no such
key. About a third of rows (bulk WARN and ERM imports) have no backing post at
all, so the post date alone could never cover them.

So the table holds its own first-listed time: stamped once on INSERT, never on
the UPDATE branch, because a daily re-import must not make an old row look new.
Rows that predate the column read their post's GMT date when they have one and
null when they do not. Null is the honest value: inventing a date would be a
first-listed time nobody observed.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB_PHP = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes", "db.php")
HARNESS = os.path.join(HERE, "fixtures", "upsert_reimport_harness.php")
PHP = shutil.which("php")

ROW = {"dedup_hash": "c4ca4238a0b923820dcc", "company": "Acme Logistics",
       "job_count": 240, "layoff_date": "2026-05-01", "country": "United States",
       "state": "CA", "source_type": "warn", "verification_level": "warn",
       "source_name": "CA WARN notice"}


def _code() -> str:
    with open(DB_PHP, encoding="utf-8") as fh:
        text = fh.read()
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _fn(name: str) -> str:
    return _code().split(f"function {name}(", 1)[1].split("\nfunction ", 1)[0]


class SchemaAndShape(unittest.TestCase):
    def test_the_table_has_a_nullable_created_at(self):
        create = _fn("alt_db_layoffs_create_sql").split("CREATE TABLE $table", 1)[1].split(") $charset", 1)[0]
        self.assertRegex(create, r"\bcreated_at DATETIME NULL DEFAULT NULL\b")

    def test_row_to_array_emits_created_at(self):
        self.assertRegex(_fn("alt_db_row_to_array"), r"'created_at'\s*=>")

    def test_the_fallback_reads_the_post_gmt_date_and_never_updated_at(self):
        body = _fn("alt_db_created_at_iso")
        self.assertIn("post_date_gmt", body)
        self.assertIn("Y-m-d\\TH:i:s\\Z", body)
        self.assertNotIn("updated_at", body,
                         "updated_at is the LAST write, not the first listing")


@unittest.skipIf(PHP is None, "php is not on PATH: UNKNOWN, not a pass.")
class StampedOnceOnInsert(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cases = {"insert": {"existing": None, "reimport": ROW},
                 "reimport": {"existing": {"id": 7, "edited": 0}, "reimport": ROW}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(cases, fh)
            path = fh.name
        try:
            run = subprocess.run([PHP, HARNESS, DB_PHP, path], capture_output=True,
                                 text=True, timeout=60)
        finally:
            os.unlink(path)
        if run.returncode != 0:
            raise AssertionError(run.stderr[:2000])
        cls.out = json.loads(run.stdout)

    def test_a_first_sighting_stamps_created_at(self):
        inserted = self.out["insert"]["inserted"]
        self.assertRegex(inserted.get("created_at") or "", r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")
        self.assertEqual(inserted["created_at"], inserted["updated_at"])

    def test_a_reimport_never_restamps_it(self):
        self.assertNotIn("created_at", self.out["reimport"]["updated"],
                         "a daily re-import would make every old row look newly listed")


if __name__ == "__main__":
    unittest.main()
