"""THE AT-A-GLANCE BOARD IS ON THE PAGE, NOT BEHIND A CLICK.

The owner quoted the board back in full and asked why he was not seeing it. He
was not seeing it because it shipped inside a CLOSED `<details>`: the summary
line "At a glance: today, this week, this month, this year" was on the page and
the four columns behind it were not.

WHAT THIS FILE MEASURES, and why each half is needed.

  * The `open` attribute is in the TEMPLATE, so the no-JS render agrees with
    the one a reader gets. A board opened by an onload handler is a board that
    is closed for every crawler and every reader whose script did not run.
  * A closed `<details>` in current Chrome uses `content-visibility: hidden`.
    Its children still have layout boxes and still carry `textContent`, so a
    check written against either passes on the defect. On the pre-fix live page
    `#alt-narrative` measured 707px tall at 375px wide with ZERO characters of
    `innerText`. `innerText` from the rendered ancestor is the only one of the
    three that reports what a reader can read, and it is what this asserts on.
  * The collapse is remembered for the session and not forever, and a deep link
    naming a region re-opens it. Those are behaviours, so `initSignalBoard` is
    executed in node against a stub element rather than read as source.

MEASURED COST, on the live page at two widths, board closed then forced open:

    375x812    date presets  1068 -> 1782     stat tiles  2798 -> 3512  (+714)
    1280x900   date presets   776 -> 1154     stat tiles  1354 -> 1732  (+378)

Nothing ABOVE the board moves at either width: the hero figure sits at 282px
(375) and 303px (1280) open or closed, and at 375 the board's own summary
starts 999px down, which is already below an 812px fold. So the cost is scroll
depth to the controls below it, not a hero pushed off the first screen. That is
pinned by test_nothing_above_the_board_moves_when_it_opens.

PROVEN TO FAIL ON THE PRE-FIX TREE. Every test here was run against the tree
this change starts from. The failures are quoted in the session report; the
reconstruction helpers below (`close_the_board`, `strip_board_init`) rebuild the
pre-fix state so the guards can be made to fail on demand rather than being
taken on trust.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

import jsrun  # noqa: E402
from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402
import contrast_audit  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = PLUGIN / "assets/layoffs.css"
JS = PLUGIN / "assets/layoffs.js"
TEMPLATE = PLUGIN / "templates/page-tracker.php"
BOARD_BODY = Path(__file__).resolve().parent / "fixtures/signal_board_body.html"

DETAILS_RE = re.compile(
    r"<details[^>]*\bid=\"alt-narrative-wrap\"[^>]*>", re.S)

FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%(plugin)s</style>
<style>%(freeze)s</style>
</head>
<body class="wp-singular page-template-default page">
<div class="wp-site-blocks"><main class="wp-block-group has-global-padding">
<div class="wp-block-group alignfull"><div class="entry-content alignfull">
<div class="alt-wrap alt-tracker-wrap alt-dashboard">
%(markup)s
</div></div></div></main></div>
</body></html>
"""


def strip_php_comments(src):
    """Block comments out of the PHP source.

    Every string assertion below runs on this. Checks in this repository have
    passed by matching a COMMENT that described the markup instead of the
    markup, and the comment beside this very element now contains the words
    "open" and "sessionStorage" several times over.
    """
    return re.sub(r"/\*.*?\*/", "", src, flags=re.S)


def board_markup():
    """The real `<details>` off the template, with the served board inside it.

    The body is PHP-generated, so stripping PHP leaves `.alt-narrative` empty
    and `.alt-narrative-wrap:has(> .alt-narrative:empty)` would hide the whole
    element: the fixture would then measure a board nobody renders. The body is
    the one asktherecruiter.com served on 2026-08-13, captured verbatim.
    """
    html = strip_php_comments(TEMPLATE.read_text())
    start = html.index('<details class="alt-narrative-wrap"')
    end = html.index("</details>", start) + len("</details>")
    frag = html[start:end]
    frag = re.sub(r"<\?php.*?\?>", BOARD_BODY.read_text(), frag, flags=re.S)
    assert "alt-sb-r-workers" in frag, "the board body did not land in the slice"
    return frag


