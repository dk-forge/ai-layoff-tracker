"""todo#1881 item 8: the console errors on every page and the 90-day label."""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
SRC = (PLUGIN / "includes" / "console-hygiene.php").read_text()
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text()
TPL = (PLUGIN / "templates" / "page-tracker.php").read_text()


class ConsoleHygiene(unittest.TestCase):
    def test_loaded_guarded(self):
        self.assertIn("includes/console-hygiene.php'", MAIN)
        self.assertIn("is_readable($alt_console_hygiene)", MAIN)

    def test_wordfence_sync_tag_is_unhooked_from_the_front_end(self):
        self.assertIn("remove_action($hook, 'wordfence::addSyncAttackDataAjax')", SRC)
        self.assertIn("'wp_head'", SRC)

    def test_navigation_view_module_is_enqueued_before_the_import_map(self):
        self.assertIn("wp_enqueue_script_module('@wordpress/block-library/navigation/view')", SRC)
        self.assertRegex(SRC, r"add_action\('wp_enqueue_scripts', 'alt_enqueue_navigation_view_early', 1\)")


class NinetyDayLabel(unittest.TestCase):
    def test_d90_says_what_it_is(self):
        m = re.search(r'data-dp="d90">([^<]+)<', TPL)
        self.assertEqual(m.group(1), "Last 90 days")


if __name__ == "__main__":
    unittest.main()
