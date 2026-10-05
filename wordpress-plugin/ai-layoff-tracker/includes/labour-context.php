<?php
/**
 * Labour-market context: the stored reference data (includes/reference-data.php)
 * put on the page.
 *
 *   [alt_labour_context]                 three charts (JOLTS, CPS, OECD), rendered
 *                                        on the Sources page
 *   alt_labour_context_stat($dim, $val)  one official figure for a facet page,
 *                                        only where the match is EXACT
 *
 * These are OFFICIAL AGGREGATE STATISTICS from all causes. They are never the
 * tracker's own counts, never summed with them, and nothing here says or
 * implies that AI caused any of the movement shown. Every panel says so in
 * words, and every panel names its source under the chart.
 *
 * A source that is missing, empty or malformed hides its panel; all three
 * missing hides the section. Never an error, never an empty chart frame.
 */
if (!defined('ABSPATH')) exit;

/** The stored document for one reference source, or null when unusable. */
function alt_labour_context_doc($source) {
    if (!function_exists('alt_reference_sources')) return null;
    $map = alt_reference_sources();
    if (!isset($map[$source])) return null;
    $doc = get_option($map[$source], array());
    if (!is_array($doc) || empty($doc['datasets']) || !is_array($doc['datasets'])) return null;
    return $doc;
}

/** Series of one dataset in a BLS doc, filtered by dim, as id => meta. */
function alt_labour_context_bls_series($doc, $dataset, $dim = null) {
    $out = array();
    foreach ((array) ($doc['datasets'][$dataset] ?? array()) as $sid => $s) {
        if (!is_array($s) || empty($s['points']) || !is_array($s['points'])) continue;
        if ($dim !== null && ($s['dim'] ?? '') !== $dim) continue;
        $out[(string) $sid] = $s;
    }
    return $out;
}

/** JOLTS industry labels that carry all three measures, in stored order. */
function alt_labour_context_jolts_industries($doc) {
    $have = array();
    foreach (alt_labour_context_bls_series($doc, 'jolts', 'industry') as $s) {
        $have[(string) ($s['label'] ?? '')][(string) ($s['measure'] ?? '')] = true;
    }
    $out = array();
    foreach ($have as $label => $m) {
        if ($label !== '' && !empty($m['layoffs_discharges'])) $out[] = $label;
    }
    return $out;
}

/** CPS demographic dimensions present, in a fixed reading order. */
function alt_labour_context_cps_dims($doc) {
    $names = array('sex' => 'Sex', 'age' => 'Age group', 'race' => 'Race and ethnicity', 'education' => 'Education');
    $out = array();
    foreach ($names as $dim => $label) {
        if (alt_labour_context_bls_series($doc, 'cps', $dim)) $out[$dim] = $label;
    }
    return $out;
}

/**
 * OECD REF_AREA code => the country name the tracker uses. A facet page matches
 * on this name EXACTLY; a country not in this list gets no context block.
 */
function alt_labour_context_oecd_names() {
    return array(
        'AUS' => 'Australia', 'AUT' => 'Austria', 'BEL' => 'Belgium', 'CAN' => 'Canada',
        'CHL' => 'Chile', 'COL' => 'Colombia', 'CRI' => 'Costa Rica', 'CZE' => 'Czech Republic',
        'DNK' => 'Denmark', 'EST' => 'Estonia', 'FIN' => 'Finland', 'FRA' => 'France',
        'DEU' => 'Germany', 'GRC' => 'Greece', 'HUN' => 'Hungary', 'ISL' => 'Iceland',
        'IRL' => 'Ireland', 'ISR' => 'Israel', 'ITA' => 'Italy', 'JPN' => 'Japan',
        'KOR' => 'South Korea', 'LVA' => 'Latvia', 'LTU' => 'Lithuania', 'LUX' => 'Luxembourg',
        'MEX' => 'Mexico', 'NLD' => 'Netherlands', 'NZL' => 'New Zealand', 'NOR' => 'Norway',
        'POL' => 'Poland', 'PRT' => 'Portugal', 'SVK' => 'Slovakia', 'SVN' => 'Slovenia',
        'ESP' => 'Spain', 'SWE' => 'Sweden', 'CHE' => 'Switzerland', 'TUR' => 'Turkey',
        'GBR' => 'United Kingdom', 'USA' => 'United States',
        'OECD' => 'OECD total', 'EA20' => 'Euro area', 'EU27_2020' => 'European Union',
        'G7' => 'G7',
    );
}

/** The headline OECD series key for a country: total, 15 and over if present. */
function alt_labour_context_oecd_headline_key($series) {
    foreach (array('_T|Y_GE15', '_T|Y15T74', '_T|Y_GE16') as $k) {
        if (!empty($series[$k])) return $k;
    }
    foreach ($series as $k => $pts) {
        if (strpos((string) $k, '_T|') === 0 && $pts) return (string) $k;
    }
    return null;
}

/** "2026-08" => "August 2026"; anything else passes through escaped later. */
function alt_labour_context_month($ym) {
    $t = strtotime((string) $ym . '-01 00:00:00 UTC');
    return $t ? gmdate('F Y', $t) : (string) $ym;
}

