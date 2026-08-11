"""Loading, loaded, failed: the three states every async region has to reach.

WHY THIS FILE EXISTS. The owner read both dashboards on 2026-08-10 and reported
that the page "looks stalled while data loads". Measured against the code, he
was describing something exact: a filter change fired /query and /aggregate and
then left the previous numbers on screen, fully styled, with no indication that
anything was happening. The table set aria-busy and nothing else; the tiles, the
charts, the at-a-glance board and the facet dropdowns set nothing at all. A
reader could not tell a slow host from a finished page.

THE THIRD STATE IS THE ONE THAT MATTERS HERE. This codebase has hit the same
defect class repeatedly and has a name for it: a mechanism that looks alive
while doing nothing. An indicator that spins forever is that defect with a
sprite on it. So the assertions below are weighted toward the failure path:
that a rejected fetch lands in a VISIBLE error state, that a request which
never answers is given up on rather than spun over, that the abandoned request
is actually aborted instead of left in flight, and that the failed state offers
a way back rather than needing a page reload.

HOW IT MATCHES, AND WHY IT IS NOT ALL REGEX. An adversarial sweep in this repo
found checks passing against defective code because they matched a COMMENT that
described a call rather than the call. Two defences here:

  * every string assertion runs against source with comments stripped, using
    railway/style_check.py's own stripper (the one the style test proves works);
  * the state machine itself is not grepped at all. jsrun.extract lifts the real
    bodies of busyBegin / busyClear / busyFail / busyTrack off disk, and they
    are executed in node against a stub document. The stubs are plumbing (a
    node with a class list, a child list and attributes); nothing that decides
    a state is stubbed, which is the line between running the code and running
    a mock of it.

PROVEN TO FAIL ON THE PRE-FIX TREE. Every test in this file was run against
origin/main@a191e92, the commit this change starts from. All 16 failed there:
the four state-machine functions and the CSS class do not exist on that tree, so
jsrun.extract raises rather than silently testing nothing, and the wiring and
stylesheet assertions have nothing to match.
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
JS_PATH = PLUGIN / "assets/layoffs.js"
CSS_PATH = PLUGIN / "assets/layoffs.css"
TPL_PATH = PLUGIN / "templates/page-tracker.php"

sys.path.insert(0, str(ROOT / "railway"))
import style_check as sc                                        # noqa: E402

JS = sc.strip_comments(JS_PATH.read_text(encoding="utf-8"), "js")
TPL = sc.strip_comments(TPL_PATH.read_text(encoding="utf-8"), "php")
CSS = re.sub(r"/\*.*?\*/", " ", CSS_PATH.read_text(encoding="utf-8"), flags=re.S)

# The regions a reader watches while a fetch is in flight, and the id each one
# is marked busy under. Adding an async surface without adding it here is the
# regression this list exists to catch.
REGIONS = {
    "alt-stats-bar": "the headline tiles",
    "alt-minigrid": "the chart grid",
    "alt-cards": "the results table",
    "alt-narrative": "the at-a-glance board",
    "alt-filterbar-body": "the facet dropdowns",
}

STATE_FNS = ["busyOverlay", "busyBegin", "busyClear", "busyFail", "busyTrack"]

# A document stub, and only a document stub. Everything that decides which of
# the three states a region is in comes off disk.
DOM_STUB = r"""
var LOAD_TIMEOUT_MS = 40;      /* the real constant is asserted separately */
var LOAD_MIN_H = 132;
var BUSY = {};
var BUSY_TOKEN = 0;
var REG = {};

