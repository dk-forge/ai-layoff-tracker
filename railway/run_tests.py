"""Run the railway unit suite as one of four groups, so CI can run them at once.

WHY THIS EXISTS.

The suite is not slow because it is wasteful. It is slow because a growing
number of its guards MEASURE A RENDERED PAGE: they start a real headless
Chrome through `cdp.py`, load a fixture, and read back geometry, computed
colour and tap-target size. Those are the guards that caught four phone-fold
regressions and an unreadable dark theme, and every one of them is worth its
seconds. But Chrome dominates the WALL clock while Python sits idle waiting on
the DevTools socket, so the halves of this suite have completely different
shapes: one is CPU, one is a subprocess we wait on.

Run in one process they add up. Run as parallel GitHub jobs they overlap, and
the workflow's wall clock becomes the largest job instead of the sum. Nothing
is skipped, nothing is marked slow, no assertion is weakened, and no test file
is edited — the only change is which runner picks it up.

BOTH HALVES OUTGREW A SINGLE JOB. The browser half hit the 15-minute ceiling
first (2026-08-26: the monthly edition's methodology content tipped it over);
a first split by module COUNT balanced the count but not the TIME — one browser
leg ran ~2m, the other ~14m — and the CPU-bound `rest` half was itself at ~14m.
So each half is now dealt across TWO legs BY WEIGHT: `rendered-1`/`rendered-2`
for the browser guards, `rest`/`rest-2` for the rest. Four legs, each about a
quarter of the old serial wall, comfortably clear of the ceiling.

THE SPLIT IS DERIVED, NEVER HAND-MAINTAINED.

A hand-written list of "the slow ones" is a list that drifts: the next browser
test lands in the fast job, nobody notices, and the ceiling creeps back. So the
half is computed from the module's own source — a module that imports `cdp`
drives a browser — and within a half the modules are dealt greedily (heaviest
first onto the lightest leg) by `weight_of()`: a per-module runtime MEASURED
from CI for the heavy few, else the count of `def test_` it declares. A weight
is only a balance hint; it can never drop a test. `test_dedup_live` is pinned to
`rest` because the live-data verdict steps in tests.yml gate on that leg.

`ALL` is the same set `unittest discover -s tests -p "test_*.py"` would find
(the same glob against the same directory), and the four groups partition it
by construction. tests/test_test_groups.py pins that: total, disjoint, weight-
balanced, the live-data module on `rest`, and every group named by the workflow.

  python3 run_tests.py --group rest
  python3 run_tests.py --group rendered-1
  python3 run_tests.py --list rendered-2      # names only, no execution

Exit code is 0 only when the group ran clean. An empty group is an ERROR, not
a pass: a group that silently selected nothing is the failure mode this file
would otherwise introduce.
"""
import argparse
import re
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE / "tests"

#: A module that imports cdp starts a real Chrome. Matched at statement
#: position so a mention inside a docstring or a comment does not count.
_IMPORTS_CDP = re.compile(r"^[ \t]*(?:from[ \t]+cdp[ \t]+import|import[ \t]+cdp)\b",
                          re.MULTILINE)

GROUPS = ("rest", "rest-2", "rendered-1", "rendered-2")

#: test_dedup_live writes LIVE_DATA_VERDICT_FILE, and the "Live-data invariants"
#: steps in tests.yml gate on `matrix.group == 'rest'`. So it MUST ride the
#: `rest` leg — pinned here so a re-weight can never drift it onto rest-2, which
#: would let a leg that never read the live site answer for the one that did.
_LIVE_DATA_PINNED_TO_REST = ("test_dedup_live",)

#: Per-module wall seconds MEASURED FROM CI on 2026-08-26 (run_tests prints
#: `TIMING <secs> <stem>`; re-run and re-read to refresh). Until 2026-08-26 TWO
#: modules dominated, both driven by style_check.collect()'s reader-copy walk:
#: test_reader_copy_says_entries (~780s) and test_style_standard (~700s). That was
#: one quadratic regex in _clean_literal (see docs/TECHLOG.md 2026-08-26): collect()
#: dropped from 762s to ~0.5s. With collect() cheap, test_style_standard is now
#: pure Python (0.6s local) and test_reader_copy is browser-bound (9s local), i.e.
#: just another rendered surface test rather than a leg unto itself. The two values
#: below are the post-fix reads (reader_copy carried to a CI-representative browser
#: figure; style_standard rounded up from 0.6s); the next CI TIMING line refreshes
#: them exactly. Everything unlisted is weighted by how many `def test_` it declares.
#: THE WEIGHT ONLY BALANCES THE DEAL: a wrong weight makes a leg heavier, never
#: drops a test (the totality guard pins that). Re-measure if a leg drifts — do NOT
#: raise the wall.
_MEASURED_WEIGHTS = {
    # browser (rendered) — measured per-test wall
    "test_reader_copy_says_entries": 40,        # now browser-bound; collect() no longer dominates
    "test_blog_applause_surface": 45,
    "test_signup_terminal_states": 43,
    "test_tap_targets": 17,
    "test_signup_reaches_landing_pages": 15,
    "test_nav_submenu": 13,
    "test_filter_controls": 12,
    "test_digest_route_is_findable": 10,
    "test_press_route_is_findable": 5,
    "test_signal_board_default": 5,
    "test_blog_reading_surface": 4,
    "test_card_space": 4,
    "test_rendered_contrast": 3,
    "test_signal_board_periods": 3,
    # non-browser (rest)
    "test_style_standard": 2,                   # collect() now ~0.5s; whole module 0.6s local
    "test_digest_sender": 31,
    "test_dedup_live": 20,
    "test_blog_claps": 15,
    "test_budget_stop_is_not_a_failure": 8,
    "test_subscriber_routes_live": 7,
}

