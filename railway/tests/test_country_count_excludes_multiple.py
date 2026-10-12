"""'Multiple countries' is a placeholder, not a place, so no published country
count may include it (bug 2026-10-12: the tracker page showed "82 countries ·
all time" beside a ribbon saying 81).

Three surfaces count countries: the aggregate totals in includes/db.php (API
totals.countries and the "countries · <year>" chip, which reads the same
aggregate under the page's date_from), the all-time chip in
templates/page-tracker.php, and alt_coverage_counts() in the main plugin file.
This test lifts each one's country expression out of the PHP and runs it on
the same seeded rows, so they cannot drift apart again.
"""
import re
import sqlite3
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin/ai-layoff-tracker"
DB_PHP = (PLUGIN / "includes/db.php").read_text()
TPL = (PLUGIN / "templates/page-tracker.php").read_text()
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text()


def _expr(src, alias):
    """The SELECT expression in `src` aliased `alias` that counts country."""
    m = re.search(r"^\s*(?:SELECT )?(COUNT\(DISTINCT [^\n]*country[^\n]*?)\s+%s,?\s*$" % alias, src, re.M)
    assert m, "no country count aliased %r" % alias
    return m.group(1).rstrip(", ")


def _count(sql):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE t (country TEXT, layoff_date TEXT)")
    con.executemany("INSERT INTO t VALUES (?, ?)", [
        ("United States", "2026-03-01"), ("United States", "2025-03-01"),
        ("United Kingdom", "2026-04-01"), ("Multiple countries", "2026-05-01"),
        ("", "2026-05-02")])
    return con.execute(sql).fetchone()[0]


class CountryCountExcludesMultiple(unittest.TestCase):
    def test_aggregate_totals(self):
        self.assertEqual(_count("SELECT %s FROM t" % _expr(DB_PHP, "countries")), 2)

    def test_aggregate_totals_in_a_year_window(self):
        sql = "SELECT %s FROM t WHERE layoff_date >= '2026-01-01'" % _expr(DB_PHP, "countries")
        self.assertEqual(_count(sql), 2)

    def test_all_time_chip(self):
        self.assertEqual(_count("SELECT %s FROM t" % _expr(TPL, "c")), 2)

    def test_coverage_ribbon_agrees(self):
        m = re.search(r"SELECT COUNT\(DISTINCT country\) FROM \$t (WHERE [^\"]+)\"", MAIN)
        self.assertTrue(m)
        self.assertEqual(_count("SELECT COUNT(DISTINCT country) FROM t " + m.group(1)), 2)

    def test_chip_cache_key_changed(self):
        # The old key holds 82 for an hour after deploy.
        self.assertNotIn("alt_figure_cache_key('fresh_alltime')", TPL)


if __name__ == "__main__":
    unittest.main()
