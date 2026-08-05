<?php
/**
 * Test harness for includes/subscribe.php: WordPress stubs + a SQLite-backed
 * $wpdb, driving the REAL handler functions end to end. Run by
 * tests/test_digest_subscription.py; prints one JSON object of observations.
 *
 * argv[1] = absolute path to includes/subscribe.php
 */

error_reporting(E_ALL & ~E_DEPRECATED);

define('ABSPATH', '/tmp/');
define('DAY_IN_SECONDS', 86400);
define('HOUR_IN_SECONDS', 3600);
define('MINUTE_IN_SECONDS', 60);

$GLOBALS['__mails'] = array();
$GLOBALS['__options'] = array();
$GLOBALS['__transients'] = array();
$GLOBALS['__redirect'] = null;

class AltRedirect extends Exception {}

function add_action(...$a) {}
function add_shortcode(...$a) {}
function wp_schedule_event(...$a) {}
function wp_next_scheduled(...$a) { return time(); }
function status_header($c) {}
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function number_format_i18n($n) { return number_format((float) $n); }
function sanitize_key($s) { return preg_replace('/[^a-z0-9_\-]/', '', strtolower((string) $s)); }
function sanitize_text_field($s) { return trim((string) $s); }
function sanitize_email($s) { return filter_var(trim((string) $s), FILTER_SANITIZE_EMAIL); }
function is_email($s) { return filter_var((string) $s, FILTER_VALIDATE_EMAIL) !== false; }
function wp_unslash($s) { return $s; }
function wp_json_encode($d) { return json_encode($d); }
function home_url($p = '') { return 'https://example.test/blog' . $p; }
function admin_url($p = '') { return 'https://example.test/blog/wp-admin/' . $p; }
function wp_get_referer() { return 'https://example.test/blog/ai-layoff-tracker/'; }
function wp_nonce_field(...$a) { echo ''; }
function wp_verify_nonce($n, $a) { return $n === 'good-nonce'; }
function add_query_arg($k, $v = null, $url = null) {
    if (is_array($k)) { $args = $k; $url = $v; } else { $args = array($k => $v); }
    $sep = strpos($url, '?') === false ? '?' : '&';
    foreach ($args as $ak => $av) { $url .= $sep . rawurlencode($ak) . '=' . rawurlencode((string) $av); $sep = '&'; }
    return $url;
}
function remove_query_arg($keys, $url) {
    foreach ((array) $keys as $k) { $url = preg_replace('/([?&])' . preg_quote($k, '/') . '=[^&#]*/', '$1', $url); }
    return rtrim(str_replace('?&', '?', $url), '?&');
}
function wp_safe_redirect($url) { $GLOBALS['__redirect'] = $url; throw new AltRedirect($url); }
function get_option($k, $d = false) { return array_key_exists($k, $GLOBALS['__options']) ? $GLOBALS['__options'][$k] : $d; }
function update_option($k, $v, $autoload = null) { $GLOBALS['__options'][$k] = $v; return true; }
function get_transient($k) { return array_key_exists($k, $GLOBALS['__transients']) ? $GLOBALS['__transients'][$k] : false; }
function set_transient($k, $v, $ttl = 0) { $GLOBALS['__transients'][$k] = $v; return true; }
function delete_transient($k) { unset($GLOBALS['__transients'][$k]); return true; }
function wp_mail($to, $subject, $body, $headers = array()) {
    $GLOBALS['__mails'][] = array('to' => $to, 'subject' => $subject, 'body' => $body, 'headers' => (array) $headers);
    return true;
}

function alt_source_health_record($source, $status, $entries, $detail) {
    $health = get_option('alt_source_health');
    if (!is_array($health)) $health = array();
    $health[$source] = array('status' => $status, 'entries' => (int) $entries,
                             'checked_at' => gmdate('c'), 'detail' => (string) $detail);
    update_option('alt_source_health', $health, false);
    return $health[$source];
}

