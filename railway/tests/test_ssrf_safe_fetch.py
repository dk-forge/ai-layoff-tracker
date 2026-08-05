"""Blind SSRF from the ingest runner, closed at the fetch.

WHY THIS FILE EXISTS. Two call sites fetched a URL chosen by somebody outside
this repository:

  * `process_tips._fetch_text` fetched the link on a PUBLIC tip form, and it
    did so BEFORE `_domain_trusted` was consulted (process_tips.py, the fetch
    at the top of the tip loop; the trust gate ~25 lines later). The gate is a
    publish gate. Nothing gated the fetch.
  * `enrich_context.fetch_text` fetched whatever `source_url` a stored row
    carried, guarded by one `startswith(("http://", "https://"))` that saw only
    hop zero.

Both used plain `requests.get`, which follows redirects anywhere and never
looks at where it landed. That runner holds WP_API_KEY and OPENROUTER_API_KEY.
So "here is a link to my layoff story" was also "please read
http://169.254.169.254/latest/meta-data/ for me".

Every test here fails on the pre-safe_fetch code. The one that matters most is
`test_a_public_host_redirecting_to_the_metadata_service_is_refused`: a
first-hop-only check passes that URL, because hop zero is a real public
website.
"""
import ipaddress
import os
import pathlib
import subprocess
import sys
import unittest

RAILWAY = pathlib.Path(__file__).resolve().parents[1]
ROOT = RAILWAY.parent
sys.path.insert(0, str(RAILWAY))

import requests  # noqa: E402

import safe_fetch  # noqa: E402
from safe_fetch import BlockedURL, safe_get, validate_url  # noqa: E402


# --- Test doubles -----------------------------------------------------------
#
# No network and no monkeypatching of requests itself: a fake session is passed
# in, and DNS is stubbed per-test. A test that reached the network would be a
# test that passes or fails on somebody else's uptime.

class FakeRaw:
    def __init__(self, body):
        self._body = body

    def read(self, n, decode_content=True):
        return self._body[:n]


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b""):
        self.status_code = status
        self.headers = headers or {}
        self.raw = FakeRaw(body)
        self.content = body
        self.closed = False

    def close(self):
        self.closed = True


class FakeSession:
    """Records every URL it was ASKED to fetch. That list is the evidence."""

    def __init__(self, responses):
        self.responses = dict(responses)
        self.requested = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        assert kwargs.get("allow_redirects") is False, (
            "safe_get must follow redirects by hand so it can revalidate each "
            "hop; allow_redirects=True hands that decision to requests")
        assert kwargs.get("stream") is True, "the body must not be buffered whole"
        assert kwargs.get("timeout"), "every hop needs a timeout"
        return self.responses[url]


def stub_dns(testcase, mapping):
    """Point hostnames at addresses of our choosing for one test."""
    real = safe_fetch.socket.getaddrinfo

    def fake(host, *args, **kwargs):
        if host not in mapping:
            raise safe_fetch.socket.gaierror(f"unknown host {host}")
        out = []
        for addr in mapping[host]:
            fam = (safe_fetch.socket.AF_INET6 if ":" in addr
                   else safe_fetch.socket.AF_INET)
            out.append((fam, safe_fetch.socket.SOCK_STREAM, 6, "", (addr, 0)))
        return out

    safe_fetch.socket.getaddrinfo = fake
    testcase.addCleanup(lambda: setattr(safe_fetch.socket, "getaddrinfo", real))


# --- The address rule -------------------------------------------------------

class BlockedRanges(unittest.TestCase):
    """Every range that reaches something the runner should not read."""

    def test_the_ranges_that_matter_are_all_refused(self):
        for literal, what in [
            ("169.254.169.254", "the cloud metadata service"),
            ("169.254.170.2", "the ECS task metadata endpoint"),
            ("127.0.0.1", "loopback"),
            ("127.1.2.3", "loopback, spelled unusually"),
            ("0.0.0.0", "the unspecified address"),
            ("10.1.2.3", "RFC1918"),
            ("172.16.5.5", "RFC1918"),
            ("192.168.1.1", "RFC1918"),
            ("100.64.0.1", "CGNAT, which a hand-written denylist forgets"),
            ("::1", "IPv6 loopback"),
            ("fd00::1", "IPv6 unique-local"),
            ("fe80::1", "IPv6 link-local"),
            ("::ffff:169.254.169.254", "the metadata service wearing an IPv6 hat"),
        ]:
            with self.subTest(literal=literal, what=what):
                self.assertFalse(
                    safe_fetch._is_public(ipaddress.ip_address(literal)),
                    f"{literal} ({what}) must never be fetchable")

    def test_a_real_public_address_is_still_fetchable(self):
        """A guard that blocks everything is not a guard, it is an outage."""
        for literal in ("93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"):
            with self.subTest(literal=literal):
                self.assertTrue(safe_fetch._is_public(ipaddress.ip_address(literal)))


