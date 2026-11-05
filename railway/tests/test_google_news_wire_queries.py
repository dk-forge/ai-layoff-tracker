"""Free recall sources for the 2026-11-05 benchmark misses.

Trade Desk, Campbell's, AmEx, Weil, Hasbro, EA and Flock were missed by the
broad sweeps. Most announce through a press wire (Business Wire, PR Newswire,
GlobeNewswire) or state the cut as "a reduction of its workforce", so the US
edition now also runs WIRE_QUERIES: Google News RSS restricted to the wires
plus workforce-reduction phrasing. Free (no key), US edition only, and still
behind the free title prefilter and the global MAX_ITEMS cap, so they add no
paid read that the cap did not already allow.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources import google_news, google_news_prefilter  # noqa: E402

US = google_news.GOOGLE_NEWS_LOCALES[0]


def _rss(title):
    return ("<rss><channel><item><title>%s</title><link>https://www.businesswire.com/"
            "news/home/1/en/x</link><pubDate>Mon, 03 Nov 2026 10:00:00 GMT</pubDate>"
            "<source url=\"https://www.businesswire.com\">Business Wire</source>"
            "</item></channel></rss>" % title)


class WireQueries(unittest.TestCase):
    def test_wire_queries_name_the_three_wires_and_reduction_terms(self):
        joined = " ".join(google_news.WIRE_QUERIES)
        for host in ("businesswire.com", "prnewswire.com", "globenewswire.com"):
            self.assertIn("site:" + host, joined)
        for term in ("layoffs", "job cuts", "workforce reduction"):
            self.assertIn(term, joined)

    def _urls(self, **kw):
        urls = []

        def get(url, params=None, headers=None, timeout=None):
            urls.append(url)

            class R:
                status_code = 200
                headers = {}
                text = "<rss><channel></channel></rss>"
            return R()
        with patch.object(google_news.requests, "get", get), \
                patch.object(google_news, "_locales_for_now", lambda: [US]), \
                patch.object(google_news, "GAP", 0):
            google_news.pull_google_news(**kw)
        return urls

    def test_broad_run_issues_every_wire_query_on_the_us_edition(self):
        urls = self._urls()
        for q in google_news.WIRE_QUERIES:
            self.assertIn(google_news._rss_url(q, *US[1:]), urls)

    def test_explicit_queries_do_not_add_wire_queries(self):
        urls = self._urls(queries=["x"])
        self.assertEqual(urls, [google_news._rss_url("x", *US[1:])])

    def test_prefilter_keeps_percent_of_workforce_wire_headlines(self):
        for title in ("FICO Announces Workforce Reduction of Approximately 15%",
                      "Hasbro to cut about 1,100 jobs",
                      "The Trade Desk announces reduction in force"):
            keep, why = google_news_prefilter.title_verdict(title, "en-US")
            self.assertTrue(keep, (title, why))

    def test_wire_item_flows_into_rows(self):
        def get(url, params=None, headers=None, timeout=None):
            class R:
                status_code = 200
                headers = {}
                text = (_rss("Hasbro to cut about 1,100 jobs")
                        if "businesswire" in url else "<rss><channel></channel></rss>")
            return R()
        with patch.object(google_news.requests, "get", get), \
                patch.object(google_news, "_locales_for_now", lambda: [US]), \
                patch.object(google_news, "GAP", 0):
            rows = google_news.pull_google_news()
        self.assertTrue(any("Hasbro" in r["raw_text"] for r in rows))


if __name__ == "__main__":
    unittest.main()
