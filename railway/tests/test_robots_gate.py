"""A publisher's robots.txt is consulted before its article body is fetched,
the fetch identifies itself, and a refusal is counted rather than swallowed.

The load-bearing test is the first one: robots says no, and the request to
the article URL must NOT go out. It is proven by mutation: with the gate
check in `sources.gdelt._fetch_article` removed, this test fails (recorded in
TECHLOG 2026-09-02). Everything else pins the edges that would let the guard
rot quietly: UNKNOWN is not ALLOW, 404 is ALLOW (no file is no rules), 403 on
the robots file is a refusal, one robots request per host however many
articles, and the agent string sent to publishers is the identifying one.
"""
import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gdelt_reach  # noqa: E402
import robots_gate  # noqa: E402
from robots_gate import ALLOW, DISALLOW, UNKNOWN, RobotsGate  # noqa: E402
from sources import gdelt  # noqa: E402

ARTICLE = "https://publisher.example/news/2026/09/02/big-layoffs"
ROBOTS = "https://publisher.example/robots.txt"


def fetch_returning(status, text=""):
    calls = []

    def fetch(robots_url, user_agent):
        calls.append((robots_url, user_agent))
        return status, text
    fetch.calls = calls
    return fetch


def fetch_raising(exc):
    def fetch(robots_url, user_agent):
        raise exc
    return fetch


class _NoArticleRequest:
    """A stand-in for requests.get that fails the test if the ARTICLE URL is
    ever requested. The robots read goes through the gate's own `fetch`, so
    any call here is a body fetch."""

    def __init__(self, testcase):
        self.tc = testcase
        self.calls = []

    def __call__(self, url, *a, **kw):
        self.calls.append((url, kw.get("headers", {})))
        self.tc.fail(f"article body was requested despite robots verdict: {url}")


class DisallowMeansNoRequest(unittest.TestCase):
    def test_disallow_all_for_us_is_not_fetched(self):
        gate = RobotsGate(fetch=fetch_returning(200, "User-agent: AiLayoffTracker\nDisallow: /\n"))
        guard = _NoArticleRequest(self)
        with mock.patch.object(gdelt.requests, "get", guard):
            with self.assertRaises(gdelt.RobotsRefused) as ctx:
                gdelt._fetch_article(ARTICLE, gate=gate)
        self.assertEqual(ctx.exception.state, DISALLOW)
        self.assertEqual(guard.calls, [])

    def test_blanket_disallow_is_not_fetched(self):
        gate = RobotsGate(fetch=fetch_returning(200, "User-agent: *\nDisallow: /\n"))
        with mock.patch.object(gdelt.requests, "get", _NoArticleRequest(self)):
            with self.assertRaises(gdelt.RobotsRefused):
                gdelt._fetch_article(ARTICLE, gate=gate)

    def test_path_disallow_is_honoured(self):
        gate = RobotsGate(fetch=fetch_returning(200, "User-agent: *\nDisallow: /news/\n"))
        state, note = gate.verdict(ARTICLE)
        self.assertEqual(state, DISALLOW)
        self.assertIn("path", note)
        # A sibling path the file does not name is allowed by the same file,
        # and costs no second robots request.
        state, _ = gate.verdict("https://publisher.example/about")
        self.assertEqual(state, ALLOW)
        self.assertEqual(gate.robots_requests, 1)

    def test_a_group_for_another_agent_does_not_bind_us(self):
        gate = RobotsGate(fetch=fetch_returning(
            200, "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"))
        self.assertEqual(gate.verdict(ARTICLE)[0], ALLOW)


