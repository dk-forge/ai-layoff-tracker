<?php
/**
 * Harness for includes/labour-context.php: WordPress stubs, the REAL
 * reference-data.php + labour-context.php + templates/partials/labour-context.php.
 *
 *   argv[1]  plugin dir (with trailing slash)
 *   argv[2]  JSON object {option_name: value} to seed get_option
 *   argv[3]  mode: "section" | "stat"
 *   argv[4]  (stat) dim, argv[5] (stat) value
 *
 * Prints JSON {"html": "..."} or {"error": "..."}. Any PHP warning is an error.
 */
error_reporting(E_ALL);
set_error_handler(function ($no, $msg, $file, $line) { throw new ErrorException($msg, 0, $no, $file, $line); });
define('ABSPATH', '/tmp/');
define('ALT_PLUGIN_DIR', $argv[1]);
$GLOBALS['__opts'] = json_decode($argv[2], true) ?: array();
function add_action(...$a) {}
function add_shortcode(...$a) {}
function register_rest_route(...$a) {}
function get_option($k, $d = false) { return array_key_exists($k, $GLOBALS['__opts']) ? $GLOBALS['__opts'][$k] : $d; }
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function home_url($p = '') { return 'https://example.test/blog' . $p; }
function rest_url($p = '') { return 'https://example.test/blog/wp-json/' . ltrim($p, '/'); }
function alt_template($file, $vars = array()) {
    extract($vars, EXTR_SKIP);
    ob_start();
    include ALT_PLUGIN_DIR . 'templates/' . $file;
    return ob_get_clean();
}
try {
    require ALT_PLUGIN_DIR . 'includes/reference-data.php';
    require ALT_PLUGIN_DIR . 'includes/labour-context.php';
    $html = $argv[3] === 'stat' ? alt_labour_context_stat($argv[4], $argv[5]) : alt_shortcode_labour_context();
    echo json_encode(array('html' => $html));
} catch (Throwable $e) {
    echo json_encode(array('error' => get_class($e) . ': ' . $e->getMessage()));
}
