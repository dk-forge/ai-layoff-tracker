"""todo#1881 item 9: the axe failures measured live on 2026-11-19."""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
TPL = (PLUGIN / "templates" / "page-tracker.php").read_text()
JS = (PLUGIN / "assets" / "layoffs.js").read_text()
CSS = (PLUGIN / "assets" / "layoffs.css").read_text()


class Axe(unittest.TestCase):
    def test_region_buttons_are_a_group_of_toggles_not_tabs(self):
        self.assertIn('id="alt-tabs" role="group" aria-label="Region"', TPL)
        self.assertNotIn('role="tablist"', TPL)
        self.assertEqual(len(re.findall(r'class="alt-tab alt-tab-\w+" aria-pressed="false"', TPL)), 10)
        self.assertIn("b.setAttribute('aria-pressed', b.getAttribute('data-tab') === key", JS)
        self.assertIn("b.setAttribute('aria-pressed', b.getAttribute('data-tab') === ACTIVE_TAB", JS)

    def test_claims_listitems_have_a_list_parent_and_the_scroller_is_focusable(self):
        self.assertIn('id="alt-bars-claims-states" role="list" aria-label="Jobless claims by US state" tabindex="0"', TPL)

    def test_map_label_sits_on_a_role(self):
        self.assertIn('id="alt-chart-aimap" role="figure" aria-label=', TPL)

    def test_api_snippet_wraps_instead_of_scrolling(self):
        # Not focusable (it is no control, and a tap-target test would rightly
        # flag it); it wraps on phones so there is no scroll region at all.
        self.assertIn('<code class="alt-journalist-api">', TPL)
        self.assertIn(".alt-journalist-api { width: 100%; box-sizing: border-box; white-space: normal; overflow-wrap: anywhere; }", CSS)

    def test_source_links_meet_target_size(self):
        self.assertIn(".alt-company-source-list a { display: inline-block; min-height: 24px;", CSS)


if __name__ == "__main__":
    unittest.main()
