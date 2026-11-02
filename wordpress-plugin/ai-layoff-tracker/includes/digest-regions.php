<?php
/**
 * BIGGEST CUTS, GROUPED BY WHERE THE JOBS WERE (owner request 2026-11-02).
 *
 * The layoff edition's ranked list is printed under one section title
 * ("Around the world"), then by world region in a FIXED order (North America,
 * Europe, Middle East, Asia-Pacific, Latin America, Africa, Other), then by
 * country (flag + name, in the existing pill style), then by US state where
 * the row carries one, then by city (pin) where the row carries one.
 *
 * THESE ARE PRESENTATION BUCKETS, NOT THE STATISTICAL ONES. The figure blocks
 * keep alt_digest_region_of() in subscribe.php, whose buckets sum to the
 * headline. Nothing here produces a number: rows arrive ranked and keep their
 * own figures, so a grouping can only move a row, never change it.
 *
 * An unknown, empty or "Multiple countries" value goes to Other, never to a
 * guessed continent. A country we cannot code gets no flag rather than a
 * wrong one.
 *
 * PURE FUNCTIONS. No query, no option: railway/tests/test_digest_world_regions.py
 * runs them under the php CLI. subscribe.php loads this file guarded and
 * falls back to the flat list when it is absent (FTPS uploads one file at a
 * time).
 */

if (!defined('ABSPATH')) exit;

function alt_digest_world_region_order() {
    return array('North America', 'Europe', 'Middle East', 'Asia-Pacific',
                 'Latin America', 'Africa', 'Other');
}

/** Country name (lowercase) => ISO 3166-1 alpha-2, plus its display region. */
function alt_digest_world_country_table() {
    static $t = null;
    if ($t !== null) return $t;
    $by_region = array(
        'North America' => array('United States' => 'US', 'USA' => 'US', 'US' => 'US',
            'Canada' => 'CA', 'Greenland' => 'GL', 'Bermuda' => 'BM'),
        'Europe' => array('United Kingdom' => 'GB', 'UK' => 'GB', 'Guernsey' => 'GG',
            'Isle of Man' => 'IM', 'Jersey' => 'JE', 'Albania' => 'AL', 'Austria' => 'AT',
            'Belgium' => 'BE', 'Bosnia and Herzegovina' => 'BA', 'Bulgaria' => 'BG',
            'Croatia' => 'HR', 'Cyprus' => 'CY', 'Czechia' => 'CZ', 'Czech Republic' => 'CZ',
            'Denmark' => 'DK', 'Estonia' => 'EE', 'Finland' => 'FI', 'France' => 'FR',
            'Germany' => 'DE', 'Greece' => 'GR', 'Hungary' => 'HU', 'Iceland' => 'IS',
            'Ireland' => 'IE', 'Italy' => 'IT', 'Latvia' => 'LV', 'Liechtenstein' => 'LI',
            'Lithuania' => 'LT', 'Luxembourg' => 'LU', 'Malta' => 'MT', 'Moldova' => 'MD',
            'Monaco' => 'MC', 'Montenegro' => 'ME', 'Netherlands' => 'NL',
            'North Macedonia' => 'MK', 'Norway' => 'NO', 'Poland' => 'PL',
            'Portugal' => 'PT', 'Romania' => 'RO', 'Serbia' => 'RS', 'Slovakia' => 'SK',
            'Slovenia' => 'SI', 'Spain' => 'ES', 'Sweden' => 'SE', 'Switzerland' => 'CH',
            'Ukraine' => 'UA'),
        'Middle East' => array('Bahrain' => 'BH', 'Iran' => 'IR', 'Iraq' => 'IQ',
            'Israel' => 'IL', 'Jordan' => 'JO', 'Kuwait' => 'KW', 'Lebanon' => 'LB',
            'Oman' => 'OM', 'Qatar' => 'QA', 'Saudi Arabia' => 'SA',
            'Türkiye' => 'TR', 'Turkey' => 'TR', 'United Arab Emirates' => 'AE',
            'UAE' => 'AE'),
        'Asia-Pacific' => array('Australia' => 'AU', 'Bangladesh' => 'BD',
            'Cambodia' => 'KH', 'China' => 'CN', "People's Republic of China" => 'CN',
            'Hong Kong' => 'HK', 'India' => 'IN', 'Indonesia' => 'ID', 'Japan' => 'JP',
            'Korea' => 'KR', 'South Korea' => 'KR', 'Laos' => 'LA', 'Macau' => 'MO',
            'Malaysia' => 'MY', 'Mongolia' => 'MN', 'Myanmar' => 'MM', 'Nepal' => 'NP',
            'New Zealand' => 'NZ', 'Pakistan' => 'PK', 'Philippines' => 'PH',
            'Singapore' => 'SG', 'Sri Lanka' => 'LK', 'Taiwan' => 'TW',
            'Thailand' => 'TH', 'Vietnam' => 'VN'),
        'Latin America' => array('Mexico' => 'MX', 'Argentina' => 'AR', 'Bolivia' => 'BO',
            'Brazil' => 'BR', 'Chile' => 'CL', 'Colombia' => 'CO', 'Costa Rica' => 'CR',
            'Dominican Republic' => 'DO', 'Ecuador' => 'EC', 'El Salvador' => 'SV',
            'Guatemala' => 'GT', 'Honduras' => 'HN', 'Nicaragua' => 'NI', 'Panama' => 'PA',
            'Paraguay' => 'PY', 'Peru' => 'PE', 'Puerto Rico' => 'PR', 'Uruguay' => 'UY',
            'Venezuela' => 'VE'),
        'Africa' => array('Algeria' => 'DZ', 'Botswana' => 'BW', 'Egypt' => 'EG',
            'Ethiopia' => 'ET', 'Ghana' => 'GH', 'Kenya' => 'KE', 'Morocco' => 'MA',
            'Nigeria' => 'NG', 'Rwanda' => 'RW', 'Senegal' => 'SN', 'South Africa' => 'ZA',
            'Tanzania' => 'TZ', 'Tunisia' => 'TN', 'Uganda' => 'UG', 'Zambia' => 'ZM',
            'Zimbabwe' => 'ZW'),
    );
    $t = array();
    foreach ($by_region as $region => $countries) {
        foreach ($countries as $name => $code) {
            $t[mb_strtolower($name, 'UTF-8')] = array($region, $code);
        }
    }
    return $t;
}

