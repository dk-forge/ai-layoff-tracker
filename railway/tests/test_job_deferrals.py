"""A worker that cannot survive its own deploy is not fail-loud, just loud.

THE DEFECT THIS CLOSES
----------------------
`Extract affected-role categories` died on 2026-08-12 with one `503 Server
Error` from `/enrich-roles` and emailed the owner. The host was answering again
minutes later. WordPress goes into maintenance mode while a plugin update is
applied, this repo deploys by FTPS on every push to main, and several deploys
went out that night: the scheduled job and the deploy of the code it runs were
colliding, and the job had no tolerance for it. The sibling tracker's
`place-unplaced` died the same night with the literal string "Briefly
unavailable for scheduled maintenance".

`host_call.py` already resolved a workflow's single `curl` to three outcomes.
The Python workers — which make many calls interleaved with model work and so
cannot shell out per call — never got it. They do now, through the SAME
`http_retry` transient set and the SAME committed ledger, because a second copy
of either is the drift those modules exist to prevent.

WHAT MUST STAY TRUE, and the reason these tests are paired
----------------------------------------------------------
Every job below is asserted twice: a transient 503 defers and exits 0, AND a
403 still exits non-zero on the first occurrence. The second half is the point.
Data-changing jobs fail loudly on any failed batch; a host that is briefly
restarting is not a failed batch, but a wrong key, a missing route, and a 2xx
body reporting failed rows all are, and softening that would be worse than the
noise this change removes.

No network anywhere. No keys.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deferral_ledger
import host_call
import http_retry


class _Response:
    """The bit of `requests.Response` the workers actually touch."""

    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)
        self.content = self.text.encode()
        self.encoding = "utf-8"
        self.url = "https://asktherecruiter.com/blog/x"

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            # A sibling test module may have installed a SimpleNamespace stub
            # for `requests`; the workers only need SOME exception here.
            error = getattr(requests, "HTTPError", None)
            if error is None:
                raise RuntimeError(f"HTTP {self.status_code}")
            raise error(f"HTTP {self.status_code}", response=self)


class _JobCase(unittest.TestCase):
    """Runs a worker's `main()` against a host scripted to one status.

    Both transports are pinned at once: `requests.get` (what `get_with_retry`
    uses) and `http_retry._send` (what `call_with_retry` uses), so a job is
    covered whichever half of the host API it happens to reach first.
    """

    #: Subclasses set these.
    module = None
    job = None
    env = {}

    def setUp(self):
        if self.module is None:
            self.skipTest("base case")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ledger = Path(self._tmp.name) / "ledger.json"
        self.envelope = str(Path(self._tmp.name) / "envelope.json")

        base = {"WP_SITE_URL": "https://asktherecruiter.com/blog",
                "WP_API_KEY": "test-key",
                "OPENROUTER_API_KEY": "test-key",
                "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1"}
        base.update(self.env)
        patch = mock.patch.dict(os.environ, base)
        patch.start()
        self.addCleanup(patch.stop)

        # Every worker defers into OUR ledger, never the committed one.
        real_defer, real_clear = host_call.defer, host_call.clear
        host_call.defer = lambda job, reason: real_defer(
            job, reason, ledger=self.ledger, envelope=self.envelope)
        host_call.clear = lambda job: real_clear(
            job, ledger=self.ledger, envelope=self.envelope)
        self.addCleanup(lambda: setattr(host_call, "defer", real_defer))
        self.addCleanup(lambda: setattr(host_call, "clear", real_clear))

    def run_against(self, status, body="{}"):
        """Exit code from the worker when the host answers only `status`.

        A worker that raises instead of returning is reported as 1: on a runner
        that is the same non-zero exit, and the assertions below are about the
        outcome the workflow sees, not the mechanism.
        """
        import importlib
        import requests

        # Reloaded so module-level SITE/KEY pick up the patched environment.
        module = importlib.reload(__import__(self.module))

        def send(method, url, data=None, headers=None, timeout=None):
            return status, body

        def respond(url, *a, **kw):
            try:
                payload = json.loads(body)
            except ValueError:
                payload = {}
            return _Response(status, payload, body)

        # `create=True` because sibling test modules install a SimpleNamespace
        # stand-in for `requests` in sys.modules, and under `unittest discover`
        # whichever ran first is the module this one gets.
        with mock.patch.object(http_retry, "_send", send), \
                mock.patch.object(requests, "get", respond, create=True), \
                mock.patch.object(requests, "post", respond, create=True), \
                mock.patch.object(requests, "RequestException", Exception,
                                  create=True), \
                mock.patch.object(http_retry, "requests", requests), \
                mock.patch("time.sleep", lambda _s: None), \
                mock.patch.object(http_retry.time, "sleep", lambda _s: None):
            buf = io.StringIO()
            with mock.patch.object(sys, "stdout", buf):
                try:
                    code = module.main()
                except SystemExit as exc:
                    code = exc.code or 0
                except Exception as exc:       # a worker that raises is red
                    print(f"[raised] {type(exc).__name__}: {exc}")
                    code = 1
            self.output = buf.getvalue()
        return code

    # -- the two halves ----------------------------------------------------

    def test_a_transient_503_defers_and_exits_zero(self):
        code = self.run_against(503, "Briefly unavailable for scheduled maintenance")
        self.assertEqual(
            code, 0,
            f"{self.job}: a 503 from a host that is restarting is not a job "
            f"that failed\n{self.output}")
        pending = deferral_ledger.pending(deferral_ledger.load(self.ledger))
        self.assertEqual(
            [e["job"] for e in pending], [self.job],
            f"{self.job}: a deferral nobody counts is a silently green job"
            f"\n{self.output}")

    def test_a_403_still_exits_non_zero(self):
        code = self.run_against(403, "forbidden")
        self.assertNotEqual(
            code, 0,
            f"{self.job}: a wrong key is a real answer, not an outage"
            f"\n{self.output}")
        self.assertEqual(
            deferral_ledger.pending(deferral_ledger.load(self.ledger)), [],
            f"{self.job}: a refusal is not a deferral\n{self.output}")


class EnrichRoles(_JobCase):
    """The job that actually broke."""
    module, job = "enrich_roles", "enrich-roles"


class EnrichContext(_JobCase):
    module, job = "enrich_context", "enrich-context"


class ReclassifyLegacyAI(_JobCase):
    module, job = "reclassify_legacy_ai", "reclassify-legacy-ai"


class EmployerDomicileBackfill(_JobCase):
    module, job = "employer_domicile_backfill", "employer-domicile-backfill"


class ArchiveBackfill(_JobCase):
    module, job = "archive_backfill", "archive-backfill"


class CanonicalEventMigrate(_JobCase):
    module, job = "canonical_event_migrate", "canonical-event-migrate"


class ReasonBackfill(_JobCase):
    module, job = "reason_backfill", "reason-backfill"


class ClaimsImport(_JobCase):
    module, job = "claims_import", "claims-import"

    def setUp(self):
        super().setUp()
        # FRED is a different upstream with its own fail-soft rule ("an empty
        # pull never overwrites the good cached payload"). This case is about
        # what happens when OUR host will not take the result.
        import sources.claims
        patch = mock.patch.object(
            sources.claims, "build_claims_payload",
            lambda **kw: {"national": {"initial": [{"date": "2026-08-01", "value": 1}]}})
        patch.start()
        self.addCleanup(patch.stop)


class ErmImport(_JobCase):
    """The one data-changing bulk import in the set.

    It defers ONLY because nothing landed: a partly applied import raises, and
    `PartialImportsStayLoud` below is the test that says so.
    """
    module, job = "erm_import", "erm-import"


class SurveyReconcile(_JobCase):
    module, job = "survey_reconcile", "survey-reconcile"
    # A past year uses the reviewed manifest and never touches the live feed,
    # so the only host in play is ours.
    env = {"BENCHMARK_YEAR": "2025",
           "SURVEY_BENCHMARK_JSON": json.dumps({"2025": [{
               "reference_month": "2025-06", "report_month": "2025-07",
               "benchmark_url": "https://example.invalid/report",
               "ai_jobs_month": 100, "ai_jobs_ytd": 1000}]})}


class PartialImportsStayLoud(unittest.TestCase):
    """The fail-loud rule, stated where it is easiest to get wrong.

    `erm_import` writes rows. Deferring is only honest when NOTHING landed. If
    some batches applied and others never reached the host, the import is
    incomplete — which is exactly the state "data-changing jobs fail loudly on
    any failed batch" exists to protect — and waiting does not fix it.
    """

    def test_some_landed_and_some_did_not_is_an_error_not_a_deferral(self):
        import erm_import

        raw = [{"row": n} for n in range(erm_import.BATCH * 2)]
        calls = []

        def post_json(url, payload, **kw):
            calls.append(url)
            if len(calls) == 1:
                return {"inserted": len(payload["entries"])}
            raise host_call.Deferred("HTTP 503 from the host")

        with mock.patch.dict(os.environ, {"WP_SITE_URL": "https://x/blog",
                                          "WP_API_KEY": "k"}), \
                mock.patch.object(erm_import, "publish_source_health",
                                  lambda *a, **kw: http_retry.OK), \
                mock.patch.object(erm_import, "report_source_health",
                                  lambda *a, **kw: True), \
                mock.patch.object(erm_import, "fetch_events", lambda: raw), \
                mock.patch.object(erm_import, "to_entry",
                                  lambda r: {"job_count": 1}), \
                mock.patch.object(erm_import.host_call, "post_json", post_json):
            with self.assertRaises(RuntimeError) as raised:
                erm_import.run()
        self.assertIn("incomplete", str(raised.exception),
                      "a partly applied bulk import must be loud, not deferred")


class OneRetryDefinition(unittest.TestCase):
    """`http_retry` exists because a retry that lived in one file was
    re-derived by the next scan and drifted. Two modules had re-derived it."""

    def test_source_health_uses_the_shared_transient_set(self):
        import source_health
        self.assertIs(source_health.http_retry.TRANSIENT, http_retry.TRANSIENT)

    def test_the_historical_sweep_uses_the_shared_transient_set(self):
        import historical_news_sweep
        self.assertIs(historical_news_sweep.TRANSIENT, http_retry.TRANSIENT,
                      "the sweep's private {500,502,503,504} disagreed with the "
                      "shared set about 408, 429 and the Cloudflare 52x family")

    def test_no_worker_carries_its_own_transient_literal(self):
        railway = Path(__file__).resolve().parents[1]
        forbidden = "{408, 429, 500, 502, 503, 504"
        for path in railway.glob("*.py"):
            if path.name == "http_retry.py":
                continue
            with self.subTest(path.name):
                self.assertNotIn(forbidden, path.read_text(),
                                 f"{path.name} re-derived the transient set; "
                                 "import http_retry.TRANSIENT instead")


class TheWorkflowsRecordWhatWasDeferred(unittest.TestCase):
    """A worker that records a deferral into a ledger the workflow never
    commits is the silently-green job this whole mechanism exists to prevent.
    Each converted job's workflow must carry the commit step, with the SAME
    ledger key the module declares."""

    WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    CONVERTED = {
        "enrich-roles.yml": "enrich-roles",
        "enrich-context.yml": "enrich-context",
        "reclassify-legacy-ai.yml": "reclassify-legacy-ai",
        "claims-import.yml": "claims-import",
        "employer-domicile-backfill.yml": "employer-domicile-backfill",
        "archive-backfill.yml": "archive-backfill",
        "canonical-event-migrate.yml": "canonical-event-migrate",
        "erm-import.yml": "erm-import",
        "survey-reconcile.yml": "survey-reconcile",
        "reason-backfill.yml": "reason-backfill",
    }

    def test_every_converted_workflow_commits_the_ledger(self):
        for name, job in self.CONVERTED.items():
            text = (self.WORKFLOWS / name).read_text()
            with self.subTest(name):
                self.assertIn("commit-deferral-ledger", text,
                              f"{name} defers but never records it")
                self.assertIn(f"job: {job}", text,
                              f"{name} must record under the module's own key")
                self.assertIn("contents: write", text,
                              f"{name} cannot push the ledger without it")

    def test_the_module_and_the_workflow_agree_on_the_key(self):
        modules = {
            "enrich-roles.yml": "enrich_roles",
            "enrich-context.yml": "enrich_context",
            "reclassify-legacy-ai.yml": "reclassify_legacy_ai",
            "claims-import.yml": "claims_import",
            "employer-domicile-backfill.yml": "employer_domicile_backfill",
            "archive-backfill.yml": "archive_backfill",
            "canonical-event-migrate.yml": "canonical_event_migrate",
            "erm-import.yml": "erm_import",
            "survey-reconcile.yml": "survey_reconcile",
            "reason-backfill.yml": "reason_backfill",
        }
        for name, module_name in modules.items():
            module = __import__(module_name)
            with self.subTest(name):
                self.assertEqual(module.JOB, self.CONVERTED[name])


if __name__ == "__main__":
    unittest.main()
