"""Regression guards for the intentionally read-only lifecycle candidate queue."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DB = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()


class AnnouncementLifecycleGuards(unittest.TestCase):
    def test_endpoint_is_public_read_only_candidate_queue(self):
        self.assertIn("/announcement-lifecycle-candidates", DB)
        start = DB.index("function alt_api_announcement_lifecycle_candidates")
        body = DB[start: DB.index("/** Public retained reconciliation history", start)]
        self.assertIn("Same normalized company, exact job count", body)
        self.assertIn("not merged automatically", body)
        self.assertNotIn("$wpdb->update", body)
        self.assertNotIn("$wpdb->delete", body)

    def test_deterministic_screen_requires_exact_count_and_source_date(self):
        start = DB.index("function alt_api_announcement_lifecycle_candidates")
        body = DB[start: DB.index("/** Public retained reconciliation history", start)]
        self.assertIn("b.job_count = a.job_count", body)
        self.assertIn("a.announcement_date <> ''", body)
        self.assertIn("a.source_url <> ''", body)
        self.assertIn("b.source_url <> ''", body)
        self.assertIn("INTERVAL 365 DAY", body)
        self.assertIn("b.country = a.country", body)


if __name__ == "__main__":
    unittest.main()
