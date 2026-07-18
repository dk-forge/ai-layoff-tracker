"""Static safeguards for the public, append-only collector-run ledger."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DB = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()


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
        self.assertNotIn("alt_db_table()", body)
        self.assertNotIn("alt_source_reports_table()", body)


if __name__ == "__main__":
    unittest.main()
