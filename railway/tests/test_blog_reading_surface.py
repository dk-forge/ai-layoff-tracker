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

# Widths the brief names, plus 1280 for the desktop measure and 1600/2000 for
# the large screens where the owner saw "one column": the page shipped with a
# single 645px width at every one of these, and nothing below 1400px can
# demonstrate that, because nothing below 1400px has the room to.
WIDTHS = (375, 414, 768, 1280, 1600, 2000)

TAP_MIN = 44.0

# The comfortable measure, in characters. 65-75 is the long-form convention on
# a desktop; a phone cannot reach it and 38-45 is the working equivalent.
DESKTOP_CPL = (60.0, 78.0)
PHONE_CPL = (36.0, 48.0)

# AND CHARACTERS PER LINE IS A FONT MEASUREMENT, WHICH MADE THIS SUITE PASS ON
# A MAC AND RED ON CI FOR FOUR COMMITS RUNNING.
#
# cpl is column width over average glyph width, and the glyph width depends on
# which face actually resolves. Three have now been measured on this exact
# stylesheet, and they differ by 9%:
#
#   0.4946 em   Vollkorn, live (700px at 21px measured 67.4 cpl)
#   0.4824 em   Charter, this fixture on macOS (700px at 21px measured 69.1)
#   0.4515 em   the Linux CI runner's serif fallback, derived from two
#               independent failures on 2026-08-16: 780px at 22px reported
#               78.5 cpl, and 820px at 23px reported 79.0
#
# A session on a Mac sizing against 0.4824 ships a line that is 6% longer for
# every reader whose device carries neither Vollkorn nor Charter. The band is
# not the problem and was not moved; the type grew. But the local measurement
# can no longer be the only one, so the projection below re-measures every
# width against the narrowest face observed, whatever the local machine has.
# Raise it only when a NARROWER face has actually been measured somewhere.
NARROWEST_GLYPH_EM = 0.4515

# PASS THREE, 2026-08-15. The owner read the 2.20.61 page and named four things.
# Each number below is one of them, stated as a threshold so the stylesheet
# cannot drift back under it.
#
#   1. The text was starved beside its own illustration: 700px of text against
#      a 1040px image at 2000px, a ratio of 1.49. Characters per line is still
#      the constraint, so the measure only widens with the type, and the media
#      comes back toward it rather than the text stretching to meet it.
MEASURE_FLOOR_AT_2000 = 800.0   # px of text on the largest screen measured
MEASURE_CEILING = 860.0         # px, past which no type size rescues the line
MEDIA_TO_TEXT_MAX = 1.35        # the image may lead the text, not leave it
#
#   2/3. Headings read as body text in bold. h2 was 30px over a 20px body
#      (1.50x) with 48px above it, on a page whose sections have to announce
#      themselves from a scroll.
# Two bars, not one, and the split is a design position rather than a dodge.
# On a 375px screen a section heading is the full width of the reader's view
# with nothing beside it; inside an 820px column on a 2000px screen it is a
# short line in a lot of white and needs the size to register. Raising the
# phone h2 to 1.60x would also drag the h1 up with it (the step ratios below
# forbid them converging), and the reference post's 57-character headline
# wraps to a fourth line above 32px. Mobile wins that trade.
H2_TO_BODY_MIN = 1.60           # at GROUND_FROM and above
H2_TO_BODY_MIN_PHONE = 1.45     # below it
H2_AIR_IN_LINES = 2.0           # space above an h2, in body line-heights
#
#   4. At 2000px the article was a thin strip in white. The frame is capped and
#      the reading column is given a ground to sit on.
FRAME_CEILING = 1320.0
GROUND_FROM = 1024              # below this the page stays edge-to-edge white
#
#   2 (again). The contents box read as a plugin widget: two columns of 16px
#      grey sans under a rule. One column, on the article's own face, at a size
#      that belongs to the body it indexes.
TOC_BODY_GAP_MAX = 4.0          # px the contents may sit under the body size
TOC_FLOOR = 16.0                # px, and never smaller than this


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

