"""No workflow reports a broken pipe as a failed step.

WHAT HAPPENED (2026-09-09, `FTPS target probe` run 34331498772).

The probe did its job. It established that no credential in this repository
authenticates against the new host, printed that finding, and then died on the
line that printed it:

    echo "$OUT" | head -2 | cut -c1-160

`head` exits after two lines and closes its end of the pipe. `echo` is still
writing, gets EPIPE, and dies 141. `set -o pipefail` reads the highest exit
code in the pipeline, so the step failed, so the workflow went red, so
`ci-alert.py` mailed the owner an alarm about a diagnostic that had succeeded.

A diagnostic that goes red for successfully diagnosing something is worse than
a broken diagnostic, because it trains the reader to discount the channel.

WHY NOTHING CAUGHT IT.

It is a RACE, not a rule. The pipe has a buffer, so a producer whose whole
output fits in it finishes before the consumer exits and never sees EPIPE. Most
of the time, on most output sizes, `cmd | head` is fine. That is precisely what
makes it dangerous: a workflow can carry the pattern for months of green runs
and fail on the one run whose output crossed the buffer. Small output is not
safety, it is a longer fuse.

THE RULE THIS ENFORCES.

Inside a `run:` block with pipefail enabled (by `set -o pipefail` in the body,
or by a `shell: bash -eo pipefail {0}` on the step), no pipeline may place an
EARLY-EXITING consumer anywhere after the first position. Position matters and
position is the whole test: `grep -m1 pattern file | tr -d x` is safe because
the early exiter reads a file and has no upstream to signal, while
`cat file | grep -m1 pattern` is not.

THE FIX IS NEVER TO DROP PIPEFAIL.

pipefail is here because this repo has been bitten from the other side: a
`pytest | tail && git push` that pushed a red tree, because `tail` succeeded and
the exit code that mattered was thrown away. Removing pipefail to quiet a broken
pipe trades a loud harmless failure for a silent harmful one, which is the worse
of the two trades. The house fix is to truncate without a pipe:

    printf '%s\\n' "$(printf '%s' "$OUT" | tr -d '\\n' | cut -c1-160)"

or to guard the pipeline explicitly, or to give the early exiter a file rather
than a producer. All three keep pipefail.

WHAT THIS TEST CANNOT SEE. It reads shell as text, so it judges the commands it
knows. A `python3 -c` that reads only part of stdin, or an `awk` that calls
`exit`, is the same defect and is not detectable from the command name alone.
Add it to EARLY_EXITING when a new one bites, and do NOT answer a finding by
widening ALLOWED without a reason that says why that particular pipeline cannot
race.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

#: Commands that stop reading before their input ends, so an upstream producer
#: can be handed EPIPE. Each entry is (name, predicate over the argument list).
#: `tail` is deliberately absent: it must read to end of input to know what the
#: end is, including `tail -n +K`. `cut`, `tr`, `wc`, `sort` and `awk` without an
#: `exit` all consume everything and are safe in a terminal position.
def _head_exits_early(args):
    # `head` always stops after its count. There is no form that reads to EOF.
    return True


def _grep_exits_early(args):
    joined = " ".join(args)
    if re.search(r"(^|\s)-[a-zA-Z]*[qlm]", joined):
        return True
    return "--quiet" in args or "--silent" in args or "--files-with-matches" in args or any(
        a.startswith("--max-count") for a in args)


def _sed_exits_early(args):
    # A `q`/`Q` command anywhere in the script stops sed before end of input.
    return any(re.search(r"\bq\b|;\s*q|\dq|Q", a) for a in args if not a.startswith("-")) or any(
        re.search(r"q\s*'?$|q;|\bQ\b", a) for a in args)


EARLY_EXITING = {
    "head": _head_exits_early,
    "grep": _grep_exits_early,
    "egrep": _grep_exits_early,
    "fgrep": _grep_exits_early,
    "zgrep": _grep_exits_early,
    "sed": _sed_exits_early,
}

#: Genuine exceptions. Key is "<workflow file>:<line>", value is the REASON,
#: which is required and is checked for being non-empty. A blanket file-level
#: exemption is deliberately not expressible here: the unit is one line.
ALLOWED = {}


#: A pipeline is cut at these; everything else is ordinary text.
_SEPARATORS = ";\n&()"


def pipelines(body):
    """Split a `run:` block into pipelines, each a list of (lineno, segment).

    A small shell tokenizer rather than a regex, because the two shapes that
    matter both defeat text matching. A pipe can sit inside a command
    substitution that is itself inside double quotes:

        echo "lftp already present: $(lftp --version | head -1)"

    and a quoted argument can span physical lines, so the pipe that closes it
    arrives on a line that starts mid-string:

        lftp -c "
          open ...;
        " 2>&1 | head -40

    Both are real findings in this repo and both are invisible to a
    line-at-a-time reader. Quote state is therefore tracked across the whole
    block, and `$(...)` reopens an unquoted context so its contents are read as
    the script they are.
    """
    text_lines = [t for _, t in body]
    first_lineno = body[0][0] if body else 1
    text = "\n".join(text_lines)

    stack = ["root"]
    line = first_lineno
    seg, seg_line = "", line
    pipeline, out = [], []

    def flush_segment():
        nonlocal seg, seg_line
        if seg.strip():
            pipeline.append((seg_line, seg.strip()))
        seg, seg_line = "", line

    def flush_pipeline():
        nonlocal pipeline
        flush_segment()
        if len(pipeline) > 1:
            out.append(pipeline)
        pipeline = []

    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            line += 1
        top = stack[-1]

        if top == "squote":
            if ch == "'":
                stack.pop()
            seg += ch
            i += 1
            continue

        if top == "dquote":
            if ch == "\\" and i + 1 < len(text):
                seg += text[i:i + 2]
                i += 2
                continue
            if ch == '"':
                stack.pop()
                seg += ch
                i += 1
                continue
            if text.startswith("$(", i):
                stack.append("subst")
                flush_pipeline()
                i += 2
                seg_line = line
                continue
            seg += ch
            i += 1
            continue

        # unquoted
        if ch == "\\" and i + 1 < len(text):
            if text[i + 1] == "\n":
                line += 1
                seg += " "
                i += 2
                continue
            seg += text[i:i + 2]
            i += 2
            continue
        if ch == "#" and (not seg or seg[-1].isspace()):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if ch == "'":
            stack.append("squote")
            seg += ch
            i += 1
            continue
        if ch == '"':
            stack.append("dquote")
            seg += ch
            i += 1
            continue
        if text.startswith("$(", i):
            stack.append("subst")
            flush_pipeline()
            i += 2
            seg_line = line
            continue
        if ch == ")" and stack[-1] == "subst":
            stack.pop()
            flush_pipeline()
            i += 1
            seg_line = line
            continue
        if text.startswith("||", i) or text.startswith("&&", i):
            flush_pipeline()
            i += 2
            seg_line = line
            continue
        if ch == "|":
            flush_segment()
            i += 1
            seg_line = line
            continue
        if ch in _SEPARATORS:
            flush_pipeline()
            i += 1
            seg_line = line
            continue
        if not seg.strip() and ch.isspace():
            seg_line = line
        seg += ch
        i += 1

    flush_pipeline()
    return out


def run_blocks(path):
    """Every `run:` block scalar in a workflow, as (start_line, [(lineno, text)]).

    A hand-rolled block-scalar reader rather than PyYAML, which this repo does
    not install and which would throw the line numbers away anyway. The finding
    has to name a line or it is not actionable.
    """
    lines = path.read_text().splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:-\s+)?run:\s*(?:\|[-+]?|>[-+]?)\s*$", lines[i])
        if not m:
            i += 1
            continue
        key_indent = len(m.group(1))
        body, body_indent, j = [], None, i + 1
        while j < len(lines):
            raw = lines[j]
            if not raw.strip():
                body.append((j + 1, ""))
                j += 1
                continue
            indent = len(raw) - len(raw.lstrip())
            if body_indent is None:
                if indent <= key_indent:
                    break
                body_indent = indent
            if indent < body_indent:
                break
            body.append((j + 1, raw[body_indent:]))
            j += 1
        blocks.append((i + 1, body))
        i = j
    return blocks


def _step_sets_pipefail_via_shell(path, run_line):
    """A `shell: bash -eo pipefail {0}` on the same step enables it without `set`."""
    lines = path.read_text().splitlines()
    # Walk back to the start of the step (the `- ` bullet) and look for `shell:`.
    for k in range(run_line - 2, -1, -1):
        stripped = lines[k].strip()
        if re.match(r"^-\s+(name|uses|id|shell|run|env|with|if):", stripped):
            break
    start = max(k, 0)
    for k in range(start, min(run_line + 1, len(lines))):
        if "shell:" in lines[k] and "pipefail" in lines[k]:
            return True
    return False


def _logical_commands(body):
    """Join `\\`-continued lines, then yield (lineno, single_command_text)."""
    joined, pending, first_line = [], "", None
    for lineno, text in body:
        stripped = text.rstrip()
        if pending:
            first_line = first_line or lineno
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            first_line = first_line or lineno
            continue
        joined.append((first_line or lineno, pending + stripped))
        pending, first_line = "", None
    if pending:
        joined.append((first_line or body[-1][0], pending))
    return joined


class Finding(object):
    def __init__(self, workflow, line, command, pipeline):
        self.workflow, self.line = workflow, line
        self.command, self.pipeline = command, pipeline

    @property
    def key(self):
        return "%s:%d" % (self.workflow, self.line)

    def __str__(self):
        return "%s  `%s` consumes early in: %s" % (self.key, self.command, self.pipeline.strip())


def scan_workflow(path):
    findings = []
    for block_start, body in run_blocks(path):
        if not body:
            continue
        text = "\n".join(t for _, t in body)
        pipefail = bool(re.search(
            r"^\s*set\s+-\S*o\S*\s+pipefail|^\s*set\s+-o\s+pipefail", text, re.M)
        ) or _step_sets_pipefail_via_shell(path, block_start)
        if not pipefail:
            continue
        for pipeline in pipelines(body):
            for position, (lineno, segment) in enumerate(pipeline):
                if position == 0:
                    # No upstream, so nothing to hand EPIPE to.
                    continue
                words = segment.split()
                if not words:
                    continue
                name = words[0].split("/")[-1]
                predicate = EARLY_EXITING.get(name)
                if predicate and predicate(words[1:]):
                    findings.append(Finding(path.name, lineno, name, segment))
    return findings


def scan_workflows():
    findings = []
    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        findings.extend(scan_workflow(path))
    return findings


class PipefailNeverMeetsAnEarlyExitingConsumer(unittest.TestCase):
    def test_no_pipefail_block_pipes_into_an_early_exiting_command(self):
        offenders = [f for f in scan_workflows() if f.key not in ALLOWED]
        self.assertEqual(
            [], [str(f) for f in offenders],
            "A pipeline under `set -o pipefail` ends in a command that stops "
            "reading early, so its producer can die on EPIPE and redden a step "
            "that did its job. Truncate without a pipe (command substitution "
            "plus `cut`), or give the early exiter a file instead of a "
            "producer. Do NOT remove pipefail: see this module's docstring.")

    def test_every_allowlist_entry_carries_a_reason(self):
        for key, reason in ALLOWED.items():
            with self.subTest(entry=key):
                self.assertRegex(key, r"^[\w.\-]+\.ya?ml:\d+$",
                                 "an allowlist key is one workflow line")
                self.assertTrue(reason and reason.strip(),
                                "an exception needs a reason saying why that "
                                "pipeline cannot race")

    def test_every_allowlist_entry_still_points_at_a_finding(self):
        """A stale exemption is an exemption nobody has read. Fail on it."""
        live = {f.key for f in scan_workflows()}
        for key in ALLOWED:
            with self.subTest(entry=key):
                self.assertIn(key, live,
                              "allowlisted line no longer has the defect, so "
                              "the entry should be deleted")

    def test_the_scanner_finds_the_defect_it_was_written_for(self):
        """The mutation, pinned. A guard that has never caught its own defect
        is untested, so the original failing line lives here as a fixture."""
        import tempfile
        original = (
            "jobs:\n"
            "  probe:\n"
            "    steps:\n"
            "      - name: report\n"
            "        run: |\n"
            "          set -uo pipefail\n"
            '          echo "$OUT" | head -2 | cut -c1-160\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "mutant.yml"
            path.write_text(original)
            findings = scan_workflow(path)
        self.assertEqual(1, len(findings), "the original defect must be caught")
        self.assertEqual("head", findings[0].command)
        self.assertEqual(7, findings[0].line)

    def test_an_early_exiter_reading_a_file_is_not_a_finding(self):
        """`grep -m1 ... file | grep -oE ...` has no upstream to signal."""
        import tempfile
        safe = (
            "jobs:\n"
            "  j:\n"
            "    steps:\n"
            "      - run: |\n"
            "          set -uo pipefail\n"
            "          V=$(grep -m1 -oE \"ALT_VERSION\" probe.php | grep -oE '[0-9.]+$')\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "safe.yml"
            path.write_text(safe)
            self.assertEqual([], [str(f) for f in scan_workflow(path)])


if __name__ == "__main__":
    unittest.main()
