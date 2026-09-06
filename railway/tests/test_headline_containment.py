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


def _feed(observations, excluded=None):
    """Stub /aggregate.

    `excluded` is the superset-member block the live endpoint publishes
    (2.20.156).  Default: every slice reports ZERO exclusions, unchanged from
    its baseline — so dedup explains nothing and every historical reading below
    is judged on its full movement, exactly as it was before the block existed.
    That default is what makes these tests evidence that accounting for dedup
    did not weaken the guard: a real re-scoring still FAILS.

    Pass a dict to model a reconcile-supersets run.  Pass `False` to model a
    build that predates the block, which must read UNKNOWN and never PASS.
    """
    def fetch(url, timeout):
        name = _slice_of(url)
        o = observations[name]
        body = {"totals": {"jobs": o["jobs"], "entries": o["entries"]}}
        if excluded is not False:
            e = (excluded or {}).get(name, {"jobs": 0, "entries": 0})
            body["excluded"] = {"jobs": e["jobs"], "entries": e["entries"]}
        return json.dumps(body).encode()
    return fetch


# The clock is injected everywhere a real historical reading is judged. These
# figures are evidence from named days, and a test that quietly turns UNKNOWN
# once the wall clock passes MAX_BASELINE_AGE_DAYS has stopped testing anything.
AT_0810 = datetime(2026, 8, 10, 19, 36, 59, tzinfo=timezone.utc)
AT_TODAY = datetime(2026, 8, 12, 5, 0, 0, tzinfo=timezone.utc)


def _run(observations, baseline_slices, now=AT_0810, pairs=None, excluded=None):
    """(Result, ctx) for one reading against one committed baseline.

    Baselines gain `excluded_jobs`/`excluded_entries` of 0 unless the caller
    set them, mirroring what the recorder stores from 2.20.156 on.
    """
    tmp = Path(tempfile.mkdtemp()) / "headline_baseline.json"
    if excluded is not False:
        baseline_slices = {
            k: ({"excluded_jobs": 0, "excluded_entries": 0} | v)
            if isinstance(v, dict) else v
            for k, v in baseline_slices.items()
        }
    tmp.write_text(json.dumps({"slices": baseline_slices}), encoding="utf-8")
    ctx = di.Ctx(_feed(observations, excluded), 5, "cb")
    inv = di.ContainmentInvariant(baseline_path=tmp, now=now,
                                  pairs=pairs or di.CONTAINMENTS)
    return inv.run(ctx), ctx


