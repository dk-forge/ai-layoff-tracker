"""OUR OWN SIGNUP IS ON THE PAGES READERS LAND ON, AND IT STANDS ON ITS OWN.

WHY THIS FILE EXISTS. alt_digest_subscribe_form() rendered on exactly two
URLs: this repo's tracker page and the sibling talent tracker's. Everything
else the plugin publishes offered nothing. Measured off the repo before this
change, by counting call sites:

    templates/page-tracker.php          1 call   (context 'layoff')
    every other template                0 calls
    any the_content / is_singular hook  none exists

while the plugin renders company profiles at /company-layoffs/<slug>/, facet
pages at /country-layoffs/, /state-layoffs/ and /industry-layoffs/, the layoffs
CPT permalinks, and styles the site's articles from
includes/blog-typography.php without ever offering anything on one.

THE DEFECT UNDERNEATH IT, which is why this is not four one-line calls. The
component's own comment claimed it "may depend on nothing outside itself". It
did not:

    .alt-digest         border: 1px solid var(--alt-border)     no fallback
    .alt-digest-status  background/color/border  4 x var(--alt-*)  no fallback
    submit button       class="alt-btn alt-btn-primary"         layoffs.css
    email field         border: 1px solid #ccc                  1.6:1 on white

Those tokens and both classes live in assets/layoffs.css, which
alt_page_needs_assets() enqueues on tracker surfaces and NOT on a blog post. A
bare var() with no fallback resolves to unset, so the pre-change component on
an article is a box with no border, a stock grey browser button and a field
outline that fails WCAG 1.4.11 everywhere it renders. Placing it without fixing
that ships four broken signups instead of none.

WHAT IS PINNED HERE:

  * the four surfaces each place it, exactly once, through one helper;
  * the blog placement is gated on is_singular('post'), the same gate
    includes/blog-typography.php uses, so the stylesheet and the markup cannot
    disagree about what an article is;
  * the excerpt gate, which is the one that actually bites: get_the_excerpt()
    runs the_content during wp_head for an SEO description, and without the
    guard the once-per-request static is spent before the article renders;
  * EVERY colour in the component resolves without layoffs.css. This is the
    assertion the pre-change tree fails hardest;
  * rendered on a real blog-post fixture, in real headless Chrome, WITH the
    third-party .atr-capture box present: the phone fold, the 44px floor, no
    sideways bleed at 375/414/768/1280, and AA contrast on the text and 3:1 on
    the control edges;
  * removing .atr-capture changes the signup's geometry by nothing, which is
    the machine-checkable form of "it does not depend on the box above it".

THE PHONE FOLD IS THE REPEATED DEFECT. Twice on 2026-08-14 the submit button
landed below 812px on a 375x812 screen, and a local pass is not evidence: the
harness rendered the component 375px wide because the fixture had no theme
gutter, reported 741.7px, and the live page put the button 15px below the fold.
The fixture below is the blog fixture from test_blog_reading_surface.py, which
carries the ancestor chain and all three database stylesheets verbatim from the
live page, gutters included.

No Chrome, no measurement: this SKIPS loudly rather than passing. Absence of a
signal is not a pass (CLAUDE.md).

PROVEN TO FAIL ON THE PRE-CHANGE TREE. The exact assertion text is recorded in
docs/TECHLOG.md for this change.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402
import contrast_audit  # noqa: E402

import test_blog_reading_surface as blog  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
MAIN = PLUGIN / "ai-layoff-tracker.php"
SUBSCRIBE = PLUGIN / "includes/subscribe.php"
PLACEMENTS = PLUGIN / "includes/subscribe-placements.php"
BLOG_CSS = PLUGIN / "assets/blog-reading.css"

# The surfaces this change adds, as (context, template that must call it).
# 'post' has no template: it is appended by a the_content filter.
TEMPLATE_SURFACES = (
    ("company", PLUGIN / "templates/page-company-directory.php"),
    ("facet", PLUGIN / "templates/page-facet.php"),
    ("entry", PLUGIN / "templates/single-layoff.php"),
)

TAP_MIN = 44.0
AA_NORMAL = 4.5
AA_LARGE = 3.0
AA_NONTEXT = 3.0
WIDTHS = (375, 414, 768, 1280)


def component_style():
    """The component's self-carried <style> block, read out of its own file."""
    src = SUBSCRIBE.read_text(encoding="utf-8")
    start = src.find("<style>")
    assert start >= 0, "includes/subscribe.php carries no <style> block"
    end = src.find("</style>", start)
    assert end >= 0, "the component's <style> block is not closed"
    return src[start + len("<style>"):end]


