"""A workflow whose YAML does not parse runs NO JOBS, and says nothing.

GitHub Actions does not fail a broken workflow file. It does not annotate a
commit, it does not open a run, it does not appear in `gh run list`. The
workflow simply stops existing, and every guard, deploy or cron it carried
stops with it while every surface stays green. Commit f014ebe left
`.github/workflows/deploy-plugin.yml` in exactly that state: a long block
scalar in a comment ran on past its indentation, and a `deploy` that nobody
could see was gone. `ftp-target-probe.yml` was broken the same way twice in one
day, both times by mis-indenting an embedded script inside a block scalar, and
both times it was caught only because somebody happened to validate by hand.

The five checks here:

  1. the workflows directory exists and is not empty. A guard that examines
     zero files passes forever and proves nothing (the lesson of
     test_test_groups: an empty group is an ERROR, not a pass);
  2. every file `safe_load`s, and a failure names the file with the parser's
     own line and column;
  3. no stray TOP-LEVEL key. This is the sharper half. A file that fails
     outright is loud; a DEDENTED CONTINUATION LINE that happens to contain a
     colon parses perfectly and quietly becomes a new root key, which Actions
     ignores along with whatever it swallowed;
  4. every file declares a trigger and at least one job;
  5. every step is a mapping carrying `run` or `uses`. A truncated block
     scalar turns a list of steps into a list of strings;
  6. no mapping repeats a key. YAML 1.1 permits it and pyyaml keeps the last
     one silently; GitHub Actions REJECTS the file. This is the one check
     here that is not about a file being malformed - a duplicate key file is
     perfectly well-formed YAML, and checks 2 through 5 all pass it.

A DUPLICATE KEY FAILS DIFFERENTLY FROM AN UNPARSEABLE FILE, and the shape is
worth knowing because it is how this check was earned. Commit 60bda6e added
`OPS_MAIL_FROM` to seven jobs that already carried it a few lines below, under
its own comment. Actions could not build the workflow, so it never read the
`on:` block, so it could not know the file does not listen to pushes: it
opened a run against the push anyway and failed it in under a second. Seven
FAILED runs per push to main, each with zero jobs, no logs, and - the
tell - `workflowName` reported as the file PATH rather than the declared
`name:`, because the name is inside the file it could not parse. A healthy
workflow always reports by its name. Those runs are `push`-triggered red runs,
so ci-alert.yml mails the owner about every one of them.

WHAT THIS CANNOT TELL YOU. pyyaml is not GitHub Actions. A file that parses
here can still be rejected or misbehave in a dozen ways this test cannot see:
an unknown key inside a job, a `runs-on` naming no runner, a malformed
`${{ }}` expression, a cron Actions will not accept, a `uses:` pointing at an
action or a ref that does not exist, a bad `needs:` edge, a matrix that
expands to nothing. A green run here means "this file is YAML shaped like a
workflow", never "this workflow will run".

No network, no keys, no imports beyond pyyaml (pinned in
railway/requirements.lock, which is what every workflow installs).
"""
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs the lock
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

#: The top-level keys GitHub Actions defines for a workflow file. `True` is
#: not a typo: pyyaml is YAML 1.1, so a bare `on:` key is read as the boolean
#: True. Every workflow in this repo therefore has True as its trigger key.
ALLOWED_TOP_LEVEL = frozenset({
    "name", "on", True, "run-name", "permissions", "env", "defaults",
    "concurrency", "jobs",
})


def _files():
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def duplicate_keys(text):
    """Every repeated key in `text`, as (key, 1-based line) pairs.

    pyyaml's own mapping constructor takes the last value and says nothing,
    which is why a duplicate survives `safe_load` and every other check in
    this file. This subclass records the collision instead of hiding it. It
    deliberately does not raise: one file's duplicates should not stop the
    walk over the rest.
    """
    found = []

    class _Loader(yaml.SafeLoader):
        pass

    def _mapping(loader, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                if key in seen:
                    found.append((key, key_node.start_mark.line + 1))
                seen.add(key)
            except TypeError:      # an unhashable key; not our business
                pass
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    _Loader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)
    yaml.load(text, Loader=_Loader)
    return found


