"""The cross-alias duplicate guard, proven on the rows it was written for.

A GUARD'S CLEAN ZERO IS WORTHLESS UNTIL IT HAS CAUGHT ONE KNOWN INSTANCE, and a
guard that shares its target's blind spot catches nothing. `duplicate_article_
rows` was written for exactly that reason in September, keyed on (source_url,
job_count) so that no spelling could remove a pair from consideration -- and
that key is bounded by the same property: it only fires when the two rows cite
the SAME article.

THE ROWS BELOW ARE THE LIVE ONES IT COULD NOT SEE. On 2026-09-07/08 Jaguar Land
Rover's 4,000 job cuts were stored four times, from four different outlets,
under four names: "Jaguar Land Rover" (moneycontrol), "JLR" (Wards Auto), "Tata
Motors' JLR" (livemint) and "捷豹路虎" (Yahoo新聞). Four URLs, so the article key
sees four unrelated rows. Four spellings, so every name-bucketed dedup pass
sees four unrelated employers. Three of them went out in the Week 37 reader
digest as three separate "Biggest cuts".

The MUTATION half is the half that proves this file is doing work: each of the
three conditions is broken in turn on the same rows, and the guard must go
quiet for each one. A guard that still fires with a condition removed is not
testing that condition.
"""
import json
import sys
import unittest
import urllib.error
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity as di


def _row(row_id, event_id, jobs, company, when, source_type="news", url=None):
    return {"id": row_id, "event_id": event_id, "job_count": jobs,
            "company_name": company, "layoff_date": when,
            "source_type": source_type,
            "source_url": url or f"https://example.test/{row_id}"}


#: The live four, verbatim in the fields the key reads. Every id, event id,
#: name and date is what /query returned on 2026-09-16.
JLR = [
    _row(179163, 151896, 4000, "Jaguar Land Rover", "2026-09-05"),
    _row(179186, 151919, 4000, "JLR", "2026-09-08"),
    _row(179194, 151927, 4000, "Tata Motors’ JLR", "2026-09-07"),
    _row(179237, 151970, 4000, "捷豹路虎", "2026-09-08"),
]

#: One employer, one day, several sites: the WARN register shape. Measured on
#: the live corpus, this exact shape produces 16 groups across two 200-row WARN
#: samples, and every one of them is correct data. WARN is exempt from fuzzy
#: dedup by policy for this reason.
WARN_SITES = [
    _row(1, 11, 6, "Manteca District Ambulance Service", "2026-06-30", "warn"),
    _row(2, 12, 6, "Manteca District Ambulance Service - Hwy 49", "2026-06-30", "warn"),
    _row(3, 13, 6, "Manteca District Ambulance Service - Powder House", "2026-06-30", "warn"),
]

ORDINARY = [
    _row(900, 800, 500, "Zimmer Biomet", "2026-09-09"),
    _row(901, 801, 470, "WKW Hungaria", "2026-09-07"),
    _row(902, 802, 345, "Nature’s Bakery, LLC", "2026-09-11"),
]


def _page(rows, total=None):
    return json.dumps({"data": rows,
                       "total": len(rows) if total is None else total}).encode()


def _ctx(body, today=date(2026, 9, 16)):
    def fetch(url, timeout):
        if isinstance(body, Exception):
            raise body
        return body
    return di.Ctx(fetch, 5, "cb", today=today)


class TheKnownInstance(unittest.TestCase):

    def test_the_live_jlr_cluster_is_found(self):
        groups = di.cross_alias_duplicate_rows(JLR)
        self.assertEqual(1, len(groups))
        self.assertEqual({179163, 179186, 179194, 179237},
                         {r["id"] for r in groups[0]["rows"]})
        # Four copies of one 4,000-job event: three of them are excess.
        self.assertEqual(12000, groups[0]["excess"])

    def test_the_invariant_FAILS_on_it_and_names_the_rows_and_the_rule(self):
        res = di.CrossAliasDuplicateInvariant().run(_ctx(_page(JLR)))
        self.assertEqual(res.state, di.FAIL)
        self.assertEqual(12000, res.observed)
        for row_id in (179163, 179186, 179194, 179237):
            self.assertIn(str(row_id), res.detail)
        self.assertIn("4,000", res.detail)
        # The sentence has to say WHY two names were read as one employer, or a
        # reader cannot check the judgement it just made.
        self.assertIn("the same canonical company key", res.detail)

    def test_the_chinese_row_is_joined_by_its_recorded_alias(self):
        pair = [dict(r) for r in JLR if r["id"] in (179186, 179237)]
        groups = di.cross_alias_duplicate_rows(pair)
        self.assertEqual(1, len(groups))
        self.assertIn("non-Latin spelling", groups[0]["why"])

    def test_it_still_fires_when_the_cluster_is_buried_in_ordinary_rows(self):
        res = di.CrossAliasDuplicateInvariant().run(
            _ctx(_page(ORDINARY + JLR + ORDINARY, total=2918)))
        self.assertEqual(res.state, di.FAIL)

    def test_the_pair_the_article_key_can_see_is_not_this_one(self):
        """The two guards are not redundant, and this is the proof.

        Every JLR row carries a DIFFERENT source_url, so the sibling guard --
        which is the right guard for one article stored twice -- reads these
        four rows as four unrelated ones and passes.
        """
        self.assertEqual([], di.duplicated_article_rows(JLR))


