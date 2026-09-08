"""A CLOUDFLARE 52x IS UNKNOWN, NOT A WRONG NUMBER. 525/526 STILL FAIL.

WHY THIS FILE EXISTS.

Until 2026-09-08 this repo rested on one sentence, written in three places:
"an HTTPError means the site DID answer". It was true while WordPress was the
only thing that could produce a status. After the move to ChemiCloud behind
Cloudflare it is not: the edge mints 520/521/522/523/524 ITSELF when it cannot
get a response out of the origin, so the request never reached WordPress and no
number was ever read. The status is not a statement about the data at all.

The cost of reading it as one is specific. `_excusable` gates whether the unit
suite skips or reddens the push, and `Result.transport` is what ops_status uses
to tell "the site could not be reached" (exit 3) from "the site answered and
answered wrongly" (a human, exit 2). A transient edge blip therefore published
a live-data alarm, which per CLAUDE.md is supposed to mean a wrong number is
already on a public surface. An alarm that fires on a blip stops being read,
and `railway/subscriber_routes.py` had already been fixed for the same defect
on the same day.

WHAT IS PINNED HERE, IN BOTH DIRECTIONS.

  * 520/521/523/524/522 are excusable, transport, and never FAIL, on every one
    of the three paths that read a status: `_excusable`, `Result.transport`,
    and `published_figures._why_unreachable`. Remove the fix and these fail.
  * 525 and 526 are NOT. Those are the Cloudflare-to-origin TLS handshake, a
    durable misconfiguration a human has to clear, and after the move to Full
    (strict) with an Origin CA certificate they are the single most likely real
    defect on this domain. Widen the set to include them and the bound tests
    fail.
  * 503 (the deploy maintenance window) keeps its old meaning, unchanged.
  * an ordinary origin status (404, 500) still reddens: the site answered, on
    exactly the parameterised path a reader uses.
  * the set here and the one in `subscriber_routes` stay identical. They are
    two copies on purpose (that module is standalone, stdlib only, and imports
    nothing from here), so drift is what this asserts against.
"""
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity as di
import published_figures as pf
import subscriber_routes

EDGE = (520, 521, 522, 523, 524)
ORIGIN_TLS = (525, 526)


def _http(code):
    return urllib.error.HTTPError("https://asktherecruiter.com/blog/", code,
                                  "edge", None, None)


class EdgeSetIsBounded(unittest.TestCase):
    def test_the_set_is_exactly_the_five_edge_to_origin_statuses(self):
        self.assertEqual(di._EDGE_TO_ORIGIN, set(EDGE))

    def test_origin_tls_failures_are_excluded(self):
        # THE BOUND. 525/526 mean the edge REACHED the origin and the TLS
        # handshake with it failed. Nothing about that clears on its own.
        for status in ORIGIN_TLS:
            self.assertNotIn(status, di._EDGE_TO_ORIGIN)

    def test_the_two_copies_have_not_drifted(self):
        self.assertEqual(di._EDGE_TO_ORIGIN, subscriber_routes._EDGE_TO_ORIGIN)


class ExcusableGatesThePush(unittest.TestCase):
    def test_edge_statuses_are_excusable(self):
        for status in EDGE:
            self.assertTrue(di._excusable(_http(status)),
                            f"HTTP {status} was minted by the edge, so no number "
                            f"was read; it must not redden a push")

    def test_origin_tls_failures_still_redden(self):
        for status in ORIGIN_TLS:
            self.assertFalse(di._excusable(_http(status)),
                             f"HTTP {status} is a durable origin TLS "
                             f"misconfiguration and must stay loud")

    def test_maintenance_window_and_transport_are_unchanged(self):
        self.assertTrue(di._excusable(_http(503)))
        self.assertTrue(di._excusable(OSError("connection refused")))
        self.assertFalse(di._excusable(None))

    def test_an_ordinary_origin_status_still_reddens(self):
        for status in (400, 404, 418, 500, 502):
            self.assertFalse(di._excusable(_http(status)),
                             f"HTTP {status} came from the origin: it answered, "
                             f"and answered wrongly")