class DedupIsNotARescoring(unittest.TestCase):
    """2026-08-31 — the 2026-08-29 false FAIL, and why it was false.

    This check subtracts two published headlines and called any divergence a
    re-scoring of already-published rows. There is a second, entirely correct
    way for a complement to move without rows: /reconcile-supersets folds a row
    into a more complete row for the same event, and its jobs leave the
    headline because they were being counted twice.

    On 2026-08-29 it read -39,292 jobs as wrong data on a live public surface.
    It was 416 rows carrying 120,883 jobs becoming members, plus two rows
    totalling 9,030 jobs gaining ai_explicit (#243). Nothing was wrong. The
    guard was not too tight or too loose; it could not see the exclusion,
    because nothing published it.

    The fix subtracts a MEASURED exclusion and judges the remainder. It is not
    a tolerance and widens with nothing. The tests above prove it did not cost
    the guard its teeth: every historical incident there still FAILS, because
    those days moved no exclusions and the residual is the whole movement.
    """

    def test_a_dedup_run_that_explains_the_move_passes(self):
        # Worldwide loses 120,000 jobs; every one of them left because a row
        # became a superset member. Rows go UP, which is the shape that used
        # to read as proof of re-scoring.
        obs = {k: dict(v) for k, v in OBS_TODAY.items()}
        obs["worldwide_all_time"]["jobs"] -= 120000
        obs["worldwide_all_time"]["entries"] += 11
        res, _ = _run(obs, BASE_TODAY, now=AT_TODAY,
                      excluded={"worldwide_all_time": {"jobs": 120000, "entries": 416}})
        self.assertEqual(res.state, di.PASS, res.detail)
        self.assertIn("dedup explains it", res.detail)

    def test_a_dedup_run_does_not_excuse_movement_beyond_it(self):
        # Same run, but 100,000 jobs more left than dedup can account for.
        # The residual is what is judged, and it is over the floor.
        obs = {k: dict(v) for k, v in OBS_TODAY.items()}
        obs["worldwide_all_time"]["jobs"] -= 220000
        obs["worldwide_all_time"]["entries"] += 11
        res, _ = _run(obs, BASE_TODAY, now=AT_TODAY,
                      excluded={"worldwide_all_time": {"jobs": 120000, "entries": 416}})
        self.assertEqual(res.state, di.FAIL, res.detail)
        self.assertIn("unexplained", res.detail)

    def test_an_unreported_exclusion_is_UNKNOWN_and_never_a_pass(self):
        # A build predating the `excluded` block cannot distinguish dedup from
        # re-scoring. Assuming zero is precisely what produced the false FAIL,
        # and assuming "probably dedup" would be the same error with the sign
        # flipped. Neither. UNKNOWN.
        obs = {k: dict(v) for k, v in OBS_TODAY.items()}
        obs["worldwide_all_time"]["jobs"] -= 120000
        obs["worldwide_all_time"]["entries"] += 11
        res, _ = _run(obs, BASE_TODAY, now=AT_TODAY, excluded=False)
        self.assertEqual(res.state, di.UNKNOWN, res.detail)
        self.assertNotEqual(res.state, di.PASS)

    def test_exclusions_leaving_the_subset_do_not_count_as_the_superset_s(self):
        # Only the SUPERSET's exclusions can explain the complement falling.
        # An exclusion inside the subset moves both sides and explains nothing,
        # so a subset-only dedup must not buy silence for a real move.
        #
        # SCOPED TO ONE PAIR DELIBERATELY. Written unscoped first, and a
        # mutation (`exc_sup - exc_sub` -> `exc_sup + exc_sub`) left it GREEN:
        # `res` rolls up every pair, the AI pair failed for its own unrelated
        # reason, and the assertion was satisfied by a failure it was not
        # testing. A roll-up assertion cannot prove anything about one pair's
        # arithmetic.
        obs = {k: dict(v) for k, v in OBS_TODAY.items()}
        obs["worldwide_all_time"]["jobs"] -= 120000
        obs["worldwide_all_time"]["entries"] += 11
        res, _ = _run(obs, BASE_TODAY, now=AT_TODAY,
                      pairs=(("us_all_time", "worldwide_all_time"),),
                      excluded={"us_all_time": {"jobs": 120000, "entries": 416}})
        self.assertEqual(res.state, di.FAIL, res.detail)
        self.assertIn("unexplained", res.detail)


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

    def _record(self, observations, baseline_slices, now=AT_0810):
        d = Path(tempfile.mkdtemp())
        bpath, ipath = d / "baseline.json", d / "incidents.json"
        # Baselines carry the exclusion figures the recorder stores from
        # 2.20.156 on, at zero: these fixtures model a re-scoring, and a
        # reconcile-supersets run must not be implied where none happened.
        baseline_slices = {
            k: ({"excluded_jobs": 0, "excluded_entries": 0} | v)
            if isinstance(v, dict) else v
            for k, v in baseline_slices.items()
        }
        bpath.write_text(json.dumps({"slices": baseline_slices}), encoding="utf-8")
        ipath.write_text(json.dumps({"open": {}, "closed": []}), encoding="utf-8")
        ctx = di.Ctx(_feed(observations), 5, "cb")
        # The clock is injected here for the same reason _run injects it (see
        # AT_0810 above). It was not, and on 2026-08-21T18:23:51Z the 2026-08-07
        # baseline in these fixtures aged past MAX_BASELINE_AGE_DAYS: the
        # movement check flipped to UNKNOWN, the recorder stopped holding the
        # failing pair, and this file went red on every branch at that instant
        # while asserting nothing it was written to assert.
        movement = di.MovementInvariant(headlines=di.HEADLINES, baseline_path=bpath,
                                        incidents_path=ipath, now=now)
        containment = di.ContainmentInvariant(baseline_path=bpath, now=now)
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


