"""The weekly CI-noise report: one email naming the causes, or none at all.

The sibling tracker measured the failure mode this guards against: 180 red
runs in a week for a handful of already-reported facts, each one a GitHub
failure notification in the owner's inbox, AFTER the per-run alert path was
already deduplicated by cause. The weekly report is the regression alarm over
the structural fixes, so its arithmetic is pinned here: what counts as noise,
what stays signal, and above all that a quiet week sends NOTHING and that
"could not check" never reads as quiet. Offline, no network, no keys.
"""
import io
import re
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_alert
import ci_noise_report as cnr

NOW = datetime(2026, 8, 3, 12, 20, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=7)


def _run(run_id, workflow, conclusion, days_ago=1, job_count=1,
         event="schedule", status="completed"):
    created = NOW - timedelta(days=days_ago)
    return {
        "databaseId": run_id,
        "workflowName": workflow,
        "status": status,
        "conclusion": conclusion,
        "createdAt": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "job_count": job_count,
    }


class ClassifyTests(unittest.TestCase):

    def test_a_quiet_week_is_zero_noise(self):
        runs = [_run(1, "Ingest layoffs", "success"), _run(2, "Tests", "success")]
        self.assertEqual(cnr.classify(runs, {}, SINCE)["noise"], 0)

    def test_the_first_red_of_a_cause_is_signal_not_noise(self):
        """Category-(a) protection as arithmetic: one real failure that
        alerted once contributes ZERO to the noise count. This report must
        never become a pressure to silence real alarms."""
        runs = [_run(1, "WARN import", "failure")]
        result = cnr.classify(runs, {"1": "HTTP 503 from wisconsin"}, SINCE)
        self.assertEqual(result["failed_runs"], 1)
        self.assertEqual(result["repeats"], 0)
        self.assertEqual(result["noise"], 0)

    def test_repeats_of_one_cause_count_as_noise(self):
        """The Spirit assertion reddened CI eight times in one afternoon;
        that week this line would have read 'repeats: 7'."""
        cause = ("AssertionError: 461648 != 435627 : the aggregate must "
                 "exclude superset members")
        runs = [_run(i, "Tests", "failure") for i in range(1, 9)]
        causes = {str(i): cause for i in range(1, 9)}
        self.assertEqual(cnr.classify(runs, causes, SINCE)["repeats"], 7)

    def test_causes_differing_only_in_numbers_are_one_cause(self):
        """Same normalisation as the alert email (ci_alert.normalise), so the
        weekly count can never disagree with the dedup that throttled it."""
        runs = [_run(1, "Tests", "failure"), _run(2, "Tests", "failure")]
        causes = {"1": "AssertionError: 461648 != 435627",
                  "2": "AssertionError: 461650 != 435629"}
        self.assertEqual(cnr.classify(runs, causes, SINCE)["repeats"], 1)

    def test_unread_causes_group_per_workflow_not_across(self):
        """Past the log cap the workflow is known and the cause is not. Two
        unread failures in one workflow plausibly repeat; across two
        workflows they are plausibly two facts, and neither is a repeat."""
        runs = [_run(1, "Tests", "failure"), _run(2, "Tests", "failure"),
                _run(3, "WARN import", "failure")]
        result = cnr.classify(runs, {}, SINCE)
        self.assertEqual(result["repeats"], 1)
        by_group = {(wf, cause): n for wf, cause, n in result["causes"]}
        self.assertEqual(by_group[("Tests", cnr.UNREAD)], 2)
        self.assertEqual(by_group[("WARN import", cnr.UNREAD)], 1)

    def test_a_zero_job_cancellation_is_noise_and_a_started_one_is_not(self):
        """Zero jobs is the concurrency-displacement fingerprint — a run that
        vanished with no record anywhere in the UI. A run cancelled after it
        started is a human or a timeout, and judging it here would punish
        legitimate cancellations."""
        runs = [_run(1, "EDGAR history sweep (rotating)", "cancelled", job_count=0),
                _run(2, "Unemployment-claims backdrop", "cancelled", job_count=1)]
        result = cnr.classify(runs, {}, SINCE)
        self.assertEqual(len(result["evictions"]), 1)
        self.assertEqual(result["evictions"][0]["run_id"], "1")
        self.assertEqual(result["noise"], 1)

    def test_an_unknown_job_count_is_not_read_as_zero(self):
        """Absence of a signal is never a pass — and never a finding either.
        A cancelled run whose job count could not be read must not be counted
        as an eviction on no evidence."""
        runs = [_run(1, "Tests", "cancelled", job_count=None)]
        self.assertEqual(cnr.classify(runs, {}, SINCE)["noise"], 0)

    def test_runs_outside_the_window_do_not_count(self):
        runs = [_run(1, "Tests", "failure", days_ago=9),
                _run(2, "Tests", "cancelled", days_ago=10, job_count=0)]
        result = cnr.classify(runs, {"1": "boom"}, SINCE)
        self.assertEqual(result["failed_runs"], 0)
        self.assertEqual(result["noise"], 0)

    def test_an_unfinished_run_is_not_judged(self):
        runs = [_run(1, "Tests", None, status="in_progress")]
        self.assertEqual(cnr.classify(runs, {}, SINCE)["window_runs"], 0)


