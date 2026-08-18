"""Run the railway unit suite as one of two groups, so CI can run both at once.

WHY THIS EXISTS.

The suite is not slow because it is wasteful. It is slow because a growing
number of its guards MEASURE A RENDERED PAGE: they start a real headless
Chrome through `cdp.py`, load a fixture, and read back geometry, computed
colour and tap-target size. Those are the guards that caught four phone-fold
regressions and an unreadable dark theme, and every one of them is worth its
seconds. But Chrome dominates the WALL clock while Python sits idle waiting on
the DevTools socket, so the two halves of this suite have completely different
shapes: one is CPU, one is a subprocess we wait on.

Run in one process they add up. Run as two GitHub jobs they overlap, and the
workflow's wall clock becomes the larger half instead of the sum. Nothing is
skipped, nothing is marked slow, no assertion is weakened, and no test file is
edited — the only change is which runner picks it up.

THE SPLIT IS DERIVED, NEVER HAND-MAINTAINED.

A hand-written list of "the slow ones" is a list that drifts: the next browser
test lands in the fast job, nobody notices, and the ceiling creeps back. So
the group is computed from the module's own source — a module that imports
`cdp` drives a browser, and that is the whole rule.

`ALL` is the same set `unittest discover -s tests -p "test_*.py"` would find
(the same glob against the same directory), and the two groups partition it by
construction. tests/test_test_groups.py pins that: total, disjoint, and both
groups actually named by the workflow.

  python3 run_tests.py --group rest
  python3 run_tests.py --group rendered
  python3 run_tests.py --list rendered      # names only, no execution

Exit code is 0 only when the group ran clean. An empty group is an ERROR, not
a pass: a group that silently selected nothing is the failure mode this file
would otherwise introduce.
"""
import argparse
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE / "tests"

#: A module that imports cdp starts a real Chrome. Matched at statement
#: position so a mention inside a docstring or a comment does not count.
_IMPORTS_CDP = re.compile(r"^[ \t]*(?:from[ \t]+cdp[ \t]+import|import[ \t]+cdp)\b",
                          re.MULTILINE)

GROUPS = ("rest", "rendered")


def all_modules():
    """Every module `unittest discover -p "test_*.py"` would collect, by stem."""
    return sorted(p.stem for p in TESTS.glob("test_*.py"))


def drives_a_browser(stem):
    src = (TESTS / f"{stem}.py").read_text(encoding="utf-8", errors="replace")
    return _IMPORTS_CDP.search(src) is not None


def group_of(stem):
    return "rendered" if drives_a_browser(stem) else "rest"


def modules_in(group):
    if group not in GROUPS:
        raise SystemExit(f"unknown group {group!r}; expected one of {GROUPS}")
    return [m for m in all_modules() if group_of(m) == group]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--group", choices=GROUPS)
    ap.add_argument("--list", choices=GROUPS, dest="list_group")
    args = ap.parse_args(argv)

    if args.list_group:
        print("\n".join(modules_in(args.list_group)))
        return 0
    if not args.group:
        ap.error("one of --group or --list is required")

    names = modules_in(args.group)
    if not names:
        print(f"group '{args.group}' selected NO modules. That is a defect in "
              f"the split, not an empty success.", file=sys.stderr)
        return 2

    # Both dirs, matching what `discover -s tests` sets up: the tests import
    # railway modules by bare name, and each other's helpers the same way.
    sys.path.insert(0, str(TESTS))
    sys.path.insert(0, str(HERE))

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in names:
        # loadTestsFromName surfaces an import error as a _FailedTest inside
        # THIS group rather than swallowing it, which is what discover does too.
        suite.addTests(loader.loadTestsFromName(name))

    print(f"group '{args.group}': {len(names)} module(s), "
          f"{suite.countTestCases()} test(s)")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