_BROWSER_CACHE = {}
_GROUPING_CACHE = {}

#: A test method declaration, counted (not imported) as the default weight.
_TEST_DEF = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+test_\w", re.MULTILINE)


def all_modules():
    """Every module `unittest discover -p "test_*.py"` would collect, by stem."""
    return sorted(p.stem for p in TESTS.glob("test_*.py"))


def drives_a_browser(stem):
    # Memoised: the grouping asks this about every module, so an unmemoised read
    # would be O(n^2) file opens. The answer is a property of the file's text,
    # which does not change inside a run.
    if stem not in _BROWSER_CACHE:
        src = (TESTS / f"{stem}.py").read_text(encoding="utf-8", errors="replace")
        _BROWSER_CACHE[stem] = _IMPORTS_CDP.search(src) is not None
    return _BROWSER_CACHE[stem]


def weight_of(stem):
    """Relative cost used only to BALANCE the deal — measured for the heavy few,
    else the count of `def test_` in the file (import-free)."""
    if stem in _MEASURED_WEIGHTS:
        return _MEASURED_WEIGHTS[stem]
    src = (TESTS / f"{stem}.py").read_text(encoding="utf-8", errors="replace")
    return max(1, len(_TEST_DEF.findall(src)))


def _deal(stems, legs, preload=None):
    """Greedy longest-processing-time: each stem, heaviest first, goes to the
    currently-lightest leg. Deterministic — ties break by (load, leg name)."""
    load = dict(preload or {})
    for leg in legs:
        load.setdefault(leg, 0)
    assign = {}
    for stem in sorted(stems, key=lambda s: (-weight_of(s), s)):
        leg = min(legs, key=lambda l: (load[l], l))
        assign[stem] = leg
        load[leg] += weight_of(stem)
    return assign


def _compute_grouping():
    """stem -> leg for every discovered module. Browser (cdp) modules split
    across two time-balanced legs; the rest split across two more, with the
    live-data module pinned to `rest`. Nothing lands in no leg."""
    browser = [m for m in all_modules() if drives_a_browser(m)]
    nonbrowser = [m for m in all_modules() if not drives_a_browser(m)]
    assign = {}
    assign.update(_deal(browser, ["rendered-1", "rendered-2"]))
    pinned = [m for m in nonbrowser if m in _LIVE_DATA_PINNED_TO_REST]
    for m in pinned:
        assign[m] = "rest"
    preload = {"rest": sum(weight_of(m) for m in pinned), "rest-2": 0}
    free = [m for m in nonbrowser if m not in _LIVE_DATA_PINNED_TO_REST]
    assign.update(_deal(free, ["rest", "rest-2"], preload=preload))
    return assign


def _grouping():
    # Cached on the module set, so a patched all_modules() (the empty-group
    # test) computes its own answer without poisoning the real one.
    key = tuple(all_modules())
    if key not in _GROUPING_CACHE:
        _GROUPING_CACHE[key] = _compute_grouping()
    return _GROUPING_CACHE[key]


def group_of(stem):
    return _grouping().get(stem, "rest")


def modules_in(group):
    if group not in GROUPS:
        raise SystemExit(f"unknown group {group!r}; expected one of {GROUPS}")
    g = _grouping()
    return [m for m in all_modules() if g.get(m) == group]


def leg_weight(group):
    """Total weight assigned to a leg — the balance the deal optimises."""
    return sum(weight_of(m) for m in modules_in(group))


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

    # Per-module wall time, printed at the end so `weight_of` can be RE-MEASURED
    # from a CI log (grep 'TIMING'). The deal is only as balanced as the weights,
    # and the weights are only as good as the last measurement — this is how you
    # take the next one without guessing. Timing the tests does not change which
    # of them run or pass.
    module_times = {}
    state = {"cur": None}

    def _emit(stem):
        if stem is not None and stem in module_times:
            print("TIMING %7.1fs  %s" % (module_times[stem], stem), flush=True)

    class _TimedResult(unittest.TextTestResult):
        def startTest(self, test):
            self._t0 = time.perf_counter()
            stem = type(test).__module__.split(".")[-1]
            if stem != state["cur"]:
                # A module just finished; emit it NOW (flushed) so a later leg
                # timeout still leaves a record of everything that completed.
                _emit(state["cur"])
                state["cur"] = stem
            super().startTest(test)

        def stopTest(self, test):
            super().stopTest(test)
            stem = type(test).__module__.split(".")[-1]
            module_times[stem] = module_times.get(stem, 0.0) + (
                time.perf_counter() - getattr(self, "_t0", time.perf_counter()))

    result = unittest.TextTestRunner(
        verbosity=2, resultclass=_TimedResult).run(suite)
    _emit(state["cur"])   # the last module, on a clean finish
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
