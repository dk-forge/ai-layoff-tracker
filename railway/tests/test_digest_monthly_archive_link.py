"""The monthly email never links an archive page that does not exist yet.

An edition goes public only after the send is recorded, and the monthly window
is the month so far, so "This edition in the archive" 404ed (audit 2026-11-15).
"""
import os
import re
import shutil
import unittest

import edition_size_fixture as fx

BRIEFING = os.path.join(os.path.dirname(__file__), "..", "..", "wordpress-plugin",
                        "ai-layoff-tracker", "includes", "digest-briefing.php")


@unittest.skipUnless(shutil.which("php"), "php not installed")
class MonthlyArchiveLink(unittest.TestCase):
    def test_unpublished_monthly_has_no_edition_link(self):
        _msg, lay, _tal = fx.build()
        self.assertNotRegex(lay["html"], r"/editions/monthly/")
        self.assertNotIn("This edition in the archive", lay["text"])
        self.assertNotRegex(lay["text"], r"editions/monthly/")


class Source(unittest.TestCase):
    def test_rule_is_in_the_composer(self):
        src = open(BRIEFING, encoding="utf-8").read()
        self.assertIn("alt_edition_get('monthly', $slug)", src)
        self.assertIn("Previous monthly edition in the archive", src)
        # A previous edition is never cited as THIS one.
        self.assertRegex(src, r"\$edition !== '' && \$edition_is_current")
        # The previous edition must come from a COMPLETE month.
        self.assertRegex(src, r"\(string\) \$row\['window_to'\] < \$month_start")


if __name__ == "__main__":
    unittest.main()
