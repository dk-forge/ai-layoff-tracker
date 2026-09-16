"""Offline tests for the "one article, one number, one row" guard.

THE KNOWN INSTANCE this is written from is live July 2026 US data. Rows 177161
("Los Angeles Unified School District") and 176442 ("LAUSD") each store 6,000
jobs, cite the SAME Google News article url, sit one day apart, carry different
event ids, and are BOTH summed into the published July headline. 6,000 jobs of
pure double count, invisible to every existing defence because all of them
bucket on a company name first and those two spellings make two buckets.

The near-misses below are the reason the key is (url, job_count) and not url
alone. Both are live shapes:

  * one CA WARN register url is the `source_url` of 129 unrelated July rows,
  * the OPM workforce-changes portal is the `source_url` of four federal
    agencies with four different counts.

A guard that flagged either would be noise, and noise is how an alert channel
gets filtered (docs/CLAUDE.md on the Spirit assertion).

No network and no keys: the fetch is injected everywhere.
"""
import json
import sys
import unittest
import urllib.error
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity as di


def _row(row_id, event_id, jobs, url, source_type="news", company="Acme"):
    return {"id": row_id, "event_id": event_id, "job_count": jobs,
            "source_url": url, "source_type": source_type,
            "company_name": company}


ARTICLE = ("https://news.google.com/rss/articles/CBMiaEFVX3lxTFB5bUs0LW82WVdB"
           "OGpwNlRWcW84dDU3V1cwcXZXMDdOT2RadnZWUVhSa1NxZ01aVlF4MXQ1UlFRWEFF")

#: The live pair, verbatim in the fields the key reads.
LAUSD = [
    _row(177161, 149894, 6000, ARTICLE, company="Los Angeles Unified School District"),
    _row(176442, 149191, 6000, ARTICLE, company="LAUSD"),
]

#: One state register url behind many unrelated notices.
CA_REGISTER = "https://edd.ca.gov/en/jobs_and_training/warn/"
WARN_REGISTER = [
    _row(134371, 559, 2212, CA_REGISTER, source_type="warn", company="Meta Platforms, Inc."),
    _row(134255, 561, 493, CA_REGISTER, source_type="warn", company="Intuit Inc."),
    _row(134368, 556, 338, CA_REGISTER, source_type="warn", company="Meta Platforms, Inc."),
]

#: One data portal behind four agencies with four different counts.
OPM = "https://data.opm.gov/explore-data/analytics/workforce-changes"
FEDERAL_RIF = [
    _row(179172, 151905, 16, OPM, source_type="federal_rif", company="Department Of Justice"),
    _row(179170, 151903, 13, OPM, source_type="federal_rif", company="Department Of HHS"),
    _row(179173, 151906, 9, OPM, source_type="federal_rif", company="Fed Mine Safety"),
    _row(179171, 151904, 6, OPM, source_type="federal_rif", company="Department Of Interior"),
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
    """It must fire on the pair that is actually live, and say what to do."""

    def test_the_live_lausd_pair_is_found(self):
        found = di.duplicated_article_rows(LAUSD)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["job_count"], 6000)
        self.assertEqual(found[0]["excess"], 6000)
        self.assertEqual([r["id"] for r in found[0]["rows"]], [176442, 177161])

    def test_the_invariant_FAILS_on_it_and_names_both_rows(self):
        res = di.DuplicateArticleInvariant().run(_ctx(_page(LAUSD)))
        self.assertEqual(res.state, di.FAIL)
        self.assertEqual(res.observed, 6000)
        self.assertIn("177161", res.detail)
        self.assertIn("176442", res.detail)
        self.assertIn("6,000", res.detail)

    def test_it_still_fires_when_the_pair_is_buried_in_ordinary_rows(self):
        """A name key misses this pair; burying it must not make this one miss."""
        rows = WARN_REGISTER + FEDERAL_RIF + LAUSD + [
            _row(99000 + n, 900 + n, 800 - n, f"https://example.com/a{n}")
            for n in range(40)]
        res = di.DuplicateArticleInvariant().run(_ctx(_page(rows)))
        self.assertEqual(res.state, di.FAIL)
        self.assertEqual(res.observed, 6000)


