"""Placement attribution is separate from each link's campaign."""
import json
import subprocess
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin/ai-layoff-tracker"


class PlacementAttribution(unittest.TestCase):
    def test_four_utm_fields_and_existing_destination(self):
        stubs = """define('ABSPATH', 1);
function add_action() {} function add_filter() {}
function alt_resume_cta_base() { return 'https://asktherecruiter.com'; }
function add_query_arg($args, $url) { return $url . '?' . http_build_query($args); }
"""
        code = stubs + "require " + json.dumps(str(PLUGIN / "includes/atr-signup-cta.php")) + ";"
        code += "echo json_encode(array(alt_atr_cta_url('tracker_home', 'inline'), alt_atr_cta_url('sticky_bar', 'sticky'), alt_atr_cta_url('tracker_home_fold', 'hero'), alt_atr_cta_url('widget', 'widget')));"
        result = subprocess.run(["php", "-r", code], capture_output=True, text=True, check=True)
        for url, campaign, placement in zip(json.loads(result.stdout), ["tracker_home", "sticky_bar", "tracker_home_fold", "widget"], ["inline", "sticky", "hero", "widget"]):
            parsed = urlparse(url)
            self.assertEqual((parsed.scheme, parsed.netloc, parsed.path), ("https", "asktherecruiter.com", "/resume-score"))
            self.assertEqual(parse_qs(parsed.query), {"utm_source": ["ai-layoff-tracker"], "utm_medium": ["referral"], "utm_campaign": [campaign], "utm_content": [placement]})

    def test_renderers_name_their_placement(self):
        helper = (PLUGIN / "includes/atr-signup-cta.php").read_text()
        hero = (PLUGIN / "templates/page-tracker.php").read_text()
        widget = (PLUGIN / "templates/page-widget.php").read_text()
        self.assertIn("alt_atr_cta_url($campaign, 'inline')", helper)
        self.assertIn("alt_atr_cta_url('sticky_bar', 'sticky')", helper)
        self.assertIn("alt_atr_cta_url('tracker_home_fold', 'hero')", hero)
        self.assertIn("alt_atr_cta_url('widget', 'widget')", widget)
