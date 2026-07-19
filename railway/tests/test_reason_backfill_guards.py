"""Reason-tag backfill: vocabulary, evidence and scheduling guardrails."""
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Unit tests exercise pure guardrails and do not create an API client.
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

from extractor import ALLOWED_REASON_TAGS, _validate_reason_result
from reason_backfill import (
    ERM_TYPE_TAGS,
    NON_WARN_SOURCES,
    erm_template_tags,
    rotating_slice,
)

ROOT = Path(__file__).resolve().parents[2]
WORKER = (ROOT / "railway/reason_backfill.py").read_text()
WORKFLOW = (ROOT / ".github/workflows/reason-backfill.yml").read_text()
CPT_PHP = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/cpt.php").read_text()


def erm_excerpt(rtype, company="Acme GmbH", country="Germany", jobs="1,230", factsheet="78221"):
    return (f"{rtype} at {company} ({country}): {jobs} announced job losses. "
            f"Recorded by the European Restructuring Monitor (Eurofound), "
            f"factsheet {factsheet}.")


class VocabularyParity(unittest.TestCase):
    def test_python_vocabulary_matches_the_plugin(self):
        # The /edit endpoint intersects submitted tags with the PHP
        # vocabulary; drift would silently drop tags server-side.
        match = re.search(r"function alt_allowed_reason_tags\(\).*?return array\((.*?)\);",
                          CPT_PHP, re.S)
        self.assertIsNotNone(match)
        php_tags = set(re.findall(r"'([a-z_]+)'", match.group(1)))
        self.assertEqual(php_tags, ALLOWED_REASON_TAGS)

    def test_erm_type_map_stays_inside_the_vocabulary(self):
        for tags in ERM_TYPE_TAGS.values():
            self.assertTrue(set(tags) <= ALLOWED_REASON_TAGS, tags)


class ErmTemplateMapping(unittest.TestCase):
    def _row(self, excerpt, source_type="erm"):
        return {"source_type": source_type, "excerpt": excerpt}

    def test_mapped_types_tag_deterministically(self):
        # The exact casings observed in the live Eurofound CSV, plus variants:
        # the type match must be case-insensitive.
        expected = {
            "Internal restructuring": ["restructuring"],
            "Merger/Acquisition": ["merger_acquisition"],
            "Merger/acquisition": ["merger_acquisition"],
            "Offshoring/Delocalisation": ["offshoring"],
            "Offshoring/delocalisation": ["offshoring"],
        }
        for rtype, tags in expected.items():
            matched, got = erm_template_tags(self._row(erm_excerpt(rtype)))
            self.assertTrue(matched, rtype)
            self.assertEqual(got, tags, rtype)

    def test_types_without_a_vocabulary_equivalent_stay_untagged(self):
        # Closure/Bankruptcy/etc. name no fixed-vocabulary reason; tagging
        # them would be inference, and they must not consume model calls.
        for rtype in ("Closure", "Bankruptcy", "Outsourcing", "Relocation",
                      "Business expansion", "Restructuring"):
            matched, got = erm_template_tags(self._row(erm_excerpt(rtype)))
            self.assertTrue(matched, rtype)
            self.assertEqual(got, [], rtype)

    def test_freeform_excerpts_never_match_the_template(self):
        news = ("Closure at the plant was announced Tuesday; the company said "
                "falling revenue forced 1,200 job cuts across three sites.")
        self.assertEqual(erm_template_tags(self._row(news)), (False, []))
        # The Eurofound attribution tail is part of the anchor.
        truncated = "Closure at Acme GmbH (Germany): 1,230 announced job losses."
        self.assertEqual(erm_template_tags(self._row(truncated)), (False, []))

    def test_non_erm_rows_never_match_even_with_a_template_excerpt(self):
        row = self._row(erm_excerpt("Internal restructuring"), source_type="news")
        self.assertEqual(erm_template_tags(row), (False, []))


class ModelReplyValidation(unittest.TestCase):
    def test_unknown_tags_are_dropped_and_order_kept(self):
        result = _validate_reason_result(
            {"reason_tags": ["cost_reduction", "downsizing", "restructuring",
                             "cost_reduction"], "ai_evidence": None},
            "cuts to reduce costs during a broad restructuring")
        self.assertEqual(result, {"reason_tags": ["cost_reduction", "restructuring"]})

    def test_malformed_replies_are_model_failures_not_empty_skips(self):
        for bad in (None, [], {"reason_tags": "restructuring"}, {"tags": []}):
            self.assertIsNone(_validate_reason_result(bad, "text"))

    def test_ai_automation_requires_the_employers_quote_in_the_excerpt(self):
        excerpt = ("The CEO said the reduction reflects efficiencies from "
                   "artificial intelligence across support teams.")
        supported = _validate_reason_result(
            {"reason_tags": ["ai_automation"],
             "ai_evidence": "efficiencies from artificial intelligence"}, excerpt)
        self.assertEqual(supported, {"reason_tags": ["ai_automation"]})
        invented = _validate_reason_result(
            {"reason_tags": ["ai_automation", "cost_reduction"],
             "ai_evidence": "AI replaced the whole division"}, excerpt)
        self.assertEqual(invented, {"reason_tags": ["cost_reduction"]})

    def test_possible_ai_needs_no_quote_gate(self):
        result = _validate_reason_result(
            {"reason_tags": ["possible_ai"], "ai_evidence": None},
            "Analysts tied the cuts to automation pressure.")
        self.assertEqual(result, {"reason_tags": ["possible_ai"]})

    def test_no_reason_is_a_definitive_empty_result(self):
        self.assertEqual(_validate_reason_result({"reason_tags": []}, "text"),
                         {"reason_tags": []})


class SchedulingGuards(unittest.TestCase):
    def test_warn_rows_are_structurally_excluded(self):
        self.assertNotIn("warn", NON_WARN_SOURCES.split(","))
        self.assertIn('row.get("source_type") == "warn"', WORKER)

    def test_rotation_covers_every_page_and_is_deterministic(self):
        rows = list(range(10))
        slices = [rotating_slice(rows, 4, day) for day in range(3)]
        self.assertEqual(slices, [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]])
        self.assertEqual(rotating_slice(rows, 4, 3), [0, 1, 2, 3])  # wraps
        self.assertEqual(rotating_slice([], 4, 1), [])

    def test_worker_stops_between_rows_before_actions_limit(self):
        self.assertIn("REASON_BACKFILL_DEADLINE_SECONDS", WORKER)
        self.assertIn("time.monotonic() - started_at >= DEADLINE_SECONDS", WORKER)
        self.assertIn("stopping safely after", WORKER)

    def test_scheduled_workflow_has_safe_bounds_and_fails_loudly(self):
        self.assertIn("REASON_BACKFILL_DEADLINE_SECONDS: '900'", WORKFLOW)
        self.assertIn("OPENROUTER_TIMEOUT_SECONDS: '35'", WORKFLOW)
        self.assertIn("concurrency", WORKFLOW)
        self.assertIn("set -o pipefail", WORKFLOW)

    def test_edits_go_through_the_pinning_corrections_endpoint(self):
        self.assertIn("/wp-json/layoffs/v1/edit", WORKER)
        self.assertIn("raise_for_status", WORKER)
        # Vocabulary drift at the server must raise, not quietly no-op.
        self.assertIn("vocabulary drift", WORKER)


if __name__ == "__main__":
    unittest.main()
