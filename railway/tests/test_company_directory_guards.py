"""Static guardrails for the WordPress company-directory foundation.

PHP is linted by deployment CI, but these tests make the publication safeguards
hard to remove accidentally while local PHP is unavailable.
"""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
MODULE = (PLUGIN / "includes/company-directory.php").read_text()
TEMPLATE = (PLUGIN / "templates/page-company-directory.php").read_text()
DB_PHP = (PLUGIN / "includes/db.php").read_text()
ENTRY_TEMPLATE = (PLUGIN / "templates/single-layoff.php").read_text()
HEALTH_TEMPLATE = (PLUGIN / "templates/page-health.php").read_text()


class CompanyDirectoryGuardTests(unittest.TestCase):
    def test_directory_requires_reviewed_registry_status(self):
        self.assertIn("review_status IN ('approved','noindex')", MODULE)
        self.assertIn("company_key", MODULE)

    def test_directory_reads_canonical_events_with_retained_source_urls(self):
        self.assertIn("e.canonical_layoff_id = l.id", MODULE)
        self.assertIn("EXISTS (SELECT 1 FROM $reports", MODULE)
        self.assertIn("source_url <> ''", MODULE)

    def test_low_value_pages_are_not_indexable(self):
        # The literal `>= 2` moved into alt_company_directory_indexable_floor()
        # so admission, the sitemap and the page share one number; the floor's
        # value and its application are pinned by ThinContentFloorTests below.
        self.assertIn("count($event_rows) >= alt_company_directory_indexable_floor()", MODULE)
        self.assertIn("function alt_company_directory_indexable_floor() { return 2; }", MODULE)
        self.assertIn("noindex,follow", MODULE)

    def test_unknown_or_unreviewed_slugs_are_not_rendered(self):
        self.assertIn("$wp_query->set_404()", MODULE)

    def test_template_lists_retained_sources_and_warn_link_caveat(self):
        self.assertIn("$alt_event['sources']", TEMPLATE)
        self.assertIn("official WARN list", TEMPLATE)
        self.assertIn("noopener nofollow", TEMPLATE)


class RowsComeThroughTheQueryLayerTests(unittest.TestCase):
    """The page must not re-derive filter semantics in its own SQL.

    It did, and that is how it became the one surface that never learned about
    supersets: a reconciled rollup row and the per-site rows it absorbed were
    both listed AND both summed into the page total, while /aggregate, the
    report pages and the press page had all been appending `superset_of = 0`
    for months.
    """

    def test_events_are_fetched_through_the_query_endpoint(self):
        self.assertIn("alt_api_query_compute(", MODULE,
                      "company page rows must come from the shared query layer, "
                      "not hand-written SQL that has to re-learn every filter rule")

    def test_the_page_asks_for_count_once_and_sourced_semantics(self):
        for param in ("'company_key'", "'sourced'", "'exclude_supersets'"):
            self.assertIn(param, MODULE,
                          f"the page must request {param} explicitly; these are "
                          f"the filters that make its rows exact, evidenced and "
                          f"counted once")

    def test_exact_identity_not_substring_match(self):
        # `company` is a LIKE match: a page keyed on it publishes Metabolix's
        # cuts under the heading "Meta layoffs".
        self.assertIn("'company_key'       => (string) $company_key,", MODULE)
        self.assertNotIn("'company' =>", MODULE)

    def test_the_three_filters_are_really_implemented(self):
        for clause in ("company_key IN (", "superset_of = 0", "canonical_layoff_id = $self"):
            self.assertIn(clause, DB_PHP,
                          f"alt_db_where must actually implement {clause!r}; a "
                          f"param the query builder never reads is silently "
                          f"ignored and returns the UNFILTERED corpus")

    def test_correlated_filter_is_alias_safe(self):
        # MySQL hides the real table name once an alias is given, so a
        # correlated reference to wp_alt_layoffs inside /conversion's
        # `FROM $table a` is an unknown-column error, not a wrong number.
        self.assertIn("function alt_db_where(WP_REST_Request $r, $except = '', $alias = '')", DB_PHP)
        self.assertIn("alt_db_where($r, 'date', 'a')", DB_PHP)


