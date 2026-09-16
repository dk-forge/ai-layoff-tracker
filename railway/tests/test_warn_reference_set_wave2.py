"""Offline guards for the US WARN reference set, wave 2 (IL/OH/PA).

Wave 1's own test file guards three things this set inherits — it must not move
the published SEC figure, it must not promote its own recall, and it must not
score a query that was never sent as a miss. This file guards the four things
that are new, each of which has already gone wrong once during assembly:

  1. **The unit is not copied.** Wave 2 must define no collapse rule, no alias
     derivation and no size band of its own, or the two waves' denominators can
     drift apart and the pooled figure becomes one number made of two questions.
  2. **The four measurement files are four files.** Wave 2 must be unable to
     write wave 1's manifest or measurement, or the SEC set's.
  3. **PA's year/month parse is checked by evidence, not by hope.** The first
     parse filed every 2024 and 2023 notice under 2025 and came back as a 36%
     coverage finding. The guard that caught it must keep working, and it must
     stay ONE-SIDED.
  4. **An empty read is never a pass.** The Ohio transcription check must have a
     `not_verified` state for a notice with no text layer, and `not_stated_in_text`
     must not be reported as a disagreement.

No network, no keys.
"""
import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warn_reference_set as W                                    # noqa: E402
import warn_reference_set_wave2 as V                              # noqa: E402


LEDGER_PATH = V.HERE / "warn_recall_adjudications_wave2.json"  # wave 2's own ledger


def _manifest():
    return json.loads(V.MANIFEST_PATH.read_text(encoding="utf-8"))


def _live_accepts():
    """Reference ids with a live `accept` in the wave-2 ledger (reverts undone)."""
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    live = {}
    for e in ledger["decisions"]:
        if e["decision"] == "revert":
            live.pop(e["reverts"].split("@")[0], None)
        else:
            live[e["reference_row_id"]] = e["decision"]
    return {rid for rid, d in live.items() if d == "accept"}


class TheUnitIsImportedAndNotCopied(unittest.TestCase):
    def test_wave2_defines_no_rule_of_its_own(self):
        body = Path(V.__file__).read_text(encoding="utf-8")
        code = re.sub('"' * 3 + ".*?" + '"' * 3, "", body, flags=re.S)
        for forbidden in ("def collapse_key_name", "def aliases_for",
                          "def query_terms_for", "def size_band",
                          "def build_events", "def systematic_sample",
                          "def candidates_for", "def summarise", "def _seed"):
            self.assertNotIn(forbidden, code,
                             f"wave 2 defines {forbidden!r} instead of importing "
                             f"wave 1's. Two waves whose unit of measurement "
                             f"drifted apart cannot be pooled at all.")

    def test_the_window_is_the_same_object_as_wave_ones(self):
        self.assertEqual(V.WINDOW, W.WINDOW)

    def test_the_manifest_records_the_same_collapse_rule(self):
        m = _manifest()
        self.assertIn(f"first-{W.COLLAPSE_TOKENS}-token", m["collapse_rule"])


class FourFilesNotTwo(unittest.TestCase):
    def test_every_path_is_distinct(self):
        import recall_goldset
        paths = [V.MANIFEST_PATH, V.MEASUREMENT_PATH,
                 W.MANIFEST_PATH, W.WARN_MEASUREMENT_PATH,
                 recall_goldset.MANIFEST_PATH, recall_goldset.MEASUREMENT_PATH]
        self.assertEqual(len(set(paths)), len(paths),
                         "two reference sets share a file; a re-measure of one "
                         "would overwrite the other's result")

    def test_wave2_code_names_no_other_sets_files(self):
        body = Path(V.__file__).read_text(encoding="utf-8")
        code = re.sub('"' * 3 + ".*?" + '"' * 3, "", body, flags=re.S)
        code = "\n".join(l for l in code.splitlines()
                         if not l.strip().startswith("#"))
        for token in ("recall_measurement.json", "recall_adjudications.json",
                      "MATCHED_FLOOR", "ca-tx-fl-tn"):
            self.assertIsNone(re.search(token, code),
                              f"wave 2's code references {token!r}; it is additive "
                              f"and must not be able to move another set's figure")


