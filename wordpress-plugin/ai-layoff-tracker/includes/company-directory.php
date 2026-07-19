<?php
/** Source-linked company-directory foundation. */
if (!defined('ABSPATH')) exit;

function alt_company_directory_is_request() { return (string) get_query_var('alt_company_layoffs_slug') !== ''; }
function alt_company_directory_source_url($url) {
    $url = esc_url_raw((string) $url);
    return preg_match('#^https?://#i', $url) ? $url : '';
}
function alt_company_directory_url($slug) { return home_url('/company-layoffs/' . rawurlencode((string) $slug) . '/'); }

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

    $layoffs = alt_db_table(); $events = alt_events_table(); $reports = alt_source_reports_table();
    // The canonical row is the surviving row after a source-preserving merge.
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT l.* FROM $layoffs l INNER JOIN $events e ON e.id = l.event_id AND e.canonical_layoff_id = l.id
         WHERE l.company_key = %s AND l.event_id > 0
         AND EXISTS (SELECT 1 FROM $reports r WHERE r.event_id = l.event_id AND r.source_url <> '')
         ORDER BY (l.layoff_date IS NULL) ASC, l.layoff_date DESC, l.id DESC", $company['company_key']), ARRAY_A) ?: array();
    $event_ids = array_values(array_unique(array_map('intval', wp_list_pluck($rows, 'event_id'))));
    $sources_by_event = array();
    if ($event_ids) {
        $ph = implode(',', array_fill(0, count($event_ids), '%d'));
        $source_rows = $wpdb->get_results($wpdb->prepare("SELECT event_id, source_name, source_type, source_url FROM $reports WHERE event_id IN ($ph) ORDER BY id ASC", $event_ids), ARRAY_A) ?: array();
        foreach ($source_rows as $source) {
            $url = alt_company_directory_source_url($source['source_url'] ?? '');
            if ($url === '') continue;
            $sources_by_event[(int) $source['event_id']][] = array('name' => sanitize_text_field($source['source_name'] ?? ''), 'type' => sanitize_key($source['source_type'] ?? ''), 'url' => $url);
        }
    }
    $event_rows = array(); $total_jobs = 0;
    foreach ($rows as $row) {
        $event_id = (int) $row['event_id'];
        if (empty($sources_by_event[$event_id])) continue;
        $row['sources'] = $sources_by_event[$event_id];
        $event_rows[] = $row; $total_jobs += max(0, (int) $row['job_count']);
    }
    if (!$event_rows) return null;
    $data = array(
        'company' => $company, 'events' => $event_rows, 'total_jobs' => $total_jobs,
        'indexable' => $company['review_status'] === 'approved' && count($event_rows) >= 2,
        'url' => alt_company_directory_url($company['slug']),
        'tracker_url' => add_query_arg('company', $company['display_name'], home_url('/ai-layoff-tracker/')),
    );
    set_transient($cache_key, $data, 5 * MINUTE_IN_SECONDS);
    return $data;
}

function alt_company_directory_current() {
    if (!alt_company_directory_is_request()) return null;
    if (array_key_exists('alt_company_directory_current', $GLOBALS)) return $GLOBALS['alt_company_directory_current'];
    $GLOBALS['alt_company_directory_current'] = alt_company_directory_data(get_query_var('alt_company_layoffs_slug'));
    return $GLOBALS['alt_company_directory_current'];
}

function alt_company_directory_register_route() { add_rewrite_rule('^company-layoffs/([^/]+)/?$', 'index.php?alt_company_layoffs_slug=$matches[1]', 'top'); }
add_action('init', 'alt_company_directory_register_route', 1);
function alt_company_directory_query_vars($vars) { $vars[] = 'alt_company_layoffs_slug'; return $vars; }
add_filter('query_vars', 'alt_company_directory_query_vars');

function alt_company_directory_prepare_request() {
    if (!alt_company_directory_is_request()) return;
    $data = alt_company_directory_current();
    if (!$data) { global $wp_query; $wp_query->set_404(); status_header(404); return; }
    if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
    nocache_headers();
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
function alt_company_directory_title($parts) { $data = alt_company_directory_current(); if ($data) $parts['title'] = $data['company']['display_name'] . ' layoffs: source-linked event history'; return $parts; }
add_filter('document_title_parts', 'alt_company_directory_title', 5);
function alt_company_directory_seo_title($title) { $data = alt_company_directory_current(); return $data ? $data['company']['display_name'] . ' layoffs: source-linked event history' : $title; }
add_filter('wpseo_title', 'alt_company_directory_seo_title', 5);
add_filter('rank_math/frontend/title', 'alt_company_directory_seo_title', 5);

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

function alt_company_directory_indexable_urls() {
    global $wpdb;
    $cache_key = 'alt_company_dir_sitemap_' . md5((string) get_option('alt_data_ver', 1));
    $cached = get_transient($cache_key);
    if (is_array($cached)) return $cached;
    $directory = alt_company_directory_table();
    $layoffs = alt_db_table(); $events = alt_events_table(); $reports = alt_source_reports_table();
    $slugs = $wpdb->get_col(
        "SELECT d.slug FROM $directory d
         WHERE d.review_status = 'approved' AND (
             SELECT COUNT(*) FROM $layoffs l
             INNER JOIN $events e ON e.id = l.event_id AND e.canonical_layoff_id = l.id
             WHERE l.company_key = d.company_key AND l.event_id > 0
             AND EXISTS (SELECT 1 FROM $reports r2 WHERE r2.event_id = l.event_id AND r2.source_url <> '')
         ) >= 2 ORDER BY d.slug ASC") ?: array();
    $urls = array_map('alt_company_directory_url', $slugs);
    set_transient($cache_key, $urls, 15 * MINUTE_IN_SECONDS);
    return $urls;
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
