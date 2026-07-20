<?php
/**
 * Plugin Name: AI Layoff Tracker
 * Description: Tracks verified AI-related and general layoffs from SEC filings and credible news sources.
 * Version: 2.19.46
 * Author: AskTheRecruiter
 */

if (!defined('ABSPATH')) exit;

define('ALT_VERSION', '2.19.46');
define('ALT_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('ALT_PLUGIN_URL', plugin_dir_url(__FILE__));

// Load includes
require_once ALT_PLUGIN_DIR . 'includes/cpt.php';
require_once ALT_PLUGIN_DIR . 'includes/db.php';
require_once ALT_PLUGIN_DIR . 'includes/api.php';
require_once ALT_PLUGIN_DIR . 'includes/company-directory.php';
require_once ALT_PLUGIN_DIR . 'includes/shortcodes.php';
require_once ALT_PLUGIN_DIR . 'includes/export.php';
require_once ALT_PLUGIN_DIR . 'includes/rss.php';
require_once ALT_PLUGIN_DIR . 'includes/contact.php';
require_once ALT_PLUGIN_DIR . 'includes/htaccess.php';
// Generated map of official state WARN list pages (source: railway/sources/warn.py).
// GUARDED: FTP deploys upload files one at a time, so this main plugin file can
// land BEFORE the generated partial does (the mid-upload race the iron rules
// warn about). A hard `require` of a not-yet-uploaded file fatals the ENTIRE
// plugin on every request until the partial arrives (WP recovery-mode email,
// 2.19.20). Include it only if present, and always define the accessor as a
// stub fallback so no caller ever hits an undefined function — WARN rows simply
// omit the state-list link until the real map lands on the next request/deploy.
$alt_warn_urls_partial = ALT_PLUGIN_DIR . 'templates/partials/warn-state-urls.php';
if (is_readable($alt_warn_urls_partial)) {
    require_once $alt_warn_urls_partial;
}
if (!function_exists('alt_state_warn_list_url')) {
    function alt_state_warn_list_url($state) { return ''; }
}
if (!function_exists('alt_state_warn_urls')) {
    function alt_state_warn_urls() { return array(); }
}

/**
 * Activation: register the CPT + custom feed before flushing rewrite rules,
 * and auto-generate the API key so the Railway pipeline can be wired up
 * without running code in the theme editor.
 */
function alt_activate() {
    alt_register_cpt();
    alt_register_feed();
    alt_db_install();
    flush_rewrite_rules();

    if (!get_option('alt_api_key')) {
        update_option('alt_api_key', bin2hex(random_bytes(32)), false);
    }
}
register_activation_hook(__FILE__, 'alt_activate');

function alt_deactivate() {
    flush_rewrite_rules();
}
register_deactivation_hook(__FILE__, 'alt_deactivate');

/**
 * The plugin is deployed via FTP, which bypasses WordPress's updater hooks — so
 * a new version's template/asset changes would otherwise sit behind the stale
 * WP-Super-Cache page cache. On the first PHP request after a version bump,
 * flush our transients plus the WP-Super-Cache and Autoptimize caches so
 * changes go live without a manual purge. (On a cache HIT PHP is skipped, but
 * any cache-missing request — logged-in user, query string, REST call — trips
 * this and clears the whole page cache.)
 */
function alt_flush_caches_on_deploy() {
    if (get_option('alt_deployed_version') === ALT_VERSION) return;
    update_option('alt_deployed_version', ALT_VERSION, false);

    // Create/upgrade the fast-query table on every deploy (dbDelta is a no-op
    // when the schema already matches).
    if (function_exists('alt_db_install')) {
        alt_db_install();
    }
    delete_transient('alt_all_cache');
    delete_transient('alt_stats_cache');
    delete_transient('alt_faq_numbers');
    delete_transient('alt_coverage_counts');
    // Public endpoint cache keys contain this value. A schema/API deployment
    // must advance it too, otherwise callers can receive a five-minute-old
    // response shape even after dbDelta has added the new columns.
    update_option('alt_data_ver', (int) get_option('alt_data_ver', 1) + 1, false);
    if (function_exists('alt_record_dataset_release')) alt_record_dataset_release(ALT_VERSION);
    if (function_exists('wp_cache_clear_cache')) {
        wp_cache_clear_cache();
    }
    // Do NOT call autoptimizeCache::clearall() here. AO filenames are content
    // hashes, so a changed asset gets a NEW aggregate automatically — deleting
    // the old files only opens a window where in-flight HTML references a file
    // that 410s, and Cloudflare then caches that 410 for 24h (incident
    // 2026-07-15, v2.7.2). Old aggregates are harmless; AO prunes its own cache.
}
add_action('init', 'alt_flush_caches_on_deploy');

// Newest column in the wp_alt_layoffs schema. UPDATE THIS on every schema
// change: the guard below re-runs dbDelta until this column really exists,
// because the version-gated flush can fire mid-FTP-upload and run against
// the previous includes/db.php (deploy race, 2026-07-19: role_categories
// never got created and every roles query silently returned nothing).
define('ALT_SCHEMA_SENTINEL_COLUMN', 'role_categories');

function alt_db_schema_verified() {
    global $wpdb;
    if (!function_exists('alt_db_table')) return false;
    $col = $wpdb->get_var($wpdb->prepare(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        alt_db_table(), ALT_SCHEMA_SENTINEL_COLUMN));
    return !empty($col);
}

function alt_ensure_schema_once() {
    if (get_option('alt_schema_ok_ver') === ALT_VERSION) return;
    if (!function_exists('alt_db_install')) return;
    if (!alt_db_schema_verified()) {
        alt_db_install();
        // Schema changed under cached responses: advance the data version so
        // no five-minute-old empty result outlives the repair.
        update_option('alt_data_ver', (int) get_option('alt_data_ver', 1) + 1, false);
    }
    // Record success ONLY once verified; otherwise every request retries
    // (the includes may still be mid-upload; a later request will succeed).
    if (alt_db_schema_verified()) {
        update_option('alt_schema_ok_ver', ALT_VERSION, false);
    }
}
add_action('init', 'alt_ensure_schema_once');

/**
 * Ensure the /contact page exists. Separate from the version-gated flush hook
 * (which can fire mid-FTP-upload before contact.php has landed and then never
 * retry) — this one keeps trying until the page actually exists.
 */
function alt_ensure_contact_page_once() {
    if (get_option('alt_contact_page_done')) return;
    if (!function_exists('alt_ensure_contact_page')) return;
    // Short-lived lock: this runs on public init, so concurrent first requests
    // could otherwise race the check-then-insert and create duplicate pages.
    if (get_transient('alt_contact_page_lock')) return;
    set_transient('alt_contact_page_lock', 1, MINUTE_IN_SECONDS);
    alt_ensure_contact_page();
    if (get_page_by_path('contact')) {
        update_option('alt_contact_page_done', 1, false);
    }
}
add_action('init', 'alt_ensure_contact_page_once');

function alt_ensure_tracker_health_page_once() {
    if (get_page_by_path('ai-layoff-tracker/ai-tracker-health')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned health page
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => 'AI Tracker Health',
        'post_name' => 'ai-tracker-health', 'post_content' => '[alt_tracker_health]'));
}
add_action('init', 'alt_ensure_tracker_health_page_once', 20);

