"""The backup artifact is published to a PUBLIC repo. Prove what cannot be in it.

`wp_alt_subscribers` holds email addresses, consent records and two live tokens.
Publishing it would be a notifiable breach, not a style violation, so "nothing
personal got in" has to be an assertion and not an intention.

THE ORDER OF THIS FILE IS THE ARGUMENT.

  1. The detector fires on a seeded positive. Until that is shown, every later
     assertion that something scanned clean is worth nothing: a scanner that
     returns [] for everything passes every negative test ever written. This
     repo has been bitten by exactly that shape (a check that resolved to a
     silent pass), so the control comes first and the export refuses to run
     when it fails.
  2. The table allowlist is complete and disjoint from the forbidden set, on
     BOTH sides - the Python and the PHP that serves the rows.
  3. The column allowlist matches the schema the plugin actually creates, so a
     new column cannot ride along unreviewed.
"""
import pathlib
import re
import unittest

import sys

RAILWAY = pathlib.Path(__file__).resolve().parents[1]
ROOT = RAILWAY.parent
sys.path.insert(0, str(RAILWAY))

import backup_tables  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
BACKUP_PHP = PLUGIN / "includes" / "backup.php"
DB_PHP = PLUGIN / "includes" / "db.php"


class TheDetectorFiresBeforeAnythingTrustsIt(unittest.TestCase):
    """A guard only ever seen to pass is indistinguishable from no guard."""

    def test_a_seeded_address_is_flagged(self):
        found = backup_tables.scan_value(
            "layoffs", "company", "Acme Corp <ops@example.invalid>")
        self.assertTrue(found, "the address detector did not fire on a seeded address")

    def test_a_seeded_64_hex_token_is_flagged(self):
        found = backup_tables.scan_value("layoffs", "company", "a" * 64)
        self.assertTrue(found, "the token detector did not fire on a seeded token")

    def test_a_whole_seeded_row_is_flagged(self):
        row = {"id": 1, "company": "Acme", "excerpt": "ordinary text",
               "source_name": "leak@example.invalid"}
        self.assertTrue(backup_tables.scan_row("layoffs", row))

    def test_the_export_refuses_when_the_control_fails(self):
        """Sabotage the detector and prove the export stops rather than proceeding."""
        original = backup_tables._ADDRESS
        try:
            # A pattern that can never match anything.
            backup_tables._ADDRESS = re.compile(r"(?!x)x")
            with self.assertRaises(backup_tables.PersonalDataInExport):
                backup_tables.assert_scanner_detects_seeded_personal_data()
        finally:
            backup_tables._ADDRESS = original
        # And it passes again once the detector is back.
        backup_tables.assert_scanner_detects_seeded_personal_data()

    def test_the_control_passes_on_the_real_detector(self):
        backup_tables.assert_scanner_detects_seeded_personal_data()

    def test_ordinary_rows_do_not_trip_it(self):
        """The control would be worthless if the detector flagged everything."""
        row = {"id": 7, "company": "Spirit Airlines", "job_count": 260,
               "country": "United States", "state": "FL",
               "source_url": "https://example.gov/warn/notice-1",
               "excerpt": "The airline said it would cut 260 roles in Florida."}
        self.assertEqual(backup_tables.scan_row("layoffs", row), [])

    def test_a_hash_column_still_refuses_an_address(self):
        """The 64-hex exemption is narrow: it exempts hashes, not everything."""
        self.assertTrue(backup_tables.scan_value(
            "source_reports", "evidence_hash", "person@example.invalid"))
        # ...and it does exempt an actual hash.
        self.assertEqual(backup_tables.scan_value(
            "source_reports", "evidence_hash", "b" * 64), [])


