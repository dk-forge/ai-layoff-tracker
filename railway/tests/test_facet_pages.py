"""Static guardrails for the country / US state / industry pages.

Same purpose and shape as test_company_directory_guards.py: PHP is linted by
deployment CI, but these make the publication safeguards hard to remove by
accident while a local PHP runtime is unavailable.

The rules pinned here are the ones whose breakage would be SILENT on a live
page: a floor that stops being one number, a slicer rendering the wrong
dimension, a page-level number computed over a different population than the
rows beneath it, and a positional tuple that another file reads by index.
"""
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
MODULE = (PLUGIN / "includes/facet-pages.php").read_text()
TEMPLATE = (PLUGIN / "templates/page-facet.php").read_text()
DB_PHP = (PLUGIN / "includes/db.php").read_text()
API_PHP = (PLUGIN / "includes/api.php").read_text()
BOOTSTRAP = (PLUGIN / "ai-layoff-tracker.php").read_text()
COMPANY = (PLUGIN / "includes/company-directory.php").read_text()
COMPANY_TEMPLATE = (PLUGIN / "templates/page-company-directory.php").read_text()
LAYOFFS_JS = (PLUGIN / "assets/layoffs.js").read_text()


class WiringTests(unittest.TestCase):
    def test_module_is_loaded_by_the_plugin(self):
        self.assertIn("require_once ALT_PLUGIN_DIR . 'includes/facet-pages.php';", BOOTSTRAP)

    def test_pages_get_the_plugin_stylesheet(self):
        # Without this the page renders unstyled: alt_page_needs_assets() is
        # is_singular()-based and a rewrite-rule route is not singular.
        self.assertIn("alt_facet_is_request()) return true;", BOOTSTRAP)

    def test_one_route_per_dimension_and_a_sitemap_route(self):
        for route in ("country-layoffs", "state-layoffs", "industry-layoffs"):
            self.assertIn("'^' . $meta['route'] . '/([^/]+)/?$'", MODULE)
            self.assertIn(route, MODULE)
        self.assertIn("^layoff-facets-sitemap\\.xml$", MODULE)

    def test_rewrite_rules_are_flushed_on_deploy(self):
        # FTP deploys never fire activation hooks, so a new rewrite rule that is
        # not flushed by a version bump 404s forever.
        self.assertIn("alt_facet_rewrite_flush_once", MODULE)
        self.assertIn("get_option('alt_facet_rewrite_version') === ALT_VERSION", MODULE)


class ThinContentFloorTests(unittest.TestCase):
    """ONE floor, read by the page AND the sitemap.

    The company pages put the literal in a helper for exactly this reason: if
    admission, the sitemap and the page each carry their own number, a URL can
    be in the sitemap while the page it points at says it is not indexable.
    """

    def test_floor_is_one_named_number(self):
        self.assertIn("function alt_facet_indexable_floor() { return 10; }", MODULE)

    def test_indexability_is_computed_from_the_floor_helper(self):
        self.assertIn("'indexable'  => $entries >= alt_facet_indexable_floor()", MODULE)

    def test_sitemap_admission_uses_the_same_helper(self):
        index_fn = MODULE.split("function alt_facet_index(")[1].split("\nfunction ")[0]
        self.assertIn("$floor = alt_facet_indexable_floor();", index_fn)
        self.assertIn("if ($n < $floor) continue;", index_fn)

    def test_below_the_floor_the_page_is_noindex_follow_not_absent(self):
        # `follow` is the point: the links out of a thin page are why it is kept.
        self.assertIn("noindex,follow", MODULE)
        self.assertIn("array('noindex', 'follow')", MODULE)
        # It still renders. A 404 would delete a record we published.
        self.assertNotIn("if (!$data['indexable']) { $wp_query->set_404", MODULE)

    def test_a_below_floor_page_explains_itself(self):
        self.assertIn("kept out of search results", TEMPLATE)
        self.assertIn("alt_facet_indexable_floor()", TEMPLATE)


