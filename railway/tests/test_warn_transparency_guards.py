"""Static guardrails for the separate, non-accusatory WARN register."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DB = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()
DOC = (ROOT / "docs/WARN_TRANSPARENCY_DATASET.md").read_text()


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


if __name__ == "__main__":
    unittest.main()
