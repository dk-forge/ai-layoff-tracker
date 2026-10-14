<?php
/**
 * Server-rendered monthly totals under the dashboard charts (2.20.253, #446 item 1).
 *
 * Crawlers and no-JS readers saw only "Loading charts…" on [alt_dashboard].
 * This prints a plain table from the SAME cached /aggregate call the dashboard
 * chart reads: whole record, date_basis=notice, include=series. Like the chart
 * (toDateMonths + fillMonths in layoffs.js), the month the clock is inside is
 * cut at today and future-dated months are left out.
 */
if (!defined('ABSPATH')) exit;

/** Pure: newest-first rows for the table, at most $limit months. */
function alt_dashboard_totals_rows($series, $now_month, $limit = 24) {
    $rows = array();
    foreach ((array) $series as $s) {
        if (!is_array($s) || empty($s['month'])) continue;
        $m = (string) $s['month'];
        if ($now_month !== '' && strcmp($m, $now_month) > 0) continue;
        $src = (isset($s['to_date']) && is_array($s['to_date'])) ? $s['to_date'] : $s;
        $rows[] = array('month' => $m, 'jobs' => (int) ($src['jobs'] ?? 0), 'ai_jobs' => (int) ($src['ai_jobs'] ?? 0));
    }
    usort($rows, function ($a, $b) { return strcmp($b['month'], $a['month']); });
    return array_slice($rows, 0, max(1, (int) $limit));
}

/** Pure: the table markup. No rows, no table. */
function alt_dashboard_totals_table_html($rows) {
    if (empty($rows)) return '';
    $months = array('', 'January', 'February', 'March', 'April', 'May', 'June', 'July',
                    'August', 'September', 'October', 'November', 'December');
    $h = '<div class="alt-dashboard-totals" style="overflow-x:auto;margin-top:18px">'
       . '<table class="alt-dashboard-totals-table" style="width:100%;border-collapse:collapse">'
       . '<caption style="text-align:left;font-weight:700;padding:6px 0">Jobs cut per month, with the AI-attributed share (by filing date, most recent '
       . esc_html(count($rows)) . ' months)</caption>'
       . '<thead><tr><th scope="col" style="text-align:left">Month</th>'
       . '<th scope="col" style="text-align:right">Jobs cut</th>'
       . '<th scope="col" style="text-align:right">AI-attributed jobs</th></tr></thead><tbody>';
    foreach ($rows as $r) {
        $parts = explode('-', (string) $r['month']);
        $label = (count($parts) === 2 && isset($months[(int) $parts[1]])) ? $months[(int) $parts[1]] . ' ' . $parts[0] : $r['month'];
        $h .= '<tr><th scope="row" style="text-align:left;font-weight:400">' . esc_html($label) . '</th>'
            . '<td style="text-align:right">' . esc_html(number_format_i18n($r['jobs'])) . '</td>'
            . '<td style="text-align:right">' . esc_html(number_format_i18n($r['ai_jobs'])) . '</td></tr>';
    }
    return $h . '</tbody></table></div>';
}

/** Template entry: fetch through the cached aggregate handler, render. Fails to nothing. */
function alt_dashboard_totals_table() {
    if (!class_exists('WP_REST_Request') || !function_exists('alt_api_aggregate')) return '';
    $req = new WP_REST_Request('GET', '/layoffs/v1/aggregate');
    $req->set_query_params(array('date_basis' => 'notice', 'include' => 'series'));
    $resp = call_user_func('alt_api_aggregate', $req);
    if (is_wp_error($resp)) return '';
    $data = ($resp instanceof WP_REST_Response) ? $resp->get_data() : $resp;
    if (!is_array($data) || empty($data['series'])) return '';
    return alt_dashboard_totals_table_html(alt_dashboard_totals_rows($data['series'], (string) current_time('Y-m')));
}
