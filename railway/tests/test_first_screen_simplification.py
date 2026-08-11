"""The tracker's first screen: one question, and the copy a human reads.

WHY THIS FILE EXISTS. The owner read the live page on 2026-08-04 and said
"horrible wording for humans and behaviour psychology" and then, on the second
look, "still very messy, lots of text, lots of confusion on what to do first
and how to start." Measured on a real 375x812 render of the template, he was
describing something exact: above the first row of data the page carried 62
visible interactive controls and 589 words, the first tile sat 2686px down and
the search box 1744px down, which is two full screens of chrome before a reader
can do anything.

The copy was written DEFENSIVELY. "Every layoff here is verified. That is the
whole point." argues with a competitor the reader has never met. "We do not
estimate." leads with a refusal. "blamed on AI by the employer" returns a
verdict this tracker does not return. And the reconciliation sentence, three
numbers and an equation, was the THIRD thing a human read.

WHAT IS PINNED HERE, and what is deliberately not:

  * the strings, in both directions: the defensive ones are gone, the
    benefit-shaped ones are present, and the AI wording stays inside the rubric
    (the employer NAMED AI; we never assert the cause);
  * the reading order in the hero, by source position;
  * the block order on the page, which is the filter-placement fix: the region
    tabs, which DO scope the board, sit above it; the date/sort/dropdown
    controls, which do not, sit below it;
  * that every caveat which moved behind a disclosure is a real <details> whose
    body is displayed when open, and that the reconciliation did NOT move behind
    one. Three separate caveats in this codebase have computed to display:none
    or 0x0 and were read by nobody, so the CSS is checked for the ways that
    happens rather than for the presence of a rule;
  * that nothing was DELETED to make the screen shorter. Every block that left
    the first screen is asserted still present further down.

HOW IT MATCHES. Comments are stripped from PHP, JS and CSS before any string
assertion. An adversarial sweep on 2026-08-04 found seven checks in these two
repos passing against defective code for the wrong reason, and two of them
matched a COMMENT describing a call instead of the call. Every "did we delete
X" assertion in this file would pass trivially against a tree where X survives
only inside the comment explaining why it went.

PROVEN TO FAIL ON THE PRE-FIX TREE. The whole file was run against
origin/main@3324bb3, the tree this change starts from: 28 of the 34 failed
there. The six that did not are named here rather than left to look like
proof they are not:

    test_the_region_tabs_are_not_rendered_twice
    test_every_element_the_front_end_writes_still_exists
    test_the_split_sentence_is_still_the_shared_helper_not_typed_here
    test_the_open_body_is_displayed_and_has_size
    test_the_summary_marker_is_hidden_without_hiding_the_summary
    test_the_hero_carries_the_one_methodology_route

Each of those describes a property the old tree already had and this change
had to preserve rather than create, and each guards a specific way this change
could have broken it: the tab block was copied to a new position and the old
one deleted (a duplicate #alt-tabs would have broken every tab handler); four
blocks were moved out of the hero carrying element IDs that layoffs.js writes
by hand; and the two CSS rules that were load-bearing for one disclosure are
now load-bearing for six. They are regression bars, not evidence.
"""
import re
import unittest
from pathlib import Path

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
TEMPLATE_PATH = PLUGIN / "templates/page-tracker.php"
JS_PATH = PLUGIN / "assets/layoffs.js"
CSS_PATH = PLUGIN / "assets/layoffs.css"


