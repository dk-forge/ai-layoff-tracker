"""A collector killed from the outside must still answer its own `running` note.

Two platforms end a collector with SIGTERM, a short grace, then SIGKILL: Railway
replaces the cron container on every deploy (~10s), and GitHub cancels a step on
`timeout-minutes` or a concurrency group (SIGTERM, then a kill ~7.5s later).
Until 2026-09-05 nothing handled either signal. The process died with its
`running` note on the ledger and no terminal note after it, and because the
ledger keeps only the LATEST note per source and a `running` row carries a
FRESH `checked_at`, a run that died mid-flight counted toward "N source(s) OK"
and reset its own staleness clock. `ops_status [2e]` measured five such
orphans: gdelt 2026-08-26 and 2026-09-03, gdelt_historical 2026-08-27 and
2026-09-04, archive_backfill 2026-08-30.

`source_health` now keeps the set of sources whose `running` note landed and
has not been answered, and ONE signal handler posts a `degraded` terminal note
for each of them ("interrupted: SIGTERM ...") before handing the signal back to
the platform, so the exit is still 143 / killed-by-SIGTERM.

PROVEN BY A REAL PROCESS, NOT BY ASSERTION. The subprocess tests start a fake
ledger on localhost, run a child that posts real notes to it, send it a real
SIGTERM, and read what the ledger received and how the child exited. The child
takes `requests` from the shared `_requests_stub.install()` and points its
`post` at urllib inside that child only, so the test needs no third-party
package and every POST is visible to the fake ledger. Mutations
that redden this file: dropping the open-set clear on a normal terminal note
(the "nothing after ok" test), dropping the request timeout in the handler
(the hang test), dropping the re-raise (the exit-status tests), dropping the
drain of the open set (the double-signal test).
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

# source_health imports `requests` at module scope; the ONE shared stub.
from tests import _requests_stub  # noqa: E402
_requests_stub.install()

import run_completion  # noqa: E402
import source_health  # noqa: E402

KILLED_BY_SIGTERM = (-int(signal.SIGTERM), 128 + int(signal.SIGTERM))
KILLED_BY_SIGINT = (-int(signal.SIGINT), 128 + int(signal.SIGINT))

# How long the fake ledger sits on a `degraded` POST in "hang" mode. Longer
# than the handler's own timeout, so a handler WITHOUT a timeout blocks here
# and the test reads that as a hang; shorter than the test's patience only so
# a mutated run fails instead of stalling the suite.
HANG_SECONDS = 8.0

# A child is given this long to exit after SIGTERM. It is comfortably above the
# handler's budget and comfortably below HANG_SECONDS, so an unbounded handler
# cannot pass by waiting the fake ledger out.
EXIT_PATIENCE = 6.0


class _FakeLedger:
    """A /source-health endpoint that records what it was sent.

    `mode` is "ok" (200 to everything), "hang_degraded" (sit on any `degraded`
    note for HANG_SECONDS before answering) or "refuse_degraded" (HTTP 500 to
    any `degraded` note).
    """

    def __init__(self, mode="ok"):
        self.mode = mode
        self.notes = []
        self.lock = threading.Lock()
        ledger = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                with ledger.lock:
                    ledger.notes.append(body)
                code = 200
                if body.get("status") == "degraded":
                    if ledger.mode == "hang_degraded":
                        time.sleep(HANG_SECONDS)
                    elif ledger.mode == "refuse_degraded":
                        code = 500
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def of(self, status):
        with self.lock:
            return [n for n in self.notes if n.get("status") == status]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


# The collector under test: posts the notes it is told to, says READY, then
# waits to be killed, exactly like a collector mid-sweep.
CHILD = textwrap.dedent("""
    import json, sys, time, urllib.error, urllib.request

    class _Resp:
        def __init__(self, code):
            self.status_code = code

    def _post(url, json=None, headers=None, timeout=None):
        import json as _json
        body = _json.dumps(json).encode()
        hdrs = dict(headers or {})
        hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return _Resp(r.status)
        except urllib.error.HTTPError as e:
            return _Resp(e.code)

    # The ONE installer (tests/_requests_stub.py), never a private stub in the
    # process-global slot. This is a fresh subprocess, so pointing its `post`
    # at urllib is safe and makes every note visible to the fake ledger
    # whether or not the real `requests` is installed.
    sys.path.insert(0, sys.argv[1])
    from tests import _requests_stub
    _requests_stub.install().post = _post
    import source_health

    for source, status in json.loads(sys.argv[2]):
        source_health.report_source_health(source, status, 0, "test note")
    print("READY", flush=True)
    while True:
        time.sleep(0.2)
