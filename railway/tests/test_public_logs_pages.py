"""/ai-layoff-tracker/corrections/ and /ai-layoff-tracker/update-log/ exist.

Both returned 404 on 2026-11-10. The corrections log lived only inside a
collapsed section of the tracker page and in the JSON API, so there was no URL
a journalist could cite for "how this tracker corrects itself", and the reader-
facing release notes in docs/release-notes.d were written and never published.

The update log is DERIVED from docs/release-notes.d by
railway/build_update_log.py into the plugin's data/update-log.json, the same
way the ingest cadence is derived (test_cadence_is_derived.py): a note that is
not in the committed file fails here, so nobody types the log by hand. A note
whose version is vNEXT, or newer than the plugin's own Version, is unreleased
and must not be listed as shipped.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.dirname(HERE)
ROOT = os.path.dirname(RAILWAY)
PLUGIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker")
INC = os.path.join(PLUGIN, "includes", "public-logs.php")
MAIN = os.path.join(PLUGIN, "ai-layoff-tracker.php")
DATA = os.path.join(PLUGIN, "data", "update-log.json")
NOTES = os.path.join(ROOT, "docs", "release-notes.d")
HARNESS = os.path.join(HERE, "fixtures", "public_logs_harness.php")
PHP = shutil.which("php")
sys.path.insert(0, RAILWAY)


def _src(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Routes(unittest.TestCase):
    def test_both_routes_are_registered_on_init_priority_1(self):
        src = _src(INC)
        self.assertIn("^ai-layoff-tracker/corrections/?$", src)
        self.assertIn("^ai-layoff-tracker/update-log/?$", src)
        # Rank Math's catch-all lands on init:1; see digest-public-archive.php.
        self.assertRegex(src, r"add_action\('init', 'alt_public_logs_routes', 1\)")

    def test_the_main_file_loads_it_guarded(self):
        src = _src(MAIN)
        self.assertIn("includes/public-logs.php", src)
        self.assertRegex(src, r"is_readable\(ALT_PLUGIN_DIR \. 'includes/public-logs\.php'\)")

    def test_it_serves_before_the_canonical_redirect(self):
        """/layoff-logs-sitemap.xml answered 301 to a trailing-slash URL on
        2026-11-10: WordPress's redirect_canonical runs on template_redirect at
        priority 10 and saw a path with no slash. The reports sitemap answers
        200 because it serves at priority 0 (report-seo.php). So does this."""
        src = _src(INC)
        self.assertRegex(src, r"add_action\('template_redirect', 'alt_public_logs_serve', 0\)")

    def test_anchors_match_the_tracker_page(self):
        """A /corrections/ link and a tracker-page link to one entry must agree."""
        rule = "'log-' . $alt_ld . '-' . $alt_log_seq[$alt_ld]"
        self.assertIn(rule, _src(os.path.join(PLUGIN, "templates", "page-tracker.php")))
        self.assertIn(rule, _src(INC))


class UpdateLogIsDerived(unittest.TestCase):
    def test_the_committed_file_matches_the_notes(self):
        import build_update_log
        expected = build_update_log.build(NOTES, MAIN)
        with open(DATA, encoding="utf-8") as fh:
            committed = json.load(fh)
        self.assertEqual(committed, expected,
                         "data/update-log.json is stale: run "
                         "python3 railway/build_update_log.py")

    def test_unreleased_notes_are_not_listed(self):
        import build_update_log
        out = build_update_log.build(NOTES, MAIN)
        self.assertTrue(out["entries"])
        plugin = build_update_log.plugin_version(MAIN)
        for e in out["entries"]:
            self.assertRegex(e["version"], r"^\d+\.\d+\.\d+$")
            self.assertLessEqual(build_update_log.vkey(e["version"]),
                                 build_update_log.vkey(plugin))

    def test_newest_first(self):
        import build_update_log
        out = build_update_log.build(NOTES, MAIN)
        keys = [(e["date"], build_update_log.vkey(e["version"])) for e in out["entries"]]
        self.assertEqual(keys, sorted(keys, reverse=True))

    def test_a_note_with_an_em_dash_is_refused(self):
        import build_update_log
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "x.md"), "w", encoding="utf-8") as fh:
                fh.write("---\nversion: 1.0.0\ntype: fix\narea: seo\ndate: 2026-01-01\n---\n"
                         "A thing — fixed.\n")
            with self.assertRaises(ValueError):
                build_update_log.build(d, MAIN)


@unittest.skipIf(PHP is None, "php is not on PATH: UNKNOWN, not a pass.")
class Rendered(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        log = [
            {"date": "2026-11-09", "action": "removed", "count": 1,
             "reason": "A running total, not one layoff.", "detail": "Bosch", "jobs": 30000},
            {"date": "2026-11-09", "action": "merged", "count": 2,
             "reason": "Same event reported twice.", "detail": ""},
            {"date": "2026-11-10", "action": "corrected", "count": 1,
             "reason": "Count fixed <b>to</b> 2,500.", "detail": ""},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"log": log}, fh)
            path = fh.name
        try:
            run = subprocess.run([PHP, HARNESS, INC, path, DATA],
                                 capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(path)
        if run.returncode != 0:
            raise AssertionError(run.stderr[:2000] + run.stdout[:2000])
        cls.out = json.loads(run.stdout)

    def test_corrections_page_lists_newest_first_with_stable_anchors(self):
        html = self.out["corrections"]
        ids = re.findall(r'<li id="(log-[^"]+)"', html)
        self.assertEqual(ids, ["log-2026-11-10-1", "log-2026-11-09-2", "log-2026-11-09-1"])
        self.assertIn("30,000 jobs", html)
        self.assertNotIn("<b>to</b>", html, "a reason is data and must be escaped")
        self.assertIn('rel="canonical" href="https://asktherecruiter.com/blog/ai-layoff-tracker/corrections/"', html)
        self.assertIn("/wp-json/layoffs/v1/corrections", html)

    def test_update_log_page_lists_every_released_note(self):
        html = self.out["update_log"]
        with open(DATA, encoding="utf-8") as fh:
            entries = json.load(fh)["entries"]
        for e in entries:
            self.assertIn(e["version"], html)
        self.assertIn('rel="canonical" href="https://asktherecruiter.com/blog/ai-layoff-tracker/update-log/"', html)

    def test_each_page_links_the_other_and_the_tracker(self):
        for key, other in (("corrections", "/update-log/"), ("update_log", "/corrections/")):
            self.assertIn("ai-layoff-tracker" + other, self.out[key])
            self.assertIn('href="https://asktherecruiter.com/blog/ai-layoff-tracker/"', self.out[key])

    def test_the_sitemap_lists_both_with_their_newest_date(self):
        xml = self.out["sitemap"]
        self.assertIn("<loc>https://asktherecruiter.com/blog/ai-layoff-tracker/corrections/</loc>"
                      "<lastmod>2026-11-10</lastmod>", xml)
        with open(DATA, encoding="utf-8") as fh:
            newest = json.load(fh)["entries"][0]["date"]
        self.assertIn("<loc>https://asktherecruiter.com/blog/ai-layoff-tracker/update-log/</loc>"
                      f"<lastmod>{newest}</lastmod>", xml)
        src = _src(INC)
        self.assertIn("^layoff-logs-sitemap\\.xml$", src)
        self.assertIn("rank_math/sitemap/index", src)

    def test_no_em_dashes_in_either_page(self):
        for key in ("corrections", "update_log"):
            self.assertNotIn("—", self.out[key])
            self.assertNotIn("&mdash;", self.out[key])


if __name__ == "__main__":
    unittest.main()
