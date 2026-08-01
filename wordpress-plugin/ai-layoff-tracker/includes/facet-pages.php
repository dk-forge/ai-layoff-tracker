<?php
/**
 * Crawlable country / US state / industry pages.
 *
 * The tracker has always filtered on these three dimensions, but `?country=`,
 * `?state=` and `?industry=` returned byte-identical HTML on one canonical URL
 * (SEO audit 2026-07-28, item 1): 124 facet values and 63,000 events collapsing
 * onto a single rankable page.
 *
 * This is the company-page build (includes/company-directory.php, 2.19.233-238)
 * applied to the remaining three dimensions, and it deliberately copies that
 * file's shape rather than inventing a second one: one rewrite rule per
 * dimension, rows through alt_api_query_compute(), ONE floor helper read by the
 * page AND the sitemap, robots/canonical/title/description repeated on both SEO
 * plugins' filters, Dataset + BreadcrumbList on indexable pages only, and a
 * self-served sitemap appended to whichever SEO plugin's index is active.
 *
 * WHY THERE ARE NO CITY PAGES. The brief asked for city pages "where the data
 * supports it" and it does not. `wp_alt_layoffs` has no city column: the state
 * WARN scrapers parse a city (railway/sources/warn.py, ca_backfill.py) but fold
 * it into the free-text excerpt and deliberately keep it out of the dedup hash,
 * and alt_short_location() states in as many words that this product is
 * "deliberately NOT city-level". Generating city pages would mean parsing
 * places back out of prose, which is how a wrong place name gets published.
 */
if (!defined('ABSPATH')) exit;

/**
 * The three dimensions, and the request param each one filters on.
 *
 * The array KEY is the alt_db_where() filter param verbatim (`country`,
 * `state`, `industry`), which is what lets one code path serve all three: the
 * page never translates a dimension into a filter, it passes it straight
 * through to the shared query builder.
 */
function alt_facet_dimensions() {
    return array(
        'country' => array(
            'route'    => 'country-layoffs',
            'noun'     => 'country',
            'crumb'    => 'Layoffs by country',
            'plural'   => 'countries',
        ),
        'state' => array(
            'route'    => 'state-layoffs',
            'noun'     => 'US state',
            'crumb'    => 'Layoffs by US state',
            'plural'   => 'US states',
        ),
        'industry' => array(
            'route'    => 'industry-layoffs',
            'noun'     => 'industry',
            'crumb'    => 'Layoffs by industry',
            'plural'   => 'industries',
        ),
    );
}

/**
 * THE THIN-CONTENT FLOOR: ten source-linked canonical events to be INDEXABLE.
 *
 * Same SHAPE as alt_company_directory_indexable_floor() and deliberately not
 * the same NUMBER, because the two pages go thin for different reasons and the
 * number was measured rather than assumed.
 *
 * A company page is the only URL that assembles one employer's separate filings
 * into one history, so it starts earning its place at two events. A facet page
 * is not that: with two events it is its two company pages, restated. What it
 * uniquely offers is a DISTRIBUTION across employers, sectors and time, and
 * that only exists once there is one.
 *
 * Measured against production on 2026-08-01, at the boundary:
 *   2 events (Mexico)    -> 2 employers,  1 industry,  2 months
 *   5 events (Japan)     -> 5 employers,  4 industries, 4 months
 *  10 events (China)     -> 9 employers,  5 industries, 9 months
 *  11 events (Singapore) -> 11 employers, 7 industries, 10 months
 * At ten, every block on the page is a list rather than a restatement of the
 * one below it. Below it the page is `noindex, follow`, never absent, for the
 * company pages' reasons exactly: the events are real, the URL is the thing we
 * ask people to cite, and the links out are the point of keeping a thin page.
 *
 * Counting is by EVENT, not by job count, for the company pages' reason: a
 * job-count floor would index only the places with one enormous employer.
 *
 * Note what does NOT drive this number. The company floor also had to hold back
 * ~27,000 near-duplicate URLs, which is a mass-generated doorway set. There are
 * 124 facet values in total, so set-level suppression is not the governing risk
 * here; usefulness is. That is why this floor is set where the page stops
 * repeating itself and not higher.
 */
function alt_facet_indexable_floor() { return 10; }

