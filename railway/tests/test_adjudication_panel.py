"""The three-model adjudication panel: aggregation truth table and the spend
guarantees, all hermetic.

NO NETWORK, NO REAL SPEND. Every model vote is injected through a fake
`call_model`, and the one place that would build a real client is driven with a
fake `client_factory` and a spy on `spend.metered_call`. The panel is DORMANT
and nothing here arms it.

The two things this file pins:

  1. AGGREGATION is asymmetric on purpose (a false apply on a public headline is
     expensive; a false hold is one click). AUTO_APPLY needs a unanimous CITING
     3-0 UNDER the headline-mover bound; any reject is REJECT; everything else
     holds for the owner.
  2. SPEND obeys CLAUDE.md: every model call goes through spend.metered_call,
     one request per call, the client sets max_retries=0, and PaidReadsOff is
     surfaced (a budget stop is undecided, never a verdict).
"""
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# openai is optional in the module (guarded import); stub it so the import is
# deterministic regardless of whether the SDK is installed in this env.
sys.modules.setdefault("openai", SimpleNamespace(OpenAI=object))

import spend  # noqa: E402
import adjudication_panel as panel  # noqa: E402

RAILWAY = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# A scripted transport: hand each model a canned JSON string.
# --------------------------------------------------------------------------
def _vote_json(approve, quote="the evidence says so", reason="because"):
    import json
    return json.dumps({"approve": approve, "cited_quote": quote, "reason": reason})


def scripted(votes_by_model):
    """Return a call_model(model, system, user) that replays canned content.

    `votes_by_model` maps model name -> raw content string. Records every call
    so tests can assert exactly three votes were gathered.
    """
    calls = []

    def call_model(model, system, user):
        calls.append((model, system, user))
        return votes_by_model[model]

    call_model.calls = calls
    return call_model


THREE = ("a/one", "b/two", "c/three")

EVIDENCE = {"source_name": "wire", "url": "https://x.invalid",
            "excerpt": "The employer said the cuts were driven by AI."}
CHANGE = {"field": "ai_explicit", "old": "false", "new": "true"}


class AggregationTruthTable(unittest.TestCase):
    """The asymmetric gate, one row of the table per test."""

    def _run(self, raws, job_count=100):
        by_model = dict(zip(THREE, raws))
        cm = scripted(by_model)
        v = panel.adjudicate("did the employer name AI?", EVIDENCE, CHANGE,
                             job_count=job_count, models=THREE, call_model=cm)
        self.assertEqual(len(cm.calls), 3, "the panel must poll all three models")
        return v

    def test_unanimous_citing_approve_under_bound_auto_applies(self):
        v = self._run([_vote_json(True), _vote_json(True), _vote_json(True)],
                      job_count=100)
        self.assertEqual(v.verdict, panel.AUTO_APPLY)
        self.assertTrue(v.unanimous)
        self.assertFalse(v.is_headline_mover)
        self.assertEqual(v.approve_tally, "3-0")

    def test_unanimous_citing_approve_but_headline_mover_holds(self):
        v = self._run([_vote_json(True), _vote_json(True), _vote_json(True)],
                      job_count=5000)
        self.assertEqual(v.verdict, panel.HOLD_FOR_REVIEW)
        self.assertTrue(v.unanimous, "still 3-0 -- the tally rides along as confidence")
        self.assertTrue(v.is_headline_mover)

    def test_headline_mover_bound_is_inclusive_at_5000(self):
        under = self._run([_vote_json(True)] * 3, job_count=4999)
        at = self._run([_vote_json(True)] * 3, job_count=5000)
        self.assertEqual(under.verdict, panel.AUTO_APPLY)
        self.assertEqual(at.verdict, panel.HOLD_FOR_REVIEW)

    def test_two_one_non_citing_approve_holds_not_rejects(self):
        # Two clean citing approves, one approve with an EMPTY cited_quote.
        # No explicit reject, but not unanimous-clean -> HOLD.
        raws = [_vote_json(True), _vote_json(True), _vote_json(True, quote="")]
        v = self._run(raws, job_count=100)
        self.assertEqual(v.verdict, panel.HOLD_FOR_REVIEW)
        self.assertTrue(v.unanimous, "all three approved (3-0), but one did not cite")
        self.assertFalse(v.votes[2].cited)

    def test_any_reject_is_reject(self):
        raws = [_vote_json(True), _vote_json(True), _vote_json(False)]
        v = self._run(raws, job_count=100)
        self.assertEqual(v.verdict, panel.REJECT)
        self.assertFalse(v.unanimous)
        self.assertEqual(v.approve_tally, "2-1")

    def test_a_single_reject_beats_two_clean_approves(self):
        raws = [_vote_json(True), _vote_json(False), _vote_json(True)]
        self.assertEqual(self._run(raws).verdict, panel.REJECT)

    def test_all_reject_is_reject(self):
        raws = [_vote_json(False)] * 3
        v = self._run(raws)
        self.assertEqual(v.verdict, panel.REJECT)
        self.assertEqual(v.approve_tally, "0-3")

    def test_approve_without_citation_is_not_a_clean_approve(self):
        # Every model approves but NONE cites -> not unanimous-clean, no reject.
        raws = [_vote_json(True, quote="")] * 3
        v = self._run(raws, job_count=100)
        self.assertEqual(v.verdict, panel.HOLD_FOR_REVIEW)
        self.assertTrue(all(not vote.cited for vote in v.votes))

    def test_an_unparseable_vote_holds_it_never_rejects_alone(self):
        raws = [_vote_json(True), _vote_json(True), "the model rambled, no json"]
        v = self._run(raws, job_count=100)
        self.assertEqual(v.verdict, panel.HOLD_FOR_REVIEW)
        self.assertIsNone(v.votes[2].approve)
        self.assertFalse(v.votes[2].is_reject)