class ComposeTests(unittest.TestCase):

    def _noisy(self):
        runs = [_run(i, "Tests", "failure") for i in (1, 2)]
        return cnr.classify(runs, {"1": "boom", "2": "boom"}, SINCE)

    def test_the_key_carries_the_week_so_next_week_is_a_new_cause(self):
        """The endpoint suppresses repeats of an OPEN cause. Without the week
        in the key, week two's report would be swallowed as a duplicate of
        week one's — a reporting channel that self-silences."""
        result = self._noisy()
        _s, _b, key1 = cnr.compose(result, repo="dk-forge/x", days=7, now=NOW)
        _s, _b, key2 = cnr.compose(result, repo="dk-forge/x", days=7,
                                   now=NOW + timedelta(days=7))
        self.assertNotEqual(key1, key2)
        self.assertTrue(key1.startswith("ci-noise:"))

    def test_the_body_marks_singletons_as_correct_not_noisy(self):
        runs = [_run(1, "WARN import", "failure"),
                _run(2, "Tests", "failure"), _run(3, "Tests", "failure")]
        result = cnr.classify(runs, {"1": "real", "2": "rep", "3": "rep"}, SINCE)
        _s, body, _k = cnr.compose(result, repo="dk-forge/x", days=7, now=NOW)
        self.assertIn("reported once, correctly", body)
        self.assertIn("1 repeat red(s)", body)


class MainTests(unittest.TestCase):
    """main() through fakes: no gh, no network, no keys."""

    def _patch(self, runs, causes=None):
        self.sent = []
        # main() derives its window from the wall clock, while every fixture
        # below is stamped relative to the fixed NOW. Without this seam the
        # class passed for seven days and then went red on the eighth, on a
        # schedule, with no code change on either side: the fixture runs aged
        # out of main()'s own 7-day window and it took the quiet-week early
        # return. ClassifyTests and ComposeTests already inject the same
        # instant explicitly via SINCE / now=; this gives MainTests the same
        # footing rather than re-dating the fixtures, which would only move
        # the expiry.
        self._orig = (cnr.fetch_runs, cnr.attach_job_counts, cnr._now,
                      cnr.ci_alert.fetch_failed_log,
                      cnr.ci_alert.extract_cause, cnr.ci_alert.post_alert)
        cnr._now = lambda: NOW
        cnr.fetch_runs = lambda repo, limit: runs
        cnr.attach_job_counts = lambda r, repo: r
        cnr.ci_alert.fetch_failed_log = (
            lambda repo, run_id: (causes or {}).get(str(run_id), ""))
        cnr.ci_alert.extract_cause = lambda log: (log, [])
        cnr.ci_alert.post_alert = (
            lambda site, key, payload, **kw:
            self.sent.append(payload) or (True, "delivered", False))

    def tearDown(self):
        if hasattr(self, "_orig"):
            (cnr.fetch_runs, cnr.attach_job_counts, cnr._now,
             cnr.ci_alert.fetch_failed_log,
             cnr.ci_alert.extract_cause, cnr.ci_alert.post_alert) = self._orig
        import os
        os.environ.pop("RESEND_API_KEY", None)

    def _main(self, argv, **env):
        import os
        os.environ.pop("RESEND_API_KEY", None)
        os.environ.update(env)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cnr.main(argv)
        return code, buf.getvalue()

    def test_a_quiet_week_posts_nothing_and_says_so(self):
        self._patch([_run(1, "Tests", "success")])
        code, out = self._main([], RESEND_API_KEY="k")
        self.assertEqual(code, 0)
        self.assertEqual(self.sent, [], "no noise means NO post")
        self.assertIn("quiet week", out)

    def test_a_noisy_week_posts_exactly_one_alert(self):
        runs = [_run(i, "Tests", "failure") for i in range(1, 5)]
        self._patch(runs, {str(i): "same cause" for i in range(1, 5)})
        code, _out = self._main([], RESEND_API_KEY="k")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.sent), 1, "one summary, never one per run")
        self.assertIn("3 noisy run(s)", self.sent[0]["subject"])

    def test_dry_run_posts_nothing_even_when_noisy(self):
        runs = [_run(i, "Tests", "failure") for i in (1, 2)]
        self._patch(runs, {"1": "x", "2": "x"})
        code, out = self._main(["--dry-run"], RESEND_API_KEY="k")
        self.assertEqual(code, 0)
        self.assertEqual(self.sent, [])
        self.assertIn("--- subject ---", out)

    def test_noise_with_no_credentials_is_loud_not_silent(self):
        """No WP_SITE_URL/WP_API_KEY fallback: mail moved to Resend on
        2026-08-19, and RESEND_API_KEY is the only credential this path
        reads now (see opsmail.configured())."""
        runs = [_run(i, "Tests", "failure") for i in (1, 2)]
        self._patch(runs, {"1": "x", "2": "x"})
        code, out = self._main([])
        self.assertEqual(code, 1)
        self.assertIn("NOT sent", out)
        self.assertIn("RESEND_API_KEY", out)

    def test_an_unreachable_gh_is_unknown_never_a_quiet_week(self):
        """PASS, FAIL and UNKNOWN are three states: 'could not read the run
        list' exits 3, the could-not-check code, so it can never be filed as
        a clean week."""
        self._patch([])

        def boom(repo, limit):
            raise cnr.GhUnavailable("no gh here")
        cnr.fetch_runs = boom
        code, out = self._main([])
        self.assertEqual(code, 3)
        self.assertIn("could not read the run list", out)


