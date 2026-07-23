"""Bounded legacy-AI reassessment must not be killed by its scheduler."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKER = (ROOT / "railway/reclassify_legacy_ai.py").read_text()
WORKFLOW = (ROOT / ".github/workflows/reclassify-legacy-ai.yml").read_text()


class ReclassifyWorkerGuards(unittest.TestCase):
    def test_scheduled_work_has_a_safe_batch_and_deadline(self):
        self.assertIn("RECLASSIFY_BATCH: ${{ github.event.inputs.batch || '5' }}", WORKFLOW)
        self.assertIn("RECLASSIFY_DEADLINE_SECONDS: '900'", WORKFLOW)
        self.assertIn("OPENROUTER_TIMEOUT_SECONDS: '35'", WORKFLOW)

    def test_worker_stops_between_rows_before_actions_limit(self):
        self.assertIn("RECLASSIFY_DEADLINE_SECONDS", WORKER)
        self.assertIn("time.monotonic() - started_at >= DEADLINE_SECONDS", WORKER)
        self.assertIn("stopping safely after", WORKER)

    def test_loud_fail_alarm_excludes_permanently_blocked_sources(self):
        """The worker must still fail LOUDLY on a real breakage, but a publisher
        bot-wall (401/403/404/410) or an empty-but-200 page is a permanent
        property of that URL, not an outage - those rows are excluded from the
        failure ratio, and the alarm needs a meaningful sample so a 1-row batch
        cannot page the owner (the false-alarm emails of 2026-07-22/23)."""
        self.assertIn("PERMANENT_HTTP = {401, 403, 404, 410}", WORKER)
        self.assertIn("MIN_ATTEMPTED_FOR_ALARM", WORKER)
        self.assertIn("attempted = checked - blocked - empty", WORKER)
        self.assertIn("return 1 if (not updates and attempted >= MIN_ATTEMPTED_FOR_ALARM", WORKER)


if __name__ == "__main__":
    unittest.main()
