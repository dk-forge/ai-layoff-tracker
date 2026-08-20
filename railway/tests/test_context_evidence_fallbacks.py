"""Wayback and alternate-source evidence fallbacks stay inside the gates.

Offline: requests / openai / BigQuery are stubbed like the other guard tests.
The fallbacks may only change WHERE a quote is read from — never whether an
exact quote is required, and never by mixing text from two sources.
"""
import os
import sys
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
sys.modules.setdefault("openai", SimpleNamespace())

import enrich_context
from sources import gdelt_bq

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/enrich-context.yml").read_text()

ARTICLE = "Acme Corp announced on March 3, 2026 it would cut 500 jobs. " * 20
EVIDENCE = {
    "announcement_date": "2026-03-03",
    "announcement_evidence": "announced on March 3, 2026 it would cut 500 jobs",
}
ROW = {
    "id": 42, "company_name": "Acme Corp", "layoff_date": "2026-03-15",
    "announcement_date": "", "source_url": "https://timesofindia.indiatimes.com/acme",
}


class WaybackFallbackTests(unittest.TestCase):
    def test_readable_primary_never_touches_the_archive(self):
        with patch.object(enrich_context, "fetch_text", return_value=ARTICLE) as fetch, \
             patch.object(enrich_context, "wayback_snapshot") as availability, \
             patch.object(enrich_context, "extract_context_evidence", return_value=dict(EVIDENCE)):
            result, channel = enrich_context.evidence_for_row(dict(ROW))
        self.assertEqual(channel, "primary")
        self.assertEqual(result["announcement_evidence"], EVIDENCE["announcement_evidence"])
        availability.assert_not_called()
        fetch.assert_called_once_with(ROW["source_url"])

    def test_blocked_primary_recovers_via_newest_snapshot_and_records_it(self):
        snapshot = "https://web.archive.org/web/20260310120000/https://timesofindia.indiatimes.com/acme"
        calls = []

        def fake_fetch(url):
            calls.append(url)
            if url == ROW["source_url"]:
                raise RuntimeError("403 Client Error")
            return ARTICLE

        with patch.object(enrich_context, "fetch_text", side_effect=fake_fetch), \
             patch.object(enrich_context, "wayback_snapshot", return_value=snapshot), \
             patch.object(enrich_context, "extract_context_evidence", return_value=dict(EVIDENCE)):
            result, channel = enrich_context.evidence_for_row(dict(ROW))

        self.assertEqual(channel, "wayback")
        # The raw (id_) variant is fetched; the human-viewable snapshot URL is recorded.
        self.assertIn("/web/20260310120000id_/", calls[1])
        self.assertIn("Wayback snapshot", result["announcement_evidence"])
        self.assertIn(snapshot, result["announcement_evidence"])
        # The quote itself stays first and intact in the evidence string.
        self.assertTrue(result["announcement_evidence"].startswith(EVIDENCE["announcement_evidence"]))

    def test_availability_lookup_resolves_newest_and_fails_soft(self):
        captured = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            captured.update({"url": url, "params": params, "timeout": timeout})
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"archived_snapshots": {"closest": {
                    "available": True,
                    "url": "http://web.archive.org/web/20260101000000/https://example.com/a",
                }}},
            )

        with patch.object(enrich_context.requests, "get", side_effect=fake_get, create=True):
            snapshot = enrich_context.wayback_snapshot("https://example.com/a")
        self.assertEqual(snapshot, "https://web.archive.org/web/20260101000000/https://example.com/a")
        self.assertEqual(captured["url"], enrich_context.WAYBACK_AVAILABILITY_API)
        self.assertEqual(captured["params"]["url"], "https://example.com/a")
        self.assertLessEqual(captured["timeout"], 30)

        with patch.object(enrich_context.requests, "get", side_effect=RuntimeError("archive down"), create=True):
            self.assertEqual(enrich_context.wayback_snapshot("https://example.com/a"), "")

    def test_unusable_primary_and_missing_snapshot_fall_through_without_raising(self):
        with patch.object(enrich_context, "fetch_text", side_effect=RuntimeError("403")), \
             patch.object(enrich_context, "wayback_snapshot", return_value=""), \
             patch.dict(os.environ, {"GCP_BIGQUERY_CREDENTIALS_JSON": ""}, clear=False):
            result, channel = enrich_context.evidence_for_row(dict(ROW))
        self.assertIsNone(result)
        self.assertEqual(channel, "")


