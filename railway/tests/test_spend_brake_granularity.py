"""The per-run brake is checked per CALL, so a run can overshoot by one call.

THE DEFECT, and the number it is measured in. `paid_reads_enabled()` was exact
and cheap, and every caller was told to check it before spending -- but not
WHERE, and the answer kept being "once per item": once per event, once per
cluster, once per audited row, once at the top of main(). An item is not a
call. The AI-evidence sweep asks up to two questions per candidate TEXT and
pulls an unbounded number of texts per event, so a gate read once per event let
the last event run on past the line. Measured, run 31516262943 (2026-08-11):
$0.0166 against a $0.015 ceiling, ~36 calls past it. The monthly
source-verification audit was worse in kind if not in dollars -- one check in
main(), then forty paid calls with no brake between them at all.

THE BOUND A PER-RUN CEILING CAN HONESTLY PROMISE IS ONE CALL. The meter learns
what a call cost only after it is charged, so the last call always straddles the
line. What must NOT happen is the SECOND call after the line, or the fortieth.
That is the property this file pins, in the shape the defect had: per-item work
that makes N model calls.

The enforcement lives in `spend.metered_call()`, where the gate and the meter
are the same function: a caller cannot spend without checking, and cannot check
without metering. The last two classes below assert that no paid call site in
the repo has slipped back outside it -- the item-level gate is exactly the shape
this drifts into, and it drifted silently for months.
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

ROOT = Path(__file__).resolve().parents[2]
RAILWAY = ROOT / "railway"


class _BrakeCase(unittest.TestCase):
    """Isolate the module's process-global meter and every env input to it."""

    CALL_COST = 0.0004        # ~ one extraction at today's prices

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

    def _restore_env(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _one_call(self, cost=None):
        """A model call that costs money and nothing else. Returns a response in
        the SDK shape metered_call reads."""
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0,
                                  cost=self.CALL_COST if cost is None else cost))


class ARunCannotOvershootByMoreThanOneCall(_BrakeCase):
    """The property, stated in dollars: for per-item work making N calls per
    item, final spend <= ceiling + one call."""

    CEILING = 0.015           # ai-evidence-sweep's named ceiling
    CALLS_PER_ITEM = 25       # the sweep's measured per-event call volume

    def _run_a_job(self, calls_per_item, items=200):
        """Drive per-item work through the real brake. Each item makes
        `calls_per_item` calls; the job stops when the brake says stop, which is
        what a caller does with PaidReadsOff."""
        os.environ["ALT_RUN_CEILING_USD"] = str(self.CEILING)
        made = 0
        for _ in range(items):
            for _ in range(calls_per_item):
                try:
                    spend.metered_call("test/model", self._one_call)
                except spend.PaidReadsOff:
                    return made
                made += 1
        return made

    def test_twenty_five_calls_per_item_overshoots_by_at_most_one_call(self):
        self._run_a_job(self.CALLS_PER_ITEM)
        self.assertLessEqual(
            spend.run_cost_usd(), self.CEILING + self.CALL_COST + 1e-9,
            f"a run making {self.CALLS_PER_ITEM} model calls per item spent "
            f"${spend.run_cost_usd():.4f} against a ${self.CEILING:.3f} ceiling "
            f"— more than one call's overshoot means the brake is being read "
            f"per item, not per call")

    def test_it_holds_whatever_the_per_item_call_count_is(self):
        """The old defect scaled with calls-per-item: one gate check per item
        bought an item's worth of overshoot, so N=40 overshot 40x as far as
        N=1. The bound must not depend on N."""
        for n in (1, 2, 3, 25, 40):
            with self.subTest(calls_per_item=n):
                spend.reset_run_meter()
                self._run_a_job(n)
                self.assertLessEqual(
                    spend.run_cost_usd(), self.CEILING + self.CALL_COST + 1e-9,
                    f"{n} calls per item overshot by more than one call")

    def test_the_run_does_get_close_to_its_ceiling(self):
        """The bound above is satisfiable by never spending at all, which would
        be a throttle, not a brake. A run must still be allowed to use what it
        was given."""
        self._run_a_job(self.CALLS_PER_ITEM)
        self.assertGreater(
            spend.run_cost_usd(), self.CEILING - self.CALL_COST,
            "the run stopped well short of its ceiling — that is lost coverage, "
            "not a brake")

    def test_the_stop_is_recorded_as_a_truncation(self):
        """A run stopped by its ceiling is not a run that finished its queue.
        PASS / FAIL / UNKNOWN: a truncated run reports what it did not reach."""
        self._run_a_job(self.CALLS_PER_ITEM)
        entry = spend.record_job_run(items=1)
        self.assertFalse(entry.get("complete", True))
        self.assertIn("ceiling", str(entry.get("truncated") or "").lower())