function alt_ensure_report_page_once() {
    $existing = get_page_by_path('ai-layoff-tracker/report');
    if ($existing) {
        // One-time rename of the original "Monthly Report" title.
        if ($existing->post_title === 'Monthly Report' && !get_option('alt_report_title_v2')) {
            wp_update_post(array('ID' => $existing->ID, 'post_title' => 'Monthly Job Cuts Report'));
            update_option('alt_report_title_v2', 1, false);
        }
        return;
    }
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned report page
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => 'Monthly Job Cuts Report',
        'post_name' => 'report', 'post_content' => '[alt_report]'));
}
add_action('init', 'alt_ensure_report_page_once', 20);

function alt_ensure_sources_page_once() {
    if (get_page_by_path('ai-layoff-tracker/sources')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned sources page
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => 'Data Sources',
        'post_name' => 'sources', 'post_content' => '[alt_sources]'));
}
add_action('init', 'alt_ensure_sources_page_once', 20);

function alt_ensure_publisher_page_once() {
    if (get_page_by_path('ai-layoff-tracker/publisher-tools')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned page
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => 'Embed the Layoff Tracker',
        'post_name' => 'publisher-tools', 'post_content' => '[alt_publisher_tools]'));
}
add_action('init', 'alt_ensure_publisher_page_once', 20);

