"""Mazowieckie register: the parse, pinned to three real posts.

WHAT THIS EXISTS FOR. On 2026-08-18 the collector was reading THREE of the
eleven notices its own listing page was serving. Nothing was down, nothing was
degraded, and the health line said "ok". Three separate defects, none of which a
zero-check could see, because the run was never zero:

  * the February post writes the legal form lowercase ("sp. z o.o."), the anchor
    required a capital S, so that post yielded ZERO anchors -- four employers and
    164 jobs simply absent;
  * the June post dates every one of its four notices as an explicit day ("do 31
    lipca 2026 r.") or a month range ("na czerwiec-lipiec 2026 r."), and the
    deadline pattern read only "do końca <month> <year>", so all four were
    skipped;
  * the June post's largest notice, "Firma Budowlana ANNA-BUD" at 76 people, has
    no legal-form suffix at all, so it produced no anchor -- missing from the
    rows AND from the skipped count that was supposed to reveal it.

THE AUDIT THAT MAKES THIS CHECKABLE. Each post states its own total for the
notices it lists, and our rows must sum to it. That is the assertion below, and
it is the one that turns "we parsed some" into "we parsed all of them".

The fixtures are the real flattened posts, saved 2026-08-18. Do not regenerate
them to make a failing assertion pass: a changed post is a parser change, and
the count in the post is the thing that says which side is wrong.

unittest, not pytest: the railway suite runs under `unittest discover`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import wup_mazowieckie as wup

FIXTURES = Path(__file__).resolve().parent / "fixtures"
POST_URL = "https://wupwarszawa.praca.gov.pl/urzad/dla-mediow/test-post"

# Hand-read off each post. company -> (jobs, completion date).
GROUND_TRUTH = {
    "luty": {
        "Curiosity Diagnostics sp. z o.o.": (60, "2026-03-31"),
        "Okaidi Poland sp. z o.o.": (57, "2026-06-30"),
        "Oriflame Poland sp. z o.o.": (31, "2026-03-31"),
        "Coca-Cola Poland Services sp. z o.o.": (16, "2026-06-30"),
    },
    "marzec": {
        "British American Tobacco Trading Sp. z o.o.": (48, "2026-04-30"),
        "Amerplast Sp. z o.o.": (29, "2026-07-31"),
        "Bank Nowy S.A.": (3, "2026-09-30"),
    },
    "czerwiec": {
        "Firma Budowlana ANNA-BUD": (76, "2026-07-31"),
        "Fenige S.A.": (39, "2026-07-31"),
        "Scandstick Poland Sp. z o.o.": (22, "2026-07-31"),
        "Bank Nowy S.A.": (3, "2026-09-30"),
    },
}


def _load(month):
    return (FIXTURES / f"wup_mazowieckie_2026_{month}.txt").read_text(encoding="utf-8")


class EveryNotifiedEmployerIsRead(unittest.TestCase):
    def _parsed(self, month):
        entries, skipped = wup._parse_post(_load(month), POST_URL)
        return {e["company_name"]: (e["job_count"], e["layoff_date"])
                for e in entries}, skipped

    def test_february_lowercase_legal_form_is_read(self):
        """The month that returned zero anchors because of one capital letter."""
        got, skipped = self._parsed("luty")
        self.assertEqual(got, GROUND_TRUTH["luty"])
        self.assertEqual(skipped, 0)

    def test_march_still_reads_the_post_that_always_worked(self):
        got, skipped = self._parsed("marzec")
        self.assertEqual(got, GROUND_TRUTH["marzec"])
        self.assertEqual(skipped, 0)

    def test_june_dated_and_ranged_deadlines_are_read(self):
        """All four were skipped: none of them phrases its date as 'do końca'."""
        got, skipped = self._parsed("czerwiec")
        self.assertEqual(got, GROUND_TRUTH["czerwiec"])
        self.assertEqual(skipped, 0)

    def test_the_employer_with_no_legal_form_is_not_invisible(self):
        """The largest notice in the June post, and the anchor could not see it."""
        got, _ = self._parsed("czerwiec")
        self.assertIn("Firma Budowlana ANNA-BUD", got)
        self.assertEqual(got["Firma Budowlana ANNA-BUD"][0], 76)


class TheRowsSumToWhatThePostDeclares(unittest.TestCase):
    """The completeness audit. A thin parse can no longer read as a healthy one."""

    def test_each_post_matches_its_own_stated_total(self):
        for month, expected in (("luty", 164), ("marzec", 80), ("czerwiec", 140)):
            with self.subTest(month=month):
                text = _load(month)
                declared = wup._declared_total(text)
                self.assertEqual(declared, expected,
                                 f"{month}: the post states its own total")
                entries, _ = wup._parse_post(text, POST_URL)
                self.assertEqual(sum(e["job_count"] for e in entries), declared)

    def test_the_declared_total_is_not_the_completed_dismissals_figure(self):
        """Each post carries TWO numbers and only one of them is ours.

        June says 280 people lost work that month (completions of earlier
        notices) and 140 in newly notified intentions. Auditing our rows against
        280 would call a correct parse broken.
        """
        self.assertEqual(wup._declared_total(_load("czerwiec")), 140)
        self.assertIn("straciło 280 osób", _load("czerwiec"))


class ProseIsNeverPostedAsAnEmployer(unittest.TestCase):
    """The general anchor's risk, and the guard that bounds it.

    The prose test applies to the GENERAL anchor only. A legal-form name
    legitimately contains the tokens "z" and "o" (they are inside "sp. z o.o."),
    so running the same check over those would reject every real company in the
    register -- which is why the guard sits where it does and not one layer up.
    """

    def test_the_sentence_fragment_in_front_of_a_real_count_is_skipped(self):
        """'Zwolnienia będą realizowane etapowo – do końca kwietnia...' is not a company."""
        for name in self._parsed_names("marzec"):
            self.assertNotIn("realizowane", name.lower())
            self.assertNotIn("zwolnienia", name.lower())

    def test_the_general_anchor_yields_no_prose_on_any_real_post(self):
        for month in GROUND_TRUTH:
            with self.subTest(month=month):
                general = [name for _s, _e, name, kind
                           in wup._anchors(_load(month)) if kind == "general"]
                for name in general:
                    self.assertFalse(
                        wup._looks_like_prose(name),
                        f"{month}: {name!r} reads as prose, not an employer")
                    self.assertIn(name, GROUND_TRUTH[month],
                                  f"{month}: the general anchor invented {name!r}")

    def test_the_prose_guard_rejects_the_fragment_it_was_written_for(self):
        self.assertTrue(wup._looks_like_prose("Zwolnienia będą realizowane etapowo"))
        self.assertFalse(wup._looks_like_prose("Firma Budowlana ANNA-BUD"))

    def _parsed_names(self, month):
        entries, _ = wup._parse_post(_load(month), POST_URL)
        return [e["company_name"] for e in entries]


class DeadlineFormsAreReadAndNeverGuessed(unittest.TestCase):
    def test_the_three_documented_forms(self):
        cases = (
            ("zwolnienia objąć mają 60 osób i przeprowadzone zostaną do końca "
             "marca 2026 r.", "2026-03-31"),
            ("planowany termin do 31 lipca 2026 r.", "2026-07-31"),
            ("proces zaplanowano na czerwiec–lipiec 2026 r.", "2026-07-31"),
        )
        for body, expected in cases:
            with self.subTest(body=body[:40]):
                self.assertEqual(wup._deadline(body), expected)

    def test_a_filing_date_is_not_read_as_a_deadline(self):
        """The June Bank Nowy item names both; only the completion date is ours."""
        body = ("zgłoszenie z 5 marca 2026 r. obejmuje zwolnienie 3 osób, "
                "proces rozłożony do 30 września 2026 r.")
        self.assertEqual(wup._deadline(body), "2026-09-30")

    def test_an_unrecognised_phrasing_returns_none_rather_than_a_guess(self):
        self.assertIsNone(wup._deadline("zwolnienia potrwają jakiś czas"))
        self.assertIsNone(wup._deadline("do końca przyszłego roku"))

    def test_february_is_dated_by_the_calendar_not_a_fixed_table(self):
        """A leap February has 29 days, and the old fixed table said 28."""
        self.assertEqual(wup._deadline("do końca lutego 2028 r."), "2028-02-29")


if __name__ == "__main__":
    unittest.main()
