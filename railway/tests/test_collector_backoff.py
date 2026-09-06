"""A throttled collector backs off and retries; it does not drop the slot.

Until 2026-09-06 the two collectors that most often meet a throttle did not
retry at all. Google News answered one 429 and that (query, edition) slice was
dropped for the run, with no error, no health row and no ledger slot, and
because run_slice rotates the ring it did not come back for a full walk.
EDGAR's full-text search answered a 403 (its throttle wears that status, not
429) and that keyword was dropped the same way. Neither is a fault the
collector can see, because a query that was never answered produces nothing.

Both now go through http_retry.get_with_retry, which honours Retry-After
(capped, so a workflow's timeout-minutes is never slept through) and retries
a bounded number of times. These tests pin:

  * Retry-After is read, capped, and used instead of the linear backoff;
  * a 429 then a 200 is ONE slice kept, not one slice dropped;
  * EDGAR's 403 is in its transient set and is retried;
  * exhaustion is a raised/reported outcome, never a silent continue;
  * and neither module carries a bare `requests.get(` any more, so a future
    fetch site cannot quietly opt back out of the retry.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import http_retry  # noqa: E402
from sources import edgar, google_news  # noqa: E402

SRC = Path(__file__).resolve().parents[1] / "sources"


class _Resp:
    def __init__(self, status, text="", headers=None, payload=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _sequence(responses, calls):
    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, timeout))
        return responses.pop(0)
    return get


class RetryAfterIsHonouredAndCapped(unittest.TestCase):
    def test_the_header_replaces_the_linear_backoff(self):
        calls, sleeps = [], []
        get = _sequence([_Resp(429, headers={"Retry-After": "7"}), _Resp(200)], calls)
        r = http_retry.get_with_retry("u", get=get, sleep=sleeps.append, backoff=5)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [7.0])

    def test_a_header_asking_for_an_hour_is_capped(self):
        sleeps = []
        get = _sequence([_Resp(503, headers={"Retry-After": "3600"}), _Resp(200)], [])
        http_retry.get_with_retry("u", get=get, sleep=sleeps.append)
        self.assertEqual(sleeps, [float(http_retry.RETRY_AFTER_CAP_SECONDS)])

    def test_no_header_falls_back_to_the_linear_backoff(self):
        sleeps = []
        get = _sequence([_Resp(429), _Resp(429), _Resp(200)], [])
        http_retry.get_with_retry("u", get=get, sleep=sleeps.append, backoff=5)
        self.assertEqual(sleeps, [5, 10])

    def test_a_garbage_header_is_not_a_sleep(self):
        self.assertIsNone(http_retry.retry_after_seconds(_Resp(429, headers={"Retry-After": "soon"})))
        self.assertIsNone(http_retry.retry_after_seconds(_Resp(429, headers={"Retry-After": "-4"})))
        self.assertIsNone(http_retry.retry_after_seconds(_Resp(429)))

    def test_exhaustion_is_none_not_the_last_throttle(self):
        get = _sequence([_Resp(429)] * 3, [])
        self.assertIsNone(http_retry.get_with_retry("u", get=get, sleep=lambda s: None))

    def test_the_widened_transient_set_is_per_call(self):
        calls = []
        get = _sequence([_Resp(403), _Resp(200)], calls)
        r = http_retry.get_with_retry("u", get=get, sleep=lambda s: None, transient={403})
        self.assertEqual((r.status_code, len(calls)), (200, 2))
        calls.clear()
        get = _sequence([_Resp(403), _Resp(200)], calls)
        r = http_retry.get_with_retry("u", get=get, sleep=lambda s: None)
        self.assertEqual((r.status_code, len(calls)), (403, 1),
                         "403 is a real answer everywhere except where a caller says otherwise")


class EdgarRetriesItsThrottle(unittest.TestCase):
    def _run(self, responses):
        calls, sleeps = [], []
        with patch.object(edgar.requests, "get", _sequence(responses, calls)), \
             patch.object(http_retry, "_sleep", sleeps.append), \
             patch.object(edgar.time, "sleep", lambda s: None):
            return edgar._fetch_filing_text("https://www.sec.gov/x.htm"), calls, sleeps

    def test_a_403_then_a_200_is_one_document_read(self):
        text, calls, sleeps = self._run([
            _Resp(403, headers={"Retry-After": "2"}),
            _Resp(200, text="<p>a reduction in force of 400 employees</p>")])
        self.assertIn("reduction in force", text)
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [2.0])

    def test_a_429_is_retried_too(self):
        text, calls, _ = self._run([_Resp(429), _Resp(200, text="<p>layoffs of 12</p>")])
        self.assertEqual(len(calls), 2)
        self.assertIn("layoffs", text)

    def test_exhaustion_raises_so_the_existing_drop_path_fires_loudly(self):
        with self.assertRaises(RuntimeError) as cm:
            self._run([_Resp(403)] * 3)
        self.assertIn("transient answer on every one of 3 attempts", str(cm.exception))

    def test_a_404_is_a_real_answer_and_is_not_retried(self):
        with self.assertRaises(RuntimeError):
            _, calls, _ = self._run([_Resp(404)])
        # one attempt: raise_for_status fired on the first answer

    def test_the_search_loop_survives_one_throttled_page(self):
        hit = {"_id": "1:doc.htm", "_source": {"ciks": ["1"], "file_date": "2026-09-01",
                                              "display_names": ["Acme Corp"]}}
        payload = {"hits": {"hits": [hit], "total": {"value": 1}}}
        calls = []
        with patch.object(edgar.requests, "get",
                          _sequence([_Resp(429, headers={"Retry-After": "1"}),
                                     _Resp(200, payload=payload)] * 8, calls)), \
             patch.object(http_retry, "_sleep", lambda s: None), \
             patch.object(edgar.time, "sleep", lambda s: None):
            hits = edgar.search_company_filings("Acme")
        self.assertTrue(hits, "one 429 must not empty the company search")


class GoogleNewsKeepsAThrottledSlice(unittest.TestCase):
    FEED = ('<?xml version="1.0"?><rss version="2.0"><channel><item>'
            '<title>Acme cuts 400 jobs</title><link>https://www.reuters.com/a</link>'
            '<pubDate>Wed, 19 Aug 2026 10:00:00 GMT</pubDate>'
            '<source url="https://www.reuters.com">Reuters</source></item>'
            '</channel></rss>')

    def _pull(self, responses):
        calls, sleeps = [], []
        with patch.object(google_news.requests, "get", _sequence(responses, calls)), \
             patch.object(http_retry, "_sleep", sleeps.append), \
             patch.object(google_news.time, "sleep", lambda s: None), \
             patch.object(google_news, "_locales_for_now",
                          lambda: [google_news.GOOGLE_NEWS_LOCALES[0]]):
            rows = google_news.pull_google_news(queries=["layoffs"])
        return rows, calls, sleeps

    def test_a_429_then_a_200_keeps_the_slice(self):
        rows, calls, sleeps = self._pull([
            _Resp(429, headers={"Retry-After": "3"}), _Resp(200, text=self.FEED)])
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [3.0])
        self.assertEqual([r["source_name"] for r in rows], ["Reuters"])

    def test_exhaustion_is_counted_as_an_error_with_a_reason(self):
        rows, calls, _ = self._pull([_Resp(429)] * 3)
        self.assertEqual(rows, [])
        self.assertEqual(len(calls), 3)
        self.assertIn("every attempt", google_news.pull_google_news.last_error)

    def test_a_real_refusal_is_still_one_attempt(self):
        rows, calls, _ = self._pull([_Resp(404)])
        self.assertEqual((rows, len(calls)), ([], 1))
        self.assertEqual(google_news.pull_google_news.last_error, "HTTP 404")


class NoFetchSiteOptsOutOfTheRetry(unittest.TestCase):
    """The only `requests.get(` allowed in either module is the one handed to
    get_with_retry as `get=`. A new bare call is a new silent-drop path."""

    BARE = re.compile(r"requests\.get\((?!\*a, \*\*k\))")

    def test_edgar_has_no_bare_fetch(self):
        text = (SRC / "edgar.py").read_text()
        self.assertEqual(self.BARE.findall(text), [])

    def test_google_news_has_no_bare_fetch(self):
        text = (SRC / "google_news.py").read_text()
        self.assertEqual(self.BARE.findall(text), [])

    def test_edgar_names_its_own_throttle_status(self):
        self.assertIn(403, edgar.EDGAR_TRANSIENT)


if __name__ == "__main__":
    unittest.main()