/** Minimal REST doubles so the digest can compose a layoff section. */
class WP_REST_Request {
    public $params = array(); public $route;
    public function __construct($m = 'GET', $route = '') { $this->route = $route; }
    public function set_param($k, $v) { $this->params[$k] = $v; }
    public function get_param($k) { return $this->params[$k] ?? null; }
}
class FakeRestResponse {
    private $data; private $err;
    public function __construct($data, $err = false) { $this->data = $data; $this->err = $err; }
    public function is_error() { return $this->err; }
    public function get_data() { return $this->data; }
}
function rest_do_request($req) {
    if (strpos($req->route, '/layoffs/v1/aggregate') === 0) {
        return new FakeRestResponse(array(
            'totals' => array('entries' => 12, 'jobs' => 3456, 'companies' => 9),
            'leaders' => array(
                array('company_name' => 'Acme Corp', 'job_count' => 1200, 'location' => 'CA, United States'),
                array('company_name' => 'Globex', 'job_count' => 800, 'location' => 'Germany'),
            ),
        ));
    }
    return new FakeRestResponse(null, true);   // talent plugin "inactive"
}

/** SQLite-backed wpdb double, honouring the prepare()/query() subset used. */
class FakeWpdb {
    public $prefix = 'wp_';
    public $pdo;
    public function __construct() {
        $this->pdo = new PDO('sqlite::memory:');
        $this->pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $this->pdo->exec('CREATE TABLE wp_alt_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            consent_layoff INTEGER NOT NULL DEFAULT 0,
            consent_talent INTEGER NOT NULL DEFAULT 0,
            consent_articles INTEGER NOT NULL DEFAULT 0,
            freq_layoff TEXT NOT NULL DEFAULT "weekly",
            freq_talent TEXT NOT NULL DEFAULT "weekly",
            freq_articles TEXT NOT NULL DEFAULT "weekly",
            status TEXT NOT NULL DEFAULT "pending",
            confirm_token TEXT NULL,
            unsub_token TEXT NOT NULL,
            pending_prefs TEXT NULL,
            created_at TEXT NOT NULL,
            confirmed_at TEXT NULL,
            unsubscribed_at TEXT NULL,
            last_sent_at TEXT NULL)');
    }
    public function esc_like($s) { return $s; }
    public function prepare($sql, ...$args) {
        if (count($args) === 1 && is_array($args[0])) $args = $args[0];
        $i = 0;
        return preg_replace_callback('/%[sd]/', function ($m) use (&$i, $args) {
            $v = $args[$i++];
            return $m[0] === '%d' ? (string) (int) $v : $this->pdo->quote((string) $v);
        }, $sql);
    }
    public function get_var($sql) {
        if (preg_match("/SHOW TABLES LIKE '(.+)'/", $sql, $m)) {
            $st = $this->pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name=" . $this->pdo->quote($m[1]));
            $r = $st->fetchColumn();
            return $r === false ? null : $r;
        }
        $r = $this->pdo->query($sql)->fetchColumn();
        return $r === false ? null : $r;
    }
    public function get_row($sql, $output = OBJECT) {
        $r = $this->pdo->query($sql)->fetch(PDO::FETCH_ASSOC);
        if (!$r) return null;
        return $output === ARRAY_A ? $r : (object) $r;
    }
    public function get_results($sql, $output = OBJECT) {
        $rows = $this->pdo->query($sql)->fetchAll(PDO::FETCH_ASSOC);
        if ($output === ARRAY_A) return $rows;
        return array_map(function ($r) { return (object) $r; }, $rows);
    }
    public function query($sql) { return $this->pdo->exec($sql); }
    public function insert($table, $data) {
        $cols = array_keys($data);
        $vals = array_map(function ($v) { return $v === null ? 'NULL' : $this->pdo->quote((string) $v); }, array_values($data));
        return $this->pdo->exec("INSERT INTO $table (" . implode(',', $cols) . ') VALUES (' . implode(',', $vals) . ')');
    }
    public function update($table, $data, $where) {
        $set = array(); $cond = array();
        foreach ($data as $k => $v) $set[] = "$k = " . ($v === null ? 'NULL' : $this->pdo->quote((string) $v));
        foreach ($where as $k => $v) $cond[] = "$k = " . $this->pdo->quote((string) $v);
        return $this->pdo->exec("UPDATE $table SET " . implode(',', $set) . ' WHERE ' . implode(' AND ', $cond));
    }
}
if (!defined('OBJECT')) define('OBJECT', 'OBJECT');
if (!defined('ARRAY_A')) define('ARRAY_A', 'ARRAY_A');
$GLOBALS['wpdb'] = new FakeWpdb();

require $argv[1];

/* ------------------------------------------------------------------ */
/* Drive the real functions                                            */
/* ------------------------------------------------------------------ */

