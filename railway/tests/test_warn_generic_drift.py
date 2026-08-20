"""Guards for per-state drift monitoring of the GENERIC (open warn-scraper) tier.

The generic tier scrapes ~40 states through one aggregate health status
(warn_us). Before this, only CA was watched, and only in the run log, so a state
like TN silently returning 0 (its page changed and the open scraper broke for
that ONE state) went dark on every surface. detect_generic_state_drift() closes
that gap: it flags a state whose volume collapsed WHILE its peers stayed healthy,
and stays quiet on a nationwide zero (an outage / genuinely quiet week) so it
never floods false alarms.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# warn_import imports the real state scrapers (sources.warn / sources.warn_custom
# / source_health) at module load. They import cleanly offline once `requests`
# is present, so a bare `requests` stub is all this test needs.
#
# We deliberately do NOT install fake `sources.*` modules here. A fake persists
# in sys.modules and shadows the REAL sources.warn / sources.warn_custom for
# every test module loaded after this one in the suite (alphabetical discovery),
# which is exactly what silently broke test_warn_history_backfills' OH/LA/NC
# parsers. A requests-only stub cannot leak into another module's real import.
# These tests exercise only pure in-memory helpers (detect_generic_state_drift,
# _parse_generic_baselines) and never call a scraper, so no network is possible.
#
# The stub comes from tests/_requests_stub.py and nowhere else: it is a
# process-global slot, so a per-module stub makes its surface depend on
# discovery order. See that module's docstring.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import unittest  # noqa: E402

import warn_import as W  # noqa: E402

# A realistic, healthy generic sweep: every state returns its usual full history.
_HEALTHY = {
    "CA": 4200, "IL": 900, "PA": 800, "NJ": 700, "VA": 650, "WI": 500, "AZ": 480,
    "CO": 460, "IN": 440, "MD": 420, "OR": 400, "SC": 380, "MO": 360, "OK": 340,
    "CT": 320, "TN": 300, "AL": 280, "IA": 260, "UT": 240, "NM": 90,
}
_EXPECTED = sorted(_HEALTHY)


class GenericDriftDetectionTest(unittest.TestCase):
    def test_state_specific_collapse_is_flagged_while_peers_healthy(self):
        # TN's scraper breaks -> 0, everyone else normal. That is the exact gap.
        counts = dict(_HEALTHY, TN=0)
        drift = W.detect_generic_state_drift(counts, _EXPECTED)
        self.assertEqual(drift, ["TN"])

    def test_multiple_dark_states_all_surface(self):
        counts = dict(_HEALTHY, TN=0, OK=0)
        self.assertEqual(W.detect_generic_state_drift(counts, _EXPECTED), ["OK", "TN"])

    def test_uniform_quiet_week_is_not_flagged(self):
        # A nationwide zero (outage / quiet week): nobody produced. warn_us's job,
        # not 20 per-state alarms. The peer gate must suppress ALL of them.
        counts = {st: 0 for st in _EXPECTED}
        self.assertEqual(W.detect_generic_state_drift(counts, _EXPECTED), [])

    def test_broad_outage_below_peer_floor_is_not_flagged(self):
        # Most of the sweep failed (only a couple states produced). We cannot tell
        # a real per-state break from the outage, so suppress rather than cry wolf.
        counts = {st: 0 for st in _EXPECTED}
        counts["CA"] = 4200
        counts["IL"] = 900
        self.assertEqual(W.detect_generic_state_drift(counts, _EXPECTED), [])

    def test_healthy_sweep_flags_nothing(self):
        self.assertEqual(W.detect_generic_state_drift(dict(_HEALTHY), _EXPECTED), [])

    def test_low_volume_state_filing_nothing_is_still_flagged_when_expected(self):
        # A 0 is a 0: if a state is in the expected generic tier and the sweep is
        # healthy, its 0 is drift regardless of its usual volume (the full-history
        # scrape means a real generic state is essentially never legitimately 0).
        counts = dict(_HEALTHY, NM=0)
        self.assertEqual(W.detect_generic_state_drift(counts, _EXPECTED), ["NM"])

    def test_numeric_floor_catches_a_partial_collapse(self):
        # CA didn't hit 0 but lost most of its history (parser change) -> below
        # floor*(1-drop_frac). With a baseline it is caught; without one it isn't.
        counts = dict(_HEALTHY, CA=200)
        self.assertEqual(W.detect_generic_state_drift(counts, _EXPECTED), [])
        baselines = {"CA": 4000}
        self.assertEqual(W.detect_generic_state_drift(counts, _EXPECTED, baselines), ["CA"])

    def test_empty_expected_is_safe(self):
        self.assertEqual(W.detect_generic_state_drift(_HEALTHY, []), [])

    def test_baseline_env_parser_is_forgiving(self):
        self.assertEqual(W._parse_generic_baselines(""), {})
        self.assertEqual(W._parse_generic_baselines("not json"), {})
        self.assertEqual(W._parse_generic_baselines('{"ca": 100, "tx": 0}'), {"CA": 100.0})


if __name__ == "__main__":
    unittest.main()