function alt_digest_world_region($country) {
    $t = alt_digest_world_country_table();
    $k = mb_strtolower(trim((string) $country), 'UTF-8');
    return isset($t[$k]) ? $t[$k][0] : 'Other';
}

/** Two regional-indicator symbols, or '' when the country has no code here. */
function alt_digest_country_flag($country) {
    $t = alt_digest_world_country_table();
    $k = mb_strtolower(trim((string) $country), 'UTF-8');
    if (!isset($t[$k])) return '';
    $flag = '';
    foreach (str_split($t[$k][1]) as $ch) {
        $flag .= mb_chr(0x1F1E6 + ord($ch) - ord('A'), 'UTF-8');
    }
    return $flag;
}

function alt_digest_us_state_name($code) {
    $code = strtoupper(trim((string) $code));
    if (function_exists('alt_us_state_names')) {
        $n = alt_us_state_names();
        if (isset($n[$code])) return $n[$code];
    }
    static $s = array('AL'=>'Alabama','AK'=>'Alaska','AZ'=>'Arizona','AR'=>'Arkansas',
        'CA'=>'California','CO'=>'Colorado','CT'=>'Connecticut','DE'=>'Delaware',
        'DC'=>'District of Columbia','FL'=>'Florida','GA'=>'Georgia','HI'=>'Hawaii',
        'ID'=>'Idaho','IL'=>'Illinois','IN'=>'Indiana','IA'=>'Iowa','KS'=>'Kansas',
        'KY'=>'Kentucky','LA'=>'Louisiana','ME'=>'Maine','MD'=>'Maryland',
        'MA'=>'Massachusetts','MI'=>'Michigan','MN'=>'Minnesota','MS'=>'Mississippi',
        'MO'=>'Missouri','MT'=>'Montana','NE'=>'Nebraska','NV'=>'Nevada',
        'NH'=>'New Hampshire','NJ'=>'New Jersey','NM'=>'New Mexico','NY'=>'New York',
        'NC'=>'North Carolina','ND'=>'North Dakota','OH'=>'Ohio','OK'=>'Oklahoma',
        'OR'=>'Oregon','PA'=>'Pennsylvania','PR'=>'Puerto Rico','RI'=>'Rhode Island',
        'SC'=>'South Carolina','SD'=>'South Dakota','TN'=>'Tennessee','TX'=>'Texas',
        'UT'=>'Utah','VT'=>'Vermont','VA'=>'Virginia','WA'=>'Washington',
        'WV'=>'West Virginia','WI'=>'Wisconsin','WY'=>'Wyoming');
    return isset($s[$code]) ? $s[$code] : $code;
}

/**
 * The city a row names, or ''. `location` is a city only when it is not the
 * state code, the country, or the "Multiple countries" bucket.
 */
