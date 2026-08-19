"""Guards for the AI-causation gold set: the corpus, the decision rule, the score.

`ai_explicit` is the field this product is named after, and until 2026-08-18
nothing had ever measured the model that sets it. The measurement that now
exists can lie in five specific ways, and each one is pinned here:

  1. scoring the candidate against a key it helped write,
  2. calling a substring match a mention, and so drawing "hard negatives"
     out of the word "maintenance",
  3. letting two disagreeing labellers resolve to a label anyway,
  4. reading a stratified sample's raw rate as the population's,
  5. putting more than one charged request behind one spend-gate read.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_causation_sample_build as build  # noqa: E402


def _load_harness():
    """ab_ai_causation imports extractor, which imports openai. Skip cleanly
    where the SDK is absent rather than failing a suite that has nothing to do
    with it."""
    try:
        import ab_ai_causation
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise unittest.SkipTest(f"openai SDK unavailable: {exc}")
    return ab_ai_causation


class CorpusTests(unittest.TestCase):
    def test_a_substring_is_not_a_mention(self):
        """`/query?keyword=AI` is a SQL LIKE '%AI%' and returns 5,322 rows.
        Drawing the hard-negative stratum from that would fill it with words
        that merely contain the letters, and the stratum whose entire job is to
        catch 'says yes whenever the text says AI' would be measuring nothing.
        """
        for text in ("maintenance staff were cut at the retail chain",
                     "Air France said 400 roles will go",
                     "the plaintiff's claim was dismissed"):
            self.assertIsNone(build.AI_MENTION.search(text), text)

    def test_a_real_mention_is_a_mention(self):
        for text in ("cuts as AI reshapes work",
                     "artificial intelligence took the roles",
                     "increased automation across the plant",
                     "replaced by chatbots",
                     "a machine-learning pipeline now does it"):
            self.assertIsNotNone(build.AI_MENTION.search(text), text)

    def test_strata_split_on_the_stored_flag_then_on_the_language(self):
        long_ai = "the company said AI caused the reduction of staff numbers"
        long_plain = "the company said it would reduce staff numbers this year"
        self.assertEqual(
            build.stratum_of({"ai_explicit": True, "excerpt": long_ai}),
            "A_positive")
        self.assertEqual(
            build.stratum_of({"ai_explicit": False, "excerpt": long_ai}),
            "B_hard_negative")
        self.assertEqual(
            build.stratum_of({"ai_explicit": False, "excerpt": long_plain}),
            "C_plain_negative")

    def test_a_row_with_no_document_is_dropped_not_labelled(self):
        """A verdict on 20 characters measures the sampler, not the model."""
        self.assertIsNone(build.stratum_of({"ai_explicit": True, "excerpt": "Meta"}))
        self.assertIsNone(build.stratum_of({"ai_explicit": False, "excerpt": ""}))

    def test_the_frame_excludes_the_paths_no_model_ever_read(self):
        """62,307 of 64,245 rows are WARN and ERM, bulk-upserted with no LLM in
        the path at all. Including them would make any accuracy figure look
        ~30x better than the classifier is."""
        self.assertNotIn("warn", build.FRAME_SOURCES)
        self.assertNotIn("erm", build.FRAME_SOURCES)

    def test_the_frozen_sample_is_present_and_carries_its_population(self):
        path = build.OUT_PATH
        self.assertTrue(path.exists(), f"{path} is the committed corpus")
        manifest = json.loads(path.read_text())
        self.assertEqual(len(manifest["items"]), sum(manifest["strata_drawn"].values()))
        for stratum, drawn in manifest["strata_drawn"].items():
            # Without the population size a stratified sample cannot be
            # reweighted, and its raw rate would be quoted as the tracker's.
            self.assertGreaterEqual(manifest["strata_population"][stratum], drawn)

    def test_the_stored_answer_is_never_inside_the_document(self):
        """`ai_language` is the stored answer. Handing a candidate the answer
        inside its own prompt is the defect the 2026-08-07 news gold set had to
        rebuild Wayback windows to avoid."""
        manifest = json.loads(build.OUT_PATH.read_text())
        for item in manifest["items"]:
            self.assertNotIn("ai_language", item)
            self.assertIn("ai_language", item["stored"])


class DecisionRuleTests(unittest.TestCase):
    """The harness must score the rule PRODUCTION runs, not a copy of it."""

    def setUp(self):
        try:
            import extractor
        except ImportError as exc:  # pragma: no cover
            raise unittest.SkipTest(f"openai SDK unavailable: {exc}")
        self.extractor = extractor

    def test_a_causal_label_with_no_verbatim_receipt_is_downgraded(self):
        text = "The company cut 300 roles after a weak quarter."
        out = self.extractor.finalize_ai_causation(
            {"ai_causation": "primary_cause",
             "ai_language": "we are replacing them with AI", "confidence": 95},
            text)
        self.assertEqual(out["ai_causation"], "unknown")
        self.assertFalse(self.extractor.ai_explicit_from_causation(out["ai_causation"]))

    def test_a_causal_label_with_a_receipt_stands(self):
        text = ("The company cut 300 roles, saying automation now handles the "
                "work those teams did.")
        out = self.extractor.finalize_ai_causation(
            {"ai_causation": "primary_cause",
             "ai_language": "automation now handles the work", "confidence": 90},
            text)
        self.assertEqual(out["ai_causation"], "primary_cause")
        self.assertTrue(self.extractor.ai_explicit_from_causation(out["ai_causation"]))

    def test_ai_explicit_has_exactly_one_definition(self):
        for cause in ("primary_cause", "contributing_cause"):
            self.assertTrue(self.extractor.ai_explicit_from_causation(cause))
        for cause in ("selection_or_operations", "context_only",
                      "explicitly_denied", "unknown", "nonsense"):
            self.assertFalse(self.extractor.ai_explicit_from_causation(cause))

    def test_the_production_call_still_uses_MODEL_not_CLASSIFY_MODEL(self):
        """The coupling this whole investigation exists to measure must stay
        visible: AI causation rides the EXTRACTION model on purpose."""
        source = Path(self.extractor.__file__).read_text()
        head = source.split("def classify_ai_evidence", 1)[1]
        body = head.split("\ndef ", 1)[0]
        # Comments explain the choice and name both constants; the CODE must
        # name only one of them.
        code = "\n".join(ln for ln in body.splitlines()
                         if not ln.lstrip().startswith("#"))
        self.assertIn("spend.metered_call(MODEL", code)
        self.assertNotIn("CLASSIFY_MODEL", code)


class ScorerTests(unittest.TestCase):
    def setUp(self):
        self.h = _load_harness()

    def test_the_candidate_is_never_one_of_the_labellers(self):
        """A gold set the scored model helped write is right by construction
        everywhere the two labellers agreed, which is most rows. This is the
        circularity guard."""
        self.assertNotIn(self.h.CANDIDATE, self.h.LABELLERS)

    def test_the_two_labellers_are_not_the_same_model_family(self):
        """Two models sharing a lineage agreeing is one observation wearing two
        coats."""
        families = {m.split("/", 1)[0] for m in self.h.LABELLERS}
        self.assertEqual(len(families), len(self.h.LABELLERS))
        self.assertNotIn(self.h.CANDIDATE.split("/", 1)[0], families)

    def test_the_first_labeller_is_the_pre_swap_incumbent(self):
        self.assertEqual(self.h.LABELLERS[0], "deepseek/deepseek-chat")

    def test_an_unlabelled_row_is_scored_nowhere(self):
        """A disagreement is UNADJUDICATED, and a model whose call errored is
        UNKNOWN. Neither may resolve to a silent pass or a silent miss."""
        items = [{"id": 1, "stratum": "A_positive"},
                 {"id": 2, "stratum": "A_positive"},
                 {"id": 3, "stratum": "A_positive"}]
        gold = {1: True}                      # 2 unadjudicated, 3 has no gold
        verdicts = {"m": {1: True, 2: False}}  # 3 errored, so no verdict
        s = self.h.score_model("m", items, gold, verdicts,
                               {"A_positive": 96}, {"A_positive": 3})
        self.assertEqual(s["totals"]["judged"], 1)
        self.assertEqual(s["totals"]["tp"], 1)
        self.assertEqual(s["totals"]["fn"], 0)

    def test_a_stratified_sample_is_reweighted_to_the_population(self):
        """Stratum A is 70 of 96 rows; stratum C is 50 of 1,742. Reading the raw
        pooled rate would let 50 sampled plain negatives speak for 1,742."""
        items = ([{"id": i, "stratum": "A_positive"} for i in range(10)]
                 + [{"id": 100 + i, "stratum": "C_plain_negative"} for i in range(10)])
        gold = {i: True for i in range(10)}
        gold.update({100 + i: False for i in range(10)})
        # Perfect on the oversampled positives, and it calls every plain
        # negative AI. Weighted precision must be dragged far below the
        # unweighted 50%, because the population holds ~17 plain negatives per
        # positive.
        verdicts = {"m": {**{i: True for i in range(10)},
                          **{100 + i: True for i in range(10)}}}
        s = self.h.score_model("m", items, gold, verdicts,
                               {"A_positive": 96, "C_plain_negative": 1742},
                               {"A_positive": 10, "C_plain_negative": 10})
        self.assertIsNotNone(s["precision"][0])
        self.assertLess(s["precision"][0], 0.20)
        # And recall, which lives only where gold is positive, is unaffected.
        self.assertGreater(s["recall"][0], 0.60)

    def test_an_empty_denominator_is_UNKNOWN_and_never_zero(self):
        """A rate of 0.0 reads as a measured zero. Absence of a signal is not
        a pass and it is not a failure either."""
        self.assertEqual(self.h._weighted([]), (None, None, None))
        self.assertEqual(self.h._weighted([(1.0, 0, 0)]), (None, None, None))
        self.assertIn("UNKNOWN", self.h._render((None, None, None)))

    def test_the_interval_is_wilson_and_not_a_bare_percentage(self):
        text = self.h._render(self.h._weighted([(1.0, 53, 53)]))
        self.assertIn("95% CI", text)
        # 53/53 under the normal approximation is [100%, 100%], which reads as
        # certainty from 53 observations.
        self.assertNotIn("[100.0%, 100.0%]", text)

    def test_one_charged_request_sits_behind_one_gate_read(self):
        """A callable that loops or retries inside metered_call puts several
        charges behind one gate check -- the defect that overshot a run ceiling
        by 36 calls on 2026-08-11. Retrying happens by calling ask() again."""
        calls = {"gate": 0, "made": 0}

        class _Msg:
            content = '{"ai_causation":"unknown","ai_language":null,"confidence":0}'

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]
            usage = {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}

        def fake_metered_call(model, make_call, **kwargs):
            calls["gate"] += 1
            return make_call()

        class _Completions:
            @staticmethod
            def create(**kwargs):
                calls["made"] += 1
                return _Resp()

        class _Client:
            chat = type("chat", (), {"completions": _Completions()})()

        spend_mod = self.h.spend
        extractor_mod = self.h.extractor
        real_call, real_client = spend_mod.metered_call, extractor_mod._get_client
        try:
            spend_mod.metered_call = fake_metered_call
            extractor_mod._get_client = lambda: _Client()
            self.h.ask("some/model", "a text long enough to be a document here")
        finally:
            spend_mod.metered_call = real_call
            extractor_mod._get_client = real_client
        self.assertEqual(calls["gate"], 1)
        self.assertEqual(calls["made"], 1)


if __name__ == "__main__":
    unittest.main()
