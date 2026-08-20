"""Guards for PARTIAL per-state collapse in the WARN import.

Every tripwire in this repo asked "did the state return anything?". On
2026-08-13 Ohio answered yes and was still broken: its JFS pages had moved, so
fetch_oh fell through to a single DAM CSV and returned 61 notices where a
healthy run returns 787. Non-zero, and OH's only other guard was a
`== 0` test, so warn_custom_legacy reported OK while 92% of the state was gone.

The floor that catches it has to come from somewhere that cannot quietly follow
the data down, which is why the ledger ratchets UP only: a floor that relaxes
toward the collapse is the same self-widening clock that let the headline guards
erase an open incident by waiting.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Same shared requests stub as test_warn_generic_drift: warn_import imports the
# real scrapers at module load, and installing fake `sources.*` modules would
# shadow them for every test discovered after this one. These tests call only
# pure in-memory helpers, so no network is reachable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import warn_import as W  # noqa: E402

# The legacy custom tier as it really runs, with Ohio's measured healthy volume.
_HEALTHY = {"TX": 2400, "FL": 1800, "GA": 900, "OH": 787, "MI": 760, "NC": 640,
            "NY": 520, "CO": 300, "MN": 210, "MA": 180, "LA": 140, "NV": 90,
            "ID": 60, "KY": 55}
_EXPECTED = sorted(_HEALTHY)
_FLOORS = dict(_HEALTHY)


class PartialCollapseTest(unittest.TestCase):
    def test_ohio_fallback_only_run_is_flagged(self):
        """The actual incident: 787 -> 61, non-zero, every old guard green."""
        counts = dict(_HEALTHY, OH=61)
        self.assertEqual([], W.detect_generic_state_drift(counts, _EXPECTED, {}),
                         "with no floors a partial collapse is undetectable — "
                         "this is why the ledger exists")
        drift = W.detect_generic_state_drift(
            counts, _EXPECTED, _FLOORS, drop_frac=0.5, zero_needs_baseline=True)
        self.assertEqual(["OH"], drift)

    def test_healthy_and_growing_runs_are_quiet(self):
        for counts, label in ((_HEALTHY, "steady"),
                              ({k: v * 2 for k, v in _HEALTHY.items()}, "grown")):
            with self.subTest(label):
                self.assertEqual([], W.detect_generic_state_drift(
                    counts, _EXPECTED, _FLOORS, drop_frac=0.5,
                    zero_needs_baseline=True))

    def test_ordinary_variation_does_not_cry_wolf(self):
        # A state 30% down is noise, not drift; 60% down is drift.
        self.assertEqual([], W.detect_generic_state_drift(
            dict(_HEALTHY, OH=550), _EXPECTED, _FLOORS, drop_frac=0.5,
            zero_needs_baseline=True))
        self.assertEqual(["OH"], W.detect_generic_state_drift(
            dict(_HEALTHY, OH=300), _EXPECTED, _FLOORS, drop_frac=0.5,
            zero_needs_baseline=True))

    def test_state_with_no_floor_yet_stays_quiet_at_zero(self):
        """zero_needs_baseline: a state that never produced has not earned an
        alarm. Naming it every run is how a real breakage gets ignored."""
        counts = dict(_HEALTHY, KY=0)
        floors = {k: v for k, v in _FLOORS.items() if k != "KY"}
        self.assertEqual([], W.detect_generic_state_drift(
            counts, _EXPECTED, floors, drop_frac=0.5, zero_needs_baseline=True))
        # ...but once it HAS a floor, the same zero counts.
        self.assertEqual(["KY"], W.detect_generic_state_drift(
            counts, _EXPECTED, _FLOORS, drop_frac=0.5, zero_needs_baseline=True))

    def test_generic_tier_semantics_are_unchanged(self):
        """The generic tier still flags a bare zero with no floor at all."""
        self.assertEqual(["KY"], W.detect_generic_state_drift(
            dict(_HEALTHY, KY=0), _EXPECTED, {}))

    def test_nationwide_collapse_stays_suppressed(self):
        """A whole-sweep failure is warn_us's job, not 14 per-state alarms."""
        self.assertEqual([], W.detect_generic_state_drift(
            {k: 0 for k in _HEALTHY}, _EXPECTED, _FLOORS, drop_frac=0.5,
            zero_needs_baseline=True))


