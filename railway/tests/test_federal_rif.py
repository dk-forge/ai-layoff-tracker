"""Guards on the OPM federal-RIF collector.

The defect these exist for (found 2026-08-16): the collector read only the
NEWEST OPM reporting file and its docstring claimed each file was a rolling
24-month window that must never be summed. Both were false. OPM files are
INCREMENTAL batches — a month's bulk lives in its own file, and later files
carry only late-reported stragglers — so reading one file saw the trickle and
never the bulk. Effective-year 2025 landed as 47 RIF separations against a true
10,739.

Two properties are load-bearing and both are cheap to break by accident:
  1. the collector reads EVERY current file in its window, not the last one;
  2. a window it could not fully read raises instead of returning a short sum,
     because /bulk field-updates on hash match and a short total would
     OVERWRITE a correct larger one.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sources import federal_layoffs as fl  # noqa: E402


def _meta(*yms):
    return [{"year": ym[:4], "month": ym[4:], "version": 1,
             "filename": f"separations_{ym}_1", "current": True} for ym in yms]


class WindowDiscovery(unittest.TestCase):
    def test_every_file_in_the_window_is_read_not_just_the_newest(self):
        """The whole defect in one assertion."""
        files = _meta("202401", "202502", "202509", "202606")
        seen = []

        def fake_read(f, sums):
            seen.append(f["filename"])
            sums[("202509", "Agency X")] += 10
            return 10

        with mock.patch.object(fl, "_current_files", return_value=files), \
             mock.patch.object(fl, "_read_rif_counts", side_effect=fake_read):
            out = fl.pull_federal_rif(min_group=5, since="202401")

        self.assertEqual(len(seen), 4, f"read only {seen} — the newest-file defect is back")
        # 4 files x 10 summed, not 10 from the last file alone.
        self.assertEqual([e["job_count"] for e in out], [40])

    def test_effective_months_before_the_window_are_dropped_not_published_short(self):
        """Files in the window carry stragglers from BEFORE it. Those months are
        only partially covered, so publishing them would understate them."""
        def fake_read(f, sums):
            sums[("202301", "Old Agency")] += 500     # before the window
            sums[("202505", "In Agency")] += 60       # inside it
            return 560

        with mock.patch.object(fl, "_current_files", return_value=_meta("202505")), \
             mock.patch.object(fl, "_read_rif_counts", side_effect=fake_read):
            out = fl.pull_federal_rif(min_group=5, since="202401")

        names = [e["company_name"] for e in out]
        self.assertEqual(names, ["In Agency"], f"published a partially covered month: {names}")

    def test_min_group_drops_trivial_agency_months(self):
        def fake_read(f, sums):
            sums[("202505", "Tiny")] += 2
            sums[("202505", "Real")] += 40
            return 42

        with mock.patch.object(fl, "_current_files", return_value=_meta("202505")), \
             mock.patch.object(fl, "_read_rif_counts", side_effect=fake_read):
            out = fl.pull_federal_rif(min_group=5, since="202401")
        self.assertEqual([e["company_name"] for e in out], ["Real"])


class PartialSumsAreNeverReturned(unittest.TestCase):
    def test_a_failed_file_raises_rather_than_returning_a_short_sum(self):
        def fake_read(f, sums):
            if f["filename"].endswith("202509_1"):
                raise fl.FederalRifIncomplete("boom")
            sums[("202505", "Agency")] += 100
            return 100

        with mock.patch.object(fl, "_current_files", return_value=_meta("202505", "202509")), \
             mock.patch.object(fl, "_read_rif_counts", side_effect=fake_read):
            with self.assertRaises(fl.FederalRifIncomplete):
                fl.pull_federal_rif(min_group=5, since="202401")

    def test_an_empty_file_listing_raises(self):
        with mock.patch.object(fl, "_current_files", return_value=[]):
            with self.assertRaises(fl.FederalRifIncomplete):
                fl.pull_federal_rif(min_group=5, since="202401")

    def test_the_importer_posts_nothing_when_the_window_is_incomplete(self):
        sys.path.insert(0, str(ROOT))
        import federal_rif_import as imp
        with mock.patch.object(imp, "pull_federal_rif",
                               side_effect=fl.FederalRifIncomplete("half a window")), \
             mock.patch.object(imp, "report_source_health") as health, \
             mock.patch.object(imp.warn_import, "post_bulk") as post:
            with self.assertRaises(fl.FederalRifIncomplete):
                imp.main()
        post.assert_not_called()
        states = [c.args[1] for c in health.call_args_list]
        self.assertIn("degraded", states)


class TheDefinitionIsPinned(unittest.TestCase):
    """`federal_rif` means executed SH RIFs and nothing else. Widening it is an
    owner decision; this makes a silent widening fail loudly."""

    def test_only_the_SH_separation_category_is_selected(self):
        src = (ROOT / "sources" / "federal_layoffs.py").read_text()
        self.assertIn('separation_category_code"] == "SH"', src)
        for code in ('"SE"', '"SJ"', '"SC"', '"SD"'):
            self.assertNotIn(f'separation_category_code"] == {code}', src,
                             "a non-RIF separation category was folded into federal_rif")

    def test_the_drp_path_is_a_dry_run_that_posts_nothing(self):
        src = (ROOT / "sources" / "federal_layoffs.py").read_text()
        self.assertIn("def pull_federal_drp_dryrun", src)
        body = src.split("def pull_federal_drp_dryrun", 1)[1]
        self.assertNotIn("dedup_hash", body,
                         "the DRP dry run builds postable entries — it must only print")

    def test_entries_carry_the_federal_rif_source_type(self):
        e = fl._entry("Department Of Example", 42, "2026-05-01", "202605")
        self.assertEqual(e["source_type"], "federal_rif")
        self.assertEqual(e["country"], "United States")
        self.assertFalse(e["ai_explicit"])

    def test_the_dedup_hash_excludes_the_count_so_revisions_upsert_in_place(self):
        a = fl._entry("Agency", 10, "2026-05-01", "202605")["dedup_hash"]
        b = fl._entry("Agency", 999, "2026-05-01", "202605")["dedup_hash"]
        self.assertEqual(a, b, "a revised count would create a duplicate row")


if __name__ == "__main__":
    unittest.main()
