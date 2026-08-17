"""THE APPLAUSE CONTROL AS A READER ON AN ARTICLE ACTUALLY SEES IT.

railway/tests/test_blog_claps.py measures the feature: the atomic increment,
the refusals, the schema, and the component's own stylesheet read as text. It
cannot see the one thing that was wrong on the live page, because the defect
is not in blog-claps.css at all. It is in the cascade.

MEASURED ON THE LIVE POST (bare URL, browser UA, no cache buster) at 2.20.71,
https://asktherecruiter.com/blog/how-long-should-a-resume-be/ :

                        375px viewport        1280px viewport
  button label          15.0px                15.0px
  the count             15.0px                15.0px
  the privacy note      19.0px, 91.2px tall   22.0px, 71.3px tall
  the note's colour     rgb(35,39,43)         rgb(35,39,43)

blog-claps.css asks for 13px in --alt-cl-note (#696d77). It got the ARTICLE
BODY, at the article body's size, in the article body's ink, because the note
is a <p> inside .entry-content and assets/blog-reading.css declares

    body.single-post .entry-content p { font-size: var(--alt-read-body)
                                        !important; color: ... !important }

at specificity (0,3,1) with !important. A component rule of (0,1,0) does not
enter that argument. So the quietest sentence in the block rendered LARGER
than the button it explains, in the same face and the same ink as the article
around it - which is exactly what the owner reported: the note is too loud.

The fix is a rule that can win, in the stylesheet that is losing to itself
(assets/blog-reading.css section 8c). This file is the measurement that says
whether it did, in real headless Chrome, on the real blog fixture, over the
REAL markup that includes/blog-claps.php emits.

WHY THE MARKUP COMES FROM PHP AND THE PAGE FROM THE BLOG FIXTURE. Both halves
have to be real or the measurement is of something nobody ships. The markup is
rendered by alt_claps_render() through tests/fixtures/claps_harness.php, and
the page around it is test_blog_reading_surface.build_page(), which carries the
ancestor chain and all three database stylesheets verbatim from the live page.
A fixture that does not carry the opposition cannot measure a cascade defect.

AND THE WORDING IS CHECKED BY RUNNING THE REAL SCRIPT. The count sentence is
produced server-side by PHP and again client-side by JavaScript after a tap.
Two languages, one sentence, and nothing structural stops them drifting. So
blog-claps.js is loaded into the page, fetch is stubbed to answer with a total,
the button is clicked, and the text the reader ends up with is compared against
what alt_claps_count_phrase() returns for that same number. A divergence fails
here with both strings printed.

No Chrome or no PHP: these SKIP loudly rather than passing. Absence of a signal
is not a pass (CLAUDE.md).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402
import contrast_audit  # noqa: E402

import test_blog_reading_surface as blog  # noqa: E402
from test_blog_claps import PHP, CLAPS_PHP, HARNESS  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CLAPS_JS = PLUGIN / "assets/blog-claps.js"
CLAPS_CSS = PLUGIN / "assets/blog-claps.css"
BLOG_CSS = PLUGIN / "assets/blog-reading.css"

WIDTHS = (375, 414, 768, 1280, 2000)
TAP_MIN = 44.0
AA_NORMAL = 4.5

# The note is subordinate to the button, and "subordinate" is a ratio rather
# than a pixel size: whatever the article's body grows to at 2000px, the note
# stays smaller than the control it explains. 0.9 rather than 1.0 because a
# note the SAME size as the button is what "mixed in" looks like.
NOTE_TO_BUTTON_MAX = 0.9
# And smaller than the article's own body text by a clear step, at every width.
# The live page had it at 1.00x and 1.00x of the body: identical.
NOTE_TO_BODY_MAX = 0.75
# An absolute ceiling as well, because a ratio alone is satisfied by a bigger
# button. 14px is the size the digest's own privacy note sits at on this page.
NOTE_PX_MAX = 14.0
# And a floor. "Quiet" is not "unreadable", and this sentence is a promise.
NOTE_PX_MIN = 12.0

# The marker for section 8c, so the RED-first control can lift exactly this
# change's rules back out of the stylesheet and measure the page as it was.
SECTION_8C = "8c. OUR OWN APPLAUSE CONTROL"


# --------------------------------------------------------------- the markup


def php_render(claps=0):
    """The REAL markup alt_claps_render() emits, for a post with `claps`."""
    if not PHP:
        raise unittest.SkipTest(
            "no php binary found, so the applause markup could not be "
            "rendered by the code that ships it. UNKNOWN, not a pass.")
    tmp = tempfile.mkdtemp(prefix="alt-clap-surface-")
    try:
        db = os.path.join(tmp, "claps.sqlite")

        def run(*args):
            proc = subprocess.run(
                [PHP, str(HARNESS), str(CLAPS_PHP), db, *[str(a) for a in args]],
                capture_output=True, text=True, timeout=120)
            assert proc.returncode == 0, (
                "claps harness %r failed:\n%s\n%s" % (args, proc.stdout, proc.stderr))
            return json.loads(proc.stdout.strip().splitlines()[-1])

        run("install")
        if claps:
            # ALT_CLAPS_PER_REQUEST caps one call at 10, so add in tens.
            left = int(claps)
            while left > 0:
                step = min(left, 10)
                run("bump", 101, 1, step)
                left -= step
        return run("render", 101)["html"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def php_phrase(count):
    """What alt_claps_count_phrase() returns, from the PHP itself.

    Never a Python reimplementation: the whole point of this file's wording
    checks is that the sentence has exactly one definition, and a second one
    here would be the third.
    """
    if not PHP:
        raise unittest.SkipTest("no php binary, so the sentence could not be read")
    # The file registers hooks at load. Stub only what loading it needs; the
    # sentence itself comes from the shipped function.
    stubs = ("define('ABSPATH', '/'); define('MINUTE_IN_SECONDS', 60); "
             "function add_action() {} function add_filter() {} "
             "function number_format_i18n($n) { return number_format($n); } ")
    code = ("require $argv[1]; "
            "echo alt_claps_count_phrase((int) $argv[2]);")
    proc = subprocess.run(
        [PHP, "-r", stubs + code, "--", str(CLAPS_PHP), str(count)],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, (
        "could not call alt_claps_count_phrase(): %s\n%s"
        % (proc.stderr, proc.stdout))
    return proc.stdout


def page_with_applause(html_block, with_fix=True):
    """The blog fixture with the applause control where the_content puts it.

    Priority 24 appends it to the end of the article, one ahead of the signup,
    so it is the last child of .entry-content here.
    """
    page = blog.build_page(with_fix=True)
    if not with_fix:
        css = BLOG_CSS.read_text(encoding="utf-8")
        at = css.find(SECTION_8C)
        assert at > 0, (
            "assets/blog-reading.css carries no %r section, so the applause "
            "control is still styled only by blog-claps.css and loses to "
            "`.entry-content p`" % SECTION_8C)
        start = css.rfind("/*", 0, at)
        stripped = css[:start]
        assert stripped != css, "removing section 8c changed nothing"
        page = blog.build_page(with_fix=False).replace(
            "</head>", "<style>%s</style></head>" % stripped)
    # The component's own stylesheet, enqueued on single posts by
    # alt_claps_enqueue(). It loads BEFORE blog-reading.css on the live page
    # (wp_enqueue_style order), and this fixture reproduces that order.
    page = page.replace(
        "</head>", "<style>%s</style></head>" % CLAPS_CSS.read_text(encoding="utf-8"))
    idx = page.rfind('<h2 class="wp-block-heading"')
    assert idx >= 0, "the blog fixture changed shape"
    close = page.find("</div>", page.find("</p>", idx))
    assert close >= 0
    page = page[:close] + html_block + page[close:]
    return page.replace(
        "</head>", "<style>%s</style></head>" % contrast_audit.FREEZE_CSS)


# ------------------------------------------------------------- measuring

PROBE = "(function () {" + contrast_audit._COLOR_JS + r"""
  function box(el) {
    if (!el) return null;
    var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    var back = backdrop(el);
    var ink = over(parse(cs.color), back.color);
    return {x: +r.left.toFixed(1), right: +r.right.toFixed(1),
            top: +(r.top + scrollY).toFixed(1),
            bottom: +(r.bottom + scrollY).toFixed(1),
            w: +r.width.toFixed(1), h: +r.height.toFixed(1),
            fs: parseFloat(cs.fontSize), fw: cs.fontWeight,
            ff: cs.fontFamily.split(',')[0].replace(/['"]/g, ''),
            color: rgbstr(ink), bg: rgbstr(back.color),
            ratio: +ratio(ink, back.color).toFixed(2),
            text: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 90)};
  }
  var root = document.querySelector('.alt-clap');
  if (!root) return JSON.stringify({missing: true});
  // The SECOND paragraph. The first is the standfirst, which is deliberately
  // larger and painted in --alt-read-ink-strong, so comparing the note
  // against it would compare against a colour no ordinary paragraph uses.
  var ps = [].slice.call(document.querySelectorAll('.entry-content > p'));
  var para = ps.length > 1 ? ps[1] : ps[0];
  return JSON.stringify({
    vw: innerWidth, vh: innerHeight,
    overflow: +(document.documentElement.scrollWidth
                - document.documentElement.clientWidth).toFixed(1),
    root: box(root),
    button: box(root.querySelector('.alt-clap-btn')),
    label: box(root.querySelector('.alt-clap-btn-text')),
    count: box(root.querySelector('.alt-clap-count')),
    note: box(root.querySelector('.alt-clap-note')),
    body: box(para)
  });
})()
"""


class _Rendered(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the applause control "
                "on an article could not be measured. UNKNOWN, not a pass.")
        cls._cache = {}
        cls._markup = {}

    @classmethod
    def markup(cls, claps):
        if claps not in cls._markup:
            cls._markup[claps] = php_render(claps)
        return cls._markup[claps]

    def rendered(self, width, height=812, claps=12, with_fix=True):
        key = (width, height, claps, with_fix)
        if key in self._cache:
            return self._cache[key]
        html = page_with_applause(self.markup(claps), with_fix=with_fix)
        try:
            with Browser(width=width, height=height) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                data = json.loads(page.eval_js(PROBE))
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        self.assertFalse(
            data.get("missing"),
            "the applause control did not render into the article at %dx%d"
            % (width, height))
        self._cache[key] = data
        return data


class ThePrivacyNoteIsQuiet(_Rendered):
    """The owner's third note. The sentence stays; its voice drops."""

    def test_the_note_is_smaller_than_the_button_it_explains(self):
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            note, btn = d["note"], d["button"]
            if note["fs"] > btn["fs"] * NOTE_TO_BUTTON_MAX + 0.05:
                bad.append(
                    "%dpx: the note is %.1fpx against a %.1fpx button label "
                    "(%.2fx, ceiling %.2fx)"
                    % (width, note["fs"], btn["fs"],
                       note["fs"] / btn["fs"], NOTE_TO_BUTTON_MAX))
        self.assertEqual(
            [], bad,
            "the privacy note is not subordinate to the control it sits "
            "under. It is a <p> inside .entry-content, so "
            "assets/blog-reading.css sets its size at (0,3,1) !important and "
            "blog-claps.css's 13px never applies:\n  " + "\n  ".join(bad))

    def test_the_note_is_clearly_smaller_than_the_article_body(self):
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            note, body = d["note"], d["body"]
            self.assertIsNotNone(body, "the fixture rendered no article paragraph")
            if note["fs"] > body["fs"] * NOTE_TO_BODY_MAX + 0.05:
                bad.append(
                    "%dpx: the note is %.1fpx against %.1fpx of article body "
                    "text (%.2fx, ceiling %.2fx)"
                    % (width, note["fs"], body["fs"],
                       note["fs"] / body["fs"], NOTE_TO_BODY_MAX))
        self.assertEqual(
            [], bad,
            "the note reads as article prose rather than as a footnote on a "
            "control:\n  " + "\n  ".join(bad))

    def test_the_note_sits_inside_a_narrow_band_of_sizes(self):
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            fs = d["note"]["fs"]
            if not (NOTE_PX_MIN - 0.05 <= fs <= NOTE_PX_MAX + 0.05):
                bad.append("%dpx: the note renders at %.1fpx" % (width, fs))
        self.assertEqual(
            [], bad,
            "the note must land between %.0f and %.0fpx at every width. Under "
            "the floor it stops being a readable promise; over the ceiling it "
            "is competing with the control again:\n  %s"
            % (NOTE_PX_MIN, NOTE_PX_MAX, "\n  ".join(bad)))

    def test_the_note_is_below_the_control_not_beside_it(self):
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            if d["note"]["top"] < d["button"]["bottom"] - 0.5:
                bad.append(
                    "%dpx: the note starts at y=%.1f while the button ends at "
                    "y=%.1f" % (width, d["note"]["top"], d["button"]["bottom"]))
        self.assertEqual(
            [], bad,
            "the note must be on its own line under the control at every "
            "width. Beside a 44px button on a 375px screen it has about 200px "
            "to say a 96-character sentence in:\n  " + "\n  ".join(bad))

    def test_the_note_keeps_its_words(self):
        """The sentence is a promise and this change is about its VOICE."""
        d = self.rendered(375, 812)
        for phrase in ("Anonymous and approximate",
                       "We store one number for this article and nothing about you"):
            self.assertIn(
                phrase, d["note"]["text"],
                "the note no longer says %r. Making it quiet is not licence to "
                "edit it: it states what the counter cannot do, and it is the "
                "reason the counter is allowed to exist. Note read: %r"
                % (phrase, d["note"]["text"]))

    def test_the_note_still_meets_AA_where_it_is_actually_painted(self):
        """Small muted text is exactly where contrast gets failed. This is the
        composited ratio in the browser, not arithmetic over two literals."""
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            n = d["note"]
            if n["ratio"] < AA_NORMAL - 0.005:
                bad.append("%dpx: %s on %s = %.2f:1, needs %.1f"
                           % (width, n["color"], n["bg"], n["ratio"], AA_NORMAL))
        self.assertEqual(
            [], bad,
            "the privacy note fails WCAG 1.4.3 on an article:\n  "
            + "\n  ".join(bad))

    def test_the_note_is_muted_and_not_the_article_ink(self):
        d = self.rendered(1280, 900)
        self.assertNotEqual(
            d["note"]["color"], d["body"]["color"],
            "the note is painted in the article's own body ink (%s), so it "
            "reads as another sentence of the article rather than as an aside "
            "on a control" % d["note"]["color"])
        self.assertLess(
            d["note"]["ratio"], d["body"]["ratio"],
            "the note (%.2f:1) is not quieter than the article body (%.2f:1)"
            % (d["note"]["ratio"], d["body"]["ratio"]))