function alt_digest_row_city($state, $country, $location) {
    $loc = trim((string) $location);
    if ($loc === '' || preg_match('/^[A-Za-z]{2}$/', $loc)) return '';
    foreach (array($state, $country, 'Multiple countries') as $not) {
        if (strcasecmp($loc, trim((string) $not)) === 0) return '';
    }
    if (trim((string) $state) !== ''
        && strcasecmp($loc, alt_digest_us_state_name($state)) === 0) return '';
    return $loc;
}

/**
 * Ranked rows (each with 'geo' => country/state/city) into
 * region -> country -> state -> rows. Regions in the fixed order; within
 * North America the United States first; everything else in the order the
 * ranked rows first name it. A row with no state sits under state ''.
 */
function alt_digest_group_by_world_region($rows) {
    $tree = array();
    foreach ((array) $rows as $row) {
        $geo = (array) ($row['geo'] ?? array());
        $country = trim((string) ($geo['country'] ?? ''));
        $region = alt_digest_world_region($country);
        if ($region === 'Other') $country = '';
        $state = strtoupper(trim((string) ($geo['state'] ?? '')));
        if (!isset($tree[$region][$country][$state])) $tree[$region][$country][$state] = array();
        $tree[$region][$country][$state][] = $row;
    }
    $out = array();
    foreach (alt_digest_world_region_order() as $region) {
        if (empty($tree[$region])) continue;
        $countries = $tree[$region];
        if (isset($countries['United States'])) {
            $countries = array('United States' => $countries['United States']) + $countries;
        }
        $clist = array();
        foreach ($countries as $country => $states) {
            if (isset($states[''])) { $none = $states['']; unset($states['']); $states[''] = $none; }
            $slist = array();
            foreach ($states as $state => $srows) {
                // Rows naming the same city sit together, first-named city first.
                $by_city = array();
                foreach ($srows as $r) {
                    $by_city[trim((string) ($r['geo']['city'] ?? ''))][] = $r;
                }
                $ordered = array();
                foreach ($by_city as $crows) foreach ($crows as $r) $ordered[] = $r;
                $slist[] = array('state' => (string) $state, 'rows' => $ordered);
            }
            $clist[] = array('country' => (string) $country, 'states' => $slist);
        }
        $out[] = array('region' => $region, 'countries' => $clist);
    }
    return $out;
}

/** The section title above the regions. */
function alt_digest_world_title() {
    return 'Around the world';
}

/**
 * HTML and text for the grouped list. $render is the card renderer for a run
 * of rows (alt_digest_rank_cards), so each item keeps exactly the card,
 * pills and text lines it had in the flat list.
 */
function alt_digest_world_cards($rows, $render) {
    $groups = alt_digest_group_by_world_region($rows);
    $html = '<p data-alt="world-title">' . esc_html(alt_digest_world_title()) . '</p>';
    $text = '  ' . alt_digest_world_title() . "\n";
    foreach ($groups as $g) {
        $html .= '<p data-alt="world-region">' . esc_html($g['region']) . '</p>';
        $text .= "\n  [" . $g['region'] . "]\n";
        foreach ($g['countries'] as $c) {
            if ($c['country'] !== '') {
                $flag = alt_digest_country_flag($c['country']);
                $label = trim($flag . ' ' . $c['country']);
                $html .= '<p data-alt="world-country"><span data-alt="pill">'
                       . esc_html($label) . '</span></p>';
                $text .= '  ' . $label . "\n";
            }
            foreach ($c['states'] as $s) {
                if ($s['state'] !== '') {
                    $name = alt_digest_us_state_name($s['state']);
                    $html .= '<p data-alt="world-state">' . esc_html($name) . '</p>';
                    $text .= '   ' . $name . "\n";
                }
                $city = null;
                $run = array();
                $flush = function () use (&$run, &$html, &$text, $render) {
                    if (!$run) return;
                    list($h, $t) = call_user_func($render, $run);
                    $html .= $h;
                    $text .= $t;
                    $run = array();
                };
                foreach ($s['rows'] as $r) {
                    $rc = trim((string) ($r['geo']['city'] ?? ''));
                    if ($rc !== $city) {
                        $flush();
                        $city = $rc;
                        if ($rc !== '') {
                            $html .= '<p data-alt="world-city">' . "\u{1F4CD} "
                                   . esc_html($rc) . '</p>';
                            $text .= '   ' . "\u{1F4CD} " . $rc . "\n";
                        }
                    }
                    $run[] = $r;
                }
                $flush();
            }
        }
    }
    return array($html, $text);
}
