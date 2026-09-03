"""The worldwide path must not LOSE a window to a cap or an early return.

Production telemetry showed a single run returning 900 / kept 99 / dropped 801,
one query capped and one window abandoned — every recent run had both. These
tests pin the rearchitecture that closes those leaks, all hermetic (the fetch and
the BigQuery client are injected; no test touches the network):

  1. a capped window BISECTS until every sub-window is under the cap;
  2. a window that stays capped to the split floor is PARTIAL, never truncated;
  3. the BigQuery mirror is PAGINATED deterministically and walked to completion;
  4. an unfinished slot PERSISTS in the work ledger and a later run completes it;
  5. mirror recovery does NOT skip the run's other sweeps (no early return);
  6. a run with any incomplete slot reports DEGRADED, not green.

Import note: this module never imports `cdp`, so run_tests.py files it under the
non-browser `rest` group, where the rest of the GDELT tests live.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gdelt_reach  # noqa: E402
from sources import gdelt, gdelt_bq  # noqa: E402


W_START = datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc)
W_END = W_START + timedelta(hours=36)


def _article(url, seendate="20260820T120000Z"):
    return {"url": url, "domain": "reuters.com", "title": "layoffs", "seendate": seendate}


class Bisection(unittest.TestCase):
    """A capped window is split until each half is under the cap."""

    def setUp(self):
        gdelt_reach.reset()

    def test_capped_window_bisects_until_under_cap(self):
        max_records = 5
        floor = gdelt.MIN_BISECT_WINDOW
        calls = []

        def fake_query(query, start, end, mr, label="broad"):
            calls.append((start, end))
            span = end - start
            # The full window still caps; once split to an 18h half it is under.
            if span > timedelta(hours=18):
                return [_article(f"cap-{len(calls)}-{i}") for i in range(mr)], False, None
            return [_article(f"ok-{len(calls)}-{i}") for i in range(2)], False, None

        with patch.object(gdelt, "_query_window", fake_query):
            arts, status, _rl, _err = gdelt._collect_window(
                gdelt.QUERY, W_START, W_END, max_records, "broad", floor)

        # One full-window query that capped, then exactly its two halves.
        self.assertEqual(len(calls), 3)
        self.assertEqual(status, "complete")
        # Parent's capped page (5) plus each under-cap half (2 + 2).
        self.assertEqual(len(arts), 9)

    def test_window_capped_to_the_floor_is_partial_not_truncated(self):
        max_records = 5
        floor = gdelt.MIN_BISECT_WINDOW
        calls = []

        def always_capped(query, start, end, mr, label="broad"):
            calls.append((start, end))
            return [_article(f"c-{len(calls)}-{i}") for i in range(mr)], False, None

        with patch.object(gdelt, "_query_window", always_capped):
            arts, status, _rl, _err = gdelt._collect_window(
                gdelt.QUERY, W_START, W_END, max_records, "broad", floor)

        self.assertEqual(status, "partial")
        # It stopped at the floor rather than splitting forever.
        self.assertLess(len(calls), 400)
        self.assertGreater(len(arts), 0)


class MirrorPagination(unittest.TestCase):
    """The BigQuery mirror walks a multi-page window to completion."""

    def _rows(self, prefix, n, base_ts=20260820120000):
        return [{"url": f"{prefix}-{i}", "domain": "reuters.com",
                 "date_int": base_ts + i, "title": "layoffs"} for i in range(n)]

    def test_deterministic_pagination_walks_a_multipage_window(self):
        seen_cursors = []
        limit = gdelt_bq.MIRROR_LIMIT
        pages = [self._rows("p1", limit), self._rows("p2", limit, base_ts=20260820130000),
                 self._rows("p3", 7, base_ts=20260820140000)]

        def fake_page(start, end, terms, after=None, limit=limit):
            seen_cursors.append(after)
            return pages[len(seen_cursors) - 1]

        articles, complete = gdelt_bq.query_window_walk(
            W_START, W_END, ["layoffs"], page_limit=limit, page_fn=fake_page)

        self.assertTrue(complete)
        # Every row across all three pages, none dropped.
        self.assertEqual(len(articles), 2 * limit + 7)
        # First call has no cursor; each later call resumes strictly after the
        # previous page's last (date_int, url) — that is what walks the tail.
        self.assertIsNone(seen_cursors[0])
        self.assertEqual(seen_cursors[1], (20260820120000 + limit - 1, f"p1-{limit - 1}"))
        self.assertEqual(seen_cursors[2], (20260820130000 + limit - 1, f"p2-{limit - 1}"))

    def test_hitting_the_page_ceiling_reports_incomplete(self):
        limit = 3

        def always_full(start, end, terms, after=None, limit=limit):
            return [{"url": f"u-{after}-{i}", "domain": "reuters.com",
                     "date_int": 20260820120000 + i, "title": "x"} for i in range(limit)]

        _articles, complete = gdelt_bq.query_window_walk(
            W_START, W_END, ["x"], page_limit=limit, max_pages=3, page_fn=always_full)
        self.assertFalse(complete)  # never reached a short page -> not proven complete


class RunLevelBehaviour(unittest.TestCase):
    """pull_gdelt_between: no early return, honest health, durable retry."""

    def setUp(self):
        gdelt_reach.reset()
        gdelt._LAST_RUN_INCOMPLETE = False
        # Return the collected list unchanged: these tests exercise window
        # collection, not the trust gate or the article fetch (both need network).
        self._fetch_patch = patch.object(gdelt, "_fetch_trusted", lambda arts: list(arts))
        self._fetch_patch.start()
        self.addCleanup(self._fetch_patch.stop)
        # These tests pin the mirror/query-API machinery; the published-files
        # path (first in preference since 2026-09-03) has its own tests in
        # test_gdelt_raw_feed.py and would otherwise reach the network here.
        self._raw_patch = patch.object(gdelt, "_raw_feed_applies", lambda s, e: False)
        self._raw_patch.start()
        self.addCleanup(self._raw_patch.stop)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write('{"slots": {}}')
        tmp.close()
        self.ledger_path = tmp.name
        self.addCleanup(lambda: os.path.exists(self.ledger_path) and os.unlink(self.ledger_path))

    def _read_ledger(self):
        with open(self.ledger_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_mirror_recovery_still_runs_the_other_sweeps(self):
        segment_calls = []

        def fake_query(query, start, end, mr, label="broad"):
            if label == "broad":
                return None, True, "HTTP 429"      # public API abandons the window
            segment_calls.append(query)
            return [_article("seg-1")], False, None

        def fake_mirror(start, end):
            return [_article("mirror-1")], "complete"

        with patch.object(gdelt, "_query_window", fake_query), \
             patch.object(gdelt, "_collect_mirror", fake_mirror), \
             patch.object(gdelt, "_planned_sweeps", lambda: [("segment", '"California"')]), \
             patch.object(gdelt_bq, "available", lambda: True):
            out = gdelt.pull_gdelt_between(
                W_START, W_END, max_records=5, ledger_path=self.ledger_path)

        urls = {a["url"] for a in out}
        # The recovered window is ASSIGNED and the sweep STILL ran (no early return).
        self.assertIn("mirror-1", urls)
        self.assertIn("seg-1", urls)
        self.assertEqual(segment_calls, ['"California"'])

    def test_capped_broad_window_reports_degraded_not_green(self):
        def always_capped(query, start, end, mr, label="broad"):
            return [_article(f"c-{i}") for i in range(mr)], False, None

        with patch.object(gdelt, "_query_window", always_capped), \
             patch.object(gdelt, "_planned_sweeps", lambda: []):
            gdelt.pull_gdelt_between(
                W_START, W_END, max_records=5, ledger_path=self.ledger_path)

        self.assertEqual(gdelt.last_run_status(), "degraded")
        ledger = self._read_ledger()
        broad = [s for s in ledger["slots"].values() if s["family"] == "broad"]
        self.assertEqual(len(broad), 1)
        self.assertEqual(broad[0]["status"], "partial")
        self.assertTrue(broad[0]["cap_hit"])

    def test_unfinished_slot_persists_and_a_later_run_completes_it(self):
        # --- Run 1: broad completes, the one segment sweep is abandoned. -----
        def run1_query(query, start, end, mr, label="broad"):
            if label == "broad":
                return [_article("broad-1")], False, None
            return None, True, "HTTP 429"          # segment abandoned

        with patch.object(gdelt, "_query_window", run1_query), \
             patch.object(gdelt, "_planned_sweeps", lambda: [("segment", '"Texas"')]):
            gdelt.pull_gdelt_between(
                W_START, W_END, max_records=5, ledger_path=self.ledger_path)

        self.assertEqual(gdelt.last_run_status(), "degraded")
        ledger = self._read_ledger()
        seg = [s for s in ledger["slots"].values() if s["family"] == "segment"]
        self.assertEqual(len(seg), 1)
        self.assertEqual(seg[0]["status"], "failed")
        self.assertEqual(seg[0]["query_text"], '"Texas"')  # stored so it can be re-issued

        # --- Run 2: a later window, NO planned sweeps of its own. The only way
        # the segment slot can finish is the cross-run pending-retry path. ----
        later_start = W_START + timedelta(hours=2)
        later_end = W_END + timedelta(hours=2)

        def run2_query(query, start, end, mr, label="broad"):
            return [_article("ok")], False, None    # everything succeeds now

        with patch.object(gdelt, "_query_window", run2_query), \
             patch.object(gdelt, "_planned_sweeps", lambda: []):
            gdelt.pull_gdelt_between(
                later_start, later_end, max_records=5, ledger_path=self.ledger_path)

        ledger = self._read_ledger()
        seg = [s for s in ledger["slots"].values() if s["family"] == "segment"]
        self.assertEqual(len(seg), 1)
        self.assertEqual(seg[0]["status"], "complete")   # the pending slot got finished
        self.assertGreaterEqual(seg[0]["attempts"], 2)
        self.assertEqual(gdelt.last_run_status(), "ok")

    def test_outage_breaker_queues_remaining_sweeps_after_first_abandoned(self):
        # 2026-08-27 (run 33094996142): api.gdeltproject.org went dark, every
        # planned sweep ground through its full retry schedule, and the
        # historical-sweep workflow cancelled ITSELF at 45 minutes — losing the
        # ledger save. One abandoned sweep = QUERY_ATTEMPTS straight failures,
        # so the rest must be QUEUED (window + query text kept, no attempt
        # spent), not attempted against a dead API.
        attempted = []

        def api_dies_after_broad(query, start, end, mr, label="broad"):
            if label == "broad":
                return [_article("broad-1")], False, None
            attempted.append(query)
            return None, True, "HTTP 429"          # every sweep would abandon

        sweeps = [("segment", '"Texas"'), ("segment", '"Ohio"'),
                  ("euphemism", '"quiet part"')]
        with patch.object(gdelt, "_query_window", api_dies_after_broad), \
             patch.object(gdelt, "_planned_sweeps", lambda: list(sweeps)):
            gdelt.pull_gdelt_between(
                W_START, W_END, max_records=5, ledger_path=self.ledger_path)

        # Only the FIRST sweep was attempted; the breaker stopped the rest.
        self.assertEqual(attempted, ['"Texas"'])
        self.assertEqual(gdelt.last_run_status(), "degraded")
        ledger = self._read_ledger()
        by_query = {s.get("query_text"): s for s in ledger["slots"].values()
                    if s["family"] != "broad"}
        self.assertEqual(by_query['"Texas"']["status"], "failed")
        self.assertEqual(by_query['"Texas"']["attempts"], 1)
        # Queued slots keep their query text for the retry path and spent no attempt.
        self.assertEqual(by_query['"Ohio"']["status"], "queued")
        self.assertEqual(by_query['"Ohio"']["attempts"], 0)
        self.assertEqual(by_query['"quiet part"']["status"], "queued")

        # --- A later healthy run picks the queued slots up via the pending path.
        def healthy(query, start, end, mr, label="broad"):
            return [_article("ok")], False, None

        with patch.object(gdelt, "_query_window", healthy), \
             patch.object(gdelt, "_planned_sweeps", lambda: []):
            gdelt.pull_gdelt_between(
                W_START + timedelta(hours=2), W_END + timedelta(hours=2),
                max_records=5, ledger_path=self.ledger_path)

        ledger = self._read_ledger()
        statuses = {s.get("query_text"): s["status"] for s in ledger["slots"].values()
                    if s["family"] != "broad"}
        self.assertEqual(statuses['"Ohio"'], "complete")
        self.assertEqual(statuses['"quiet part"'], "complete")

    def test_outage_breaker_stops_the_pending_retry_walk_too(self):
        # Six pending slots against a dead API is the same unbounded grind:
        # the retry walk must stop at the first abandoned slot, leaving the
        # rest pending (their natural, durable state).
        # Seed a ledger with three pending slots inside the retry horizon.
        ledger = {"slots": {}}
        for i, q in enumerate(('"A"', '"B"', '"C"')):
            key = gdelt._slot_key("segment", q, W_START, W_END)
            ledger["slots"][key] = {
                "family": "segment", "query_text": q,
                "window_start": gdelt._win_stamp(W_START),
                "window_end": gdelt._win_stamp(W_END),
                "status": "queued", "returned": 0, "cap_hit": False,
                "oldest": None, "newest": None, "attempts": 0,
                "first_seen": gdelt._win_stamp(W_START),
                "updated": gdelt._win_stamp(W_START)}
        with open(self.ledger_path, "w", encoding="utf-8") as fh:
            json.dump(ledger, fh)

        attempted = []

        def api_dead_for_sweeps(query, start, end, mr, label="broad"):
            if label == "broad":
                return [_article("broad-1")], False, None
            attempted.append(query)
            return None, True, "HTTP 429"

        with patch.object(gdelt, "_query_window", api_dead_for_sweeps), \
             patch.object(gdelt, "_planned_sweeps", lambda: []):
            gdelt.pull_gdelt_between(
                W_START, W_END + timedelta(hours=1), max_records=5,
                ledger_path=self.ledger_path)

        # Exactly one pending slot was tried; the walk stopped there.
        self.assertEqual(len(attempted), 1)
        after = self._read_ledger()
        pending = [s for s in after["slots"].values()
                   if s["family"] != "broad" and s["status"] in ("queued", "failed")]
        self.assertEqual(len(pending), 3)  # 1 failed + 2 still queued, none lost

    def test_fully_abandoned_broad_window_still_raises_loudly(self):
        # No mirror available, public API abandons: a genuine failed batch that
        # must be non-zero (cron -> degraded), not a silent empty run.
        def dead(query, start, end, mr, label="broad"):
            return None, True, "HTTP 429"

        with patch.object(gdelt, "_query_window", dead), \
             patch.object(gdelt, "_planned_sweeps", lambda: []), \
             patch.object(gdelt_bq, "available", lambda: False):
            with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                gdelt.pull_gdelt_between(
                    W_START, W_END, max_records=5, ledger_path=self.ledger_path)


class SweepCollectionRespectsTheDeadline(unittest.TestCase):
    """The rotating sweep loop is the unbounded phase (run 33094996142,
    2026-08-27): the broad slot went through the BigQuery mirror in seconds,
    then ten rotating sweeps hit the throttled public API one after another --
    each one patient (QUERY_ATTEMPTS x QUERY_BACKOFF_SECONDS backoff) with no
    clock of its own -- and the job was killed by timeout-minutes with the
    third sweep still retrying. gdelt_backfill.py already computes a run-wide
    BACKFILL_DEADLINE_SECONDS budget, but only consulted it in the
    post-collection extraction loop; collection itself had no ceiling. This
    pins that pull_gdelt_between stops STARTING new sweeps once the deadline
    has passed, the same way reason_backfill.py's single run-wide clock does
    (tests/test_job_deadlines.py).
    """

    def setUp(self):
        gdelt_reach.reset()
        gdelt._LAST_RUN_INCOMPLETE = False
        self._fetch_patch = patch.object(gdelt, "_fetch_trusted", lambda arts: list(arts))
        self._fetch_patch.start()
        self.addCleanup(self._fetch_patch.stop)
        # These tests pin the mirror/query-API machinery; the published-files
        # path (first in preference since 2026-09-03) has its own tests in
        # test_gdelt_raw_feed.py and would otherwise reach the network here.
        self._raw_patch = patch.object(gdelt, "_raw_feed_applies", lambda s, e: False)
        self._raw_patch.start()
        self.addCleanup(self._raw_patch.stop)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write('{"slots": {}}')
        tmp.close()
        self.ledger_path = tmp.name
        self.addCleanup(lambda: os.path.exists(self.ledger_path) and os.unlink(self.ledger_path))

    def test_no_new_sweep_starts_once_the_deadline_has_passed(self):
        now = [0.0]
        started = []

        def fake_query(query, start, end, mr, label="broad"):
            if label == "broad":
                return [], False, None
            started.append(label)
            # Simulate this sweep's own retries burning the whole budget, the
            # way ten throttled QUERY_ATTEMPTS x QUERY_BACKOFF_SECONDS retries
            # did in the real run -- only the NEXT deadline check can catch it.
            now[0] = 999.0
            return [_article(f"{label}-1")], False, None

        with patch.object(gdelt, "_query_window", fake_query), \
             patch.object(gdelt, "_planned_sweeps",
                          lambda: [("segment", "a"), ("native", "b"), ("euphemism", "c")]), \
             patch.object(gdelt.time, "monotonic", lambda: now[0]):
            gdelt.pull_gdelt_between(
                W_START, W_END, max_records=5, ledger_path=self.ledger_path, deadline=500.0)

        self.assertEqual(started, ["segment"],
                         "a sweep started after the deadline had already passed")
        self.assertEqual(gdelt.last_run_status(), "degraded")

    def test_no_deadline_means_unbounded_as_before(self):
        started = []

        def fake_query(query, start, end, mr, label="broad"):
            if label == "broad":
                return [], False, None
            started.append(label)
            return [_article(f"{label}-1")], False, None

        with patch.object(gdelt, "_query_window", fake_query), \
             patch.object(gdelt, "_planned_sweeps",
                          lambda: [("segment", "a"), ("native", "b")]):
            gdelt.pull_gdelt_between(
                W_START, W_END, max_records=5, ledger_path=self.ledger_path)

        self.assertEqual(started, ["segment", "native"])


if __name__ == "__main__":
    unittest.main()
