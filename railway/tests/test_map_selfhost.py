"""todo#1881 item 7: the map's libraries and atlases are self-hosted and pinned,
and a failed load shows the figures as a table (review B4)."""
import hashlib
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
VENDOR = PLUGIN / "assets" / "vendor"
JS = (PLUGIN / "assets" / "layoffs.js").read_text()
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text()

PINS = {
    "d3.min.js": "f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539",
    "topojson-client.min.js": "25cd02ae486cc5063e0215a4e4cfb15de83700c87ac48bac4d57dc6aaf3ebb89",
    "countries-50m.json": "04342cdc1e3016bcd7db1630de95684d67b79fe3c8c460321e87aef469502394",
    "states-10m.json": "d76b391ccfa8bff601d51e3e3da5d43a89fa46cd5caca72ce731b383be5596d0",
}


class SelfHosted(unittest.TestCase):
    def test_vendor_files_match_their_pins(self):
        readme = (VENDOR / "README.md").read_text()
        for name, sha in PINS.items():
            got = hashlib.sha256((VENDOR / name).read_bytes()).hexdigest()
            self.assertEqual(got, sha, name)
            self.assertIn(sha, readme)

    def test_no_map_dependency_comes_from_a_cdn(self):
        self.assertNotRegex(JS, r"cdn\.jsdelivr\.net/npm/(d3|topojson-client|world-atlas|us-atlas)@")
        self.assertIn("'vendorUrl' => esc_url_raw(ALT_PLUGIN_URL . 'assets/vendor/')", MAIN)

    def test_failed_load_falls_back_to_a_table_from_the_same_points(self):
        fb = JS[JS.index("function renderAiMapFallback"):]
        fb = fb[:fb.index("\n    }\n")]
        self.assertIn("aiMapPoints(scope, AIMAP.data)", fb)
        self.assertIn("<caption>", fb)
        self.assertIn('scope="col"', fb)
        self.assertGreaterEqual(JS.count("renderAiMapFallback(box, note,"), 2)  # lib timeout + data failure

    def test_atlas_fetch_treats_a_bad_status_as_failure(self):
        lt = JS[JS.index("function loadTopo"):]
        self.assertIn("if (!r.ok) throw new Error('HTTP ' + r.status);", lt[:600])


if __name__ == "__main__":
    unittest.main()
