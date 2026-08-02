"""Static guardrails for the whole-record trajectory strip in the trend card.

Same shape and purpose as test_facet_pages.py: there is no JS runtime and no
PHP runtime in this suite, so these pin the properties whose breakage would be
SILENT on a live page.

Three of them are the reason the strip exists at all, and each has a specific
way of going wrong quietly:

  * NO INTERPOLATION. The Chart.js path above the strip runs the series
    through fillMonths(), which substitutes {jobs: 0} for a month with no
    rows. That is defensible inside a dense selected year and it is not
    defensible over the full record, where a month we hold nothing for would
    be published as a month in which nobody was laid off. The strip must break
    its path instead, and nothing about a broken line tells a reader whether
    the break was meant.

  * COST. The strip's data is a SECOND /aggregate call. The endpoint's default
    is ~31 SQL statements; `include=series` is one grouped SUM plus the totals
    row. Dropping the include (or adding a new default block to serve this)
    would put that on the flagship page without anything failing.

  * THE TEXT IS OUT OF THE DRAWING. Axis values and dates are HTML beside the
    SVG so they stay CSS pixels in a card ~190px wide. A <text> element put
    back inside the plot renders at about a third of its intended size there
    and nothing errors.
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


def _draw_trajectory_body() -> str:
    """The source of drawTrajectory(), from its signature to renderTrend's neighbour."""
    start = JS.index("function drawTrajectory(box, full)")
    end = JS.index("// Align the claims series to the chart's months", start)
    return JS[start:end]


class WiringTests(unittest.TestCase):
    def test_the_container_lives_inside_the_trend_card(self):
        # Outside it, the strip would read as a chart of its own rather than
        # as the record the chart above is a window on.
        card = TEMPLATE[TEMPLATE.index('class="alt-mini alt-chart-card alt-trend-card"'):]
        card = card[: card.index('<div class="alt-mini')]
        self.assertIn('id="alt-trend-full"', card)
        self.assertIn('class="alt-tj"', card)

    def test_the_container_starts_hidden(self):
        # A failed fetch or a view with under two months must leave no empty
        # frame behind.
        self.assertRegex(TEMPLATE, r'<div class="alt-tj" id="alt-trend-full" hidden>')

    def test_render_charts_draws_it_outside_the_chartjs_guard(self):
        body = JS[JS.index("function renderCharts(agg)"):]
        body = body[: body.index("function renderLeaderboard")] if "function renderLeaderboard" in body else body[:4000]
        self.assertIn("renderTrendTrajectory();", body)
        chartjs_block = body[body.index("if (chartsAvailable())"):]
        chartjs_block = chartjs_block[: chartjs_block.index("renderTrendTrajectory();")]
        # The strip is plain SVG; it must not be inside the Chart.js branch.
        self.assertIn("}", chartjs_block)


class NoInterpolationTests(unittest.TestCase):
    """A month we hold no rows for must read as missing, never as zero."""

    def test_a_missing_month_breaks_the_path(self):
        body = _draw_trajectory_body()
        self.assertIn("if (!row) { cur = null; return; }", body)

    def test_it_does_not_run_the_series_through_the_zero_filling_helper(self):
        # fillMonths() substitutes {month: k, jobs: 0, ai_jobs: 0} for absent
        # months. Correct for the selected-year chart, a fabricated zero here.
        self.assertNotIn("fillMonths", _draw_trajectory_body())

    def test_the_gap_count_is_published(self):
        body = _draw_trajectory_body()
        self.assertIn("var gaps = keys.filter(", body)
        self.assertIn("months have no event we can source", body)

    def test_a_lone_month_is_still_drawn(self):
        # A one-month run emits "M x y L x y" so the round cap renders a dot;
        # a bare moveto draws nothing and the month silently disappears.
        self.assertIn("s.length === 1 ? ' L' + s[0]", _draw_trajectory_body())


