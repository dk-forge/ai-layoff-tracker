"""The reader-facing archive promise is ONE promise, kept by the crons.

Every listing surface (tracker cards, company pages, facet pages, entry
permalinks) shows, beside a row whose source has no Wayback snapshot yet:

    "No archive snapshot yet. We re-check weekly; next check by <date>."

The date is DERIVED from the real schedule — the daily archive-backfill cron,
the 72h 'pending' retry spacing and the 7-day 'unavailable' re-check — in TWO
renderers (db.php for the server-rendered pages, layoffs.js for the tracker
cards). This file pins the pieces together so the sentence can never become a
typed promise the crons don't keep:

  * the PHP cadence constants equal the JS mirror constants,
  * the PHP daily-run time equals the cron in archive-backfill.yml,
  * both renderers print the SAME sentence,
  * the templates actually call the shared helper,
  * data_integrity.ArchiveRecheckInvariant judges the live payload honestly
    (PASS / FAIL / UNKNOWN, never a silent pass),
  * and the tracker page's measured-completeness paragraph renders from the
    committed measurement instead of hardcoding "24 of 57".
"""
import json
import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity
from data_integrity import FAIL, PASS, UNKNOWN, ArchiveRecheckInvariant

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLUGIN = REPO / "wordpress-plugin" / "ai-layoff-tracker"
DB_PHP = (PLUGIN / "includes" / "db.php").read_text(encoding="utf-8")
LAYOFFS_JS = (PLUGIN / "assets" / "layoffs.js").read_text(encoding="utf-8")
BACKFILL_YML = (REPO / ".github" / "workflows" / "archive-backfill.yml").read_text(encoding="utf-8")

PROMISE = "No archive snapshot yet. We re-check weekly; next check by"


def _php_define(name):
    m = re.search(r"define\('" + name + r"',\s*'?([\d:]+)'?\)", DB_PHP)
    assert m, f"{name} not defined in db.php"
    return m.group(1)


class CadenceIsOneDefinition(unittest.TestCase):
    def test_js_mirror_equals_php_constants(self):
        php_retry = int(_php_define("ALT_ARCHIVE_RETRY_HOURS"))
        php_recheck = int(_php_define("ALT_ARCHIVE_RECHECK_DAYS"))
        php_run = _php_define("ALT_ARCHIVE_DAILY_RUN_UTC")
        m = re.search(r"ARCHIVE_RETRY_HOURS = (\d+), ARCHIVE_RECHECK_DAYS = (\d+), "
                      r"ARCHIVE_RUN_UTC = \[(\d+), (\d+)\]", LAYOFFS_JS)
        self.assertIsNotNone(m, "layoffs.js lost its archive cadence mirror constants")
        self.assertEqual(int(m.group(1)), php_retry,
                         "pending-retry hours drifted between db.php and layoffs.js")
        self.assertEqual(int(m.group(2)), php_recheck,
                         "weekly re-check days drifted between db.php and layoffs.js")
        h, mi = php_run.split(":")
        self.assertEqual((int(m.group(3)), int(m.group(4))), (int(h), int(mi)),
                         "daily-run time drifted between db.php and layoffs.js")

    def test_php_run_time_matches_the_actual_cron(self):
        # The date printed on the pages is only real if the cron actually runs
        # then. '25 5 * * *' <=> ALT_ARCHIVE_DAILY_RUN_UTC '05:25'.
        h, mi = _php_define("ALT_ARCHIVE_DAILY_RUN_UTC").split(":")
        cron = re.search(r"cron:\s*'(\d+)\s+(\d+)\s+\*\s+\*\s+\*'", BACKFILL_YML)
        self.assertIsNotNone(cron, "archive-backfill.yml lost its daily cron line")
        self.assertEqual((int(cron.group(2)), int(cron.group(1))), (int(h), int(mi)),
                         "the cron time in archive-backfill.yml no longer matches "
                         "ALT_ARCHIVE_DAILY_RUN_UTC — the printed next-check date is a lie")

    def test_candidate_query_uses_the_constants_not_literals(self):
        body = DB_PHP[DB_PHP.find("function alt_api_archive_candidates("):]
        body = body[:body.find("\n}\n")]
        self.assertIn("ALT_ARCHIVE_RETRY_HOURS", body)
        self.assertIn("ALT_ARCHIVE_RECHECK_DAYS", body)

    def test_weekly_is_the_slowest_promised_cadence(self):
        # "We re-check weekly" is a floor: every state must re-enter the
        # candidate list within 7 days of eligibility.
        self.assertLessEqual(int(_php_define("ALT_ARCHIVE_RETRY_HOURS")), 7 * 24)
        self.assertLessEqual(int(_php_define("ALT_ARCHIVE_RECHECK_DAYS")), 7)