class TheNearMisses(unittest.TestCase):
    """The shapes that make a url-only key useless. None may be reported."""

    def test_a_shared_warn_register_url_is_not_a_duplicate(self):
        self.assertEqual(di.duplicated_article_rows(WARN_REGISTER), [])

    def test_a_shared_federal_portal_url_is_not_a_duplicate(self):
        self.assertEqual(di.duplicated_article_rows(FEDERAL_RIF), [])

    def test_two_equal_counts_on_a_register_url_are_still_not_reported(self):
        """Register exclusion is by source_type, so it holds even on a tie.

        Companies legally file several WARN notices close together, and the
        iron rule exempts WARN from fuzzy dedup. Two 500s on one register page
        are two notices, not one stored twice.
        """
        rows = [_row(1, 11, 500, CA_REGISTER, source_type="warn"),
                _row(2, 12, 500, CA_REGISTER, source_type="warn")]
        self.assertEqual(di.duplicated_article_rows(rows), [])

    def test_one_article_with_two_different_counts_is_not_reported(self):
        rows = [_row(1, 11, 500, "https://x/a"), _row(2, 12, 400, "https://x/a")]
        self.assertEqual(di.duplicated_article_rows(rows), [])

    def test_rows_already_joined_into_one_event_are_not_reported(self):
        rows = [_row(1, 77, 500, "https://x/a"), _row(2, 77, 500, "https://x/a")]
        self.assertEqual(di.duplicated_article_rows(rows), [])

    def test_blank_urls_and_zero_counts_never_group(self):
        rows = [_row(1, 11, 500, ""), _row(2, 12, 500, ""),
                _row(3, 13, 0, "https://x/a"), _row(4, 14, 0, "https://x/a")]
        self.assertEqual(di.duplicated_article_rows(rows), [])

    def test_a_clean_page_passes_and_prints_its_floor(self):
        rows = WARN_REGISTER + [_row(5, 55, 550, "https://x/b")]
        res = di.DuplicateArticleInvariant().run(_ctx(_page(rows, total=2918)))
        self.assertEqual(res.state, di.PASS)
        # The floor is the SMALLEST count the page reached, and it is printed so
        # a reader never mistakes this sweep's reach for the whole corpus.
        self.assertIn("down to 338 jobs", res.detail)
        self.assertIn("2,918", res.detail)
        self.assertIn("NOT claimed clean", res.detail)


class MissingDataIsNotAPass(unittest.TestCase):

    def test_an_unreachable_query_is_UNKNOWN(self):
        res = di.DuplicateArticleInvariant().run(_ctx(OSError("refused")))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertTrue(res.transport)

    def test_a_503_deploy_window_is_UNKNOWN_not_FAIL(self):
        err = urllib.error.HTTPError("u", 503, "maint", None, None)
        res = di.DuplicateArticleInvariant().run(_ctx(err))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertIn("503", res.detail)

    def test_an_empty_page_is_UNKNOWN_not_clean(self):
        res = di.DuplicateArticleInvariant().run(_ctx(_page([])))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertIn("did not run", res.detail)

    def test_an_undecodable_body_is_UNKNOWN(self):
        res = di.DuplicateArticleInvariant().run(_ctx(b"<html>bot challenge</html>"))
        self.assertEqual(res.state, di.UNKNOWN)


class ItIsRegisteredAndBounded(unittest.TestCase):

    def test_it_is_in_the_live_invariant_set(self):
        keys = [i.key for i in di.INVARIANTS]
        self.assertIn("duplicate_article_rows", keys)

    def test_it_declares_that_it_reads_live_data(self):
        """So a failure raises under the branch-free live.data incident scope."""
        self.assertTrue(di.DuplicateArticleInvariant.reads_live_data)

    def test_the_sweep_is_exactly_one_request(self):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return _page(LAUSD)

        ctx = di.Ctx(fetch, 5, "cb", today=date(2026, 9, 16))
        di.DuplicateArticleInvariant().run(ctx)
        self.assertEqual(len(calls), 1, "never page-walk the live host")
        self.assertIn("per_page=200", calls[0])
        self.assertIn("exclude_supersets=1", calls[0])
        self.assertIn("from=2026-03-20", calls[0])


if __name__ == "__main__":
    unittest.main()