# The article's vertical frame, measured live at 2000px and at 375px on
# 2026-08-15: `main` carries a 70px top margin and the article group a 70px top
# padding on a desktop (30px below 782px), which is the 140px hole between the
# site header and the headline. The site header itself is 89.2px tall at 2000px
# and 64px on a phone; the fixture reproduces it as a fixed block so the gap is
# a measurable number rather than a judgement.
SITE_FRAME = """
header.wp-block-template-part { height: 89.2px; background: #fff; border-bottom: 1px solid #eee; }
.wp-site-blocks > main { margin-top: 70px; }
main > .wp-block-group.alignfull.has-global-padding { padding-top: 70px; padding-bottom: 70px; }
.wp-block-post-title { margin-bottom: 22.4px; }
.wp-block-post-featured-image { margin-bottom: 32px; }
.wp-block-post-featured-image img { width: 100%; height: auto; display: block; }
img { max-width: 100%; height: auto; }
@media (max-width: 781px) {
  header.wp-block-template-part { height: 64px; }
  .wp-site-blocks > main { margin-top: 0; }
  main > .wp-block-group.alignfull.has-global-padding { padding-top: 30px; padding-bottom: 30px; }
}
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

# The featured image, at the live post's real intrinsic size (1288x943), drawn
# as an inline SVG so the fixture stays offline and contacts no host. Its
# intrinsic width is what makes "the media is wider than the text" a real
# measurement rather than an upscale: 1040px is inside 1288px.
_HERO_SRC = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
             "width='1288' height='943'><rect width='1288' height='943' "
             "fill='rgb(206,212,218)'/></svg>")

# The third-party Mailjet block. The owner is removing it in wp-admin, so the
# layout is measured BOTH with it and without it and nothing may depend on it.
CAPTURE_HTML = """
        <div class="atr-capture">
          <p class="atr-capture-title">Get recruiter-backed job search tips</p>
          <form class="atr-capture-form">
            <input class="atr-capture-input" type="email" placeholder="you@example.com">
            <button class="atr-capture-btn" type="submit">Subscribe</button>
          </form>
          <span class="atr-capture-msg">No spam. Unsubscribe any time.</span>
        </div>
"""

# The table of contents as easy-table-of-contents actually emits it on the live
# post: eleven links, a CLASSLESS <nav> (the plugin's own markup - a fixture
# that gives it `nav.ez-toc-nav` would let a selector pass here and miss live),
# and no nesting.
_TOC_ITEMS = [
    "Mid-Career Professionals: One to Two Pages",
    "Senior and Executive Candidates",
    "What Recruiters Actually Object To",
    "Early Career and Graduates",
    "Academic and Federal Applications",
    "Formatting That Buys You Space",
    "What to Cut First",
    "Keywords and the Screening Layer",
    "Two Pages Is Not a Licence",
    "How Recruiters Actually Skim",
    "The Short Answer",
]

TOC_HTML = ("""
        <div id="ez-toc-container" class="ez-toc-v2_0_86 counter-hierarchy ez-toc-counter ez-toc-grey">
          <div class="ez-toc-title-container"><p class="ez-toc-title">Table of Contents</p></div>
          <nav><ul class="ez-toc-list">
"""
            + "\n".join("            <li class='ez-toc-page-1'>"
                        "<a class='ez-toc-link' href='#s%d'>%s</a></li>"
                        % (i, t) for i, t in enumerate(_TOC_ITEMS))
            + """
          </ul></nav>
        </div>
""")


def build_body(with_capture=True):
    return """
<div class="wp-site-blocks">
  <header class="wp-block-template-part"></header>
  <main id="wp--skip-link--target" class="wp-block-group has-global-padding is-layout-constrained">
    <div class="wp-block-group alignfull has-global-padding is-layout-constrained">
      <h1 class="wp-block-post-title">How Long Should a Resume Be? Recruiters Answer the Debate</h1>
      <figure class="wp-block-post-featured-image">
        <img class="wp-post-image" src="%(hero)s" width="1288" height="943" alt="">
      </figure>
      <div class="entry-content alignfull wp-block-post-content has-global-padding is-layout-constrained">
        <p>%(p)s</p>
%(capture)s%(toc)s
        <h2 class="wp-block-heading" id="s0">Mid-Career Professionals: One to Two Pages</h2>
        <p>%(p)s</p>
        <h3 class="wp-block-heading">A shorter step inside the section</h3>
        <p>%(p)s</p>
        <ul><li>%(p)s</li><li>A shorter item.</li></ul>
        <blockquote class="wp-block-quote"><p>Length is a byproduct of relevance done well.</p></blockquote>
        <figure class="wp-block-image"><img src="%(hero)s" width="1288" height="943" alt=""></figure>
        <h2 class="wp-block-heading" id="s1">Senior and Executive Candidates</h2>
        <p>%(p)s</p>
      </div>
    </div>
  </main>