/** Last point of a series as [period, value], or null. */
function alt_labour_context_last($points) {
    if (!is_array($points) || !$points) return null;
    $p = end($points);
    return (is_array($p) && isset($p[0], $p[1]) && is_numeric($p[1])) ? array((string) $p[0], $p[1]) : null;
}

/** Data-as-of line for a panel: the newest month and the collection date. */
function alt_labour_context_asof($doc, $latest_key) {
    $month = (string) ($doc['latest'][$latest_key] ?? '');
    $upd = strtotime((string) ($doc['updated'] ?? ''));
    $parts = array();
    if ($month !== '') $parts[] = 'Data through ' . alt_labour_context_month($month);
    if ($upd) $parts[] = 'collected ' . gmdate('j M Y', $upd);
    return $parts ? implode(', ', $parts) . '.' : '';
}

function alt_shortcode_labour_context() {
    $bls = alt_labour_context_doc('bls_jolts_cps');
    $oecd = alt_labour_context_doc('oecd_unemployment');
    $industries = $bls ? alt_labour_context_jolts_industries($bls) : array();
    $dims = $bls ? alt_labour_context_cps_dims($bls) : array();
    $countries = array();
    if ($oecd) {
        $names = alt_labour_context_oecd_names();
        foreach ((array) ($oecd['datasets']['monthly'] ?? array()) as $code => $series) {
            if (!is_array($series) || !$series) continue;
            $countries[(string) $code] = $names[$code] ?? (string) $code;
        }
        asort($countries);
    }
    if (!$industries && !$dims && !$countries) {
        return '<!-- alt_labour_context: no reference data stored -->';
    }
    $api = function_exists('rest_url') ? rest_url('layoffs/v1/reference/') : '';
    return alt_template('partials/labour-context.php', array(
        'alt_lc_bls' => $bls,
        'alt_lc_oecd' => $oecd,
        'alt_lc_industries' => $industries,
        'alt_lc_dims' => $dims,
        'alt_lc_countries' => $countries,
        'alt_lc_api' => $api,
    ));
}
add_shortcode('alt_labour_context', 'alt_shortcode_labour_context');

/**
 * One official figure for a facet page, or '' when there is no EXACT match.
 *
 *   industry: the facet value must equal a JOLTS supersector label verbatim
 *             (today only "Manufacturing"). JOLTS is US-only; the block says so.
 *   country:  the facet value must equal the OECD member's name in
 *             alt_labour_context_oecd_names().
 */
function alt_labour_context_stat($dim, $value) {
    $value = (string) $value;
    if ($dim === 'industry') {
        $doc = alt_labour_context_doc('bls_jolts_cps');
        if (!$doc) return '';
        foreach (alt_labour_context_bls_series($doc, 'jolts', 'industry') as $s) {
            if (($s['measure'] ?? '') !== 'layoffs_discharges' || (string) ($s['label'] ?? '') !== $value) continue;
            $last = alt_labour_context_last($s['points']);
            if (!$last) return '';
            return alt_labour_context_stat_html(
                number_format((float) $last[1] * 1000),
                'layoffs and discharges in US ' . strtolower($value) . ' in ' . alt_labour_context_month($last[0])
                    . ' (seasonally adjusted survey estimate, all causes, United States only)',
                'Source: U.S. Bureau of Labor Statistics, JOLTS.'
            );
        }
        return '';
    }
    if ($dim === 'country') {
        $doc = alt_labour_context_doc('oecd_unemployment');
        if (!$doc) return '';
        $code = array_search($value, alt_labour_context_oecd_names(), true);
        if ($code === false) return '';
        $series = $doc['datasets']['monthly'][$code] ?? null;
        if (!is_array($series)) return '';
        $key = alt_labour_context_oecd_headline_key($series);
        $last = $key ? alt_labour_context_last($series[$key]) : null;
        if (!$last) return '';
        return alt_labour_context_stat_html(
            rtrim(rtrim(number_format((float) $last[1], 1), '0'), '.') . '%',
            'unemployment rate in ' . $value . ' in ' . alt_labour_context_month($last[0])
                . ' (seasonally adjusted, all causes)',
            'Source: OECD (CC BY 4.0).'
        );
    }
    return '';
}

function alt_labour_context_stat_html($figure, $label, $source) {
    return '<aside class="alt-lc-stat" aria-label="Official labour-market context">'
        . '<p class="alt-lc-stat-k">Official statistics, not our count</p>'
        . '<p><strong>' . esc_html($figure) . '</strong> ' . esc_html($label) . '.</p>'
        . '<p class="alt-lc-note">An official aggregate from all causes, shown for scale beside the entries above. '
        . 'It is not a tracker count, is not added to it, and does not say anything about AI.</p>'
        . '<p class="alt-lc-src">' . esc_html($source) . ' <a href="' . esc_url(home_url('/ai-layoff-tracker/sources/#labour-context')) . '">More context</a></p>'
        . '</aside>';
}
