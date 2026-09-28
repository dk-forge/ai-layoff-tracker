"""The daily ingest runs in exactly one place.

2026-09-28: the ingest moved to the VPS (ingest-cron-vps.yml). Railway keeps the
cron schedule (the rotation and the public "next update" read it) but must not
also ingest, or the same candidates are paid for twice. The VPS job must carry the
one Railway setting that differs from the code default (GDELT_PREFER_BQ=1).
"""
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class IngestRunsOnce(unittest.TestCase):
    def test_railway_container_does_not_ingest(self):
        deploy = tomllib.loads((ROOT / "railway" / "railway.toml").read_text())["deploy"]
        self.assertNotIn("cron.py", deploy["startCommand"])
        self.assertTrue(deploy["cronSchedule"])

    def test_vps_job_runs_cron_with_railway_settings(self):
        wf = (ROOT / ".github" / "workflows" / "ingest-cron-vps.yml").read_text()
        self.assertIn("run: python cron.py", wf)
        self.assertIn("GDELT_PREFER_BQ: '1'", wf)


if __name__ == "__main__":
    unittest.main()
