"""The news catch-up pays for each candidate URL at most once per run, and
never for a URL the site already holds.

Run 42993859950 (2026-11-11, window 2026-09-29..2026-11-05) spent its whole
$0.150 ceiling on 831 calls and stored 24 rows: the same Google News URL was
extracted three times in a row (two dated queries per day return the same
item), and the job never called the shared seen-URL pre-check that cron.py,
gdelt_backfill and company_watchlist all use. So every re-dispatch re-paid for
the first days of the window and the cap ran out before the late-October days
(AmEx 10-23, Weil 10-28, NatWest 10-30, Ecco 11-02, Fiserv 11-03) were read.
"""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()
sys.modules.setdefault("openai", SimpleNamespace())

import news_catchup  # noqa: E402


def _e(url, title="t"):
    return {"source_url": url, "title": title}


class UniqueCandidates(unittest.TestCase):
    def test_repeated_url_is_kept_once_first_wins(self):
        got = news_catchup.unique_candidates(
            [_e("https://a/1", "first"), _e("https://a/2"), _e("https://a/1", "again")])
        self.assertEqual([g["source_url"] for g in got], ["https://a/1", "https://a/2"])
        self.assertEqual(got[0]["title"], "first")

    def test_entry_without_url_is_never_dropped(self):
        got = news_catchup.unique_candidates([_e(""), _e(""), {"title": "x"}])
        self.assertEqual(len(got), 3)


class RunPaysOncePerUrl(unittest.TestCase):
    def _run(self, news, dated, seen_filter):
        calls = []
        with patch.dict(os.environ, {"NEWS_DAYS_BACK": "7"}, clear=False), \
             patch.object(news_catchup, "report_source_health", return_value=True), \
             patch.object(news_catchup, "pull_news_articles", return_value=news), \
             patch.object(news_catchup, "dated_google_news", return_value=dated), \
             patch.object(news_catchup, "filter_already_seen", side_effect=seen_filter), \
             patch.object(news_catchup, "extract_layoff_data",
                          side_effect=lambda raw: calls.append(raw["source_url"]) or None), \
             patch.object(news_catchup.spend, "record_job_run"):
            news_catchup.run()
        return calls

    def test_duplicate_urls_across_sources_are_extracted_once(self):
        calls = self._run([_e("https://n/1")],
                          [_e("https://g/1"), _e("https://g/1"), _e("https://n/1")],
                          lambda es: es)
        self.assertEqual(calls, ["https://n/1", "https://g/1"])

    def test_urls_the_site_holds_are_not_extracted(self):
        calls = self._run([], [_e("https://g/held"), _e("https://g/new")],
                          lambda es: [e for e in es if e["source_url"] != "https://g/held"])
        self.assertEqual(calls, ["https://g/new"])


if __name__ == "__main__":
    unittest.main()
