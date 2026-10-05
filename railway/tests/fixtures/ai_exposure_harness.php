<?php
/**
 * Harness for includes/ai-exposure.php: WordPress stubs, the REAL
 * reference-data.php + ai-exposure.php + templates/partials/ai-exposure.php.
 *
 *   argv[1]  plugin dir (with trailing slash)
 *   argv[2]  JSON object {option_name: value} to seed get_option, or @file
 *   argv[3]  mode: "section" (the shortcode HTML) | "bundle" (alt_ax_bundle)
 *
 * Prints JSON {"html": ...} or {"error": "..."}. Any PHP warning is an error.
 */
error_reporting(E_ALL);
set_error_handler(function ($no, $msg, $file, $line) { throw new ErrorException($msg, 0, $no, $file, $line); });
define('ABSPATH', '/tmp/');
define('ALT_PLUGIN_DIR', $argv[1]);
$GLOBALS['__opts'] = json_decode($argv[2][0] === '@' ? file_get_contents(substr($argv[2], 1)) : $argv[2], true) ?: array();
function add_action(...$a) {}
function add_shortcode(...$a) {}
function register_rest_route(...$a) {}
function get_option($k, $d = false) { return array_key_exists($k, $GLOBALS['__opts']) ? $GLOBALS['__opts'][$k] : $d; }
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function alt_template($file, $vars = array()) {
    extract($vars, EXTR_SKIP);
    ob_start();
    include ALT_PLUGIN_DIR . 'templates/' . $file;
    return ob_get_clean();
}
try {
    require ALT_PLUGIN_DIR . 'includes/reference-data.php';
    require ALT_PLUGIN_DIR . 'includes/ai-exposure.php';
    $html = ($argv[3] ?? 'section') === 'bundle' ? alt_ax_bundle(alt_ax_doc()) : alt_shortcode_ai_exposure();
    echo json_encode(array('html' => $html));
} catch (Throwable $e) {
    echo json_encode(array('error' => get_class($e) . ': ' . $e->getMessage()));
}
