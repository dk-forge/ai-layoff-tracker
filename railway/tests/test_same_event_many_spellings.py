"""One event may not be counted once per spelling of its employer.

WRITTEN FROM A LIVE INSTANCE. The Week 37 reader digest carried ONE Jaguar
Land Rover event three times -- under a Chinese-language name, under the
parent's possessive, and under the abbreviation -- inflating the week's
"verified job cuts" by about 8,000 and the Automotive figure with it, and
producing the "no country recorded" line a reader saw.

Every existing defence was blind to it:
  * `duplicated_article_rows` keys on (source_url, job_count). Three outlets,
    three urls, so the key never grouped them.
  * every upstream dedup buckets on a company NAME, so three spellings make
    three buckets and the pair is never compared.

These tests pin the new key and, just as importantly, pin what it must NOT
report. A duplicate check that fires on two genuinely different employers is
worse than none, because the correction machinery is destructive.

Offline: pure functions over dict rows. No network, no keys.
"""
import sys
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAILWAY))

import data_integrity as di  # noqa: E402


def row(rid, event_id, name, jobs, when="2026-09-09",
        url=None, source_type="news"):
    return {"id": rid, "event_id": event_id, "company_name": name,
            "job_count": jobs, "layoff_date": when,
            "source_url": url or f"https://example.test/{rid}",
            "source_type": source_type}


class TheWeek37Instance(unittest.TestCase):
    """The defect that put this here, in the shape it actually had."""

    def setUp(self):
        # Three outlets, three urls, three spellings, one event.
        self.rows = [
            row(1, 101, "Jaguar Land Rover", 8000),
            row(2, 102, "捷豹路虎", 8000),      # the Chinese-language name
            row(3, 103, "Tata Motors' Jaguar Land Rover", 8000),
        ]

    def test_the_triple_is_reported(self):
        groups = di.same_event_under_many_spellings(self.rows)
        self.assertEqual(len(groups), 1, groups)
        self.assertEqual({r["id"] for r in groups[0]["rows"]}, {1, 2, 3})

    def test_the_excess_is_what_the_headline_carried_over(self):
        """Two extra copies of 8,000 is 16,000 of excess, not 24,000."""
        groups = di.same_event_under_many_spellings(self.rows)
        self.assertEqual(groups[0]["excess"], 16000)

    def test_the_article_key_cannot_see_it(self):
        """The reason this is a second check and not a widened first one."""
        self.assertEqual(di.duplicated_article_rows(self.rows), [])

    def test_the_abbreviation_is_caught_too(self):
        rows = [row(1, 101, "Jaguar Land Rover", 8000),
                row(2, 102, "JLR", 8000)]
        groups = di.same_event_under_many_spellings(rows)
        self.assertEqual(len(groups), 1)
        self.assertIn("initialism", groups[0]["reasons"][0])

    def test_the_reason_names_the_branch_that_fired(self):
        """A reviewer must know which branch put a pair in front of them."""
        groups = di.same_event_under_many_spellings(self.rows)
        joined = " | ".join(groups[0]["reasons"])
        self.assertIn("non-Latin script", joined)
        self.assertIn("identity word", joined)


class WhatItMustNotReport(unittest.TestCase):
    """A destructive correction follows a FAIL, so false positives are costly."""

    def test_two_different_employers_cutting_the_same_number_same_day(self):
        rows = [row(1, 101, "Acme Steel", 500),
                row(2, 102, "Bedrock Logistics", 500)]
        self.assertEqual(di.same_event_under_many_spellings(rows), [])

    def test_rows_already_joined_under_one_event_id(self):
        """One event already; the aggregate does not double count it."""
        rows = [row(1, 101, "Jaguar Land Rover", 8000),
                row(2, 101, "JLR", 8000)]
        self.assertEqual(di.same_event_under_many_spellings(rows), [])

    def test_register_rows_are_exempt(self):
        """WARN filings are legitimately several notices for one event."""
        rows = [row(1, 101, "Jaguar Land Rover", 8000, source_type="warn"),
                row(2, 102, "JLR", 8000, source_type="warn")]
        self.assertEqual(di.same_event_under_many_spellings(rows), [])

    def test_the_same_spelling_twice_is_left_to_the_article_key(self):
        """Two checks must not argue over one row."""
        rows = [row(1, 101, "Jaguar Land Rover", 8000),
                row(2, 102, "Jaguar Land Rover", 8000)]
        self.assertEqual(di.same_event_under_many_spellings(rows), [])

    def test_a_different_date_is_a_different_observation(self):
        rows = [row(1, 101, "Jaguar Land Rover", 8000, when="2026-09-09"),
                row(2, 102, "JLR", 8000, when="2026-09-10")]
        self.assertEqual(di.same_event_under_many_spellings(rows), [])

    def test_a_row_with_no_date_is_skipped_not_guessed(self):
        rows = [row(1, 101, "Jaguar Land Rover", 8000, when=""),
                row(2, 102, "JLR", 8000, when="")]
        self.assertEqual(di.same_event_under_many_spellings(rows), [])

    def test_a_single_letter_is_not_an_initialism(self):
        """'A' against 'Acme' would match far too much to mean anything."""
        self.assertIsNone(di.names_may_be_one_employer("A", "Acme Steel"))