# --------------------------------------------------------------- static bars


class TheSignupIsPlacedOnEverySurfaceReadersLandOn(unittest.TestCase):

    def test_the_placement_file_exists_and_is_loaded(self):
        self.assertTrue(
            PLACEMENTS.is_file(),
            "includes/subscribe-placements.php does not exist, so the signup "
            "still renders only where page-tracker.php calls it by hand")
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn(
            "includes/subscribe-placements.php", main,
            "ai-layoff-tracker.php never loads includes/subscribe-placements."
            "php, so none of its hooks are registered and the file is dead")

    def test_a_new_include_is_race_guarded_not_hard_required(self):
        """An FTPS deploy uploads one file at a time. A hard require of a
        not-yet-uploaded include fatals the whole plugin (2.19.20)."""
        main = MAIN.read_text(encoding="utf-8")
        m = re.search(
            r"\$alt_subscribe_placements\s*=.*?\n\s*if \(is_readable\(\$alt_subscribe_placements\)\)",
            main, re.S)
        self.assertTrue(
            m,
            "includes/subscribe-placements.php is loaded without an "
            "is_readable() guard. It is a NEW file, so the deploy that "
            "introduces it can land ai-layoff-tracker.php first, and a hard "
            "require of a file that is not there yet white-screens /blog on "
            "every request until it arrives.")

    def test_each_template_surface_places_it_exactly_once(self):
        bad = []
        for context, path in TEMPLATE_SURFACES:
            if not path.is_file():
                bad.append("%s does not exist" % path.name)
                continue
            src = path.read_text(encoding="utf-8")
            calls = re.findall(r"alt_digest_placement\('([a-z]+)'\)", src)
            if calls != [context]:
                bad.append(
                    "%s calls alt_digest_placement%r, expected exactly one "
                    "call with %r" % (path.name, calls, context))
        self.assertEqual(
            [], bad,
            "a surface readers land on does not offer our own signup, or "
            "offers it twice:\n  " + "\n  ".join(bad))

    def test_the_template_calls_are_function_exists_guarded(self):
        """The FTP-deploy race again, from the other side: the template can
        render before includes/subscribe-placements.php has landed."""
        bad = []
        for _context, path in TEMPLATE_SURFACES:
            src = path.read_text(encoding="utf-8")
            for m in re.finditer(r"alt_digest_placement\('", src):
                head = src[:m.start()]
                near = head.rsplit("\n", 3)[-3:]
                if not any("function_exists('alt_digest_placement')" in ln
                           for ln in near):
                    bad.append("%s:%d" % (path.name, head.count("\n") + 1))
        self.assertEqual(
            [], bad,
            "an unguarded call to alt_digest_placement() would fatal the page "
            "if the include has not landed yet:\n  " + "\n  ".join(bad))

    def test_the_blog_placement_uses_the_same_gate_as_the_stylesheet(self):
        src = PLACEMENTS.read_text(encoding="utf-8")
        self.assertIn(
            "is_singular('post')", src,
            "the blog placement is not gated on is_singular('post'), which is "
            "the gate includes/blog-typography.php uses for the stylesheet "
            "that styles this block. Two different answers to 'what is an "
            "article' is how one ships without the other.")
        self.assertIn(
            "add_filter('the_content', 'alt_digest_append_to_post'", src,
            "nothing hooks the_content, so a blog post renders no signup")

    def test_the_excerpt_pass_cannot_eat_the_placement(self):
        """get_the_excerpt() runs the_content filters, and an SEO plugin does
        that during wp_head. Without this gate the once-per-request static is
        spent on a meta description and the reader gets nothing."""
        src = PLACEMENTS.read_text(encoding="utf-8")
        self.assertIn(
            "doing_filter('get_the_excerpt')", src,
            "alt_digest_append_to_post() does not stand down during an "
            "excerpt pass, so the form can be consumed before the article "
            "renders and the reader sees no signup at all")
        for gate in ("in_the_loop()", "is_main_query()"):
            self.assertIn(
                gate, src,
                "alt_digest_append_to_post() does not check %s, so a "
                "related-posts widget rendering the same content prints a "
                "second form with a second id=\"alt-digest\"" % gate)

    def test_one_placement_per_page_is_enforced_not_assumed(self):
        src = PLACEMENTS.read_text(encoding="utf-8")
        self.assertTrue(
            re.search(r"static \$placed\s*=\s*false", src),
            "alt_digest_placement() keeps no once-per-request state, so "
            "the_content firing more than once for one article (WordPress "
            "does this routinely) prints the form twice, with two identical "
            "id=\"alt-digest\" anchors on one page")

    def test_no_second_form_table_or_route_was_built(self):
        """One signup, one flow. This file must place the existing form."""
        src = PLACEMENTS.read_text(encoding="utf-8")
        for banned, why in (
                ("<form", "a second form"),
                ("CREATE TABLE", "a second table"),
                ("register_rest_route", "a second route")):
            self.assertNotIn(
                banned, src,
                "includes/subscribe-placements.php contains %r, so it is "
                "building %s instead of calling the one in subscribe.php"
                % (banned, why))


