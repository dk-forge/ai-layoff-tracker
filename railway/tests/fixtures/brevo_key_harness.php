<?php
// Runs alt_brevo_key_lookup() against stubbed options. Prints sources and a
// boolean "found", never a key.
$GLOBALS['__opts'] = array();
function get_option($n, $d = false) { return array_key_exists($n, $GLOBALS['__opts']) ? $GLOBALS['__opts'][$n] : $d; }
function add_action() {} function add_filter() {} function register_rest_route() {}
if (!defined('ABSPATH')) define('ABSPATH', '/tmp/');
require $argv[1];
$K = 'xkeysib-' . str_repeat('a', 64) . '-test';
$cases = array(
  'none' => array(),
  'main_access' => array('sib_main_option' => array('access_key' => $K)),
  'main_api' => array('sib_main_option' => array('api_key' => $K)),
  'v3_string' => array('sib_api_key_v3' => $K),
  'v3_array' => array('sib_api_key_v3' => array('access_key' => $K)),
  'v2_only' => array('sib_main_option' => array('access_key' => 'old-v2-key')),
);
$out = array();
foreach ($cases as $name => $opts) {
  $GLOBALS['__opts'] = $opts;
  $r = alt_brevo_key_lookup();
  $out[$name] = array('source' => $r['source'], 'found' => $r['key'] === $K, 'empty' => $r['key'] === '');
}
echo json_encode($out);
