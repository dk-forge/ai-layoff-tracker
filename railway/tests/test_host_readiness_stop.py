"""When the publish host is down, the cron stops BEFORE its first paid call.

Shape of the 2026-09-12 scheduled run: GDELT discovery was clean, then the
WordPress path returned 504 on every publish. The item-level seen-URL
pre-check failed open, as designed, and the run went on to spend $0.1598 over
1,544 model calls to extract 1,101 candidates it could not post. The repair
(PR #338) adds a strict run-level readiness probe between free discovery and
the first gate or extraction call.

This file pins the SHAPE of that stop with the probe stubbed as "host
unavailable", without any network:

  * the run exits non-zero, with a message naming the deferral;
  * `spend.metered_call` is never entered, so no paid request can have been
    built (the iron rule makes that the single door for paid work);
  * neither the gate nor the extractor nor the poster is called;
  * the item-level seen-URL filter is never consulted, so no URL is marked and
    the candidates are exactly as pulled (recoverable by the next window);
  * a healthy probe changes nothing about the existing pipeline.

Red on a tree without the probe: `cron.publishing_host_ready` does not exist,
so the harness cannot stub it. Green on top of PR #338.
"""
import contextlib
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cron  # noqa: E402
import extractor  # noqa: E402
import spend  # noqa: E402


class _Tripwire(BaseException):
    """Escapes every `except Exception` in cron.run(), so a stub that was
    forgotten fails the test instead of running for real (see
    test_cost_funnel.CronWiringTests for the full reasoning)."""


def _trip(reason):
    def _raise(*a, **k):
        raise _Tripwire(reason)
    return _raise


class HostReadinessStopTests(unittest.TestCase):
    def setUp(self):
        spend.reset_run_meter()
        os.environ["ALT_PAID_READS"] = "on"

    def tearDown(self):
        spend.reset_run_meter()

    def _run(self, host_ready):
        entries = [
            {"raw_text": "Acme Corp to lay off 500 workers",
             "source_url": "https://x.test/1", "source_type": "news",
             "source_name": "Example Wire"},
            {"raw_text": "Beta Ltd cuts 200 roles",
             "source_url": "https://x.test/2", "source_type": "news",
             "source_name": "Example Wire"},
        ]
        pulled = [dict(e) for e in entries]
        posted = []
        stubs = [
            patch("time.sleep", _trip("cron.run() slept inside this harness")),
            patch("socket.getaddrinfo", _trip("cron.run() resolved a host")),
            patch.object(spend, "metered_call",
                         _trip("a paid call was attempted while the host was down")),
            patch.object(cron, "GATE_MODE", "live"),
            patch.object(cron, "_mark_phase"),
            patch.object(cron, "_spend_preflight"),
            patch.object(cron, "report_source_health"),
            patch.object(cron, "_post_spend_record"),
            patch.object(cron, "pull_edgar_filings", return_value=[]),
            patch.object(cron, "pull_google_news", return_value=pulled),
            patch.object(cron, "_pull_local_news_rows", return_value=[]),
            patch.object(cron, "_pull_regional_feeds_rows", return_value=[]),
            patch.object(cron, "_pull_national_feeds_rows", return_value=[]),
            patch.object(cron, "pull_press_releases", return_value=[]),
            patch.object(cron, "pull_mn_warn_letters", return_value=[]),
            patch.object(cron, "reviewed_feed_count", return_value=1),
            patch.object(cron, "pull_gdelt_between", return_value=[]),
        ]
        with contextlib.ExitStack() as stack:
            for stub in stubs:
                stack.enter_context(stub)
            # The probe is the subject. On a tree without it this line raises
            # AttributeError, which is the red this file expects before #338.
            probe = stack.enter_context(patch.object(
                cron, "publishing_host_ready", return_value=host_ready))
            seen_filter = stack.enter_context(patch.object(
                cron, "filter_already_seen", side_effect=lambda e: e))
            gate = stack.enter_context(patch.object(
                extractor, "gate_verdict", return_value=extractor.GATE_YES))
            extract = stack.enter_context(patch.object(
                cron, "extract_layoff_data",
                return_value={"company_name": "Acme", "job_count": 500}))
            stack.enter_context(patch.object(
                cron, "post_to_wordpress",
                side_effect=lambda x: posted.append(x) or "posted"))
            try:
                cron.run()
                exit_code = 0
            except SystemExit as stopped:
                exit_code = stopped.code
        return {"exit": exit_code, "probe": probe, "seen_filter": seen_filter,
                "gate": gate, "extract": extract, "posted": posted,
                "entries": entries, "pulled": pulled}

    def test_host_down_stops_loudly_before_the_first_paid_call(self):
        r = self._run(host_ready=False)
        self.assertEqual(r["probe"].call_count, 1, "the probe ran exactly once")
        self.assertNotEqual(r["exit"], 0, "a host outage is a loud stop, not exit 0")
        self.assertIn("before paid extraction", str(r["exit"]))
        self.assertEqual(r["gate"].call_count, 0, "the gate is a paid call")
        self.assertEqual(r["extract"].call_count, 0, "the extractor is a paid call")
        self.assertEqual(r["posted"], [], "nothing was posted")
        self.assertEqual(spend.run_cost_usd(), 0.0, "the run meter saw no spend")

    def test_host_down_leaves_candidates_unmarked_and_recoverable(self):
        r = self._run(host_ready=False)
        self.assertEqual(r["seen_filter"].call_count, 0,
                         "the seen-URL filter was never consulted, so no URL was marked")
        # cron stamps each pulled dict with its in-process `_collector` tag
        # (the spend meter books calls under it); that is not a mark on the
        # host. Everything else is exactly what discovery returned.
        stripped = [{k: v for k, v in e.items() if k != "_collector"}
                    for e in r["pulled"]]
        self.assertEqual(stripped, r["entries"],
                         "the pulled candidates are exactly what discovery returned")

    def test_host_up_leaves_the_pipeline_untouched(self):
        r = self._run(host_ready=True)
        self.assertEqual(r["exit"], 0)
        self.assertEqual(r["seen_filter"].call_count, 1)
        self.assertEqual(r["gate"].call_count, 2)
        self.assertEqual(r["extract"].call_count, 2)
        self.assertEqual(len(r["posted"]), 2)


if __name__ == "__main__":
    unittest.main()