class Parsing(unittest.TestCase):
    def test_empty_cited_quote_is_non_citing(self):
        vote = panel.parse_vote("m", _vote_json(True, quote="   "))
        self.assertTrue(vote.approve)
        self.assertFalse(vote.cited)

    def test_json_embedded_in_prose_is_recovered(self):
        raw = 'Sure, here is my decision:\n{"approve": true, "cited_quote": "x", "reason": "y"}\nThanks!'
        vote = panel.parse_vote("m", raw)
        self.assertTrue(vote.approve)
        self.assertTrue(vote.cited)

    def test_non_boolean_approve_is_a_no_vote(self):
        vote = panel.parse_vote("m", '{"approve": "yes", "cited_quote": "x"}')
        self.assertIsNone(vote.approve)
        self.assertTrue(vote.error)


class DogeFixtureWouldHaveBeenKilled(unittest.TestCase):
    """The real held case: three rejects -> REJECT, the bad relabel dies."""

    def test_three_rejects_return_reject(self):
        fx = panel.DOGE_FIXTURE
        raws = [_vote_json(False, quote="carried out by federal agencies",
                           reason="the cuts were US federal, not aerospace")
                for _ in THREE]
        cm = scripted(dict(zip(THREE, raws)))
        rel = fx["relabels"][0]  # industry -> Aerospace & Defense
        v = panel.adjudicate_relabel(fx["row"], rel["field"], rel["old"],
                                     rel["new"], fx["evidence"],
                                     models=THREE, call_model=cm)
        self.assertEqual(v.verdict, panel.REJECT)
        self.assertTrue(v.is_headline_mover, "60,000 jobs is well over the bound")
        self.assertEqual(len(cm.calls), 3)

    def test_the_headline_mover_never_auto_applies_even_if_approved(self):
        fx = panel.DOGE_FIXTURE
        raws = [_vote_json(True, quote="Pentagon was among the departments")
                for _ in THREE]
        cm = scripted(dict(zip(THREE, raws)))
        rel = fx["relabels"][0]
        v = panel.adjudicate_relabel(fx["row"], rel["field"], rel["old"],
                                     rel["new"], fx["evidence"],
                                     models=THREE, call_model=cm)
        self.assertEqual(v.verdict, panel.HOLD_FOR_REVIEW)


# --------------------------------------------------------------------------
# Spend guarantees
# --------------------------------------------------------------------------
class _FakeClient:
    """Records each chat.completions.create call as one request."""

    def __init__(self, content='{"approve": true, "cited_quote": "x", "reason": "y"}'):
        self.requests = []
        self._content = content

        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.requests.append(kwargs)
                return SimpleNamespace(
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(content=outer._content))],
                    usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0,
                                          cost=0.0004))
        self.chat = SimpleNamespace(completions=_Completions())


