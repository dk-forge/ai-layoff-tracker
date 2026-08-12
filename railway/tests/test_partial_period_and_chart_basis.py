"""Two published numbers that were wrong on the live page, pinned.

Same shape as test_trend_trajectory.py and test_facet_pages.py: there is no JS
runtime and no PHP runtime in this suite, so these pin the source properties
whose breakage would be SILENT on the page. Both were found by reading the live
site on 2026-08-04, not by any check here, which is why they are here now.

------------------------------------------------------------------------------
1. THE IN-PROGRESS MONTH WAS DRAWN AS A COMPLETED ONE.

fillMonths() caps the charted window at the CURRENT month, which stops future
months rendering as fake zeros. It never stopped the current month itself
rendering as finished. On 4 August 2026 the August bucket held 16,546 verified
cuts, four days of a month whose completed neighbours in 2026 averaged about
58,000, and three charts published that as a fact at once:

    trend        a fall from 55,304 (July) to 16,546, read as a ~70% collapse
    AI share     terminated at exactly 0.0%, an AI numerator that had not
                 landed yet over a denominator of four days
    year-on-year the 2026 line crossed under 2025 in the final month

Four days at that rate is ABOVE the run rate, not below it. Every one of the
three said the reverse of what the data says.

The rule chosen (one rule, all three charts, so a reader learns it once): the
in-progress month is labelled partial, drawn dashed with a marker, and named in
a sentence under the chart. It is NOT extrapolated to a full-month figure and
NOT annualised: a projection is a number no source states.

------------------------------------------------------------------------------
2. THE BARS AND THE HEADLINE WERE DIFFERENT QUANTITIES.

The bar cards drew $topN's index [1], which is SUM(job_count) over verified AND
announced, immediately beside a headline tile counting verified only. In the
default 2026 view the visible country bars summed to about 757,000 against a
published headline of 444,871, roughly 70% over, with nothing on the card
saying they were different measures. /aggregate now carries a verified pair at
[4]/[5] and the dashboard draws that.

WHY [4] AND [5] AND NOT [1] AND [2]: the same block is published, under a
stage=announced query, as the announced section of the quarterly appendix CSV
(export.php). Redefining [1] would zero every announced row in a published
artifact. The two bases have to coexist. Index [3] stays null because
renderBarList reads it as a display label (test_facet_pages guards that).
"""
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
JS = (PLUGIN / "assets/layoffs.js").read_text()
CSS = (PLUGIN / "assets/layoffs.css").read_text()
TEMPLATE = (PLUGIN / "templates/page-tracker.php").read_text()
DB_PHP = (PLUGIN / "includes/db.php").read_text()


def _fn_body(src: str, signature: str, stop_at: str = "\n    function ") -> str:
    """Source of one top-level function in layoffs.js, signature to next one."""
    start = src.index(signature)
    end = src.find(stop_at, start + len(signature))
    return src[start:end if end != -1 else len(src)]


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def _font_size_px(selector: str) -> int:
    """The largest px in the font-size declaration of one CSS rule.

    Comments are stripped first and only `font-size` is read. An earlier
    version of this helper took the largest px anywhere in the block, which
    happily reported a rule's `max-width: 1180px` as its type size and a
    superseded value quoted in its own comment as the live one.
    """
    block = re.search(re.escape(selector) + r"\s*\{(.*?)\}", CSS, re.S)
    assert block is not None, "no CSS rule for %s" % selector
    decls = _strip_comments(block.group(1))
    sizes = re.findall(r"font-size\s*:([^;]+);", decls)
    assert sizes, "no font-size in %s" % selector
    px = [int(n) for n in re.findall(r"(\d+)px", " ".join(sizes))]
    assert px, "font-size of %s carries no px value" % selector
    return max(px)