/** How many events the page lists inline, newest first. */
function alt_facet_visible_rows() { return 50; }

/**
 * Every value that can have a page, as dimension => (stored value => display).
 *
 * Read from /facets (the endpoint the filter dropdowns already use) so the page
 * set and the dropdown can never disagree about what exists.
 *
 * TWO KINDS OF VALUE GET NO PAGE, both for the reason the company directory
 * refuses "Unknown Company":
 *  - "Multiple countries" is not a place. It is the honest bucket
 *    alt_normalize_country() folds "Global"/"EMEA"/"India and US" into
 *    precisely so one event is not split across countries and double counted.
 *    A page titled "Multiple countries layoffs" answers no search and would
 *    imply a jurisdiction that does not exist.
 *  - A state code alt_normalize_state() does not recognise. The column is
 *    CHAR(2) and populated only by the US WARN path; anything else in it is
 *    data damage, and damage should not mint a URL.
 */
function alt_facet_catalogue() {
    static $cache = null;
    if ($cache !== null) return $cache;
    $facets = array();
    if (function_exists('alt_api_facets')) {
        $resp = alt_api_facets(new WP_REST_Request('GET'));
        $facets = is_object($resp) && method_exists($resp, 'get_data') ? (array) $resp->get_data() : (array) $resp;
    }
    $out = array('country' => array(), 'state' => array(), 'industry' => array());
    foreach ((array) ($facets['countries'] ?? array()) as $value) {
        $value = trim((string) $value);
        if ($value === '' || $value === 'Multiple countries') continue;
        $out['country'][$value] = $value;
    }
    $names = function_exists('alt_us_state_names') ? alt_us_state_names() : array();
    foreach ((array) ($facets['states'] ?? array()) as $value) {
        $code = strtoupper(trim((string) $value));
        if ($code === '' || !isset($names[$code])) continue;
        $out['state'][$code] = $names[$code];
    }
    foreach ((array) ($facets['industries'] ?? array()) as $value) {
        $value = trim((string) $value);
        if ($value === '') continue;
        $out['industry'][$value] = $value;
    }
    $cache = $out;
    return $cache;
}

function alt_facet_slug($display) { return sanitize_title((string) $display); }

function alt_facet_url($dim, $display) {
    $dims = alt_facet_dimensions();
    if (!isset($dims[$dim])) return '';
    return home_url('/' . $dims[$dim]['route'] . '/' . rawurlencode(alt_facet_slug($display)) . '/');
}

/**
 * A requested slug -> the stored value it names, or null.
 *
 * Exact slug match first, then the project's own normalizers as ALIASES, which
 * is what makes `/country-layoffs/usa/` and `/state-layoffs/ca/` resolve at all
 * (they 301 to the canonical slug below). The normalizer result is always
 * checked back against the catalogue rather than trusted: alt_normalize_country()
 * returns an unrecognised name unchanged and alt_normalize_industry() falls back
 * to Title Case, so neither can be used as an existence test on its own.
 */
function alt_facet_resolve($dim, $slug) {
    $slug = sanitize_title((string) $slug);
    if ($slug === '') return null;
    $catalogue = alt_facet_catalogue();
    if (!isset($catalogue[$dim])) return null;
    foreach ($catalogue[$dim] as $value => $display) {
        if (alt_facet_slug($display) === $slug) {
            return array('dim' => $dim, 'value' => (string) $value, 'display' => (string) $display);
        }
    }
    $probe = str_replace('-', ' ', $slug);
    $alias = '';
    if ($dim === 'country' && function_exists('alt_normalize_country')) {
        $alias = alt_normalize_country($probe);
    } elseif ($dim === 'state' && function_exists('alt_normalize_state')) {
        $alias = alt_normalize_state($probe);
    } elseif ($dim === 'industry' && function_exists('alt_normalize_industry')) {
        $alias = alt_normalize_industry($probe);
    }
    if ($alias !== '' && isset($catalogue[$dim][$alias])) {
        return array('dim' => $dim, 'value' => (string) $alias, 'display' => (string) $catalogue[$dim][$alias]);
    }
    return null;
}

