"""A BOARD CELL LINKS TO THE NUMBER IT SHOWS, ON BOTH PATHS.

THE DEFECT. The at-a-glance board (Today / This week / This month / YTD) counts
on the EFFECTIVE date. That is deliberate, it is disclosed in the board's own
footnote, and `test_date_basis_default.py::test_the_board_says_it_answers_a_
different_question` pins it. Its cell LINKS were not deliberate. They carried
`from`/`to` (or `years`) and nothing else, and since 2.20.4 the tracker they
link into DEFAULTS to the filing basis. So a reader who clicked "9,412" landed
on a page that recounted the same days on a different date column and published
a different number, with nothing on screen accounting for the change. That is
the same defect the report page's receipt links had, fixed in 2.20.11
(TECHLOG), and the board was listed there as found-and-not-fixed because it
needed the JS half as well.

WHY THE JS HALF IS NOT OPTIONAL. The board renders twice: server-side into the
first paint (page-tracker.php, `$alt_sb_meta`) and again in the browser
(layoffs.js, `updateNarrative`). The browser copy installs a `.alt-nfilter`
click handler that preventDefault()s the href and applies the data-* attributes
to the page's own controls. Fix only the href and the same cell produces two
different views depending on whether JS ran. Fix only the handler and every
no-JS reader, every middle-click, every "open in new tab" keeps the old wrong
number. Both, or the paths diverge.

WHAT IS DELIBERATELY NOT CHANGED. The board's PARAMS. `alt_signal_board_periods()`
and `P` in layoffs.js must stay byte-identical or `bootParamsMatch`/`takeBoot`
reject the server-inlined board and the first paint silently becomes four live
fetches. The basis rides on the LINK, and is READ OFF the params so a board that
ever does name a basis carries that one instead of this file's assumption.

HOW THESE CHECK. Where a behaviour can be RUN it is run: the PHP meta builder is
lifted out of the template and executed under the php binary with WordPress's
three escaping helpers stubbed, and the JS meta builder and click handler are
lifted out of layoffs.js and executed in node. Source-only checks say so.

CONFIRMED RED ON THE PRE-CHANGE TREE (ab4dea1, run as a file, with the two
plugin files reverted and this file left in place): 8 of the 15 tests here
fail. The other 7 are REGRESSION BARS, named here rather than left to look like
evidence of this change:

  * test_the_board_params_do_not_name_a_basis. The params were already free of
    date_basis; this holds them against a "fix" that adds it there, which would
    break bootParamsMatch and silently cost four fetches per paint.
  * test_the_cell_links_add_no_new_bootstrap_suppression. Already true before,
    because from/to and years are themselves in $alt_boot_url_filters. It is
    here because date_basis IS in that list, so the question had to be asked.
  * test_the_two_renderers_produce_byte_identical_cells and
    test_the_href_and_the_data_attributes_agree. The two renderers agreed
    before this change too: they agreed on a link with no basis in it. These
    hold the agreement while the cell grows a third thing to agree about, which
    is exactly when a hand-copied twin drifts.
  * test_a_cell_with_no_basis_leaves_the_reader_s_basis_alone and
    test_a_junk_basis_is_ignored_rather_than_applied. Trivially true on a tree
    whose handler reads no basis at all. They become real the moment it does.
  * test_the_copy_has_no_em_dashes. House rule, held over copy this change
    rewrites.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
TPL_PATH = PLUGIN / "templates/page-tracker.php"
JS_PATH = PLUGIN / "assets/layoffs.js"
DB_PATH = PLUGIN / "includes/db.php"

TPL = TPL_PATH.read_text()
JS = JS_PATH.read_text()
DB = DB_PATH.read_text()

PHP = shutil.which("php")


def strip_js_comments(src: str) -> str:
    """Comments out, strings intact. Two checks in this repo have passed
    against defective code by matching a comment that described a call."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"":
            j = i + 1
            while j < n and not (src[j] == c and src[j - 1] != "\\"):
                j += 1
            out.append(src[i:j + 1])
            i = j + 1
        elif c == "/" and src[i + 1:i + 2] == "/":
            i = src.find("\n", i)
            i = n if i == -1 else i
        elif c == "/" and src[i + 1:i + 2] == "*":
            i = src.find("*/", i) + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


JS_NC = strip_js_comments(JS)