""")


class _Subprocess(unittest.TestCase):
    """Run the child against a fake ledger, kill it, read both sides."""

    mode = "ok"

    def setUp(self):
        self.ledger = _FakeLedger(self.mode)
        self.addCleanup(self.ledger.close)
        fd, self.script = tempfile.mkstemp(suffix=".py", prefix="alt-child-")
        with os.fdopen(fd, "w") as fh:
            fh.write(CHILD)
        self.addCleanup(os.unlink, self.script)
        self.proc = None

    def tearDown(self):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()
        self.proc.stderr.close()

    def start(self, plan):
        env = dict(os.environ, WP_SITE_URL=self.ledger.url, WP_API_KEY="test-key",
                   PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen(
            [sys.executable, self.script, RAILWAY, json.dumps(plan)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        line = self.proc.stdout.readline()
        if line.strip() != b"READY":
            err = self.proc.stderr.read().decode(errors="replace")
            self.fail(f"child never became ready; stderr:\n{err}")
        return self.proc

    def kill_and_wait(self, sig=signal.SIGTERM, patience=EXIT_PATIENCE):
        sent = time.monotonic()
        os.kill(self.proc.pid, sig)
        try:
            self.proc.wait(timeout=patience)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.fail(f"child did not exit within {patience}s of {sig!s}; the "
                      f"handler outlived the platform's grace window")
        return time.monotonic() - sent


class SigtermAfterRunningPostsOneDegradedNote(_Subprocess):
    def test_one_degraded_interrupted_note_per_open_run_and_exit_by_sigterm(self):
        self.start([["gdelt", "running"]])
        self.kill_and_wait(signal.SIGTERM)
        self.assertIn(self.proc.returncode, KILLED_BY_SIGTERM,
                      f"exit was {self.proc.returncode}, not killed-by-SIGTERM/143")
        degraded = self.ledger.of("degraded")
        self.assertEqual(len(degraded), 1, f"expected exactly one terminal note, got {degraded}")
        note = degraded[0]
        self.assertEqual(note["source"], "gdelt")
        self.assertEqual(note["entries"], 0)
        self.assertTrue(note["detail"].startswith("interrupted: SIGTERM before the run finished"),
                        note["detail"])
        self.assertLessEqual(len(note["detail"]), 240)
        # And the child's stdout said so, once.
        out = self.proc.stdout.read().decode(errors="replace")
        self.assertEqual(out.count("closed as degraded"), 1, out)

    def test_every_open_run_is_closed_when_several_are_open(self):
        self.start([["gdelt", "running"], ["gdelt_historical", "running"]])
        self.kill_and_wait(signal.SIGTERM)
        self.assertIn(self.proc.returncode, KILLED_BY_SIGTERM)
        closed = sorted(n["source"] for n in self.ledger.of("degraded"))
        self.assertEqual(closed, ["gdelt", "gdelt_historical"])

    def test_sigint_is_named_in_the_note_and_the_exit_is_by_sigint(self):
        self.start([["archive_backfill", "running"]])
        self.kill_and_wait(signal.SIGINT)
        self.assertIn(self.proc.returncode, KILLED_BY_SIGINT,
                      f"exit was {self.proc.returncode}")
        degraded = self.ledger.of("degraded")
        self.assertEqual(len(degraded), 1)
        self.assertIn("interrupted: SIGINT", degraded[0]["detail"])

    def test_the_interrupted_note_reads_as_a_finish_to_run_completion(self):
        """The whole point: `[2e]` must stop reporting the run as an orphan."""
        self.start([["gdelt", "running"]])
        self.kill_and_wait(signal.SIGTERM)
        runs = [{"source": n["source"], "status": n["status"],
                 "attempted_at": f"2026-09-04T22:0{i}:00+00:00"}
                for i, n in enumerate(self.ledger.notes)]
        self.assertEqual(run_completion.orphans(runs, now=run_completion.datetime(
            2026, 9, 5, 12, 0, tzinfo=run_completion.timezone.utc)), [])


class NormalFinishLeavesNothingForTheHandler(_Subprocess):
    def test_after_ok_the_handler_posts_nothing(self):
        self.start([["gdelt", "running"], ["gdelt", "ok"]])
        self.kill_and_wait(signal.SIGTERM)
        self.assertIn(self.proc.returncode, KILLED_BY_SIGTERM)
        self.assertEqual(self.ledger.of("degraded"), [],
                         "a run that finished normally was closed a second time")
        self.assertEqual([n["status"] for n in self.ledger.notes], ["running", "ok"])

    def test_after_degraded_the_handler_posts_nothing_more(self):
        self.start([["gdelt", "running"], ["gdelt", "degraded"]])
        self.kill_and_wait(signal.SIGTERM)
        self.assertIn(self.proc.returncode, KILLED_BY_SIGTERM)
        self.assertEqual(len(self.ledger.of("degraded")), 1,
                         "the collector's own degraded note was followed by another")

    def test_a_finished_run_does_not_shadow_a_later_open_one(self):
        # cron.py opens and closes one source after another; only the one in
        # flight at the kill is interrupted.
        self.start([["edgar", "running"], ["edgar", "ok"], ["gdelt", "running"]])
        self.kill_and_wait(signal.SIGTERM)
        closed = [n["source"] for n in self.ledger.of("degraded")]
        self.assertEqual(closed, ["gdelt"])


class HandlerPostingIsBounded(_Subprocess):
    mode = "hang_degraded"

    def test_a_ledger_that_never_answers_cannot_hold_the_exit_past_the_grace(self):
        self.start([["gdelt", "running"]])
        took = self.kill_and_wait(signal.SIGTERM, patience=EXIT_PATIENCE)
        self.assertIn(self.proc.returncode, KILLED_BY_SIGTERM)
        # The note was ATTEMPTED (the ledger saw it arrive) and then abandoned
        # inside the handler's own timeout, not the ledger's.
        self.assertEqual(len(self.ledger.of("degraded")), 1)
        self.assertLess(took, source_health.INTERRUPT_BUDGET_SECONDS + 1.0,
                        f"exit took {took:.1f}s; the handler waited on the ledger")
        err = self.proc.stdout.read().decode(errors="replace")
        self.assertIn("exiting anyway", err)


class HandlerPostFailureIsNotARaise(_Subprocess):
    mode = "refuse_degraded"

    def test_a_refused_note_prints_one_line_and_the_exit_is_still_by_sigterm(self):
        self.start([["gdelt", "running"]])
        self.kill_and_wait(signal.SIGTERM)
        self.assertIn(self.proc.returncode, KILLED_BY_SIGTERM)
        out = self.proc.stdout.read().decode(errors="replace")
        err = self.proc.stderr.read().decode(errors="replace")
        self.assertEqual(out.count("interrupted note for gdelt refused"), 1, out)
        self.assertNotIn("Traceback", err)


class _Response:
    def __init__(self, code=200):
        self.status_code = code


class HandlerInProcess(unittest.TestCase):
    """The parts a signal cannot show from outside: idempotence, the fired
    guard, the not-landed case, and that the handler hands the signal back."""

    def setUp(self):
        self._saved = (dict(source_health._open_runs),
                       source_health._handlers_installed, dict(source_health._previous_handlers))
        self._saved_signals = {s: signal.getsignal(s) for s in source_health.INTERRUPT_SIGNALS}
        source_health._open_runs.clear()
        source_health._handlers_installed = False
        source_health._previous_handlers.clear()
        self.posts = []
        self.reraised = []
        self.env = mock.patch.dict(os.environ, {"WP_SITE_URL": "https://example.test/blog",
                                                "WP_API_KEY": "k"})
        self.env.start()
        self.post = mock.patch.object(source_health.requests, "post", side_effect=self._post)
        self.post.start()
        self.reraise = mock.patch.object(source_health, "_reraise", side_effect=self.reraised.append)
        self.reraise.start()
        self.sleep = mock.patch.object(source_health.time, "sleep")
        self.sleep.start()
        self.code = 200
        self.boom = None

    def tearDown(self):
        for p in (self.sleep, self.reraise, self.post, self.env):
            p.stop()
        for s, h in self._saved_signals.items():
            signal.signal(s, h)
        (runs, installed, prev) = self._saved
        source_health._open_runs.clear()
        source_health._open_runs.update(runs)
        source_health._handlers_installed = installed
        source_health._previous_handlers.clear()
        source_health._previous_handlers.update(prev)

    def _post(self, url, json=None, headers=None, timeout=None):
        if self.boom and json.get("status") == "degraded":
            raise self.boom
        self.posts.append((json, timeout))
        return _Response(self.code)

    def degraded(self):
        return [j for j, _t in self.posts if j["status"] == "degraded"]

    def test_running_registers_the_run_and_installs_the_handler_once(self):
        self.assertIsNot(signal.getsignal(signal.SIGTERM), source_health._on_interrupt)
        source_health.report_source_health("gdelt", "running", 0, "collection in progress")
        self.assertEqual(source_health.open_runs(), {"gdelt": "collection in progress"})
        self.assertIs(signal.getsignal(signal.SIGTERM), source_health._on_interrupt)
        self.assertIs(signal.getsignal(signal.SIGINT), source_health._on_interrupt)
        before = dict(source_health._previous_handlers)
        source_health.report_source_health("edgar", "running", 0, "x")
        self.assertEqual(source_health._previous_handlers, before, "installed twice")

    def test_a_second_signal_posts_nothing_and_still_hands_the_signal_back(self):
        source_health.report_source_health("gdelt", "running", 0, "x")
        source_health._on_interrupt(signal.SIGTERM, None)
        source_health._on_interrupt(signal.SIGTERM, None)
        self.assertEqual(len(self.degraded()), 1, self.degraded())
        self.assertEqual(self.reraised, [signal.SIGTERM, signal.SIGTERM])
        self.assertEqual(source_health.open_runs(), {})

    def test_the_note_is_one_attempt_with_a_short_timeout(self):
        source_health.report_source_health("gdelt", "running", 0, "x")
        source_health._on_interrupt(signal.SIGTERM, None)
        degraded = [(j, t) for j, t in self.posts if j["status"] == "degraded"]
        self.assertEqual(len(degraded), 1)
        _note, timeout = degraded[0]
        self.assertIsNotNone(timeout, "the interrupted note had no timeout")
        self.assertLessEqual(timeout, source_health.INTERRUPT_POST_TIMEOUT_SECONDS)
        self.assertLess(source_health.INTERRUPT_BUDGET_SECONDS, 7.5,
                        "the budget must fit inside GitHub's ~7.5s grace")

    def test_a_running_note_that_never_landed_is_not_registered(self):
        self.code = 500
        source_health.report_source_health("gdelt", "running", 0, "x")
        self.assertEqual(source_health.open_runs(), {},
                         "a running note the ledger refused has nothing to orphan")

    def test_a_failing_post_inside_the_handler_does_not_raise(self):
        source_health.report_source_health("gdelt", "running", 0, "x")
        self.boom = ConnectionError("relay down")
        source_health._on_interrupt(signal.SIGTERM, None)   # must not raise
        self.assertEqual(self.reraised, [signal.SIGTERM])
        self.assertEqual(source_health.open_runs(), {})

    def test_a_terminal_note_that_did_not_land_keeps_the_run_open(self):
        # The terminal POST was refused, so the ledger still holds `running`;
        # a kill after that must still answer it.
        source_health.report_source_health("gdelt", "running", 0, "x")
        self.code = 500
        source_health.report_source_health("gdelt", "ok", 3, "done")
        self.assertEqual(source_health.open_runs(), {"gdelt": "x"})

    def test_a_deferral_closes_the_run_too(self):
        # host_call.defer posts `degraded` through report_source_health, which
        # is the same door, so a deferred job leaves nothing for the handler.
        source_health.report_source_health("archive_backfill", "running", 0, "x")
        source_health.report_source_health("archive_backfill", "degraded", 0,
                                           "deferred: host never answered")
        source_health._on_interrupt(signal.SIGTERM, None)
        self.assertEqual(len(self.degraded()), 1)


if __name__ == "__main__":
    unittest.main()
