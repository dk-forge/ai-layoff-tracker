"""DeepSeek is banned in this repo. The owner ruled it out on EU grounds
months before 2026-09-03, and CLAUDE.md's "No DeepSeek (EU)" note says so --
but that rule lived in a memory file, not in a test, and it was still wired
into SIX live call sites when the Grupo Volkswagen panel error (2026-09-03)
forced someone to actually look:

    extractor.CLASSIFY_MODEL default            (industry/roles/reason/context)
    dedupe_llm.MODEL default                     (cross-source dedup, daily cron)
    adjudication_panel._DEFAULT_PANEL_MODELS     (the held-relabel panel)
    daily_classification_spotcheck.SPOTCHECK_MODEL (flag + confirm passes)
    ai_evidence_sweep.AI_CAUSATION_MODEL         (AI-quote hunt, daily cron)
    process_tips.py / source_verification_audit.py (second-pass confirmations)

Two of those are a DELIBERATE, DOCUMENTED exception: `ab_ai_causation.py`'s
AIC_LABELLERS and `ab_extraction_models.py`'s DEFAULT_MODELS both name
deepseek/deepseek-chat as the historical PRE-SWAP INCUMBENT for a recorded
measurement -- renaming that would falsify what the measurement compared
against. Both are manual-dispatch-only workflows (never scheduled), so a
live DeepSeek call from them requires a human to explicitly run one.

This test is the guard CLAUDE.md's "prove every guard by MUTATION" rule asks
for: it does not just check today's five defaults, it re-derives "does this
production module carry a live DeepSeek default" from the module's own
attributes, so a REINTRODUCED default -- not just the ones fixed today --
trips it too.
"""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[2]

# Files where a live deepseek/* default would be a compliance violation: every
# production module that has ever made (or could make) a paid model call, and
# is NOT one of the two documented historical-measurement exceptions below.
LIVE_MODULES = (
    "extractor",
    "dedupe_llm",
    "adjudication_panel",
    "daily_classification_spotcheck",
    "ai_evidence_sweep",
    "process_tips",
    "source_verification_audit",
)

# Deliberately excluded: named historical incumbents in a recorded A/B
# measurement, manual-dispatch-only (.github/workflows/ab-*.yml), never
# scheduled. Renaming the incumbent there falsifies what was measured; see
# each module's own docstring.
DOCUMENTED_EXCEPTIONS = {"ab_ai_causation.py", "ab_extraction_models.py"}

# spend.py's FALLBACK_PRICES table is a generic $/token lookup keyed by every
# model this project or its tests have ever priced (openai, google, deepseek
# alike) -- it is a price BOOK, not a call site, and pricing a model is not
# the same as defaulting to it. Excluded from the literal sweep for that
# reason, same as the two A/B harnesses above but for a different one.
NOT_A_CALL_SITE = {"spend.py"}


def _clean_import(name):
    """Import (or reload) `name` with every model-choosing env var cleared, so
    a locally-exported OPENROUTER_* variable cannot hide a bad default."""
    scrub = {k: v for k, v in os.environ.items()
             if not k.startswith("OPENROUTER") and k != "ALT_PANEL_MODELS"}
    with mock.patch.dict(os.environ, scrub, clear=True):
        if name in sys.modules:
            return importlib.reload(sys.modules[name])
        return importlib.import_module(name)


