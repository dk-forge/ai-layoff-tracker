"""ONE `metered_call` is ONE request, and every request is gated and metered.

WHY THIS FILE EXISTS, AND WHY IT IS NOT THE SAME FILE AS
test_spend_brake_granularity.py. That file pins the rule that the brake is read
per CALL rather than per ITEM, and it pins that every paid script routes its
request through `spend.metered_call()`. Both held. What neither could see is a
callable that goes through metered_call and then makes the request TWICE:

  * `daily_classification_spotcheck.ask_model` passed `attempts=2` to
    `request_json` INSIDE the metered lambda. Two POSTs, one gate read, and
    only whichever attempt returned was metered.
  * five scripts built `openai.OpenAI(...)` with the SDK's DEFAULT
    `max_retries=2` (extractor.py: 1). The SDK re-POSTs on 408/409/429/5xx and
    on any connection error, from inside the callable. Same shape, invisible,
    and imported rather than written.

The charge is not hypothetical. A client-side timeout does not cancel a
generation: OpenRouter may have produced and billed the completion the client
stopped waiting for, so the retry is a second charge that no ledger entry, no
per-run ceiling and no $/row figure has ever seen. That is worse than an
overshoot — an overshoot is at least measured.

THE PROPERTY, stated so it cannot be satisfied by accident:

    requests made  <=  gate reads,  and  every response that comes back is
    metered.

`spend.metered_call(attempts=N)` is now the one supported way to retry: each
attempt is gate read -> request -> meter, so N attempts cost at most N calls,
each of them checked and each of them counted. The per-run ceiling keeps its
honest bound of a single call of overshoot.

The last class is the source-level backstop, because the SDK default is the
version of this defect that arrives by upgrading a dependency rather than by
anybody writing a loop.
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

import spend  # noqa: E402

RAILWAY = Path(__file__).resolve().parents[1]


class _MeterCase(unittest.TestCase):
    """Isolate the process-global meter and every env input to it."""

    CALL_COST = 0.0004

    def setUp(self):
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        self._env = {k: os.environ.get(k) for k in
                     ("ALT_JOB", "ALT_RUN_CEILING_USD", "ALT_PAID_READS",
                      "OPENROUTER_API_KEY", "GITHUB_WORKFLOW_REF",
                      "ALT_RUN_SPEND_FILE", "GITHUB_RUN_ID")}
        for k in self._env:
            os.environ.pop(k, None)
        self.addCleanup(self._restore_env)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._snap = spend.SNAPSHOT_PATH
        spend.SNAPSHOT_PATH = os.path.join(self.tmp.name, "spend_month.json")
        self.addCleanup(lambda: setattr(spend, "SNAPSHOT_PATH", self._snap))
        spend._prices_fetched = True
        # Count how often the brake is consulted, without changing what it says.
        self.gate_reads = 0
        real_gate = spend.paid_reads_enabled

        def counting_gate():
            self.gate_reads += 1
            return real_gate()

        spend.paid_reads_enabled = counting_gate
        self.addCleanup(lambda: setattr(spend, "paid_reads_enabled", real_gate))

    def _restore_env(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _response(self):
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0,
                                  cost=self.CALL_COST))


class ARetryIsAFullCycle(_MeterCase):
    """Gate read, request, meter — for every attempt, not only the first."""

    def test_each_attempt_reads_the_brake_again(self):
        requests_made = []

        def flaky():
            requests_made.append(1)
            if len(requests_made) < 3:
                raise TimeoutError("provider timed out")
            return self._response()

        os.environ["ALT_RUN_CEILING_USD"] = "1.00"
        spend.metered_call("test/model", flaky, attempts=3)
        self.assertEqual(len(requests_made), 3)
        self.assertGreaterEqual(
            self.gate_reads, len(requests_made),
            "requests outnumbered gate reads: a retry was made without the "
            "brake being re-read, which is a charge nothing checked")

    def test_a_run_at_its_ceiling_does_not_buy_the_retry(self):
        """The expensive case. A callable that retries internally spends its
        remaining attempts AFTER the line; metered_call must not."""
        os.environ["ALT_RUN_CEILING_USD"] = str(self.CALL_COST)  # one call's worth
        spend.metered_call("test/model", self._response)         # spends it all
        requests_made = []

        def should_not_run():
            requests_made.append(1)
            raise TimeoutError("x")

        with self.assertRaises(spend.PaidReadsOff):
            spend.metered_call("test/model", should_not_run, attempts=5)
        self.assertEqual(requests_made, [],
                         "a run past its ceiling still sent a request")

    def test_the_brake_is_re_read_between_attempts_not_cached(self):
        """The gate must be consulted again, not remembered from attempt 1.
        Proved by switching paid reads off DURING the retry: attempt 2 must be
        refused and no request sent."""
        os.environ["ALT_RUN_CEILING_USD"] = "1.00"
        sent = []

        def fail_then_switch_off():
            sent.append(1)
            os.environ[spend.PAID_READS_ENV] = "off"
            raise TimeoutError("provider timed out")

        self.addCleanup(lambda: os.environ.pop(spend.PAID_READS_ENV, None))
        with self.assertRaises(spend.PaidReadsOff):
            spend.metered_call("test/model", fail_then_switch_off, attempts=4)
        self.assertEqual(len(sent), 1,
                         "the retry was sent after paid reads were switched "
                         "off — the brake was read once and cached")

    def test_every_response_that_comes_back_is_metered(self):
        os.environ["ALT_RUN_CEILING_USD"] = "1.00"
        for _ in range(4):
            spend.metered_call("test/model", self._response, attempts=2)
        self.assertEqual(spend._run["calls"], 4)
        self.assertAlmostEqual(spend.run_cost_usd(), 4 * self.CALL_COST, places=9)

    def test_the_last_failure_still_propagates(self):
        """Retrying must not convert a transport failure into a silent success:
        the caller's existing except: branch is what degrades the row."""
        os.environ["ALT_RUN_CEILING_USD"] = "1.00"

        def always_fails():
            raise TimeoutError("provider is down")

        with self.assertRaises(TimeoutError):
            spend.metered_call("test/model", always_fails, attempts=2)

    def test_one_attempt_is_still_the_default(self):
        """No caller gets extra spend by upgrading spend.py."""
        sent = []

        def fails():
            sent.append(1)
            raise TimeoutError("x")

        os.environ["ALT_RUN_CEILING_USD"] = "1.00"
        with self.assertRaises(TimeoutError):
            spend.metered_call("test/model", fails)
        self.assertEqual(len(sent), 1)


