<?php
/**
 * Renders the digest COMPOSERS against a fixture /aggregate response.
 *
 * WHY A SECOND HARNESS. tests/fixtures/digest_harness.php drives the signup
 * and confirm handlers, and to do that it carries a SQLite $wpdb and a stack
 * of request plumbing. The composers need almost none of it and need one
 * thing it does not have: a `rest_do_request` that answers with a payload the
 * test chose. Bolting a REST stub onto the signup harness would couple two
 * unrelated tests to one file, so this is its own.
 *
 * NOTHING HERE INVENTS A FIGURE. The fixture payloads are shapes copied from
 * a real /aggregate response (the column order of the top_* tuples especially,
 * which is [label, all_jobs, ai_jobs, display_label, verified_jobs,
 * ai_verified_jobs] and is the reason the country block was reading the wrong
 * tier). The composer does the arithmetic; this only feeds it.
 *
 * argv[1] = absolute path to includes/subscribe.php
 * argv[2] = absolute path to a JSON file: {"layoff": {...}, "ytd": {...},
 *           "from": "...", "to": "..."}
 * stdout  = one JSON object: {"html": ..., "text": ...} or {"null": true}
 */

error_reporting(E_ALL & ~E_DEPRECATED);

define('ABSPATH', '/tmp/');
define('DAY_IN_SECONDS', 86400);
define('HOUR_IN_SECONDS', 3600);
define('MINUTE_IN_SECONDS', 60);

function add_action(...$a) {}
function add_shortcode(...$a) {}
function wp_schedule_event(...$a) {}
function wp_next_scheduled(...$a) { return time(); }
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function number_format_i18n($n) { return number_format((float) $n); }
function sanitize_key($s) { return preg_replace('/[^a-z0-9_\-]/', '', strtolower((string) $s)); }
function sanitize_text_field($s) { return trim((string) $s); }
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
    /*
      DROPS THE `=` ON AN EMPTY VALUE, because the real one does. Observed in
      a live preview on 2026-08-17: a caller passing '' got `&years&quarters`
      and not `&years=&quarters=`. This stub used to append `=` unconditionally
      and so passed a test about the digest's tracker link that production
      would have failed. A stub that is kinder than the function it stands in
      for is worse than no stub: it makes the assertion about the wrong thing.
    */
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

// The shared sentence the real db.php owns. Copied verbatim so a drift shows
// up as a failing assertion rather than as a quietly missing clause.
function alt_announced_tier_sentence() {
    return 'Announced cuts are plans companies have stated that no filing or named report verifies yet.';
}

/**
 * api.php's "data last updated" stamp, fed from the fixture.
 *
 * Nothing is copied here, unlike alt_announced_tier_sentence above: the real
 * function's job is to FORMAT a timestamp out of an option, which is api.php's
 * business and not the composer's. What the composer has to get right is the
 * two branches, a stamp and no stamp, so the fixture supplies the string and a
 * fixture that omits it exercises the empty one. Absence of a stamp must print
 * no sentence, never a guess.
 */
function alt_data_last_updated_label() {
    global $FIXTURE;
    return (string) ($FIXTURE['last_updated_label'] ?? '');
}

class WP_REST_Request {
    public $method, $route, $params = array();
    public function __construct($method, $route) { $this->method = $method; $this->route = $route; }
    public function set_param($k, $v) { $this->params[$k] = $v; }
    public function get_param($k) { return $this->params[$k] ?? null; }
}

class WP_REST_Response_Stub {
    private $data, $error;
    public function __construct($data, $error = false) { $this->data = $data; $this->error = $error; }
    public function is_error() { return $this->error; }
    public function get_data() { return $this->data; }
}

$FIXTURE = json_decode(file_get_contents($argv[2]), true);

/**
 * The stub REST layer. Chooses a fixture by the window the composer asked
 * for, so the year-to-date call and the period call cannot be confused: the
 * composer sending the wrong `from` is exactly the kind of bug worth failing.
 */
function rest_do_request($req) {
    global $FIXTURE;
    if (strpos($req->route, '/talent/') === 0) {
        $key = ($req->get_param('since') === $FIXTURE['from']) ? 'talent' : 'talent_ytd';
        if (empty($FIXTURE[$key])) return new WP_REST_Response_Stub(null, true);
        return new WP_REST_Response_Stub($FIXTURE[$key]);
    }
    $key = ($req->get_param('from') === $FIXTURE['from']) ? 'layoff' : 'ytd';
    if (empty($FIXTURE[$key])) return new WP_REST_Response_Stub(null, true);
    return new WP_REST_Response_Stub($FIXTURE[$key]);
}

require $argv[1];

$which = $FIXTURE['compose'] ?? 'layoff';
$out = ($which === 'talent')
    ? alt_digest_compose_talent($FIXTURE['from'], $FIXTURE['to'], 0)
    : alt_digest_compose_layoff($FIXTURE['from'], $FIXTURE['to'], 0);

echo json_encode($out === null ? array('null' => true) : $out);
