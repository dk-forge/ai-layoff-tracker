<?php
/**
 * Loads the SHIPPED includes/db.php and reports what its search-term logic
 * builds, so the Python suite can assert on the real function rather than on a
 * reimplementation of it.
 *
 * usage: php search_boundary_harness.php <path/to/db.php> <path/to/cases.json>
 *
 * Cases are {"terms": [...], "matches": [[term, haystack], ...]}. For each
 * term it prints the pattern per dialect; for each (term, haystack) it prints
 * whether the ICU pattern matches. PCRE stands in for the server's ICU engine:
 * the two agree on `\b` over Latin text, which is the whole of what this
 * function ever emits a boundary for, and the DIALECT ITSELF is proven on the
 * live server by alt_regexp_boundary_syntax()'s own positive/negative probe
 * rather than here.
 */
foreach (array('add_action', 'add_filter', 'get_transient', 'set_transient',
               'register_rest_route', 'wp_json_encode', 'current_time',
               'get_option', 'update_option', 'sanitize_text_field',
               'apply_filters', 'do_action', 'delete_transient', 'absint') as $fn) {
    if (!function_exists($fn)) { eval("function $fn() { return null; }"); }
}
if (!defined('DAY_IN_SECONDS')) define('DAY_IN_SECONDS', 86400);
if (!defined('ABSPATH')) define('ABSPATH', '/tmp/');

require $argv[1];

$cases = json_decode(file_get_contents($argv[2]), true);
$out = array('patterns' => array(), 'matches' => array());

foreach ($cases['terms'] as $term) {
    $out['patterns'][$term] = array(
        'icu'   => alt_boundary_pattern($term, 'icu'),
        'posix' => alt_boundary_pattern($term, 'posix'),
        'none'  => alt_boundary_pattern($term, ''),
    );
}
foreach ($cases['matches'] as $pair) {
    list($term, $haystack) = $pair;
    $pattern = alt_boundary_pattern($term, 'icu');
    if ($pattern === '') {
        // No boundary for this term: the endpoint runs the substring alone.
        $hit = (stripos($haystack, trim($term)) !== false);
    } else {
        $hit = (bool) preg_match('/' . $pattern . '/iu', $haystack);
    }
    $out['matches'][] = array($term, $haystack, $hit);
}
echo json_encode($out, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
