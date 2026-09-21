"""A slow runner must still reach the tail of the Hawaii crawl.

The crawl started at the top every run and the deadline cut it from the
bottom, so a runner that is always slow read the same head forever. The start
now rotates with run_slice. This walks every ring size a listing could have,
at the WORST case (each run covers only what it is guaranteed to start), over
consecutive scheduled runs, and fails on a single notice never reached.
Offline.
"""
import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hi_warn_import  # noqa: E402
import run_slice  # noqa: E402
from sources import warn_hi_ocr as hi  # noqa: E402

DEADLINE = hi_warn_import.DEADLINE_SECONDS


def _runs(count):
    """`count` consecutive scheduled runs, one run_index apart."""
    now = datetime(2026, 9, 21, 16, 30, tzinfo=timezone.utc)
    out, last = [], None
    while len(out) < count:
        idx = run_slice.run_index(now)
        if idx != last:
            out.append(now)
            last = idx
        now += timedelta(hours=1)
    return out


class EveryNoticeIsReached(unittest.TestCase):
    def test_worst_case_runs_tile_the_ring(self):
        step = hi.guaranteed_per_run(DEADLINE)
        self.assertGreaterEqual(step, 1)
        for n in range(1, 121):
            ring = [("2026-01-01", f"c{i}", f"u{i}") for i in range(n)]
            bound = math.ceil(n / min(n, step))
            reached = set()
            for now in _runs(bound):
                order = hi.crawl_order(ring, DEADLINE, now=now)
                self.assertEqual(sorted(order), sorted(ring))   # a rotation, nothing lost
                reached.update(order[:min(n, step)])
            self.assertEqual(len(reached), n, f"ring of {n}: {n - len(reached)} never reached "
                             f"in {bound} worst-case run(s)")

    def test_the_guarantee_is_what_the_deadline_loop_enforces(self):
        w = hi.PER_NOTICE_WORST_CASE_SECONDS
        spent = started = 0
        while spent + w <= DEADLINE:      # the loop's own admission rule
            started += 1
            spent += w
        self.assertEqual(hi.guaranteed_per_run(DEADLINE), started)

    def test_no_deadline_means_the_listing_order(self):
        ring = [(1, 2, "a"), (1, 2, "b")]
        self.assertEqual(hi.crawl_order(ring, None), ring)

    def test_the_module_derives_no_run_counter_of_its_own(self):
        text = Path(hi.__file__).read_text()
        for banned in ("tm_yday", "toordinal", "timetuple"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
