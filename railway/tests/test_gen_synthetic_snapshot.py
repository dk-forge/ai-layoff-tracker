"""Synthetic snapshot generation never needs a database."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gen_synthetic_snapshot as snapshot


class SyntheticSnapshot(unittest.TestCase):
    def test_seed_reproduces_rows_without_changing_global_random(self):
        import random
        state = random.getstate()
        self.assertEqual(snapshot._rows(8, 17), snapshot._rows(8, 17))
        self.assertNotEqual(snapshot._rows(8, 17), snapshot._rows(8, 18))
        self.assertEqual(random.getstate(), state)

    def test_empty_request_has_no_rows(self):
        self.assertEqual(snapshot._rows(0, 17), [])

    def test_rows_have_synthetic_names_and_consistent_source_tiers(self):
        rows = snapshot._rows(100, 17)
        self.assertEqual([row[0] for row in rows], list(range(1, 101)))
        for row in rows:
            self.assertEqual(len(row), 14)
            self.assertTrue(row[1].startswith("Synthetic Co "))
            self.assertEqual(row[10], snapshot.VERIF[row[9]])
            if row[5] != "United States":
                self.assertEqual(row[7], "")
            if row[9] == "warn":
                self.assertEqual((row[11], row[12], row[13]), (0, "", ""))

    def test_wrong_count_type_fails_instead_of_producing_rows(self):
        with self.assertRaises(TypeError):
            snapshot._rows("three", 17)

    def test_cli_writes_only_the_requested_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "fixture.sql"
            with patch.object(sys, "argv", ["snapshot", "--rows", "2", "--out", str(out)]), contextlib.redirect_stdout(io.StringIO()):
                snapshot.main()
            sql = out.read_text()
            self.assertIn(snapshot.DDL, sql)
            self.assertEqual(sql.count("INSERT INTO wp_alt_layoffs"), 1)
            self.assertEqual(sql.count("Synthetic Co "), 2)