class TheControlDidNotShrinkWithIt(_Rendered):
    """Quieting the note must not touch the thing a thumb aims at."""

    def test_the_button_clears_the_tap_floor_at_every_width(self):
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            b = d["button"]
            if b["h"] < TAP_MIN - 0.05 or b["w"] < TAP_MIN - 0.05:
                bad.append("%dpx: the button is %.1f x %.1f" % (width, b["w"], b["h"]))
        self.assertEqual(
            [], bad,
            "the applause button is under %.0f x %.0f (WCAG 2.5.5):\n  %s"
            % (TAP_MIN, TAP_MIN, "\n  ".join(bad)))

    def test_the_control_does_not_bleed_sideways(self):
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            if d["overflow"] > 0.5:
                bad.append("%dpx: the document is %.1fpx wider than the viewport"
                           % (width, d["overflow"]))
            r = d["root"]
            if r["x"] < -0.5 or r["right"] > d["vw"] + 0.5:
                bad.append("%dpx: the control spans %.1f to %.1f in a %dpx viewport"
                           % (width, r["x"], r["right"], d["vw"]))
        self.assertEqual([], bad, "the applause control bleeds sideways:\n  "
                                  + "\n  ".join(bad))

    def test_the_count_is_readable_and_meets_AA(self):
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            c = d["count"]
            if c["ratio"] < AA_NORMAL - 0.005:
                bad.append("%dpx count: %s on %s = %.2f:1"
                           % (width, c["color"], c["bg"], c["ratio"]))
            if c["fs"] < d["note"]["fs"] + 0.5:
                bad.append("%dpx: the count (%.1fpx) is not larger than the "
                           "note (%.1fpx)" % (width, c["fs"], d["note"]["fs"]))
        self.assertEqual([], bad, "the count reads wrong on an article:\n  "
                                  + "\n  ".join(bad))