class AlternateSourceTests(unittest.TestCase):
    CANDIDATES = [
        {"url": "https://sketchy.example/acme", "domain": "sketchy.example", "title": "", "seendate": ""},
        {"url": "https://timesofindia.indiatimes.com/acme-2", "domain": "timesofindia.indiatimes.com", "title": "", "seendate": ""},
        {"url": "https://www.cnbc.com/2026/03/03/acme-layoffs.html", "domain": "www.cnbc.com", "title": "", "seendate": ""},
    ]

    def _env(self):
        return patch.dict(os.environ, {"GCP_BIGQUERY_CREDENTIALS_JSON": "{}"}, clear=False)

    def test_only_trusted_other_domain_candidates_are_fetched(self):
        fetched = []

        def fake_fetch(url):
            fetched.append(url)
            return ARTICLE

        with self._env(), \
             patch.object(gdelt_bq, "query_company_articles", return_value=list(self.CANDIDATES)) as query, \
             patch.object(enrich_context, "fetch_text", side_effect=fake_fetch), \
             patch.object(enrich_context, "extract_context_evidence", return_value=dict(EVIDENCE)):
            result, channel = enrich_context.alternate_source_evidence(dict(ROW))

        self.assertEqual(channel, "alternate")
        # Untrusted domain and the unreadable original outlet are both skipped.
        self.assertEqual(fetched, ["https://www.cnbc.com/2026/03/03/acme-layoffs.html"])
        self.assertIn("alternate trusted source", result["announcement_evidence"])
        self.assertIn("https://www.cnbc.com/2026/03/03/acme-layoffs.html", result["announcement_evidence"])
        # Narrow query: company + bounded window + shared title vocabulary.
        (company, start, end, terms), _ = query.call_args
        self.assertEqual(company, "Acme Corp")
        self.assertLessEqual((end - start).days, 2 * enrich_context.ALT_WINDOW_DAYS + 1)
        self.assertIn("layoff", " ".join(terms).lower())

    def test_candidate_fetches_are_bounded_and_fail_soft(self):
        many = [
            {"url": f"https://www.cnbc.com/a{i}", "domain": "cnbc.com", "title": "", "seendate": ""}
            for i in range(10)
        ]
        fetched = []

        def failing_fetch(url):
            fetched.append(url)
            raise RuntimeError("403")

        with self._env(), \
             patch.object(gdelt_bq, "query_company_articles", return_value=many), \
             patch.object(enrich_context, "fetch_text", side_effect=failing_fetch):
            result, channel = enrich_context.alternate_source_evidence(dict(ROW))

        self.assertIsNone(result)
        self.assertEqual(channel, "")
        self.assertEqual(len(fetched), enrich_context.ALT_FETCH_LIMIT)

    def test_bigquery_failure_or_missing_anchor_returns_nothing(self):
        with self._env(), \
             patch.object(gdelt_bq, "query_company_articles", side_effect=RuntimeError("quota")):
            self.assertEqual(enrich_context.alternate_source_evidence(dict(ROW)), (None, ""))
        no_anchor = dict(ROW, layoff_date="", announcement_date="")
        with self._env():
            self.assertEqual(enrich_context.alternate_source_evidence(no_anchor), (None, ""))

    def test_readable_but_unsupported_alternate_never_invents_evidence(self):
        with self._env(), \
             patch.object(gdelt_bq, "query_company_articles", return_value=list(self.CANDIDATES)), \
             patch.object(enrich_context, "fetch_text", return_value=ARTICLE), \
             patch.object(enrich_context, "extract_context_evidence", return_value=None):
            self.assertEqual(enrich_context.alternate_source_evidence(dict(ROW)), (None, ""))


class CompanyQueryHelperTests(unittest.TestCase):
    def test_company_pattern_is_escaped_and_lowercased(self):
        self.assertEqual(gdelt_bq.company_pattern("Acme  (US) Corp."), r"acme\ \(us\)\ corp\.")
        self.assertEqual(gdelt_bq.company_pattern("  "), "$^")

    def test_query_binds_company_window_and_caps_scan(self):
        from datetime import datetime
        captured = {}

        class FakeParam(SimpleNamespace):
            def __init__(self, name, kind, value):
                super().__init__(name=name, kind=kind, value=value)

        class FakeConfig(SimpleNamespace):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)

        class FakeClient:
            def query(self, sql, job_config=None):
                captured["sql"] = sql
                captured["config"] = job_config
                return SimpleNamespace(result=lambda: iter([
                    {"url": "https://www.cnbc.com/a", "domain": "CNBC.com", "date_int": 20260303120000,
                     "title": "Acme layoffs"},
                    {"url": "", "domain": "cnbc.com", "date_int": None, "title": ""},
                ]))

        fake_bigquery = SimpleNamespace(ScalarQueryParameter=FakeParam, QueryJobConfig=FakeConfig)
        with patch.object(gdelt_bq, "_client", return_value=(fake_bigquery, FakeClient())):
            articles = gdelt_bq.query_company_articles(
                "Acme Corp", datetime(2026, 2, 1), datetime(2026, 4, 15, 23, 59, 59), ("layoffs",))

        self.assertEqual(articles, [{
            "url": "https://www.cnbc.com/a", "domain": "cnbc.com",
            "title": "Acme layoffs", "seendate": "20260303T120000Z",
        }])
        self.assertIn("_PARTITIONTIME", captured["sql"])
        self.assertIn("LIMIT 60", captured["sql"])
        self.assertEqual(captured["config"].maximum_bytes_billed, gdelt_bq.MAX_BYTES_BILLED)
        params = {p.name: p.value for p in captured["config"].query_parameters}
        self.assertEqual(params["company_re"], r"acme\ corp")
        self.assertEqual(params["day_start"], "2026-02-01")
        self.assertEqual(params["day_end"], "2026-04-16")
        self.assertEqual(params["window_start"], 20260201000000)
        self.assertEqual(params["window_end"], 20260415235959)


class WorkflowWiringTests(unittest.TestCase):
    def test_workflow_installs_bigquery_and_passes_credentials(self):
        self.assertIn("google-cloud-bigquery", WORKFLOW)
        self.assertIn("GCP_BIGQUERY_CREDENTIALS_JSON: ${{ secrets.GCP_BIGQUERY_CREDENTIALS_JSON }}", WORKFLOW)

    def test_worker_stops_between_rows_before_actions_limit(self):
        self.assertIn("CONTEXT_DEADLINE_SECONDS: '900'", WORKFLOW)
        worker = (ROOT / "railway/enrich_context.py").read_text()
        self.assertIn("time.monotonic() - started_at >= DEADLINE_SECONDS", worker)
        self.assertIn("stopping safely after", worker)


if __name__ == "__main__":
    unittest.main()
