"""THE EMAIL DIGEST HAS A ROUTE ON THE FIRST SCREEN, AND THE JUMP LANDS.

WHY THIS FILE EXISTS. This is the press-route defect a second time, on a
second surface. The digest signup is live, it works, and until this change the
only way to reach it was to scroll to the bottom of the page. Measured off the
LIVE page on 2026-08-14, bare URL, browser User-Agent, no cache buster,
ver=2.20.50:

    viewport     digest section top    document height
    1280 x 900   17,731px              18,849px
     375 x 812   40,744px              42,483px

That is nineteen screens down on a desktop and fifty on a phone, and unlike
the press kit there was not even a text link pointing at it from anywhere
above. The fix is the one that worked for the press kit: a control in
.alt-hero-actions, same family and same weight as the three already there.

THE SECOND HALF, WHICH THE PRESS CHANGE HAD TO LEARN THE HARD WAY. This route
is a same-page jump, so shipping the button is only half of it. The press
page's own jump menu ended 847px down an 812px screen, which is a menu nobody
on a phone ever saw. A jump that lands with the signup's email field below the
fold is the same defect wearing the fix's clothes, so what is asserted here is
the LANDING: after the browser follows the hash, the section's heading, its
email field and its submit button are all inside the viewport at 375x812 and
at 1280x900.

WHAT IS PINNED, all of it reader-visible:

  * the digest route renders WITHIN THE FIRST VIEWPORT at 375x812 and at
    1280x900. This is the assertion that fails on the pre-fix tree;
  * it is a boxed control, 44x44 at 375 and at 414, with 8px to its
    neighbours, the floor the rest of this page already holds;
  * it says what the destination calls itself: the h2 of the signup section
    is read out of includes/subscribe.php and compared against the button's
    rendered innerText, so renaming either surface breaks this rather than
    quietly producing a second name for one thing;
  * FOLLOWING IT LANDS SOMEWHERE USABLE. Heading, email field and submit
    button all on screen at both widths;
  * its boundary clears 3:1 against its own fill, the page and both stops of
    the hero gradient, in light, dark-by-choice and dark-by-OS, hover
    included. .alt-btn:hover repaints the edge in --alt-chart-dim, which is
    ~1.2:1 on a light fill: a control that dissolves its own outline the
    moment a pointer arrives fails 1.4.11 while somebody is using it, and the
    stock hover is what this button would have inherited;
  * the hero FIGURE stays above it, so no width lets this push the number the
    page exists to publish;
  * no horizontal document overflow at 375, 414, 768, 1024 or 1280.

HOW IT MEASURES. Geometry and text come from a real headless Chrome render of
the real template, with the real signup component spliced in at the point the
template calls it (both are read from their own files with PHP stripped, never
hand-written here). innerText, never textContent. Controls are found by what
they SAY, never by class.

No Chrome, no measurement: this SKIPS loudly rather than passing. Absence of a
signal is not a pass (CLAUDE.md).

PROVEN TO FAIL ON THE PRE-FIX TREE. Run against the tree this change starts
from, these assertions failed:

    at 375x812 nothing a reader can see and click says 'Email digest'
    at 1280x900 nothing a reader can see and click says 'Email digest'
    at 414x896 nothing a reader can see and click says 'Email digest'
    layoffs.css has no rule '.alt-btn-digest {'
    layoffs.css has no rule '.alt-btn-digest:hover {'
    at 375x812 the jump leaves the email field 871px down an 812px screen

The remaining tests passed there and are named rather than left to look like
proof they are not: the no-overflow bars and the hero-figure bar describe
things the old tree already had and this change had to preserve.
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
    FIXTURE, JS_BUILT, SITE_OVERRIDE, THEME_SHIM,
)
from test_theme_light_dark import (  # noqa: E402
    DARK_EXPLICIT_SEL, DARK_MEDIA_SEL, LIGHT_SEL, block_body, contrast,
    strip_css_comments, tokens_in,
)

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = PLUGIN / "assets/layoffs.css"
TRACKER = PLUGIN / "templates/page-tracker.php"
SUBSCRIBE = PLUGIN / "includes/subscribe.php"

TAP_MIN = 44.0
GAP_MIN = 8.0
EDGE_MIN = 3.0    # WCAG 1.4.11, non-text contrast
TEXT_MIN = 4.5    # WCAG 1.4.3

PHONE_WIDTHS = (375, 414)

# THE THEME'S HORIZONTAL GUTTER, AND WHY THIS FILE CARRIES IT.
#
# The shared fixture wraps the markup in `.has-global-padding` and then styles
# nothing, so a 375px viewport renders this page's content 375px wide. The live
# page renders it 339px wide: 18px of gutter each side, measured off
# asktherecruiter.com at 375x812 on 2026-08-15 at ver=2.20.52.
#
# 36px of phantom width is not cosmetic here. The signup's email row is
# `flex-basis: 220px` for the field plus an 8px gap plus a ~106px button, which
# fits on one line at 375 and wraps at 339. Without this rule the landing test
# measured an unwrapped row, reported 741.7px on an 812px screen and passed,
# and the live page put the Subscribe button 15px BELOW the fold. Every
# geometry claim in this file is about a phone, and a phone has gutters.
SITE_GUTTER = """
.wp-block-group.has-global-padding { padding-left: 18px; padding-right: 18px; }
"""


def digest_markup():
    """The signup component, read out of the file that ships it.

    The tracker template reaches it through a PHP function call, so the
    PHP-stripping fixture the rest of this suite uses renders a page with no
    signup on it at all, and every assertion about the landing would measure
    nothing. Slicing it out by its own landmarks (its self-carried <style>
    block through the close of its <section>) keeps this describing the real
    component: restructure it and this raises rather than quietly shrinking.
    """
    src = SUBSCRIBE.read_text()
    start = src.find("<style>\n    .alt-digest {")
    assert start >= 0, (
        "the signup component no longer opens with its self-carried <style> "
        "block, so this fixture cannot find it in subscribe.php")
    end = src.find("</section>", start)
    assert end >= 0, "the signup component's <section> is not closed"
    return re.sub(r"<\?php.*?\?>", "", src[start:end + len("</section>")],
                  flags=re.S)


def digest_heading():
    """The name the signup gives itself, read out of its own source.

    Typing the label into this file as a constant would let the button and the
    thing it opens drift apart while the test stayed green.
    """
    m = re.search(r'<section class="alt-digest"[^>]*>\s*<h2>([^<]+)</h2>',
                  SUBSCRIBE.read_text())
    assert m, "the signup section has no plain <h2> to read a name out of"
    return re.sub(r"\s+", " ", m.group(1)).strip()


def markup_with_the_digest():
    """The whole tracker template, PHP stripped, signup spliced in where the
    template actually calls it, so it is measured in its real position."""
    src = TRACKER.read_text()
    call = re.search(r"<\?php(?:(?!\?>).)*alt_digest_subscribe_form(?:(?!\?>).)*\?>",
                     src, re.S)
    assert call, ("page-tracker.php no longer calls alt_digest_subscribe_form, "
                  "so the signup does not render on the tracker at all")
    marker = "<!--ALT-DIGEST-SPLICE-->"
    src = src[:call.start()] + marker + src[call.end():]
    html = re.sub(r"<\?php.*?\?>", "", src, flags=re.S)
    assert marker in html
    return html.replace(marker, digest_markup())


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
  return JSON.stringify({
    controls: out,
    viewport: window.innerHeight,
    overflow: +(document.documentElement.scrollWidth
                - document.documentElement.clientWidth).toFixed(1),
    figure: fr ? {y: +(fr.y + window.scrollY).toFixed(1),
                  h: +fr.height.toFixed(1)} : null
  });
})()
"""

