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
import tempfile
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


QUEUED_NOTE = "No archive snapshot yet. This source has not been checked yet; first check by"
UNAVAILABLE_NOTE = "Not in the Internet Archive yet. We keep checking weekly; next check by"

# Words that would announce a retirement. The re-check gate never retires a
# URL: ALT_ARCHIVE_MAX_ATTEMPTS moves it from the 72h 'pending' retry ONTO the
# ALT_ARCHIVE_RECHECK_DAYS gate, and it is re-checked from there forever. On
# 2026-08-15 the oldest un-archived attempt in the whole 3,462-URL pool was 4.9
# days old. Copy claiming we stopped would be false in the reader's favour.
STOP_WORDS = ("no longer check", "stopped checking", "given up", "gave up",
              "will not check", "final check", "we stop")


def _render_all_states(retry_hours, recheck_days, run_utc):
    """The three note sentences as PHP and JS actually render them.

    EXECUTED, not pattern-matched. The property under test is that a cadence
    constant moves the printed date, and only running the two renderers can
    show that. A regex would pass on a renderer that had quietly started
    printing a literal.
    """
    php = _render_php(retry_hours, recheck_days, run_utc)
    js = _render_js(retry_hours, recheck_days, run_utc)
    assert php == js, (
        "db.php and layoffs.js disagree about the archive note.\n"
        f"  php: {php}\n  js:  {js}")
    return php


def _php_fn(name):
    # _php_function_body() stops AT the closing brace, so put it back.
    body = data_integrity._php_function_body(DB_PHP, name)
    assert body, f"{name} missing from db.php"
    return body + "\n}"


def _js_fn(name):
    m = re.search(r"^    function " + name + r"\(.*?^    \}", LAYOFFS_JS, re.M | re.S)
    assert m, f"{name} missing from layoffs.js"
    return m.group(0)


# A fixed instant, so the assertions are about the constants and never about
# the day the suite happens to run.
NOW = "2026-08-15 12:00:00"
STATES = (("queued", ""), ("pending", "2026-08-14 06:00:00"), ("unavailable", "2026-08-10 07:36:24"))


def _render_php(retry_hours, recheck_days, run_utc):
    src = [
        "<?php",
        # A namespace so the frozen time() below shadows the builtin: PHP
        # resolves an unqualified internal call to the current namespace first,
        # and time() cannot be redefined globally.
        "namespace ArchiveNoteHarness;",
        "define('HOUR_IN_SECONDS', 3600); define('DAY_IN_SECONDS', 86400);",
        f"define('ALT_ARCHIVE_RETRY_HOURS', {retry_hours});",
        f"define('ALT_ARCHIVE_RECHECK_DAYS', {recheck_days});",
        f"define('ALT_ARCHIVE_DAILY_RUN_UTC', '{run_utc}');",
        "function esc_html($s) { return $s; }",
        # Freeze time: the renderers clamp a past eligibility to "now", so a
        # real clock would make the queued row's date drift with the calendar.
        f"function time() {{ return strtotime('{NOW} UTC'); }}",
        _php_fn("alt_archive_next_check_date"),
        _php_fn("alt_archive_note_text"),
        "$out = array();",
        "foreach ([" + ", ".join(f"['{s}', '{c}']" for s, c in STATES) + "] as $p) {",
        "  $out[] = alt_archive_note_text($p[0], alt_archive_next_check_date($p[0], $p[1]));",
        "}",
        "echo json_encode($out);",
    ]
    return _run_interpreter(["php"], "\n".join(src), ".php")


def _render_js(retry_hours, recheck_days, run_utc):
    h, mi = run_utc.split(":")
    src = [
        "function escapeHtml(s) { return s; }",
        f"var ARCHIVE_RETRY_HOURS = {retry_hours}, ARCHIVE_RECHECK_DAYS = {recheck_days},"
        f" ARCHIVE_RUN_UTC = [{int(h)}, {int(mi)}];",
        f"Date.now = function () {{ return Date.parse('{NOW.replace(' ', 'T')}Z'); }};",
        _js_fn("archiveNextCheckDate").strip(),
        _js_fn("archiveNoteText").strip(),
        "var out = [" + ", ".join(
            "archiveNoteText({archive_status: '%s', archive_checked_at: '%s'})" % (s, c)
            for s, c in STATES) + "];",
        "console.log(JSON.stringify(out));",
    ]
    return _run_interpreter(["node"], "\n".join(src), ".js")


