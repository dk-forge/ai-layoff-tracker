"""A red run that scrolled out of the query window must not read as green.

MEASURED, 2026-08-14. `[4] RECENT CI` asked `gh run list -L 80 --branch main`
and called a workflow green when its newest FINISHED run was green. That is
sound only while one page reaches back far enough to contain every workflow's
newest run. Two merges in one afternoon generated enough runs that the page
began at 17:10Z; the 15:42Z "Data quality report (anomaly flags)" failure fell
off the end, and this section printed "No workflow is currently failing on
main" while it was failing. At -L 300 the same page still spanned only 12
hours, so raising the number alone does not fix it.

A red run reaching GitHub Actions and stopping there is the exact silence this
section was written to break, so the window is now part of the answer: a full
page over less than a day is not evidence of green, and the code asks the
question a different way instead of guessing.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ops_status


def _run(name, conclusion, created, status="completed"):
    return {"name": name, "conclusion": conclusion, "status": status,
            "url": "https://github.com/dk-forge/ai-layoff-tracker/actions/runs/1",
            "createdAt": created}


class ATruncatedWindowIsNotAPass(unittest.TestCase):
    def _gh_stub(self, page, failures=None, per_workflow=None):
        """Stands in for _gh, routing by which query is being made."""
        import json as _json

        def gh(args, timeout=None):
            if "--status" in args:
                return True, _json.dumps(failures or []), ""
            if "--workflow" in args:
                name = args[args.index("--workflow") + 1]
                return True, _json.dumps((per_workflow or {}).get(name, [])), ""
            return True, _json.dumps(page), ""
        return gh

    def test_a_full_page_spanning_hours_falls_back_and_finds_the_red_run(self):
        # 300 runs, all inside one afternoon: the page is full and short, which
        # is the 2026-08-14 shape exactly.
        page = [_run(f"Filler {i}", "success", "2026-08-14T17:%02d:00Z" % (i % 60))
                for i in range(300)]
        red = _run("Data quality report (anomaly flags)", "failure",
                   "2026-08-14T15:42:00Z")
        with mock.patch.object(ops_status, "_gh", self._gh_stub(
                page,
                failures=[{"name": "Data quality report (anomaly flags)"}],
                per_workflow={"Data quality report (anomaly flags)": [red]})):
            failures, why = ops_status._report_ci()
        self.assertEqual(why, "", "the fallback reported UNKNOWN instead of answering")
        self.assertTrue(any("Data quality report" in f[0] for f in failures),
                        "the red run that scrolled out of the page was not "
                        "recovered; this is the false green of 2026-08-14")

    def test_a_full_short_page_never_returns_an_empty_green_silently(self):
        # Same truncated page, but every follow-up query fails. The only honest
        # answer is UNKNOWN with a reason -- never an empty failure list, which
        # the caller renders as "No workflow is currently failing on main".
        page = [_run(f"Filler {i}", "success", "2026-08-14T17:%02d:00Z" % (i % 60))
                for i in range(300)]

        def gh(args, timeout=None):
            if "--status" in args:
                return False, "", "gh exploded"
            return True, __import__("json").dumps(page), ""

        with mock.patch.object(ops_status, "_gh", gh):
            failures, why = ops_status._report_ci()
        self.assertEqual(failures, [])
        self.assertTrue(why, "an unreadable CI state returned a clean bill of health")
        self.assertIn("Not a pass", why)

    def test_a_page_spanning_more_than_a_day_is_used_as_is(self):
        page = [_run("Tests", "success", "2026-08-14T17:00:00Z"),
                _run("Data quality report (anomaly flags)", "failure",
                     "2026-08-13T02:00:00Z")]
        with mock.patch.object(ops_status, "_gh", self._gh_stub(page)):
            failures, why = ops_status._report_ci()
        self.assertEqual(why, "")
        self.assertTrue(any("Data quality report" in f[0] for f in failures))

    def test_an_in_progress_run_does_not_hide_the_finished_red_one(self):
        # Pre-existing property, pinned here because the fallback path builds
        # its own `runs` list and must not lose it.
        page = [_run("Tests", None, "2026-08-14T18:00:00Z", status="in_progress"),
                _run("Tests", "failure", "2026-08-13T02:00:00Z")]
        with mock.patch.object(ops_status, "_gh", self._gh_stub(page)):
            failures, why = ops_status._report_ci()
        self.assertEqual(why, "")
        self.assertTrue(any(f[0] == "Tests" for f in failures))


if __name__ == "__main__":
    unittest.main()
