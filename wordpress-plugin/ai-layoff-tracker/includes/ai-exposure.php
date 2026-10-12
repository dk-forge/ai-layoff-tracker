<?php
/**
 * AI exposure by job and city: [alt_ai_exposure].
 *
 * Reads the stored /reference/ai_exposure document (railway/sources/
 * ai_exposure.py: "GPTs are GPTs" exposure scores joined to O*NET titles, BLS
 * OEWS employment and wages, and BLS Employment Projections) and renders,
 * server-side, the most- and least-exposed occupations, an exposure x
 * projected-growth quadrant, and a metro picker. Rendered at the end of the
 * Sources page by page-sources.php (plugin-owned template); no stored page
 * content changes. assets/ai-exposure.js only swaps the metro panel.
 *
 * Exposure means tasks an AI system could speed up, per the study. It is not
 * a forecast of job loss, and nothing here is read by the layoff table,
 * ingest or classification. Missing or malformed data renders nothing.
 */
if (!defined('ABSPATH')) exit;

/** Occupations smaller than this nationally are left out of the ranked lists. */
if (!defined('ALT_AX_MIN_EMPLOYMENT')) define('ALT_AX_MIN_EMPLOYMENT', 25000);
if (!defined('ALT_AX_LIST_N')) define('ALT_AX_LIST_N', 10);

/** The stored document, or null when it is missing or not the expected shape. */
function alt_ax_doc() {
    $doc = get_option('alt_ref_ai_exposure', array());
    if (!is_array($doc) || empty($doc['datasets']['occupations']) || !is_array($doc['datasets']['occupations'])) return null;
    $occ = array();
    foreach ($doc['datasets']['occupations'] as $r) {
        if (!is_array($r) || count($r) < 6 || !is_numeric($r[2]) || !is_numeric($r[3])) continue;
        $occ[(string) $r[0]] = array(
            'soc' => (string) $r[0], 'title' => (string) $r[1], 'exposure' => (float) $r[2],
            'emp' => (int) $r[3], 'wage' => $r[4], 'growth' => is_numeric($r[5]) ? (float) $r[5] : null,
        );
    }
    if (count($occ) < 2 * ALT_AX_LIST_N) return null;
    $doc['_occ'] = $occ;
    $doc['threshold'] = isset($doc['threshold']) && is_numeric($doc['threshold']) ? (float) $doc['threshold'] : 0.5;
    return $doc;
}

function alt_ax_quadrant($o, $threshold) {
    if ($o['growth'] === null) return '';
    $exp = $o['exposure'] >= $threshold ? 'exposed' : 'less';
    return $exp . '-' . ($o['growth'] < 0 ? 'shrinking' : 'growing');
}

function alt_ax_quadrant_label($q) {
    $labels = array(
        'exposed-shrinking' => 'Exposed and shrinking',
        'exposed-growing' => 'Exposed but growing',
        'less-shrinking' => 'Less exposed, shrinking',
        'less-growing' => 'Less exposed, growing',
    );
    return $labels[$q] ?? 'No projection';
}

function alt_ax_num($n) { return number_format((float) $n); }
function alt_ax_pct($x) { return round($x * 100) . '%'; }
function alt_ax_wage($w) {
    if ($w === '#') return 'Above BLS top code';
    return is_numeric($w) ? '$' . number_format((float) $w) : 'Not published';
}
function alt_ax_growth($g) {
    if ($g === null) return 'Not projected';
    return ($g > 0 ? '+' : ($g < 0 ? '-' : '')) . number_format(abs($g), 1) . '%';
}

/** Everything the template draws, computed once (also what the tests read). */
function alt_ax_bundle($doc) {
    if (!$doc) return null;
    $t = $doc['threshold'];
    $big = array_filter($doc['_occ'], function ($o) { return $o['emp'] >= ALT_AX_MIN_EMPLOYMENT; });
    $by = array_values($big);
    usort($by, function ($a, $b) { return $b['exposure'] <=> $a['exposure'] ?: $b['emp'] <=> $a['emp']; });
    $most = array_slice($by, 0, ALT_AX_LIST_N);
    $least = array_slice(array_reverse($by), 0, ALT_AX_LIST_N);
    $quad = array();
    foreach (array('exposed-shrinking', 'exposed-growing', 'less-shrinking', 'less-growing') as $q) {
        $quad[$q] = array('n' => 0, 'emp' => 0, 'top' => array());
    }
    foreach ($big as $o) {
        $q = alt_ax_quadrant($o, $t);
        if ($q === '') continue;
        $quad[$q]['n']++;
        $quad[$q]['emp'] += $o['emp'];
        $quad[$q]['top'][] = $o;
    }
    foreach ($quad as $q => $v) {
        usort($v['top'], function ($a, $b) { return $b['emp'] <=> $a['emp']; });
        $quad[$q]['top'] = array_slice($v['top'], 0, 3);
    }
    $metros = array();
    foreach ((array) ($doc['datasets']['metros'] ?? array()) as $r) {
        if (!is_array($r) || count($r) < 4 || !is_numeric($r[2]) || !is_numeric($r[3]) || (int) $r[2] <= 0) continue;
        $metros[(string) $r[0]] = array('title' => (string) $r[1], 'total' => (int) $r[2], 'exposed' => (int) $r[3], 'jobs' => array());
    }
    foreach ((array) ($doc['datasets']['metro_occupations'] ?? array()) as $r) {
        if (!is_array($r) || count($r) < 3 || !isset($metros[(string) $r[0]]) || !isset($doc['_occ'][(string) $r[1]])) continue;
        $o = $doc['_occ'][(string) $r[1]];
        $metros[(string) $r[0]]['jobs'][] = array($o['title'], (int) $r[2], alt_ax_pct($o['exposure']));
    }
    $metros = array_filter($metros, function ($m) { return !empty($m['jobs']); });
    return array('threshold' => $t, 'most' => $most, 'least' => $least, 'quadrants' => $quad, 'metros' => $metros);
}

/** "Data: ..." line from the stored versions. */
function alt_ax_asof($doc) {
    $v = (array) ($doc['versions'] ?? array());
    $parts = array();
    if (!empty($v['oews'])) $parts[] = 'BLS employment and wages for ' . $v['oews'];
    if (!empty($v['ep'])) $parts[] = 'BLS projections ' . $v['ep'];
    if (!empty($v['onet'])) $parts[] = 'O*NET ' . $v['onet'];
    $parts[] = 'exposure scores as published in 2024';
    $line = 'Data: ' . implode('; ', $parts) . '.';
    if (!empty($doc['updated']) && ($ts = strtotime((string) $doc['updated']))) {
        $line .= ' Collected ' . gmdate('j M Y', $ts) . '.';
    }
    return $line;
}

function alt_shortcode_ai_exposure() {
    $doc = alt_ax_doc();
    $b = alt_ax_bundle($doc);
    if (!$b) return '<!-- alt_ai_exposure: no reference data stored -->';
    return alt_template('partials/ai-exposure.php', array('alt_ax' => $b, 'alt_ax_doc' => $doc));
}
add_shortcode('alt_ai_exposure', 'alt_shortcode_ai_exposure');