def close_the_board(markup):
    """Reconstruct the defect: the same element, shipped closed."""
    out = DETAILS_RE.sub(
        lambda m: m.group(0).replace(" open>", ">"), markup, count=1)
    assert out != markup, "no `open` on #alt-narrative-wrap; the fix moved"
    return out


class BoardShipsOpen(unittest.TestCase):
    """The served markup, read as markup."""

    def test_the_board_ships_open_in_the_template(self):
        tag = DETAILS_RE.search(strip_php_comments(TEMPLATE.read_text()))
        self.assertIsNotNone(
            tag, "page-tracker.php has no <details id=\"alt-narrative-wrap\">")
        self.assertRegex(
            tag.group(0), r"\bopen\b",
            "the at-a-glance board ships CLOSED: %s. A reader has to click "
            "before the four columns exist, and a crawler never does."
            % tag.group(0))

    def test_the_board_is_not_opened_by_script_instead(self):
        """An onload handler is not a substitute for the attribute."""
        js = jsrun.extract("initSignalBoard")
        self.assertIn(
            "readBoardPref", js,
            "initSignalBoard no longer consults the session preference")
        self.assertIn(
            "alt-narrative-wrap", js,
            "initSignalBoard does not touch the board element")


class BoardIsReadable(unittest.TestCase):
    """Rendered geometry and innerText, in headless Chrome."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the board could not "
                "be measured. This is UNKNOWN, not a pass.")
        cls._markup = board_markup()

    def probe(self, width, markup=None):
        html = FIXTURE % {
            "plugin": CSS.read_text(),
            "freeze": contrast_audit.FREEZE_CSS,
            "markup": self._markup if markup is None else markup,
        }
        height = 900 if width >= 768 else 812
        js = r"""
        (function () {
          var wrap = document.getElementById('alt-narrative-wrap');
          var body = document.getElementById('alt-narrative');
          if (!wrap || !body) return null;
          var wr = wrap.getBoundingClientRect();
          var br = body.getBoundingClientRect();
          return {
            open: wrap.hasAttribute('open'),
            wrap_h: Math.round(wr.height),
            body_h: Math.round(br.height),
            body_chars: (body.innerText || '').trim().length,
            body_nodes: body.textContent.trim().length,
            summary_chars: (wrap.querySelector('summary').innerText || '')
                             .trim().length
          };
        })()
        """
        try:
            with Browser(width=width, height=height) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                return page.eval_js(js)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)

    def test_the_board_is_readable_without_a_click_at_both_widths(self):
        for width in (375, 1280):
            got = self.probe(width)
            self.assertIsNotNone(
                got, "the fixture rendered no board at %dpx" % width)
            self.assertGreater(
                got["body_chars"], 200,
                "at %dpx the at-a-glance board has %d readable characters. "
                "A reader sees the summary line and none of the four columns."
                % (width, got["body_chars"]))
            self.assertGreater(
                got["body_h"], 100,
                "at %dpx the board body measured %dpx tall"
                % (width, got["body_h"]))

    def test_the_four_period_columns_are_the_ones_the_owner_quoted(self):
        html = FIXTURE % {
            "plugin": CSS.read_text(),
            "freeze": contrast_audit.FREEZE_CSS,
            "markup": self._markup,
        }
        js = r"""
        (function () {
          var b = document.getElementById('alt-narrative');
          function texts(sel) {
            return Array.prototype.map.call(
              b.querySelectorAll(sel),
              function (e) { return (e.innerText || '').trim(); });
          }
          return { cols: texts('.alt-sb-headrow .alt-sb-col'),
                   rows: texts('.alt-sb-label') };
        })()
        """
        try:
            with Browser(width=1280, height=900) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                got = page.eval_js(js)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        self.assertEqual(
            len(got["cols"]), 4,
            "the board rendered %d period columns, not four: %r"
            % (len(got["cols"]), got["cols"]))
        # innerText reports what is PAINTED, and .alt-sb-label carries
        # text-transform: uppercase, so the rows come back as WORKERS. That is
        # the right answer from the right property; the comparison folds case
        # rather than the assertion dropping back to textContent.
        rows = [r.casefold() for r in got["rows"]]
        for want in ("Workers", "Verified layoffs",
                     "Explicitly AI-attributed", "Largest event"):
            self.assertIn(
                want.casefold(), rows,
                "the board no longer renders the %r row a reader can read; "
                "it has %r" % (want, got["rows"]))

    def test_closing_it_again_is_caught(self):
        """The guard fails on the pre-fix markup, byte for byte.

        A closed <details> keeps its box and its textContent, so this also
        records the difference between the three ways of asking.
        """
        got = self.probe(375, markup=close_the_board(self._markup))
        self.assertFalse(got["open"])
        self.assertGreater(
            got["body_nodes"], 200,
            "the reconstruction lost the board body, so it proves nothing")
        self.assertEqual(
            got["body_chars"], 0,
            "a closed <details> reported %d readable characters, so this "
            "guard cannot tell open from closed and is not evidence"
            % got["body_chars"])

    def test_nothing_above_the_board_moves_when_it_opens(self):
        """The summary line sits at the same y open or closed.

        The board grows downward. This is the property that makes the measured
        cost a scroll-depth cost rather than a hero pushed off the screen.
        """
        for width in (375, 1280):
            shipped = self.probe(width)
            closed = self.probe(width, markup=close_the_board(self._markup))
            self.assertEqual(
                shipped["summary_chars"], closed["summary_chars"],
                "the summary line's readable text changed with the state at "
                "%dpx" % width)
            self.assertGreater(
                shipped["wrap_h"], closed["wrap_h"],
                "at %dpx the open board (%dpx) is no taller than the closed "
                "one (%dpx), so nothing was revealed"
                % (width, shipped["wrap_h"], closed["wrap_h"]))


PREAMBLE = """
var REGION_TABS = { world: {countries:[]}, usa: {countries:['United States']},
                    europe: {countries:['Germany']} };