function alt_ensure_press_page_once() {
    if (get_page_by_path('ai-layoff-tracker/press')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned page
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => 'Press & Media',
        'post_name' => 'press', 'post_content' => '[alt_press_media]'));
}
add_action('init', 'alt_ensure_press_page_once', 20);

// The health page is an operations surface for maintainers, deliberately
// unlinked from the public pages (2026-07-19) and kept out of search.
function alt_health_page_noindex($robots) {
    if (is_page('ai-tracker-health')) { $robots['noindex'] = true; $robots['follow'] = true; }
    return $robots;
}
add_filter('wp_robots', 'alt_health_page_noindex');

function alt_ensure_quarterly_report_page_once() {
    if (get_page_by_path('ai-layoff-tracker/state-of-layoffs')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned report page
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => 'State of Layoffs',
        'post_name' => 'state-of-layoffs', 'post_content' => '[alt_quarterly_report]'));
}
add_action('init', 'alt_ensure_quarterly_report_page_once', 21);

/**
 * A deliberately narrow, iframe-safe widget surface. It is limited to a
 * United States national or state view; metro geography is not yet reliable.
 * The explicit query route avoids a shared-host canonical redirect that cannot
 * reliably serve a virtual child page. The response is noindex by design.
 */
function alt_is_widget_request() {
    return isset($_GET['alt_tracker_widget']) && (string) wp_unslash($_GET['alt_tracker_widget']) === '1';
}

// The host adds SAMEORIGIN before template rendering. Remove it during header
// construction, then repeat after headers are sent for plugins that add it
// late. This applies only to the explicit, noindex widget query.
function alt_widget_response_headers($headers) {
    if (alt_is_widget_request()) {
        unset($headers['X-Frame-Options']);
        $headers['Content-Security-Policy'] = 'frame-ancestors *';
    }
    return $headers;
}
add_filter('wp_headers', 'alt_widget_response_headers');

function alt_widget_remove_frame_header() {
    if (!alt_is_widget_request()) return;
    header_remove('X-Frame-Options');
    header('Content-Security-Policy: frame-ancestors *', true);
}
add_action('send_headers', 'alt_widget_remove_frame_header', PHP_INT_MAX);

function alt_render_widget_route() {
    if (!alt_is_widget_request()) return;
    status_header(200);
    header('X-Robots-Tag: noindex, nofollow', true);
    // This is the only intentionally embeddable route. It has no cookies,
    // forms or account state; do not relax frame protection for tracker pages.
    header_remove('X-Frame-Options');
    header('Content-Security-Policy: frame-ancestors *', true);
    nocache_headers();
    include ALT_PLUGIN_DIR . 'templates/page-widget.php';
    exit;
}
add_action('template_redirect', 'alt_render_widget_route', 1);

/**
 * Only load DataTables/Chart.js on pages that actually use a plugin shortcode
 * — loading two CDN libraries on every page of the site would be wasteful.
 * Filter `alt_enqueue_assets` to force-enable on custom templates.
 */
