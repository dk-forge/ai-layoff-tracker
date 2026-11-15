<?php
/**
 * Loads the SHIPPED includes/db.php and prints the SQL and params that
 * alt_freetext_clause() builds for each term, so the Python suite can EXECUTE
 * that SQL (SQLite, with REGEXP registered) rather than pattern-match it.
 *
 * usage: php freetext_clause_harness.php <path/to/db.php> <terms.json>
 */
foreach (array('add_action', 'add_filter', 'set_transient', 'register_rest_route',
               'wp_json_encode', 'current_time', 'get_option', 'update_option',
               'sanitize_text_field', 'apply_filters', 'do_action',
               'delete_transient', 'absint') as $fn) {
    if (!function_exists($fn)) { eval("function $fn() { return null; }"); }
}
// The dialect is proven on the live server by its own probe; here it is ICU.
function get_transient($k) { return $k === 'alt_rx_boundary_syntax' ? 'icu' : false; }
if (!defined('DAY_IN_SECONDS')) define('DAY_IN_SECONDS', 86400);
if (!defined('ABSPATH')) define('ABSPATH', '/tmp/');

class StubWpdb {
    public function esc_like($t) { return addcslashes((string) $t, '_%\\'); }
}
$GLOBALS['wpdb'] = new StubWpdb();

require $argv[1];

$out = array();
foreach (json_decode(file_get_contents($argv[2]), true) as $term) {
    $params = array();
    $sql = alt_freetext_clause(array('company'), $term, $params);
    $out[] = array('term' => $term, 'sql' => $sql, 'params' => $params);
}
echo json_encode($out, JSON_UNESCAPED_UNICODE), "\n";