class TheContextArgumentDoesSomething(unittest.TestCase):
    """It was a parameter that the body never read. Placing the form on four
    more surfaces is the reason it has to."""

    def test_every_placed_context_has_its_own_lead_sentence(self):
        src = SUBSCRIBE.read_text(encoding="utf-8")
        m = re.search(r"function alt_digest_context_lead\(.*?\n\}", src, re.S)
        self.assertTrue(
            m,
            "there is no alt_digest_context_lead(), so $context is still a "
            "parameter that alt_digest_subscribe_form() never reads and the "
            "signup says 'what changed on these trackers' to a reader who "
            "arrived on an article about resume length")
        body = m.group(0)
        placements = PLACEMENTS.read_text(encoding="utf-8")
        contexts = re.findall(r"'([a-z]+)'",
                              re.search(r"function alt_digest_placement_contexts"
                                        r"\(.*?\n\}", placements, re.S).group(0))
        for context in contexts:
            self.assertIn(
                "'%s'" % context, body,
                "context %r is placed on a real page but has no lead sentence, "
                "so that surface renders the tracker's own wording" % context)

    def test_the_lead_is_rendered_and_escaped(self):
        src = SUBSCRIBE.read_text(encoding="utf-8")
        self.assertIn(
            "esc_html($lead)", src,
            "the context lead is not escaped on output")

    def test_the_section_open_tag_is_still_regex_readable(self):
        """test_digest_route_is_findable.py reads the signup's own <h2> with a
        `<section class="alt-digest"[^>]*>\\s*<h2>` pattern over the raw PHP.
        A PHP echo in that tag carries a literal '>' in its '?>' and breaks it,
        which is why the context rides on the <form> instead."""
        m = re.search(r'<section class="alt-digest"[^>]*>\s*<h2>([^<]+)</h2>',
                      SUBSCRIBE.read_text(encoding="utf-8"))
        self.assertTrue(
            m,
            "the signup's <section> open tag or its <h2> changed shape, which "
            "breaks digest_heading() in test_digest_route_is_findable.py and "
            "with it the check that the hero button and this section carry one "
            "name")


