"""A transient 504 on the sweep's cursor bookkeeping is not an action item.

On 2026-07-29 (run 30482640840) the historical GDELT window completed — "0
posted" printed and all — and then a single Bluehost 504 on the cursor SAVE
turned the healthy run red and emailed the owner. The cursor not advancing is
self-healing: the next daily run repeats the identical window and dedup
absorbs it. RED means a human must act; there is nothing here for a human to
do that host-watch (sibling repo) is not already doing.

Both `main()` tests fail on the pre-fix tree, where `_api` was a single
un-retried `raise_for_status()`.
"""
import pathlib
import sys
import types
import unittest

RAILWAY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

# The real gdelt_backfill drags in the OpenRouter client at import time; every
# test here replaces `run` anyway, so a stub keeps this file importable in a
# bare environment. setdefault: if another test already imported the real one,
# the real one is kept and monkeypatched per test.
sys.modules.setdefault("gdelt_backfill", types.SimpleNamespace(run=lambda: None))

import historical_news_sweep as sweep  # noqa: E402


# A self-contained stand-in for the requests module. Another test file in
# this suite plants a bare stub of `requests` into sys.modules, so relying on
# the real module's attributes here would make this file pass or fail on test
# ORDER. The sweep only touches request/RequestException/HTTPError.
class FakeRequestException(Exception):
    pass


class FakeHTTPError(FakeRequestException):
    def __init__(self, message="", response=None):
        super().__init__(message)
        self.response = response


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise FakeHTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._payload


def fake_requests(request_fn):
    return types.SimpleNamespace(request=request_fn,
                                 RequestException=FakeRequestException,
                                 HTTPError=FakeHTTPError)


class Env:
    """WP env + no real sleeps, restored per test."""

    def __init__(self, testcase):
        import os
        import time
        for key, value in (("WP_SITE_URL", "https://tracker.example/blog"),
                           ("WP_API_KEY", "k"),
                           ("HISTORICAL_START_OVERRIDE", ""),
                           ("HISTORICAL_END_OVERRIDE", "")):
            old = os.environ.get(key)
            os.environ[key] = value
            testcase.addCleanup(
                (lambda k, o: (lambda: os.environ.update({k: o}) if o is not None
                               else os.environ.pop(k, None)))(key, old))
        real_sleep = time.sleep
        sweep.time.sleep = lambda seconds: None
        testcase.addCleanup(lambda: setattr(sweep.time, "sleep", real_sleep))


class TheCursorIsBookkeepingNotAGuard(unittest.TestCase):
    def test_a_504_on_the_cursor_read_defers_green(self):
        Env(self)
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append((method, url))
            return FakeResponse(504)

        real = sweep.requests
        sweep.requests = fake_requests(fake_request)
        try:
            code = sweep.main()
        finally:
            sweep.requests = real
        self.assertEqual(code, 0, "an outage at the very start ran nothing "
                                  "and loses nothing; red is for action items")
        self.assertEqual(len(calls), 3, "the 504 must be retried before being "
                                        "deferred")

    def test_a_504_on_the_cursor_save_after_a_good_window_defers_green(self):
        Env(self)

        def fake_request(method, url, **kwargs):
            if method == "POST":
                return FakeResponse(504)
            return FakeResponse(200, {"next_start": "2017-01-01"})

        ran = []
        real_request = sweep.requests
        real_run = sweep.gdelt_backfill.run
        sweep.requests = fake_requests(fake_request)
        sweep.gdelt_backfill.run = lambda: ran.append(True)
        try:
            code = sweep.main()
        finally:
            sweep.requests = real_request
            sweep.gdelt_backfill.run = real_run
        self.assertEqual(ran, [True], "the window itself must have run")
        self.assertEqual(code, 0, "the window succeeded; a refused bookkeeping "
                                  "write repeats the window tomorrow")

    def test_a_real_backfill_failure_is_still_loud(self):
        """The guard that matters is untouched: a crash inside the window is
        an action item and stays red."""
        Env(self)

        def fake_request(method, url, **kwargs):
            return FakeResponse(200, {"next_start": "2017-01-01"})

        def exploding_run():
            raise RuntimeError("the collector broke")

        real_request = sweep.requests
        real_run = sweep.gdelt_backfill.run
        sweep.requests = fake_requests(fake_request)
        sweep.gdelt_backfill.run = exploding_run
        try:
            with self.assertRaises(RuntimeError):
                sweep.main()
        finally:
            sweep.requests = real_request
            sweep.gdelt_backfill.run = real_run


if __name__ == "__main__":
    unittest.main()
