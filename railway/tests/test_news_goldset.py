"""Guards for the corroborated NEWS answer key.

The SEC gold set can be checked by opening the filing: the count is in the
document the manifest links. This one cannot, because its answer is DERIVED —
two sources had to state the same number — so the derivation itself is the
thing that has to be trustworthy. Four ways it could quietly produce a key that
is really one source wearing two hats, each pinned here:

  one newsroom under two names       (geekwire.com / GeekWire)
  one paragraph under two names      (wire copy reprinted verbatim)
  an event-merge that never agreed   (+/-30 day fuzzy match, different count)
  a percentage read as a headcount

Plus the rule that keeps the harness honest about what it is reading: a row
whose model input cannot be rebuilt is excluded from the set, not scored
against a substitute window.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from news_goldset_build import (assemble, corroborating_outlets,
                                is_syndicated_copy, outlet_key,
                                outlets_are_independent, window_plan)

MANIFEST = (Path(__file__).resolve().parents[2] / "docs" / "recall-reference-sets"
            / "news-corroborated-2026-08.goldset.json")


def _row(**kw):
    row = {"id": 1, "event_id": 9, "company_name": "Acme", "job_count": 500,
           "country": "United States", "layoff_date": "2026-08-04",
           "announcement_date": "2026-08-04", "source_type": "news",
           "source_name": "geekwire.com", "source_url": "https://www.geekwire.com/a",
           "archived_url": "https://web.archive.org/web/20260805/https://www.geekwire.com/a",
           "excerpt": "Acme cuts 500 jobs in its largest layoff of the year."}
    row.update(kw)
    return row


def _report(name, url, excerpt, stype="news"):
    return {"source_name": name, "source_url": url, "excerpt": excerpt,
            "source_type": stype, "observed_at": "2026-08-04 22:17:10"}


class OutletIdentityTests(unittest.TestCase):
    def test_one_newsroom_under_two_spellings_is_one_outlet(self):
        self.assertEqual(outlet_key("geekwire.com", "https://www.geekwire.com/a"),
                         outlet_key("GeekWire", "https://news.google.com/rss/x?oc=5"))
        self.assertFalse(outlets_are_independent("geekwire", "geekwire"))

    def test_a_longer_name_for_the_same_outlet_is_not_a_second_source(self):
        self.assertFalse(outlets_are_independent("inman", "inmanrealestatenews"))

    def test_country_domains_of_one_broadcaster_are_one_outlet(self):
        self.assertEqual(outlet_key("", "https://www.bbc.co.uk/news/1"),
                         outlet_key("", "https://www.bbc.com/news/1"))

    def test_two_real_newsrooms_are_independent(self):
        self.assertTrue(outlets_are_independent("geekwire", "housingwire"))

    def test_an_empty_key_never_corroborates(self):
        self.assertFalse(outlets_are_independent("", "housingwire"))

    def test_a_wayback_url_identifies_the_publisher_not_the_archive(self):
        self.assertEqual(
            outlet_key("", "https://web.archive.org/web/20260805/https://www.geekwire.com/a"),
            "geekwire")


class SyndicationTests(unittest.TestCase):
    def test_the_same_paragraph_under_two_names_is_one_observation(self):
        a = ("British technology company Dyson is cutting 900 jobs globally due to "
             "the impact of the pandemic on consumer demand, it said on Thursday.")
        self.assertTrue(is_syndicated_copy(a, a.upper()))
        self.assertTrue(is_syndicated_copy(a, a + " More follows."))

    def test_two_differently_worded_reports_are_two_observations(self):
        self.assertFalse(is_syndicated_copy(
            "Acme cuts 500 jobs in its largest layoff of the year.",
            "Acme to lay off 500 staff in restructuring, sources say."))


class CorroborationTests(unittest.TestCase):
    def test_a_second_outlet_stating_a_different_count_does_not_corroborate(self):
        # The exact shape the +/-30 day fuzzy merge produces: one event, one
        # follow-up story, two different numbers. Observed live on Zillow 500.
        found = corroborating_outlets(_row(), [
            _report("geekwire.com", "https://www.geekwire.com/a",
                    "Acme cuts 500 jobs in its largest layoff of the year."),
            _report("GeekWire", "https://news.google.com/rss/x?oc=5",
                    "Acme layoffs hit 91 jobs in Washington state."),
        ])
        self.assertEqual([f["outlet"] for f in found], ["geekwire"])

    def test_a_percentage_is_not_a_headcount(self):
        found = corroborating_outlets(_row(job_count=18), [
            _report("housingwire.com", "https://www.housingwire.com/b",
                    "Acme is cutting 18% of its workforce."),
        ])
        self.assertEqual([f["outlet"] for f in found if f["kind"] == "cross_outlet"], [])

    def test_an_official_filing_corroborates_without_the_outlet_test(self):
        found = corroborating_outlets(_row(), [
            _report("CA WARN notice", "https://edd.ca.gov/warn.xlsx",
                    "Layoff Permanent at Acme. 500 employees affected.", stype="warn"),
        ])
        self.assertIn("official_record", [f["kind"] for f in found])

    def test_one_outlet_alone_is_not_an_answer_key(self):
        events, _ = assemble([_row()], {1: []})
        self.assertEqual(events, [])

    def test_two_independent_outlets_make_an_answer_key(self):
        events, excluded = assemble([_row()], {1: [
            _report("housingwire.com", "https://www.housingwire.com/b",
                    "Acme to lay off 500 staff in restructuring."),
        ]})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["stated_job_count"], 500)
        self.assertEqual(events[0]["corroboration_kinds"], ["cross_outlet", "primary"])
        self.assertEqual(excluded, [])


class WindowTests(unittest.TestCase):
    def test_a_google_news_row_is_excluded_because_its_window_is_gone(self):
        # The model read an RSS title and snippet. The feed is a rolling window
        # and the redirect does not carry the item text, so there is nothing to
        # rebuild — and substituting the full article would score the model on a
        # window production never used.
        source, url = window_plan(_row(
            source_url="https://news.google.com/rss/articles/CBMiabc?oc=5"))
        self.assertEqual(source, "unrecoverable_headline_window")
        self.assertIsNone(url)

    def test_a_publisher_url_with_no_snapshot_is_excluded_not_refetched(self):
        source, url = window_plan(_row(archived_url=""))
        self.assertEqual(source, "no_frozen_snapshot")
        self.assertIsNone(url)

    def test_excluded_rows_are_reported_and_not_silently_dropped(self):
        row = _row(source_url="https://news.google.com/rss/articles/CBMiabc?oc=5")
        events, excluded = assemble([row], {1: [
            _report("housingwire.com", "https://www.housingwire.com/b",
                    "Acme to lay off 500 staff in restructuring."),
        ]})
        self.assertEqual(events, [])
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["window_source"], "unrecoverable_headline_window")


class FrozenManifestTests(unittest.TestCase):
    """The committed set is what the harness actually scores, so its invariants
    are asserted on the file, not only on the builder that wrote it."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_it_is_labelled_as_a_model_comparison_and_not_a_recall_number(self):
        self.assertEqual(self.manifest["publication_status"],
                         "internal_model_comparison_reference_not_a_recall_measurement")
        self.assertIn("not a recall measurement",
                      self.manifest["what_it_can_and_cannot_support"])

    def test_every_event_carries_two_independent_outlets_and_a_frozen_window(self):
        self.assertGreaterEqual(len(self.manifest["reference_events"]), 20)
        for event in self.manifest["reference_events"]:
            outlets = [c["outlet"] for c in event["corroboration"]]
            self.assertGreaterEqual(len(outlets), 2, event["reference_row_id"])
            self.assertEqual(len(outlets), len(set(outlets)), event["reference_row_id"])
            self.assertEqual(event["window_source"], "wayback_article")
            self.assertTrue(event["frozen_window_url"].startswith(
                "https://web.archive.org/web/"), event["reference_row_id"])
            self.assertGreater(int(event["stated_job_count"]), 0)

    def test_no_event_carries_the_count_from_only_one_sentence(self):
        for event in self.manifest["reference_events"]:
            texts = {(c["count_evidence"] or "").strip() for c in event["corroboration"]}
            self.assertGreaterEqual(len(texts), 2, event["reference_row_id"])

    def test_the_country_field_is_recorded_but_declared_unscored(self):
        # The source-report table stores no country, so the second source
        # corroborates the company and the count only. Saying otherwise would
        # be a number nothing measured.
        self.assertIn("NOT SCORED", self.manifest["answer_key_rule"]["country"])

    def test_the_excluded_rows_keep_their_reason(self):
        for row in self.manifest["excluded_rows"]:
            self.assertIn(row["window_source"],
                          ("unrecoverable_headline_window", "no_frozen_snapshot"))


if __name__ == "__main__":
    unittest.main()
