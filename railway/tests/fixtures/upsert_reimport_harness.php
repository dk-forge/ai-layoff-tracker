<?php
/**
 * Loads the SHIPPED includes/db.php and reports what alt_db_upsert() actually
 * WRITES on the UPDATE branch, so the Python suite can assert on the real
 * function rather than on a reimplementation of it.
 *
 * usage: php upsert_reimport_harness.php <path/to/db.php> <path/to/cases.json>
 *
 * Cases are {"existing": {...}, "reimport": {...}} pairs. `existing` describes
 * the row already in the table (only `edited` is read by the function); the
 * harness reports every column the re-import's UPDATE would set, so a column
 * that is ABSENT from the payload is one the re-import leaves alone and a
 * column present with "" is one it blanks.
 */
foreach (array('add_action', 'add_filter', 'get_transient', 'set_transient',
               'register_rest_route', 'wp_json_encode', 'current_time',
               'get_option', 'update_option', 'apply_filters', 'do_action',
               'delete_transient', 'absint', 'update_post_meta',
               'get_post_meta', 'wp_cache_flush') as $fn) {
    if (!function_exists($fn)) { eval("function $fn() { return null; }"); }
}
if (!function_exists('sanitize_text_field')) {
    function sanitize_text_field($v) { return trim((string) $v); }
}
if (!function_exists('sanitize_textarea_field')) {
    function sanitize_textarea_field($v) { return trim((string) $v); }
}
if (!function_exists('sanitize_key')) {
    function sanitize_key($v) { return strtolower(preg_replace('/[^a-z0-9_\-]/i', '', (string) $v)); }
}
if (!defined('DAY_IN_SECONDS')) define('DAY_IN_SECONDS', 86400);
if (!defined('ABSPATH')) define('ABSPATH', '/tmp/');

/** Minimal $wpdb: records the UPDATE/INSERT payload, answers the lookup. */
class AltHarnessWpdb {
    public $prefix = 'wp_';
    public $insert_id = 0;
    public $last_error = '';
    public $existing = null;      // stdClass|null returned by get_row()
    public $updates = array();
    public $inserts = array();
    public function prepare($sql, ...$args) { return $sql; }
    public function get_row($sql) { return $this->existing; }
    public function update($table, $data, $where) { $this->updates[] = $data; return 1; }
    public function insert($table, $data) { $this->inserts[] = $data; $this->insert_id = 4242; return 1; }
    public function get_var($sql) { return null; }
    public function get_col($sql) { return array(); }
    public function get_results($sql, $mode = null) { return array(); }
    public function query($sql) { return 0; }
    public function get_charset_collate() { return ''; }
}
global $wpdb;
$wpdb = new AltHarnessWpdb();

require $argv[1];

$cases = json_decode(file_get_contents($argv[2]), true);
$out = array();
foreach ($cases as $name => $case) {
    $wpdb->updates = array();
    $wpdb->inserts = array();
    $existing = $case['existing'];
    $wpdb->existing = $existing === null ? null : (object) $existing;
    alt_db_upsert($case['reimport']);
    $out[$name] = array(
        'updated' => $wpdb->updates ? $wpdb->updates[0] : null,
        'inserted' => $wpdb->inserts ? $wpdb->inserts[0] : null,
    );
}
echo json_encode($out, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