class PartialMonthHelperTests(unittest.TestCase):
    """The helpers exist and compute the partial month from the clock."""

    def test_the_helpers_exist(self):
        for name in ("function partialMonthAt(", "function partialLabel(",
                     "function partialNoteText(", "function setPartialNote(",
                     "function markPartialPoint("):
            self.assertIn(name, JS, "%s is missing" % name)

    def test_the_partial_month_is_the_month_the_clock_is_in(self):
        body = _fn_body(JS, "function nowMonthKey()")
        self.assertIn("new Date()", body)
        self.assertIn("getMonth() + 1", body)
        # Derived from the clock, never a constant: a hard-coded month would
        # be correct for one month and wrong for every other.
        self.assertNotRegex(body, r"'20\d\d-\d\d'")

    def test_the_note_states_elapsed_days_and_refuses_to_project(self):
        body = _fn_body(JS, "function partialNoteText(")
        self.assertIn("info.days", body)
        self.assertIn("info.of", body)
        self.assertIn("not a projection", body)

    def test_nothing_extrapolates_the_partial_month(self):
        # The specific failure mode the owner ruled out. A run-rate scale-up
        # would look like dividing by elapsed days and multiplying by the
        # month length, so no renderer may do that arithmetic.
        for sig in ("function renderTrend(", "function renderAiShare(",
                    "function renderYoY("):
            body = _fn_body(JS, sig)
            self.assertNotIn("daysInMonth", body,
                             "%s looks like it scales a partial month to a full one" % sig)

    def test_marking_a_point_dashes_only_the_segment_that_ends_on_it(self):
        body = _fn_body(JS, "function markPartialPoint(")
        self.assertIn("ctx.p1DataIndex === idx", body)
        self.assertIn("borderDash", body)
        # And it must give the point a visible marker, since a dash alone is
        # invisible at one point on a pointRadius-0 line.
        self.assertIn("pointRadius", body)


class ThreeChartsTests(unittest.TestCase):
    """All three charts that showed the artefact carry the same treatment."""

    CHARTS = {
        "function renderTrend(": "alt-trend-partial",
        "function renderAiShare(": "alt-ai-share-partial",
        "function renderYoY(": "alt-yoy-partial",
    }

    def test_each_chart_computes_and_marks_the_partial_month(self):
        for sig, note_id in self.CHARTS.items():
            body = _fn_body(JS, sig)
            self.assertIn("partialMonthAt(", body,
                          "%s never asks whether it is drawing an unfinished month" % sig)
            self.assertIn("markPartialPoint(", body,
                          "%s computes the partial month but never marks it" % sig)
            self.assertIn(note_id, body,
                          "%s never writes its partial-period note" % sig)

    def test_each_chart_clears_the_note_before_it_can_go_stale(self):
        # Every one of these has an early return (compare mode) and a filtered
        # past-year path. A note left over from the previous render would say
        # a completed view contains an unfinished month.
        for sig, note_id in self.CHARTS.items():
            body = _fn_body(JS, sig)
            self.assertIn("setPartialNote('%s', null)" % note_id, body,
                          "%s can leave a stale partial note behind" % sig)

    def test_the_two_per_month_charts_label_the_axis_tick(self):
        # These two have one label per calendar month, so "(partial)" can go
        # on the axis and be unambiguous.
        for sig in ("function renderTrend(", "function renderAiShare("):
            body = _fn_body(JS, sig)
            self.assertIn("partialLabel(", body,
                          "%s does not label the partial month on its axis" % sig)

    def test_year_over_year_labels_the_series_not_the_shared_axis(self):
        # Its x-axis is bare month names SHARED by both years. Suffixing the
        # tick there would label last year's completed August as partial too,
        # which is a second wrong statement rather than a fix for the first.
        body = _fn_body(JS, "function renderYoY(")
        self.assertNotIn("partialLabel(", body)
        self.assertIn("partial)", body)

    def test_every_note_element_exists_in_the_template(self):
        for note_id in self.CHARTS.values():
            self.assertIn('id="%s"' % note_id, TEMPLATE,
                          "%s is written by JS but has nowhere to render" % note_id)

    def test_the_notes_start_hidden(self):
        # A past-year view has no partial month; an empty bordered box under
        # the chart would read as a failed render.
        for note_id in self.CHARTS.values():
            self.assertRegex(TEMPLATE, r'id="%s" hidden>' % re.escape(note_id))

    def test_the_note_is_visible_prose_not_a_collapsed_disclosure(self):
        # The whole point is that the reader does not have to open anything.
        # If these ever move inside the card's (i) <details>, the artefact is
        # back for everyone who does not click.
        for note_id in self.CHARTS.values():
            idx = TEMPLATE.index('id="%s"' % note_id)
            # The nearest preceding tag must not be an open <details>/<summary>.
            before = TEMPLATE[max(0, idx - 1200):idx]
            self.assertGreater(before.count("</details>"), before.count("<details") - 1,
                               "%s appears to sit inside an unclosed <details>" % note_id)

    def test_the_partial_note_is_styled_to_stand_out(self):
        self.assertIn(".alt-chart-note-partial", CSS)


