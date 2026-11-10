<?php
/**
 * Renders the SHIPPED includes/public-logs.php pages to strings.
 *
 * argv[1] = includes/public-logs.php
 * argv[2] = JSON file {"log": [corrections log entries, append order]}
 * argv[3] = data/update-log.json
 * stdout  = {"corrections": "<html>", "update_log": "<html>"}
 */
error_reporting(E_ALL & ~E_DEPRECATED);
define('ABSPATH', '/tmp/');
define('ALT_VERSION', '0.0.0-test');
define('ALT_PLUGIN_DIR', '/tmp/');
function add_action(...$a) {}
function add_filter(...$a) {}
function add_rewrite_rule(...$a) {}
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function home_url($p = '') { return 'https://asktherecruiter.com/blog' . $p; }
function rest_url($p = '') { return 'https://asktherecruiter.com/blog/wp-json/' . ltrim($p, '/'); }
function wp_json_encode($d, $f = 0) { return json_encode($d, $f); }
function get_option($k, $d = false) { return $d; }
function update_option($k, $v, $a = null) { return true; }

require $argv[1];
$in = json_decode(file_get_contents($argv[2]), true);
$log = json_decode(file_get_contents($argv[3]), true);
echo json_encode(array(
    'corrections' => alt_public_log_render_corrections($in['log']),
    'update_log'  => alt_public_log_render_update_log($log['entries']),
    'sitemap'     => alt_public_logs_sitemap_xml($in['log'], $log['entries']),
), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
