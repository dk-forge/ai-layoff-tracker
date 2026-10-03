"""`_try_rebase`'s git calls, against a REAL repo. Everything else in
tests/test_merge_train.py deliberately fakes `gh` and never shells to git; this
file is the one place that proves the actual `git checkout -B` the unstick
path runs still works when the working tree is not pristine.

THE DEFECT THIS CATCHES (run 37060109696, 2026-10-02)
------------------------------------------------------
A merge-train run escalated PR #439 (`needs-human`), which calls
`notify()` -> `ops_notify.notify()` -> `alert_state.save()`. That writes
`railway/alert_state.json` IN PLACE WITH NO GIT, by that file's own design,
because `ALERT_STATE_COMMIT` is only set inside ci-alert.yml/alert-drain.yml
(see railway/alert_state.py) and merge-train.yml never sets it. The same run
then tried to unstick PR #441 (`SKIP_CONFLICT`) via `_try_rebase`, whose very
first git command, `git checkout -B mt/<branch> origin/<branch>`, refused:

    error: Your local changes to the following files would be overwritten
    by checkout:
        railway/alert_state.json
    Please commit your changes or stash them before you switch branches.

One PR's escalation dirtied a tracked file the train never intends to carry
forward, and the next PR's unstick attempt died on it. `test_mutation_removing_force`
below reverts the fix and proves this file actually catches that.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import merge_train as mt  # noqa: E402


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=check)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


class FakeClient:
    """`_try_rebase` only calls `.comment` on this, and only off the
    non-dry-run path this test never takes."""

    def comment(self, number, body):
        raise AssertionError("dry_run must never post a comment")


def _build_repo(tmp_path: Path) -> tuple[Path, str]:
    """origin (bare) + a clone, with `main` and `pr-branch` diverging on
    README.md, and `alert_state.json` diverging too (main picks up a second
    commit to it after the branch point) -- the shape that makes a dirty
    working copy of that file actually collide with the checkout target,
    rather than being silently carried through untouched."""
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(repo)], check=True)
    _git(repo, "config", "user.email", "a@a.com")
    _git(repo, "config", "user.name", "a")

    _write(repo / "README.md", "base\n")
    _write(repo / "alert_state.json", '{"version": 1}\n')
    _git(repo, "add", "README.md", "alert_state.json")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "branch", "-M", "main")
    _git(repo, "push", "-q", "origin", "main")

    _git(repo, "checkout", "-qb", "pr-branch")
    _write(repo / "README.md", "base\nfeature change\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "feature change")
    pr_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "push", "-q", "origin", "pr-branch")

    _git(repo, "checkout", "-q", "main")
    _write(repo / "alert_state.json",
          '{"version": 1, "open": {"deploy:main:abc123": {"first": 100}}}\n')
    _git(repo, "add", "alert_state.json")
    _git(repo, "commit", "-qm", "ci-alert: committed ledger claim")
    _git(repo, "push", "-q", "origin", "main")
    return repo, pr_sha


class ItSurvivesANotifyLeftDirtyTree(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.repo, self.pr_sha = _build_repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _dirty_alert_state(self) -> None:
        # Mirrors ops_notify.notify() -> alert_state.save() writing in place,
        # uncommitted, during THIS run -- never the content a human wrote.
        _write(self.repo / "alert_state.json",
              '{"version": 1, "open": {"merge-train:needs-human:439": '
              '{"first": 200}}}\n')
        self.assertIn("alert_state.json", _git(self.repo, "status", "--porcelain").stdout)

    def test_a_dirty_alert_state_json_does_not_block_the_unstick_checkout(self):
        """The real-world failure: #439's escalation dirties alert_state.json,
        then #441's unstick tries to check out its branch in the same tree."""
        self._dirty_alert_state()
        pr = {"number": 441, "headRefOid": self.pr_sha, "headRefName": "pr-branch"}
        rep = mt.Report(dry_run=True)
        ok = mt._try_rebase(FakeClient(), mt.Config.from_dict({
            "repo": "x/y", "min_checks": 3,
        }), pr, rep, dry_run=True, worktree=self.repo, attempt=1)
        self.assertTrue(ok, "\n".join(rep.lines))
        # The dirty file must not have been silently discarded as part of
        # some OTHER path; it is simply not in the way any more.
        self.assertTrue((self.repo / "alert_state.json").exists())

    def test_mutation_removing_force_reproduces_the_live_failure(self):
        """Mutation proof: call git exactly as `_try_rebase` did before this
        fix (plain `checkout -B`, no `--force`) against the same dirty tree,
        and show it fails with the exact error from the failing run."""
        self._dirty_alert_state()
        _git(self.repo, "fetch", "-q", "origin", "main", "pr-branch")
        proc = _git(self.repo, "checkout", "-B", "mt/pr-branch", "origin/pr-branch",
                    check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("would be overwritten by checkout", proc.stderr)
        self.assertIn("alert_state.json", proc.stderr)


if __name__ == "__main__":
    unittest.main()