class BaselineLedgerTest(unittest.TestCase):
    def test_ratchet_raises_but_never_lowers(self):
        ledger = {"legacy_custom": dict(_HEALTHY)}
        # A collapsed run must NOT teach the collapse as the new normal.
        self.assertFalse(W.ratchet_state_baselines(
            ledger, "legacy_custom", dict(_HEALTHY, OH=61), _EXPECTED))
        self.assertEqual(787, ledger["legacy_custom"]["OH"])
        # A genuinely bigger run raises the floor.
        self.assertTrue(W.ratchet_state_baselines(
            ledger, "legacy_custom", dict(_HEALTHY, OH=900), _EXPECTED))
        self.assertEqual(900, ledger["legacy_custom"]["OH"])

    def test_ratchet_seeds_an_empty_tier(self):
        ledger = {}
        self.assertTrue(W.ratchet_state_baselines(
            ledger, "legacy_custom", _HEALTHY, _EXPECTED))
        self.assertEqual(787, ledger["legacy_custom"]["OH"])

    def test_missing_or_malformed_ledger_is_unknown_not_a_pass(self):
        self.assertEqual({}, W.load_state_baselines("/nonexistent/warn.json"))
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{ not json")
            bad = fh.name
        try:
            self.assertEqual({}, W.load_state_baselines(bad))
        finally:
            os.unlink(bad)

    def test_round_trip_normalises_case_and_writes_ints(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            path = fh.name
        try:
            W.save_state_baselines({"legacy_custom": {"oh": 787.0, "TX": 2400.0}},
                                   path)
            with open(path) as fh:
                raw = json.load(fh)
            # Written as plain ints so the git diff stays readable.
            self.assertEqual({"TX": 2400, "oh": 787}, raw["legacy_custom"])
            # Read back upper-cased, so a hand-edited lowercase key still matches
            # the state codes the importer counts by.
            self.assertEqual({"OH": 787.0, "TX": 2400.0},
                             W.load_state_baselines(path)["legacy_custom"])
        finally:
            os.unlink(path)

    def test_one_broken_state_does_not_withhold_its_siblings_floors(self):
        """The bug that kept the ledger empty in the first place.

        Every caller used to gate the whole tier on `if not drift:`, so a single
        permanently-broken state meant NOBODY in that tier ever recorded a
        floor — and a tier with no floors can only detect a hard zero, which is
        precisely the blindness the ledger exists to remove. The drifted state
        must be skipped; its healthy siblings must still be recorded.
        """
        ledger = {}
        counts = dict(_HEALTHY, OH=61)          # OH collapsed, everyone else fine
        self.assertTrue(W.ratchet_state_baselines(
            ledger, "legacy_custom", counts, _EXPECTED, skip=["OH"]))
        tier = ledger["legacy_custom"]
        self.assertNotIn("OH", tier, "a collapsed state must not teach a floor")
        self.assertEqual(2400, tier["TX"])
        self.assertEqual(520, tier["NY"])
        # And the healthy siblings really did all get one.
        self.assertEqual(len(_EXPECTED) - 1, len(tier))

    def test_new_custom_tier_catches_a_90_percent_drop(self):
        """New Mexico, concretely.

        The new-states tier (MS/WV/NM/WA/KS/AL) had NO floors at all — its only
        tripwire was `len(got) == 0`. So NM could fall from a full year of
        notices to a single one and the health page would still read
        "warn_custom_states: ok". With a floor from its own history, that drop
        is drift.
        """
        wanted = ["MS", "WV", "NM", "WA", "KS", "AL"]
        floors = {"MS": 142, "WV": 26, "NM": 11, "WA": 206, "KS": 13, "AL": 274}
        healthy = dict(floors)
        self.assertEqual([], W.detect_generic_state_drift(
            healthy, wanted, floors, drop_frac=0.5, zero_needs_baseline=True,
            peer_min_frac=0.0, peer_min_total=1))
        collapsed = dict(healthy, NM=1)         # 11 -> 1 is a 91% drop
        self.assertEqual(["NM"], W.detect_generic_state_drift(
            collapsed, wanted, floors, drop_frac=0.5, zero_needs_baseline=True,
            peer_min_frac=0.0, peer_min_total=1))

    def test_small_tier_is_not_silenced_by_the_nationwide_peer_gate(self):
        """The peer gate is calibrated for a 40-state sweep.

        Left at its defaults on a six-state tier it needs 3 producing states AND
        50 notices before it will speak, so the tier would be unguarded on most
        runs — a check that is off by default is not a check.
        """
        wanted = ["MS", "WV", "NM", "WA", "KS", "AL"]
        floors = {"MS": 142, "WV": 26, "NM": 11, "WA": 206, "KS": 13, "AL": 274}
        # Only two of the six states file enough to clear a 50-notice total on a
        # quiet run, so the nationwide gate suppresses a real collapse purely on
        # tier size.
        quiet = {"MS": 8, "WV": 2, "NM": 1, "WA": 9, "KS": 1, "AL": 6}
        quiet_floors = {"MS": 8, "WV": 2, "NM": 11, "WA": 9, "KS": 1, "AL": 6}
        self.assertEqual([], W.detect_generic_state_drift(
            quiet, wanted, quiet_floors, drop_frac=0.5, zero_needs_baseline=True,
            peer_min_frac=0.5, peer_min_total=50))
        # With the tier's own gate, the same run names NM.
        self.assertEqual(["NM"], W.detect_generic_state_drift(
            quiet, wanted, quiet_floors, drop_frac=0.5, zero_needs_baseline=True,
            peer_min_frac=0.0, peer_min_total=1))
        collapsed = dict(floors, NM=1)
        # And a busy run with the tier gate still names only the collapsed state.
        self.assertEqual(["NM"], W.detect_generic_state_drift(
            collapsed, wanted, floors, drop_frac=0.5, zero_needs_baseline=True,
            peer_min_frac=0.0, peer_min_total=1))

    def test_shipped_ledger_is_not_empty(self):
        """An empty ledger is the blind state, and it reads exactly like a
        healthy one. `{"generic": {}, "legacy_custom": {}}` parses fine, passes
        every structural check, and silently downgrades all three tiers to
        hard-zero detection — which is how New Mexico's decline stayed invisible
        while the health page said every supported state was fine."""
        loaded = W.load_state_baselines()
        self.assertTrue(loaded, "baseline ledger is empty — per-state floors are "
                                "UNKNOWN, so only a hard zero is detectable")
        for tier in ("legacy_custom", "new_custom"):
            self.assertTrue(
                loaded.get(tier),
                f"tier {tier!r} has no per-state floors; a partial collapse in it "
                f"cannot be detected")

    def test_every_legacy_state_the_importer_scrapes_has_a_floor(self):
        """Idaho, concretely — the state that proved the detector was blind.

        `fetch_id` raised "WARN pdf link not found on landing page" for days
        and nothing anywhere reported it. Idaho is not high-volume, so its 0
        never reached `_real_drift`; and with `zero_needs_baseline=True` a
        state holding no floor has its 0 read as UNPROVEN rather than
        anomalous. Both halves are correct on their own, and together they mean
        a floorless state is exactly the state whose breakage cannot be seen.

        A floor is therefore not optional per state. Any legacy scraper the
        importer runs and the ledger does not carry is silent in the same way,
        so this test names the gap instead of waiting for the next accident.
        """
        try:
            from sources.warn_custom import CUSTOM_STATES
        except Exception as exc:            # pragma: no cover - import guard
            self.skipTest(f"warn_custom unavailable: {exc}")
        floors = W.load_state_baselines().get("legacy_custom", {})
        missing = sorted(set(CUSTOM_STATES) - set(floors))
        self.assertEqual(
            [], missing,
            f"legacy WARN state(s) {missing} are scraped but hold no floor, so a "
            f"break in them reports nothing (Idaho's failure mode)")

    def test_a_broken_idaho_now_surfaces_per_state(self):
        """The whole point of the floor, on the real shape.

        `pull_warn_custom` swallows a fetcher exception and logs it, so a raised
        Idaho arrives at the drift check as a plain 0 among thirteen healthy
        siblings. With its measured floor that 0 is drift, it is named alone,
        and the ratchet still records every sibling — the state that starved
        its tier must not go on starving it while broken.
        """
        floors = dict(_FLOORS, ID=133)
        counts = dict(_HEALTHY, ID=0)
        self.assertEqual(["ID"], W.detect_generic_state_drift(
            counts, _EXPECTED, floors, drop_frac=0.5, zero_needs_baseline=True))
        ledger = {}
        self.assertTrue(W.ratchet_state_baselines(
            ledger, "legacy_custom", counts, _EXPECTED, skip=["ID"]))
        tier = ledger["legacy_custom"]
        self.assertNotIn("ID", tier, "a broken state must not record a 0 floor")
        self.assertEqual(len(_EXPECTED) - 1, len(tier))

    def test_rolling_window_states_are_never_ratcheted(self):
        """AZ, concretely (owner decision 2026-08-14).

        AZ's portal publishes a rolling window: 307, 299, 58, 76 on four
        consecutive days, 16-755 over two weeks. The first 755-day would pin a
        never-lowering floor that flags every ordinary day after it (below 226
        at drop_frac=0.7) as drift, forever — a permanent false alarm
        manufactured by the ratchet itself. So the ratchet must refuse to
        record a rolling-window state even on its biggest run, while still
        recording its archive-publishing siblings.
        """
        ledger = {}
        counts = {"AZ": 755, "CA": 17366, "IL": 3139}
        self.assertTrue(W.ratchet_state_baselines(
            ledger, "generic", counts, ["AZ", "CA", "IL"]))
        tier = ledger["generic"]
        self.assertNotIn("AZ", tier,
                         "a rolling-window count is recent volume, not archive "
                         "size — it must never become a floor")
        self.assertEqual(17366, tier["CA"])
        self.assertEqual(3139, tier["IL"])

    def test_stale_committed_rolling_floor_cannot_resurrect_the_alarm(self):
        """The exemption must hold at LOAD too: a floor for AZ that survives in
        the committed file (hand-edit, old branch, revert) must be dropped, or
        the false alarm the ratchet no longer manufactures comes back through
        the ledger instead."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"generic": {"AZ": 755, "CA": 17366}}, fh)
            path = fh.name
        try:
            loaded = W.load_state_baselines(path)
        finally:
            os.unlink(path)
        self.assertEqual({"CA": 17366.0}, loaded["generic"])

    def test_rolling_window_states_still_flag_a_hard_zero(self):
        """Exempt from the ratchet, not from watching: in the generic tier a
        bare 0 needs no floor, so a broken AZ scraper still surfaces."""
        counts = {"AZ": 0, "CA": 17366, "IL": 3139, "NJ": 2307}
        self.assertEqual(["AZ"], W.detect_generic_state_drift(
            counts, ["AZ", "CA", "IL", "NJ"], {}))

    def test_hand_set_floor_still_applies_to_a_rolling_state(self):
        """WARN_GENERIC_BASELINE is a reviewed human judgment, not the ratchet;
        the detector honours a floor for AZ when a human deliberately sets one."""
        counts = {"AZ": 10, "CA": 17366, "IL": 3139, "NJ": 2307}
        self.assertEqual(["AZ"], W.detect_generic_state_drift(
            counts, ["AZ", "CA", "IL", "NJ"], {"AZ": 100}, drop_frac=0.7))

    def test_shipped_ledger_holds_no_rolling_window_state(self):
        with open(W.BASELINE_LEDGER) as fh:
            raw = json.load(fh)
        for tier, states in raw.items():
            stray = sorted(set(states) & set(W.ROLLING_WINDOW_STATES))
            self.assertEqual([], stray,
                             f"tier {tier!r} carries floor(s) for rolling-window "
                             f"state(s) {stray}; the ledger must not hold them")

    def test_shipped_ledger_is_valid(self):
        """The committed ledger must always parse — a broken one silently
        downgrades every tier to hard-zero detection."""
        loaded = W.load_state_baselines()
        self.assertIsInstance(loaded, dict)
        with open(W.BASELINE_LEDGER) as fh:
            raw = json.load(fh)
        self.assertIn("legacy_custom", raw)
        self.assertIn("generic", raw)


if __name__ == "__main__":
    unittest.main()