class TheComponentStandsOnItsOwn(unittest.TestCase):
    """The assertion the pre-change tree fails hardest. layoffs.css is not
    enqueued on a blog post, so anything the component borrows from it is
    simply absent there."""

    def test_every_var_in_the_self_carried_style_has_a_fallback(self):
        style = component_style()
        # Tokens the component DEFINES in this same block need no fallback:
        # they are the indirection, and each one carries the literal itself.
        # Only a token borrowed from outside the component can go unresolved.
        own = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", style, re.M))
        naked = []
        for m in re.finditer(r"var\(\s*(--[a-z0-9-]+)\s*([,)])", style):
            if m.group(2) == ")" and m.group(1) not in own:
                naked.append(m.group(1))
        self.assertEqual(
            [], sorted(set(naked)),
            "the signup's self-carried <style> reads %s with no fallback "
            "value. Those tokens are defined in assets/layoffs.css, which is "
            "enqueued on tracker surfaces and on NO blog post, so on an "
            "article each one resolves to unset: no border on the box, no "
            "fill on the button. Write var(--token, #literal)."
            % ", ".join(sorted(set(naked))))

    def test_the_submit_button_does_not_borrow_a_layoffs_css_class(self):
        src = SUBSCRIBE.read_text(encoding="utf-8")
        m = re.search(r'<button type="submit"[^>]*class="([^"]+)"', src)
        self.assertTrue(m, "the signup has no submit button with a class")
        classes = set(m.group(1).split())
        borrowed = classes & {"alt-btn", "alt-btn-primary", "alt-btn-sm"}
        self.assertEqual(
            set(), borrowed,
            "the submit button wears %s, which is defined in "
            "assets/layoffs.css and absent on every blog post, so the reader "
            "gets a stock grey browser button. It also inherits "
            ".alt-btn:hover, which repaints a control's edge in "
            "--alt-chart-dim at about 1.2:1 on a light fill."
            % ", ".join(sorted(borrowed)))
        self.assertIn(
            "alt-digest-submit", classes,
            "the submit button carries no component-owned class to style")

    def test_no_hardcoded_control_edge_survives(self):
        style = component_style()
        self.assertNotIn(
            "#ccc", style,
            "the email field's border is still the hard-coded #ccc it shipped "
            "with. That measures 1.6:1 against white and fails WCAG 1.4.11 "
            "(3:1 for a control boundary) on every surface, tracker included.")

    def test_the_component_declares_no_dark_palette_of_its_own(self):
        """Deliberate, and the reason is worth pinning: the surfaces with a
        dark mode all load layoffs.css and are served by the var() half of
        every token. The one surface leaning on the literals is the blog, and
        blog-reading.css declares no dark palette while the theme pins the
        article to #fff. A dark box on a permanently white page is a hole."""
        self.assertNotIn(
            "prefers-color-scheme", component_style(),
            "the signup's self-carried style declares a dark palette. Its "
            "fallback literals are used only where layoffs.css is absent, "
            "which today is the blog, and the blog has no dark mode: see "
            "assets/blog-reading.css, which declares none.")
        self.assertNotIn(
            "prefers-color-scheme", BLOG_CSS.read_text(encoding="utf-8"),
            "assets/blog-reading.css now declares a dark palette, so the "
            "reasoning above no longer holds and the signup's fallbacks need "
            "a dark half after all")


class NothingTouchesTheThirdPartyCapture(unittest.TestCase):
    """div.atr-capture is a cross-origin Mailjet iframe injected from
    WordPress. The owner deletes it in wp-admin; this repo cannot, and must not
    depend on whether it is there."""

    def test_the_new_code_never_mentions_it(self):
        for path in (PLACEMENTS, SUBSCRIBE):
            src = path.read_text(encoding="utf-8")
            code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
            code = re.sub(r"^\s*(//|\*).*$", "", code, flags=re.M)
            self.assertNotIn(
                "atr-capture", code,
                "%s references .atr-capture outside a comment. Its contents "
                "are cross-origin and unreachable, and the owner may delete "
                "it at any moment." % path.name)

    def test_the_new_blog_rules_never_select_it(self):
        css = BLOG_CSS.read_text(encoding="utf-8")
        marker = css.find("8b. OUR OWN email signup")
        self.assertGreater(
            marker, 0, "section 8b is missing from blog-reading.css")
        # Slice from the OPENING of the comment that carries the marker, not
        # from the marker itself: starting mid-comment drops the `/*` and the
        # comment stripper below then cannot see where the prose ends.
        new = css[css.rfind("/*", 0, marker):]
        # Selectors, not prose: section 8b's comment explains at length why it
        # leaves that box alone, and naming a thing in order to say "this does
        # not touch it" is the opposite of coupling to it.
        new = re.sub(r"/\*.*?\*/", "", new, flags=re.S)
        self.assertNotIn(
            "atr-capture", new,
            "the new signup rules select .atr-capture. Section 8 above "
            "already styles it and predates this change; section 8b must not "
            "couple our block to whether that box exists.")


# ------------------------------------------------------- the rendered checks

# The signup, sliced out of its own file, PHP stripped. Reuses the landmarks
# test_digest_route_is_findable.py already relies on so the two cannot drift.
def digest_markup(context_lead=""):
    src = SUBSCRIBE.read_text(encoding="utf-8")
    start = src.find("<style>")
    end = src.find("</section>", start)
    assert start >= 0 and end >= 0, "cannot slice the signup out of its file"
    html = re.sub(r"<\?php.*?\?>", "", src[start:end + len("</section>")],
                  flags=re.S)
    # The lead sentence is PHP-emitted, so stripping PHP removes it. Put the
    # real one back: it is the longest intro any surface renders and therefore
    # the one the fold has to survive.
    if context_lead:
        html = html.replace('class="alt-digest-intro">',
                            'class="alt-digest-intro">%s ' % context_lead)
    return html


