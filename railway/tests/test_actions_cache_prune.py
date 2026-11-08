"""The daily cache prune must stay scheduled, scoped and age-limited.

The repo's 10 GB Actions cache hit 100% on 2026-11-05. The prune deletes only
caches unused for MAX_AGE_DAYS (default 2 since 2026-11-07, when weekly with 7 days left the cache at 100%; never below 1), with the least
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

    def test_runs_daily(self):
        on = self.wf[True]  # pyyaml reads the bare key 'on' as True
        crons = [s["cron"] for s in on["schedule"]]
        self.assertEqual(len(crons), 1)
        self.assertEqual(crons[0].split()[2:], ["*", "*", "*"])

    def test_least_privilege(self):
        self.assertEqual(self.wf["permissions"], {"actions": "write"})

    def test_age_limited_and_floor(self):
        self.assertIn("MAX_AGE_DAYS: ${{ inputs.max_age_days || '2' }}", self.text)
        self.assertIn("if days < 1:", self.text)
        self.assertIn("if seen < cutoff:", self.text)

    def test_size_cap_when_age_prune_frees_nothing(self):
        # 2026-11-08: three runs deleted 0 caches (all used within 2 days) while
        # the cache stayed at 9.96 of 10 GB. Over the cap, the least recently
        # used caches go until the total is under it.
        self.assertIn("MAX_TOTAL_GB: ${{ inputs.max_total_gb || '7' }}", self.text)
        self.assertIn("key=lambda c: c[\"last_accessed_at\"]", self.text)
        self.assertIn("while total > cap and rest:", self.text)


if __name__ == "__main__":
    unittest.main()
