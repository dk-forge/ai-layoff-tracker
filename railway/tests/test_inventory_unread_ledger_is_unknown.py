"""AN UNREAD HEALTH LEDGER IS UNKNOWN, NOT 39 COLLECTORS THAT NEVER REPORTED.

On 2026-09-13 an egress-blocked cloud session ran `ops_status.py` and got an
ACTION NEEDED line: "39 collector(s) declared but never reported". The health
endpoint had not been reached at all ([2] printed HEALTH UNREACHABLE), and
`[2c]` passed `health or {}` into the inventory, so every declared collector
was diffed against an empty ledger and named as missing. A check that could
not run is UNKNOWN; it must never manufacture a finding out of its own
blindness, because a red line known to be wrong is how a real never-reported
collector learns to hide.

Pinned in both directions: `None` (not read) raises and the summary reports
UNKNOWN; `{}` (read, and genuinely empty) still names every declared
collector, because a ledger that answered with nothing is a real finding.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import source_inventory as si  # noqa: E402


class UnreadIsUnknown(unittest.TestCase):
    def test_none_ledger_raises_rather_than_reading_empty(self):
        with self.assertRaises(ValueError):
            si.reporting_collectors(None)
        with self.assertRaises(ValueError):
            si.never_reported(None)

    def test_summary_reports_unknown_not_a_list(self):
        out = si.summary(None)
        self.assertIsNone(out["never_reported"])
        self.assertIsNone(out["awaiting_first_run"])
        self.assertIn("UNKNOWN", out["never_reported_error"])

    def test_an_answered_empty_ledger_is_still_a_finding(self):
        declared = si.declared_collectors()
        self.assertTrue(declared, "the registry must be readable for this test")
        missing = si.never_reported({})
        self.assertTrue(missing)
        self.assertTrue(set(missing) <= set(declared))

    def test_ops_status_hands_the_ledger_through_untouched(self):
        src = open(os.path.join(HERE, "..", "ops_status.py"), encoding="utf-8").read()
        self.assertNotIn("summary(health or {})", src)
        self.assertIn("summary(health)", src)


if __name__ == "__main__":
    unittest.main()
