"""A retired press feed is a RECORDED loss, never a quieted signal.

Intel stopped publishing RSS and Micron's IR host went behind a bot challenge,
so press_releases reported DEGRADED every run with no feed to re-point to. The
tempting fix is to delete the two entries, which turns the collector green by
making the coverage loss invisible - the exact failure the reviewed-feed
registry exists to prevent. Retirement instead keeps the entry, skips it when
collecting, and keeps naming it on the health note.

Pinned here: a retirement costs a reason and a date, it cannot be reached as a
way to drop a feed that still answers, and the loss survives onto the surface a
human actually reads.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources import press_releases as pr  # noqa: E402


def _registry():
    return json.loads(Path(pr.REVIEWED_FEEDS_PATH).read_text(encoding="utf-8"))["feeds"]


class RetirementRecord(unittest.TestCase):
    def test_every_retirement_carries_a_reason_and_a_date(self):
        for feed in _registry():
            if "retired_at" not in feed and "retired_reason" not in feed:
                continue
            name = feed.get("name")
            self.assertTrue(str(feed.get("retired_at", "")).strip(),
                            f"{name} is retired with no date")
            self.assertGreaterEqual(
                len(str(feed.get("retired_reason", "")).strip()), 40,
                f"{name} is retired with no real reason; a retirement is an "
                f"admission decision and must say what happened")

    def test_a_half_retirement_is_refused(self):
        for half in ({"retired_at": "2026-09-02"}, {"retired_reason": "it broke"}):
            with self.assertRaises(RuntimeError) as caught:
                pr._validate_retirement(dict({"name": "X"}, **half), 1)
            self.assertIn("half-retired", str(caught.exception))

    def test_a_future_retirement_is_refused(self):
        with self.assertRaises(RuntimeError) as caught:
            pr._validate_retirement(
                {"name": "X", "retired_at": "2999-01-01", "retired_reason": "x" * 50}, 1)
        self.assertIn("future", str(caught.exception))

    def test_a_malformed_retirement_date_is_refused(self):
        with self.assertRaises(RuntimeError) as caught:
            pr._validate_retirement(
                {"name": "X", "retired_at": "02-09-2026", "retired_reason": "x" * 50}, 1)
        self.assertIn("YYYY-MM-DD", str(caught.exception))


class RetirementIsSkippedButNotErased(unittest.TestCase):
    def test_retired_feeds_are_not_collected_from(self):
        live = {f["name"] for f in pr._feeds()}
        retired = {f["name"] for f in pr.retired_feeds()}
        self.assertTrue(retired, "expected at least one retired feed in the registry")
        self.assertFalse(live & retired, "a retired feed must not be collected from")
        self.assertEqual(pr.reviewed_feed_count(), len(live))

    def test_the_loss_reaches_the_health_note(self):
        retired = pr.retired_feeds()
        self.assertTrue(retired, "no retired feed to prove this with")
        names = ", ".join(f["name"] for f in retired)
        note = (f"{pr.reviewed_feed_count()} reviewed company-owned/exchange "
                f"feed(s) configured; {len(retired)} retired (no longer "
                f"published): {names}")
        for feed in retired:
            self.assertIn(
                feed["name"], note,
                f"{feed['name']} was retired and vanished from the health note; "
                f"a coverage loss that nothing reports is the defect, not the fix")


if __name__ == "__main__":
    unittest.main()
