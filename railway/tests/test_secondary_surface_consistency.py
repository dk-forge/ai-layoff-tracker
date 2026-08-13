"""THE PAGES NOBODY LOOKS AT ARE THE PAGES A JOURNALIST CHECKS.

WHY THIS FILE EXISTS. Every check in this repository reads the dashboard,
because the dashboard is where the numbers are. The methodology, sources,
press, quotes and publisher pages are the ones an outside reader opens when
they have decided to test whether the numbers can be trusted, and on
2026-08-10 an audit against the live site in two independent browsers found
that those pages were carrying, all at once: prose that did not render in dark
mode, tables a phone could not scroll, the same fact published as two
different numbers, contents entries that landed on a section contradicting
their own label, four names for one destination of which two did not reach it,
and five pages printing their own title twice in two different wordings.

None of it moved a number. All of it moves whether a reader believes the
numbers, which is the same thing one step later.

WHAT THIS FILE REFUSES TO DO. It does not read comments. Both codebases write
long rationale comments that quote the display string verbatim, INCLUDING the
version that was replaced, so a checker that reads comments grades the
commentary: it passes while the page is wrong and fails after a correct fix.
Every string assertion below runs against a comment-stripped copy of the file,
and _StripTests proves the stripper actually strips, on text built to catch
exactly that mistake. The behavioural checks go further and execute the real
layoffs.js in node through jsrun.
"""
import json
import os
import re
import subprocess
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from shutil import which

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = PLUGIN / "assets/layoffs.css"
JS = PLUGIN / "assets/layoffs.js"
TPL = PLUGIN / "templates"
SHORTCODES = PLUGIN / "includes/shortcodes.php"

SITE = "https://asktherecruiter.com/blog/ai-layoff-tracker/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# The secondary surfaces this file owns. The dashboard is deliberately absent:
# it has its own guards, and it is the one page that renders no <h1> of its own.
# The one name the press page has, everywhere it is named. Kept here rather
# than typed into each assertion so a future rename moves in one place and the
# guards below cannot drift apart from each other.
LINK_LABEL = "Press kit and soundbites"

SECONDARY = {
    "methodology": TPL / "page-methodology.php",
    "sources": TPL / "page-sources.php",
    "press": TPL / "page-press.php",
    "ai-quotes": TPL / "page-ai-quotes.php",
    "publisher-tools": TPL / "page-publisher.php",
}


def strip_block_comments(text):
    """Remove /* ... */ comments. Correct for CSS and for the JS/PHP files here."""
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def strip_line_comments(text):
    """Remove // comments that are not inside a quoted string on that line."""
    out = []
    for line in text.split("\n"):
        i, in_s, in_d = 0, False, False
        while i < len(line):
            c = line[i]
            if in_s:
                if c == "'" and line[i - 1:i] != "\\":
                    in_s = False
            elif in_d:
                if c == '"' and line[i - 1:i] != "\\":
                    in_d = False
            elif c == "'":
                in_s = True
            elif c == '"':
                in_d = True
            elif c == "/" and line[i + 1:i + 2] == "/":
                line = line[:i]
                break
            i += 1
        out.append(line)
    return "\n".join(out)


def strip_php_comments(text):
    """Drop <?php /* ... */ ?> blocks, /* */ and // comments from a template."""
    return strip_line_comments(strip_block_comments(text))


def read(path, strip=True):
    t = path.read_text()
    return strip_php_comments(t) if strip else t


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def contrast(fg, bg):
    def lum(c):
        vals = []
        for v in _rgb(c):
            v /= 255.0
            vals.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
    a, b = lum(fg), lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def token(css, block_head, name):
    """Value of a custom property inside the first block whose head matches."""
    i = css.index(block_head)
    blk = css[i:css.index("}", i)]
    m = re.search(r"--%s:\s*([^;]+);" % re.escape(name), blk)
    if not m:
        raise AssertionError("no --%s in the block at %r" % (name, block_head))
    return m.group(1).strip()


class _StripTests(unittest.TestCase):
    """The comment stripper is load bearing, so it is tested before it is trusted."""

    def test_a_string_that_only_appears_in_a_comment_is_gone(self):
        src = "a{color:red}\n/* .alt-wrap p { color: var(--alt-ink) !important } */\nb{}"
        self.assertNotIn("--alt-ink", strip_php_comments(src))

    def test_a_line_comment_quoting_the_fix_is_gone(self):
        src = "// tip = display + ': ' + fmt(jobs)\nvar x = 1;"
        self.assertNotIn("display", strip_php_comments(src))

    def test_a_url_in_a_string_survives(self):
        src = "var u = 'https://example.com/x';"
        self.assertIn("https://example.com/x", strip_php_comments(src))


