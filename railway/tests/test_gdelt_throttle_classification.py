"""GDELT refuses at HTTP 200, and we read that refusal as a broken parser.

THE DEFECT THIS PINS (measured 2026-08-29, production query shape). The DOC 2.0
API does not reliably use status codes. Against the live endpoint, at >=5s
spacing from one address, the non-JSON responses were:

    HTTP 200  "Your query was too short or too long."
    HTTP 200  "Please limit requests to one every 5 seconds."
    HTTP 429  "Please limit requests to one every 5 seconds."

`resp.raise_for_status()` passes on a 200, so `resp.json()` raised
`JSONDecodeError`, the generic `except` recorded "Expecting value: line 1
column 1 (char 0)", and `saw_rate_limit` stayed False. The behaviour was
survivable; the INFORMATION was wrong, in three places that each exist to tell
throttled from broken:

  1. `gdelt_reach` published `rate_limited=0` on a throttled run.
  2. The RuntimeError for a fully-abandoned broad window quoted a JSON parser.
  3. `gdelt_backfill._is_upstream_throttle` greps for "429"/"rate limit"/
     "timeout"; a JSONDecodeError matches none, so an upstream throttle RAISED
     — a red run and a breakage email no human can act on, which is exactly
     what that function's own comment says it prevents.

AND THIS FIX MUST STAY FREE. CLAUDE.md is explicit that a rate limit is not
answered with more retries or a longer backoff. `test_costs_nothing_extra`
below pins that: the same number of requests and the same total sleep as
before, byte for byte. If a later change buys quiet with patience, that test
fails first.

Hermetic: `requests.get` and `time.sleep` are injected. No test touches the
network.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gdelt_backfill  # noqa: E402
import gdelt_reach  # noqa: E402
from sources import gdelt  # noqa: E402

W_START = datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc)
W_END = W_START + timedelta(hours=36)

THROTTLE_BODY = "Please limit requests to one every 5 seconds."
TOO_LONG_BODY = "Your query was too short or too long."


class FakeResponse:
    """Only the surface `_query_window` touches."""

    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        import json as _json
        return _json.loads(self.text)


def _json_body(n):
    arts = [{"url": f"https://reuters.com/a{i}", "domain": "reuters.com",
             "title": "layoffs", "seendate": "20260820T120000Z"} for i in range(n)]
    import json as _json
    return _json.dumps({"articles": arts})


class _Harness(unittest.TestCase):
    def setUp(self):
        gdelt_reach.reset()
        self.sleeps = []
        self.requests = 0

    def run_window(self, bodies):
        """Serve `bodies` (a list of FakeResponse) in order, last one repeating."""
        def fake_get(url, params=None, headers=None, timeout=None):
            resp = bodies[min(self.requests, len(bodies) - 1)]
            self.requests += 1
            return resp

        with patch.object(gdelt.requests, "get", fake_get), \
             patch.object(gdelt.time, "sleep", self.sleeps.append):
            return gdelt._query_window(gdelt.QUERY, W_START, W_END, 250, "broad")


class ThrottleAtHttp200(_Harness):

    def test_throttle_body_is_recorded_as_a_rate_limit(self):
        arts, saw_rl, err = self.run_window([FakeResponse(200, THROTTLE_BODY)])
        self.assertIsNone(arts, "a refused window is abandoned, never an empty result")
        self.assertTrue(saw_rl,
                        "GDELT said 'limit requests' at HTTP 200; that is a rate "
                        "limit and must be reported as one")
        self.assertIn("limit requests", err.lower())
        self.assertNotIn("expecting value", (err or "").lower(),
                         "the diagnosis must be the server's sentence, not a JSON parser's")

    def test_reach_telemetry_reports_the_throttle(self):
        """gdelt_reach exists to tell throttled from broken. It was blind here."""
        self.run_window([FakeResponse(200, THROTTLE_BODY)])
        totals = gdelt_reach.current().totals()
        self.assertEqual(totals["abandoned"], 1)
        self.assertEqual(totals["rate_limited"], 1,
                         "a throttled run published rate_limited=0")

    def test_backfill_treats_it_as_upstream_not_as_our_breakage(self):
        """The two halves of one contract: the message we write, the matcher
        that reads it. A throttle must not become a red run."""
        _arts, _rl, err = self.run_window([FakeResponse(200, THROTTLE_BODY)])
        self.assertTrue(
            gdelt_backfill._is_upstream_throttle(RuntimeError(err)),
            "an upstream throttle raised as a collector breakage")


class NonThrottleRefusalStaysDistinct(_Harness):
    """'too short or too long' is NOT a rate limit, and conflating the two is
    the failure mode this whole investigation was about."""

    def test_query_refusal_is_named_but_not_called_a_rate_limit(self):
        arts, saw_rl, err = self.run_window([FakeResponse(200, TOO_LONG_BODY)])
        self.assertIsNone(arts)
        self.assertFalse(saw_rl, "a non-throttle refusal must not inflate rate_limited")
        self.assertIn("too short or too long", err.lower())
        self.assertEqual(gdelt_reach.current().totals()["rate_limited"], 0)


class RecoveryAndCost(_Harness):

    def test_a_refusal_followed_by_an_answer_still_succeeds(self):
        """The refusal is intermittent — the identical query was rejected then
        accepted minutes apart. Retrying remains correct."""
        arts, saw_rl, _err = self.run_window(
            [FakeResponse(200, THROTTLE_BODY), FakeResponse(200, _json_body(3))])
        self.assertEqual(len(arts), 3)
        self.assertTrue(saw_rl, "a throttle seen on the way to success is still a throttle")
        self.assertEqual(gdelt_reach.current().totals()["abandoned"], 0)

    def test_costs_nothing_extra(self):
        """No extra request and no extra second. Buying quiet with patience is
        explicitly not the answer to a shared rate limit (CLAUDE.md)."""
        self.run_window([FakeResponse(200, THROTTLE_BODY)])
        self.assertEqual(self.requests, gdelt.QUERY_ATTEMPTS,
                         "the retry count must be unchanged")
        self.assertEqual(self.sleeps, [gdelt.REQUEST_DELAY] * gdelt.QUERY_ATTEMPTS,
                         "the sleep schedule must be unchanged — no backoff was "
                         "added to answer a rate limit")


class BodyClassifier(unittest.TestCase):
    """The classifier itself, at its edges."""

    def test_json_bodies_are_not_signals(self):
        self.assertIsNone(gdelt._upstream_text_signal('{"articles": []}'))
        self.assertIsNone(gdelt._upstream_text_signal('  [1,2] '))
        self.assertIsNone(gdelt._upstream_text_signal(""))
        self.assertIsNone(gdelt._upstream_text_signal(None))

    def test_throttle_wordings(self):
        for body in ("Please limit requests to one every 5 seconds.",
                     "please limit requests to one every 10 sec",
                     "Rate limit exceeded", "Too Many Requests"):
            kind, msg = gdelt._upstream_text_signal(body)
            self.assertEqual(kind, "throttle", body)
            # Verbatim: the server's sentence is the diagnosis a human reads on
            # the health page. It is not rewritten into words a matcher greps.
            self.assertEqual(msg, body)
            self.assertTrue(gdelt_backfill._is_upstream_throttle(RuntimeError(body)),
                            f"the two halves disagree about: {body}")

    def test_the_backfill_matcher_uses_the_collectors_definition(self):
        """One definition, not two lists that drift. If someone re-copies the
        wordings into gdelt_backfill, this is what notices."""
        self.assertIs(gdelt_backfill._THROTTLE_BODY_RX, gdelt._THROTTLE_BODY_RX)

    def test_other_refusals_are_upstream(self):
        kind, msg = gdelt._upstream_text_signal(TOO_LONG_BODY)
        self.assertEqual(kind, "upstream")
        self.assertEqual(msg, TOO_LONG_BODY)

    def test_a_long_body_is_truncated_for_a_240_char_health_detail(self):
        kind, msg = gdelt._upstream_text_signal("x" * 5000)
        self.assertEqual(kind, "upstream")
        self.assertLessEqual(len(msg), gdelt._MAX_SIGNAL_BODY)


if __name__ == "__main__":
    unittest.main()