class MeteredCallIsTheGateAndTheMeter(_BrakeCase):

    def test_it_refuses_before_the_request_when_paid_reads_are_off(self):
        os.environ[spend.PAID_READS_ENV] = "off"

        def explode():
            raise AssertionError("a paid call was made while paid reads are OFF")

        with self.assertRaises(spend.PaidReadsOff):
            spend.metered_call("test/model", explode)

    def test_the_refusal_is_an_ordinary_exception(self):
        """Every paid call site wraps its request in a try/except that degrades
        to a safe value. The refusal has to land in handling that exists."""
        self.assertTrue(issubclass(spend.PaidReadsOff, Exception))

    def test_a_call_that_is_made_is_always_metered(self):
        spend.metered_call("test/model", self._one_call)
        self.assertEqual(spend._run["calls"], 1)
        self.assertAlmostEqual(spend.run_cost_usd(), self.CALL_COST, places=9)

    def test_it_meters_a_raw_json_response_too(self):
        """dedupe_llm and the spot-check hold the parsed JSON, not an SDK
        object. Same charged counts, and the same meter must read them."""
        spend.metered_call("test/model",
                           lambda: {"usage": {"prompt_tokens": 0,
                                              "completion_tokens": 0,
                                              "cost": self.CALL_COST}})
        self.assertAlmostEqual(spend.run_cost_usd(), self.CALL_COST, places=9)

    def test_an_error_from_the_request_propagates_unchanged(self):
        """Existing per-call error handling must be untouched: a transport
        failure is still a transport failure, not a budget stop."""
        with self.assertRaises(TimeoutError):
            spend.metered_call("test/model",
                               lambda: (_ for _ in ()).throw(TimeoutError("x")))


class EveryPaidCallSiteUsesIt(unittest.TestCase):
    """Source-level backstop. A new caller that hand-rolls create() +
    record_usage() is one refactor away from being gated per item again, and
    that is not visible in any test that only exercises the paths we remembered
    to exercise."""

    # spend.py DEFINES the metered path; the tests exercise the meter directly.
    EXEMPT = {"spend.py"}

    def _paid_sources(self):
        for path in sorted(RAILWAY.rglob("*.py")):
            if "tests" in path.parts or path.name in self.EXEMPT:
                continue
            text = path.read_text()
            if "chat/completions" in text or "chat.completions.create" in text:
                yield path, text

    def test_the_sweep_finds_the_paid_scripts_it_is_meant_to_cover(self):
        """A rglob that matches nothing passes every assertion below."""
        found = {p.name for p, _ in self._paid_sources()}
        for expected in ("extractor.py", "ai_evidence_sweep.py", "dedupe_llm.py",
                         "process_tips.py", "source_verification_audit.py",
                         "daily_classification_spotcheck.py"):
            self.assertIn(expected, found)

    def test_no_paid_call_is_made_outside_metered_call(self):
        for path, text in self._paid_sources():
            with self.subTest(script=path.name):
                self.assertIn(
                    "spend.metered_call(", text,
                    f"{path.name} makes a model call without going through "
                    f"spend.metered_call, so its brake and its meter are two "
                    f"separate things a caller can put in the wrong place")

    def test_nothing_meters_by_hand(self):
        """record_usage() outside metered_call means either a call that was
        charged without the brake being read, or a double count."""
        for path, text in self._paid_sources():
            with self.subTest(script=path.name):
                code = "\n".join(line for line in text.splitlines()
                                 if not re.match(r"\s*#", line))
                self.assertNotIn(
                    "spend.record_usage(", code,
                    f"{path.name} calls record_usage directly; metered_call "
                    f"already meters, so this is a charge outside the brake or "
                    f"a call counted twice")


class TheLedgerRecordsTheCeilingTheRunRanUnder(_BrakeCase):
    """So "the per-job brake is not holding" can be a fact rather than an
    inference. ops_status.py [2a] compared every run to the table's NAMED
    ceiling, which reports a brake failure whenever an operator authorised a
    one-dispatch override: run 31572141302 spent $0.2721 under an explicit
    $0.40 and was reported against $0.150."""

    def test_the_entry_carries_the_effective_ceiling(self):
        os.environ["ALT_JOB"] = "ai-evidence-sweep"
        entry = spend.record_job_run(items=1)
        self.assertAlmostEqual(entry["ceiling_usd"], 0.015, places=6)

    def test_an_operator_override_is_what_gets_recorded(self):
        os.environ["ALT_JOB"] = "ai-evidence-sweep"
        os.environ["ALT_RUN_CEILING_USD"] = "0.40"
        entry = spend.record_job_run(items=1)
        self.assertAlmostEqual(entry["ceiling_usd"], 0.40, places=6)


if __name__ == "__main__":
    unittest.main()
