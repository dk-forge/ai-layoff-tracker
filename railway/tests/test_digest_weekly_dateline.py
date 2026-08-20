"""A weekly edition that explains its own window when it arrives late.

WHAT HAPPENED. A weekly headed "Weekly edition, 2026 Week 33 · August 10-16"
arrived on Thursday 20 August. Every figure in it was right, and so was the
window: week 33 is the most recent COMPLETE ISO week, and week 34 had not
closed. The owner still had to stop and work out why he was reading about the
week before last.

THE NUMBER WAS NEVER WRONG. THE FRAMING WAS. This is a product a journalist may
cite, and an edition that looks stale on arrival is trusted less than one that
says what it covers, even when both carry identical figures.

TWO CHANGES, AND THE SECOND ONE IS CONDITIONAL ON PURPOSE.

The dateline now leads with when the window ENDED, so a skimming reader gets
"how current is this" in the first three words instead of decoding a week
number. The ISO week keeps its place, second, because that is what a citation
needs.

And a staleness line appears ONLY when the send is genuinely late. A caveat
that prints every week is furniture: readers stop seeing it, and it stops
working on the one week it was written for. This repository has learned that
lesson twice already in this same file, in the country block and in the
undated-signals note.

WHAT MUST NOT CHANGE, AND IS ASSERTED HERE BECAUSE IT IS EASY TO BREAK BY
ACCIDENT: the subject line. "1,387 hiring signals · Aug 10-16" was settled with
the owner after several rounds. `period_phrase` feeds the subject's fallback,
so a fix applied there rather than to the body would have rewritten the subject
silently.
"""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import digest_layout as layout
import digest_send

WEEK_33 = {"freq": "weekly", "from": "2026-08-10", "to": "2026-08-16"}
DAILY = {"freq": "daily", "from": "2026-08-19", "to": "2026-08-20"}


class TheDatelineLeadsWithWhenTheWindowEnded(unittest.TestCase):

    def test_it_says_week_ending_before_anything_else(self):
        self.assertTrue(
            layout.body_dateline(WEEK_33).startswith("week ending Sunday, August 16"),
            layout.body_dateline(WEEK_33))

    def test_the_iso_week_is_kept_for_citation(self):
        self.assertIn("2026 Week 33", layout.body_dateline(WEEK_33))

    def test_the_kicker_a_reader_actually_sees(self):
        self.assertEqual(
            digest_send._kicker(WEEK_33),
            "Weekly edition, week ending Sunday, August 16 · 2026 Week 33")

    def test_the_iso_year_is_used_and_not_the_calendar_year(self):
        """28 December 2026 to 3 January 2027 is 2026 Week 53. Reading the
        calendar year beside an ISO week ships silently and is found in
        January."""
        payload = {"freq": "weekly", "from": "2026-12-28", "to": "2027-01-03"}
        self.assertEqual(
            layout.body_dateline(payload),
            "week ending Sunday, January 3 · 2026 Week 53")

    def test_the_weekday_is_read_and_never_assumed(self):
        """A forced window does not have to end on a Sunday, and printing
        "Sunday" over a Friday would be a wrong fact in the one line whose job
        is to be checkable."""
        payload = {"freq": "weekly", "from": "2026-08-08", "to": "2026-08-14"}
        self.assertIn("week ending Friday, August 14", layout.body_dateline(payload))

    def test_a_daily_edition_is_untouched(self):
        self.assertEqual(layout.body_dateline(DAILY), "")
        self.assertEqual(digest_send._kicker(DAILY), "Daily edition, August 20, 2026")

    def test_an_unreadable_window_falls_back_and_guesses_nothing(self):
        self.assertEqual(layout.body_dateline({"freq": "weekly", "to": "nonsense"}), "")


class TheSubjectIsNotReopened(unittest.TestCase):
    """`period_phrase` feeds the subject fallback. It keeps the approved shape."""

    def test_period_phrase_still_returns_the_edition_label(self):
        start = datetime.date(2026, 8, 10)
        end = datetime.date(2026, 8, 16)
        self.assertEqual(layout.period_phrase(WEEK_33),
                         layout.edition_label(start, end))

    def test_the_subject_period_token_is_unchanged(self):
        self.assertEqual(layout.subject_period(WEEK_33), "Aug 10-16")