class TransportRoutesTheDashboard(unittest.TestCase):
    """ops_status reads `transport` to pick exit 3 over exit 2."""

    def _result(self, err):
        return di.Result(None, di.UNKNOWN, error=err)

    def test_edge_statuses_are_transport(self):
        for status in EDGE:
            self.assertTrue(self._result(_http(status)).transport,
                            f"HTTP {status} never reached the origin, which is "
                            f"the same fact as a socket error one hop closer")

    def test_origin_tls_failures_are_not_transport(self):
        for status in ORIGIN_TLS:
            self.assertFalse(self._result(_http(status)).transport)

    def test_an_ordinary_origin_status_is_not_transport(self):
        for status in (404, 500, 503):
            self.assertFalse(self._result(_http(status)).transport)

    def test_a_socket_error_is_still_transport_and_no_error_is_not(self):
        self.assertTrue(self._result(OSError("no route to host")).transport)
        self.assertFalse(self._result(None).transport)


class TheDetailSaysWhichHalfFailed(unittest.TestCase):
    def test_edge_detail_names_the_edge_and_disclaims_a_verdict(self):
        for status in EDGE:
            for detail in (di._edge_detail(status), pf._why_unreachable(_http(status))):
                self.assertIn(str(status), detail)
                self.assertIn("Cloudflare", detail)
                self.assertIn("NOT a verdict", detail)

    def test_origin_tls_detail_is_not_excused(self):
        for status in ORIGIN_TLS:
            detail = pf._why_unreachable(_http(status))
            self.assertIn(str(status), detail)
            self.assertNotIn("Cloudflare", detail)

    def test_maintenance_and_unreachable_wording_are_unchanged(self):
        self.assertIn("maintenance window", pf._why_unreachable(_http(503)))
        self.assertIn("could not reach", pf._why_unreachable(OSError("refused")))


class NothingFailsOnAnEdgeBlip(unittest.TestCase):
    """End to end: the real registry, over a live fetch that only 52x's.

    This is the assertion the incident is actually about. Every invariant that
    reads the live site must land UNKNOWN carrying a flag that says so, or
    ops_status routes an edge blip into "the live API answered, but wrongly"
    and pages a human for nothing, while test_dedup_live reddens the push.

    `transport` OR `pending`: those are the two branches the consumers take
    before the final `self.fail`, and different call sites here set different
    ones. What must never happen is neither.
    """

    def _report(self, status):
        def fetch(url, timeout):
            raise _http(status)
        return di.check_all(fetch=fetch)

    def test_an_edge_blip_produces_no_failure_and_no_bare_unknown(self):
        for status in EDGE:
            report = self._report(status)
            self.assertEqual([], report.failed,
                             f"HTTP {status} reached no origin, so nothing was "
                             f"measured and nothing can be wrong")
            reached_the_site = [r for r in report.unknown if r.error is not None]
            self.assertTrue(reached_the_site, "no live check ran at all")
            for r in reached_the_site:
                self.assertTrue(r.transport or r.pending,
                                f"{r.inv.key} on HTTP {status}: UNKNOWN with "
                                f"neither flag reads as a server regression")

    def test_an_origin_tls_failure_is_still_a_bare_unknown(self):
        # Not FAIL: the checks have always called any status UNKNOWN. The point
        # is that it is UNKNOWN with NEITHER flag, which is the bucket that
        # sends ops_status to exit 2 and a human.
        for status in ORIGIN_TLS:
            report = self._report(status)
            live = [r for r in report.unknown if r.error is not None]
            self.assertTrue(live)
            for r in live:
                self.assertFalse(r.transport, f"{r.inv.key} on HTTP {status}")
                self.assertFalse(r.pending, f"{r.inv.key} on HTTP {status}")


if __name__ == "__main__":
    unittest.main()