def _brace_block(src: str, start_needle: str, open_at: str = "{") -> str:
    """Source text from `start_needle` through its matching close brace."""
    start = src.index(start_needle)
    i = src.index(open_at, start)
    close = {"{": "}", "(": ")"}[open_at]
    depth, j = 0, i
    while j < len(src):
        if src[j] == open_at:
            depth += 1
        elif src[j] == close:
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
        j += 1
    raise AssertionError("unbalanced %s extracting %r" % (open_at, start_needle))


# --------------------------------------------------------------------------
# The server render, RUN. The real foreach out of page-tracker.php, under php,
# with WordPress's escapers stubbed to something faithful enough to compare.
# --------------------------------------------------------------------------

PHP_HARNESS = r"""
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
$alt_cols = array('today' => 'Today', 'week' => 'This week', 'month' => 'This month', 'ytd' => '2026 YTD');
$alt_board = array(
    'today' => array('params' => array('from' => '2026-08-11', 'to' => '2026-08-11', 'stage' => 'verified')),
    'week'  => array('params' => array('from' => '2026-08-05', 'to' => '2026-08-11', 'stage' => 'verified')),
    'month' => array('params' => array('from' => '2026-08-01', 'to' => '2026-08-11', 'stage' => 'verified')),
    'ytd'   => array('params' => array('from' => '2026-01-01', 'to' => '2026-08-11', 'stage' => 'verified')),
);
%s
echo json_encode($alt_sb_meta), "\n";
$alt_board['ytd']['params'] = array('years' => '2026', 'stage' => 'verified');
%s
echo json_encode($alt_sb_meta), "\n";
$alt_board['today']['params']['date_basis'] = 'notice';
%s
echo json_encode($alt_sb_meta), "\n";
"""


