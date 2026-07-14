<?php
/**
 * REST API endpoints (layoffs/v1).
 *
 * Authenticated (X-Layoff-API-Key header):
 *   POST /wp-json/layoffs/v1/add
 *   GET  /wp-json/layoffs/v1/check-duplicate?hash=...
 *
 * Public:
 *   GET  /wp-json/layoffs/v1/all
 *   GET  /wp-json/layoffs/v1/stats
 *   GET  /wp-json/layoffs/v1/company/{name}
 */

if (!defined('ABSPATH')) exit;

function alt_get_api_key() {
    // wp-config.php constant takes precedence over the stored option
    if (defined('AI_LAYOFF_API_KEY') && AI_LAYOFF_API_KEY) {
        return (string) AI_LAYOFF_API_KEY;
    }
    return (string) get_option('alt_api_key', '');
}

/**
 * Permission callback for authenticated routes. Fails CLOSED: if no key is
 * configured on the server, every request is rejected — an empty stored key
 * must never match an empty header.
 */
function alt_api_permission($request) {
    $stored = alt_get_api_key();
    if ($stored === '') {
        return new WP_Error(
            'alt_key_missing',
            'API key is not configured on this site. Activate the plugin (or set AI_LAYOFF_API_KEY in wp-config.php).',
            array('status' => 503)
        );
    }

    $provided = (string) $request->get_header('X-Layoff-API-Key');
    if ($provided === '' || !hash_equals($stored, $provided)) {
        return new WP_Error('alt_forbidden', 'Invalid or missing API key.', array('status' => 403));
    }
    return true;
}

function alt_register_routes() {
    register_rest_route('layoffs/v1', '/add', array(
        'methods'             => 'POST',
        'callback'            => 'alt_api_add',
        'permission_callback' => 'alt_api_permission',
    ));

    register_rest_route('layoffs/v1', '/check-duplicate', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_check_duplicate',
        'permission_callback' => 'alt_api_permission',
        'args' => array(
            'hash' => array('required' => true, 'type' => 'string'),
        ),
    ));

    register_rest_route('layoffs/v1', '/all', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_all',
        'permission_callback' => '__return_true',
    ));

    register_rest_route('layoffs/v1', '/stats', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_stats',
        'permission_callback' => '__return_true',
    ));

    register_rest_route('layoffs/v1', '/company/(?P<name>[^/]+)', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_company',
        'permission_callback' => '__return_true',
    ));
}
add_action('rest_api_init', 'alt_register_routes');

/* ------------------------------------------------------------------ */
/* Shared helpers                                                      */
/* ------------------------------------------------------------------ */

function alt_hash_exists($hash) {
    $query = new WP_Query(array(
        'post_type'      => 'layoffs',
        'post_status'    => 'any',
        'meta_key'       => 'dedup_hash',
        'meta_value'     => $hash,
        'fields'         => 'ids',
        'posts_per_page' => 1,
        'no_found_rows'  => true,
    ));
    return $query->have_posts();
}

function alt_entry_to_array($post_id) {
    $tags = get_post_meta($post_id, 'reason_tags', true);
    if (!is_array($tags)) {
        $tags = ($tags === '' || $tags === false || $tags === null) ? array() : (array) $tags;
    }

    $ticker      = (string) get_post_meta($post_id, 'ticker', true);
    $ai_language = (string) get_post_meta($post_id, 'ai_language', true);

    return array(
        'id'                 => (int) $post_id,
        'company_name'       => (string) get_post_meta($post_id, 'company_name', true),
        'ticker'             => $ticker !== '' ? $ticker : null,
        'job_count'          => (int) get_post_meta($post_id, 'job_count', true),
        'layoff_date'        => (string) get_post_meta($post_id, 'layoff_date', true),
        'industry'           => (string) get_post_meta($post_id, 'industry', true),
        'country'            => (string) get_post_meta($post_id, 'country', true),
        'source_type'        => (string) get_post_meta($post_id, 'source_type', true),
        'source_name'        => (string) get_post_meta($post_id, 'source_name', true),
        'verification_level' => (string) get_post_meta($post_id, 'verification_level', true),
        'source_url'         => (string) get_post_meta($post_id, 'source_url', true),
        'ai_explicit'        => (bool) get_post_meta($post_id, 'ai_explicit', true),
        'ai_language'        => $ai_language !== '' ? $ai_language : null,
        'reason_tags'        => array_values(array_map('strval', $tags)),
        'excerpt'            => (string) get_post_meta($post_id, 'excerpt', true),
    );
}

/**
 * All published entries, newest layoff first, cached for 5 minutes (the
 * front-end fetches this on every tracker/dashboard page view).
 *
 * Sorting happens in PHP rather than via a meta_value orderby: WP_Query's
 * meta orderby INNER JOINs on the meta key, which would silently drop posts
 * created manually in wp-admin that lack a layoff_date meta row.
 */