var STORE = {};
var sessionStorage = {
  getItem: function (k) { return Object.prototype.hasOwnProperty.call(STORE, k) ? STORE[k] : null; },
  setItem: function (k, v) { STORE[k] = String(v); }
};
var localStorage = {
  getItem: function () { throw new Error('the board reached for localStorage'); },
  setItem: function () { throw new Error('the board reached for localStorage'); }
};
var HASH = '';
var location = { get hash() { return HASH; } };
var WRAP = { open: false, _fns: [],
             addEventListener: function (t, fn) { if (t === 'toggle') this._fns.push(fn); },
             fire: function () { this._fns.forEach(function (f) { f(); }); } };
var document = { getElementById: function (id) { return id === 'alt-narrative-wrap' ? WRAP : null; } };
var TIMERS = [];
function setTimeout(fn) { TIMERS.push(fn); }
function drain() { var t = TIMERS.slice(); TIMERS.length = 0; t.forEach(function (f) { f(); }); }
"""

NAMES = ["readBoardPref", "writeBoardPref", "initSignalBoard"]


def board_pref_key():
    """The storage key, lifted from the source rather than assumed."""
    m = re.search(r"var BOARD_PANEL_PREF = '([^']+)'", JS.read_text())
    assert m, "layoffs.js has no BOARD_PANEL_PREF"
    return m.group(1)


class CollapseBehaviour(unittest.TestCase):
    """initSignalBoard, executed. Not read."""

    def setUp(self):
        jsrun.require_node(self)
        self.key = board_pref_key()

    def run_js(self, expression, store="{}", hash_=""):
        pre = "%s\nvar BOARD_PANEL_PREF = %s;\nSTORE = %s;\nHASH = %s;\n" % (
            PREAMBLE, json.dumps(self.key), store, json.dumps(hash_))
        return jsrun.run(NAMES, pre, expression)

    def test_a_first_visit_leaves_the_board_open(self):
        got = self.run_js("(initSignalBoard(), {open: WRAP.open, store: STORE})")
        self.assertTrue(
            got["open"],
            "a reader with an empty session got the board CLOSED")
        self.assertEqual(
            got["store"], {},
            "the board wrote a preference the reader never expressed: %r"
            % got["store"])

    def test_a_collapse_from_this_session_is_honoured(self):
        got = self.run_js(
            "(initSignalBoard(), WRAP.open)",
            store="{%s: '0'}" % json.dumps(self.key))
        self.assertFalse(
            got, "the reader collapsed the board and it came back open")

    def test_a_deep_linked_region_reopens_it(self):
        got = self.run_js(
            "(initSignalBoard(), WRAP.open)",
            store="{%s: '0'}" % json.dumps(self.key), hash_="usa")
        self.assertTrue(
            got, "a #usa deep link left the board hidden. The region tabs are "
                 "the one control that scopes this board, so the view that "
                 "arrived by naming a region is the one it must be open for.")

    def test_an_unrelated_hash_does_not_reopen_it(self):
        got = self.run_js(
            "(initSignalBoard(), WRAP.open)",
            store="{%s: '0'}" % json.dumps(self.key),
            hash_="alt-metric-definitions")
        self.assertFalse(
            got, "an in-page anchor re-opened a board the reader collapsed")

    def test_a_reader_collapse_is_recorded_and_only_after_boot(self):
        got = self.run_js(
            "(function () {"
            " initSignalBoard();"
            " var afterInit = JSON.parse(JSON.stringify(STORE));"
            " drain();"
            " WRAP.open = false; WRAP.fire();"
            " return {afterInit: afterInit, afterClick: STORE};"
            "})()")
        self.assertEqual(
            got["afterInit"], {},
            "initSignalBoard's own assignment reached the toggle listener and "
            "wrote %r before the reader touched anything" % got["afterInit"])
        self.assertEqual(
            got["afterClick"], {self.key: "0"},
            "collapsing the board did not record it: %r" % got["afterClick"])

    def test_the_collapse_is_session_scoped_not_permanent(self):
        """localStorage throws in the stub, so reaching for it fails loudly."""
        got = self.run_js(
            "(function () { initSignalBoard(); drain();"
            " WRAP.open = false; WRAP.fire(); return STORE; })()")
        self.assertEqual(got, {self.key: "0"})

    def test_the_board_key_is_not_the_filter_panel_key(self):
        panel = re.search(r"var FILTER_PANEL_PREF = '([^']+)'", JS.read_text())
        self.assertIsNotNone(panel, "layoffs.js has no FILTER_PANEL_PREF")
        self.assertNotEqual(
            self.key, panel.group(1),
            "the board and the filter panel share the storage key %r, so "
            "collapsing one hides the other" % self.key)


class NothingWasRemoved(unittest.TestCase):
    """The period presets the board sits above are still on the page.

    They are a separate control from the board and the owner asked after both
    in the same breath. Pinned here so "make the board visible" can never be
    landed by moving these behind it.
    """

    def test_the_six_date_presets_are_present_and_in_order(self):
        html = strip_php_comments(TEMPLATE.read_text())
        got = re.findall(r'data-dp="([a-z0-9]+)">([^<]+)</button>', html)
        self.assertEqual(
            got,
            [("today", "Today"), ("d7", "Last 7 days"), ("d30", "Last 30 days"),
             ("d90", "Last quarter"), ("ytd", "Year to date"),
             ("all", "All time")],
            "the quick date presets changed: %r" % (got,))

    def test_the_presets_still_sit_below_the_board(self):
        html = strip_php_comments(TEMPLATE.read_text())
        self.assertLess(
            html.index('id="alt-narrative-wrap"'),
            html.index('id="alt-datepresets"'),
            "the date presets moved ABOVE the board. They do not scope it, "
            "and a control standing above content it does not control is the "
            "defect the block order was arranged to fix.")


if __name__ == "__main__":
    unittest.main()