/**
 * The filter set every number and row on a facet page is computed from.
 *
 * ONE population for the whole page: the headline totals, the floor that
 * decides indexability, and the list of events all use this, so the page cannot
 * contradict itself the way a headline computed over one set and a list drawn
 * from another would.
 *
 * `sourced=1` mirrors the company pages: the page's claim is that every event
 * shown links to a filing, notice or report, so events whose sources we can no
 * longer point a reader at are out of the population, not merely hidden.
 * `exclude_supersets=1` counts a reconciled rollup and the per-site rows it
 * absorbed once.
 *
 * COUNTRY BASIS, decided and stated: the DEFAULT strict job-location basis, NOT
 * `country_basis=any`. The inclusive basis is correct where it is used and is
 * documented as intentional, but on a page titled "Layoffs in Germany" it would
 * list rows whose own country field reads "Multiple countries", and it would
 * publish a fifth number for Germany that no other surface shows. Strict
 * matches /aggregate, the report pages, the press page and the headline stats.
 * Measured 2026-08-01: the difference is +61 events for Germany and +126 for
 * the United States. The page says which basis it used and links to the
 * inclusive view in the tracker.
 */
function alt_facet_query_params($dim, $value) {
    return array(
        $dim                => (string) $value,
        'sourced'           => '1',
        'exclude_supersets' => '1',
    );
}

/**
 * Which aggregate blocks each dimension needs.
 *
 * NEVER the block for the dimension the page IS. alt_api_aggregate_compute()'s
 * $topN slicers each drop their OWN dimension from the WHERE (so a bar chart can
 * show the alternatives to the current selection), which means `top_states` on a
 * state page returns every state in the country rather than the one the page is
 * about. Asking for it would render a nationwide list under a Texas heading.
 */
function alt_facet_aggregate_blocks($dim) {
    $blocks = array('repeat_companies');
    if ($dim !== 'industry') $blocks[] = 'top_industries';
    if ($dim !== 'state')    $blocks[] = 'top_states';
    if ($dim !== 'country')  $blocks[] = 'top_countries';
    return $blocks;
}

/**
 * Per-value event counts for every facet, as dimension => value => events.
 *
 * ONE aggregate call over the same population as alt_facet_query_params(), so
 * the count that admits a page to the sitemap is the same count the page
 * itself prints. Cached against alt_data_ver: every data-changing write bumps
 * that option, so a longer TTL can never serve a number a write has superseded
 * (the reasoning alt_api_cached() already runs on), while a cold recompute is
 * three grouped queries rather than one per facet value.
 */
function alt_facet_counts() {
    static $memo = null;
    if ($memo !== null) return $memo;
    $cache_key = 'alt_facet_counts_' . md5((string) get_option('alt_data_ver', 1));
    $cached = get_transient($cache_key);
    if (is_array($cached)) { $memo = $cached; return $memo; }
    $r = new WP_REST_Request('GET');
    $r->set_query_params(array(
        'sourced' => '1', 'exclude_supersets' => '1', 'include' => 'facet_counts',
    ));
    $agg = alt_api_aggregate_compute($r);
    $counts = isset($agg['facet_counts']) && is_array($agg['facet_counts']) ? $agg['facet_counts'] : array();
    set_transient($cache_key, $counts, 6 * HOUR_IN_SECONDS);
    $memo = $counts;
    return $memo;
}

function alt_facet_count($dim, $value) {
    $counts = alt_facet_counts();
    return (int) ($counts[$dim][$value] ?? 0);
}

/**
 * Every facet that clears the floor, as a flat list ready for the sitemap and
 * for the sibling navigation on each page. Ordered by event count so the
 * strongest pages are linked first.
 */
function alt_facet_index($dim = '') {
    $out = array();
    $floor = alt_facet_indexable_floor();
    $catalogue = alt_facet_catalogue();
    foreach ($catalogue as $d => $values) {
        if ($dim !== '' && $d !== $dim) continue;
        $rows = array();
        foreach ($values as $value => $display) {
            $n = alt_facet_count($d, $value);
            if ($n < $floor) continue;
            $rows[] = array('dim' => $d, 'value' => (string) $value, 'display' => (string) $display,
                            'events' => $n, 'url' => alt_facet_url($d, $display));
        }
        usort($rows, function ($a, $b) {
            if ($a['events'] === $b['events']) return strcmp($a['display'], $b['display']);
            return $b['events'] - $a['events'];
        });
        foreach ($rows as $row) $out[] = $row;
    }
    return $out;
}