function drive($fn) {
    $GLOBALS['__redirect'] = null;
    try { $fn(); } catch (AltRedirect $e) {}
    $url = (string) $GLOBALS['__redirect'];
    return preg_match('/alt_dg=([a-z]+)/', $url, $m) ? $m[1] : $url;
}
function row($email) {
    global $wpdb;
    return $wpdb->get_row('SELECT * FROM wp_alt_subscribers WHERE email = ' . $wpdb->pdo->quote($email), ARRAY_A);
}
function post_signup($email, $lists, $freq = 'weekly') {
    $_POST = array('alt_digest_nonce' => 'good-nonce', 'alt_ts' => time() - 10,
                   'alt_email' => $email, 'alt_freq' => $freq, 'alt_website' => '');
    foreach ($lists as $l) $_POST['alt_list_' . $l] = '1';
    $_SERVER['REMOTE_ADDR'] = '203.0.113.9';
    $_SERVER['REQUEST_METHOD'] = 'POST';
    return drive('alt_digest_subscribe_submit');
}

$out = array();
$mails = &$GLOBALS['__mails'];

// 1. Zero boxes is refused before anything touches the store.
$out['prefs_none_is_null'] = alt_digest_prefs_from_post(array('alt_freq' => 'weekly')) === null;
$out['submit_zero_boxes'] = post_signup('zero@example.com', array());
$out['zero_row_absent'] = row('zero@example.com') === null;
$out['zero_mails'] = count($mails);

// 2. A real signup: pending + exactly one mail (the confirmation).
$out['submit_ok'] = post_signup('reader@example.com', array('layoff', 'articles'));
$r = row('reader@example.com');
$out['status_after_signup'] = $r['status'];
$out['consents'] = array((int) $r['consent_layoff'], (int) $r['consent_talent'], (int) $r['consent_articles']);
$out['confirm_token'] = $r['confirm_token'];
$out['unsub_token'] = $r['unsub_token'];
$out['mails_after_signup'] = count($mails);
$out['confirm_mail_to'] = $mails[0]['to'] ?? '';
$out['confirm_mail_subject'] = $mails[0]['subject'] ?? '';
$out['confirm_mail_has_token'] = strpos($mails[0]['body'] ?? '', $r['confirm_token']) !== false;
$out['confirm_mail_has_email_in_url'] = (bool) preg_match('/https?:\S*reader(%40|@)/', $mails[0]['body'] ?? '');

// 3. DOUBLE OPT-IN: a digest run while pending sends NOTHING.
list($sent, $eligible) = alt_digest_send('weekly');
$out['send_while_pending'] = array($sent, $eligible, count($mails));

// 4. Confirm, then the digest goes out with unsubscribe affordances.
$_REQUEST = array('t' => $r['confirm_token']);
$_SERVER['REQUEST_METHOD'] = 'GET';
$out['confirm_redirect'] = drive('alt_digest_confirm');
$r2 = row('reader@example.com');
$out['status_after_confirm'] = $r2['status'];
$out['confirm_token_cleared'] = $r2['confirm_token'] === null || $r2['confirm_token'] === '';
$out['confirm_reuse'] = drive('alt_digest_confirm');   // same link again: politely expired
list($sent2, $eligible2) = alt_digest_send('weekly');
$digest = end($mails);
$out['send_after_confirm'] = array($sent2, $eligible2);
$out['digest_to'] = $digest['to'];
$out['digest_headers'] = $digest['headers'];
$out['digest_has_unsub_link'] = strpos($digest['body'], $r2['unsub_token']) !== false;
$out['digest_has_img'] = stripos($digest['body'], '<img') !== false;
$out['digest_mentions_layoff'] = strpos($digest['body'], 'AI Layoff Tracker') !== false;
$out['digest_daily_none'] = alt_digest_send('daily');   // weekly subscriber gets no daily mail

// 5. Health stamp carries counts, never an address.
alt_digest_cron_run();
$health = get_option('alt_source_health');
$out['health_row'] = $health['digest_mailer'] ?? null;

