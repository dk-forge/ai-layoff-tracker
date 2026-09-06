"""A restore path that has never been executed is a belief, not a backup.

This is the executed one. It runs the PRODUCTION PHP sealer over synthetic
rows, opens the result with openssl and the private half of a throwaway
keypair, and compares byte for byte. It is not a Python re-implementation
agreeing with itself: the code under test is the same file the host runs, which
is the whole reason the sealer is a pure function in its own include instead of
living inside the route.

It also holds the BOUNDARY that made this safe to build at all. The public
export's allowlist is a structural guarantee and it stays complete: this change
must not have added the subscriber table to it anywhere.

WHY THE NEGATIVE CONTROLS ARE HERE AND NOT OPTIONAL
A detector that has only ever been observed to pass is indistinguishable from a
detector that does nothing, and this repo has been bitten by that shape more
than once. So the MAC is proved to REFUSE a flipped byte, the unwrap is proved
to refuse a foreign key, and the recipient check is proved to notice a key the
repository does not vouch for, before any clean result from them is believed.
"""
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


def _repo_root():
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError("test_subscriber_backup_crypto: no repo root above %s" % here)


ROOT = _repo_root()
sys.path.insert(0, str(ROOT / "railway"))
_spec = importlib.util.spec_from_file_location(
    "subscriber_backup", ROOT / "railway" / "subscriber_backup.py")
sb = importlib.util.module_from_spec(_spec)
sys.modules["subscriber_backup"] = sb
_spec.loader.exec_module(sb)

import backup_tables  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
ROUTE_PHP = PLUGIN / "includes" / "subscriber-backup.php"
SEAL_PHP = PLUGIN / "includes" / "subscriber-backup-seal.php"
EXPORT_PHP = PLUGIN / "includes" / "backup.php"

HAVE_TOOLS = bool(shutil.which("openssl") and shutil.which("php"))


class RoundTrip(unittest.TestCase):
    @unittest.skipUnless(HAVE_TOOLS, "openssl and php are required")
    def test_the_drill_passes(self):
        """The whole round trip plus its four negative controls. Exit 0 or the
        drill itself names which half failed."""
        self.assertEqual(sb.selftest(), 0)

    def test_the_drill_reports_unknown_when_it_cannot_run(self):
        """Absence of a signal is never a pass. With no openssl on PATH the
        drill must say UNKNOWN and exit 3, not exit 0."""
        real = shutil.which
        shutil.which = lambda name: None
        try:
            self.assertEqual(sb.selftest(), 3)
        finally:
            shutil.which = real


class Container(unittest.TestCase):
    def test_a_missing_field_is_a_fault(self):
        self.assertTrue(sb.verify_structure({"format": sb.FORMAT}))

    def test_a_foreign_recipient_is_a_fault(self):
        header = {
            "format": sb.FORMAT, "created_at": "2026-09-06T00:00:00Z",
            "schema_version": 1, "rows": 1, "columns": list(sb.COLUMNS),
            "key_fingerprint": "aa" * 32, "wrapped_key": "AAAA", "iv": "AAAA",
            "ciphertext": "A" * 24, "mac": "AAAA",
        }
        faults = sb.verify_structure(header, expect_fingerprint="bb" * 32)
        self.assertTrue(any("does not vouch" in f for f in faults), faults)

    def test_the_mac_covers_every_field_a_restore_depends_on(self):
        """A field outside the MAC is a field an attacker may rewrite. The
        canonical string is hard-coded on both sides; this pins the list."""
        header = {
            "format": sb.FORMAT, "created_at": "2026-09-06T00:00:00Z",
            "schema_version": 1, "rows": 3, "columns": list(sb.COLUMNS),
            "key_fingerprint": "aa" * 32, "wrapped_key": "W", "iv": "I",
            "ciphertext": "C",
        }
        base = sb.canonical(header)
        for field, changed in (("created_at", "2026-09-07T00:00:00Z"), ("rows", 4),
                               ("schema_version", 2), ("key_fingerprint", "bb" * 32),
                               ("wrapped_key", "X"), ("iv", "J"), ("ciphertext", "D")):
            moved = dict(header, **{field: changed})
            self.assertNotEqual(base, sb.canonical(moved),
                                f"{field} is not covered by the MAC")


