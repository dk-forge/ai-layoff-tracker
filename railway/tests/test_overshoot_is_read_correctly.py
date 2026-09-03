"""A last-call overshoot is not a brake failure, and the report must say which.

THE DEFECT (2026-09-03). `ops_status [2a]` reported:

    "data-quality spent $0.007 in one run, past its $0.005 ceiling (the ceiling
     that run ran under) - the per-job brake is not holding"

The brake was holding. `spend.metered_call` reads the gate BEFORE a request and
meters AFTER, so the call that crosses the ceiling has already landed and been
billed -- its own docstring says a run "can still only overshoot its ceiling by
a single call, which is the honest bound". Three data-quality runs in the
committed ledger are exactly that, and the plainest is 2026-08-16: ONE call,
$0.00552 against $0.005. A single call cannot bypass a gate, because the first
gate read sees $0.00 spent and must permit it.

The old test was `cost <= ceiling * 1.25` -- a flat pad with no relationship to
what one call costs. It absorbed two of the three and reported the third as a
brake failure, on nothing but how long the model happened to answer. A false
ACTION item in the one place that reports real overshoot is how a real
overshoot later goes unread; it is the same defect class as a health note
saying "scheme changed" for a feed with a bad character in it.

WHAT THIS FILE PINS. The verdict is derived, not chosen: cost < ceiling +
dearest call is the inequality a correctly gated run cannot break, so
structural and bypass are separable exactly, with nothing left to widen. The
mutation tests below are the point of the file -- a guard that has only ever
seen one shape of input has not been shown to discriminate.
"""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", types.SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import spend  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OPS_SRC = (ROOT / "railway/ops_status.py").read_text(encoding="utf-8")


def entry(**kw):
    base = {"job": "data-quality", "date": "2026-09-02", "cost_usd": 0.001,
            "calls": 2, "ceiling_usd": 0.005}
    base.update(kw)
    return base


class TheVerdict(unittest.TestCase):

    def test_within_the_ceiling_is_ok(self):
        self.assertEqual(spend.judge_overshoot(entry())[0], spend.OVERSHOOT_OK)

    def test_a_single_call_over_the_ceiling_is_structural_not_a_failure(self):
        """The 2026-08-16 run, from the committed ledger. One call, $0.00552 of
        a $0.005 ceiling. No gate can prevent the FIRST call of a run."""
        v, why = spend.judge_overshoot(
            entry(date="2026-08-16", calls=1, cost_usd=0.00552))
        self.assertEqual(v, spend.OVERSHOOT_STRUCTURAL, why)
        self.assertNotIn("brake", why.lower())

    def test_the_run_that_raised_the_alarm_is_structural(self):
        """Run 33666038578: 2 calls, $0.006785 of $0.005, truncated after."""
        v, why = spend.judge_overshoot(entry(calls=2, cost_usd=0.006785))
        self.assertEqual(v, spend.OVERSHOOT_STRUCTURAL, why)

    def test_no_committed_ledger_entry_is_a_bypass(self):
        """The forensic sweep of 2026-09-03, kept live. If a real bypass ever
        lands in the committed ledger, this is what says so."""
        ledger = json.loads(
            (ROOT / "railway/spend_jobs.json").read_text(encoding="utf-8"))
        bad = [(e.get("date"), e.get("job"), spend.judge_overshoot(e)[1])
               for e in ledger["entries"]
               if spend.judge_overshoot(e)[0] == spend.OVERSHOOT_BYPASS]
        self.assertEqual(
            bad, [], "a run spent past what a correctly gated run can: "
                     f"{bad}")


class TheAlarmStillFires(unittest.TestCase):
    """MUTATION. A guard that has only ever seen one shape of input has not
    been shown to discriminate."""

    def test_a_real_bypass_is_still_an_alarm(self):
        """Ten calls of $0.002 under a $0.005 ceiling is $0.020 -- the shape of
        a paid call that never reached the gate. The bound (ceiling + dearest
        call = $0.007) is broken, so this is an ALARM, and the message must
        name the two causes worth hunting."""
        v, why = spend.judge_overshoot(
            entry(calls=10, cost_usd=0.020, max_call_usd=0.002))
        self.assertEqual(v, spend.OVERSHOOT_BYPASS, why)
        self.assertIn("metered_call", why)
        self.assertIn("one request", why)

    def test_the_bound_is_the_dearest_call_not_a_percentage(self):
        """The boundary. Same total, same ceiling; only the dearest call moves.
        A pad-based test cannot tell these apart and this one must."""
        over = entry(calls=4, cost_usd=0.0090)
        self.assertEqual(
            spend.judge_overshoot(dict(over, max_call_usd=0.0050))[0],
            spend.OVERSHOOT_STRUCTURAL)
        self.assertEqual(
            spend.judge_overshoot(dict(over, max_call_usd=0.0030))[0],
            spend.OVERSHOOT_BYPASS)

    def test_the_old_flat_percentage_pad_is_gone(self):
        """The pad is what mis-read all three data-quality runs. Its absence
        from ops_status is part of the fix, not an incidental cleanup."""
        self.assertNotIn(
            "1.25", OPS_SRC,
            "ops_status [2a] is judging an overshoot against a percentage pad "
            "again. The bound is the run's dearest call; a pad has no "
            "relationship to what one call costs")