class WorkflowFilesAreValidYaml(unittest.TestCase):

    def setUp(self):
        if yaml is None:
            self.skipTest("pyyaml is in requirements.lock; CI asserts this")

    def _parsed(self):
        """Every file that parses, as (path, document).

        Unparseable files are SKIPPED here on purpose. Check 2 owns that
        failure and reports it once, with the parser's line and column. The
        first version of this file re-parsed the same broken file in every
        check, so one mis-indented script produced four failures, three of
        them raw tracebacks. One readable failure beats four noisy ones.
        """
        out = []
        for path in _files():
            try:
                doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue
            out.append((path, doc))
        return out

    def test_there_are_workflow_files_to_check(self):
        self.assertTrue(WORKFLOWS.is_dir(),
                        f"{WORKFLOWS} does not exist, so this whole file has "
                        f"been checking nothing")
        self.assertTrue(_files(),
                        f"no workflow files under {WORKFLOWS}: a guard that "
                        f"examines zero files passes forever and proves "
                        f"nothing")

    def test_every_workflow_file_parses(self):
        broken = []
        for path in _files():
            try:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                mark = getattr(exc, "problem_mark", None)
                where = (f" at line {mark.line + 1}, column {mark.column + 1}"
                         if mark else "")
                problem = getattr(exc, "problem", None) or str(exc)
                broken.append(f"{path.name}{where}: {problem}")
        self.assertEqual(broken, [],
                         "these workflow files do not parse as YAML, so "
                         "GitHub Actions runs NO jobs from them and reports "
                         "nothing anywhere:\n  " + "\n  ".join(broken))

    def test_no_workflow_has_a_stray_top_level_key(self):
        stray = []
        for path, doc in self._parsed():
            if not isinstance(doc, dict):
                stray.append(f"{path.name}: the document is "
                             f"{type(doc).__name__}, not a mapping")
                continue
            for key in doc:
                if key not in ALLOWED_TOP_LEVEL:
                    stray.append(f"{path.name}: {key!r}")
        self.assertEqual(stray, [],
                         "these root keys are not workflow keys, so Actions "
                         "ignores them silently. The usual cause is a "
                         "dedented continuation line containing a colon, "
                         "which parses fine and takes the rest of its block "
                         "with it:\n  " + "\n  ".join(stray))

    def test_every_workflow_declares_a_trigger_and_a_job(self):
        problems = []
        for path, doc in self._parsed():
            if not isinstance(doc, dict):
                continue
            # `on:` is True under YAML 1.1; accept the quoted form too.
            if True not in doc and "on" not in doc:
                problems.append(f"{path.name}: no trigger, so it never runs")
            jobs = doc.get("jobs")
            if not isinstance(jobs, dict) or not jobs:
                problems.append(f"{path.name}: no jobs, so it does nothing")
        self.assertEqual(problems, [], "\n  ".join([""] + problems))

    def test_every_step_is_a_mapping_that_runs_or_uses_something(self):
        problems = []
        for path, doc in self._parsed():
            if not isinstance(doc, dict):
                continue
            jobs = doc.get("jobs")
            if not isinstance(jobs, dict):
                continue
            for job_id, job in jobs.items():
                if not isinstance(job, dict):
                    problems.append(f"{path.name}:{job_id} is not a mapping")
                    continue
                if "uses" in job:
                    continue  # a reusable-workflow call has no steps
                steps = job.get("steps")
                if not isinstance(steps, list) or not steps:
                    problems.append(
                        f"{path.name}:{job_id} declares no steps list")
                    continue
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        problems.append(
                            f"{path.name}:{job_id} step {i} is "
                            f"{type(step).__name__}, not a mapping (a "
                            f"truncated block scalar does this)")
                    elif "run" not in step and "uses" not in step:
                        problems.append(
                            f"{path.name}:{job_id} step {i} has neither run "
                            f"nor uses")
        self.assertEqual(problems, [], "\n  ".join([""] + problems))


class WorkflowFilesRepeatNoKey(unittest.TestCase):
    """Check 6, and a mutation proving the check can actually fail.

    A guard whose clean zero has never caught a known instance is worth
    nothing, so `test_the_detector_sees_a_planted_duplicate` plants the exact
    shape 60bda6e shipped and asserts the detector reports it.
    """

    def setUp(self):
        if yaml is None:
            self.skipTest("pyyaml is in requirements.lock; CI asserts this")

    def test_no_workflow_repeats_a_key_in_one_mapping(self):
        repeated = []
        for path in _files():
            try:
                dupes = duplicate_keys(path.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue        # check 2 owns unparseable files
            for key, line in dupes:
                repeated.append(f"{path.name}:{line}: {key!r}")
        self.assertEqual(
            repeated, [],
            "these mappings set the same key twice. pyyaml keeps the last "
            "one and says nothing, but GitHub Actions REJECTS the file: it "
            "opens a run against whatever event triggered it, fails it in a "
            "second with zero jobs and no logs, and reports the run under "
            "the file's PATH because the `name:` is inside the file it "
            "could not read. On main those are push-triggered red runs, so "
            "the owner is emailed for each one:\n  "
            + "\n  ".join(repeated))

    def test_the_detector_sees_a_planted_duplicate(self):
        planted = (
            "name: Planted\n"
            "on:\n"
            "  schedule:\n"
            "    - cron: '0 13 1 * *'\n"
            "jobs:\n"
            "  go:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - env:\n"
            "          OPS_MAIL_TO: to\n"
            "          OPS_MAIL_FROM: from\n"
            "          # a comment, exactly as in 60bda6e\n"
            "          OPS_MAIL_FROM: from\n"
            "        run: true\n"
        )
        # It is valid YAML and shaped like a workflow, which is why every
        # other check in this file passes it.
        self.assertIsInstance(yaml.safe_load(planted), dict)
        self.assertEqual(duplicate_keys(planted), [("OPS_MAIL_FROM", 13)])


if __name__ == "__main__":
    unittest.main()
