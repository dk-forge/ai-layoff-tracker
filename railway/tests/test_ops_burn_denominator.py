"""The burn alarm compares an account against a repo, or it says nothing true.

THE DEFECT, in the numbers it was measured in. `ops_status.py [2a]` printed two
figures side by side and compared them:

    budget      $3.21 of $14.00 spent (14/31 days) ... on track
    burn        $1.04/day over the last 5d ($5.22 total)
    -> ACTION NEEDED: the measured burn ($1.04/day, ~$31/month) is above the
       $14.00/month allowance

$5.22 over five days does not fit inside $3.21 over fourteen, and the two lines
never had to agree: `budget` reads THIS repo's ledger, `burn` reads the fall in
one OpenRouter ACCOUNT's balance, and both trackers bill that account. On
2026-08-14 the account fell $1.04/day, of which this repo's own meter recorded
$0.38/day. The alarm therefore blamed this repo for a sibling's spend, and no
change made here could have cleared it -- a permanently red line on a
dashboard, which is how a dashboard stops being read.

WHAT IS ASSERTED. Not that the alarm is quieter. That each half is judged
against its own denominator, that an account overspend this repo did not cause
is still reported rather than dropped, and that the report says which is which.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ops_status


class TheRepoIsNotBlamedForTheAccount(unittest.TestCase):
    """The 2026-08-14 numbers, which is the case that was wrong."""

    def verdict(self):
        return ops_status.burn_problems(account_per_day=1.04, repo_per_day=0.38,
                                        allowance_month=14.00, runway_days=9.3)

    def test_no_line_says_this_repo_is_over_its_allowance(self):
        for line in self.verdict():
            self.assertNotIn("THIS repo's own metered burn", line,
                             "this repo spent $0.38/day against a $14/month "
                             "allowance and is still being named as the overspender")

    def test_the_account_overspend_is_still_reported(self):
        joined = " | ".join(self.verdict())
        self.assertIn("SHARED account is burning", joined,
                      "an account burning ~$31/month went unreported; the fix "
                      "was supposed to restate the alarm, not silence it")
        self.assertIn("$0.38", joined,
                      "the report does not say how much of the account burn "
                      "this repo can account for, which is the whole question")

    def test_short_runway_still_reaches_the_owner(self):
        joined = " | ".join(self.verdict())
        self.assertIn("9.3 days", joined)
        self.assertIn("owner's call", joined,
                      "a 9.3-day runway on a shared account was reported as if "
                      "this repo could fix it alone")


class EachHalfKeepsItsOwnDenominator(unittest.TestCase):
    def test_this_repo_over_its_allowance_is_named_as_this_repo(self):
        joined = " | ".join(ops_status.burn_problems(
            account_per_day=2.00, repo_per_day=0.60,
            allowance_month=14.00, runway_days=90))
        self.assertIn("THIS repo's own metered burn", joined,
                      "$0.60/day is $18/month against a $14 allowance and no "
                      "line names this repo")

    def test_a_repo_inside_its_allowance_on_a_healthy_account_is_silent(self):
        self.assertEqual(ops_status.burn_problems(
            account_per_day=0.30, repo_per_day=0.20,
            allowance_month=14.00, runway_days=90), [])

    def test_an_unreadable_ledger_attributes_nothing_rather_than_zero(self):
        # UNKNOWN is not "this repo spent nothing". With no ledger the account
        # half still reports and the repo half must not be asserted either way.
        joined = " | ".join(ops_status.burn_problems(
            account_per_day=2.00, repo_per_day=None,
            allowance_month=14.00, runway_days=90))
        self.assertNotIn("THIS repo", joined)
        self.assertNotIn("SHARED account is burning", joined)

    def test_the_runway_floor_is_the_named_constant(self):
        # A burn small enough that only the runway arm can fire, so this pins
        # the floor rather than accidentally re-testing the allowance arm.
        floor = ops_status.RUNWAY_FLOOR_DAYS
        self.assertEqual(ops_status.burn_problems(0.10, 0.05, 14.0, floor + 0.1), [])
        self.assertTrue(ops_status.burn_problems(0.10, 0.05, 14.0, floor - 0.1))


if __name__ == "__main__":
    unittest.main()
