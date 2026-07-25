<?php
/**
 * CSV + JSON export downloads via admin-post.php (works for logged-out
 * visitors through the nopriv hooks).
 *
 * Exports read from the fast-query table (the complete dataset, including
 * bulk WARN notices) and stream in chunks so 100K+ rows never sit in memory.
 */

if (!defined('ABSPATH')) exit;

add_action('admin_post_alt_export_csv', 'alt_export_csv');
add_action('admin_post_nopriv_alt_export_csv', 'alt_export_csv');
add_action('admin_post_alt_export_json', 'alt_export_json');
add_action('admin_post_nopriv_alt_export_json', 'alt_export_json');
add_action('admin_post_alt_quarterly_appendix', 'alt_quarterly_appendix_download');
add_action('admin_post_nopriv_alt_quarterly_appendix', 'alt_quarterly_appendix_download');

/**
 * Neutralize spreadsheet formula injection: a cell starting with = + - @
 * would execute as a formula when the CSV is opened in Excel/Sheets.
 */
function alt_csv_guard($value) {
    $value = (string) $value;
    if ($value !== '' && in_array($value[0], array('=', '+', '-', '@'), true)) {
        return "'" . $value;
    }
    return $value;
}

/**
 * Exports honor the same filter params as /query (years, industry, state, q…)
 * so "download what I'm looking at" works. No params = the full dataset.
 */
function alt_export_filters() {
    $req = new WP_REST_Request('GET');
    $params = wp_unslash($_GET);
    unset($params['action']);
    $req->set_query_params($params);
    return alt_db_where($req); // array($where_sql, $params)
}

function alt_export_is_filtered() {
    $keys = array('years', 'quarters', 'months', 'industry', 'country', 'state',
        'sources', 'reasons', 'roles', 'from', 'to', 'q', 'company', 'keyword', 'min_jobs',
        'ai', 'ai_broad', 'date_basis', 'stage');
    foreach ($keys as $k) {
        if (!empty($_GET[$k])) return true;
    }
    return false;
}

/** Iterate matching rows in id-keyed chunks, calling $cb($row) per row. */
function alt_export_walk($cb) {
    global $wpdb;
    $table = alt_db_table();
    list($where, $params) = alt_export_filters();
    $last = 0;
    while (true) {
        $sql = "SELECT * FROM $table WHERE ($where) AND id > %d ORDER BY id ASC LIMIT 2000";
        $rows = $wpdb->get_results($wpdb->prepare($sql, array_merge($params, array($last))));
        if (!$rows) break;
        foreach ($rows as $row) {
            $last = (int) $row->id;
            $cb($row);
        }
        if (count($rows) < 2000) break;
    }
}

/**
 * Lightweight per-IP throttle for the anonymous full-dataset exports. Bulk reuse
 * is welcome (the data is licensed for it), but repeated concurrent full-table
 * downloads shouldn't be able to hammer the origin. 20 exports / 10 min per IP;
 * over that, 429 + exit. Filtered exports and the API remain the fast paths.
 */
function alt_export_throttle() {
    $ip = isset($_SERVER['REMOTE_ADDR']) ? preg_replace('/[^0-9a-f:.]/i', '', (string) $_SERVER['REMOTE_ADDR']) : '0';
    $key = 'alt_export_rl_' . md5($ip);
    $n = (int) get_transient($key);
    if ($n >= 20) {
        status_header(429);
        nocache_headers();
        header('Retry-After: 600');
        header('Content-Type: text/plain; charset=utf-8');
        echo "Export rate limit reached. The full dataset is free to reuse — please wait a few minutes, filter your export, or use the public API.";
        exit;
    }
    set_transient($key, $n + 1, 10 * MINUTE_IN_SECONDS);
}

function alt_export_csv() {
    alt_export_throttle();
    nocache_headers();
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="ai-layoff-tracker-' . (alt_export_is_filtered() ? 'filtered-' : '') . gmdate('Y-m-d') . '.csv"');

    $out = fopen('php://output', 'w');

    // UTF-8 BOM so Excel renders umlauts/CJK correctly instead of mojibake
    fwrite($out, "\xEF\xBB\xBF");

    fputcsv($out, array(
        'company_name', 'ticker', 'job_count', 'layoff_date', 'industry',
        'country', 'state', 'roles', 'role_categories', 'source_type', 'verification_level', 'source_url',
        'source_list_url', 'ai_explicit', 'ai_language', 'reason_tags', 'excerpt', 'source_attribution',
    ));

    alt_export_walk(function ($row) use ($out) {
        fputcsv($out, array(
            alt_csv_guard($row->company),
            alt_csv_guard((string) $row->ticker),
            (int) $row->job_count,
            $row->layoff_date ?: '',
            alt_csv_guard($row->industry),
            alt_csv_guard($row->country),
            alt_csv_guard($row->state),
            alt_csv_guard((string) $row->roles),
            // Public categories only — the ',unknown,' checked-marker is
            // queue bookkeeping, not data.
            alt_csv_guard(implode('|', array_diff(alt_db_unpack_tags($row->role_categories ?? ''), array('unknown')))),
            alt_csv_guard($row->source_type),
            alt_csv_guard($row->verification_level),
            alt_csv_guard((string) $row->source_url),
            alt_csv_guard($row->source_type === 'warn' && function_exists('alt_state_warn_list_url')
                ? alt_state_warn_list_url($row->state) : ''),
            $row->ai_explicit ? 'true' : 'false',
            alt_csv_guard((string) $row->ai_language),
            alt_csv_guard(implode('|', alt_db_unpack_tags($row->reason_tags))),
            alt_csv_guard((string) $row->excerpt),
            'AI Layoff Tracker - asktherecruiter.com',
        ));
    });

    fclose($out);
    exit;
}

