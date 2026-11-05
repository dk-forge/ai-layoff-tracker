"""The 8-K window anchors on the Item 2.05 HEADING, not on a reference to it.

HubSpot's 2026-10-06 8-K (accession 0001193125-26-414965) opens with an
Item 2.02 paragraph that says "the restructuring plan ... described in Item
2.05 below". `_primary_window` took the first match of the keyword
"item 2.05", which was that forward reference, about 1,200 characters before
the heading. The 3,000-character window still reached the disclosure in that
filing, but only because its Item 2.02 text was short: a longer Item 2.02 or
Item 7.01 block pushes the real Item 2.05 sentence, and its headcount, past
the window, and `extractor._count_in_text` then refuses a count the filing
does state. The window must start at the heading.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import edgar  # noqa: E402

FILLER = ("The information under this Item 2.02 is furnished and shall not be "
          "deemed filed for purposes of Section 18 of the Exchange Act. ") * 40

HUBSPOT_SHAPE = (
    "Item 2.02. Results of Operations and Financial Condition. The costs "
    "associated with the restructuring plan (the Plan) described in Item 2.05 "
    "below will be excluded from non-GAAP results. " + FILLER +
    "Item 2.05. Costs Associated with Exit or Disposal Activities. On October 1, "
    "2026, the Board authorized the Plan, which eliminates approximately 660 "
    "positions. Item 7.01. Regulation FD Disclosure."
)


class Item205AnchorTest(unittest.TestCase):
    def test_window_starts_at_the_heading_not_the_forward_reference(self):
        window, section = edgar._primary_window(HUBSPOT_SHAPE)
        self.assertIn("approximately 660 positions", window)
        self.assertEqual(section, "item_2.05")

    def test_heading_with_no_period_or_line_break_is_still_found(self):
        text = ("See Item 2.05 below. " + FILLER +
                "ITEM 2.05 COSTS ASSOCIATED WITH EXIT OR DISPOSAL ACTIVITIES\n"
                "The Company will reduce its workforce by 120 employees.")
        window, _ = edgar._primary_window(text)
        self.assertIn("120 employees", window)

    def test_no_heading_falls_back_to_the_first_keyword(self):
        text = "Intro. " * 10 + "The Company announced a reduction in force of 75 employees."
        window, _ = edgar._primary_window(text)
        self.assertIn("75 employees", window)


if __name__ == "__main__":
    unittest.main()
