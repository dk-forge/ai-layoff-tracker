"""Static safety guards for immutable quarterly research snapshots."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DB = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()
WORKFLOW = (ROOT / ".github/workflows/quarterly-report.yml").read_text()
TEMPLATE = (ROOT / "wordpress-plugin/ai-layoff-tracker/templates/page-quarterly-report.php").read_text()
EXPORT = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/export.php").read_text()


class QuarterlyReportGuards(unittest.TestCase):
    def test_writer_generates_snapshot_from_server_queries(self):
        start = DB.index("function alt_api_quarterly_report_post")
        body = DB[start: DB.index("/** Called only on a versioned plugin deployment", start)]
        self.assertIn("alt_quarterly_report_aggregate($verified_query)", body)
        self.assertIn("alt_quarterly_report_aggregate($announced_query)", body)
        self.assertNotIn("$r->get_param('snapshot')", body)
        self.assertNotIn("$r->get_param('totals')", body)

    def test_snapshot_is_immutable_and_discloses_limits(self):
        start = DB.index("function alt_api_quarterly_report_post")
        body = DB[start: DB.index("/** Called only on a versioned plugin deployment", start)]
        self.assertIn("Quarterly reports are immutable", body)
        self.assertIn("degraded_sources", body)
        self.assertIn("not a complete census", body)
        self.assertIn("revision_notice", body)

    def test_workflow_posts_only_identifier_and_status(self):
        self.assertIn('\\"report_id\\":\\"$REPORT_ID\\"', WORKFLOW)
        self.assertIn('\\"publication_status\\":\\"$STATUS\\"', WORKFLOW)
        self.assertNotIn('\\"snapshot\\"', WORKFLOW)
        self.assertIn("immutable snapshot retained", WORKFLOW)

    def test_html_report_exposes_revision_and_source_snapshot(self):
        self.assertIn("Data revision notice", TEMPLATE)
        self.assertIn("Machine-readable frozen report snapshot", TEMPLATE)
        self.assertIn("not a layoff census", TEMPLATE)

    def test_table_renderer_is_declared_before_its_first_render_call(self):
        declaration = TEMPLATE.index("function alt_quarterly_report_table")
        first_call = TEMPLATE.index("alt_quarterly_report_table($verified")
        self.assertLess(declaration, first_call)

    def test_appendix_is_read_only_from_the_stored_snapshot(self):
        self.assertIn("/reports/quarterly/(?P<report_id>", DB)
        start = DB.index("function alt_quarterly_report_appendix_data")
        body = DB[start: DB.index("function alt_api_quarterly_report_appendix_get", start)]
        self.assertIn("Frozen aggregate tables and time series only", body)
        self.assertNotIn("alt_api_aggregate_compute", body)
        export_start = EXPORT.index("function alt_quarterly_appendix_download")
        export_body = EXPORT[export_start:]
        self.assertIn("alt_quarterly_report_appendix_data($report)", export_body)
        self.assertNotIn("alt_db_where", export_body)
        self.assertNotIn("$wpdb", export_body)

    def test_html_report_links_both_readable_and_downloadable_appendices(self):
        self.assertIn("Readable JSON appendix", TEMPLATE)
        self.assertIn("Download CSV appendix", TEMPLATE)
        self.assertIn("Download JSON appendix", TEMPLATE)


if __name__ == "__main__":
    unittest.main()