class UnknownStaysUnknown(unittest.TestCase):

    def test_an_unprovable_overshoot_is_uncertain_never_a_pass(self):
        v, why = spend.judge_overshoot(entry(calls=200, cost_usd=0.020))
        self.assertEqual(v, spend.OVERSHOOT_UNCERTAIN, why)
        self.assertIn("UNKNOWN", why)

    def test_a_run_with_no_recorded_ceiling_is_unrecorded(self):
        e = entry(cost_usd=9.0)
        e.pop("ceiling_usd")
        self.assertEqual(spend.judge_overshoot(e)[0],
                         spend.OVERSHOOT_UNRECORDED)

    def test_a_malformed_entry_does_not_raise_and_does_not_pass(self):
        self.assertEqual(spend.judge_overshoot({})[0],
                         spend.OVERSHOOT_UNRECORDED)
        self.assertEqual(
            spend.judge_overshoot({"cost_usd": "x", "ceiling_usd": "y"})[0],
            spend.OVERSHOOT_UNRECORDED)

    def test_a_legacy_uncertain_run_does_not_make_the_session_exit_three(self):
        """A pre-2026-09-03 relic that cannot be judged is PRINTED, never a
        verdict. Two weeks of exit 3 over a run nobody can audit erodes the
        audit exactly as a false ACTION does -- the same reason [2a]'s
        unrecorded-ceiling bucket is printed and not an ACTION. It is
        self-clearing: the UNCERTAIN branch is reachable only for an entry
        with no max_call_usd."""
        src = OPS_SRC[OPS_SRC.index("OVERSHOOT_UNCERTAIN"):]
        self.assertIn(
            'e.get("max_call_usd") is not None', src,
            "[2a] stopped distinguishing a legacy unjudgeable run from one "
            "that records its dearest call and is still unjudgeable")


class TheMeterRecordsTheWidth(unittest.TestCase):

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("ALT_RUN_SPEND_FILE", "ALT_JOB")}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["ALT_RUN_SPEND_FILE"] = str(Path(self.tmp.name) / "run.json")
        os.environ.pop("ALT_JOB", None)
        self.addCleanup(self._restore)
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)

    def _restore(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_the_meter_records_the_dearest_call_not_the_mean(self):
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 100, "completion_tokens": 10})
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 100000, "completion_tokens": 10000})
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            e = spend.record_job_run(job="data-quality", run_id="local-test")
        self.assertGreater(e["max_call_usd"], 0)
        self.assertLess(e["max_call_usd"], e["cost_usd"],
                        "two calls, so the dearest is not the total")
        self.assertGreater(e["max_call_usd"], e["cost_usd"] / e["calls"],
                           "that is the mean, not the dearest")

    def test_the_dearest_call_survives_a_retried_attempt(self):
        """The bound is a statement about the whole LOGICAL run. A second
        attempt that only makes cheap calls must not narrow it and turn a
        retried structural overshoot into a reported bypass.

        This is also the regression test for _persist_run_cost() building its
        payload INSIDE `with open(path, "w")`: open truncates, so the first
        carried read landing there answered 0.0 and silently narrowed both the
        carried spend and this bound to one attempt."""
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 100000, "completion_tokens": 10000})
        dear = spend.logical_run_max_call_usd()
        self.assertGreater(dear, 0)
        spend.reset_run_meter()          # a fresh process: the retry
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 10, "completion_tokens": 1})
        self.assertAlmostEqual(spend.logical_run_max_call_usd(), dear)
        self.assertAlmostEqual(spend.carried_run_cost_usd(), dear)


if __name__ == "__main__":
    unittest.main()
