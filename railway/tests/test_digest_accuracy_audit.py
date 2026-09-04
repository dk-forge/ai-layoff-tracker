"""The 2026-09-04 accuracy audit of the two delivered daily editions.

Every number in the talent edition of 2026-09-04 (108 signals, 107 companies,
0 verified, 20 hiring, 38 leadership, 27 funding, 12 pay) and of 2026-09-03
(111, 110, 8, 8, 52, 28, 18) reproduced exactly from the live /talent/v1 rows
filtered on each row's own captured_at stamp. The FIGURES were right. Five
sentences around them were not, and each is pinned here against the composer
(tests/fixtures/digest_compose_harness.php, as test_digest_scope_rules does):

  1. "Biggest hiring signals ... (30 jobs ...)" over a row the tracker stores
     as signal_direction 'neutral' / headcount_scope 'affected': thirty jobs
     SAVED in a rescue, ranked and printed as thirty roles named.
  2. "108 new ... signals" over a window (yesterday and today, deliberate)
     that puts every signal dated yesterday into two consecutive editions.
  3. "counted by the date the source published, or for a job-board reading
     the date we read the board", when the window is COALESCE(published_date,
     DATE(captured_at)) and 4 of the 108 rows were undated news reports; and
     the undated note that said "We do not substitute the day we captured it"
     while the window had done exactly that.
  4. No statement that the window is provisional, when the previous edition's
     111 read 207 one day later.
  5. "Source: Indeed Hiring Lab Job Postings Tracker ... AI share as of July
     31": the AI share is Hiring Lab's AI Tracker, a different dataset, and the
     baseline / month-earlier comparisons are our arithmetic, which CC BY 4.0
     asks us to say.

And the em-dash rule, which held (0 in 315 rows) but was unguarded: a quoted
headline carrying one now reaches neither the composed part nor the relayed
message (railway/digest_layout.plain_dashes).

Without php on PATH the composer cases SKIP, which is UNKNOWN and not a pass.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from test_digest_scope_rules import PHP, compose, talent_fixture  # noqa: E402
import digest_layout as layout  # noqa: E402


def talent_rows(rows, **over):
    fixture = talent_fixture()
    fixture["talent"]["rows"] = rows
    fixture.update(over)
    return compose(fixture)


HIRING = {
    "company": "Grupo Purdy", "headline": "Grupo Purdy ofrecera 20 puestos",
    "published_date": "2026-08-14", "headcount": 20,
    "headcount_scope": "new_roles", "signal_direction": "hiring",
    "collector": "national_press", "source_name": "El Financiero CR",
    "source_url": "https://www.elfinancierocr.com/x", "country": "CR",
}
RESCUE = {
    "company": "Beacon Park Boats",
    "headline": "Jobs and holidays saved after business rescued from administration",
    "published_date": "2026-08-15", "headcount": 30,
    "headcount_scope": "affected", "signal_direction": "neutral",
    "collector": "national_press", "source_name": "BusinessLive",
    "source_url": "https://www.business-live.co.uk/x", "country": "GB",
}
DISPLACEMENT = {
    "company": "Nordwerk", "headline": "Nordwerk to shed 500 posts",
    "published_date": "2026-08-15", "headcount": 500,
    "headcount_scope": "affected", "signal_direction": "displacement",
    "collector": "national_press", "source_name": "Handelsblatt",
    "source_url": "https://www.handelsblatt.com/x", "country": "DE",
}
BOARD = {
    "company": "Mirum Pharmaceuticals",
    "headline": "Mirum Pharmaceuticals's job board listed 23 more active "
                "postings than our previous scan",
    "published_date": "2026-08-16", "headcount": 23,
    "headcount_scope": "new_roles", "signal_direction": "hiring",
    "collector": "ats_boards", "source_name": "Greenhouse job board",
    "source_url": "https://job-boards.greenhouse.io/mirum", "country": None,
}


@unittest.skipIf(PHP is None, "php is not on PATH, so the composer could not "
                              "be run. UNKNOWN, not a pass.")
class AHeadcountIsJobsOnlyWhenTheRowSaysItNamesRoles(unittest.TestCase):

    def test_a_rescue_is_not_printed_as_jobs(self):
        text = talent_rows([RESCUE, HIRING])["text"]
        self.assertIn("20 jobs", text)
        self.assertNotIn("30 jobs", text)

    def test_a_rescue_does_not_outrank_a_hiring_row(self):
        text = talent_rows([RESCUE, HIRING])["text"]
        self.assertLess(text.index("Grupo Purdy"), text.index("Beacon Park Boats"))

    def test_a_displacement_is_not_printed_as_jobs(self):
        text = talent_rows([DISPLACEMENT, HIRING])["text"]
        self.assertNotIn("500 jobs", text)
        self.assertIn("20 jobs", text)

    def test_a_board_reading_still_names_its_postings(self):
        text = talent_rows([BOARD, HIRING])["text"]
        self.assertIn("23 more postings listed", text)

    def test_a_row_with_neither_field_keeps_todays_behaviour(self):
        # The default fixture rows carry no scope and no direction. They are
        # the legacy shape, and an over-correction that dropped their figure
        # would fail here rather than half-ship.
        text = compose(talent_fixture())["text"]
        self.assertIn("2,200 jobs", text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheWindowIsDescribedAsWhatItIs(unittest.TestCase):

    def test_the_count_is_not_called_new(self):
        out = compose(talent_fixture())
        for part in (out["text"], out["html"]):
            self.assertNotIn(" new talent and employer-activity signal", part)
            self.assertNotIn("new hiring signal", part)
            self.assertNotIn(">new talent", part)

    def test_the_basis_names_the_capture_date_fallback(self):
        text = compose(talent_fixture())["text"]
        self.assertIn("or, for a job-board reading or a source that carries "
                      "no date, the day we captured it", text)

    def test_the_undated_note_does_not_deny_the_substitution(self):
        # The default fixture's Northwind row has no date and reaches the list.
        text = compose(talent_fixture())["text"]
        self.assertIn("shows no date", text)
        self.assertNotIn("We do not substitute", text)
        self.assertIn("the window placed it by the day we captured it", text)

    def test_every_edition_says_the_window_is_provisional(self):
        text = compose(talent_fixture())["text"]
        self.assertIn("Figures for this window are provisional", text)

    def test_only_the_daily_pair_states_the_overlap(self):
        weekly = compose(talent_fixture())["text"]
        self.assertNotIn("also in yesterday's edition", weekly)
        daily = compose(talent_fixture(**{"from": "2026-08-15",
                                          "to": "2026-08-16"}))["text"]
        self.assertIn("A daily edition covers yesterday and today, so a signal "
                      "dated yesterday was also in yesterday's edition.", daily)


def indeed(**over):
    data = {
        "source": "Indeed Hiring Lab",
        "national": {"index": 101.91, "as_of": "2026-08-21", "vs_baseline": 1.91,
                     "baseline": "February 1, 2020 = 100",
                     "seasonally_adjusted": True,
                     "source_name": "Indeed Hiring Lab Job Postings Tracker",
                     "month_ago": {"date": "2026-07-22", "delta": 0.0}},
        "ai": {"share_pct": 6.28, "as_of": "2026-07-31",
               "source_name": "Indeed Hiring Lab AI Tracker",
               "month_ago": {"date": "2026-07-01", "delta": 0.33}},
    }
    data.update(over)
    return data


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheIndeedBackdropIsAttributedToTheWorksItUses(unittest.TestCase):

    def test_each_series_is_credited_to_its_own_dataset(self):
        text = compose(talent_fixture(indeed=indeed()))["text"]
        self.assertIn("Sources: Indeed Hiring Lab Job Postings Tracker for the "
                      "index and Indeed Hiring Lab AI Tracker for the AI share, "
                      "both published by Indeed Hiring Lab under CC BY 4.0.", text)
        self.assertIn("Index as of August 21, 2026. AI share as of July 31, 2026.", text)

    def test_the_level_says_it_is_seasonally_adjusted(self):
        text = compose(talent_fixture(indeed=indeed()))["text"]
        self.assertIn("(February 1, 2020 = 100, seasonally adjusted) stood at 101.91", text)

    def test_the_comparisons_are_declared_as_our_arithmetic(self):
        text = compose(talent_fixture(indeed=indeed()))["text"]
        self.assertIn("are our own arithmetic on the published series", text)

    def test_no_comparison_means_no_arithmetic_claim(self):
        bare = indeed()
        bare["national"] = {"index": 101.91, "as_of": "2026-08-21",
                            "source_name": "Indeed Hiring Lab Job Postings Tracker"}
        bare["ai"] = {"share_pct": 6.28, "as_of": "2026-07-31",
                      "source_name": "Indeed Hiring Lab AI Tracker"}
        text = compose(talent_fixture(indeed=bare))["text"]
        self.assertNotIn("our own arithmetic", text)

    def test_an_older_seed_without_an_ai_name_keeps_the_single_source_line(self):
        older = indeed()
        older["ai"] = {"share_pct": 6.28, "as_of": "2026-07-31",
                       "month_ago": {"date": "2026-07-01", "delta": 0.33}}
        text = compose(talent_fixture(indeed=older))["text"]
        self.assertIn("Source: Indeed Hiring Lab Job Postings Tracker (CC BY 4.0).", text)
        self.assertNotIn("AI Tracker", text)


EM = "—"


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class NoEmDashReachesAComposedPart(unittest.TestCase):

    def test_a_quoted_headline_and_outlet_lose_their_em_dashes(self):
        row = dict(HIRING, headline=f"Acme {EM} hiring 40 in Leeds",
                   source_name=f"The Post {EM} Business")
        out = talent_rows([row])
        for part in (out["text"], out["html"]):
            self.assertNotIn(EM, part)
            self.assertIn("Acme - hiring 40 in Leeds", part)
            self.assertIn("The Post - Business", part)


class NoEmDashReachesTheRelayedMessage(unittest.TestCase):

    PART = ("talent", f"<h2>Talent</h2><p>Acme {EM} hiring 40</p>",
            f"Talent\nAcme {EM} hiring 40\n", "", "")

    def test_plain_dashes_spaces_a_hyphen_in(self):
        self.assertEqual(layout.plain_dashes(f"a{EM}b"), "a - b")
        self.assertEqual(layout.plain_dashes(f"a {EM} b"), "a - b")
        self.assertEqual(layout.plain_dashes("a - b"), "a - b")
        self.assertEqual(layout.plain_dashes(None), "")

    def test_the_html_message_carries_none(self):
        html = layout.render_html([self.PART], subject=f"S {EM} T",
                                  preheader=f"P {EM} Q", kicker=f"K {EM} L",
                                  unsub_url="https://x/u", manage_url="https://x/m")
        self.assertNotIn(EM, html)
        self.assertIn("Acme - hiring 40", html)

    def test_the_text_message_carries_none(self):
        text = layout.render_text([self.PART], kicker=f"K {EM} L",
                                  unsub_url="https://x/u", manage_url="https://x/m")
        self.assertNotIn(EM, text)
        self.assertIn("Acme - hiring 40", text)


if __name__ == "__main__":
    unittest.main()
