"""Standalone widgets retain a tracked route to the free match check."""
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin/ai-layoff-tracker"


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


class WidgetMatchCta(unittest.TestCase):
    def test_rendered_widget_has_tagged_free_match_link(self):
        stubs = r'''
define('ABSPATH', '/'); define('ALT_VERSION', 'test');
define('ALT_PLUGIN_URL', 'https://example.org/plugin/');
function add_action(){} function language_attributes(){echo 'lang="en"';}
function bloginfo($key){echo 'UTF-8';}
function home_url($path){return 'https://asktherecruiter.com/blog'.$path;}
function rest_url($path){return home_url('/wp-json/'.$path);}
function esc_html($v){return htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8');}
function esc_url($v){return esc_html($v);}
function wp_json_encode($v,$flags=0){return json_encode($v,$flags);}
function add_query_arg($args,$url){return $url.'?'.http_build_query($args);}
function alt_resume_cta_base(){return 'https://asktherecruiter.com';}
'''
        script = stubs + f"require '{PLUGIN}/includes/atr-signup-cta.php'; require '{PLUGIN}/templates/page-widget.php';"
        result = subprocess.run(["php", "-r", script], check=True, capture_output=True, text=True)
        parser = Anchors()
        parser.feed(result.stdout)
        links = [a for a in parser.links if "alt-widget-cta" in a.get("class", "").split()]
        self.assertEqual(len(links), 1)
        url = urlsplit(links[0]["href"])
        self.assertEqual((url.netloc, url.path), ("asktherecruiter.com", "/resume-score"))
        self.assertEqual(parse_qs(url.query), {"utm_source": ["ai-layoff-tracker"],
                                             "utm_medium": ["referral"], "utm_campaign": ["widget"]})
        self.assertIn("Check my match, free", result.stdout)
        css = (PLUGIN / "assets/widget.css").read_text()
        self.assertIn(".alt-widget-cta", css)
        self.assertIn("min-height:44px", css.replace(" ", ""))
