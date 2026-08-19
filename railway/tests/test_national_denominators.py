"""THE COLLECTORS THAT TURN A PUBLISHED TOTAL INTO A COVERAGE FIGURE.

Every assertion here exists because getting it wrong produces a number that
looks right. That is the whole risk class in this module: nothing crashes when a
denominator is 43 times too large, or when two countries counting different
things are added together, or when a suppressed cell is read as a zero. The
figure just comes out wrong and gets quoted.

The five that matter most:

  THE TAIWAN TWIN. data.gov.tw carries 27505 (大量解僱通報, art. 4 collective
  dismissal notifications, keyed on ROC years) and 27508 (大量解僱預警通報, the
  wage-arrears early-warning tripwire, keyed on Western years). The titles differ
  by two characters and 27508's numbers are ~43x larger. Built on the wrong one,
  Taiwan's denominator becomes half a million workers and our coverage reads as a
  rounding error nobody can explain. The parser refuses a Western-year column
  rather than converting it, and the fixture below has 27508's exact shape.

  NO SUM ACROSS SERIES. Directive 98/59/EC lets each state set its own
  threshold, and Taiwan counts plants rather than employers. `combine()` must
  refuse a mismatched unit AND a mismatched period, and the refusal must be an
  exception rather than a None a caller can ignore.

  A SUPPRESSED CELL IS NOT A ZERO. ONS writes '[c]' where a figure is
  confidential. Summed as 0 it deflates the denominator, which INFLATES our
  coverage — the direction a broken measurement must never fail in. A window
  containing one raises instead.

  A PARTIAL WINDOW IS NOT A WINDOW. Same failure direction: eleven months summed
  and divided as if twelve is a smaller denominator and a flattering ratio.

  THE OVER-UNIVERSE RESULT IS A RESULT. Our rows are not a subset of the
  notified population, so a ratio above 1.0 is a category error rather than
  great coverage, and it must not be clamped to 100%.
"""
import json
import sys
import unittest
import unittest.mock
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import national_denominators as nd  # noqa: E402
from recall_goldset import UNKNOWN  # noqa: E402
from rolling_recall import MEASURED, NOT_MEASURABLE  # noqa: E402


def _mol(records):
    return {"success": True, "updateTime": "20260611T154255",
            "result": {"resource_id": "A17000000J-020115-aUA", "records": records}}


class TheTaiwanTwin(unittest.TestCase):
    """27505 is the notification series; 27508 is a different statute."""

    def test_roc_years_are_converted(self):
        rows, when = nd.parse_taiwan(_mol([
            {"序號": "1", "民國年（民國年）": "114", "家數（數量）": "337",
             "人數（數量）": "11752", "備註": ""},
            {"序號": "2", "民國年（民國年）": "113", "家數（數量）": "303",
             "人數（數量）": "10528", "備註": ""}]))
        self.assertEqual(rows[0], {"year": 2025, "establishments": 337,
                                   "workers": 11752})
        self.assertEqual(when, "20260611T154255")

    def test_western_years_are_refused_not_converted(self):
        # 27508's own shape and its own 2025 numbers: 43x larger.
        with self.assertRaises(nd.TaiwanWrongDataset):
            nd.parse_taiwan(_mol([
                {"序號": "1", "年（年）": "2025", "家數（數量）": "6579",
                 "人數（數量）": "503386", "備註": ""}]))

    def test_a_roc_column_holding_a_western_year_is_refused(self):
        with self.assertRaises(nd.TaiwanWrongDataset):
            nd.parse_taiwan(_mol([
                {"民國年（民國年）": "2025", "家數（數量）": "6579",
                 "人數（數量）": "503386"}]))

    def test_the_pinned_resource_id_is_27505s(self):
        self.assertIn("A17000000J-020115-aUA", nd.TW_REST)


class SeriesAreNotAddedTogether(unittest.TestCase):
    """There is no worldwide denominator and there must not be one."""

    @staticmethod
    def _slice(unit, label, kind="months_12", value=100):
        return {"state": MEASURED, "unit": unit, "denominator": value,
                "period": {"kind": kind, "label": label}}

    def test_same_unit_and_period_sums(self):
        self.assertEqual(nd.combine([self._slice(nd.WORKERS, "2025-07..2026-06"),
                                     self._slice(nd.WORKERS, "2025-07..2026-06")]),
                         200)

    def test_different_units_refuse(self):
        with self.assertRaises(nd.IncomparableSeries):
            nd.combine([self._slice(nd.WORKERS, "2025"),
                        self._slice(nd.ESTABLISHMENTS, "2025")])

    def test_different_periods_refuse(self):
        with self.assertRaises(nd.IncomparableSeries):
            nd.combine([self._slice(nd.WORKERS, "2025-07..2026-06"),
                        self._slice(nd.WORKERS, "2024-07..2025-06")])

    def test_different_period_kinds_refuse(self):
        with self.assertRaises(nd.IncomparableSeries):
            nd.combine([self._slice(nd.WORKERS, "2025", kind="year"),
                        self._slice(nd.WORKERS, "2025", kind="financial_year_apr_mar")])

    def test_an_unmeasured_slice_may_not_be_summed(self):
        bad = dict(self._slice(nd.WORKERS, "2025"), state=UNKNOWN)
        with self.assertRaises(nd.IncomparableSeries):
            nd.combine([self._slice(nd.WORKERS, "2025"), bad])

    def test_the_gb_and_ni_slices_cannot_be_summed_as_declared(self):
        # The one pair a reader would most want summed into "the UK": they
        # count over different period shapes, so the refusal is not theoretical.
        self.assertNotEqual(nd.SERIES["gb_hr1_potential_redundancies"]["cadence"],
                            nd.SERIES["ni_proposed_redundancies"]["cadence"])