class DarkThemeProseTests(unittest.TestCase):
    """The tracker's own prose has to render in the theme half its readers get.

    Measured live on 2026-08-10: 186 text nodes on the dashboard and 26 to 133
    on each secondary page rendered between 1.02:1 and 1.28:1 under
    prefers-color-scheme: dark, with no data-theme set - the DEFAULT for a
    dark-OS visitor. The cause is not the tokens, which are correct and are
    applied. It is a site-level rule in the document head declaring
    `.entry-content p{color:#2a2a2a!important}` and the same for h2 and h3,
    which beats a var() every time. So the plugin's own declaration has to win
    on the same terms.
    """

    def setUp(self):
        self.css = read(CSS)

    def test_the_dark_ink_beats_the_site_rule_on_prose_and_headings(self):
        for tag in ("p", "h2", "h3"):
            self.assertIn(
                ':root[data-theme="dark"] .entry-content .alt-wrap %s' % tag, self.css,
                "explicit dark does not restate the colour of a %s inside the wrapper, "
                "so the site rule's #2a2a2a/#1a1a1a keeps winning" % tag)
            self.assertIn(
                ':root:not([data-theme="light"]) .entry-content .alt-wrap %s' % tag, self.css,
                "the OS-preference dark path leaves %s unfixed. That path is the "
                "DEFAULT (Auto), so fixing only the button leaves the common case "
                "broken." % tag)

    def test_the_override_is_important_because_the_rule_it_beats_is(self):
        # Specificity alone cannot win against !important. A rule added here
        # without it renders green in review and changes nothing on the page.
        sel = ':root[data-theme="dark"] .entry-content .alt-wrap p'
        self.assertIn(sel, self.css, "there is no dark prose override to check")
        i = self.css.index(sel)
        block = self.css[i:self.css.index("}", i)]
        self.assertIn("!important", block)
        self.assertIn("var(--alt-ink)", block)

    def test_the_override_cannot_reach_wider_than_the_rule_it_beats(self):
        # It must stay scoped to a content wrapper. A bare `.alt-wrap p` would
        # also repaint the standalone chart embed, which renders outside any
        # .entry-content and is not affected by the site rule at all.
        for line in self.css.split("\n"):
            if ".alt-wrap p," in line or ".alt-wrap p " in line or line.strip().endswith(".alt-wrap p"):
                if "data-theme" in line or "not([data-theme" in line:
                    self.assertTrue(
                        ".entry-content" in line or ".wp-block-post-content" in line,
                        "dark prose override is wider than the rule it exists to "
                        "beat: %r" % line.strip())

    def test_the_dark_ink_actually_clears_aa_against_the_dark_page(self):
        ink = token(self.css, ':root[data-theme="dark"] {', "alt-ink")
        page = token(self.css, ':root[data-theme="dark"] {', "alt-page")
        r = contrast(ink, page)
        self.assertGreaterEqual(round(r, 2), 4.5,
                                "dark body ink is %s on %s = %.2f:1" % (ink, page, r))

    def test_the_rule_under_every_h2_is_not_left_near_white(self):
        # The same site rule declares `border-bottom: 2px solid #eef3ee` on
        # every h2. Measured live at rgb(238,243,238) on rgb(18,20,26), under
        # all 13 headings of /methodology/ at once. A contrast sweep reads text
        # and not borders, which is why this one survived the audit that found
        # the ink.
        self.assertIn("border-bottom-color: var(--alt-border) !important", self.css)
        for scope in (':root[data-theme="dark"]', ':root:not([data-theme="light"])'):
            self.assertIn("%s .entry-content .alt-wrap h2,\n" % scope, self.css)

    def test_the_site_chrome_this_plugin_darkened_gets_its_ink_back(self):
        # The footer band is painted --alt-surface by this stylesheet. Its own
        # text colours are inline style attributes at #20283A / #404858 /
        # #5E6675, which is 1.16:1 on that band. Darkening a band and leaving
        # its text is worse than not darkening it.
        for literal, tok in (("#20283A", "--alt-ink-warm"),
                             ("#404858", "--alt-ink-warm-2"),
                             ("#5E6675", "--alt-muted")):
            self.assertIn('[style*="%s"]' % literal, self.css,
                          "footer text at %s is left on the darkened band" % literal)
            self.assertIn("var(%s)" % tok, self.css)

    def test_each_remapped_literal_is_that_tokens_own_light_value(self):
        # The mapping is only safe because each literal IS the light value of
        # the token it maps to: light cannot change, and dark gets the other
        # end of the same pair. A literal that drifts from its token is a
        # colour decision nobody made.
        light = self.css[self.css.index(":root {"):self.css.index("@media (prefers-color-scheme: dark)")]
        for literal, name in (("#20283a", "alt-ink-warm"),
                              ("#3d4658", "alt-ink-warm-2")):
            m = re.search(r"--%s:\s*([^;]+);" % name, light)
            self.assertEqual(m.group(1).strip().lower(), literal)


class PressTablesScrollTests(unittest.TestCase):
    """Five of seven press tables were unreachable on a phone.

    `overflow: hidden` was added for the wrapper's 10px radius and silently
    replaced the base `.alt-health-table-wrap{overflow-x:auto}`. The identical
    wrapper scrolled correctly on /methodology/ and /sources/, so the product
    shipped two versions of one component and the press kit got the one that
    eats content: at 375px the release-schedule table overflowed by 164px with
    no scrollbar, taking every "Open the report" link out of reach.
    """

    def setUp(self):
        self.css = read(CSS)

    def _decl(self):
        needle = ".alt-press-page .alt-health-table-wrap {"
        i = self.css.index(needle)
        return self.css[i:self.css.index("}", i)]

    def test_the_press_wrapper_scrolls_horizontally(self):
        self.assertIn("overflow-x: auto", self._decl())

    def test_the_press_wrapper_does_not_clip_the_horizontal_axis(self):
        d = self._decl()
        self.assertNotRegex(d, r"overflow:\s*hidden",
                            "a bare `overflow: hidden` clips BOTH axes and takes the "
                            "scrollbar with it")
        self.assertNotRegex(d, r"overflow-x:\s*hidden")

    def test_the_base_wrapper_still_scrolls(self):
        self.assertIn(".alt-health-table-wrap{overflow-x:auto}", self.css)


