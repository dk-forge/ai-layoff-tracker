"""Both shipped Dataset emitters name the research publisher and sources."""
import re
import unittest
from pathlib import Path

PLUGIN = (Path(__file__).resolve().parents[2] / "wordpress-plugin" /
          "ai-layoff-tracker" / "ai-layoff-tracker.php")


class DatasetPublisher(unittest.TestCase):
    def setUp(self):
        self.source = PLUGIN.read_text(encoding="utf-8")
        start = self.source.index("function alt_dataset_jsonld()")
        end = self.source.index("\nfunction ", start + 1)
        self.helper = self.source[start:end]
        marker = "'@id'                 => $alt_tracker_url . '#dataset'"
        start = self.source.index(marker)
        self.head = self.source[start:start + 2500]

    def test_helper_separates_publisher_from_unchanged_creator(self):
        self.assertIn("Ask The Recruiter Research", self.helper)
        self.assertIn("'publisher' => $publisher", self.helper)
        self.assertIn("'creator' => $org", self.helper)
        self.assertRegex(self.helper, r"\$publisher\s*=\s*array\('@type'\s*=>\s*'Organization'")
        self.assertIn("'isBasedOn'", self.helper)
        self.assertIn("/ai-layoff-tracker/sources/", self.helper)

    def test_head_dataset_has_research_publisher_and_sources(self):
        self.assertRegex(self.head, r"'publisher'[\s\S]{0,200}Ask The Recruiter Research")
        self.assertIn("'isBasedOn'", self.head)
        self.assertIn("/ai-layoff-tracker/sources/", self.head)

    def test_neither_dataset_publisher_uses_the_old_brand(self):
        for block in (self.helper, self.head):
            self.assertNotRegex(block, r"'publisher'\s*=>\s*\$org")
            self.assertNotRegex(block, r"'publisher'\s*=>\s*array\([^)]*'name'\s*=>\s*'AskTheRecruiter'")
            self.assertRegex(block, r"'isBasedOn'\s*=>\s*array\('@type'\s*=>\s*'WebPage'")

    def test_plugin_version_header_and_constant_agree(self):
        header = re.search(r"Version:\s*([0-9.]+)", self.source)
        constant = re.search(r"define\('ALT_VERSION',\s*'([0-9.]+)'\)", self.source)
        self.assertIsNotNone(header)
        self.assertIsNotNone(constant)
        self.assertEqual(header.group(1), constant.group(1))

    def test_new_reader_strings_have_no_em_dash(self):
        for value in ("Ask The Recruiter Research", "AI Layoff Tracker sources"):
            self.assertIn(value, self.helper)
            self.assertIn(value, self.head)
            self.assertNotIn("\u2014", value)


if __name__ == "__main__":
    unittest.main()