/**
 * Everything one facet page renders. Null when the slug names nothing, or
 * names something with no source-linked event at all (no page, not an empty
 * one — the company directory's rule).
 */
function alt_facet_data($dim, $slug) {
    $resolved = alt_facet_resolve($dim, $slug);
    if (!$resolved) return null;
    $value = $resolved['value'];
    $cache_key = 'alt_facet_' . md5((string) get_option('alt_data_ver', 1) . '|' . $dim . '|' . $value);
    $cached = get_transient($cache_key);
    if (is_array($cached)) return $cached;

    $base = alt_facet_query_params($dim, $value);

    $ar = new WP_REST_Request('GET');
    $ar->set_query_params(array_merge($base, array(
        'include' => implode(',', alt_facet_aggregate_blocks($dim)),
    )));
    $agg = alt_api_aggregate_compute($ar);
    $totals = isset($agg['totals']) && is_array($agg['totals']) ? $agg['totals'] : array();
    $entries = (int) ($totals['entries'] ?? 0);
    if ($entries < 1) return null;

    $qr = new WP_REST_Request('GET');
    $qr->set_query_params(array_merge($base, array(
        'sort' => 'layoff_date', 'dir' => 'desc',
        'per_page' => (string) alt_facet_visible_rows(), 'page' => '1',
    )));
    $q = alt_api_query_compute($qr);

    $events = array();
    foreach ((array) ($q['data'] ?? array()) as $row) {
        // The same source-assembly the company pages publish under, reused
        // rather than reimplemented so "every row has a source" means one thing
        // on both surfaces.
        $sources = function_exists('alt_company_directory_row_sources')
            ? alt_company_directory_row_sources($row) : array();
        if (!$sources) continue;
        $row['sources'] = $sources;
        $row['company_url'] = function_exists('alt_company_directory_url_for_company')
            ? alt_company_directory_url_for_company((string) ($row['company_name'] ?? '')) : '';
        $events[] = $row;
    }

    // Employers, as links into the company pages. Deliberately shows the ROUND
    // COUNT and not a job total: alt_api_aggregate_compute() computes
    // repeat_companies over the un-deduped WHERE on purpose (a frequency view
    // would lose real site-level filings), so its `jobs` figure can include a
    // superset member and must never be printed beside a deduped headline.
    $employers = array();
    foreach ((array) ($agg['repeat_companies'] ?? array()) as $entry) {
        $name = (string) ($entry[0] ?? '');
        if ($name === '') continue;
        $url = function_exists('alt_company_directory_url_for_company')
            ? alt_company_directory_url_for_company($name) : '';
        if ($url === '') continue;   // no page to link to, so not a link
        $employers[] = array('name' => $name, 'rounds' => (int) ($entry[1] ?? 0), 'url' => $url);
        if (count($employers) >= 12) break;
    }

    $breakdowns = array();
    foreach (array('industry' => 'top_industries', 'state' => 'top_states', 'country' => 'top_countries') as $bd => $key) {
        if ($bd === $dim || empty($agg[$key])) continue;
        $rows = array();
        foreach ((array) $agg[$key] as $entry) {
            $label = (string) ($entry[0] ?? '');
            if ($label === '') continue;
            $target = ($bd === 'state') ? strtoupper($label) : $label;
            $catalogue = alt_facet_catalogue();
            if (!isset($catalogue[$bd][$target])) continue;   // no page (e.g. "Multiple countries")
            if (alt_facet_count($bd, $target) < alt_facet_indexable_floor()) continue;
            $rows[] = array(
                'display' => (string) $catalogue[$bd][$target],
                'jobs'    => (int) ($entry[1] ?? 0),
                'url'     => alt_facet_url($bd, $catalogue[$bd][$target]),
            );
            if (count($rows) >= 10) break;
        }
        if ($rows) $breakdowns[$bd] = $rows;
    }

    $data = array(
        'dim'        => $dim,
        'value'      => $value,
        'display'    => $resolved['display'],
        'url'        => alt_facet_url($dim, $resolved['display']),
        'entries'    => $entries,
        'jobs'       => (int) ($totals['jobs'] ?? 0),
        'ai_entries' => (int) ($totals['ai_entries'] ?? 0),
        'ai_jobs'    => (int) ($totals['ai_jobs'] ?? 0),
        'companies'  => (int) ($totals['companies'] ?? 0),
        'min_date'   => (string) ($totals['min_date'] ?? ''),
        'max_date'   => (string) ($totals['max_date'] ?? ''),
        'events'     => $events,
        'shown'      => count($events),
        'employers'  => $employers,
        'breakdowns' => $breakdowns,
        'indexable'  => $entries >= alt_facet_indexable_floor(),
        'tracker_url' => add_query_arg($dim, $value, home_url('/ai-layoff-tracker/')),
    );
    set_transient($cache_key, $data, 30 * MINUTE_IN_SECONDS);
    return $data;
}

