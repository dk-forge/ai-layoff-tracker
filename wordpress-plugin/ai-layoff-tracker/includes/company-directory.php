<?php
/** Source-linked company-directory foundation. */
if (!defined('ABSPATH')) exit;

function alt_company_directory_is_request() { return (string) get_query_var('alt_company_layoffs_slug') !== ''; }
function alt_company_directory_source_url($url) {
    $url = esc_url_raw((string) $url);
    return preg_match('#^https?://#i', $url) ? $url : '';
}
function alt_company_directory_url($slug) { return home_url('/company-layoffs/' . rawurlencode((string) $slug) . '/'); }

/**
 * The ONE canonical directory row for a company_key.
 *
 * SCOPE (audit 2026-07-28): the directory table carries UNIQUE KEY company_key,
 * so two rows can never share a key TODAY - this helper and the 301 below are
 * a guard for the day that constraint is relaxed or bypassed, not a fix for
 * the observed Meta/Meta-Platforms pair. That pair holds two DIFFERENT stale
 * keys (layoff rows keep the company_key computed at write time; nothing
 * re-normalizes history when an alias is added), so merging it requires the
 * entity re-key repair tracked in HANDOFF.md, not URL canonicalisation.
 *
 * Aliases mean several directory rows can share a company_key ("Meta" and
 * "Meta Platforms" both key to `meta`). Because the page gathers events BY
 * company_key, every such row renders byte-identical content at a different
 * URL — duplicate content that splits ranking signals and looks sloppy to a
 * reporter. Both were live in the sitemap (audit 2026-07-27).
 *
 * The winner is deterministic and stable: approved outranks noindex, then the
 * shortest slug (the plain brand name, "meta" over "meta-platforms"), then the
 * lowest id as a final tiebreak so the choice never flips between requests.
 */
