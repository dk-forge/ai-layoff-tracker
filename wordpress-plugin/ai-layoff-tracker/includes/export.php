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

/** Iterate the fast table in id-keyed chunks, calling $cb($row) per row. */
function alt_export_walk($cb) {
    global $wpdb;
    $table = alt_db_table();
    $last = 0;
    while (true) {
        $rows = $wpdb->get_results($wpdb->prepare(
            "SELECT * FROM $table WHERE id > %d ORDER BY id ASC LIMIT 2000", $last));
        if (!$rows) break;
        foreach ($rows as $row) {
            $last = (int) $row->id;
            $cb($row);
        }
        if (count($rows) < 2000) break;
    }
}

function alt_export_csv() {
    nocache_headers();
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="ai-layoff-tracker-' . gmdate('Y-m-d') . '.csv"');

    $out = fopen('php://output', 'w');

    // UTF-8 BOM so Excel renders umlauts/CJK correctly instead of mojibake
    fwrite($out, "\xEF\xBB\xBF");

    fputcsv($out, array(
        'company_name', 'ticker', 'job_count', 'layoff_date', 'industry',
        'country', 'state', 'roles', 'source_type', 'verification_level', 'source_url',
        'ai_explicit', 'ai_language', 'reason_tags', 'excerpt', 'source_attribution',
    ));

    alt_export_walk(function ($row) use ($out) {
        fputcsv($out, array(
            alt_csv_guard($row->company),
            alt_csv_guard((string) $row->ticker),
            (int) $row->job_count,
            $row->layoff_date ?: '',
            alt_csv_guard($row->industry),
            alt_csv_guard($row->country),
            $row->state,
            alt_csv_guard((string) $row->roles),
            $row->source_type,
            $row->verification_level,
            alt_csv_guard((string) $row->source_url),
            $row->ai_explicit ? 'true' : 'false',
            alt_csv_guard((string) $row->ai_language),
            implode('|', alt_db_unpack_tags($row->reason_tags)),
            alt_csv_guard((string) $row->excerpt),
            'AI Layoff Tracker - asktherecruiter.com',
        ));
    });

    fclose($out);
    exit;
}

function alt_export_json() {
    global $wpdb;
    $total = (int) $wpdb->get_var("SELECT COUNT(*) FROM " . alt_db_table());

    nocache_headers();
    header('Content-Type: application/json; charset=utf-8');
    header('Content-Disposition: attachment; filename="ai-layoff-tracker-' . gmdate('Y-m-d') . '.json"');

    echo '{';
    echo '"source":"AI Layoff Tracker - asktherecruiter.com",';
    echo '"license":"Free to use with attribution to asktherecruiter.com.",';
    echo '"source_url":' . wp_json_encode(home_url('/ai-layoff-tracker/')) . ',';
    echo '"generated":"' . gmdate('Y-m-d\TH:i:s\Z') . '",';
    echo '"total_records":' . $total . ',';
    echo '"data":[';

    $first = true;
    alt_export_walk(function ($row) use (&$first) {
        $entry = alt_db_row_to_array($row);
        unset($entry['id']);
        echo ($first ? '' : ',') . wp_json_encode($entry, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        $first = false;
    });

    echo ']}';
    exit;
}