/* ------------------------------------------------------------------ */
/* Request plumbing                                                    */
/* ------------------------------------------------------------------ */

function alt_facet_is_request() {
    $dim = (string) get_query_var('alt_facet_dim');
    return $dim !== '' && isset(alt_facet_dimensions()[$dim]) && (string) get_query_var('alt_facet_slug') !== '';
}

function alt_facet_current() {
    if (!alt_facet_is_request()) return null;
    if (array_key_exists('alt_facet_current', $GLOBALS)) return $GLOBALS['alt_facet_current'];
    $GLOBALS['alt_facet_current'] = alt_facet_data(
        (string) get_query_var('alt_facet_dim'), (string) get_query_var('alt_facet_slug'));
    return $GLOBALS['alt_facet_current'];
}

function alt_facet_register_routes() {
    foreach (alt_facet_dimensions() as $dim => $meta) {
        add_rewrite_rule('^' . $meta['route'] . '/([^/]+)/?$',
            'index.php?alt_facet_dim=' . $dim . '&alt_facet_slug=$matches[1]', 'top');
    }
    add_rewrite_rule('^layoff-facets-sitemap\.xml$', 'index.php?alt_facet_sitemap=1', 'top');
}
add_action('init', 'alt_facet_register_routes', 1);

function alt_facet_query_vars($vars) {
    $vars[] = 'alt_facet_dim'; $vars[] = 'alt_facet_slug'; $vars[] = 'alt_facet_sitemap';
    return $vars;
}
add_filter('query_vars', 'alt_facet_query_vars');

function alt_facet_rewrite_flush_once() {
    if (!file_exists(ALT_PLUGIN_DIR . 'templates/page-facet.php')) return;
    if (get_option('alt_facet_rewrite_version') === ALT_VERSION) return;
    flush_rewrite_rules(false);
    update_option('alt_facet_rewrite_version', ALT_VERSION, false);
}
add_action('init', 'alt_facet_rewrite_flush_once', 99);

/**
 * Alias 301s, so `/country-layoffs/usa/` and `/state-layoffs/ca/` consolidate
 * onto the canonical slug instead of competing with it. Same loop guard as the
 * company pages: never redirect to a slug that does not round-trip
 * sanitize_title() unchanged.
 */
function alt_facet_redirect_aliases() {
    if (!alt_facet_is_request()) return;
    $dim = (string) get_query_var('alt_facet_dim');
    $slug = sanitize_title((string) get_query_var('alt_facet_slug'));
    $resolved = alt_facet_resolve($dim, $slug);
    if (!$resolved) return;
    $canonical = alt_facet_slug($resolved['display']);
    if ($canonical === '' || $canonical !== sanitize_title($canonical) || $canonical === $slug) return;
    $target = alt_facet_url($dim, $resolved['display']);
    if (!empty($_SERVER['QUERY_STRING'])) {
        $target .= '?' . sanitize_text_field(wp_unslash($_SERVER['QUERY_STRING']));
    }
    wp_safe_redirect($target, 301);
    exit;
}
add_action('template_redirect', 'alt_facet_redirect_aliases', 1);

function alt_facet_prepare_request() {
    if (!alt_facet_is_request()) return;
    if (!alt_facet_current()) {
        global $wp_query;
        $wp_query->set_404();
        status_header(404);
        if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
        nocache_headers();
        return;
    }
    if (!headers_sent()) header('Cache-Control: public, max-age=600');
}
add_action('template_redirect', 'alt_facet_prepare_request', 1);

