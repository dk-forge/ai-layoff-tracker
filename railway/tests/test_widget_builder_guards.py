"""Static guardrails for the public iframe-widget builder."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HEALTH_TEMPLATE = (ROOT / "wordpress-plugin/ai-layoff-tracker/templates/page-health.php").read_text()
HEALTH_JS = (ROOT / "wordpress-plugin/ai-layoff-tracker/assets/health.js").read_text()


class WidgetBuilderGuardTests(unittest.TestCase):
    def test_builder_is_limited_to_us_national_or_state_scope(self):
        self.assertIn("Embed a US layoff widget", HEALTH_TEMPLATE)
        self.assertIn("Metro widgets are deliberately unavailable", HEALTH_TEMPLATE)
        self.assertIn("country', 'United States'", HEALTH_JS)
        self.assertIn("/^[A-Z]{2}$/", HEALTH_JS)

    def test_builder_uses_existing_noindex_widget_and_exact_tracker_filters(self):
        self.assertIn("window.altHealthData.widgetUrl", HEALTH_JS)
        self.assertIn("tracker_year", HEALTH_JS)
        self.assertIn("Preview exact tracker view", HEALTH_TEMPLATE)

    def test_builder_does_not_request_or_promise_backlinks(self):
        self.assertIn("no backlink is requested or promised", HEALTH_TEMPLATE)
        self.assertIn("<iframe src=", HEALTH_JS)


if __name__ == "__main__":
    unittest.main()
