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
 *
 * TAB and CR are in that list because Excel and LibreOffice STRIP leading
 * whitespace before deciding what a cell is, so "\t=cmd|..." is read as
 * "=cmd|..." and the guard that only looked at $value[0] saw a tab, found it
 * harmless and let the formula through intact. Same for a leading \r, which
 * additionally lets a value forge a row break inside a quoted field. This is
 * defence in depth, not a live hole: every value reaching here is normalised
 * through a fixed vocabulary or is a number. Depth is the point.
 */
function alt_csv_guard($value) {
    $value = (string) $value;
    if ($value === '') return $value;
    $lead = ltrim($value, " \t\r\n");
    if ($lead !== '' && in_array($lead[0], array('=', '+', '-', '@'), true)) {
        return "'" . $value;
    }
    if (in_array($value[0], array('=', '+', '-', '@', "\t", "\r"), true)) {
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
    // REFUSE ARRAY-SHAPED PARAMS. DO NOT DROP THEM.
    // ?q[]=x makes $_GET['q'] an array; alt_db_where() hands it to a string
    // function and PHP fatals - in an export that lands AFTER the throttle
    // slot is burned and after the 200, the Content-Disposition header, the
    // BOM and the header row are on the wire.
    //
    // The first fix here dropped the offending key, and the audit caught that
    // as the graver defect: dropping ?company[]=x silently widens the request
    // to the WHOLE corpus and serves it under a filename saying "filtered".
    // A confident wrong answer beats a visible failure only in appearance.
    foreach ($params as $k => $v) {
        if (!is_scalar($v) || !is_scalar($k)) {
            status_header(400);
            nocache_headers();
            header('Content-Type: text/plain; charset=utf-8');
            echo "Bad request: filter parameters must be single values.\n";
            exit;
        }
    }
    $req->set_query_params(array_map('strval', $params));
    return alt_db_where($req); // array($where_sql, $params)
}

/**
 * Does this export carry a filter? Decides whether the download is named
 * `ai-layoff-tracker-filtered-<date>` or `ai-layoff-tracker-<date>`, so getting
 * it wrong ships a partial extract under the full-dataset filename.
 *
 * Reads the single canonical list in db.php instead of keeping its own copy —
 * its own copy is exactly what drifted, sitting 6 params behind alt_db_where
 * (ai_primary, employer_country, review_status and the three *_missing backlog
 * filters). The function_exists fallback is the FTP-deploy race rule: db.php can
 * be mid-upload, and a hard dependency would fatal the export. The fallback is
 * deliberately the corrected, broader list so a mid-deploy request still labels
 * these correctly. `date_basis` is dropped on purpose: it reinterprets the other
 * filters rather than narrowing anything by itself, so alone it does not make an
 * export partial.
 */
function alt_export_is_filtered() {
    $keys = function_exists('alt_filter_param_names')
        ? alt_filter_param_names()
        : array('years', 'quarters', 'months', 'from', 'to', 'industry', 'country',
            'employer_country', 'state', 'sources', 'reasons', 'roles', 'q',
            'company', 'keyword', 'min_jobs', 'stage', 'ai', 'ai_broad',
            'ai_primary', 'review_status', 'context_missing', 'industry_missing',
            'roles_missing', 'company_key', 'sourced', 'exclude_supersets');
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
        echo "Export rate limit reached. The full dataset is free to reuse. Please wait a few minutes, filter your export, or use the public API.";
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

    /*
      announcement_date SITS BESIDE layoff_date BECAUSE THE EXPORT HAS TO BE
      ABLE TO REPRODUCE THE VIEW IT CAME FROM.

      This file has always accepted `date_basis` — alt_export_filters() hands
      the request straight to alt_db_where(), so a `date_basis=notice` export
      selects its rows on COALESCE(announcement_date, layoff_date). Since 2.20.4
      that is the tracker page's DEFAULT, so the ordinary "CSV" link beside the
      headline shipped rows chosen by a date the file did not contain. A
      journalist could not re-derive the count they had just been shown, on the
      one artifact whose entire purpose is that they can check it.

      Not a bucketing bug, and that is why it outlived six of them: every
      individual row was correct. The provenance was missing, and a missing
      column looks like a design decision rather than a defect.

      The JSON export already carried the field (alt_db_row_to_array() has
      emitted it for as long as the column has existed), so the two formats of
      the same download disagreed about what a row is. They agree now.

      Placed next to layoff_date rather than appended: the CSV is the format
      somebody opens in a spreadsheet, and two dates for one event belong in
      adjacent columns. Nothing in this repo reads the header positionally, and
      the JSON export remains the stable machine surface.
    */
    fputcsv($out, array(
        'company_name', 'ticker', 'job_count', 'layoff_date', 'announcement_date', 'industry',
        'country', 'state', 'roles', 'role_categories', 'source_type', 'verification_level', 'source_url',
        'source_list_url', 'ai_explicit', 'ai_language', 'reason_tags', 'excerpt', 'source_attribution',
    ));

    alt_export_walk(function ($row) use ($out) {
        fputcsv($out, array(
            alt_csv_guard($row->company),
            alt_csv_guard((string) $row->ticker),
            (int) $row->job_count,
            $row->layoff_date ?: '',
            $row->announcement_date ?: '',
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
    // Same formula guard the row export uses. It was absent here entirely,
    // which is the more interesting half of the defect: the appendix is the
    // artifact a journalist opens in a spreadsheet and cites, and `label`
    // carries an industry, a country, a state or a reason tag, all of which
    // originate in extracted text before normalisation reduces them.
    $write = function ($section, $metric, $label, $jobs, $ai_jobs = '') use ($out, $meta) {
        fputcsv($out, array_map('alt_csv_guard',
            array_merge(array($section, $metric, $label, $jobs, $ai_jobs), $meta)));
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