class SharedQueryPathTests(unittest.TestCase):
    """No hand-written SQL in the page layer.

    Hand-written SQL is how the company page became the one surface that never
    learned about supersets. The facet pages must inherit filter semantics
    rather than re-derive them.
    """

    def test_rows_come_from_the_query_layer(self):
        self.assertIn("alt_api_query_compute(", MODULE)

    def test_stats_come_from_the_aggregate_layer(self):
        self.assertIn("alt_api_aggregate_compute(", MODULE)

    def test_the_page_module_contains_no_sql(self):
        for token in ("SELECT ", "$wpdb", "FROM $table"):
            self.assertNotIn(token, MODULE,
                             "facet pages must not query the database directly")

    def test_one_population_for_rows_floor_and_headline(self):
        # Every number and row on the page is built from alt_facet_query_params.
        self.assertIn("$base = alt_facet_query_params($dim, $value);", MODULE)
        self.assertIn("array_merge($base,", MODULE)

    def test_events_are_counted_once_and_evidence_gated(self):
        params = MODULE.split("function alt_facet_query_params(")[1].split("\n}")[0]
        self.assertIn("'sourced'           => '1'", params)
        self.assertIn("'exclude_supersets' => '1'", params)

    def test_source_assembly_is_reused_not_reimplemented(self):
        self.assertIn("alt_company_directory_row_sources(", MODULE)


class CountryBasisTests(unittest.TestCase):
    """The documented job-location vs employer-HQ split is intentional.

    country_basis=any is correct where it is used and must not be "fixed"; the
    decision recorded here is that facet pages use the STRICT default, and that
    the page says so.
    """

    def test_pages_do_not_send_the_inclusive_basis(self):
        # Checked against CODE, not prose: the decision to use the strict basis
        # is explained at length in the docblock, which names the param.
        code = re.sub(r"/\*.*?\*/", "", MODULE, flags=re.S)
        code = re.sub(r"//.*", "", code)
        self.assertNotIn("country_basis", code)

    def test_the_page_states_which_basis_it_used(self):
        self.assertIn("Counted by where the jobs were located.", TEMPLATE)
        self.assertIn("employer headquarters", TEMPLATE)


class SlicerDimensionTests(unittest.TestCase):
    """A $topN slicer drops its OWN dimension from the WHERE.

    So `top_states` on a state page returns every state in the country, not the
    one the page is about. Asking for it would render a nationwide list under a
    single state's heading.
    """

    def test_a_page_never_requests_its_own_dimension_block(self):
        fn = MODULE.split("function alt_facet_aggregate_blocks(")[1].split("\n}")[0]
        self.assertIn("if ($dim !== 'industry') $blocks[] = 'top_industries';", fn)
        self.assertIn("if ($dim !== 'state')    $blocks[] = 'top_states';", fn)
        self.assertIn("if ($dim !== 'country')  $blocks[] = 'top_countries';", fn)

    def test_breakdown_rendering_skips_the_page_dimension(self):
        self.assertIn("if ($bd === $dim || empty($agg[$key])) continue;", MODULE)


class AggregateIncludeTests(unittest.TestCase):
    """The opt-in block list must never change /aggregate's default output."""

    def test_default_is_everything_that_existed_before(self):
        self.assertIn("$include = null;", DB_PHP)
        self.assertIn("$include === null ? alt_aggregate_default_blocks() : $include", DB_PHP)

    def test_facet_counts_is_opt_in_and_not_a_default(self):
        # Three grouped COUNTs over the whole table. Defaulting it on would put
        # that cost on the flagship tracker page's cold aggregate to serve a
        # block only the facet sitemap reads.
        default = DB_PHP.split("function alt_aggregate_default_blocks()")[1].split("\n}")[0]
        self.assertNotIn("facet_counts", default)
        self.assertIn("array_merge(alt_aggregate_default_blocks(), array('facet_counts'))", DB_PHP)

    def test_an_include_naming_no_valid_block_falls_back_to_everything(self):
        self.assertIn("if ($valid) $include = $valid;", DB_PHP)

    def test_totals_are_never_optional(self):
        # Every other block is reported against totals; a caller able to drop
        # the denominator while keeping a numerator is the scope-mixing the
        # concentration block exists to prevent.
        self.assertNotIn("$want('totals')", DB_PHP)

    def test_include_is_not_a_filter_param(self):
        # alt_filter_param_names() lists params that NARROW the result set;
        # `include` selects blocks and must not make an export think it is
        # filtered (the bug that labelled a partial extract as complete).
        names = DB_PHP.split("function alt_filter_param_names()")[1].split("\n}")[0]
        self.assertNotIn("'include'", names)

    def test_every_gated_block_is_declared(self):
        declared = set()
        for fn in ("alt_aggregate_blocks", "alt_aggregate_default_blocks"):
            body = DB_PHP.split("function %s()" % fn)[1].split("\n}")[0]
            declared |= set(re.findall(r"'([a-z_]+)'", body))
        used = set(re.findall(r"\$want\('([a-z_]+)'\)", DB_PHP))
        self.assertTrue(used, "expected gated blocks")
        self.assertEqual(used - declared, set(),
                         "a block is gated by $want() but not listed in alt_aggregate_blocks()")