class WorkflowFileTests(unittest.TestCase):

    def test_the_report_is_scheduled_weekly_and_holds_undeliverables(self):
        text = (Path(__file__).resolve().parents[2]
                / ".github" / "workflows" / "ci-noise-report.yml").read_text()
        self.assertIn("* * 1'", text.replace("  ", " "),
                      "weekly, on Mondays")
        self.assertIn("alert_outbox.py enqueue", text,
                      "an undeliverable report is HELD, not lost")
        self.assertNotIn("|| true", text)


class KeyShapeTests(unittest.TestCase):
    """The composed key must be a key /alert will ACCEPT.

    Measured in the sibling tracker on 2026-08-03: `compose()` formatted the
    ISO week with `%G-W%V`, minting `ci-noise:2026-W32`. The endpoint validates
    both `dedupe_key` and `resolve_scope` against
    `^[a-z0-9][a-z0-9:._-]{0,159}$`, so the uppercase W came back HTTP 400
    `bad dedupe_key` — a SETTLED failure no amount of retrying can fix. The
    report was held in the outbox, retried 16 times, went `stuck`, and the host
    watchdog then failed every tick on "alerts are stuck with the host up". A
    watchdog that is permanently red cannot report an outage, so one bad
    character in a cache key disabled the outage alarm.

    This repo shipped the identical `%G-W%V` and had simply not had a noisy
    enough week to fire it yet.
    """

    def _endpoint_regex(self):
        """The literal the PHP endpoint actually validates against, read from
        source. Mirroring a regex in two languages is only safe if a test
        fails when the two drift apart."""
        php = (Path(__file__).resolve().parents[2] / "wordpress-plugin"
               / "ai-layoff-tracker" / "includes" / "api.php").read_text()
        found = re.search(r"\$safe\s*=\s*'/\^(.*?)\$/';", php)
        self.assertIsNotNone(
            found, "alt_api_alert() no longer declares $safe as a literal, so "
                   "the Python mirror in ci_alert.KEY_SAFE is now unpinned")
        return found.group(1)

    def test_the_python_mirror_matches_the_endpoint_literal(self):
        self.assertEqual(ci_alert.KEY_SAFE.pattern.strip("^$"),
                         self._endpoint_regex())

    def test_the_composed_key_is_accepted_by_the_endpoint_shape(self):
        """Across a whole year, so no week number, month or year boundary can
        mint a character the endpoint rejects."""
        runs = [_run(i, "WARN import", "failure") for i in (1, 2)]
        result = cnr.classify(runs, {}, SINCE)
        endpoint = re.compile("^" + self._endpoint_regex() + "$")
        for offset in range(0, 366, 7):
            moment = NOW + timedelta(days=offset)
            subject, _body, key = cnr.compose(
                result, repo="dk-forge/ai-layoff-tracker", days=7, now=moment)
            self.assertRegex(key, endpoint, f"rejected key on {moment.date()}")
            self.assertRegex(key, ci_alert.KEY_SAFE)
            # The subject quotes the same token, so the email in the inbox can
            # be tied to the key in the endpoint's open-alert state.
            self.assertIn(key.split(":", 1)[1], subject)

    def test_an_uppercase_week_would_have_been_caught(self):
        """The bug itself as a fixture: proof this test is able to fail."""
        self.assertNotRegex("ci-noise:2026-W32", ci_alert.KEY_SAFE)


class StdlibOnlyTests(unittest.TestCase):

    def test_the_reporter_needs_no_venv(self):
        """Like ci_alert.py: a reporting path must not be breakable by a
        dependency resolution failure. ci_alert itself is already held to
        this bar by test_ci_alert. opsmail is the same kind of exception —
        it is the local, stdlib-only Resend transport (see its own module
        docstring), not a pip dependency."""
        import ast
        tree = ast.parse((Path(cnr.__file__)).read_text())
        imported = {
            name.name.split(".")[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for name in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        }
        self.assertEqual(
            imported - set(sys.stdlib_module_names) - {"ci_alert", "opsmail"},
            set())


if __name__ == "__main__":
    unittest.main()
