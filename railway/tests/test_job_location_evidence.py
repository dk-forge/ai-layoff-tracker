"""A supported quote is not an answering quote, pinned on the four that proved it.

The 2026-08-18 blank-country re-read fetched 31 readable source bodies, spent
$0.0093 and returned four "recovered" countries. Every one passed the verbatim
quote gate that guards every other evidence path in this module. Three of the
four still could not place a row, and one of those three would have published a
wrong country:

  Zepz -> Poland, quoting "closure of business units in Kenya and Poland"
  Bosch -> Germany, quoting a nationwide PROTEST that names no country
  Thermo Fisher -> United States, quoting two city names and no country
  Stellantis -> United States, quoting "U.S. plant workers"

The quotes below are copied verbatim from that run. Only the last one states
the answer, and only the last one may be written.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import (  # noqa: E402
    _canonical_country, _countries_named_in, _enclosing_sentence,
    _quote_names_exactly,
)

#: The two sentences that put a wrong country on the live site on 2026-08-19,
#: copied verbatim from the sources. Both name two countries; the model quoted
#: a single-country slice of each, and a quote-only check let both through.
ZEPZ_BODY = (
    "As part of the cost-cutting exercise, Zepz also proposed the closure of "
    "business units in Kenya and Poland. Mark Lenhard, CEO of U.K.-based "
    "remittances platform Zepz."
)
CINEVERSE_BODY = (
    "There are 145 employees based in the U.S. and 155 based in India. Watch "
    "on Deadline During the quarter, total revenue nearly tripled."
)
STELLANTIS_BODY = (
    "Stellantis will indefinitely lay off up to 2,450 U.S. plant workers in "
    "Warren, Michigan, later this year as it discontinues production of an "
    "older version of its Ram 1500 pickup."
)


class TheTruncationEscape(unittest.TestCase):
    """A model can trim the disqualifying half out of a quote. It cannot trim
    the sentence the quote came from."""

    def test_the_zepz_truncation_is_refused_by_its_own_sentence(self):
        trimmed = "proposed the closure of business units in Kenya"
        # Quote-only: single country, passes. This is the defect.
        self.assertEqual(_countries_named_in(trimmed), {"Kenya"})
        # Sentence: two countries, refused.
        self.assertFalse(_quote_names_exactly("Kenya", trimmed, ZEPZ_BODY))
        self.assertFalse(_quote_names_exactly("Poland", trimmed, ZEPZ_BODY))

    def test_a_headcount_breakdown_is_refused_by_its_own_sentence(self):
        trimmed = "155 based in India"
        self.assertEqual(_countries_named_in(trimmed), {"India"})
        self.assertFalse(_quote_names_exactly("India", trimmed, CINEVERSE_BODY))

    def test_the_one_correct_row_still_passes_on_its_sentence(self):
        self.assertTrue(_quote_names_exactly(
            "United States", "U.S. plant workers", STELLANTIS_BODY))

    def test_the_sentence_is_the_one_the_quote_sits_in(self):
        sentence = _enclosing_sentence("155 based in India", CINEVERSE_BODY)
        self.assertIn("145 employees based in the U.S.", sentence)
        self.assertNotIn("Watch on Deadline", sentence)

    def test_a_quote_absent_from_the_body_falls_back_to_the_quote(self):
        # Never silently widen to the whole document: an unlocatable quote is
        # judged on itself, and _quote_is_supported has already refused it.
        self.assertEqual(_enclosing_sentence("not in here", ZEPZ_BODY), "not in here")

#: (label, model's country, the exact quote it returned, may this be written)
LIVE_RUN = [
    ("Zepz", "Poland",
     "proposed the closure of business units in Kenya and Poland", False),
    ("Bosch", "Germany",
     "Bundesweit gehen 25.000 Beschäftigte auf die Straße.", False),
    ("Thermo Fisher", "United States", "Cambridge and Plainville", False),
    ("Stellantis", "US", "U.S. plant workers", True),
]


class CanonicalCountry(unittest.TestCase):
    def test_the_models_shorthand_resolves_to_the_stored_label(self):
        for value in ("US", "us", "U.S.", "usa", "United States", "america"):
            self.assertEqual(_canonical_country(value), "United States", value)
        self.assertEqual(_canonical_country("uk"), "United Kingdom")
        self.assertEqual(_canonical_country("Brazil"), "Brazil")

    def test_a_value_that_is_not_a_country_resolves_to_nothing(self):
        for value in ("", None, "  ", "North Carolina", "EMEA", "Global",
                      "Multiple countries", "Bay Area"):
            self.assertEqual(_canonical_country(value), "", repr(value))


class CountriesNamedInAQuote(unittest.TestCase):
    def test_the_zepz_quote_names_two_countries(self):
        self.assertEqual(
            _countries_named_in("proposed the closure of business units in Kenya and Poland"),
            {"Kenya", "Poland"})

    def test_a_protest_sentence_names_no_country(self):
        self.assertEqual(
            _countries_named_in("Bundesweit gehen 25.000 Beschäftigte auf die Straße."),
            set())

    def test_city_names_are_not_countries(self):
        self.assertEqual(_countries_named_in("Cambridge and Plainville"), set())

    def test_an_abbreviation_counts_as_naming_the_country(self):
        self.assertEqual(_countries_named_in("U.S. plant workers"), {"United States"})

    def test_a_country_ending_a_sentence_still_counts(self):
        # "Poland." must not read as no country because of the full stop; that
        # is how the Kenya-and-Poland sentence would have passed anyway.
        self.assertEqual(_countries_named_in("units in Kenya and Poland."),
                         {"Kenya", "Poland"})
        self.assertEqual(_countries_named_in("cuts in Japan."), {"Japan"})


class TheGate(unittest.TestCase):
    def test_the_live_run_is_reduced_to_the_one_answering_quote(self):
        written = []
        for label, value, quote, allowed in LIVE_RUN:
            country = _canonical_country(value)
            passes = bool(country) and _quote_names_exactly(country, quote)
            self.assertEqual(passes, allowed, f"{label}: {quote!r}")
            if passes:
                written.append(label)
        self.assertEqual(written, ["Stellantis"])

    def test_a_quote_naming_a_second_country_is_refused_in_either_direction(self):
        quote = "closure of business units in Kenya and Poland"
        self.assertFalse(_quote_names_exactly("Poland", quote))
        self.assertFalse(_quote_names_exactly("Kenya", quote))

    def test_a_quote_naming_a_different_country_is_refused(self):
        self.assertFalse(_quote_names_exactly("Germany", "cuts at the Swedish plant"))

    def test_a_substring_of_a_longer_word_does_not_name_a_country(self):
        # "us" inside "campus", "chad" inside "Chadwick": a naive substring
        # test places rows on syllables.
        self.assertEqual(_countries_named_in("closing the campus"), set())
        self.assertEqual(_countries_named_in("Chadwick Road"), set())


if __name__ == "__main__":
    unittest.main()
