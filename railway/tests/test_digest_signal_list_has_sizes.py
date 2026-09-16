"""A list headed "biggest" may only hold rows that have a size.

WRITTEN FROM THE DELIVERED EDITION OF 2026-09-14. Under "Biggest hiring
signals" the reader met, in slots four and five, "Creative Investments Holding
secures $20 million first close" and "PayTabs strikes $100 million+ deal".
Neither names a job. Neither was ranked by anything. They were there because
`alt_digest_talent_rank()` sorted the job-carrying rows to the front and then
took the list's full width regardless, PADDING the leftover slots from the
endpoint's own order. The list always showed five rows because it was always
allowed five.

WHY THE HEADING WAS NOT THE PLACE TO FIX IT. The three-branch heading derives
from a scan-versus-reported count, which answers WHICH KIND of figure a listed
row carries. It cannot see a row that carries none, so no branch of it was ever
going to be true over a padded list.

THE OVER-CORRECTION IS GUARDED TOO, and it is the more expensive mistake: this
section is where the digest earns its subject line, so a selection that emptied
it on an ordinary week would be worse than the padding. A row that names roles
is never dropped, a job-board reading counts as a size, and a thin week ships a
short list rather than no list.

Composer cases SKIP without php on PATH, which is UNKNOWN and not a pass.
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from test_digest_scope_rules import PHP, compose, talent_fixture  # noqa: E402
from test_digest_accuracy_audit import (BOARD, HIRING, RESCUE,  # noqa: E402
                                        talent_rows)
import digest_layout as layout  # noqa: E402

#: Every unit this list is allowed to rank by, as the composer prints them.
SIZE = re.compile(r"\((?:[\d,]+ (?:jobs?|more postings? listed))")

FUNDING = {
    "company": "Creative Investments Holding",
    "headline": "Creative Investments Holding secures $20 million first close",
    "published_date": "2026-09-13", "headcount": None,
    "headcount_scope": None, "signal_direction": "funding",
    "collector": "national_press", "source_name": "Wamda",
    "source_url": "https://www.wamda.com/x", "country": "AE",
}
DEAL = {
    "company": "PayTabs",
    "headline": "PayTabs strikes $100 million+ deal",
    "published_date": "2026-09-13", "headcount": None,
    "headcount_scope": None, "signal_direction": "funding",
    "collector": "national_press", "source_name": "Wamda",
    "source_url": "https://www.wamda.com/x2", "country": "SA",
}


def listed(text):
    return [ln for ln in text.splitlines() if ln.strip().startswith("- ")]


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheDeliveredInstance(unittest.TestCase):

    def test_the_two_funding_rows_do_not_reach_the_list(self):
        text = talent_rows([FUNDING, DEAL, HIRING])["text"]
        self.assertIn("Grupo Purdy", text)
        self.assertNotIn("Creative Investments", text)
        self.assertNotIn("PayTabs", text)

    def test_a_thin_week_ships_a_short_list_not_a_padded_one(self):
        rows = listed(talent_rows([FUNDING, DEAL, HIRING])["text"])
        self.assertEqual(len(rows), 1, rows)

    def test_every_listed_row_prints_the_figure_that_ranked_it(self):
        text = talent_rows([FUNDING, DEAL, HIRING, BOARD])["text"]
        for ln in listed(text):
            self.assertRegex(ln, SIZE, f"a row with no size was listed: {ln}")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class WhatTheSelectionMustNotDo(unittest.TestCase):
    """The expensive direction. Emptying this section is worse than padding."""

    def test_a_job_board_reading_counts_as_a_size(self):
        text = talent_rows([BOARD])["text"]
        self.assertIn("23 more postings listed", text)

    def test_the_default_fixture_still_ships_a_list(self):
        self.assertTrue(listed(compose(talent_fixture())["text"]))

    def test_no_rankable_row_is_dropped_when_others_are(self):
        text = talent_rows([FUNDING, HIRING, BOARD])["text"]
        self.assertIn("Grupo Purdy", text)
        self.assertIn("Mirum Pharmaceuticals", text)

    def test_a_week_with_no_rankable_row_omits_the_block_rather_than_lying(self):
        """It does not ship an empty heading, and it does not ship the rows.

        Those signals are still counted in the headline and still named in
        "Other talent activity", so nothing is hidden by leaving them out of a
        list about size.
        """
        text = talent_rows([FUNDING, DEAL, RESCUE])["text"]
        self.assertEqual(listed(text), [])
        for heading in ("Biggest hiring signals",
                        "Largest observed job-board increases",
                        "Biggest signals and job-board increases"):
            self.assertNotIn(heading, text)


class TheCitationDoesNotOverflowAPhone(unittest.TestCase):
    """The citation URL is plain text on purpose, so it must be breakable.

    It is printed unlinked because a citation is meant to be pasted. The
    tracker's own URL is a 61-character token with no space and no hyphen in
    it, at 13px inside a content box about 240px wide on a 320px viewport. An
    unbreakable token that does not fit is not wrapped by a mail client: it is
    clipped, or it widens the card and takes the section sideways with it.
    """

    def test_the_note_variant_may_break_a_long_token(self):
        style = layout.VARIANT_STYLES[("p", "note")]
        self.assertIn("overflow-wrap:break-word", style)

    def test_the_declaration_survives_restyle(self):
        """The table above is not what reaches the reader; restyle() is."""
        html = layout.restyle(
            '<p data-alt="note">Talent Intelligence Tracker, '
            'AskTheRecruiter.com. '
            'https://asktherecruiter.com/blog/talent-intelligence-tracker/</p>')
        self.assertIn("overflow-wrap:break-word", html)

    def test_it_does_not_reach_for_break_all(self):
        """`break-all` would chop ordinary prose mid-word, and this variant
        carries whole paragraphs of small print as well as the citation."""
        self.assertNotIn("break-all", layout.VARIANT_STYLES[("p", "note")])


if __name__ == "__main__":
    unittest.main()
