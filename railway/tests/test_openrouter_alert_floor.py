"""A key cap smaller than the floor must not alarm forever.

WHAT WENT WRONG
---------------
`openrouter_balance_check` takes `binding = min(account_balance,
key_remaining)` and alerts when `binding < THRESHOLD`, with THRESHOLD a flat
$10. This repo's own key carries a $10/MONTH limit, so `key_remaining` can
never EXCEED the floor: the comparison went true at the first cent of spend
and stayed true for the rest of the month.

The alert was not reporting a low balance. It was reporting that the cap
equals the floor, every month, while $58.23 sat untouched in the account
behind it.

An alarm that cannot stop firing is one a reader learns to delete, and this
one guards the moment all AI enrichment stops. The same lesson the sibling
project recorded as "eight identical emails is how an alert channel gets
filtered".

THE FIX, AND WHY IT IS PER-CEILING
----------------------------------
An absolute floor is a scale-free statement about a POOL: "under $10 left in
the account" means something at any account size. It is meaningless about a
CAP, which is a policy number the owner picked -- what matters there is how
much of this month's allowance is gone, not how it compares to a threshold
chosen for a different quantity.

So the account keeps the absolute floor, and a key cap gets a fraction of its
own limit. Runway is untouched and still fires independently: it answers "how
fast", which no level can.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import openrouter_balance_check as obc  # noqa: E402


def _floor_for(balance, key_left, key_limit):
    """Calls the module's REAL floor_for, not a copy of its arithmetic.

    The first version of this test reimplemented the selection here. It passed
    when the fix was mutated away, because it was checking its own mirror. A
    test that cannot fail guards nothing.
    """
    binding = min(c for c in (balance, key_left) if c is not None)
    floor, _note = obc.floor_for(binding, balance, key_limit)
    return binding, floor


class TestFloorIsChosenPerCeiling(unittest.TestCase):
    def test_a_cap_equal_to_the_floor_does_not_alarm_when_nearly_full(self):
        """The exact 2026-09-01 case: $9.59 left of a $10/month cap."""
        binding, floor = _floor_for(58.23, 9.59, 10.0)
        self.assertFalse(
            binding < floor,
            "a key at 96% of its cap alarmed; with a $10 cap and a $10 floor "
            "this fires at the first cent and never stops",
        )

    def test_the_first_cent_of_spend_does_not_alarm(self):
        binding, floor = _floor_for(58.23, 9.99, 10.0)
        self.assertFalse(binding < floor)

    def test_a_genuinely_exhausted_cap_still_alarms(self):
        """Dedupe must not become suppression: the alarm has to still fire."""
        binding, floor = _floor_for(58.23, 1.50, 10.0)
        self.assertTrue(
            binding < floor,
            "a key with $1.50 of a $10 cap left is genuinely nearly out and "
            "must alarm, or the fix has silenced the thing it was guarding",
        )

    def test_the_account_keeps_its_absolute_floor(self):
        """A pool is scale-free; only the CAP case changes."""
        binding, floor = _floor_for(6.00, 25.00, 30.0)
        self.assertEqual(floor, obc.THRESHOLD)
        self.assertTrue(binding < floor)

    def test_an_unlimited_key_falls_back_to_the_absolute_floor(self):
        """`limit: null` means no cap, so only the account can bind."""
        binding, floor = _floor_for(8.00, 8.00, None)
        self.assertEqual(floor, obc.THRESHOLD)

    def test_raising_the_cap_scales_the_floor_with_it(self):
        """The point of a fraction: no retuning when the owner changes a cap."""
        _, floor_10 = _floor_for(58.0, 5.0, 10.0)
        _, floor_30 = _floor_for(58.0, 5.0, 30.0)
        self.assertLess(floor_10, floor_30)


class TestTheConstantsAreSane(unittest.TestCase):
    def test_the_fraction_is_a_fraction(self):
        self.assertGreater(obc.KEY_FLOOR_FRACTION, 0.0)
        self.assertLess(obc.KEY_FLOOR_FRACTION, 1.0)

    def test_runway_is_untouched_and_still_present(self):
        """The half that caught the 2026-08-02 case, where a level said
        healthy at $22.92 while the account fell $7/day."""
        self.assertGreater(obc.RUNWAY_DAYS, 0)


if __name__ == "__main__":
    unittest.main()
