"""Save-Page-Now leaves from a hosted runner; the keyed VPS records the result.

Three promises: the capture budget and pacing are unchanged by the move, the
hosted stage cannot make the VPS record anything the VPS did not plan or any
link that is not a Wayback permalink, and a capture stage that never ran costs
a day of captures and nothing else. Offline: every request is a stub.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import archive_backfill as ab  # noqa: E402
import archive_relay as ar  # noqa: E402

GOOD = "https://web.archive.org/web/20260921000000/https://example.com/a"


class Tmp(unittest.TestCase):
    def path(self, name):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return os.path.join(d, name)


class PlanStage(Tmp):
    def test_handoff_plans_the_same_budget_and_captures_nothing_here(self):
        plan = self.path("plan.json")
        urls = [f"https://example.com/{i}" for i in range(5)]
        posted = []
        with mock.patch.object(ab, "HANDOFF_FILE", plan), \
             mock.patch.object(ab, "SPN_MAX", 3), mock.patch.object(ab, "DRY_RUN", False), \
             mock.patch.object(ab, "fetch_candidates", side_effect=[(urls, {}), ([], {})]), \
             mock.patch.object(ab, "check_availability", return_value=None), \
             mock.patch.object(ab, "save_page_now",
                               side_effect=AssertionError("captured on the VPS")), \
             mock.patch.object(ab, "post_records", side_effect=lambda r: posted.extend(r)), \
             mock.patch.object(ab, "report_source_health",
                               side_effect=AssertionError("closed a run that is not over")), \
             mock.patch.object(ab.requests, "Session"):
            ab.run()
        self.assertEqual(ar.read_plan(plan), urls[:3])
        # Over-budget misses are recorded pending as always; planned ones are not yet.
        self.assertEqual([r["url"] for r in posted], urls[3:])


class CaptureStage(Tmp):
    def test_budget_gap_and_backoff_are_the_backfills_own(self):
        plan, out = self.path("p.json"), self.path("r.json")
        ar.write_plan(plan, [f"https://example.com/{i}" for i in range(4)])
        answers = iter([GOOD, ab.RATE_LIMITED, None])
        sleeps = []
        with mock.patch.object(ab, "SPN_MAX", 3), mock.patch.object(ab, "SPN_GAP_SECONDS", 6):
            ar.capture(plan, out, save=lambda u, s: next(answers), sleep=sleeps.append)
        rows = json.load(open(out))["results"]
        self.assertEqual(len(rows), 3)                  # SPN_MAX, not the plan's 4
        self.assertEqual(sleeps, [6, 18, 6])
        self.assertEqual([r["status"] for r in rows], ["archived", "pending", "pending"])


class PostStage(Tmp):
    def test_only_planned_urls_and_only_wayback_permalinks_are_recorded(self):
        planned = ["https://example.com/a", "https://example.com/b", "https://example.com/c"]
        doc = {"results": [
            {"url": planned[0], "archived_url": GOOD, "status": "archived"},
            {"url": planned[1], "archived_url": "https://evil.example/x", "status": "archived"},
            {"url": "https://not-planned.example/", "archived_url": GOOD, "status": "archived"},
        ]}
        records, captured, throttled, unreported = ar.settle(planned, doc)
        self.assertEqual([r["url"] for r in records], planned)
        self.assertEqual([r["status"] for r in records], ["archived", "pending", "pending"])
        self.assertEqual((captured, unreported), (1, 1))

    def test_a_capture_job_that_never_ran_leaves_everything_pending_and_degraded(self):
        plan = self.path("p.json")
        ar.write_plan(plan, ["https://example.com/a"])
        posted, notes = [], []
        with mock.patch.object(ab, "post_records", side_effect=lambda r: posted.extend(r)), \
             mock.patch("source_health.report_source_health",
                        side_effect=lambda *a: notes.append(a) or True):
            self.assertEqual(ar.post(plan, self.path("missing.json")), 0)
        self.assertEqual(posted, [{"url": "https://example.com/a", "archived_url": "",
                                   "status": "pending"}])
        self.assertEqual(notes[0][1], "degraded")

    def test_all_throttled_is_degraded_and_a_capture_is_ok(self):
        for rows, want in (([{"url": "u", "status": "pending", "archived_url": "",
                              "throttled": True}], "degraded"),
                           ([{"url": "u", "status": "archived", "archived_url": GOOD,
                              "throttled": False}], "ok")):
            plan, res = self.path("p.json"), self.path("r.json")
            ar.write_plan(plan, ["u"])
            json.dump({"results": rows}, open(res, "w"))
            notes = []
            with mock.patch.object(ab, "post_records"), \
                 mock.patch("source_health.report_source_health",
                            side_effect=lambda *a: notes.append(a) or True):
                ar.post(plan, res)
            self.assertEqual(notes[0][1], want)


class TheHostedJobsHoldNoSecret(unittest.TestCase):
    def test_no_secret_reaches_a_hosted_relay_job(self):
        import re
        root = Path(__file__).resolve().parents[2] / ".github" / "workflows"
        for name, job in (("archive-backfill.yml", "capture"), ("warn-import.yml", "scrape")):
            text = (root / name).read_text()
            block = re.search(rf"\n  {job}:\n(.*?)(?=\n  [a-z_]+:\n|\Z)", text, re.S).group(1)
            self.assertIn("ubuntu-latest", block, name)
            self.assertNotIn("secrets.", block, f"{name}:{job} must hold no secret")
            self.assertNotIn("asktherecruiter.com", block.replace(
                "asktherecruiter.com.", ""), f"{name}:{job} must not call the host")


if __name__ == "__main__":
    unittest.main()
