"""The region bars are ALL verified cuts, not the AI-attributed figure above them.

The 2026-11-08 weekly printed the region rows (summing to 134,595, the week's
verified total) directly under "AI-attributed: 61,700 this week", with no
label of their own in the HTML, so a reader took the bars for an AI split.
The text part already said "By region:". The HTML now says what the bars count.
"""
import re
import unittest

from test_digest_briefing import PHP, base_fixture, compose


@unittest.skipIf(PHP is None, "php is not on PATH.")
class RegionLabel(unittest.TestCase):

    def test_html_names_what_the_region_bars_count(self):
        out = compose(base_fixture())
        html = out["html"]
        ai = html.index("AI-attributed:")
        rows = html.index("North America", ai)
        between = re.sub(r"<[^>]+>", " ", html[ai:rows])
        self.assertIn("Verified job cuts by region", between)

    def test_text_names_what_the_region_rows_count(self):
        out = compose(base_fixture())
        self.assertIn("Verified job cuts by region:", out["text"])
