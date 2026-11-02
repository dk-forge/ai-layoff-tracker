"""Biggest cuts shows every cut in the period (owner "remove the cap", 2026-11-02).

The layoff edition used to print the five largest rows only. It now prints
every row the window holds, grouped by region as before, up to 40; past 40 it
prints the 40 largest and one "See all N on the tracker" link to the tracker
page for the same window. HTML and plain text say the same thing.
Without php on PATH these SKIP, which is not a pass.
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from test_digest_talent_activity import compose, PHP  # noqa: E402
from test_digest_dimension_blocks import layoff_fixture  # noqa: E402

DB_PHP = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker", "includes", "db.php"))


def fixture(n):
    f = layoff_fixture()
    f["layoff"]["leaders"] = [
        {"company_name": f"Cutco {i:02d}", "job_count": 10000 - i * 10,
         "layoff_date": "2026-08-12", "location": "TX", "state": "TX",
         "country": "United States", "permalink": "", "announced": False,
         "source_url": ""}
        for i in range(1, n + 1)]
    return f


def names(blob):
    return sorted(set(re.findall(r"Cutco \d\d", blob)))


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class EveryCutShown(unittest.TestCase):

    def test_twelve_items_all_shown(self):
        out = compose(fixture(12))
        for part in ("html", "text"):
            self.assertEqual(len(names(out[part])), 12, part)
            self.assertNotIn("See all", out[part], part)

    def test_fifty_five_items_forty_and_see_all(self):
        out = compose(fixture(55))
        for part in ("html", "text"):
            got = names(out[part])
            self.assertEqual(len(got), 40, part)
            # The 40 largest by size: Cutco 01..40.
            self.assertIn("Cutco 40", got)
            self.assertNotIn("Cutco 41", got)
            self.assertIn("See all 55 on the tracker", out[part], part)
        self.assertRegex(out["html"],
                         r'<a href="[^"]*ai-layoff-tracker[^"]*"[^>]*>See all 55 on the tracker</a>')


class LeadersFetchIsWideEnough(unittest.TestCase):
    """The aggregate's leaders block was LIMIT 24; the digest must be able to
    ask for more, and the cache key must tell the two requests apart."""

    def test_leaders_limit_param(self):
        src = open(DB_PHP, encoding="utf-8").read()
        self.assertIn("'leaders_limit'", src)
        self.assertNotRegex(src, r"ORDER BY job_count DESC, id DESC LIMIT 24\"")


if __name__ == "__main__":
    unittest.main()
