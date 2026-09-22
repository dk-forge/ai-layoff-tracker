"""A news.google.com/rss/articles/... redirector is not a checkable source.

`recall_precision.measure_precision()` used to fetch every stored
`source_url`, including unresolved Google News redirectors, and count a miss
whenever the job count was not in the fetched text. But
`sources/google_news_url.py` documents that these hosts are Disallow: / in
robots.txt and, measured 2026-08-18 (`blank_country_census.py`
UNREADABLE_HOSTS), return an 11-byte redirect stub with no article content.
Fetching one and grading it against the stub misread "we refuse to read this"
as "the number is fabricated" -- every PRECISION MISS in the 2026-09-21 run
was a news.google.com link (recall-precision.yml run 35650796130).

These tests need no network: `requests.get` is patched, and a call for a
news.google.com URL raises if it is ever attempted at all.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import recall_precision as rp


class FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        return self._json


REDIRECTOR = ("https://news.google.com/rss/articles/"
              "CBMiiAFBVV95cUxQWTNPZjIzVGJmWGd5M")


def _query_rows(rows):
    return FakeResponse(200, json_data={"data": rows})


class MeasurePrecisionRedirectorTests(unittest.TestCase):
    def _run(self, rows, extra_get=None):
        def fake_get(url, **kw):
            if "wp-json" in url:
                return _query_rows(rows)
            if url == REDIRECTOR:
                raise AssertionError(
                    "news.google.com must never be fetched — robots.txt is "
                    "Disallow: / for every UA (sources/google_news_url.py)")
            if extra_get:
                return extra_get(url)
            raise AssertionError(f"unexpected fetch: {url}")

        with mock.patch("recall_precision.requests.get", side_effect=fake_get), \
             mock.patch("recall_precision.time.sleep"):
            return rp.measure_precision()

    def test_redirector_never_fetched_and_excluded_from_checked(self):
        rows = [{"company_name": "VW Group", "job_count": 4100,
                  "source_url": REDIRECTOR}]
        result = self._run(rows)
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["reasons"].get("google_news_redirector"), 1)
        self.assertNotIn("number_not_in_source", result["reasons"])

    def test_redirector_does_not_drag_down_precision_with_real_rows(self):
        rows = [
            {"company_name": "VW Group", "job_count": 4100,
             "source_url": REDIRECTOR},
            {"company_name": "Real Corp", "job_count": 500,
             "source_url": "https://www.realpublisher.com/article-500-jobs"},
        ]
        result = self._run(
            rows,
            extra_get=lambda url: FakeResponse(
                200, text="Real Corp is cutting 500 jobs today."))
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["reasons"], {"google_news_redirector": 1})

    def test_a_real_fabricated_number_from_a_readable_source_still_fails(self):
        rows = [{"company_name": "Fabricated Co", "job_count": 999,
                  "source_url": "https://www.realpublisher.com/article"}]
        result = self._run(
            rows,
            extra_get=lambda url: FakeResponse(
                200, text="Fabricated Co had layoffs but no number here."))
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["ok"], 0)
        self.assertEqual(result["reasons"].get("number_not_in_source"), 1)


if __name__ == "__main__":
    unittest.main()


class RedirectorsDoNotEatTheSample(unittest.TestCase):
    def test_the_sample_is_cut_from_readable_sources(self):
        rows = ([{"company_name": f"R{i}", "job_count": 10, "source_url": REDIRECTOR}
                 for i in range(rp.SAMPLE)]
                + [{"company_name": f"C{i}", "job_count": 10,
                    "source_url": f"https://www.realpublisher.com/{i}"}
                   for i in range(rp.SAMPLE)])

        def fake_get(url, **kw):
            if "wp-json" in url:
                return _query_rows(rows)
            if url == REDIRECTOR:
                raise AssertionError("news.google.com must never be fetched")
            return FakeResponse(200, text="cutting 10 jobs")

        with mock.patch("recall_precision.requests.get", side_effect=fake_get), \
             mock.patch("recall_precision.time.sleep"):
            result = rp.measure_precision()
        self.assertEqual(result["checked"], rp.SAMPLE)
        self.assertEqual(result["reasons"]["google_news_redirector"], rp.SAMPLE)
        self.assertEqual(rp.judge_precision(result)[0], "pass")
