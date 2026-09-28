"""The source-archive backfill's URL-dedup + status logic + fail-open behavior.

Invariants:
  1. Candidate URLs are de-duplicated and non-http values dropped, so a capture
     is never wasted on a value the store would reject.
  2. The availability parser accepts only a real, usable (2xx/3xx) snapshot and
     normalizes it to https; anything else yields None (no fake link).
  3. classify_outcome records 'archived' ONLY with a real permalink; a throttle,
     a failure, or nothing found leaves the URL 'pending' for a later run.
  4. Every network helper fails OPEN: a transport error yields None / pending
     and never raises, so Wayback being down can only defer coverage.
"""
import os
import sys
import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import archive_backfill as ab  # noqa: E402


class DedupeTests(unittest.TestCase):
    def test_dedupes_and_drops_non_http(self):
        urls = [
            " https://x.test/a ",           # trimmed
            "https://x.test/a",             # exact dup after trim
            "http://x.test/b",
            "",                             # blank dropped
            "ftp://x.test/c",               # non-http dropped
            "not a url",                    # dropped
            "https://x.test/d",
        ]
        self.assertEqual(
            ab.dedupe_urls(urls),
            ["https://x.test/a", "http://x.test/b", "https://x.test/d"],
        )

    def test_empty_and_none(self):
        self.assertEqual(ab.dedupe_urls([]), [])
        self.assertEqual(ab.dedupe_urls(None), [])


class AvailabilityParseTests(unittest.TestCase):
    def test_returns_https_permalink_when_available(self):
        payload = {"archived_snapshots": {"closest": {
            "available": True, "status": "200",
            "url": "http://web.archive.org/web/20240101000000/https://x.test/a"}}}
        self.assertEqual(
            ab.parse_availability(payload),
            "https://web.archive.org/web/20240101000000/https://x.test/a")

    def test_no_snapshot_returns_none(self):
        self.assertIsNone(ab.parse_availability({"archived_snapshots": {}}))
        self.assertIsNone(ab.parse_availability({}))
        self.assertIsNone(ab.parse_availability({"archived_snapshots": {"closest": {"available": False}}}))

    def test_rejects_non_content_snapshot(self):
        # A stored 404 snapshot is a receipt of a dead page, not a usable copy.
        payload = {"archived_snapshots": {"closest": {
            "available": True, "status": "404",
            "url": "http://web.archive.org/web/1/https://x.test/a"}}}
        self.assertIsNone(ab.parse_availability(payload))

    def test_garbage_payload_returns_none(self):
        self.assertIsNone(ab.parse_availability(None))
        self.assertIsNone(ab.parse_availability("nope"))


class ClassifyOutcomeTests(unittest.TestCase):
    def test_availability_hit_is_archived(self):
        self.assertEqual(
            ab.classify_outcome("https://web.archive.org/web/1/https://x.test", ""),
            ("archived", "https://web.archive.org/web/1/https://x.test"))

    def test_save_hit_is_archived(self):
        self.assertEqual(
            ab.classify_outcome(None, "https://web.archive.org/web/2/https://x.test"),
            ("archived", "https://web.archive.org/web/2/https://x.test"))

    def test_rate_limited_is_pending_not_archived(self):
        self.assertEqual(ab.classify_outcome(None, ab.RATE_LIMITED), ("pending", ""))

    def test_nothing_found_is_pending(self):
        self.assertEqual(ab.classify_outcome(None, ""), ("pending", ""))
        self.assertEqual(ab.classify_outcome(None, None), ("pending", ""))

    def test_never_archived_without_real_permalink(self):
        # A non-URL string must never be recorded as an archived link.
        self.assertEqual(ab.classify_outcome(None, "error"), ("pending", ""))


