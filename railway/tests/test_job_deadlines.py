"""A scheduled job must stop ITSELF, before the runner cancels it.

Reason-tag backfill run 31462430383 (2026-08-11) was killed by
timeout-minutes: 45 after five clean runs. A cancelled run skips everything
after the point of death, so the day's tagging was lost outright -- and the
run before it had been a perfectly ordinary 5.5 minutes. The job had not
"grown"; it had an unbounded phase.

The rule these tests pin, for reason_backfill.py and ai_evidence_sweep.py:

  * every phase that can block is under ONE run-wide wall clock, measured from
    process start (not from the start of the last phase),
  * the phases that DECIDE work hold back a reserve so the phase that WRITES
    work always gets to run,
  * decided work is flushed as early as it is decided, not banked to the end,
  * and the workflow's timeout-minutes is derived from that deadline rather
    than being an independent guess with a thousand seconds of slop in it.
"""
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

import reason_backfill

ROOT = Path(__file__).resolve().parents[2]
RB_YML = (ROOT / ".github/workflows/reason-backfill.yml").read_text()
SWEEP_YML = (ROOT / ".github/workflows/ai-evidence-sweep.yml").read_text()

# The per-operation timeouts the ceiling arithmetic is built on. If one of
# these moves, the derived ceiling below stops covering the worst in-flight
# call and the ceiling test says so.
QUERY_PAGE_WORST_SECONDS = 3 * 60 + 5 + 10   # 3 attempts x 60s + 5s + 10s backoff
SOURCE_FETCH_WORST_SECONDS = 3 * 40 + 5 + 10  # get_with_retry(attempts=3, timeout=40)


def strip_comments(text):
    """Match against CODE, not against the comment that describes it."""
    out = []
    for line in text.splitlines():
        line = re.sub(r'(^|\s)#.*$', '', line)
        out.append(line)
    body = "\n".join(out)
    return re.sub(r'(?s)""".*?"""', "", body)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")


class ScanIsUnderTheRunDeadline(unittest.TestCase):
    """fetch_candidates was the unbounded phase: 107 pages, no clock."""

    def setUp(self):
        self.pages = []
        row = {"id": 1, "source_type": "news", "reason_tags": [],
               "excerpt": "x" * 80}

        def fake_get(url, params=None, headers=None, timeout=None):
            self.pages.append(params["page"])
            # Always claim more data, so only a deadline can end this scan.
            return FakeResponse({"data": [dict(row, id=params["page"])] * reason_backfill.PAGE_SIZE,
                                 "total": 10 ** 6})

        self._real_requests = reason_backfill.requests
        reason_backfill.requests = SimpleNamespace(get=fake_get)

    def tearDown(self):
        reason_backfill.requests = self._real_requests

    def test_scan_stops_when_the_run_deadline_passes(self):
        # Three pages of budget, then the clock is spent.
        calls = {"n": 0}

        def stop():
            calls["n"] += 1
            return calls["n"] > 3

        candidates, pages, truncated = reason_backfill.fetch_candidates(stop=stop)
        self.assertTrue(truncated,
                        "a scan cut short by the deadline must report itself as short")
        self.assertLess(len(self.pages), reason_backfill.MAX_PAGES,
                        "the scan ignored the deadline and paged to MAX_PAGES")
        self.assertEqual(self.pages, [1, 2, 3, 4])
        self.assertTrue(candidates, "the pages already scanned must still be usable")

    def test_a_complete_scan_is_not_reported_as_truncated(self):
        # An honest short-run signal is only useful if a full run never sets it.
        def fake_get(url, params=None, headers=None, timeout=None):
            return FakeResponse({"data": [], "total": 0})

        reason_backfill.requests = SimpleNamespace(get=fake_get)
        candidates, pages, truncated = reason_backfill.fetch_candidates(stop=lambda: False)
        self.assertFalse(truncated)
        self.assertEqual(candidates, [])