class OneSentenceEverywhere(unittest.TestCase):
    def test_both_renderers_print_the_same_promise(self):
        self.assertIn(PROMISE, DB_PHP, "db.php alt_archive_note_html lost the promise sentence")
        self.assertIn(PROMISE, LAYOFFS_JS, "layoffs.js archiveCell lost the promise sentence")

    def test_no_em_dash_in_the_promise_copy(self):
        for src, name in ((DB_PHP, "db.php"), (LAYOFFS_JS, "layoffs.js")):
            i = src.find(PROMISE)
            self.assertNotIn("—", src[i:i + 200], f"em-dash in UI copy near the promise in {name}")

    def test_every_server_rendered_listing_calls_the_shared_helper(self):
        for tpl in ("page-company-directory.php", "page-facet.php", "single-layoff.php"):
            src = (PLUGIN / "templates" / tpl).read_text(encoding="utf-8")
            self.assertIn("alt_archive_note_html", src,
                          f"{tpl} no longer renders the row's archive state")

    def test_coverage_line_is_computed_not_typed(self):
        # The methodology + health coverage line comes from one live helper.
        self.assertIn("alt_archive_coverage_line_html", DB_PHP)
        for tpl in ("page-methodology.php", "page-health.php"):
            src = (PLUGIN / "templates" / tpl).read_text(encoding="utf-8")
            self.assertIn("alt_archive_coverage_line_html", src,
                          f"{tpl} lost the live archive-coverage line")


def _run(payload):
    inv = ArchiveRecheckInvariant()
    ctx = data_integrity.Ctx(lambda url, timeout: json.dumps(payload).encode(), 5, "cb")
    return inv.run(ctx)


class InvariantJudgesHonestly(unittest.TestCase):
    BASE = {"distinct_source_urls": 25029, "archived": 21110, "pending": 3800,
            "unavailable": 110, "queued": 9, "coverage_pct": 84.3, "recheck_days": 7}

    def _payload(self, age_days):
        stamp = (datetime.now(timezone.utc) - timedelta(days=age_days)).strftime("%Y-%m-%d %H:%M:%S")
        return dict(self.BASE, oldest_unarchived_checked_at=stamp)

    def test_fresh_attempts_pass(self):
        r = _run(self._payload(3))
        self.assertEqual(r.state, PASS)

    def test_a_stale_pool_fails_the_promise(self):
        r = _run(self._payload(ArchiveRecheckInvariant.MAX_AGE_DAYS + 2))
        self.assertEqual(r.state, FAIL)
        self.assertIn("promising a re-check", r.detail)

    def test_bound_matches_the_cadence_math(self):
        # 7 (promise) + 1 (daily-run granularity) + 2 (slack). Change the
        # cadence and this number must be re-derived, not nudged.
        self.assertEqual(ArchiveRecheckInvariant.MAX_AGE_DAYS, 7 + 1 + 2)

    def test_a_build_without_the_fields_is_unknown_never_pass(self):
        r = _run(self.BASE)   # no oldest_unarchived_checked_at key at all
        self.assertEqual(r.state, UNKNOWN)
        self.assertTrue(r.pending)

    def test_an_empty_await_pool_passes(self):
        r = _run(dict(self.BASE, pending=0, unavailable=0,
                      oldest_unarchived_checked_at=None))
        self.assertEqual(r.state, PASS)

    def test_a_pool_with_no_timestamp_is_unknown(self):
        r = _run(dict(self.BASE, oldest_unarchived_checked_at=None))
        self.assertEqual(r.state, UNKNOWN)

    def test_a_vanished_archive_index_fails(self):
        r = _run(dict(self.BASE, archived=0, oldest_unarchived_checked_at=None,
                      pending=0, unavailable=0))
        self.assertEqual(r.state, FAIL)


class RecallParagraphIsRendered(unittest.TestCase):
    def test_tracker_page_no_longer_hardcodes_the_measurement(self):
        src = (PLUGIN / "templates" / "page-tracker.php").read_text(encoding="utf-8")
        self.assertNotIn("24 of 57", src,
                         "the measured-completeness paragraph is typed again — it must render "
                         "from alt_recall_measurement()")
        self.assertNotIn("38 of 39", src)
        self.assertIn("alt_recall_measurement", src)

    def test_plugin_render_copy_matches_the_canonical_measurement(self):
        canonical = json.loads((REPO / "railway" / "recall_measurement.json").read_text())
        render = json.loads((PLUGIN / "data" / "recall-measurement.json").read_text())
        for key in ("matched", "reference_events", "reference_set_id"):
            self.assertEqual(render[key], canonical[key],
                             f"data/recall-measurement.json {key} drifted from "
                             f"railway/recall_measurement.json — recall_precision.py writes both")

    def test_render_copy_is_internally_sane(self):
        render = json.loads((PLUGIN / "data" / "recall-measurement.json").read_text())
        self.assertGreater(render["reference_events"], 0)
        self.assertGreaterEqual(render["matched"], 0)
        self.assertLessEqual(render["matched"], render["reference_events"])
        p = render.get("precision_verbatim")
        if p is not None:
            self.assertGreater(p["checked"], 0)
            self.assertGreaterEqual(p["ok"], 0)
            self.assertLessEqual(p["ok"], p["checked"])


if __name__ == "__main__":
    unittest.main()