# What a reader has to be able to see and use once the jump has landed: the
# name of the thing, the field, and the control that submits it. Read by
# rendered text and by the field's own label, never by class.
LANDING_PROBE = r"""
(function () {
  function box(el) {
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return {top: +r.top.toFixed(1), bottom: +r.bottom.toFixed(1),
            text: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60)};
  }
  var sec = document.querySelector('#alt-digest');
  if (!sec) return JSON.stringify({missing: true});
  var heading = sec.querySelector('h2');
  var field = sec.querySelector('input[type="email"]');
  var submit = null;
  Array.prototype.forEach.call(sec.querySelectorAll('button'), function (b) {
    if (!submit && b.type === 'submit') submit = b;
  });
  return JSON.stringify({
    vh: window.innerHeight,
    heading: box(heading), field: box(field), submit: box(submit)
  });
})()
"""


class _Rendered(unittest.TestCase):
    """Loads the real template in headless Chrome and returns what it renders."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the digest route could "
                "not be measured. This is UNKNOWN, not a pass: run this where "
                "a browser exists.")
        cls._markup = markup_with_the_digest()
        cls._cache = {}

    def _html(self):
        return FIXTURE % {
            "plugin": CSS.read_text(),
            "theme": THEME_SHIM, "site": SITE_OVERRIDE + SITE_GUTTER,
            "freeze": contrast_audit.FREEZE_CSS,
            "markup": self._markup,
            "built": JS_BUILT,
        }

    def _page(self, page, html):
        page.call("Page.navigate", {"url": "about:blank"})
        page.eval_js(
            "(function(){document.open();document.write(%s);"
            "document.close();return true;})()" % json.dumps(html))
        page.eval_js(contrast_audit.REVEAL_JS)

    def rendered(self, width, height=None):
        height = height or (812 if width < 768 else 900)
        key = (width, height)
        if key in self._cache:
            return self._cache[key]
        try:
            with Browser(width=width, height=height) as page:
                self._page(page, self._html())
                data = json.loads(page.eval_js(PROBE))
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        self._cache[key] = data
        return data

    def digest_control(self, width, height=None):
        """The control a reader would click, found by what it says."""
        heading = digest_heading()
        data = self.rendered(width, height)
        hits = sorted(
            [c for c in data["controls"]
             if heading.lower() in c["text"].lower()],
            key=lambda c: c["y"])
        self.assertTrue(
            hits,
            "at %dx%d nothing a reader can see and click says %r. The route "
            "to the signup is either absent or renders no text."
            % (width, data["viewport"], heading))
        first = hits[0]
        on_screen = [c for c in hits if c["y"] + c["h"] < data["viewport"]]
        self.assertLessEqual(
            len(on_screen), 1,
            "at %dpx the first screen offers %d controls all saying %r. One "
            "destination under one name, twice on one screen, reads as two "
            "different things." % (width, len(on_screen), heading))
        return first, data


class TheDigestRouteIsOnTheFirstScreen(_Rendered):
    """The assertion the defect would have failed. Everything else is a bar."""

    def test_a_reader_meets_it_on_the_first_screen_on_a_phone(self):
        ctl, data = self.digest_control(375)
        self.assertLess(
            ctl["y"] + ctl["h"], data["viewport"],
            "at 375x%d the digest route's bottom edge is %.0fpx down, so a "
            "reader has to scroll to be offered the emails. Measured live on "
            "2026-08-14 the signup itself was 40,744px down a 42,483px "
            "document, which is fifty screens."
            % (data["viewport"], ctl["y"] + ctl["h"]))

    def test_a_reader_meets_it_on_the_first_screen_on_a_desktop(self):
        ctl, data = self.digest_control(1280)
        self.assertLess(
            ctl["y"] + ctl["h"], data["viewport"],
            "at 1280x%d the digest route's bottom edge is %.0fpx down, so it "
            "is below the fold on the widest layout this page has. Measured "
            "live on 2026-08-14 the signup was 17,731px down."
            % (data["viewport"], ctl["y"] + ctl["h"]))

    def test_the_hero_figure_is_above_the_digest_route(self):
        """The number the page exists to publish cannot be pushed by this."""
        for width in (375, 1280):
            ctl, data = self.digest_control(width)
            fig = data["figure"]
            self.assertIsNotNone(
                fig, "at %dpx the hero figure did not render at all" % width)
            self.assertLessEqual(
                fig["y"] + fig["h"], ctl["y"],
                "at %dpx the digest route starts at %.0fpx, above the bottom "
                "of the hero figure at %.0fpx. Anything placed above that "
                "figure moves it down on every screen."
                % (width, ctl["y"], fig["y"] + fig["h"]))


class FollowingTheDigestRouteLandsSomewhereUsable(_Rendered):
    """A jump that lands with the field off-screen is the defect, not the fix.

    The press page's own jump menu ended 847px down an 812px screen and that
    was shipped as a fix. This asserts the LANDING, not the anchor.
    """

    def landing(self, width, height):
        html = self._html()
        try:
            with Browser(width=width, height=height) as page:
                self._page(page, html)
                # The reader's action: follow the hash the button carries.
                page.eval_js("(function(){location.hash='';"
                             "location.hash='alt-digest';return true;})()")
                data = json.loads(page.eval_js(LANDING_PROBE))
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        self.assertFalse(
            data.get("missing"),
            "there is no #alt-digest on the page, so the hero button's href "
            "points at nothing")
        return data

    def _assert_lands(self, width, height):
        d = self.landing(width, height)
        for part in ("heading", "field", "submit"):
            box = d[part]
            self.assertIsNotNone(
                box, "the signup has no %s after the jump" % part)
            self.assertGreaterEqual(
                box["top"], 0,
                "at %dx%d the jump scrolls the signup's %s %.0fpx above the "
                "top of the screen" % (width, height, part, -box["top"]))
            self.assertLessEqual(
                box["bottom"], d["vh"],
                "at %dx%d the jump leaves the signup's %s %.0fpx down a %dpx "
                "screen, so a reader who takes the route lands on a form they "
                "still have to hunt for. This is the press page's jump menu "
                "ending 847px down an 812px screen, again."
                % (width, height, part, box["bottom"], d["vh"]))

    def test_the_jump_lands_the_whole_signup_on_screen_on_a_phone(self):
        self._assert_lands(375, 812)

    def test_the_jump_lands_the_whole_signup_on_screen_on_a_desktop(self):
        self._assert_lands(1280, 900)


class TheDigestRouteIsAControlAThumbCanHit(_Rendered):
    """44x44 with 8px of clearance, the floor the rest of this page holds."""

    def test_it_clears_the_tap_floor_on_both_phone_widths(self):
        for width in PHONE_WIDTHS:
            ctl, _ = self.digest_control(width, 812 if width == 375 else 896)
            self.assertGreaterEqual(
                ctl["h"], TAP_MIN,
                "the digest route is %.1fpx tall at %dpx, under the %.0fpx "
                "floor (WCAG 2.5.5). It is a route, not a word in a sentence: "
                "%r" % (ctl["h"], width, TAP_MIN, ctl["text"]))
            self.assertGreaterEqual(
                ctl["w"], TAP_MIN,
                "the digest route is %.1fpx wide at %dpx, under the %.0fpx "
                "floor" % (ctl["w"], width, TAP_MIN))
            self.assertNotEqual(
                "inline", ctl["display"],
                "the digest route lays out as an inline box, which is what a "
                "link inside a paragraph does: %r" % ctl["text"])

    def test_it_is_8px_clear_of_its_neighbours_at_375(self):
        ctl, data = self.digest_control(375)
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
            "the digest route sits under %.0fpx from a neighbouring control, "
            "so a thumb aimed at it takes the other one:\n  %s"
            % (GAP_MIN, "\n  ".join(bad)))


class TheDigestRouteSaysWhatItOpens(_Rendered):

    def test_the_button_carries_the_signups_own_heading(self):
        heading = digest_heading()
        ctl, _ = self.digest_control(1280)
        self.assertIn(
            heading.lower(), ctl["text"].lower(),
            "the digest route reads %r and the thing it opens is headed %r. "
            "Two names for one destination is how a reader concludes they are "
            "two destinations." % (ctl["text"], heading))

    def test_it_says_how_often_without_renaming_the_signup(self):
        ctl, _ = self.digest_control(1280)
        self.assertIn(
            "weekly or daily", ctl["text"].lower(),
            "the button reads %r. 'How often will you email me' is the first "
            "question anyone asks of a signup, and the answer is a choice the "
            "form already offers." % ctl["text"])

    def test_the_copy_carries_no_dash_a_style_check_would_miss(self):
        """style_check.py needs 12 characters and 3 real words before a string
        is eligible, so a short button label slips past it entirely."""
        ctl, _ = self.digest_control(1280)
        for ch, name in (("—", "em dash"), ("–", "en dash")):
            self.assertNotIn(
                ch, ctl["text"],
                "the digest button copy %r carries an %s" % (ctl["text"], name))


class NothingBleedsSidewaysAtAnyWidth(_Rendered):
    """A regression bar. The hero row gained a fourth control; a control that
    cannot wrap widens the document instead."""

    def test_no_horizontal_document_overflow(self):
        bad = []
        for width in (375, 414, 768, 1024, 1280):
            data = self.rendered(width, 812 if width < 768 else 900)
            if data["overflow"] > 0.5:
                bad.append("%dpx: document is %.1fpx wider than the viewport"
                           % (width, data["overflow"]))
        self.assertEqual([], bad, "the page bleeds sideways:\n  "
                                  + "\n  ".join(bad))


class TheDigestRouteHasAVisibleBoundaryInEveryTheme(unittest.TestCase):
    """1.4.11, which fails independently of every text check on this page."""

    BTN = ".alt-btn-digest {"
    HOVER = ".alt-btn-digest:hover {"
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
                raise AssertionError("rule %r declares no %r"
                                     % (selector, prop))
            return fallback
        return m.group(1).strip()

    def _colour(self, palette, value, label):
        seen = 0
        while True:
            m = re.search(r"var\(\s*(--alt-[a-z0-9-]+)", value)
            if not m:
                break
            name = m.group(1)
            self.assertIn(name, palette,
                          "%s: %s is not defined" % (label, name))
            value = palette[name]
            seen += 1
            self.assertLess(seen, 10, "%s: var() indirection loops" % label)
        m = re.search(r"#[0-9a-fA-F]{3,6}\b", value)
        self.assertTrue(m, "%s: %r does not resolve to a colour"
                        % (label, value))
        return m.group(0)

    def test_the_boundary_and_the_labels_clear_their_bars(self):
        bad = []
        for label in sorted(self.palettes):
            pal = self.palettes[label]
            fill = self._colour(pal, self._decl(self.BTN, "background"), label)
            edge = self._colour(pal, self._decl(self.BTN, "border-color"), label)
            ink = self._colour(pal, self._decl(self.BTN, "color"), label)
            tag = self._colour(pal, self._decl(
                ".alt-btn-digest .alt-btn-tag {", "color"), label)
            page = self._colour(pal, "var(--alt-page)", label)
            hero_top = self._colour(pal, "var(--alt-red-tint)", label)
            hero_bottom = self._colour(pal, "var(--alt-surface)", label)
            pairs = [
                ("edge vs its own fill", edge, fill, EDGE_MIN),
                ("edge vs the page", edge, page, EDGE_MIN),
                ("edge vs the hero gradient top", edge, hero_top, EDGE_MIN),
                ("edge vs the hero gradient bottom", edge, hero_bottom,
                 EDGE_MIN),
                ("the label on its own fill", ink, fill, TEXT_MIN),
                ("the cadence tag on its own fill", tag, fill, TEXT_MIN),
            ]
            for what, fg, bg, need in pairs:
                got = contrast(fg, bg)
                if got < need - 0.005:
                    bad.append("%s: %s (%s on %s) = %.2f:1, need %.1f"
                               % (label, what, fg, bg, got, need))
        self.assertEqual(
            [], bad,
            "the digest button is not visible as a control:\n  "
            + "\n  ".join(bad))

    def test_hover_does_not_dissolve_the_boundary(self):
        """.alt-btn:hover repaints the edge in --alt-chart-dim, ~1.2:1 on a
        light fill. This button must not inherit that."""
        bad = []
        for label in sorted(self.palettes):
            pal = self.palettes[label]
            fill = self._colour(pal, self._decl(self.HOVER, "background"),
                                label)
            edge = self._colour(pal, self._decl(self.HOVER, "border-color"),
                                label)
            got = contrast(edge, fill)
            if got < EDGE_MIN - 0.005:
                bad.append("%s: hovered edge (%s on %s) = %.2f:1"
                           % (label, edge, fill, got))
        self.assertEqual([], bad,
                         "the digest button loses its edge on hover:\n  "
                         + "\n  ".join(bad))
