"""The "By location" table: one ranked table of places, owner-approved 2026-10-19.

Static and offline (plus one PHP execution of the pure period function when a
`php` binary exists; it SKIPS loudly otherwise). Nothing here reaches the
deployed site.

What is pinned, and why each one:

* /by-location is a READ-ONLY public route behind the same whitelist-keyed
  micro-cache as /aggregate, and it builds its WHERE from alt_db_where, so it
  can never grow a filter dialect of its own.
* The basis is stated and fixed: VERIFIED cuts (announced = 0), superset rows
  folded (superset_of = 0), country = the strict JOB-LOCATION column. That is
  the headline's basis and the bar cards' basis, so a row in this table can be
  laid beside either without a footnote.
* The grouping column is chosen from a closed list and never from the request.
* The period is calendar-aligned and computed by one pure function.
* The page carries its config on data- attributes (Autoptimize, CLAUDE.md
  gotcha #10), the view lives in the query string and is restored on load, and
  a bare URL stays bare.
* At 375px the table scrolls inside its own container with the place pinned,
  and the two key numbers come first.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
INC = PLUGIN / "includes/by-location.php"
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8")
DB = (PLUGIN / "includes/db.php").read_text(encoding="utf-8")
TPL = (PLUGIN / "templates/page-tracker.php").read_text(encoding="utf-8")
JS = (PLUGIN / "assets/layoffs.js").read_text(encoding="utf-8")
CSS = (PLUGIN / "assets/layoffs.css").read_text(encoding="utf-8")


def src():
    return INC.read_text(encoding="utf-8")


def card_markup():
    start = TPL.index('id="alt-loc-card"')
    start = TPL.rindex("<div", 0, start)
    end = TPL.index("<!-- /alt-loc-card -->", start)
    return TPL[start:end]


class Route(unittest.TestCase):
    def test_route_is_registered_public_get_and_cached(self):
        s = src()
        self.assertIn("register_rest_route('layoffs/v1', '/by-location'", s)
        self.assertIn("'methods'  => 'GET'", s)
        self.assertIn("'permission_callback' => '__return_true'", s)
        self.assertRegex(s, r"return alt_api_cached\('by_location', \$r,")

    def test_include_is_guarded_for_the_ftps_race(self):
        self.assertRegex(MAIN, r"is_readable\(\$alt_by_location\)\)\s*\{\s*require_once \$alt_by_location;")

    def test_where_comes_from_the_shared_builder(self):
        s = src()
        self.assertIn("alt_db_where(", s)
        self.assertNotRegex(s, r"get_param\('(country|state|industry|years)'\)",
                            "the table must not parse filters itself")

    def test_basis_is_verified_superset_folded_job_location(self):
        s = src()
        self.assertIn("superset_of = 0", s)
        self.assertIn("announced = 0", s)
        self.assertIn("ai_explicit = 1", s)
        self.assertNotIn("employer_country", s.split("function alt_by_location_views")[1].split("}")[0])
        self.assertIn("'basis'", s)

    def test_group_column_is_a_closed_list(self):
        s = src()
        body = s.split("function alt_by_location_views")[1].split("\n}")[0]
        self.assertIn("'country' => 'country'", body)
        self.assertIn("'state'   => 'state'", body)
        # city: the table has no city column, so the switch must not offer one.
        self.assertNotIn("city", body)
        self.assertNotRegex(s, r"\$col\s*=\s*\$r->get_param", "column taken from the request")

    def test_its_params_shape_the_cache_key(self):
        body = DB.split("function alt_cached_route_param_names")[1].split("\n}")[0]
        for name in ("view", "period"):
            self.assertIn(f"'{name}'", body, f"{name} would be dropped from the cache key")

    def test_period_and_view_reads_are_whitelisted(self):
        read = set(re.findall(r"get_param\('([a-z_]+)'\)", src()))
        self.assertTrue(read <= {"view", "period", "date_basis"}, read)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: no php binary to execute the period function")
class PeriodBounds(unittest.TestCase):
    def bounds(self, period, today):
        code = (
            "function add_action(){} function register_rest_route(){}"
            f"require '{INC}';"
            f"echo json_encode(alt_by_location_period_bounds('{period}', '{today}'));"
        )
        out = subprocess.run(["php", "-r", code], capture_output=True, text=True, check=True).stdout
        import json
        return json.loads(out)

    def test_calendar_aligned(self):
        # 2026-10-19 is a Monday; 2026-10-22 a Thursday.
        self.assertEqual(self.bounds("week", "2026-10-22"), ["2026-10-19", "2026-10-22"])
        self.assertEqual(self.bounds("week", "2026-10-19"), ["2026-10-19", "2026-10-19"])
        self.assertEqual(self.bounds("month", "2026-10-19"), ["2026-10-01", "2026-10-19"])
        self.assertEqual(self.bounds("quarter", "2026-10-19"), ["2026-10-01", "2026-10-19"])
        self.assertEqual(self.bounds("quarter", "2026-08-05"), ["2026-07-01", "2026-08-05"])
        self.assertEqual(self.bounds("ytd", "2026-10-19"), ["2026-01-01", "2026-10-19"])
        self.assertEqual(self.bounds("all", "2026-10-19"), [None, None])

    def test_unknown_period_is_the_default_not_everything(self):
        self.assertEqual(self.bounds("bogus", "2026-10-19"), ["2026-01-01", "2026-10-19"])


class Markup(unittest.TestCase):
    def test_card_sits_under_where_the_cuts_are(self):
        where = TPL.index("<h2>Where the cuts are</h2>")
        card = TPL.index('id="alt-loc-card"')
        trending = TPL.index("alt-grid-h", where + 10)
        self.assertTrue(where < card < trending)

    def test_switch_period_sort_and_copy_controls(self):
        m = card_markup()
        for view in ("country", "state"):
            self.assertIn(f'data-loc-view="{view}"', m)
        self.assertNotIn('data-loc-view="city"', m)
        for p in ("week", "month", "quarter", "ytd", "all"):
            self.assertIn(f'value="{p}"', m)
        for k in ("place", "jobs", "ai_jobs", "events", "ai_events"):
            self.assertIn(f'data-loc-sort="{k}"', m)
        self.assertIn('id="alt-loc-copy"', m)
        self.assertIn('id="alt-loc-more"', m)
        self.assertIn('aria-sort', m)

    def test_config_rides_on_data_attributes(self):
        m = card_markup()
        self.assertIn('data-loc-route="by-location"', m)
        self.assertIn('data-loc-top="25"', m)

    def test_two_key_numbers_come_first(self):
        m = card_markup()
        order = [m.index(f'data-loc-sort="{k}"') for k in ("place", "jobs", "ai_jobs", "events", "ai_events")]
        self.assertEqual(order, sorted(order))

    def test_copy_has_no_em_dash_and_no_typed_cadence(self):
        text = re.sub(r"<\?php.*?\?>", "", card_markup(), flags=re.S)
        self.assertNotIn("—", text)
        self.assertNotIn("&mdash;", text)
        self.assertNotRegex(text.lower(), r"twice daily|once daily|every day|hourly|daily")

    def test_basis_is_stated_to_the_reader(self):
        m = card_markup().lower()
        self.assertIn("verified", m)
        self.assertIn("where the jobs are", m)


class Script(unittest.TestCase):
    def block(self):
        start = JS.index("BY LOCATION TABLE")
        return JS[start:JS.index("END BY LOCATION TABLE", start)]

    def test_reads_config_from_the_card_not_a_new_global(self):
        b = self.block()
        self.assertIn("getAttribute('data-loc-route')", b)
        self.assertNotIn("window.altLoc", b)

    def test_row_tap_uses_the_existing_filter_mechanism(self):
        b = self.block()
        self.assertIn("ensureOption(", b)
        self.assertIn("toggleMultiFilter(", b)
        self.assertIn("refreshAll()", b)

    def test_state_lives_in_the_query_string_and_is_restored(self):
        b = self.block()
        for p in ("loc", "loc_period", "loc_sort", "loc_dir", "loc_all"):
            self.assertIn(f"'{p}'", b)
        self.assertIn("restoreLocFromUrl", JS.split("restoreFiltersFromUrl();", 1)[1][:400])
        sync = JS.split("function syncUrlFromFilters()")[1][:900]
        self.assertIn("locQueryParams()", sync)

    def test_a_default_view_adds_nothing_to_the_url(self):
        b = self.block()
        self.assertIn("LOC_DEFAULTS", b)
        self.assertRegex(b, r"if \(LOC\.\w+ !== LOC_DEFAULTS\.\w+\)")

    def test_refresh_reloads_the_table(self):
        body = JS.split("function refreshAll()")[1][:700]
        self.assertIn("loadLocations()", body)

    def test_copy_link_uses_the_clipboard_with_a_fallback(self):
        b = self.block()
        self.assertIn("navigator.clipboard", b)
        self.assertIn("fallbackCopy", b)

    def test_rows_are_escaped(self):
        self.assertIn("escapeHtml(", self.block())


class Style(unittest.TestCase):
    def rule(self, selector):
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
        self.assertIsNotNone(m, selector)
        return m.group(1)

    def test_table_scrolls_inside_its_own_container(self):
        r = self.rule(".alt-wrap .alt-loc-scroll")
        self.assertIn("overflow-x: auto", r)
        self.assertIn("max-width: 100%", r)

    def test_place_column_is_pinned(self):
        r = self.rule(".alt-wrap .alt-loc-table th:first-child,\n.alt-wrap .alt-loc-table td:first-child")
        self.assertIn("position: sticky", r)
        self.assertIn("left: 0", r)
        self.assertIn("var(--alt-surface)", r)

    def test_colours_are_tokens_scoped_above_the_site_override(self):
        block = CSS[CSS.index("/* BY LOCATION TABLE"):CSS.index("/* END BY LOCATION TABLE")]
        self.assertNotRegex(block, r"#[0-9a-fA-F]{3,6}\b", "literal colour: dark mode cannot reach it")
        self.assertIn("color: var(--alt-ink)", block)

    def test_card_spans_the_grid(self):
        self.assertIn("grid-column: 1 / -1", self.rule(".alt-wrap .alt-loc-card"))


if __name__ == "__main__":
    unittest.main()
