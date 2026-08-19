"""An unconfirmed recommendation must not be able to reach the score.

THE DEFECT THIS EXISTS FOR
--------------------------
The `ai-causation-2026-08` gold set is labelled by two models where they agree
and BY A HUMAN where they do not. That split is the whole design: a gold set
labelled only by models proves nothing about models, and the 34 rows the
labellers could not settle are exactly the rows where a model's opinion is
worth least.

On 2026-08-19 a session read those 34 rows against the written rubric and
produced 33 recommended rulings. Careful work -- and still a model's reading.
The first draft wrote them into `ai-causation-2026-08.adjudications.json` as
live `id: bool` entries with a `_status: "RECOMMENDATION"` field alongside.
That is a marker, not a guard. `--rescore` is free, calls no model, and prints
a verdict; the next session to run it for an unrelated reason would have got a
confident-looking score built on 33 unconfirmed model rulings, with nothing in
the output saying so. Absence of a signal is not a pass.

So the rulings are PARKED under `rec:` and the parser cannot see them as
rulings. This test is the thing that keeps that true. It does not check that
somebody remembered; it checks the property.

WHY IT DOES NOT GO RED WHEN THE OWNER CONFIRMS
-----------------------------------------------
The invariant is conditional on `_confirmed_by`, not on today's contents:
while nobody has signed the file, nothing in it may score. The day the owner
strips the prefixes and names himself, these tests keep passing, because that
is the confirmation working rather than the guard failing.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REF = Path(__file__).resolve().parents[2] / "docs" / "recall-reference-sets"
ADJ = REF / "ai-causation-2026-08.adjudications.json"
SAMPLE = REF / "ai-causation-2026-08.sample.json"
PARKED_PREFIX = "rec:"


def _load_harness():
    """ab_ai_causation imports extractor, which imports openai. Skip cleanly
    where the SDK is absent, exactly as test_ai_causation_goldset.py does --
    but note that the FIRST test below deliberately needs no import at all, so
    the one assertion that must never be skippable never is."""
    try:
        import ab_ai_causation
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise unittest.SkipTest(f"openai SDK unavailable: {exc}")
    return ab_ai_causation


class TheParkedRulingsCannotScore(unittest.TestCase):

    def test_an_unconfirmed_file_holds_no_live_ruling_at_all(self):
        """The guard, stated so it cannot be skipped.

        Reads nothing but JSON, so no missing SDK can turn this into a pass.
        A bare numeric key IS a ruling to `read_adjudications`; while nobody
        has signed the file there must not be one.
        """
        raw = json.loads(ADJ.read_text())
        if raw.get("_confirmed_by"):
            self.skipTest(f"confirmed by {raw['_confirmed_by']!r}")
        live = [k for k in raw if isinstance(k, str) and k.lstrip("-").isdigit()]
        self.assertEqual(
            live, [],
            "adjudications.json names no _confirmed_by, so a human has ruled "
            "on nothing -- yet these row ids would be folded into the gold set "
            "as the owner's calls by the next `--rescore`, and the score "
            f"printed from them would look measured. Park them under "
            f"'{PARKED_PREFIX}' or have a human sign the file. Do not answer "
            "this failure by editing the test.")
        self.assertTrue(
            [k for k in raw if isinstance(k, str) and k.startswith(PARKED_PREFIX)],
            "an unconfirmed adjudications file holding neither rulings nor "
            "parked recommendations is a silence: the next session cannot "
            "tell pending work from finished work. If the queue is genuinely "
            "empty, say so in _status.")

    def test_the_parser_agrees_that_nothing_here_scores(self):
        """The same property, through the production reader."""
        aic = _load_harness()
        raw = json.loads(ADJ.read_text())
        rulings, parked, _skipped = aic.read_adjudications(ADJ)
        self.assertEqual(aic.PARKED_PREFIX, PARKED_PREFIX)
        if raw.get("_confirmed_by"):
            self.skipTest(f"confirmed by {raw['_confirmed_by']!r}")
        self.assertEqual(rulings, {},
                         "read_adjudications() would hand these to the gold "
                         "set as the owner's calls")
        self.assertEqual(len(parked), 33)

    def test_a_parked_recommendation_is_reported_not_swallowed(self):
        """UNKNOWN is a state to report, not a silence.

        `skipped` keys are noise (the readme, a comment). A parked ruling is
        PENDING WORK and must come back under its own name, so the caller can
        print how many are waiting.
        """
        aic = _load_harness()
        _rulings, parked, skipped = aic.read_adjudications(ADJ)
        self.assertNotIn("rec:70293", skipped)
        self.assertIn(70293, parked)

    def test_stripping_the_prefix_is_what_confirms_a_row(self):
        """Confirming must stay ONE edit, or nobody will do it."""
        aic = _load_harness()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adj.json"
            path.write_text(json.dumps({"rec:70293": True, "rec:26455": False}))
            rulings, parked, _ = aic.read_adjudications(path)
            self.assertEqual(rulings, {})
            self.assertEqual(parked, [26455, 70293])

            path.write_text(json.dumps({"70293": True, "rec:26455": False}))
            rulings, parked, _ = aic.read_adjudications(path)
            self.assertEqual(rulings, {70293: True},
                             "stripping 'rec:' must promote exactly that row")
            self.assertEqual(parked, [26455],
                             "and must leave the others parked")

    def test_a_malformed_line_is_named_never_defaulted(self):
        """One stray line must not quietly discard the file around it."""
        aic = _load_harness()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adj.json"
            path.write_text(json.dumps({
                "_readme": "words",
                "rec:70293": "yes",      # not a bool: not a parked ruling
                "rec:not-a-row": True,   # not a row id
                "306": None,             # not a bool: not a ruling
                "26455": False,          # the only real ruling
            }))
            rulings, parked, skipped = aic.read_adjudications(path)
            self.assertEqual(rulings, {26455: False})
            self.assertEqual(parked, [])
            self.assertEqual(sorted(skipped),
                             ["306", "_readme", "rec:70293", "rec:not-a-row"])

    def test_every_parked_row_is_a_row_in_the_frozen_sample(self):
        """A typo'd id is a ruling that will never land on anything."""
        aic = _load_harness()
        _rulings, parked, _skipped = aic.read_adjudications(ADJ)
        known = {i["id"] for i in json.loads(SAMPLE.read_text())["items"]}
        self.assertEqual([p for p in parked if p not in known], [],
                         "parked recommendation for a row that is not in the "
                         "frozen sample")


if __name__ == "__main__":
    unittest.main(verbosity=2)