function alt_page_needs_assets() {
    if (function_exists('alt_company_directory_is_request') && alt_company_directory_is_request()) return true;
    if (!is_singular()) return false;
    if (is_singular('layoffs')) return true;   // per-entry permalink pages
    $post = get_post();
    if (!$post) return false;
    $shortcodes = array(
        'alt_tracker', 'alt_stats_bar', 'alt_dashboard',
        'alt_ai_tracker', 'alt_tracker_health', 'alt_publisher_tools', 'alt_quarterly_report', 'alt_company_history', 'alt_export_buttons',
        'alt_contact', 'alt_press_media', 'alt_sources', 'alt_report',
    );
    foreach ($shortcodes as $shortcode) {
        if (has_shortcode($post->post_content, $shortcode)) return true;
    }
    return false;
}

function alt_enqueue_assets() {
    if (!apply_filters('alt_enqueue_assets', alt_page_needs_assets())) return;

    // Version our assets by ALT_VERSION + file mtime, not ALT_VERSION alone.
    // FTPS deploys upload the main PHP (new version string) before the assets,
    // so a request in that window used to let Autoptimize aggregate the OLD
    // asset content under the NEW ver= key — and that stale mapping persisted
    // for the whole release (incident 2026-07-19, v2.18.58). With mtime in the
    // key, the finished upload always mints a fresh cache key by itself.
    $alt_asset_ver = function ($rel) {
        $t = @filemtime(ALT_PLUGIN_DIR . $rel);
        return ALT_VERSION . ($t ? '.' . $t : '');
    };
    wp_enqueue_style('alt-styles', ALT_PLUGIN_URL . 'assets/layoffs.css', array(), $alt_asset_ver('assets/layoffs.css'));
    $alt_page_content = is_singular() ? get_post_field('post_content', get_queried_object_id()) : '';
    $is_health_page = $alt_page_content && (has_shortcode($alt_page_content, 'alt_tracker_health') || has_shortcode($alt_page_content, 'alt_publisher_tools'));
    if ($is_health_page) {
        wp_enqueue_script('alt-health-js', ALT_PLUGIN_URL . 'assets/health.js', array(), $alt_asset_ver('assets/health.js'), array('in_footer' => true, 'strategy' => 'defer'));
        wp_localize_script('alt-health-js', 'altHealthData', array(
            'apiUrl' => esc_url_raw(rest_url('layoffs/v1/')),
            'widgetUrl' => esc_url_raw(home_url('/?alt_tracker_widget=1')),
            'trackerUrl' => esc_url_raw(home_url('/ai-layoff-tracker/')),
        ));
        return;
    }

    // DataTables
    wp_enqueue_style(
        'datatables-css',
        'https://cdnjs.cloudflare.com/ajax/libs/datatables/1.10.21/css/jquery.dataTables.min.css',
        array(),
        '1.10.21'
    );
    wp_enqueue_script(
        'datatables-js',
        'https://cdnjs.cloudflare.com/ajax/libs/datatables/1.10.21/js/jquery.dataTables.min.js',
        array('jquery'),
        '1.10.21',
        true
    );

    // Chart.js (UMD build, no dependencies)
    wp_enqueue_script(
        'chartjs',
        'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js',
        array(),
        '4.4.0',
        true
    );

    // chartjs-chart-geo: the geographic bubble-map chart type for the "AI job
    // loss map". Bundles topojson-client; depends on Chart.js. Deferred with the
    // rest so it loads after Chart.js (dependency order is enforced by WP).
    wp_enqueue_script(
        'chartjs-geo',
        // cdnjs does NOT host this package; jsdelivr's npm mirror does. UMD
        // build exposes window.ChartGeo (incl. ChartGeo.topojson) and registers
        // the bubbleMap chart type on Chart.js.
        'https://cdn.jsdelivr.net/npm/chartjs-chart-geo@4.3.4/build/index.umd.min.js',
        array('chartjs'),
        '4.3.4',
        true
    );

    // Main JS
    wp_enqueue_script(
        'alt-js',
        ALT_PLUGIN_URL . 'assets/layoffs.js',
        array('jquery', 'datatables-js', 'chartjs', 'chartjs-geo'),
        $alt_asset_ver('assets/layoffs.js'),
        // Autoptimize defers our dependencies (jquery/datatables/chartjs).
        // Since our file is AO-excluded it MUST defer too, or it executes
        // before deferred jQuery exists and dies on its first line
        // (2026-07-19 blank-page incident).
        array('in_footer' => true, 'strategy' => 'defer')
    );

    // Pass data to JS
    wp_localize_script('alt-js', 'altData', array(
        'apiUrl'    => esc_url_raw(rest_url('layoffs/v1/')),
        'ajaxUrl'   => admin_url('admin-ajax.php'),
        'nonce'     => wp_create_nonce('alt_nonce'),
        'exportCsv' => admin_url('admin-post.php?action=alt_export_csv'),
        'exportJson'=> admin_url('admin-post.php?action=alt_export_json'),
    ));
}
add_action('wp_enqueue_scripts', 'alt_enqueue_assets');