class WritesSurviveTheDeadline(unittest.TestCase):
    """Decided work is flushed as it is decided, and never banked to the end."""

    def setUp(self):
        self.posted = []

        def fake_post(url, json=None, headers=None, timeout=None):
            ids = [e["id"] for e in json["edits"]]
            self.posted.append(ids)
            return FakeResponse({"edited": ids, "not_found": [], "rejected": []})

        self._real_requests = reason_backfill.requests
        reason_backfill.requests = SimpleNamespace(post=fake_post)

    def tearDown(self):
        reason_backfill.requests = self._real_requests

    def test_writes_stop_starting_new_chunks_past_the_deadline(self):
        items = [{"id": i, "reason_tags": ["restructuring"]}
                 for i in range(reason_backfill.EDIT_BATCH * 3)]
        calls = {"n": 0}

        def stop():
            calls["n"] += 1
            return calls["n"] > 1  # one chunk of budget

        edited, not_found, unwritten = reason_backfill.post_edits(items, stop=stop)
        self.assertEqual(len(self.posted), 1,
                         "post_edits kept POSTing after its deadline")
        self.assertEqual(len(edited), reason_backfill.EDIT_BATCH)
        self.assertEqual(unwritten, reason_backfill.EDIT_BATCH * 2,
                         "rows left unsent must be counted, not silently dropped")

    def test_deterministic_edits_are_written_before_the_model_loop(self):
        # The 400 ERM rows are the bulk of a run's writes and cost no model
        # call. Banking them until after the expensive phase is exactly how a
        # cancelled run loses a whole day of tagging.
        erm = {"id": 7, "source_type": "erm", "reason_tags": [],
               "excerpt": ("Internal restructuring at Acme GmbH (Germany): 1,230 announced "
                           "job losses. Recorded by the European Restructuring Monitor "
                           "(Eurofound), factsheet 78221.")}
        seen_before_model = []

        def fake_classify(text):
            seen_before_model.append(list(self.posted))
            raise RuntimeError("the expensive phase blew up")

        patches = {
            "fetch_candidates": lambda stop=None: ([erm], 1, False),
            "classify_reason_tags": fake_classify,
            "spend": SimpleNamespace(record_job_run=lambda **kw: None),
            "report_source_health": lambda *a, **k: True,
            "DRY_RUN": False,
            "SITE": "https://example.invalid/blog",
            "KEY": "k",
        }
        # A model row so the loop is actually entered.
        news = {"id": 9, "source_type": "news", "reason_tags": [], "excerpt": "y" * 80}
        patches["fetch_candidates"] = lambda stop=None: ([erm, news], 1, False)
        originals = {k: getattr(reason_backfill, k) for k in patches}
        for k, v in patches.items():
            setattr(reason_backfill, k, v)
        try:
            with self.assertRaises(RuntimeError):
                reason_backfill.run()
        finally:
            for k, v in originals.items():
                setattr(reason_backfill, k, v)

        self.assertTrue(seen_before_model,
                        "the model loop never ran, so this proves nothing")
        self.assertEqual(seen_before_model[0], [[7]],
                         "the ERM edits were still unwritten when the model loop "
                         "started; a run killed there loses all of them")


class OneClockNotThree(unittest.TestCase):
    def test_the_deadline_is_measured_from_process_start(self):
        code = strip_comments(Path(reason_backfill.__file__).read_text())
        self.assertIn("STARTED_AT = time.monotonic()", code,
                      "the run-wide clock must start at import, not inside a phase")
        self.assertRegex(code, r"def past_deadline\(reserve=0\)")
        # The model loop must not restart the clock for itself.
        self.assertNotIn("started_at = time.monotonic()", code,
                         "the model loop still owns a private clock, so the scan "
                         "and the writes are unbounded again")

    def test_every_blocking_phase_consults_it(self):
        code = strip_comments(Path(reason_backfill.__file__).read_text())
        for phase in ("def fetch_candidates(stop=None)", "def post_edits(items, stop=None)"):
            self.assertIn(phase, code, f"{phase} does not accept the run clock")
        self.assertIn("work_stop = lambda: past_deadline(WRITE_RESERVE_SECONDS)", code)
        self.assertIn("write_stop = lambda: past_deadline()", code)

    def test_the_work_phases_hold_back_a_write_reserve(self):
        self.assertGreater(reason_backfill.WRITE_RESERVE_SECONDS, 0)
        self.assertLess(reason_backfill.WRITE_RESERVE_SECONDS,
                        reason_backfill.DEADLINE_SECONDS,
                        "a reserve at or above the whole budget leaves no time to "
                        "decide anything to write")


