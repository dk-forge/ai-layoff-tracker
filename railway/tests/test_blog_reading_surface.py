"""THE BLOG READS LIKE LONG-FORM, AND THE TWO DEFECTS THAT SAID OTHERWISE.

WHY THIS FILE EXISTS. asktherecruiter.com/blog is a WordPress block theme
(Twenty Twenty-Five) whose article styling is contested by two stylesheets that
are NOT on the filesystem of either repo: both are held in the WordPress
database and emitted inline, so no grep finds them and no deploy can edit them.
Measured off https://asktherecruiter.com/blog/how-long-should-a-resume-be/ on
2026-08-15 at ver=2.20.55, by walking document.styleSheets in a real browser:

  BEFORE, at 1280x900
    paragraph   x=317.5  w=645   16.8px / 29.9px line   ~77 chars per line
    h2          x=50.0   w=645   23.2px                 420px left of its text
    h1                          47.2px                  2.81x the body size

  BEFORE, at 375x900
    paragraph   x=78.0   w=219   16.8px / 29.9px        ~26 chars per line
    ancestors   main 18px + group 30px + entry-content 30px = 78px a side

TWO ROOT CAUSES, BOTH NAMED RATHER THAN PATCHED AROUND.

  1. THE HEADINGS ARE FLUSH LEFT WHILE THE TEXT IS CENTRED - the "two columns"
     a reader sees. <style id="wp-block-library-inline-css"> carries
        .entry-content h2 { margin: 2.2rem 0 .8rem !important }
     and that shorthand's `0` sets margin-left/right to zero. WP core centres a
     constrained child with
        .is-layout-constrained > :where(:not(.alignfull)) { margin-left:auto!important }
     at specificity (0,1,0); `.entry-content h2` is (0,1,1) and wins. h3 has the
     same shorthand. Anything that beats it needs !important AND more
     specificity, which is why every rule in the fix is scoped `body.single-post`.

  2. THE 78px MOBILE GUTTER - 47% of a 375px screen.
     <style id="global-styles-inline-css"> (Site Editor > Styles > Additional
     CSS, stored in the wp_global_styles post) carries, under
     @media (max-width:781px),
        .entry-content.alignfull, .wp-block-group.alignfull {
           margin-left:0!important; margin-right:0!important }
     which cancels core's `.has-global-padding > .alignfull { margin-inline:
     -root-padding }`. With the cancellation gone the three gutters STACK. This
     is the same mechanism as the tracker's own 2026-08-04 defect (TECHLOG,
     2.19.264), seen here on the blog.

WHAT THE FIXTURE IS. The ancestor chain, the WP core layout rules and BOTH
database stylesheets are reproduced VERBATIM below from the live measurement,
then assets/blog-reading.css is appended exactly as the browser would receive
it. A fixture that does not carry the opposition is not measuring this change:
the 2.20.53 signup defect shipped because a fixture was 36px wider than the
page. Everything asserted here fails on the fixture with the last <style>
removed, and the test proves that itself (test_fixture_reproduces_the_defect).

THE FONT IS NOT LOADED HERE, ON PURPOSE. The fixture is offline, so Vollkorn's
@font-face (which points into the active theme) does not resolve and the
stylesheet's declared fallback - Charter/Georgia/serif - renders instead. That
is the right thing to measure: the fallback is what a reader sees for the first
paint and forever if the theme ever stops carrying the file, so the measure has
to be comfortable in it. The characters-per-line bands below are therefore
stated for the FALLBACK metric, and the live post is measured separately at the
end of the session.

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

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = PLUGIN / "assets/blog-reading.css"
INCLUDE = PLUGIN / "includes/blog-typography.php"
MAIN = PLUGIN / "ai-layoff-tracker.php"

# Widths the brief names, plus 1280 for the desktop measure.
WIDTHS = (375, 414, 768, 1280)

TAP_MIN = 44.0

# The comfortable measure, in characters. 65-75 is the long-form convention on
# a desktop; a phone cannot reach it and 38-45 is the working equivalent.
DESKTOP_CPL = (60.0, 78.0)
PHONE_CPL = (36.0, 48.0)


# ----------------------------------------------------------------- fixture

# WP core's layout + global-padding rules, as emitted by 6.x into
# <style id="global-styles-inline-css">. Copied from the live page.
WP_CORE = """
:root { --wp--style--global--content-size: 645px; --pad: 50px; }
@media (max-width: 781px) { :root { --pad: 30px; } }
body { margin: 0; font-family: Manrope, sans-serif; background: #fff; }
.wp-site-blocks { }
.has-global-padding { padding-right: var(--pad); padding-left: var(--pad); }
.has-global-padding > .alignfull {
  margin-right: calc(var(--pad) * -1); margin-left: calc(var(--pad) * -1);
}
.is-layout-constrained > :where(:not(.alignleft):not(.alignright):not(.alignfull)) {
  max-width: var(--wp--style--global--content-size);
  margin-left: auto !important; margin-right: auto !important;
}
:root :where(.is-layout-constrained) > * { margin-block: 1.2rem 0; }
:root :where(.is-layout-constrained) > :first-child { margin-block-start: 0; }
h1, h2, h3, h4, h5, h6 { font-weight: 400; }
a:where(:not(.wp-element-button)) { color: currentColor; }
"""

# `main` carries 18px rather than the root padding BELOW 782px on this site.
# Measured live: main padding-left is 18px at 375, 414 and 768, and 50px at
# 1280. The breakpoint matters - a fixture that gives main 18px at 1280 while
# core still hands the .alignfull child a -50px margin manufactures 32px of
# horizontal overflow that the real page does not have.
SITE_MAIN_GUTTER = """
@media (max-width: 781px) {
  main.wp-block-group.has-global-padding { padding-left: 18px; padding-right: 18px; }
}
"""

# DATABASE STYLESHEET 1 - <style id="wp-block-library-inline-css">, the excerpt
# that touches article content. Verbatim from the live page.
DB_SHEET_BLOCK_LIBRARY = """
.entry-content p, .wp-block-post-content p {
  font-size: 1.05rem !important; line-height: 1.78 !important;
  color: #2a2a2a !important; margin-bottom: 1.2rem !important;
}
.entry-content h2, .wp-block-post-content h2 {
  font-size: 1.45rem !important; font-weight: 700 !important; color: #1a1a1a !important;
  margin: 2.2rem 0 .8rem !important; padding-bottom: .35rem !important;
  border-bottom: 2px solid #eef3ee !important;
}
.entry-content h3, .wp-block-post-content h3 {
  font-size: 1.15rem !important; font-weight: 600 !important; color: #222 !important;
  margin: 1.5rem 0 .5rem !important;
}
.wp-block-heading { font-size: 1.5rem; font-weight: 700; text-align: center; margin-bottom: 1rem; }
figcaption, .wp-element-caption { display: none !important; }
"""

# DATABASE STYLESHEET 2 - the @media(max-width:781px) block inside
# <style id="global-styles-inline-css"> that cancels the negative margins.
DB_SHEET_GLOBAL_STYLES = """
@media (max-width: 781px) {
  .wp-block-query.alignfull, .alignfull.wp-block-post-template,
  .wp-block-post-template > .wp-block-post, .entry-content.alignfull,
  .wp-block-group.alignfull {
    margin-left: 0px !important; margin-right: 0px !important; max-width: 100% !important;
  }
}
"""

# DATABASE STYLESHEET 3 - the WPCode snippet's article-relevant clause.
DB_SHEET_WPCODE = """
@media (max-width: 781px) {
  html, body { overflow-x: hidden; max-width: 100%; }
  img, svg, video, iframe { max-width: 100% !important; height: auto; }
  .entry-content, .wp-block-post-content, .wp-block-group, .wp-block-quote, blockquote {
    max-width: 100% !important; box-sizing: border-box !important;
  }
}
"""

# The site's own inline .atr-capture styling, verbatim.
DB_SHEET_CAPTURE = """
.atr-capture{border:1px solid #e3e3e3;border-radius:8px;padding:14px 16px;margin:18px 0;background:#fafafa}
.atr-capture-title{font-weight:600;margin:0 0 8px;font-size:.95rem}
.atr-capture-form{display:flex;gap:8px;flex-wrap:wrap}
.atr-capture-input{flex:1 1 200px;padding:8px 10px;border:1px solid #ccc;border-radius:6px;font-size:.9rem}
.atr-capture-btn{padding:8px 16px;border:0;border-radius:6px;background:#c8102e;color:#fff;font-weight:600;cursor:pointer}
.atr-capture-msg{display:block;font-size:.82rem;margin-top:6px;color:#444}
"""

_PARA = ("Most recruiters surveyed on the topic agree that length matters far less "
         "than relevance, and that the decision belongs to the content rather than "
         "to a rule somebody repeated at a careers fair. What follows is the test "
         "they actually apply when a document lands in the pile on a Tuesday.")

BODY = """
<div class="wp-site-blocks">
  <main id="wp--skip-link--target" class="wp-block-group has-global-padding is-layout-constrained">
    <div class="wp-block-group alignfull has-global-padding is-layout-constrained">
      <h1 class="wp-block-post-title">How Long Should a Resume Be? Recruiters Answer the Debate</h1>
      <div class="entry-content alignfull wp-block-post-content has-global-padding is-layout-constrained">
        <p>%(p)s</p>
        <div class="atr-capture">
          <p class="atr-capture-title">Get recruiter-backed job search tips</p>
          <form class="atr-capture-form">
            <input class="atr-capture-input" type="email" placeholder="you@example.com">
            <button class="atr-capture-btn" type="submit">Subscribe</button>
          </form>
          <span class="atr-capture-msg">No spam. Unsubscribe any time.</span>
        </div>
        <div id="ez-toc-container" class="ez-toc-v2_0_86 counter-hierarchy ez-toc-counter ez-toc-grey">
          <div class="ez-toc-title-container"><p class="ez-toc-title">Table of Contents</p></div>
          <nav class="ez-toc-nav"><ul class="ez-toc-list">
            <li><a href="#a">Mid-Career Professionals: One to Two Pages</a></li>
            <li><a href="#b">Senior and Executive Candidates</a></li>
            <li><a href="#c">What Recruiters Actually Object To</a></li>
          </ul></nav>
        </div>
        <h2 class="wp-block-heading" id="a">Mid-Career Professionals: One to Two Pages</h2>
        <p>%(p)s</p>
        <h3 class="wp-block-heading">A shorter step inside the section</h3>
        <p>%(p)s</p>
        <ul><li>%(p)s</li><li>A shorter item.</li></ul>
        <blockquote class="wp-block-quote"><p>Length is a byproduct of relevance done well.</p></blockquote>
        <h2 class="wp-block-heading" id="b">Senior and Executive Candidates</h2>
        <p>%(p)s</p>
      </div>
    </div>
  </main>
</div>
""" % {"p": _PARA}


def build_page(with_fix=True):
    sheets = [WP_CORE, SITE_MAIN_GUTTER, DB_SHEET_BLOCK_LIBRARY,
              DB_SHEET_GLOBAL_STYLES, DB_SHEET_WPCODE, DB_SHEET_CAPTURE]
    if with_fix:
        sheets.append(CSS.read_text(encoding="utf-8"))
    styles = "\n".join("<style>%s</style>" % s for s in sheets)
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            + styles + "</head>"
            "<body class='wp-singular post-template-default single single-post'>"
            + BODY + "</body></html>")


def data_url(html):
    import base64
    return "data:text/html;base64," + base64.b64encode(html.encode("utf-8")).decode()


# --------------------------------------------------------------- measuring

MEASURE_JS = r"""
(() => {
  const ec = document.querySelector('.entry-content');
  const kids = [...ec.children];
  const firstOf = (tag) => kids.find(e => e.tagName === tag);
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return {x:+r.x.toFixed(1), y:+r.y.toFixed(1), w:+r.width.toFixed(1), h:+r.height.toFixed(1),
            fs: parseFloat(cs.fontSize), lh: parseFloat(cs.lineHeight),
            ff: cs.fontFamily, fw: cs.fontWeight, ta: cs.textAlign,
            mts: cs.marginBlockStart, mbe: cs.marginBlockEnd,
            ml: cs.marginLeft, mr: cs.marginRight};
  };
  // Characters per line from the element's OWN resolved font, measured with a
  // canvas rather than assumed from an em ratio.
  const cpl = (el) => {
    const cs = getComputedStyle(el);
    const c = document.createElement('canvas').getContext('2d');
    c.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
    const alpha = 'abcdefghijklmnopqrstuvwxyz ';
    const avg = c.measureText(alpha).width / alpha.length;
    return +(el.getBoundingClientRect().width / avg).toFixed(1);
  };
  // Second paragraph: the first is the standfirst and is deliberately larger.
  const ps = kids.filter(e => e.tagName === 'P');
  const p = ps.length > 1 ? ps[1] : ps[0];
  const out = {
    vw: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    p: box(p), cpl: cpl(p),
    standfirst: box(ps[0]),
    h1: box(document.querySelector('.wp-block-post-title')),
    h2: box(firstOf('H2')),
    h3: box(firstOf('H3')),
    ul: box(firstOf('UL')),
    bq: box(firstOf('BLOCKQUOTE')),
    toc: box(document.querySelector('#ez-toc-container')),
    capture: box(document.querySelector('.atr-capture')),
    tocLinks: [...document.querySelectorAll('#ez-toc-container a')].map(a => {
      const r = a.getBoundingClientRect(); return {w:+r.width.toFixed(1), h:+r.height.toFixed(1)};
    }),
    controls: ['.atr-capture-input', '.atr-capture-btn'].map(sel => {
      const e = document.querySelector(sel); const r = e.getBoundingClientRect();
      return {sel, w:+r.width.toFixed(1), h:+r.height.toFixed(1)};
    }),
  };
  return out;
})()
"""


def measure(browser, html, widths=WIDTHS):
    url = data_url(html)
    out = {}
    for w in widths:
        browser.resize(w, 900)
        browser.navigate(url, settle=0.5)
        out[w] = browser.eval_js(MEASURE_JS)
    return out


_MEASURED = {}


def measured(with_fix=True):
    """Render once per variant per process. Raises CDPUnavailable upward."""
    key = bool(with_fix)
    if key not in _MEASURED:
        with Browser(width=WIDTHS[0], height=900) as b:
            _MEASURED[key] = measure(b, build_page(with_fix))
    return _MEASURED[key]


class ChromeBackedTest(unittest.TestCase):
    """Every geometry test skips LOUDLY when Chrome is absent, never passes."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "UNKNOWN, NOT A PASS: no Chrome/Chromium found, so the blog "
                "reading surface was not measured. Set CHROME_BIN or install "
                "Chrome. Absence of a signal is not a pass (CLAUDE.md).")
        try:
            cls.m = measured(True)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("UNKNOWN, NOT A PASS: %s" % exc)


# ------------------------------------------------------------------ tests

class HeadingsSitOverTheirOwnText(ChromeBackedTest):
    """Defect 1. The reader's "two columns"."""

    def test_every_heading_shares_the_paragraph_left_edge(self):
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            px = d["p"]["x"]
            for name in ("h2", "h3"):
                hx = d[name]["x"]
                if abs(hx - px) > 1.0:
                    bad.append("at %dpx the %s starts at x=%.1f and the "
                               "paragraph under it at x=%.1f (%.0fpx apart)"
                               % (w, name.upper(), hx, px, abs(hx - px)))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_headings_are_not_centred_text(self):
        bad = [("at %dpx the H2 renders text-align:%s" % (w, self.m[w]["h2"]["ta"]))
               for w in WIDTHS if self.m[w]["h2"]["ta"] not in ("start", "left")]
        self.assertEqual(bad, [], "\n".join(bad))


class TheMobileColumnIsReadable(ChromeBackedTest):
    """Defect 2. 78px of stacked gutter on a 375px screen."""

    def test_only_one_gutter_survives_on_a_phone(self):
        bad = []
        for w in (375, 414, 768):
            d = self.m[w]
            # main keeps its 18px on purpose; the two inner .alignfull
            # wrappers must contribute nothing.
            if d["p"]["x"] > 24.0 and w < 768:
                bad.append("at %dpx the paragraph starts %.0fpx in; only "
                           "main's 18px gutter should survive"
                           % (w, d["p"]["x"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_phone_column_is_wide_enough_to_read(self):
        bad = []
        for w in (375, 414):
            got = self.m[w]["p"]["w"]
            want = w - 40
            if got < want:
                bad.append("at %dpx the paragraph is %.0fpx wide, under the "
                           "%.0fpx a single 18px gutter each side leaves"
                           % (w, got, want))
        self.assertEqual(bad, [], "\n".join(bad))


class TheMeasureIsComfortable(ChromeBackedTest):

    def test_characters_per_line_land_in_the_reading_band(self):
        bands = {375: PHONE_CPL, 414: PHONE_CPL,
                 768: DESKTOP_CPL, 1280: DESKTOP_CPL}
        bad = []
        for w, (lo, hi) in bands.items():
            got = self.m[w]["cpl"]
            if not (lo <= got <= hi):
                bad.append("at %dpx the measure is %.1f characters per line, "
                           "outside %.0f-%.0f" % (w, got, lo, hi))
        self.assertEqual(bad, [], "\n".join(bad))


class TheTypeIsSizedForReading(ChromeBackedTest):

    def test_body_size_and_leading(self):
        bad = []
        for w in WIDTHS:
            p = self.m[w]["p"]
            if not (19.0 <= p["fs"] <= 21.0):
                bad.append("at %dpx the body is %.1fpx, outside 19-21"
                           % (w, p["fs"]))
            ratio = p["lh"] / p["fs"]
            if not (1.5 <= ratio <= 1.75):
                bad.append("at %dpx the leading is %.2f x the body size "
                           "(%.1fpx / %.1fpx), outside 1.50-1.75"
                           % (w, ratio, p["lh"], p["fs"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_body_is_the_serif_and_the_headings_are_the_sans(self):
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            if "Vollkorn" not in d["p"]["ff"]:
                bad.append("at %dpx the body font stack is %r, which does not "
                           "lead with the reading face" % (w, d["p"]["ff"]))
            for name in ("h1", "h2", "h3"):
                if "Manrope" not in d[name]["ff"]:
                    bad.append("at %dpx the %s font stack is %r, which does "
                               "not lead with Manrope"
                               % (w, name.upper(), d[name]["ff"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_heading_scale_steps_rather_than_leaps(self):
        """h1 -> h2 -> h3 -> body, each step a ratio a reader can follow.

        The site shipped 47.2 / 23.2 / 18.4 over a 16.8px body: h1 was 2.03x
        the H2 under it and 2.81x the text. That single leap is most of the
        reason the page did not read as an article.
        """
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            steps = [("h1/h2", d["h1"]["fs"] / d["h2"]["fs"]),
                     ("h2/h3", d["h2"]["fs"] / d["h3"]["fs"]),
                     ("h3/body", d["h3"]["fs"] / d["p"]["fs"])]
            for label, r in steps:
                if not (1.05 <= r <= 1.45):
                    bad.append("at %dpx the %s step is %.2fx, outside "
                               "1.05-1.45" % (w, label, r))
            top = d["h1"]["fs"] / d["p"]["fs"]
            if top > 2.25:
                bad.append("at %dpx the h1 is %.2fx the body size, over 2.25"
                           % (w, top))
        self.assertEqual(bad, [], "\n".join(bad))


class ThereIsVerticalRhythm(ChromeBackedTest):

    def test_a_heading_is_closer_to_its_own_text_than_to_the_section_above(self):
        """The single most-read signal of structure: space belongs ABOVE a
        heading, not below it. If the gap under an h2 is larger than the gap
        over it, the heading visually joins the wrong section."""
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            for name in ("h2", "h3"):
                above = float(d[name]["mts"].rstrip("px"))
                below = float(d[name]["mbe"].rstrip("px"))
                if above <= below * 1.5:
                    bad.append("at %dpx the %s has %.0fpx above and %.0fpx "
                               "below; a heading must sit nearer its own text"
                               % (w, name.upper(), above, below))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_paragraph_separation_is_visible_but_not_a_gulf(self):
        bad = []
        for w in WIDTHS:
            p = self.m[w]["p"]
            gap = float(p["mbe"].rstrip("px"))
            if not (0.7 <= gap / p["lh"] <= 1.3):
                bad.append("at %dpx the paragraph gap is %.0fpx against a "
                           "%.0fpx line; that is %.2f lines"
                           % (w, gap, p["lh"], gap / p["lh"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_lists_and_quotes_are_on_the_same_column_as_the_text(self):
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            for name in ("ul", "bq", "toc", "capture"):
                if d[name] is None:
                    bad.append("at %dpx there is no %s to measure" % (w, name))
                    continue
                right_edge = d[name]["x"] + d[name]["w"]
                p_right = d["p"]["x"] + d["p"]["w"]
                # A list indents its markers, a quote its rule; both must stay
                # inside the reading column, never wider than it.
                if right_edge > p_right + 1.0 or d[name]["x"] < d["p"]["x"] - 1.0:
                    bad.append("at %dpx the %s spans %.0f-%.0f, outside the "
                               "reading column %.0f-%.0f"
                               % (w, name, d[name]["x"], right_edge,
                                  d["p"]["x"], p_right))
        self.assertEqual(bad, [], "\n".join(bad))


class NothingOverflowsAndEverythingIsTappable(ChromeBackedTest):

    def test_no_horizontal_document_overflow(self):
        bad = [("at %dpx the document scrolls sideways: scrollWidth %d vs "
                "clientWidth %d" % (w, self.m[w]["scrollWidth"],
                                    self.m[w]["clientWidth"]))
               for w in WIDTHS
               if self.m[w]["scrollWidth"] > self.m[w]["clientWidth"]]
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_contents_list_and_the_signup_clear_44px(self):
        bad = []
        for w in (375, 414):
            d = self.m[w]
            for i, a in enumerate(d["tocLinks"]):
                if a["h"] < TAP_MIN:
                    bad.append("at %dpx table-of-contents link %d is %.1fpx "
                               "tall, under %.0f" % (w, i, a["h"], TAP_MIN))
            for c in d["controls"]:
                if c["h"] < TAP_MIN:
                    bad.append("at %dpx %s is %.1fpx tall, under %.0f"
                               % (w, c["sel"], c["h"], TAP_MIN))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_signup_row_does_not_wrap_off_its_own_box(self):
        """The 2.20.53 lesson, on the other signup. At 339px the field, the
        gap and the button do not fit on one line, so they must each take a
        full row rather than half-wrapping."""
        d = self.m[375]
        cap = d["capture"]
        for c in d["controls"]:
            if c["w"] > cap["w"]:
                self.fail("at 375px %s is %.0fpx wide inside a %.0fpx box"
                          % (c["sel"], c["w"], cap["w"]))


class TheFixtureReproducesTheDefect(ChromeBackedTest):
    """RED-BEFORE-GREEN, asserted rather than remembered.

    Strip the last <style> (assets/blog-reading.css) from the same fixture and
    the two defects must come back. If they do not, this file is measuring
    something other than the page.
    """

    def test_without_the_stylesheet_the_headings_and_the_gutter_break(self):
        try:
            before = measured(False)
        except CDPUnavailable as exc:
            self.skipTest("UNKNOWN, NOT A PASS: %s" % exc)

        d1280 = before[1280]
        self.assertGreater(
            abs(d1280["h2"]["x"] - d1280["p"]["x"]), 100.0,
            "the fixture does not reproduce the flush-left heading defect: "
            "H2 x=%.1f, paragraph x=%.1f" % (d1280["h2"]["x"], d1280["p"]["x"]))

        d375 = before[375]
        self.assertGreater(
            d375["p"]["x"], 60.0,
            "the fixture does not reproduce the stacked 78px gutter: the "
            "paragraph starts at x=%.1f" % d375["p"]["x"])
        self.assertLess(
            d375["cpl"], 32.0,
            "the fixture does not reproduce the unreadable phone measure: "
            "%.1f characters per line" % d375["cpl"])


# ------------------------------------------------------- source-level guards

class TheStylesheetCannotReintroduceTheBug(unittest.TestCase):
    """No Chrome needed. These are properties of the source text."""

    def test_no_margin_shorthand_anywhere_in_the_stylesheet(self):
        """`margin: 2.2rem 0 .8rem` IS defect 1. A shorthand on a constrained
        child silently zeroes the auto centring that puts the block over its
        own text, and it does it without touching a selector anyone would
        grep. This file uses margin-block-start/end, or margin-left/right:auto,
        and never the shorthand."""
        src = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
        offenders = []
        for i, line in enumerate(src.splitlines(), 1):
            if re.search(r"(^|[;{\s])margin\s*:", line):
                offenders.append("%s:%d %s" % (CSS.name, i, line.strip()))
        self.assertEqual(offenders, [], (
            "the `margin` shorthand zeroes margin-left/right, which is exactly "
            "the defect this stylesheet exists to fix. Use margin-block-start "
            "/ margin-block-end.\n" + "\n".join(offenders)))

    def test_every_rule_is_scoped_to_a_single_post(self):
        """This sheet loads on posts, but a stylesheet is global once loaded
        and this plugin's real job is four other surfaces. Every selector
        carries `body.single-post` so a mis-scoped enqueue cannot restyle the
        tracker."""
        src = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
        # Flatten @media blocks: keep only selector lists (text before `{`).
        offenders = []
        for block in re.finditer(r"([^{}]+)\{[^{}]*\}", src):
            sel = block.group(1).strip()
            if not sel or sel.startswith("@"):
                continue
            for one in sel.split(","):
                one = one.strip()
                if not one or one.startswith("@"):
                    continue
                if "body.single-post" not in one:
                    offenders.append(one)
        self.assertEqual(offenders, [], (
            "every selector must be scoped `body.single-post`:\n"
            + "\n".join(offenders)))

    def test_no_external_host_is_contacted(self):
        css = CSS.read_text(encoding="utf-8")
        urls = re.findall(r"url\(\s*['\"]?([^'\")]+)", css)
        remote = [u for u in urls if u.startswith(("http://", "https://", "//"))]
        self.assertEqual(remote, [], (
            "the reading surface must not import from a CDN or any other "
            "host: %r" % remote))
        self.assertNotIn("@import", css)


class TheEnqueueIsGatedAndGuarded(unittest.TestCase):

    def test_it_loads_on_single_posts_only(self):
        src = INCLUDE.read_text(encoding="utf-8")
        self.assertIn("is_singular('post')", src)
        self.assertIn("wp_enqueue_style('alt-blog-reading'", src)

    def test_the_font_is_only_declared_when_the_theme_carries_it(self):
        """A declared @font-face whose file 404s costs a request and still
        falls back. The check is what makes the fallback stack honest."""
        src = INCLUDE.read_text(encoding="utf-8")
        self.assertIn("file_exists", src)
        self.assertIn("get_theme_file_uri", src)

    def test_the_new_include_cannot_fatal_a_mid_upload_deploy(self):
        """FTPS uploads one file at a time, so the main plugin file can land
        before a NEW include does. A hard require of a missing include fatals
        every request until it arrives (2.19.20)."""
        main = MAIN.read_text(encoding="utf-8")
        m = re.search(r"is_readable\(\$alt_blog_typography\)", main)
        self.assertIsNotNone(m, (
            "includes/blog-typography.php is new, so ai-layoff-tracker.php "
            "must include it behind is_readable(), not a bare require_once"))
        self.assertNotIn("require_once ALT_PLUGIN_DIR . 'includes/blog-typography.php'",
                         main)

    def test_no_function_name_collides_with_another_include(self):
        """The 2.20.54 outage: two includes declaring one function is a PHP
        fatal on every request. This is the same assertion, kept local so a new
        include cannot ship without it."""
        seen = {}
        inc_dir = PLUGIN / "includes"
        for path in sorted(inc_dir.glob("*.php")):
            src = path.read_text(encoding="utf-8")
            for m in re.finditer(r"^\s*function\s+([a-z0-9_]+)\s*\(", src, re.M):
                seen.setdefault(m.group(1), []).append(path.name)
        dupes = {k: v for k, v in seen.items() if len(v) > 1}
        self.assertEqual(dupes, {}, (
            "these function names are declared in more than one plugin "
            "include, which PHP treats as a fatal: %r" % dupes))


if __name__ == "__main__":
    unittest.main(verbosity=2)