class TheStalenessLineAppearsOnlyWhenTheSendIsLate(unittest.TestCase):
    """The threshold comes from the schedule, not from a guess.

    The weekly fires Monday 07:30 Eastern over the week that closed the
    previous day, so the ordinary gap is ONE day. Two days is a send that
    slipped to Tuesday and is still obviously current. Three is the first gap
    that cannot happen on the normal schedule at all.
    """

    def test_it_is_silent_on_the_normal_monday_send(self):
        self.assertEqual(
            layout.staleness_note(WEEK_33, datetime.date(2026, 8, 17)), "")

    def test_it_is_still_silent_a_day_late(self):
        self.assertEqual(
            layout.staleness_note(WEEK_33, datetime.date(2026, 8, 18)), "")

    def test_it_speaks_once_the_gap_cannot_be_the_schedule(self):
        self.assertEqual(
            layout.staleness_note(WEEK_33, datetime.date(2026, 8, 19)),
            "This covers the last complete week. Week 34, August 17-23, "
            "closes Sunday.")

    def test_the_thursday_send_the_owner_actually_received(self):
        note = layout.staleness_note(WEEK_33, datetime.date(2026, 8, 20))
        self.assertIn("Week 34", note)
        self.assertIn("closes Sunday", note)

    def test_it_names_the_week_the_reader_is_living_in(self):
        """Not the week being reported. The reader's question is "why am I not
        reading about this week", and the answer is when this week closes."""
        note = layout.staleness_note(WEEK_33, datetime.date(2026, 8, 20))
        self.assertNotIn("Week 33", note)
        self.assertNotIn("August 10-16", note)

    def test_a_daily_edition_never_gets_one(self):
        self.assertEqual(
            layout.staleness_note(DAILY, datetime.date(2026, 9, 30)), "")

    def test_an_unreadable_window_produces_no_line(self):
        self.assertEqual(
            layout.staleness_note({"freq": "weekly", "to": ""},
                                  datetime.date(2026, 8, 20)), "")

    def test_it_crosses_a_year_boundary_on_the_iso_numbering(self):
        payload = {"freq": "weekly", "from": "2026-12-28", "to": "2027-01-03"}
        note = layout.staleness_note(payload, datetime.date(2027, 1, 7))
        self.assertEqual(note, "This covers the last complete week. Week 1, "
                               "January 4-10, closes Sunday.")


class TheCopyRulesThisFileIsHeldTo(unittest.TestCase):

    def _copy(self):
        return [layout.body_dateline(WEEK_33),
                digest_send._kicker(WEEK_33),
                layout.staleness_note(WEEK_33, datetime.date(2026, 8, 20))]

    def test_no_em_dash_reaches_a_reader(self):
        for line in self._copy():
            self.assertNotIn("—", line)
            self.assertNotIn("–", line)

    def test_every_sentence_stays_under_thirty_words(self):
        for line in self._copy():
            for sentence in line.split(". "):
                self.assertLess(len(sentence.split()), 30, sentence)


class TheLineIsRenderedNearTheTopOfBothParts(unittest.TestCase):
    """A note nobody threads into the message is a function with a test and no
    effect. This is the assertion that it reaches a reader."""

    NOTE = "This covers the last complete week."

    def _parts(self):
        return [("layoff", "<p>Body</p>", "Body")]

    def test_the_html_carries_it_under_the_masthead(self):
        html = layout.render_html(
            self._parts(), subject="s", preheader="p",
            kicker="Weekly edition, week ending Sunday, August 16",
            notice=self.NOTE, unsub_url="https://x.example/u",
            manage_url="https://x.example/m")
        self.assertIn(self.NOTE, html)
        self.assertLess(html.index(self.NOTE), html.index("Body"))

    def test_the_text_part_carries_the_same_sentence(self):
        text = layout.render_text(
            self._parts(),
            kicker="Weekly edition, week ending Sunday, August 16",
            notice=self.NOTE, unsub_url="https://x.example/u",
            manage_url="https://x.example/m")
        self.assertIn(self.NOTE, text)
        self.assertLess(text.index(self.NOTE), text.index("Body"))

    def test_an_empty_note_adds_no_empty_paragraph(self):
        html = layout.render_html(
            self._parts(), subject="s", preheader="p", kicker="Daily edition",
            notice="", unsub_url="https://x.example/u",
            manage_url="https://x.example/m")
        self.assertNotIn("margin:8px 0 0", html)


if __name__ == "__main__":
    unittest.main()
