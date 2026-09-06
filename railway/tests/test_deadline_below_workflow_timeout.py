"""A run's own deadline must sit strictly below the deadline the runner enforces.

Every scheduled job here has two clocks. The outer one is the workflow's
`timeout-minutes`, which the runner enforces by SIGTERM and then a kill. The
inner one is the script's own wall-clock deadline, which is how the job stops
ITSELF: it finishes the item in hand, posts a terminal health note, writes what
it has and exits 0.

Only the inner clock produces a clean stop. If the outer one fires first the
run is killed mid-item, and while source_health's interrupt handler (2026-09-05)
means that no longer leaves an orphan `running` note, the run still loses the
work in flight and reports an interruption rather than a completion.

So the invariant is not "the default is small enough". It is "the LARGEST value
this deadline can take is still below the kill", because every one of these is
an env var an operator can raise. On 2026-09-06 five of eleven failed it, all
with safe defaults and all one `vars` entry away from a job that could never
finish cleanly:

    ai_evidence_sweep              ceiling 3600s vs a 27min kill
    reason_backfill                ceiling 1800s vs a 27min kill
    archive_sources                UNBOUNDED     vs a 60min kill
    company_watchlist              UNBOUNDED     vs a 90min kill
    daily_classification_spotcheck UNBOUNDED     vs a 10min kill

The test derives both sides from the tree, so a new deadline constant, a new
workflow, or a lowered `timeout-minutes` is covered without anyone listing it
here. The failure message names the pair and the two numbers, because "raise the
workflow first, then the deadline" is the fix and the reader needs both.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAILWAY = ROOT / "railway"
WORKFLOWS = ROOT / ".github" / "workflows"

#: A module-level assignment whose name matches this is a whole-run wall clock.
DEADLINE_NAME = re.compile(r"^(DEADLINE|DEADLINE_SECONDS|RUN_BUDGET_SECONDS)$")

#: The margin the inner clock must leave the outer one. A job that stops itself
#: still has to post its health note, write its state and push, and a deadline
#: equal to the kill is a race, not a budget.
MIN_MARGIN_SECONDS = 60


def _ceiling(node):
    """The largest value a clamp expression can evaluate to, or None if unbounded.

    Reads `min(<literal>, ...)` anywhere inside the expression. `max(60, ...)`
    only raises a floor and is ignored. An expression with no `min` on a literal
    can be driven arbitrarily high by its env var, which is the unbounded case.
    """
    best = None
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
        if name != "min":
            continue
        for arg in sub.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
                best = arg.value if best is None else min(best, arg.value)
            elif isinstance(arg, ast.Name):
                # A named ceiling (archive_backfill's DEADLINE_CAP_SECONDS).
                resolved = _module_constants.get(arg.id)
                if isinstance(resolved, (int, float)):
                    best = resolved if best is None else min(best, resolved)
    return best


_module_constants = {}


def _deadlines(path):
    """{constant name: ceiling or None} for one module."""
    global _module_constants
    tree = ast.parse(path.read_text())
    _module_constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, (int, float)):
            _module_constants[node.targets[0].id] = node.value.value
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not DEADLINE_NAME.match(target.id):
            continue
        if isinstance(node.value, ast.Constant):
            continue  # a plain literal is its own ceiling and no env var moves it
        found[target.id] = _ceiling(node.value)
    return found


def _timeouts():
    """{script basename: (workflow name, timeout-minutes)} for scheduled jobs."""
    out = {}
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        text = wf.read_text()
        if "cron:" not in text:
            continue
        m = re.search(r"timeout-minutes:\s*(\d+)", text)
        if not m:
            continue
        minutes = int(m.group(1))
        for script in set(re.findall(r"([A-Za-z0-9_]+)\.py", text)):
            prev = out.get(script)
            # The tightest kill wins: the deadline must clear every job it runs in.
            if prev is None or minutes < prev[1]:
                out[script] = (wf.name, minutes)
    return out


class EveryDeadlineClearsItsKill(unittest.TestCase):
    def test_every_scheduled_deadline_has_a_ceiling_below_its_workflow_timeout(self):
        timeouts = _timeouts()
        self.assertTrue(timeouts, "no scheduled workflow parsed; the scan is broken")
        checked, failures = [], []
        for path in sorted(RAILWAY.rglob("*.py")):
            if "tests" in path.parts:
                continue
            hit = timeouts.get(path.stem)
            if hit is None:
                continue
            workflow, minutes = hit
            for name, ceiling in _deadlines(path).items():
                budget = minutes * 60 - MIN_MARGIN_SECONDS
                checked.append(f"{path.name}:{name}")
                if ceiling is None:
                    failures.append(
                        f"{path.name}:{name} is UNBOUNDED but {workflow} kills the "
                        f"run at {minutes}min. Clamp it with min(<seconds>, ...).")
                elif ceiling > budget:
                    failures.append(
                        f"{path.name}:{name} can reach {ceiling}s but {workflow} "
                        f"kills the run at {minutes}min ({minutes * 60}s), leaving "
                        f"{budget}s once the {MIN_MARGIN_SECONDS}s reporting margin "
                        f"is kept. Raise timeout-minutes first, then the ceiling.")
        self.assertTrue(checked, "no deadline constants found; the scan is broken")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_the_scan_actually_sees_the_known_deadlines(self):
        """A guard whose clean zero comes from finding nothing is not a guard."""
        timeouts = _timeouts()
        seen = set()
        for path in sorted(RAILWAY.rglob("*.py")):
            if "tests" in path.parts or path.stem not in timeouts:
                continue
            if _deadlines(path):
                seen.add(path.stem)
        for expected in ("ai_evidence_sweep", "reason_backfill", "archive_sources",
                         "company_watchlist", "daily_classification_spotcheck",
                         "enrich_context", "enrich_roles", "industry_backfill",
                         "reclassify_legacy_ai", "distress_watchlist",
                         "archive_backfill"):
            self.assertIn(expected, seen,
                          f"{expected} carries a deadline the scan no longer reads")


if __name__ == "__main__":
    unittest.main()
