"""ONE COLLECTOR, ONE SOURCE ID.

THE BUG THIS IS FOR
-------------------
On 2026-08-24 the Minnesota per-company WARN-letters collector shipped with two
names for one thing. `cron.py` registered it in the collector loop as
`mn_warn_letters`; the module itself, `sources/warn_mn_letters.py`, posted its
own terminal health note as `warn_mn_letters`. Both landed every run, one
second apart, with identical entry counts — 2026-09-03T22:05:56Z and :57Z, `ok 5`
each.

Nothing anywhere was red. The damage was quiet and in three places:

  1. **The OK count was inflated.** `ops_status [2]` counts ledger rows, so one
     collector was two of the "39 source(s) OK" a human reads to decide whether
     the fleet is healthy. An inflated denominator is not cosmetic — it is the
     number the fleet is judged by.
  2. **The public Health page showed an unlabelled row**, because only
     `warn_mn_letters` has a `meta{}` entry in `assets/health.js`.
  3. **The collision was invisible precisely BECAUSE of the split.** cron's
     generic terminal note carries an empty detail and a blind `ok`. Written to
     the same key it would have erased the collector's own note — including the
     `degraded` the collector posts when discovery fails outright. Two keys meant
     neither write clobbered the other, so a latent overwrite sat there unseen.

`source_inventory.py` could not catch this. It asks "which declared collectors
never report?" and diffs the declared side against the ledger — a duplicate is
an EXTRA row, not a missing one, so it read as 39 healthy declarations and said
nothing. This test asks the other question.

WHY THIS DOES NOT FIRE ON THE LEGITIMATE SHAPE
----------------------------------------------
Several collectors may share one source id (that is normal and untouched here).
The defect is the reverse — ONE collector reporting under SEVERAL ids — so the
check is deliberately narrow: for each `(id, callable)` the cron collector loop
registers, the module behind that callable may post health under that id and no
other. A module that posts no literal id at all passes; a module that posts
exactly its registered id passes. Only a disagreement fails.

MUTATION-PROVEN: this test was written against the live defect and observed to
FAIL on `("mn_warn_letters", pull_mn_warn_letters)` before the rename, naming
both ids. A guard that has only ever seen a clean tree has not been tested.
"""
import ast
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.dirname(HERE)
CRON = os.path.join(RAILWAY, "cron.py")


def _module_paths_for(func_name, cron_src, tree):
    """Files that could post health on behalf of `func_name` in cron's loop.

    Two shapes are wired today: a name imported straight from `sources.X`, and a
    thin local adapter (`_pull_local_news_rows`) that calls such a name. Both
    resolve to the underlying `sources/*.py`, which is where a module-owned
    health note would live.
    """
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sources."):
            for alias in node.names:
                imported[alias.asname or alias.name] = node.module.split(".", 1)[1]

    mods = set()
    if func_name in imported:
        mods.add(imported[func_name])

    # A local adapter: follow the sources.* names its body calls.
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                    if call.func.id in imported:
                        mods.add(imported[call.func.id])

    return {m: os.path.join(RAILWAY, "sources", m + ".py") for m in mods}


def _literal_health_ids(path):
    """Literal first arguments to report_source_health(...) in one file."""
    if not os.path.exists(path):
        return set()
    with open(path) as fh:
        body = fh.read()
    return set(re.findall(
        r"""report_source_health\(\s*["']([^"']+)["']""", body))


def cron_collector_registrations():
    """[(source_id, callable_name)] from cron.py's collector loop."""
    with open(CRON) as fh:
        src = fh.read()
    return re.findall(r'\(\s*"([a-z0-9_]+)"\s*,\s*(\w+)\s*\)\s*,', src)


def collectors_reporting_under_several_ids():
    """[(source_id, module, extra_ids)] — the findings. Empty is the clean tree."""
    with open(CRON) as fh:
        src = fh.read()
    tree = ast.parse(src)
    findings = []
    for source_id, func_name in cron_collector_registrations():
        for module, path in _module_paths_for(func_name, src, tree).items():
            ids = _literal_health_ids(path)
            extras = ids - {source_id}
            if extras:
                findings.append((source_id, module, sorted(extras)))
    return findings


class OneCollectorReportsUnderOneId(unittest.TestCase):
    def test_no_collector_posts_health_under_a_second_id(self):
        findings = collectors_reporting_under_several_ids()
        self.assertEqual(
            findings, [],
            "One collector, two source ids. Each finding is a collector cron "
            "registers under one id whose own module posts health under "
            "another, so it writes two ledger rows per run, is counted twice "
            "in ops_status [2]'s OK total, and may show an unlabelled row on "
            "the public Health page:\n" + "\n".join(
                f"  cron registers {sid!r} -> sources/{mod}.py also posts "
                f"under {extra}" for sid, mod, extra in findings))

    def test_the_loop_is_still_parseable(self):
        # A guard that silently finds nothing to check is not a passing guard.
        # If the loop is reshaped so this regex stops matching, the test above
        # would go vacuously green — so assert the registrations are still read.
        regs = cron_collector_registrations()
        self.assertGreaterEqual(
            len(regs), 5,
            "cron.py's collector loop no longer parses into (id, callable) "
            "pairs, so this guard is inspecting nothing. Re-point it at the "
            "loop rather than deleting it.")
        self.assertIn("warn_mn_letters", [sid for sid, _ in regs],
                      "the known duplicate-id instance is no longer registered; "
                      "if the collector was removed, retire this anchor "
                      "deliberately rather than letting the guard lose its "
                      "only module-owned-health subject.")

    def test_a_module_owned_health_note_is_actually_being_inspected(self):
        # THE SCAN MUST NOT SHARE ITS TARGET'S BLIND SPOT. A clean zero is
        # worthless if the resolver never reaches any file that posts health.
        # Exactly one cron-loop module owns its terminal note today; if that
        # stops being true the resolver is broken, not the tree.
        with open(CRON) as fh:
            src = fh.read()
        tree = ast.parse(src)
        inspected = {}
        for source_id, func_name in cron_collector_registrations():
            for module, path in _module_paths_for(func_name, src, tree).items():
                ids = _literal_health_ids(path)
                if ids:
                    inspected[module] = sorted(ids)
        self.assertTrue(
            inspected,
            "the resolver reached no cron-loop module that posts health under "
            "a literal id, so the duplicate-id check above proves nothing. "
            "sources/warn_mn_letters.py owns its own note and must be reached.")
        self.assertEqual(inspected.get("warn_mn_letters"), ["warn_mn_letters"])


if __name__ == "__main__":
    unittest.main()