class CeilingsAreDerivedFromTheScriptDeadline(unittest.TestCase):
    """A ceiling nobody derived is the bug: 45 minutes was a guess."""

    def _ceiling(self, yml):
        m = re.search(r"^\s*timeout-minutes:\s*(\d+)\s*$", yml, re.M)
        self.assertIsNotNone(m, "workflow lost its timeout-minutes")
        return int(m.group(1))

    def _env_seconds(self, yml, name):
        m = re.search(name + r":\s*'(\d+)'", yml)
        self.assertIsNotNone(m, f"{name} is not set in the workflow")
        return int(m.group(1))

    def test_reason_backfill_ceiling_covers_the_deadline_and_nothing_more(self):
        ceiling = self._ceiling(RB_YML) * 60
        deadline = self._env_seconds(RB_YML, "REASON_BACKFILL_DEADLINE_SECONDS")
        floor = deadline + QUERY_PAGE_WORST_SECONDS
        self.assertGreater(ceiling, floor,
                           "the runner would cancel a run that stopped itself on time")
        # 8 minutes of slop over the derived floor means the number was picked,
        # not derived -- which is how a job silently outgrows its ceiling.
        self.assertLess(ceiling - floor, 8 * 60,
                        f"timeout-minutes is {ceiling / 60:g} but the script's own "
                        f"hard stop is {floor / 60:.1f} min; derive it, don't guess it")

    def test_ai_evidence_sweep_ceiling_covers_the_deadline_and_nothing_more(self):
        ceiling = self._ceiling(SWEEP_YML) * 60
        deadline = self._env_seconds(SWEEP_YML, "AI_SWEEP_DEADLINE_SECONDS")
        floor = deadline + SOURCE_FETCH_WORST_SECONDS
        self.assertGreater(ceiling, floor,
                           "the sweep can stop itself later than the runner allows")
        self.assertLess(ceiling - floor, 8 * 60,
                        f"timeout-minutes is {ceiling / 60:g} but the script's own "
                        f"hard stop is {floor / 60:.1f} min; derive it, don't guess it")

    def test_the_script_default_matches_what_the_workflow_sets(self):
        # Two numbers that must agree, so a dispatch without the env var
        # behaves like the schedule does.
        self.assertEqual(reason_backfill.DEADLINE_SECONDS,
                         self._env_seconds(RB_YML, "REASON_BACKFILL_DEADLINE_SECONDS"))
        self.assertEqual(reason_backfill.WRITE_RESERVE_SECONDS,
                         self._env_seconds(RB_YML, "REASON_BACKFILL_WRITE_RESERVE_SECONDS"))


class SweepOwnsItsClock(unittest.TestCase):
    def test_the_sweep_checks_a_wall_clock_in_both_unbounded_loops(self):
        code = strip_comments((ROOT / "railway/ai_evidence_sweep.py").read_text())
        self.assertIn("STARTED_AT = time.monotonic()", code)
        self.assertIn("def past_deadline():", code)
        # Once for the per-event loop, once for the per-text loop inside it --
        # the texts loop is the one the press search made unbounded.
        self.assertGreaterEqual(code.count("if past_deadline():"), 2,
                                "the sweep bounds its event loop but not the "
                                "per-article model calls inside each event")

    def test_the_sweep_deadline_is_above_its_measured_max(self):
        # 888s was the slowest healthy script run (2026-08-07). A deadline at
        # or below it would truncate work that finishes fine today.
        m = re.search(r"AI_SWEEP_DEADLINE_SECONDS:\s*'(\d+)'", SWEEP_YML)
        self.assertIsNotNone(m)
        self.assertGreater(int(m.group(1)), 888)


if __name__ == "__main__":
    unittest.main()