class NothingIsMatchedUntilAnEditorSaysSo(unittest.TestCase):
    # Until 2026-09-16 these two tests asserted that every event arrives
    # `not_matched` and that the committed numerator is zero. That was the
    # correct assertion for a set nobody had reviewed. Wave 2 was adjudicated
    # on 2026-09-16 (reviewer agent-a-2026-09-16, ledger
    # railway/warn_recall_adjudications_wave2.json), so the assertion is now
    # wave 1's stronger form: a match may exist, but ONLY with a named
    # adjudicator and a live ledger accept behind it, and the measurement's
    # numerator must be exactly the ledger's accepts -- no larger (a machine
    # promoted itself) and no smaller (a signed decision never reached the
    # measurement).
    def test_the_committed_manifest_has_no_self_awarded_match(self):
        m = _manifest()
        accepted = _live_accepts()
        for key in ("reference_events", "large_event_census"):
            for ev in m[key]:
                rid = ev["reference_row_id"]
                if ev.get("match_decision") == "matched":
                    self.assertTrue(ev.get("adjudicated_by"),
                                    f"{rid} is matched with no adjudicator")
                    self.assertIn(rid, accepted,
                                  f"{rid} is matched with no live accept in the "
                                  f"wave-2 ledger")
                else:
                    self.assertEqual(ev["match_decision"], "not_matched", rid)
                    self.assertNotIn(rid, accepted,
                                     f"{rid} has a live accept but is not matched")

    def test_the_committed_measurements_numerator_is_exactly_the_ledgers_accepts(self):
        if not V.MEASUREMENT_PATH.exists():
            self.skipTest("UNKNOWN, NOT RUN: no wave-2 measurement is committed")
        meas = json.loads(V.MEASUREMENT_PATH.read_text(encoding="utf-8"))
        accepted = _live_accepts()
        for stratum in ("primary", "large_census"):
            ids = {r["id"] for r in meas["results"][stratum]}
            confirmed = {r["id"] for r in meas["results"][stratum]
                         if r["match_decision"] == "matched"}
            self.assertEqual(confirmed, accepted & ids,
                             f"{stratum}: the measurement's matched ids and the "
                             f"ledger's live accepts disagree; re-run --measure or "
                             f"find the hand edit")
        k = meas["summary"]["editor_confirmed_overall"]["k"]
        self.assertEqual(k, len(accepted & {r["id"] for r in meas["results"]["primary"]}))


class PennsylvaniaYearParse(unittest.TestCase):
    """The guard that caught a frame which read as a result."""

    @staticmethod
    def _rows(month, authored, n=4):
        return [{"published_month": month, "cms_modify_date": authored}
                for _ in range(n)]

    def test_a_month_authored_long_before_itself_raises(self):
        rows = self._rows("2025-08", "2024-09-19")
        with self.assertRaises(RuntimeError) as cm:
            V._pa_year_month_is_sane(rows)
        self.assertIn("2025-08", str(cm.exception))
        self.assertIn("wrong", str(cm.exception).lower())

    def test_it_is_one_sided_an_entry_edited_later_is_ordinary(self):
        # A correction re-publishes an old entry. That must NOT trip the guard.
        self.assertTrue(V._pa_year_month_is_sane(self._rows("2025-08", "2026-05-01")))

    def test_one_republished_old_entry_cannot_trip_it(self):
        rows = (self._rows("2025-08", "2025-08-14", 4)
                + self._rows("2025-08", "2019-01-01", 1))
        self.assertTrue(V._pa_year_month_is_sane(rows))

    def test_the_committed_pa_frame_passes_its_own_guard(self):
        m = _manifest()
        rows = [{"published_month": c["published_month"],
                 "cms_modify_date": c.get("cms_modify_date")}
                for key in ("reference_events", "large_event_census")
                for ev in m[key] if ev["state"] == "PA"
                for c in ev["component_rows"] if c.get("published_month")]
        self.assertTrue(V._pa_year_month_is_sane(rows))

    def test_the_tolerance_is_not_quietly_widened(self):
        self.assertLessEqual(V.PA_MAX_AUTHORED_BEFORE_DAYS, 120,
                             "widening this is how the defect comes back; find "
                             "which heading form the walk stopped recognising")

    def test_the_year_pattern_matches_a_bare_h2_as_well_as_a_classed_one(self):
        for markup in ('<h2 class="cmp-accordion__main-heading--large">2025</h2>',
                       "<h2>2024</h2>", "<h2 >2023</h2>"):
            hit = V._PA_TITLE.search(markup)
            self.assertIsNotNone(hit, markup)
            self.assertTrue(hit.group(2), f"{markup} did not read as a year")


class StatusMarkersAreCutOnTheReferenceSideOnly(unittest.TestCase):
    def test_a_leading_update_marker_is_cut(self):
        name, raw, cut = V._employer("UPDATE Senior Resource Connection")
        self.assertEqual(name, "Senior Resource Connection")
        self.assertEqual(raw, "UPDATE Senior Resource Connection")
        self.assertTrue(cut)

    def test_a_marker_inside_a_name_is_not_cut(self):
        name, _, cut = V._employer("Acme Update Services LLC")
        self.assertEqual(name, "Acme Update Services LLC")
        self.assertFalse(cut)

    def test_a_marker_that_is_the_whole_name_is_not_a_marker(self):
        name, _, cut = V._employer("Updated")
        self.assertEqual(name, "Updated")
        self.assertFalse(cut)

    def test_the_raw_published_string_survives_onto_every_component_row(self):
        m = _manifest()
        cutrows = [c for key in ("reference_events", "large_event_census")
                   for ev in m[key] for c in ev["component_rows"]
                   if c.get("status_marker_cut")]
        for c in cutrows:
            self.assertTrue(c.get("employer_published_raw"),
                            "a cut row lost the state's own published string, so "
                            "a reviewer cannot check the cut")
            self.assertNotEqual(c["employer_published_raw"], c["employer_published"])


