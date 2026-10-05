<?php
/**
 * Labour-market context, part two: the FRED trend chart and the Census QWI
 * "Hiring vs separations" chart, rendered inside [alt_labour_context]
 * (includes/labour-context.php, templates/partials/labour-trends.php).
 *
 * Same rules as the BLS/OECD panels: OFFICIAL AGGREGATE STATISTICS from all
 * causes, never tracker counts, never summed with them, nothing here says or
 * implies AI caused any movement. A source that is missing, empty or malformed
 * hides its panel. The browser draws the charts from the public filtered
 * /reference/<source>?field=a,b endpoints (assets/labour-context.js); this
 * file only decides which panels and which picker options exist.
 */
if (!defined('ABSPATH')) exit;

/** FRED series offered in the trend picker, in picker order => label. */
function alt_lc_fred_picker() {
    return array(
        'ICSA'   => 'Weekly initial jobless claims',
        'UNRATE' => 'Unemployment rate',
        'PAYEMS' => 'Payrolls, all employees, total nonfarm',
        'USINFO' => 'Information-sector jobs',
    );
}

/** FRED picker options whose rows are actually stored, id => label. */
function alt_lc_fred_options($doc) {
    if (!is_array($doc)) return array();
    $have = array();
    foreach ((array) ($doc['datasets']['observations'] ?? array()) as $row) {
        if (is_array($row) && isset($row[0], $row[2]) && is_numeric($row[2])) $have[(string) $row[0]] = true;
    }
    $out = array();
    foreach (alt_lc_fred_picker() as $id => $label) {
        if (!empty($have[$id])) $out[$id] = $label;
    }
    return $out;
}

/** As-of line for the FRED panel: newest week and month, and the pull date. */
function alt_lc_fred_asof($doc) {
    $parts = array();
    $w = (string) ($doc['latest']['weekly'] ?? '');
    $m = (string) ($doc['latest']['monthly'] ?? '');
    if ($m !== '') $parts[] = 'Monthly series through ' . alt_labour_context_month($m);
    if ($w !== '') $parts[] = 'weekly claims through ' . alt_labour_context_month($w);
    $upd = strtotime((string) ($doc['updated'] ?? ''));
    if ($upd) $parts[] = 'collected ' . gmdate('j M Y', $upd);
    return $parts ? implode(', ', $parts) . '.' : '';
}

/** 2-digit state FIPS => name (50 states + DC). */
function alt_lc_state_names() {
    return array(
        '01' => 'Alabama', '02' => 'Alaska', '04' => 'Arizona', '05' => 'Arkansas', '06' => 'California',
        '08' => 'Colorado', '09' => 'Connecticut', '10' => 'Delaware', '11' => 'District of Columbia',
        '12' => 'Florida', '13' => 'Georgia', '15' => 'Hawaii', '16' => 'Idaho', '17' => 'Illinois',
        '18' => 'Indiana', '19' => 'Iowa', '20' => 'Kansas', '21' => 'Kentucky', '22' => 'Louisiana',
        '23' => 'Maine', '24' => 'Maryland', '25' => 'Massachusetts', '26' => 'Michigan', '27' => 'Minnesota',
        '28' => 'Mississippi', '29' => 'Missouri', '30' => 'Montana', '31' => 'Nebraska', '32' => 'Nevada',
        '33' => 'New Hampshire', '34' => 'New Jersey', '35' => 'New Mexico', '36' => 'New York',
        '37' => 'North Carolina', '38' => 'North Dakota', '39' => 'Ohio', '40' => 'Oklahoma', '41' => 'Oregon',
        '42' => 'Pennsylvania', '44' => 'Rhode Island', '45' => 'South Carolina', '46' => 'South Dakota',
        '47' => 'Tennessee', '48' => 'Texas', '49' => 'Utah', '50' => 'Vermont', '51' => 'Virginia',
        '53' => 'Washington', '54' => 'West Virginia', '55' => 'Wisconsin', '56' => 'Wyoming',
    );
}

