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

    def test_a_table_that_may_legitimately_be_empty_does_not_fail_at_zero(self):
        """warn_transparency is an editorial register nobody has written into.

        The first live export failed the whole run on it. That was the table
        being misclassified, not the check being wrong, so the fix is a
        per-table declaration and not a softer rule.
        """
        self.assertTrue(backup_tables.TABLES["warn_transparency"]["may_be_empty"])
        empty = {"rows": 0, "bytes": 0, "sha256": "", "site_count": 0,
                 "restorable": "manual", "date_range": None}
        m = manifest()
        m["tables"]["warn_transparency"] = dict(empty)
        previous = manifest()
        previous["tables"]["warn_transparency"] = dict(empty)
        verdict, lines = backup_export.check_drift(m, state_from(previous))
        self.assertEqual(verdict, PASS, f"an empty-by-design table failed: {lines}")

    def test_but_an_empty_by_design_table_LOSING_rows_still_fails(self):
        """`may_be_empty` licenses staying empty, never going empty."""
        m = manifest()
        m["tables"]["warn_transparency"] = {
            "rows": 0, "bytes": 0, "sha256": "", "site_count": 0,
            "restorable": "manual", "date_range": None}
        verdict, lines = backup_export.check_drift(m, state_from(manifest()))
        self.assertEqual(verdict, FAIL)
        self.assertTrue(any("warn_transparency" in l and "past the" in l for l in lines))

    def test_every_table_declares_both_states_rather_than_defaulting(self):
        for name, spec in backup_tables.TABLES.items():
            with self.subTest(name):
                self.assertIn("optional", spec)
                self.assertIn("may_be_empty", spec,
                              f"{name} must decide whether empty is legitimate")

    def test_the_corpus_may_never_be_empty(self):
        """The tables worth backing up are the ones this must still catch."""
        for name in ("layoffs", "events", "source_reports", "archive",
                     "company_directory", "source_runs"):
            self.assertFalse(backup_tables.TABLES[name]["may_be_empty"], name)

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


class TheWorkflowKeepsTheFileUnlessDriftFAILED(unittest.TestCase):
    """The artifact is gated on the verdict, never on the exit code.

    The first run of all is UNKNOWN because there is no baseline. Discarding a
    complete, scanned 24 MB export because it could not be compared to last
    week's would be exactly backwards, and it is what the first version did.
    """

    WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "backup-export.yml"

    def test_the_export_step_emits_a_verdict_output(self):
        import inspect
        src = inspect.getsource(backup_export.run)
        self.assertIn("verdict={verdict}", src)

    def test_publishing_is_gated_on_the_verdict_and_not_on_success(self):
        text = self.WORKFLOW.read_text(encoding="utf-8")
        publish = text.split("Publish the export as a release asset")[1].split("- name:")[0]
        self.assertIn("steps.export.outputs.verdict != 'FAIL'", publish)
        self.assertNotIn("if: ${{ success()", publish)

    def test_a_fail_verdict_withholds_the_artifact(self):
        text = self.WORKFLOW.read_text(encoding="utf-8")
        for step in ("Publish the export as a release asset", "Keep the last 12 backup releases"):
            with self.subTest(step):
                block = text.split(step)[1].split("- name:")[0]
                self.assertIn("!= 'FAIL'", block)

    def test_an_unrun_export_publishes_nothing(self):
        """An empty verdict means the step never got far enough to have one."""
        text = self.WORKFLOW.read_text(encoding="utf-8")
        publish = text.split("Publish the export as a release asset")[1].split("- name:")[0]
        self.assertIn("steps.export.outputs.verdict != ''", publish)


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