class OneTitlePerPageTests(unittest.TestCase):
    """Five pages printed their own name twice, in two typefaces, reworded.

    The theme renders the WordPress post title as an <h1> and each plugin
    template renders its own. The two do not agree, because one lives in the
    database and one lives here: "Methodology & Sources" over "Methodology &
    sources", "AI layoffs, in their own words" over "AI layoffs, in the
    employer's own words". On /sources/ they were byte-identical, 199px apart,
    neither subordinate to the other.
    """

    def test_the_theme_title_is_suppressed_where_the_plugin_supplies_one(self):
        css = read(CSS)
        self.assertIn("body:has(.alt-wrap h1) h1.wp-block-post-title", css)
        self.assertIn("body:has(.alt-wrap h1) .entry-title", css)
        i = css.index("body:has(.alt-wrap h1) h1.wp-block-post-title")
        self.assertIn("display: none", css[i:css.index("}", i)])

    def test_the_rule_is_self_limiting_and_leaves_the_dashboard_alone(self):
        # The dashboard renders no <h1> of its own and USES the theme title,
        # demoted to a kicker. If it ever grew one, this rule would hide the
        # kicker rule's target and the page would lose its heading entirely.
        tracker = read(TPL / "page-tracker.php")
        self.assertNotIn("<h1", tracker,
                         "the dashboard now renders an <h1>, which means the "
                         "theme-title suppression rule applies to it too. Either "
                         "drop the template <h1> or narrow the CSS selector.")

    def test_each_secondary_page_supplies_exactly_one_heading_of_its_own(self):
        for name, path in SECONDARY.items():
            n = len(re.findall(r"<h1[\s>]", read(path)))
            self.assertEqual(n, 1, "%s renders %d <h1> elements" % (name, n))


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    return which("php")