class ASuppressedCellIsNotAZero(unittest.TestCase):

    def test_ons_confidential_marker_reads_as_missing(self):
        self.assertIsNone(nd._int_or_none("[c]"))
        self.assertIsNone(nd._int_or_none(""))
        self.assertIsNone(nd._int_or_none(None))
        self.assertEqual(nd._int_or_none("20,931"), 20931)

    def test_a_window_containing_a_suppressed_month_raises(self):
        months = {date(2025, m if m <= 12 else 1, 1): {"workers": 100, "employers": 5}
                  for m in range(1, 13)}
        months[date(2025, 6, 1)]["workers"] = None
        with self.assertRaises(ValueError) as ctx:
            nd.window_from_months(months, today=date(2026, 8, 18))
        self.assertIn("INFLATE", str(ctx.exception))


class APartialWindowIsNotAWindow(unittest.TestCase):

    def test_eleven_settled_months_raise(self):
        months = {date(2025, m, 1): {"workers": 100, "employers": 5}
                  for m in range(1, 12)}
        with self.assertRaises(ValueError):
            nd.window_from_months(months, today=date(2026, 8, 18))

    def test_the_window_ends_at_the_last_settled_month(self):
        months = {date(y, m, 1): {"workers": 10, "employers": 1}
                  for y in (2025, 2026) for m in range(1, 13)}
        out = nd.window_from_months(months, today=date(2026, 8, 18))
        # 45 settle days from 2026-08-18 lands in July, so June is the last
        # month that CLOSED long enough ago to be judged.
        self.assertEqual(out["period"]["label"], "2025-07..2026-06")
        self.assertEqual(out["value"], 120)
        self.assertEqual(out["unit"], nd.WORKERS)

    def test_the_settle_lag_is_imported_not_re_chosen(self):
        import rolling_recall
        self.assertIs(nd.SETTLE_DAYS, rolling_recall.SETTLE_DAYS)


class ExcelDates(unittest.TestCase):

    def test_the_1899_epoch(self):
        self.assertEqual(nd.excel_date(46204), date(2026, 7, 1))
        self.assertEqual(nd.excel_date("43556"), date(2019, 4, 1))

    def test_a_header_cell_does_not_become_a_date(self):
        self.assertIsNone(nd.excel_date("Month"))
        self.assertIsNone(nd.excel_date(None))
        self.assertIsNone(nd.excel_date(3))


class TheNorthernIrelandRollingRow(unittest.TestCase):
    """The last row is labelled like a financial year and is not one."""

    HTML = ('<img src="data:image/png;base64,' + 'A' * 200 + '" />'
            '<a href="data:text/csv;base64,'
            + __import__("base64").b64encode(
                b'"Year","Proposed","Confirmed"\r\n'
                b'"2023/24",2820,2640\r\n"2024/25",2980,2370\r\n'
                b'"2025/26",2780,1390\r\n').decode() + '"></a>')

    def test_the_final_row_is_flagged_rolling(self):
        rows = nd.parse_ni(self.HTML)
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[-1]["rolling"])
        self.assertFalse(rows[0]["rolling"])

    def test_the_measured_year_is_the_last_complete_one(self):
        rows = [r for r in nd.parse_ni(self.HTML) if not r["rolling"]]
        self.assertEqual(rows[-1]["financial_year"], "2024/25")
        self.assertEqual(rows[-1]["proposed"], 2980)

    def test_a_report_without_the_series_raises(self):
        with self.assertRaises(ValueError):
            nd.parse_ni("<html>no charts here</html>")


