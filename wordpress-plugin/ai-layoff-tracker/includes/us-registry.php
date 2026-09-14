<?php
/**
 * US jurisdiction registry: one row per jurisdiction, nothing typed by hand.
 *
 * The committed half (data/us-jurisdictions.json) is written by
 * railway/generate_us_registry.py from the source inventory, the scrapers' own
 * state registries, the official-URL map the importer stamps onto notices, the
 * per-source freshness ledger and the WARN workflows' cron lines. The live
 * half is what only the plugin holds: the source-health ledger (when each
 * collector last completed) and the layoffs table (how far back each state's
 * notices go, whether the notices carry worker counts and documents).
 *
 * Absence is rendered as absence. A jurisdiction with no collector prints no
 * cadence; a collector with no health row prints "not yet reported"; a state
 * with no rows prints no range. Nothing here falls back to a default a reader
 * could mistake for a measurement.
 */
if (!defined('ABSPATH')) exit;

/** The committed registry, or null when the file is missing or malformed. */
function alt_us_registry_data() {
    static $memo = false;
    if ($memo !== false) return $memo;
    $path = ALT_PLUGIN_DIR . 'data/us-jurisdictions.json';
    $memo = null;
    if (!is_readable($path)) return null;
    $j = json_decode((string) file_get_contents($path), true);
    if (!is_array($j) || empty($j['rows']) || !is_array($j['rows'])) return null;
    $memo = $j;
    return $memo;
}

/**
 * Per-state facts from the layoffs table, one grouped query, cached against
 * alt_data_ver so a write always invalidates it. Keys are state codes.
 *
 *   rows        WARN rows on file (superset members excluded, as everywhere)
 *   first/last  earliest and latest effective date on file
 *   counted     rows carrying a worker count
 *   documents   rows whose cited source is a notice document or data file
 *               rather than the state's landing page
 */
function alt_us_registry_table_facts() {
    static $memo = null;
    if ($memo !== null) return $memo;
    $cache_key = 'alt_us_registry_' . md5((string) get_option('alt_data_ver', 1));
    $cached = get_transient($cache_key);
    if (is_array($cached)) { $memo = $cached; return $memo; }
    global $wpdb;
    $t = alt_db_table();
    $landing = function_exists('alt_state_warn_urls') ? alt_state_warn_urls() : array();
    $rows = $wpdb->get_results(
        "SELECT state,
                COUNT(*) AS n,
                MIN(layoff_date) AS first_date,
                MAX(layoff_date) AS last_date,
                SUM(job_count > 0) AS counted,
                SUM(source_url IS NOT NULL AND source_url <> '') AS sourced
         FROM $t
         WHERE source_type = 'warn' AND state <> '' AND superset_of = 0
         GROUP BY state", ARRAY_A);
    $out = array();
    foreach ((array) $rows as $r) {
        $code = strtoupper((string) $r['state']);
        $out[$code] = array(
            'rows'      => (int) $r['n'],
            'first'     => (string) $r['first_date'],
            'last'      => (string) $r['last_date'],
            'counted'   => (int) $r['counted'],
            'sourced'   => (int) $r['sourced'],
        );
    }
    // A cited source that is not the state's landing page is a per-notice
    // document or data file. One query per state on file, cached with the
    // rest; the landing map lives in PHP, so the comparison does too.
    foreach ($out as $code => $facts) {
        $page = isset($landing[$code]) ? $landing[$code] : '';
        if ($page === '') { $out[$code]['documents'] = $facts['sourced']; continue; }
        $out[$code]['documents'] = (int) $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM $t WHERE source_type = 'warn' AND state = %s AND superset_of = 0
             AND source_url IS NOT NULL AND source_url <> '' AND source_url <> %s",
            $code, $page));
    }
    set_transient($cache_key, $out, 6 * HOUR_IN_SECONDS);
    $memo = $out;
    return $memo;
}

/**
 * The rows the page renders: committed registry + live ledger + table facts.
 * Returns an empty array when the committed registry cannot be read, and the
 * template says so rather than rendering a table of blanks.
 */
