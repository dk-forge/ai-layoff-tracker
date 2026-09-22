"""The sandbox main-green check, ported here 2026-09-22 and running from
this public repo against the private sandbox.

Everything is offline: `api` is a dict-backed fake, no socket is opened and
`gh` is never started.

The cases that are NOT a straight copy of the sandbox's own tests are the
ones about this file living somewhere else now:
  * it must judge the SANDBOX, never the repo it runs in
  * absence of a run is UNKNOWN, never green, because a check that reports
    green about a repo it cannot see is worse than no check
  * the running issue is opened on the SANDBOX
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sandbox_watch import main_green as mg  # noqa: E402

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
SANDBOX = "dk-forge/asktherecruiter-sandbox"
HEAD = "a" * 40


def _run(file, conclusion="success", sha=HEAD, hours_ago=1, run_id=7,
         status="completed", **over):
    at = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = {"id": run_id, "status": status, "conclusion": conclusion,
         "head_sha": sha, "created_at": at, "updated_at": at,
         "html_url": f"https://github.com/{SANDBOX}/actions/runs/{run_id}"}
    r.update(over)
    return r


def _api(runs_by_file, *, head=HEAD, head_age_hours=0.5, issues=None,
         jobs=None, calls=None):
    """A fake `gh api`. Records every path it is asked for."""
    issues = [] if issues is None else issues
    calls = calls if calls is not None else []

    def api(path, *, method="GET", payload=None):
        calls.append((method, path, payload))
        if path.startswith(f"repos/{SANDBOX}/commits/main"):
            when = (NOW - timedelta(hours=head_age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return {"sha": head, "commit": {"committer": {"date": when}}}
        if "/actions/workflows/" in path and "/runs" in path:
            wf = path.split("/actions/workflows/")[1].split("/runs")[0]
            if wf not in runs_by_file:
                raise mg.ReadError(f"no such workflow {wf}")
            return {"workflow_runs": runs_by_file[wf]}
        if "/actions/runs/" in path and path.endswith("/jobs?per_page=100"):
            return {"jobs": jobs or []}
        if path.startswith(f"repos/{SANDBOX}/issues?state=open"):
            return issues
        if path.startswith(f"repos/{SANDBOX}/issues"):
            return {"number": 4242}
        raise AssertionError(f"unexpected path {path}")
    return api, calls


def _all_green():
    return {wf.file: [_run(wf.file)] for wf in mg.WORKFLOWS}


class ItJudgesTheSandboxNotTheRepoItRunsIn(unittest.TestCase):
    def test_the_default_target_is_the_sandbox(self):
        self.assertEqual(mg.DEFAULT_REPO, SANDBOX)

    def test_github_repository_is_never_read(self):
        """THE DEFECT THIS PINS: in the sandbox the target came from
        GITHUB_REPOSITORY, because the check ran inside the repo it judged.
        Here that variable names THIS repo, so reading it would quietly
        judge the layoff tracker and report a wall of UNKNOWN about the
        wrong repository while the run looked fine."""
        src = Path(mg.__file__).read_text(encoding="utf-8")
        code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
        self.assertNotIn("GITHUB_REPOSITORY", code)

    def test_every_call_names_the_sandbox(self):
        api, calls = _api(_all_green())
        mg.check(SANDBOX, api, NOW)
        self.assertTrue(calls)
        for _method, path, _payload in calls:
            self.assertTrue(path.startswith(f"repos/{SANDBOX}/"), path)

    def test_the_env_var_can_override_the_target(self):
        with mock.patch.dict("os.environ", {"SANDBOX_REPO": "o/other"}, clear=False):
            with mock.patch.object(mg, "gh_json") as fake:
                fake.side_effect = mg.ReadError("stop here")
                with redirect_stdout(io.StringIO()):
                    mg.main(["--no-issue"])
        asked = [c.args[0] for c in fake.call_args_list]
        self.assertTrue(asked and all(p.startswith("repos/o/other/") for p in asked))


class ItImportsNothingFromTheSandbox(unittest.TestCase):
    def test_the_module_is_stdlib_only(self):
        src = Path(mg.__file__).read_text(encoding="utf-8")
        for line in src.splitlines():
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                name = s.split()[1].split(".")[0]
                self.assertIn(name, {"__future__", "hashlib", "json", "os",
                                     "subprocess", "sys", "dataclasses",
                                     "datetime", "typing"}, line)


class AbsenceIsNeverGreen(unittest.TestCase):
    def test_no_run_at_all_is_unknown(self):
        wf = mg.WORKFLOWS[0]
        v = mg.judge(wf, {"workflow_runs": []}, HEAD, NOW, NOW)
        self.assertEqual(v.state, mg.UNKNOWN)

    def test_a_read_that_failed_is_unknown_not_pass(self):
        runs = _all_green()
        runs.pop(mg.WORKFLOWS[0].file)          # this one will raise
        api, _ = _api(runs)
        out = mg.check(SANDBOX, api, NOW)
        first = [v for v in out if v.file == mg.WORKFLOWS[0].file][0]
        self.assertEqual(first.state, mg.UNKNOWN)
        self.assertIn("read failed", first.detail)

    def test_an_unreadable_head_makes_every_workflow_unknown(self):
        def api(path, *, method="GET", payload=None):
            raise mg.ReadError("no head")
        out = mg.check(SANDBOX, api, NOW)
        self.assertEqual({v.state for v in out}, {mg.UNKNOWN})
        self.assertEqual(len(out), len(mg.WORKFLOWS))

    def test_only_all_pass_exits_zero(self):
        api, _ = _api(_all_green())
        self.assertEqual(mg.exit_code(mg.check(SANDBOX, api, NOW)), 0)

    def test_one_unknown_exits_three_and_one_fail_exits_one(self):
        good = [mg.Verdict("a.yml", mg.PASS, "")]
        self.assertEqual(mg.exit_code(good + [mg.Verdict("b.yml", mg.UNKNOWN, "")]), 3)
        self.assertEqual(mg.exit_code(good + [mg.Verdict("b.yml", mg.FAIL, "")]), 1)

    def test_never_started_is_a_failure_not_a_pass(self):
        good = [mg.Verdict("a.yml", mg.PASS, "")]
        self.assertEqual(
            mg.exit_code(good + [mg.Verdict("b.yml", mg.NEVER_STARTED, "")]), 1)

    def test_an_empty_verdict_list_is_not_green(self):
        self.assertEqual(mg.exit_code([]), 3)


class ItReadsTheFourthState(unittest.TestCase):
    REFUSED = {"runner_id": 0, "runner_name": "", "conclusion": "failure",
               "steps": []}

    def test_a_refused_run_is_never_started_not_fail(self):
        runs = _all_green()
        wf = mg.WORKFLOWS[0].file
        runs[wf] = [_run(wf, conclusion="failure")]
        api, _ = _api(runs, jobs=[self.REFUSED])
        out = [v for v in mg.check(SANDBOX, api, NOW) if v.file == wf][0]
        self.assertEqual(out.state, mg.NEVER_STARTED)

    def test_a_real_failure_stays_fail(self):
        runs = _all_green()
        wf = mg.WORKFLOWS[0].file
        runs[wf] = [_run(wf, conclusion="failure")]
        ran = {"runner_id": 9, "runner_name": "vps", "conclusion": "failure",
               "steps": [{"name": "Set up job"}]}
        api, _ = _api(runs, jobs=[ran])
        out = [v for v in mg.check(SANDBOX, api, NOW) if v.file == wf][0]
        self.assertEqual(out.state, mg.FAIL)

    def test_a_jobs_read_that_fails_leaves_the_fail_alone(self):
        """The fourth state needs evidence, never absence."""
        wf = mg.WORKFLOWS[0]
        payload = {"workflow_runs": [_run(wf.file, conclusion="failure")]}

        def api(path, *, method="GET", payload_=None, **kw):
            raise mg.ReadError("jobs unreadable")
        v = mg.judge(wf, payload, HEAD, NOW, NOW)
        self.assertEqual(mg.refine(wf, v, payload, SANDBOX, api).state, mg.FAIL)


class TheRunningIssueStaysInTheSandbox(unittest.TestCase):
    def test_it_is_opened_on_the_sandbox(self):
        bad = [mg.Verdict("x.yml", mg.FAIL, "boom")]
        api, calls = _api({})
        said = mg.sync_issue(SANDBOX, bad, api, NOW)
        posts = [c for c in calls if c[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][1], f"repos/{SANDBOX}/issues")
        self.assertIn("opened issue", said)

    def test_the_same_problem_set_does_not_rewrite_it(self):
        bad = [mg.Verdict("x.yml", mg.FAIL, "boom")]
        body = f"{mg.MARKER}\n{mg.SET_PREFIX}{mg.problem_set(bad)} -->"
        api, calls = _api({}, issues=[{"number": 5, "body": body}])
        said = mg.sync_issue(SANDBOX, bad, api, NOW)
        self.assertIn("already describes this set", said)
        self.assertEqual([c for c in calls if c[0] == "PATCH"], [])

    def test_all_pass_closes_it_once(self):
        body = f"{mg.MARKER}\n{mg.SET_PREFIX}deadbeef -->"
        api, calls = _api({}, issues=[{"number": 5, "body": body}])
        said = mg.sync_issue(SANDBOX, [mg.Verdict("x.yml", mg.PASS, "ok")], api, NOW)
        self.assertIn("closed issue #5", said)
        closed = [c for c in calls if c[0] == "PATCH"
                  and (c[2] or {}).get("state") == "closed"]
        self.assertEqual(len(closed), 1)

    def test_nothing_open_and_nothing_wrong_writes_nothing(self):
        api, calls = _api({}, issues=[])
        said = mg.sync_issue(SANDBOX, [mg.Verdict("x.yml", mg.PASS, "ok")], api, NOW)
        self.assertIn("none needed", said)
        self.assertEqual([c for c in calls if c[0] != "GET"], [])


class TheWorkflowWiresItCorrectly(unittest.TestCase):
    WF = (Path(__file__).resolve().parents[2] / ".github" / "workflows"
          / "sandbox-main-green.yml")

    def setUp(self):
        self.text = self.WF.read_text(encoding="utf-8")
        # The header explains WHY it left the VPS, so it names `CI_RUNNER`
        # and `self-hosted` on purpose. The assertions below are about what
        # the workflow DOES, so they read the YAML with comments stripped.
        self.yaml = "\n".join(
            l for l in self.text.splitlines() if not l.strip().startswith("#"))

    def test_it_runs_on_a_free_hosted_runner(self):
        """The whole point: it must not be able to land on the VPS it
        reports about."""
        self.assertIn("runs-on: ubuntu-latest", self.yaml)
        self.assertNotIn("CI_RUNNER", self.yaml)
        self.assertNotIn("self-hosted", self.yaml)

    def test_it_names_the_sandbox_and_the_token_that_can_read_it(self):
        self.assertIn("SANDBOX_REPO: dk-forge/asktherecruiter-sandbox", self.yaml)
        self.assertIn("secrets.MERGE_TRAIN_TOKEN", self.yaml)

    def test_it_asks_for_no_write_on_this_repo(self):
        self.assertIn("contents: read", self.yaml)
        self.assertNotIn("contents: write", self.yaml)

    def test_it_is_scheduled(self):
        self.assertIn("schedule:", self.yaml)
        self.assertIn("cron:", self.yaml)


if __name__ == "__main__":
    unittest.main()
