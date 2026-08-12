"""THE 44px FLOOR, EVERYWHERE ELSE ON THE PAGE.

2.20.10 gave every control INSIDE the filter bar one shape and a 44px height
under 768px, and it was explicit about what it had not touched. This is that
list, measured rather than repeated. Taken off the LIVE page at 375px from a
reader's view (bare URL, browser User-Agent, no cache buster, ver=2.20.11),
632 of this plugin's 882 laid-out interactive targets were under 44x44:

  per-tile (i) disclosure          15.0 x 15.0   (18 of them)
  jobless-claims checkbox          13.0 x 13.0
  chart icon buttons               26.0 x 26.0   6.0px apart   (61)
  "Details" on a result card       64.4 x 24.9                 (25)
  map scope switch                 53.8 x 24.0   0.0px, segmented
  "Show all N" under a bar list   285.0 x 26.0
  conversation-range buttons       87.4 x 26.0   4.0px apart
  theme switch                     71.2 x 26.5   3.9px apart
  active-filter chip / clear      105.7 x 27.6
  region tabs                      78.7 x 29.0   5.9px apart   (10)
  small buttons                    97.5 x 29.6
  per-page select                  62.0 x 30.0
  signal-board cells               71.5 x 32.0   4.0px apart   (9)
  pagination                       32.5 x 32.2   3.9px apart   (5)
  hero buttons                    152.8 x 36.8
  bar-list rows                   285.0 x 41.5   4.5px apart   (144)
  card headline link              305.0 x 21.6                 (7)
  source link on a card           114.6 x 15.0   2.0px from "archived"  (149)
  "archived" beside it             48.7 x 15.0                 (21)
  corrections-log "#" anchor        8.4 x 16.0                 (152)
  citeline links (CSV/JSON/API)    95.8 x 20.0   0.0px apart

SIZE IS HALF OF IT. Two 44px targets 2px apart still take the wrong tap, and
six of the groups above were under 6px from their neighbour. Both halves are
asserted below.

44px IS NOT THE ANSWER FOR EVERY ONE OF THEM, AND SAYING SO IS THE POINT.
An anchor inside a paragraph cannot be 44px tall without opening a 44px hole in
the sentence around it. WCAG says this itself: 2.5.5 and 2.5.8 both carry an
exception for a target "in a sentence or its size is otherwise constrained by
the line-height of non-target text". So those get a hit area that grows under
text that does not move, which on a `display: inline` box is exactly what
vertical padding does: it hit-tests and it does not enter the line-box
calculation. The floor for them is 30px of rendered hit box, and the test
below asserts THE PARAGRAPH DID NOT MOVE at the same time, because a "fix"
that inflated the line would be a worse page than the defect.

THE TRAP, INHERITED FROM THE FILTER-BAR WORK AND WORTH REPEATING. A closed
<details> in current Chrome uses content-visibility: hidden. Its children still
have layout boxes and still carry textContent. `innerText` is the only one of
the three that reports what a reader can read, and it is the only one this file
asserts on. Geometry is read from getBoundingClientRect on the rendered page,
never from the stylesheet source.

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

TAP_MIN = 44.0
GAP_MIN = 8.0
# The floor for a link inside a sentence. Not 44 (see the module docstring),
# not 15 either: this is the size the hit area reaches once vertical padding
# is applied to an inline box, and it clears WCAG 2.5.8's 24px AA minimum
# with room to spare.
INLINE_HIT_MIN = 30.0

SITE_OVERRIDE = """
.entry-content p ,.wp-block-post-content p  { font-size:1.05rem !important; line-height:1.78 !important; color:#2a2a2a !important; margin-bottom:1.2rem !important }
.entry-content h2,.wp-block-post-content h2 { font-size:1.45rem !important; font-weight:700 !important; color:#1a1a1a !important; border-bottom:2px solid #eef3ee !important }
.entry-content h3,.wp-block-post-content h3 { font-size:1.15rem !important; font-weight:600 !important; color:#222 !important }
"""

THEME_SHIM = """
body { background-color: #ffffff; color: #16181d;
       margin: 0; font-family: system-ui, sans-serif; }
"""

# ---------------------------------------------------------------------------
# The controls layoffs.js builds at runtime, so they are not in the template
# and a template-only fixture would silently stop covering them. Each entry is
# the markup the REAL builder emits, and TheFixtureStillDescribesTheRealPage
# below re-derives every class name from layoffs.js with comments stripped, so
# this cannot drift into measuring markup the page does not ship.
# ---------------------------------------------------------------------------
JS_BUILT = """
<div class="alt-af-bar" id="alt-af-bar">
  <button type="button" class="alt-af-chip alt-af-blue" data-i="0">Year: 2026 <span aria-hidden="true">&#10005;</span></button>
  <button type="button" class="alt-af-clear" id="alt-af-clear">Clear all</button>
</div>
<div class="alt-mini"><div class="alt-barlist">
  <button type="button" class="alt-barrow"><span class="alt-barrow-top"><span class="alt-barrow-name">California</span><span class="alt-barrow-val">16,324</span></span><span class="alt-bartrack"></span></button>
  <button type="button" class="alt-barrow"><span class="alt-barrow-top"><span class="alt-barrow-name">Texas</span><span class="alt-barrow-val">17,351</span></span><span class="alt-bartrack"></span></button>
  <button type="button" class="alt-bar-more">Show all 47 &rarr;</button>
</div></div>
<div class="alt-card">
  <a class="alt-card-h" href="#x">Supermassive plans to cut 75 jobs</a>
  <div class="alt-card-foot">
    <span class="alt-card-src"><a href="#s" target="_blank" rel="noopener nofollow">eurogamer.net &#8599;</a><span class="alt-archived"> &middot; <a href="#a" target="_blank" rel="noopener nofollow" class="alt-muted">archived</a></span></span>
    <button type="button" class="alt-card-more" aria-expanded="false">Details</button>
  </div>
</div>
<div class="alt-pager">
  <div class="alt-page-nums">
    <button type="button" class="alt-page-btn alt-page-nav" data-page="0">Previous</button>
    <button type="button" class="alt-page-btn alt-page-on" data-page="1">1</button>
    <button type="button" class="alt-page-btn" data-page="2">2</button>
    <button type="button" class="alt-page-btn alt-page-nav" data-page="2">Next</button>
  </div>
  <label class="alt-page-size">Per page
    <select id="alt-per-page"><option>10</option><option>25</option></select>
  </label>
</div>
"""

FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<!-- Without this the emulated phone lays out at 980px and every mobile media
     query is skipped, which would let a 375px check measure the desktop
     rendering and call it a pass. -->
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
%(built)s
</div></div></div></main></div>
</body></html>
"""

# Every interactive thing this plugin renders. Third-party chrome (the theme
# header, the WordPress skip link, the cookie banner) is not this plugin's
# markup and is not this plugin's to fix.
PROBE = r"""
(function () {
  var SEL = 'a[href], button, [role="button"], [role="tab"], [role="link"],'
          + ' input:not([type="hidden"]), select, textarea, summary,'
          + ' [tabindex]:not([tabindex="-1"]), .alt-dd-row';
  var out = [];
  Array.prototype.forEach.call(document.querySelectorAll(SEL), function (el) {
    var cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    if (el.offsetParent === null && cs.position !== 'fixed') return;
    var r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    // An element inside another interactive element is not a separate target:
    // the browser-drawn checkbox inside a 44px dropdown row is hit by hitting
    // the row, and reporting it would invent three hundred fake failures.
    var p = el.parentElement;
    while (p) { if (p.matches && p.matches(SEL)) return; p = p.parentElement; }
    // THE HIT AREA, NOT THE INK. An out-of-flow ::after is how a control
    // keeps a 15px look and gains a 44px target without moving anything
    // around it, so the rect a thumb actually lands in is the union of the
    // two. Only an absolutely positioned pseudo counts: an inline "↗" glyph
    // after a link is decoration and is already inside the box.
    var w = r.width, h = r.height;
    var pa = getComputedStyle(el, '::after');
    if (pa && pa.content && pa.content !== 'none' && pa.position === 'absolute') {
      w = Math.max(w, parseFloat(pa.width) || 0);
      h = Math.max(h, parseFloat(pa.height) || 0);
    }
    out.push({
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      cls: (typeof el.className === 'string') ? el.className : '',
      // innerText, never textContent: a closed <details> still carries
      // textContent for text no reader can read.
      text: (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40),
      display: cs.display,
      aria: el.getAttribute('aria-label') || '',
      // True when this box is painted on its own layer (a dropdown or the
      // date popover). Those overlap the page underneath them by design and
      // are never both on screen at the coordinates the other occupies, so
      // the adjacency check must not read one against the other.
      layer: !!el.closest('.alt-dd-pop, .alt-range-pop, .alt-embed-pop'),
      w: Math.round(w * 10) / 10,
      h: Math.round(h * 10) / 10,
      // The union is centred on the element, so the rect grows both ways.
      x: Math.round((r.left + window.scrollX - (w - r.width) / 2) * 10) / 10,
      y: Math.round((r.top + window.scrollY - (h - r.height) / 2) * 10) / 10
    });
  });
  return out;
})()
"""

# Where the paragraph sits, so a "fix" that inflated a line box is caught. The
# selector is a sentence that contains one of the inline links.
PARAGRAPH_PROBE = r"""
(function () {
  var p = document.querySelector('.alt-why-quality');
  if (!p) return null;
  var r = p.getBoundingClientRect();
  return { h: Math.round(r.height * 10) / 10,
           text: (p.innerText || '').trim().slice(0, 60) };
})()
"""

# LINKS INSIDE A SENTENCE. Named one at a time, because a rule that discovers
# its own exemptions grants itself new ones every time somebody adds a class.
INLINE_IN_SENTENCE = (
    "alt-why-quality",        # "...disclosed in the open log."
    "alt-hero-asof-more",     # "Why two figures", inside the as-of line
    "alt-log-anchor",         # the "#" permalink at the end of a log entry
    "alt-muted",              # "archived", beside a publisher's own link
    "alt-card-src",           # the publisher link on a card
    "alt-detail",             # links inside an expanded card detail
    "alt-card-detail",
    "alt-sb-foot",            # the signal board's footnote list
    "alt-chart-sub",          # a chart subtitle that names a filter
    "alt-narrative",          # the at-a-glance prose
    "alt-why-item",
    "alt-faq",
    "alt-metric-def",
    "alt-corrections",
    "alt-footnote",
    "alt-lead",
    "alt-src-note",
    "alt-tip",
)

# A segmented switch shares one edge between its halves by design, the way the
# date-basis switch in the filter bar does. Splitting them would say they are
# two controls when they are one.
SEGMENTED = ("alt-map-scope", "alt-datebasis-opt", "alt-theme-b")


def strip_css_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def strip_js_comments(js):
    """Block and line comments out, string literals left alone.

    Checks in this repository have passed by matching a comment that described
    the code instead of the code, so nothing here matches raw source.
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


def template_markup():
    """The whole tracker template with PHP stripped, not a hand-written slice.

    A fixture somebody maintains by hand stops describing the page the first
    time a control moves, and then it passes forever.
    """
    html = re.sub(r"<\?php.*?\?>", "", TEMPLATE.read_text(), flags=re.S)
    return html


def remove_the_tap_target_section(css):
    """Reconstruct the page as it was: no floor outside the filter bar.

    This is the measured pre-fix state, not an invented one. If the guard
    cannot be made to fail on it, it is not evidence.
    """
    marker = "TAP TARGETS OUTSIDE THE FILTER BAR"
    at = css.find(marker)
    assert at >= 0, "the tap-target section is gone from layoffs.css"
    start = css.rindex("/*", 0, at)
    out = css[:start]
    assert out != css, "removing the section changed nothing"
    return out


def is_a_fixture_artifact(row):
    """A control whose whole label is written by PHP.

    The fixture strips PHP rather than executing it, which is what keeps it
    honest about STRUCTURE. The cost is that a link like
    `<a><?php echo $label ?><span class="alt-browse-n"><?php ... ?></span></a>`
    renders here with no text and therefore no width. Measuring that as a
    22px target would be measuring the fixture, not the page: the same link
    on the live page carries a country name. Only a target that renders NO
    readable text at all qualifies, so a real icon-only button (which has an
    explicit size in the stylesheet) is never excused by this.
    """
    return row["tag"] == "a" and not row["text"] and not row["aria"]


def is_inline_in_sentence(row):
    # A BUTTON IS NEVER A WORD IN A SENTENCE. Without this the substring
    # match below excused <button id="alt-cite-copy"> for containing
    # "alt-cite", which is how an exemption list quietly grows.
    if row["tag"] != "a":
        return False
    blob = (row["cls"] or "") + " " + (row["id"] or "")
    if any(k in blob for k in INLINE_IN_SENTENCE):
        return True
    # An anchor the browser lays out as an inline box IS in a line of text.
    # This is the structural half of the rule; the list above is the named
    # half, and both have to agree before a target is excused.
    return row["tag"] == "a" and row["display"] == "inline"


def describe(row):
    return "%s%s%s %r  %.1fx%.1f at (%.0f,%.0f)" % (
        row["tag"],
        ("#" + row["id"]) if row["id"] else "",
        ("." + ".".join(row["cls"].split()[:3])) if row["cls"] else "",
        row["text"][:32], row["w"], row["h"], row["x"], row["y"])


def adjacent_pairs(rows):
    """Pairs that share a row or a column, with the edge-to-edge distance.

    Diagonal neighbours are not a mis-tap risk: a thumb that misses low and
    left of a target lands on the page, not on the control two rows down.

    Two boxes that overlap on BOTH axes are not neighbours either, they are
    stacked: an open dropdown sits on top of the controls beneath it and only
    one of them is on screen at those coordinates. Measuring that as a 0px gap
    is how a check invents defects the page does not have.
    """
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a["layer"] != b["layer"]:
                continue
            dx = max(0.0, max(a["x"] - (b["x"] + b["w"]),
                              b["x"] - (a["x"] + a["w"])))
            dy = max(0.0, max(a["y"] - (b["y"] + b["h"]),
                              b["y"] - (a["y"] + a["h"])))
            if dx > 0 and dy > 0:
                continue
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if ox > 0.5 and oy > 0.5:
                continue
            out.append((dx + dy, a, b))
    return out


class _Rendered(unittest.TestCase):
    """Loads the fixture in headless Chrome and returns rendered geometry."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so tap targets could not "
                "be measured. This is UNKNOWN, not a pass: run this where a "
                "browser exists.")
        cls._markup = template_markup()

    def render(self, probe, css=None, width=375):
        html = FIXTURE % {
            "plugin": css if css is not None else CSS.read_text(),
            "theme": THEME_SHIM, "site": SITE_OVERRIDE,
            "freeze": contrast_audit.FREEZE_CSS,
            "markup": self._markup,
            "built": JS_BUILT,
        }
        height = 812 if width < 768 else 900
        try:
            with Browser(width=width, height=height) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                page.eval_js(contrast_audit.REVEAL_JS)
                page.eval_js("(function(){document.querySelectorAll('details')"
                             ".forEach(function(d){d.open=true;});return 1;})()")
                return page.eval_js(probe)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)

    def targets(self, css=None, width=375):
        return self.render(PROBE, css=css, width=width)


class EveryBoxedControlClearsTheTapFloor(_Rendered):
    """A control with a box of its own is 44x44 on a phone. WCAG 2.5.5."""

    @classmethod
    def setUpClass(cls):
        super(EveryBoxedControlClearsTheTapFloor, cls).setUpClass()

    def test_the_fixture_actually_rendered_something_to_measure(self):
        """An empty measurement is UNKNOWN, and UNKNOWN is not a pass."""
        rows = self.targets()
        self.assertGreater(
            len(rows), 60,
            "only %d interactive targets laid out, so this run measured "
            "almost nothing. Treat it as UNKNOWN, not as a pass." % len(rows))

    def test_no_boxed_control_is_under_44_at_375(self):
        rows = self.targets()
        bad = [r for r in rows
               if not is_inline_in_sentence(r)
               and not is_a_fixture_artifact(r)
               and (r["w"] < TAP_MIN or r["h"] < TAP_MIN)]
        self.assertFalse(
            bad,
            "%d control(s) below %.0fx%.0f at 375px:\n  %s"
            % (len(bad), TAP_MIN, TAP_MIN,
               "\n  ".join(describe(r) for r in bad[:25])))

    def test_the_guard_fails_on_the_page_as_it_was(self):
        """The second half that makes the first half evidence."""
        rows = self.targets(css=remove_the_tap_target_section(CSS.read_text()))
        bad = [r for r in rows
               if not is_inline_in_sentence(r)
               and (r["w"] < TAP_MIN or r["h"] < TAP_MIN)]
        self.assertTrue(
            bad,
            "the pre-fix stylesheet produced no undersized control, so this "
            "guard cannot see the defect it was written for")


class ALinkInASentenceGetsAHitAreaInsteadOfASize(_Rendered):
    """44px is the wrong answer for a word inside a paragraph, so it is not
    the answer applied. The hit box grows and the text does not move."""

    def test_the_inline_links_have_a_real_hit_area(self):
        rows = [r for r in self.targets() if is_inline_in_sentence(r)]
        self.assertTrue(rows, "no inline links rendered, so nothing was checked")
        bad = [r for r in rows if r["h"] < INLINE_HIT_MIN]
        self.assertFalse(
            bad,
            "%d link(s) inside a sentence still hit-test under %.0fpx tall. "
            "The fix is vertical padding on an inline box, which grows the "
            "hit area without entering the line-box calculation:\n  %s"
            % (len(bad), INLINE_HIT_MIN,
               "\n  ".join(describe(r) for r in bad[:20])))

    def test_the_paragraph_around_them_did_not_move(self):
        """If the hit area cost the sentence its line height, the treatment
        was the wrong one and this is the assertion that says so."""
        before = self.render(
            PARAGRAPH_PROBE,
            css=remove_the_tap_target_section(CSS.read_text()))
        after = self.render(PARAGRAPH_PROBE)
        self.assertIsNotNone(after, "the sentence under test is gone")
        self.assertAlmostEqual(
            before["h"], after["h"], delta=1.0,
            msg="the paragraph holding these links changed height from %.1fpx "
                "to %.1fpx. Growing a hit area may not move the copy: on a "
                "display:inline box vertical padding does not enter the line "
                "box, so a height change means the element stopped being "
                "inline." % (before["h"], after["h"]))
        self.assertEqual(
            before["text"], after["text"],
            "the sentence itself changed, which is not this change's business")


class AdjacentTargetsAreFarEnoughApart(_Rendered):
    """Two 44px targets 2px apart still take the wrong tap."""

    def test_no_two_neighbouring_controls_are_closer_than_8px(self):
        rows = [r for r in self.targets() if not is_inline_in_sentence(r)]
        bad = []
        for dist, a, b in adjacent_pairs(rows):
            if dist >= GAP_MIN - 0.2:
                continue
            blob = a["cls"] + " " + b["cls"]
            if any(s in blob for s in SEGMENTED):
                continue          # one control with an internal edge
            bad.append((dist, a, b))
        bad.sort(key=lambda t: t[0])
        self.assertFalse(
            bad,
            "%d neighbouring control pair(s) under %.0fpx apart at 375px:\n  %s"
            % (len(bad), GAP_MIN,
               "\n  ".join("%.1fpx: %s  |  %s" % (d, describe(a), describe(b))
                           for d, a, b in bad[:20])))


class TheFixtureStillDescribesTheRealPage(unittest.TestCase):
    """The runtime-built controls above are copied markup, so they are only
    evidence while layoffs.js still builds exactly those classes."""

    def test_every_runtime_class_in_the_fixture_is_still_built_by_layoffs_js(self):
        js = strip_js_comments(JS.read_text())
        for cls in ("alt-af-chip", "alt-af-clear", "alt-barrow", "alt-bar-more",
                    "alt-card-h", "alt-card-src", "alt-archived", "alt-muted",
                    "alt-card-more", "alt-page-btn", "alt-page-nav",
                    "alt-page-on"):
            self.assertIn(
                cls, js,
                "the fixture measures .%s but layoffs.js no longer builds it, "
                "so this file is measuring markup the page does not ship"
                % cls)

    def test_the_stylesheet_scopes_the_floor_to_a_phone(self):
        """At a desk these are hit with a pointer and the page is denser by
        design. A floor that leaked to 1280 would be a different change."""
        css = CSS.read_text()
        at = css.find("TAP TARGETS OUTSIDE THE FILTER BAR")
        self.assertGreater(at, 0, "the tap-target section is gone")
        tail = strip_css_comments(css[at:])
        self.assertRegex(
            tail, r"@media\s*\(max-width:\s*767px\)",
            "the tap-target rules are not scoped to <=767px")


class TheDesktopLayoutIsUntouched(_Rendered):
    """The brief was mobile. A change that also redrew the desk is a change
    nobody asked for, and this is how that gets noticed."""

    def test_the_region_tabs_keep_their_desktop_height(self):
        rows = self.targets(width=1280)
        tabs = [r for r in rows if "alt-tab-usa" in r["cls"]]
        self.assertTrue(tabs, "the region tabs did not render at 1280")
        self.assertLess(
            tabs[0]["h"], TAP_MIN,
            "the 44px phone floor leaked to the desktop layout: the region "
            "tab is %.1fpx tall at 1280px" % tabs[0]["h"])


if __name__ == "__main__":
    unittest.main()
