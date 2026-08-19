"""The guard that fails the SECOND merge of a plugin version.

Every case is built in a throwaway git repository, so the suite proves the
BEHAVIOUR without depending on this repo's history. One class at the end
replays the two real collisions of 2026-08-19 when the history is present, and
skips when it is not, because CI checks out shallow.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import version_collision as vc  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PLUGIN_PHP = vc.MAIN_PHP


def php(version):
    return ("<?php\n/**\n * Version: %s\n */\ndefine('ALT_VERSION', '%s');\n"
            % (version, version))


class Sandbox:
    """A tiny repo shaped like this one: a plugin folder and a railway folder."""

    def __init__(self, tmp):
        self.path = Path(tmp)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "test")
        self.write(PLUGIN_PHP, php("2.20.114"))
        self.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "a{}\n")
        self.write("railway/cron.py", "x = 1\n")
        self.commit("base")

    def git(self, *args):
        out = subprocess.run(["git"] + list(args), cwd=self.path,
                             capture_output=True, text=True)
        if out.returncode != 0:
            raise AssertionError(" ".join(args) + ": " + out.stderr)
        return out.stdout.strip()

    def write(self, rel, text):
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def branch(self, name, at="main"):
        self.git("checkout", "-q", "-b", name, at)

    def checkout(self, name):
        self.git("checkout", "-q", name)

    def merge(self, name):
        self.git("merge", "-q", "--no-ff", "-m", "Merge " + name, name)
        return self.git("rev-parse", "HEAD")

    def check(self, base, head, mode="main"):
        return vc.check(base, head, mode=mode, repo=str(self.path))


class SandboxCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Sandbox(self.tmp.name)

    def race(self):
        """Two branches off 2.20.114, both bumping to 2.20.115. The real shape."""
        start = self.repo.git("rev-parse", "HEAD")
        for name, extra in (("a", "templates/page-a.php"),
                            ("b", "templates/page-b.php")):
            self.repo.branch(name, start)
            self.repo.write(PLUGIN_PHP, php("2.20.115"))
            self.repo.write("wordpress-plugin/ai-layoff-tracker/" + extra, "<?php\n")
            self.repo.commit("branch " + name)
            self.repo.checkout("main")
        return start


class ANormalBump(SandboxCase):
    def test_a_bumped_plugin_change_passes(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        self.repo.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "b{}\n")
        after = self.repo.commit("ship")
        result = self.repo.check(before, after)
        self.assertEqual(vc.PASS, result.verdict, result.detail)
        self.assertTrue(result.ok)
        self.assertEqual(0, result.exit_code)

    def test_a_minor_or_major_bump_passes_too(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write(PLUGIN_PHP, php("2.21.0"))
        after = self.repo.commit("ship")
        self.assertEqual(vc.PASS, self.repo.check(before, after).verdict)

    def test_the_suggested_number_is_the_next_patch(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        after = self.repo.commit("ship")
        self.assertEqual("2.20.116", self.repo.check(before, after).suggested)


class TheSecondMergeOfARace(SandboxCase):
    def test_the_first_merge_passes_and_the_second_fails(self):
        self.race()
        before = self.repo.git("rev-parse", "HEAD")
        first = self.repo.merge("a")
        self.assertEqual(vc.PASS, self.repo.check(before, first).verdict)

        second = self.repo.merge("b")
        result = self.repo.check(first, second)
        self.assertEqual(vc.FAIL, result.verdict)
        self.assertFalse(result.ok)
        self.assertEqual(1, result.exit_code)
        self.assertEqual("COLLIDED", result.findings[0].cause)

    def test_the_failure_names_the_version_to_use(self):
        self.race()
        first = self.repo.merge("a")
        second = self.repo.merge("b")
        result = self.repo.check(first, second)
        self.assertEqual("2.20.116", result.suggested)
        lines = []
        vc.report(result, "main", first, second, log=lines.append)
        text = "\n".join(lines)
        self.assertIn("2.20.116", text)
        self.assertIn("Rebase onto main", text)

    def test_it_names_the_plugin_files_that_shipped_unversioned(self):
        self.race()
        self.repo.merge("a")
        second = self.repo.merge("b")
        files = self.repo.check(self.repo.git("rev-parse", "HEAD~1"),
                                second).findings[0].files
        self.assertIn("wordpress-plugin/ai-layoff-tracker/templates/page-b.php",
                      files)

    def test_forgetting_the_bump_entirely_is_the_same_finding(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "c{}\n")
        after = self.repo.commit("no bump")
        result = self.repo.check(before, after)
        self.assertEqual(vc.FAIL, result.verdict)
        self.assertEqual("COLLIDED", result.findings[0].cause)


class AChangeThatOwesNoVersion(SandboxCase):
    """The condition that must never manufacture a red run."""

    def test_a_python_only_change_is_skipped(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write("railway/cron.py", "x = 2\n")
        after = self.repo.commit("python only")
        result = self.repo.check(before, after)
        self.assertEqual(vc.SKIP, result.verdict)
        self.assertTrue(result.ok)
        self.assertEqual(0, result.exit_code)

    def test_a_workflow_only_change_is_skipped(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write(".github/workflows/tests.yml", "name: Tests\n")
        after = self.repo.commit("workflow only")
        self.assertEqual(vc.SKIP, self.repo.check(before, after).verdict)

    def test_a_docs_only_change_is_skipped(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write("docs/TECHLOG.md", "note\n")
        after = self.repo.commit("docs")
        self.assertEqual(vc.SKIP, self.repo.check(before, after).verdict)

    def test_a_zip_inside_the_plugin_folder_is_not_a_plugin_change(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write("wordpress-plugin/ai-layoff-tracker/old.zip", "junk\n")
        after = self.repo.commit("zip")
        self.assertEqual(vc.SKIP, self.repo.check(before, after).verdict)

    def test_a_python_only_pr_is_skipped_even_when_main_moved_the_plugin(self):
        """Diffing a stale branch against the main TIP would demand a bump here."""
        start = self.repo.git("rev-parse", "HEAD")
        self.repo.branch("py", start)
        self.repo.write("railway/cron.py", "x = 3\n")
        head = self.repo.commit("python only")
        self.repo.checkout("main")
        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        self.repo.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "d{}\n")
        self.repo.commit("main ships a plugin change")
        result = self.repo.check("main", head, mode="pr")
        self.assertEqual(vc.SKIP, result.verdict, result.detail)


class AStalePullRequest(SandboxCase):
    def test_it_fails_against_a_main_that_took_its_number(self):
        start = self.repo.git("rev-parse", "HEAD")
        self.repo.branch("b", start)
        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        self.repo.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "e{}\n")
        head = self.repo.commit("branch")
        self.repo.checkout("main")

        self.assertEqual(vc.PASS, self.repo.check("main", head, mode="pr").verdict)

        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        self.repo.write("wordpress-plugin/ai-layoff-tracker/templates/x.php", "<?php\n")
        self.repo.commit("main took 115")

        result = self.repo.check("main", head, mode="pr")
        self.assertEqual(vc.FAIL, result.verdict)
        self.assertEqual("COLLIDED", result.findings[0].cause)
        self.assertEqual("2.20.116", result.suggested)
        self.assertIn("current main tip", result.findings[0].detail)


class AVersionThatWasSpentBefore(SandboxCase):
    def test_reusing_an_earlier_number_fails(self):
        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        self.repo.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "f{}\n")
        self.repo.commit("115")
        self.repo.write(PLUGIN_PHP, php("2.20.116"))
        before = self.repo.commit("116")
        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        self.repo.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "g{}\n")
        after = self.repo.commit("rollback reusing 115")
        result = self.repo.check(before, after)
        self.assertEqual(vc.FAIL, result.verdict)
        self.assertEqual({"COLLIDED", "REUSED"} & {f.cause for f in result.findings},
                         {"COLLIDED"})

    def test_a_forward_jump_onto_a_spent_number_is_caught(self):
        """Only the history guard can see this one: the version still rises."""
        self.repo.write(PLUGIN_PHP, php("2.20.120"))
        self.repo.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "h{}\n")
        self.repo.commit("120")
        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        before = self.repo.commit("back to 115, no plugin bytes")
        self.repo.write(PLUGIN_PHP, php("2.20.120"))
        self.repo.write("wordpress-plugin/ai-layoff-tracker/assets/layoffs.css", "i{}\n")
        after = self.repo.commit("120 again")
        result = self.repo.check(before, after)
        self.assertEqual(vc.FAIL, result.verdict)
        self.assertEqual("REUSED", result.findings[0].cause)
        self.assertEqual("2.20.121", result.suggested)


class ABranchThatLandedNothing(SandboxCase):
    def test_a_merge_that_ships_no_plugin_bytes_but_wanted_to_fails(self):
        """PR #155's shape: both branches typed the same version, the loser is a no-op."""
        self.race()
        first = self.repo.merge("a")
        # b now types exactly what a already landed, so its merge is empty.
        self.repo.checkout("b")
        self.repo.git("rm", "-q", "wordpress-plugin/ai-layoff-tracker/templates/page-b.php")
        self.repo.commit("b keeps only the bump")
        self.repo.checkout("main")
        second = self.repo.merge("b")
        self.assertEqual([], vc.plugin_files_changed(first, second, repo=str(self.repo.path)))
        result = self.repo.check(first, second)
        self.assertEqual(vc.FAIL, result.verdict)
        self.assertIn("LANDED_NOOP", [f.cause for f in result.findings])

    def test_a_merge_of_a_branch_that_never_touched_the_plugin_is_skipped(self):
        start = self.repo.git("rev-parse", "HEAD")
        self.repo.branch("py", start)
        self.repo.write("railway/cron.py", "x = 9\n")
        self.repo.commit("python only")
        self.repo.checkout("main")
        before = self.repo.git("rev-parse", "HEAD")
        after = self.repo.merge("py")
        self.assertEqual(vc.SKIP, self.repo.check(before, after).verdict)