class CostTests(unittest.TestCase):
    def test_the_second_aggregate_call_opts_into_series_only(self):
        body = JS[JS.index("function renderTrendTrajectory()"):]
        body = body[: body.index("function drawTrajectory")]
        self.assertIn("rest.include = 'series';", body)
        self.assertIn("apiGet('aggregate', rest)", body)

    def test_no_request_at_all_when_no_period_filter_is_set(self):
        # Without a period filter the chart above already IS the whole record,
        # so the strip hides itself before it can cost anything.
        body = JS[JS.index("function renderTrendTrajectory()"):]
        body = body[: body.index("function drawTrajectory")]
        self.assertIn("if (!periodFiltered(params)) { box.hidden = true; return; }", body)

    def test_the_fetch_waits_until_the_card_is_near_the_viewport(self):
        self.assertIn("function observeTrajectoryReveal()", JS)
        block = JS[JS.index("function observeTrajectoryReveal()"):]
        self.assertIn("IntersectionObserver", block[:900])
        self.assertIn("rootMargin", block[:900])

    def test_no_new_block_was_added_to_the_aggregate_default_set(self):
        # The strip must not make the flagship page's own aggregate wider.
        defaults = DB_PHP[DB_PHP.index("function alt_aggregate_default_blocks()"):]
        defaults = defaults[: defaults.index("}")]
        self.assertEqual(
            sorted(re.findall(r"'([a-z_]+)'", defaults)),
            sorted(['concentration', 'top_industries', 'top_countries', 'top_states',
                    'map_states', 'map_countries', 'top_roles', 'source_types',
                    'reasons', 'series', 'leaders', 'repeat_companies']))

    def test_series_is_a_valid_include_block(self):
        # If it were not, `include=series` would fall back to everything and
        # the strip would quietly cost the full ~31 statements.
        self.assertIn("'series'", DB_PHP[DB_PHP.index("function alt_aggregate_default_blocks()"):][:600])


class ScalableDrawingTests(unittest.TestCase):
    """The card is ~190px wide on a phone and ~700px expanded; one markup."""

    def test_grid_and_lines_do_not_scale_their_stroke(self):
        body = _draw_trajectory_body()
        self.assertEqual(body.count('vector-effect="non-scaling-stroke"'), 3)

    def test_the_endpoint_dots_are_a_separate_svg_with_no_viewbox(self):
        body = _draw_trajectory_body()
        dots = body[body.index('<svg class="alt-tj-dots"'):]
        dots = dots[: dots.index("</svg>")]
        self.assertNotIn("viewBox", dots)
        self.assertIn('cx="100%"', body)

    def test_no_text_is_drawn_inside_the_plot(self):
        body = _draw_trajectory_body()
        plot = body[body.index('<svg class="alt-tj-svg"'):body.index('<svg class="alt-tj-dots"')]
        self.assertNotIn("<text", plot)

    def test_the_axis_values_and_dates_are_html(self):
        body = _draw_trajectory_body()
        self.assertIn('class="alt-tj-ys"', body)
        self.assertIn('class="alt-tj-xs"', body)
        for cls in ("alt-tj-ys", "alt-tj-xs", "alt-tj-box", "alt-tj-dots", "alt-tj-band", "alt-tj-grid"):
            self.assertIn("." + cls, CSS, cls + " has no stylesheet rule")

    def test_the_scale_starts_at_zero(self):
        # tjNiceMax() returns the top of the axis; the bottom is literally 0.
        body = _draw_trajectory_body()
        self.assertIn("var gy = y(max * g / 2);", body)
        self.assertIn("<span>0</span>", body)


class CopyTests(unittest.TestCase):
    def test_no_em_dashes_in_the_strip_copy(self):
        strings = re.findall(r"'([^'\\\n]{6,})'", _draw_trajectory_body())
        for s in strings:
            self.assertNotIn("—", s)
            self.assertNotIn("–", s)

    def test_the_band_is_only_described_when_one_is_drawn(self):
        self.assertIn("bands.length ? '. The shaded band is the period charted above.'",
                      _draw_trajectory_body())


if __name__ == "__main__":
    unittest.main()