class BarBasisTests(unittest.TestCase):
    """The bars are the same quantity as the headline tile, and say so."""

    def test_aggregate_carries_a_verified_pair(self):
        topn = DB_PHP.split("$topN = function (")[1].split("};")[0]
        self.assertIn("SUM(CASE WHEN announced=0 THEN job_count END)", topn)
        self.assertIn("SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END)", topn)

    def test_the_all_jobs_pair_is_still_published(self):
        # export.php writes the announced section of the quarterly appendix
        # from this same block under a stage=announced query. If [1] ever
        # becomes announced=0, every announced row there silently zeroes.
        topn = DB_PHP.split("$topN = function (")[1].split("};")[0]
        self.assertIn("SUM(job_count) v", topn)
        self.assertIn("(int) $row->v, (int) $row->a", topn)

    def test_the_dashboard_draws_the_verified_pair(self):
        body = _fn_body(JS, "function verifiedBasis(")
        self.assertIn("e[4]", body)
        self.assertIn("e[5]", body)
        # Re-sorted, because the server orders by the all-jobs total for the
        # sake of the facet pages and the appendix CSV that read the same rows.
        self.assertIn(".sort(", body)

    def test_every_bar_card_goes_through_it(self):
        body = _fn_body(JS, "function renderCharts(agg)", stop_at="\n    /*")
        for card in ("alt-bars-industries", "alt-bars-states", "alt-bars-countries",
                     "alt-bars-roles", "alt-bars-sourcetypes"):
            self.assertIn(card, body)
        # The three geographic/industry lists and the two computed ones are all
        # fed from verifiedBasis() output rather than the raw aggregate rows.
        self.assertNotIn("renderBarList('alt-bars-industries', agg.top_industries", body)
        self.assertNotIn("renderBarList('alt-bars-states', agg.top_states", body)
        self.assertGreaterEqual(body.count("verifiedBasis("), 3)

    def test_the_map_uses_the_same_basis_as_the_bars(self):
        body = _fn_body(JS, "function aiMapPoints(scope, agg)")
        self.assertIn("verifiedBasis(", body,
                      "a bubble sized on verified+announced is the same defect, rounder")

    def test_the_csv_download_matches_the_bars_it_sits_under(self):
        # A file whose column disagrees with the bar above the button is how a
        # wrong figure escapes the page into someone else's chart.
        self.assertIn("verifiedBasis((meta && LAST_AGG && LAST_AGG[meta[0]]) || [])", JS)
        self.assertIn("label,verified_jobs,ai_attributed_verified_jobs", JS)

    def test_the_ai_intensity_share_is_verified_over_verified(self):
        body = _fn_body(JS, "function renderCharts(agg)", stop_at="\n    /*")
        chunk = body[body.index("var intensity"):body.index("alt-bars-ai-intensity")]
        self.assertIn("industryRows", chunk,
                      "a verified numerator over an all-jobs denominator understates the share")

    def test_the_cards_state_their_basis(self):
        body = _fn_body(JS, "function barBasisNote(")
        self.assertIn("verified job cuts", body)
        # It must name the announced tier it excludes, using the real figure
        # from totals rather than a typed one.
        self.assertIn("totals.announced_jobs", body)

    def test_the_note_reconciles_the_bars_against_the_headline(self):
        # The requirement is that a reader can add up what they see and land on
        # the published number, or be told why they cannot. So the sentence
        # sums the DRAWN rows and subtracts them from the headline, rather than
        # gesturing at a gap.
        body = _fn_body(JS, "function barBasisNote(")
        self.assertIn("(totals.jobs || 0) - ann", body, "headline is not derived from totals")
        self.assertIn(".reduce(", body, "the drawn total is not summed from the drawn rows")
        self.assertIn("headline - drawn", body, "the remainder is not computed")
        self.assertIn("BARLIST_LIMIT", body,
                      "the sentence must count the rows the card actually draws")

    def test_the_note_refuses_the_arithmetic_when_it_would_be_false(self):
        # Each bar list ignores its OWN dimension's filter so a reader can
        # switch. With that filter on, the bars cover a wider population than
        # the headline and no subtraction relates them.
        body = _fn_body(JS, "function barBasisNote(")
        self.assertIn("dimensionFiltered", body)
        guarded = body[body.index("if (dimensionFiltered)"):]
        self.assertIn("return", guarded.split("}")[0],
                      "the filtered branch must return before the subtraction")
        self.assertLess(body.index("if (dimensionFiltered)"), body.index("headline - drawn"))

    def test_every_card_passes_its_own_filter_state(self):
        body = _fn_body(JS, "function renderCharts(agg)", stop_at="\n    /*")
        for control in ("alt-f-industry", "alt-f-state", "alt-f-country", "alt-f-verification"):
            self.assertIn("barBasisNote(barTotals, ", body)
            self.assertIn("selectedList('%s').length > 0" % control, body,
                          "the %s card does not tell the note whether it is filtered" % control)

    def test_the_basis_note_elements_exist_and_start_hidden(self):
        for card in ("alt-bars-industries", "alt-bars-states",
                     "alt-bars-countries", "alt-bars-sourcetypes"):
            self.assertRegex(TEMPLATE, r'id="%s-basis" hidden>' % re.escape(card))

    def test_the_basis_sentence_is_written_from_totals_not_typed(self):
        # A grouped figure typed into the sentence would be correct for one
        # day. The incident numbers ARE allowed in the comments that record
        # what went wrong, so this reads the function body with its comments
        # stripped rather than searching the whole file.
        body = _strip_comments(_fn_body(JS, "function barBasisNote("))
        self.assertNotRegex(body, r"\d{1,3},\d{3}")
        self.assertIn("fmt(", body)
        # Same rule for the hero, which renders the headline total server-side.
        hero = TEMPLATE[TEMPLATE.index('<header class="alt-hero">'):]
        hero = hero[: hero.index("</header>")]
        self.assertNotRegex(re.sub(r"<\?php.*?\?>", " ", hero, flags=re.S), r"\d{1,3},\d{3}")


