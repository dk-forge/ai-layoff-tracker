"""THE DEPLOY'S OWN FIRST REQUEST MUST NOT BE THE LOAD EVENT.

WHY THIS FILE EXISTS. Every outage on the weekend of 2026-09-12/13 began
within minutes of a plugin deploy. The first visitor request after a version
bump runs alt_flush_caches_on_deploy() on one PHP worker, and until 2.20.193
that request downloaded the Nevada WARN PDF from detr.nv.gov inline (a
wp_remote_get with a 45 second timeout), swept wp_options with four LIKE
predicates, ran the undated-dedup self-join over the whole layoffs table, and
then five modules each called flush_rewrite_rules(false) from their own init
hook at priority 99. deploy-plugin.yml then purged Cloudflare, so every reader
arrived at an origin whose worker was already held. On a shared host with an
entry-process ceiling that pins the account.

This test reads the PHP as text and pins four things:

  * the deploy hook no longer calls alt_nv_mirror_refresh() inline; it
    schedules the existing alt_nv_mirror_cron hook once, ten minutes out,
    and only if none is already pending;
  * the wp_options LIKE sweep and alt_dedup_undated_cleanup() sit behind a
    dated guard (alt_deploy_sweeps_ran_on = today) that is WRITTEN AFTER they
    run, so three deploys in one night run them once and the first deploy of a
    day still runs them;
  * exactly one flush_rewrite_rules( call remains on the init path. The five
    callers keep their own version options (nothing loses its "I need a
    flush" signal) but raise a flag, and one init priority 100 hook flushes
    once if any flag is set. Activation and deactivation keep their own
    flush, because those are not the deploy path.

Rules for the parent: no request to the live host, no other suite.
"""

import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8")
INCLUDES = PLUGIN / "includes"

CALLERS = {
    "facet-pages.php": "alt_facet_rewrite_version",
    "company-index.php": "alt_company_index_rewrite_version",
    "digest-archive.php": "alt_edition_rewrite_version",
    "report-seo.php": "alt_report_rewrite_version",
    "company-directory.php": "alt_company_directory_rewrite_version",
}


def _function_body(src, name):
    start = src.index("function %s(" % name)
    depth = 0
    i = src.index("{", start)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise AssertionError("unterminated function %s" % name)


class DeployHookLeavesTheStormToLater(unittest.TestCase):
    def setUp(self):
        self.hook = _function_body(MAIN, "alt_flush_caches_on_deploy")

    def test_nv_mirror_is_not_downloaded_inside_the_deploy_request(self):
        self.assertFalse("alt_nv_mirror_refresh(" in self.hook,
                         "the deploy request still downloads the Nevada PDF inline")

    def test_nv_mirror_is_scheduled_once_ten_minutes_out(self):
        m = re.search(r"wp_schedule_single_event\(\s*time\(\)\s*\+\s*600\s*,\s*'alt_nv_mirror_cron'", self.hook)
        self.assertIsNotNone(m, "the deploy hook must schedule alt_nv_mirror_cron ten minutes out")
        guard = self.hook.index("wp_next_scheduled('alt_nv_mirror_cron')")
        self.assertLess(guard, m.start(), "the schedule must be guarded by wp_next_scheduled first")
        # The hook itself still exists and still carries the daily cron.
        self.assertTrue("add_action('alt_nv_mirror_cron', 'alt_nv_mirror_refresh');" in MAIN, "cron hook lost")
        self.assertTrue("wp_schedule_event(time() + 300, 'daily', 'alt_nv_mirror_cron');" in MAIN, "daily cron lost")

    def test_sweeps_run_at_most_once_a_day_and_the_guard_is_written_after(self):
        read = re.search(r"get_option\('alt_deploy_sweeps_ran_on'\)", self.hook)
        self.assertIsNotNone(read, "the sweeps are not behind the dated guard")
        like = self.hook.index("option_name LIKE")
        dedup = self.hook.index("alt_dedup_undated_cleanup(")
        write = re.search(r"update_option\('alt_deploy_sweeps_ran_on',\s*\$[a-z_]+,\s*false\)", self.hook)
        self.assertIsNotNone(write, "the guard option is never written")
        self.assertLess(read.start(), like)
        self.assertLess(read.start(), dedup)
        self.assertGreater(write.start(), like, "guard written before the LIKE sweep ran")
        self.assertGreater(write.start(), dedup, "guard written before the dedup cleanup ran")
        # The date the guard compares against is today, so the first deploy of a day runs them.
        self.assertRegex(self.hook, r"gmdate\('Y-m-d'\)|current_time\('Y-m-d'\)|wp_date\('Y-m-d'\)")


class RewriteFlushesCoalesce(unittest.TestCase):
    def test_exactly_one_flush_on_the_init_path(self):
        on_init = MAIN.count("flush_rewrite_rules(")
        for name in CALLERS:
            on_init += (INCLUDES / name).read_text(encoding="utf-8").count("flush_rewrite_rules(")
        # activation + deactivation keep theirs; everything else is ONE call.
        activate = _function_body(MAIN, "alt_activate").count("flush_rewrite_rules(")
        deactivate = _function_body(MAIN, "alt_deactivate").count("flush_rewrite_rules(")
        self.assertEqual(activate, 1)
        self.assertEqual(deactivate, 1)
        self.assertEqual(on_init - activate - deactivate, 1,
                         "expected one coalesced flush_rewrite_rules on init, found %d"
                         % (on_init - activate - deactivate))

    def test_the_one_flush_runs_at_init_priority_100_behind_a_flag(self):
        body = _function_body(MAIN, "alt_rewrite_flush_if_requested")
        self.assertTrue("flush_rewrite_rules(false)" in body)
        self.assertTrue("add_action('init', 'alt_rewrite_flush_if_requested', 100);" in MAIN, "no priority-100 hook")
        self.assertTrue("function alt_request_rewrite_flush(" in MAIN, "no flag setter")

    def test_every_caller_keeps_its_option_and_raises_the_flag(self):
        for name, option in CALLERS.items():
            src = (INCLUDES / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertTrue("get_option('%s') === ALT_VERSION" % option in src, "option read lost")
                self.assertTrue("update_option('%s', ALT_VERSION, false)" % option in src, "option write lost")
                self.assertTrue("alt_request_rewrite_flush()" in src, "%s does not raise the flag" % name)
                self.assertFalse("flush_rewrite_rules(" in src, "%s still flushes itself" % name)


if __name__ == "__main__":
    unittest.main()
