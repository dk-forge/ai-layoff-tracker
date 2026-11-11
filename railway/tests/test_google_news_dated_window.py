"""The weekly news catch-up re-reads each past day through dated Google News RSS.

The 2026-11-05 benchmark missed 13 of 25 events, and every one of the shared
no-row misses (AmEx 3,500 on 10-23, EA 400 on 10-21, Comcast 10-22, Weil 10-28,
FICO 10-07, Flock 10-09, Hasbro 10-13, Workday 10-01, Trade Desk) was announced
inside the 2026-09-29 to 2026-11-05 ingest gap. The catch-up that was meant to
recover them read only NewsAPI (relevance-capped, 9 posted for 30 days), and
an undated Google News query returns today's most-relevant items, never a
specific past day. Google News RSS honours `after:`/`before:`, so a per-day
query reaches those headlines (measured 2026-11-11: "American Express to Cut
3,500 Jobs - WSJ" and "Electronic Arts lays off 400" for 2026-10-22..24).
Free (no key), US edition only, title prefilter on, capped per day.
"""
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources import google_news  # noqa: E402


def _rss(*titles):
    items = "".join(
        "<item><title>%s</title><link>https://www.wsj.com/a/%d</link>"
        "<pubDate>Fri, 23 Oct 2026 10:00:00 GMT</pubDate>"
        "<source url=\"https://www.wsj.com\">WSJ</source></item>" % (t, i)
        for i, t in enumerate(titles))
    return "<rss><channel>%s</channel></rss>" % items


class R:
    status_code = 200

    def __init__(self, text):
        self.text = text


class DatedQueries(unittest.TestCase):
    def test_each_query_is_bounded_to_one_day(self):
        qs = google_news.dated_queries(date(2026, 10, 23))
        self.assertTrue(qs)
        for q in qs:
            self.assertIn("after:2026-10-22", q)
            self.assertIn("before:2026-10-24", q)

    def test_covers_broad_and_workforce_phrasing(self):
        joined = " ".join(google_news.dated_queries(date(2026, 10, 23)))
        self.assertIn("job cuts", joined)
        self.assertIn("percent of its workforce", joined)

    def test_days_between_is_inclusive_and_ordered(self):
        days = google_news.days_between(date(2026, 10, 1), date(2026, 10, 3))
        self.assertEqual(days, [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)])


class PullDay(unittest.TestCase):
    def _pull(self, text, cap=25):
        urls = []

        def get(url, **kw):
            urls.append(url)
            return R(text)
        with patch.object(google_news.http_retry, "get_with_retry",
                          side_effect=lambda url, **kw: get(url)), \
                patch.object(google_news.time, "sleep"):
            rows = google_news.pull_google_news_day(date(2026, 10, 23), max_items=cap)
        return rows, urls

    def test_rows_have_the_news_shape_and_dedupe_across_queries(self):
        rows, urls = self._pull(_rss("American Express to Cut 3,500 Jobs"))
        self.assertEqual(len(rows), 1)          # same story from every query: one read
        row = rows[0]
        self.assertEqual(row["source_type"], "news")
        self.assertEqual(row["verification_level"], "bronze")
        self.assertIn("3,500", row["raw_text"])
        self.assertEqual(row["filing_date"], "2026-10-23")
        self.assertTrue(all("gl=US" in u for u in urls))   # US edition only

    def test_prefilter_drops_non_layoff_titles(self):
        rows, _ = self._pull(_rss("Trade Desk stock rises after earnings"))
        self.assertEqual(rows, [])

    def test_cap_holds(self):
        titles = [f"Company {i} to cut {100 + i} jobs" for i in range(40)]
        rows, _ = self._pull(_rss(*titles), cap=5)
        # The cap is per query (see VerbHeadlines): each query adds at most 5.
        n = len(google_news.dated_queries(date(2026, 10, 23)))
        self.assertEqual(len(rows), 5 * n)


class VerbHeadlines(unittest.TestCase):
    """2026-11-08 benchmark misses that Google News holds but the two broad
    dated queries never returned (measured 2026-11-11): "Fiserv cuts 3,000
    employees and contractor jobs" (Reuters), "NatWest slashes 1,000 jobs"
    (Telegraph), "Flutter to axe up to 1,400 jobs" (Reuters), "Netherlands
    aims to cut around 20% of government jobs" and "GSK to eliminate 1,200
    jobs". A verb-form query reached all five on their day."""

    def test_a_dated_query_reads_verb_form_job_headlines(self):
        qs = google_news.dated_queries(date(2026, 10, 30))
        verb = [q for q in qs if "slashes" in q and "axe" in q and "eliminate" in q]
        self.assertEqual(len(verb), 1)
        self.assertIn("jobs", verb[0])

    def test_each_query_gets_its_own_cap_so_the_first_cannot_starve_the_rest(self):
        per_query = {}

        def get(url, **kw):
            n = len(per_query)
            per_query[url] = n
            return R(_rss(*[f"Firm{n}x{i} to cut {100 + i} jobs" for i in range(10)])
                     .replace("/a/", f"/q{n}/"))
        with patch.object(google_news.http_retry, "get_with_retry",
                          side_effect=lambda url, **kw: get(url)), \
                patch.object(google_news.time, "sleep"):
            rows = google_news.pull_google_news_day(date(2026, 10, 30), max_items=4)
        n = len(google_news.dated_queries(date(2026, 10, 30)))
        self.assertEqual(len(per_query), n)
        self.assertEqual(len(rows), 4 * n)


class CatchupWiring(unittest.TestCase):
    def test_news_catchup_reads_the_dated_windows(self):
        src = (Path(__file__).resolve().parents[1] / "news_catchup.py").read_text()
        self.assertIn("pull_google_news_day", src)


if __name__ == "__main__":
    unittest.main()