class TheGuardFailsOnThePageAsItWas(_Rendered):
    """The half that makes every assertion above evidence.

    With section 8c lifted back out of assets/blog-reading.css, the note has to
    measure as the defect the owner reported - and specifically as TOO LARGE,
    not merely as different, or this file is passing for the wrong reason.
    """

    def test_without_section_8c_the_note_is_larger_than_the_button(self):
        seen = []
        for width in (375, 1280):
            d = self.rendered(width, 812 if width < 768 else 900, with_fix=False)
            if d["note"]["fs"] > d["button"]["fs"]:
                seen.append("%dpx: note %.1fpx > button label %.1fpx"
                            % (width, d["note"]["fs"], d["button"]["fs"]))
        self.assertTrue(
            seen,
            "with section 8c removed the note did NOT render larger than the "
            "button, so this file can no longer see the defect it was written "
            "for. Either the blog stylesheet stopped setting `.entry-content "
            "p` at (0,3,1) !important, or the removal is no longer removing "
            "the fix. Fix the control, do not delete these assertions.")

    def test_without_section_8c_the_note_matches_the_article_body(self):
        d = self.rendered(1280, 900, with_fix=False)
        self.assertAlmostEqual(
            d["note"]["fs"], d["body"]["fs"], delta=0.6,
            msg="the pre-fix note measured %.1fpx against a %.1fpx article "
                "body. The recorded defect is that they are the SAME size, "
                "because both are matched by the same rule."
                % (d["note"]["fs"], d["body"]["fs"]))


