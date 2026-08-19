"""THE STASH-STACK WATCH MUST NOT RESOLVE A THING IT COULD NOT READ INTO A PASS.

WHY THIS TEST EXISTS.

The stash stack is per-REPOSITORY, and every worktree of the repo pushes onto
and pops off the same one. With a dozen agent worktrees live at once that is a
shared mutable structure with no owner. It is not hypothetical here: this repo's
`stash@{0}` is labelled "restored: popped by accident from a sibling worktree",
and the sibling talent repo accumulated four AUTOSTASH entries written silently
by `git rebase --autostash`, one of which held work that exists nowhere on main.

It cannot be enforced. `rebase.autoStash=false` is set locally in all three
repos, but an explicit `--autostash` on the command line overrides config, and
no hook can refuse a stash push without risking a rebase left half-finished. A
check is all there is, so the check has to be honest in the one way that matters:

  * an unreadable repo, an unreadable entry, or a missing base is UNKNOWN, and
    UNKNOWN is never a pass — the load-bearing rule across this codebase;
  * an autostash entry is a FAIL however few there are, because the count is not
    the point: the point is that something wrote to a shared stack silently.

The tests build real throwaway repos rather than mocking git, because the whole
value of the module is what git actually reports.
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import stash_watch  # noqa: E402


def _run(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   capture_output=True, text=True)


def _repo(tmp):
    """A repo with one commit on main and an `origin/main` to compare against."""
    _run(tmp, "init", "-q", "-b", "main")
    _run(tmp, "config", "user.email", "t@example.com")
    _run(tmp, "config", "user.name", "t")
    with open(os.path.join(tmp, "f.py"), "w") as fh:
        fh.write("original = 1\n")
    _run(tmp, "add", "f.py")
    _run(tmp, "commit", "-qm", "base")
    # A local ref standing in for origin/main, so no network is involved.
    _run(tmp, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp


class StashWatchTests(unittest.TestCase):

    def test_an_empty_stack_is_the_only_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            verdict, why, _ = stash_watch.check(_repo(tmp))
            self.assertEqual(stash_watch.PASS, verdict, why)

    def test_a_repo_it_cannot_read_is_unknown_and_says_so(self):
        verdict, why, _ = stash_watch.check("/private/tmp/no-such-repo-here")
        self.assertEqual(stash_watch.UNKNOWN, verdict)
        self.assertIn("NOT A PASS", why.upper())

    def test_a_missing_base_makes_every_entry_unknown_not_landed(self):
        """If origin/main is not in the checkout there is nothing to compare
        against. That must not read as 'nothing differs'."""
        with tempfile.TemporaryDirectory() as tmp:
            _repo(tmp)
            with open(os.path.join(tmp, "f.py"), "w") as fh:
                fh.write("original = 2\n")
            _run(tmp, "stash", "push", "-q", "-m", "wip")
            verdict, _why, lines = stash_watch.check(tmp, base="origin/absent")
            self.assertNotEqual(stash_watch.PASS, verdict)
            self.assertTrue(any(stash_watch.UNKNOWN in l for l in lines),
                            "a missing base must show as UNKNOWN per entry")

    def test_one_autostash_fails_however_short_the_stack(self):
        """The count is not the point. Something wrote to a shared stack
        silently, and that is the finding."""
        with tempfile.TemporaryDirectory() as tmp:
            _repo(tmp)
            with open(os.path.join(tmp, "f.py"), "w") as fh:
                fh.write("original = 3\n")
            _run(tmp, "stash", "push", "-q", "-m", "autostash")
            verdict, why, _ = stash_watch.check(tmp)
            self.assertEqual(stash_watch.FAIL, verdict)
            self.assertIn("AUTOSTASH", why.upper())

    def test_content_already_on_main_reads_landed(self):
        """The cheap verdict: main holds byte-identical copies of every file the
        entry touches, so the entry is clutter rather than a hostage."""
        with tempfile.TemporaryDirectory() as tmp:
            _repo(tmp)
            with open(os.path.join(tmp, "f.py"), "w") as fh:
                fh.write("landed = 1\n")
            _run(tmp, "stash", "push", "-q", "-m", "wip")
            # Main now carries exactly what the stash carries.
            with open(os.path.join(tmp, "f.py"), "w") as fh:
                fh.write("landed = 1\n")
            _run(tmp, "add", "f.py")
            _run(tmp, "commit", "-qm", "land it")
            _run(tmp, "update-ref", "refs/remotes/origin/main", "HEAD")
            verdict, why, _files = stash_watch.classify(tmp, 0)
            self.assertEqual("LANDED", verdict, why)

    def test_unlanded_content_is_never_called_landed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _repo(tmp)
            with open(os.path.join(tmp, "f.py"), "w") as fh:
                fh.write("only_in_the_stash = 1\n")
            _run(tmp, "stash", "push", "-q", "-m", "wip")
            verdict, _why, _files = stash_watch.classify(tmp, 0)
            self.assertEqual("DIFFERS", verdict)

    def test_containment_reports_a_line_that_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            _repo(tmp)
            with open(os.path.join(tmp, "f.py"), "w") as fh:
                fh.write("original = 1\ndef a_distinctive_identifier():\n    pass\n")
            _run(tmp, "stash", "push", "-q", "-m", "wip")
            rows = stash_watch.containment(tmp, 0)
            pcts = [p for _f, p, _t, _n in rows if p is not None]
            self.assertTrue(pcts and pcts[0] < 100,
                            "an added line absent from main must not score 100%")


if __name__ == "__main__":
    unittest.main()