class UnknownIsNotPermission(unittest.TestCase):
    def test_unreachable_robots_is_unknown_and_not_fetched(self):
        gate = RobotsGate(fetch=fetch_raising(TimeoutError("robots timed out")))
        with mock.patch.object(gdelt.requests, "get", _NoArticleRequest(self)):
            with self.assertRaises(gdelt.RobotsRefused) as ctx:
                gdelt._fetch_article(ARTICLE, gate=gate)
        self.assertEqual(ctx.exception.state, UNKNOWN)
        self.assertIn("not allowed", ctx.exception.note)

    def test_5xx_is_unknown(self):
        gate = RobotsGate(fetch=fetch_returning(503))
        state, note = gate.verdict(ARTICLE)
        self.assertEqual(state, UNKNOWN)
        self.assertIn("503", note)

    def test_oversize_robots_is_unknown(self):
        gate = RobotsGate(fetch=fetch_returning(-1))
        self.assertEqual(gate.verdict(ARTICLE)[0], UNKNOWN)

    def test_redirect_to_a_non_robots_page_is_unknown(self):
        # An apex host that answers /robots.txt with its HTML homepage has
        # not published rules; parsing a homepage as directives would read
        # as "allow everything". Not a file we read, so not permission.
        gate = RobotsGate(fetch=fetch_returning(-2))
        state, note = gate.verdict(ARTICLE)
        self.assertEqual(state, UNKNOWN)
        self.assertIn("not a robots file", note)

    def test_default_fetch_refuses_a_homepage_dressed_as_robots(self):
        resp = mock.Mock()
        resp.status_code = 200
        resp.encoding = "utf-8"
        resp.url = "https://publisher.example/"
        resp.headers = {"content-type": "text/html; charset=utf-8"}
        resp.raw.read = lambda n, decode_content=True: b"<html>"
        with mock.patch.object(robots_gate.requests, "get", return_value=resp):
            self.assertEqual(robots_gate._default_fetch(ROBOTS, robots_gate.PUBLISHER_UA), (-2, ""))
        resp.url = ROBOTS
        resp.headers = {"content-type": "text/plain"}
        resp.raw.read = lambda n, decode_content=True: b"User-agent: *\nDisallow: /x\n"
        with mock.patch.object(robots_gate.requests, "get", return_value=resp):
            status, text = robots_gate._default_fetch(ROBOTS, robots_gate.PUBLISHER_UA)
        self.assertEqual(status, 200)
        self.assertIn("Disallow: /x", text)

    def test_403_on_the_robots_file_is_a_refusal(self):
        # The ledger doctrine: a server that refuses our identifying agent is
        # refusing us, and a browser string to get past it would be spoofing.
        gate = RobotsGate(fetch=fetch_returning(403))
        state, note = gate.verdict(ARTICLE)
        self.assertEqual(state, DISALLOW)
        self.assertIn("refusal", note)
        self.assertIn("publisher.example", gate.refused_hosts)

    def test_no_robots_file_is_unrestricted(self):
        gate = RobotsGate(fetch=fetch_returning(404))
        state, note = gate.verdict(ARTICLE)
        self.assertEqual(state, ALLOW)
        self.assertIn("404", note)


