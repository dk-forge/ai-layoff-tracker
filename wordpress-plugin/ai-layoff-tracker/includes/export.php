<?php
/**
 * CSV + JSON export downloads via admin-post.php (works for logged-out
 * visitors through the nopriv hooks).
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

function alt_export_csv() {
    $entries = alt_get_all_entries();

    nocache_headers();
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="ai-layoff-tracker-' . gmdate('Y-m-d') . '.csv"');

    $out = fopen('php://output', 'w');

    // UTF-8 BOM so Excel renders umlauts/CJK correctly instead of mojibake
    fwrite($out, "\xEF\xBB\xBF");

    fputcsv($out, array(
        'company_name', 'ticker', 'job_count', 'layoff_date', 'industry',
        'country', 'source_type', 'verification_level', 'source_url',
        'ai_explicit', 'ai_language', 'reason_tags', 'excerpt',
    ));

    foreach ($entries as $entry) {
        fputcsv($out, array(
            alt_csv_guard($entry['company_name']),
            alt_csv_guard((string) $entry['ticker']),
            $entry['job_count'],
            $entry['layoff_date'],
            alt_csv_guard($entry['industry']),
            alt_csv_guard($entry['country']),
            $entry['source_type'],
            $entry['verification_level'],
            alt_csv_guard($entry['source_url']),
            $entry['ai_explicit'] ? 'true' : 'false',
            alt_csv_guard((string) $entry['ai_language']),
            implode('|', $entry['reason_tags']),
            alt_csv_guard($entry['excerpt']),
        ));
    }

    fclose($out);
    exit;
}

function alt_export_json() {
    $entries = alt_get_all_entries();

    // Match the spec's published JSON schema (no internal post ID)
    $data = array();
    foreach ($entries as $entry) {
        unset($entry['id']);
        $data[] = $entry;
    }

    nocache_headers();
    header('Content-Type: application/json; charset=utf-8');
    header('Content-Disposition: attachment; filename="ai-layoff-tracker-' . gmdate('Y-m-d') . '.json"');

    echo wp_json_encode(array(
        'generated'     => gmdate('Y-m-d\TH:i:s\Z'),
        'total_records' => count($data),
        'data'          => $data,
    ), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

    exit;
}