class TheTwoStylesheetsAgreeAboutTheNote(unittest.TestCase):
    """No Chrome needed. The one number that is written twice.

    CSS cannot read another rule's font-size, so assets/blog-reading.css has to
    restate the size assets/blog-claps.css declares. That is a second copy of a
    value, which is a thing that drifts, so it is checked rather than trusted.
    """

    @staticmethod
    def _size(text, selector):
        src = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        i = src.find(selector)
        assert i > -1, "no rule %r" % selector
        body = src[src.index("{", i) + 1:src.index("}", src.index("{", i))]
        m = re.search(r"font-size:\s*([0-9.]+)px", body)
        assert m, "rule %r declares no px font-size: %r" % (selector, body)
        return float(m.group(1))

    def test_the_note_is_the_same_size_in_both_files(self):
        component = self._size(CLAPS_CSS.read_text(encoding="utf-8"),
                               ".alt-clap-note {")
        page = self._size(BLOG_CSS.read_text(encoding="utf-8"),
                          "p.alt-clap-note {")
        self.assertEqual(
            component, page,
            "assets/blog-claps.css sets the privacy note at %.0fpx and "
            "assets/blog-reading.css sets it at %.0fpx. The second exists only "
            "because `.entry-content p` outranks the first; it is not a "
            "different design decision and it must not become one."
            % (component, page))

    def test_the_page_rule_carries_the_element_selector_that_makes_it_win(self):
        css = re.sub(r"/\*.*?\*/", " ", BLOG_CSS.read_text(encoding="utf-8"),
                     flags=re.S)
        self.assertIn(
            "body.single-post .entry-content p.alt-clap-note", css,
            "the note's rule in assets/blog-reading.css does not name the "
            "element. `.entry-content p` is (0,1,1) and a class alone is "
            "(0,1,0), so between two !important declarations the article's "
            "body rule still wins and this change moves nothing.")


