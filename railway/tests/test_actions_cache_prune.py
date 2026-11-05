"""The weekly cache prune must stay scheduled, scoped and age-limited.

The repo's 10 GB Actions cache hit 100% on 2026-11-05. The prune deletes only
caches unused for MAX_AGE_DAYS (default 7, never below 1), with the least
permission that can delete a cache.
"""
import unittest
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parent.parent.parent / ".github" / "workflows" / "actions-cache-prune.yml"


class ThePruneStaysSafe(unittest.TestCase):
    def setUp(self):
        self.text = WF.read_text()
        self.wf = yaml.safe_load(self.text)

    def test_runs_weekly(self):
        on = self.wf[True]  # pyyaml reads the bare key 'on' as True
        crons = [s["cron"] for s in on["schedule"]]
        self.assertEqual(len(crons), 1)
        self.assertEqual(crons[0].split()[2:], ["*", "*", "0"])

    def test_least_privilege(self):
        self.assertEqual(self.wf["permissions"], {"actions": "write"})

    def test_age_limited_and_floor(self):
        self.assertIn("MAX_AGE_DAYS: ${{ inputs.max_age_days || '7' }}", self.text)
        self.assertIn("if days < 1:", self.text)
        self.assertIn("if seen < cutoff:", self.text)


if __name__ == "__main__":
    unittest.main()
