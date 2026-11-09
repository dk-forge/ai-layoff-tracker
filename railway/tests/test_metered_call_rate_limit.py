"""A 429 from the model host is waited out, not hammered (AI-LAYOFF-TRACKER-5).

On 2026-11-05/06 one cron run logged 1,022 upstream 429s for
google/gemini-2.5-flash-lite: `metered_call` retried a throttled call at once
(no backoff, `Retry-After` ignored) and the next item fired straight after,
so a shared-pool throttle turned into a burst. These tests pin:

  * a 429 is retried after a backoff, honouring a capped `Retry-After`;
  * a timeout / connection error is retried after a backoff too;
  * after a run of consecutive 429s the breaker opens and further calls are
    refused WITHOUT a request until the cooldown has passed;
  * a non-transient error is still not slept on.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())

import spend  # noqa: E402


class RateLimitError(Exception):
    def __init__(self, retry_after=None):
        super().__init__("Error code: 429 - rate-limited upstream")
        self.status_code = 429
        headers = {} if retry_after is None else {"retry-after": str(retry_after)}
        self.response = SimpleNamespace(headers=headers)


class APITimeoutError(Exception):
    pass


class _Clock:
    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class MeteredCallRateLimit(unittest.TestCase):
    def setUp(self):
        self.clock = _Clock()
        self._saved = (spend._sleep, spend._now, spend.paid_reads_enabled,
                       spend.record_usage)
        spend._sleep, spend._now = self.clock.sleep, self.clock.now
        spend.paid_reads_enabled = lambda: True
        spend.record_usage = lambda *a, **k: None
        spend.reset_rate_limit_state()

    def tearDown(self):
        (spend._sleep, spend._now, spend.paid_reads_enabled,
         spend.record_usage) = self._saved
        spend.reset_rate_limit_state()

    def _flaky(self, errors):
        calls = []

        def make():
            calls.append(1)
            if errors:
                raise errors.pop(0)
            return SimpleNamespace(usage=None)
        return make, calls

    def test_429_honours_retry_after(self):
        make, calls = self._flaky([RateLimitError(retry_after=7)])
        spend.metered_call("m", make, attempts=2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.clock.sleeps, [7.0])

    def test_retry_after_is_capped(self):
        make, _ = self._flaky([RateLimitError(retry_after=3600)])
        spend.metered_call("m", make, attempts=2)
        self.assertEqual(self.clock.sleeps, [spend.RATE_LIMIT_MAX_WAIT_SECONDS])

    def test_429_without_header_backs_off(self):
        make, _ = self._flaky([RateLimitError()])
        spend.metered_call("m", make, attempts=2)
        self.assertEqual(len(self.clock.sleeps), 1)
        self.assertGreaterEqual(self.clock.sleeps[0], spend.RATE_LIMIT_BASE_SECONDS)

    def test_timeout_backs_off(self):
        make, calls = self._flaky([APITimeoutError("Request timed out.")])
        spend.metered_call("m", make, attempts=2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(self.clock.sleeps), 1)

    def test_non_transient_error_not_slept(self):
        make, _ = self._flaky([ValueError("bad"), ValueError("bad")])
        with self.assertRaises(ValueError):
            spend.metered_call("m", make, attempts=2)
        self.assertEqual(self.clock.sleeps, [])

    def test_breaker_opens_and_refuses_without_request(self):
        trip = spend.RATE_LIMIT_TRIP_AFTER
        make, calls = self._flaky([RateLimitError() for _ in range(trip)])
        for _ in range(trip):
            with self.assertRaises(RateLimitError):
                spend.metered_call("m", make, attempts=1)
        self.assertEqual(len(calls), trip)
        with self.assertRaises(spend.UpstreamRateLimited):
            spend.metered_call("m", make, attempts=1)
        self.assertEqual(len(calls), trip)  # no request was made
        self.clock.t += spend.RATE_LIMIT_COOLDOWN_SECONDS + 1
        spend.metered_call("m", make, attempts=1)  # half-open: one probe
        self.assertEqual(len(calls), trip + 1)

    def test_success_resets_consecutive_count(self):
        make, _ = self._flaky([RateLimitError()])
        spend.metered_call("m", make, attempts=2)
        self.assertEqual(spend._rate_limit_streak, 0)


if __name__ == "__main__":
    unittest.main()
