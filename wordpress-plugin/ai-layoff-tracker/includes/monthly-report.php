<?php
/**
 * Monthly AI-layoffs report: release timing, figures and the press summary.
 *
 * The report page itself (?period=YYYY-MM, templates/page-report.php) renders
 * live from the database. This module adds what turns it into a monthly
 * release a newsroom can plan around:
 *
 *   - alt_mr_first_business_day(): release day = first business day of the
 *     following month. Challenger, Gray & Christmas publishes its job-cuts
 *     report around the first Thursday; the first business day is never later
 *     than that (tests/test_monthly_report.py walks 2024-2030).
 *   - alt_mr_latest_period(): the newest released month.
 *   - alt_mr_figures(): the numbers, same population and basis as the report
 *     page (superset_of=0, effective date, verified = announced=0).
 *   - alt_mr_pitch(): a press-release-style summary built ONLY from the figures
 *     passed in. A missing figure produces no sentence, never a zero.
 *   - a daily WP-cron tick that freezes the latest release and its pitch into
 *     the `alt_monthly_report_latest` option, read by the press page and by the
 *     press-list sender (includes/press-list.php).
 *
 * NOTHING HERE SENDS EMAIL. Journalist outreach is an explicit admin click on
 * the press list screen; there is no automatic cold send.
 * Runbook: docs/RUNBOOK_GROWTH.md, "Monthly report".
 */
if (!defined('ABSPATH')) exit;

/** First business day (US) of a month: not a weekend, New Year's, or Labor Day. */
function alt_mr_first_business_day($y, $m) {
    $y = (int) $y; $m = (int) $m;
    for ($d = 1; $d <= 7; $d++) {
        $ts = gmmktime(12, 0, 0, $m, $d, $y);
        $dow = (int) gmdate('N', $ts); // 1 = Monday .. 7 = Sunday
        if ($dow >= 6) continue;
        // New Year's Day, and its Monday observance when 1 January is a Sunday.
        if ($m === 1 && ($d === 1 || ($d === 2 && $dow === 1))) continue;
        // Labor Day: the first Monday of September.
        if ($m === 9 && $dow === 1) continue;
        return $d;
    }
    return 1;
}

/** The newest month whose report is released as of $today (Y-m-d), as YYYY-MM. */
function alt_mr_latest_period($today) {
    $ts = strtotime((string) $today . ' 12:00:00 UTC');
    if (!$ts) $ts = time();
    $y = (int) gmdate('Y', $ts); $m = (int) gmdate('n', $ts); $d = (int) gmdate('j', $ts);
    $back = ($d >= alt_mr_first_business_day($y, $m)) ? 1 : 2;
    $m -= $back;
    while ($m < 1) { $m += 12; $y--; }
    return sprintf('%04d-%02d', $y, $m);
}

/** Press-release summary. Pure: every figure comes from $f. */
function alt_mr_pitch(array $f) {
    $nf = function ($n) { return number_format((int) $n); };
    $label = (string) ($f['label'] ?? '');
    $v = (int) ($f['verified_jobs'] ?? 0);
    $out = array();
    $out[] = 'AI Layoff Tracker monthly report, ' . $label . '.';
    $lead = 'The AI Layoff Tracker by AskTheRecruiter.com documented ' . $nf($v)
        . ' verified job cuts worldwide in ' . $label;
    if (!empty($f['entries'])) $lead .= ', across ' . $nf($f['entries']) . ' separate entries';
    $out[] = $lead . '.';
    $pv = (int) ($f['prior_verified_jobs'] ?? 0);
    if ($pv > 0 && !empty($f['prior_label'])) {
        $pct = (int) round(100 * ($v - $pv) / $pv);
        $out[] = 'That is ' . ($pct >= 0 ? 'up ' : 'down ') . abs($pct) . '% from '
            . $nf($pv) . ' in ' . $f['prior_label'] . '.';
    }
    $ai = (int) ($f['ai_verified_jobs'] ?? 0);
    if ($ai > 0 && $v > 0) {
        $out[] = 'Employers attributed ' . $nf($ai) . ' of those cuts ('
            . (int) round(100 * $ai / $v) . '%) to AI or automation in their own words.';
    }
    $list = function ($rows) use ($nf) {
        $parts = array();
        foreach (array_slice((array) $rows, 0, 5) as $r) {
            if (!is_array($r) || (string) ($r[0] ?? '') === '') continue;
            $parts[] = $r[0] . ' (' . $nf($r[1] ?? 0) . ')';
        }
        return implode(', ', $parts);
    };
    if ($s = $list($f['top_companies'] ?? array())) $out[] = 'Largest employers cutting: ' . $s . '.';
    if ($s = $list($f['top_countries'] ?? array())) $out[] = 'Top countries: ' . $s . '.';
    if ($s = $list($f['top_states'] ?? array())) $out[] = 'Top US states: ' . $s . '.';
    $out[] = 'Methodology: every figure links to an SEC filing, a state WARN notice or a named report, and AI attribution requires the employer\'s own words. Counts are a documented floor, not a census.';
    if (!empty($f['report_url'])) $out[] = 'Full report: ' . $f['report_url'];
    if (!empty($f['csv_url'])) $out[] = 'Data (CSV): ' . $f['csv_url'];
    if (!empty($f['contact_url'])) $out[] = 'Press contact: ' . $f['contact_url'];
    return implode("\n", $out);
}

