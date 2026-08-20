"""Regression guards for the weekly news catch-up's health telemetry.

The id is pinned on purpose. This job posted under the RETIRED "newsapi" id for
five weeks after that collector was stood down, which both voided the retirement
(alt_retired_sources() only masks a row whose last run predates the retirement
date) and produced a permanent "newsapi stale" alarm on ops_status, because
"newsapi" carried a twice-daily ceiling while this job runs weekly. Pinning the
id here means a future rename has to be a deliberate, reviewed change.
"""
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
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()
sys.modules.setdefault("openai", SimpleNamespace())

import news_catchup


class NewsCatchupHealthTests(unittest.TestCase):
    def test_successful_manual_run_reports_running_then_ok(self):
        reports = []
        with patch.dict(os.environ, {"NEWS_DAYS_BACK": "7"}, clear=False), \
             patch.object(news_catchup, "report_source_health", side_effect=lambda *args: (reports.append(args) or True)), \
             patch.object(news_catchup, "pull_news_articles", return_value=[]):
            news_catchup.run()

        self.assertEqual(reports[0], ("news_catchup", "running", 0, "7-day catch-up in progress"))
        self.assertEqual(reports[-1], (
            "news_catchup", "ok", 0,
            "7-day catch-up: 0 posted, 0 duplicates, 0 non-events, 0 processing failures",
        ))

    def test_collection_exception_is_visible_as_degraded_and_propagates(self):
        reports = []
        with patch.dict(os.environ, {"NEWS_DAYS_BACK": "7"}, clear=False), \
             patch.object(news_catchup, "report_source_health", side_effect=lambda *args: (reports.append(args) or True)), \
             patch.object(news_catchup, "pull_news_articles", side_effect=RuntimeError("upstream unavailable")):
            with self.assertRaisesRegex(RuntimeError, "upstream unavailable"):
                news_catchup.run()

        self.assertEqual(reports[-1], (
            "news_catchup", "degraded", 0,
            "7-day catch-up failed: upstream unavailable",
        ))

    def test_health_write_failure_fails_the_manual_workflow(self):
        with patch.dict(os.environ, {"NEWS_DAYS_BACK": "7"}, clear=False), \
             patch.object(news_catchup, "report_source_health", return_value=False), \
             patch.object(news_catchup, "pull_news_articles") as collector:
            with self.assertRaisesRegex(RuntimeError, "Could not publish news catch-up health status"):
                news_catchup.run()
        collector.assert_not_called()

    def test_never_reports_under_the_retired_newsapi_id(self):
        # The retired collector must receive no further posts, or
        # alt_retired_sources() can never mask it and ops_status shows a
        # permanent, un-clearable "newsapi stale".
        self.assertEqual(news_catchup.HEALTH_ID, "news_catchup")
        src = Path(news_catchup.__file__).read_text(encoding="utf-8")
        body = src.split('"""', 2)[-1]          # skip the module docstring
        self.assertNotIn('report_source_health("newsapi"', body)


if __name__ == "__main__":
    unittest.main()
