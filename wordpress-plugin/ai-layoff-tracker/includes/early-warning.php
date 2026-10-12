<?php
/**
 * Early-warning view (issue #478 item 1), rendered inside [alt_labour_context].
 *
 * For a chosen industry it lines up, month by month:
 *   - the tracker's own count of US WARN notices (filed that month),
 *   - FRED weekly initial jobless claims (national, averaged per month),
 *   - BLS JOLTS layoffs and discharges for the matching supersector,
 *   - Census QWI separations for the matching NAICS sectors, summed over the
 *     states that published (quarterly, placed on the quarter's last month).
 *
 * THE STATUS LABEL (cooling / stable / heating up) IS COMPUTED ONLY FROM THE
 * OFFICIAL SERIES, never from the tracker's own counts, by this rule
 * (alt_ew_status, pinned by railway/tests/test_early_warning.py):
 *
 *   1. Monthly series (claims, JOLTS): mean of the latest 3 months against the
 *      mean of the 12 months before them. Quarterly QWI is not seasonally
 *      adjusted, so it compares the latest quarter with the same quarter one
 *      year earlier instead.
 *   2. A change of +5% or more is "rising", -5% or less is "falling", anything
 *      between is "flat". A series without enough history is not judged.
 *   3. At least two official series must be judged, or no label is shown.
 *   4. "Heating up" when at least two are rising and more rise than fall;
 *      "Cooling" when at least two are falling and more fall than rise;
 *      otherwise "Stable".
 *
 * These are all-cause measures. Nothing here says why anyone lost a job and
 * nothing here attributes any change to AI.
 */
if (!defined('ABSPATH')) exit;

if (!defined('ALT_EW_MONTHS')) define('ALT_EW_MONTHS', 36);
if (!defined('ALT_EW_THRESHOLD')) define('ALT_EW_THRESHOLD', 0.05);

/**
 * Industry key => [label, tracker industries, JOLTS supersector label, QWI
 * NAICS sectors]. The pairing is approximate: tracker industries are a
 * newsroom vocabulary, JOLTS and QWI use NAICS. The caption says so.
 */
function alt_ew_industries() {
    return array(
        'all' => array('All industries', null, 'Total nonfarm', null),
        'information' => array('Information and technology', array('Technology', 'Telecom', 'Media & Entertainment'), 'Information', array('51')),
        'manufacturing' => array('Manufacturing', array('Manufacturing', 'Automotive', 'Aerospace & Defense'), 'Manufacturing', array('31-33')),
        'finance' => array('Finance and insurance', array('Finance & Insurance'), 'Financial activities', array('52', '53')),
        'trade' => array('Retail, trade and transport', array('Retail & E-commerce', 'Logistics & Transport', 'Consumer Goods'), 'Trade, transportation, and utilities', array('42', '44-45', '48-49', '22')),
        'professional' => array('Professional and business services', array('Professional Services'), 'Professional and business services', array('54', '55', '56')),
        'health_education' => array('Health care and education', array('Healthcare & Pharma', 'Education'), 'Private education and health services', array('61', '62')),
        'leisure' => array('Leisure and hospitality', array('Food & Hospitality', 'Airlines & Travel'), 'Leisure and hospitality', array('71', '72')),
        'construction' => array('Construction and real estate', array('Real Estate & Construction'), 'Construction', array('23')),
    );
}

/** Mean of numeric values, or null for an empty list. */
function alt_ew_mean($vals) {
    $vals = array_values(array_filter((array) $vals, 'is_numeric'));
    return $vals ? array_sum($vals) / count($vals) : null;
}

/**
 * Rule step 1 for a monthly series: latest $recent mean vs the $base months
 * before them, as a fraction (0.06 = +6%). $vals is chronological, no gaps
 * assumed beyond what the caller passes. Null when history is too short or the
 * base is not positive.
 */
function alt_ew_change($vals, $recent = 3, $base = 12) {
    $vals = array_values(array_filter((array) $vals, 'is_numeric'));
    if (count($vals) < $recent + $base) return null;
    $r = alt_ew_mean(array_slice($vals, -$recent));
    $b = alt_ew_mean(array_slice($vals, -($recent + $base), $base));
    if ($b === null || $b <= 0) return null;
    return $r / $b - 1;
}

/** Rule step 1 for quarterly QWI: latest quarter vs the same quarter a year before. */
function alt_ew_change_yoy($by_quarter) {
    if (!is_array($by_quarter) || !$by_quarter) return null;
    ksort($by_quarter);
    $last = array_key_last($by_quarter);
    if (!preg_match('/^(\d{4})-Q([1-4])$/', (string) $last, $m)) return null;
    $prev = ((int) $m[1] - 1) . '-Q' . $m[2];
    if (!isset($by_quarter[$prev]) || !is_numeric($by_quarter[$prev]) || $by_quarter[$prev] <= 0) return null;
    return $by_quarter[$last] / $by_quarter[$prev] - 1;
}

