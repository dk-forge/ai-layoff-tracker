"""Owner ruling 2026-11-13: in the email, place a row with no job location by
its employer's headquarters, labelled as such.

The 2026-W45 weekly printed "Not recorded 69,026" of 134,595 (51%): news rows
that name the employer but not where the jobs are. The row's
employer_country (curated HQ or the filing entity) is known for many of
them. The region bars now place those jobs under the HQ's region as a
separate "by employer HQ" sub-line, so the bars still sum to the worldwide
figure and a reader can see which part is job location and which is HQ.
The United States stat and the country list stay strict job location
(CLAUDE.md: headline stats are job-location; only the email bars change).
"""
import copy
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_digest_briefing import PHP, base_fixture, compose  # noqa: E402


def _block(text):
    return text.split("Verified job cuts by region:")[1].split("Provisional")[0]


def _with_hq(fx, country="United States"):
    fx = copy.deepcopy(fx)
    for r in fx["layoff_rows"]:
        if r["id"] == 6:  # "Unknown Place Co", 20 jobs, country ""
            r["employer_country"] = country
    return fx


@unittest.skipIf(PHP is None, "php is not on PATH.")
class PlacedByEmployerHQ(unittest.TestCase):

    def test_unlocated_row_moves_to_its_hq_region_labelled(self):
        out = compose(_with_hq(base_fixture()))
        block = _block(out["text"])
        self.assertNotIn("Not recorded", block)
        self.assertIn("by employer HQ 20", block)
        self.assertIn("North America (US 932 · rest of North America 175 · by employer HQ 20): 1,127", block)
        self.assertEqual(out["held"], [])

    def test_bars_still_sum_to_worldwide(self):
        block = _block(compose(_with_hq(base_fixture(), "Germany"))["text"])
        rows = re.findall(r"^\s{4}(\S.*): ([\d,]+)$", block, re.M)
        self.assertEqual(sum(int(n.replace(",", "")) for _, n in rows), 1220)
        self.assertIn("Europe (UK 40 · other Europe 53 · by employer HQ 20): 113", block)

    def test_us_stat_stays_job_location(self):
        text = compose(_with_hq(base_fixture()))["text"]
        self.assertIn("United States: 932 verified job cuts", text)

    def test_a_note_says_how_many_were_placed_by_hq(self):
        text = compose(_with_hq(base_fixture()))["text"]
        self.assertIn("20 jobs with no job location are placed by the employer's headquarters", text)

    def test_without_employer_country_nothing_changes(self):
        block = _block(compose(base_fixture())["text"])
        self.assertIn("Not recorded: 20", block)
        self.assertNotIn("employer HQ", block)

    def test_a_multi_country_hq_is_not_a_place(self):
        block = _block(compose(_with_hq(base_fixture(), "Multiple countries"))["text"])
        self.assertIn("Not recorded: 20", block)


if __name__ == "__main__":
    unittest.main()
