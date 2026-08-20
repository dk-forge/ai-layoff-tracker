"""A routine re-import must never blank a field it does not carry.

alt_db_upsert() builds the full column set from the incoming row and, on the
UPDATE branch, writes ALL of it. That is correct for the columns a source
restates every time (company, count, dates, source) and wrong for the columns
another worker filled in: the daily WARN/ERM `/bulk` sweep re-upserts tens of
thousands of existing rows every morning, and every `/add` re-post of a seen
article does the same thing to one row.

MEASURED, 2026-08-19, against the shipped function (this harness) and the live
corpus:

  * `employer_country_evidence` and `announcement_evidence` had NO guard. Every
    re-import wrote '' over whatever enrich_context.py had stored.
  * `announcement_date` had a guard that HAS NEVER FIRED. It tested `=== ''`,
    but the value it inspects has already been through alt_db_valid_date(),
    which returns NULL — never the empty string — for a missing or unparseable
    date. So the branch was unreachable and the daily re-import went on writing
    NULL over stored notice dates. It read as protected for as long as it
    existed.
  * `industry` was, and remains, correct.

The live corpus shows no surviving casualty: 137/137 news rows and 180/180 8-K
rows that carry an announcement_date still carry its evidence quote, and no
WARN row carries a domicile at all. That is NOT the same as "it never fired" —
these writes land daily, and a value destroyed before anything can read it
leaves the same trace as a value never written. The guard is what makes the
distinction observable.

Clearing any of these deliberately goes through `/edit`, which pins the row
with `edited = 1` and is skipped by the upsert entirely.

The harness loads the SHIPPED includes/db.php behind a recording $wpdb, so
these assertions are about the real function and not a reimplementation of it.
A column ABSENT from the UPDATE payload is one the re-import leaves alone; a
column present with '' or NULL is one it destroys.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB_PHP = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                      "includes", "db.php")
HARNESS = os.path.join(HERE, "fixtures", "upsert_reimport_harness.php")
PHP = shutil.which("php")

#: Every column a re-import must leave alone when it carries no value for it.
PRESERVED = ("industry", "announcement_date",
             "employer_country_evidence", "announcement_evidence")

#: A WARN notice as warn_import.py actually sends it through `/bulk`: company,
#: count, effective date, state. No industry, no notice date, no evidence.
WARN_REIMPORT = {
    "dedup_hash": "d41d8cd98f00b204e980", "company": "Acme Logistics",
    "job_count": 240, "layoff_date": "2026-05-01", "country": "United States",
    "state": "CA", "source_type": "warn", "verification_level": "warn",
    "source_name": "CA WARN notice",
}

#: The same row as a source that DOES restate every field. Nothing here may be
#: dropped: the guard is "not carried", never "never written".
FULL_REIMPORT = dict(WARN_REIMPORT, **{
    "industry": "Transportation & Logistics",
    "announcement_date": "2026-03-04",
    "employer_country_evidence": "Acme Logistics, headquartered in Dublin",
    "announcement_evidence": "announced on March 4, 2026 that it would cut 240 jobs",
})

CASES = {
    # The daily sweep, on a row an enrichment worker has already filled.
    "warn_reimport": {"existing": {"id": 991, "edited": 0},
                      "reimport": WARN_REIMPORT},
    # An `/add` re-post of a seen article whose extraction found no quote.
    "news_repost_without_evidence": {
        "existing": {"id": 992, "edited": 0},
        "reimport": dict(WARN_REIMPORT, source_type="news",
                         verification_level="bronze",
                         source_url="https://example.com/a"),
    },
    # Empty strings, which is how a caller spells "the source did not say".
    "reimport_with_empty_strings": {
        "existing": {"id": 993, "edited": 0},
        "reimport": dict(WARN_REIMPORT, industry="", announcement_date="",
                         employer_country_evidence="",
                         announcement_evidence=""),
    },
    # A date the validator rejects resolves to NULL exactly like a missing one.
    "reimport_with_unparseable_date": {
        "existing": {"id": 994, "edited": 0},
        "reimport": dict(WARN_REIMPORT, announcement_date="not-a-date"),
    },
    # The other direction: a carried value must still be written.
    "reimport_carrying_every_field": {"existing": {"id": 995, "edited": 0},
                                      "reimport": FULL_REIMPORT},
    # A first sighting is an INSERT, which has nothing to protect.
    "first_insert": {"existing": None, "reimport": FULL_REIMPORT},
}


@unittest.skipIf(PHP is None,
                 "php is not on PATH, so the shipped upsert could not be run. "
                 "UNKNOWN, not a pass.")
class UpsertReimportGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as fh:
            json.dump(CASES, fh)
            path = fh.name
        try:
            run = subprocess.run([PHP, HARNESS, DB_PHP, path],
                                 capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(path)
        if run.returncode != 0:
            raise AssertionError(f"the harness failed: {run.stderr[:2000]}")
        cls.out = json.loads(run.stdout)

    def updated(self, case):
        payload = self.out[case]["updated"]
        self.assertIsNotNone(payload, f"{case} did not take the UPDATE branch")
        return payload

    def test_a_reimport_that_carries_nothing_writes_none_of_them(self):
        for case in ("warn_reimport", "news_repost_without_evidence",
                     "reimport_with_empty_strings"):
            payload = self.updated(case)
            for column in PRESERVED:
                self.assertNotIn(
                    column, payload,
                    f"{case}: the daily re-import blanks {column} "
                    f"(wrote {payload.get(column)!r}) — a value another worker "
                    f"filled in is destroyed. Clearing goes through /edit.")

    def test_an_unparseable_date_is_not_carried_either(self):
        """The guard the announcement_date column HAD tested `=== ''`, which
        alt_db_valid_date() can never return. Null and '' both mean 'the source
        did not say' and both must skip the write."""
        payload = self.updated("reimport_with_unparseable_date")
        self.assertNotIn("announcement_date", payload)

    def test_a_reimport_that_carries_values_still_writes_them(self):
        """The guard is 'not carried', never 'never written'. A source that
        restates these fields must keep correcting the row."""
        payload = self.updated("reimport_carrying_every_field")
        for column in PRESERVED:
            self.assertEqual(payload.get(column), FULL_REIMPORT[column],
                             f"{column} was carried and must be written")

    def test_a_first_sighting_still_inserts_every_column(self):
        inserted = self.out["first_insert"]["inserted"]
        self.assertIsNotNone(inserted, "a new row must take the INSERT branch")
        for column in PRESERVED:
            self.assertEqual(inserted.get(column), FULL_REIMPORT[column])

    def test_an_edited_row_is_still_pinned_before_any_of_this(self):
        """Nothing above may weaken the correction pin: an edited row takes no
        write at all, which is a stronger promise than per-column guards."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as fh:
            json.dump({"pinned": {"existing": {"id": 996, "edited": 1},
                                  "reimport": FULL_REIMPORT}}, fh)
            path = fh.name
        try:
            run = subprocess.run([PHP, HARNESS, DB_PHP, path],
                                 capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(path)
        out = json.loads(run.stdout)["pinned"]
        self.assertIsNone(out["updated"], "an edited row must take no write")
        self.assertIsNone(out["inserted"])


if __name__ == "__main__":
    unittest.main()