class TheNameRules(unittest.TestCase):
    def test_legal_form_words_do_not_make_two_names_different(self):
        self.assertIsNone(
            di.names_may_be_one_employer("Jaguar Land Rover Ltd",
                                         "Jaguar Land Rover Limited"))

    def test_legal_form_words_do_not_break_an_initialism(self):
        self.assertIsNotNone(
            di.names_may_be_one_employer("JLR", "Jaguar Land Rover Ltd"))

    def test_a_possessive_parent_contains_the_subsidiary(self):
        why = di.names_may_be_one_employer("Tata Motors' Jaguar Land Rover",
                                           "Jaguar Land Rover")
        self.assertIsNotNone(why)
        self.assertIn("identity word", why)

    def test_overlapping_but_neither_containing_is_not_reported(self):
        """'Acme Steel' and 'Acme Plastics' share a word and are not one firm."""
        self.assertIsNone(
            di.names_may_be_one_employer("Acme Steel", "Acme Plastics"))

    def test_two_non_latin_names_are_not_paired_on_script_alone(self):
        """The script branch exists to bridge Latin and non-Latin, not to
        pair two unrelated CJK names with each other."""
        self.assertIsNone(
            di.names_may_be_one_employer("捷豹路虎",
                                         "丰田汽车"))


class TheInvariantContract(unittest.TestCase):
    """PASS / FAIL / UNKNOWN are three states and absence is not a pass."""

    def _ctx(self, body, **kw):
        import datetime

        class Ctx:
            today = datetime.date(2026, 9, 16)
            cachebust = "1"
            timeout = 5

            def fetch(self, url, timeout):
                if isinstance(body, Exception):
                    raise body
                return body
        c = Ctx()
        for k, v in kw.items():
            setattr(c, k, v)
        return c

    def test_no_rows_is_unknown_not_pass(self):
        import json
        res = di.SameEventManySpellingsInvariant().run(
            self._ctx(json.dumps({"data": [], "total": 0})))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertIn("did not run", res.detail)

    def test_an_unreadable_body_is_unknown(self):
        res = di.SameEventManySpellingsInvariant().run(
            self._ctx(RuntimeError("boom")))
        self.assertEqual(res.state, di.UNKNOWN)

    def test_a_clean_page_prints_the_floor_it_did_not_look_below(self):
        import json
        body = json.dumps({"total": 9, "data": [
            row(1, 101, "Acme Steel", 900),
            row(2, 102, "Bedrock Logistics", 400)]})
        res = di.SameEventManySpellingsInvariant().run(self._ctx(body))
        self.assertEqual(res.state, di.PASS)
        self.assertIn("400", res.detail)
        self.assertIn("NOT claimed clean", res.detail)

    def test_the_triple_fails_with_the_rows_named(self):
        import json
        body = json.dumps({"total": 3, "data": [
            row(1, 101, "Jaguar Land Rover", 8000),
            row(2, 102, "捷豹路虎", 8000),
            row(3, 103, "Tata Motors' Jaguar Land Rover", 8000)]})
        res = di.SameEventManySpellingsInvariant().run(self._ctx(body))
        self.assertEqual(res.state, di.FAIL)
        self.assertEqual(res.observed, 16000)
        for rid in ("1", "2", "3"):
            self.assertIn(rid, res.detail)
        self.assertIn("never", res.detail.lower())   # "never by hand"

    def test_it_is_registered_and_reads_live_data(self):
        keys = [getattr(i, "key", None) for i in di.INVARIANTS]
        self.assertIn("same_event_many_spellings", keys)
        inv = next(i for i in di.INVARIANTS
                   if getattr(i, "key", None) == "same_event_many_spellings")
        self.assertTrue(inv.reads_live_data)

    def test_it_does_not_share_a_key_with_the_article_check(self):
        keys = [getattr(i, "key", None) for i in di.INVARIANTS]
        self.assertEqual(len(keys), len(set(keys)), "duplicate invariant key")


if __name__ == "__main__":
    unittest.main()
