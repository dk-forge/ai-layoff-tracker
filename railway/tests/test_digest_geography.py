"""Geography in both editions (owner, 2026-10-19: "still not by geography ...
State and country?").

The talent edition gains a "Where" block: signals by country (top 8, then
"and N more countries", N measured from the endpoint's distinct count, not a
capped list) and US signals by state (top 8). The layoff edition's country
line grows to 8 and its US state line to 10, each ending "and N more".

Rendered from fixture data through the real composer; no network. Without php
on PATH these SKIP, which is not a pass.
"""
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from test_digest_talent_activity import compose, PHP  # noqa: E402
from test_digest_talent_redesign import daily  # noqa: E402
from test_digest_dimension_blocks import layoff_fixture, _tuple  # noqa: E402

CODES = [("US", 14), ("GB", 7), ("IN", 5), ("DE", 4), ("FR", 3), ("CA", 3),
         ("BR", 2), ("JP", 2), ("AU", 1), ("PL", 1), ("ES", 1)]
NAMES = {"US": "United States", "GB": "United Kingdom", "IN": "India",
         "DE": "Germany", "FR": "France", "CA": "Canada", "BR": "Brazil",
         "JP": "Japan", "AU": "Australia"}
STATES = [("CA", 5), ("NY", 3), ("TX", 2), ("WA", 1), ("MA", 1), ("IL", 1),
          ("GA", 1), ("OR", 1), ("CO", 1), ("FL", 1)]


def talent(**over):
    f = daily()
    f["country_names"] = NAMES
    # 13 distinct countries, though only 11 came back in the capped list.
    f["talent_geo"] = {"total": 45, "countries": 13,
                       "by_country": [{"k": k, "n": n} for k, n in CODES]}
    f["talent_geo_us"] = {"total": 18,
                          "by_state": [{"k": k, "n": n} for k, n in STATES]}
    f.update(over)
    return f


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class TalentWhere(unittest.TestCase):
    def test_country_and_state_lines(self):
        out = compose(talent())
        text = out["text"]
        self.assertIn("\nWhere\n", text)
        line = text.split("signals by country", 1)[1].split("\n", 1)[0]
        for name in ("United States 14", "United Kingdom 7", "India 5",
                     "Germany 4", "France 3", "Canada 3", "Brazil 2", "Japan 2"):
            self.assertIn(name, line)
        self.assertNotIn("Australia", line)
        self.assertTrue(line.endswith(", and 5 more countries."), line)
        sline = text.split("US signals by state: ", 1)[1].split("\n", 1)[0]
        self.assertTrue(sline.startswith("California 5"), sline)
        self.assertIn("New York 3", sline)
        self.assertTrue(sline.endswith(", and 2 more states."), sline)
        self.assertIn("<h3>Where</h3>", out["html"])
        self.assertIn("country=US", out["html"])
        # The block sits before the year-to-date figure, inside the edition.
        self.assertLess(text.index("\nWhere\n"), text.index("YTD"))

    def test_counts_signals_not_money(self):
        text = compose(talent())["text"]
        line = text.split("\nWhere\n", 1)[1].split("YTD", 1)[0]
        self.assertNotIn("$", line)

    def test_failed_call_prints_nothing(self):
        f = talent()
        del f["talent_geo"]
        self.assertNotIn("\nWhere\n", compose(f)["text"])

    def test_ignored_us_filter_drops_the_state_line(self):
        f = talent(talent_geo_us={"total": 45, "by_state": [
            {"k": "CA", "n": 30}, {"k": "NY", "n": 15}]})
        text = compose(f)["text"]
        self.assertIn("\nWhere\n", text)
        self.assertNotIn("US signals by state", text)


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class LayoffGeography(unittest.TestCase):
    def setUp(self):
        f = layoff_fixture()
        f["layoff"]["top_countries"] = [_tuple(c, 9, v) for c, v in [
            ("United States", 7862), ("Brazil", 476), ("India", 400),
            ("Germany", 350), ("United Kingdom", 300), ("Canada", 250),
            ("France", 200), ("Japan", 150), ("Mexico", 120), ("Poland", 90)]]
        f["layoff"]["top_states"] = [_tuple(s, 9, v) for s, v in [
            ("CA", 5200), ("IL", 1800), ("TX", 1200), ("NY", 900), ("WA", 600),
            ("OH", 500), ("MI", 400), ("FL", 300), ("GA", 200), ("NC", 150),
            ("PA", 100), ("NJ", 50)]]
        self.text = compose(f)["text"]

    def test_top_eight_countries_then_more(self):
        line = self.text.split("\nTop countries\n", 1)[1].split("\n", 1)[0]
        self.assertIn("Japan 150", line)
        self.assertNotIn("Mexico", line)
        self.assertTrue(line.endswith(", and 2 more countries."), line)

    def test_top_ten_states_then_more(self):
        line = self.text.split("\nBy US state\n", 1)[1].split("\n", 1)[0]
        self.assertIn("North Carolina 150", line)
        self.assertNotIn("Pennsylvania", line)
        self.assertTrue(line.endswith(", and 2 more states."), line)

    def test_complete_list_says_nothing_more(self):
        text = compose(layoff_fixture())["text"]
        line = text.split("\nBy US state\n", 1)[1].split("\n", 1)[0]
        self.assertTrue(line.endswith("Washington 600."), line)


if __name__ == "__main__":
    unittest.main()
