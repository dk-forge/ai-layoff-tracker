"""The committed ingest schedule must match the REAL cron, forever.

data/ingest-schedule.json powers the tracker page's "next update" promise
(server-rendered dateline + the header's live countdown). It is generated from
railway/railway.toml by generate_ingest_schedule.py; this test fails the build
if either side moves without the other, so the public promise can never drift
from the schedule that actually runs.
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from generate_ingest_schedule import OUT, TOML, parse_cron_schedule  # noqa: E402


class IngestScheduleMatchesCron(unittest.TestCase):
    def test_committed_json_matches_railway_toml(self):
        expected = parse_cron_schedule(TOML.read_text(encoding="utf-8"))
        self.assertTrue(OUT.exists(),
                        "data/ingest-schedule.json is missing; run "
                        "python3 railway/generate_ingest_schedule.py")
        committed = json.loads(OUT.read_text(encoding="utf-8"))
        self.assertEqual(expected, committed,
                         "ingest-schedule.json drifted from railway.toml; "
                         "regenerate with python3 railway/generate_ingest_schedule.py")

    def test_schedule_shape_is_sane(self):
        committed = json.loads(OUT.read_text(encoding="utf-8"))
        hours = committed["utc_hours"]
        self.assertTrue(hours, "schedule must carry at least one UTC hour")
        self.assertEqual(hours, sorted(set(hours)))
        for h in hours:
            self.assertTrue(0 <= h <= 23)
        self.assertTrue(0 <= committed["utc_minute"] <= 59)

    def test_no_typed_pull_hours_left_in_js(self):
        """layoffs.js must read altData.ingest, never hardcode the hours."""
        js_path = os.path.normpath(os.path.join(
            HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker",
            "assets", "layoffs.js"))
        js = open(js_path, encoding="utf-8").read()
        self.assertNotIn("[13, 22]", js,
                         "nextPullET must derive its hours from altData.ingest "
                         "(data/ingest-schedule.json), not a typed list")

    def test_methodology_cadence_is_derived_not_typed(self):
        """The methodology page's update promise must come from the cron too.

        It read "twice daily (morning and after US market close, ET)" while the
        cron was once daily in the evening, and named 11 AM ET / noon ET for two
        workflows that run at 9 AM ET / 11 AM ET. layoffs.js was guarded and this
        page was not, so the same fact was right in one place and wrong in the
        other. A clock time typed into this paragraph has no generator behind it
        and nothing to fail when the schedule moves.
        """
        php_path = os.path.normpath(os.path.join(
            HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker",
            "templates", "page-methodology.php"))
        with open(php_path, encoding="utf-8") as fh:
            php = fh.read()
        # PHP block comments carry the history above; judge only what renders.
        rendered = re.sub(r"/\*.*?\*/", "", php, flags=re.S)
        m = re.search(r"How often it updates\.</b>(.*?)</p>", rendered, re.S)
        self.assertIsNotNone(
            m, "the 'How often it updates.' paragraph moved or was renamed; "
               "this guard must move with it, not be deleted")
        para = m.group(1)
        self.assertIn(
            "alt_ing_say", para,
            "the news/SEC cadence must be echoed from alt_ingest_schedule() "
            "(data/ingest-schedule.json), never typed")
        typed = re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)\b", para)
        self.assertEqual(
            [], typed,
            "typed clock time(s) %r in the update-cadence paragraph: no "
            "generator reads them, so they go stale silently. State the "
            "cadence, or derive the hour." % (typed,))
        self.assertNotIn(
            "noon", para.lower(),
            "'noon' is a typed clock time with no generator behind it")
