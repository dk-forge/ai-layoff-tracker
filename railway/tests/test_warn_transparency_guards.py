"""Static guardrails for the separate, non-accusatory WARN register."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DB = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()
DOC = (ROOT / "docs/WARN_TRANSPARENCY_DATASET.md").read_text()
BUILDER = (ROOT / "railway/warn_transparency_evidence.py").read_text()
STAGE1 = (ROOT / "docs/WARN_TRANSPARENCY_STAGE1.md").read_text()


class WarnTransparencyGuards(unittest.TestCase):
    def test_register_is_separate_from_layoff_totals(self):
        self.assertIn("alt_warn_transparency", DB)
        self.assertIn("joined to layoff tables or aggregate endpoints", DB)
        self.assertIn("not included in layoff or AI totals", DB)

    def test_only_court_status_may_call_an_employer_a_violation(self):
        self.assertIn("court_adjudicated_warn_violation", DB)
        self.assertIn("court/adjudication URL and evidence excerpt", DB)
        self.assertIn("short_notice_unresolved", DB)
        self.assertIn("explicitly not a violation label", DOC)

    def test_writer_requires_primary_source_evidence(self):
        start = DB.index("function alt_api_warn_transparency_post")
        body = DB[start: DB.index("function alt_api_trash", start)]
        self.assertIn("source name/URL and a non-trivial evidence excerpt", body)
        self.assertIn("hash('sha256', $excerpt)", body)
        self.assertNotIn("alt_db_upsert", body)


class Stage1EvidenceBuilderGuards(unittest.TestCase):
    """Static guards over the stage-1 arithmetic builder and its spec doc."""

    def test_builder_emits_only_observation_labels_never_verdicts(self):
        import importlib
        import sys
        sys.path.insert(0, str(ROOT / "railway"))
        wte = importlib.import_module("warn_transparency_evidence")
        self.assertEqual(wte.STATUTORY_NOTICE_DAYS, 60)
        for label in wte.OBSERVATION_LABELS:
            for banned in ("violation", "non_compliant", "noncompliant",
                           "illegal", "unlawful"):
                self.assertNotIn(banned, label)
        # The court label is manual-only; the builder must not know it.
        self.assertNotIn("court_adjudicated_warn_violation", BUILDER)

    def test_builder_is_offline_and_write_free(self):
        # Arithmetic only: no HTTP client, no API key, no register writes.
        self.assertNotIn("import requests", BUILDER)
        self.assertNotIn("urllib", BUILDER)
        self.assertNotIn("WP_API_KEY", BUILDER)
        self.assertNotIn("X-Layoff-API-Key", BUILDER)

    def test_builder_documents_the_no_imputation_and_amendment_rules(self):
        self.assertIn("NO IMPUTATION", BUILDER)
        self.assertIn("EARLIEST recorded notice", BUILDER)
        self.assertIn("never a verdict", BUILDER)

    def test_stage1_doc_keeps_the_no_verdict_invariant(self):
        self.assertIn("no employer is ever\nlabeled non-compliant", STAGE1)
        self.assertIn("never a verdict", STAGE1)
        self.assertIn("Missing dates stay excluded, never imputed", STAGE1)
        self.assertIn("earliest notice date", STAGE1)

    def test_stage1_doc_cites_the_statute_and_all_three_exceptions(self):
        for citation in ("29 U.S.C. § 2102(a)", "29 U.S.C. § 2102(b)(1)",
                         "29 U.S.C. § 2102(b)(2)(A)",
                         "29 U.S.C. § 2102(b)(2)(B)",
                         "29 U.S.C. § 2102(b)(3)", "20 C.F.R. § 639.9",
                         "29 U.S.C. § 2104", "20 C.F.R. § 639.1(d)"):
            self.assertIn(citation, STAGE1)
        for exc in ("Faltering company", "Unforeseeable business circumstances",
                    "Natural disaster"):
            self.assertIn(exc, STAGE1)

    def test_stage1_endpoint_spec_is_read_only_and_unranked(self):
        self.assertIn("Read-only, keyless, public", STAGE1)
        self.assertIn("never joined to layoff tables", STAGE1)
        self.assertIn("not by gap size", STAGE1)

    def test_foundation_doc_links_stage1_and_keeps_arithmetic_bounded(self):
        self.assertIn("WARN_TRANSPARENCY_STAGE1.md", DOC)
        self.assertIn("Pure\narithmetic on recorded fields is permitted", DOC)
        self.assertIn("excluded, never guessed", DOC)


if __name__ == "__main__":
    unittest.main()