/** QWI 2-digit NAICS sector code => plain name. */
function alt_lc_naics_sectors() {
    return array(
        '11' => 'Agriculture, forestry and fishing', '21' => 'Mining, oil and gas', '22' => 'Utilities',
        '23' => 'Construction', '31-33' => 'Manufacturing', '42' => 'Wholesale trade', '44-45' => 'Retail trade',
        '48-49' => 'Transportation and warehousing', '51' => 'Information', '52' => 'Finance and insurance',
        '53' => 'Real estate', '54' => 'Professional, scientific and technical services',
        '55' => 'Management of companies', '56' => 'Administrative and support services',
        '61' => 'Educational services', '62' => 'Health care and social assistance',
        '71' => 'Arts, entertainment and recreation', '72' => 'Accommodation and food services',
        '81' => 'Other services', '92' => 'Public administration',
    );
}

/** "Split by" choices: QWI breakdown id => label, only those stored. */
function alt_lc_qwi_splits($doc) {
    $names = array('sex' => 'Sex', 'agegrp' => 'Age group', 'education' => 'Education',
        'race' => 'Race', 'ethnicity' => 'Ethnicity');
    $out = array();
    foreach ($names as $k => $label) {
        if (!empty($doc['datasets'][$k]) && is_array($doc['datasets'][$k])) $out[$k] = $label;
    }
    return $out;
}

/**
 * The QWI panel's picker options, or null when the document cannot draw the
 * basic hires-vs-separations line (no sector rows).
 *   states:  FIPS => name, only states with rows
 *   sectors: NAICS => name, only sectors with rows
 *   splits:  breakdown => label
 */
function alt_lc_qwi_options($doc) {
    if (!is_array($doc) || empty($doc['datasets']['by_sector']) || !is_array($doc['datasets']['by_sector'])) return null;
    $names = alt_lc_state_names();
    $sectors_all = alt_lc_naics_sectors();
    $states = array();
    $sectors = array();
    foreach ($doc['datasets']['by_sector'] as $row) {
        if (!is_array($row) || count($row) < 12) continue;
        $st = (string) $row[1];
        $ind = (string) $row[3];
        if (isset($names[$st])) $states[$st] = $names[$st];
        if (isset($sectors_all[$ind])) $sectors[$ind] = $sectors_all[$ind];
    }
    if (!$states || !$sectors) return null;
    asort($states);
    $ordered = array();
    foreach ($sectors_all as $code => $label) {
        if (isset($sectors[$code])) $ordered[$code] = $label;
    }
    return array('states' => $states, 'sectors' => $ordered, 'splits' => alt_lc_qwi_splits($doc));
}

/** "2026-Q1" => "the first quarter of 2026"-style short label "Q1 2026". */
function alt_lc_quarter($q) {
    $q = (string) $q;
    return preg_match('/^(\d{4})-Q([1-4])$/', $q, $m) ? 'Q' . $m[2] . ' ' . $m[1] : $q;
}

/** As-of line for the QWI panel. */
function alt_lc_qwi_asof($doc) {
    $parts = array();
    $q = (string) ($doc['latest_quarter'] ?? '');
    if ($q !== '') $parts[] = 'Data through ' . alt_lc_quarter($q);
    $upd = strtotime((string) ($doc['updated'] ?? ''));
    if ($upd) $parts[] = 'collected ' . gmdate('j M Y', $upd);
    return $parts ? implode(', ', $parts) . '.' : '';
}

/**
 * Data the QWI panel needs before any fetch: hires and separations summed over
 * every state per quarter per sector (the "All states" view, so the default
 * chart never downloads the whole document), the latest quarter, and the code
 * labels for the split groups.
 */
function alt_lc_qwi_client($doc) {
    $nat = array();
    foreach ((array) ($doc['datasets']['by_sector'] ?? array()) as $row) {
        if (!is_array($row) || count($row) < 12) continue;
        $q = (string) $row[2];
        $ind = (string) $row[3];
        if (!isset($nat[$q][$ind])) $nat[$q][$ind] = array(0, 0);
        $nat[$q][$ind][0] += is_numeric($row[9]) ? (int) $row[9] : 0;
        $nat[$q][$ind][1] += is_numeric($row[10]) ? (int) $row[10] : 0;
    }
    ksort($nat);
    $codes = array();
    foreach (array('sex', 'agegrp', 'education', 'race', 'ethnicity') as $k) {
        if (!empty($doc['codes'][$k]) && is_array($doc['codes'][$k])) $codes[$k] = $doc['codes'][$k];
    }
    return array('national' => $nat, 'latest' => (string) ($doc['latest_quarter'] ?? ''), 'codes' => $codes);
}
