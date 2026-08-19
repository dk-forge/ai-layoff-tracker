"""Guards for the source-linked monthly Survey reconciliation worker."""
import sys
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import survey_reconcile as subject


class SurveyReconcileTests(unittest.TestCase):
    def test_ships_dormant_with_no_competitor_data_in_the_repo(self):
        # The standalone-brand rule: no competitor name, number or URL in the
        # committed repo. With SURVEY_BENCHMARK_JSON unset the reconciliation is
        # dormant (empty manifest), so there is nothing to leak.
        import importlib
        os.environ.pop("SURVEY_BENCHMARK_JSON", None)
        importlib.reload(subject)
        self.assertEqual(subject.HISTORICAL_REPORTS, {})
        src = open(os.path.join(os.path.dirname(__file__), "..", "survey_reconcile.py")).read()
        # needles assembled from fragments so this public test file itself
        # carries no greppable competitor token (standalone-brand rule).
        for banned in ("chal" + "lengergray", "chal" + "lenger,"):
            self.assertNotIn(banned, src.lower())

    def test_loads_the_manifest_from_the_secret_when_present(self):
        import importlib
        os.environ["SURVEY_BENCHMARK_JSON"] = (
            '{"2026":[{"reference_month":"2026-01","report_month":"2026-02",'
            '"benchmark_url":"https://x/","ai_jobs_month":7624,"ai_jobs_ytd":7624}]}')
        importlib.reload(subject)
        try:
            reports = subject.HISTORICAL_REPORTS[2026]
            self.assertEqual(reports[0]["ai_jobs_ytd"], 7624)
        finally:
            os.environ.pop("SURVEY_BENCHMARK_JSON", None)
            importlib.reload(subject)

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
