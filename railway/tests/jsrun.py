"""Run named functions out of layoffs.js, for real, in node.

WHY THIS EXISTS. Every other front-end test in this suite pins SOURCE
PROPERTIES, because there is no JS runtime here. That is a real limitation and
it has bitten: an adversarial sweep on 2026-08-04 found five checks in these
two repos that passed against defective code for the wrong reason, and two of
them were string checks that matched a COMMENT describing a call instead of the
call. A regex cannot tell those apart. Node can.

WHAT IT DOES. layoffs.js is one big IIFE, so its internals are not exportable.
This lifts the source text of the functions you name, concatenates it with a
small preamble of stubs, evaluates it in node, and returns whatever your
expression produced as JSON. The function bodies are the real ones, byte for
byte, straight off disk. If a function is renamed or deleted the extraction
raises rather than quietly testing nothing.

WHAT IT DOES NOT DO. It does not build a DOM. Anything touching the page has to
be stubbed by the caller, and a caller that stubs away the thing under test is
back to proving nothing, so keep the stubs to plumbing.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
JS_PATH = PLUGIN / "assets/layoffs.js"

NODE = shutil.which("node")


def require_node(test):
    if not NODE:
        raise unittest.SkipTest("node is not installed; cannot execute layoffs.js")


def extract(name, src=None):
    """Source text of one `function <name>(` declaration in layoffs.js.

    Brace-matched, so a nested function or an object literal inside the body
    does not truncate it. Raises if the name is absent: a test that silently
    extracted nothing would pass for the worst possible reason.
    """
    src = JS_PATH.read_text() if src is None else src
    needle = "function %s(" % name
    start = src.find(needle)
    if start == -1:
        raise AssertionError("layoffs.js has no `%s`" % needle)
    if src.find(needle, start + 1) != -1:
        raise AssertionError("`%s` appears more than once in layoffs.js" % needle)
    i = src.index("{", start)
    depth, j = 0, i
    in_s = in_d = in_line = in_block = in_re = False
    while j < len(src):
        c = src[j]
        prev = src[j - 1] if j else ""
        if in_line:
            if c == "\n":
                in_line = False
        elif in_block:
            if c == "/" and prev == "*":
                in_block = False
        elif in_s:
            if c == "'" and prev != "\\":
                in_s = False
        elif in_d:
            if c == '"' and prev != "\\":
                in_d = False
        elif in_re:
            if c == "/" and prev != "\\":
                in_re = False
        elif c == "/" and src[j + 1:j + 2] == "/":
            in_line = True
        elif c == "/" and src[j + 1:j + 2] == "*":
            in_block = True
        elif c == "'":
            in_s = True
        elif c == '"':
            in_d = True
        elif c == "/" and src[:j].rstrip()[-1:] in "(,=:[!&|?{};" :
            in_re = True
        else:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return src[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


def run(names, preamble, expression, src=None, optional=()):
    """Evaluate `expression` with the named real functions in scope.

    `optional` names are included when present and skipped when not. That
    matters when the same test is pointed at a tree from before the helper
    existed: without it the test aborts on the missing symbol, which proves
    only that a name is absent. With it, the tree's OWN renderer runs and the
    assertion fails on the wrong number it actually produces.

    Returns the parsed JSON of the expression's value.
    """
    require_node(None)
    text = JS_PATH.read_text() if src is None else src
    present = [n for n in optional if ("function %s(" % n) in text]
    bodies = "\n".join(extract(n, src) for n in list(names) + present)
    script = "%s\n%s\nconsole.log(JSON.stringify(%s));\n" % (preamble, bodies, expression)
    proc = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError("node failed:\n%s" % proc.stderr.strip())
    return json.loads(proc.stdout)


# Plumbing every extracted function tends to need. Deliberately tiny: these are
# the page's formatting and clock helpers, not any logic under test.
BASE_PREAMBLE = """
var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function pad2(n) { return (n < 10 ? '0' : '') + n; }
function fmt(n) { return (n == null) ? '' : Number(n).toLocaleString('en-US'); }
function daysInMonth(y, m) { return new Date(y, m, 0).getDate(); }
function monthLabel(k) {
    var p = String(k).split('-');
    return MONTHS[parseInt(p[1], 10) - 1] + ' ' + p[0];
}
var CONTROLS = {};
function readControl(id) { return Object.prototype.hasOwnProperty.call(CONTROLS, id) ? CONTROLS[id] : ''; }
function selectedList(id) { var v = readControl(id); return Array.isArray(v) ? v : (v ? [v] : []); }
"""