# ------------------------------------------------- one sentence, two languages

TAP_SCRIPT = r"""
(function () {
  window.__served = null;
  window.fetch = function (url, opts) {
    var body = JSON.parse(opts.body);
    window.__served = __TOTAL__;
    return Promise.resolve({ok: true, json: function () {
      return Promise.resolve({post_id: body.id, claps: __TOTAL__, counted: true});
    }});
  };
  return true;
})()
"""

READ_COUNT = r"""
(function () {
  var el = document.querySelector('[data-alt-clap-count]');
  var live = document.querySelector('[data-alt-clap-live]');
  return JSON.stringify({
    count: (el ? el.textContent : '').replace(/\s+/g, ' ').trim(),
    live: (live ? live.textContent : '').replace(/\s+/g, ' ').trim()
  });
})()
"""


class TheSentenceHasOneDefinition(unittest.TestCase):
    """PHP writes it on the server and JavaScript rewrites it after a tap.

    Two languages cannot share a string literal, so what is shared instead is
    the TEMPLATE: PHP emits it into the markup and blog-claps.js fills in the
    number. This runs the real script in a real browser over the real markup
    and compares what the reader ends up with against what the PHP function
    says, so a divergence cannot ship quietly.
    """

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium, so the script that rewrites the count "
                "could not be run. UNKNOWN, not a pass.")

    def _after_taps(self, start, total):
        html = page_with_applause(php_render(start))
        # alt_claps_enqueue() puts the endpoint in front of the script with
        # wp_add_inline_script(..., 'before'). Same order here, or setup()
        # returns on its first line and nothing is measured.
        html = html.replace(
            "</body>",
            "<script>window.ALT_CLAPS_ENDPOINT = "
            "'https://example.test/wp-json/layoffs/v1/clap';</script>"
            "<script>%s</script></body>" % CLAPS_JS.read_text(encoding="utf-8"))
        try:
            with Browser(width=1280, height=900) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                page.eval_js(TAP_SCRIPT.replace("__TOTAL__", str(total)))
                page.eval_js(
                    "(function(){document.querySelector('[data-alt-clap-btn]')"
                    ".click();return true;})()")
                # The script batches taps for 500ms before it sends.
                page.eval_js("new Promise(function(r){setTimeout(function(){"
                             "r(true);}, 1200);})", await_promise=True)
                return json.loads(page.eval_js(READ_COUNT))
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)

    def test_one_is_a_person_and_two_are_people_after_a_tap(self):
        for total in (1, 2, 12, 1234):
            with self.subTest(total=total):
                want = php_phrase(total)
                got = self._after_taps(0, total)["count"]
                self.assertEqual(
                    got, want,
                    "after a tap the browser shows %r while "
                    "alt_claps_count_phrase(%d) in includes/blog-claps.php "
                    "says %r. The sentence is rendered twice, once per "
                    "language, and the two have drifted. The template must "
                    "reach the script through the markup so there is one "
                    "definition." % (got, total, want))

    def test_the_announcement_uses_the_same_sentence(self):
        data = self._after_taps(0, 7)
        want = php_phrase(7)
        self.assertIn(
            want, data["live"],
            "the aria-live announcement says %r, which does not contain the "
            "sentence a sighted reader sees (%r). A screen reader must be told "
            "the same thing." % (data["live"], want))

    def test_the_script_carries_no_copy_of_the_words(self):
        js = CLAPS_JS.read_text(encoding="utf-8")
        js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
        js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
        for word in ("helpful", "person", "people", "clap'", 'clap"'):
            self.assertNotIn(
                word, js,
                "assets/blog-claps.js contains %r. The count sentence has one "
                "definition, in alt_claps_count_phrase(), and it reaches the "
                "script as a template in the markup. A literal here is the "
                "second definition and it will drift." % word)


if __name__ == "__main__":
    unittest.main()