function alt_facet_template($template) {
    if (!alt_facet_is_request() || !alt_facet_current()) return $template;
    $custom = ALT_PLUGIN_DIR . 'templates/page-facet.php';
    return file_exists($custom) ? $custom : $template;
}
add_filter('template_include', 'alt_facet_template');

/* ------------------------------------------------------------------ */
/* SEO head                                                            */
/* ------------------------------------------------------------------ */

/** "Layoffs in Germany", "Layoffs in California", "Technology layoffs". */
function alt_facet_heading($data) {
    if ($data['dim'] === 'industry') return $data['display'] . ' layoffs';
    return 'Layoffs in ' . $data['display'];
}

function alt_facet_title($data) {
    return alt_facet_heading($data) . ': source-linked record of every event we hold';
}

/**
 * Built only from what the page shows, like the company pages: a facet with no
 * AI-attributed event says nothing about AI rather than printing a zero.
 */
function alt_facet_description($data) {
    $bits = number_format((int) $data['entries']) . ' recorded layoff '
          . ($data['entries'] === 1 ? 'event' : 'events') . ' '
          . ($data['dim'] === 'industry' ? 'in the ' . $data['display'] . ' sector' : 'in ' . $data['display']);
    if ($data['min_date'] !== '' && $data['max_date'] !== '') {
        $from = substr($data['min_date'], 0, 4);
        $to = substr($data['max_date'], 0, 4);
        $bits .= ($from === $to) ? ', ' . $from : ', ' . $from . ' to ' . $to;
    }
    $bits .= '. ';
    if ((int) $data['jobs'] > 0) {
        $bits .= number_format((int) $data['jobs']) . ' jobs across '
              . number_format((int) $data['companies']) . ' employers. ';
    }
    if ((int) $data['ai_entries'] > 0) {
        $bits .= number_format((int) $data['ai_entries']) . ' of them the employer attributed to AI. ';
    }
    return $bits . 'Every entry links to the filing, WARN notice or report behind it.';
}

function alt_facet_robots($robots) {
    $data = alt_facet_current();
    if ($data && !$data['indexable']) $robots['noindex'] = true;
    return $robots;
}
add_filter('wp_robots', 'alt_facet_robots');
add_filter('wpseo_robots', function ($robots) {
    $data = alt_facet_current();
    return ($data && !$data['indexable']) ? 'noindex,follow' : $robots;
});
add_filter('rank_math/frontend/robots', function ($robots) {
    $data = alt_facet_current();
    return ($data && !$data['indexable']) ? array('noindex', 'follow') : $robots;
});

function alt_facet_canonical_filter($canonical) {
    $data = alt_facet_current();
    return $data ? ($data['indexable'] ? $data['url'] : false) : $canonical;
}
add_filter('wpseo_canonical', 'alt_facet_canonical_filter');
add_filter('rank_math/frontend/canonical', 'alt_facet_canonical_filter');

add_filter('document_title_parts', function ($parts) {
    $data = alt_facet_current();
    if ($data) $parts['title'] = alt_facet_title($data);
    return $parts;
}, 5);
function alt_facet_seo_title($title) {
    $data = alt_facet_current();
    return $data ? alt_facet_title($data) : $title;
}
add_filter('wpseo_title', 'alt_facet_seo_title', 5);
add_filter('rank_math/frontend/title', 'alt_facet_seo_title', 5);

function alt_facet_seo_description($desc) {
    $data = alt_facet_current();
    return $data ? alt_facet_description($data) : $desc;
}
add_filter('wpseo_metadesc', 'alt_facet_seo_description', 5);
add_filter('rank_math/frontend/description', 'alt_facet_seo_description', 5);

/** No-SEO-plugin fallback, guarded so we never print a second canonical. */
function alt_facet_head_fallback() {
    $data = alt_facet_current();
    if (!$data) return;
    if (defined('WPSEO_VERSION') || class_exists('RankMath')) return;
    echo '<meta name="description" content="' . esc_attr(alt_facet_description($data)) . '" />' . "\n";
    if ($data['indexable']) {
        echo '<link rel="canonical" href="' . esc_url($data['url']) . '" />' . "\n";
    } else {
        echo '<meta name="robots" content="noindex, follow" />' . "\n";
    }
}
add_action('wp_head', 'alt_facet_head_fallback', 1);