// 6. Unsubscribe: one click, idempotent, then nothing ever sends again.
$mail_count_before_unsub = count($mails);
$_REQUEST = array('t' => $r2['unsub_token']);
$_SERVER['REQUEST_METHOD'] = 'GET';
$out['unsub1'] = drive('alt_digest_unsubscribe');
$r3 = row('reader@example.com');
$out['status_after_unsub'] = $r3['status'];
$out['unsub2'] = drive('alt_digest_unsubscribe');
$r4 = row('reader@example.com');
$out['unsub_idempotent_same_stamp'] = $r3['unsubscribed_at'] === $r4['unsubscribed_at'];
list($sent3, ) = alt_digest_send('weekly');
$out['send_after_unsub'] = array($sent3, count($mails) - $mail_count_before_unsub);

// 7. Tokens: two subscribers, all four tokens distinct 64-hex, none derived
//    from the address by any obvious digest.
$GLOBALS['__transients'] = array();   // clear the rate limiter between scenarios
post_signup('second@example.com', array('talent'), 'daily');
$s = row('second@example.com');
$tokens = array($r['confirm_token'], $r['unsub_token'], $s['confirm_token'], $s['unsub_token']);
$out['tokens_distinct'] = count(array_unique($tokens)) === 4;
$out['tokens_hex64'] = array_values(array_map(function ($t) { return (bool) preg_match('/^[a-f0-9]{64}$/', (string) $t); }, $tokens));
$derived = array();
foreach (array('second@example.com') as $e) {
    foreach (array('md5', 'sha1', 'sha256', 'sha512') as $alg) {
        $derived[] = substr(hash($alg, $e), 0, 64);
        $derived[] = substr(hash($alg, strrev($e)), 0, 64);
    }
    $derived[] = substr(bin2hex($e), 0, 64);
}
$out['token_not_derived_from_email'] = !in_array(substr($s['confirm_token'], 0, 64), $derived, true)
                                    && !in_array(substr($s['unsub_token'], 0, 64), $derived, true);

// 8. Rate limit: the 6th signup in an hour from one IP is refused.
$GLOBALS['__transients'] = array();
$codes = array();
for ($i = 0; $i < 6; $i++) $codes[] = post_signup("rl$i@example.com", array('layoff'));
$out['rate_limit_codes'] = $codes;

// 9. Purge deletes exactly what the privacy note claims.
global $wpdb;
$wpdb->pdo->exec('DELETE FROM wp_alt_subscribers');
$old = gmdate('Y-m-d H:i:s', time() - 40 * 86400);
$fresh = gmdate('Y-m-d H:i:s', time() - 5 * 86400);
$seed = function ($email, $status, $created, $confirmed, $unsubbed) use ($wpdb) {
    $wpdb->insert('wp_alt_subscribers', array(
        'email' => $email, 'status' => $status, 'unsub_token' => bin2hex(random_bytes(32)),
        'created_at' => $created, 'confirmed_at' => $confirmed, 'unsubscribed_at' => $unsubbed));
};
$seed('unsub-old@example.com', 'unsubscribed', $old, $old, $old);
$seed('unsub-fresh@example.com', 'unsubscribed', $old, $old, $fresh);
$seed('pending-old@example.com', 'pending', $old, null, null);
$seed('pending-fresh@example.com', 'pending', $fresh, null, null);
$seed('confirmed-old@example.com', 'confirmed', $old, $old, null);
$out['purged'] = alt_digest_purge();
$out['left_after_purge'] = $wpdb->get_results('SELECT email FROM wp_alt_subscribers ORDER BY email', ARRAY_A);

// 10. A confirmed address re-submitting with new choices keeps its current
//     prefs until the NEW link is clicked (a stranger cannot alter them).
$wpdb->pdo->exec('DELETE FROM wp_alt_subscribers');
$GLOBALS['__transients'] = array();
post_signup('careful@example.com', array('layoff'));
$c = row('careful@example.com');
$_REQUEST = array('t' => $c['confirm_token']);
drive('alt_digest_confirm');
$GLOBALS['__transients'] = array();
post_signup('careful@example.com', array('talent'), 'daily');   // "someone" re-submits
$c2 = row('careful@example.com');
$out['prefs_unchanged_until_reconfirm'] = array((int) $c2['consent_layoff'], (int) $c2['consent_talent'], $c2['status']);
$_REQUEST = array('t' => $c2['confirm_token']);
$out['change_confirm_redirect'] = drive('alt_digest_confirm');
$c3 = row('careful@example.com');
$out['prefs_after_reconfirm'] = array((int) $c3['consent_layoff'], (int) $c3['consent_talent'], $c3['freq_talent'], $c3['status']);

echo json_encode($out), "\n";
