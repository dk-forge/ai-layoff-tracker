"""Offline tests for data_integrity.ContainmentInvariant.

WHY THIS GUARD EXISTS, in the numbers it is written from.

On 2026-08-08 the published "United States jobs, all time" headline rose 92,686
(and by the 2026-08-10 reading, 93,210) while "Worldwide jobs, all time" — of
which the US slice is a strict subset — rose 14,911. `headline_movement` judges
each slice on its own, against an allowance of `|Δentries| * base_mean *
mean_factor`. That allowance is bought by rows that ARRIVED, and a re-scoring
moves a headline while nothing arrives, so the budget is unrelated to the thing
that moved the number: 18 arriving US entries bought 34,730 jobs of headroom for
a 92,686-job move that no arriving row had anything to do with. At 49 net new
entries the identical re-scoring passes silently.

The containment rule does not depend on entry counts at all, and this file
pins that. A row can only ever add jobs and a row together, or remove jobs and
a row together, so in ANY population jobs and entries move in the same
direction. When the complement of a subset (worldwide minus the US) LOSES jobs
while GAINING rows, no arrival and no departure explains it: jobs were re-scored
across the boundary between the two published slices.

Every figure below is real and is quoted from railway/headline_baseline.json's
own git history plus the closed incident in railway/headline_incidents.json.
"""
import json
import sys
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity as di


# --------------------------------------------------------------------------
# The real readings. These are the evidence, so they are named, not inlined.
# --------------------------------------------------------------------------
# Committed baseline of 2026-08-07 (commit 4028cec), the last one recorded
# before the re-scoring, and the one the us_all_time incident stayed pinned to.
BASE_0807 = {
    "worldwide_all_time": {"jobs": 20392202, "entries": 63574,
                           "captured_at": "2026-08-07T18:23:38Z"},
    "us_all_time": {"jobs": 6968670, "entries": 43341,
                    "captured_at": "2026-08-07T18:23:51Z"},
    "ai_all_time": {"jobs": 215065, "entries": 99,
                    "captured_at": "2026-08-07T18:23:24Z"},
}
# What the live site read on 2026-08-10. Worldwide/AI are the figures the
# recorder committed that day (commit 0894291, 18:24Z); the US pair is
# `observed_at_open` from the closed incident (19:36Z), which is the reading
# ops_status.py [3] rendered and the one the incident was opened on.
OBS_0810 = {
    "worldwide_all_time": {"jobs": 20407113, "entries": 63602},
    "us_all_time": {"jobs": 7061880, "entries": 43359},
    "ai_all_time": {"jobs": 215065, "entries": 99},
}

# Today. Baselines are the committed ones after the incident was closed (the
# us_all_time entry is the reviewer's replacement baseline, which is why its
# capture time is ~10h adrift of the other two); observations are the live
# figures read from /aggregate on 2026-08-12.
BASE_TODAY = {
    "worldwide_all_time": {"jobs": 20379846, "entries": 63615,
                           "captured_at": "2026-08-11T18:26:48Z"},
    "us_all_time": {"jobs": 6978103, "entries": 43368,
                    "captured_at": "2026-08-12T04:42:24Z"},
    "ai_all_time": {"jobs": 215065, "entries": 99,
                    "captured_at": "2026-08-11T18:26:39Z"},
}
OBS_TODAY = {
    "worldwide_all_time": {"jobs": 20383796, "entries": 63620},
    "us_all_time": {"jobs": 6978103, "entries": 43368},
    "ai_all_time": {"jobs": 215065, "entries": 99},
}