class TheMutations(unittest.TestCase):
    """Break one condition at a time; the guard must go quiet for each."""

    def test_different_counts_are_not_reported(self):
        rows = [dict(r) for r in JLR]
        rows[1]["job_count"] = 3800      # a different figure is a different fact
        groups = di.cross_alias_duplicate_rows(rows)
        self.assertEqual({179163, 179194, 179237},
                         {r["id"] for g in groups for r in g["rows"]})

    def test_dates_beyond_the_window_are_not_reported(self):
        rows = [dict(r) for r in JLR]
        for row, when in zip(rows, ("2026-03-05", "2026-06-08", "2026-09-07", "2026-09-08")):
            row["layoff_date"] = when
        # Only the two that remain within two days of each other survive, and
        # 09-07/09-08 is that pair.
        groups = di.cross_alias_duplicate_rows(rows)
        self.assertEqual([{179194, 179237}], [{r["id"] for r in g["rows"]} for g in groups])

    def test_names_that_do_not_resolve_to_one_employer_are_not_reported(self):
        """The blind spot itself, made visible.

        Rename the rows to four unrelated employers and the guard goes silent
        on rows that are otherwise identical. That is the whole reason the
        employer test cannot be dropped for something cheaper.
        """
        rows = [dict(r) for r in JLR]
        for row, name in zip(rows, ("Zimmer Biomet", "Trinity Health", "BBC", "Ilva")):
            row["company_name"] = name
        self.assertEqual([], di.cross_alias_duplicate_rows(rows))

    def test_rows_already_joined_into_one_event_are_not_reported(self):
        rows = [dict(r) for r in JLR]
        for row in rows:
            row["event_id"] = 151896
        self.assertEqual([], di.cross_alias_duplicate_rows(rows))

    def test_an_unrecorded_non_latin_name_still_joins_on_the_same_day_only(self):
        """The alias list is exact and blind to the next spelling; the script
        branch is general and weak, and they are not the same claim.

        alt_company_key strips every character outside [a-z0-9 ], so a CJK name
        has no company key and nothing can INFER that four glyphs are Jaguar
        Land Rover. Remove the recorded alias and the row is no longer joined
        by NAME. But a Latin and a non-Latin name cannot be compared as words
        at all, so a pair carrying the same count on the SAME DAY is still
        reported, on the count and the date alone, with a reason that says so.
        (That branch is adapted from PR #377, which reached the general case
        this module's alias list does not.)
        """
        import entity_resolution as er
        recorded = er.NON_LATIN_ALIASES.pop("捷豹路虎")
        try:
            # In isolation: the CJK row and the same-day Latin row, joined
            # on the count and the date alone.
            same_day = [dict(r) for r in JLR if r["id"] in (179186, 179237)]
            cluster = di.cross_alias_duplicate_rows(same_day)
            self.assertEqual(1, len(cluster), "the same-day pair must still be reported")
            self.assertIn("non-Latin script", cluster[0]["why"])
            self.assertIn("only signal", cluster[0]["why"])
            self.assertEqual({179186, 179237}, {r["id"] for r in cluster[0]["rows"]})
            # And in the full set it is still held, now inside the cluster the
            # three Latin spellings already form.
            groups = di.cross_alias_duplicate_rows(JLR)
            self.assertEqual(1, len(groups))
            self.assertIn(179237, {r["id"] for r in groups[0]["rows"]})
        finally:
            er.NON_LATIN_ALIASES["捷豹路虎"] = recorded

    def test_the_script_branch_does_not_reach_across_the_two_day_window(self):
        """No name evidence means same day only, or the weakest branch would
        also be the widest one."""
        import entity_resolution as er
        recorded = er.NON_LATIN_ALIASES.pop("捷豹路虎")
        try:
            # 2026-09-07 and 2026-09-08: inside the window, one day apart.
            rows = [dict(r) for r in JLR if r["id"] in (179194, 179237)]
            self.assertEqual([], di.cross_alias_duplicate_rows(rows))
        finally:
            er.NON_LATIN_ALIASES["捷豹路虎"] = recorded