class TheRecorderStoresWhatTheCheckSubtracts(unittest.TestCase):
    """2026-09-06 — the dedup subtraction had no recorded side to subtract from.

    2.20.156 taught `headline_containment` to read /aggregate's `excluded`
    block and subtract the exclusion delta before judging. It did not teach
    `record_baseline` to STORE that figure, and a delta needs two readings. So
    `have_exc` was False on every production run, that branch returned UNKNOWN,
    and the FAIL below it became unreachable: the guard could not report a
    finding at all. Six days of it, with the committed baseline of 2026-09-05
    still carrying only jobs / entries / captured_at / recorded_in.

    Every test in the classes above builds its own baseline dict and puts the
    exclusion keys in by hand, which is exactly why none of them saw it. These
    drive the REAL recorder and read back what it actually wrote.
    """

    def _record(self, observations, baseline_slices, excluded=None, now=AT_TODAY):
        """Run the real Movement + Containment + record_baseline, return the file."""
        d = Path(tempfile.mkdtemp())
        bpath, ipath = d / "baseline.json", d / "incidents.json"
        bpath.write_text(json.dumps({"slices": baseline_slices}), encoding="utf-8")
        ipath.write_text(json.dumps({"open": {}, "closed": []}), encoding="utf-8")
        ctx = di.Ctx(_feed(observations, excluded), 5, "cb")
        movement = di.MovementInvariant(headlines=di.HEADLINES, baseline_path=bpath,
                                        incidents_path=ipath, now=now)
        containment = di.ContainmentInvariant(baseline_path=bpath, now=now)
        report = di.Report([movement.run(ctx), containment.run(ctx)])
        di.record_baseline(ctx, report, path=bpath, incidents_path=ipath)
        return bpath, json.loads(bpath.read_text())["slices"]

    def test_the_recorder_commits_the_exclusion_pool_it_read(self):
        """Without this the check has nothing to subtract from, ever."""
        _, slices = self._record(
            OBS_TODAY, {},
            excluded={"worldwide_all_time": {"jobs": 120763, "entries": 414},
                      "us_all_time": {"jobs": 103990, "entries": 415}})
        self.assertEqual(slices["worldwide_all_time"]["excluded_jobs"], 120763)
        self.assertEqual(slices["worldwide_all_time"]["excluded_entries"], 414)
        self.assertEqual(slices["us_all_time"]["excluded_jobs"], 103990)
        self.assertEqual(slices["ai_all_time"]["excluded_jobs"], 0)

    def test_a_build_reporting_no_exclusion_records_none_rather_than_zero(self):
        """ABSENT and 0 are different facts, and only one is a measurement.

        The lazy version of the fix above writes 0 whenever the block is
        missing. That arms the subtraction with a number nobody took, and the
        check then subtracts it confidently — the same assume-zero error it was
        written to remove, one layer further down.
        """
        _, slices = self._record(OBS_TODAY, {}, excluded=False)
        for name in ("worldwide_all_time", "us_all_time", "ai_all_time"):
            self.assertNotIn("excluded_jobs", slices[name])
            self.assertNotIn("excluded_entries", slices[name])

    def test_a_recorded_baseline_arms_the_subtraction_end_to_end(self):
        """THE LOAD-BEARING TEST: judge against the RECORDER'S OWN output.

        Every other dedup test hands the check a baseline the test itself
        wrote. This one records one the way production does and then asks the
        check to use it, which is the step that was missing and the only step
        that proves the two halves of the mechanism meet.
        """
        bpath, _ = self._record(
            OBS_TODAY, {},
            excluded={"worldwide_all_time": {"jobs": 120763, "entries": 414}})

        after = {k: dict(v) for k, v in OBS_TODAY.items()}
        after["worldwide_all_time"]["jobs"] -= 120000   # a big reconcile pass
        after["worldwide_all_time"]["entries"] += 11    # and ordinary arrivals
        pool_after = {"worldwide_all_time": {"jobs": 240763, "entries": 830}}

        ctx = di.Ctx(_feed(after, pool_after), 5, "cb")
        res = di.ContainmentInvariant(baseline_path=bpath, now=AT_TODAY).run(ctx)
        self.assertEqual(res.state, di.PASS, res.detail)
        self.assertIn("dedup explains it", res.detail)


