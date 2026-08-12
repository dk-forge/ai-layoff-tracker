"""THE GUARD FOR "IT GETS LOST".

The owner's report about the filter bar was three words long and exactly right.
The measurement behind it, taken off the live page in all four theme
combinations before any of this changed:

  date basis option (inactive)   1.00 : 1     `border: 1px solid transparent`
  filter dropdown, text, number  1.22 : 1     --alt-grid on --alt-surface
  date presets, search, sort,
  quick views                    1.28 : 1     --alt-border on --alt-surface
  reset button                   1.79 : 1     --alt-crit-border on --alt-red-tint
  date range button              1.81 : 1     --alt-blue-border, and dashed

WCAG 2.1 AA 1.4.11 asks a user interface component's visual boundary for 3:1.
Every text element on the same page passed AA, and had done for a while: the
contrast work in August measured what a reader could READ and nothing measured
whether they could see that a control was a control. The bar was audited green
the entire time it was invisible.

Alongside the boundaries the bar carried nine control heights (29.6 to 38.0px),
four border radii (8, 10, 20 and 999px), four type sizes, one dashed border and
one transparent one, and widths chosen per control rather than from a scheme.

This file measures the RENDERED result of the shipped stylesheet against the
template's own markup, in three theme states, at two widths, and it does the
second half that makes the first half mean anything: it reconstructs the defect
and proves the guard fails on it. A check that cannot be made to fail is not
evidence.

No Chrome, no measurement: this SKIPS loudly rather than passing. Absence of a
signal is not a pass (CLAUDE.md).
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402
import contrast_audit  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = PLUGIN / "assets/layoffs.css"
JS = PLUGIN / "assets/layoffs.js"
TEMPLATE = PLUGIN / "templates/page-tracker.php"

# Reproduced from the live document head, same as test_rendered_contrast.py.
# A fixture without it measures a page nobody is served.
SITE_OVERRIDE = """
.entry-content p ,.wp-block-post-content p  { font-size:1.05rem !important; line-height:1.78 !important; color:#2a2a2a !important; margin-bottom:1.2rem !important }
.entry-content h2,.wp-block-post-content h2 { font-size:1.45rem !important; font-weight:700 !important; color:#1a1a1a !important; border-bottom:2px solid #eef3ee !important }
.entry-content h3,.wp-block-post-content h3 { font-size:1.15rem !important; font-weight:600 !important; color:#222 !important }
"""

THEME_SHIM = """
body { background-color: var(--wp--preset--color--base, #ffffff);
       color: var(--wp--preset--color--contrast, #16181d);
       margin: 0; font-family: system-ui, sans-serif; }
"""

# layoffs.js replaces each multi-select with a checkbox dropdown. The fixture
# builds the same button, and test_the_dropdown_button_still_looks_like_this
# below asserts against the real builder with comments stripped, so this cannot
# drift into measuring a control the page does not ship.
DD_BUILDER = """
document.querySelectorAll('.alt-filter[data-dd]').forEach(function (cell) {
  var select = cell.querySelector('select[multiple]');
  if (!select) return;
  select.style.display = 'none';
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'alt-dd';
  btn.innerHTML = '<span class="alt-dd-txt">'
    + (cell.getAttribute('data-empty') || 'All')
    + '</span><svg width="11" height="11" viewBox="0 0 24 24" fill="none"'
    + ' stroke="currentColor" stroke-width="2.4" aria-hidden="true">'
    + '<path d="M6 9l6 6 6-6"/></svg>';
  cell.appendChild(btn);
  var pop = document.createElement('div');
  pop.className = 'alt-dd-pop';
  pop.hidden = true;
  Array.prototype.forEach.call(select.options, function (o) {
    var row = document.createElement('label');
    row.className = 'alt-dd-row';
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    row.appendChild(cb);
    row.appendChild(document.createTextNode(' ' + o.textContent));
    pop.appendChild(row);
  });
  cell.appendChild(pop);
});
"""

FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<!-- Without this the emulated phone lays out at 980px and every mobile media
     query is skipped, which would have let the 375px checks below measure the
     desktop rendering and call it a pass. -->
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%(plugin)s</style>
<style>%(theme)s</style>
<style>%(site)s</style>
<style>%(freeze)s</style>
</head>
<body class="wp-singular page-template-default page">
<div class="wp-site-blocks"><main class="wp-block-group has-global-padding">
<div class="wp-block-group alignfull"><div class="entry-content alignfull">
<div class="alt-wrap alt-tracker-wrap">
%(markup)s
</div></div></div></main></div>
<script>%(dd)s</script>
</body></html>
"""


def template_markup():
    """The filter bar and the results summary, lifted out of the real template.

    PHP is stripped rather than executed, so the numbers are absent and the
    structure is exactly what ships. Slicing rather than hand-writing is the
    point: a fixture somebody maintains by hand stops describing the page the
    first time a control moves, and then it passes forever.
    """
    src = TEMPLATE.read_text()
    html = re.sub(r"<\?php.*?\?>", "", src, flags=re.S)
    start = html.index('<div class="alt-datepresets"')
    end = html.index('<section class="alt-why-lower"')
    frag = html[start:end]
    # The slice has to be balanced or the browser will re-parent half of it and
    # every measurement below would be of a shape the page never renders.
    voids = {"input", "br", "img", "hr", "meta", "link", "path", "rect",
             "circle", "polyline", "line", "use", "source"}
    opens, closes = {}, {}
    for tag in re.findall(r"<(\w+)(?=[\s>])(?![^>]*/>)", frag):
        if tag not in voids:
            opens[tag] = opens.get(tag, 0) + 1
    for tag in re.findall(r"</(\w+)>", frag):
        closes[tag] = closes.get(tag, 0) + 1
    ragged = {t: (opens.get(t, 0), closes.get(t, 0))
              for t in set(opens) | set(closes)
              if t not in voids and opens.get(t, 0) != closes.get(t, 0)}
    assert not ragged, "the template slice is unbalanced: %r" % ragged
    return frag


def strip_css_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def strip_js_comments(js):
    """Block and line comments out, string literals left alone.

    Roughly a dozen checks in this repository have passed by matching a comment
    that described the code instead of the code, several of them in the week
    this file was written, so nothing here matches against raw source.
    """
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if c in "\"'`":
            j = i + 1
            while j < n:
                if js[j] == "\\":
                    j += 2
                    continue
                if js[j] == c:
                    break
                j += 1
            out.append(js[i:j + 1])
            i = j + 1
        elif js.startswith("/*", i):
            i = js.find("*/", i + 2)
            i = n if i < 0 else i + 2
        elif js.startswith("//", i):
            j = js.find("\n", i)
            i = n if j < 0 else j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def break_the_control_boundary(css):
    """Reconstruct the bar as it was: control edges drawn from --alt-border.

    This is the pre-fix defect, not an invented one. --alt-border is the token
    every one of these controls used before, it is still the token panels and
    rules use, and it measures 1.28:1 against --alt-surface in light. If the
    guard below cannot see this, it cannot see the thing it was written for.
    """
    out = re.sub(r"--alt-control-border:\s*#[0-9a-fA-F]{3,8};",
                 "--alt-control-border: var(--alt-border);", css)
    assert out != css, "no --alt-control-border definition found; the fix moved"
    return out


def flatten_the_control_heights(css):
    """Take the shared height back out, leaving each control its own padding."""
    out = re.sub(r"min-height:\s*var\(--alt-ctl-h\);", "", css)
    assert out != css, "no shared control height found; the fix moved"
    return out


class _Rendered(unittest.TestCase):
    """Loads the fixture in headless Chrome and returns the audit's own rows."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the filter controls "
                "could not be measured. This is UNKNOWN, not a pass: run "
                "`python3 railway/contrast_audit.py` where a browser exists.")
        cls._markup = template_markup()

    def render(self, probe, css=None, theme="light", attr=None, width=1280,
               markup=None):
        """Render the fixture and evaluate one probe expression in it."""
        html = FIXTURE % {
            "plugin": css if css is not None else CSS.read_text(),
            "theme": THEME_SHIM, "site": SITE_OVERRIDE,
            "freeze": contrast_audit.FREEZE_CSS,
            "markup": self._markup if markup is None else markup,
            "dd": DD_BUILDER,
        }
        height = 900 if width >= 768 else 812
        try:
            with Browser(width=width, height=height) as page:
                page.call("Emulation.setEmulatedMedia", {
                    "features": [{"name": "prefers-color-scheme",
                                  "value": theme}]})
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                # FREEZE FIRST, THEME SECOND. Reading a computed background in
                # the same task that flipped the theme returns the colour the
                # control is transitioning FROM; the audit invented twenty
                # violations that way the first time it ran. The freeze is in
                # the fixture's own <head> so it is in effect before first
                # paint, and the attribute is set before anything is measured.
                if attr is not None:
                    page.eval_js(
                        "document.documentElement.setAttribute("
                        "'data-theme', %s)" % json.dumps(attr))
                else:
                    page.eval_js("document.documentElement.removeAttribute("
                                 "'data-theme'); true")
                page.eval_js(contrast_audit.REVEAL_JS)
                return page.eval_js(probe)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)

    def controls(self, css=None, theme="light", attr=None, width=1280):
        rows = self.render(contrast_audit.controls_js(), css=css, theme=theme,
                           attr=attr, width=width)
        self.assertTrue(rows, "the fixture rendered no filter controls at all, "
                              "so this measured nothing")
        return rows


# The tile grid, measured as GEOMETRY rather than read off the stylesheet. An
# orphan is a row that does not fill its container, and equal heights are two
# tiles in one row ending at the same y. Both are properties of the rendered
# box, and neither is visible in a grid-template-columns declaration.
TILES_JS = r"""
(function () {
  function rows(sel, parentSel) {
    var parent = document.querySelector(parentSel);
    if (!parent) return null;
    var cs = getComputedStyle(parent);
    var gap = parseFloat(cs.columnGap) || 0;
    var inner = parent.getBoundingClientRect().width
              - parseFloat(cs.paddingLeft || 0) - parseFloat(cs.paddingRight || 0);
    var byTop = {};
    document.querySelectorAll(sel).forEach(function (c) {
      var r = c.getBoundingClientRect();
      var k = Math.round(r.top);
      (byTop[k] = byTop[k] || []).push(
        { w: r.width, h: r.height,
          label: (c.querySelector('.alt-stat-label') || { textContent: '?' })
                   .textContent.trim().slice(0, 26) });
    });
    var out = [];
    Object.keys(byTop).sort(function (a, b) { return a - b; }).forEach(function (k) {
      var row = byTop[k];
      var used = row.reduce(function (a, c) { return a + c.w; }, 0)
               + gap * (row.length - 1);
      out.push({ top: +k, n: row.length, used: Math.round(used * 10) / 10,
                 container: Math.round(inner * 10) / 10,
                 heights: row.map(function (c) { return Math.round(c.h * 10) / 10; }),
                 labels: row.map(function (c) { return c.label; }) });
    });
    return out;
  }
  var note = document.querySelector('.alt-stats-derived-note');
  return JSON.stringify({
    primary: rows('.alt-stats-bar > .alt-stat-card', '.alt-stats-bar'),
    derived: rows('.alt-broad-strip > .alt-stat-card', '.alt-broad-strip'),
    note: note ? { rendered: (note.innerText || '').trim().length,
                   inMarkup: (note.textContent || '').trim().length } : null
  });
})()
"""


# The three states the owner named, spelled out. "auto on a dark OS" is the
# default a reader gets without touching anything, and it is a DIFFERENT half
# of the stylesheet from chosen-dark: the plugin's dark rules are written as
# [data-theme=dark] OR :not([data-theme=light]) under the media query.
THEME_STATES = (
    ("light", "light", None),
    ("dark, chosen", "light", "dark"),
    ("auto on a dark OS", "dark", None),
)


class BoundaryTests(_Rendered):

    def test_every_control_boundary_clears_three_to_one_in_every_theme(self):
        for name, os_scheme, attr in THEME_STATES:
            with self.subTest(theme=name):
                rows = self.controls(theme=os_scheme, attr=attr)
                bad = contrast_audit.control_violations(rows)
                self.assertEqual(
                    [], [(b["kind"], b["sel"], b["line"], b["outside"],
                          b["ratio"]) for b in bad],
                    "filter controls below %.1f:1 in %s"
                    % (contrast_audit.AA_NONTEXT, name))

    def test_the_bar_that_is_measured_is_the_whole_bar(self):
        # Guards the fixture. Without this the two tests above would pass by
        # measuring three controls, or none, and read exactly as green.
        rows = self.controls()
        got = {r["kind"] for r in rows}
        for kind, _sel in (contrast_audit.FILTER_CONTROLS
                           + contrast_audit.FILTER_TAP_TARGETS):
            self.assertIn(kind, got,
                          "%s is in the audit's selector table but rendered "
                          "nothing in the fixture" % kind)
        self.assertGreaterEqual(
            len(rows), 25,
            "the bar has twelve kinds of control and around thirty "
            "instances; %d is not the whole bar" % len(rows))

    def test_the_inactive_date_basis_option_has_a_boundary_at_all(self):
        # Named on its own because it is the one that measured 1.00:1: not a
        # faint edge, no edge. A regression here would hide inside an average.
        rows = self.controls()
        opts = [r for r in rows if r["kind"] == "date basis option"]
        self.assertEqual(2, len(opts), "expected both segments of the switch")
        for o in opts:
            self.assertTrue(o["bordered"],
                            "a date-basis segment paints no border at all")
            self.assertGreaterEqual(o["ratio"], contrast_audit.AA_NONTEXT)


class ShapeTests(_Rendered):

    def bounded(self, **kw):
        """Only the controls that are their own box.

        A row inside an open dropdown is a tap target and is measured as one,
        but it is a row in a list rather than a control with a perimeter, so
        it has no business in a check about shared shape."""
        return [r for r in self.controls(**kw) if not r["tapOnly"]]

    def test_every_control_is_one_height(self):
        rows = self.bounded()
        heights = sorted({r["h"] for r in rows})
        self.assertEqual(
            1, len(heights),
            "the filter bar renders %d different control heights: %s"
            % (len(heights), heights))

    def test_every_control_is_one_shape(self):
        rows = self.bounded()
        radii = sorted({r["radius"] for r in rows})
        self.assertEqual(
            1, len(radii),
            "the filter bar renders %d different border radii: %s"
            % (len(radii), radii))
        styles = sorted({tuple(r["borderWidths"]) for r in rows})
        self.assertEqual([(1.0, 1.0, 1.0, 1.0)], styles,
                         "not every control draws a one pixel box: %s" % styles)

    def test_no_control_carries_a_width_of_its_own(self):
        # The width scheme is two tokens with content-based growth. A literal
        # px width inside one of these rules is the defect coming back one
        # control at a time, which is how the bar acquired five of them: a
        # 320px flex basis on search, a 150px minimum in the date popover, a
        # 160px grid minimum in the panel and a 190px one in the legacy grid.
        css = strip_css_comments(CSS.read_text())
        for token in ("--alt-ctl-min", "--alt-ctl-chip-min"):
            self.assertIn(token + ":", css, "%s is not defined" % token)
        watched = (".alt-search-wrap", ".alt-filterbar-row", ".alt-filters",
                   ".alt-range-pop .alt-filter", ".alt-btn-reset",
                   ".alt-datepresets .alt-dp", ".alt-quickviews .alt-qv")
        offenders = []
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            head = sel.strip()
            if not any(head == w or head.startswith(w + ",") or
                       ("\n" + w) in ("\n" + head) for w in watched):
                continue
            for prop, val in re.findall(
                    r"(width|min-width|max-width|flex|flex-basis|"
                    r"grid-template-columns)\s*:([^;]*)", body):
                if re.search(r"\d+px", val) and "var(--alt-ctl" not in val:
                    offenders.append((head, prop, val.strip()))
        self.assertEqual([], offenders,
                         "a per-control width survived the scheme")


class TapTargetTests(_Rendered):

    def test_every_control_clears_forty_four_pixels_on_a_phone(self):
        rows = self.controls(width=375)
        bad = contrast_audit.control_violations(
            rows, contrast_audit.TAP_MIN)
        self.assertEqual(
            [], [(b["kind"], b["w"], b["h"]) for b in bad],
            "controls below the %.0fpx target size at 375px"
            % contrast_audit.TAP_MIN)


class TheGuardCanActuallyFailTests(_Rendered):
    """With the fix removed, the audit MUST report the original defect.

    This is the half that makes everything above mean something, and it is a
    reproduction of the real bar rather than a synthetic failure: the same
    token, the same markup, the same fixture.
    """

    def test_putting_the_control_edge_back_on_alt_border_fails_the_audit(self):
        rows = self.controls(css=break_the_control_boundary(CSS.read_text()))
        bad = contrast_audit.control_violations(rows)
        self.assertTrue(bad, "the audit passed a filter bar whose every "
                             "control edge is --alt-border on --alt-surface: "
                             "it cannot catch the defect it exists for")
        worst = min(b["ratio"] for b in bad)
        self.assertLess(worst, 1.5, "expected the reproduction to land near "
                                    "1.3:1, got %.2f" % worst)
        self.assertGreaterEqual(
            len(bad), 20,
            "only %d control(s) flagged; the reproduction breaks the whole "
            "bar and the guard should say so" % len(bad))

    def test_taking_the_shared_height_out_fails_the_height_check(self):
        rows = [r for r in
                self.controls(css=flatten_the_control_heights(CSS.read_text()))
                if not r["tapOnly"]]
        heights = {r["h"] for r in rows}
        self.assertGreater(
            len(heights), 1,
            "with the shared height removed the controls still measured one "
            "height, so the height check is not measuring the height")


class TileGridTests(_Rendered):
    """Five tiles, no orphan, and every tile in a row the same height.

    Measured before this changed, at 1280: four tiles across at 279x154 and the
    fifth alone on a second row at 279x117, with three empty columns beside it.
    A row that does not fill its container reads as a tile that failed to load
    rather than as a row that ended.
    """

    def tiles(self, width=1280, css=None, markup=None):
        rows = self.render(TILES_JS, width=width, css=css, markup=markup)
        return json.loads(rows)

    def test_no_tile_row_leaves_an_empty_column(self):
        for width in (1280, 1024, 375):
            with self.subTest(width=width):
                got = self.tiles(width)
                for group in ("primary", "derived"):
                    for row in got[group] or []:
                        self.assertAlmostEqual(
                            row["used"], row["container"], delta=1.5,
                            msg="%s row at y=%d holds %d tile(s) filling "
                                "%.1f of %.1f px: %s"
                                % (group, row["top"], row["n"], row["used"],
                                   row["container"], row["labels"]))

    def test_every_tile_in_a_row_is_the_same_height(self):
        for width in (1280, 1024):
            with self.subTest(width=width):
                got = self.tiles(width)
                for group in ("primary", "derived"):
                    for row in got[group] or []:
                        self.assertEqual(
                            1, len(set(row["heights"])),
                            "%s row at y=%d has heights %s for %s"
                            % (group, row["top"], row["heights"], row["labels"]))

    def test_the_five_primary_tiles_are_all_measured(self):
        # Guards the two above: with zero tiles found they would both pass.
        got = self.tiles(1280)
        self.assertEqual(5, sum(r["n"] for r in got["primary"]))
        self.assertEqual(3, sum(r["n"] for r in got["derived"]))

    def test_a_four_column_grid_is_caught_as_an_orphan(self):
        # The reproduction. Four columns is what shipped, and it is what left
        # the fifth tile alone; if the check above cannot see it, it is not
        # checking anything.
        css = re.sub(r"(\.alt-stats-bar\s*\{[^}]*grid-template-columns:\s*)"
                     r"repeat\(5,", r"\1repeat(4,",
                     strip_css_comments(CSS.read_text()))
        got = self.tiles(1280, css=css)
        ragged = [r for r in got["primary"]
                  if abs(r["used"] - r["container"]) > 1.5]
        self.assertTrue(
            ragged, "a four-column grid holding five tiles measured as full "
                    "rows, so the orphan check cannot see an orphan")


class DerivedNoteTests(_Rendered):
    """The sentence that stops a journalist double counting.

    It sat inside a closed <details>. Current Chrome renders a closed
    <details> with content-visibility:hidden, so its children still have
    layout boxes and still carry textContent: the paragraph measured 758x60
    with a non-zero rect and 145 characters of markup, and a reader could read
    none of it. innerText is the only one of the three that reports what is
    actually legible, which is why this asserts on innerText.
    """

    def _note(self, width=1280, markup=None):
        return json.loads(self.render(TILES_JS, width=width,
                                      markup=markup))["note"]

    def test_the_caveat_is_readable_without_a_click(self):
        for width in (1280, 375):
            with self.subTest(width=width):
                note = self._note(width)
                self.assertIsNotNone(note, "the derived-totals note is gone")
                self.assertGreaterEqual(
                    note["rendered"], 100,
                    "the note renders %d characters of its %d; a caveat "
                    "nobody can read is not a caveat"
                    % (note["rendered"], note["inMarkup"]))
                self.assertEqual(note["rendered"], note["inMarkup"],
                                 "part of the note is not being rendered")

    def test_putting_it_back_behind_a_disclosure_is_caught(self):
        # The reproduction, and the reason this asserts on innerText: the
        # markup and the bounding box below are both unchanged.
        markup = self._markup.replace(
            '<section class="alt-stats-derived" '
            'aria-labelledby="alt-stats-derived-h">',
            '<details class="alt-stats-derived"><summary>Derived totals'
            '</summary>').replace(
            '</section>\n        ', '</details>\n        ', 1)
        note = self._note(markup=markup)
        self.assertEqual(
            0, note["rendered"],
            "a paragraph inside a closed <details> reported %d readable "
            "characters, so this check cannot tell collapsed from visible"
            % note["rendered"])
        self.assertGreater(note["inMarkup"], 100,
                           "the reproduction lost the paragraph entirely, so "
                           "it is not the reproduction")


class TheDropdownFixtureMatchesTheShippedBuilderTests(unittest.TestCase):
    """The .alt-dd button is built by layoffs.js, so the fixture builds one too.

    That is a copy, and a copy is a drift risk, so it is pinned to the real
    builder here rather than trusted. Comments are stripped before matching:
    the builder is described in a comment two lines above the code, and a test
    that matched the comment would keep passing after the code was deleted.
    """

    def test_the_dropdown_button_still_looks_like_this(self):
        js = strip_js_comments(JS.read_text())
        self.assertIn("btn.className = 'alt-dd'", js,
                      "layoffs.js no longer builds a .alt-dd button, so the "
                      "fixture is measuring a control the page does not ship")
        self.assertIn("<span class=\"alt-dd-txt\">", js)
        self.assertIn("aria-haspopup", js)

    def test_the_filter_panel_ships_open(self):
        # The owner asked for the filters to be visible rather than hidden
        # behind the toggle. Comments stripped, so this matches the branch and
        # not the paragraph above it explaining the branch.
        js = strip_js_comments(JS.read_text())
        self.assertRegex(
            js, r"setFilterPanelOpen\(\s*chosen\s*\|\|\s*pref\s*!==\s*'0'\s*\)",
            "initFilterPanel no longer defaults the panel to open")
        self.assertIn("sessionStorage.getItem(FILTER_PANEL_PREF)", js,
                      "a reader's collapse is not remembered for the session")
        self.assertNotIn("localStorage.setItem(FILTER_PANEL_PREF", js,
                         "a collapse is a 'not right now', not a permanent "
                         "preference")

    def test_no_filter_was_removed_or_re_scoped(self):
        # The brief that produced the visible-boundary work was explicit that
        # no filter may be removed, reordered or re-scoped. This pins the set
        # and the order, from the template rather than from a list somebody
        # keeps in step by hand.
        html = re.sub(r"<\?php.*?\?>", "", TEMPLATE.read_text(), flags=re.S)
        ids = re.findall(r'<(?:select|input)[^>]*\bid="(alt-f-[\w-]+)"', html)
        self.assertEqual(
            ["alt-f-from", "alt-f-to", "alt-f-years", "alt-f-quarters",
             "alt-f-months", "alt-f-industry", "alt-f-country", "alt-f-state",
             "alt-f-reasons", "alt-f-verification", "alt-f-roles",
             "alt-f-company", "alt-f-keyword", "alt-f-minjobs", "alt-f-ai",
             "alt-f-ai-broad", "alt-f-announced"],
            ids,
            "a filter was added, removed or reordered in the template")


if __name__ == "__main__":
    unittest.main()