class EveryDeclaredSliceIsReported(unittest.TestCase):
    """rolling_recall's rule: a slice that cannot be computed says so."""

    def test_declared_is_the_union_of_both_registries(self):
        self.assertEqual(set(nd.DECLARED_SLICES),
                         set(nd.SERIES) | set(nd.NOT_BUILDABLE))

    def test_a_missing_slice_makes_the_report_unknown(self):
        doc = {"measured_at": nd._utc_now_iso(),
               "declared_slices": ["a", "b"],
               "slices": {"a": {"state": NOT_MEASURABLE, "detail": "x"}}}
        state, detail = nd.judge(doc)
        self.assertEqual(state, UNKNOWN)
        self.assertIn("b", detail)

    def test_an_unknown_slice_is_never_averaged_away(self):
        doc = {"measured_at": nd._utc_now_iso(),
               "declared_slices": ["a", "b"],
               "slices": {"a": {"state": MEASURED, "coverage_lower": 0.5,
                                "coverage_upper": 0.5, "denominator": 10,
                                "period": {"label": "2025"}},
                          "b": {"state": UNKNOWN, "detail": "fetch failed"}}}
        self.assertEqual(nd.judge(doc)[0], UNKNOWN)

    def test_no_measurement_at_all_is_unknown_not_fine(self):
        self.assertEqual(nd.judge(None)[0], UNKNOWN)

    def test_a_stale_measurement_is_unknown(self):
        doc = {"measured_at": "2020-01-01T00:00:00Z", "declared_slices": [],
               "slices": {}}
        state, detail = nd.judge(doc)
        self.assertEqual(state, UNKNOWN)
        self.assertIn("days old", detail)


class TheOverUniverseResult(unittest.TestCase):
    """A ratio above 1.0 is a category error, not great coverage."""

    def test_it_is_not_clamped_and_not_measured(self):
        spec = dict(nd.SERIES["ee_collective_redundancy_notices"])
        spec["collector"] = lambda today=None, get=None: {
            "period": {"kind": "months_12", "label": "2025-07..2026-06",
                       "from": "2025-07-01", "to": "2026-06-30"},
            "value": 1000, "unit": nd.WORKERS}
        with unittest.mock.patch.dict(
                nd.SERIES, {"ee_collective_redundancy_notices": spec}), \
             unittest.mock.patch.object(nd, "held",
                                        lambda *a, **k: (900, 4000, {})):
            out = nd.measure_series("ee_collective_redundancy_notices",
                                    today=date(2026, 8, 18))
        self.assertEqual(out["state"], nd.OVER_UNIVERSE)
        self.assertGreater(out["coverage_upper"], 1.0)
        self.assertEqual(nd.judge({"measured_at": nd._utc_now_iso(),
                                   "declared_slices": ["k"],
                                   "slices": {"k": out}})[0], UNKNOWN)


class ANumeratorWeCannotBuildIsNotMeasurable(unittest.TestCase):
    """Northern Ireland: the denominator is real and no matching numerator is."""

    def test_ni_is_declared_without_a_numerator(self):
        self.assertFalse(
            nd.SERIES["ni_proposed_redundancies"].get("numerator_available", True))

    def test_the_reason_names_the_missing_split(self):
        why = nd.SERIES["ni_proposed_redundancies"]["no_numerator_why"]
        self.assertIn("Northern Ireland", why)
        self.assertIn("United Kingdom", why)


class EverySeriesDeclaresWhatItCounts(unittest.TestCase):
    """Without these fields the comparability guard cannot do its job."""

    REQUIRED = ("country", "label", "authority", "cadence", "unit", "counts",
                "collector", "licence", "robots", "caveats")

    def test_every_field_is_present(self):
        for key, spec in nd.SERIES.items():
            for field in self.REQUIRED:
                self.assertIn(field, spec, f"{key} is missing {field}")
            self.assertIn(spec["unit"], nd.UNITS, key)
            self.assertIn(spec["cadence"], nd.MAX_SERIES_LAG_DAYS, key)
            self.assertTrue(spec["caveats"], f"{key} declares no caveats")

    def test_every_not_buildable_entry_says_why(self):
        for key, spec in nd.NOT_BUILDABLE.items():
            self.assertTrue(spec.get("why"), key)
            self.assertTrue(spec.get("country"), key)

    def test_the_assessment_expires(self):
        stale = nd.assess_not_buildable("pl_group_layoffs", today=date(2030, 1, 1))
        self.assertEqual(stale["state"], UNKNOWN)
        fresh = nd.assess_not_buildable("pl_group_layoffs", today=date(2026, 8, 19))
        self.assertEqual(fresh["state"], NOT_MEASURABLE)


class TheCommittedMeasurementParses(unittest.TestCase):

    def test_it_is_readable_and_declares_its_slices(self):
        doc = nd.load_measurement()
        if doc is None:
            self.skipTest("no measurement committed yet")
        self.assertEqual(set(doc["declared_slices"]) - set(doc["slices"]), set())
        for key, s in doc["slices"].items():
            self.assertIn("state", s, key)

    def test_it_is_valid_json_on_disk(self):
        if nd.MEASUREMENT_PATH.exists():
            json.loads(nd.MEASUREMENT_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
