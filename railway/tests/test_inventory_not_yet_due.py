"""A collector whose first run is still ahead is UNKNOWN, not NEVER REPORTED.

The monthly digest slot was armed on 2026-09-06 and first fires on 2026-10-01.
Between those dates it is declared, silent, and correctly so, but the source
inventory called it "declared but never reported" and put it in ACTION NEEDED,
where it would have sat for 25 days. A red line that is known to be wrong is
how a real never-reported collector learns to hide: the 2026-05 case sat in a
list for thirteen months.

The exemption is dated and narrow. On and after the due date the collector is
judged like every other one, and absence is still never a pass.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import source_inventory as si  # noqa: E402


class TheExemptionIsDatedAndNarrow(unittest.TestCase):
    def test_a_slot_before_its_first_run_is_not_yet_due(self):
        self.assertTrue(si.not_yet_due("digest_monthly", today="2026-09-30"))

    def test_on_the_due_date_it_is_judged_like_any_other(self):
        self.assertFalse(si.not_yet_due("digest_monthly", today="2026-10-01"))
        self.assertFalse(si.not_yet_due("digest_monthly", today="2026-11-14"))

    def test_a_collector_with_no_entry_is_never_exempt(self):
        for name in ("gdelt", "warn_import", "sec_edgar", ""):
            self.assertFalse(si.not_yet_due(name, today="2026-09-06"), name)

    def test_every_entry_carries_a_real_iso_date(self):
        import datetime
        self.assertTrue(si.NOT_YET_DUE, "an empty exemption map would pass vacuously")
        for name, due in si.NOT_YET_DUE.items():
            datetime.date.fromisoformat(due)  # raises if it is not a date
            self.assertRegex(name, r"^[a-z0-9_]+$")


class TheTwoListsDoNotOverlap(unittest.TestCase):
    def _health(self):
        return {"gdelt": {"status": "ok"}}

    def test_a_not_yet_due_collector_leaves_never_reported(self):
        never = si.never_reported(self._health(), path=si.HEALTH_JS)
        self.assertNotIn("digest_monthly", never)

    def test_and_appears_in_awaiting_first_run_instead(self):
        waiting = si.awaiting_first_run(self._health(), path=si.HEALTH_JS,
                                        today="2026-09-06")
        self.assertIn("digest_monthly", waiting)

    def test_after_the_due_date_it_moves_back_to_never_reported(self):
        waiting = si.awaiting_first_run(self._health(), path=si.HEALTH_JS,
                                        today="2026-10-02")
        self.assertNotIn("digest_monthly", waiting)


if __name__ == "__main__":
    unittest.main()