class FacetCountsBlockTests(unittest.TestCase):
    """facet_counts is a NAMED block, not a fourth element on the $topN triple.

    renderBarList() in layoffs.js already reads index [3] of those rows as a
    display label, and top_industries / top_states are handed to it unmapped, so
    appending a count there would silently print the event count as the name of
    a bar.
    """

    def test_counts_live_in_their_own_block(self):
        self.assertIn("'facet_counts'   => $facet_counts,", DB_PHP)
        self.assertIn("$want('facet_counts')", DB_PHP)

    def test_the_topn_triple_is_still_three_wide(self):
        topn = DB_PHP.split("$topN = function (")[1].split("};")[0]
        self.assertIn("$out[] = array($row->k, (int) $row->v, (int) $row->a);", topn)

    def test_layoffs_js_still_owns_index_three(self):
        # If this ever stops being true the guard above can be revisited; while
        # it holds, the tuple must not grow.
        self.assertIn("countryFlag(e[0]) + e[0]", LAYOFFS_JS)

    def test_counts_are_events_not_jobs(self):
        block = DB_PHP.split("$facet_counts = array();")[1].split("// Reason breakdown")[0]
        self.assertIn("COUNT(*) n", block)
        self.assertNotIn("SUM(job_count)", block)

    def test_counts_are_superset_deduped(self):
        block = DB_PHP.split("$facet_counts = array();")[1].split("// Reason breakdown")[0]
        self.assertIn("WHERE $where_dd", block)


class NoCityPagesTests(unittest.TestCase):
    """City pages were asked for and the data does not support them."""

    def test_the_absence_is_explained_rather_than_silent(self):
        self.assertIn("WHY THERE ARE NO CITY PAGES", MODULE)

    def test_there_is_still_no_city_column(self):
        schema = DB_PHP.split("CREATE TABLE")[1].split(") $charset")[0]
        self.assertNotIn(" city ", schema.lower())

    def test_short_location_is_still_not_city_level(self):
        self.assertIn("Deliberately NOT city-level", DB_PHP)


class IdentityGateTests(unittest.TestCase):
    def test_multiple_countries_gets_no_page(self):
        # It is the honest bucket for "Global"/"EMEA"/"India and US", not a
        # place, and normalize folds real multi-country events into it
        # specifically so they are not split and double counted.
        self.assertIn("$value === 'Multiple countries') continue;", MODULE)

    def test_unrecognised_state_codes_get_no_page(self):
        self.assertIn("!isset($names[$code])) continue;", MODULE)

    def test_state_names_have_one_definition(self):
        self.assertIn("function alt_us_state_names()", API_PHP)
        press = (PLUGIN / "templates/page-press.php").read_text()
        self.assertNotIn("'AL'=>'Alabama'", press,
                         "page-press.php must use alt_us_state_names(), not its own copy")
        self.assertEqual(press.count("alt_us_state_names()"), 2)

    def test_aliases_are_checked_back_against_the_catalogue(self):
        # alt_normalize_country() returns unknown names unchanged and
        # alt_normalize_industry() falls back to Title Case, so neither is an
        # existence test on its own.
        self.assertIn("if ($alias !== '' && isset($catalogue[$dim][$alias]))", MODULE)


