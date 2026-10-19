<?php
/**
 * /by-location: one ranked table of places (owner-approved 2026-10-19, made
 * the same way on the sibling Talent Intelligence Tracker so both read alike).
 *
 * READ-ONLY and public. Rows are places, columns are events, jobs cut,
 * AI-attributed events and AI-attributed jobs, for a calendar period.
 *
 * THE BASIS, stated once and returned in every response as `basis`:
 *   - VERIFIED cuts only (announced = 0), the headline's basis and the bar
 *     cards' drawn value [4]/[5]. An announced-only plan is not in this table.
 *   - Superset rows folded (superset_of = 0), so one event counts once.
 *   - Country is the STRICT JOB-LOCATION column, the headline basis. The
 *     inclusive country_basis=any union belongs to the results list and the
 *     exports; using it here would count one US-HQ global cut under two
 *     countries in a table whose rows are meant to add up.
 *   - AI-attributed = ai_explicit = 1 (the employer's own attribution).
 *
 * FILTERS come from alt_db_where, never parsed here. The table drops its OWN
 * dimension (the slicer contract every bar card keeps, so filtering to one
 * country still lists the others to switch to) and its own date dimension,
 * because the period selector replaces the page's date filter.
 *
 * NO CITY VIEW: wp_alt_layoffs has no city column. The switch offers what the
 * data holds, and alt_by_location_views() is the closed list.
 *
 * Retired sources: alt_retired_sources() governs the health ledger, not rows,
 * so there is nothing to mask here; any future row-level source exclusion
 * belongs in alt_db_where and reaches this table automatically.
 */

if (!defined('ABSPATH') && !function_exists('add_action')) { exit; }

/** view slug => grouping column. Closed list; the column never comes from the request. */
function alt_by_location_views() {
    return array(
        'country' => 'country',
        'state'   => 'state',
    );
}

function alt_by_location_periods() {
    return array('week', 'month', 'quarter', 'ytd', 'all');
}

/**
 * Calendar-aligned [from, to] for a period ending today (inclusive). `all` is
 * unbounded. An unknown period is the DEFAULT (ytd), never "everything": a
 * typo must not quietly widen the window. Pure, so it is tested by execution.
 */
function alt_by_location_period_bounds($period, $today) {
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', (string) $today, $m)) { return array(null, null); }
    $y = (int) $m[1]; $mo = (int) $m[2]; $d = (int) $m[3];
    if (!in_array($period, alt_by_location_periods(), true)) { $period = 'ytd'; }
    switch ($period) {
        case 'all':
            return array(null, null);
        case 'week':
            $ts = gmmktime(0, 0, 0, $mo, $d, $y);
            $dow = (int) gmdate('N', $ts); // 1 = Monday
            return array(gmdate('Y-m-d', $ts - ($dow - 1) * 86400), $today);
        case 'month':
            return array(sprintf('%04d-%02d-01', $y, $mo), $today);
        case 'quarter':
            return array(sprintf('%04d-%02d-01', $y, (int) (floor(($mo - 1) / 3) * 3 + 1)), $today);
        default:
            return array(sprintf('%04d-01-01', $y), $today);
    }
}

function alt_register_by_location_route() {
    register_rest_route('layoffs/v1', '/by-location', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_by_location',
        'permission_callback' => '__return_true',
    ));
}
add_action('rest_api_init', 'alt_register_by_location_route');

function alt_api_by_location(WP_REST_Request $r) {
    return alt_api_cached('by_location', $r, function () use ($r) {
        return alt_api_by_location_compute($r);
    });
}

function alt_api_by_location_compute(WP_REST_Request $r) {
    global $wpdb;
    $views = alt_by_location_views();
    $view = (string) $r->get_param('view');
    if (!isset($views[$view])) { $view = 'country'; }
    $col = $views[$view];
    $period = (string) $r->get_param('period');
    if (!in_array($period, alt_by_location_periods(), true)) { $period = 'ytd'; }
    $today = function_exists('alt_site_today') ? alt_site_today() : gmdate('Y-m-d');
    list($from, $to) = alt_by_location_period_bounds($period, $today);

    // The period REPLACES the page's date filter: a copy of the request with
    // the date params removed, then the period's own bounds applied below.
    $q = clone $r;
    foreach (array('from', 'to', 'years', 'quarters', 'months') as $p) { $q->set_param($p, null); }
    list($where, $params) = alt_db_where($q, $view);
    $date_col = alt_db_date_col($r);
    if ($from !== null) { $where .= " AND $date_col >= %s"; $params[] = $from; }
    if ($to !== null) { $where .= " AND $date_col <= %s"; $params[] = $to; }

    $table = alt_db_table();
    $rows = $wpdb->get_results(alt_db_prep(
        "SELECT $col k, COUNT(*) events, COALESCE(SUM(job_count),0) jobs,
                SUM(CASE WHEN ai_explicit = 1 THEN 1 ELSE 0 END) ai_events,
                COALESCE(SUM(CASE WHEN ai_explicit = 1 THEN job_count END),0) ai_jobs
           FROM $table
          WHERE $where AND superset_of = 0 AND announced = 0 AND $col <> ''
          GROUP BY $col ORDER BY jobs DESC, events DESC, k ASC LIMIT 300", $params));

    $out = array();
    foreach ($rows ?: array() as $row) {
        $out[] = array(
            'place'     => (string) $row->k,
            'events'    => (int) $row->events,
            'jobs'      => (int) $row->jobs,
            'ai_events' => (int) $row->ai_events,
            'ai_jobs'   => (int) $row->ai_jobs,
        );
    }
    return array(
        'view'   => $view,
        'period' => $period,
        'from'   => $from,
        'to'     => $to,
        'basis'  => 'verified cuts (announced excluded), each event counted once; '
                  . ($view === 'country' ? 'country = where the jobs are (job location), the headline basis' : 'US state = where the jobs are'),
        'rows'   => $out,
    );
}