function alt_company_directory_canonical_slug($company_key) {
    global $wpdb;
    $company_key = (string) $company_key;
    if ($company_key === '') return '';
    $directory = alt_company_directory_table();
    $slug = $wpdb->get_var($wpdb->prepare(
        "SELECT slug FROM $directory
         WHERE company_key = %s AND review_status IN ('approved','noindex')
         ORDER BY (review_status = 'approved') DESC, CHAR_LENGTH(slug) ASC, id ASC
         LIMIT 1", $company_key));
    return (string) $slug;
}

/**
 * THE THIN-CONTENT FLOOR: two source-linked canonical events to be INDEXABLE.
 *
 * Below it the page is still built and still returns 200 — it is `noindex,
 * follow`, not absent. That distinction is the whole policy, so it is worth
 * writing down why each half is the way it is.
 *
 * Why the page EXISTS below the floor: the employer is real, the event is real,
 * and the URL is the stable thing we ask people to cite. Deleting it would 404
 * a record we published, and it is the page that carries a reader from a single
 * entry permalink back into the tracker. `follow` is deliberate: the links out
 * of a thin page are the point of keeping it.
 *
 * Why it is NOT indexable below the floor: with one event this page shows what
 * the entry permalink and the tracker row already show, in the same words. That
 * is a near-duplicate, and ~33k of them would be a mass-generated doorway set,
 * which is the pattern that costs a domain its standing (the same reasoning
 * that keeps weekly report pulses out of the index in report-seo.php).
 *
 * Why TWO and not three or five: at two the page starts doing something no
 * other URL on the site does — it is the only place that assembles one
 * employer's separate filings into one history, which is exactly what someone
 * searching "<company> layoffs" is looking for. A higher floor would exclude
 * pages that genuinely answer the question. Counting is deliberately by EVENT,
 * not by job count: a small employer's two documented notices are a real
 * record, and a job-count floor would just index the big companies.
 */
function alt_company_directory_indexable_floor() { return 2; }

/**
 * The employer's events, THROUGH THE QUERY LAYER.
 *
 * This used to be hand-written SQL, which is how the page ended up as the one
 * surface that never learned about supersets: /aggregate, the report pages and
 * the press page all append `superset_of = 0`, and this did not — so an
 * employer whose company-wide news total had been reconciled against its own
 * per-site WARN rows had BOTH shown here and BOTH summed into the page total.
 * Going through alt_api_query_compute() means the page inherits the filter
 * semantics rather than re-deriving them, and each row arrives in the same
 * shape /query serves (permalink, additional_sources, archived URLs included).
 *
 * Paged rather than capped at one request: an employer that legally filed a
 * notice per site can have hundreds of events (Boeing has ~324), and showing
 * the first 200 while printing a total computed from all of them is how a page
 * ends up contradicting itself. MAX_ROWS is a safety ceiling, not an expected
 * outcome; when it is hit the template says so instead of quietly truncating.
 */
function alt_company_directory_event_rows($company_key) {
    $per_page = 200;              // alt_api_query_compute's own hard cap
    $max_rows = 1000;             // safety ceiling for a pathological employer
    $rows = array();
    $total = 0;
    for ($page = 1; count($rows) < $max_rows; $page++) {
        $r = new WP_REST_Request('GET');
        $r->set_query_params(array(
            'company_key'       => (string) $company_key,
            'sourced'           => '1',
            'exclude_supersets' => '1',
            'sort'              => 'layoff_date',
            'dir'               => 'desc',
            'per_page'          => (string) $per_page,
            'page'              => (string) $page,
        ));
        $out = alt_api_query_compute($r);
        $batch = (isset($out['data']) && is_array($out['data'])) ? $out['data'] : array();
        $total = (int) ($out['total'] ?? 0);
        if (!$batch) break;
        foreach ($batch as $row) { $rows[] = $row; }
        if (count($batch) < $per_page) break;
    }
    return array('rows' => $rows, 'total' => $total);
}

/**
 * Every retained source for a row, as {name, type, url}. The row's own primary
 * link first, then the other reports on the same event that /query already
 * attached as `additional_sources`. Duplicates collapse; a row that ends up
 * with no reachable URL is dropped by the caller, because "every row here has a
 * source" is the page's entire claim.
 */
function alt_company_directory_row_sources(array $row) {
    $out = array(); $seen = array();
    $push = function ($name, $type, $url) use (&$out, &$seen) {
        $url = alt_company_directory_source_url($url);
        if ($url === '' || isset($seen[$url])) return;
        $seen[$url] = true;
        $out[] = array('name' => sanitize_text_field((string) $name),
                       'type' => sanitize_key((string) $type),
                       'url'  => $url);
    };
    $push($row['source_name'] ?? '', $row['source_type'] ?? '', $row['source_url'] ?? '');
    if (!empty($row['source_list_url'])) {
        $push($row['source_name'] ?? '', 'warn', $row['source_list_url']);
    }
    foreach ((array) ($row['additional_sources'] ?? array()) as $extra) {
        $push($extra['source_name'] ?? '', $extra['source_type'] ?? '', $extra['source_url'] ?? '');
    }
    return $out;
}

/**
 * The company page for a raw company NAME, or '' when that employer has none.
 *
 * Normalizes through alt_company_key() rather than slugging the name, because
 * the key is what groups an employer's filings ("Boeing", "Boeing Company" and
 * "The Boeing Co" are one key and one page) and sanitize_title() on the raw
 * name would miss two of the three. Used by the entry permalinks to link back
 * up to their employer, which is the link those pages never had.
 */
function alt_company_directory_url_for_company($company_name) {
    $company_name = trim((string) $company_name);
    if ($company_name === '' || !function_exists('alt_company_key')) return '';
    $normalized = function_exists('alt_normalize_company_ws')
        ? alt_normalize_company_ws($company_name) : $company_name;
    $key = alt_company_key($normalized);
    if ($key === '') return '';
    $slug = alt_company_directory_canonical_slug($key);
    return $slug !== '' ? alt_company_directory_url($slug) : '';
}

function alt_company_directory_data($slug) {
    global $wpdb;
    $slug = sanitize_title((string) $slug);
    if ($slug === '') return null;
    $directory = alt_company_directory_table();
    $company = $wpdb->get_row($wpdb->prepare("SELECT * FROM $directory WHERE slug = %s AND review_status IN ('approved','noindex') LIMIT 1", $slug), ARRAY_A);
    if (!$company || empty($company['company_key'])) return null;
    $cache_key = 'alt_company_dir_' . md5((int) get_option('alt_data_ver', 1) . '|' . (int) $company['id']);
    $cached = get_transient($cache_key);
    if (is_array($cached)) return $cached;

    $fetched = alt_company_directory_event_rows($company['company_key']);
    $event_rows = array(); $total_jobs = 0; $ai_events = 0;
    $first_date = ''; $last_date = ''; $countries = array();
    // Modal country / state / industry across this employer's events, so the
    // page can link OUT to the three facet pages it belongs to. Counted rather
    // than taken from the first row: an employer's one-off notice in another
    // state should not decide which state page it points at.
    $tally = array('country' => array(), 'state' => array(), 'industry' => array());
    foreach ($fetched['rows'] as $row) {
        $sources = alt_company_directory_row_sources($row);
        if (!$sources) continue;   // no reachable source, no row on this page
        $row['sources'] = $sources;
        $event_rows[] = $row;
        $total_jobs += max(0, (int) $row['job_count']);
        if (!empty($row['ai_explicit'])) $ai_events++;
        $date = (string) ($row['layoff_date'] ?? '');
        if ($date !== '') {
            if ($first_date === '' || $date < $first_date) $first_date = $date;
            if ($last_date === '' || $date > $last_date) $last_date = $date;
        }
        $country = trim((string) ($row['country'] ?? ''));
        if ($country !== '') $countries[$country] = true;
        foreach ($tally as $dim => $_) {
            $v = trim((string) ($row[$dim === 'country' ? 'country' : $dim] ?? ''));
            if ($dim === 'state') $v = strtoupper($v);
            if ($v === '') continue;
            $tally[$dim][$v] = ($tally[$dim][$v] ?? 0) + 1;
        }
    }
    if (!$event_rows) return null;
    // Links out to the country / US state / industry pages this employer's
    // records belong to. Only to facets that HAVE an indexable page, so a
    // company page never links into a thin one, and said once at the foot of
    // the page rather than per event (the note that printed 316 times on Boeing
    // is the standing lesson here).
    $facet_links = array();
    if (function_exists('alt_facet_url') && function_exists('alt_facet_count')) {
        $catalogue = alt_facet_catalogue();
        foreach ($tally as $dim => $counts) {
            if (!$counts) continue;
            arsort($counts);
            $top = (string) key($counts);
            if (!isset($catalogue[$dim][$top])) continue;
            if (alt_facet_count($dim, $top) < alt_facet_indexable_floor()) continue;
            $facet_links[] = array(
                'display' => (string) $catalogue[$dim][$top],
                'url'     => alt_facet_url($dim, $catalogue[$dim][$top]),
            );
        }
    }
    $data = array(
        'facet_links' => $facet_links,
        'company'     => $company,
        'events'      => $event_rows,
        'total_jobs'  => $total_jobs,
        'ai_events'   => $ai_events,
        'first_date'  => $first_date,
        'last_date'   => $last_date,
        'countries'   => array_keys($countries),
        // True when the safety ceiling clipped the list, so the template can say
        // so rather than presenting a partial history as a complete one.
        'truncated'   => (int) $fetched['total'] > count($event_rows),
        'total_known' => (int) $fetched['total'],
        'indexable'   => $company['review_status'] === 'approved'
                         && count($event_rows) >= alt_company_directory_indexable_floor(),
        'url'         => alt_company_directory_url($company['slug']),
        'tracker_url' => add_query_arg('company', $company['display_name'], home_url('/ai-layoff-tracker/')),
    );
    set_transient($cache_key, $data, 5 * MINUTE_IN_SECONDS);
    return $data;
}

/**
 * The page's own meta description, built only from what the page shows. No
 * template padding: a company with three events says three, and the sentence
 * changes shape when there are no dates rather than printing an empty range.
 */
function alt_company_directory_description($data) {
    $name = $data['company']['display_name'];
    $count = count($data['events']);
    $bits = $count . ' recorded layoff ' . ($count === 1 ? 'entry' : 'entries') . ' for ' . $name;
    if ($data['first_date'] !== '' && $data['last_date'] !== '') {
        $from = substr($data['first_date'], 0, 4);
        $to = substr($data['last_date'], 0, 4);
        $bits .= ($from === $to) ? ' in ' . $from : ', ' . $from . ' to ' . $to;
    }
    $bits .= '. ';
    if ($data['total_jobs'] > 0) {
        $bits .= number_format((int) $data['total_jobs']) . ' jobs across those records. ';
    }
    if ($data['ai_events'] > 0) {
        $bits .= $data['ai_events'] . ' of them the employer attributed to AI. ';
    }
    return $bits . 'Every entry links to the filing, WARN notice or report behind it.';
}

function alt_company_directory_current() {
    if (!alt_company_directory_is_request()) return null;
    if (array_key_exists('alt_company_directory_current', $GLOBALS)) return $GLOBALS['alt_company_directory_current'];
    $GLOBALS['alt_company_directory_current'] = alt_company_directory_data(get_query_var('alt_company_layoffs_slug'));
    return $GLOBALS['alt_company_directory_current'];
}

/**
 * Send an alias URL to the canonical one with a 301, so duplicates consolidate
 * instead of competing. Runs on `template_redirect` (before output), and only
 * when the requested slug is genuinely a non-canonical alias of a real row.
 */
function alt_company_directory_redirect_aliases() {
    if (!alt_company_directory_is_request()) return;
    global $wpdb;
    $slug = sanitize_title((string) get_query_var('alt_company_layoffs_slug'));
    if ($slug === '') return;
    $directory = alt_company_directory_table();
    $key = $wpdb->get_var($wpdb->prepare(
        "SELECT company_key FROM $directory WHERE slug = %s AND review_status IN ('approved','noindex') LIMIT 1", $slug));
    if (!$key) return;
    $canonical = alt_company_directory_canonical_slug($key);
    // Loop guard: if a row ever lands with an unsanitised slug (manual insert,
    // import), redirecting to it would bounce forever between the sanitised
    // request and the raw stored value. Never redirect to a slug that does not
    // round-trip sanitize_title() unchanged.
    if ($canonical !== sanitize_title($canonical)) return;
    if ($canonical && $canonical !== $slug) {
        $target = alt_company_directory_url($canonical);
        // Keep the inbound query string (utm_* etc.) - the redirect exists to
        // consolidate referral traffic, so dropping attribution defeats it.
        if (!empty($_SERVER['QUERY_STRING'])) {
            $target .= '?' . sanitize_text_field(wp_unslash($_SERVER['QUERY_STRING']));
        }
        wp_safe_redirect($target, 301);
        exit;
    }
}
add_action('template_redirect', 'alt_company_directory_redirect_aliases', 1);

function alt_company_directory_register_route() { add_rewrite_rule('^company-layoffs/([^/]+)/?$', 'index.php?alt_company_layoffs_slug=$matches[1]', 'top'); }
add_action('init', 'alt_company_directory_register_route', 1);
function alt_company_directory_query_vars($vars) { $vars[] = 'alt_company_layoffs_slug'; return $vars; }
add_filter('query_vars', 'alt_company_directory_query_vars');

function alt_company_directory_prepare_request() {
    if (!alt_company_directory_is_request()) return;
    $data = alt_company_directory_current();
    if (!$data) {
        // A miss must never be cached: the slug becomes real the moment the
        // indexer admits that employer, and a cached 404 would outlive it.
        global $wp_query;
        $wp_query->set_404();
        status_header(404);
        if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
        nocache_headers();
        return;
    }
    // A RENDERED company page is deliberately cacheable now. It used to set
    // DONOTCACHEPAGE + nocache_headers() unconditionally, which was invisible
    // while 29 URLs existed and is a different proposition once every employer
    // has one: it makes each of tens of thousands of crawlable URLs an origin
    // request on a shared host that has already returned 504 twice in a day.
    // It never bought freshness either, since the page's own data is held in a
    // 5-minute transient regardless. Ten minutes at the edge is shorter than
    // that transient, so nothing goes staler than it already was.
    if (!headers_sent()) header('Cache-Control: public, max-age=600');
}
add_action('template_redirect', 'alt_company_directory_prepare_request', 1);
function alt_company_directory_template($template) {
    if (!alt_company_directory_is_request() || !alt_company_directory_current()) return $template;
    $custom = ALT_PLUGIN_DIR . 'templates/page-company-directory.php';
    return file_exists($custom) ? $custom : $template;
}
add_filter('template_include', 'alt_company_directory_template');

function alt_company_directory_rewrite_flush_once() {
    if (!file_exists(ALT_PLUGIN_DIR . 'templates/page-company-directory.php')) return;
    if (get_option('alt_company_directory_rewrite_version') === ALT_VERSION) return;
    flush_rewrite_rules(false); update_option('alt_company_directory_rewrite_version', ALT_VERSION, false);
}
add_action('init', 'alt_company_directory_rewrite_flush_once', 99);

function alt_company_directory_robots($robots) {
    $data = alt_company_directory_current();
    if ($data && !$data['indexable']) $robots['noindex'] = true;
    return $robots;
}
add_filter('wp_robots', 'alt_company_directory_robots');
function alt_company_directory_yoast_robots($robots) { $data = alt_company_directory_current(); return ($data && !$data['indexable']) ? 'noindex,follow' : $robots; }
add_filter('wpseo_robots', 'alt_company_directory_yoast_robots');
add_filter('rank_math/frontend/robots', function ($robots) { $data = alt_company_directory_current(); return ($data && !$data['indexable']) ? array('noindex', 'follow') : $robots; });
function alt_company_directory_canonical($canonical) { $data = alt_company_directory_current(); return $data ? ($data['indexable'] ? $data['url'] : false) : $canonical; }
add_filter('wpseo_canonical', 'alt_company_directory_canonical');
add_filter('rank_math/frontend/canonical', 'alt_company_directory_canonical');
function alt_company_directory_title($parts) { $data = alt_company_directory_current(); if ($data) $parts['title'] = $data['company']['display_name'] . ' layoffs: source-linked entry history'; return $parts; }
add_filter('document_title_parts', 'alt_company_directory_title', 5);
function alt_company_directory_seo_title($title) { $data = alt_company_directory_current(); return $data ? $data['company']['display_name'] . ' layoffs: source-linked entry history' : $title; }
add_filter('wpseo_title', 'alt_company_directory_seo_title', 5);
add_filter('rank_math/frontend/title', 'alt_company_directory_seo_title', 5);

/**
 * Meta description. Company pages had none at all (audit 2026-07-28, item 4),
 * so search engines wrote their own from whatever text came first. Repeated on
 * both SEO plugins' filters for the reason recorded in TECHLOG: a core hook
 * alone is silently replaced by whichever plugin is active.
 */
function alt_company_directory_seo_description($desc) {
    $data = alt_company_directory_current();
    return $data ? alt_company_directory_description($data) : $desc;
}
add_filter('wpseo_metadesc', 'alt_company_directory_seo_description', 5);
add_filter('rank_math/frontend/description', 'alt_company_directory_seo_description', 5);

/**
 * Fallback for an install with no SEO plugin: emit the canonical, the robots
 * meta and the description ourselves. Guarded so we never print a second
 * canonical or description alongside a plugin's own (same shape as
 * report-seo.php's fallback).
 */
function alt_company_directory_head_fallback() {
    $data = alt_company_directory_current();
    if (!$data) return;
    if (defined('WPSEO_VERSION') || class_exists('RankMath')) return;
    echo '<meta name="description" content="' . esc_attr(alt_company_directory_description($data)) . '" />' . "\n";
    if ($data['indexable']) {
        echo '<link rel="canonical" href="' . esc_url($data['url']) . '" />' . "\n";
    } else {
        echo '<meta name="robots" content="noindex, follow" />' . "\n";
    }
}
add_action('wp_head', 'alt_company_directory_head_fallback', 1);

/**
 * Dataset structured data for the pages we actually offer to the index.
 *
 * Honest on both counts. It is a Dataset because that is what the page is: a
 * bounded set of records with a temporal range, a publisher and a licence.
 * `about` is an Organization naming the EMPLOYER, which says the dataset is
 * about that company — it does not claim to be that company's own page, and it
 * carries no address, logo or contact detail we have not got. `isPartOf` points
 * at the tracker's dataset node so this reads as a slice of it rather than a
 * competing dataset with the same name, which is the mistake that put ~1,830
 * identical Dataset nodes on the site before 2.19.219.
 *
 * Not emitted below the floor: offering structured data for a page we are
 * telling Google to skip is a mixed signal, and there is nothing to gain.
 */
function alt_company_directory_dataset_schema() {
    $data = alt_company_directory_current();
    if (!$data || !$data['indexable']) return;
    $name = $data['company']['display_name'];
    $node = array(
        '@context'      => 'https://schema.org',
        '@type'         => 'Dataset',
        '@id'           => $data['url'] . '#dataset',
        'name'          => $name . ' layoff records',
        'description'   => alt_company_directory_description($data),
        'url'           => $data['url'],
        'isPartOf'      => array('@id' => home_url('/ai-layoff-tracker/') . '#dataset'),
        'about'         => array('@type' => 'Organization', 'name' => $name),
        'creator'       => array('@type' => 'Organization', 'name' => 'AskTheRecruiter'),
        'license'       => 'https://creativecommons.org/licenses/by/4.0/',
        'isAccessibleForFree' => true,
    );
    if ($data['first_date'] !== '' && $data['last_date'] !== '') {
        $node['temporalCoverage'] = $data['first_date'] . '/' . $data['last_date'];
    }
    if ($data['countries']) {
        $node['spatialCoverage'] = array_values($data['countries']);
    }
    echo '<script type="application/ld+json">' . wp_json_encode($node, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";
}
add_action('wp_head', 'alt_company_directory_dataset_schema', 22);

/**
 * Indexable company URLs: approved mappings whose evidence support still
 * meets the two-event threshold at read time. Cached against the data
 * version so admissions and merges refresh the list.
 */
// Google breadcrumbs for company pages: Blog > AI Layoff Tracker > {Company}.
// Emitted only for directory requests; the trail mirrors the real link path.
function alt_company_directory_breadcrumbs() {
    $data = alt_company_directory_current();
    if (!$data) return;
    $crumbs = array(
        '@context' => 'https://schema.org',
        '@type'    => 'BreadcrumbList',
        'itemListElement' => array(
            array('@type' => 'ListItem', 'position' => 1, 'name' => 'AskTheRecruiter', 'item' => home_url('/')),
            array('@type' => 'ListItem', 'position' => 2, 'name' => 'AI Layoff Tracker', 'item' => home_url('/ai-layoff-tracker/')),
            array('@type' => 'ListItem', 'position' => 3, 'name' => $data['company']['display_name'] . ' layoffs', 'item' => $data['url']),
        ),
    );
    echo '<script type="application/ld+json">' . wp_json_encode($crumbs, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";
}
add_action('wp_head', 'alt_company_directory_breadcrumbs', 21);

/**
 * ONE definition of "a source-linked canonical event", as a grouped subquery
 * keyed by company_key. Admission, the sitemap and the coverage report all read
 * it, so the count that admits a page, the count that indexes it and the count
 * we publish can never be three different numbers.
 *
 * `superset_of = 0` is part of the definition: a rollup row and the per-site
 * rows it absorbed are ONE event, and counting both was how a page could clear
 * a two-event floor on the strength of a single reconciled announcement.
 */
function alt_company_directory_supported_events_sql() {
    $layoffs = alt_db_table(); $events = alt_events_table(); $reports = alt_source_reports_table();
    return "SELECT l.company_key, COUNT(*) AS supported
              FROM $layoffs l
              INNER JOIN $events e ON e.id = l.event_id AND e.canonical_layoff_id = l.id
             WHERE l.event_id > 0 AND l.company_key <> '' AND l.superset_of = 0
               AND EXISTS (SELECT 1 FROM $reports r2 WHERE r2.event_id = l.event_id AND r2.source_url <> '')
             GROUP BY l.company_key";
}

/** The same count for ONE key, used by the admission validator. */
function alt_company_directory_supported_count($company_key) {
    global $wpdb;
    $layoffs = alt_db_table(); $events = alt_events_table(); $reports = alt_source_reports_table();
    return (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COUNT(*) FROM $layoffs l
           INNER JOIN $events e ON e.id = l.event_id AND e.canonical_layoff_id = l.id
          WHERE l.company_key = %s AND l.event_id > 0 AND l.superset_of = 0
            AND EXISTS (SELECT 1 FROM $reports r2 WHERE r2.event_id = l.event_id AND r2.source_url <> '')",
        (string) $company_key));
}

function alt_company_directory_indexable_urls() {
    global $wpdb;
    $cache_key = 'alt_company_dir_sitemap_' . md5((string) get_option('alt_data_ver', 1));
    $cached = get_transient($cache_key);
    if (is_array($cached)) return $cached;
    $directory = alt_company_directory_table();
    $supported = alt_company_directory_supported_events_sql();
    $floor = alt_company_directory_indexable_floor();
    // JOINED against the grouped counts, not a correlated subquery per directory
    // row. The old shape re-counted the whole evidence set once per approved
    // company; at 29 companies that was invisible and at thousands it is a
    // sitemap that times out on shared hosting.
    //
    // GROUP BY company_key so an alias pair contributes ONE url. The picked
    // slug matches alt_company_directory_canonical_slug()'s ordering, so the
    // sitemap and the 301 target can never disagree.
    $slugs = $wpdb->get_col($wpdb->prepare(
        "SELECT SUBSTRING_INDEX(GROUP_CONCAT(d.slug ORDER BY CHAR_LENGTH(d.slug) ASC, d.id ASC), ',', 1) AS canon_slug
           FROM $directory d
           INNER JOIN ($supported) s ON s.company_key = d.company_key AND s.supported >= %d
          WHERE d.review_status = 'approved'
          GROUP BY d.company_key ORDER BY canon_slug ASC", $floor)) ?: array();
    $urls = array_map('alt_company_directory_url', $slugs);
    set_transient($cache_key, $urls, 15 * MINUTE_IN_SECONDS);
    return $urls;
}

/**
 * How far the employer index actually reaches, as public numbers. Published on
 * /company-directory so the coverage claim is checkable from outside without a
 * key, and so a stalled indexer shows up as a number rather than as pages
 * nobody notices are missing.
 */
function alt_company_directory_coverage() {
    global $wpdb;
    $cache_key = 'alt_company_dir_coverage_' . md5((string) get_option('alt_data_ver', 1));
    $cached = get_transient($cache_key);
    if (is_array($cached)) return $cached;
    $directory = alt_company_directory_table();
    $supported = alt_company_directory_supported_events_sql();
    $floor = alt_company_directory_indexable_floor();
    $row = $wpdb->get_row($wpdb->prepare(
        "SELECT COUNT(*) AS employers,
                SUM(s.supported >= %d) AS above_floor,
                SUM(d.company_key IS NOT NULL) AS mapped,
                SUM(d.review_status = 'approved') AS approved,
                SUM(d.review_status = 'noindex') AS noindexed,
                SUM(d.review_status = 'pending') AS pending
           FROM ($supported) s
           LEFT JOIN $directory d ON d.company_key = s.company_key", $floor), ARRAY_A) ?: array();
    $out = array(
        'employers_with_sourced_events' => (int) ($row['employers'] ?? 0),
        'employers_above_index_floor'   => (int) ($row['above_floor'] ?? 0),
        'employers_with_a_page'         => (int) ($row['approved'] ?? 0) + (int) ($row['noindexed'] ?? 0),
        'pages_indexable'               => count(alt_company_directory_indexable_urls()),
        'pages_noindexed'               => (int) ($row['noindexed'] ?? 0),
        'held_for_identity_review'      => (int) ($row['pending'] ?? 0),
        'employers_not_yet_indexed'     => (int) ($row['employers'] ?? 0) - (int) ($row['mapped'] ?? 0),
        'index_floor_events'            => $floor,
    );
    set_transient($cache_key, $out, 15 * MINUTE_IN_SECONDS);
    return $out;
}

/**
 * Self-served company sitemap. The production site's SEO plugin disables WP
 * core sitemaps (wp-sitemap.xml is 404; sitemap_index.xml is the real index),
 * so a core-sitemaps provider would silently never render. Instead the plugin
 * serves /company-layoffs-sitemap.xml itself and appends that URL to whichever
 * SEO plugin's sitemap index is active — the same defensive dual-hook pattern
 * as the robots/canonical/title filters above.
 */
function alt_company_directory_sitemap_url() { return home_url('/company-layoffs-sitemap.xml'); }
function alt_company_directory_register_sitemap_route() {
    add_rewrite_rule('^company-layoffs-sitemap\.xml$', 'index.php?alt_company_sitemap=1', 'top');
}
add_action('init', 'alt_company_directory_register_sitemap_route', 1);
function alt_company_directory_sitemap_query_vars($vars) { $vars[] = 'alt_company_sitemap'; return $vars; }
add_filter('query_vars', 'alt_company_directory_sitemap_query_vars');
function alt_company_directory_render_sitemap() {
    if ((string) get_query_var('alt_company_sitemap') === '') return;
    $urls = alt_company_directory_indexable_urls();
    if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
    status_header(200);
    header('Content-Type: application/xml; charset=UTF-8');
    header('X-Robots-Tag: noindex, follow');
    echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
    echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
    foreach ($urls as $url) { echo '  <url><loc>' . esc_url($url) . '</loc></url>' . "\n"; }
    echo '</urlset>';
    exit;
}
add_action('template_redirect', 'alt_company_directory_render_sitemap', 0);
function alt_company_directory_sitemap_index_entry($xml) {
    if (!alt_company_directory_indexable_urls()) return $xml;
    return $xml . '<sitemap><loc>' . esc_url(alt_company_directory_sitemap_url()) . '</loc></sitemap>' . "\n";
}
add_filter('wpseo_sitemap_index', 'alt_company_directory_sitemap_index_entry');
add_filter('rank_math/sitemap/index', 'alt_company_directory_sitemap_index_entry');
