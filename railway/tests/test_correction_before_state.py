"""A signed correction must leave its before-state as evidence.

THE CASE, 2026-11-09/10. Five trashes and one KLM country edit moved the US
and non-US headline slices, and `us_all_time` could not be closed because the
runs uploaded no artifact and their log line `before id=... jobs ...` never
printed the row's country. The before-state now carries the country and is
written to BEFORE_STATE_PATH as JSON, which apply-correction.yml and
dedupe-llm.yml upload as an artifact.
"""
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.dirname(HERE)
ROOT = os.path.dirname(RAILWAY)
sys.path.insert(0, RAILWAY)

import apply_correction  # noqa: E402


class BeforeStateFile(unittest.TestCase):
    def test_writes_country_and_jobs_per_row(self):
        before = {183020: {"company_name": "Microsoft", "job_count": "60000",
                           "layoff_date": "2026-11-03", "country": "United States"}}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "before.json")
            apply_correction.write_before_state(path, "trash", [183020, 1], before)
            data = json.load(open(path))
        self.assertEqual(data["action"], "trash")
        row = data["rows"][0]
        self.assertEqual((row["id"], row["country"], row["job_count"]),
                         (183020, "United States", "60000"))
        self.assertIsNone(data["rows"][1]["country"])
        self.assertFalse(data["rows"][1]["visible"])

    def test_no_path_writes_nothing(self):
        apply_correction.write_before_state("", "trash", [1], {})

    def test_before_line_prints_country(self):
        src = open(os.path.join(RAILWAY, "apply_correction.py")).read()
        line = re.search(r'print\(f"  before  id=\{i\}.*?\n.*?\n', src).group(0)
        self.assertIn("country", line)


class WorkflowsUploadIt(unittest.TestCase):
    def test_both_workflows_upload_before_state(self):
        for wf in ("apply-correction.yml", "dedupe-llm.yml"):
            text = open(os.path.join(ROOT, ".github", "workflows", wf)).read()
            self.assertIn("actions/upload-artifact@", text, wf)
            self.assertIn("BEFORE_STATE_PATH", text, wf)
            self.assertIn("if: ${{ always() }}", text, wf)


if __name__ == "__main__":
    unittest.main()