class WhatTheMinusThirtyNineTwoNineTwoActuallyWas(unittest.TestCase):
    """2026-09-06 — #243, re-derived from the run logs instead of from a summary.

    ab4714f closed #243 saying the 2026-08-29 movement "was 416 rows carrying
    120,883 jobs becoming members". That is the STANDING POOL, not the window's
    delta. `jobs_excluded` in a reconcile-supersets run is cumulative, and its
    sibling field `changes` is how many rows that run actually re-marked:

        2026-08-29T00:41Z  run 33224262318  jobs_excluded=120,763  changes=0
        2026-08-29T19:30Z  run 33271008361  jobs_excluded=120,643  changes=1
        2026-08-30T19:25Z  run 33330828111  jobs_excluded=120,883  changes=3

    Four rows across the whole window, and the pool moved +120 jobs. Dedup
    explains 120 of the 39,292, so the finding stands and that branch never
    could have cleared it. What did move it is in the closed incident: twelve
    rows LEFT (seven trashed by the owner's signed 2026-08-29 correction,
    headlined by one of 50,000, and five merged by dedupe-llm) against roughly
    twenty-three arrivals, which nets to the +10 entries the check saw.
    """

    E0829 = "2026-08-29T01:07:26Z"
    # railway/headline_incidents.json, the closed ai_all_time incident's
    # `baseline_at_open`, plus the worldwide reading from the issue's table.
    BASE = {
        "ai_all_time": {"jobs": 234869, "entries": 93,
                        "captured_at": "2026-08-29T01:06:25Z", "recorded_in": E0829,
                        "excluded_jobs": 0, "excluded_entries": 0},
        "worldwide_all_time": {"jobs": 20544588, "entries": 65241,
                               "captured_at": "2026-08-29T01:06:25Z",
                               "recorded_in": E0829,
                               "excluded_jobs": 120763, "excluded_entries": 414},
    }
    OBS = {"ai_all_time": {"jobs": 243869, "entries": 94},
           "worldwide_all_time": {"jobs": 20514296, "entries": 65252}}
    POOL = {"worldwide_all_time": {"jobs": 120883, "entries": 416},
            "ai_all_time": {"jobs": 0, "entries": 0}}
    AT = datetime(2026, 8, 30, 19, 58, 41, tzinfo=timezone.utc)

    # Scoped to the one pair, for the reason the mutation note further up
    # records: a roll-up assertion can be satisfied by a failure it is not
    # testing.
    PAIR = (("ai_all_time", "worldwide_all_time"),)

    def _judge(self):
        return _run(self.OBS, {k: dict(v) for k, v in self.BASE.items()},
                    now=self.AT, pairs=self.PAIR, excluded=self.POOL)[0]

    def test_the_true_exclusion_delta_does_not_clear_it(self):
        res = self._judge()
        self.assertEqual(res.state, di.FAIL, res.detail)
        self.assertIn("-120 of that", res.detail)   # what dedup actually explains
        self.assertIn("-39,172", res.detail)        # the residual that remains

    def test_the_finding_names_which_half_moved(self):
        """#243's second finding: the alert pointed the investigation at AI.

        -39,292 on its own reads as a subset problem. It was not: worldwide
        fell 30,292 while the AI slice rose 9,000, so three quarters of the
        movement was never in the AI slice at all. A reader must not have to
        subtract two numbers that are not in front of them.
        """
        res = self._judge()
        self.assertIn("-39,292", res.detail)
        self.assertIn("-30,292", res.detail)
        self.assertIn("+9,000", res.detail)

    def test_it_does_not_assert_a_mechanism_it_cannot_establish(self):
        """A net entry count is the difference of two gross flows.

        The old text stated re-scoring as fact, and on this very day that was
        wrong. Both mechanisms have to be offered, and the reason +10 entries
        does not rule out the second has to be on the page.

        The negative is matched case-insensitively on purpose. Written with a
        literal assertNotIn first, and a mutation that restored the old claim
        with one capital letter changed left it GREEN — a negative assertion on
        an exact string tests the string, not the claim.
        """
        res = self._judge()
        self.assertIn("TWO mechanisms", res.detail)
        self.assertIn("LEFT carried more jobs", res.detail)
        self.assertIn("NET figure", res.detail)
        # The old sentence's spine: departures ruled out by fiat.
        self.assertNotIn("that arrived, left, or was folded moved these",
                         res.detail.lower())


class ItIsInTheOneRegistry(unittest.TestCase):

    def test_the_invariant_is_registered(self):
        keys = [i.key for i in di.INVARIANTS]
        self.assertIn("headline_containment", keys)
        self.assertEqual(len(keys), len(set(keys)), "two invariants share a key")


if __name__ == "__main__":
    unittest.main()