def strip_php_comments(src: str) -> str:
    """Drop PHP comments and HTML comments, KEEP PHP code.

    Deleting whole <?php ... ?> islands would be simpler and wrong: half this
    template's visible markup is echoed from PHP (the signal board, the tile
    (i) bodies), so a stripper that ate the islands would let this file assert
    that markup is absent when it is on the page every day.

    So: walk the source, and inside PHP track single quotes, double quotes and
    heredocs well enough that a `//` or a `#` inside a string is not read as the
    start of a comment.
    """
    out, i, n = [], 0, len(src)
    in_php = False
    while i < n:
        if not in_php:
            j = src.find("<?php", i)
            k = src.find("<!--", i)
            if k != -1 and (j == -1 or k < j):
                out.append(src[i:k])
                end = src.find("-->", k)
                i = n if end == -1 else end + 3
                out.append(" ")
                continue
            if j == -1:
                out.append(src[i:])
                break
            out.append(src[i:j])
            out.append("<?php")
            i, in_php = j + 5, True
            continue
        c = src[i]
        two = src[i:i + 2]
        if two == "?>":
            out.append("?>")
            i, in_php = i + 2, False
            continue
        if two == "/*":
            end = src.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
            continue
        if two == "//" or c == "#":
            while i < n and src[i] != "\n" and src[i:i + 2] != "?>":
                i += 1
            out.append(" ")
            continue
        if c in "'\"":
            q = c
            out.append(c)
            i += 1
            while i < n:
                if src[i] == "\\":
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                if src[i] == q:
                    i += 1
                    break
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def strip_js_comments(src: str) -> str:
    out, i, n = [], 0, len(src)
    in_s = in_d = in_t = False
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if in_s or in_d or in_t:
            out.append(c)
            if c == "\\":
                if i + 1 < n:
                    out.append(src[i + 1])
                i += 2
                continue
            if in_s and c == "'":
                in_s = False
            elif in_d and c == '"':
                in_d = False
            elif in_t and c == "`":
                in_t = False
            i += 1
            continue
        if c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and nxt == "*":
            end = src.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
            continue
        if c == "'":
            in_s = True
        elif c == '"':
            in_d = True
        elif c == "`":
            in_t = True
        out.append(c)
        i += 1
    return "".join(out)