function alt_us_registry_rows() {
    $data = alt_us_registry_data();
    if (!$data) return array();
    $health = function_exists('alt_source_health_masked') ? alt_source_health_masked() : array();
    $facts = alt_us_registry_table_facts();
    $out = array();
    foreach ($data['rows'] as $row) {
        $code = (string) $row['code'];
        // Last successful collection: the newest 'ok' completion among the
        // collectors that serve this jurisdiction. A collector that never
        // reported, or whose last run failed, contributes nothing here and is
        // named as such by the template.
        $last_ok = '';
        $last_status = '';
        foreach ((array) $row['collectors'] as $c) {
            $id = (string) $c['health_id'];
            if (!isset($health[$id]) || !is_array($health[$id])) continue;
            $st = (string) ($health[$id]['status'] ?? '');
            $at = (string) ($health[$id]['checked_at'] ?? '');
            if ($last_status === '' || $st === 'ok') $last_status = $st;
            if ($st === 'ok' && $at !== '' && ($last_ok === '' || strcmp($at, $last_ok) > 0)) $last_ok = $at;
        }
        $row['last_ok'] = $last_ok;
        $row['last_status'] = $last_status;
        $row['facts'] = isset($facts[$code]) ? $facts[$code] : null;
        $out[] = $row;
    }
    return $out;
}

/** Cadence words for a row: the distinct cadences its collectors derive. */
function alt_us_registry_cadence($row) {
    $words = array();
    foreach ((array) $row['collectors'] as $c) {
        $w = (string) ($c['cadence'] ?? '');
        if ($w !== '' && !in_array($w, $words, true)) $words[] = $w;
    }
    return implode(' / ', $words);
}

/**
 * The freshness cell, in reader words, from the ledger's own states. The
 * mapping is total over the five states the generator can emit; anything
 * else renders as the raw word rather than as a guess.
 */
function alt_us_registry_freshness_label($row) {
    $f = isset($row['freshness']) ? $row['freshness'] : array();
    $state = (string) ($f['state'] ?? '');
    $verdict = (string) ($f['verdict'] ?? '');
    if ($state === 'UNAVAILABLE') {
        return !empty($row['no_public_register']) ? 'No public register' : 'Published, not countable';
    }
    if ($state === 'ABSENT') {
        return empty($row['collectors']) ? 'No register on record' : 'Not judged';
    }
    if ($state === 'UNKNOWN') return 'Too few notices to judge';
    if ($state === 'HEALTHY') {
        if ($verdict === 'PASS') return 'Fresh';
        if ($verdict === 'QUIET') return 'Quiet';
        if ($verdict === 'DARK') return 'Dark';
        return 'Healthy';
    }
    return $state !== '' ? ucfirst(strtolower($state)) : 'Not judged';
}

/** CSS modifier for the freshness pill. */
function alt_us_registry_freshness_class($row) {
    $label = alt_us_registry_freshness_label($row);
    $map = array(
        'Fresh' => 'ok', 'Healthy' => 'ok', 'Quiet' => 'quiet', 'Dark' => 'dark',
        'Too few notices to judge' => 'unknown', 'Not judged' => 'unknown',
        'No public register' => 'none', 'No register on record' => 'none',
        'Published, not countable' => 'partial',
    );
    return isset($map[$label]) ? $map[$label] : 'unknown';
}

function alt_shortcode_us_registry() {
    return alt_template('page-us-registry.php');
}
add_shortcode('alt_us_registry', 'alt_shortcode_us_registry');

function alt_ensure_us_registry_page_once() {
    if (get_page_by_path('ai-layoff-tracker/us-warn-registry')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned page
    $title = function_exists('alt_secondary_page_title') ? alt_secondary_page_title('page-us-registry.php') : '';
    if ($title === '') return; // retry later; never create a page named by a guess
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => $title,
        'post_name' => 'us-warn-registry', 'post_content' => '[alt_us_registry]'));
}
add_action('init', 'alt_ensure_us_registry_page_once', 20);
