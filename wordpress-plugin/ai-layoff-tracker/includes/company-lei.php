<?php
/**
 * GLEIF Legal Entity Identifiers on company pages.
 *
 * data/company_lei.json is written by railway/gleif_lei.py (weekly,
 * gleif-lei.yml) from the GLEIF golden copy, CC0 1.0, using SEC 8-K and news
 * rows only (never WARN). A name is listed only on a UNIQUE normalised-name
 * match whose legal-address country equals the row's one country, so absence
 * means "not asserted", never "has no LEI".
 *
 * Keyed by the exact company_name string. A page shows an LEI only when every
 * listed name on it points at the SAME code. Callers guard with
 * function_exists(): FTPS uploads one file at a time.
 */
if (!defined('ABSPATH')) exit;

function alt_company_lei_map() {
    static $map = null;
    if ($map !== null) return $map;
    $map = array();
    $file = ALT_PLUGIN_DIR . 'data/company_lei.json';
    if (!is_readable($file)) return $map;
    $doc = json_decode((string) file_get_contents($file), true);
    if (is_array($doc) && isset($doc['companies']) && is_array($doc['companies'])) {
        $map = $doc['companies'];
    }
    return $map;
}

/** The one LEI the page's names agree on, or ''. PURE given the map. */
function alt_company_lei_for_names(array $names, $map = null) {
    $map = $map === null ? alt_company_lei_map() : $map;
    $found = array();
    foreach ($names as $n) {
        $n = (string) $n;
        if ($n !== '' && isset($map[$n])) $found[(string) $map[$n]] = true;
    }
    if (count($found) !== 1) return '';
    $lei = (string) key($found);
    // ISO 17442: 18 alphanumerics then two check digits.
    return preg_match('/^[A-Z0-9]{18}[0-9]{2}$/', $lei) ? $lei : '';
}

function alt_company_lei_for_events(array $events, $map = null) {
    return alt_company_lei_for_names(array_map(function ($e) {
        return (string) ($e['company_name'] ?? '');
    }, $events), $map);
}

function alt_company_lei_url($lei) {
    return 'https://search.gleif.org/#/record/' . rawurlencode($lei);
}

/** Fields merged into the schema.org Organization node. */
function alt_company_lei_jsonld($lei) {
    if ($lei === '') return array();
    return array(
        'leiCode'    => $lei,
        'identifier' => array('@type' => 'PropertyValue', 'propertyID' => 'LEI',
                              'value' => $lei, 'url' => alt_company_lei_url($lei)),
    );
}

function alt_company_lei_html($lei) {
    if ($lei === '') return '';
    return '<p class="alt-company-lei">LEI: <a href="' . esc_url(alt_company_lei_url($lei))
         . '" rel="noopener">' . esc_html($lei) . '</a>'
         . ' <span class="alt-company-lei-source">(Legal Entity Identifier from the'
         . ' <a href="https://www.gleif.org/en/lei-data/gleif-golden-copy" rel="noopener">GLEIF Golden Copy</a>,'
         . ' CC0; matched on legal name and country)</span></p>';
}