function makeEl(tag) {
    var el = { tagName: tag, children: [], attrs: {}, style: {}, parentNode: null,
               hidden: false, offsetHeight: 0, textContent: '', _cls: {} };
    el.classList = {
        add: function (c) { el._cls[c] = 1; },
        remove: function (c) { delete el._cls[c]; },
        contains: function (c) { return !!el._cls[c]; }
    };
    el.setAttribute = function (k, v) { el.attrs[k] = String(v); };
    el.getAttribute = function (k) {
        return Object.prototype.hasOwnProperty.call(el.attrs, k) ? el.attrs[k] : null;
    };
    el.appendChild = function (c) { c.parentNode = el; el.children.push(c); return c; };
    el.removeChild = function (c) {
        var i = el.children.indexOf(c);
        if (i > -1) { el.children.splice(i, 1); c.parentNode = null; }
        return c;
    };
    el.querySelector = function (sel) {
        var want = String(sel).replace(/^\./, '');
        for (var i = 0; i < el.children.length; i++) {
            if (el.children[i]._cls[want]) return el.children[i];
        }
        return null;
    };
    Object.defineProperty(el, 'className', {
        get: function () { return Object.keys(el._cls).join(' '); },
        set: function (v) {
            el._cls = {};
            String(v).split(/\s+/).forEach(function (c) { if (c) el._cls[c] = 1; });
        }
    });
    Object.defineProperty(el, 'innerHTML', {
        get: function () { return ''; },
        set: function (html) {
            el.children = [];
            var re = /<(\w+)([^>]*)>/g, m;
            while ((m = re.exec(html))) {
                var attrs = m[2] || '';
                var child = makeEl(m[1]);
                var cm = /class="([^"]*)"/.exec(attrs);
                if (cm) child.className = cm[1];
                if (/\bhidden\b/.test(attrs.replace(/class="[^"]*"/, ''))) child.hidden = true;
                el.appendChild(child);
            }
        }
    });
    return el;
}

var document = { getElementById: function (id) { return REG[id] || null; },
                 createElement: makeEl };
var window = { requestAnimationFrame: function (f) { setTimeout(f, 0); } };

function region(id, height) {
    var el = makeEl('div');
    el.offsetHeight = height || 0;
    REG[id] = el;
    return el;
}

