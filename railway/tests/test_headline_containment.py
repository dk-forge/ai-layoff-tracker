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
#
# `recorded_in` is the recorder run that wrote the entry. These three were
# written by one run, which is what makes their differences a complement — see
# `TheStraddleArtifact` for the day they were not.
E0807 = "2026-08-07T18:23:55Z"
BASE_0807 = {
    "worldwide_all_time": {"jobs": 20392202, "entries": 63574,
                           "captured_at": "2026-08-07T18:23:38Z",
                           "recorded_in": E0807},
    "us_all_time": {"jobs": 6968670, "entries": 43341,
                    "captured_at": "2026-08-07T18:23:51Z",
                    "recorded_in": E0807},
    "ai_all_time": {"jobs": 215065, "entries": 99,
                    "captured_at": "2026-08-07T18:23:24Z",
                    "recorded_in": E0807},
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

# A clean day: one recorder run wrote all three, and the live figures are the
# ones read from /aggregate on 2026-08-12. (The committed baselines of that
# morning were a mixed pair — the us_all_time entry was a reviewer's
# replacement baseline installed 10h after the others — and the check then
# tolerated that skew because it was under a one-day window. It no longer does;
# that exact shape is TheStraddleArtifact below. So this fixture is the same
# figures as one observation, which is what a clean day now means.)
E_TODAY = "2026-08-12T04:42:24Z"
BASE_TODAY = {
    "worldwide_all_time": {"jobs": 20379846, "entries": 63615,
                           "captured_at": "2026-08-11T18:26:48Z",
                           "recorded_in": E_TODAY},
    "us_all_time": {"jobs": 6978103, "entries": 43368,
                    "captured_at": "2026-08-12T04:42:24Z",
                    "recorded_in": E_TODAY},
    "ai_all_time": {"jobs": 215065, "entries": 99,
                    "captured_at": "2026-08-11T18:26:39Z",
                    "recorded_in": E_TODAY},
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


# --------------------------------------------------------------------------
# 2026-08-14: the day the check asserted a correction as a finding
# --------------------------------------------------------------------------
# A signed-off editorial correction (commit 3ec3f3a, ~42,000 jobs off already
# published rows) was applied between the 05:06Z recorder run and the 18:26Z
# one. At 18:26Z the ai pair FAILED, which held BOTH ai_all_time and
# worldwide_all_time at their pre-correction figures; the us pair passed under
# its floor (-20,159 against 25,000), so us_all_time alone advanced to a
# post-correction reading. From then on the pair straddled the correction, and
# the subtraction returned the correction itself: -53,476 jobs on +56 entries,
# every run, with no incident to close and no exit but a fourteen-day timeout.
#
# Every figure below is real: the baselines are railway/headline_baseline.json
# at 271faef, the observations are /aggregate read live on 2026-08-15.
STRADDLED = {
    "worldwide_all_time": {"jobs": 20414760, "entries": 63673,      # pre-correction
                           "captured_at": "2026-08-14T05:06:00Z",
                           "recorded_in": "2026-08-14T05:06:00Z"},
    "us_all_time": {"jobs": 6950893, "entries": 43450,              # post-correction
                    "captured_at": "2026-08-14T18:26:18Z",
                    "recorded_in": "2026-08-14T18:26:18Z"},
    "ai_all_time": {"jobs": 211158, "entries": 96,
                    "captured_at": "2026-08-15T06:04:44Z",
                    "recorded_in": "close:ai_all_time:2026-08-15T06:04:44Z"},
}
OBS_0815 = {
    "worldwide_all_time": {"jobs": 20361284, "entries": 63729},
    "us_all_time": {"jobs": 6950893, "entries": 43450},            # not one job moved
    "ai_all_time": {"jobs": 211158, "entries": 96},
}
AT_0815 = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)


class TheStraddleArtifact(unittest.TestCase):
    """Two readings taken either side of a correction are not evidence."""

    def test_the_straddled_pair_is_unknown_and_names_why(self):
        res, _ = _run(OBS_0815, STRADDLED, now=AT_0815)
        self.assertEqual(res.state, di.UNKNOWN, res.detail)
        self.assertIn("DIFFERENT recorder runs", res.detail)
        self.assertNotIn("53,476", res.detail,
                         "the artifact is still being asserted as a number")

    def test_the_same_numbers_taken_together_are_still_a_fail(self):
        """The half that keeps this from being decorative.

        Identical readings, identical baselines — only the recorder stamp is
        made common. -53,476 jobs on +56 arriving entries is then a real
        containment breach and must FAIL. The new UNKNOWN is about the
        provenance of the two readings, and nothing else.
        """
        one_run = {k: dict(v, recorded_in="2026-08-14T05:06:00Z")
                   for k, v in STRADDLED.items()}
        res, _ = _run(OBS_0815, one_run, now=AT_0815)
        self.assertEqual(res.state, di.FAIL, res.detail)
        self.assertIn("53,476", res.detail)

    def test_a_baseline_written_before_the_stamp_existed_is_unknown(self):
        """The migration case: no stamp is missing data, never a pass."""
        legacy = {k: {x: y for x, y in v.items() if x != "recorded_in"}
                  for k, v in STRADDLED.items()}
        res, _ = _run(OBS_0815, legacy, now=AT_0815)
        self.assertEqual(res.state, di.UNKNOWN, res.detail)
        self.assertIn("recorder-run stamp", res.detail)
        self.assertIn("UNJUDGED", res.detail)

    def test_it_self_heals_in_one_recorder_run_with_no_hand_edit(self):
        """UNKNOWN does not hold the baseline, so the next run re-arms it.

        This is the whole exit from the stuck state: nothing is FAILING, so
        nothing is held, so all three slices are recorded together under one
        stamp and the pair is comparable again the very next run — without
        editing either JSON by hand, which is forbidden.
        """
        d = Path(tempfile.mkdtemp())
        bpath, ipath = d / "baseline.json", d / "incidents.json"
        legacy = {k: {x: y for x, y in v.items() if x != "recorded_in"}
                  for k, v in STRADDLED.items()}
        bpath.write_text(json.dumps({"slices": legacy}), encoding="utf-8")
        ipath.write_text(json.dumps({"open": {}, "closed": []}), encoding="utf-8")
        ctx = di.Ctx(_feed(OBS_0815), 5, "cb")
        movement = di.MovementInvariant(headlines=di.HEADLINES, baseline_path=bpath,
                                        incidents_path=ipath)
        containment = di.ContainmentInvariant(baseline_path=bpath, now=AT_0815)
        report = di.Report([movement.run(ctx), containment.run(ctx)])
        di.record_baseline(ctx, report, path=bpath, incidents_path=ipath)

        stamps = {name: entry.get("recorded_in")
                  for name, entry in json.loads(bpath.read_text())["slices"].items()}
        self.assertEqual(len(set(stamps.values())), 1, stamps)
        self.assertTrue(all(stamps.values()), stamps)
        self.assertEqual(json.loads(ipath.read_text())["open"], {},
                         "an UNJUDGED pair must not open an incident")


class HonestDegradation(unittest.TestCase):

    def test_a_missing_baseline_is_unknown_never_a_pass(self):
        base = {k: v for k, v in BASE_0807.items() if k != "worldwide_all_time"}
        res, _ = _run(OBS_0810, base)
        self.assertEqual(res.state, di.UNKNOWN, res.detail)

    def test_a_baseline_too_old_to_bound_a_movement_is_unknown(self):
        base = {k: dict(v) for k, v in BASE_0807.items()}
        base["worldwide_all_time"]["captured_at"] = "2026-07-20T18:23:38Z"
        res, _ = _run(OBS_0810, base)
        self.assertEqual(res.state, di.UNKNOWN, res.detail)
        self.assertIn("too stale", res.detail)

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

    def test_a_pair_advances_together_or_not_at_all(self):
        """The straddle is made unconstructible, not merely detected.

        The 2026-08-14 shape exactly: the AI pair fails, which holds ai and
        worldwide — and us_all_time, whose own pair was passing, used to advance
        alone and land on the far side of whatever happened in between. All
        three now wait, so the next comparison is still between two readings of
        the same instant.
        """
        obs = {k: dict(v) for k, v in OBS_TODAY.items()}
        obs["ai_all_time"]["jobs"] -= 60000        # re-scored across the AI boundary
        obs["ai_all_time"]["entries"] += 5
        base, incidents, notes, _ = self._record(obs, BASE_TODAY)
        self.assertIn("ai_all_time", incidents["open"], notes)
        for name in ("ai_all_time", "worldwide_all_time", "us_all_time"):
            self.assertEqual(base["slices"][name]["jobs"], BASE_TODAY[name]["jobs"],
                             f"{name} advanced while its group was held: {notes}")
        self.assertTrue(any("HELD WITH ITS PAIR" in n for n in notes), notes)

    def test_every_slice_recorded_in_one_run_carries_that_run_s_stamp(self):
        base, _incidents, notes, _ = self._record(OBS_TODAY, BASE_TODAY)
        stamps = {n: base["slices"][n].get("recorded_in")
                  for n in ("ai_all_time", "worldwide_all_time", "us_all_time")}
        self.assertTrue(all(stamps.values()), f"{stamps} {notes}")
        self.assertEqual(len(set(stamps.values())), 1, stamps)

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