def longest_lead():
    """The worst case for the fold: the longest sentence any context adds."""
    src = SUBSCRIBE.read_text(encoding="utf-8")
    m = re.search(r"function alt_digest_context_lead\(.*?\n\}", src, re.S)
    if not m:
        return ""
    leads = re.findall(r"=>\s*'([^']*)'", m.group(0))
    return max(leads, key=len) if leads else ""


def blog_page_with_signup(with_capture=True):
    """The real blog fixture, with the signup appended to .entry-content
    exactly where the_content puts it: as the last child of the article."""
    html = blog.build_page(with_fix=True)
    block = digest_markup(longest_lead())
    marker = "</div>\n      </div>\n    </div>\n  </main>"
    assert html.count("</div>") > 3
    # Append inside .entry-content, immediately before it closes.
    idx = html.find('<h2 class="wp-block-heading" id="b">')
    assert idx >= 0, "the blog fixture changed shape"
    close = html.find("</div>", html.find("</p>", idx))
    assert close >= 0
    html = html[:close] + block + html[close:]
    if not with_capture:
        start = html.find('<div class="atr-capture">')
        assert start >= 0, "the blog fixture no longer carries .atr-capture"
        end = html.find("</div>", html.find("atr-capture-msg")) + len("</div>")
        html = html[:start] + html[end:]
    return html.replace("</head>",
                        "<style>%s</style></head>" % contrast_audit.FREEZE_CSS)


# The colour arithmetic is contrast_audit's, pasted in rather than reimplemented:
# two implementations of a contrast ratio is two numbers to reconcile the first
# time they disagree (contrast_audit.py's own comment, and its rule).
PROBE = contrast_audit._COLOR_JS + r"""
(function () {
  function box(el) {
    if (!el) return null;
    var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return {top: +(r.top + scrollY).toFixed(1), h: +r.height.toFixed(1),
            w: +r.width.toFixed(1), left: +r.left.toFixed(1),
            right: +r.right.toFixed(1),
            fs: parseFloat(cs.fontSize), fw: cs.fontWeight,
            color: cs.color, bg: cs.backgroundColor,
            border: cs.borderTopColor, bw: parseFloat(cs.borderTopWidth) || 0,
            text: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80)};
  }
  var sec = document.querySelector('#alt-digest');
  if (!sec) return JSON.stringify({missing: true});
  var texts = [];
  Array.prototype.forEach.call(sec.querySelectorAll('h2, p, label, legend, summary, button'),
    function (el) {
      var own = '';
      Array.prototype.forEach.call(el.childNodes, function (n) {
        if (n.nodeType === 3) own += n.nodeValue;
      });
      if (!own.trim()) return;
      var cs = getComputedStyle(el);
      var back = backdrop(el);
      var ink = over(parse(cs.color), back.color);
      texts.push({tag: el.tagName, color: rgbstr(ink),
                  bg: rgbstr(back.color), painted: back.painted,
                  ratio: +ratio(ink, back.color).toFixed(2),
                  fs: parseFloat(cs.fontSize), fw: cs.fontWeight,
                  text: own.replace(/\s+/g, ' ').trim().slice(0, 50)});
    });
  function edge(el, againstEl) {
    if (!el) return null;
    var cs = getComputedStyle(el);
    var bw = parseFloat(cs.borderTopWidth) || 0;
    var col = over(parse(cs.borderTopColor), backdrop(el).color);
    var against = backdrop(againstEl || el.parentElement).color;
    return {width: bw, color: rgbstr(col), against: rgbstr(against),
            ratio: +ratio(col, against).toFixed(2)};
  }
  function fill(el, againstEl) {
    if (!el) return null;
    var c = over(parse(getComputedStyle(el).backgroundColor),
                 backdrop(el.parentElement).color);
    var against = backdrop(againstEl || el.parentElement).color;
    return {color: rgbstr(c), against: rgbstr(against),
            ratio: +ratio(c, against).toFixed(2)};
  }
  return JSON.stringify({
    vh: innerHeight, vw: innerWidth,
    overflow: +(document.documentElement.scrollWidth
                - document.documentElement.clientWidth).toFixed(1),
    section: box(sec),
    heading: box(sec.querySelector('h2')),
    field: box(sec.querySelector('input[type="email"]')),
    submit: box(sec.querySelector('button[type="submit"]')),
    summary: box(sec.querySelector('summary')),
    sectionEdge: edge(sec, sec.parentElement),
    fieldEdge: edge(sec.querySelector('input[type="email"]'), sec),
    submitFill: fill(sec.querySelector('button[type="submit"]'), sec),
    texts: texts
  });
})()
"""


