"""Subscriber email redesign, stage 2: region colours, top 5 countries and
industries, résumé line in the talent digest. php cases SKIP without php."""
import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_design                       # noqa: E402

PLUGIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker")
HELPERS = os.path.join(PLUGIN, "includes", "digest-sections.php")
SUBSCRIBE = os.path.join(PLUGIN, "includes", "subscribe.php")
MAIN = os.path.join(PLUGIN, "ai-layoff-tracker.php")
JS = os.path.join(PLUGIN, "assets", "layoffs.js")
PHP = shutil.which("php")
URL = "https://asktherecruiter.com/?utm_campaign=digest-talent"


def php(expr):
    run = subprocess.run([PHP, "-r", f"require $argv[1]; echo json_encode({expr});",
                          HELPERS], capture_output=True, text=True, timeout=60)
    if run.returncode != 0:
        raise AssertionError(run.stderr[:1000] or run.stdout[:1000])
    return json.loads(run.stdout)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class ResumeLine(unittest.TestCase):
    def test_fires_on_a_reported_signal_of_500(self):
        html, text = php("alt_digest_talent_resume_line(array("
                         "array('company'=>'Acme','jobs'=>499),"
                         "array('company'=>'Globex','jobs'=>800)), "
                         f"'{URL}')")
        self.assertIn("Globex named 800 jobs", text)
        self.assertIn(URL, text)
        self.assertIn(f'<a href="{URL}">Tailor your résumé to its openings</a>', html)

    def test_job_board_scans_never_fire(self):
        self.assertEqual(php("alt_digest_talent_resume_line(array(array("
                             "'company'=>'Globex','jobs'=>5000,'scan'=>true)), "
                             f"'{URL}')"), ["", ""])

    def test_below_floor_or_bad_url_is_silent(self):
        self.assertEqual(php("alt_digest_talent_resume_line(array(array("
                             f"'company'=>'A','jobs'=>499)), '{URL}')"), ["", ""])
        self.assertEqual(php("alt_digest_talent_resume_line(array(array("
                             "'company'=>'A','jobs'=>900)), 'http://x')"), ["", ""])

    def test_top_n_keeps_endpoint_order(self):
        self.assertEqual(php("alt_digest_top_n(array('US'=>9,'UK'=>5,''=>4,'DE'=>0,"
                             "'FR'=>3,'IN'=>2,'JP'=>1,'BR'=>1), 5)"),
                         {"US": 9, "UK": 5, "FR": 3, "IN": 2, "JP": 1})


class RegionColours(unittest.TestCase):
    def test_each_region_has_its_own_fixed_colour(self):
        line = ('<p data-alt="series">Cuts: United States 900 · Europe 300 · '
                'Asia Pacific 200. Regions are our own grouping.</p>')
        drawn = digest_design.add_charts(line)
        for region in ("United States", "Europe", "Asia Pacific"):
            self.assertIn(f'bgcolor="{digest_design.REGION_COLOURS[region]}"', drawn)
        self.assertEqual(len(set(digest_design.REGION_COLOURS.values())),
                         len(digest_design.REGION_COLOURS) - 2)  # 3 residual greys

    def test_every_region_the_site_names_has_a_colour(self):
        sub = read(SUBSCRIBE)
        for region in ("United States", "Canada", "United Kingdom", "Europe",
                       "Asia Pacific", "Latin America", "Middle East and Africa"):
            self.assertIn(f"'{region}'", sub)
            self.assertIn(region, digest_design.REGION_COLOURS)

    def test_other_series_keep_the_section_accent(self):
        drawn = digest_design.add_charts(
            '<p data-alt="series">x: Retail 5 · Tech 3</p>', "#123456")
        self.assertIn('bgcolor="#123456"', drawn)


class Wiring(unittest.TestCase):
    def test_loaded_guarded_and_used_guarded(self):
        self.assertIn("includes/digest-sections.php", read(MAIN))
        sub = read(SUBSCRIBE)
        for fn in ("alt_digest_top_n", "alt_digest_talent_resume_line"):
            self.assertIn(f"function_exists('{fn}')", sub)
        self.assertIn("<h3>Top countries</h3>", sub)
        self.assertIn("array_slice($industries_all, 0, 5, true)", sub)

    def test_tracker_page_reads_the_filters_the_links_carry(self):
        js = read(JS)
        for key in ("country:", "industry:", "reasons:", "state:", "'company'"):
            self.assertIn(key, js)


if __name__ == "__main__":
    unittest.main()