class WhatItCannotAnswer(SandboxCase):
    def test_a_shallow_checkout_is_unknown_and_is_not_a_pass(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write(PLUGIN_PHP, php("2.20.115"))
        after = self.repo.commit("ship")
        with tempfile.TemporaryDirectory() as clone:
            subprocess.run(["git", "clone", "-q", "--depth", "1",
                            "file://" + str(self.repo.path), clone],
                           capture_output=True, text=True, check=True)
            result = vc.check(before, after, repo=clone)
        self.assertEqual(vc.UNKNOWN, result.verdict)
        self.assertFalse(result.ok)
        self.assertEqual(3, result.exit_code)

    def test_an_unresolvable_revision_is_unknown(self):
        result = self.repo.check("0" * 40, "HEAD")
        self.assertEqual(vc.UNKNOWN, result.verdict)
        self.assertFalse(result.ok)

    def test_an_unreadable_version_is_unknown_rather_than_a_pass(self):
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.write(PLUGIN_PHP, "<?php\n// no constant here\n")
        after = self.repo.commit("break the constant")
        result = self.repo.check(before, after)
        self.assertEqual(vc.UNKNOWN, result.verdict)
        self.assertFalse(result.ok)


class TheParser(unittest.TestCase):
    def test_versions_sort_numerically_not_as_text(self):
        self.assertGreater(vc.parse_version("2.20.116"), vc.parse_version("2.20.99"))
        self.assertGreater(vc.parse_version("2.21.0"), vc.parse_version("2.20.999"))

    def test_a_non_version_is_none(self):
        for bad in (None, "", "2.20.x", "abc"):
            self.assertIsNone(vc.parse_version(bad))

    def test_next_version_bumps_the_last_component(self):
        self.assertEqual("2.20.117", vc.next_version({(2, 20, 116), (2, 20, 114)}))


class TheTwoRealCollisions(unittest.TestCase):
    """2026-08-19, replayed. Skips when the history is not in this checkout."""

    FIRST_PARENT = "78f26df185927729d105a030af66eedecfc7f763"   # main at 2.20.115
    FIRST_MERGE = "1b3ce80f58086150407a7318cd010c377cdc3c50"    # PR #153, also 2.20.115
    CLEAN_PARENT = "5e87091cd266a1ef01e356b2edee8cfebbaab82b"   # main at 2.20.114
    CLEAN_MERGE = "5be64e64cc5195ba9bb384b75ea58127e551bd15"    # PR #154, 2.20.115
    SECOND_PARENT = "ba4b9270430f8ebf7c72976b773a89aa14593206"  # main at 2.20.116
    SECOND_MERGE = "2c2f28ff8501d3dbb375aa2fcd0f667471f8c6c4"   # PR #155, also 2.20.116

    def setUp(self):
        try:
            if vc.is_shallow(str(REPO)):
                self.skipTest("shallow checkout")
            for sha in (self.FIRST_PARENT, self.FIRST_MERGE, self.SECOND_MERGE):
                vc.git(["cat-file", "-e", sha + "^{commit}"], repo=str(REPO))
        except vc.GitError:
            self.skipTest("history not present in this checkout")

    def test_the_2_20_115_collision_fails(self):
        result = vc.check(self.FIRST_PARENT, self.FIRST_MERGE, repo=str(REPO))
        self.assertEqual(vc.FAIL, result.verdict)
        self.assertEqual("COLLIDED", result.findings[0].cause)
        self.assertEqual("2.20.116", result.suggested)

    def test_the_2_20_116_collision_fails(self):
        result = vc.check(self.SECOND_PARENT, self.SECOND_MERGE, repo=str(REPO))
        self.assertEqual(vc.FAIL, result.verdict)
        self.assertIn("LANDED_NOOP", [f.cause for f in result.findings])

    def test_the_merge_that_was_correct_still_passes(self):
        result = vc.check(self.CLEAN_PARENT, self.CLEAN_MERGE, repo=str(REPO))
        self.assertEqual(vc.PASS, result.verdict, result.detail)


if __name__ == "__main__":
    unittest.main()