class FailOpenTests(unittest.TestCase):
    def test_check_availability_swallows_exceptions(self):
        session = mock.Mock()
        session.get.side_effect = OSError("net down")
        self.assertIsNone(ab.check_availability("https://x.test/a", session))

    def test_check_availability_non_200_is_none(self):
        session = mock.Mock()
        session.get.return_value = mock.Mock(status_code=503)
        self.assertIsNone(ab.check_availability("https://x.test/a", session))

    def test_save_page_now_swallows_exceptions(self):
        session = mock.Mock()
        session.get.side_effect = OSError("net down")
        self.assertIsNone(ab.save_page_now("https://x.test/a", session))

    def test_save_page_now_reports_rate_limit(self):
        session = mock.Mock()
        session.get.return_value = mock.Mock(status_code=429, headers={}, url="")
        self.assertEqual(ab.save_page_now("https://x.test/a", session), ab.RATE_LIMITED)

    def test_save_page_now_returns_content_location_permalink(self):
        resp = mock.Mock(status_code=200,
                         headers={"Content-Location": "/web/20240101/https://x.test/a"},
                         url="https://web.archive.org/save/https://x.test/a")
        session = mock.Mock(); session.get.return_value = resp
        self.assertEqual(ab.save_page_now("https://x.test/a", session),
                         "https://web.archive.org/web/20240101/https://x.test/a")



class BatchStampsLandBeforeNextFetch(unittest.TestCase):
    """2026-09-28: a batch's sub-FLUSH_EVERY remainder was still buffered when
    the next /archive-candidates fetch ran, so the server re-served it."""

    def test_no_url_is_reserved_when_the_server_honours_stamps(self):
        pool = [f"https://example.com/{i}" for i in range(40)]
        stamped = set()

        def fetch():
            due = [u for u in pool if u not in stamped][:15]
            return due, {}

        def post(items):
            stamped.update(i["url"] for i in items)
            return {"pending": len(items)}

        out = io.StringIO()
        with mock.patch.object(ab, "fetch_candidates", side_effect=fetch), \
             mock.patch.object(ab, "post_records", side_effect=post), \
             mock.patch.object(ab, "check_availability", return_value=None), \
             mock.patch.object(ab, "report_source_health", return_value=True), \
             mock.patch.object(ab, "LIMIT", 40), mock.patch.object(ab, "FLUSH_EVERY", 25), \
             mock.patch.object(ab, "SPN_MAX", 0), mock.patch.object(ab, "DRY_RUN", False), \
             mock.patch.object(ab, "HANDOFF_FILE", ""), \
             mock.patch.object(ab.requests.Session, "get", side_effect=Exception("offline")), \
             redirect_stdout(out):
            ab.run()
        self.assertEqual(stamped, set(pool))
        self.assertNotIn("re-served", out.getvalue())

if __name__ == "__main__":
    unittest.main()


class TestRecheckStampsMustStick(unittest.TestCase):
    """2026-09-27: the run processed one 500-URL batch a day, then read the
    server re-serving those same URLs as "0 candidates" and stopped, so the
    oldest attempt advanced 11 minutes a day. A re-served recorded URL must be
    counted, and an unacknowledged write must be counted, never hidden."""

    def test_reserved_recorded_urls_are_counted_not_hidden(self):
        new, reserved = ab.split_batch(["a", "b", "c"], {"a", "b"})
        self.assertEqual(new, ["c"])
        self.assertEqual(reserved, 2)

    def test_handoff_urls_are_expected_to_come_back(self):
        new, reserved = ab.split_batch(["a", "h"], {"a", "h"}, ["h"])
        self.assertEqual(new, [])
        self.assertEqual(reserved, 1)

    def test_empty_server_batch_is_drained_not_reserved(self):
        self.assertEqual(ab.split_batch([], {"a"}), ([], 0))

    def test_unacknowledged_writes_are_counted(self):
        items = [{"url": "a"}, {"url": "b"}, {"url": "c"}]
        self.assertEqual(ab.unacknowledged(items, {"archived": 1, "pending": 1, "unavailable": 1}), 0)
        self.assertEqual(ab.unacknowledged(items, {"pending": 1, "rejected": ["b", "c"]}), 2)
        self.assertEqual(ab.unacknowledged(items, None), 3)

    def test_configured_capacity_covers_the_live_pool_inside_the_promise(self):
        # Live 2026-09-27: 3,071 due, 7d promise -> 439/day needed. Capacity is
        # not the constraint; the stamps not sticking is. Pin that it stays so.
        import re
        wf = open(os.path.join(os.path.dirname(__file__), "..", "..", ".github",
                               "workflows", "archive-backfill.yml")).read()
        limit = int(re.search(r"inputs\.limit \|\| '(\d+)'", wf).group(1))
        deadline = int(re.search(r"ARCHIVE_BACKFILL_DEADLINE_SECONDS: '(\d+)'", wf).group(1))
        per_day = min(limit, int(deadline * 0.513))
        self.assertGreaterEqual(per_day, -(-3071 // 7))