/** Rule step 2: a change => 'up' | 'down' | 'flat', or null when not judged. */
function alt_ew_direction($change) {
    if ($change === null || !is_numeric($change)) return null;
    if ($change >= ALT_EW_THRESHOLD) return 'up';
    if ($change <= -ALT_EW_THRESHOLD) return 'down';
    return 'flat';
}

/**
 * Rule steps 3 and 4. $changes is name => fraction|null for OFFICIAL series
 * only. Returns 'heating' | 'cooling' | 'stable', or null with fewer than two
 * judged series.
 */
function alt_ew_status($changes) {
    $up = $down = $judged = 0;
    foreach ((array) $changes as $c) {
        $d = alt_ew_direction($c);
        if ($d === null) continue;
        $judged++;
        if ($d === 'up') $up++;
        if ($d === 'down') $down++;
    }
    if ($judged < 2) return null;
    if ($up >= 2 && $up > $down) return 'heating';
    if ($down >= 2 && $down > $up) return 'cooling';
    return 'stable';
}

/** Plain words for a status key. */
function alt_ew_status_label($status) {
    $map = array('heating' => 'Heating up', 'cooling' => 'Cooling', 'stable' => 'Stable');
    return $map[$status] ?? '';
}

/** "+6%" / "-3%" / "0%". */
function alt_ew_pct($change) {
    $p = (int) round($change * 100);
    return ($p > 0 ? '+' : '') . $p . '%';
}

/** Monthly mean of weekly FRED ICSA rows, ym => value. */
function alt_ew_claims_monthly($fred) {
    $sum = $n = array();
    foreach ((array) ($fred['datasets']['observations'] ?? array()) as $row) {
        if (!is_array($row) || ($row[0] ?? '') !== 'ICSA' || !isset($row[1], $row[2]) || !is_numeric($row[2])) continue;
        $ym = substr((string) $row[1], 0, 7);
        $sum[$ym] = ($sum[$ym] ?? 0) + (float) $row[2];
        $n[$ym] = ($n[$ym] ?? 0) + 1;
    }
    $out = array();
    foreach ($sum as $ym => $s) $out[$ym] = round($s / $n[$ym]);
    ksort($out);
    return $out;
}

/** JOLTS layoffs and discharges (thousands) for one supersector label, ym => value. */
function alt_ew_jolts_monthly($bls, $label) {
    foreach ((array) ($bls['datasets']['jolts'] ?? array()) as $s) {
        if (!is_array($s) || ($s['dim'] ?? '') !== 'industry' || ($s['measure'] ?? '') !== 'layoffs_discharges'
            || (string) ($s['label'] ?? '') !== $label) continue;
        $out = array();
        foreach ((array) ($s['points'] ?? array()) as $p) {
            if (is_array($p) && isset($p[0], $p[1]) && is_numeric($p[1])) $out[(string) $p[0]] = (float) $p[1];
        }
        ksort($out);
        return $out;
    }
    return array();
}

/** QWI separations summed over states, quarter => value; null sectors = every sector. */
function alt_ew_qwi_quarterly($qwi, $sectors) {
    $out = array();
    foreach ((array) ($qwi['datasets']['by_sector'] ?? array()) as $row) {
        if (!is_array($row) || count($row) < 12 || !is_numeric($row[10])) continue;
        if ($sectors !== null && !in_array((string) $row[3], $sectors, true)) continue;
        $q = (string) $row[2];
        $out[$q] = ($out[$q] ?? 0) + (int) $row[10];
    }
    ksort($out);
    return $out;
}

/** "2026-Q2" => "2026-06" (the quarter's last month). */
function alt_ew_quarter_month($q) {
    return preg_match('/^(\d{4})-Q([1-4])$/', (string) $q, $m) ? sprintf('%s-%02d', $m[1], (int) $m[2] * 3) : '';
}

/**
 * The tracker's own US WARN notices per month per stored industry, as
 * [ym => [industry => n]] over the window. Cached; '' industry rows dropped.
 */