// Keep this plugin's assets OUT of Autoptimize. Each is already a single
// file, so aggregation buys nothing — and during deploys AO's content-hashed
// bundles go stale or get pruned while cached HTML still references them
// (three broken-page incidents on 2026-07-19 alone). Raw asset URLs always
// resolve: worst case a 5-minute-old page loads a 5-minute-old-but-working
// script.
function alt_autoptimize_exclude_js($exclude) {
    return $exclude . ', ai-layoff-tracker/assets';
}
add_filter('autoptimize_filter_js_exclude', 'alt_autoptimize_exclude_js');
function alt_autoptimize_exclude_css($exclude) {
    return $exclude . ', ai-layoff-tracker/assets';
}
add_filter('autoptimize_filter_css_exclude', 'alt_autoptimize_exclude_css');

/**
 * SEO for tracker pages: JSON-LD Dataset structured data (eligible for Google
 * Dataset Search; signals a citable, downloadable dataset) plus Open Graph /
 * Twitter tags for shareable link previews. The OG block is filterable off via
 * `alt_output_og_tags` if an SEO plugin (Yoast/RankMath) already emits them.
 */
/**
 * The <title> tag comes from the WordPress page title, which may contain an
 * em dash. Replace em/en dashes with a colon on tracker pages so the browser
 * tab and search snippet read in plain punctuation (house style: no em dashes
 * in reader-facing copy).
 */
function alt_title_no_emdash($parts) {
    if (alt_page_needs_assets() && !empty($parts['title'])) {
        $parts['title'] = trim(preg_replace('/\s*[\x{2013}\x{2014}]\s*/u', ': ', $parts['title']));
    }
    return $parts;
}
add_filter('document_title_parts', 'alt_title_no_emdash');

// This site runs Yoast, which renders <title> through its own filter and
// bypasses document_title_parts. Catch the final title string on tracker
// pages there too (and RankMath, defensively).
function alt_title_string_no_emdash($title) {
    if (alt_page_needs_assets()) {
        $title = trim(preg_replace('/\s*[\x{2013}\x{2014}]\s*/u', ': ', (string) $title));
    }
    return $title;
}
add_filter('wpseo_title', 'alt_title_string_no_emdash', 99);
add_filter('rank_math/frontend/title', 'alt_title_string_no_emdash', 99);

