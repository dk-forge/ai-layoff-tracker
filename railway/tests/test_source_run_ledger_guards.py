"""Static safeguards for the public, append-only collector-run ledger."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DB = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()
HEALTH_TEMPLATE = (ROOT / "wordpress-plugin/ai-layoff-tracker/templates/page-health.php").read_text()
HEALTH_JS = (ROOT / "wordpress-plugin/ai-layoff-tracker/assets/health.js").read_text()


class SourceRunLedgerGuards(unittest.TestCase):
    def test_ledger_is_bounded_public_read_and_keyed_write_only(self):
        self.assertIn("alt_source_runs", DB)
        self.assertIn("'/source-runs'", DB)
        start = DB.index("function alt_api_source_runs")
        body = DB[start: DB.index("function alt_api_integrity_status", start)]
        self.assertIn("min(90, max(1", body)
        self.assertIn("min(200, max(1", body)
        self.assertIn("Append-only collector-attempt telemetry", body)
        self.assertNotIn("DELETE FROM", body)
        self.assertNotIn("UPDATE ", body)

    def test_health_writer_retains_run_without_touching_layoff_facts(self):
        start = DB.index("function alt_api_source_health_post")
        body = DB[start: DB.index("function alt_api_source_runs", start)]
        self.assertIn("$wpdb->insert(alt_source_runs_table()", body)
        self.assertIn("alt_source_runs_table_ready()", body)
        self.assertNotIn("alt_db_table()", body)
        self.assertNotIn("alt_source_reports_table()", body)

    def test_health_page_has_bounded_run_history_windows(self):
        self.assertIn('id="alt-health-run-days"', HEALTH_TEMPLATE)
        self.assertIn('value="7"', HEALTH_TEMPLATE)
        self.assertIn('value="30"', HEALTH_TEMPLATE)
        self.assertIn('value="90"', HEALTH_TEMPLATE)
        self.assertIn('source-runs?days=', HEALTH_JS)
        self.assertIn('per_page=200', HEALTH_JS)

    def test_failed_collection_is_not_presented_as_zero_found(self):
        self.assertIn("const entriesLabel", HEALTH_JS)
        self.assertIn("x.status === 'ok'", HEALTH_JS)
        self.assertIn("'No completed count'", HEALTH_JS)


if __name__ == "__main__":
    unittest.main()