function alt_facet_breadcrumbs() {
    $data = alt_facet_current();
    if (!$data) return;
    $dims = alt_facet_dimensions();
    echo '<script type="application/ld+json">' . wp_json_encode(array(
        '@context' => 'https://schema.org',
        '@type'    => 'BreadcrumbList',
        'itemListElement' => array(
            array('@type' => 'ListItem', 'position' => 1, 'name' => 'AskTheRecruiter', 'item' => home_url('/')),
            array('@type' => 'ListItem', 'position' => 2, 'name' => 'AI Layoff Tracker', 'item' => home_url('/ai-layoff-tracker/')),
            array('@type' => 'ListItem', 'position' => 3, 'name' => $dims[$data['dim']]['crumb'], 'item' => $data['url']),
            array('@type' => 'ListItem', 'position' => 4, 'name' => alt_facet_heading($data), 'item' => $data['url']),
        ),
    ), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";
}
add_action('wp_head', 'alt_facet_breadcrumbs', 21);

/**
 * Dataset node, indexable pages only, `isPartOf` the tracker's dataset so this
 * reads as a slice of it and not a rival dataset with the same name — the
 * mistake that put ~1,830 identical Dataset nodes on the site before 2.19.219.
 */
function alt_facet_dataset_schema() {
    $data = alt_facet_current();
    if (!$data || !$data['indexable']) return;
    $node = array(
        '@context'    => 'https://schema.org',
        '@type'       => 'Dataset',
        '@id'         => $data['url'] . '#dataset',
        'name'        => alt_facet_heading($data) . ': recorded events',
        'description' => alt_facet_description($data),
        'url'         => $data['url'],
        'isPartOf'    => array('@id' => home_url('/ai-layoff-tracker/') . '#dataset'),
        'creator'     => array('@type' => 'Organization', 'name' => 'AskTheRecruiter'),
        'license'     => 'https://creativecommons.org/licenses/by/4.0/',
        'isAccessibleForFree' => true,
    );
    if ($data['min_date'] !== '' && $data['max_date'] !== '') {
        $node['temporalCoverage'] = $data['min_date'] . '/' . $data['max_date'];
    }
    if ($data['dim'] === 'country') {
        $node['spatialCoverage'] = $data['display'];
    } elseif ($data['dim'] === 'state') {
        $node['spatialCoverage'] = $data['display'] . ', United States';
    }
    echo '<script type="application/ld+json">' . wp_json_encode($node, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";
}
add_action('wp_head', 'alt_facet_dataset_schema', 22);

/* ------------------------------------------------------------------ */
/* Sitemap                                                             */
/* ------------------------------------------------------------------ */

function alt_facet_sitemap_url() { return home_url('/layoff-facets-sitemap.xml'); }

/**
 * ONE sitemap for all three dimensions rather than three files. The company
 * sitemap is its own file because it carries thousands of URLs; this one is
 * ~100 in total, and three sitemap-index entries for thirty URLs each is noise
 * in the index for no crawl benefit. Reads alt_facet_index(), which reads the
 * same floor the page does, so admission and rendering cannot disagree.
 */
function alt_facet_render_sitemap() {
    if ((string) get_query_var('alt_facet_sitemap') === '') return;
    if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
    status_header(200);
    header('Content-Type: application/xml; charset=UTF-8');
    header('X-Robots-Tag: noindex, follow');
    echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
    echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
    foreach (alt_facet_index() as $entry) {
        echo '  <url><loc>' . esc_url($entry['url']) . '</loc></url>' . "\n";
    }
    echo '</urlset>';
    exit;
}
add_action('template_redirect', 'alt_facet_render_sitemap', 0);

function alt_facet_sitemap_index_entry($xml) {
    if (!alt_facet_index()) return $xml;
    return $xml . '<sitemap><loc>' . esc_url(alt_facet_sitemap_url()) . '</loc></sitemap>' . "\n";
}
add_filter('wpseo_sitemap_index', 'alt_facet_sitemap_index_entry');
add_filter('rank_math/sitemap/index', 'alt_facet_sitemap_index_entry');
