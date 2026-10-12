<?php
/**
 * Renders templates/page-sources.php with WordPress stubbed out, so a test can
 * read the HTML a visitor gets. argv[1] = plugin dir. Prints the page.
 */
error_reporting(E_ALL & ~E_DEPRECATED & ~E_WARNING & ~E_NOTICE);
define('ABSPATH', '/tmp/');
define('ALT_PLUGIN_DIR', rtrim($argv[1], '/') . '/');
define('ALT_PLUGIN_URL', 'https://example.test/');
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function home_url($p = '') { return 'https://example.test/blog' . $p; }
function add_action() {}
function add_filter() {}
function alt_warn_states_phrase() { return 'many states'; }
function alt_state_warn_urls() { return array(); }
function alt_page_link_label($x = '') { return 'page'; }
function __($s) { return $s; }
function apply_filters($t, $v) { return $v; }
function get_option($k, $d = false) { return $d; }
include ALT_PLUGIN_DIR . 'templates/page-sources.php';