class SeoHeadTests(unittest.TestCase):
    """Every robots/canonical/title decision repeated on the SEO plugin filter.

    A core hook alone is silently replaced by whichever plugin is active; that
    is how the health page served `follow, index` for months.
    """

    def test_robots_is_repeated_on_both_plugins(self):
        for hook in ("wp_robots", "wpseo_robots", "rank_math/frontend/robots"):
            self.assertIn(hook, MODULE)

    def test_canonical_and_title_and_description_are_repeated(self):
        for hook in ("wpseo_canonical", "rank_math/frontend/canonical",
                     "wpseo_title", "rank_math/frontend/title",
                     "wpseo_metadesc", "rank_math/frontend/description"):
            self.assertIn(hook, MODULE)

    def test_noindex_pages_do_not_emit_a_canonical(self):
        self.assertIn("$data['indexable'] ? $data['url'] : false", MODULE)

    def test_dataset_is_a_slice_of_the_tracker_not_a_rival(self):
        self.assertIn("'isPartOf'    => array('@id' => home_url('/ai-layoff-tracker/') . '#dataset')", MODULE)

    def test_dataset_is_not_emitted_below_the_floor(self):
        schema = MODULE.split("function alt_facet_dataset_schema()")[1].split("\n}")[0]
        self.assertIn("if (!$data || !$data['indexable']) return;", schema)

    def test_sitemap_is_itself_noindex(self):
        self.assertIn("header('X-Robots-Tag: noindex, follow');", MODULE)

    def test_sitemap_is_registered_with_whichever_plugin_is_active(self):
        self.assertIn("add_filter('wpseo_sitemap_index', 'alt_facet_sitemap_index_entry');", MODULE)
        self.assertIn("add_filter('rank_math/sitemap/index', 'alt_facet_sitemap_index_entry');", MODULE)


class InterlinkTests(unittest.TestCase):
    def test_pages_link_to_company_pages(self):
        self.assertIn("alt_company_directory_url_for_company(", MODULE)

    def test_employer_links_are_dropped_when_there_is_no_page(self):
        self.assertIn("if ($url === '') continue;   // no page to link to, so not a link", MODULE)

    def test_company_pages_link_back_into_the_facet_mesh(self):
        self.assertIn("alt_facet_url(", COMPANY)
        self.assertIn("$alt_dir['facet_links']", COMPANY_TEMPLATE)

    def test_company_pages_never_link_to_a_thin_facet(self):
        self.assertIn("alt_facet_count($dim, $top) < alt_facet_indexable_floor()", COMPANY)

    def test_breakdown_links_never_point_below_the_floor(self):
        self.assertIn("if (alt_facet_count($bd, $target) < alt_facet_indexable_floor()) continue;", MODULE)

    def test_sibling_navigation_makes_the_set_a_connected_mesh(self):
        self.assertIn("alt_facet_index($alt_f['dim'])", TEMPLATE)

    def test_state_pages_link_up_to_their_country(self):
        self.assertIn("alt_facet_url('country', 'United States')", TEMPLATE)


class NumbersDiscipline(unittest.TestCase):
    def test_employer_rounds_are_printed_not_their_job_total(self):
        # repeat_companies is computed over the UN-deduped WHERE on purpose, so
        # its jobs figure can include a row already folded into a rollup and
        # must never be printed beside a deduped headline.
        self.assertIn("recorded rounds", TEMPLATE)
        self.assertIn("'rounds' => (int) ($entry[1] ?? 0)", MODULE)
        self.assertNotIn("$alt_emp['jobs']", TEMPLATE)

    def test_a_truncated_list_says_so(self):
        self.assertIn("if ((int) $alt_f['entries'] > (int) $alt_f['shown'])", TEMPLATE)
        self.assertIn("most\n        recent of", TEMPLATE)

    def test_zero_values_produce_no_sentence(self):
        # A facet with no AI-attributed event says nothing about AI rather than
        # printing a zero, the company pages' rule.
        self.assertIn("if ((int) $alt_f['ai_entries'] > 0)", TEMPLATE)
        self.assertIn("if ((int) $data['ai_entries'] > 0)", MODULE)