class ThinContentFloorTests(unittest.TestCase):
    """A floor that is written down, applied, and explained on the page."""

    def test_floor_is_one_named_constant(self):
        self.assertIn("function alt_company_directory_indexable_floor()", MODULE,
                      "the floor must have ONE definition; three copies of '2' "
                      "is how the admission gate, the sitemap and the page "
                      "start disagreeing about which pages are indexed")

    def test_indexability_uses_the_named_floor(self):
        self.assertIn("count($event_rows) >= alt_company_directory_indexable_floor()", MODULE)

    def test_below_floor_pages_are_noindex_and_not_deleted(self):
        self.assertIn("noindex,follow", MODULE)
        # `follow` is the point: the links out of a thin page are why it is kept.
        self.assertIn("'follow'", MODULE)

    def test_the_reasoning_is_recorded_in_the_code(self):
        for phrase in ("THIN-CONTENT FLOOR", "near-duplicate", "doorway"):
            self.assertIn(phrase, MODULE,
                          f"the floor's reasoning must survive in the code; "
                          f"'{phrase}' is part of why it sits where it does")

    def test_the_indexer_assigns_both_statuses(self):
        # Every employer above the floor is approved and every one below is
        # noindex. Admitting everything as 'approved' is what would turn the
        # coverage increase into a mass-generated doorway set.
        self.assertIn("$indexable ? 'approved' : 'noindex'", DB_PHP)

    def test_the_page_explains_its_own_noindex_state(self):
        self.assertIn("kept out of search results", TEMPLATE)

    def test_health_page_states_the_real_threshold(self):
        # The health page publicly claimed "three or more" while the gate was
        # two (audit 2026-07-28, item 3).
        self.assertNotIn("three or more source-linked", HEALTH_TEMPLATE)
        self.assertIn("two or more such events", HEALTH_TEMPLATE)


class CoverageTests(unittest.TestCase):
    """The indexer has to be able to finish, and to say whether it did."""

    def test_indexer_is_resumable(self):
        for token in ("after_key", "next_cursor", "'complete'"):
            self.assertIn(token, DB_PHP,
                          f"the indexer must be resumable ({token}); a single "
                          f"capped run against tens of thousands of employers "
                          f"never drains the backlog")

    def test_sitemap_query_is_set_based(self):
        # The old shape ran one correlated COUNT per approved directory row.
        # Invisible at 29 companies, a timeout at thousands.
        self.assertIn("INNER JOIN ($supported) s", MODULE)

    def test_supported_event_count_has_one_definition(self):
        self.assertIn("function alt_company_directory_supported_events_sql()", MODULE)
        self.assertIn("alt_company_directory_supported_count(", DB_PHP,
                      "admission must count with the same helper the sitemap "
                      "and coverage report use")

    def test_coverage_is_publicly_checkable(self):
        self.assertIn("function alt_company_directory_coverage()", MODULE)
        self.assertIn("'coverage' =>", DB_PHP)


class SeoFundamentalsTests(unittest.TestCase):

    def test_description_is_built_from_the_data(self):
        self.assertIn("function alt_company_directory_description(", MODULE)
        for hook in ("wpseo_metadesc", "rank_math/frontend/description"):
            self.assertIn(hook, MODULE,
                          f"a core hook alone is silently replaced by whichever "
                          f"SEO plugin is active; {hook} must be covered too")

    def test_dataset_schema_only_on_indexable_pages(self):
        self.assertIn("function alt_company_directory_dataset_schema()", MODULE)
        self.assertIn("if (!$data || !$data['indexable']) return;", MODULE,
                      "structured data on a page we are telling Google to skip "
                      "is a mixed signal for no gain")

    def test_dataset_is_part_of_the_tracker_dataset(self):
        # ~1,830 identically-named Dataset nodes with no shared @id is the
        # mistake 2.19.219 fixed; a per-company node must resolve as a SLICE.
        self.assertIn("'isPartOf'", MODULE)
        self.assertIn("#dataset", MODULE)

    def test_entry_permalinks_link_back_to_their_employer(self):
        # 1,798 entry permalinks were indexable and linked from nowhere.
        self.assertIn("alt_company_directory_url_for_company", ENTRY_TEMPLATE)
        self.assertIn("function alt_company_directory_url_for_company(", MODULE)
        self.assertIn("function_exists('alt_company_directory_url_for_company')", ENTRY_TEMPLATE,
                      "keep the FTP-race guard: company-directory.php can be "
                      "mid-upload and a hard dependency would fatal the entry page")

    def test_company_page_links_out_to_the_entry_permalinks(self):
        self.assertIn("$alt_event['permalink']", TEMPLATE)


class UiCopyTests(unittest.TestCase):

    def test_no_em_dashes_in_the_rendered_copy(self):
        # House rule: em-dashes are for the code comments, never the UI.
        for name, text in (("page-company-directory.php", TEMPLATE),):
            visible = "\n".join(
                line for line in text.splitlines()
                if "//" not in line and "*" not in line.strip()[:1])
            self.assertNotIn("—", visible, f"em-dash in {name} UI copy")


if __name__ == "__main__":
    unittest.main()