class Boundary(unittest.TestCase):
    """The public export's personal-data boundary must be exactly as complete
    as it was before this change."""

    def test_the_subscriber_table_is_still_forbidden_on_the_python_side(self):
        self.assertIn("alt_subscribers", backup_tables.FORBIDDEN_TABLES)
        self.assertNotIn("subscribers", backup_tables.TABLES)
        backup_tables.assert_allowlists_disjoint()

    def test_the_public_export_route_still_refuses_it(self):
        php = EXPORT_PHP.read_text()
        self.assertIn("alt_subscribers", php)
        # It appears only in the FORBIDDEN list and the prose, never as an entry
        # of alt_backup_tables().
        allowlist = php.split("function alt_backup_tables()")[1].split("function alt_backup_forbidden_tables")[0]
        self.assertNotIn("alt_subscribers", allowlist)

    def test_the_new_route_has_no_branch_that_returns_rows(self):
        """The promise of this route is that no mode of it emits plaintext.
        Enforced by reading the file, because the alternative is trusting that
        nobody adds a debug branch."""
        php = ROUTE_PHP.read_text()
        responses = re.findall(r"rest_ensure_response\(([^)]*)\)", php)
        self.assertTrue(responses)
        for r in responses:
            self.assertNotIn("$rows", r, "a response is built from raw rows")
            self.assertNotIn("$payload", r, "a response is built from the plaintext")
            self.assertNotIn("$lines", r, "a response is built from the plaintext lines")

    def test_the_route_nulls_the_plaintext_before_responding(self):
        php = ROUTE_PHP.read_text()
        self.assertIn("$payload = null;", php)

    def test_it_ships_disarmed(self):
        """No recipient key is committed, so a merge of this branch arms
        nothing. Arming is the owner's step and only his."""
        self.assertFalse(sb.PUBLIC_KEY_PATH.exists(),
                         "a recipient public key is committed; this should be the "
                         "owner's deliberate arming step, not a side effect of a PR")
        self.assertEqual(sb.committed_public_key(), "")

    def test_there_is_no_scheduled_workflow_that_touches_the_host(self):
        """A public repository's Actions artifacts and releases are downloadable
        by anyone, so nothing on a schedule may hold this ciphertext. The only
        workflow shipped is the OFFLINE drill."""
        for wf in (ROOT / ".github" / "workflows").glob("*subscriber-backup*"):
            text = wf.read_text()
            self.assertNotIn("schedule:", text, f"{wf.name} is on a schedule")
            self.assertNotIn("WP_API_KEY", text, f"{wf.name} can reach the host")
            self.assertNotIn("upload-artifact", text, f"{wf.name} uploads something")


class ColumnParity(unittest.TestCase):
    """The two column lists must agree, or the container's header describes rows
    it does not contain."""

    def test_php_and_python_pin_the_same_columns(self):
        php = ROUTE_PHP.read_text()
        block = php.split("function alt_sbk_columns()")[1].split("}")[0]
        names = re.findall(r"'([a-z_]+)'", block)
        self.assertEqual(names, sb.COLUMNS)

    def test_every_pinned_column_exists_in_the_schema(self):
        """And the other direction: a column in the live CREATE TABLE that
        nobody pinned would be dropped from the backup silently. The route
        fails the run on one, and this catches it a deploy earlier."""
        db = (PLUGIN / "includes" / "db.php").read_text()
        create = db.split("CREATE TABLE $subscribers (")[1].split("PRIMARY KEY")[0]
        declared = re.findall(r"^\s*([a-z_]+)\s+(?:BIGINT|VARCHAR|TINYINT|CHAR|TEXT|DATETIME)",
                              create, re.M)
        self.assertEqual(sorted(declared), sorted(sb.COLUMNS))


class SealRefusals(unittest.TestCase):
    @unittest.skipUnless(HAVE_TOOLS, "openssl and php are required")
    def _seal_with(self, pem_text):
        with tempfile.TemporaryDirectory() as tmp:
            pub = pathlib.Path(tmp) / "pub.pem"
            pub.write_text(pem_text)
            return sb.php_seal(b"{}\n", pub, 1)

    @unittest.skipUnless(HAVE_TOOLS, "openssl and php are required")
    def test_a_weak_key_is_refused(self):
        """A container meant to outlive the host is sealed once and revisited
        never, so the floor is checked at seal time."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            sb._openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                         "-out", str(tmp / "weak.pem")])
            sb._openssl(["pkey", "-in", str(tmp / "weak.pem"), "-pubout",
                         "-out", str(tmp / "weak.pub")])
            with self.assertRaises(sb.ContainerError):
                sb.php_seal(b"{}\n", tmp / "weak.pub", 1)

    @unittest.skipUnless(HAVE_TOOLS, "openssl and php are required")
    def test_junk_is_refused(self):
        with self.assertRaises(sb.ContainerError):
            self._seal_with("not a key at all")


if __name__ == "__main__":
    unittest.main()