/** CSV download of exactly one report period, on the report's own basis. */
function alt_mr_csv_url($from, $to, $us_only = false) {
    $args = array('action' => 'alt_export_csv', 'from' => $from, 'to' => $to, 'date_basis' => 'effective');
    if ($us_only) $args['country'] = 'United States';
    return add_query_arg($args, admin_url('admin-post.php'));
}

/** Figures for one month. Same population as templates/page-report.php. */
function alt_mr_figures($period, $us_only = false) {
    global $wpdb;
    if (!preg_match('/^(\d{4})-(\d{2})$/', (string) $period, $mm)) return null;
    $y = (int) $mm[1]; $m = (int) $mm[2];
    $from = sprintf('%04d-%02d-01', $y, $m); $to = gmdate('Y-m-t', strtotime($from));
    $pts = strtotime($from . ' -1 month');
    $pfrom = gmdate('Y-m-01', $pts); $pto = gmdate('Y-m-t', $pts);
    $cache = 'alt_mr_fig_' . md5((string) get_option('alt_data_ver', 1) . '|' . $period . '|' . ($us_only ? 'us' : 'w'));
    $hit = get_transient($cache);
    if (is_array($hit)) return $hit;
    $t = alt_db_table();
    $geo = $us_only ? " AND country = 'United States'" : '';
    $sum = function ($a, $b) use ($wpdb, $t, $geo) {
        return $wpdb->get_row($wpdb->prepare(
            "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                    SUM(CASE WHEN announced=0 THEN 1 ELSE 0 END) n,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) ai
             FROM $t WHERE superset_of=0 AND layoff_date BETWEEN %s AND %s$geo", $a, $b), ARRAY_A) ?: array();
    };
    $top = function ($col, $extra = '') use ($wpdb, $t, $geo, $from, $to) {
        $rows = $wpdb->get_results($wpdb->prepare(
            "SELECT $col k, COALESCE(SUM(job_count),0) j FROM $t
             WHERE superset_of=0 AND announced=0 AND layoff_date BETWEEN %s AND %s AND $col <> ''$geo$extra
             GROUP BY $col ORDER BY j DESC LIMIT 5", $from, $to), ARRAY_A) ?: array();
        return array_map(function ($r) { return array((string) $r['k'], (int) $r['j']); }, $rows);
    };
    $cur = $sum($from, $to); $prev = $sum($pfrom, $pto);
    $months = array(1=>'January','February','March','April','May','June','July','August','September','October','November','December');
    $fig = array(
        'period'              => $period,
        'from'                => $from, 'to' => $to,
        'label'               => $months[$m] . ' ' . $y,
        'prior_label'         => $months[(int) gmdate('n', $pts)] . ' ' . gmdate('Y', $pts),
        'verified_jobs'       => (int) ($cur['v'] ?? 0),
        'entries'             => (int) ($cur['n'] ?? 0),
        'ai_verified_jobs'    => (int) ($cur['ai'] ?? 0),
        'prior_verified_jobs' => (int) ($prev['v'] ?? 0),
        'top_companies'       => $top('company'),
        'top_states'          => $top('state', " AND country = 'United States'"),
        'top_countries'       => $us_only ? array() : $top('country'),
        'report_url'          => add_query_arg(array_filter(array('period' => $period, 'scope' => $us_only ? 'us' : '')),
                                               home_url('/ai-layoff-tracker/report/')),
        'csv_url'             => alt_mr_csv_url($from, $to, $us_only),
        'contact_url'         => home_url('/contact/'),
    );
    set_transient($cache, $fig, HOUR_IN_SECONDS);
    return $fig;
}

/**
 * Daily tick: once the first business day of a month is reached, freeze the
 * previous month's figures and pitch. Idempotent, and it catches up on its own
 * if WP-cron missed a day (it compares periods, not dates).
 */
function alt_monthly_report_tick() {
    $today = function_exists('alt_site_now_ts') ? gmdate('Y-m-d', alt_site_now_ts()) : current_time('Y-m-d');
    $period = alt_mr_latest_period($today);
    $have = get_option('alt_monthly_report_latest');
    if (is_array($have) && ($have['period'] ?? '') === $period) return;
    $fig = alt_mr_figures($period);
    if (!$fig) return;
    update_option('alt_monthly_report_latest', array(
        'period'       => $period,
        'label'        => $fig['label'],
        'report_url'   => $fig['report_url'],
        'csv_url'      => $fig['csv_url'],
        'pitch'        => alt_mr_pitch($fig),
        'generated_at' => gmdate('c'),
    ), false);
}
add_action('alt_monthly_report_tick', 'alt_monthly_report_tick');

add_action('init', function () {
    if (!wp_next_scheduled('alt_monthly_report_tick')) {
        // 10:00 UTC = 06:00 ET: before the US news day and before Challenger.
        $next = strtotime(gmdate('Y-m-d') . ' 10:00:00 UTC');
        if ($next <= time()) $next += DAY_IN_SECONDS;
        wp_schedule_event($next, 'daily', 'alt_monthly_report_tick');
    }
}, 30);