function alt_get_all_entries() {
    $cached = get_transient('alt_all_cache');
    if (is_array($cached)) {
        return $cached;
    }

    $query = new WP_Query(array(
        'post_type'      => 'layoffs',
        'post_status'    => 'publish',
        'posts_per_page' => -1,
        'no_found_rows'  => true,
    ));

    $rows = array();
    foreach ($query->posts as $post) {
        $rows[] = alt_entry_to_array($post->ID);
    }

    usort($rows, function ($a, $b) {
        return strcmp($b['layoff_date'], $a['layoff_date']); // undated entries sink
    });

    set_transient('alt_all_cache', $rows, 5 * MINUTE_IN_SECONDS);
    return $rows;
}

function alt_flush_caches() {
    delete_transient('alt_all_cache');
    delete_transient('alt_stats_cache');
}
// Manual edits/deletes in wp-admin must also invalidate the caches
add_action('save_post_layoffs', 'alt_flush_caches');
add_action('deleted_post', 'alt_flush_caches');

/* ------------------------------------------------------------------ */
/* Route callbacks                                                     */
/* ------------------------------------------------------------------ */

function alt_api_add($request) {
    $meta_in = $request->get_param('meta');
    if (!is_array($meta_in)) {
        return new WP_Error('alt_bad_request', 'Missing "meta" object.', array('status' => 400));
    }

    $company = sanitize_text_field($meta_in['company_name'] ?? '');
    if ($company === '') {
        return new WP_Error('alt_bad_request', 'company_name is required.', array('status' => 400));
    }

    $job_count = absint($meta_in['job_count'] ?? 0);
    if ($job_count < 1) {
        return new WP_Error('alt_bad_request', 'job_count must be a positive integer.', array('status' => 400));
    }

    $layoff_date = sanitize_text_field($meta_in['layoff_date'] ?? '');
    if ($layoff_date !== '' && !preg_match('/^\d{4}-\d{2}-\d{2}$/', $layoff_date)) {
        $layoff_date = '';
    }

    $dedup_hash = strtolower(sanitize_text_field($meta_in['dedup_hash'] ?? ''));
    if (!preg_match('/^[a-f0-9]{32}$/', $dedup_hash)) {
        return new WP_Error('alt_bad_request', 'dedup_hash must be an md5 hex string.', array('status' => 400));
    }

    // Server-side dedup re-check — the Railway pre-check fails open, so this
    // is the authoritative guard against duplicates
    if (alt_hash_exists($dedup_hash)) {
        return new WP_Error('alt_duplicate', 'An entry with this dedup_hash already exists.', array('status' => 409));
    }

    $verification = sanitize_text_field($meta_in['verification_level'] ?? '');
    if (!in_array($verification, alt_allowed_verification_levels(), true)) {
        $verification = 'bronze';
    }

    $source_type = sanitize_text_field($meta_in['source_type'] ?? '');
    if (!in_array($source_type, alt_allowed_source_types(), true)) {
        $source_type = 'news';
    }

    $tags_in = $meta_in['reason_tags'] ?? array();
    $tags    = array();
    if (is_array($tags_in)) {
        $tags = array_values(array_intersect(
            array_map('sanitize_key', $tags_in),
            alt_allowed_reason_tags()
        ));
    }

    $title = sanitize_text_field((string) $request->get_param('title'));
    if ($title === '') {
        $title = sprintf('%s — %s jobs — %s', $company, number_format_i18n($job_count), $layoff_date);
    }

    $post_id = wp_insert_post(array(
        'post_type'   => 'layoffs',
        'post_status' => 'publish',
        'post_title'  => $title,
    ), true);

    if (is_wp_error($post_id)) {
        return new WP_Error('alt_insert_failed', $post_id->get_error_message(), array('status' => 500));
    }

    $meta_values = array(
        'company_name'       => $company,
        'ticker'             => sanitize_text_field($meta_in['ticker'] ?? ''),
        'job_count'          => $job_count,
        'layoff_date'        => $layoff_date,
        'industry'           => sanitize_text_field($meta_in['industry'] ?? ''),
        'country'            => sanitize_text_field($meta_in['country'] ?? ''),
        'source_url'         => esc_url_raw($meta_in['source_url'] ?? ''),
        'source_type'        => $source_type,
        'source_name'        => sanitize_text_field($meta_in['source_name'] ?? ''),
        'verification_level' => $verification,
        'excerpt'            => sanitize_textarea_field($meta_in['excerpt'] ?? ''),
        'reason_tags'        => $tags,
        'ai_explicit'        => !empty($meta_in['ai_explicit']),
        'ai_language'        => sanitize_text_field($meta_in['ai_language'] ?? ''),
        'dedup_hash'         => $dedup_hash,
    );
    foreach ($meta_values as $key => $value) {
        update_post_meta($post_id, $key, $value);
    }

    alt_flush_caches();

    return new WP_REST_Response(array('id' => $post_id, 'created' => true), 201);
}

