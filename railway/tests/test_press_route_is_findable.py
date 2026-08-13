"""THE PRESS ROUTE IS ON THE FIRST SCREEN, AND IT IS A CONTROL.

WHY THIS FILE EXISTS. Journalists are this product's primary reader. The press
kit and soundbite library at /ai-layoff-tracker/press/ has been live since
2.19.61 and carries ready-to-quote statements with copy buttons, the evidence
ladder and the citation line. On 2026-08-13 the owner failed to find it twice
in one day, and he knew it was there.

Measured off the LIVE page that morning, bare URL, browser User-Agent, no cache
buster, ver=2.20.28, the only route to it was one text link among four inside
.alt-lead-links:

    viewport     link top edge      document height
    1280 x 900   13,252px            19,139px
     375 x 812   31,707px            44,128px

That is fifteen screens down on a desktop and thirty-nine on a phone. 2.20.27
had already fixed what the link SAID (it read "Press & media"; it now reads the
destination's own heading) without touching where it was, which is why the
owner could not find it after the fix either. A link that says the right thing
from the bottom of a forty-thousand-pixel page is not a route.

WHAT IS PINNED, and it is all reader-visible:

  * the press route renders WITHIN THE FIRST VIEWPORT at 375x812 and at
    1280x900. This is the assertion that fails on the pre-fix tree, and it is
    the only one that would have caught the defect;
  * it is a boxed control, not a word in a sentence: 44x44 at 375px with 8px
    to its neighbours, the floor the rest of this page already holds;
  * it says what the destination calls itself. The h1 on page-press.php is
    read out of that template and compared against the button's rendered
    innerText, so a rename of either surface breaks this rather than quietly
    producing a fifth name for one page;
  * its BOUNDARY clears 3:1 against its own fill, the page, and both stops of
    the hero gradient it sits on, in light, dark-by-choice and dark-by-OS.
    1.4.11 fails independently of 1.4.3: the theme switcher shipped with
    8.50:1 labels inside a control edged at 1.20:1 and every text check on
    this page was green throughout;
  * the hero FIGURE is above it, so no width can let this button push the
    number the page exists to publish;
  * the destination is offered ONCE. Two links to one page under one name,
    one of them thirty thousand pixels down, is the state this change ended.

HOW IT MEASURES. Geometry and text come from a real headless Chrome render of
the real template (PHP stripped, not a hand-written slice), through the same
fixture the tap-target suite uses. innerText, never textContent: a closed
<details> still carries textContent for text no reader can read. Contrast is
resolved from the tokens the RULES name, so renaming a token or restyling the
button re-measures rather than passing on a variable that happens to exist.

No Chrome, no measurement: this SKIPS loudly rather than passing. Absence of a
signal is not a pass (CLAUDE.md).

PROVEN TO FAIL ON THE PRE-FIX TREE. All twelve tests were run against
origin/main@8da7938 (2.20.28), the tree this change starts from. Six failed,
with these assertions:

    at 375x812 the press route's bottom edge is 9140px down
    at 1280x900 the press route's bottom edge is 4337px down
    layoffs.css has no rule '.alt-btn-press {'
    layoffs.css has no rule '.alt-btn-press:hover {'
    the button reads 'Press kit and soundbites' [and never says who it is for]
    the row of peer links still reads '... Press kit and soundbites ...'

(The two pixel figures are the FIXTURE's, which strips PHP and so renders a
shorter page than the live one. The live measurement is in the table above.)

The other six passed there and are named rather than left to look like proof
they are not:

    test_the_hero_figure_is_above_the_press_route
    test_the_three_other_routes_are_still_in_that_row
    test_it_clears_the_tap_floor_at_375
    test_it_is_8px_clear_of_its_neighbours_at_375
    test_the_button_carries_the_press_pages_own_heading
    test_the_copy_carries_no_dash_a_style_check_would_miss

Each describes something the old tree already had and this change had to
preserve rather than create. The old link was 44px tall and 8px clear because
2.20.11 gave every .alt-lead-links anchor a hit area; it already carried the
destination's own heading because 2.20.27 renamed it there; and it could not
push the hero figure because it was nine thousand pixels below it. They are
regression bars, not evidence.
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

from test_tap_targets import (  # noqa: E402
    FIXTURE, JS_BUILT, SITE_OVERRIDE, THEME_SHIM, template_markup,
)
from test_theme_light_dark import (  # noqa: E402
    DARK_EXPLICIT_SEL, DARK_MEDIA_SEL, LIGHT_SEL, block_body, contrast,
    strip_css_comments, tokens_in,
)

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = PLUGIN / "assets/layoffs.css"
TRACKER = PLUGIN / "templates/page-tracker.php"
PRESS = PLUGIN / "templates/page-press.php"

TAP_MIN = 44.0
GAP_MIN = 8.0
EDGE_MIN = 3.0    # WCAG 1.4.11, non-text contrast
TEXT_MIN = 4.5    # WCAG 1.4.3

PRESS_HREF = "/ai-layoff-tracker/press/"

# Every laid-out anchor and button on the page, with the two things a reader
# has: where it is, and what it says. Selection is by RENDERED TEXT rather
# than by class, so a rename of the class cannot make this file measure
# nothing and report a pass.
PROBE = r"""
(function () {
  var out = [];
  Array.prototype.forEach.call(
    document.querySelectorAll('a[href], button, [role="button"]'),
    function (el) {
      var cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      var r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      out.push({
        text: (el.innerText || '').replace(/\s+/g, ' ').trim(),
        x: +r.x.toFixed(1), y: +(r.y + window.scrollY).toFixed(1),
        w: +r.width.toFixed(1), h: +r.height.toFixed(1),
        display: cs.display
      });
    });
  var fig = document.querySelector('.alt-hero-figure-value');
  var fr = fig ? fig.getBoundingClientRect() : null;
  // innerText of the RENDERED ancestor, which is what the row reads as. The
  // separators between the links are text nodes on the row, not on the
  // anchors, so only the row itself carries what a reader sees.
  var row = document.querySelector('.alt-lead-links');
  return JSON.stringify({
    controls: out,
    viewport: window.innerHeight,
    lead_links_text: row ? (row.innerText || '').replace(/\s+/g, ' ').trim() : null,
    figure: fr ? {y: +(fr.y + window.scrollY).toFixed(1),
                  h: +fr.height.toFixed(1)} : null
  });
})()
"""


def press_page_heading():
    """The name the press page gives itself, read out of its own template.

    Typing "Press kit and soundbites" into this file as a constant would let
    the two surfaces drift apart while the test stayed green, which is the
    exact defect 2.20.27 was fixing on the other four links.
    """
    m = re.search(r"<h1>([^<]+)</h1>", PRESS.read_text())
    assert m, "page-press.php has no plain <h1> to read a name out of"
    return re.sub(r"\s+", " ", m.group(1)).strip()


class _Rendered(unittest.TestCase):
    """Loads the real template in headless Chrome and returns what it renders."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the press route could "
                "not be measured. This is UNKNOWN, not a pass: run this where "
                "a browser exists.")
        cls._markup = template_markup()
        cls._cache = {}

    def rendered(self, width):
        if width in self._cache:
            return self._cache[width]
        html = FIXTURE % {
            "plugin": CSS.read_text(),
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
                data = json.loads(page.eval_js(PROBE))
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        self._cache[width] = data
        return data

    def press_control(self, width):
        """The control a journalist would click, found by what it says.

        Deliberately NOT found by class or id: a test that selects
        `.alt-btn-press` proves a class name exists, and this file is about
        whether a reader can see and tap the thing.
        """
        heading = press_page_heading()
        data = self.rendered(width)
        hits = sorted(
            [c for c in data["controls"] if heading.lower() in c["text"].lower()],
            key=lambda c: c["y"])
        self.assertTrue(
            hits,
            "at %dpx nothing a reader can see and click says %r. The route to "
            "the press kit is either absent or renders no text."
            % (width, heading))
        # THE TOPMOST ONE, because that is the one a reader meets. The page
        # also carries a colophon link in the provenance footer, which is a
        # different register and not a competing headline route; what this
        # file forbids is the press kit ranking BELOW anything, and a second
        # copy sharing the first screen with the button.
        first = hits[0]
        on_screen = [c for c in hits if c["y"] + c["h"] < data["viewport"]]
        self.assertLessEqual(
            len(on_screen), 1,
            "at %dpx the first screen offers %d controls all saying %r. One "
            "destination under one name, twice on one screen, reads as two "
            "different pages." % (width, len(on_screen), heading))
        return first, data


class ThePressRouteIsOnTheFirstScreen(_Rendered):
    """The assertion the defect would have failed. Everything else is a bar."""

    def test_a_journalist_meets_it_on_the_first_screen_on_a_phone(self):
        ctl, data = self.press_control(375)
        self.assertLess(
            ctl["y"] + ctl["h"], data["viewport"],
            "at 375x%d the press route's bottom edge is %.0fpx down, so a "
            "journalist has to scroll to find the page written for them. "
            "Measured live on 2026-08-13 it was 31,707px down a 44,128px "
            "document, which is thirty-nine screens."
            % (data["viewport"], ctl["y"] + ctl["h"]))

    def test_a_journalist_meets_it_on_the_first_screen_on_a_desktop(self):
        ctl, data = self.press_control(1280)
        self.assertLess(
            ctl["y"] + ctl["h"], data["viewport"],
            "at 1280x%d the press route's bottom edge is %.0fpx down, so it is "
            "below the fold on the widest layout this page has. Measured live "
            "on 2026-08-13 it was 13,252px down."
            % (data["viewport"], ctl["y"] + ctl["h"]))

    def test_the_hero_figure_is_above_the_press_route(self):
        """The number the page exists to publish cannot be pushed by this.

        A regression bar, not evidence: the pre-fix tree had no button here to
        violate it. It is what makes "costs the first screen nothing" checkable
        rather than a claim in a commit message.
        """
        for width in (375, 1280):
            ctl, data = self.press_control(width)
            fig = data["figure"]
            self.assertIsNotNone(
                fig, "at %dpx the hero figure did not render at all" % width)
            self.assertLessEqual(
                fig["y"] + fig["h"], ctl["y"],
                "at %dpx the press route starts at %.0fpx, above the bottom of "
                "the hero figure at %.0fpx. Anything placed above that figure "
                "moves it down on every screen."
                % (width, ctl["y"], fig["y"] + fig["h"]))


class ThePressRouteIsAControlAThumbCanHit(_Rendered):
    """44x44 with 8px of clearance, the floor the rest of this page holds."""

    def test_it_clears_the_tap_floor_at_375(self):
        ctl, _ = self.press_control(375)
        self.assertGreaterEqual(
            ctl["h"], TAP_MIN,
            "the press route is %.1fpx tall at 375px, under the %.0fpx floor "
            "(WCAG 2.5.5). It is a route, not a word in a sentence: %r"
            % (ctl["h"], TAP_MIN, ctl["text"]))
        self.assertGreaterEqual(
            ctl["w"], TAP_MIN,
            "the press route is %.1fpx wide at 375px, under the %.0fpx floor"
            % (ctl["w"], TAP_MIN))
        self.assertNotEqual(
            "inline", ctl["display"],
            "the press route lays out as an inline box, which is what a link "
            "inside a paragraph does. It was one of those and that is the "
            "defect: %r" % ctl["text"])

    def test_it_is_8px_clear_of_its_neighbours_at_375(self):
        ctl, data = self.press_control(375)
        bad = []
        for other in data["controls"]:
            if other is ctl or (other["x"], other["y"]) == (ctl["x"], ctl["y"]):
                continue
            dx = max(0.0, max(ctl["x"] - (other["x"] + other["w"]),
                              other["x"] - (ctl["x"] + ctl["w"])))
            dy = max(0.0, max(ctl["y"] - (other["y"] + other["h"]),
                              other["y"] - (ctl["y"] + ctl["h"])))
            if dx > 0 and dy > 0:
                continue           # diagonal: a missed tap lands on the page
            if dx + dy < GAP_MIN - 0.05:
                bad.append("%.1fpx from %r" % (dx + dy, other["text"][:40]))
        self.assertEqual(
            [], bad,
            "the press route sits under %.0fpx from a neighbouring control, so "
            "a thumb aimed at it takes the other one:\n  %s"
            % (GAP_MIN, "\n  ".join(bad)))


class ThePressRouteSaysWhatTheDestinationCallsItself(_Rendered):

    def test_the_button_carries_the_press_pages_own_heading(self):
        heading = press_page_heading()
        ctl, _ = self.press_control(1280)
        self.assertIn(
            heading.lower(), ctl["text"].lower(),
            "the press route reads %r and the page it opens is headed %r. "
            "This page has already shipped four names for one destination; a "
            "fifth is not an improvement." % (ctl["text"], heading))

    def test_it_says_who_it_is_for_without_renaming_the_page(self):
        ctl, _ = self.press_control(1280)
        self.assertIn(
            "for press", ctl["text"].lower(),
            "the button reads %r. The owner's question was 'are you press, "
            "click here', and a reader scanning for themselves should not "
            "have to infer that a press kit is for them." % ctl["text"])

    def test_the_copy_carries_no_dash_a_style_check_would_miss(self):
        """style_check.py needs 12 characters and 3 real words before a string
        is eligible, so a short button label slips past it entirely."""
        ctl, _ = self.press_control(1280)
        for ch, name in (("—", "em dash"), ("–", "en dash")):
            self.assertNotIn(
                ch, ctl["text"],
                "the press button copy %r carries an %s" % (ctl["text"], name))


class ThePressRouteHasAVisibleBoundaryInEveryTheme(unittest.TestCase):
    """1.4.11, which fails independently of every text check on this page.

    The theme switcher shipped at 8.50:1 for its labels inside a control whose
    edge was 1.20:1. Ratios are recomputed from the tokens the RULES name, so
    this cannot pass because a variable happens to exist.
    """

    BTN = ".alt-btn {"
    PRESS = ".alt-btn-press {"
    TAG = ".alt-btn-tag {"

    def setUp(self):
        self.css = strip_css_comments(CSS.read_text())
        light = tokens_in(block_body(self.css, LIGHT_SEL))
        self.palettes = {"light": light}
        for label, sel in (("dark (OS preference)", DARK_MEDIA_SEL),
                           ("dark (chosen)", DARK_EXPLICIT_SEL)):
            merged = dict(light)
            merged.update(tokens_in(block_body(self.css, sel)))
            self.palettes[label] = merged

    def _decl(self, selector, prop, fallback=None):
        body = block_body(self.css, selector)
        self.assertTrue(body.strip(), "rule %r does not exist" % selector)
        m = re.search(r"(?:^|[;{\s])%s\s*:\s*([^;}]+)" % re.escape(prop), body)
        if not m:
            if fallback is None:
                raise AssertionError("rule %r declares no %r" % (selector, prop))
            return fallback
        return m.group(1).strip()

    def _colour(self, palette, value, label):
        seen = 0
        while True:
            m = re.search(r"var\(\s*(--alt-[a-z0-9-]+)", value)
            if not m:
                break
            name = m.group(1)
            self.assertIn(name, palette, "%s: %s is not defined" % (label, name))
            value = palette[name]
            seen += 1
            self.assertLess(seen, 10, "%s: var() indirection loops" % label)
        m = re.search(r"#[0-9a-fA-F]{3,6}\b", value)
        self.assertTrue(m, "%s: %r does not resolve to a colour" % (label, value))
        return m.group(0)

    def test_the_boundary_and_the_labels_clear_their_bars(self):
        bad = []
        for label in sorted(self.palettes):
            pal = self.palettes[label]
            fill = self._colour(pal, self._decl(self.PRESS, "background"), label)
            edge = self._colour(pal, self._decl(self.PRESS, "border-color"), label)
            ink = self._colour(pal, self._decl(self.PRESS, "color"), label)
            tag = self._colour(pal, self._decl(self.TAG, "color"), label)
            page = self._colour(pal, "var(--alt-page)", label)
            # BOTH stops of the hero gradient, because the actions row sits
            # partway down it and neither stop is "the" background.
            hero_top = self._colour(pal, "var(--alt-red-tint)", label)
            hero_bottom = self._colour(pal, "var(--alt-surface)", label)
            pairs = [
                ("edge vs its own fill", edge, fill, EDGE_MIN),
                ("edge vs the page", edge, page, EDGE_MIN),
                ("edge vs the hero gradient top", edge, hero_top, EDGE_MIN),
                ("edge vs the hero gradient bottom", edge, hero_bottom, EDGE_MIN),
                ("the label on its own fill", ink, fill, TEXT_MIN),
                ("the 'for press' tag on its own fill", tag, fill, TEXT_MIN),
            ]
            for what, fg, bg, need in pairs:
                got = contrast(fg, bg)
                if got < need - 0.005:
                    bad.append("%s: %s (%s on %s) = %.2f:1, need %.1f"
                               % (label, what, fg, bg, got, need))
        self.assertEqual(
            [], bad,
            "the press button is not visible as a control:\n  " + "\n  ".join(bad))

    def test_hover_does_not_dissolve_the_boundary(self):
        """.alt-btn:hover repaints the edge in --alt-chart-dim, which on this
        button's own fill is ~1.2:1. A control that loses its outline the
        moment a pointer arrives is a control that fails 1.4.11 while
        somebody is using it."""
        bad = []
        for label in sorted(self.palettes):
            pal = self.palettes[label]
            fill = self._colour(
                pal, self._decl(".alt-btn-press:hover {", "background"), label)
            edge = self._colour(
                pal, self._decl(".alt-btn-press:hover {", "border-color"), label)
            got = contrast(edge, fill)
            if got < EDGE_MIN - 0.005:
                bad.append("%s: hovered edge (%s on %s) = %.2f:1"
                           % (label, edge, fill, got))
        self.assertEqual([], bad, "the press button loses its edge on hover:\n  "
                                 + "\n  ".join(bad))


PRESS_FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%(plugin)s</style>
<style>%(theme)s</style>
<style>%(site)s</style>
<style>%(freeze)s</style>
</head>
<body class="wp-singular page-template-default page">
<div class="wp-site-blocks"><main class="wp-block-group has-global-padding">
<div class="wp-block-group alignfull"><div class="entry-content alignfull">
%(markup)s
</div></div></main></div>
</body></html>"""


class TheSoundbiteLibraryIsAnnouncedOnThePressPagesFirstScreen(unittest.TestCase):
    """The same discoverability defect, one page later.

    A journalist who takes the new button lands on a page whose reason to
    exist is the soundbite library and the ready-to-quote statements. Measured
    live at 375x812 on 2026-08-13, before this change: the h1 at 273px, the
    jump menu at 943px, the first quotable statement at 4,858px on a 26,289px
    page. Nothing on the first screen said the statements were there.

    What is asserted is the ANNOUNCEMENT, not the statements themselves. Two
    "before you quote a number" sections stand between the menu and the first
    card and they earn their place: a reporter who quotes the wrong basis
    writes a wrong sentence. The menu is how somebody skips them deliberately,
    so the menu is what has to be visible.
    """

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the press page could "
                "not be measured. UNKNOWN, not a pass.")

    def render(self, width, height):
        markup = re.sub(r"<\?php.*?\?>", "", PRESS.read_text(), flags=re.S)
        html = PRESS_FIXTURE % {
            "plugin": CSS.read_text(), "theme": THEME_SHIM,
            "site": SITE_OVERRIDE, "freeze": contrast_audit.FREEZE_CSS,
            "markup": markup,
        }
        probe = r"""
        (function () {
          function m(sel) {
            var el = document.querySelector(sel);
            if (!el) return null;
            var r = el.getBoundingClientRect();
            return {top: +(r.top + window.scrollY).toFixed(1),
                    bottom: +(r.bottom + window.scrollY).toFixed(1),
                    text: (el.innerText || '').replace(/\s+/g, ' ').trim()};
          }
          return JSON.stringify({
            h1: m('h1'), nav: m('.alt-press-toc'), vh: window.innerHeight});
        })()
        """
        try:
            with Browser(width=width, height=height) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                page.eval_js(contrast_audit.REVEAL_JS)
                return json.loads(page.eval_js(probe))
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)

    def test_the_jump_menu_is_on_the_first_screen_on_a_phone(self):
        d = self.render(375, 812)
        self.assertIsNotNone(d["nav"], "the press page's jump menu is gone")
        self.assertLess(
            d["nav"]["bottom"], d["vh"],
            "the press page's jump menu ends %.0fpx down a %dpx screen, so a "
            "journalist who arrives on a phone is told nothing about the "
            "soundbite library before they scroll. It read %r"
            % (d["nav"]["bottom"], d["vh"], d["nav"]["text"][:60]))

    def test_the_menu_names_the_soundbites_and_the_ready_made_numbers(self):
        d = self.render(375, 812)
        text = d["nav"]["text"].lower()
        for expected in ("soundbites", "numbers to use now"):
            self.assertIn(
                expected, text,
                "the jump menu no longer offers %r, which is the thing this "
                "page exists for. It reads %r" % (expected, d["nav"]["text"]))

    def test_the_heading_still_comes_first(self):
        """A menu above the title would be a worse page than the defect."""
        d = self.render(375, 812)
        self.assertLess(
            d["h1"]["top"], d["nav"]["top"],
            "the jump menu was moved above the page's own heading")


class ThePressLinkLeftTheRowOfPeerLinks(_Rendered):
    """The demotion half of the change, read off the rendered row.

    .alt-lead-links is a row of four peer text links inside the data strip,
    which starts 30,955px down at 375px. While the press kit was one of them
    it was, by construction, indistinguishable from the three links beside it
    and unreachable without thirty screens of scrolling. Promoting it to a
    button and leaving the peer link behind would offer one destination twice
    under one name, at two wildly different weights, which is how a reader
    concludes they are two different pages.

    The three links that remain are untouched: the monthly report, the quotes
    page and the embed tools. None of them has a route above it, so none of
    them is duplicated by anything, and removing any of them would delete
    somebody's only way in.
    """

    def test_the_data_strip_row_no_longer_names_the_press_page(self):
        heading = press_page_heading()
        text = self.rendered(1280)["lead_links_text"]
        self.assertIsNotNone(
            text, "the .alt-lead-links row did not render at all. This change "
                  "demoted one link out of it and must not have removed it.")
        self.assertNotIn(
            heading.lower(), text.lower(),
            "the row of peer links still reads %r. The press kit is a button "
            "in the hero now; the same name twice on one page, once at the top "
            "and once 30,955px down, reads as two destinations." % text)

    def test_the_three_other_routes_are_still_in_that_row(self):
        text = self.rendered(1280)["lead_links_text"].lower()
        # The quotes link's label is written by alt_page_link_label() and the
        # fixture strips PHP rather than executing it, so that one anchor
        # renders empty here. Asserting on it would be asserting on the
        # fixture. Its href is checked below instead.
        for expected in ("monthly report", "embed this tracker"):
            self.assertIn(
                expected, text,
                "the peer-link row no longer offers %r. Only the press link "
                "was demoted, because only it gained a better route; the other "
                "three are somebody's only way to those pages." % expected)
        src = re.sub(r"/\*.*?\*/", " ", TRACKER.read_text(), flags=re.S)
        self.assertIn(
            "/ai-layoff-tracker/ai-quotes/", src,
            "the quotes page lost its only route off the tracker. Its label is "
            "written by PHP so the render cannot see it; the href is the only "
            "thing left to check.")