class ThemeTitleRemovalTests(unittest.TestCase):
    """The duplicate is removed in PHP, and the real filter is executed here.

    The previous fix was a stylesheet rule hiding the theme's copy. Measured
    live in a browser on 2026-08-13 it works, so a reader sees one heading on
    all six pages - but the HTML that leaves the server still carries two <h1>
    elements whose text disagrees, the rule needs :has(), and a stylesheet that
    fails to load takes the fix with it. So the block is dropped at the source
    and the stylesheet rule stays only as a fallback.

    Everything below RUNS alt_drop_theme_post_title(). Nothing here reads its
    source text, because the defect this guards against is a scope mistake -
    stripping a title on a page that needed it - and a scope mistake is exactly
    what source-reading cannot see.
    """

    SECONDARY_SHORTCODES = {
        "methodology": "alt_methodology",
        "sources": "alt_sources",
        "press": "alt_press_media",
        "ai-quotes": "alt_ai_quotes",
        "publisher-tools": "alt_publisher_tools",
        "ai-tracker-health": "alt_tracker_health",
    }

    def setUp(self):
        if not _php():
            self.skipTest("php not installed")
        src = SHORTCODES.read_text()
        self.fns = ""
        for name in ("alt_own_h1_shortcodes", "alt_page_supplies_its_own_h1",
                     "alt_drop_theme_post_title"):
            needle = "function %s(" % name
            self.assertTrue(needle in src,
                            "%s() is gone from includes/shortcodes.php, so "
                            "nothing removes the theme's second <h1> from the "
                            "HTML that leaves the server" % name)
            body = src[src.index(needle):]
            self.fns += body[:body.index("\n}\n") + 3]

    STUBS = """
function is_singular() { return $GLOBALS['CASE']['singular']; }
function get_post() {
    $p = new stdClass();
    $p->ID = $GLOBALS['CASE']['post_id'];
    $p->post_content = $GLOBALS['CASE']['content'];
    return $p;
}
function get_queried_object_id() { return $GLOBALS['CASE']['queried_id']; }
function has_shortcode($content, $tag) {
    return (bool) preg_match('/\\[' . preg_quote($tag, '/') . '[\\s\\]\\/]/', $content);
}
function add_filter() { return true; }
"""

    def _render(self, content, block="core/post-title", html="<h1>Theme title</h1>",
                singular=True, post_id=7, queried_id=7):
        case = {"content": content, "singular": singular,
                "post_id": post_id, "queried_id": queried_id}
        shim = self.STUBS + self.fns + """
$GLOBALS['CASE'] = json_decode(file_get_contents('php://stdin'), true);
echo json_encode(alt_drop_theme_post_title(
    $GLOBALS['CASE']['html'], array('blockName' => $GLOBALS['CASE']['block'])));
"""
        case["html"], case["block"] = html, block
        proc = subprocess.run([_php(), "-r", shim], input=json.dumps(case),
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_every_page_that_heads_itself_loses_the_themes_copy(self):
        for page, shortcode in self.SECONDARY_SHORTCODES.items():
            with self.subTest(page=page):
                self.assertEqual(
                    self._render("[%s]" % shortcode), "",
                    "/%s/ still ships the theme's post title as a second <h1> "
                    "above its own heading" % page)

    def test_the_dashboard_keeps_the_only_heading_it_has(self):
        # page-tracker.php renders no <h1> at all and uses the theme title,
        # styled down to a kicker. Stripping it there leaves the flagship page
        # with no heading of any level.
        self.assertEqual(self._render("[alt_tracker]"), "<h1>Theme title</h1>")

    def test_the_report_page_keeps_its_title(self):
        # /report/ renders exactly one <h1> today, and it is the theme's.
        self.assertEqual(self._render("[alt_report]"), "<h1>Theme title</h1>")

    def test_an_ordinary_post_is_untouched(self):
        self.assertEqual(self._render("<p>a blog post</p>"), "<h1>Theme title</h1>")

    def test_a_title_inside_a_query_loop_on_our_page_survives(self):
        # A core/post-title rendered for some OTHER post - a related-posts or
        # latest-posts block - is that post's only name in the list.
        self.assertEqual(
            self._render("[alt_sources]", post_id=91, queried_id=7),
            "<h1>Theme title</h1>",
            "a post-title block for a different post than the queried page was "
            "stripped, which blanks a row in a listing")

    def test_no_other_block_is_touched(self):
        for block in ("core/heading", "core/paragraph", "core/post-content"):
            with self.subTest(block=block):
                self.assertEqual(
                    self._render("[alt_sources]", block=block, html="<p>x</p>"),
                    "<p>x</p>")

    def test_a_non_singular_request_is_left_alone(self):
        self.assertEqual(self._render("[alt_sources]", singular=False),
                         "<h1>Theme title</h1>")

    def test_the_list_is_exactly_the_pages_that_head_themselves(self):
        # A template that grows its own <h1> without joining this list ships the
        # duplicate back; a shortcode listed here whose template has no <h1>
        # loses its heading entirely.
        src = read(SHORTCODES)
        listed = set(re.findall(r"'(alt_[a-z_]+)'", re.search(
            r"function alt_own_h1_shortcodes\(\) \{(.*?)\n\}", src, re.S).group(1)))
        self.assertEqual(listed, set(self.SECONDARY_SHORTCODES.values()))
        for page, shortcode in self.SECONDARY_SHORTCODES.items():
            tpl = {"ai-tracker-health": TPL / "page-health.php"}.get(
                page, SECONDARY.get(page))
            self.assertEqual(len(re.findall(r"<h1[\s>]", read(tpl))), 1,
                             "%s is on the strip list but its template does not "
                             "supply exactly one <h1>" % page)

    def test_the_stylesheet_fallback_is_still_there(self):
        # Belt and braces: the PHP filter needs a block theme rendering
        # core/post-title. A classic theme printing .entry-title reaches none of
        # it, and that is the case the CSS rule still covers.
        self.assertIn("body:has(.alt-wrap h1) .entry-title", read(CSS))


class RenderedPageHeadingTests(unittest.TestCase):
    """Asserted against the page a reader is served, not against a template.

    A test over these templates already existed and could not see this defect,
    because a template read in isolation renders one <h1> and is correct. The
    second one is the theme's, and it only exists once the theme has wrapped the
    template. Nothing in this checkout can produce that page: it needs
    WordPress, this theme, and the post titles that live in the site database.
    So this is the honest check, and it reads the live site.

    It reaches the site the way a reader does - bare URL, browser-ish
    User-Agent, no cache buster - and when it cannot reach it the result is
    UNKNOWN, never a pass.
    """

    # The six that supply their own heading, plus the two the fix deliberately
    # leaves alone. /report/ renders one <h1> and it is the theme's.
    PAGES = ("press/", "sources/", "methodology/", "ai-tracker-health/",
             "publisher-tools/", "ai-quotes/", "report/")

    _cache = {}

    def _fetch(self, page):
        if page not in self._cache:
            req = urllib.request.Request(SITE + page, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                self._cache[page] = r.read().decode("utf-8", "replace")
        return self._cache[page]

    def _headings(self, page):
        try:
            html = self._fetch(page)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            self.skipTest("UNKNOWN, NOT passing: could not reach %s (%s)" % (page, e))
        if "<h1" not in html and "wp-block-post-title" not in html:
            self.skipTest("UNKNOWN, NOT passing: %s returned no page body" % page)
        out = []
        for m in re.finditer(r"<h1\b[^>]*>(.*?)</h1>", html, re.S | re.I):
            # The text a reader reads, not the markup around it.
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            out.append(re.sub(r"\s+", " ", text).strip())
        return out

    def test_every_page_a_reader_opens_has_exactly_one_h1(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                got = self._headings(page)
                self.assertEqual(
                    len(got), 1,
                    "%s serves %d <h1> elements to a reader: %r. Two of them "
                    "is the page publishing its own name twice, in two "
                    "wordings, to anything that does not run our stylesheet."
                    % (page, len(got), got))

    def test_the_one_heading_is_not_empty(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                got = self._headings(page)
                self.assertTrue(got and got[0],
                                "%s heads itself with nothing" % page)


class BarRowTooltipTests(unittest.TestCase):
    """renderBarList is executed for real, so a comment cannot pass this.

    Two live defects: the tooltip opened with the row's FILTER VALUE rather
    than its name (so the roles card answered "sales_marketing: 26,089 total"
    when a reader hovered "Sales & marketing"), and it was suppressed entirely
    when the AI figure was zero, so it appeared on four of 22 country rows with
    no rule a reader could infer.
    """

    PREAMBLE = jsrun.BASE_PREAMBLE + """
var CAPTURED = '';
function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
var BARLIST_LIMIT = 24;
var BOX = {
    closest: function () { return null; },
    querySelectorAll: function () { return []; },
    querySelector: function () { return null; },
    set innerHTML(v) { CAPTURED = v; },
    get innerHTML() { return CAPTURED; }
};
var document = { getElementById: function () { return BOX; } };
function titles() {
    var out = [], re = /title="([^"]*)"/g, m;
    while ((m = re.exec(CAPTURED)) !== null) out.push(m[1]);
    return out;
}
"""

    def _titles(self, rows, suffix="undefined"):
        return jsrun.run(
            ["renderBarList"], self.PREAMBLE,
            "(function () { renderBarList('x', %s, 'f', [], null, %s); return titles(); })()"
            % (json.dumps(rows), suffix),
        )

    def test_the_tooltip_names_the_row_the_reader_hovered(self):
        # Roles rows carry the slug at [0] and the label at [3], exactly as
        # renderCharts builds them.
        got = self._titles([["sales_marketing", 26089, 23700, "Sales & marketing"]])
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith("Sales &amp; marketing:"),
                        "tooltip opens with an internal identifier: %r" % got[0])
        self.assertNotIn("sales_marketing", got[0])

    def test_a_row_with_no_ai_attributed_cuts_still_has_a_tooltip(self):
        got = self._titles([
            ["United States", 369821, 71000, "United States"],
            ["Bangladesh", 18000, 0, "Bangladesh"],
            ["Australia", 4415, 120, "Australia"],
        ])
        self.assertEqual(len(got), 3,
                         "the tooltip still comes and goes down the list: %r" % got)
        self.assertIn("Bangladesh: 18,000 total", got[1])
        self.assertIn("none attributed to AI", got[1])

    def test_the_zero_row_claims_no_number_it_did_not_have(self):
        got = self._titles([["Bangladesh", 18000, 0, "Bangladesh"]])
        self.assertEqual(len(got), 1, "the zero-AI row has no tooltip at all")
        self.assertNotIn("(0%)", got[0])
        self.assertNotIn("0 AI-attributed", got[0])

    def test_a_row_whose_ai_figure_exceeds_its_total_claims_neither(self):
        # Data we do not trust: no share, and no "none", because both would be
        # a statement about a number that cannot be right.
        got = self._titles([["Nowhere", 100, 500, "Nowhere"]])
        self.assertEqual(got, [], "an impossible row was given a tooltip: %r" % got)

    def test_cards_measured_in_something_other_than_jobs_carry_no_tooltip(self):
        # "Repeat layoffs" counts rounds; "AI intensity" is a percent. An
        # AI-attributed clause on either would be nonsense.
        self.assertEqual(self._titles([["Acme", 3, 0, "Acme"]], "' rounds'"), [])


class CountryFlagTests(unittest.TestCase):
    """A country with no flag starts a flag's width left of the twenty above it.

    Every name in the list is laid out from the same x, so a missing flag does
    not degrade gracefully - it breaks the left edge of a ranked list mid-list,
    which is the one line the eye tracks down it.
    """

    # Every country the live card is known to draw, read off /facets on
    # 2026-08-10, plus the two canonical strings alt_normalize_country emits
    # that are not the everyday spelling.
    KNOWN = [
        "United States", "India", "United Kingdom", "Germany", "Canada",
        "Bangladesh", "Netherlands", "Australia", "Türkiye", "Romania",
        "Taiwan", "Bosnia and Herzegovina", "Cyprus", "Malta", "Isle of Man",
        "UAE", "Trinidad and Tobago",
    ]

    def test_every_country_the_card_draws_has_a_flag(self):
        src = JS.read_text()
        iso_line = [ln for ln in src.split("\n") if ln.strip().startswith("var COUNTRY_ISO")]
        self.assertEqual(len(iso_line), 1, "COUNTRY_ISO moved or was duplicated")
        got = jsrun.run(
            ["countryFlag"], jsrun.BASE_PREAMBLE + iso_line[0] + "\n",
            "(%s).map(function (n) { return countryFlag(n); })" % json.dumps(self.KNOWN),
        )
        missing = [n for n, f in zip(self.KNOWN, got) if not f.strip()]
        self.assertEqual(missing, [], "no flag for %r, so those rows break the "
                                      "left edge of the list" % missing)

    # ------------------------------------------------------------------
    # Completing the vocabulary fixes the countries we draw today. It does
    # nothing for the next one the data reaches, and the data reaches new
    # countries without being asked. These three execute renderBarList for
    # real and assert the LAYOUT tolerates a flagless row, which is the part
    # the vocabulary check above cannot see.
    # ------------------------------------------------------------------

    ICON_PREAMBLE = jsrun.BASE_PREAMBLE + """
var CAPTURED = '';
function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
var BARLIST_LIMIT = 24;
var BOX = {
    closest: function () { return null; },
    querySelectorAll: function () { return []; },
    querySelector: function () { return null; },
    set innerHTML(v) { CAPTURED = v; },
    get innerHTML() { return CAPTURED; }
};
var document = { getElementById: function () { return BOX; } };
function names() {
    var out = [], re = /<span class="alt-barrow-name">(.*?)<\\/span><span class="alt-barrow-val"/g, m;
    while ((m = re.exec(CAPTURED)) !== null) out.push(m[1]);
    return out;
}
"""

    def _names(self, rows):
        return jsrun.run(
            ["renderBarList"], self.ICON_PREAMBLE,
            "(function () { renderBarList('x', %s, 'f', []); return names(); })()"
            % json.dumps(rows),
        )

    def test_a_row_with_no_flag_still_gets_the_flag_column(self):
        # Row two is a country the emoji vocabulary has not met. Every row of
        # the card must open with the same icon span, or its name starts a
        # flag's width left of the rows above and below it.
        got = self._names([
            ["United States", 369821, 71000, "United States", "\U0001F1FA\U0001F1F8"],
            ["Ruritania", 18000, 0, "Ruritania", ""],
            ["India", 4415, 120, "India", "\U0001F1EE\U0001F1F3"],
        ])
        self.assertEqual(len(got), 3)
        for name, row in zip(got, ["United States", "Ruritania", "India"]):
            self.assertTrue(
                name.startswith('<span class="alt-barrow-icon" aria-hidden="true">'),
                "%r does not open with the reserved icon column, so its name "
                "starts further left than its neighbours" % row)

    def test_the_flagless_row_reserves_the_column_without_inventing_a_flag(self):
        got = self._names([
            ["India", 4415, 120, "India", "\U0001F1EE\U0001F1F3"],
            ["Ruritania", 18000, 0, "Ruritania", ""],
        ])
        self.assertIn(
            '<span class="alt-barrow-icon" aria-hidden="true"></span>Ruritania',
            got[1],
            "the column must be reserved and EMPTY: sparse data gets a label, "
            "never a stand-in glyph")

    def test_a_card_with_no_icons_at_all_grows_no_empty_column(self):
        # Industries, roles, sources and company rows carry no icon. They must
        # not gain a 1.5em indent because the country card needed one.
        got = self._names([
            ["Technology", 369821, 71000, "Technology"],
            ["Retail", 18000, 0, "Retail"],
        ])
        for name in got:
            self.assertNotIn("alt-barrow-icon", name)

    def test_the_reserved_column_has_a_fixed_width_in_the_stylesheet(self):
        # A span with no width reserves nothing, so the JS above would emit a
        # column that still collapses on the flagless row.
        css = strip_block_comments(CSS.read_text())
        rule = re.search(r"\.alt-barrow-icon\s*\{([^}]*)\}", css)
        self.assertIsNotNone(rule, "no .alt-barrow-icon rule; the column the "
                                   "JS emits reserves no space")
        body = rule.group(1)
        self.assertRegex(body, r"width\s*:\s*[0-9.]+\s*(em|px|ch|rem)",
                         "the icon column has no fixed width: %r" % body)
        self.assertRegex(body, r"display\s*:\s*inline-block",
                         "an inline span collapses to zero width when empty")

    def test_the_flag_no_longer_rides_on_the_display_name(self):
        # If the flag goes back onto the label, the tooltip says it twice and
        # the column stops being what reserves the space.
        js = strip_line_comments(strip_block_comments(JS.read_text()))
        self.assertNotIn("countryFlag(e[0]) + e[0]", js)

    def test_multiple_countries_still_gets_the_globe_and_not_a_flag(self):
        src = JS.read_text()
        iso_line = [ln for ln in src.split("\n") if ln.strip().startswith("var COUNTRY_ISO")][0]
        got = jsrun.run(["countryFlag"], jsrun.BASE_PREAMBLE + iso_line + "\n",
                        "countryFlag('Multiple countries')")
        self.assertEqual(got.strip(), "\U0001F310")


class PartialMonthNoteTests(unittest.TestCase):
    """One 435-character paragraph, byte-identical, in three charts.

    The three notes sat within about 950px of scroll and were verified equal on
    the live page. That does not read as three captions, it reads as a template
    that fired three times, and the third copy of a paragraph is where a reader
    stops reading the paragraph at all - including the sentence naming the cuts
    that are filed but not yet in effect.

    The fix is not a shorter duplicate: the three charts plot three different
    quantities, and each note now describes the one it sits under.
    """

    SERIES = [{"month": "2026-08", "verified_jobs": 35548,
               "full": {"verified_jobs": 46631}}]

    def _notes(self):
        info = {"key": "2026-08", "index": 0, "days": 10, "of": 31,
                "charted": 35548, "later": 11083}
        return jsrun.run(
            ["partialNoteText"], jsrun.BASE_PREAMBLE,
            "[partialNoteText(%s), partialNoteText(%s, 'year'), partialNoteText(%s, 'share')]"
            % (json.dumps(info), json.dumps(info), json.dumps(info)),
        )

    def test_the_three_charts_do_not_print_the_same_paragraph(self):
        jobs, year, share = self._notes()
        self.assertNotEqual(jobs, year)
        self.assertNotEqual(jobs, share)
        self.assertNotEqual(year, share)

    def test_every_one_of_them_still_states_the_elapsed_days(self):
        for n in self._notes():
            self.assertIn("10 of 31 days so far", n)

    def test_none_of_them_projects_the_month(self):
        for n in self._notes():
            self.assertIn("not a projection", n)

    def test_the_jobs_chart_note_is_unchanged_to_the_byte(self):
        # It is the chart whose y-axis IS the job count, so it is the one that
        # can name what the point counts and what is still to come.
        jobs = self._notes()[0]
        self.assertIn("This point counts the 35,548 verified job cuts", jobs)
        self.assertIn("A further 11,083 are on notices already filed", jobs)

    def test_the_percent_chart_does_not_quote_a_job_count_as_its_point(self):
        share = self._notes()[2]
        self.assertIn("share for this month is computed on the 35,548", share)
        self.assertNotIn("A further 11,083", share)

    def test_the_default_call_is_the_jobs_note(self):
        # test_published_number_basis.py calls partialNoteText with one
        # argument and asserts both figures appear. A mode that changed the
        # default would break that silently.
        jobs, _, _ = self._notes()
        self.assertIn("35,548", jobs)
        self.assertIn("11,083", jobs)

    def test_no_em_dashes_in_any_of_them(self):
        for n in self._notes():
            self.assertNotIn("\u2014", n)
            self.assertNotIn("\u2013", n)


class EmbedToolbarParityTests(unittest.TestCase):
    """Four icons, four, then three, in one band at the same y.

    Share, CSV and expand are on every chart card. Embed is added only for an
    id in EMBED_OK, so an omission prints a short toolbar next to full ones and
    leaves the reader to guess which card lost a control and why.
    """

    def setUp(self):
        self.js = strip_php_comments(JS.read_text())
        self.php = read(TPL / "page-chart-embed.php")

    def _embed_ok(self):
        m = re.search(r"var EMBED_OK = \{(.*?)\};", self.js, re.S)
        return set(re.findall(r"'([^']+)':", m.group(1)))

    def _route_charts(self):
        m = re.search(r"\$alt_embed_charts = array\((.*?)\n\);", self.php, re.S)
        return set(re.findall(r"'(alt-[a-z0-9\-]+)'\s*=>", m.group(1)))

    def test_the_button_and_the_route_agree(self):
        # A card in only one of them either offers a button that falls back to
        # the trend line, or hides a route that already works.
        self.assertEqual(self._embed_ok(), self._route_charts())

    def test_every_aggregate_driven_bar_card_can_be_embedded(self):
        for cid in ("alt-bars-industries", "alt-bars-states", "alt-bars-countries",
                    "alt-bars-roles", "alt-bars-sourcetypes", "alt-bars-leaders",
                    "alt-bars-repeat", "alt-bars-ai-intensity"):
            self.assertIn(cid, self._embed_ok())

    def test_the_dol_claims_card_stays_out(self):
        # Official jobless-claims data, drawn grey and labelled "context only,
        # not our counts". An embed of it would travel to another site inside
        # this tracker's frame carrying a number this tracker did not collect.
        self.assertNotIn("alt-bars-claims-states", self._embed_ok())

    def test_a_bar_embed_carries_its_basis_sentence(self):
        # barBasisNote() states what the drawn rows cover and where the rest
        # is. It writes by id, and this shell used to ship no element for it,
        # so every bar embed left the page with the caveat stripped off - on
        # the one surface read with none of the dashboard around it.
        # Both ship hidden. setBarBasisNote() clears `hidden` on the one it
        # writes into, and two of these cards have no basis sentence at all -
        # an empty .alt-chart-note still carries its 10px top margin, so an
        # unhidden one hangs dead space off the bottom of exactly the embeds
        # with nothing to say.
        for suffix in ("basis", "note"):
            self.assertIn(
                'id="<?php echo esc_attr($alt_chart); ?>-%s" hidden' % suffix, self.php)

    def test_a_canvas_embed_carries_its_partial_month_sentence(self):
        for note_id in ("alt-trend-partial", "alt-yoy-partial", "alt-ai-share-partial",
                        "alt-chart-reasons-basis"):
            self.assertIn("'%s'" % note_id, self.php,
                          "an embed of that chart can end on an unfinished month "
                          "and say nothing about it")

    def test_the_embed_titles_are_the_dashboard_titles(self):
        tracker = read(TPL / "page-tracker.php")
        for title in ("Layoffs by US state", "Layoffs by country", "By industry",
                      "By data source", "Roles most impacted", "Repeat layoffs",
                      "Largest single job cuts", "AI intensity by industry"):
            self.assertIn(title, self.php)
            self.assertIn(title, tracker,
                          "%r is an embed title with no card of that name" % title)


class ChartTitleGrammarTests(unittest.TestCase):
    """The template and the renderer must not name one card two ways."""

    def test_the_country_card_keeps_the_name_the_template_gave_it(self):
        js = strip_php_comments(JS.read_text())
        tracker = read(TPL / "page-tracker.php")
        self.assertIn("Layoffs by country", tracker)
        i = js.index("var countryTitle = document.getElementById('alt-country-chart-title')")
        block = js[i:i + 700]
        self.assertNotIn("'By country <span", block,
                         "the renderer still renames the card a beat after load, "
                         "leaving a bare fragment beside 'Layoffs by US state'")
        self.assertEqual(block.count("Layoffs by country"), 2)


class TableOfContentsTests(unittest.TestCase):
    """A contents entry is a promise about what is down there.

    The entry "Global authorities" on /sources/ landed on the heading "Why most
    countries appear through news, not a registry" - it advertised a directory
    of official authorities and delivered the explanation that for most
    countries no such registry is read. That is the one mismatch that changes
    what a reader believes before they read.
    """

    def _toc_and_headings(self, path, nav_class):
        src = read(path)
        nav = re.search(r'<nav class="%s".*?</nav>' % nav_class, src, re.S).group(0)
        toc = re.findall(r'<a href="#([a-z0-9\-]+)">(.*?)</a>', nav, re.S)
        heads = dict(re.findall(r'<h2 id="([a-z0-9\-]+)">(.*?)</h2>', src, re.S))
        heads.update(dict(re.findall(
            r'<section class="alt-method-sec" id="([a-z0-9\-]+)">\s*<h2>(.*?)</h2>', src, re.S)))
        clean = lambda s: re.sub(r"<[^>]+>|<\?php.*?\?>", "", s, flags=re.S).strip()
        return [(a, clean(b)) for a, b in toc], {k: clean(v) for k, v in heads.items()}

    def test_every_methodology_entry_is_its_headings_own_words(self):
        toc, heads = self._toc_and_headings(TPL / "page-methodology.php", "alt-method-toc")
        self.assertEqual(len(toc), 13)
        for anchor, label in toc:
            self.assertIn(anchor, heads, "%r points at no section" % label)
            self.assertEqual(label, heads[anchor],
                             "the contents say %r and the section says %r"
                             % (label, heads[anchor]))

    def test_the_methodology_contents_are_in_document_order(self):
        src = read(TPL / "page-methodology.php")
        toc, _ = self._toc_and_headings(TPL / "page-methodology.php", "alt-method-toc")
        pos = [src.index('id="%s"' % a, src.index("</nav>")) for a, _ in toc]
        self.assertEqual(pos, sorted(pos),
                         "reading down the contents walks back up the page")

    def test_the_sources_entry_does_not_promise_the_opposite_of_its_section(self):
        toc, heads = self._toc_and_headings(TPL / "page-sources.php", "alt-src-toc")
        got = dict(toc)["alt-src-global"]
        self.assertNotEqual(got, "Global authorities")
        self.assertTrue(heads["alt-src-global"].lower().startswith(got.lower()),
                        "contents entry %r does not open the heading %r"
                        % (got, heads["alt-src-global"]))


class SiblingNavigationTests(unittest.TestCase):
    """Four names for one destination, and two of them did not reach it."""

    METHODOLOGY = "/ai-layoff-tracker/methodology/"

    def test_no_link_labelled_as_the_methodology_lands_on_the_dashboard(self):
        for path in list(SECONDARY.values()) + [TPL / "page-facet.php",
                                                TPL / "page-company-directory.php"]:
            src = read(path)
            for href, label in re.findall(r"<a href=\"(.*?)\"[^>]*>(.*?)</a>", src, re.S):
                flat = re.sub(r"<[^>]+>|<\?php.*?\?>", "", label, flags=re.S).strip().lower()
                if href.startswith("#"):
                    continue  # an anchor within the same page reaches itself
                if flat in ("methodology", "how the ai tag works", "tracker methodology",
                            "full methodology &rarr;", "how we count"):
                    self.assertIn("methodology", href,
                                  "%s labels a link %r and sends it to %r"
                                  % (path.name, flat, href))

    def test_every_secondary_page_offers_the_way_back_to_how_we_count(self):
        for name, path in SECONDARY.items():
            if name == "methodology":
                continue
            self.assertIn(self.METHODOLOGY, read(path),
                          "%s has no route to the methodology page" % name)

    def test_the_press_page_is_called_one_thing(self):
        # It was "Press kit" from /methodology/ and /report/, "Press & media"
        # from the dashboard and /publisher-tools/, and titled itself "Press &
        # Media Kit".
        for path in list(SECONDARY.values()) + [TPL / "page-report.php",
                                                TPL / "page-tracker.php"]:
            self.assertNotIn(">Press kit<", read(path),
                             "%s still calls the press page by a third name" % path.name)

    def test_the_press_page_calls_itself_what_the_links_call_it(self):
        """The page's own heading has to be the name the links use.

        Forbidding a third name was not enough: every link said "Press kit and
        soundbites" while the page it opened was headed "Press & Media Kit", so
        a reader who clicked to find the soundbites landed on a page that
        appeared to be something else. The owner reported exactly that.
        """
        press = read(TPL / "page-press.php")
        self.assertIn("<h1>%s</h1>" % LINK_LABEL, press,
                      "the press page heads itself with something other than "
                      "%r, which is what every link to it says" % LINK_LABEL)
        for path in list(SECONDARY.values()) + [TPL / "page-report.php",
                                                TPL / "page-tracker.php"]:
            body = read(path)
            if "ai-layoff-tracker/press" not in body:
                continue
            self.assertIn(LINK_LABEL, body,
                          "%s links to the press page by some other name than "
                          "%r" % (path.name, LINK_LABEL))


class WarnCoverageBasisTests(unittest.TestCase):
    """The same fact was published as two different numbers, one page apart.

    /sources/ counted the registries the importer READS (47 states + DC).
    The dashboard ribbon and /methodology/ count the states PRESENT IN THE DATA
    (46 US states + DC), through alt_warn_states_phrase(). Both are right and
    neither said which it was, so a journalist checking the WARN claim across
    two of our own pages found two answers and no basis.
    """

    def test_the_sources_page_names_both_bases(self):
        src = read(TPL / "page-sources.php")
        self.assertIn("alt_warn_states_phrase", src,
                      "/sources/ still publishes only its own count, so the two "
                      "numbers on the tracker stay unreconciled")
        self.assertIn("Two counts, and they answer different questions", src)

    def test_the_registry_count_says_it_is_the_registries_we_read(self):
        src = read(TPL / "page-sources.php")
        self.assertIn("US state WARN registries we read", src)

    def test_neither_count_is_hardcoded(self):
        src = read(TPL / "page-sources.php")
        for n in ("46", "47", "48"):
            self.assertNotRegex(src, r"\b%s (US )?states?\b" % n,
                                "a typed state count is how the two numbers "
                                "disagreed in the first place")

    def test_the_one_owner_of_the_data_side_count_is_unchanged(self):
        # alt_warn_states_phrase() is quoted inline in sentences on three
        # surfaces. Re-wording its return value to carry the basis would
        # garble all of them, so the basis is stated where the contradiction
        # was authored instead.
        php = read(PLUGIN / "ai-layoff-tracker.php")
        self.assertIn("return number_format_i18n((int) $c['us_states']) . ' US states and DC';", php)


class PressDateFormatTests(unittest.TestCase):
    """Three date conventions and two freshness stamps on the press kit."""

    def setUp(self):
        self.src = read(TPL / "page-press.php")

    def test_the_page_uses_one_date_format(self):
        fmts = set(re.findall(r"gmdate\('([a-zA-Z, :]+)'", self.src))
        display = {f for f in fmts if any(c in f for c in "FMjD") and "-" not in f}
        self.assertEqual(
            display, {"M j, Y", "F Y"},
            "the press page prints more than one display date convention: %r. "
            "'F Y' is a month name with no day and is a different thing from a "
            "date; anything else is a second rendering of the same one." % sorted(display))

    def test_the_two_freshness_stamps_say_which_is_which(self):
        self.assertIn("That is a different stamp from", self.src)
        self.assertIn("use the date you accessed the tracker", self.src)


if __name__ == "__main__":
    unittest.main()
