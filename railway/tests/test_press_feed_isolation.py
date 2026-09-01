"""One publisher's format change must not end the whole press-release run.

2026-09-01: `press_releases` reported DEGRADED with the note "syntax error:
line 1, column 0" and no feed named. Five reviewed feeds were configured;
three answered with valid XML. Intel's `newsroom.intel.com/feed` had begun
redirecting to an HTML newsroom landing page, which is an HTTP 200 with a body
that is not a feed.

`pull_press_releases` documents per-feed isolation, and it had it for the
FETCH: `requests.get` and `raise_for_status` sat inside a try/except that
appended to `failed` and continued. But the PARSE -- `_items(payload)`, which
calls `ET.fromstring` -- sat below that `except`. So a body that fetched fine
and parsed badly raised `ET.ParseError` straight out of the function, past
every remaining feed. One dead publisher cost the other four.

The second half is the health note. The collector's branch in `cron.py`
reported "ok, N reviewed feed(s) configured" from `reviewed_feed_count()`,
which counts what is CONFIGURED. It never asked how many of them answered, so
a feed could rot for months behind an "ok". Configured is not collected.

Both properties are pinned here. No network: the feeds are scripted.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sources"))

import tests._requests_stub  # noqa: F401  (installs the shared requests stub)

from sources import press_releases


GOOD_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Example Corp to cut 400 jobs in restructuring</title>
    <link>https://ir.example.com/2026/layoffs</link>
    <description>The company said it will lay off 400 employees.</description>
    <pubDate>Mon, 01 Sep 2026 09:00:00 +0000</pubDate>
  </item>
</channel></rss>"""

# An HTTP 200 whose body is a newsroom landing page, which is exactly what a
# moved feed URL serves. `raise_for_status()` is happy; `ET.fromstring` is not.
HTML_NOT_A_FEED = "<!doctype html>\n<html><head><title>Newsroom</title></head>"


class _Response:
    def __init__(self, body, status=200):
        self.content = body.encode("utf-8")
        self.text = body
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code} Client Error")


def _feed(name, url, host):
    return {
        "name": name,
        "url": url,
        "owner_domain": host,
        "terms_url": f"https://{host}/terms",
        "reviewed_at": "2026-01-01",
        "country": "United States",
    }


FEEDS = [
    _feed("Good One", "https://ir.good-one.example/rss", "good-one.example"),
    _feed("Moved Feed", "https://newsroom.moved.example/feed", "moved.example"),
    _feed("Good Two", "https://ir.good-two.example/rss", "good-two.example"),
]

BODIES = {
    "https://ir.good-one.example/rss": _Response(GOOD_FEED),
    "https://newsroom.moved.example/feed": _Response(HTML_NOT_A_FEED),
    "https://ir.good-two.example/rss": _Response(GOOD_FEED),
}


def _fake_get(url, **_kwargs):
    return BODIES[url]


class OneBadFeedDoesNotEndTheRun(unittest.TestCase):
    def setUp(self):
        self._feeds = mock.patch.object(press_releases, "_feeds",
                                        return_value=list(FEEDS))
        self._get = mock.patch.object(press_releases.requests, "get",
                                      side_effect=_fake_get)
        self._terms = mock.patch.object(press_releases, "discovery_terms",
                                        return_value=["lay off", "cut"])
        self._feeds.start()
        self._get.start()
        self._terms.start()
        self.addCleanup(self._feeds.stop)
        self.addCleanup(self._get.stop)
        self.addCleanup(self._terms.stop)

    def test_a_body_that_is_not_xml_is_that_feed_s_failure_only(self):
        """The two healthy feeds' items still come back.

        MUTATION: move `list(_items(...))` back below the `except` in
        pull_press_releases and this raises ET.ParseError instead.
        """
        rows = press_releases.pull_press_releases(days_back=3650)
        names = sorted(r["source_name"] for r in rows)
        self.assertEqual(names, ["Good One", "Good Two"],
                         "a feed that answers 200 with HTML must cost only "
                         "itself, never the feeds after it in the list")

    def test_the_broken_feed_is_named_for_the_health_note(self):
        """A failure nobody can read is a failure nobody will fix."""
        press_releases.pull_press_releases(days_back=3650)
        failures = press_releases.pull_press_releases.last_failures
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("Moved Feed", failures[0])
        self.assertIn("ParseError", failures[0])

    def test_last_failures_is_readable_before_any_run(self):
        """cron.py reads this attribute; it must never be an AttributeError."""
        self.assertIsInstance(
            getattr(press_releases.pull_press_releases, "last_failures", None),
            list)

    def test_every_feed_failing_is_still_loud(self):
        """Isolation must not have turned a total outage into a quiet zero."""
        with mock.patch.object(
                press_releases.requests, "get",
                side_effect=lambda url, **_k: _Response(HTML_NOT_A_FEED)):
            with self.assertRaises(RuntimeError):
                press_releases.pull_press_releases(days_back=3650)


class ConfiguredIsNotCollected(unittest.TestCase):
    """cron.py must report a partly-dead registry as degraded, not ok.

    Read as source rather than executed: importing cron.py pulls in the whole
    ingest path (paid clients, the spend meter, every collector module), which
    is not something a unit test should stand up to check one branch.
    """

    SOURCE = (Path(__file__).resolve().parents[1] / "cron.py").read_text(
        encoding="utf-8")

    def test_the_branch_reads_the_failures_before_it_says_ok(self):
        self.assertIn("last_failures", self.SOURCE,
                      "cron.py must ask the collector which reviewed feeds "
                      "actually answered before reporting health")

    def test_a_partly_dead_registry_reports_degraded(self):
        block = self.SOURCE.split('if source == "press_releases":', 1)[1]
        block = block.split("elif source in", 1)[0]
        degraded_at = block.find('"degraded"')
        ok_at = block.find('"ok"')
        self.assertNotEqual(degraded_at, -1,
                            "the press_releases branch lost its degraded path")
        self.assertLess(
            degraded_at, ok_at,
            "the broken-feed check must be decided BEFORE the ok branch; "
            "an ok that is reached first can never be corrected")


if __name__ == "__main__":
    unittest.main()