def _run_interpreter(cmd, src, suffix):
    import subprocess
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as fh:
        fh.write(src)
        path = fh.name
    try:
        p = subprocess.run(cmd + [path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    if p.returncode != 0:
        raise AssertionError(f"{cmd[0]} failed rendering the archive note:\n{p.stderr}")
    return json.loads(p.stdout.strip())


def _have(binary):
    import shutil
    return shutil.which(binary) is not None


def _interpreters_missing():
    """'' when both renderers can be executed, else why not.

    IN CI THIS IS NEVER A SKIP. ubuntu-latest ships php and node, so a missing
    one there means the runner image changed under us, and quietly skipping the
    only test that EXECUTES the two renderers would leave the promise unchecked
    while the suite went green. Locally it skips, because a contributor without
    php should not see a red suite for it -- and the skip says so out loud
    rather than being invisible in a dot.
    """
    missing = [b for b in ("php", "node") if not _have(b)]
    if not missing:
        return ""
    why = f"{' and '.join(missing)} not installed, so both renderers cannot be executed"
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise AssertionError(
            f"{why}. On CI this is a FAILURE, not a skip: this is the only test that runs "
            "db.php and layoffs.js for real, and a silent skip would leave the archive "
            "promise unverified behind a green suite. Install php and node in tests.yml.")
    return why + " (local skip; CI fails instead)"


@unittest.skipIf(_interpreters_missing(), _interpreters_missing() or "interpreters present")
class ThreeStatesSayThreeDifferentTrueThings(unittest.TestCase):
    """One flattened sentence told a URL nothing had looked at that it had been
    re-checked. Before 2.20.51 all three archive states printed "No archive
    snapshot yet. We re-check weekly; next check by <date>", including 'queued',
    which has no archive row at all and has never been attempted.
    """

    def test_the_three_states_are_distinct(self):
        queued, pending, unavailable = _render_all_states(72, 4, "05:25")
        self.assertEqual(len({queued, pending, unavailable}), 3,
                         "two archive states print the same sentence again")
        self.assertIn(QUEUED_NOTE, queued)
        self.assertIn(PROMISE, pending)
        self.assertIn(UNAVAILABLE_NOTE, unavailable)

    def test_a_never_attempted_row_does_not_claim_a_re_check(self):
        queued = _render_all_states(72, 4, "05:25")[0]
        self.assertNotIn("re-check", queued,
                         "a 'queued' URL has no archive row and has never been attempted; "
                         "calling its first look a re-check is the defect 2.20.51 fixed")
        self.assertIn("first check by", queued)

    def test_unavailable_never_announces_a_stop_we_do_not_make(self):
        """'unavailable' is not a retirement. ALT_ARCHIVE_MAX_ATTEMPTS moves a
        URL onto the re-check gate; nothing takes it off. Measured 2026-08-15:
        oldest un-archived attempt 4.9d against a 7d promise."""
        unavailable = _render_all_states(72, 4, "05:25")[2].lower()
        for phrase in STOP_WORDS:
            self.assertNotIn(phrase, unavailable,
                             f"the 'unavailable' note claims we stopped checking ({phrase!r}); "
                             "the cron re-checks it forever on ALT_ARCHIVE_RECHECK_DAYS")
        self.assertIn("keep checking", unavailable)

    def test_moving_a_cadence_constant_moves_every_printed_date(self):
        """The one-definition property, executed rather than asserted.

        A constant is only the single definition if changing it changes what
        every reader sees. This renders both renderers at the live cadence and
        again at a slower one, and fails if any dated state sits still. It is
        the guard that would catch a renderer that started printing a literal
        date, or a JS mirror left behind when the PHP moved.
        """
        base = _render_all_states(72, 4, "05:25")
        slower = _render_all_states(96, 9, "05:25")
        # 'pending' is gated by RETRY_HOURS, 'unavailable' by RECHECK_DAYS.
        self.assertNotEqual(base[1], slower[1],
                            "ALT_ARCHIVE_RETRY_HOURS moved and the 'pending' date did not")
        self.assertNotEqual(base[2], slower[2],
                            "ALT_ARCHIVE_RECHECK_DAYS moved and the 'unavailable' date did not")
        # 'queued' has no last attempt, so it is gated by the daily run time only.
        later_run = _render_all_states(72, 4, "18:40")
        self.assertNotEqual(base[0], later_run[0],
                            "ALT_ARCHIVE_DAILY_RUN_UTC moved and the 'queued' date did not")

    def test_no_em_or_en_dash_in_any_state(self):
        for note in _render_all_states(72, 4, "05:25"):
            self.assertNotIn("—", note, f"em-dash in UI copy: {note}")
            self.assertNotIn("–", note, f"en-dash in UI copy: {note}")

    def test_every_state_stays_inside_the_copy_budget(self):
        for note in _render_all_states(72, 4, "05:25"):
            self.assertLessEqual(len(note.split()), 30, f"note over the 30-word cap: {note}")


def _run(payload):
    inv = ArchiveRecheckInvariant()
    ctx = data_integrity.Ctx(lambda url, timeout: json.dumps(payload).encode(), 5, "cb")
    return inv.run(ctx)


class InvariantJudgesHonestly(unittest.TestCase):
    # A HEALTHY margin by default, so the age-half tests below keep testing the
    # age half. 3,900 due at 4,000/day re-checked over 48h is a ~1-day cycle.
    BASE = {"distinct_source_urls": 25029, "archived": 21110, "pending": 3800,
            "unavailable": 110, "queued": 9, "coverage_pct": 84.3, "recheck_days": 7,
            "unarchived_live": 3910, "rechecked_recent": 8000, "recheck_window_hours": 48}

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


class TheCheckWarnsBeforeThePromiseBreaks(unittest.TestCase):
    """A check that only fails once the published claim is already false is not
    a check, it is a post-mortem.

    Every number below is measured, from the archive-backfill run logs and the
    live /archive-coverage payload on 2026-08-04 and 2026-08-06.
    """

    BASE = dict(InvariantJudgesHonestly.BASE)

    def _payload(self, age_days, **over):
        stamp = (datetime.now(timezone.utc) - timedelta(days=age_days)).strftime("%Y-%m-%d %H:%M:%S")
        return dict(self.BASE, oldest_unarchived_checked_at=stamp, **over)

    def test_the_2026_08_04_reading_that_passed_would_now_fail(self):
        """THE REGRESSION THIS FILE EXISTS FOR.

        On 2026-08-04 the invariant read 8.6d against a 10d bound and PASSED.
        Two days later it read 11.7d and the pages had been promising a weekly
        re-check the cron was not delivering. The pool and the throughput were
        both visible on 08-04: 3,864 due, a measured 500/run once a day. That
        is a 7.7d cycle and an 8.7d worst age, past the 8d projected bound, so
        the margin was 1.4 days wide and nothing said so.
        """
        r = _run(self._payload(8.6, unarchived_live=3864,
                               rechecked_recent=1000, recheck_window_hours=48))
        self.assertEqual(r.state, FAIL,
                         "the 2026-08-04 numbers must fail on the projection while the "
                         "reading is still inside the bound")
        self.assertIn("about to become false", r.detail)
        self.assertIn("inside the 10d bound TODAY", r.detail)

    def test_the_post_fix_throughput_passes_the_same_reading(self):
        """Same pool, same day, the 2,000/run this change ships: 1.9d cycle."""
        r = _run(self._payload(8.6, unarchived_live=3782,
                               rechecked_recent=4000, recheck_window_hours=48))
        self.assertEqual(r.state, PASS)
        self.assertIn("projected bound", r.detail)

    def test_a_stopped_cron_is_a_failure_not_a_fresh_reading(self):
        """Right after the pool is drained the reading is young, so the age half
        alone would pass for days while nothing ran at all.

        REVISED 2026-08-14. The trigger is being OVERDUE, not merely idle. A
        re-check is gated: a URL is ineligible until ALT_ARCHIVE_RECHECK_DAYS
        after its last attempt, so a window with zero re-checks in it while the
        oldest attempt is younger than the gate means the server had nothing to
        hand out — which is what the live runs actually do (run 31756911580 read
        "batch 2: 0 candidate URL(s)" and finished). Once the oldest attempt is
        older than the gate there ARE overdue URLs, and zero is a stall. That
        still catches it days before the 10d reading does, which is the point of
        the test; it just no longer fires on a healthy idle day.
        """
        r = _run(self._payload(9.0, recheck_days=7, unarchived_live=3782,
                               rechecked_recent=0))
        self.assertEqual(r.state, FAIL)
        self.assertIn("NOTHING was re-checked", r.detail)

    def test_an_idle_window_inside_the_gate_is_the_gate_working(self):
        """The other half of the same rule, and the reason it had to change: at
        a 4-day gate the whole pool is re-attempted in a convoy and then nothing
        is due for days. Failing on that is failing on the system working."""
        r = _run(self._payload(1.0, recheck_days=4, unarchived_live=3782,
                               rechecked_recent=0))
        self.assertEqual(r.state, PASS, r.detail)
        self.assertIn("nothing was DUE", r.detail)

    def test_an_old_build_leaves_the_margin_unknown_never_a_pass(self):
        """A server that does not publish the margin fields must not be read as
        a healthy margin. Absence of a signal is not a pass."""
        old = {k: v for k, v in self.BASE.items()
               if k not in ("unarchived_live", "rechecked_recent", "recheck_window_hours")}
        stamp = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        r = _run(dict(old, oldest_unarchived_checked_at=stamp))
        self.assertEqual(r.state, UNKNOWN)
        self.assertIn("MARGIN is unmeasured", r.detail)

    def test_a_completed_pass_is_not_overruled_by_a_two_day_sample(self):
        """THE 2026-08-14 FALSE FAIL, pinned as a PASS.

        Live /archive-coverage that morning, byte for byte: 3,480 due, 593
        re-checked in 48h, oldest un-archived attempt 3.9 days old, gate 4 days.
        The projection read 296/day -> an 11.7d cycle and reddened `Tests` for
        three days, naming archive-backfill.yml. The workflow was innocent twice
        over: run 31756911580 asked for a second batch and was handed
        "0 candidate URL(s)", because at a 4-day gate the pool is re-attempted in
        a convoy and nothing is due in between.

        The site's own timestamps settle it. An oldest attempt of 3.9d means
        EVERY un-archived URL was attempted within 3.9 days, so the pool
        completed a full pass in 3.9 days — the thing the projection was trying
        to estimate, measured directly, four days better than the estimate and
        well inside the 7-day promise. A rate sampled over 2 days cannot measure
        a 4-day cycle.
        """
        r = _run(self._payload(3.9, recheck_days=4, unarchived_live=3480,
                               rechecked_recent=593, recheck_window_hours=48))
        self.assertEqual(r.state, PASS, r.detail)
        self.assertIn("completed a pass", r.detail)
        self.assertIn("is not believed", r.detail)

    def test_the_early_warning_still_fires_where_it_was_written_to(self):
        """The rule above must not be able to excuse the case the projection
        exists for. On 2026-08-04 the age was already 8.6d, so the direct
        reading contradicts nothing and the FAIL stands — two days before the
        10d reading would have caught it."""
        r = _run(self._payload(8.6, unarchived_live=3864, rechecked_recent=1000))
        self.assertEqual(r.state, FAIL)
        self.assertIn("about to become false", r.detail)

    def test_no_bound_was_widened_to_get_that_pass(self):
        """The cheap way to silence 2026-08-14 was to move a number. None moved:
        a session reading this can check the four constants against the
        published sentence without re-deriving anything."""
        self.assertEqual(ArchiveRecheckInvariant.PROMISE_DAYS, 7)
        self.assertEqual(ArchiveRecheckInvariant.RUN_GRANULARITY_DAYS, 1)
        self.assertEqual(ArchiveRecheckInvariant.PROJECTED_MAX_AGE_DAYS, 8)
        self.assertEqual(ArchiveRecheckInvariant.MAX_AGE_DAYS, 10)

    def test_the_projected_bound_is_derived_from_the_published_promise(self):
        # "We re-check weekly" + one day of daily-run granularity. It is
        # deliberately TIGHTER than MAX_AGE_DAYS: the 2 days of slack exist to
        # absorb a missed run, not to be spent as normal operating margin.
        self.assertEqual(ArchiveRecheckInvariant.PROJECTED_MAX_AGE_DAYS, 7 + 1)
        self.assertLess(ArchiveRecheckInvariant.PROJECTED_MAX_AGE_DAYS,
                        ArchiveRecheckInvariant.MAX_AGE_DAYS)

    def test_the_age_half_still_fails_on_its_own(self):
        """The projection must not be able to excuse a broken promise: a
        healthy margin with a blown reading is still a FAIL."""
        r = _run(self._payload(11.7, unarchived_live=3782, rechecked_recent=8000))
        self.assertEqual(r.state, FAIL)
        self.assertIn("promising a re-check", r.detail)


class TheRunCanActuallyReachItsOwnLimit(unittest.TestCase):
    """ARCHIVE_BACKFILL_LIMIT is a promise about throughput. If the deadline
    stops the run first, the limit is a number that never happens and the
    cadence is sized off a capacity that does not exist. That is exactly how
    this broke: the workflow advertised 1,500 URLs a run and delivered a median
    of 500, because the 2400s deadline (itself clamped by a 3000s cap in the
    module) ended every run mid-pool.
    """

    # Read from SOURCE, not by importing: archive_backfill needs `requests`, and
    # a guard about arithmetic must not be skippable because a network library
    # is missing. Same reason ab_extraction_models.score() imports nothing.
    BACKFILL_PY = (REPO / "railway" / "archive_backfill.py").read_text(encoding="utf-8")

    def _yml_env(self, name):
        m = re.search(name + r":\s*\$\{\{\s*github\.event\.inputs\.\w+\s*\|\|\s*'(\d+)'\s*\}\}",
                      BACKFILL_YML)
        if not m:
            m = re.search(name + r":\s*'(\d+)'", BACKFILL_YML)
        self.assertIsNotNone(m, f"{name} not found in archive-backfill.yml")
        return int(m.group(1))

    def _py_const(self, name):
        m = re.search(rf"^{name} = ([\d./ ]+)$", self.BACKFILL_PY, re.M)
        self.assertIsNotNone(m, f"{name} not found in archive_backfill.py")
        return eval(m.group(1))          # noqa: S307 - a numeric literal we just matched

    def test_the_deadline_is_long_enough_to_reach_the_limit(self):
        limit = self._yml_env("ARCHIVE_BACKFILL_LIMIT")
        deadline = self._yml_env("ARCHIVE_BACKFILL_DEADLINE_SECONDS")
        cap = self._py_const("DEADLINE_CAP_SECONDS")
        rate = self._py_const("MEASURED_URLS_PER_SECOND")
        effective = min(cap, deadline)
        reachable = effective * rate
        self.assertGreaterEqual(
            reachable, limit,
            f"the workflow asks for {limit} URLs a run but its {deadline}s deadline "
            f"(clamped to {effective}s by DEADLINE_CAP_SECONDS) only reaches "
            f"{reachable:.0f} at the measured {rate:.3f} URL/s. The limit is a "
            f"capacity the run never delivers.")

    def test_the_module_cap_does_not_silently_clamp_the_workflow(self):
        """A cap quietly cutting the configured deadline in half is the same
        defect one layer down, and it leaves no trace in any log."""
        deadline = self._yml_env("ARCHIVE_BACKFILL_DEADLINE_SECONDS")
        self.assertGreaterEqual(
            self._py_const("DEADLINE_CAP_SECONDS"), deadline,
            "archive_backfill.DEADLINE_CAP_SECONDS is below the deadline the workflow "
            "sets, so the run stops earlier than the workflow says it does")

    def test_the_deadline_stays_inside_the_job_timeout(self):
        """The deadline exists so the run stops ITSELF, cleanly, having flushed
        its records. A run killed by the Actions timeout loses the tail."""
        m = re.search(r"timeout-minutes:\s*(\d+)", BACKFILL_YML)
        self.assertIsNotNone(m, "archive-backfill.yml lost its job timeout")
        job_timeout_s = int(m.group(1)) * 60
        deadline = self._yml_env("ARCHIVE_BACKFILL_DEADLINE_SECONDS")
        self.assertLess(deadline, job_timeout_s - 600,
                        "less than 10 minutes between the script's deadline and the job "
                        "timeout leaves no room for checkout, install and the final flush")


class TheGateLeavesRoomToKeepThePromise(unittest.TestCase):
    """The re-check GATE sets the throughput ceiling. The workflow cannot.

    2026-08-13: archive_recheck_cadence went red projecting a 15.8d cycle, and
    every arrow in the failure message pointed at archive-backfill.yml. The
    workflow was innocent. On 4 of the 5 preceding days the run drained the due
    pool and stopped on an EMPTY batch -- 08-13 took 14 candidates and finished
    in 5 minutes against a 2,000 limit and a 5,400s deadline; 08-11 took 1,230
    and stopped the same way. A bigger batch or a second daily run would have
    been handed zero extra URLs on those days.

    What had moved was the pool's composition: 'pending' fell 3,698 -> 195 and
    'unavailable' rose 0 -> 3,381 as URLs crossed ALT_ARCHIVE_MAX_ATTEMPTS, so
    almost the whole pool left the 72h retry gate for the weekly one. A pool
    gated at 7 days cycles in 7 days, which is exactly the cycle the invariant
    demands, so the check sat on its own bound and flipped on sampling noise.

    These two tests pin the arithmetic that makes that unarguable, so the next
    session to meet this red does not answer it by raising the batch size.
    """

    def _gate_days(self):
        return int(_php_define("ALT_ARCHIVE_RECHECK_DAYS"))

    def test_the_gate_is_short_enough_to_cycle_inside_the_projected_bound(self):
        """Worst-case composition is the whole pool on the weekly gate, which is
        what 2026-08-13 actually looked like. Then the best cycle any workflow
        can reach IS the gate, and the worst age is gate + run granularity."""
        worst_age = self._gate_days() + ArchiveRecheckInvariant.RUN_GRANULARITY_DAYS
        self.assertLessEqual(
            worst_age, ArchiveRecheckInvariant.PROJECTED_MAX_AGE_DAYS - 2,
            f"ALT_ARCHIVE_RECHECK_DAYS = {self._gate_days()} caps the achievable cycle "
            f"at {worst_age}d worst age against a {ArchiveRecheckInvariant.PROJECTED_MAX_AGE_DAYS}d "
            f"projected bound. Under 2 days of margin means the check rides its own "
            f"bound and flips on which side of a run the 48h window lands. Shorten the "
            f"GATE -- no value of ARCHIVE_BACKFILL_LIMIT can reach over it.")

    def test_a_fully_drained_pool_on_this_gate_passes_the_invariant(self):
        """End to end, not just an inequality: feed the invariant the very best
        throughput this gate permits and require a PASS. At a 7-day gate this
        fails, which is the whole point."""
        pool = 3529                      # live, 2026-08-13
        gate = self._gate_days()
        window_h = 48
        # A perfectly drained, perfectly spread pool: pool/gate URLs a day.
        rechecked = int(pool / gate * (window_h / 24))
        stamp = (datetime.now(timezone.utc) - timedelta(days=gate)).strftime("%Y-%m-%d %H:%M:%S")
        r = _run({"distinct_source_urls": 25206, "archived": 21742, "pending": 195,
                  "unavailable": 3381, "queued": 0, "coverage_pct": 86.3,
                  "oldest_unarchived_checked_at": stamp, "recheck_days": gate,
                  "unarchived_live": pool, "rechecked_recent": rechecked,
                  "recheck_window_hours": window_h})
        self.assertEqual(
            r.state, PASS,
            f"the best throughput a {gate}-day gate allows ({rechecked / 2:.0f}/day over a "
            f"{pool:,} pool) still does not satisfy archive_recheck_cadence: {r.detail}")


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
                             f"railway/recall_measurement.json — recall_goldset."
                             f"write_measurement() writes both, so re-run the writer "
                             f"rather than editing either file")

    def test_only_one_function_writes_either_measurement_file(self):
        """The cause of the 24-vs-52 drift: two writers, one of which wrote one file.

        `recall_goldset.py --write` is the path a human takes right after an
        adjudication moves the figure, and it used to write ONLY the canonical
        file, leaving the live page publishing the superseded number. Any new
        writer must go through write_measurement(), which writes both.
        """
        rail = REPO / "railway"
        offenders = []
        for path in sorted(rail.glob("*.py")):
            src = path.read_text(encoding="utf-8")
            for name in ("MEASUREMENT_PATH", "PLUGIN_MEASUREMENT_PATH"):
                for m in re.finditer(rf"\b{name}\b[^\n]*\.write_text", src):
                    line = src[:m.start()].count("\n") + 1
                    if path.name == "recall_goldset.py":
                        continue
                    offenders.append(f"{path.name}:{line}")
        self.assertEqual(offenders, [],
                         "a second writer of the recall measurement files: only "
                         "recall_goldset.write_measurement() may write them, or the "
                         "canonical figure and the figure the site publishes drift again "
                         f"({offenders})")

    def test_write_measurement_refreshes_both_files(self):
        sys.path.insert(0, str(REPO / "railway"))
        try:
            import recall_goldset
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "recall_measurement.json"
            render = Path(tmp) / "plugin" / "recall-measurement.json"
            render.parent.mkdir()
            render.write_text(json.dumps({
                "matched": 24, "reference_events": 57,
                "reference_set_id": "sec-item-205-us-2025-07_2026-06",
                "measured_at": "2026-08-10T16:30:56Z",
                "precision_verbatim": {"ok": 40, "checked": 40,
                                       "measured_at": "2026-08-10"}}) + "\n")
            measurement = {"matched": 52, "reference_events": 57,
                           "reference_set_id": "sec-item-205-us-2025-07_2026-06",
                           "measured_at": "2026-08-12T23:44:31Z"}
            # No precision sample — the `recall_goldset.py --write` path.
            wrote = recall_goldset.write_measurement(
                measurement, None, measurement_path=canonical, plugin_path=render)
            self.assertTrue(wrote, "a moved figure must rewrite the render copy")
            out = json.loads(render.read_text())
            self.assertEqual(out["matched"], 52)
            self.assertEqual(out["measured_at"], "2026-08-12T23:44:31Z")
            self.assertEqual(json.loads(canonical.read_text())["matched"], 52)
            self.assertEqual(out["precision_verbatim"],
                             {"ok": 40, "checked": 40, "measured_at": "2026-08-10"},
                             "a recall-only re-measure must carry the dated precision "
                             "block forward, not delete the sentence it renders")
            # Idempotent: same figures, no rewrite, so no needless FTPS deploy.
            self.assertFalse(recall_goldset.write_measurement(
                measurement, None, measurement_path=canonical, plugin_path=render))

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


class TheWeeklyArchiverFitsInsideItsOwnCeiling(unittest.TestCase):
    """A job that never finishes cannot keep the promise above.

    "Archive WARN sources to Wayback" had NEVER completed. Both runs it had
    ever had were killed by its own `timeout-minutes: 20` - 20m21s on
    2026-07-27 and 20m19s on 2026-08-03 - and both ended `cancelled`, which the
    CI alerter discarded as routine, so a weekly job that never once ran to the
    end also never said so. On the day this was found the re-check invariant
    read 8.6 days against its 10-day bound: one missed run from breaking the
    sentence the pages print to readers.

    The measurement: 54 source documents, and /save/ is a live crawl, so the
    per-URL ceiling was doing real work. 54 * (90 + 8) = 88 minutes against a
    20-minute job. This pins the arithmetic that replaces it, so no later
    change can quietly put the job back inside a box it cannot fit in.
    """

    def _archiver(self):
        import types
        sys.modules.setdefault("requests", types.ModuleType("requests"))
        import archive_sources
        return archive_sources

    def test_a_full_sweep_fits_inside_the_scripts_own_deadline(self):
        mod = self._archiver()
        total = len(mod.source_urls())
        self.assertGreater(total, 0)
        worst = total * (mod.PER_URL_TIMEOUT + mod.GAP_SECONDS)
        self.assertLessEqual(
            worst, mod.DEADLINE_SECONDS,
            f"{total} URLs at {mod.PER_URL_TIMEOUT}s + {mod.GAP_SECONDS}s gap "
            f"is {worst / 60:.1f} min, past the {mod.DEADLINE_SECONDS / 60:.0f} "
            "min deadline. Either the list grew or a ceiling moved; raise the "
            "deadline AND the workflow timeout together, or the job goes back "
            "to being killed halfway through every week.")

    def test_the_workflow_ceiling_is_above_the_scripts_deadline(self):
        """The script must stop itself FIRST. If the runner gets there first the
        run is `cancelled` again, and a partial sweep becomes a self-timeout
        email instead of a green partial success."""
        mod = self._archiver()
        yml = (REPO / ".github" / "workflows" / "archive-sources.yml").read_text()
        found = re.search(r"timeout-minutes:\s*(\d+)", yml)
        self.assertIsNotNone(found)
        self.assertGreater(int(found.group(1)) * 60, mod.DEADLINE_SECONDS,
                           "the runner would kill the script before its own "
                           "deadline fires, which is the original bug")

    def test_a_truncated_sweep_drops_a_different_tail_each_week(self):
        """Without this, a run that always starts at index 0 and always stops
        early archives the head of the list forever and the tail never - and
        every one of those runs is green. The offset comes from the ISO week
        rather than a cursor file because the runner is ephemeral: a cursor
        would read 0 every single week, which is the starvation bug with extra
        code."""
        mod = self._archiver()
        urls = mod.source_urls()
        base = datetime(2026, 1, 5, tzinfo=timezone.utc)
        offsets = {mod.week_offset(len(urls), base + timedelta(weeks=w))
                   for w in range(8)}
        self.assertGreater(len(offsets), 6, "the rotation barely moves")
        rotated = mod.rotate(urls, mod.week_offset(len(urls), base))
        self.assertEqual(sorted(rotated), sorted(urls),
                         "rotation must not lose or duplicate a document")

    def test_the_deadline_is_checked_before_the_request_not_after(self):
        """Stopping once the clock has already run out is how you get killed
        inside the last capture, which is the failure this replaces."""
        import inspect
        mod = self._archiver()
        src = inspect.getsource(mod.main)
        self.assertIn("spent + PER_URL_TIMEOUT > DEADLINE_SECONDS", src)
        self.assertLess(src.index("DEADLINE_SECONDS"), src.index("archive(url)"))

    def test_a_deadline_truncated_run_is_not_reported_as_wayback_being_down(self):
        """`attempted`, not `total`. A run that archived nothing because it
        attempted nothing is a scheduling problem, and calling it "Wayback
        unreachable" sends a human hunting the wrong thing."""
        import inspect
        mod = self._archiver()
        src = inspect.getsource(mod.main)
        self.assertIn("if attempted and ok == 0:", src)
        self.assertNotIn("if urls and ok == 0:", src)


if __name__ == "__main__":
    unittest.main()