function alt_export_json() {
    alt_export_throttle();
    nocache_headers();
    header('Content-Type: application/json; charset=utf-8');
    header('Content-Disposition: attachment; filename="ai-layoff-tracker-' . (alt_export_is_filtered() ? 'filtered-' : '') . gmdate('Y-m-d') . '.json"');

    echo '{';
    echo '"source":"AI Layoff Tracker - asktherecruiter.com",';
    echo '"license":"Free to use with attribution to asktherecruiter.com.",';
    echo '"source_url":' . wp_json_encode(home_url('/ai-layoff-tracker/')) . ',';
    echo '"generated":"' . gmdate('Y-m-d\TH:i:s\Z') . '",';
    echo '"data":[';

    // Count while streaming (rather than a COUNT(*) up front) so total_records
    // always equals the rows actually emitted, even if writes land mid-export.
    $count = 0;
    alt_export_walk(function ($row) use (&$count) {
        $entry = alt_db_row_to_array($row);
        unset($entry['id']);
        echo ($count ? ',' : '') . wp_json_encode($entry, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        $count++;
    });

    echo '],"total_records":' . $count . '}';
    exit;
}

/**
 * Download a CSV or JSON appendix from a report's already-stored snapshot.
 * This deliberately has no query-builder or database aggregate call: a report
 * appendix must remain byte-for-byte about the historic report data, not the
 * current live dataset. JSON mirrors the readable REST appendix endpoint.
 */
function alt_quarterly_appendix_download() {
    $report_id = sanitize_text_field((string) ($_GET['report_id'] ?? ''));
    $format = sanitize_key((string) ($_GET['format'] ?? 'csv'));
    $report = function_exists('alt_quarterly_report_by_id') ? alt_quarterly_report_by_id($report_id) : null;
    if (!$report || !function_exists('alt_quarterly_report_appendix_data')) {
        wp_die('Quarterly report appendix not found.', 'Not found', array('response' => 404));
    }
    $appendix = alt_quarterly_report_appendix_data($report);
    $filename = 'state-of-layoffs-' . sanitize_file_name($report_id) . '-appendix';
    nocache_headers();
    if ($format === 'json') {
        header('Content-Type: application/json; charset=utf-8');
        header('Content-Disposition: attachment; filename="' . $filename . '.json"');
        echo wp_json_encode($appendix, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        exit;
    }
    if ($format !== 'csv') wp_die('Appendix format must be csv or json.', 'Bad request', array('response' => 400));
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="' . $filename . '.csv"');
    $out = fopen('php://output', 'w');
    fwrite($out, "\xEF\xBB\xBF");
    fputcsv($out, array('section', 'metric_or_dimension', 'label', 'jobs', 'ai_attributed_jobs', 'report_id', 'dataset_revision', 'period_from', 'period_to', 'appendix_scope'));
    $meta = array(
        $appendix['report_id'], (int) $appendix['dataset_revision'],
        (string) ($appendix['period']['from'] ?? ''), (string) ($appendix['period']['to'] ?? ''),
        (string) $appendix['appendix_scope'],
    );
    $write = function ($section, $metric, $label, $jobs, $ai_jobs = '') use ($out, $meta) {
        fputcsv($out, array_merge(array($section, $metric, $label, $jobs, $ai_jobs), $meta));
    };
    foreach (array('verified', 'announced', 'ai_primary_verified_subset') as $section) {
        $data = $appendix['snapshot'][$section] ?? array();
        foreach (($data['totals'] ?? array()) as $metric => $value) {
            if (is_scalar($value)) $write($section, 'total', $metric, $value);
        }
        foreach (array('top_industries' => 'industry', 'top_countries' => 'country', 'top_states' => 'state', 'reasons' => 'reason') as $key => $dimension) {
            foreach (($data[$key] ?? array()) as $row) {
                $write($section, $dimension, (string) ($row[0] ?? ''), (int) ($row[1] ?? 0), isset($row[2]) ? (int) $row[2] : '');
            }
        }
        foreach (($data['series'] ?? array()) as $row) {
            $write($section, 'month', (string) ($row['month'] ?? ''), (int) ($row['jobs'] ?? 0), (int) ($row['ai_jobs'] ?? 0));
        }
    }
    fclose($out);
    exit;
}
