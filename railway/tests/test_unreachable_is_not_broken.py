"""A host we could not REACH is not a source that BROKE.

THE DEFECT THIS CLOSES
----------------------
On 2026-08-17/18 three separate items sat on `ops_status.py` and every one of
them was the same sentence written three ways: an upstream host did not answer
the datacentre, and the collector converted "could not reach" into a verdict
about our own code.

  * `warn_us` / `warn_custom_legacy` said "LA=33 (floor 324) — likely site
    drift". Louisiana's parser was perfect. 33 is EXACTLY the 21 notices in the
    live 2025 PDF plus the 12 in the live 2026 PDF; laworks.net hosts only the
    current two years, every year 2015-2024 is read from a Wayback snapshot,
    and Wayback was unreachable from the runner that morning. Measured locally
    the same day: `fetch_la()` returns 324. The message accused the only
    component that was working, which is the Quebec failure of 2026-08-13 with
    a different state on the label.
  * `Archive WARN sources to Wayback` went RED with "zero snapshots taken —
    Wayback unreachable?". The question mark is the defect: the run could not
    tell, and it reddened CI for a week on a third-party outage. This repo
    already answered that question for undeliverable alerts — held, not lost,
    and exiting 0 — and an unarchived URL is likewise not lost, because the
    sweep is idempotent and the week rotation re-attempts it.
  * `national_feeds` said "feed broke: economynext_lk: HTTP 202". The feed
    serves valid RSS to a laptop (probed 2026-08-18, all 15 feeds HTTP 200 and
    well-formed). A 202 with a non-feed body is a bot wall keyed on the
    datacentre's address range.

So three guards, one idea in each: an unreachable upstream must be REPORTED as
unreachable, must not be reported as working, and must not be reported as a
defect in the code that reads it.

AND THE OTHER HALF, which is why none of these is a softened assertion: each
guard also pins the case where the host DID answer coherently and we still got
nothing. That is a real defect and must still go red / still say "broke".
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import archive_sources as arch  # noqa: E402
from sources import national_feeds as nf  # noqa: E402
from sources import warn_custom as wc  # noqa: E402

nf.GAP = 0.0


class _Resp:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code = status
        self.content = body if isinstance(body, bytes) else body.encode()
        self.text = self.content.decode("utf-8", "replace")
        self.headers = headers or {}


# ---------------------------------------------------------------------------
# 1. archive_sources: zero snapshots is HELD when the archive is unreachable,
#    and still RED when it is answering.
# ---------------------------------------------------------------------------
class ArchiveZeroSnapshotsTests(unittest.TestCase):
    """`attempted and ok == 0` has two causes and they need two verdicts."""

    def test_probe_reports_unreachable_on_a_transport_error(self):
        def get(url, **kw):
            raise OSError("Connection to web.archive.org timed out")
        self.assertFalse(arch.wayback_reachable(get=get))

    def test_probe_reports_unreachable_on_a_throttle_or_outage_status(self):
        for status in (429, 500, 502, 503):
            with self.subTest(status=status):
                self.assertFalse(
                    arch.wayback_reachable(get=lambda u, s=status, **k: _Resp(s)))

    def test_probe_reports_reachable_when_the_archive_answers(self):
        body = b'{"archived_snapshots": {}}'
        self.assertTrue(
            arch.wayback_reachable(get=lambda u, **k: _Resp(200, body)))

    def test_zero_snapshots_with_an_unreachable_archive_exits_zero(self):
        """Held, not lost: the sweep is idempotent and next week re-attempts."""
        code = arch.verdict(attempted=54, ok=0, total=54, done=54,
                            reachable=False)
        self.assertEqual(code, 0)

    def test_zero_snapshots_while_the_archive_answers_is_still_red(self):
        """The half that must NOT be softened. A coherent archive plus zero
        captures is our defect, and the run has to be able to say so."""
        code = arch.verdict(attempted=54, ok=0, total=54, done=54,
                            reachable=True)
        self.assertEqual(code, 1)

    def test_a_deadline_that_fits_no_capture_is_still_red(self):
        code = arch.verdict(attempted=0, ok=0, total=54, done=0, reachable=True)
        self.assertEqual(code, 1)

    def test_a_normal_sweep_is_green(self):
        self.assertEqual(
            arch.verdict(attempted=54, ok=51, total=54, done=54, reachable=True), 0)


# ---------------------------------------------------------------------------
# 2. national_feeds: every failing feed is named, and a bot wall is not a break.
# ---------------------------------------------------------------------------
class NationalFeedFailureTests(unittest.TestCase):

    def _feeds(self, n=3):
        return tuple(nf.FEEDS[:n])

    def test_every_failing_feed_is_named_not_just_the_last(self):
        """One host answering 202 suggests a CLASS, and until this guard the
        collector could not answer that question about itself: `last_error` was
        a single slot, overwritten per feed, so three dead feeds reported one."""
        feeds = self._feeds(3)
        dead = {f.key for f in feeds[:2]}

        def fetch(url, timeout):
            key = next(f.key for f in feeds if f.url == url)
            return (403, "<html>go away</html>") if key in dead else (200, _RSS)

        nf.pull_national_feeds(feeds=feeds, fetch=fetch)
        named = {f["feed"] for f in nf.pull_national_feeds.failures}
        self.assertEqual(named, dead)
        for key in dead:
            self.assertIn(key, nf.pull_national_feeds.last_error)

    def test_a_bot_wall_status_is_classified_unreachable_not_broken(self):
        feeds = self._feeds(1)
        for status in (202, 403, 429, 503):
            with self.subTest(status=status):
                nf.pull_national_feeds(
                    feeds=feeds,
                    fetch=lambda u, t, s=status: (s, "<html>challenge</html>"))
                self.assertEqual(
                    [f["kind"] for f in nf.pull_national_feeds.failures],
                    ["unreachable"])

    def test_a_dead_or_changed_feed_is_still_classified_broken(self):
        """The half that must NOT be softened: 404/410 is the document gone,
        and a 200 that is not RSS is a changed scheme. Both are ours to fix."""
        feeds = self._feeds(1)
        for status, body in ((404, "nope"), (410, "gone"),
                             (200, "<html>a web page</html>")):
            with self.subTest(status=status):
                nf.pull_national_feeds(
                    feeds=feeds, fetch=lambda u, t, s=status, b=body: (s, b))
                self.assertEqual(
                    [f["kind"] for f in nf.pull_national_feeds.failures],
                    ["broke"])

    def test_a_healthy_sweep_records_no_failure(self):
        feeds = self._feeds(2)
        nf.pull_national_feeds(feeds=feeds, fetch=lambda u, t: (200, _RSS))
        self.assertEqual(nf.pull_national_feeds.failures, [])
        self.assertIsNone(nf.pull_national_feeds.last_error)

    def test_the_health_detail_never_claims_a_blocked_feed_is_working(self):
        """Whatever the wording, a feed the collector cannot read must not
        resolve to `ok` on the health page."""
        status, detail = nf.health_verdict(
            [{"feed": "economynext_lk", "kind": "unreachable",
              "detail": "HTTP 202"}])
        self.assertEqual(status, "degraded")
        self.assertIn("economynext_lk", detail)
        self.assertNotIn("broke", detail.lower())

    def test_the_health_detail_still_says_broke_when_a_feed_broke(self):
        status, detail = nf.health_verdict(
            [{"feed": "jordan_news", "kind": "broke", "detail": "HTTP 404"}])
        self.assertEqual(status, "degraded")
        self.assertIn("broke", detail.lower())

    def test_no_failures_is_ok(self):
        self.assertEqual(nf.health_verdict([])[0], "ok")


_RSS = ("<?xml version='1.0'?><rss version='2.0'><channel>"
        "<item><title>Nothing here</title>"
        "<link>https://example.com/a</link></item></channel></rss>")


# ---------------------------------------------------------------------------
# 3. Louisiana: an unreachable archive is not a collapsed state.
# ---------------------------------------------------------------------------
class LouisianaUnreachableTests(unittest.TestCase):

    def setUp(self):
        wc.SOURCE_UNREACHABLE.clear()

    def test_an_unreachable_wayback_is_recorded_as_unreachable(self):
        """The live site hosts only the current two years, so every earlier
        year rides on Wayback. When Wayback does not answer, the state's count
        is INCOMPLETE, and calling that 'site drift' sends a human to a parser
        that is working."""
        def get(url, **kw):
            # NB the Wayback URL embeds the laworks one, so match on the
            # prefix — a substring test here silently tests nothing.
            if url.startswith("https://www.laworks.net"):
                return _Resp(404, b"<html>not found</html>")
            raise OSError("Connection to web.archive.org timed out")

        wc.fetch_la(get=get)
        self.assertIn("LA", wc.SOURCE_UNREACHABLE)
        self.assertIn("web.archive.org", wc.SOURCE_UNREACHABLE["LA"])

    def test_a_year_genuinely_absent_from_the_archive_is_not_unreachable(self):
        """A coherent 404 from Wayback means no snapshot exists for that year.
        That is a real gap in the archive, not an outage, and must not be
        laundered into 'the network was down'."""
        def get(url, **kw):
            return _Resp(404, b"not in archive")

        wc.fetch_la(get=get)
        self.assertNotIn("LA", wc.SOURCE_UNREACHABLE)

    def test_the_drift_message_separates_unreachable_from_site_drift(self):
        import warn_import as wi
        drift = wi.describe_state_drift(
            ["LA", "OH"], {"LA": 33, "OH": 61},
            {"LA": 324.0, "OH": 787.0},
            unreachable={"LA": "web.archive.org did not answer for 10 year(s)"})
        self.assertIn("LA=33", drift)
        self.assertIn("web.archive.org", drift)
        self.assertNotIn("OH=61 (floor 787) [", drift)
        self.assertIn("OH=61", drift)

    def test_the_message_is_unchanged_when_nothing_was_unreachable(self):
        import warn_import as wi
        self.assertEqual(
            wi.describe_state_drift(["OH"], {"OH": 61}, {"OH": 787.0}),
            "OH=61 (floor 787)")


# ---------------------------------------------------------------------------
# 4. Colorado: a Google-export rate-limit is UNREACHABLE, not a collapsed state.
# ---------------------------------------------------------------------------
class ColoradoUnreachableTests(unittest.TestCase):
    """CDLE publishes the year as Google Sheets workbooks, and Google rate-limits
    a CI runner's IP with a 403/429 HTML body. When every workbook is refused
    that way `fetch_co` used to return 0 rows silently, which the per-state floor
    read as `CO=0 (floor 39) — likely site drift` and sent a human to a parser
    that reads the full year from any un-blocked address. A refusal is UNREACHABLE;
    only a workbook that answered 200 with a real xlsx counts as read."""

    @staticmethod
    def _empty_xlsx():
        """A real, openable workbook with a WARN sheet but no data rows — the
        source answering coherently with nothing, which is not an outage. Starts
        with the PK magic so it also passes the reachability gate."""
        import io
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.title = "2026 WARN"
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def setUp(self):
        wc.SOURCE_UNREACHABLE.clear()

    def test_a_refused_export_is_recorded_as_unreachable(self):
        """Every workbook comes back as a 403 HTML body — the datacentre block.
        CO must be flagged UNREACHABLE, not silently returned as zero rows."""
        def get(url, **kw):
            if "export?format=xlsx" in url:
                return _Resp(403, b"<html>Sorry, too many requests</html>")
            return _Resp(200, b"<html>no ids here</html>")  # landing, no IDs

        out = wc.fetch_co(get=get)
        self.assertEqual(out, [])
        self.assertIn("CO", wc.SOURCE_UNREACHABLE)
        self.assertIn("UNREAD", wc.SOURCE_UNREACHABLE["CO"])

    def test_a_429_throttle_is_also_unreachable(self):
        def get(url, **kw):
            if "export?format=xlsx" in url:
                return _Resp(429, b"<html>rate limited</html>")
            return _Resp(200, b"")
        wc.fetch_co(get=get)
        self.assertIn("CO", wc.SOURCE_UNREACHABLE)

    def test_a_reachable_but_empty_workbook_is_NOT_unreachable(self):
        """The half that must NOT be softened: a 200 with a genuine (if empty)
        xlsx is the source answering coherently. Zero rows there is a real state
        of the data, our finding to make — never laundered into 'the net was
        down'."""
        book = self._empty_xlsx()
        def get(url, **kw):
            if "export?format=xlsx" in url:
                return _Resp(200, book)
            return _Resp(200, b"")
        wc.fetch_co(get=get)
        self.assertNotIn("CO", wc.SOURCE_UNREACHABLE)

    def test_the_drift_message_separates_co_unreachable_from_site_drift(self):
        import warn_import as wi
        drift = wi.describe_state_drift(
            ["CO", "OH"], {"CO": 0, "OH": 61},
            {"CO": 39.0, "OH": 787.0},
            unreachable={"CO": "Google Sheets export refused this runner"})
        self.assertIn("CO", drift)
        self.assertIn("Google Sheets", drift)
        self.assertIn("OH=61", drift)


if __name__ == "__main__":
    unittest.main()
