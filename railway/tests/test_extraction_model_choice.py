"""Which model this project pays for, and what moves when that changes.

`OPENROUTER_MODEL` is read in three places and only ONE of them has ever been
scored against an answer key:

    extractor.MODEL           full extraction + AI causation   MEASURED
    extractor.CLASSIFY_MODEL  industry, roles, reason, context UNMEASURED
    dedupe_llm.ask_llm        which rows are one event         UNMEASURED

Until 2026-08-07 `CLASSIFY_MODEL` defaulted to `MODEL`, so a swap decided by an
extraction benchmark moved a classifier that benchmark never looked at, and the
separate literal in `dedupe_llm` quietly did not move at all. Three surfaces
changed, one measured, and nothing said so.

Both are legitimate decisions. Neither was being made on purpose, and that is
what this file fixes: the extraction model moves because two gold sets say it
may, and the two unmeasured surfaces stay put until something measures them.

2026-09-03: both unmeasured surfaces moved anyway, off deepseek/deepseek-chat,
because the owner's compliance ruling against DeepSeek (EU grounds, months
old) is not conditional on a surface having its own benchmark. They now share
`extractor.MODEL`'s already-measured default (google/gemini-2.5-flash-lite) --
the nearest thing to "no opinion yet" this project has, since it is the one
model actually scored on this project's layoff text and it beat deepseek-chat
on cost at equal accuracy. A dedicated classify-path / dedup-path A/B is still
open work; UNMEASURED_SURFACE_MODEL names what holds the seat until it exists.

A note on the pre-extraction gate: `GATE_MODEL` has always had its own default
and is deliberately untouched here.
"""
import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# What the A/B decided, on the SEC Item 2.05 set (2026-08-06) and the
# corroborated news set (2026-08-07): level on accuracy, 0.387x the price.
MEASURED_EXTRACTION_MODEL = "google/gemini-2.5-flash-lite"
# What the unmeasured surfaces keep until they have a benchmark of their own.
# Was deepseek/deepseek-chat until 2026-09-03; moved off it on compliance
# grounds (owner's DeepSeek ruling, EU), not because a benchmark ran. Both
# unmeasured surfaces now share the one model this project HAS measured on
# layoff text, so the value is identical to MEASURED_EXTRACTION_MODEL -- kept
# as a separate name because the two constants mean different things (one is
# earned by a gold set, one is a placeholder that happens to be the same
# model) and a future classify/dedup A/B may move this one without touching
# extraction.
UNMEASURED_SURFACE_MODEL = "google/gemini-2.5-flash-lite"

_MODEL_ENV = ("OPENROUTER_MODEL", "OPENROUTER_CLASSIFY_MODEL", "OPENROUTER_GATE_MODEL")


def _extractor_with(**env):
    """Reload extractor under a controlled environment. The module reads its
    model names at import, so the environment has to be set before the reload
    and the module has to be restored afterwards."""
    clean = {k: v for k, v in os.environ.items() if k not in _MODEL_ENV}
    clean.update(env)
    with mock.patch.dict(os.environ, clean, clear=True):
        import extractor
        return importlib.reload(extractor)


class ModelChoiceTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        _extractor_with()          # leave the module as the next test finds it

    def test_the_shipped_extraction_default_is_the_model_the_gold_sets_chose(self):
        self.assertEqual(_extractor_with().MODEL, MEASURED_EXTRACTION_MODEL)

    def test_moving_the_extraction_model_does_not_move_the_classifier(self):
        # The whole point. An extraction benchmark may not relabel every row's
        # industry as a side effect.
        mod = _extractor_with(OPENROUTER_MODEL="some/other-model")
        self.assertEqual(mod.MODEL, "some/other-model")
        self.assertEqual(mod.CLASSIFY_MODEL, UNMEASURED_SURFACE_MODEL)

    def test_the_classifier_still_has_its_own_override(self):
        mod = _extractor_with(OPENROUTER_CLASSIFY_MODEL="some/classifier")
        self.assertEqual(mod.CLASSIFY_MODEL, "some/classifier")

    def test_the_pre_extraction_gate_is_independent_of_both(self):
        mod = _extractor_with(OPENROUTER_MODEL="some/other-model")
        self.assertEqual(mod.GATE_MODEL, "google/gemini-2.5-flash-lite")
        mod = _extractor_with(OPENROUTER_GATE_MODEL="some/gate")
        self.assertEqual(mod.GATE_MODEL, "some/gate")

    def test_the_dedup_judge_is_the_third_reader_and_it_did_not_move_either(self):
        """dedupe_llm cannot import extractor (it is deliberately stdlib-only,
        no openai), so its default is a second copy. Asserted through the
        request it actually builds, not by reading the source, because the
        source is where a copy drifts silently."""
        import dedupe_llm
        captured = {}

        class _Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b'{"choices":[{"message":{"content":"{}"}}]}'

        def _urlopen(req, timeout=None):
            captured["model"] = json.loads(req.data)["model"]
            return _Resp()

        clean = {k: v for k, v in os.environ.items() if k not in _MODEL_ENV}
        with mock.patch.dict(os.environ, clean, clear=True), \
                mock.patch.object(dedupe_llm.urllib.request, "urlopen", _urlopen):
            dedupe_llm.ask_llm([{"id": 1, "company_name": "Acme", "job_count": 5,
                                 "layoff_date": "2026-08-01", "source_name": "x",
                                 "excerpt": "Acme cut 5 jobs."}])
        self.assertEqual(captured.get("model"), UNMEASURED_SURFACE_MODEL)


if __name__ == "__main__":
    unittest.main()