class _Rendered(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the signup on a blog "
                "post could not be measured. This is UNKNOWN, not a pass.")
        cls._cache = {}

    def rendered(self, width, height=812, with_capture=True):
        key = (width, height, with_capture)
        if key in self._cache:
            return self._cache[key]
        html = blog_page_with_signup(with_capture)
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
            "the signup did not render into the article at all at %dx%d"
            % (width, height))
        self._cache[key] = data
        return data


class TheSignupFitsAPhoneScreen(_Rendered):
    """THE REPEATED DEFECT. Twice on 2026-08-14 the submit button landed below
    812px on a 375x812 screen, and both times a local run passed."""

    def test_the_whole_signup_fits_one_phone_screen(self):
        for width, height in ((375, 812), (414, 896)):
            d = self.rendered(width, height)
            top = d["section"]["top"]
            bad = []
            for part in ("heading", "field", "submit"):
                b = d[part]
                self.assertIsNotNone(b, "the signup has no %s" % part)
                # Measured as a reader who has scrolled the block to the top of
                # the screen, which is the best case any reader can reach.
                offset = b["top"] - top + b["h"]
                if offset > height:
                    bad.append(
                        "%s ends %.1fpx down a %dpx screen" % (part, offset, height))
            self.assertEqual(
                [], bad,
                "at %dx%d the signup does not fit one screen even scrolled to "
                "its own top, so a reader must scroll to find the thing they "
                "were just offered:\n  %s" % (width, height, "\n  ".join(bad)))

    def test_the_field_and_the_button_clear_the_tap_floor(self):
        for width, height in ((375, 812), (414, 896)):
            d = self.rendered(width, height)
            for part in ("field", "submit", "summary"):
                b = d[part]
                self.assertGreaterEqual(
                    b["h"], TAP_MIN - 0.05,
                    "at %dpx the signup's %s is %.1fpx tall, under the %.0fpx "
                    "floor (WCAG 2.5.5). It is hit with a thumb."
                    % (width, part, b["h"], TAP_MIN))

    def test_nothing_bleeds_sideways_at_any_width(self):
        bad = []
        for width in WIDTHS:
            d = self.rendered(width, 812 if width < 768 else 900)
            if d["overflow"] > 0.5:
                bad.append("%dpx: document is %.1fpx wider than the viewport"
                           % (width, d["overflow"]))
            sec = d["section"]
            if sec["left"] < -0.5 or sec["right"] > d["vw"] + 0.5:
                bad.append("%dpx: the signup spans %.1f to %.1f in a %dpx "
                           "viewport" % (width, sec["left"], sec["right"], d["vw"]))
        self.assertEqual([], bad, "the article bleeds sideways:\n  "
                                  + "\n  ".join(bad))