class TheFetchIdentifiesItself(unittest.TestCase):
    def test_publisher_request_carries_the_identifying_agent(self):
        gate = RobotsGate(fetch=fetch_returning(404))
        seen = {}

        def fake_get(url, headers=None, timeout=None, **kw):
            seen["url"] = url
            seen["ua"] = (headers or {}).get("User-Agent")
            resp = mock.Mock()
            resp.text = "<html><body><p>Company announces layoffs of 120 staff.</p></body></html>"
            resp.raise_for_status = lambda: None
            return resp
        with mock.patch.object(gdelt.requests, "get", fake_get):
            text = gdelt._fetch_article(ARTICLE, gate=gate)
        self.assertEqual(seen["url"], ARTICLE)
        self.assertEqual(seen["ua"], robots_gate.PUBLISHER_UA)
        self.assertNotEqual(seen["ua"], gdelt.BROWSER_UA)
        self.assertIn("layoffs", text)

    def test_robots_read_uses_the_same_agent(self):
        fetch = fetch_returning(404)
        gate = RobotsGate(fetch=fetch)
        gate.verdict(ARTICLE)
        self.assertEqual(fetch.calls, [(ROBOTS, robots_gate.PUBLISHER_UA)])

    def test_publisher_agent_is_identifying_with_a_contact_url(self):
        self.assertTrue(robots_gate.PUBLISHER_UA.startswith("AiLayoffTracker/"))
        self.assertIn("+https://asktherecruiter.com", robots_gate.PUBLISHER_UA)
        self.assertNotIn("Mozilla", robots_gate.PUBLISHER_UA)

    def test_own_host_agent_is_untouched(self):
        # ModSecurity on the WP host blocks python-requests; the string sent
        # there is set at each call site and is not read from the gate.
        src = open(os.path.join(os.path.dirname(__file__), "..", "cron.py")).read()
        self.assertIn('"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"', src)

    def test_robots_matching_binds_on_our_first_token(self):
        # A publisher writes `User-agent: AiLayoffTracker`; the full string we
        # send has a version and a URL after it. It must still apply.
        gate = RobotsGate(fetch=fetch_returning(
            200, "User-agent: ailayofftracker\nDisallow: /\n"))
        self.assertEqual(gate.verdict(ARTICLE)[0], DISALLOW)


class OneRobotsRequestPerHost(unittest.TestCase):
    def test_many_articles_one_host_one_request(self):
        fetch = fetch_returning(200, "User-agent: *\nAllow: /\n")
        gate = RobotsGate(fetch=fetch)
        for i in range(50):
            gate.verdict(f"https://publisher.example/story/{i}")
        self.assertEqual(gate.robots_requests, 1)

    def test_a_refusing_host_is_asked_once_then_never(self):
        fetch = fetch_returning(403)
        gate = RobotsGate(fetch=fetch)
        for i in range(20):
            self.assertEqual(gate.verdict(f"https://publisher.example/story/{i}")[0], DISALLOW)
        self.assertEqual(gate.robots_requests, 1)

    def test_unknown_is_cached_too_so_an_outage_is_not_amplified(self):
        gate = RobotsGate(fetch=fetch_raising(ConnectionError("down")))
        for i in range(20):
            self.assertEqual(gate.verdict(f"https://publisher.example/story/{i}")[0], UNKNOWN)
        self.assertEqual(gate.robots_requests, 1)

    def test_concurrent_workers_share_one_in_flight_read(self):
        started = threading.Event()
        release = threading.Event()
        count = [0]
        lock = threading.Lock()

        def slow_fetch(robots_url, ua):
            with lock:
                count[0] += 1
            started.set()
            release.wait(5)
            return 404, ""
        gate = RobotsGate(fetch=slow_fetch)
        results = []
        threads = [threading.Thread(target=lambda i=i: results.append(
            gate.verdict(f"https://publisher.example/story/{i}"))) for i in range(6)]
        for t in threads:
            t.start()
        started.wait(5)
        release.set()
        for t in threads:
            t.join(5)
        self.assertEqual(count[0], 1)
        self.assertEqual({r[0] for r in results}, {ALLOW})

    def test_ttl_expiry_asks_again(self):
        now = [0.0]
        fetch = fetch_returning(404)
        gate = RobotsGate(fetch=fetch, ttl_seconds=100, clock=lambda: now[0])
        gate.verdict(ARTICLE)
        now[0] = 50
        gate.verdict(ARTICLE)
        self.assertEqual(gate.robots_requests, 1)
        now[0] = 101
        gate.verdict(ARTICLE)
        self.assertEqual(gate.robots_requests, 2)

    def test_crawl_delay_is_honoured_and_capped(self):
        slept = []
        now = [100.0]
        gate = RobotsGate(fetch=fetch_returning(200, "User-agent: *\nCrawl-delay: 600\n"),
                          clock=lambda: now[0], sleep=slept.append)
        gate.verdict(ARTICLE)
        gate.pace(ARTICLE)                   # first hit: no wait
        gate.pace("https://publisher.example/other")
        self.assertEqual(slept, [robots_gate.MAX_CRAWL_DELAY])


