"""Every column the plugin creates in company_directory must be pinned.

Regression for backup-export run 39105677784 (2026-10): 2.20.210 added
`admitted_by` to the plugin table without pinning it in backup_tables.py, so
the live export REFUSED the whole run. Read the CREATE TABLE offline.
"""
import pathlib
import re
import sys
import unittest

RAILWAY = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAILWAY))
import backup_tables  # noqa: E402

DB_PHP = RAILWAY.parent / "wordpress-plugin" / "ai-layoff-tracker" / "includes" / "db.php"


def _create_columns(var: str):
    src = DB_PHP.read_text(encoding="utf-8")
    m = re.search(r"CREATE TABLE \$" + var + r" \((.*?)\) \$charset", src, re.S)
    assert m, var
    cols = []
    for line in m.group(1).splitlines():
        w = line.strip().split(" ", 1)[0]
        if w and w.upper() not in ("PRIMARY", "UNIQUE", "KEY", "INDEX"):
            cols.append(w)
    return cols


class CompanyDirectoryParity(unittest.TestCase):
    def test_every_plugin_column_is_pinned(self):
        pinned = set(backup_tables.TABLES["company_directory"]["columns"])
        cols = _create_columns("directory")
        self.assertIn("admitted_by", cols)
        self.assertEqual([c for c in cols if c not in pinned], [])
        backup_tables.assert_columns_pinned("company_directory", cols)


if __name__ == "__main__":
    unittest.main()