class RenderingTests(unittest.TestCase):
    """The defects that only rendering the page can find, pinned by cause."""

    def test_the_warn_note_is_said_once_per_page(self):
        # It printed 316 times on Boeing before 2.19.238.
        self.assertEqual(TEMPLATE.count("official\n    WARN list"), 1)
        self.assertIn("break 2;", TEMPLATE)

    def test_two_warn_links_name_their_destinations(self):
        self.assertIn("' (data file)'", TEMPLATE)
        self.assertIn("' (state page)'", TEMPLATE)

    def test_link_grid_cannot_bleed_the_page(self):
        css = (PLUGIN / "assets/layoffs.css").read_text()
        block = css.split("Country / state / industry pages")[1]
        # A grid track's default min-width is auto, so one long employer name
        # would widen the track past the viewport without this.
        self.assertIn("repeat(2, minmax(0, 1fr))", block)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", block)
        # The value keeps its width and the NAME truncates; without this both
        # children shrink in proportion and the value's text spills (2.19.220).
        self.assertIn(".alt-facet-links-val { flex: 0 0 auto;", block)

    def test_country_names_taking_the_article_get_it(self):
        # Live at 2.19.241 the H1, <title> and meta description of the biggest
        # page in the set all read "Layoffs in United States".
        self.assertIn("'United States', 'United Kingdom', 'Netherlands', 'Philippines'", MODULE)
        self.assertIn("return 'Layoffs in ' . alt_facet_phrase(", MODULE)
        self.assertIn("alt_facet_phrase($alt_f['dim'], $alt_f['display'])", TEMPLATE)

    def test_plurals_agree_with_their_counts(self):
        # Live at 2.19.239: "4,000 jobs across 1 employers".
        self.assertIn("=== 1 ? ' employer. ' : ' employers. '", MODULE)
        self.assertIn("=== 1 ? 'employer' : 'employers'", TEMPLATE)

    def test_no_em_dashes_in_rendered_copy(self):
        rendered = re.sub(r"<\?php.*?\?>", "", TEMPLATE, flags=re.S)
        rendered = re.sub(r"//.*", "", rendered)
        self.assertNotIn("—", rendered)


class DocumentShellTests(unittest.TestCase):
    """get_header() in a BLOCK theme loads wp-includes/theme-compat/header.php.

    That legacy shim printed a second <title> and an <h1> containing the SITE
    NAME above the page's own <h1>, and rendered no site header, footer or
    navigation at all. It shipped on every company page from 2.19.233 and was
    invisible to the status code, the sitemap count and every assertion about
    the body content.
    """

    def test_both_templates_use_the_shared_shell(self):
        for template in (TEMPLATE, COMPANY_TEMPLATE):
            self.assertIn("alt_render_page_header();", template)
            self.assertIn("alt_render_page_footer();", template)
            self.assertNotIn("\nget_header();", template)
            self.assertNotIn("get_footer(); ?>", template)

    def test_block_themes_get_the_real_header_and_footer_parts(self):
        self.assertIn("block_template_part('header');", BOOTSTRAP)
        self.assertIn("block_template_part('footer');", BOOTSTRAP)

    def test_classic_themes_still_use_get_header(self):
        self.assertIn("get_header();\n        return;", BOOTSTRAP)
        self.assertIn("get_footer();\n        return;", BOOTSTRAP)

    def test_the_shell_still_runs_wp_head_and_wp_footer(self):
        # The SEO plugin, the canonical and our stylesheet all hang off these.
        self.assertIn("wp_head();", BOOTSTRAP)
        self.assertIn("wp_footer();", BOOTSTRAP)

    def test_the_shell_does_not_add_a_second_viewport(self):
        shell = BOOTSTRAP.split("function alt_render_page_header()")[1].split("\n}")[0]
        self.assertNotIn("viewport", shell.split("//")[0])

    def test_the_shell_degrades_rather_than_fatals(self):
        self.assertIn("!function_exists('block_template_part')", BOOTSTRAP)


if __name__ == "__main__":
    unittest.main()