function alt_api_check_duplicate($request) {
    $hash = strtolower(sanitize_text_field($request->get_param('hash')));
    return rest_ensure_response(array(
        'exists' => $hash !== '' && alt_hash_exists($hash),
    ));
}

function alt_api_all() {
    $entries = alt_get_all_entries();
    return rest_ensure_response(array(
        'generated'     => gmdate('Y-m-d\TH:i:s\Z'),
        'total_records' => count($entries),
        'data'          => $entries,
    ));
}

function alt_api_stats() {
    $cached = get_transient('alt_stats_cache');
    if (is_array($cached)) {
        return rest_ensure_response($cached);
    }

    $entries       = alt_get_all_entries();
    $current_month = current_time('Y-m');
    $current_year  = current_time('Y');

    // Current week, Monday–Sunday, in the site's timezone
    $now_ts     = current_time('timestamp');
    $dow        = (int) date('N', $now_ts);              // 1 = Mon … 7 = Sun
    $monday_ts  = strtotime('-' . ($dow - 1) . ' days', $now_ts);
    $sunday_ts  = strtotime('+6 days', $monday_ts);
    $week_start = date('Y-m-d', $monday_ts);
    $week_end   = date('Y-m-d', $sunday_ts);

    $stats = array(
        'generated'     => gmdate('Y-m-d\TH:i:s\Z'),
        'total_entries' => count($entries),
        'total_jobs'    => 0,
        'ai_entries'    => 0,
        'ai_jobs'       => 0,
        'week_entries'  => 0,
        'week_jobs'     => 0,
        'month_entries' => 0,
        'month_jobs'    => 0,
        'year_entries'  => 0,
        'year_jobs'     => 0,
        // Labels that name the actual period and roll over automatically
        'week_range'    => date('M j', $monday_ts) . ' – ' . date('M j', $sunday_ts),
        'month_label'   => current_time('F Y'),
        'year_label'    => current_time('Y'),
        'coverage_start' => '',   // earliest layoff date on record, e.g. "Jan 2024"
    );

    $min_date = '';
    foreach ($entries as $entry) {
        $jobs = (int) $entry['job_count'];
        $stats['total_jobs'] += $jobs;

        if (!empty($entry['ai_explicit'])) {
            $stats['ai_entries']++;
            $stats['ai_jobs'] += $jobs;
        }

        $date = (string) $entry['layoff_date'];
        if ($date !== '') {
            if ($min_date === '' || $date < $min_date) {
                $min_date = $date;
            }
            // ISO dates sort lexicographically, so string comparison is a valid range check
            if ($date >= $week_start && $date <= $week_end) {
                $stats['week_entries']++;
                $stats['week_jobs'] += $jobs;
            }
            if (strpos($date, $current_month) === 0) {
                $stats['month_entries']++;
                $stats['month_jobs'] += $jobs;
            }
            if (strpos($date, $current_year) === 0) {
                $stats['year_entries']++;
                $stats['year_jobs'] += $jobs;
            }
        }
    }

    if ($min_date !== '') {
        $stats['coverage_start'] = date('M Y', strtotime($min_date));
    }

    set_transient('alt_stats_cache', $stats, 5 * MINUTE_IN_SECONDS);
    return rest_ensure_response($stats);
}

function alt_api_company($request) {
    $name = sanitize_text_field(urldecode((string) $request['name']));
    if ($name === '') {
        return new WP_Error('alt_bad_request', 'Company name is required.', array('status' => 400));
    }

    $query = new WP_Query(array(
        'post_type'      => 'layoffs',
        'post_status'    => 'publish',
        'posts_per_page' => -1,
        'no_found_rows'  => true,
        'meta_query'     => array(
            array(
                'key'     => 'company_name',
                'value'   => $name,
                'compare' => 'LIKE',
            ),
        ),
    ));

    $rows = array();
    foreach ($query->posts as $post) {
        $rows[] = alt_entry_to_array($post->ID);
    }

    // Newest layoff first; empty dates sink to the bottom
    usort($rows, function ($a, $b) {
        return strcmp($b['layoff_date'], $a['layoff_date']);
    });

    return rest_ensure_response(array(
        'company'       => $name,
        'total_records' => count($rows),
        'total_jobs'    => array_sum(wp_list_pluck($rows, 'job_count')),
        'data'          => $rows,
    ));
}