def strip_css_comments(src: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", src, flags=re.S)


TEMPLATE_RAW = TEMPLATE_PATH.read_text()
TEMPLATE = strip_php_comments(TEMPLATE_RAW)
JS_RAW = JS_PATH.read_text()
JS = strip_js_comments(JS_RAW)
CSS = strip_css_comments(CSS_PATH.read_text())


def at(haystack: str, needle: str) -> int:
    i = haystack.find(needle)
    if i == -1:
        raise AssertionError("not found in the comment-stripped source: %r" % needle)
    return i


class HeroCopyTests(unittest.TestCase):
    """The words a human reads, and the order they read them in."""

    # Each of these was live copy on 2026-08-04. They may survive in a comment
    # recording why they went; they may not survive on the page.
    RETIRED = (
        "That is the whole point",
        "We do not estimate",
        "blamed on AI",
        "A verified floor, not a survey",
        "New here? Start with",
        "Filter below; every number",
        "No figure appears unless its source states it",
    )

    def test_the_defensive_copy_is_off_the_page(self):
        for phrase in self.RETIRED:
            self.assertNotIn(phrase, TEMPLATE,
                             "%r is still rendered by page-tracker.php" % phrase)

    def test_the_defensive_copy_is_off_the_front_end_too(self):
        # renderStats() wrote "of verified cuts were blamed on AI by the
        # employer" into the AI tile on every filter change, so fixing only the
        # template would have left the page publishing both wordings.
        for phrase in ("blamed on AI", "explicitly blamed"):
            self.assertNotIn(phrase, JS, "%r is still written by layoffs.js" % phrase)

    def test_the_trust_line_is_the_benefit_not_the_refusal(self):
        # "We do not estimate" and "Every entry links to ..." are the same fact.
        # One is what we refuse to do; the other is what the reader gets.
        self.assertIn("Every entry links to the filing, notice or report it came from.",
                      TEMPLATE)

    def test_there_is_exactly_one_trust_claim_in_the_hero(self):
        hero = TEMPLATE[at(TEMPLATE, '<header class="alt-hero">'):]
        hero = hero[: hero.index("</header>")]
        self.assertEqual(1, hero.count("alt-hero-thesis"))
        self.assertNotIn("alt-hero-trust", hero)
        self.assertNotIn("alt-fresh-check", hero)

    def test_the_ai_line_reports_the_employers_words_and_claims_no_cause(self):
        self.assertIn("the employer named AI as a reason", TEMPLATE)
        # The rubric is attribution, not causation. None of these may appear.
        for overclaim in ("caused by AI", "AI caused", "due to AI", "because of AI"):
            self.assertNotIn(overclaim, TEMPLATE,
                             "%r asserts a cause the source does not state" % overclaim)

    def test_the_hero_reads_number_then_meaning_then_trust_then_detail(self):
        # Behavioural order, asserted by source position: the figure, what it
        # counts, who said AI, why it can be trusted, the two routes out, and
        # only then the arithmetic. The reconciliation used to be third.
        order = [
            'class="alt-hero-figure-value"',
            'class="alt-hero-figure-label"',
            'class="alt-hero-figure-sub"',
            'class="alt-hero-thesis"',
            'class="alt-hero-actions"',
            'id="alt-hero-asof-wrap"',
        ]
        seen = [at(TEMPLATE, k) for k in order]
        self.assertEqual(seen, sorted(seen),
                         "the hero reads out of order: %s" % list(zip(order, seen)))

    def test_the_reconciliation_is_demoted_but_not_hidden(self):
        # It has to stay: a journalist needs it, and it is what makes the home
        # page and the press page name the same period. Demoted means LATER,
        # never BEHIND A DISCLOSURE, because three caveats in this codebase have
        # been demoted into a <details> and then read by nobody.
        hero = TEMPLATE[at(TEMPLATE, '<header class="alt-hero">'):]
        hero = hero[: hero.index("</header>")]
        self.assertIn('id="alt-hero-asof"', hero)
        self.assertNotIn("<details", hero, "the hero grew a disclosure")
        self.assertNotIn("<summary", hero)
        block = hero[hero.index('id="alt-hero-asof-wrap"'):]
        self.assertTrue(block.lstrip().startswith('id="alt-hero-asof-wrap"'))
        self.assertRegex(block[:400], r"In this figure:")

    def test_the_split_sentence_is_still_the_shared_helper_not_typed_here(self):
        # The hero now calls the COMPRESSED helper (alt_period_split_short),
        # twinned character for character by periodSplitShort() in layoffs.js.
        # The invariant this test holds is unchanged and is not about the name:
        # the hero must not type a reconciliation of its own. The full sentence
        # still exists and is still called, by the press page, which
        # test_headline_total_agreement pins separately.
        self.assertIn("alt_period_split_short(", TEMPLATE_RAW)
        hero = TEMPLATE[at(TEMPLATE, '<header class="alt-hero">'):]
        hero = hero[: hero.index("</header>")]
        self.assertNotRegex(hero, r"\d{1,3},\d{3}",
                            "a headline figure was typed into the hero")

    def test_no_em_or_en_dashes_in_the_copy_this_change_wrote(self):
        # Scoped to what this change authored. The quarter options below have
        # carried an en dash in "Q1 (Jan-Mar)" since long before it and are not
        # this test's business.
        hero = TEMPLATE[at(TEMPLATE, '<header class="alt-hero">'):]
        hero = hero[: hero.index("</header>")]
        foot = TEMPLATE[at(TEMPLATE, "alt-sb-foot"):]
        foot = foot[: foot.index("</ul>")]
        for block in (hero, foot):
            for dash in ("—", "–"):
                self.assertNotIn(dash, block)


class BlockOrderTests(unittest.TestCase):
    """Controls sit above the content they control, and nowhere else."""

    def test_the_region_tabs_come_before_the_board_they_scope(self):
        # updateNarrative() scopes every period query to
        # REGION_TABS[ACTIVE_TAB].countries, so the tabs DO narrow the board.
        self.assertLess(at(TEMPLATE, 'id="alt-tabs"'), at(TEMPLATE, 'id="alt-narrative-wrap"'))

    def test_the_controls_that_do_not_scope_the_board_come_after_it(self):
        board = at(TEMPLATE, 'id="alt-narrative-wrap"')
        for later in ('class="alt-toolbar2"', 'class="alt-quickviews"', 'id="alt-filterbar-body"'):
            self.assertLess(board, at(TEMPLATE, later),
                            "%s sits above a board it does not filter" % later)

    def test_the_board_scoping_rule_is_stated_where_the_board_is(self):
        self.assertIn("This board follows the region tabs above", TEMPLATE)
        self.assertIn("This board follows the region tabs above", JS)

    def test_the_region_tabs_are_not_rendered_twice(self):
        self.assertEqual(1, TEMPLATE.count('id="alt-tabs"'))
        self.assertEqual(1, TEMPLATE.count('class="alt-tab alt-tab-world"'))

    def test_the_first_screen_is_the_figure_and_one_control_cluster(self):
        # Everything between the hero and the region tabs is what a reader has
        # to get past before the first control. It used to be the coverage
        # ribbon, the cite/export row, the open board and four link groups.
        gap = TEMPLATE[at(TEMPLATE, "</header>"): at(TEMPLATE, 'id="alt-tabs"')]
        for gone in ("alt-ribbon", "alt-citeline", "alt-lead", "alt-filter-context",
                     "alt-fresh"):
            self.assertNotIn(gone, gap, "%s is still between the hero and the controls" % gone)


class NothingWasDeletedTests(unittest.TestCase):
    """Shorter first screen, same page. Every moved block is still rendered."""

    def test_the_moved_blocks_all_survive_below_the_data(self):
        cards = at(TEMPLATE, 'id="alt-cards"')
        for moved in ('class="alt-fresh"', 'class="alt-ribbon"', 'class="alt-citeline"',
                      'class="alt-lead"'):
            self.assertGreater(at(TEMPLATE, moved), cards,
                               "%s was dropped from the page instead of moved" % moved)
        self.assertIn("alt-datastrip", TEMPLATE)
        self.assertIn("scan-scope.php", TEMPLATE_RAW)

    def test_every_element_the_front_end_writes_still_exists(self):
        # renderStatus(), renderStats() and updateExportLinks() write these by
        # id. Moving a block that took one of them with it would leave a live
        # setText() writing into nothing, silently.
        for el_id in ("alt-next-top", "alt-citeline-total", "alt-export-csv-top",
                      "alt-export-json-top", "alt-hero-asof", "alt-hero-ai",
                      "alt-hero-total", "alt-stat-ai-share-line"):
            self.assertIn('id="%s"' % el_id, TEMPLATE,
                          "layoffs.js writes #%s and the page no longer has it" % el_id)

    def test_the_hidden_wrapper_hides_the_label_with_the_sentence(self):
        # The sentence sits inside "In this figure: ...". An empty split has to
        # hide the wrapper or the hero prints a label with nothing after it.
        body = jsrun.extract("renderStats", JS_RAW)
        self.assertIn("getElementById('alt-hero-asof-wrap')", strip_js_comments(body))


class MethodologyEntryPointTests(unittest.TestCase):
    """One link, one destination."""

    def test_the_start_here_box_is_gone(self):
        self.assertNotIn("alt-stats-links", TEMPLATE)
        # Scoped to everything ABOVE the methodology section, where those were
        # links pointing INTO it. The section's own <summary> headings still
        # say "Where do we get this data?" and should: that is the answer, not
        # a sixth signpost to the answer.
        above = TEMPLATE[: at(TEMPLATE, '<section class="alt-methodology alt-faq"')]
        for link in ("New here? Start with", "What these numbers mean",
                     "Where do we get this data?", "How we catch &amp; fix errors",
                     "Why this is verified", "See the full methodology"):
            self.assertNotIn(link, above,
                             "%r is a duplicate methodology entry point" % link)

    def test_the_hero_carries_the_one_methodology_route(self):
        hero = TEMPLATE[at(TEMPLATE, '<header class="alt-hero">'):]
        hero = hero[: hero.index("</header>")]
        self.assertIn("How we count", hero)


class DisclosureVisibilityTests(unittest.TestCase):
    """A caveat behind a disclosure must be READ when the disclosure is open.

    Measured on a real 375px render of this template: opening each tile (i)
    yields 57 to 200 characters of rendered text in a box 247 to 341px wide and
    45 to 79px tall, and opening the board yields 656 characters including all
    four footnote lines. What is pinned below is the machinery that produced
    that, and specifically the three ways it has failed here before.
    """

    def test_every_tile_explanation_is_a_real_details(self):
        grid = TEMPLATE[at(TEMPLATE, 'id="alt-stats-bar"'):]
        grid = grid[: grid.index('<details class="alt-stats-derived">')]
        self.assertEqual(5, grid.count("$alt_tile_i("),
                         "a tile lost its (i) or grew a second one")
        # And what that helper emits is a real <details> with a real <summary>:
        # hidden by the browser, not by a class this file could get wrong, and
        # keyboard reachable with no JS at all.
        helper = TEMPLATE[at(TEMPLATE, "$alt_tile_i = function"):]
        helper = helper[: helper.index("};")]
        self.assertIn('<details class="alt-stat-i alt-stat-i-tile">', helper)
        self.assertIn("<summary", helper)
        self.assertIn('class="alt-stat-i-body"', helper)

    def test_no_tile_still_carries_standing_prose(self):
        grid = TEMPLATE[at(TEMPLATE, 'id="alt-stats-bar"'):]
        grid = grid[: grid.index('<details class="alt-stats-derived">')]
        self.assertNotIn("alt-stat-desc", grid,
                         "a tile still explains itself in a paragraph on its face")

    def test_the_open_body_is_displayed_and_has_size(self):
        rule = re.search(r"\.alt-stat-i\[open\]\s*>\s*\.alt-stat-i-body\s*\{([^}]*)\}", CSS)
        self.assertIsNotNone(rule, "nothing displays the (i) body when it is open")
        decl = rule.group(1)
        self.assertRegex(decl, r"display:\s*block")
        # The three ways a caveat has vanished in this codebase before.
        for killer in (r"display:\s*none", r"width:\s*0\b", r"height:\s*0\b",
                       r"font-size:\s*0\b", r"visibility:\s*hidden", r"opacity:\s*0\b"):
            self.assertNotRegex(decl, killer)

    def test_the_summary_marker_is_hidden_without_hiding_the_summary(self):
        m = re.search(r"\.alt-stat-i\s*>\s*summary\s*\{([^}]*)\}", CSS)
        self.assertIsNotNone(m)
        self.assertNotRegex(m.group(1), r"display:\s*none")
        self.assertRegex(m.group(1), r"width:\s*1[0-9]px")

    def test_the_board_summary_is_a_real_summary_and_the_panel_is_not_display_none(self):
        self.assertIn('<details class="alt-narrative-wrap"', TEMPLATE)
        self.assertIn('<summary class="alt-narrative-summary">', TEMPLATE)
        m = re.search(r"\.alt-narrative-wrap\s*>\s*summary\s*\{([^}]*)\}", CSS)
        self.assertIsNotNone(m)
        self.assertNotRegex(m.group(1), r"display:\s*none")


class BoardTests(unittest.TestCase):
    """The three things the owner reported on the live board."""

    def test_the_less_more_legend_is_gone(self):
        # It rendered as the words "less" and "more" beside the columns and was
        # never a control. Removed in both renderers.
        self.assertNotIn("alt-sb-legend", TEMPLATE)
        self.assertNotIn("alt-sb-legend", JS)
        self.assertNotIn("alt-sb-legend", CSS)

    def test_the_footnote_is_four_clauses_not_one_sentence(self):
        for src, where in ((TEMPLATE, "page-tracker.php"), (JS, "layoffs.js")):
            foot = src[at(src, "alt-sb-foot"):]
            foot = foot[: foot.index("</ul>")]
            self.assertEqual(4, foot.count("<li>"),
                             "%s no longer splits the footnote" % where)
        self.assertNotIn("Verified events, counted the day each cut takes effect; the AI row",
                         TEMPLATE)

    def test_a_repeated_leader_is_marked_in_both_renderers(self):
        # Dird Group led BOTH "This week" and "This month" on the live page,
        # which is right (a week sits inside a month) and reads like a bug.
        for src, where in ((TEMPLATE, "page-tracker.php"), (JS, "layoffs.js")):
            self.assertIn("alt-sb-ev-repeat", src, "%s does not mark the repeat" % where)
            self.assertIn("same event", src, "%s marks it with no word for a reader" % where)
        self.assertIn(".alt-sb-again", CSS)

    def test_the_repeat_marker_is_computed_not_hardcoded_to_two_columns(self):
        # A rule that only ever compared week-with-month would be right today
        # and wrong the first time YTD's leader also leads the month.
        body = strip_js_comments(jsrun.extract("updateNarrative", JS_RAW))
        self.assertIn("lseen", body)
        self.assertIn("hasOwnProperty.call(lseen, name)", body)


class FilterPanelTests(unittest.TestCase):
    """Eleven dropdowns behind one button, without breaking a no-JS reader."""

    def test_the_panel_has_one_toggle_with_the_aria_it_needs(self):
        row = TEMPLATE[at(TEMPLATE, "alt-filterbar-toggle-row"):]
        row = row[: row.index('<div class="alt-filterbar"')]
        self.assertIn('id="alt-filters-toggle"', row)
        self.assertIn('aria-expanded="true"', row)
        self.assertIn('aria-controls="alt-filterbar-body"', row)
        self.assertIn("<button", row)

    def test_it_ships_open_so_a_no_js_reader_keeps_every_filter(self):
        # The toggle ships hidden and the panel ships open; layoffs.js flips
        # both. Shipping it collapsed would hide eleven controls from anyone
        # whose JS failed to load.
        row = TEMPLATE[at(TEMPLATE, "alt-filterbar-toggle-row"):]
        toggle = row[: row.index("</button>")]
        self.assertIn("hidden", toggle)
        panel = TEMPLATE[at(TEMPLATE, 'id="alt-filterbar-body"'):]
        self.assertFalse(panel[:120].split(">")[0].strip().endswith("hidden"))

    def test_the_toggle_is_wired_from_the_real_init_sequence(self):
        # Not a comment mentioning it: the call, in the init body, with
        # comments stripped first.
        self.assertIn("initFilterPanel();", JS)
        self.assertIn("function initFilterPanel(", JS)

    def test_the_count_only_counts_what_is_inside_the_panel(self):
        # Counting search or the region tabs would print "Filters (3)" over a
        # panel holding none of them.
        body = strip_js_comments(jsrun.extract("panelFilterCount", JS_RAW))
        self.assertIn("PANEL_FILTER_IDS", body)
        ids = re.search(r"var PANEL_FILTER_IDS = \[(.*?)\];", JS, re.S).group(1)
        for outside in ("alt-search", "alt-f-from", "alt-f-to", "alt-sort"):
            self.assertNotIn("'%s'" % outside, ids)
        for inside in ("alt-f-industry", "alt-f-country", "alt-f-roles", "alt-f-minjobs"):
            self.assertIn("'%s'" % inside, ids)

    def test_the_count_runs_for_real_and_gets_the_arithmetic_right(self):
        # Executed in node against the real function bodies: a multi-select
        # contributes one per selected value, a text box one, an empty control
        # nothing, and controls outside the panel are never counted.
        n = jsrun.run(
            ["panelFilterCount"],
            jsrun.BASE_PREAMBLE + """
var PANEL_FILTER_IDS = ['alt-f-years','alt-f-quarters','alt-f-months','alt-f-industry',
    'alt-f-country','alt-f-state','alt-f-reasons','alt-f-verification','alt-f-roles',
    'alt-f-company','alt-f-keyword','alt-f-minjobs'];
CONTROLS = { 'alt-f-country': ['France','Spain'], 'alt-f-company': 'Acme',
             'alt-f-keyword': '', 'alt-search': 'ignored', 'alt-f-from': '2026-01-01' };
var document = { getElementById: function (id) {
    return PANEL_FILTER_IDS.indexOf(id) === -1 ? null : {}; } };
""",
            "panelFilterCount()",
            src=JS_RAW,
        )
        self.assertEqual(3, n)

    def test_a_deep_linked_filter_leaves_the_panel_open(self):
        body = strip_js_comments(jsrun.extract("initFilterPanel", JS_RAW))
        self.assertIn("setFilterPanelOpen(chosen)", body)
        # The years pill is set for every reader on first load, so it is not
        # evidence that anybody chose anything.
        self.assertIn("if (id === 'alt-f-years') return false;", body)


if __name__ == "__main__":
    unittest.main()