class SchemeAndHost(unittest.TestCase):
    def test_only_http_and_https_reach_a_socket(self):
        for url in ("file:///etc/passwd", "gopher://x/1", "ftp://h/f",
                    "data:text/html,x", "jar:http://h/!/", "//h/path", "x"):
            with self.subTest(url=url):
                with self.assertRaises(BlockedURL):
                    validate_url(url)

    def test_a_bare_private_literal_is_refused(self):
        with self.assertRaises(BlockedURL):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_a_hostname_that_resolves_private_is_refused(self):
        """The interesting case: the URL looks like an ordinary website."""
        stub_dns(self, {"internal.example.com": ["10.0.0.7"]})
        with self.assertRaises(BlockedURL):
            validate_url("https://internal.example.com/report")

    def test_a_host_with_one_public_and_one_private_answer_is_refused(self):
        """Which record requests connects to is not ours to choose, so a split
        answer is refused rather than gambled on."""
        stub_dns(self, {"split.example.com": ["93.184.216.34", "127.0.0.1"]})
        with self.assertRaises(BlockedURL):
            validate_url("https://split.example.com/")


# --- The redirect rule, which is the whole point ----------------------------

class RedirectsAreRevalidated(unittest.TestCase):
    def test_a_public_host_redirecting_to_the_metadata_service_is_refused(self):
        """THE case the old code got wrong.

        `https://news.example.com/story` is a real, public, allowlist-clean
        host. Hop zero passes every check anyone would write. It answers 302
        Location: http://169.254.169.254/latest/meta-data/iam/security-
        credentials/ and the old plain `requests.get` followed it, read the
        body and handed it to the extractor and to the model.
        """
        stub_dns(self, {"news.example.com": ["93.184.216.34"]})
        session = FakeSession({
            "https://news.example.com/story": FakeResponse(
                302,
                {"Location": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"}),
        })
        with self.assertRaises(BlockedURL) as caught:
            safe_get("https://news.example.com/story", session=session)
        self.assertIn("169.254.169.254", str(caught.exception))
        self.assertEqual(session.requested, ["https://news.example.com/story"],
                         "the metadata service must never have been requested")

    def test_the_second_hop_is_checked_too_not_only_the_first(self):
        """Two public hops then a private one. A guard that revalidates only
        the FIRST redirect passes this."""
        stub_dns(self, {"a.example.com": ["93.184.216.34"],
                        "b.example.com": ["93.184.216.35"]})
        session = FakeSession({
            "https://a.example.com/1": FakeResponse(302, {"Location": "https://b.example.com/2"}),
            "https://b.example.com/2": FakeResponse(302, {"Location": "http://127.0.0.1:8080/admin"}),
        })
        with self.assertRaises(BlockedURL):
            safe_get("https://a.example.com/1", session=session)
        self.assertNotIn("http://127.0.0.1:8080/admin", session.requested)

    def test_a_relative_redirect_is_resolved_against_the_hop_it_came_from(self):
        stub_dns(self, {"a.example.com": ["93.184.216.34"]})
        session = FakeSession({
            "https://a.example.com/x/1": FakeResponse(302, {"Location": "/y/2"}),
            "https://a.example.com/y/2": FakeResponse(200, {}, b"<p>ok</p>"),
        })
        status, body, final = safe_get("https://a.example.com/x/1", session=session)
        self.assertEqual((status, final), (200, "https://a.example.com/y/2"))
        self.assertEqual(body, b"<p>ok</p>")

    def test_a_redirect_loop_ends_rather_than_spinning(self):
        stub_dns(self, {"a.example.com": ["93.184.216.34"]})
        session = FakeSession({
            "https://a.example.com/": FakeResponse(302, {"Location": "https://a.example.com/"}),
        })
        with self.assertRaises(BlockedURL):
            safe_get("https://a.example.com/", session=session)
        self.assertLessEqual(len(session.requested), safe_fetch.MAX_REDIRECTS + 1)


class BodyIsBounded(unittest.TestCase):
    def test_a_hostile_body_is_truncated_not_swallowed(self):
        stub_dns(self, {"a.example.com": ["93.184.216.34"]})
        session = FakeSession({
            "https://a.example.com/": FakeResponse(200, {}, b"A" * 5_000_000),
        })
        _status, body, _final = safe_get("https://a.example.com/", session=session,
                                         max_bytes=1000)
        self.assertEqual(len(body), 1000)

    def test_the_response_is_closed_even_when_capped(self):
        stub_dns(self, {"a.example.com": ["93.184.216.34"]})
        response = FakeResponse(200, {}, b"A" * 100)
        session = FakeSession({"https://a.example.com/": response})
        safe_get("https://a.example.com/", session=session, max_bytes=10)
        self.assertTrue(response.closed, "a streamed response left open leaks a "
                                         "connection on every row of a batch")


class AMidBodyFailureIsARequestsException(unittest.TestCase):
    """A host that returns 200 and then goes silent mid-body must surface as
    `requests.RequestException`, the exception class `safe_get` documents and
    every caller catches — NOT as urllib3's own `ReadTimeoutError`, which no
    caller catches. The sibling tracker took exactly that bullet on
    2026-08-05: one dead publisher's mid-body timeout escaped every per-host
    guard and killed a 19-minute run. Both tests fail on the pre-fix tree.
    """

    class DyingRaw:
        def read(self, n, decode_content=True):
            import urllib3
            raise urllib3.exceptions.ReadTimeoutError(
                None, "host.example", "Read timed out.")

    def test_a_read_timeout_mid_body_is_translated(self):
        stub_dns(self, {"host.example": ["93.184.216.34"]})
        response = FakeResponse(200, {}, b"")
        response.raw = self.DyingRaw()
        session = FakeSession({"https://host.example/x": response})
        with self.assertRaises(requests.RequestException):
            safe_get("https://host.example/x", session=session)
        self.assertTrue(response.closed, "the dead response must still close")

    def test_safe_get_with_retry_absorbs_it_per_its_contract(self):
        """`safe_get_with_retry` promises None when every attempt failed
        transiently; a mid-body timeout is exactly such a failure."""
        stub_dns(self, {"host.example": ["93.184.216.34"]})
        response = FakeResponse(200, {}, b"")
        response.raw = self.DyingRaw()
        session = FakeSession({"https://host.example/x": response})
        out = safe_fetch.safe_get_with_retry(
            "https://host.example/x", session=session, attempts=2,
            sleep=lambda seconds: None)
        self.assertIsNone(out, "a dead host is an outcome, not an exception")


# --- The two call sites actually route through it ---------------------------

class CallSitesUseTheGate(unittest.TestCase):
    """Source-level, because the alternative is importing two modules that want
    OpenRouter and BigQuery at import time. What is asserted is the property
    that regressed: a raw fetch on an untrusted URL."""

    def test_process_tips_fetches_tip_links_through_safe_fetch(self):
        src = (RAILWAY / "process_tips.py").read_text()
        body = src[src.index("def _fetch_text"):]
        body = body[:body.index("\ndef ", 1)]
        self.assertIn("safe_get_with_retry", body)
        self.assertNotRegex(body, r"(?<!safe_)get_with_retry\(url",
                            "the tip link must not go through the plain retry "
                            "helper, which follows redirects anywhere")

    def test_enrich_context_fetches_source_urls_through_safe_fetch(self):
        src = (RAILWAY / "enrich_context.py").read_text()
        body = src[src.index("def fetch_text"):]
        body = body[:body.index("\ndef ", 1)]
        self.assertIn("safe_get", body)
        self.assertNotIn("requests.get(url", body,
                         "a stored source_url is not a trusted URL")


# --- The intake side --------------------------------------------------------

PHP_SHIM = r"""<?php
function wp_parse_url($url) { return parse_url($url); }
%s
$cases = json_decode(file_get_contents('php://stdin'), true);
$out = array();
foreach ($cases as $url) { $out[$url] = alt_tip_url_allowed($url) ? 1 : 0; }
echo json_encode($out);
"""


class TipIntakeRefusesUnfetchableLinks(unittest.TestCase):
    """alt_tips_append is what tells the runner what to go and fetch. Run for
    real against the plugin's own source, not asserted as a substring."""

    def setUp(self):
        db = ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "includes" / "db.php"
        src = db.read_text()
        self.assertIn("function alt_tip_url_allowed", src,
                      "the intake gate is missing from db.php")
        fn = src[src.index("function alt_tip_url_allowed"):]
        fn = fn[:fn.index("\n}\n") + 3]
        self.fn = fn
        if not _php():
            self.skipTest("php not installed")

    def _allowed(self, urls):
        import json
        proc = subprocess.run(
            [_php(), "-r", (PHP_SHIM % self.fn).replace("<?php\n", "", 1)],
            input=json.dumps(urls), capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_the_addresses_a_tip_may_not_point_at(self):
        refused = ["http://169.254.169.254/latest/meta-data/",
                   "http://127.0.0.1:8080/wp-admin/",
                   "http://[::1]/", "http://10.0.0.5/", "http://192.168.0.1/",
                   "http://localhost:3000/", "file:///etc/passwd",
                   "ftp://host/f", "gopher://host/1", "javascript:alert(1)"]
        got = self._allowed(refused)
        for url in refused:
            with self.subTest(url=url):
                self.assertEqual(got[url], 0, f"{url} must not enter the tip queue")

    def test_an_ordinary_tip_link_still_gets_in(self):
        got = self._allowed(["https://www.reuters.com/business/story-2026",
                             "http://news.example.co.uk/a?b=c"])
        self.assertEqual(list(got.values()), [1, 1],
                         "the guard must not cost us real tips")


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    from shutil import which
    return which("php")


if __name__ == "__main__":
    unittest.main()