class TheNearMisses(unittest.TestCase):

    def test_the_warn_register_shape_never_trips_it(self):
        """One employer, one day, several sites is a WARN register's normal
        output and it is correct data. Measured over two 200-row live WARN
        samples this shape produces 16 groups; the source-type exclusion is
        what keeps every one of them out."""
        self.assertEqual([], di.cross_alias_duplicate_rows(WARN_SITES))
        # And the exclusion is doing the work, not luck about the fixture.
        self.assertEqual(1, len(di.cross_alias_duplicate_rows(
            WARN_SITES, register_types=set())))

    def test_federal_rif_rows_are_excluded_too(self):
        rows = [_row(i, 500 + i, 16, "Department Of Justice", "2026-09-07", "federal_rif")
                for i in (1, 2)]
        self.assertEqual([], di.cross_alias_duplicate_rows(rows))

    def test_two_genuine_rounds_at_one_employer_stay_two_rows(self):
        rows = [_row(1, 11, 500, "Zimmer Biomet", "2026-05-01"),
                _row(2, 12, 500, "Zimmer Biomet", "2026-09-09")]
        self.assertEqual([], di.cross_alias_duplicate_rows(rows))

    def test_a_shared_date_and_count_at_different_employers_is_not_a_duplicate(self):
        rows = [_row(1, 11, 400, "Vodafone", "2026-09-02"),
                _row(2, 12, 400, "Telefonica", "2026-09-02")]
        self.assertEqual([], di.cross_alias_duplicate_rows(rows))

    def test_rows_with_no_date_never_group(self):
        rows = [_row(1, 11, 4000, "JLR", ""), _row(2, 12, 4000, "Jaguar Land Rover", "")]
        self.assertEqual([], di.cross_alias_duplicate_rows(rows))

    def test_zero_counts_never_group(self):
        rows = [_row(1, 11, 0, "JLR", "2026-09-07"),
                _row(2, 12, 0, "Jaguar Land Rover", "2026-09-08")]
        self.assertEqual([], di.cross_alias_duplicate_rows(rows))

    def test_a_clean_page_passes_and_prints_its_floor(self):
        res = di.CrossAliasDuplicateInvariant().run(_ctx(_page(ORDINARY, total=2918)))
        self.assertEqual(res.state, di.PASS)
        self.assertIn("down to 345 jobs", res.detail)
        self.assertIn("2,918", res.detail)
        self.assertIn("NOT claimed clean", res.detail)


class MissingDataIsNotAPass(unittest.TestCase):

    def test_an_unreachable_query_is_UNKNOWN(self):
        res = di.CrossAliasDuplicateInvariant().run(_ctx(OSError("refused")))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertTrue(res.transport)

    def test_a_503_deploy_window_is_UNKNOWN_not_FAIL(self):
        err = urllib.error.HTTPError("u", 503, "maint", None, None)
        res = di.CrossAliasDuplicateInvariant().run(_ctx(err))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertIn("503", res.detail)

    def test_an_empty_page_is_UNKNOWN_not_clean(self):
        res = di.CrossAliasDuplicateInvariant().run(_ctx(_page([])))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertIn("did not run", res.detail)

    def test_an_undecodable_body_is_UNKNOWN(self):
        res = di.CrossAliasDuplicateInvariant().run(_ctx(b"<html>bot challenge</html>"))
        self.assertEqual(res.state, di.UNKNOWN)


class ItIsRegisteredAndBounded(unittest.TestCase):

    def test_it_is_in_the_live_invariant_set(self):
        self.assertIn("cross_alias_duplicate_rows", [i.key for i in di.INVARIANTS])

    def test_it_declares_that_it_reads_live_data(self):
        self.assertTrue(di.CrossAliasDuplicateInvariant.reads_live_data)

    def test_the_sweep_is_exactly_one_request(self):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return _page(JLR)

        di.CrossAliasDuplicateInvariant().run(di.Ctx(fetch, 5, "cb", today=date(2026, 9, 16)))
        self.assertEqual(1, len(calls), "never page-walk the live host")
        self.assertIn("per_page=200", calls[0])
        self.assertIn("exclude_supersets=1", calls[0])


if __name__ == "__main__":
    unittest.main()