class TheSpotCheckSendsOneRequestPerGateRead(_MeterCase):
    """End-to-end on the caller that had the defect written out in full.

    Drives `daily_classification_spotcheck.ask_model` with a fake transport and
    counts POSTs. Before this fix it sent two per gate read.
    """

    def setUp(self):
        super().setUp()
        import daily_classification_spotcheck as spot
        self.spot = spot
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        os.environ["ALT_RUN_CEILING_USD"] = "1.00"
        self.posts = []
        real_urlopen = spot.urllib.request.urlopen
        self.addCleanup(lambda: setattr(spot.urllib.request, "urlopen", real_urlopen))
        real_sleep = spot.time.sleep
        spot.time.sleep = lambda *_a, **_k: None
        self.addCleanup(lambda: setattr(spot.time, "sleep", real_sleep))
        # metered_call's own backoff must not slow the suite either.
        self._orig_metered = spend.metered_call

        def no_sleep_metered(*args, **kwargs):
            kwargs["retry_sleep"] = 0.0
            return self._orig_metered(*args, **kwargs)

        spend.metered_call = no_sleep_metered
        self.addCleanup(lambda: setattr(spend, "metered_call", self._orig_metered))

    def _transport(self, failures):
        """A urlopen that fails `failures` times, then answers."""
        def urlopen(req, timeout=None):
            self.posts.append(getattr(req, "full_url", ""))
            if len(self.posts) <= failures:
                raise TimeoutError("provider timed out")
            body = ('{"choices":[{"message":{"content":"{\\"rows\\": []}"}}],'
                    '"usage":{"prompt_tokens":0,"completion_tokens":0,"cost":0.0004}}')
            return SimpleNamespace(read=lambda: body.encode(),
                                   __enter__=lambda s: s,
                                   __exit__=lambda *a: False)
        return urlopen

    def test_a_clean_answer_costs_exactly_one_request(self):
        self.spot.urllib.request.urlopen = self._transport(failures=0)
        self.spot.ask_model("q")
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(spend._run["calls"], 1)

    def test_a_retried_answer_reads_the_brake_for_the_second_request_too(self):
        self.spot.urllib.request.urlopen = self._transport(failures=1)
        self.spot.ask_model("q")
        self.assertEqual(len(self.posts), 2)
        self.assertGreaterEqual(
            self.gate_reads, len(self.posts),
            "the spot-check sent more requests than it read the brake — the "
            "retry is back inside the metered callable")

    def test_it_sends_nothing_once_the_ceiling_is_spent(self):
        os.environ["ALT_RUN_CEILING_USD"] = str(self.CALL_COST)
        self.spot.urllib.request.urlopen = self._transport(failures=0)
        self.spot.ask_model("q")            # spends the ceiling
        self.assertEqual(len(self.posts), 1)
        with self.assertRaises(spend.PaidReadsOff):
            self.spot.ask_model("q")
        self.assertEqual(len(self.posts), 1,
                         "a request went out after the ceiling was spent")