class TheTableAllowlistIsTheBoundary(unittest.TestCase):

    def test_no_forbidden_table_is_in_the_export_set(self):
        backup_tables.assert_allowlists_disjoint()

    def test_subscribers_is_named_as_forbidden_with_a_reason(self):
        self.assertIn("alt_subscribers", backup_tables.FORBIDDEN_TABLES)
        reason = backup_tables.FORBIDDEN_TABLES["alt_subscribers"]
        self.assertGreater(len(reason), 60, "an exclusion without a reason gets re-litigated")

    def test_subscribers_can_never_be_reached_through_the_allowlist(self):
        self.assertIsNone(
            backup_tables.TABLES.get("subscribers"),
            "wp_alt_subscribers must not be reachable by any logical name")

    def test_adding_a_forbidden_table_to_the_allowlist_fails_loudly(self):
        """The positive control for layer 1."""
        backup_tables.TABLES["subscribers"] = {
            "pk": "id", "restorable": "manual", "optional": True,
            "why": "seeded by a test", "columns": ["id", "email"],
        }
        backup_tables.FORBIDDEN_TABLES["subscribers"] = "seeded by a test"
        try:
            with self.assertRaises(backup_tables.PersonalDataInExport):
                backup_tables.assert_allowlists_disjoint()
        finally:
            backup_tables.TABLES.pop("subscribers", None)
            backup_tables.FORBIDDEN_TABLES.pop("subscribers", None)
        backup_tables.assert_allowlists_disjoint()

    def test_the_php_serves_exactly_the_same_set(self):
        """Two allowlists that disagree are one allowlist and one decoration."""
        php = BACKUP_PHP.read_text(encoding="utf-8")
        body = php.split("function alt_backup_tables()")[1].split("function alt_backup_forbidden_tables")[0]
        php_names = set(re.findall(r"^\s*'([a-z_]+)' => array\(", body, re.M))
        self.assertEqual(
            php_names, set(backup_tables.TABLES),
            "includes/backup.php and railway/backup_tables.py name different tables")

    def test_the_php_never_names_the_subscribers_table_as_servable(self):
        php = BACKUP_PHP.read_text(encoding="utf-8")
        servable = php.split("function alt_backup_tables()")[1].split("function alt_backup_forbidden_tables")[0]
        self.assertNotIn("alt_subscribers", servable)

    def test_the_php_route_has_no_passthrough_for_a_raw_table_name(self):
        """A parameter that reaches SQL is a hole whatever the allowlist says."""
        php = BACKUP_PHP.read_text(encoding="utf-8")
        # The only place a caller's table param is used is to look up a spec.
        self.assertIn("alt_backup_table_spec($name)", php)
        self.assertNotIn("FROM {$name}", php)
        self.assertNotIn("FROM `$name`", php)


class TheColumnAllowlistMatchesTheRealSchema(unittest.TestCase):
    """Layer 2 is only complete if it names the columns the plugin creates."""

    @staticmethod
    def _schema_columns(sql_block: str):
        cols = []
        for line in sql_block.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith(("/*", "*", "PRIMARY KEY", "UNIQUE KEY", "KEY", ")")):
                continue
            m = re.match(r"^([a-z_]+)\s+[A-Z]", line)
            if m:
                cols.append(m.group(1))
        return cols

    def test_layoffs_columns_are_all_pinned(self):
        php = DB_PHP.read_text(encoding="utf-8")
        block = php.split('$sql = "CREATE TABLE $table (')[1].split(") $charset")[0]
        schema = set(self._schema_columns(block))
        pinned = set(backup_tables.TABLES["layoffs"]["columns"])
        self.assertTrue(schema, "could not read the layoffs schema out of db.php")
        self.assertEqual(
            schema - pinned, set(),
            "db.php creates layoffs columns the backup allowlist does not pin; "
            "review each one before adding it")

    def test_every_exported_table_pins_its_primary_key(self):
        for name, spec in backup_tables.TABLES.items():
            self.assertIn(spec["pk"], spec["columns"], f"{name} does not pin its own pk")

    def test_an_unpinned_column_stops_the_export(self):
        """The positive control for layer 2."""
        with self.assertRaises(backup_tables.UnpinnedColumn):
            backup_tables.assert_columns_pinned("layoffs", ["id", "company", "email"])
        # And a legitimate column set passes.
        backup_tables.assert_columns_pinned(
            "layoffs", backup_tables.TABLES["layoffs"]["columns"])

    def test_the_failure_message_says_what_to_do(self):
        try:
            backup_tables.assert_columns_pinned("layoffs", ["id", "surprise_column"])
        except backup_tables.UnpinnedColumn as exc:
            msg = str(exc)
            self.assertIn("surprise_column", msg)
            self.assertIn("personal data", msg)
            self.assertIn("Do not widen this check", msg)
        else:
            self.fail("an unpinned column did not raise")

    def test_digest_tables_carry_no_recipient_column(self):
        """The reason these two are exportable at all, asserted rather than assumed."""
        for table in ("digest_sends", "digest_links"):
            cols = backup_tables.TABLES[table]["columns"]
            for banned in ("email", "subscriber_id", "recipient", "ip", "user_agent",
                           "confirm_token", "unsub_token"):
                self.assertNotIn(banned, cols, f"{table} pins a {banned} column")

    def test_claps_is_two_integers(self):
        self.assertEqual(backup_tables.TABLES["post_claps"]["columns"], ["post_id", "claps"])


if __name__ == "__main__":
    unittest.main()
