"""A self-hosted-runner workflow must not write scratch files to a bare /tmp/
path.

Found 2026-10-02 by the hourly ops check. `company-directory-autopilot.yml`
and `evidence-hash-backfill.yml` both `runs-on: [self-hosted, linux,
contabo]` -- the SAME physical machine, shared across every workflow pinned
to it, with no per-job filesystem isolation. Both wrote their scratch files
to fixed names directly under `/tmp/` (`/tmp/resp.json`, `/tmp/summary.txt`,
`/tmp/last.json`, `/tmp/vars.sh`). On 2026-10-01/02 this produced two
distinct failures with the same root cause: `company-directory-autopilot.yml`
died with `/tmp/summary.txt: Permission denied` (run 36730357949, then again
36877552925) and `evidence-hash-backfill.yml` died with
`curl: (23) Failure writing output to destination` trying to write
`/tmp/resp.json` (run 36976068264) -- a stale file left in the shared `/tmp`
by some other job on the same machine, owned by a user or with permissions
this job's user could not overwrite.

`RUNNER_TEMP` is a directory GitHub Actions creates fresh per job and cleans
up afterward, so it cannot collide with another job's leftovers the way a
hardcoded `/tmp/<name>` can. The fix moved every scratch path in both
workflows to `$RUNNER_TEMP` (read via `os.environ['RUNNER_TEMP']` inside the
embedded Python, since a quoted heredoc delimiter is not shell-expanded).

This pins only the two workflows that demonstrably broke this way, not every
self-hosted workflow -- several others (`deploy-plugin.yml`,
`ftp-target-probe.yml`, `quarterly-report.yml`,
`recall-benchmark-publish.yml`, `tracker-crosscheck.yml`) still use `/tmp/`
directly and carry the same latent risk, but widening this test to all of
them is a separate, deliberate change, not a side effect of fixing what was
actually observed broken.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

FIXED_FILES = [
    "company-directory-autopilot.yml",
    "evidence-hash-backfill.yml",
]

# A bare /tmp/<name> reference, as opposed to $RUNNER_TEMP/<name> or
# "$RUNNER_TEMP"/<name>.
BARE_TMP = re.compile(r"(?<!RUNNER_)/tmp/\S")


class SelfHostedScratchPathsUseRunnerTemp(unittest.TestCase):
    def test_no_bare_tmp_path_in_the_fixed_workflows(self):
        for name in FIXED_FILES:
            path = WORKFLOWS / name
            with self.subTest(workflow=name):
                self.assertTrue(path.is_file(), f"{path} is missing")
                text = path.read_text(encoding="utf-8")
                matches = BARE_TMP.findall(text)
                self.assertEqual(
                    matches, [],
                    f"{name} writes a scratch file to a bare /tmp/ path "
                    f"({matches!r}), which collides with other jobs on the "
                    "shared self-hosted runner. Use $RUNNER_TEMP instead.")

    def test_both_workflows_still_run_on_the_shared_self_hosted_runner(self):
        # If either workflow stops using the shared runner, this test (and
        # the incident it documents) no longer applies to it -- that's fine,
        # but it should be a deliberate edit here, not a silent gap.
        for name in FIXED_FILES:
            path = WORKFLOWS / name
            with self.subTest(workflow=name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("self-hosted", text)


if __name__ == "__main__":
    unittest.main()
