"""The public /archive-coverage route must not run the raw scans per request.

Regression for live-surface-check run 39191197293 (2026-10-19): the route called
alt_archive_coverage_counts() uncached; three unindexable MD5 join scans on
every cache-busted hit, and one 500'd on the shared host. Offline source read.
"""
import pathlib
import re
import unittest

DB = (pathlib.Path(__file__).resolve().parents[2] / "wordpress-plugin"
      / "ai-layoff-tracker" / "includes" / "db.php").read_text(encoding="utf-8")


def _body(name):
    m = re.search(r"function " + name + r"\([^)]*\)\s*\{(.*?)\n\}", DB, re.S)
    assert m, name
    return m.group(1)


class ArchiveCoverageRouteCached(unittest.TestCase):
    def test_route_uses_the_cached_reader(self):
        body = _body("alt_api_archive_coverage")
        self.assertIn("alt_archive_coverage_counts_cached()", body)
        self.assertNotRegex(body, r"alt_archive_coverage_counts\(\)")

    def test_cache_is_a_transient_keyed_on_data_version(self):
        body = _body("alt_archive_coverage_counts_cached")
        self.assertIn("alt_figure_cache_key(", body)
        self.assertIn("set_transient(", body)


if __name__ == "__main__":
    unittest.main()
