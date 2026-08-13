"""THE FILED BASIS IS THE DEFAULT, AND EVERY TOTAL SAYS WHICH QUESTION IT ANSWERS.

WHY THIS CHANGE EXISTS. Layoffs are reported nearly everywhere on the FILING
date. On that basis our US July 2026 figure sits within about one percent of
the independent national estimate for the same month. On the effective-date
basis, which was the default, the same month reads roughly double, so a reader
arriving with a number in their head met a figure they could not reconcile and
a paragraph of explanation standing between them and the data. Defaulting to
the basis everybody else reports on turns the differentiator from "a different
number that needs explaining" into "the same number, with a filing behind every
row".

WHAT THAT BREAKS IF IT IS DONE CARELESSLY, which is what these tests hold:

  1. A DEFAULT LIVES IN FOUR PLACES. layoffs.js (DATE_BASIS), the segmented
     switch's markup (which option carries alt-datebasis-on), the server
     bootstrap (the date_basis the inlined first-paint payload was computed
     on), and the hero's own basis label. Any one of them left behind publishes
     a number counted one way under a label naming the other. That is the exact
     defect this change was made to remove.

  2. DEEP LINKS. While the default was 'effective', a link saying
     date_basis=effective was indistinguishable from a link saying nothing, so
     reading only 'notice' back off the URL happened to work. It does not work
     now: an effective-basis share has to be honoured explicitly or it silently
     becomes a filed-basis view showing a different number under the same URL.

  3. THREE TOTALS THAT READ AS ONE CLAIM. The hero, the at-a-glance board's YTD
     column and the cite line were live together at 484,427, 335,637 and 24,754
     with nothing on screen saying which was which. Each now states its
     geography, its period and its basis, or says plainly that it answers a
     different question.

  4. A CAPTION THAT NAMES BOTH BASES. The lead tile read "Filed or reported,
     counted on the day each cut takes effect", which is wrong on whichever
     basis is live. One basis per caption, and it changes with the toggle.

HOW THESE CHECK. Where a behaviour can be RUN it is run: jsrun lifts the real
function bodies out of layoffs.js into node, and the PHP helper is executed
through the php binary. Where a check has to read source, it strips comments
first and says so, because two checks in this repo have passed against
defective code by matching a comment that described a call instead of the call.
39 of the 42 tests here were confirmed to fail on the pre-change tree (git
a191e92), run as a file, with comments stripped before matching. The three that
pass there are REGRESSION BARS and are named here rather than left to look like
proof of this change:

  * test_the_threshold_was_not_lowered_to_fill_the_card. The 1,000-cut floor on
    the AI intensity card already existed. This holds it against a later edit
    that reaches for it to fill whitespace.
  * test_the_filed_basis_is_written_explicitly. The pre-change code already
    wrote date_basis=notice when the toggle was on notice. Its twin,
    test_the_effective_basis_is_written_explicitly_too, is the one that goes
    red, and it is the one that matters under the new default.
  * test_it_is_not_inside_a_disclosure. The hero had no <details> before and
    must not grow one now.

Two tests in the first draft of this file passed against the defective tree for
the wrong reason and were rewritten before it landed: one read the caption
through a helper that strips `<?php ... ?>` blocks, which is where the caption
is built, so it matched nothing; the other compared this file's own EXPECTED
constant with itself.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
JS = (PLUGIN / "assets/layoffs.js").read_text()
CSS = (PLUGIN / "assets/layoffs.css").read_text()
DB_PHP = (PLUGIN / "includes/db.php").read_text()
TRACKER_TPL = (PLUGIN / "templates/page-tracker.php").read_text()

PHP = shutil.which("php")


def strip_js_comments(text):
    """Block and line comments out of JS, so an assertion cannot match prose.

    This file's rationale comments quote the strings they are about, including
    the versions that were REPLACED, so a checker reading comments would grade
    the commentary: it would pass while the page was wrong and fail after a
    correct fix. Strings can contain '//' (a URL), so line-comment removal only
    fires on a '//' that starts a line after optional whitespace.
    """
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


def strip_php_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


def visible_copy(text):
    """PHP/HTML with comments and tags removed: what a reader actually sees."""
    text = re.sub(r"<\?php.*?\?>", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return re.sub(r"<[^>]+>", " ", text)


JS_NC = strip_js_comments(JS)
TPL_NC = strip_php_comments(TRACKER_TPL)
DB_NC = strip_php_comments(DB_PHP)


# --------------------------------------------------------------------------
# 1. The default, in all four places that hold it.
# --------------------------------------------------------------------------

class TheDefaultIsTheFiledBasis(unittest.TestCase):

    def test_the_js_closure_default_is_notice(self):
        """Source check with comments stripped: a `var` initialiser is not a
        function, so there is no body to lift into node."""
        m = re.search(r"var\s+DATE_BASIS\s*=\s*'([a-z]+)'", JS_NC)
        self.assertTrue(m, "DATE_BASIS is gone from layoffs.js")
        self.assertEqual(
            m.group(1), "notice",
            "the front-end default basis is %r; the filed/notice basis is the "
            "default this page ships on" % m.group(1))

    def test_the_switch_marks_the_filed_option_as_active(self):
        """The segmented switch is buttons, not a form field, so its default is
        which button carries alt-datebasis-on and aria-pressed=true. A closure
        default the markup contradicts renders a page whose control says it is
        showing the other basis."""
        opts = re.findall(
            r'<button[^>]*class="alt-datebasis-opt([^"]*)"[^>]*data-basis="([a-z]+)"[^>]*aria-pressed="(true|false)"',
            TPL_NC)
        self.assertEqual(len(opts), 2, "expected exactly two basis options, got %r" % (opts,))
        on = [(cls, basis, pressed) for cls, basis, pressed in opts if "alt-datebasis-on" in cls]
        self.assertEqual(len(on), 1, "exactly one option may be marked active: %r" % (opts,))
        self.assertEqual(on[0][1], "notice",
                         "the active option is %r, not the filed basis" % on[0][1])
        self.assertEqual(on[0][2], "true", "the active option is not aria-pressed")
        off = [o for o in opts if "alt-datebasis-on" not in o[0]]
        self.assertEqual(off[0][2], "false", "the inactive option claims aria-pressed=true")

    def test_the_filed_option_is_listed_first(self):
        """A segmented switch is read left to right. The default sitting second
        teaches a reader the page is showing the other one."""
        self.assertLess(
            TPL_NC.index('data-basis="notice"'), TPL_NC.index('data-basis="effective"'),
            "the effective option precedes the filed default in the switch")

    def test_the_server_bootstrap_is_computed_on_the_filed_basis(self):
        """The bootstrap IS the first paint, and it is what a reader without JS
        and every crawler is served. Computed on the other basis it publishes a
        figure counted one way under a label naming the other, then swaps the
        number when JS runs."""
        m = re.search(r"\$aggregate_params\s*=\s*array\((.*?)\);", DB_NC, re.S)
        self.assertTrue(m, "alt_tracker_bootstrap_payload no longer builds $aggregate_params")
        self.assertRegex(
            m.group(1), r"'date_basis'\s*=>\s*'notice'",
            "the inlined aggregate is not computed on the filed basis: %s" % m.group(1).strip())
        q = re.search(r"\$query_params\s*=\s*array\((.*?)\);", DB_NC, re.S)
        self.assertTrue(q, "alt_tracker_bootstrap_payload no longer builds $query_params")
        self.assertRegex(
            q.group(1), r"'date_basis'\s*=>\s*'notice'",
            "the inlined results page is not fetched on the filed basis")

    def test_the_effective_basis_is_not_removed(self):
        """One click away, never gone. The effective date answers a real
        question and the whole page must still recount on it."""
        self.assertIn('data-basis="effective"', TPL_NC,
                      "the effective-date option was removed rather than demoted")
        self.assertIn("effective", strip_js_comments(jsrun.extract("setDateBasis")),
                      "setDateBasis cannot select the effective basis")


# --------------------------------------------------------------------------
# 2. Deep links. Run, not read.
# --------------------------------------------------------------------------

PARAMS_PREAMBLE = """
var CONTROLS = {};
function readControl(id) { return CONTROLS[id] === undefined ? '' : CONTROLS[id]; }
function multiParam(id) {
  var v = readControl(id);
  if (Array.isArray(v)) return v.length ? v.join(',') : '';
  return v || '';
}
var DATE_BASIS = 'notice';
"""


class DeepLinksKeepTheirBasis(unittest.TestCase):
    """currentParams() is the one place the basis reaches both the API request
    and (through syncUrlFromFilters) the address bar. These run the real body."""

    def _params(self, basis):
        return jsrun.run(
            ["currentParams"],
            PARAMS_PREAMBLE + ("DATE_BASIS = %r;\n" % basis).replace("'", "'"),
            "currentParams()")

    def test_the_filed_basis_is_written_explicitly(self):
        """The server's own default column is layoff_date, so a request that
        omits date_basis is counted on the EFFECTIVE basis no matter what the
        UI says. The filed default therefore has to be sent, every time."""
        self.assertEqual(self._params("notice").get("date_basis"), "notice")

    def test_the_effective_basis_is_written_explicitly_too(self):
        """This is the one that made a share URL mean "whatever the default is
        on the day you open it". While the default was effective, omitting the
        param was equivalent to naming it. The default has now changed once, so
        every basis is named."""
        self.assertEqual(self._params("effective").get("date_basis"), "effective")

    def test_an_inbound_effective_link_is_read_back(self):
        """Source check on the restore path, comments stripped: it touches the
        DOM and the URL, so there is no body to run without a browser. The
        pre-change code read ONLY 'notice', which under the new default makes
        every effective-basis share silently become a filed-basis view."""
        restore = re.search(r"date_basis.{0,400}", JS_NC, re.S)
        self.assertTrue(restore)
        window = JS_NC[JS_NC.index("query.get('date_basis')") - 400:]
        window = window[:900]
        self.assertIn("'effective'", window,
                      "the URL restore path never compares against 'effective', so a "
                      "link naming the effective basis is ignored")
        self.assertIn("setDateBasis(", window,
                      "the URL restore path does not go through setDateBasis, so the "
                      "switch and the captions can disagree with the closure state")

    def test_the_clean_url_baseline_carries_the_default_basis(self):
        """currentParams() always writes date_basis now, so the baseline the
        default view is compared against has to carry it too. Otherwise every
        unfiltered load rewrites the address bar with a querystring that
        changes nothing."""
        m = re.search(r"var\s+URL_BASELINE\s*=\s*([^;]+);", JS_NC)
        self.assertTrue(m, "URL_BASELINE is gone")
        self.assertIn("date_basis=notice", m.group(1),
                      "the default view no longer produces a clean URL: %s" % m.group(1))


# --------------------------------------------------------------------------
# 3. One basis per caption, and it changes with the toggle.
# --------------------------------------------------------------------------

class EveryCaptionNamesOneBasis(unittest.TestCase):

    BOTH_BASES = re.compile(
        r"[Ff]iled or reported,\s*counted on the day each cut takes effect")

    def test_the_lead_tile_caption_does_not_name_both_bases(self):
        """Read off the COMMENT-STRIPPED TEMPLATE, not off visible_copy().

        The first version of this test used visible_copy(), which strips
        `<?php ... ?>` blocks. The caption is built inside one of those blocks,
        so the check saw nothing, found nothing, and passed against the
        defective tree. That is the exact failure mode this suite was written
        to stop, caught here by running the new tests against the pre-change
        tree and noticing this one did not go red.
        """
        self.assertNotRegex(
            TPL_NC, self.BOTH_BASES,
            "the Verified job cuts tile names the filing basis and the effective "
            "basis in one sentence, so it is wrong on whichever one is live")
        self.assertNotRegex(JS_NC, self.BOTH_BASES)

    def test_both_bases_have_their_own_tile_caption(self):
        """BASIS_COPY is the one table every basis word is written from. Two
        entries, each naming its own basis and not the other."""
        self.assertIn("BASIS_COPY", JS_NC, "the basis copy table is gone")
        block = JS_NC[JS_NC.index("var BASIS_COPY"):]
        block = block[:block.index("function basisCopy")]
        self.assertIn("notice:", block)
        self.assertIn("effective:", block)
        for key in ("headline", "tile", "toggleTitle"):
            self.assertEqual(
                block.count(key + ":"), 2,
                "%r is not defined for both bases in BASIS_COPY" % key)

    def test_the_tile_caption_is_rewritten_when_the_basis_changes(self):
        """The caption has to MOVE with the toggle, not just be right on load.
        setDateBasis calls renderBasisCopy, and renderBasisCopy writes the
        tile body element by id."""
        self.assertIn("renderBasisCopy()", strip_js_comments(jsrun.extract("setDateBasis")),
                      "setDateBasis does not refresh the basis captions")
        body = strip_js_comments(jsrun.extract("renderBasisCopy"))
        self.assertIn("alt-stat-total-i-body", body,
                      "renderBasisCopy does not rewrite the lead tile's caption")
        self.assertIn("alt-hero-total-basis", body,
                      "renderBasisCopy does not rewrite the hero's basis label")
        # The id is passed to the $alt_tile_i closure, which emits it, so the
        # template holds the string rather than the rendered attribute.
        self.assertIn("'alt-stat-total-i-body'", TPL_NC,
                      "the lead tile's caption has no id for renderBasisCopy to write")

    def test_the_server_default_caption_matches_the_js_default_caption(self):
        """The server prints the filed wording and JS holds the same string. If
        they drift, the first paint says one thing and the first repaint says
        another, with no number change to explain it."""
        m = re.search(r"\$alt_hero_basis\s*=\s*'([^']+)'", TPL_NC)
        self.assertTrue(m, "the server no longer names a default basis")
        js = re.search(r"notice:\s*\{[^}]*?headline:\s*'([^']+)'", JS_NC, re.S)
        self.assertTrue(js, "BASIS_COPY.notice.headline is gone")
        self.assertEqual(m.group(1), js.group(1),
                         "server default basis label %r != JS default %r"
                         % (m.group(1), js.group(1)))


# --------------------------------------------------------------------------
# 4. Three totals, three self-descriptions.
# --------------------------------------------------------------------------

class EveryTotalSaysWhichQuestionItAnswers(unittest.TestCase):

    def test_the_hero_label_states_geography_period_and_basis(self):
        """The hero is the figure a journalist compares against an outside
        estimate inside ten seconds. A correct number whose basis is unstated
        is read as a contradiction of whatever it is set beside, at the same
        cost as a wrong one."""
        block = [l for l in TPL_NC.splitlines() if 'class="alt-hero-figure-label"' in l]
        self.assertEqual(len(block), 1, "the hero figure's label is gone or duplicated")
        block = block[0]
        for wanted in ("alt-hero-total-geo", "alt-hero-total-period", "alt-hero-total-basis"):
            self.assertIn(wanted, block,
                          "the hero figure's label does not state %s" % wanted)

    def test_the_cite_line_states_geography_period_and_basis(self):
        """It was "N verified job cuts recorded for <year> so far": no
        geography, no basis, and a period that reads like the hero's. It was
        also the SMALLEST of the three live totals, so a screenshot of it
        captioned as our figure was a story we handed out."""
        line = [l for l in TPL_NC.splitlines() if 'id="alt-citeline-total"' in l]
        self.assertTrue(line, "the cite line is gone")
        for wanted in ("alt-citeline-geo", "alt-citeline-period", "alt-citeline-basis"):
            self.assertIn(wanted, line[0],
                          "the cite line does not state %s" % wanted)

    def test_the_cite_line_says_its_number_is_the_part_already_in_effect(self):
        """Its number is to-date, which is a different question from the hero's
        whole-window total. Saying so is the whole point."""
        line = [l for l in TPL_NC.splitlines() if 'id="alt-citeline-total"' in l][0]
        self.assertIn("taken effect", line,
                      "the cite line does not say that its figure is the part that "
                      "has already taken effect: %s" % line.strip())

    def test_the_board_no_longer_answers_a_different_question(self):
        """THE FOOTNOTE WAS NOT ENOUGH, so the number moved instead.

        The at-a-glance board counted on the EFFECTIVE date and followed the
        region tabs only. That was harmless while the headline did too, and
        under the filed default it became a second total on a second basis
        inches from the first. The answer used to be a footnote naming the
        difference in words. The person who commissioned the page read the
        footnote and still could not reconcile the two figures, which is the
        evidence that disclosure was the wrong instrument: the board now counts
        on the page's own basis and the server-rendered line says they agree.

        The "different questions" wording is not gone. It moved to the case it
        is actually true in, the reader who toggles the page to the effective
        basis, and layoffs.js paints it there (see the test below)."""
        foot = TPL_NC[TPL_NC.index("alt-sb-foot"):]
        foot = foot[:foot.index("</ul>")]
        self.assertIn(
            "by filing date", foot,
            "the board footnote does not name the basis it counts on")
        self.assertIn(
            "the same basis as the headline figure above", foot,
            "the served board footnote does not tell the reader that the "
            "board and the headline now count the same way, which is the "
            "whole point of moving it")
        self.assertNotIn(
            "not meant to match", foot,
            "the served board still tells a reader the two totals answer "
            "different questions, which is now false: both count by filing "
            "date on the default view")

    def test_the_board_footnote_follows_the_toggle(self):
        """The inversion, after the board moved onto the page's basis.

        It used to be: the board is on the effective basis, so a reader who
        toggles the page to effective makes the two agree. It is now the other
        way round. The board is pinned to the page DEFAULT (filing), so the
        default view agrees and a reader who toggles to the effective basis
        moves the headline without moving the board. The confusing case used to
        be the one nobody chose; it is now the one somebody did.

        Pinned rather than wired to DATE_BASIS on purpose: following the toggle
        would refetch six period queries on every switch, and this line is the
        only thing about the board that a basis change has to touch.

        The two sentences moved out of updateNarrative() into boardBasisNote()
        in 2.20.12, which is what let renderBasisCopy() rewrite the line without
        refetching four periods. Carrying both and picking by DATE_BASIS is the
        invariant, not which function holds the literal, so this now reads the
        helper AND holds the wiring that made the move worth doing: the paint
        calls it, and the single basis writer calls it too."""
        note = strip_js_comments(jsrun.extract("boardBasisNote"))
        self.assertIn("DATE_BASIS === 'effective'", note,
                      "the board footnote does not vary with the active basis")
        # WHICH branch carries which sentence, not merely that both strings are
        # somewhere in the helper. Before the board moved onto the page's
        # basis the pairing was the other way round, and a helper holding both
        # sentences passes a mere "contains" check under either wiring: that is
        # a test that cannot see the change it is here to hold.
        eff, _, dflt = note.partition(":")
        self.assertIn(
            "not meant to match", eff,
            "the EFFECTIVE branch of the board footnote does not say the two "
            "totals answer different questions. That is now the only case "
            "where they do: the reader moved the headline off the basis the "
            "board counts on.")
        self.assertIn(
            "the same basis as the headline figure above", dflt,
            "the DEFAULT branch of the board footnote does not say the board "
            "and the headline agree. They do now, and saying otherwise on the "
            "served page is the defect inverted rather than fixed.")
        self.assertNotIn(
            "the same basis as the headline figure above", eff,
            "the board footnote claims it matches the headline on the basis "
            "the reader toggled AWAY from it")
        self.assertIn("by filing date", note,
                      "neither branch of the board footnote names the basis "
                      "the board actually counts on")
        nar = strip_js_comments(jsrun.extract("updateNarrative"))
        self.assertIn("boardBasisNote()", nar,
                      "the board no longer paints its basis line from the one helper")
        self.assertIn("boardBasisNote()", strip_js_comments(jsrun.extract("renderBasisCopy")),
                      "a basis switch no longer rewrites the board's basis line, so the "
                      "board can sit saying the two totals are not meant to match at the "
                      "moment they do")


# --------------------------------------------------------------------------
# 4b. The FOURTH total, the one inside the structured data.
#
# Section 4 pinned the three totals a reader can see. There is a fourth that a
# reader mostly cannot: alt_live_numbers() feeds alt_faq_items(), which is
# rendered as visible FAQ copy AND emitted as FAQPage JSON-LD, and it is
# hardcoded YEAR(layoff_date) while the page around it defaults to the filing
# basis. Live on 2026-08-12 that was 479,410 in the JSON-LD against 445,869 in
# the cite line a few pixels below, 33,541 apart, both worded "so far in 2026
# ... worldwide". Structured data is quoted with none of the page around it, so
# an unlabelled basis there is worse than an unlabelled basis on screen.
#
# 2.20.12 kept the effective basis (reasons in alt_live_numbers()) and labelled
# it. These tests do NOT pin that choice: they pin the invariant that survives
# either choice, which is that the words and the SQL agree. The label is
# DERIVED from the column the query actually windows on, so switching
# alt_live_numbers() to the page basis passes here only if the copy switches
# with it. Source checks, because the query needs a database and the FAQ needs
# WordPress; comments are stripped first, since a comment describing this is
# exactly what was wrong before.
#
# Three of these five were confirmed red on the pre-change tree (ab4dea1), run
# as a file. The other two are REGRESSION BARS, named here rather than left to
# look like proof of this change:
#
#   * test_the_basis_words_are_the_pages_own_words. Vacuous before the copy
#     named a basis at all. It holds the wording against a later edit that
#     paraphrases one label and reintroduces two names for one basis.
#   * test_the_meta_description_rides_the_same_numbers. The description already
#     read alt_live_numbers(). This stops it growing its own query, which would
#     give the SERP snippet a third basis that nothing on the page labels.
# --------------------------------------------------------------------------

PLUGIN_PHP = (PLUGIN / "ai-layoff-tracker.php").read_text()
PLUGIN_NC = strip_php_comments(PLUGIN_PHP)


def _plugin_fn(name):
    """Body of one top-level `function <name>(` in the plugin file, brace-matched."""
    needle = "function %s(" % name
    start = PLUGIN_NC.find(needle)
    assert start != -1, "ai-layoff-tracker.php has no `%s`" % needle
    i = PLUGIN_NC.index("{", start)
    depth, j = 0, i
    while j < len(PLUGIN_NC):
        if PLUGIN_NC[j] == "{":
            depth += 1
        elif PLUGIN_NC[j] == "}":
            depth -= 1
            if depth == 0:
                return PLUGIN_NC[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


def _js_basis_headline(basis):
    m = re.search(r"%s:\s*\{[^}]*?headline:\s*'([^']+)'" % basis, JS_NC, re.S)
    assert m, "BASIS_COPY.%s.headline is gone" % basis
    return m.group(1)


class TheStructuredDataTotalNamesItsOwnBasis(unittest.TestCase):

    # The one place this file writes the mapping down: a date column, and the
    # words the rest of the page uses for the basis that column IS. Both
    # strings are read out of layoffs.js rather than typed here, so this cannot
    # become a constant compared with itself.
    def _label_for_column(self, col):
        return {
            "layoff_date": _js_basis_headline("effective"),
            "COALESCE(announcement_date, layoff_date)": _js_basis_headline("notice"),
        }.get(" ".join(col.split()))

    def _faq_basis_column(self):
        """The column alt_live_numbers() windows its year on."""
        body = _plugin_fn("alt_live_numbers")
        m = re.search(r"AND YEAR\(([^)]+(?:\([^)]*\))?[^)]*)\)\s*=\s*%d", body)
        self.assertIsNotNone(
            m, "alt_live_numbers() no longer windows on YEAR(<column>); if it now takes "
               "a basis from somewhere else, teach this test where, because the FAQ copy "
               "names a basis in words and the two have to be checked against each other")
        return m.group(1).strip()

    def _year_answer(self):
        """The 'How many layoffs ... so far?' entry of alt_faq_items()."""
        body = _plugin_fn("alt_faq_items")
        i = body.find("How many layoffs have there been in")
        self.assertNotEqual(i, -1, "the year question is gone from the FAQ")
        j = body.find("array('", i)
        return body[i:j if j != -1 else len(body)]

    def test_the_answer_names_the_basis_its_own_query_counts_on(self):
        """This is the whole defect. The number went out inside FAQPage JSON-LD
        with no basis on it, next to a differently-based number that did have
        one, under identical wording."""
        col = self._faq_basis_column()
        label = self._label_for_column(col)
        self.assertIsNotNone(
            label, "alt_live_numbers() windows on %r, which is neither basis the page "
                   "has words for. Add the wording to BASIS_COPY before publishing a "
                   "third basis in structured data." % col)
        self.assertIn(
            label, self._year_answer(),
            "the FAQ answer is counted on %r but never says so. It says %r, and it "
            "ships as FAQPage JSON-LD, where a search engine quotes it with none of "
            "the page around it." % (label, self._year_answer()[:400]))

    def test_the_answer_says_the_page_answers_a_different_question(self):
        """Required only while the two bases actually differ. If the FAQ is ever
        moved onto the page's own basis, this flips and demands the copy stop
        claiming a difference that no longer exists."""
        faq_label = self._label_for_column(self._faq_basis_column())
        page = re.search(r"\$alt_hero_basis\s*=\s*'([^']+)'", TPL_NC)
        self.assertTrue(page, "the server no longer names a default basis")
        page_label = page.group(1)
        answer = self._year_answer()
        if faq_label == page_label:
            self.assertNotIn(
                "not meant to match", answer,
                "the FAQ and the page now count the same way, so the copy telling the "
                "reader they answer different questions is false: %r" % answer[:400])
            return
        self.assertIn(
            page_label, answer,
            "the FAQ figure (%s) and the page's own totals (%s) answer different "
            "questions inches apart. The answer must name the page's basis too, or "
            "the reader is left to assume the numbers should agree: %r"
            % (faq_label, page_label, answer[:400]))
        self.assertIn(
            "not meant to match", answer,
            "naming both bases is not enough: the answer has to say plainly that the "
            "two totals are not meant to match, the way the at-a-glance board's "
            "footnote does for the same situation: %r" % answer[:400])

    def test_the_basis_words_are_the_pages_own_words(self):
        """Two labels for one basis is the same defect one step later. The FAQ
        writes its own copy (no JS rewrites JSON-LD), so the strings have to be
        the ones the hero and the cite line render."""
        answer = self._year_answer()
        for basis in ("notice", "effective"):
            head = _js_basis_headline(basis)
            if head.lower() in answer.lower():
                self.assertIn(head, answer,
                              "the FAQ names the %s basis in different words than the "
                              "rest of the page: %r is not %r" % (basis, answer[:400], head))

    def test_the_meta_description_rides_the_same_numbers(self):
        """The SERP description is built from alt_live_numbers() too, so it
        inherits whatever basis that function is on. If a later change gives the
        description its own query, it gets its own basis and its own drift."""
        desc = _plugin_fn("alt_tracker_meta_description")
        self.assertIn("alt_live_numbers()", desc,
                      "the meta description no longer reads the same figures as the FAQ")
        self.assertNotRegex(desc, r"\$wpdb->(get_row|get_var|prepare)",
                            "the meta description grew its own query; it would then "
                            "publish a basis nothing on the page labels")

    def test_the_citeline_comment_does_not_claim_the_two_agree(self):
        """A prose check, deliberately, and the only one here. The reason this
        defect survived a whole release is that page-tracker.php's own comment
        said the cite line had been changed to agree with alt_live_numbers(),
        which stopped being true the moment the default basis moved. The next
        person to read that comment must not be told the check is unnecessary."""
        block = TRACKER_TPL[TRACKER_TPL.index('id="alt-citeline-total"') - 3000:
                            TRACKER_TPL.index('id="alt-citeline-total"')]
        block = block[block.rindex("<?php /*"):]
        self.assertIn(
            "alt_live_numbers", block,
            "the cite line's comment no longer mentions the other total on this page")
        self.assertRegex(
            block, r"(?i)effective",
            "the cite line's comment names the other total but not the basis that "
            "total is counted on, which is the fact that went stale: %s" % block[:800])
        self.assertRegex(
            block, r"(?is)(no longer true|different basis|different window|not meant to match)",
            "the cite line's comment must record that the FAQ total is computed on a "
            "different basis, not imply the two agree: %s" % block[:800])


# --------------------------------------------------------------------------
# 5. The compressed reconciliation. Both implementations, run.
# --------------------------------------------------------------------------

PHP_SHORT_HARNESS = r"""<?php
%s
echo alt_period_split_short(24754, 33817, 'Jul 2026'), "\n";
echo alt_period_split_short(100, 100, '2026'), "\n";
"""


def _php_fn(name):
    """Brace-matched source of one top-level `function <name>(` in db.php."""
    start = DB_PHP.index("function %s(" % name)
    i = DB_PHP.index("{", start)
    depth, j = 0, i
    while j < len(DB_PHP):
        if DB_PHP[j] == "{":
            depth += 1
        elif DB_PHP[j] == "}":
            depth -= 1
            if depth == 0:
                return DB_PHP[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


class TheReconciliationIsCompressedAndStillVisible(unittest.TestCase):

    EXPECTED = ("24,754 have taken effect. The other 9,063 are filed for "
                "effective dates later in Jul 2026. Together, 33,817.")

    def test_the_js_helper_produces_the_line(self):
        got = jsrun.run(
            ["periodSplitShort"],
            "function fmt(n) { return Number(n).toLocaleString('en-US'); }\n",
            "periodSplitShort(24754, 33817, 'Jul 2026')")
        self.assertEqual(got, self.EXPECTED)

    @unittest.skipUnless(PHP, "php binary not available")
    def test_the_php_helper_produces_the_identical_line(self):
        """Character for character, or the home page and the press page drift
        the way they did when they published totals 33,939 apart."""
        out = subprocess.run(
            [PHP, "-r", PHP_SHORT_HARNESS[6:] % _php_fn("alt_period_split_short")],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        lines = out.stdout.splitlines()
        self.assertEqual(lines[0], self.EXPECTED)
        self.assertEqual(lines[1], "",
                         "a zero remainder must render nothing, not a sentence "
                         "explaining that nothing is left over")

    def test_it_carries_all_three_numbers(self):
        """Asserted against what the HELPER produces, not against this file's
        own EXPECTED constant. The first version compared the constant with
        itself, which is a tautology that passes on any tree, including one
        with no helper at all."""
        got = jsrun.run(
            ["periodSplitShort"],
            "function fmt(n) { return Number(n).toLocaleString('en-US'); }\n",
            "periodSplitShort(24754, 33817, 'Jul 2026')")
        for n, what in (("24,754", "the part already in effect"),
                        ("9,063", "the remainder still ahead"),
                        ("33,817", "the total the two make")):
            self.assertIn(n, got, "the compressed line drops %s" % what)

    def test_it_is_shorter_than_the_full_sentence(self):
        """Compressed, which is the point. Both sides are RUN: comparing this
        file's constant against the live full sentence passed on a tree with no
        compressed helper in it."""
        pre = "function fmt(n) { return Number(n).toLocaleString('en-US'); }\n"
        short = jsrun.run(["periodSplitShort"], pre,
                          "periodSplitShort(24754, 33817, 'Jul 2026')")
        full = jsrun.run(["periodSplitSentence"], pre,
                         "periodSplitSentence(24754, 33817, 'Aug 11, 2026', 'Jul 2026')")
        self.assertLess(len(short), len(full),
                        "the 'compressed' line is not shorter than the full one")

    def test_it_is_not_inside_a_disclosure(self):
        """Three caveats in this codebase have been demoted into a <details>
        and then read by nobody. This one is prose in the hero."""
        hero = TPL_NC[TPL_NC.index('<header class="alt-hero">'):]
        hero = hero[:hero.index("</header>")]
        self.assertIn('id="alt-hero-asof-wrap"', hero)
        self.assertNotIn("<details", hero, "the hero grew a disclosure")
        self.assertNotIn("hidden>", hero[hero.index('id="alt-hero-asof-wrap"'):],
                         "the reconciliation line ships hidden")

    def test_the_fuller_explanation_is_one_click_away(self):
        self.assertIn('href="#alt-basis-explainer"', TPL_NC,
                      "the compressed line does not link out to the full explanation")
        self.assertIn('id="alt-basis-explainer"', TPL_NC,
                      "the link target for the full explanation does not exist")


# --------------------------------------------------------------------------
# 6. The explanatory copy no longer argues for the old default.
# --------------------------------------------------------------------------

class TheCopyMatchesTheControl(unittest.TestCase):

    def test_the_page_no_longer_argues_for_the_effective_default(self):
        """This paragraph read "We date each cut by when it takes effect, not
        when it was filed ... That is what a worker lives through". Left
        standing it contradicts the control it explains."""
        visible = visible_copy(TRACKER_TPL)
        self.assertNotIn("We date each cut by when it takes effect, not when it was filed", visible)
        self.assertNotIn("counted on the day they take effect; the main figure", visible)

    def test_the_effective_reasoning_is_relocated_not_deleted(self):
        """It answers a real question and the page still says so."""
        visible = visible_copy(TRACKER_TPL)
        self.assertIn("what a worker lives through", visible,
                      "the effective-date reasoning was deleted rather than relocated")
        self.assertIn("when the jobs actually ended", visible)

    def test_the_new_copy_says_why_the_filed_basis_is_the_default(self):
        visible = visible_copy(TRACKER_TPL)
        self.assertIn("reported nearly everywhere on the filing date", visible)

    def test_the_comparison_uses_the_neutral_public_framing(self):
        """Standing rule with a scrub history behind it: no competing tracker
        and no survey publisher is named anywhere, in any file, comment,
        fixture or page. The public framing is "the US national survey" or "an
        independent national estimate".

        THIS TEST IS DELIBERATELY POSITIVE, and that is not a weakening. The
        obvious check is a banned-word list, but a banned-word list is a list
        of those names, in a file, in this repo, which is the exact thing the
        rule forbids and the reason the last scrub happened. So the machine
        holds the half it can hold without breaking the rule: the approved
        framing is what the copy actually uses where the comparison is made.
        """
        visible = visible_copy(TRACKER_TPL)
        self.assertIn("national estimate", visible,
                      "the copy that positions our figure against an outside number "
                      "no longer uses the approved neutral framing")
        # The rationale comments in the changed files describe the comparison
        # too, and they are shipped source. They use the same framing.
        for src, label in ((JS, "layoffs.js"), (TRACKER_TPL, "page-tracker.php")):
            window = src[src.index("BASIS_COPY") if "BASIS_COPY" in src else 0:][:4000]
            self.assertNotRegex(
                window, r"(?i)\bversus [A-Z][a-z]+\b",
                "%s appears to name an outside product in the basis rationale" % label)

    def test_no_em_or_en_dashes_in_the_copy_this_change_wrote(self):
        blocks = []
        hero = TRACKER_TPL[TRACKER_TPL.index('<header class="alt-hero">'):]
        blocks.append(visible_copy(hero[:hero.index("</header>")]))
        expl = TRACKER_TPL[TRACKER_TPL.index('id="alt-basis-explainer"'):]
        blocks.append(visible_copy(expl[:expl.index("</p>")]))
        basis_copy = JS[JS.index("var BASIS_COPY"):]
        blocks.append(basis_copy[:basis_copy.index("function basisCopy")])
        for block in blocks:
            for dash in ("—", "–"):
                self.assertNotIn(dash, block, "em or en dash in UI copy")


# --------------------------------------------------------------------------
# 7. Quick date ranges, back on the surface. Run, not read.
# --------------------------------------------------------------------------

def _js_var_object(name):
    """Source text of a top-level `var <name> = { ... };` in layoffs.js.

    jsrun.extract only lifts `function <name>(` declarations, and the preset
    table is an object literal. Lifting the REAL literal matters: a test that
    stubbed the ranges would be asserting its own arithmetic rather than the
    page's, which is precisely the failure mode this suite exists to avoid.
    """
    needle = "var %s = {" % name
    if needle not in JS:
        # Absent on a tree from before the table existed. Returning nothing
        # rather than raising at IMPORT time matters: a module that cannot be
        # imported fails every test in this file for one reason, which proves
        # only that a name is missing. Returning "" lets each preset test run
        # against the tree's own code and fail on what that code actually does.
        return "/* %s absent */" % name
    start = JS.index(needle)
    i = JS.index("{", start)
    depth, j = 0, i
    while j < len(JS):
        if JS[j] == "{":
            depth += 1
        elif JS[j] == "}":
            depth -= 1
            if depth == 0:
                return JS[start:j + 1] + ";"
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


PRESET_PREAMBLE = """
function pad2(n) { return (n < 10 ? '0' : '') + n; }
var CONTROLS = {};
function readControl(id) { return CONTROLS[id] === undefined ? '' : CONTROLS[id]; }
function writeControl(id, v) { CONTROLS[id] = v; }
""" + _js_var_object("DATE_PRESETS") + "\n"


class QuickDateRangesAreBackAndApplyWhatTheyName(unittest.TestCase):

    def test_the_row_is_visible_chrome_not_inside_the_filters_panel(self):
        """A date preset is a one-tap, high-intent control. Inside the
        collapsed Filters panel it costs a panel-open before it can be seen."""
        self.assertIn('id="alt-datepresets"', TPL_NC, "the quick date range row is missing")
        panel = TPL_NC[TPL_NC.index('id="alt-datepresets"'):]
        self.assertNotIn("alt-filter-panel", TPL_NC[:TPL_NC.index('id="alt-datepresets"')][-2000:],
                         "the preset row was placed inside the collapsed filters panel")

    def test_every_preset_applies_the_range_it_names(self):
        """Run, not read. Each preset writes the same from/to controls the date
        popover writes, so there is one date range on this page and not two."""
        got = jsrun.run(
            ["applyDatePreset", "isoDay", "daysAgo"],
            PRESET_PREAMBLE,
            "(function () {"
            " var out = {};"
            " ['today','d7','d30','d90','ytd','all'].forEach(function (k) {"
            "   CONTROLS = {};"
            "   applyDatePreset(k);"
            "   out[k] = [CONTROLS['alt-f-from'], CONTROLS['alt-f-to']];"
            " });"
            " return out; })()",
            optional=("DATE_PRESETS",))
        import datetime
        today = datetime.date.today()
        iso = lambda d: d.isoformat()
        self.assertEqual(got["today"], [iso(today), iso(today)])
        self.assertEqual(got["d7"], [iso(today - datetime.timedelta(days=6)), iso(today)])
        self.assertEqual(got["d30"], [iso(today - datetime.timedelta(days=29)), iso(today)])
        self.assertEqual(got["d90"], [iso(today - datetime.timedelta(days=89)), iso(today)])
        self.assertEqual(got["ytd"], ["%d-01-01" % today.year, iso(today)])
        self.assertEqual(got["all"], ["", ""], "All time must clear both bounds")

    def test_a_preset_clears_the_period_dropdowns_it_would_intersect_with(self):
        """years/quarters/months AND with a date range in alt_db_where, so a
        preset left beside years=2024 returns an empty intersection and the
        page goes blank for a reason nothing on screen explains."""
        got = jsrun.run(
            ["applyDatePreset", "isoDay", "daysAgo"],
            PRESET_PREAMBLE,
            "(function () {"
            " CONTROLS = {'alt-f-years': ['2024'], 'alt-f-quarters': ['1'], 'alt-f-months': ['3']};"
            " applyDatePreset('d30');"
            " return [CONTROLS['alt-f-years'], CONTROLS['alt-f-quarters'], CONTROLS['alt-f-months']];"
            " })()",
            optional=("DATE_PRESETS",))
        self.assertEqual(got, [[], [], []])

    def test_the_active_preset_is_computed_from_the_view_not_from_the_last_click(self):
        """So a range typed by hand that happens to equal a preset lights that
        preset, which is correct: the page IS showing it."""
        got = jsrun.run(
            ["datePresetActive", "isoDay", "daysAgo"],
            PRESET_PREAMBLE,
            "(function () {"
            " var d = new Date(); var iso = isoDay(d);"
            " CONTROLS = {'alt-f-from': iso, 'alt-f-to': iso};"
            " var a = datePresetActive('today');"
            " CONTROLS['alt-f-years'] = ['2026'];"
            " var b = datePresetActive('today');"
            " CONTROLS = {};"
            " var c = datePresetActive('all');"
            " return [a, b, c]; })()",
            optional=("DATE_PRESETS",))
        self.assertEqual(got[0], True, "a hand-typed range equal to Today is not marked")
        self.assertEqual(got[1], False,
                         "a preset stays marked while a period dropdown narrows the view "
                         "further, so the pill claims a view the numbers do not show")
        self.assertEqual(got[2], True, "All time is not marked on an unbounded view")

    def test_the_active_preset_is_visibly_marked(self):
        upd = strip_js_comments(jsrun.extract("updateDatePresetStates"))
        self.assertIn("alt-dp-on", upd)
        self.assertIn("aria-pressed", upd, "the marked preset is not exposed to a screen reader")
        self.assertRegex(CSS, r"\.alt-dp-on[^{]*\{[^}]+\}", "the active preset has no styling")


# --------------------------------------------------------------------------
# 8. Card whitespace: truncation is a bug, honest emptiness is a label.
# --------------------------------------------------------------------------

class CardsEitherFillOrExplainThemselves(unittest.TestCase):

    def test_the_largest_events_query_fetches_what_the_card_can_draw(self):
        """"Largest single job cuts" was truncated by the QUERY, not the card:
        the fetch stopped at 10 while the bar list draws up to BARLIST_LIMIT,
        so it sat short beside full-height neighbours with rows still
        available. Fetch what the card can draw; do not pad the card."""
        m = re.search(r"FROM \$table WHERE \$w2 ORDER BY job_count DESC, id DESC LIMIT (\d+)", DB_NC)
        self.assertTrue(m, "the largest-events query changed shape")
        limit = int(m.group(1))
        bl = re.search(r"var\s+BARLIST_LIMIT\s*=\s*(\d+)", JS_NC)
        self.assertTrue(bl, "BARLIST_LIMIT is gone")
        self.assertGreaterEqual(
            limit, int(bl.group(1)),
            "the largest-events query fetches %d rows while the card draws up to %s, "
            "so the card truncates while rows remain" % (limit, bl.group(1)))

    def test_the_ai_intensity_card_explains_its_own_sparseness(self):
        """It legitimately draws one bar: industries under 1,000 cuts are
        excluded on purpose, because a 50 percent AI rate over 4 cuts is the
        kind of number this project refuses to publish. The threshold is NOT
        lowered and the card is NOT padded. It says how many industries were
        considered and how many cleared the bar."""
        self.assertIn('id="alt-bars-ai-intensity-note"', TPL_NC,
                      "the AI intensity card has nowhere to explain its sparseness")
        charts = strip_js_comments(jsrun.extract("renderCharts"))
        self.assertIn("alt-bars-ai-intensity-note", charts,
                      "nothing writes the AI intensity card's explanation")
        self.assertIn("in this view", charts)
        self.assertIn(".hidden = false", charts,
                      "the explanation is written but never unhidden, which is the "
                      "defect this codebase has shipped three times")

    def test_the_threshold_was_not_lowered_to_fill_the_card(self):
        charts = strip_js_comments(jsrun.extract("renderCharts"))
        self.assertIn("e[1] >= 1000", charts,
                      "the 1,000-cut floor on the AI intensity card was weakened")

    def test_the_zero_row_case_says_so_rather_than_rendering_empty(self):
        charts = strip_js_comments(jsrun.extract("renderCharts"))
        self.assertIn("no rate to show", charts,
                      "a view where no industry clears the bar renders an empty card "
                      "with nothing saying why")


# --------------------------------------------------------------------------
# 9. Tile alignment and the cross-link control.
# --------------------------------------------------------------------------

class TilesAlignAndTheCrossLinkIsAControl(unittest.TestCase):

    def test_the_tiles_share_one_internal_structure(self):
        """They carried between one and three caption lines each, so the labels
        did not line up across the row. The label now occupies the same
        vertical band in every tile, and the caption block below it therefore
        starts at the same height. Both tile rows get it, or the derived strip
        stays ragged under a tidy one."""
        self.assertRegex(
            CSS,
            r"\.alt-stats-bar\s*>\s*\.alt-stat-card\s*>\s*\.alt-stat-label\s*\{[^}]*min-height",
            "the primary tiles' labels reserve no shared band")
        self.assertRegex(
            CSS,
            r"\.alt-broad-strip\s*>\s*\.alt-stat-card\s*>\s*\.alt-stat-label\s*\{[^}]*min-height",
            "the derived tiles were left ragged")

    def test_the_optional_detail_line_has_reserved_space(self):
        """Reserved, so a tile without the line does not collapse and shift its
        neighbours when a filter makes the line appear. The AI tile's share
        sentence disappears entirely once the view is filtered to AI rows,
        which is the case that used to move the row."""
        block = re.search(
            r"\.alt-stats-bar\s*>\s*\.alt-stat-card\s*>\s*\.alt-stat-detail\s*,"
            r"[^{]*\{([^}]*)\}", CSS)
        self.assertTrue(block, "the optional detail row reserves no space")
        self.assertIn("min-height", block.group(1))
        self.assertIn(".alt-stat-sub + .alt-stat-sub", CSS,
                      "the AI tile's optional share line is not covered by the reserve")

    def test_the_cross_link_is_a_button_with_an_accessible_name(self):
        line = [l for l in TPL_NC.splitlines() if "alt-crosslink" in l and "<a" in l]
        self.assertTrue(line, "the cross-link to the sibling tracker is gone")
        self.assertIn("alt-crosslink-btn", line[0], "the cross-link is still body prose")
        self.assertIn("aria-label=", line[0], "the cross-link control has no accessible name")

    def test_the_cross_link_uses_theme_tokens_and_has_a_focus_state(self):
        block = re.search(r"\.alt-crosslink-btn\s*\{([^}]*)\}", CSS)
        self.assertTrue(block, "the cross-link control has no styling")
        self.assertIn("var(--alt-", block.group(1),
                      "the cross-link hardcodes colours instead of using the theme tokens")
        self.assertRegex(CSS, r"\.alt-crosslink-btn:focus-visible\s*\{[^}]*outline",
                         "the cross-link has no visible focus state")
        self.assertNotRegex(block.group(1), r"#[0-9a-fA-F]{3,6}",
                            "the cross-link hardcodes a hex colour, so it cannot follow "
                            "the light and dark themes")


if __name__ == "__main__":
    unittest.main()