def _slice_of(url):
    """Which headline a stubbed /aggregate URL is asking for."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if q.get("ai") == ["1"]:
        return "ai_all_time"
    if q.get("country") == ["United States"]:
        return "us_all_time"
    return "worldwide_all_time"


def _feed(observations):
    def fetch(url, timeout):
        o = observations[_slice_of(url)]
        return json.dumps({"totals": {"jobs": o["jobs"], "entries": o["entries"]}}).encode()
    return fetch


# The clock is injected everywhere a real historical reading is judged. These
# figures are evidence from named days, and a test that quietly turns UNKNOWN
# once the wall clock passes MAX_BASELINE_AGE_DAYS has stopped testing anything.
AT_0810 = datetime(2026, 8, 10, 19, 36, 59, tzinfo=timezone.utc)
AT_TODAY = datetime(2026, 8, 12, 5, 0, 0, tzinfo=timezone.utc)


def _run(observations, baseline_slices, now=AT_0810, pairs=None):
    """(Result, ctx) for one reading against one committed baseline."""
    tmp = Path(tempfile.mkdtemp()) / "headline_baseline.json"
    tmp.write_text(json.dumps({"slices": baseline_slices}), encoding="utf-8")
    ctx = di.Ctx(_feed(observations), 5, "cb")
    inv = di.ContainmentInvariant(baseline_path=tmp, now=now,
                                  pairs=pairs or di.CONTAINMENTS)
    return inv.run(ctx), ctx


class TheIncidentItWasWrittenFor(unittest.TestCase):

    def test_the_2026_08_10_readings_fail(self):
        """THE LOAD-BEARING TEST. This is the day, and these are the numbers."""
        res, _ = _run(OBS_0810, BASE_0807)
        self.assertEqual(res.state, di.FAIL, res.detail)
        # The complement of the US slice (worldwide minus the US) lost 78,299
        # jobs while gaining 10 rows: (20,407,113-7,061,880) - (20,392,202-6,968,670).
        self.assertIn("78,299", res.detail)
        self.assertIn("United States jobs, all time", res.detail)
        # The AI pair is clean on the same day and must not be named as failing.
        self.assertNotIn("AI-attributed", res.detail)

    def test_it_fires_however_many_entries_arrived(self):
        """The whole point. `headline_movement` goes quiet at 49 new entries."""
        for extra in (0, 18, 49, 200, 5000):
            obs = {k: dict(v) for k, v in OBS_0810.items()}
            obs["us_all_time"]["entries"] += extra
            obs["worldwide_all_time"]["entries"] += extra
            res, _ = _run(obs, BASE_0807)
            self.assertEqual(res.state, di.FAIL,
                             f"{extra} extra arriving entries bought silence: {res.detail}")

    def test_forty_nine_arriving_entries_would_have_bought_the_movement_allowance(self):
        """Not a test of the new guard — the arithmetic that made it necessary.

        `headline_movement` lets |Δentries| * base_mean * mean_factor explain a
        move. Against the 2026-08-07 US baseline that is 160.787 * 12 = 1,929
        jobs per net new entry: the 18 that actually arrived bought 34,730 and
        the check failed, but 49 would have bought 94,543 and the identical
        re-scoring of 93,210 would have passed in silence.
        """
        base = BASE_0807["us_all_time"]
        base_mean = base["jobs"] / base["entries"]
        moved = OBS_0810["us_all_time"]["jobs"] - base["jobs"]
        us = next(h for h in di.HEADLINES if h.name == "us_all_time")
        self.assertEqual(moved, 93210)
        self.assertLess(18 * base_mean * us.mean_factor, moved)     # what landed
        self.assertGreater(49 * base_mean * us.mean_factor, moved)  # what would have hidden it


class TodayIsClean(unittest.TestCase):

    def test_todays_readings_pass(self):
        res, _ = _run(OBS_TODAY, BASE_TODAY, now=AT_TODAY)
        self.assertEqual(res.state, di.PASS, res.detail)

    def test_a_baseline_skew_inside_the_tolerance_still_renders_a_verdict(self):
        """Today's two baselines are ~10h apart, because closing the incident
        installed a replacement baseline for one slice only. That is inside one
        recorder cycle, so the pair is still comparable and must be judged."""
        skew = di._days_since(BASE_TODAY["worldwide_all_time"]["captured_at"], AT_TODAY) \
            - di._days_since(BASE_TODAY["us_all_time"]["captured_at"], AT_TODAY)
        self.assertLess(abs(skew), di.MAX_PAIR_SKEW_DAYS)
        self.assertGreater(abs(skew), 0.4, "the skew this tolerance is sized for is real")


class HonestDegradation(unittest.TestCase):

    def test_a_missing_baseline_is_unknown_never_a_pass(self):
        base = {k: v for k, v in BASE_0807.items() if k != "worldwide_all_time"}
        res, _ = _run(OBS_0810, base)
        self.assertEqual(res.state, di.UNKNOWN, res.detail)

    def test_baselines_captured_a_week_apart_are_unknown(self):
        base = {k: dict(v) for k, v in BASE_0807.items()}
        base["worldwide_all_time"]["captured_at"] = "2026-07-31T18:23:38Z"
        res, _ = _run(OBS_0810, base)
        self.assertEqual(res.state, di.UNKNOWN, res.detail)
        self.assertIn("apart", res.detail)

    def test_an_unreachable_api_is_unknown(self):
        def dead(url, timeout):
            raise OSError("tunnel connection failed")
        inv = di.ContainmentInvariant()
        res = inv.run(di.Ctx(dead, 5, "cb"))
        self.assertEqual(res.state, di.UNKNOWN, res.detail)

    def test_a_subset_bigger_than_its_superset_is_a_fail(self):
        obs = {k: dict(v) for k, v in OBS_TODAY.items()}
        obs["us_all_time"]["jobs"] = obs["worldwide_all_time"]["jobs"] + 1
        res, _ = _run(obs, BASE_TODAY)
        self.assertEqual(res.state, di.FAIL, res.detail)
        self.assertIn("larger than", res.detail)


class TheRelationshipsAreStructural(unittest.TestCase):
    """The pairs are asserted from the headlines' own params, not assumed.

    A subset on one date basis and a superset on another is not a containment
    relation, and neither is a pair whose filters do not nest.
    """

    def test_every_declared_pair_really_nests(self):
        by_name = {h.name: h for h in di.HEADLINES}
        self.assertTrue(di.CONTAINMENTS)
        for sub_name, sup_name in di.CONTAINMENTS:
            sub, sup = by_name[sub_name], by_name[sup_name]
            self.assertIsNone(di.containment_problem(sub, sup),
                              f"{sub_name} is not contained by {sup_name}")

    def test_a_date_windowed_slice_is_refused(self):
        windowed = next(h for h in di.HEADLINES if h.date_windowed)
        world = next(h for h in di.HEADLINES if h.name == "worldwide_all_time")
        self.assertIsNotNone(di.containment_problem(windowed, world))
        self.assertIsNotNone(di.containment_problem(world, windowed))

    def test_two_unrelated_filters_are_refused(self):
        a = di.Headline(name="a", label="A", params={"country": "France"}, max_share=1)
        b = di.Headline(name="b", label="B", params={"ai": "1"}, max_share=1)
        self.assertIsNotNone(di.containment_problem(a, b))

    def test_the_pair_that_would_have_caught_it_is_declared(self):
        self.assertIn(("us_all_time", "worldwide_all_time"), di.CONTAINMENTS)
        self.assertIn(("ai_all_time", "worldwide_all_time"), di.CONTAINMENTS)


class ItCannotLaunderItself(unittest.TestCase):
    """A containment FAIL must not become tomorrow's normal.

    The movement guard's rule — a failing slice keeps yesterday's baseline and
    opens a sticky incident — has to cover this finding too. Without it the
    recorder would advance both readings the same evening, the difference
    between them would be gone, and the guard would have laundered the defect
    it just caught.
    """

    def _record(self, observations, baseline_slices):
        d = Path(tempfile.mkdtemp())
        bpath, ipath = d / "baseline.json", d / "incidents.json"
        bpath.write_text(json.dumps({"slices": baseline_slices}), encoding="utf-8")
        ipath.write_text(json.dumps({"open": {}, "closed": []}), encoding="utf-8")
        ctx = di.Ctx(_feed(observations), 5, "cb")
        movement = di.MovementInvariant(headlines=di.HEADLINES, baseline_path=bpath,
                                        incidents_path=ipath)
        containment = di.ContainmentInvariant(baseline_path=bpath)
        report = di.Report([movement.run(ctx), containment.run(ctx)])
        written, notes = di.record_baseline(ctx, report, path=bpath,
                                            incidents_path=ipath)
        return (json.loads(bpath.read_text()), json.loads(ipath.read_text()),
                notes, written)

    def test_neither_side_of_a_failing_pair_is_recorded(self):
        base, incidents, notes, _ = self._record(OBS_0810, BASE_0807)
        for name in ("us_all_time", "worldwide_all_time"):
            self.assertEqual(base["slices"][name]["jobs"],
                             BASE_0807[name]["jobs"],
                             f"{name} advanced over a containment FAIL: {notes}")
        self.assertIn("us_all_time", incidents["open"])

    def test_a_clean_day_still_advances(self):
        base, incidents, notes, written = self._record(OBS_TODAY, BASE_TODAY)
        self.assertTrue(written)
        self.assertEqual(incidents["open"], {})
        self.assertEqual(base["slices"]["worldwide_all_time"]["jobs"],
                         OBS_TODAY["worldwide_all_time"]["jobs"], notes)


class ItIsInTheOneRegistry(unittest.TestCase):

    def test_the_invariant_is_registered(self):
        keys = [i.key for i in di.INVARIANTS]
        self.assertIn("headline_containment", keys)
        self.assertEqual(len(keys), len(set(keys)), "two invariants share a key")


if __name__ == "__main__":
    unittest.main()