class NoPaidCallableRetriesInsideItself(unittest.TestCase):
    """Source-level backstop, in the two shapes the defect actually took."""

    #: Scripts that construct their own OpenAI client for a paid call.
    def _paid_sources(self):
        for path in sorted(RAILWAY.rglob("*.py")):
            if "tests" in path.parts or path.name == "spend.py":
                continue
            text = path.read_text()
            if "chat/completions" in text or "chat.completions.create" in text:
                yield path, text

    def test_the_sweep_finds_the_paid_scripts_it_is_meant_to_cover(self):
        found = {p.name for p, _ in self._paid_sources()}
        for expected in ("extractor.py", "ai_evidence_sweep.py",
                         "process_tips.py", "source_verification_audit.py",
                         "daily_classification_spotcheck.py"):
            self.assertIn(expected, found)

    def test_every_openai_client_disables_the_sdks_own_retries(self):
        """`openai.OpenAI()` defaults to max_retries=2. Inside a metered
        callable that is two charges behind one gate read, and it arrives by
        dependency upgrade rather than by anybody writing a loop."""
        pattern = re.compile(r"(?:openai\.)?OpenAI\s*\(", re.MULTILINE)
        for path, text in self._paid_sources():
            for match in pattern.finditer(text):
                # The constructor's argument list, up to its closing paren.
                depth, i = 0, match.end() - 1
                while i < len(text):
                    if text[i] == "(":
                        depth += 1
                    elif text[i] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    i += 1
                args = text[match.end():i]
                with self.subTest(script=path.name, at=text[:match.start()].count("\n") + 1):
                    self.assertRegex(
                        args, r"max_retries\s*=\s*0",
                        f"{path.name} builds an OpenAI client without "
                        f"max_retries=0, so the SDK will re-POST from inside "
                        f"the callable handed to spend.metered_call — a charge "
                        f"with no gate read and no ledger entry. Retry with "
                        f"spend.metered_call(attempts=N) instead")

    @staticmethod
    def _metered_callables(text):
        """Yield (line_no, source of the callable) for every metered_call.

        Only the CALLABLE argument, never metered_call's own kwargs: an
        `attempts=` on metered_call is the supported route and an `attempts=`
        inside the callable is the defect, and a test that cannot tell them
        apart would have to be loosened until it caught neither.
        """
        for match in re.finditer(r"spend\.metered_call\(", text):
            line_no = text[:match.start()].count("\n") + 1
            i = text.index("lambda", match.end()) if "lambda" in text[match.end():match.end() + 400] else None
            if i is None:
                # A named callable (not a lambda): its own body is checked
                # where it is defined; nothing to extract here.
                continue
            depth, j = 0, i
            while j < len(text):
                ch = text[j]
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                elif ch == "," and depth == 0:
                    break
                j += 1
            yield line_no, text[i:j]

    def test_the_extractor_is_seen_as_retrying_via_metered_call(self):
        """Guards the extractor above: if the parse ever stops finding these
        callables, every assertion below passes vacuously."""
        text = (RAILWAY / "extractor.py").read_text()
        found = list(self._metered_callables(text))
        self.assertEqual(len(found), 8, "expected 8 metered lambdas in extractor.py")

    def test_no_metered_callable_asks_a_helper_to_retry(self):
        """`attempts=` on a helper INSIDE the lambda is the hand-written form
        of the same defect (daily_classification_spotcheck, until 2026-08-18).
        Retries belong on metered_call, where the gate and the meter are."""
        for path, text in self._paid_sources():
            for line_no, body in self._metered_callables(text):
                with self.subTest(script=path.name, line=line_no):
                    self.assertNotRegex(
                        body, r"\battempts\s*=\s*(?!1\b)\w+",
                        f"{path.name}:{line_no} hands metered_call a callable "
                        f"that retries internally. Every request after the "
                        f"first is then unchecked and unmetered. Use "
                        f"spend.metered_call(attempts=N)")
                    self.assertNotRegex(
                        body, r"\bfor\b.*\brange\(|\bwhile\b",
                        f"{path.name}:{line_no} hands metered_call a callable "
                        f"that loops: several charges behind one gate read")


if __name__ == "__main__":
    unittest.main()
