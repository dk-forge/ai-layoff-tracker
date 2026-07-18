"""Regression guards for NewsAPI catch-up health telemetry."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# The test exercises only mocked collector/health calls.  Keep it runnable in
# the repository's lightweight local test environment, which may not install
# the Railway requirements first.
sys.modules.setdefault("requests", SimpleNamespace())
sys.modules.setdefault("openai", SimpleNamespace())

import news_catchup


class NewsCatchupHealthTests(unittest.TestCase):
    def test_successful_manual_run_reports_running_then_ok(self):
        reports = []
        with patch.dict(os.environ, {"NEWS_DAYS_BACK": "7"}, clear=False), \
             patch.object(news_catchup, "report_source_health", side_effect=lambda *args: reports.append(args)), \
             patch.object(news_catchup, "pull_news_articles", return_value=[]):
            news_catchup.run()

        self.assertEqual(reports[0], ("newsapi", "running", 0, "manual 7-day catch-up in progress"))
        self.assertEqual(reports[-1], (
            "newsapi", "ok", 0,
            "manual 7-day catch-up: 0 posted, 0 duplicates, 0 non-events, 0 processing failures",
        ))

    def test_collection_exception_is_visible_as_degraded_and_propagates(self):
        reports = []
        with patch.dict(os.environ, {"NEWS_DAYS_BACK": "7"}, clear=False), \
             patch.object(news_catchup, "report_source_health", side_effect=lambda *args: reports.append(args)), \
             patch.object(news_catchup, "pull_news_articles", side_effect=RuntimeError("upstream unavailable")):
            with self.assertRaisesRegex(RuntimeError, "upstream unavailable"):
                news_catchup.run()

        self.assertEqual(reports[-1], (
            "newsapi", "degraded", 0,
            "manual 7-day catch-up failed: upstream unavailable",
        ))


if __name__ == "__main__":
    unittest.main()