// What a reader and a screen reader can actually tell about a region.
function snapshot(id) {
    var el = REG[id];
    var ov = null;
    for (var i = 0; i < el.children.length; i++) {
        if (el.children[i]._cls['alt-load']) ov = el.children[i];
    }
    return {
        ariaBusy: el.getAttribute('aria-busy'),
        minHeight: el.style.minHeight || '',
        hostClass: el.classList.contains('alt-load-host'),
        overlay: !ov ? null : {
            role: ov.getAttribute('role'),
            failed: ov.classList.contains('alt-load-failed'),
            message: (ov.querySelector('.alt-load-msg') || {}).textContent,
            spinner: !!ov.querySelector('.alt-load-spin'),
            retryHidden: (ov.querySelector('.alt-load-retry') || {}).hidden
        }
    };
}
"""


def js_states(scenario_body):
    """Run the real state machine in node and return its JSON report."""
    jsrun.require_node(None)
    bodies = "\n".join(jsrun.extract(n) for n in STATE_FNS)
    script = "%s\n%s\n(async function () {\n%s\n})().then(function (out) {\n  console.log(JSON.stringify(out));\n}, function (e) {\n  console.error(e && e.stack || e); process.exit(1);\n});\n" % (
        DOM_STUB, bodies, scenario_body)
    proc = subprocess.run([jsrun.NODE, "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError("node failed:\n%s" % proc.stderr.strip())
    return json.loads(proc.stdout)


class LoadingStateMachineTests(unittest.TestCase):
    """The three states, run for real."""

    def setUp(self):
        jsrun.require_node(self)

    def test_the_loading_state_says_so_and_marks_the_region_busy(self):
        out = js_states("""
            region('r', 300);
            var never = new Promise(function () {});
            busyTrack('r', 'Loading the totals', function () { return never; }, null);
            return snapshot('r');
        """)
        self.assertEqual(out["ariaBusy"], "true",
                         "a region whose content is stale must say so to assistive tech")
        self.assertIsNotNone(out["overlay"], "nothing visible said the page was working")
        self.assertEqual(out["overlay"]["role"], "status",
                         "the indicator must be announced, not merely drawn")
        self.assertEqual(out["overlay"]["message"], "Loading the totals")
        self.assertFalse(out["overlay"]["failed"])
        self.assertTrue(out["overlay"]["retryHidden"],
                        "a retry offered while the request is still running invites a double fetch")

    def test_the_loading_state_reserves_the_space_it_is_using(self):
        # An empty region on first paint gets the floor; a region that already
        # has content keeps its own height. Either way the content that arrives
        # does not move the page.
        out = js_states("""
            region('empty', 0); region('full', 480);
            var never = new Promise(function () {});
            busyTrack('empty', 'Loading', function () { return never; }, null);
            busyTrack('full', 'Loading', function () { return never; }, null);
            return { empty: snapshot('empty'), full: snapshot('full') };
        """)
        self.assertEqual(out["empty"]["minHeight"], "132px")
        self.assertEqual(out["full"]["minHeight"], "480px")
        self.assertTrue(out["empty"]["hostClass"] and out["full"]["hostClass"])

    def test_the_loaded_state_removes_the_indicator_and_the_reservation(self):
        out = js_states("""
            region('r', 300);
            await busyTrack('r', 'Loading', function () { return Promise.resolve({ ok: 1 }); }, null);
            await new Promise(function (res) { setTimeout(res, 5); });
            return snapshot('r');
        """)
        self.assertIsNone(out["overlay"], "the indicator outlived the data it was waiting for")
        self.assertEqual(out["ariaBusy"], "false")
        self.assertFalse(out["hostClass"])
        self.assertEqual(out["minHeight"], "",
                         "the reserved height has to be released or the region can never shrink")

    def test_a_failed_fetch_lands_in_a_visible_error_state_with_a_way_out(self):
        out = js_states("""
            region('r', 300);
            var retried = 0;
            try {
                await busyTrack('r', 'Loading', function () {
                    return Promise.reject(new Error('HTTP 500'));
                }, function () { retried += 1; });
            } catch (e) { /* the caller still sees the rejection */ }
            var before = snapshot('r');
            var ov = REG['r'].children[0];
            ov.querySelector('.alt-load-retry').onclick();
            return { before: before, after: snapshot('r'), retried: retried };
        """)
        self.assertIsNotNone(out["before"]["overlay"], "a failed fetch left nothing on screen")
        self.assertTrue(out["before"]["overlay"]["failed"])
        self.assertEqual(out["before"]["overlay"]["message"], "We could not load this data.")
        self.assertEqual(out["before"]["ariaBusy"], "false",
                         "a region that has given up must stop claiming to be working")
        self.assertFalse(out["before"]["overlay"]["retryHidden"],
                         "an error with no retry makes a page reload the only way out")
        self.assertEqual(out["retried"], 1)
        self.assertIsNone(out["after"]["overlay"],
                          "retrying has to clear the error it is retrying")

    def test_a_request_that_never_answers_is_given_up_on_and_aborted(self):
        # THE DEFECT THIS FILE EXISTS FOR. A promise that never settles used to
        # mean an indicator that never stops. It now has a deadline, the state
        # says the data could not be loaded, a retry is offered, and the request
        # behind it is cancelled rather than left running.
        out = js_states("""
            region('r', 300);
            var seen = null, retried = 0;
            busyTrack('r', 'Loading', function (signal) {
                seen = signal;
                return new Promise(function () {});
            }, function () { retried += 1; });
            await new Promise(function (res) { setTimeout(res, 120); });
            var snap = snapshot('r');
            REG['r'].children[0].querySelector('.alt-load-retry').onclick();
            return { snap: snap, aborted: !!(seen && seen.aborted), retried: retried,
                     gotSignal: !!seen };
        """)
        self.assertTrue(out["gotSignal"], "no signal reached the request, so nothing could cancel it")
        self.assertIsNotNone(out["snap"]["overlay"])
        self.assertTrue(out["snap"]["overlay"]["failed"],
                        "the indicator was still in its loading state after the deadline")
        self.assertEqual(out["snap"]["overlay"]["message"], "This is taking longer than usual.")
        self.assertEqual(out["snap"]["ariaBusy"], "false")
        self.assertFalse(out["snap"]["overlay"]["retryHidden"])
        self.assertTrue(out["aborted"], "the abandoned request was left in flight")
        self.assertEqual(out["retried"], 1)

    def test_a_late_answer_cannot_resurrect_a_region_that_already_failed(self):
        # The response that arrives after the deadline belongs to a token the
        # region no longer holds, so it must not clear an error a reader is
        # currently looking at.
        out = js_states("""
            region('r', 300);
            var settle;
            var p = busyTrack('r', 'Loading', function () {
                return new Promise(function (res) { settle = res; });
            }, function () {});
            p.then(function () {}, function () {});
            await new Promise(function (res) { setTimeout(res, 120); });
            settle({ late: true });
            await new Promise(function (res) { setTimeout(res, 20); });
            return snapshot('r');
        """)
        self.assertIsNotNone(out["overlay"])
        self.assertTrue(out["overlay"]["failed"])

    def test_two_overlapping_begins_do_not_stack_two_indicators(self):
        out = js_states("""
            region('r', 300);
            var never = new Promise(function () {});
            busyTrack('r', 'Loading the records', function () { return never; }, null);
            busyTrack('r', 'Loading the records', function () { return never; }, null);
            var n = 0;
            REG['r'].children.forEach(function (c) { if (c._cls['alt-load']) n += 1; });
            return { overlays: n, minHeight: REG['r'].style.minHeight };
        """)
        self.assertEqual(out["overlays"], 1)
        self.assertEqual(out["minHeight"], "300px",
                         "a second begin re-measured a region it had already covered")


class WiringTests(unittest.TestCase):
    """Every async surface is actually wired, in the shipped source."""

    def test_every_async_region_is_marked_busy_by_name(self):
        for rid, what in REGIONS.items():
            self.assertRegex(
                JS, r"busy(?:Track|Begin)\(\s*'%s'" % re.escape(rid),
                "%s (#%s) starts a fetch with no loading state" % (what, rid))

    def test_every_async_region_exists_in_the_template(self):
        for rid, what in REGIONS.items():
            self.assertIn('id="%s"' % rid, TPL,
                          "%s is marked busy under an id the page never renders" % what)

    def test_the_deadline_is_a_real_finite_number_in_the_shipped_source(self):
        m = re.search(r"var LOAD_TIMEOUT_MS\s*=\s*(\d+);", JS)
        self.assertTrue(m, "there is no deadline, so an unanswered fetch spins forever")
        ms = int(m.group(1))
        self.assertGreater(ms, 2000, "a deadline this short would fail healthy slow loads")
        self.assertLessEqual(ms, 30000, "a reader will not wait past half a minute for a verdict")

    def test_the_filter_path_is_covered_and_not_only_the_first_paint(self):
        # "Stalled" is felt hardest on a filter change, so the two functions a
        # filter change calls are the two that must carry the state.
        for fn in ("loadRows", "fetchAndRenderAggregate"):
            body = jsrun.extract(fn)
            self.assertIn("busy", sc.strip_comments(body, "js"),
                          "%s runs on every filter change with no loading state" % fn)

    def test_the_board_failure_no_longer_blanks_itself(self):
        # It used to `el.textContent = ''` on failure, which is indistinguishable
        # from a board with nothing to report.
        body = sc.strip_comments(jsrun.extract("updateNarrative"), "js")
        self.assertNotIn("el.textContent = ''", body)
        self.assertIn("busyFail('alt-narrative'", body)


class PresentationTests(unittest.TestCase):
    """No layout shift, no forced animation, no white box on a dark page."""

    def _rule(self, selector):
        i = CSS.find(selector)
        self.assertNotEqual(i, -1, "layoffs.css has no rule %r" % selector)
        j = CSS.index("{", i)
        depth, k = 0, j
        while k < len(CSS):
            if CSS[k] == "{":
                depth += 1
            elif CSS[k] == "}":
                depth -= 1
                if depth == 0:
                    return CSS[j + 1:k]
            k += 1
        raise AssertionError("unbalanced braces after %r" % selector)

    def test_the_overlay_takes_no_flow_space(self):
        body = self._rule(".alt-load {")
        self.assertRegex(body, r"position:\s*absolute",
                         "an in-flow indicator moves the content it is announcing")
        self.assertRegex(body, r"inset:\s*0")

    def test_reduced_motion_gets_a_state_and_not_an_animation(self):
        blocks = re.findall(r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\n\}",
                            CSS, flags=re.S)
        self.assertTrue(any(".alt-load-spin" in b and re.search(r"animation:\s*none", b)
                            for b in blocks),
                        "the indicator keeps spinning for a reader who asked it not to")
        # And the state never depended on the spinner: the message is a
        # separate element, so removing the animation removes nothing readable.
        self.assertIn("alt-load-msg", JS)

    def test_the_scrim_is_defined_in_all_three_theme_blocks(self):
        # A token defined in light and forgotten in dark silently keeps its
        # light value, which is a white panel over a dark page.
        self.assertEqual(len(re.findall(r"--alt-load-scrim\s*:", CSS)), 3)

    def test_the_failed_state_is_styled_as_a_state_not_as_a_spinner(self):
        self.assertRegex(CSS, r"\.alt-load-failed\s+\.alt-load-spin\s*\{[^}]*display:\s*none")


if __name__ == "__main__":
    unittest.main()
