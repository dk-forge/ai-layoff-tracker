"""A job-board reading is an OBSERVATION we took, not a report somebody filed.

WHAT WAS DELIVERED. The daily talent edition of 2026-08-28 carried these four
statements, in one email, about the same rows:

    "Some signals are job-board scans, where a rise means the employer listed
     more active postings than our previous scan, not that it confirmed new
     openings."
    "... the signals naming the most jobs first ..."
    "Databricks's job board listed 23 more active postings in London than our
     previous scan (23 jobs, United Kingdom, Greenhouse, August 28, 2026)"
    "Each headline is quoted as its source published it, in that source's own
     language."

The first says a posting delta is not confirmed hiring. The second and third
then relabel those deltas "jobs" - the third contradicting its own headline
four words later. The fourth is a claim about provenance that is false for
every row in that edition: a job-board line is COMPOSED by the talent tracker's
own collector out of two readings of the board, and no source published it.

A FIFTH, in the same message: "0 of the 30 are verified against a primary
document. The rest are published indications we have not confirmed." Measured
against the committed database over that window: 27 rows, of which 10 are
readings of the employers' OWN Greenhouse/Ashby/Lever boards. A first-party
employer board is not an unconfirmed indication. "Who published it" and "what
it establishes" are two axes, and that sentence had one bin.

WHAT THESE TESTS HOLD.

    A row the tracker OBSERVED is never described in the words used for a row
    somebody REPORTED - not its count, not its date, not its provenance - and
    a list holding only reported rows still says exactly what it always said.

The last clause matters as much as the rest. The old caption was TRUE for a
list of news rows, so a fix that rewrote it for every list would have traded
one piece of fixed prose around variable data for another. It is derived from
the rows now, and the all-reported branch is pinned byte for byte.

The composers are PHP, so this drives them through
tests/fixtures/digest_compose_harness.php, exactly as
tests/test_digest_scope_rules.py does. Without php on PATH these SKIP, which
is UNKNOWN and not a pass.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_scope_rules import PHP, compose, talent_fixture  # noqa: E402


#: One reading of an employer's own careers board. The shape is the live one:
#: `collector` is what /talent/v1/query returns and what the talent tracker's
#: own pipeline/count_meaning.py keys its job-board test on, and the headline
#: is the sentence collectors/ats_boards.py composes.
SCAN = {
    "company": "Databricks",
    "headline": "Databricks's job board listed 23 more active postings in "
                "London than our previous scan (job board: 300 to 323)",
    "published_date": "2026-08-28",
    "headcount": 23,
    "collector": "ats_boards",
    "source_name": "Greenhouse",
    "source_url": "https://boards.greenhouse.io/databricks",
    "country": "GB",
}

#: A story an outlet actually published, for the mixed and reported-only cases.
REPORTED = {
    "company": "Sanad Service Centres",
    "headline": "create more than 2,200 jobs",
    "published_date": "2026-08-27",
    "headcount": 2200,
    "collector": "google_news",
    "source_name": "Gulf News",
    "source_url": "https://example.com/sanad",
    "country": "AE",
}

#: The old blanket provenance claim, which may only be printed over a list in
#: which it is true of every row.
BLANKET = ("Each headline is quoted as its source published it, in that "
           "source's own language.")


def edition(rows, **over):
    fixture = talent_fixture()
    fixture["from"], fixture["to"] = "2026-08-27", "2026-08-28"
    fixture["talent"]["rows"] = rows
    fixture.update(over)
    return compose(fixture)["text"]


@unittest.skipIf(PHP is None, "php is not on PATH, so the composer could not "
                              "be run. UNKNOWN, not a pass.")
class ABoardReadingIsNotCountedInJobs(unittest.TestCase):
    """"23 jobs" beside a headline reading "23 more active postings"."""

    @classmethod
    def setUpClass(cls):
        cls.text = edition([dict(SCAN), dict(REPORTED)])

    def test_the_delta_is_labelled_postings_and_not_jobs(self):
        self.assertIn("23 more postings listed", self.text)

    def test_the_word_jobs_never_lands_on_the_board_row(self):
        row = [l for l in self.text.splitlines() if "Databricks" in l][0]
        self.assertNotIn("23 jobs", row)

    def test_a_reported_row_still_names_jobs(self):
        """The fix is a distinction, not a retreat from the word. A source that
        said 2,200 jobs said jobs."""
        row = [l for l in self.text.splitlines() if "Sanad" in l][0]
        self.assertIn("2,200 jobs", row)

    def test_the_board_date_says_it_is_a_reading_and_not_a_publication(self):
        """The collector stamps the day it READ the board. A bare date there
        says an outlet published something on a day nobody published."""
        row = [l for l in self.text.splitlines() if "Databricks" in l][0]
        self.assertIn("board read August 28, 2026", row)

    def test_a_reported_row_keeps_a_bare_publication_date(self):
        row = [l for l in self.text.splitlines() if "Sanad" in l][0]
        self.assertIn("August 27, 2026", row)
        self.assertNotIn("board read", row)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheCaptionDescribesTheRowsItSitsOver(unittest.TestCase):
    """The provenance sentence is the serious one: it is the paragraph that
    tells a journalist how to cite the list, and it was false for a whole
    class of row."""

    def test_an_all_board_list_never_claims_the_headlines_were_published(self):
        text = edition([dict(SCAN)])
        self.assertNotIn(BLANKET, text)
        self.assertIn("not a headline anyone published", text)

    def test_an_all_board_list_names_postings_in_its_ordering_claim(self):
        text = edition([dict(SCAN)])
        self.assertIn("the signals listing the most postings first", text)
        self.assertNotIn("naming the most jobs first", text)

    def test_a_mixed_list_says_both_and_claims_neither_of_the_other(self):
        text = edition([dict(SCAN), dict(REPORTED)])
        self.assertNotIn(BLANKET, text)
        self.assertIn("A news headline is quoted as its source published it",
                      text)
        self.assertIn("A job-board line is our own description", text)
        self.assertIn("the signals naming the most jobs or postings first",
                      text)

    def test_an_all_reported_list_keeps_the_old_sentence_byte_for_byte(self):
        """THE OVER-CORRECTION GUARD. The old caption was true for a list of
        news rows. Rewriting it for every list would swap one piece of fixed
        prose around variable data for another."""
        text = edition([dict(REPORTED)])
        self.assertIn("the signals naming the most jobs first, then newest "
                      "first. " + BLANKET, text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheRemainderIsNotAllOneBin(unittest.TestCase):
    """"0 of the 30 are verified ... the rest are published indications we
    have not confirmed", over an edition in which a third of the rows were the
    employers' own careers boards."""

    @classmethod
    def setUpClass(cls):
        cls.text = edition([dict(SCAN), dict(REPORTED)])

    def test_the_old_sentence_is_gone(self):
        self.assertNotIn("The rest are published indications we have not "
                         "confirmed", self.text)

    def test_a_first_party_board_is_named_as_first_party(self):
        self.assertIn("readings of employers' own job boards", self.text)
        self.assertIn("A board reading is first-party", self.text)

    def test_the_verified_count_is_not_widened_to_rescue_the_word(self):
        """A board reading stays OUT of the verified figure: promoting it
        would overstate our own measurement as a figure the employer filed.
        The fixture's verified count is unchanged."""
        self.assertIn("568 of the 1,332 are verified against a primary "
                      "document", self.text)

    def test_verified_still_means_a_filed_document(self):
        self.assertIn("which here means a filed one", self.text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheHeadlineCountStatesItsOwnMix(unittest.TestCase):
    """The edition is headed "N hiring signals" and counts every signal in the
    window. Measured on the committed database: 9 of 27 rows state a hiring
    direction on the daily window of 2026-08-27/28, and 215 of 1,075 over the
    week to 2026-08-23. The rest are funding, leadership and site news."""

    def test_the_measured_hiring_share_is_printed(self):
        text = edition([dict(REPORTED)],
                       talent_cat_direction_hiring={"total": 9})
        self.assertIn("9 of the 1,332 signals listed on August 27 and 28, "
                      "2026 state a direction of hiring", text)

    def test_it_carries_its_own_window(self):
        """Lifted out on its own the line is still true and still says what it
        covers. tests/test_digest_scope_rules.py holds this for every figure
        line; this names it for the one added here."""
        text = edition([dict(REPORTED)],
                       talent_cat_direction_hiring={"total": 9})
        line = [l for l in text.splitlines()
                if "a direction of hiring" in l][0]
        self.assertIn("2026", line)

    def test_an_endpoint_that_cannot_answer_prints_no_line(self):
        """UNKNOWN is not zero and is not a pass. The harness answers a
        category filter it was given no fixture for with an ERROR, which is
        what a talent plugin that cannot serve the filter really does."""
        text = edition([dict(REPORTED)])
        self.assertNotIn("a direction of hiring", text)

    def test_a_total_equal_to_the_headline_is_a_dropped_filter_and_is_suppressed(self):
        """/talent/v1/aggregate answers an unrecognised filter with the
        UNFILTERED total, so equality with the headline is the signature of a
        filter that was ignored. Publishing it would put the worldwide total
        under a category label, as a measurement."""
        text = edition([dict(REPORTED)],
                       talent_cat_direction_hiring={"total": 1332})
        self.assertNotIn("a direction of hiring", text)

    def test_the_headline_unit_is_not_redefined_to_cover_the_mix(self):
        """The answer to a mislabelled count is a measurement, not a gloss
        wide enough to make a funding round a hiring signal."""
        text = edition([dict(REPORTED)],
                       talent_cat_direction_hiring={"total": 9})
        self.assertIn("1,332 new hiring signals", text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheDateBasisAdmitsTheReadingsItCounts(unittest.TestCase):
    """"counted by the date the source published" over a table a third of
    whose rows nobody published."""

    @classmethod
    def setUpClass(cls):
        cls.text = edition([dict(SCAN), dict(REPORTED)])

    def test_the_window_figure_names_both_bases(self):
        self.assertIn("counted by the date the source published, or for a "
                      "job-board reading the date we read the board",
                      self.text)

    def test_the_year_to_date_figure_names_the_same_two(self):
        """ONE DEFINITION. The two figures each carried their own copy of the
        old clause, so a fix applied to one would have left the other saying
        something else about the same table."""
        ytd = self.text.split("2026 YTD", 1)[1]
        self.assertIn("or for a job-board reading the date we read the board",
                      ytd)


if __name__ == "__main__":
    unittest.main()
