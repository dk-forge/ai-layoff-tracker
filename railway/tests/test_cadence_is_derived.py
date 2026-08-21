"""No reader-facing surface may TYPE the ingest cadence.

The cron went to one run a day on 2026-08-14 and moved from 16:00 to 22:00 UTC
on 2026-08-18. `data/ingest-schedule.json` followed, and so did the two places
that computed their copy from it. Everything else had "twice daily" typed in:
the Sources page said it seven times, the Health page's schedule list once, the
FAQ twice, `assets/health.js` on eight collector labels, and all 182 rows of the
generated country table promised "2x/day (13:00 & 22:00 UTC)". The methodology
page contradicted itself four lines apart on the live site.

None of it errored, because typed copy has no generator behind it and nothing to
fail when the schedule moves. This file is that missing failure.

It also refuses a FALLBACK cadence. `shortcodes.php` used to guess 'twice daily'
whenever the schedule could not be read, which is how a surface keeps asserting
a number after the fact behind it is gone. An absent cadence is honest.
"""
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))
RAILWAY = os.path.dirname(HERE)

# Reader-facing surfaces. A cadence in any of these must be rendered from
# alt_ingest_cadence_phrase() / altHealthData.ingestCadence, never typed.
# HAND-EDITED surfaces only. The two generated partials legitimately CONTAIN a
# rendered cadence -- that is the whole point of generating them -- so they are
# checked further down against the generator instead.
SURFACES = (
    "templates/page-sources.php",
    "templates/page-health.php",
    "templates/page-methodology.php",
    "assets/health.js",
    "ai-layoff-tracker.php",
    "includes/shortcodes.php",
)

# Phrasings that assert a cadence. Matched against CODE and MARKUP, with
# comments stripped first — the fix's own explanation names the defect, and
# convicting the explanation would just teach the next session to delete it.
TYPED_CADENCE = re.compile(
    r"twice[ -]daily|twice a day|2\s*(?:×|&times;|x)\s*/\s*day|"
    r"once daily|1\s*(?:×|&times;|x)\s*/\s*day",
    re.I)

def _strip_php_and_js_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*(//|\*|#).*$", " ", text, flags=re.M)


class CadenceIsNeverTyped(unittest.TestCase):

    def test_no_reader_surface_types_a_cadence(self):
        offenders = []
        for rel in SURFACES:
            path = os.path.join(PLUGIN, rel)
            with open(path, encoding="utf-8") as fh:
                body = _strip_php_and_js_comments(fh.read())
            for m in TYPED_CADENCE.finditer(body):
                line = body[:m.start()].count("\n") + 1
                offenders.append(f"{rel}:{line} {m.group(0)!r}")
        self.assertEqual(
            offenders, [],
            "these surfaces state a cadence that no generator produced. Render "
            "alt_ingest_cadence_phrase() (PHP) or altHealthData.ingestCadence "
            "(health.js) instead, so the copy moves when railway.toml does: "
            + "; ".join(offenders))

    def test_there_is_no_fallback_cadence(self):
        """An unreadable schedule must print nothing, not a guess."""
        with open(os.path.join(PLUGIN, "includes", "db.php"), encoding="utf-8") as fh:
            db = fh.read()
        self.assertIn("function alt_ingest_cadence_phrase()", db)
        body = db.split("function alt_ingest_cadence_phrase()", 1)[1].split("\n}", 1)[0]
        self.assertIn("if (!$s) return '';", body,
                      "alt_ingest_cadence_phrase must return '' on an unreadable "
                      "schedule; a default is how a surface keeps asserting a "
                      "cadence after the fact behind it is gone")


class GeneratedPartialsMatchTheSchedule(unittest.TestCase):
    """The committed partials must agree with the committed schedule."""

    def setUp(self):
        with open(os.path.join(PLUGIN, "data", "ingest-schedule.json"),
                  encoding="utf-8") as fh:
            self.sched = json.load(fh)

    def test_country_table_states_the_real_hours(self):
        import sys
        if RAILWAY not in sys.path:
            sys.path.insert(0, RAILWAY)
        import generate_country_table as gct
        with open(os.path.join(PLUGIN, "templates", "partials",
                               "country-sources-table.php"), encoding="utf-8") as fh:
            html = fh.read()
        expected = gct.scan_cadence_cell()
        self.assertIn(expected, html)
        # And no row may carry a different one.
        cells = set(re.findall(r"<td>(Active[^<]*)</td>", html))
        self.assertEqual(cells, {expected},
                         f"country table rows disagree about the schedule: {cells}")

    def test_jurisdiction_table_states_the_real_cadence(self):
        import sys
        if RAILWAY not in sys.path:
            sys.path.insert(0, RAILWAY)
        import generate_jurisdiction_table as gjt
        with open(os.path.join(PLUGIN, "templates", "partials",
                               "jurisdiction-table.php"), encoding="utf-8") as fh:
            html = fh.read()
        cadence = gjt._ingest_cadence()
        self.assertTrue(cadence, "the schedule did not resolve for the generator")
        self.assertIn(f"SEC full-text search, {cadence},", html,
                      "the committed jurisdiction table disagrees with the cron; "
                      "regenerate with python3 railway/generate_jurisdiction_table.py")

    def test_the_sweep_figure_matches_the_ring_and_the_cadence(self):
        """"about every N days" is arithmetic, not a remembered number.

        It read "about every six days" for the news editions, which was true at
        two runs a day and became eleven on 2026-08-14 with nothing to catch it.
        """
        import math
        rot = self.sched.get("rotation") or {}
        self.assertTrue(rot, "ingest-schedule.json carries no rotation block; "
                             "regenerate with generate_ingest_schedule.py")
        runs_per_day = len(self.sched["utc_hours"])
        for key, r in rot.items():
            with self.subTest(ring=key):
                self.assertEqual(r["runs"], math.ceil(r["terms"] / r["per_run"]))
                self.assertEqual(r["days"], math.ceil(r["runs"] / runs_per_day))


if __name__ == "__main__":
    unittest.main()
