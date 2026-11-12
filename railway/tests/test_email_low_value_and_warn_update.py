"""Two defects the 2026-11-11 daily edition carried (audit 2026-11-12).

1. Ohio's amended notice arrives as "Update Marc Glassman, Inc." with no
   colon, so the "Update:" stripper missed it and the same 55-job layoff was
   listed twice (rows 179293 and 179254). A bare "Update " before a corporate
   name is the revision marker; a company actually called "Update Software AG"
   keeps its name.
2. The daily list showed up to 40 rows, down to 33-job notices, with no "See
   all". The daily now shows the ten largest and links the rest.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import warn_import as W  # noqa: E402
from test_digest_briefing import PHP, base_fixture, compose, row  # noqa: E402


class AmendedNoticeName(unittest.TestCase):
    def test_bare_update_prefix_is_stripped(self):
        self.assertEqual(W._clean_company("Update Marc Glassman, Inc."), "Marc Glassman, Inc.")
        self.assertEqual(W._clean_company("UPDATE Acme Foods LLC"), "Acme Foods LLC")
        self.assertEqual(W._clean_company("Update: Acme Foods LLC"), "Acme Foods LLC")

    def test_a_company_named_update_is_kept(self):
        self.assertEqual(W._clean_company("Update Software AG"), "Update Software AG")
        self.assertEqual(W._clean_company("Updater Inc."), "Updater Inc.")


@unittest.skipIf(PHP is None, "php is not on PATH.")
class DailyListIsTheTopTen(unittest.TestCase):
    def test_daily_lists_ten_and_links_the_rest(self):
        fx = base_fixture()
        fx.update({"freq": "daily", "from": "2026-11-01", "to": "2026-11-01"})
        extra = [row(200 + i, f"Small Co {i}", 10 + i, state="OH",
                     source_name="OH WARN notice") for i in range(12)]
        fx["layoff_rows"] += extra
        add = sum(r["job_count"] for r in extra)
        fx["layoff"]["totals"]["jobs"] += add
        fx["layoff"]["map_countries"][0][1] += add
        fx["layoff"]["map_countries"][0][4] += add
        out = compose(fx)
        cards = re.findall(r'data-alt="card-figure"', out["html"])
        self.assertEqual(len(cards), 10)
        self.assertIn("See 8 more verified entries today", out["text"])


if __name__ == "__main__":
    unittest.main()