function alt_seo_head() {
    if (!alt_page_needs_assets()) return;

    $page_url = get_permalink();
    if (!$page_url) $page_url = home_url('/');
    $title = 'AI Layoff Tracker: Live Data on Jobs Lost to AI & Automation';
    $desc  = 'A continuously updated tracker of verified layoffs worldwide, all industries and causes, flagging which ones companies attribute to AI. Filter by country, US state, industry, or period. Sourced from SEC filings, state WARN notices, and credible news globally, with the exact quote and primary source link for every entry.';

    $schema = array(
        '@context'            => 'https://schema.org',
        '@type'               => 'Dataset',
        'name'                => 'AI Layoff Tracker',
        'alternateName'       => array('AI Layoffs Tracker', 'AI Job Layoff Tracker', 'Job Layoff Tracker', 'Layoff Tracker', 'Layoffs Tracker ' . gmdate('Y')),
        'description'         => $desc,
        'url'                 => $page_url,
        'keywords'            => array('AI layoffs', 'layoffs', 'layoff tracker', 'job layoff tracker', 'jobs lost to AI', 'AI job losses', 'AI layoff tracker', 'automation layoffs', 'tech layoffs', 'layoffs worldwide', 'global layoffs', 'layoffs by country', 'layoffs ' . gmdate('Y'), 'WARN notices'),
        'license'             => 'https://creativecommons.org/licenses/by/4.0/',
        'isAccessibleForFree' => true,
        'temporalCoverage'    => '2015-01-01/..',
        'spatialCoverage'     => 'Worldwide',
        'dateModified'        => gmdate('Y-m-d'),
        'variableMeasured'    => array('company', 'job_count', 'layoff_date', 'country', 'US state', 'industry', 'AI attribution', 'source URL'),
        'creator'             => array(
            '@type' => 'Organization',
            'name'  => 'AskTheRecruiter',
            'url'   => home_url('/'),
        ),
        'distribution'        => array(
            array('@type' => 'DataDownload', 'encodingFormat' => 'text/csv',         'contentUrl' => admin_url('admin-post.php?action=alt_export_csv')),
            array('@type' => 'DataDownload', 'encodingFormat' => 'application/json', 'contentUrl' => admin_url('admin-post.php?action=alt_export_json')),
        ),
    );

    echo "\n<script type=\"application/ld+json\">" . wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";

    // FAQ rich results + the same Q/A rendered server-side on the page (so
    // crawlers and LLM bots see real numbers without executing JavaScript).
    $faq_schema = array(
        '@context'   => 'https://schema.org',
        '@type'      => 'FAQPage',
        'mainEntity' => array_map(function ($qa) {
            return array(
                '@type'          => 'Question',
                'name'           => $qa[0],
                'acceptedAnswer' => array('@type' => 'Answer', 'text' => $qa[1]),
            );
        }, alt_faq_items()),
    );
    echo "<script type=\"application/ld+json\">" . wp_json_encode($faq_schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";

    if (apply_filters('alt_output_og_tags', true)) {
        echo '<meta property="og:type" content="website">' . "\n";
        echo '<meta property="og:title" content="' . esc_attr($title) . '">' . "\n";
        echo '<meta property="og:description" content="' . esc_attr($desc) . '">' . "\n";
        echo '<meta property="og:url" content="' . esc_url($page_url) . '">' . "\n";
        echo '<meta name="twitter:card" content="summary_large_image">' . "\n";
        echo '<meta name="twitter:title" content="' . esc_attr($title) . '">' . "\n";
        echo '<meta name="twitter:description" content="' . esc_attr($desc) . '">' . "\n";
    }
}
add_action('wp_head', 'alt_seo_head', 20);

/**
 * FAQ content shared by the FAQPage JSON-LD (wp_head) and the on-page FAQ
 * section (template) — one source so Google's "must match visible text" rule
 * holds. Numbers come from the live table, cached an hour.
 */
function alt_faq_items() {
    $n = get_transient('alt_faq_numbers');
    if (!is_array($n)) {
        global $wpdb;
        $t = alt_db_table();
        $y = (int) gmdate('Y');
        $row = $wpdb->get_row($wpdb->prepare(
            "SELECT COUNT(*) entries, COALESCE(SUM(job_count),0) jobs,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs
             FROM $t WHERE YEAR(layoff_date) = %d", $y));
        $all = $wpdb->get_row(
            "SELECT COUNT(*) entries, COUNT(DISTINCT NULLIF(country,'')) countries,
                    COUNT(DISTINCT NULLIF(state,'')) states FROM $t");
        $n = array(
            'y'         => $y,
            'entries'   => $row ? (int) $row->entries : 0,
            'jobs'      => $row ? (int) $row->jobs : 0,
            'ai_jobs'   => $row ? (int) $row->ai_jobs : 0,
            'all'       => $all ? (int) $all->entries : 0,
            'countries' => $all ? (int) $all->countries : 0,
            'states'    => $all ? (int) $all->states : 0,
        );
        set_transient('alt_faq_numbers', $n, HOUR_IN_SECONDS);
    }
    $f = function ($v) { return number_format((float) $v); };
    return array(
        array('What is the AI Layoff Tracker?',
            'A free, continuously updated layoff tracker covering verified job cuts worldwide across all industries and causes. It flags which layoffs companies explicitly attribute to AI or automation. Every entry links to a primary source: a SEC 8-K filing, a US state WARN notice, or a named news outlet with the exact quote.'),
        array('How many layoffs have there been in ' . $n['y'] . ' so far?',
            'So far in ' . $n['y'] . ' the tracker holds ' . $f($n['entries']) . ' verified layoff events totaling ' . $f($n['jobs']) . ' job cuts worldwide. Companies explicitly blamed AI for ' . $f($n['ai_jobs']) . ' of those cuts. Totals update daily as new filings and reports are verified.'),
        array('Where does the layoff data come from?',
            'Four kinds of sources. SEC 8-K filings, searched twice daily. Official WARN notices from ' . $f($n['states']) . ' US states, imported daily with no AI processing. The European Restructuring Monitor, which is Eurofound\'s official per-company database of announced restructuring across the EU27, Norway and historically the UK (imported daily and credited to Eurofound; because these are announcement-stage figures, they feed the separately labeled "Announced" tier and never the verified totals). And worldwide press coverage in 65+ languages through the GDELT news index plus NewsAPI. The dataset spans 2015 to the present across ' . $f($n['countries']) . ' countries, ' . $f($n['all']) . ' events in total.'),
        array('What sources do you use?',
            'Official government filings and legally required notices first: every SEC 8-K/6-K filing, official WARN mass-layoff notices from ' . $f($n['states']) . ' US states (each a live link on our Data Sources page), and the EU\'s Eurofound restructuring monitor. Worldwide, we add named news coverage in 65+ languages from an editorially maintained trusted-outlet allowlist. Nothing is estimated — every number links back to one of these. The Data Sources page lists each one, with links to check the raw source yourself.',
            array('ai-layoff-tracker/sources/', 'See the full Data Sources page &rarr;')),
        array('How is this different from the Challenger report or the WSJ and TrueUp layoff trackers?',
            'Announcement surveys count corporate intentions on the day of the announcement. This job layoff tracker counts what has a verifiable document or quoted primary source behind it, so it is a documented floor rather than an estimate. Announcement-stage cuts are also tracked, but in a separately labeled tier that is never mixed into the verified totals.'),
        array('Can journalists and researchers use this data?',
            'Yes, free with attribution to asktherecruiter.com (CC BY 4.0). Filtered or full CSV and JSON downloads are on the page, and a public REST API serves the same data. Corrected entries are publicly flagged, and every correction to published figures is disclosed in the on-page corrections log.'),
        array('How often is the tracker updated?',
            'Continuously. News and SEC filings are collected twice daily (morning and after US market close, ET); official WARN notices and Eurofound ERM records import daily; the daily summary, stats, charts and table read live data on every page load; and the US Challenger comparison updates automatically each month when their report publishes. The Tracker Health page shows every collector\'s latest run in real time.'),
        array('What is the difference between "verified" and "announced" job cuts?',
            'Verified cuts have a filing or independently reported source behind them: a WARN notice, an SEC filing, or a named outlet\'s report of cuts taking place. Announced cuts are company plans reported at announcement stage, tracked in their own labeled tier and never mixed into the verified totals, because announced plans can shrink, stretch over years, or partially happen through attrition.'),
        array('How do I report an error?',
            'Use the contact page and corrections get priority. Every entry links to its primary source, so you can check any number against the underlying document.'),
    );
}

/**
 * Live coverage counts for the intro line: real countries (excluding the
 * "Multiple countries" bucket) and US states with WARN data. Cached an hour.
 */
function alt_coverage_counts() {
    $c = get_transient('alt_coverage_counts');
    if (is_array($c)) return $c;
    global $wpdb;
    $t = alt_db_table();
    $countries = (int) $wpdb->get_var(
        "SELECT COUNT(DISTINCT country) FROM $t WHERE country <> '' AND country <> 'Multiple countries'");
    $states = (int) $wpdb->get_var(
        "SELECT COUNT(DISTINCT state) FROM $t WHERE source_type = 'warn' AND state <> ''");
    $c = array('countries' => $countries, 'states' => $states);
    set_transient('alt_coverage_counts', $c, HOUR_IN_SECONDS);
    return $c;
}

/**
 * Render single layoff entries (/blog/layoff/{company}-{date}) with the plugin's
 * own template so each event has a clean, citable permalink page.
 */
function alt_single_template($template) {
    if (is_singular('layoffs')) {
        $custom = ALT_PLUGIN_DIR . 'templates/single-layoff.php';
        if (file_exists($custom)) {
            return $custom;
        }
    }
    return $template;
}
add_filter('single_template', 'alt_single_template');

/**
 * Small admin page (Tools → AI Layoff Tracker) showing the API key the
 * Railway pipeline authenticates with, plus entry counts.
 */
function alt_register_admin_page() {
    add_management_page(
        'AI Layoff Tracker',
        'AI Layoff Tracker',
        'manage_options',
        'alt-settings',
        'alt_render_admin_page'
    );
}
add_action('admin_menu', 'alt_register_admin_page');

function alt_render_admin_page() {
    if (!current_user_can('manage_options')) return;

    if (isset($_POST['alt_regenerate_key']) && check_admin_referer('alt_regenerate_key')) {
        update_option('alt_api_key', bin2hex(random_bytes(32)), false);
        echo '<div class="notice notice-success"><p>New API key generated. Update WP_API_KEY in Railway.</p></div>';
    }

    $key   = alt_get_api_key();
    $count = wp_count_posts('layoffs');
    $total = isset($count->publish) ? (int) $count->publish : 0;
    ?>
    <div class="wrap">
        <h1>AI Layoff Tracker</h1>
        <p><strong><?php echo esc_html(number_format_i18n($total)); ?></strong> published layoff entries.</p>
        <h2>Pipeline API key</h2>
        <p>Copy this value into the Railway environment variable <code>WP_API_KEY</code>.
           Requests must send it in the <code>X-Layoff-API-Key</code> header.</p>
        <input type="text" readonly class="regular-text code" style="width:520px"
               value="<?php echo esc_attr($key); ?>" onfocus="this.select();">
        <?php if (defined('AI_LAYOFF_API_KEY') && AI_LAYOFF_API_KEY) : ?>
            <p><em>Note: <code>AI_LAYOFF_API_KEY</code> is defined in wp-config.php and overrides the stored option.</em></p>
        <?php endif; ?>
        <form method="post" style="margin-top:12px;">
            <?php wp_nonce_field('alt_regenerate_key'); ?>
            <button type="submit" name="alt_regenerate_key" value="1" class="button"
                    onclick="return confirm('Regenerate the key? The Railway pipeline will stop authenticating until WP_API_KEY is updated.');">
                Regenerate key
            </button>
        </form>
        <h2>Endpoints</h2>
        <ul style="list-style:disc;padding-left:20px;">
            <li><code>POST <?php echo esc_html(rest_url('layoffs/v1/add')); ?></code> (key required)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/check-duplicate')); ?></code> (key required)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/all')); ?></code> (public)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/stats')); ?></code> (public)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/company/{name}')); ?></code> (public)</li>
        </ul>
    </div>
    <?php
}