class OneDominantFigureTests(unittest.TestCase):
    """The first screen leads with the number the page exists to publish."""

    def test_the_hero_carries_the_verified_total(self):
        self.assertIn('id="alt-hero-total"', TEMPLATE)
        self.assertIn('class="alt-hero-figure-value"', TEMPLATE)

    def test_the_hero_figure_and_the_verified_tile_are_one_number(self):
        # Written from the same variable in the same pass, so a filter change
        # cannot leave the page publishing two different headline totals.
        body = _fn_body(JS, "function renderStats(t)")
        self.assertIn("setText('alt-stat-total', fmt(verifiedJ))", body)
        self.assertIn("setText('alt-hero-total', fmt(verifiedJ))", body)

    def test_the_figure_outranks_the_page_title(self):
        self.assertGreater(_font_size_px(".alt-hero-figure-value"),
                           _font_size_px(".entry-title"),
                           "the page's own name is larger than the figure it publishes")

    def test_the_figure_outranks_the_freshness_panel_numbers(self):
        self.assertGreater(_font_size_px(".alt-hero-figure-value"),
                           _font_size_px(".alt-fresh-stat b"))

    def test_the_figure_outranks_the_thesis_and_the_tiles(self):
        figure = _font_size_px(".alt-hero-figure-value")
        self.assertGreater(figure, _font_size_px(".alt-hero-thesis"))
        self.assertGreater(figure, _font_size_px(".alt-stat-value"))

    def test_the_headline_total_is_not_printed_twice_on_one_screen(self):
        # It was in the hero panel AND the tile grid; at two sizes, a reader
        # has to work out which is the real one.
        hero = TEMPLATE[TEMPLATE.index('<aside class="alt-fresh"'):]
        hero = hero[: hero.index("</aside>")]
        self.assertNotIn("$alt_stat('total')", hero)

    def test_tiles_that_exist_only_to_be_warned_about_are_kept_out_of_the_grid(self):
        # Each of these carried a caption whose only job was to warn a reader
        # off the tile it was printed on. None is deleted; all three sit in
        # their own section with their element IDs unchanged, so renderStats
        # keeps writing them.
        #
        # That section was a closed <details> and is now a visible <section>:
        # the sentence explaining that these three cannot be added to the tiles
        # above is the sentence that stops a double count, and behind a click
        # it measured zero rendered characters. The separation this test
        # guards is unchanged. Only its visibility moved.
        grid = TEMPLATE[TEMPLATE.index('<div class="alt-stats-bar" id="alt-stats-bar">'):]
        grid = grid[: grid.index("</div>\n        <?php")]
        for demoted in ("alt-stat-all", "alt-stat-ai-total", "alt-stat-ai-broad"):
            self.assertNotIn('id="%s"' % demoted, grid,
                             "%s is back in the first-screen tile grid" % demoted)
        derived = TEMPLATE[TEMPLATE.index('<section class="alt-stats-derived"'):]
        for demoted in ("alt-stat-all", "alt-stat-ai-total", "alt-stat-ai-broad"):
            self.assertIn('id="%s"' % demoted, derived,
                          "%s was dropped instead of demoted" % demoted)

    def test_the_demoted_numbers_are_still_rendered(self):
        body = _fn_body(JS, "function renderStats(t)")
        for demoted in ("alt-stat-all", "alt-stat-ai-total", "alt-stat-ai-broad"):
            self.assertIn("'%s'" % demoted, body)

    def test_one_tile_leads_the_remaining_grid(self):
        self.assertIn("alt-stat-card-lead", TEMPLATE)
        self.assertGreater(_font_size_px(".alt-stat-card-lead .alt-stat-value"),
                           _font_size_px(".alt-stat-value"),
                           "the grid is back to N totals at one identical size")


class CopyRulesTests(unittest.TestCase):
    """House rules that apply to every string added above."""

    ADDED_IDS = ("alt-trend-partial", "alt-yoy-partial", "alt-ai-share-partial",
                 "alt-hero-figure", "alt-stats-derived")

    def test_no_em_dashes_in_the_copy_this_change_added(self):
        for fn in ("function partialNoteText(", "function barBasisNote("):
            self.assertNotIn("—", _fn_body(JS, fn))
        block = TEMPLATE[TEMPLATE.index('<header class="alt-hero">'):]
        block = block[: block.index("</header>")]
        self.assertNotIn("—", block)
