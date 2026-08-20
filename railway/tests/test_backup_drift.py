"""An export that silently starts producing nothing must go red, not green.

A backup nobody watches is a hypothesis, and the specific way this one would
fail quietly is a walk that returns fewer rows than the table holds - a paging
bug, a truncated response, a route half-deployed. All of those produce a small
file and a green run.

Every assertion below is a POSITIVE control: it hands `check_drift` a broken
manifest and requires FAIL. The two negative cases at the end exist so the
whole file cannot pass by the checker simply always failing.
"""
import pathlib
import sys
import unittest

RAILWAY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

# backup_export imports source_health, which imports `requests` at module
# scope. The ONE shared stub, never a partial one installed here: a per-module
# stub is what made the suite order-dependent (see tests/_requests_stub.py).
from tests import _requests_stub  # noqa: E402
_requests_stub.install()

import backup_export  # noqa: E402
import backup_tables  # noqa: E402

FAIL, PASS, UNKNOWN = backup_export.FAIL, backup_export.PASS, backup_export.UNKNOWN


def manifest(tables=None, **over):
    """A healthy manifest, for a test to break one field of at a time."""
    base_tables = {}
    for name, spec in backup_tables.TABLES.items():
        if spec["optional"]:
            continue
        base_tables[name] = {"rows": 1000, "bytes": 5000, "sha256": "x",
                             "site_count": 1000, "restorable": spec["restorable"],
                             "date_range": None}
    m = {
        "exported_at": "2026-08-19T00:00:00Z",
        "schema_version": 1,
        "plugin_version": "2.20.123",
        "tables": tables if tables is not None else base_tables,
    }
    m["total_rows"] = sum(t["rows"] for t in m["tables"].values())
    m.update(over)
    return m


def state_from(m):
    return {"tables": {k: {"rows": v["rows"]} for k, v in m["tables"].items()}}


class AnEmptyOrShrunkenExportFails(unittest.TestCase):

    def test_a_wholly_empty_export_fails(self):
        verdict, lines = backup_export.check_drift(
            manifest(tables={}, total_rows=0), state_from(manifest()))
        self.assertEqual(verdict, FAIL)
        self.assertTrue(any("no tables" in l or "empty" in l for l in lines))

    def test_a_required_table_at_zero_rows_fails(self):
        m = manifest()
        m["tables"]["layoffs"]["rows"] = 0
        m["tables"]["layoffs"]["site_count"] = 0
        m["total_rows"] = sum(t["rows"] for t in m["tables"].values())
        verdict, lines = backup_export.check_drift(m, state_from(manifest()))
        self.assertEqual(verdict, FAIL)
        self.assertTrue(any("ZERO rows" in l for l in lines))

    def test_a_required_table_missing_entirely_fails(self):
        m = manifest()
        del m["tables"]["layoffs"]
        verdict, lines = backup_export.check_drift(m, state_from(manifest()))
        self.assertEqual(verdict, FAIL)
        self.assertTrue(any("REQUIRED table is missing" in l for l in lines))

    def test_a_shrink_past_tolerance_fails(self):
        previous = state_from(manifest())
        m = manifest()
        m["tables"]["layoffs"]["rows"] = 800          # 20% down on 1000
        m["tables"]["layoffs"]["site_count"] = 800
        m["total_rows"] = sum(t["rows"] for t in m["tables"].values())
        verdict, lines = backup_export.check_drift(m, previous)
        self.assertEqual(verdict, FAIL)
        self.assertTrue(any("past the" in l for l in lines))

    def test_a_shrink_inside_tolerance_passes_but_is_reported(self):
        """Rows legitimately leave: /trash, /bulk-purge, the superset reconciler."""
        previous = state_from(manifest())
        m = manifest()
        m["tables"]["layoffs"]["rows"] = 980          # 2% down
        m["tables"]["layoffs"]["site_count"] = 980
        m["total_rows"] = sum(t["rows"] for t in m["tables"].values())
        verdict, lines = backup_export.check_drift(m, previous)
        self.assertEqual(verdict, PASS)
        self.assertTrue(any("down 20" in l for l in lines))


class AShortWalkFails(unittest.TestCase):
    """The site said N rows; we came away with fewer. That is the silent one."""

    def test_walking_far_fewer_rows_than_the_site_counted_fails(self):
        m = manifest()
        m["tables"]["layoffs"]["rows"] = 400
        m["tables"]["layoffs"]["site_count"] = 1000
        m["total_rows"] = sum(t["rows"] for t in m["tables"].values())
        verdict, lines = backup_export.check_drift(m, state_from(manifest()))
        self.assertEqual(verdict, FAIL)
        self.assertTrue(any("stopped early" in l for l in lines))

    def test_a_few_rows_of_skew_is_tolerated(self):
        """An import landing mid-walk moves the count under us. That is not corruption."""
        m = manifest()
        m["tables"]["layoffs"]["rows"] = 997
        m["tables"]["layoffs"]["site_count"] = 1000
        m["total_rows"] = sum(t["rows"] for t in m["tables"].values())
        verdict, _ = backup_export.check_drift(m, state_from(manifest()))
        self.assertEqual(verdict, PASS)

    def test_no_site_count_is_unverified_and_said_so(self):
        m = manifest()
        m["tables"]["layoffs"]["site_count"] = None
        verdict, lines = backup_export.check_drift(m, state_from(manifest()))
        self.assertTrue(any("UNVERIFIED" in l for l in lines))
        self.assertEqual(verdict, PASS)   # unverified walk, but nothing failed


class AMissingManifestFieldFails(unittest.TestCase):

    def test_each_required_field_is_actually_required(self):
        for field in backup_export.REQUIRED_MANIFEST_FIELDS:
            with self.subTest(field=field):
                m = manifest()
                m[field] = None
                verdict, lines = backup_export.check_drift(m, state_from(manifest()))
                self.assertEqual(verdict, FAIL, f"a missing {field} did not fail")
                self.assertTrue(any(field in l for l in lines))


class NoBaselineIsUnknownAndNeverAPass(unittest.TestCase):

    def test_the_first_run_reports_unchecked(self):
        verdict, lines = backup_export.check_drift(manifest(), {})
        self.assertEqual(verdict, UNKNOWN)
        self.assertTrue(any("UNCHECKED" in l for l in lines))

    def test_unknown_is_not_a_zero_exit(self):
        """UNKNOWN must not resolve to success anywhere in the exit mapping."""
        self.assertNotEqual(UNKNOWN, PASS)


class AHealthyExportPasses(unittest.TestCase):
    """Without this the file could pass by the checker failing everything."""

    def test_a_good_run_against_a_good_baseline_passes(self):
        m = manifest()
        verdict, lines = backup_export.check_drift(m, state_from(m))
        self.assertEqual(verdict, PASS, f"a healthy export did not pass: {lines}")

    def test_growth_passes(self):
        previous = state_from(manifest())
        m = manifest()
        for entry in m["tables"].values():
            entry["rows"] = 1200
            entry["site_count"] = 1200
        m["total_rows"] = sum(t["rows"] for t in m["tables"].values())
        self.assertEqual(backup_export.check_drift(m, previous)[0], PASS)

    def test_an_absent_optional_table_is_a_note_and_not_a_failure(self):
        m = manifest()          # built without the optional tables at all
        verdict, lines = backup_export.check_drift(m, state_from(m))
        self.assertEqual(verdict, PASS)
        self.assertTrue(any("optional table" in l for l in lines))


if __name__ == "__main__":
    unittest.main()