def php_meta():
    """[default board, a years= board, a board naming its own basis]."""
    loop = _brace_block(TPL, "$alt_sb_meta = array();\n        foreach (")
    out = subprocess.run([PHP, "-r", PHP_HARNESS % (loop, loop, loop)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise AssertionError("php failed:\n%s" % out.stderr.strip())
    return [json.loads(l) for l in out.stdout.splitlines() if l.strip()]


# --------------------------------------------------------------------------
# The browser render and the click, RUN. The meta builder and the onclick body
# are inline inside updateNarrative()'s .then, so they are lifted by anchor
# rather than by function name; both anchors raise if they move.
# --------------------------------------------------------------------------

JS_PREAMBLE = r"""
var DATE_BASIS = 'notice';
var CONTROLS = {};
function writeControl(id, v) { CONTROLS[id] = v; }
function readControl(id) {
    var v = Object.prototype.hasOwnProperty.call(CONTROLS, id) ? CONTROLS[id] : '';
    return Array.isArray(v) ? '' : (v || '');
}
function multiParam(id) {
    var v = Object.prototype.hasOwnProperty.call(CONTROLS, id) ? CONTROLS[id] : [];
    return Array.isArray(v) ? (v.length ? v.join(',') : '') : (v || '');
}
function selectedList(id) {
    var v = Object.prototype.hasOwnProperty.call(CONTROLS, id) ? CONTROLS[id] : [];
    return Array.isArray(v) ? v : (v ? [v] : []);
}
function readChecked(id) { return !!CONTROLS[id]; }
// Plumbing the click handler calls on its way out. None of it is under test.
var CALLED = [];
function updateRangeLabel() { CALLED.push('updateRangeLabel'); }
function updateDropdownSummaries() { CALLED.push('updateDropdownSummaries'); }
function refreshAll() { CALLED.push('refreshAll'); }
function renderBasisCopy() { CALLED.push('renderBasisCopy'); }
// setDateBasis is the REAL one (it is the thing under test on the JS path);
// only its DOM reach is stubbed away.
var document = { querySelectorAll: function () { return []; } };
function cell(attrs) {
    return { getAttribute: function (k) {
        return Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null; } };
}
function clickEvent(attrs) {
    var a = cell(attrs);
    return { target: { closest: function () { return a; } }, preventDefault: function () {} };
}
"""


def js_meta(p_json):
    """meta{} as the browser builds it, for a given P."""
    block = _brace_block(JS, "var meta = {};\n            KEYS.forEach(", "(")
    src = ("var KEYS = ['today','week','month','ytd'];\nvar P = %s;\n%s;\nvar meta = meta;\n"
           % (p_json, block.replace("var meta = {};", "var meta = {};\n", 1)))
    return _node(src, "meta")


def js_click(attrs, basis="notice"):
    """DATE_BASIS and the controls, after one real click on a cell."""
    body = _brace_block(JS, "el.onclick = function (e) {")
    src = ("DATE_BASIS = %r;\nvar boardClick = %s;\nboardClick(clickEvent(%s));\n"
           % (basis, body[body.index("function (e)"):].rstrip(";"), json.dumps(attrs)))
    return _node(src, "({basis: DATE_BASIS, controls: CONTROLS, called: CALLED})",
                 names=["setDateBasis", "currentParams"])


def _node(src, expression, names=()):
    jsrun.require_node(None)
    bodies = "\n".join(jsrun.extract(n) for n in names)
    script = "%s\n%s\n%s\nconsole.log(JSON.stringify(%s));\n" % (
        JS_PREAMBLE, bodies, src, expression)
    proc = subprocess.run([jsrun.NODE, "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError("node failed:\n%s" % proc.stderr.strip())
    return json.loads(proc.stdout)


DEFAULT_P = json.dumps({
    "today": {"from": "2026-08-11", "to": "2026-08-11", "stage": "verified", "include": "leaders"},
    "week": {"from": "2026-08-05", "to": "2026-08-11", "stage": "verified", "include": "leaders"},
    "month": {"from": "2026-08-01", "to": "2026-08-11", "stage": "verified", "include": "leaders"},
    "ytd": {"from": "2026-01-01", "to": "2026-08-11", "stage": "verified", "include": "leaders"},
})


def href_params(href):
    return dict(kv.split("=", 1) for kv in href.lstrip("?").replace("&amp;", "&").split("&"))


# --------------------------------------------------------------------------
# 1. The href. The no-JS path, and the one a middle-click follows.
# --------------------------------------------------------------------------

@unittest.skipUnless(PHP, "php binary not available")
class TheServerRenderedHrefNamesItsBasis(unittest.TestCase):

    def test_every_cell_href_carries_the_basis_it_was_counted_on(self):
        """The whole defect in one assertion: four periods, four links, and
        before this change not one of them said which date column produced the
        number printed inside it."""
        meta = php_meta()[0]
        self.assertEqual(sorted(meta), ["month", "today", "week", "ytd"])
        for k, m in meta.items():
            self.assertEqual(href_params(m["href"]).get("date_basis"), "effective",
                             "the %s cell links to a view that recounts it on the "
                             "page default (the filing basis): %s" % (k, m["href"]))

    def test_the_years_shaped_cell_carries_it_too(self):
        """The YTD column was `years=` shaped until it became a real to-date
        window, and the branch survives. A basis added to only one branch is a
        defect that comes back the day the other branch is used again."""
        meta = php_meta()[1]
        self.assertIn("years=2026", meta["ytd"]["href"])
        self.assertEqual(href_params(meta["ytd"]["href"]).get("date_basis"), "effective")
        self.assertIn('data-date-basis="effective"', meta["ytd"]["data"])

    def test_the_basis_is_read_off_the_board_not_hardcoded(self):
        """'effective' is the fallback because the board's params name no basis
        and the server's own default column is layoff_date. It must be a
        fallback and not an assertion: a board that ever does name a basis has
        to carry THAT one into the link, or this fix becomes the next version
        of the same bug."""
        meta = php_meta()[2]
        self.assertEqual(href_params(meta["today"]["href"]).get("date_basis"), "notice")
        self.assertIn('data-date-basis="notice"', meta["today"]["data"])
        self.assertEqual(href_params(meta["week"]["href"]).get("date_basis"), "effective",
                         "one period's basis leaked into another period's link")

    def test_the_href_and_the_data_attributes_agree(self):
        """They are the two halves of the same cell: the href is what a reader
        without JS follows, the data-* is what the click handler applies. A
        cell whose two halves disagree is the divergence this file exists to
        prevent, printed on one element."""
        for meta in php_meta():
            for k, m in meta.items():
                h = href_params(m["href"])
                d = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', m["data"]))
                self.assertEqual(h.get("date_basis"), d.get("date-basis"), k)
                for a, b in (("from", "from"), ("to", "to"), ("years", "years")):
                    self.assertEqual(h.get(a), d.get(b), "%s/%s" % (k, a))


class TheParamsThemselvesWereNotTouched(unittest.TestCase):

    def test_the_board_params_name_the_basis_on_BOTH_sides_or_neither(self):
        """The board now counts on the page's own basis, so date_basis IS in
        the period params. The thing that was ever actually at stake is the
        one asserted here: the two renderers agree.

        This test used to forbid date_basis in the params outright, on the
        reasoning that adding it would make P differ from
        alt_signal_board_periods() and make bootParamsMatch reject the inlined
        board. That reasoning was about DIVERGENCE, not about the key: adding
        it to one side costs six REST calls per paint, adding it to both costs
        nothing. So the bar is symmetry, held on both halves and on the value.
        """
        periods = _brace_block(DB, "function alt_signal_board_periods(")
        p_block = _brace_block(JS_NC, "var P = {", "{")
        php_n = len(re.findall(r"'date_basis'\s*=>\s*'notice'", periods))
        js_n = len(re.findall(r"date_basis:\s*'notice'", p_block))
        self.assertEqual(
            php_n, 6,
            "alt_signal_board_periods() names date_basis=notice on %d of its "
            "six columns. A board counting two ways is worse than a board "
            "counting one way that the footnote names." % php_n)
        self.assertEqual(
            js_n, php_n,
            "P in layoffs.js names the basis on %d columns and "
            "alt_signal_board_periods() on %d. bootParamsMatch compares the "
            "key set and every value, so the inlined board is rejected and "
            "every first paint becomes six live REST calls." % (js_n, php_n))
        for block, where in ((periods, "alt_signal_board_periods()"),
                             (p_block, "P in layoffs.js")):
            found = set(re.findall(r"date_basis'?\s*(?:=>|:)\s*'(\w+)'", block))
            self.assertEqual(
                found, {"notice"},
                "%s counts its columns on %r. Every column, one basis, and it "
                "is the page's." % (where, sorted(found)))

    def test_the_cell_links_add_no_new_bootstrap_suppression(self):
        """REGRESSION BAR (green before this change too), and the reason it is
        asked: date_basis IS one of $alt_boot_url_filters, so naming it in a
        href could in principle have cost a cell its inlined first paint. It
        does not, because from/to and years are in that list as well, so every
        one of these hrefs already suppressed the bootstrap before this param
        joined it. Asserted rather than reasoned about, because the list is
        edited by hand."""
        listing = TPL[TPL.index("$alt_boot_url_filters = array("):]
        listing = listing[:listing.index(");")]
        named = set(re.findall(r"'([a-z_]+)'", listing))
        self.assertIn("date_basis", named, "the premise of this test has changed")
        for carrier in ("from", "to", "years"):
            self.assertIn(carrier, named,
                          "a board cell href carries %s, which no longer suppresses "
                          "the bootstrap, so date_basis is now a NEW suppression and "
                          "every cell click costs a first paint" % carrier)


# --------------------------------------------------------------------------
# 2. The click. The JS path, run.
# --------------------------------------------------------------------------

class TheClickCarriesTheBasisToo(unittest.TestCase):

    def setUp(self):
        jsrun.require_node(self)

    def test_the_browser_render_builds_the_same_link(self):
        """The two renderers are a copy of each other by hand. Run both."""
        js = js_meta(DEFAULT_P)
        for k, m in js.items():
            self.assertEqual(href_params(m["href"]).get("date_basis"), "effective", k)
            self.assertIn('data-date-basis="effective"', m["data"], k)

    @unittest.skipUnless(PHP, "php binary not available")
    def test_the_two_renderers_produce_byte_identical_cells(self):
        """A hand-copied twin drifts. The board's params are the same four
        windows on both sides, so the cells they produce have to match
        character for character."""
        self.assertEqual(js_meta(DEFAULT_P), php_meta()[0])

    def test_a_tap_switches_the_page_onto_the_cell_s_basis(self):
        """THE TEST THIS CHANGE EXISTS FOR. The handler preventDefault()s the
        href, so without this the JS path filtered the period and left the page
        counting by filing date: the same cell, two numbers, depending on
        whether a script loaded."""
        got = js_click({"data-from": "2026-08-01", "data-to": "2026-08-11",
                        "data-date-basis": "effective"}, basis="notice")
        self.assertEqual(got["basis"], "effective",
                         "the tap left the page on the filing basis, so the filtered "
                         "view recounts the period the cell just published")
        self.assertEqual(got["controls"]["alt-f-from"], "2026-08-01")
        self.assertEqual(got["controls"]["alt-f-to"], "2026-08-11")

    def test_the_tap_produces_exactly_the_view_the_href_names(self):
        """Not "it sets a variable": the request params and the address bar
        both come from currentParams(), so this compares what the tap actually
        asks the API for against what the untapped link would have opened."""
        meta = js_meta(DEFAULT_P)["month"]
        attrs = dict(("data-" + k, v) for k, v in
                     re.findall(r'data-([a-z-]+)="([^"]*)"', meta["data"]))
        got = js_click(attrs, basis="notice")
        p = got["controls"] and _node(
            "DATE_BASIS = %r;\nCONTROLS = %s;\n" % (got["basis"], json.dumps(got["controls"])),
            "currentParams()", names=["currentParams"])
        want = href_params(meta["href"])
        for k in ("from", "to", "date_basis"):
            self.assertEqual(p.get(k), want.get(k),
                             "the tapped view and the link differ on %s" % k)

    def test_it_goes_through_the_single_basis_writer(self):
        """setDateBasis() owns the closure state, the segmented switch's visual
        and aria state and every caption naming the basis. Assigning DATE_BASIS
        here would leave the switch showing the other basis and the captions
        describing it, which is the defect class this change is inside of.
        Run, not read: renderBasisCopy is stubbed to record the call, and it is
        only reachable through setDateBasis."""
        got = js_click({"data-from": "2026-08-01", "data-to": "2026-08-11",
                        "data-date-basis": "effective"}, basis="notice")
        self.assertIn("renderBasisCopy", got["called"],
                      "the tap changed the basis without going through "
                      "setDateBasis(), so the switch and the captions now "
                      "describe the basis the page is no longer on")

    def test_a_cell_with_no_basis_leaves_the_reader_s_basis_alone(self):
        """The largest-event fallback cell filters by company and names no
        period, so it names no basis either. Basis is not a filter and narrows
        nothing: silently recounting a reader's page because they clicked an
        employer name would be a new version of the same defect."""
        for basis in ("notice", "effective"):
            got = js_click({"data-company": "Dird Group"}, basis=basis)
            self.assertEqual(got["basis"], basis)
            self.assertEqual(got["controls"]["alt-f-company"], "Dird Group")
            self.assertNotIn("renderBasisCopy", got["called"])

    def test_a_junk_basis_is_ignored_rather_than_applied(self):
        """The attribute is markup and markup is data. currentParams() writes
        whatever DATE_BASIS holds straight into the API request and the address
        bar, and alt_db_date_col() falls through to layoff_date on anything it
        does not recognise, so an unvalidated value publishes a URL whose basis
        param means something other than what the page did."""
        got = js_click({"data-from": "2026-08-01", "data-to": "2026-08-11",
                        "data-date-basis": "announcement"}, basis="notice")
        self.assertEqual(got["basis"], "notice")


# --------------------------------------------------------------------------
# 3. The copy. Source check (it is a string in two renderers), stated as one.
# --------------------------------------------------------------------------

class TheFootnoteSaysWhatTheTapDoes(unittest.TestCase):

    def test_both_renderers_say_the_tap_keeps_the_board_s_own_count(self):
        """It used to say only "Tap any number to filter the page to that
        period", which was the true description of a link that then showed a
        different number."""
        line = "counted the same way this board counts it"
        for src, where in ((TPL, "page-tracker.php"), (JS_NC, "layoffs.js")):
            self.assertIn(line, src, "%s does not say what the tap does" % where)

    def test_the_copy_has_no_em_dashes(self):
        """House rule, UI copy."""
        for src, where in ((TPL, "page-tracker.php"), (JS_NC, "layoffs.js")):
            foot = src[src.index('<ul class="alt-sb-foot">'):]
            foot = foot[:foot.index("</ul>")]
            for bad in ("—", "–"):
                self.assertNotIn(bad, foot, "%s footnote carries a dash" % where)


if __name__ == "__main__":
    unittest.main()