class ARefusalIsCountedNotSwallowed(unittest.TestCase):
    def test_reach_vocabulary_has_both_robots_outcomes(self):
        self.assertIn("robots_disallowed", gdelt_reach.REASONS)
        self.assertIn("robots_unknown", gdelt_reach.REASONS)

    def _run_fetch_trusted(self, gate):
        gdelt_reach.reset()
        articles = [{"url": ARTICLE, "domain": "publisher.example", "title": "t", "seendate": "20260902T000000Z"}]
        with mock.patch.object(gdelt, "TRUSTED_DOMAINS", {"publisher.example"}), \
             mock.patch.object(gdelt, "ROBOTS", gate), \
             mock.patch.object(gdelt.requests, "get", _NoArticleRequest(self)), \
             mock.patch.object(gdelt.time, "sleep", lambda s: None):
            return gdelt._fetch_trusted(articles)

    def test_disallowed_row_is_kept_headline_only_under_its_own_reason(self):
        gate = RobotsGate(fetch=fetch_returning(200, "User-agent: *\nDisallow: /\n"))
        results = self._run_fetch_trusted(gate)
        # The row survives on GDELT's own metadata; the body was never asked for.
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["raw_text"], "t")
        self.assertEqual(results[0]["source_url"], ARTICLE)
        by_reason = gdelt_reach.current().by_reason()
        self.assertEqual(by_reason.get("robots_disallowed"), 1)
        self.assertFalse(by_reason.get("fetch_failed"))
        self.assertFalse(by_reason.get("kept"))
        totals = gdelt_reach.current().totals()
        self.assertEqual(totals["headline_only"], 1)
        self.assertEqual(totals["dropped"], 0)
        detail = gdelt_reach.current().health_detail()
        self.assertIn("robots_disallowed=1", detail)
        self.assertIn("headline_only=1", detail)

    def test_unknown_row_is_kept_headline_only_under_unknown(self):
        gate = RobotsGate(fetch=fetch_raising(OSError("no route")))
        results = self._run_fetch_trusted(gate)
        self.assertEqual(len(results), 1)
        by_reason = gdelt_reach.current().by_reason()
        self.assertEqual(by_reason.get("robots_unknown"), 1)
        self.assertFalse(by_reason.get("robots_disallowed"))

    def test_refused_row_with_no_title_is_nothing_to_hand_on(self):
        gate = RobotsGate(fetch=fetch_returning(403))
        gdelt_reach.reset()
        articles = [{"url": ARTICLE, "domain": "publisher.example", "title": "", "seendate": ""}]
        with mock.patch.object(gdelt, "TRUSTED_DOMAINS", {"publisher.example"}), \
             mock.patch.object(gdelt, "ROBOTS", gate), \
             mock.patch.object(gdelt.requests, "get", _NoArticleRequest(self)), \
             mock.patch.object(gdelt.time, "sleep", lambda s: None):
            self.assertEqual(gdelt._fetch_trusted(articles), [])
        self.assertEqual(gdelt_reach.current().by_reason().get("robots_disallowed"), 1)

    def test_health_detail_stays_nameless(self):
        gate = RobotsGate(fetch=fetch_returning(403))
        self._run_fetch_trusted(gate)
        gdelt_reach.assert_nameless(gdelt_reach.current().summary())
        self.assertNotIn("publisher.example", gdelt_reach.current().health_detail())
        # The host IS named in the run-log lines, for the owner, and flagged
        # as a ledger candidate rather than added anywhere.
        lines = "\n".join(gate.report_lines())
        self.assertIn("publisher.example", lines)
        self.assertIn("REFUSAL_LEDGER", lines)


if __name__ == "__main__":
    unittest.main()
