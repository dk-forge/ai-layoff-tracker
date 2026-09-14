"""AN UNREACHABLE HOST MUST NOT KILL A DEPLOY STEP BEFORE IT CAN SAY SO.

WHY THIS FILE EXISTS. Three verification steps in deploy-plugin.yml run a
checker that answers in three states: 0 PASS, 2 FAIL (the site answered and
the answer is wrong, which fails the deploy) and 3 UNKNOWN (the site could not
be reached, which is a warning, because a host outage must not manufacture red
runs that manufacture alerts that also fail). Each step reads `STATUS=$?` and
branches on it. Each step also opens with `set -uo pipefail` and nothing else,
and GitHub runs `run:` blocks under `bash -e {0}`. Under errexit a command
that exits 3 ends the step right there, before `STATUS=$?` is reached, with
exit code 3 and no annotation at all. That is exactly what reddened the
2.20.191 and 2.20.192 deploys on 2026-09-12/13: the host was behind a bot
wall, the checker said UNKNOWN, and the step died silently instead of warning.
The alert ledger then carried the old bare `AssertionError` and
`JSONDecodeError` causes this checker was written to replace.

WHAT IS PINNED. Every `run:` block in deploy-plugin.yml that reads `STATUS=$?`
must switch errexit off (`set +e`) before the command it measures, so the
three-state contract the step documents is the contract the step keeps.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "deploy-plugin.yml"


def _run_blocks(text):
    """Every `run: |` block scalar, as (step name, body) pairs."""
    out = []
    name = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"\s*- name: (.+)$", line)
        if m:
            name = m.group(1).strip()
        m = re.match(r"^(\s*)run: \|\s*$", line)
        if m:
            indent = len(m.group(1))
            body = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or
                                      len(lines[i]) - len(lines[i].lstrip()) > indent):
                body.append(lines[i])
                i += 1
            out.append((name, "\n".join(body)))
            continue
        i += 1
    return out


class AStepThatReadsStatusMustNotRunUnderErrexit(unittest.TestCase):
    def test_every_status_reading_step_turns_errexit_off_first(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        blocks = [(n, b) for n, b in _run_blocks(text) if "STATUS=$?" in b]
        self.assertGreaterEqual(len(blocks), 3, "the three verification steps must still be here")
        for name, body in blocks:
            status_at = body.index("STATUS=$?")
            plus_e = body.find("set +e")
            self.assertNotEqual(plus_e, -1,
                                f"step {name!r} reads STATUS=$? but never runs `set +e`; "
                                "under GitHub's `bash -e` a checker that exits 3 (UNKNOWN) "
                                "kills the step before the branch that would warn")
            self.assertLess(plus_e, status_at,
                            f"step {name!r} must switch errexit off BEFORE the command it measures")
            self.assertNotRegex(body, r"set -[a-z]*e[a-z]*\b(?!.*set \+e)",
                                f"step {name!r} re-enables errexit after switching it off")


if __name__ == "__main__":
    unittest.main()
