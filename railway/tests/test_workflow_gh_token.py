"""A step that runs `gh` must have a token in its own environment.

WRITTEN FROM THE MERGE TRAIN'S FIRST DISPATCH. `merge-train.yml` proved its
tools with `gh auth status >/dev/null` in a step carrying no `GH_TOKEN`, while
the token was set on the later step that does the work. On a self-hosted runner
nothing has ever run `gh auth login`, so the preflight asked a logged-out CLI
whether it was logged in, got "You are not logged into any GitHub hosts", and
exited 1. The train never reached the code that judges a pull request, and every
scheduled tick would have failed the same way.

THE FAILURE MODE IS WORTH NAMING because it is invisible on a hosted runner: the
`gh` shipped in the GitHub-hosted image picks up `GITHUB_TOKEN` from the
environment the runner already exports, so the same YAML works there and fails
here. A workflow that only ever runs on this repo's own box cannot rely on that.

Env lookup is per step: a variable set on one step is not visible to another,
and `env` at the job or workflow level IS inherited. So the rule is that every
step invoking `gh` must see a token from its own `env`, its job's, or the
workflow's.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

TOKEN_KEYS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _has_token(*envs):
    return any(k in (e or {}) for e in envs for k in TOKEN_KEYS)


def _runs_gh(step):
    run = step.get("run")
    return bool(run) and re.search(r"(?m)(^|[|&;(\s])gh\s", run) is not None


@unittest.skipIf(yaml is None, "pyyaml is not installed. UNKNOWN, not a pass.")
class EveryGhStepCarriesAToken(unittest.TestCase):

    def test_every_step_that_runs_gh_can_authenticate(self):
        offenders = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            top = doc.get("env") or {}
            for job_name, job in (doc.get("jobs") or {}).items():
                if not isinstance(job, dict):
                    continue
                job_env = job.get("env") or {}
                for step in job.get("steps") or []:
                    if not isinstance(step, dict) or not _runs_gh(step):
                        continue
                    if not _has_token(step.get("env"), job_env, top):
                        offenders.append(
                            "%s :: %s :: %s"
                            % (path.name, job_name,
                               step.get("name") or step.get("id") or "<unnamed>"))
        self.assertEqual(
            offenders, [],
            "these steps invoke gh with no token in scope, so gh runs "
            "unauthenticated and `gh auth status` fails outright on a "
            "self-hosted runner: %s" % offenders)

    def test_the_detector_sees_the_defect_it_was_written_for(self):
        """A guard that cannot fail is not a guard."""
        step = {"name": "preflight", "run": "set -e\ngh auth status >/dev/null"}
        self.assertTrue(_runs_gh(step))
        self.assertFalse(_has_token(step.get("env"), {}, {}))
        self.assertTrue(_has_token({"GH_TOKEN": "x"}, {}, {}))

    def test_it_does_not_fire_on_a_word_merely_containing_gh(self):
        for run in ("echo highlight", "python3 weigh.py", "./gherkin-runner"):
            self.assertFalse(_runs_gh({"run": run}), run)

    def test_there_are_workflows_to_check(self):
        self.assertTrue(list(WORKFLOWS.glob("*.yml")))


if __name__ == "__main__":
    unittest.main()
