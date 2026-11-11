<?php
/**
 * Loads the SHIPPED includes/db.php behind a fake $wpdb whose live table has
 * a configurable column set, and reports what the schema guard and the
 * INSERT path of alt_db_upsert() actually do.
 *
 * usage: php schema_drift_harness.php <db.php> <mode> [live columns csv]
 *   mode "schema"  : print the columns the shipped CREATE TABLE declares
 *   mode "insert"  : print the column names a first-listing INSERT writes
 *   mode "missing" : print alt_db_missing_columns() against the live set
 *   mode "fail"    : make the INSERT fail with Unknown column and print what
 *                    was recorded and what repair ran
 */
foreach (array('add_action', 'add_filter', 'get_transient', 'set_transient',
               'register_rest_route', 'wp_json_encode', 'current_time',
               'apply_filters', 'do_action', 'delete_transient', 'absint',
               'update_post_meta', 'get_post_meta', 'wp_cache_flush', 'dbDelta') as $fn) {
    if (!function_exists($fn)) { eval("function $fn() { return null; }"); }
}
$GLOBALS['alt_opts'] = array();
function get_option($k, $d = false) { return array_key_exists($k, $GLOBALS['alt_opts']) ? $GLOBALS['alt_opts'][$k] : $d; }
function update_option($k, $v, $a = null) { $GLOBALS['alt_opts'][$k] = $v; return true; }
function sanitize_text_field($v) { return trim((string) $v); }
function sanitize_textarea_field($v) { return trim((string) $v); }
function sanitize_key($v) { return strtolower(preg_replace('/[^a-z0-9_\-]/i', '', (string) $v)); }
if (!defined('DAY_IN_SECONDS')) define('DAY_IN_SECONDS', 86400);
@mkdir(sys_get_temp_dir() . '/altwp/wp-admin/includes', 0777, true);
@file_put_contents(sys_get_temp_dir() . '/altwp/wp-admin/includes/upgrade.php', '<?php');
if (!defined('ABSPATH')) define('ABSPATH', sys_get_temp_dir() . '/altwp/');

class AltDriftWpdb {
    public $prefix = 'wp_';
    public $insert_id = 0;
    public $last_error = '';
    public $live = array();
    public $fail_insert = false;
    public $inserts = array();
    public $queries = array();
    public function prepare($sql, ...$args) { return $sql; }
    public function get_row($sql) { return null; }
    public function update($t, $d, $w) { return 1; }
    public function insert($t, $data) {
        $this->inserts[] = $data;
        if ($this->fail_insert) {
            $this->last_error = "Unknown column 'created_at' in 'field list'";
            $this->insert_id = 0;
            return false;
        }
        $this->last_error = '';
        $this->insert_id = 4242;
        return 1;
    }
    public function get_var($sql) { return null; }
    public function get_col($sql) { return $this->live; }
    public function get_results($sql, $mode = null) { return array(); }
    public function query($sql) { $this->queries[] = $sql; return 0; }
    public function get_charset_collate() { return ''; }
}
global $wpdb;
$wpdb = new AltDriftWpdb();
require $argv[1];
$mode = $argv[2];
$wpdb->live = isset($argv[3]) && $argv[3] !== '' ? explode(',', $argv[3]) : array();
$row = array('company' => 'Acme Logistics Inc', 'job_count' => 10,
             'dedup_hash' => 'abcdef0123456789abcdef0123456789',
             'layoff_date' => '2026-11-01');
if ($mode === 'schema') {
    echo json_encode(alt_db_layoffs_columns()), "\n";
} elseif ($mode === 'insert') {
    alt_db_upsert($row);
    echo json_encode(array_keys($wpdb->inserts[0])), "\n";
} elseif ($mode === 'missing') {
    echo json_encode(alt_db_missing_columns()), "\n";
} elseif ($mode === 'fail') {
    $wpdb->fail_insert = true;
    $id = alt_db_upsert($row);
    echo json_encode(array(
        'returned' => $id,
        'attempts' => count($wpdb->inserts),
        'recorded' => get_option('alt_last_insert_error'),
        'alters' => array_values(array_filter($wpdb->queries, function ($q) { return stripos($q, 'ALTER TABLE') !== false; })),
    )), "\n";
}
