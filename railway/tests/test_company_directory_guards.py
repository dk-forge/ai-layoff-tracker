"""Static guardrails for the WordPress company-directory foundation.

PHP is linted by deployment CI, but these tests make the publication safeguards
hard to remove accidentally while local PHP is unavailable.
"""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/company-directory.php").read_text()
TEMPLATE = (ROOT / "wordpress-plugin/ai-layoff-tracker/templates/page-company-directory.php").read_text()


class CompanyDirectoryGuardTests(unittest.TestCase):
    def test_directory_requires_reviewed_registry_status(self):
        self.assertIn("review_status IN ('approved','noindex')", MODULE)
        self.assertIn("company_key", MODULE)

    def test_directory_reads_canonical_events_with_retained_source_urls(self):
        self.assertIn("e.canonical_layoff_id = l.id", MODULE)
        self.assertIn("EXISTS (SELECT 1 FROM $reports", MODULE)
        self.assertIn("source_url <> ''", MODULE)

    def test_low_value_pages_are_not_indexable(self):
        self.assertIn("count($event_rows) >= 2", MODULE)
        self.assertIn("noindex,follow", MODULE)

    def test_unknown_or_unreviewed_slugs_are_not_rendered(self):
        self.assertIn("$wp_query->set_404()", MODULE)

    def test_template_lists_retained_sources_and_warn_link_caveat(self):
        self.assertIn("$event['sources']", TEMPLATE)
        self.assertIn("official WARN list", TEMPLATE)
        self.assertIn("noopener nofollow", TEMPLATE)


if __name__ == "__main__":
    unittest.main()
