"""entity_resolution.typo_variant: a worklist hint for misspelled employers.

Synthetic names only. The keep-apart half matters most: a typo hint that fires
on two real, different employers sends a reviewer after a row that is fine.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import entity_resolution as er  # noqa: E402


class TypoVariant(unittest.TestCase):
    def test_flags_single_letter_typos(self):
        for a, b in [("Brightwater Logistics", "Brightwatter Logistics"),
                     ("Northfield Analytics Inc.", "Northfeild Analytics"),
                     ("Kestrelmont Foods", "Kestrelmount Foods LLC")]:
            with self.subTest(a=a, b=b):
                self.assertGreaterEqual(er.typo_variant(a, b), er.TYPO_MIN_SIMILARITY)

    def test_symmetric(self):
        self.assertEqual(er.typo_variant("Quillon Systems Group", "Quilon Systems Group"),
                         er.typo_variant("Quilon Systems Group", "Quillon Systems Group"))

    def test_keeps_apart_short_and_distinct_names(self):
        for a, b in [("Zentra", "Zentro"),           # too short to judge
                     ("Velmora Bank", "Delmora Mining"),
                     ("Orvane Labs", "Orvane Labs Europe Pharma"),  # token count differs
                     ("Calderon Steel", "Calderon Steel"),           # identical: not a typo
                     ("Calderon Steel Inc", "Calderon Steel Corp"),  # same key already
                     ("Halvex Motors", "Halvex Motors")]:
            with self.subTest(a=a, b=b):
                self.assertEqual(er.typo_variant(a, b), 0.0)

    def test_blank_and_non_latin_are_zero(self):
        self.assertEqual(er.typo_variant("", "Brightwater Logistics"), 0.0)
        self.assertEqual(er.typo_variant("捷豹路虎", "捷豹路虎汽车"), 0.0)

    def test_never_changes_same_entity(self):
        # The hint must stay a hint: identity is unchanged by its existence.
        self.assertFalse(er.same_entity("Brightwater Logistics", "Brightwatter Logistics"))


if __name__ == "__main__":
    unittest.main()