class TheDefaultCallGoesThroughMeteredCall(unittest.TestCase):
    """Every paid call is gated and metered, one request per metered_call."""

    def setUp(self):
        self._key = os.environ.get("OPENROUTER_API_KEY")
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        self.addCleanup(self._restore_key)
        self._real_metered = spend.metered_call
        self.metered_calls = 0

        def spy(model, make_call, **kwargs):
            self.metered_calls += 1
            return self._real_metered(model, make_call, **kwargs)

        spend.metered_call = spy
        self.addCleanup(lambda: setattr(spend, "metered_call", self._real_metered))
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        spend._prices_fetched = True
        os.environ["ALT_RUN_CEILING_USD"] = "1.00"
        self.addCleanup(lambda: os.environ.pop("ALT_RUN_CEILING_USD", None))

    def _restore_key(self):
        if self._key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = self._key

    def test_one_request_per_metered_call(self):
        client = _FakeClient()
        raw = panel._default_call_model(
            "test/model", "sys", "user", client_factory=lambda: client)
        self.assertEqual(self.metered_calls, 1, "the vote must be metered")
        self.assertEqual(len(client.requests), 1,
                         "exactly one request per metered_call")
        self.assertIn("approve", raw)

    def test_the_full_panel_meters_every_vote(self):
        # Drive adjudicate() through the DEFAULT call path with a fake client
        # per model, and confirm three metered calls, one request each.
        clients = {}

        def call_model(model, system, user):
            c = _FakeClient()
            clients[model] = c
            return panel._default_call_model(
                model, system, user, client_factory=lambda: c)

        panel.adjudicate("q", EVIDENCE, CHANGE, job_count=100,
                         models=THREE, call_model=call_model)
        self.assertEqual(self.metered_calls, 3)
        self.assertEqual([len(c.requests) for c in clients.values()], [1, 1, 1])

    def test_paid_reads_off_is_surfaced_not_swallowed(self):
        os.environ["ALT_PAID_READS"] = "off"
        self.addCleanup(lambda: os.environ.pop("ALT_PAID_READS", None))
        client = _FakeClient()
        with self.assertRaises(spend.PaidReadsOff):
            panel._default_call_model("test/model", "s", "u",
                                      client_factory=lambda: client)
        self.assertEqual(len(client.requests), 0,
                         "no request may go out once paid reads are off")

    def test_adjudicate_lets_a_budget_stop_propagate_as_no_verdict(self):
        # A PaidReadsOff from a vote must NOT be converted into a REJECT or a
        # HOLD -- the panel reached no verdict and the caller must requeue.
        def refusing_call_model(model, system, user):
            raise spend.PaidReadsOff("brake is down")

        with self.assertRaises(spend.PaidReadsOff):
            panel.adjudicate("q", EVIDENCE, CHANGE, job_count=100,
                             models=THREE, call_model=refusing_call_model)


class TheClientDisablesSdkRetries(unittest.TestCase):
    """max_retries=0: the SDK default of 2 re-POSTs from inside the metered
    callable on a timeout, an unmetered charge (CLAUDE.md)."""

    def test_openai_is_constructed_with_max_retries_zero(self):
        text = (RAILWAY / "adjudication_panel.py").read_text()
        matches = list(re.finditer(r"OpenAI\s*\(", text))
        self.assertTrue(matches, "expected an OpenAI(...) construction to guard")
        for m in matches:
            depth, i = 0, m.end() - 1
            while i < len(text):
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            args = text[m.end():i]
            self.assertRegex(
                args, r"max_retries\s*=\s*0",
                "adjudication_panel builds an OpenAI client without "
                "max_retries=0 -- the SDK will re-POST from inside the metered "
                "callable, an unmetered charge")

    def test_the_meter_context_is_the_panel_source_tag(self):
        self.assertEqual(panel.PANEL_SOURCE, "panel")


class Configuration(unittest.TestCase):
    def test_three_distinct_providers_by_default(self):
        providers = [m.split("/")[0] for m in panel._DEFAULT_PANEL_MODELS]
        self.assertEqual(len(providers), 3)
        self.assertEqual(len(set(providers)), 3,
                         "the default panel must be three DIFFERENT providers, "
                         "or 'independent' is a false claim")

    def test_env_override_parses_a_comma_list(self):
        prev = os.environ.get("ALT_PANEL_MODELS")
        os.environ["ALT_PANEL_MODELS"] = " x/a , y/b ,z/c "
        try:
            self.assertEqual(panel._panel_models(), ("x/a", "y/b", "z/c"))
        finally:
            if prev is None:
                os.environ.pop("ALT_PANEL_MODELS", None)
            else:
                os.environ["ALT_PANEL_MODELS"] = prev

    def test_headline_mover_bound_matches_held_relabel_bound(self):
        self.assertEqual(panel.HEADLINE_MOVER_JOBS, 5000)


if __name__ == "__main__":
    unittest.main()
