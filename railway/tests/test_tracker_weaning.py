"""Guards for the competitor-weaning mechanics in tracker_diff:

  * chase_today       — graduated cadence: daily until independent recall holds
                        >= 90% for 21 straight recorded days, then Mondays only,
                        snapping back to daily on any dip.
  * outlet_suggestions — learn-from-wins: repeat-winner outlets not already in
                        the allowlist are ranked candidates; trusted or one-off
                        outlets never surface.
  * _win_key          — outlet identity: real domain when present, RSS source
                        name for Google News redirect links.

Pure-function tests, no network. Only `requests` is stubbed (never fake
sources.* modules — see tests/test_warn_generic_drift.py for why).
"""
import sys
import types
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()
if "openai" not in sys.modules:
    sys.modules["openai"] = types.ModuleType("openai")

import tracker_diff as td

MON = date(2026, 7, 20)   # a Monday
TUE = date(2026, 7, 21)


def _pts(values):
    return [{"d": f"2026-06-{i+1:02d}", "ind": v, "total": 95.0}
            for i, v in enumerate(values)]


class ChaseCadenceTests(unittest.TestCase):
    def test_short_history_chases_daily(self):
        self.assertTrue(td.chase_today(_pts([95] * 5), TUE))
        self.assertTrue(td.chase_today([], TUE))
        self.assertTrue(td.chase_today(None, TUE))

    def test_weaned_after_21_strong_days_mondays_only(self):
        hist = _pts([92] * 21)
        self.assertTrue(td.chase_today(hist, MON))
        self.assertFalse(td.chase_today(hist, TUE))

    def test_one_dip_snaps_back_to_daily(self):
        hist = _pts([92] * 20 + [88])   # dip on the latest day
        self.assertTrue(td.chase_today(hist, TUE))

    def test_old_weak_days_do_not_block_weaning(self):
        # 10 weak days long ago, then 21 strong: the window is the RECENT 21.
        hist = _pts([70] * 10 + [93] * 21)
        self.assertFalse(td.chase_today(hist, TUE))


class OutletSuggestionTests(unittest.TestCase):
    TRUSTED = ("techcrunch.com", "reuters.com", "cnbc.com")

    def test_repeat_untrusted_outlet_is_suggested(self):
        wins = {"inc42.com": 3, "reuters.com": 5, "one-off.com": 1}
        self.assertEqual(td.outlet_suggestions(wins, self.TRUSTED), [("inc42.com", 3)])

    def test_name_token_matching_filters_trusted(self):
        # A Google News win recorded under the outlet NAME still matches its
        # allowlisted domain ("techcrunch" is inside techcrunch.com).
        wins = {"techcrunch": 4, "globes english": 2}
        self.assertEqual(td.outlet_suggestions(wins, self.TRUSTED), [("globes english", 2)])

    def test_ranked_by_count_and_capped(self):
        wins = {f"outlet{i}.com": i + 2 for i in range(15)}
        out = td.outlet_suggestions(wins, self.TRUSTED)
        self.assertEqual(len(out), 10)
        self.assertEqual(out[0], ("outlet14.com", 16))

    def test_empty_inputs_are_safe(self):
        self.assertEqual(td.outlet_suggestions({}, self.TRUSTED), [])
        self.assertEqual(td.outlet_suggestions(None, None), [])

    def test_country_suffix_carries_through_but_never_breaks_trust_match(self):
        # Wins are tagged 'outlet · Country' so the owner learns WHERE a repeat
        # winner reports from; the allowlist match uses only the outlet part.
        wins = {"techcrunch.com · United States": 4, "inc42.com · India": 3}
        self.assertEqual(td.outlet_suggestions(wins, self.TRUSTED),
                         [("inc42.com · India", 3)])


class VocabHitTests(unittest.TestCase):
    TERMS = ("layoff", "job cuts", "rightsizing")

    def test_matching_headline_is_a_hit(self):
        self.assertTrue(td.vocab_hit("Acme announces job cuts in Ohio", self.TERMS))

    def test_invisible_headline_is_a_miss(self):
        # The learning signal: a resolved win our broad sweep could never see.
        self.assertFalse(td.vocab_hit("Acme to sunset its Berlin operation", self.TERMS))

    def test_empty_inputs_are_safe(self):
        self.assertFalse(td.vocab_hit("", self.TERMS))
        self.assertFalse(td.vocab_hit("anything", ()))


class WinKeyTests(unittest.TestCase):
    def test_real_domain_wins(self):
        raw = {"source_url": "https://www.sifted.eu/articles/x-layoffs", "source_name": "Sifted"}
        self.assertEqual(td._win_key(raw), "sifted.eu")

    def test_google_redirect_falls_back_to_source_name(self):
        raw = {"source_url": "https://news.google.com/rss/articles/abc123",
               "source_name": "The Globe and Mail"}
        self.assertEqual(td._win_key(raw), "the globe and mail")

    def test_empty_raw_is_safe(self):
        self.assertEqual(td._win_key({}), "")


if __name__ == "__main__":
    unittest.main()