class NoLiveModuleDefaultsToDeepSeek(unittest.TestCase):
    """Each module's OWN notion of "the model I'd call with no override" must
    not be deepseek/*. Reads the actual attribute, not a copy of the string,
    so a future edit that changes the attribute name without changing the
    literal still gets caught by whichever test below reads that attribute.
    """

    def test_extractor_classify_model(self):
        mod = _clean_import("extractor")
        self.assertNotIn("deepseek", mod.CLASSIFY_MODEL.lower())

    def test_extractor_extraction_model_too(self):
        # Not the point of this incident, but a regression here would be
        # worse (the correctness-critical surface), so pin it while we're here.
        mod = _clean_import("extractor")
        self.assertNotIn("deepseek", mod.MODEL.lower())

    def test_dedupe_llm_model(self):
        mod = _clean_import("dedupe_llm")
        self.assertNotIn("deepseek", mod.MODEL.lower())

    def test_adjudication_panel_default_models(self):
        mod = _clean_import("adjudication_panel")
        for m in mod._DEFAULT_PANEL_MODELS:
            self.assertNotIn("deepseek", m.lower(),
                             f"the panel's default roster still names {m}")

    def test_daily_classification_spotcheck_model(self):
        mod = _clean_import("daily_classification_spotcheck")
        self.assertNotIn("deepseek", mod.SPOTCHECK_MODEL.lower())

    def test_ai_evidence_sweep_model(self):
        mod = _clean_import("ai_evidence_sweep")
        self.assertNotIn("deepseek", mod.AI_CAUSATION_MODEL.lower())

    def test_process_tips_tracks_extractor_model(self):
        mod = _clean_import("process_tips")
        self.assertNotIn("deepseek", mod.extractor.MODEL.lower())

    def test_source_verification_audit_model(self):
        mod = _clean_import("source_verification_audit")
        self.assertNotIn("deepseek", mod.AUDIT_MODEL.lower())


class StaticSweepCatchesAReintroducedLiteral(unittest.TestCase):
    """Belt-and-suspenders on the attribute checks above: no *.py file under
    railway/ (outside the documented exceptions and tests/) may carry a
    quoted "deepseek..." string literal at all -- catching a NEW call site
    that hardcodes the model inline rather than reading a module attribute,
    which the attribute-level tests above cannot see.
    """

    def test_no_quoted_deepseek_literal_outside_the_documented_exceptions(self):
        """A CODE literal, not a comment mentioning history. This project's
        own convention is to document a compliance fix in a comment right
        next to the code it fixed ("was deepseek/deepseek-chat until ..."),
        and several of those comments quote the old literal on purpose, for a
        human reading the diff. Flagging prose would either fail on every
        honest changelog comment or train people to write dishonest ones, so
        only a line that is CODE (not a bare '#'-comment line) counts.
        """
        import re
        pattern = re.compile(r'''["']deepseek''', re.I)
        skip = DOCUMENTED_EXCEPTIONS | NOT_A_CALL_SITE
        railway_dir = REPO / "railway"
        offenders = []
        for path in sorted(railway_dir.glob("*.py")):
            if path.name in skip:
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if line.strip().startswith("#"):
                    continue           # a comment, not executable code
                if pattern.search(line):
                    offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "a quoted deepseek/* string literal exists in CODE outside the "
            "documented exceptions "
            f"({sorted(skip)}):\n  " + "\n  ".join(offenders))


class TheDocumentedExceptionsStayNarrow(unittest.TestCase):
    """The two A/B harnesses ARE allowed to name deepseek/deepseek-chat, but
    only as the historical incumbent, and only behind manual dispatch. If
    either workflow ever gains a `schedule:` trigger, the exception stops
    being "a human explicitly asked for a historical comparison" and starts
    being "DeepSeek runs on a timer" -- which is exactly what this whole
    guard exists to prevent. Mutating either workflow to add a schedule must
    fail this.
    """

    def test_the_ab_workflows_have_no_schedule_trigger(self):
        import yaml  # available: PyYAML ships with the full requirements lock
        for wf in ("ab-ai-causation.yml", "ab-extraction-models.yml"):
            path = REPO / ".github" / "workflows" / wf
            self.assertTrue(path.exists(), f"{wf} is missing")
            with open(path, encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            # YAML parses the bare key `on:` as the boolean True.
            triggers = doc.get("on") or doc.get(True) or {}
            self.assertNotIn(
                "schedule", triggers,
                f"{wf} gained a schedule trigger -- it names deepseek/deepseek-chat "
                "as a historical incumbent ONLY because it is manual-dispatch-only; "
                "a scheduled run would call DeepSeek unattended, which the owner's "
                "compliance ruling does not allow.")


if __name__ == "__main__":
    unittest.main()
