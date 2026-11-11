"""AI-LAYOFF-TRACKER-2: a slow gate call must retry, then degrade quietly.

The pre-extraction gate (extractor.gate_verdict) already fails open to
GATE_ERROR, but the Sentry OpenAI integration reported every timed-out attempt
as an UNHANDLED error before our except clause ran. The gate now retries three
times with an explicit timeout, logs a handled warning on final failure, and
sentry_init drops the SDK's auto-captured transient errors.
"""
import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import extractor
import sentry_init
import spend


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


class RateLimitError(Exception):
    status_code = 429


class _Completions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=out))],
            usage=None)


def _client(comp):
    return SimpleNamespace(chat=SimpleNamespace(completions=comp))


class GateRetryTests(unittest.TestCase):
    def setUp(self):
        spend.reset_run_meter()
        spend._prices_fetched = True
        self.entry = {"raw_text": "Acme to lay off 500", "source_name": "Wire"}
        self._sleep = patch.object(spend, "_sleep", lambda s: None)
        self._sleep.start()
        self._rs = patch.object(spend, "_wait_for_upstream", lambda w: None)
        self._rs.start()

    def tearDown(self):
        self._sleep.stop()
        self._rs.stop()
        spend.reset_run_meter()

    def _run(self, outcomes):
        comp = _Completions(outcomes)
        with patch.object(extractor, "_get_client", return_value=_client(comp)):
            return extractor.gate_verdict(self.entry), comp

    def test_recovers_after_two_transient_failures(self):
        for exc in (APITimeoutError("t"), APIConnectionError("c"),
                    RateLimitError("r")):
            verdict, comp = self._run([exc, exc, "YES"])
            self.assertEqual(verdict, extractor.GATE_YES, type(exc).__name__)
            self.assertEqual(len(comp.calls), 3)

    def test_gives_up_after_three_attempts_and_fails_open_with_warning(self):
        with self.assertLogs("extractor", level="WARNING") as cm:
            verdict, comp = self._run([APITimeoutError("t")] * 3)
        self.assertEqual(verdict, extractor.GATE_ERROR)
        self.assertEqual(len(comp.calls), 3)
        self.assertTrue(any("gate" in m and "APITimeoutError" in m
                            for m in cm.output))

    def test_every_attempt_has_an_explicit_timeout(self):
        _, comp = self._run([APITimeoutError("t"), "NO"])
        for call in comp.calls:
            self.assertEqual(call["timeout"], extractor.GATE_TIMEOUT_SECONDS)
        self.assertGreater(extractor.GATE_TIMEOUT_SECONDS, 0)


class SentryFilterTests(unittest.TestCase):
    @staticmethod
    def _event(exc_type, mechanism):
        return {"exception": {"values": [
            {"type": exc_type, "mechanism": {"type": mechanism, "handled": False}}]}}

    def test_drops_openai_captured_transient_errors(self):
        for name in ("APITimeoutError", "APIConnectionError", "RateLimitError"):
            self.assertIsNone(
                sentry_init.before_send(self._event(name, "openai"), {}), name)

    def test_keeps_everything_else(self):
        ev = self._event("ValueError", "openai")
        self.assertIs(sentry_init.before_send(ev, {}), ev)
        ev = self._event("APITimeoutError", "logging")
        self.assertIs(sentry_init.before_send(ev, {}), ev)
        ev = {"message": "x"}
        self.assertIs(sentry_init.before_send(ev, {}), ev)


if __name__ == "__main__":
    unittest.main()