class AnEmptyReadIsNeverAPass(unittest.TestCase):
    def test_the_transcription_check_has_a_not_verified_state(self):
        body = Path(V.__file__).read_text(encoding="utf-8")
        for state in ("not_verified", "not_stated_in_text",
                      "partially_confirmed", "confirmed"):
            self.assertIn(state, body)

    def test_no_committed_ohio_event_is_recorded_as_a_bare_disagreement(self):
        m = _manifest()
        allowed = {"confirmed", "partially_confirmed",
                   "not_stated_in_text", "not_verified"}
        for key in ("reference_events", "large_event_census"):
            for ev in m[key]:
                check = ev.get("transcription_check")
                if check:
                    self.assertIn(check["status"], allowed, ev["reference_row_id"])

    def test_every_ohio_sampled_event_carries_a_check(self):
        m = _manifest()
        for key in ("reference_events", "large_event_census"):
            for ev in m[key]:
                if ev["state"] == "OH":
                    self.assertIn("transcription_check", ev,
                                  f"{ev['reference_row_id']} was never checked "
                                  f"against the state's own notice, and an "
                                  f"unperformed check is not a pass")


class TheManifestSaysWhatItIsAndWhatItIsNot(unittest.TestCase):
    def test_it_is_not_eligible_for_the_public_benchmark_endpoint(self):
        m = _manifest()
        self.assertIn("not_published", m["publication_status"])
        self.assertIn("single actor", m["assembled_by"])

    def test_new_york_is_recorded_as_excluded_with_a_reason(self):
        m = _manifest()
        self.assertIn("NY", m["excluded_states"])
        self.assertNotIn("NY", m["states"])
        self.assertGreater(len(m["excluded_states"]["NY"]), 200,
                           "an exclusion is a claim and needs its evidence")

    def test_ohios_independence_cost_is_stated_in_the_manifest(self):
        note = _manifest()["sources"]["OH"]["note"]
        self.assertIn("NOT", note)
        self.assertIn("independent", note.lower())

    def test_pennsylvanias_month_only_basis_is_stated(self):
        m = _manifest()
        self.assertIn("MONTH", m["period"]["date_field"])

    def test_every_pa_notice_date_is_the_first_of_a_month(self):
        m = _manifest()
        for key in ("reference_events", "large_event_census"):
            for ev in m[key]:
                if ev["state"] == "PA":
                    self.assertTrue(ev["notice_date"].endswith("-01"),
                                    ev["reference_row_id"])

    def test_the_window_boundaries_are_month_boundaries(self):
        # This is what makes PA's month-only basis sufficient. If either
        # boundary ever moves off a month edge, a PA event can straddle the
        # frame edge and the state stops qualifying under criterion (d).
        lo, hi = (date.fromisoformat(x) for x in V.WINDOW)
        self.assertEqual(lo.day, 1)
        self.assertEqual((hi + __import__("datetime").timedelta(days=1)).day, 1)

    def test_every_frame_covers_every_month_of_the_window(self):
        m = _manifest()
        for st, rng in m["frame_notice_date_range"].items():
            self.assertEqual(rng["months_covered"], 12,
                             f"{st}'s frame is short; a frame that stops early is "
                             f"a smaller denominator, not a recall result")


class IllinoisParseIsCheckedAgainstThePublisher(unittest.TestCase):
    def test_every_month_has_a_footer_check_and_the_row_counts_agree(self):
        m = _manifest()
        checks = m.get("il_monthly_footer_check") or []
        self.assertEqual(len(checks), 12, "one arithmetic check per month of the window")
        for c in checks:
            pub = c.get("published_totals") or []
            if len(pub) == 2:
                self.assertEqual(pub[0], c["parsed_rows"],
                                 f"{c['month']}: the department counts "
                                 f"{pub[0]} events and this parse found "
                                 f"{c['parsed_rows']} -- a row was missed or invented")

    def test_a_disagreeing_month_says_by_how_much(self):
        for c in _manifest().get("il_monthly_footer_check") or []:
            if not c.get("agrees"):
                self.assertIsNotNone(c.get("impacted_delta"),
                                     f"{c['month']} disagrees and does not say by "
                                     f"how much, which reads as 'the parse is "
                                     f"wrong somewhere'")


if __name__ == "__main__":
    unittest.main()
