<?php
/**
 * Drives the ARCHIVE'S PUBLICATION GATE against documents the test chooses.
 *
 * The gate (alt_edition_public_safe in includes/digest-archive.php) is the one
 * thing standing between the composed content and a public page, so it is
 * exercised directly rather than through a database. It needs the real
 * alt_digest_link_hosts() from includes/subscribe.php, so both files are
 * loaded exactly as the plugin loads them.
 *
 * The WordPress stubs here are the same shapes digest_compose_harness.php
 * uses. Nothing is kinder than the function it stands in for: a stub that
 * accepted more than production does would make the assertion about the wrong
 * thing.
 *
 * argv[1] = absolute path to includes/subscribe.php
 * argv[2] = absolute path to includes/digest-archive.php
 * argv[3] = absolute path to a JSON file: {"docs": {"name": "<document>"},
 *           "slugs": [[freq, from, to], ...]}
 * stdout  = {"docs": {"name": {"ok": bool, "rule": str}}, "slugs": [...]}
 */

error_reporting(E_ALL & ~E_DEPRECATED);

define('ABSPATH', '/tmp/');
define('DAY_IN_SECONDS', 86400);
define('HOUR_IN_SECONDS', 3600);
define('MINUTE_IN_SECONDS', 60);
define('ALT_VERSION', '0.0.0-test');
define('ALT_PLUGIN_DIR', '/tmp/');

function add_action(...$a) {}
function add_filter(...$a) {}
function add_shortcode(...$a) {}
function add_rewrite_rule(...$a) {}
function register_rest_route(...$a) {}
function wp_schedule_event(...$a) {}
function wp_next_scheduled(...$a) { return time(); }
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function number_format_i18n($n) { return number_format((float) $n); }
function sanitize_key($s) { return preg_replace('/[^a-z0-9_\-]/', '', strtolower((string) $s)); }
function sanitize_text_field($s) { return trim((string) $s); }
function wp_strip_all_tags($s) { return strip_tags((string) $s); }
function wp_unslash($s) { return $s; }
function wp_json_encode($d) { return json_encode($d); }
function home_url($p = '') { return 'https://asktherecruiter.com/blog' . $p; }
function admin_url($p = '') { return 'https://asktherecruiter.com/blog/wp-admin/' . $p; }
function rest_url($p = '') { return 'https://asktherecruiter.com/blog/wp-json/' . ltrim($p, '/'); }
function get_option($k, $d = false) { return $d; }
function update_option($k, $v, $a = null) { return true; }
function get_transient($k) { return false; }
function set_transient($k, $v, $t = 0) { return true; }
function apply_filters($tag, $value) { return $value; }
function wp_parse_url($url, $component = -1) { return parse_url($url, $component); }
function add_query_arg($k, $v = null, $url = null) {
    if (is_array($k)) { $args = $k; $url = $v; } else { $args = array($k => $v); }
    $sep = strpos((string) $url, '?') === false ? '?' : '&';
    foreach ($args as $ak => $av) {
        $url .= $sep . rawurlencode($ak);
        if ((string) $av !== '') $url .= '=' . rawurlencode((string) $av);
        $sep = '&';
    }
    return $url;
}
function alt_announced_tier_sentence() { return ''; }
function alt_data_last_updated_label() { return ''; }
function rest_do_request($req) { return null; }
function get_posts($args = array()) { return array(); }

class WP_REST_Request {
    public $method, $route, $params = array();
    public function __construct($method = 'GET', $route = '') { $this->method = $method; $this->route = $route; }
    public function set_param($k, $v) { $this->params[$k] = $v; }
    public function get_param($k) { return $this->params[$k] ?? null; }
}
class WP_REST_Response {
    public function __construct($data = null, $status = 200) {}
    public function header($k, $v) {}
}

require $argv[1];
require $argv[2];

$in = json_decode(file_get_contents($argv[3]), true);
$out = array('docs' => array(), 'slugs' => array());
foreach ((array) ($in['docs'] ?? array()) as $name => $doc) {
    $out['docs'][$name] = alt_edition_public_safe((string) $doc);
}
foreach ((array) ($in['slugs'] ?? array()) as $triple) {
    $out['slugs'][] = alt_edition_slug($triple[0], $triple[1], $triple[2]);
}
echo json_encode($out);