class TheSignupIsReadableOnAnArticle(_Rendered):
    """Rendered contrast, composited, in the browser. The blog is light-only:
    the theme and both database stylesheets pin the article to #fff."""

    def test_every_line_of_it_meets_aa(self):
        bad = []
        for width in (375, 1280):
            d = self.rendered(width, 812 if width < 768 else 900)
            self.assertTrue(d["texts"], "the signup rendered no text at all")
            for t in d["texts"]:
                need = (AA_LARGE if (t["fs"] >= 24 or
                                     (t["fs"] >= 18.66 and int(t["fw"]) >= 700))
                        else AA_NORMAL)
                if t["ratio"] < need - 0.005:
                    bad.append("%dpx %s %r: %s on %s = %.2f:1, need %.1f"
                               % (width, t["tag"], t["text"], t["color"],
                                  t["bg"], t["ratio"], need))
        self.assertEqual(
            [], bad,
            "the signup fails WCAG 1.4.3 on an article:\n  " + "\n  ".join(bad))

    def test_the_panel_edge_is_drawn_at_all(self):
        """THE PANEL, NOT A CONTROL, and the distinction is the repo's own.

        assets/layoffs.css states it where --alt-control-border is defined: "A
        panel edge separates two regions and may be quiet; a control edge tells
        a reader 'this is a thing you operate', and WCAG 1.4.11 asks it for
        3:1". The signup's outer box is a panel. Holding it to the control bar
        would fail --alt-border (1.28:1) and --alt-read-rule (1.26:1) on every
        surface of both products, which is a bar nothing here has ever held.

        What this asserts instead is the thing that actually broke: an
        unresolved var() with no fallback draws NO border, and the box simply
        stops existing as a box.
        """
        for width in (375, 1280):
            d = self.rendered(width, 812 if width < 768 else 900)
            e = d["sectionEdge"]
            self.assertGreater(
                e["width"], 0,
                "at %dpx the signup's outer box has no border width at all, "
                "which is what an unresolved var(--alt-border) with no "
                "fallback looks like on a page that does not load layoffs.css"
                % width)
            self.assertNotEqual(
                e["color"], e["against"],
                "at %dpx the signup's border is exactly the colour behind it "
                "(%s), so the box is invisible" % (width, e["color"]))

    def test_the_controls_have_edges_a_reader_can_see(self):
        """1.4.11 proper, on the two things a reader operates."""
        bad = []
        for width in (375, 1280):
            d = self.rendered(width, 812 if width < 768 else 900)
            e = d["fieldEdge"]
            self.assertGreater(
                e["width"], 0,
                "at %dpx the email field draws no border" % width)
            if e["ratio"] < AA_NONTEXT - 0.005:
                bad.append("%dpx field edge: %s on %s = %.2f:1, need %.1f"
                           % (width, e["color"], e["against"], e["ratio"],
                              AA_NONTEXT))
            f = d["submitFill"]
            if f["ratio"] < AA_NONTEXT - 0.005:
                bad.append("%dpx submit fill: %s on %s = %.2f:1, need %.1f"
                           % (width, f["color"], f["against"], f["ratio"],
                              AA_NONTEXT))
        self.assertEqual(
            [], bad,
            "the signup's controls are not visible AS controls (WCAG "
            "1.4.11):\n  " + "\n  ".join(bad))


class ItDoesNotDependOnTheThirdPartyBox(_Rendered):
    """Both signups are on the page until the owner deletes the WPCode
    snippet. Neither state may be the one it was built for."""

    def test_removing_the_mailjet_box_changes_our_geometry_by_nothing(self):
        with_box = self.rendered(375, 812, with_capture=True)
        without = self.rendered(375, 812, with_capture=False)
        for part in ("heading", "field", "submit", "section"):
            a, b = with_box[part], without[part]
            for prop in ("h", "w"):
                self.assertAlmostEqual(
                    a[prop], b[prop], delta=0.5,
                    msg="the signup's %s %s is %.1fpx with .atr-capture on the "
                        "page and %.1fpx without it, so this block is laid out "
                        "by whether the third-party box is there. The owner is "
                        "deleting it in wp-admin and this repo cannot see it "
                        "happen." % (part, prop, a[prop], b[prop]))


class TheCopyPassesTheHouseStandard(unittest.TestCase):

    def test_no_em_or_en_dash_in_the_lead_sentences(self):
        src = SUBSCRIBE.read_text(encoding="utf-8")
        m = re.search(r"function alt_digest_context_lead\(.*?\n\}", src, re.S)
        self.assertTrue(m, "alt_digest_context_lead() is missing")
        for lead in re.findall(r"=>\s*'([^']*)'", m.group(0)):
            for ch, name in (("—", "em dash"), ("–", "en dash")):
                self.assertNotIn(
                    ch, lead,
                    "the lead sentence %r carries an %s" % (lead, name))

    def test_every_lead_sentence_is_under_the_ceiling(self):
        """30 words, docs/STYLE.md. A copy edit reddened CI four times on
        2026-08-15 by going over it."""
        src = SUBSCRIBE.read_text(encoding="utf-8")
        m = re.search(r"function alt_digest_context_lead\(.*?\n\}", src, re.S)
        for lead in re.findall(r"=>\s*'([^']*)'", m.group(0)):
            words = len(lead.split())
            self.assertLessEqual(
                words, 30,
                "the lead sentence is %d words, over the 30-word ceiling in "
                "docs/STYLE.md: %r" % (words, lead))


if __name__ == "__main__":
    unittest.main()
