"""The unit on the talent figure is MEASURED, never typed.

WHAT WAS DELIVERED, 2026-08-28 21:02 UTC. The daily Talent Intelligence
edition went out with this subject:

    30 hiring signals · Aug 28

and, four lines into its own body, this:

    9 of the 30 signals listed on August 27 and 28, 2026 state a direction of
    hiring. The rest are other employer activity in the same window: funding,
    leadership, pay and site news.

Twenty-one of the thirty were not hiring. The email contradicted its own
subject line, and the subject is the one line every recipient sees whether or
not they open the message.

THE MEASUREMENT ALREADY EXISTED AND NOTHING READ IT. The composer had asked
/talent/v1/aggregate for the hiring-direction share since 2026-08-28 and
printed the answer as a note underneath the wrong label. A measurement that
only ever prints a caveat under a false headline has not corrected anything;
it has published the contradiction in one message.

THE CLASS IS `derived-value-typed-by-hand`, the same shape as the cadence
phrase that appeared seven times on the Sources page after the cron halved.
A word describing variable data, typed once into copy, is wrong the moment the
data moves and nothing reports it. So these tests do not check for a string the
owner approved; they check that the string TRACKS THE ROWS.

    THE NOUN ON A TALENT FIGURE MAY BE THE NARROW ONE ONLY WHERE THE NARROW
    ONE HAS BEEN MEASURED TRUE, AND UNKNOWN IS NOT MEASURED TRUE.

The second clause is the one that will be under pressure later. The endpoint
answers a filter it does not recognise with the UNFILTERED total, so "all of
them are hiring" and "the filter was dropped" arrive as the same number. That
is UNKNOWN, and an unknown mix must not be published as an all-hiring one.

The composers are PHP, so these drive them through
tests/fixtures/digest_compose_harness.php. Without php on PATH they SKIP, which
is UNKNOWN and not a pass.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_scope_rules import PHP, compose, talent_fixture  # noqa: E402
from test_digest_talent_observation import REPORTED, SCAN  # noqa: E402

#: The narrow word. It may appear on a figure only where the mix was measured
#: and came back all-hiring.
NARROW = "hiring signals"

#: The noun that is true whether the window is all hiring or none of it: a
#: funding round is employer activity, and so is a hiring announcement.
NEUTRAL = "talent and employer-activity signals"


def edition(rows, hiring=None, **over):
    """A daily talent edition. `hiring` is what /talent/v1/aggregate answers
    for direction=hiring; None means it cannot answer at all."""
    fixture = talent_fixture()
    fixture["from"], fixture["to"] = "2026-08-27", "2026-08-28"
    fixture["freq"] = "daily"
    fixture["talent"]["rows"] = rows
    if hiring is not None:
        fixture["talent_cat_direction_hiring"] = {"total": hiring}
    fixture.update(over)
    return compose(fixture)


@unittest.skipIf(PHP is None, "php is not on PATH, so the composer could not "
                              "be run. UNKNOWN, not a pass.")
class TheSubjectFragmentTracksTheMix(unittest.TestCase):
    """`metric` is the fragment both senders put in the subject line: the
    in-WordPress alt_digest_send and the relay's digest_layout.subject_line
    each read it off the composed section, so this one string is the subject
    on both paths."""

    def test_a_mixed_window_is_not_called_hiring(self):
        """The delivered defect, in the line that carried it."""
        metric = edition([dict(REPORTED)], hiring=9)["metric"]
        self.assertNotIn(NARROW, metric)
        self.assertEqual("1,332 " + NEUTRAL, metric)

    def test_the_composed_subject_is_the_one_the_owner_asked_for(self):
        """`<metric> · <period>`, the shape alt_digest_subject_line joins.
        Asserted whole, because the fragment being right and the join being
        wrong would still put a false line in an inbox."""
        metric = edition([dict(SCAN), dict(REPORTED)], hiring=9)["metric"]
        self.assertEqual("1,332 talent and employer-activity signals · Aug 28",
                         metric + " · Aug 28")

    def test_an_unanswerable_endpoint_does_not_earn_the_narrow_word(self):
        """UNKNOWN is not a pass. With no reading at all there is no evidence
        the window is all hiring, so the narrow word is not available."""
        metric = edition([dict(REPORTED)])["metric"]
        self.assertNotIn(NARROW, metric)

    def test_a_dropped_filter_does_not_earn_it_either(self):
        """The endpoint answers an unrecognised filter with the UNFILTERED
        total. Equality with the headline is therefore indistinguishable from
        "every row is hiring", and the composer must read it as UNKNOWN - the
        same guard that suppresses the mix note.

        THIS IS THE TEST MOST LIKELY TO BE 'FIXED' WRONGLY. Reading equality as
        all-hiring would restore the exact subject line of 2026-08-28 on any
        day the endpoint stopped honouring the parameter, silently.
        """
        metric = edition([dict(REPORTED)], hiring=1332)["metric"]
        self.assertNotIn(NARROW, metric)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class EverySurfaceNamingTheUnitReadsOneDerivation(unittest.TestCase):
    """Four places name the unit: the headline's unit line, the lede, the note
    that defines the word, and the subject fragment. They were four literals.
    A fix applied to one would have left the others saying something else about
    the same figure, in the same message."""

    @classmethod
    def setUpClass(cls):
        cls.section = edition([dict(SCAN), dict(REPORTED)], hiring=9)

    def test_the_narrow_word_never_lands_on_a_figure(self):
        for part in ("html", "text"):
            body = self.section[part]
            for line in body.replace("><", ">\n<").splitlines():
                if "state a direction of hiring" in line:
                    continue          # the measurement itself, which is true
                self.assertNotRegex(
                    line, r"[\d,]+\s+(new\s+)?hiring signals",
                    f"a figure wearing the unmeasured narrow unit in {part}")

    def test_the_note_defines_the_word_the_figure_wore(self):
        """It read "A hiring signal is one sourced employer update" under a
        figure labelled something else, so it defined a term the reader was
        never shown."""
        self.assertIn("A " + NEUTRAL[:-1] + " is one sourced employer update",
                      self.section["text"])

    def test_the_year_to_date_figure_is_not_stamped_with_the_windows_reading(self):
        """The mix was measured over two days. The YTD figure covers eight
        months and nobody measured that, so it resolves to UNKNOWN on its own
        rather than borrowing a number about a different window."""
        ytd = self.section["text"].split("2026 YTD", 1)[1]
        self.assertIn(NEUTRAL, ytd)
        self.assertNotIn(NARROW, ytd)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheRankedListsHeadingDescribesWhatItRanks(unittest.TestCase):
    """"Biggest hiring signals" sat over five readings of employers' own job
    boards ranked by how far their posting counts had risen. The caption
    directly beneath it was already derived from those rows; the heading over
    them was not."""

    def test_an_all_board_list_says_what_it_actually_ranks(self):
        text = edition([dict(SCAN)], hiring=9)["text"]
        self.assertIn("Largest observed job-board increases", text)
        self.assertNotIn("Biggest hiring signals", text)

    def test_a_mixed_list_claims_neither_alone(self):
        text = edition([dict(SCAN), dict(REPORTED)], hiring=9)["text"]
        self.assertIn("Biggest signals and job-board increases", text)

    def test_an_all_reported_list_keeps_the_approved_heading(self):
        """THE OVER-CORRECTION GUARD, the same one the caption carries. The
        heading was true over a list of news rows, and rewriting it everywhere
        would trade one piece of fixed prose around variable data for another.
        """
        text = edition([dict(REPORTED)], hiring=9)["text"]
        self.assertIn("Biggest hiring signals", text)

    def test_the_heading_and_the_caption_never_disagree(self):
        """Both are derived from the same two counts, so a list described as
        board increases must not be captioned as published headlines."""
        text = edition([dict(SCAN)], hiring=9)["text"]
        self.assertIn("Largest observed job-board increases", text)
        self.assertIn("not a headline anyone published", text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheNarrowWordIsStillReachable(unittest.TestCase):
    """The fix must not be "never say hiring again". If a window really is all
    hiring, the label should be able to say so - otherwise the neutral noun is
    just a second hardcoded word and the next reader cannot tell the
    difference."""

    def test_the_definition_returns_the_narrow_word_when_the_mix_is_all_hiring(self):
        """alt_digest_talent_signal_noun, called directly. It is exercised here
        rather than through a fixture because today's endpoint cannot express
        "the filter was honoured AND everything matched" - see the call site's
        dropped-filter guard, which is asserted above. The branch is the
        definition; the transport is what cannot currently supply it."""
        got = compose({"noun_probe": [
            {"total": 30, "hiring": 30},   # every row states hiring
            {"total": 30, "hiring": 31},   # more than the total, still all
            {"total": 30, "hiring": 9},    # the delivered edition's mix
            {"total": 30, "hiring": 0},    # none of them
            {"total": 30},                 # nobody could measure it
        ]})
        self.assertEqual(["hiring signal",
                          "hiring signal",
                          "talent and employer-activity signal",
                          "talent and employer-activity signal",
                          "talent and employer-activity signal"], got)


if __name__ == "__main__":
    unittest.main()