</div>
""" % {"p": _PARA, "hero": _HERO_SRC, "toc": TOC_HTML,
       "capture": CAPTURE_HTML if with_capture else ""}


def build_page(with_fix=True, with_capture=True):
    sheets = [WP_CORE, SITE_FRAME, SITE_MAIN_GUTTER, DB_SHEET_BLOCK_LIBRARY,
              DB_SHEET_GLOBAL_STYLES, DB_SHEET_WPCODE, DB_SHEET_CAPTURE]
    if with_fix:
        sheets.append(CSS.read_text(encoding="utf-8"))
    styles = "\n".join("<style>%s</style>" % s for s in sheets)
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            + styles + "</head>"
            "<body class='wp-singular post-template-default single single-post'>"
            + build_body(with_capture) + "</body></html>")


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
    hero: box(document.querySelector('.wp-block-post-featured-image')),
    heroImg: box(document.querySelector('.wp-block-post-featured-image img')),
    figure: box(document.querySelector('.entry-content > figure.wp-block-image')),
    // The gap the reader sees before the article starts.
    headerGap: (() => {
      const h = document.querySelector('header.wp-block-template-part');
      const t = document.querySelector('.wp-block-post-title');
      if (!h || !t) return null;
      return +(t.getBoundingClientRect().top - h.getBoundingClientRect().bottom).toFixed(1);
    })(),
    // The contents box, as edges rather than as taste: a 1px left/right border
    // is a vertical line down a 6000px page, which is what "one column" is
    // made of.
    tocEdges: (() => {
      const c = document.querySelector('#ez-toc-container');
      if (!c) return null;
      const cs = getComputedStyle(c);
      return {l: parseFloat(cs.borderLeftWidth), r: parseFloat(cs.borderRightWidth),
              t: parseFloat(cs.borderTopWidth), b: parseFloat(cs.borderBottomWidth),
              pl: parseFloat(cs.paddingLeft), bg: cs.backgroundColor};
    })(),
    tocColumns: (() => {
      const ul = document.querySelector('#ez-toc-container nav > ul');
      return ul ? getComputedStyle(ul).columnCount : null;
    })(),
    // The contents as TYPE rather than as a box: a nav set four sizes under
    // the prose it indexes is a widget however it is framed.
    tocType: (() => {
      const a = document.querySelector('#ez-toc-container a.ez-toc-link');
      if (!a) return null;
      const cs = getComputedStyle(a);
      return {fs: parseFloat(cs.fontSize), ff: cs.fontFamily, color: cs.color};
    })(),
    // The page frame, and whether the reading column sits on anything. `main`
    // is the full-width band; the group inside it is the article itself.
    frame: (() => {
      const g = document.querySelector('.wp-site-blocks > main > .wp-block-group');
      if (!g) return null;
      const r = g.getBoundingClientRect(), cs = getComputedStyle(g);
      return {x: +r.x.toFixed(1), w: +r.width.toFixed(1),
              bg: cs.backgroundColor};
    })(),
    ground: (() => {
      const m = document.querySelector('.wp-site-blocks > main');
      return m ? getComputedStyle(m).backgroundColor : null;
    })(),
    // The LIST's own left edge, not the link's. With padding-inline-start at
    // 0 a marker renders outside the padding box, so a contents whose links
    // are correctly on the column can still hang bullets 20px left of every
    // paragraph on the page.
    tocListEdge: (() => {
      const li = document.querySelector('#ez-toc-container nav > ul > li');
      if (!li) return null;
      return {x: +li.getBoundingClientRect().x.toFixed(1),
              marker: getComputedStyle(li).listStyleType};
    })(),
    tocLinkX: (() => {
      const a = document.querySelector('#ez-toc-container a.ez-toc-link');
      return a ? +a.getBoundingClientRect().x.toFixed(1) : null;
    })(),
    tocLinks: [...document.querySelectorAll('#ez-toc-container a')].map(a => {
      const r = a.getBoundingClientRect(); return {w:+r.width.toFixed(1), h:+r.height.toFixed(1)};
    }),
    // Null when the third-party box is absent, which is a page this layout
    // must also be correct on: the owner is deleting it in wp-admin.
    controls: ['.atr-capture-input', '.atr-capture-btn'].map(sel => {
      const e = document.querySelector(sel);
      if (!e) return null;
      const r = e.getBoundingClientRect();
      return {sel, w:+r.width.toFixed(1), h:+r.height.toFixed(1)};
    }).filter(Boolean),
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


def measured(with_fix=True, with_capture=True):
    """Render once per variant per process. Raises CDPUnavailable upward."""
    key = (bool(with_fix), bool(with_capture))
    if key not in _MEASURED:
        with Browser(width=WIDTHS[0], height=900) as b:
            _MEASURED[key] = measure(b, build_page(with_fix, with_capture))
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
                 768: DESKTOP_CPL, 1280: DESKTOP_CPL,
                 1600: DESKTOP_CPL, 2000: DESKTOP_CPL}
        bad = []
        for w, (lo, hi) in bands.items():
            got = self.m[w]["cpl"]
            if not (lo <= got <= hi):
                bad.append("at %dpx the measure is %.1f characters per line, "
                           "outside %.0f-%.0f" % (w, got, lo, hi))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_line_is_still_short_enough_in_the_narrowest_fallback(self):
        """The same band, re-measured against a face this machine may not
        have. The test above asks "how long is the line HERE"; this one asks
        "how long is it for a reader whose device carries neither Vollkorn nor
        Charter", which is the question that went unasked until the CI runner
        answered it four commits in a row.

        Only the ceiling is checked. A narrower face can only lengthen a line,
        so the floor is already covered by the local measurement.
        """
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            hi = (PHONE_CPL if w < 768 else DESKTOP_CPL)[1]
            projected = d["p"]["w"] / (d["p"]["fs"] * NARROWEST_GLYPH_EM)
            if projected > hi:
                bad.append("at %dpx the measure is %.0fpx at %.0fpx type, "
                           "which is %.1f characters per line in the narrowest "
                           "serif measured (%.4f em), over %.0f. It reads %.1f "
                           "on this machine, so sizing by what is rendered "
                           "here ships a longer line to everyone else."
                           % (w, d["p"]["w"], d["p"]["fs"], projected,
                              NARROWEST_GLYPH_EM, hi, d["cpl"]))
        self.assertEqual(bad, [], "\n".join(bad))


class TheTypeIsSizedForReading(ChromeBackedTest):

    def test_body_size_and_leading(self):
        bad = []
        for w in WIDTHS:
            p = self.m[w]["p"]
            # 19-24. The ceiling moved twice with pass three, and both times
            # it was the type FOLLOWING the column rather than leading it: the
            # measure is only allowed to widen because the type widens with
            # it, so a band pinned at 21px would have forbidden the fix rather
            # than guarded it. The second move, 23 to 24, was forced by the
            # narrow-fallback measurement above - the column did not grow, the
            # line it produced for a third of readers turned out to be longer
            # than anyone here could see. The thing actually being guarded is
            # characters per line, and that is now asserted twice at every
            # width: as rendered, and as projected onto the narrowest face.
            if not (19.0 <= p["fs"] <= 24.0):
                bad.append("at %dpx the body is %.1fpx, outside 19-24"
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


class ThePageHasMoreThanOneWidth(ChromeBackedTest):
    """Defect 3, the owner's own words: "zoomed out you see it's constructed
    to one column".

    Measured at 2000px on 2026-08-15: paragraph x=677.5 w=645, h1 w=645,
    featured image w=645, contents box w=645, signup w=645. Nothing was
    misaligned and nothing was too narrow. There was one width on the page,
    over 6317px of article, so there was no rhythm and no scale.
    """

    LARGE = (1280, 1600, 2000)

    def test_media_runs_wider_than_the_text_on_a_large_screen(self):
        """The one contrast that does most of the work. A hero the same width
        as the paragraph under it reads as another paragraph."""
        bad = []
        for w in self.LARGE:
            d = self.m[w]
            hero, p = d["hero"], d["p"]
            if hero is None:
                bad.append("at %dpx there is no featured image to measure" % w)
                continue
            if hero["w"] - p["w"] < 100.0:
                bad.append("at %dpx the featured image is %.0fpx wide and the "
                           "text is %.0fpx: %.0fpx of contrast, under the "
                           "100px a reader can see"
                           % (w, hero["w"], p["w"], hero["w"] - p["w"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_an_in_article_figure_is_wider_than_the_text_too(self):
        bad = []
        for w in self.LARGE:
            d = self.m[w]
            fig, p = d["figure"], d["p"]
            if fig is None:
                bad.append("at %dpx there is no in-article figure" % w)
                continue
            if fig["w"] - p["w"] < 100.0:
                bad.append("at %dpx the article figure is %.0fpx against "
                           "%.0fpx of text (%.0fpx of contrast)"
                           % (w, fig["w"], p["w"], fig["w"] - p["w"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_media_stays_centred_on_the_same_axis_as_the_text(self):
        """Wider is only right if it is wider around the SAME centre. A hero
        that widens to one side is the two-column defect again."""
        bad = []
        for w in self.LARGE:
            d = self.m[w]
            if d["hero"] is None:
                continue
            hc = d["hero"]["x"] + d["hero"]["w"] / 2
            pc = d["p"]["x"] + d["p"]["w"] / 2
            if abs(hc - pc) > 1.0:
                bad.append("at %dpx the featured image is centred on x=%.1f "
                           "and the text on x=%.1f" % (w, hc, pc))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_phone_has_exactly_one_width(self):
        """A hero wider or narrower than the text at 375px would only be a
        mistake: below 782px the token is 100%, and at phone widths 100% of
        the article IS the measure. (At 768px the article is 732px wide while
        the measure is still 645px, so the hero runs to the gutters there and
        the next test covers that case.)"""
        bad = []
        for w in (375, 414):
            d = self.m[w]
            if d["hero"] is None:
                bad.append("at %dpx there is no featured image" % w)
                continue
            if abs(d["hero"]["w"] - d["p"]["w"]) > 1.0:
                bad.append("at %dpx the featured image is %.0fpx and the text "
                           "%.0fpx; on a phone they must be one width"
                           % (w, d["hero"]["w"], d["p"]["w"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_media_never_runs_narrower_than_the_text_or_past_the_gutters(self):
        """The two ways a media token goes wrong at a width nobody looked at:
        an image narrower than the paragraph beside it, or one that pushes
        past the article's own gutters and takes the document sideways."""
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            if d["hero"] is None:
                continue
            if d["hero"]["w"] < d["p"]["w"] - 1.0:
                bad.append("at %dpx the featured image (%.0fpx) is narrower "
                           "than the text (%.0fpx)"
                           % (w, d["hero"]["w"], d["p"]["w"]))
            if d["hero"]["x"] < 0 or \
                    d["hero"]["x"] + d["hero"]["w"] > d["clientWidth"] + 1.0:
                bad.append("at %dpx the featured image spans %.0f-%.0f, "
                           "outside the %dpx viewport"
                           % (w, d["hero"]["x"], d["hero"]["x"] + d["hero"]["w"],
                              d["clientWidth"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_measure_grows_with_the_type_and_stays_in_the_reading_band(self):
        """PASS THREE. 700px of text beside a 1040px image looked starved, and
        it was: the column had stopped growing two steps before the media did.

        The measure now climbs to 820px at 2000px, and it is allowed to only
        because the type climbs with it. Characters per line is the constraint,
        never pixels - the band itself is asserted by TheMeasureIsComfortable
        at every width, and this asserts the pixel move that band permits.
        """
        narrow, wide = self.m[1280], self.m[2000]
        self.assertGreater(
            wide["p"]["w"], narrow["p"]["w"] + 20.0,
            "the measure does not grow on a large screen: %.0fpx at 1280 and "
            "%.0fpx at 2000" % (narrow["p"]["w"], wide["p"]["w"]))
        self.assertGreaterEqual(
            wide["p"]["w"], MEASURE_FLOOR_AT_2000,
            "at 2000px the text is %.0fpx wide against a %.0fpx image; that is "
            "the starved column the owner saw, and %.0fpx is the floor"
            % (wide["p"]["w"], wide["hero"]["w"] if wide["hero"] else -1,
               MEASURE_FLOOR_AT_2000))
        self.assertLess(
            wide["p"]["w"], MEASURE_CEILING,
            "the measure grew to %.0fpx, which is a long line whatever the "
            "type size" % wide["p"]["w"])
        self.assertGreater(
            wide["p"]["fs"], narrow["p"]["fs"],
            "the column grew but the type did not, so the line got longer to "
            "read: %.1fpx at 1280 and %.1fpx at 2000"
            % (narrow["p"]["fs"], wide["p"]["fs"]))

    def test_the_media_leads_the_text_without_leaving_it(self):
        """The other half of the same complaint. A hero the width of the
        paragraph reads as another paragraph (asserted above); a hero half
        again as wide reads as a different page. 1.49x was the second one."""
        bad = []
        for w in self.LARGE:
            d = self.m[w]
            if d["hero"] is None:
                continue
            ratio = d["hero"]["w"] / d["p"]["w"]
            if ratio > MEDIA_TO_TEXT_MAX:
                bad.append("at %dpx the featured image is %.2fx the text "
                           "(%.0fpx against %.0fpx), over %.2f: the image is "
                           "running away from the column it illustrates"
                           % (w, ratio, d["hero"]["w"], d["p"]["w"],
                              MEDIA_TO_TEXT_MAX))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_hero_image_is_never_upscaled(self):
        """The source is 1288px wide. A media step past that is a blurry hero,
        which is a worse page than a narrow one."""
        bad = [("at %dpx the featured image renders %.0fpx wide, past the "
                "1288px source" % (w, self.m[w]["heroImg"]["w"]))
               for w in WIDTHS
               if self.m[w]["heroImg"] and self.m[w]["heroImg"]["w"] > 1288.0]
        self.assertEqual(bad, [], "\n".join(bad))


class TheArticleDoesNotOpenWithAHole(ChromeBackedTest):
    """Measured live at 2000px: the site header ended at y=89 and the headline
    began at y=229. 140px of nothing above the one line that has to be read.
    """

    def test_the_headline_sits_close_under_the_site_header(self):
        bad = []
        for w in WIDTHS:
            gap = self.m[w]["headerGap"]
            if gap is None:
                bad.append("at %dpx the header/headline gap is not measurable" % w)
                continue
            if gap > 80.0:
                bad.append("at %dpx there are %.0fpx between the site header "
                           "and the headline, over 80" % (w, gap))
            if gap < 16.0:
                bad.append("at %dpx the headline sits %.0fpx under the site "
                           "header, which is not a break at all" % (w, gap))
        self.assertEqual(bad, [], "\n".join(bad))


class TheContentsIsNoLongerABox(ChromeBackedTest):
    """Its 1px left and right borders were two of the vertical lines the
    "one column" read was made of, on the tallest element of the opening
    screen. It stays inline and on the reading column; it stops being a box.
    """

    def test_the_contents_draws_no_vertical_edges(self):
        bad = []
        for w in WIDTHS:
            e = self.m[w]["tocEdges"]
            if e is None:
                bad.append("at %dpx there is no contents box to measure" % w)
                continue
            if e["l"] > 0 or e["r"] > 0:
                bad.append("at %dpx the contents box still draws %.0fpx/%.0fpx "
                           "side borders" % (w, e["l"], e["r"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_it_is_still_ruled_off_from_the_article(self):
        """Removing the edges must not leave an unmarked list floating in the
        prose: horizontal rules cut the column instead of drawing it."""
        bad = []
        for w in WIDTHS:
            e = self.m[w]["tocEdges"]
            if e and (e["t"] <= 0 or e["b"] <= 0):
                bad.append("at %dpx the contents has no top/bottom rule "
                           "(%.0f/%.0f)" % (w, e["t"], e["b"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_its_links_sit_on_the_articles_own_left_edge(self):
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            if d["tocLinkX"] is None:
                continue
            if abs(d["tocLinkX"] - d["p"]["x"]) > 1.0:
                bad.append("at %dpx the contents links start at x=%.1f and "
                           "the text at x=%.1f"
                           % (w, d["tocLinkX"], d["p"]["x"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_it_hangs_no_markers_outside_the_reading_column(self):
        """A bulleted list of the article's own headings is the widget look
        this pass exists to remove, and it is also a real misalignment: the
        block sets padding-inline-start to 0 so its links sit on the article's
        left edge, and a marker rendered outside that padding box lands 20px
        left of every paragraph on the page."""
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            e = d["tocListEdge"]
            if e is None:
                bad.append("at %dpx there is no contents list to measure" % w)
                continue
            if e["marker"] != "none":
                bad.append("at %dpx the contents list draws %s markers"
                           % (w, e["marker"]))
            if e["x"] < d["p"]["x"] - 1.0:
                bad.append("at %dpx the contents list starts at x=%.1f, left "
                           "of the article's own %.1f"
                           % (w, e["x"], d["p"]["x"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_it_is_one_column_at_every_width(self):
        """PASS THREE, and a reversal of 2.20.61. Two columns solved a height
        problem the 44px tap floor created, and bought a widget: a reader on a
        desktop pointer does not need a 44px row, and two columns of 300px grey
        sans is the single most plugin-looking thing on the page. The height is
        solved where it came from - the floor is now scoped to the phone - and
        the list reads as one column of the article's own type."""
        bad = [("at %dpx the contents is set in %s columns; an editorial "
                "contents is one column at every width"
                % (w, self.m[w]["tocColumns"]))
               for w in WIDTHS if self.m[w]["tocColumns"] != "auto"]
        self.assertEqual(bad, [], "\n".join(bad))

    def test_it_is_set_at_a_size_that_belongs_to_the_body(self):
        """16px sans under a 21px serif is a widget's type, not an article's.
        The gap closes and the face is the reading face, because these strings
        are the article's own headings quoted back."""
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            t = d["tocType"]
            if t is None:
                bad.append("at %dpx there are no contents links to measure" % w)
                continue
            gap = d["p"]["fs"] - t["fs"]
            if gap > TOC_BODY_GAP_MAX:
                bad.append("at %dpx the contents is %.0fpx against %.0fpx of "
                           "body text, %.0fpx under it (max %.0f)"
                           % (w, t["fs"], d["p"]["fs"], gap, TOC_BODY_GAP_MAX))
            if t["fs"] < TOC_FLOOR:
                bad.append("at %dpx the contents is %.0fpx, under the %.0fpx "
                           "floor" % (w, t["fs"], TOC_FLOOR))
            if "Vollkorn" not in t["ff"]:
                bad.append("at %dpx the contents font stack is %r, which is "
                           "not the article's reading face" % (w, t["ff"]))
        self.assertEqual(bad, [], "\n".join(bad))


class TheHeadingsAnnounceASection(ChromeBackedTest):
    """PASS THREE. "Headings do not stand out enough" - h2 was 30px over a
    20px body, 1.50x, with 48px above it. At that ratio a section heading is
    body text in bold, and a 6000px article reads as one flat block.

    Two numbers do the work, and they are different numbers: SIZE says this is
    a heading, SPACE says a section begins here. The scale still steps rather
    than leaps - TheTypeIsSizedForReading holds the 1.05-1.45 ratios between
    each level and the 2.25x ceiling on the h1, and both suites must pass.
    """

    def test_an_h2_is_materially_larger_than_the_text_under_it(self):
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            ratio = d["h2"]["fs"] / d["p"]["fs"]
            floor = (H2_TO_BODY_MIN if w >= GROUND_FROM
                     else H2_TO_BODY_MIN_PHONE)
            if ratio < floor:
                bad.append("at %dpx the H2 is %.0fpx over a %.0fpx body "
                           "(%.2fx), under %.2f: it reads as bold body text"
                           % (w, d["h2"]["fs"], d["p"]["fs"], ratio, floor))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_a_section_visibly_begins(self):
        """Space above an h2, counted in body lines rather than pixels, so the
        threshold means the same thing at 19px on a phone and 23px at 2000."""
        bad = []
        for w in WIDTHS:
            d = self.m[w]
            above = float(d["h2"]["mts"].rstrip("px"))
            lines = above / d["p"]["lh"]
            if lines < H2_AIR_IN_LINES:
                bad.append("at %dpx there are %.0fpx above the H2, %.2f body "
                           "lines, under %.2f: the section does not begin, it "
                           "continues" % (w, above, lines, H2_AIR_IN_LINES))
        self.assertEqual(bad, [], "\n".join(bad))


class TheColumnSitsOnAGround(ChromeBackedTest):
    """PASS THREE, the fourth thing. "At 2000px the article is a thin strip
    floating in white." Two answers were offered and this commits to both
    halves of one of them: the article frame is CAPPED so it cannot spread
    further, and it is given a ground so the cap is something a reader can see.
    A cap alone changes no pixel on a page that was already narrower than it.

    Below 1024px there is no ground and no card. A phone has no room for a
    margin around the reading column, and inventing one is the stacked-gutter
    defect with a nicer name.
    """

    def test_the_frame_stops_spreading_on_a_very_wide_screen(self):
        bad = [("at %dpx the article frame is %.0fpx wide, over the %.0fpx cap"
                % (w, self.m[w]["frame"]["w"], FRAME_CEILING))
               for w in (1600, 2000)
               if self.m[w]["frame"] and self.m[w]["frame"]["w"] > FRAME_CEILING]
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_article_is_a_different_surface_from_the_page_around_it(self):
        bad = []
        for w in (1280, 1600, 2000):
            d = self.m[w]
            if d["frame"] is None or d["ground"] is None:
                bad.append("at %dpx the frame or the ground is not measurable" % w)
                continue
            if d["frame"]["bg"] == d["ground"]:
                bad.append("at %dpx the article and the page around it are the "
                           "same colour (%s), so the column has no ground and "
                           "the cap is invisible" % (w, d["ground"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_phone_keeps_one_edge_to_edge_surface(self):
        bad = []
        for w in (375, 414, 768):
            d = self.m[w]
            if d["frame"] is None or d["ground"] is None:
                continue
            if d["frame"]["bg"] != d["ground"]:
                bad.append("at %dpx the article is on a card (%s on %s); below "
                           "%dpx the page must stay one surface"
                           % (w, d["frame"]["bg"], d["ground"], GROUND_FROM))
        self.assertEqual(bad, [], "\n".join(bad))


class TheLayoutHoldsWithoutTheThirdPartyBox(ChromeBackedTest):
    """div.atr-capture is a Mailjet block injected from wp-admin and the owner
    is deleting it. Nothing in this layout may depend on it being there, and
    the page must be right on both sides of that deletion.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.without = measured(True, False)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("UNKNOWN, NOT A PASS: %s" % exc)

    def test_the_box_is_really_gone_from_the_variant(self):
        self.assertIsNone(self.without[1280]["capture"],
                          "the without-capture fixture still renders one, so "
                          "this class is measuring the same page twice")

    def test_nothing_overflows_without_it(self):
        bad = [("at %dpx the document scrolls sideways without the third-party "
                "box: scrollWidth %d vs clientWidth %d"
                % (w, self.without[w]["scrollWidth"], self.without[w]["clientWidth"]))
               for w in WIDTHS
               if self.without[w]["scrollWidth"] > self.without[w]["clientWidth"]]
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_geometry_that_matters_is_unchanged(self):
        bad = []
        for w in WIDTHS:
            a, b = self.m[w], self.without[w]
            for name in ("p", "hero", "toc"):
                if a[name] is None or b[name] is None:
                    continue
                if abs(a[name]["w"] - b[name]["w"]) > 1.0 or \
                        abs(a[name]["x"] - b[name]["x"]) > 1.0:
                    bad.append("at %dpx the %s moves when the third-party box "
                               "is removed: %.0f@%.0f -> %.0f@%.0f"
                               % (w, name, a[name]["w"], a[name]["x"],
                                  b[name]["w"], b[name]["x"]))
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

    def test_without_the_stylesheet_the_page_has_exactly_one_width(self):
        """Defect 3, proved on the fixture rather than remembered from the
        screenshot: strip the sheet and the hero, the figure, the contents box
        and the text are all the same 645px, which is the page the owner
        described."""
        try:
            before = measured(False)
        except CDPUnavailable as exc:
            self.skipTest("UNKNOWN, NOT A PASS: %s" % exc)

        d = before[2000]
        widths = {name: d[name]["w"] for name in ("p", "hero", "figure", "toc")
                  if d[name] is not None}
        self.assertEqual(
            len(set(round(v) for v in widths.values())), 1,
            "the fixture does not reproduce the one-width page: %r" % widths)

        self.assertGreater(
            d["headerGap"], 120.0,
            "the fixture does not reproduce the 140px hole above the "
            "headline: %.0fpx" % d["headerGap"])


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
