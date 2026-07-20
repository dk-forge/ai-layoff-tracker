"""Guards for the source-linked monthly Survey reconciliation worker."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("requests", SimpleNamespace())

import survey_reconcile as subject


class SurveyReconcileTests(unittest.TestCase):
    def test_reviewed_manifest_is_monthly_and_source_linked(self):
        reports = subject.HISTORICAL_REPORTS[2026]
        self.assertEqual([item["reference_month"] for item in reports], [
            "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
        ])
        self.assertEqual([item["ai_jobs_ytd"] for item in reports], [7624, 12304, 27645, 49135, 87714, 101743])
        self.assertTrue(all(item["benchmark_url"].startswith("https://www.challengergray.com/") for item in reports))

    def test_reference_month_window_uses_source_evidenced_announcement_date(self):
        self.assertEqual(subject.month_window("2026-02"), ("2026-02-01", "2026-02-28"))
        self.assertEqual(subject.month_window("2026-02", ytd=True), ("2026-01-01", "2026-02-28"))

    def test_new_report_parser_keeps_month_and_ytd_separate(self):
        text = "In June, Artificial Intelligence led all reasons with 14,029 announced during the month. So far in 2026, AI has been cited for 101,743 job cut announcements."
        response = SimpleNamespace(text=text)
        response.raise_for_status = lambda: None
        with patch.object(subject.requests, "get", return_value=response, create=True):
            self.assertEqual(subject.survey_ai_totals("https://example.test/report", "2026-06"), (14029, 101743))

    def test_gap_is_an_alert_not_a_processing_failure_by_default(self):
        worker = (Path(__file__).resolve().parents[1] / "survey_reconcile.py").read_text()
        self.assertIn('SURVEY_FAIL_ON_GAP", "").lower()', worker)
        self.assertIn("return 2 if outside and fail_on_gap else 0", worker)


if __name__ == "__main__":
    unittest.main()