function alt_ew_warn_counts() {
    global $wpdb;
    if (!isset($wpdb) || !function_exists('alt_db_table')) return array();
    $key = function_exists('alt_figure_cache_key') ? alt_figure_cache_key('ew_warn') : 'alt_ew_warn';
    $hit = function_exists('get_transient') ? get_transient($key) : false;
    if (is_array($hit)) return $hit;
    $since = gmdate('Y-m-01', strtotime('-' . (ALT_EW_MONTHS + 1) . ' months'));
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT DATE_FORMAT(announcement_date, '%%Y-%%m') AS ym, industry, COUNT(*) AS n
         FROM " . alt_db_table() . "
         WHERE source_type = 'warn' AND country = 'United States' AND industry <> ''
           AND announcement_date IS NOT NULL AND announcement_date >= %s
         GROUP BY ym, industry", $since), ARRAY_A) ?: array();
    $out = array();
    foreach ($rows as $r) {
        $out[(string) $r['ym']][(string) $r['industry']] = (int) $r['n'];
    }
    if (function_exists('set_transient')) set_transient($key, $out, 6 * HOUR_IN_SECONDS);
    return $out;
}

/** Index a list to its own mean over the window (100 = average); nulls stay null. */
function alt_ew_index($vals) {
    $m = alt_ew_mean($vals);
    return array_map(function ($v) use ($m) {
        return ($v === null || !$m) ? null : round($v / $m * 100, 1);
    }, $vals);
}

/**
 * Everything the view draws, or null when no official series exists.
 *   months: ['2023-10', ...]
 *   industries: key => [label, status, status_label, reasons[], series[]]
 *   series: [name, kind (official|tracker), raw[], index[]]
 */
function alt_ew_bundle($bls, $fred, $qwi, $warn, $now = null) {
    $now = $now ?: time();
    $last = gmdate('Y-m', strtotime(gmdate('Y-m-01', $now) . ' -1 month'));
    $months = array();
    for ($i = ALT_EW_MONTHS - 1; $i >= 0; $i--) {
        $months[] = gmdate('Y-m', strtotime($last . '-01 -' . $i . ' months'));
    }
    $claims = $fred ? alt_ew_claims_monthly($fred) : array();
    $out = array();
    foreach (alt_ew_industries() as $key => $def) {
        list($label, $tracker, $jolts_label, $sectors) = $def;
        $jolts = $bls ? alt_ew_jolts_monthly($bls, $jolts_label) : array();
        $qwi_q = $qwi ? alt_ew_qwi_quarterly($qwi, $sectors) : array();
        if (!$jolts && !$qwi_q && !$claims) continue;

        $changes = array();
        $reasons = array();
        $series = array();
        $official = array(
            array('Weekly initial jobless claims (US, all industries)', $claims, 'm', 'FRED initial claims'),
            array('JOLTS layoffs and discharges', $jolts, 'm', 'JOLTS layoffs'),
        );
        foreach ($official as $o) {
            if (!$o[1]) continue;
            $c = alt_ew_change(array_values($o[1]));
            $changes[$o[3]] = $c;
            if ($c !== null) $reasons[] = $o[3] . ' ' . alt_ew_pct($c) . ' (last 3 months vs the 12 before)';
            $raw = array();
            foreach ($months as $ym) $raw[] = isset($o[1][$ym]) ? $o[1][$ym] * ($o[3] === 'JOLTS layoffs' ? 1000 : 1) : null;
            $series[] = array('name' => $o[0], 'kind' => 'official', 'raw' => $raw, 'index' => alt_ew_index($raw));
        }
        if ($qwi_q) {
            $c = alt_ew_change_yoy($qwi_q);
            $changes['QWI separations'] = $c;
            if ($c !== null) $reasons[] = 'QWI separations ' . alt_ew_pct($c) . ' (latest quarter vs a year earlier)';
            $byM = array();
            foreach ($qwi_q as $q => $v) $byM[alt_ew_quarter_month($q)] = $v;
            $raw = array();
            foreach ($months as $ym) $raw[] = $byM[$ym] ?? null;
            if (array_filter($raw, 'is_numeric')) {
                $series[] = array('name' => 'QWI separations, all causes (quarterly)', 'kind' => 'official', 'raw' => $raw, 'index' => alt_ew_index($raw));
            }
        }
        // The tracker's own count: shown on the timeline, NEVER fed to the status.
        $raw = array();
        $any = false;
        foreach ($months as $ym) {
            $n = 0;
            foreach ((array) ($warn[$ym] ?? array()) as $ind => $c) {
                if ($tracker === null || in_array((string) $ind, $tracker, true)) $n += (int) $c;
            }
            $raw[] = $n;
            if ($n > 0) $any = true;
        }
        if ($any) {
            $series[] = array('name' => 'WARN notices in this tracker', 'kind' => 'tracker', 'raw' => $raw, 'index' => alt_ew_index($raw));
        }
        $status = alt_ew_status($changes);
        $out[$key] = array(
            'label' => $label,
            'status' => $status,
            'status_label' => $status ? alt_ew_status_label($status) : '',
            'reasons' => $reasons,
            'series' => $series,
        );
    }
    return $out ? array('months' => $months, 'industries' => $out) : null;
}
