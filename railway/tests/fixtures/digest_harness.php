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
class AltDie extends Exception {
    public $body;
    public function __construct($body, $code) { parent::__construct($body, $code); $this->body = $body; }
}

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
/*
  THE REFERER THE REQUEST ACTUALLY CARRIED, not a fixed one. This returned the
  tracker page unconditionally, so anything reading it was tested against a
  value no real request had to produce. That hid a redirect loop: the
  unsubscribe button POSTs from a page whose URL is the unsubscribe route, and
  a handler returning the reader to the referer re-enters itself.
*/
function wp_get_referer() {
    $ref = (string) ($_SERVER['HTTP_REFERER'] ?? '');
    return $ref !== '' ? $ref : 'https://example.test/blog/ai-layoff-tracker/';
}
function wp_nonce_field(...$a) { echo ''; }
function wp_verify_nonce($n, $a) { return $n === 'good-nonce'; }
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
function remove_query_arg($keys, $url) {
    foreach ((array) $keys as $k) { $url = preg_replace('/([?&])' . preg_quote($k, '/') . '=[^&#]*/', '$1', $url); }
    return rtrim(str_replace('?&', '?', $url), '?&');
}
function wp_safe_redirect($url) { $GLOBALS['__redirect'] = $url; throw new AltRedirect($url); }
/**
 * The one-click unsubscribe POST ends the request without redirecting, so it
 * cannot be observed the way alt_digest_redirect() is. Same trick: the
 * terminal call throws instead of exiting, and the driver catches it.
 */
function wp_die($message = '', $title = '', $args = array()) {
    $code = is_array($args) ? (int) ($args['response'] ?? 500) : 500;
    throw new AltDie((string) $message, $code);
}
function nocache_headers() { $GLOBALS['__nocache'] = true; }
function get_option($k, $d = false) { return array_key_exists($k, $GLOBALS['__options']) ? $GLOBALS['__options'][$k] : $d; }
function update_option($k, $v, $autoload = null) { $GLOBALS['__options'][$k] = $v; return true; }
function get_transient($k) { return array_key_exists($k, $GLOBALS['__transients']) ? $GLOBALS['__transients'][$k] : false; }
function set_transient($k, $v, $ttl = 0) { $GLOBALS['__transients'][$k] = $v; return true; }
function delete_transient($k) { unset($GLOBALS['__transients'][$k]); return true; }
function wp_mail($to, $subject, $body, $headers = array()) {
    $GLOBALS['__mails'][] = array('to' => $to, 'subject' => $subject, 'body' => $body, 'headers' => (array) $headers);
    return true;
}

function apply_filters($tag, $value, ...$rest) { return $value; }
function wp_strip_all_tags($s) { return trim(strip_tags((string) $s)); }

/**
 * The site's own posts, for the articles section. Set $GLOBALS['__posts'] to a
 * list of post objects; this honours the subset of get_posts() arguments the
 * composer actually passes (type, status, the date_query window, the ceiling).
 */
$GLOBALS['__posts'] = array();
function get_posts($args = array()) {
    $type   = $args['post_type'] ?? 'post';
    $status = $args['post_status'] ?? 'publish';
    $limit  = (int) ($args['numberposts'] ?? 5);
    $window = $args['date_query'][0] ?? array();
    $after  = (string) ($window['after'] ?? '');
    $before = (string) ($window['before'] ?? '');
    // NEWEST FIRST, like the real get_posts() the composer asks for. This
    // stub used to return insertion order, so "the 3 newest" was asserted
    // against a list that was not sorted and the claim was never tested.
    $pool = $GLOBALS['__posts'];
    usort($pool, function ($a, $b) {
        return strcmp((string) ($b->post_date_gmt ?? ''), (string) ($a->post_date_gmt ?? ''));
    });
    // `fields => 'ids'` answers with ids and `numberposts => -1` lifts the
    // ceiling, as the real function does: the composer counts the window that
    // way since 2.20.171, and a stub that ignored either would hand the count
    // query the ceiling back.
    $ids_only = (($args['fields'] ?? '') === 'ids');
    $found = array();
    foreach ($pool as $i => $p) {
        if (($p->post_type ?? 'post') !== $type) continue;
        if (($p->post_status ?? 'publish') !== $status) continue;
        $when = (string) ($p->post_date_gmt ?? '');
        if ($after !== '' && $when < $after) continue;
        if ($before !== '' && $when > $before) continue;
        $found[] = $ids_only ? ($p->ID ?? ($i + 1)) : $p;
        if ($limit > 0 && count($found) >= $limit) break;
    }
    return $found;
}
function get_permalink($p) {
    $slug = is_object($p) ? (string) $p->post_name : (string) $p;
    return 'https://example.test/blog/' . $slug . '/';
}
function get_the_title($p) { return is_object($p) ? (string) $p->post_title : ''; }
/**
 * WordPress's own excerpt: the one an editor typed, or a trim of the post's
 * opening words when nobody did. That fallback is the whole reason this stub
 * exists. `post_excerpt` is empty on every post on the real blog, so the
 * digest's articles section shipped as a bare list of links while the code
 * that prints a blurb sat there looking correct. Neither branch writes a
 * sentence: one is the editor's words, the other the author's own first ones.
 */
function get_the_excerpt($p) {
    if (!is_object($p)) return '';
    $typed = trim((string) ($p->post_excerpt ?? ''));
    if ($typed !== '') return $typed;
    return trim((string) ($p->post_content ?? ''));
}
function wp_parse_url($url, $component = -1) { return $component === -1 ? parse_url($url) : parse_url($url, $component); }
function rest_url($path = '') { return 'https://example.test/blog/wp-json/' . ltrim($path, '/'); }
function register_rest_route(...$a) { $GLOBALS['__routes'][] = $a; }
class WP_REST_Response {
    public $data; public $status; public $headers = array();
    public function __construct($data = null, $status = 200) { $this->data = $data; $this->status = $status; }
    public function header($k, $v) { $this->headers[$k] = $v; }
    public function get_data() { return $this->data; }
}
$GLOBALS['__routes'] = array();

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
    public $params = array(); public $route; public $json = null;
    public function __construct($m = 'GET', $route = '') { $this->route = $route; }
    public function set_param($k, $v) { $this->params[$k] = $v; }
    public function get_param($k) { return $this->params[$k] ?? null; }
    /** The POST body /digest-complete reads. */
    public function set_json_params($p) { $this->json = $p; }
    public function get_json_params() { return $this->json; }
    public function get_header($k) { return ''; }
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
    public $insert_id = 0;
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
            last_sent_at TEXT NULL,
            last_sent_daily TEXT NULL,
            last_sent_weekly TEXT NULL)');
        $this->install_digest_log_tables();
    }
    /** The send log + aggregate click counter, mirroring includes/db.php. */
    public function install_digest_log_tables() {
        $this->pdo->exec('CREATE TABLE IF NOT EXISTS wp_alt_digest_sends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            freq TEXT NOT NULL DEFAULT "weekly",
            sent_at TEXT NOT NULL,
            recipients INTEGER NOT NULL DEFAULT 0,
            eligible INTEGER NOT NULL DEFAULT 0)');
        $this->pdo->exec('CREATE TABLE IF NOT EXISTS wp_alt_digest_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            send_id INTEGER NOT NULL,
            link_hash TEXT NOT NULL,
            url TEXT NOT NULL,
            clicks INTEGER NOT NULL DEFAULT 0,
            UNIQUE (send_id, link_hash))');
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
    public function query($sql) {
        // MySQL's INSERT IGNORE spells the same intent as SQLite's INSERT OR IGNORE.
        $sql = preg_replace('/^\s*INSERT IGNORE\b/i', 'INSERT OR IGNORE', $sql);
        return $this->pdo->exec($sql);
    }
    public function insert($table, $data) {
        $cols = array_keys($data);
        $vals = array_map(function ($v) { return $v === null ? 'NULL' : $this->pdo->quote((string) $v); }, array_values($data));
        $n = $this->pdo->exec("INSERT INTO $table (" . implode(',', $cols) . ') VALUES (' . implode(',', $vals) . ')');
        $this->insert_id = (int) $this->pdo->lastInsertId();
        return $n;
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
// Optional second include: includes/digest-api.php, the external relay's half.
// Loading BOTH in one process is also how a redeclared function would show up
// here as the fatal it is on the live site, rather than passing one file at a
// time. See tests/test_digest_sender.py NoRedeclaredFunction.
if (isset($argv[2]) && $argv[2] !== '') require $argv[2];

/* ------------------------------------------------------------------ */
/* Drive the real functions                                            */
/* ------------------------------------------------------------------ */

function drive($fn) {
    $GLOBALS['__redirect'] = null;
    // AltDie as well as AltRedirect: a handler may END the request with a
    // page instead of a redirect, and the unsubscribe GET now does.
    try { $fn(); } catch (AltRedirect $e) {} catch (AltDie $e) {}
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
$out['confirm_mail_body_new'] = $mails[0]['body'] ?? '';
$out['confirm_mail_has_token'] = strpos($mails[0]['body'] ?? '', $r['confirm_token']) !== false;
$out['confirm_mail_has_email_in_url'] = (bool) preg_match('/https?:\S*reader(%40|@)/', $mails[0]['body'] ?? '');

// 3. DOUBLE OPT-IN: a digest run while pending sends NOTHING.
list($sent, $eligible) = alt_digest_send('weekly');
$out['send_while_pending'] = array($sent, $eligible, count($mails));

// 4. Confirm, then the digest goes out with unsubscribe affordances.
$_REQUEST = array('t' => $r['confirm_token']);
$_SERVER['REQUEST_METHOD'] = 'GET';
$out['confirm_redirect'] = drive('alt_digest_confirm');
// The WHOLE redirect URL, before anything else overwrites it. The receipt
// token rides here, and so would an address if one ever leaked into it.
$out['confirm_redirect_url'] = (string) $GLOBALS['__redirect'];
$out['confirm_receipt'] = preg_match('/alt_r=([a-f0-9]{64})/',
    $out['confirm_redirect_url'], $__rm) ? $__rm[1] : '';
$out['confirm_receipt_store'] = $GLOBALS['__transients']['alt_dg_r_' . $out['confirm_receipt']] ?? null;
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

// 6. Unsubscribe: one press of the button, idempotent, then nothing ever
//    sends again. A POST, because a GET only ASKS since 2026-08-17.
$mail_count_before_unsub = count($mails);
$_REQUEST = array('t' => $r2['unsub_token']);
$_POST = array('alt_unsub_confirm' => '1');
$_SERVER['REQUEST_METHOD'] = 'POST';
$out['unsub1'] = drive('alt_digest_unsubscribe');
$r3 = row('reader@example.com');
$out['status_after_unsub'] = $r3['status'];
$out['unsub2'] = drive('alt_digest_unsubscribe');
$_POST = array();
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
$mails = array();
post_signup('careful@example.com', array('talent'), 'daily');   // "someone" re-submits
$c2 = row('careful@example.com');
$out['prefs_unchanged_until_reconfirm'] = array((int) $c2['consent_layoff'], (int) $c2['consent_talent'], $c2['status']);
// The email that authorises this change. It is the only place the reader is
// ever told that ticking `talent` alone takes `layoff` away.
$change_mail = end($mails);
$out['change_mail_subject'] = $change_mail['subject'] ?? '';
$out['change_mail_body'] = $change_mail['body'] ?? '';
$out['change_mail_count'] = count($mails);
$_REQUEST = array('t' => $c2['confirm_token']);
$out['change_confirm_redirect'] = drive('alt_digest_confirm');
$c3 = row('careful@example.com');
$out['prefs_after_reconfirm'] = array((int) $c3['consent_layoff'], (int) $c3['consent_talent'], $c3['freq_talent'], $c3['status']);

// 10b. The same form used the way a reader who wants to ADD would use it if
//      they had read the warning: every list they want, ticked. Nothing stops,
//      so the email must not manufacture an alarm.
$wpdb->pdo->exec('DELETE FROM wp_alt_subscribers');
$GLOBALS['__transients'] = array();
$mails = array();
post_signup('adder@example.com', array('layoff'));
$a = row('adder@example.com');
$_REQUEST = array('t' => $a['confirm_token']);
drive('alt_digest_confirm');
$GLOBALS['__transients'] = array();
$mails = array();
post_signup('adder@example.com', array('layoff', 'articles'));
$add_mail = end($mails);
$out['add_mail_subject'] = $add_mail['subject'] ?? '';
$out['add_mail_body'] = $add_mail['body'] ?? '';
$a2 = row('adder@example.com');
$_REQUEST = array('t' => $a2['confirm_token']);
drive('alt_digest_confirm');
$a3 = row('adder@example.com');
$out['prefs_after_add'] = array((int) $a3['consent_layoff'], (int) $a3['consent_articles']);

/* ------------------------------------------------------------------ */
/* 11. Send log, aggregate click counting, and the stats payload.       */
/* ------------------------------------------------------------------ */

$wpdb->pdo->exec('DELETE FROM wp_alt_subscribers');
$wpdb->pdo->exec('DELETE FROM wp_alt_digest_sends');
$wpdb->pdo->exec('DELETE FROM wp_alt_digest_links');
$GLOBALS['__transients'] = array();

// A run with nobody eligible must not log a send: "sent to 0" would read as a
// delivery failure when nothing was due.
alt_digest_send('weekly');
$out['sends_logged_when_nobody_eligible'] = (int) $wpdb->get_var('SELECT COUNT(*) FROM wp_alt_digest_sends');

// Two confirmed weekly subscribers, one daily.
$confirm_signup = function ($email, $lists, $freq = 'weekly') {
    $GLOBALS['__transients'] = array();
    post_signup($email, $lists, $freq);
    $r = row($email);
    $_REQUEST = array('t' => $r['confirm_token']);
    $_SERVER['REQUEST_METHOD'] = 'GET';
    drive('alt_digest_confirm');
    return row($email);
};
$confirm_signup('a@example.com', array('layoff'));
$confirm_signup('b@example.com', array('layoff', 'articles'));
$confirm_signup('c@example.com', array('layoff'), 'daily');

$mails_before = count($mails);
list($sent_w, ) = alt_digest_send('weekly');
$digest = end($mails);
$send = $wpdb->get_row('SELECT * FROM wp_alt_digest_sends ORDER BY id DESC LIMIT 1', ARRAY_A);
$out['send_row'] = array((int) $send['recipients'], (int) $send['eligible'], $send['freq']);
$out['send_row_matches_mails'] = ((int) $send['recipients']) === (count($mails) - $mails_before);

$links = $wpdb->get_results('SELECT * FROM wp_alt_digest_links ORDER BY id', ARRAY_A);
$out['links_stored'] = count($links);
// EVERY stored destination, not only the first. The digest linked one thing
// per send until 2026-08-19; it now links every ranked row, and a test that
// reads $links[0] would stop noticing the other twenty.
$out['link_urls'] = array_map(function ($l) { return $l['url']; }, $links);
$out['link_url'] = $links ? $links[0]['url'] : null;
$out['link_starts_at_zero'] = $links && ((int) $links[0]['clicks']) === 0;
// The email carries the first-party counter URL, not the bare destination.
$out['digest_uses_click_url'] = strpos($digest['body'], '/wp-json/layoffs/v1/click') !== false;
$out['digest_html_has_bare_tracker_link'] = (bool) preg_match(
    '/href="https:\/\/example\.test\/blog\/ai-layoff-tracker\/"/', $digest['body']);

// A click: counted once, lands on the stored destination.
$click = function ($s, $l, $ip = '198.51.100.7') {
    $_SERVER['REMOTE_ADDR'] = $ip;
    $req = new WP_REST_Request('GET', '');
    $req->set_param('s', $s);
    $req->set_param('l', $l);
    $GLOBALS['__redirect'] = null;
    try { alt_api_digest_click($req); } catch (AltRedirect $e) {}
    return (string) $GLOBALS['__redirect'];
};
$sid = (int) $links[0]['send_id'];
$hash = $links[0]['link_hash'];
$out['click_redirect'] = $click($sid, $hash);
$out['clicks_after_one'] = (int) $wpdb->get_var(
    'SELECT clicks FROM wp_alt_digest_links WHERE id = ' . (int) $links[0]['id']);

// OPEN REDIRECT: every shape of attempt lands on our own home page and counts
// nothing. There is no parameter that takes a destination, so the only way to
// name one is to guess a hash, and a wrong guess goes home.
$home = 'https://example.test/blog/';
$out['click_unknown_hash'] = $click($sid, str_repeat('a', 32));
$out['click_bad_hash_shape'] = $click($sid, 'https://evil.example/phish');
$out['click_bad_send_id'] = $click(999999, $hash);
$out['click_negative_send'] = $click(-1, $hash);
// Even a hostile row planted directly in the table is refused at redemption:
// the host guard runs again on the way out, not only on the way in.
$evil = 'https://evil.example/phish';
$wpdb->insert('wp_alt_digest_links', array(
    'send_id' => $sid, 'link_hash' => md5($evil), 'url' => $evil, 'clicks' => 0));
$out['click_planted_foreign_host'] = $click($sid, md5($evil));
$out['planted_row_click_count'] = (int) $wpdb->get_var(
    "SELECT clicks FROM wp_alt_digest_links WHERE link_hash = '" . md5($evil) . "'");
$out['home_url'] = $home;

// The guard itself, over the shapes that get used to slip past host checks.
$out['link_allowed'] = array(
    'own_host'      => alt_digest_link_allowed('https://example.test/blog/ai-layoff-tracker/'),
    'www_sibling'   => alt_digest_link_allowed('https://www.example.test/blog/'),
    'foreign'       => alt_digest_link_allowed('https://evil.example/phish'),
    'userinfo'      => alt_digest_link_allowed('https://example.test@evil.example/phish'),
    'prefix_trick'  => alt_digest_link_allowed('https://example.test.evil.example/phish'),
    'protocol_rel'  => alt_digest_link_allowed('//evil.example/phish'),
    'javascript'    => alt_digest_link_allowed('javascript:alert(1)'),
    'data_uri'      => alt_digest_link_allowed('data:text/html,<script>1</script>'),
    'relative'      => alt_digest_link_allowed('/blog/ai-layoff-tracker/'),
    'empty'         => alt_digest_link_allowed(''),
);
// A destination that fails the guard is never wrapped and never stored.
$before_rows = (int) $wpdb->get_var('SELECT COUNT(*) FROM wp_alt_digest_links');
$out['track_link_refuses_foreign'] = alt_digest_track_link($sid, $evil) === $evil;
$out['track_link_stored_nothing'] = ((int) $wpdb->get_var('SELECT COUNT(*) FROM wp_alt_digest_links')) === $before_rows;

// Rate limit: past the ceiling the visit still lands, uncounted.
$GLOBALS['__transients'] = array();
$flood_dest = array();
for ($i = 0; $i < 70; $i++) $flood_dest[] = $click($sid, $hash, '198.51.100.99');
$out['flood_all_landed'] = count(array_unique($flood_dest)) === 1 && $flood_dest[0] === $out['click_redirect'];
$out['clicks_after_flood'] = (int) $wpdb->get_var(
    'SELECT clicks FROM wp_alt_digest_links WHERE id = ' . (int) $links[0]['id']);

// One unsubscribe inside the 48h window after that send.
$_REQUEST = array('t' => row('b@example.com')['unsub_token']);
$_POST = array('alt_unsub_confirm' => '1');
$_SERVER['REQUEST_METHOD'] = 'POST';
drive('alt_digest_unsubscribe');
$_POST = array();

$stats = alt_digest_stats();
$out['stats'] = $stats;
$out['stats_json'] = json_encode($stats);

/* ------------------------------------------------------------------ */
/* 13. The articles list: the third consent box, and its sender.        */
/* ------------------------------------------------------------------ */

$wpdb->pdo->exec('DELETE FROM wp_alt_subscribers');
$wpdb->pdo->exec('DELETE FROM wp_alt_digest_sends');
$wpdb->pdo->exec('DELETE FROM wp_alt_digest_links');
$GLOBALS['__transients'] = array();
$GLOBALS['__posts'] = array();

// THE WINDOW THE WEEKLY TIER REALLY REPORTS, asked for rather than rebuilt:
// alt_digest_send('weekly') below composes on this same window, and a fixture
// that composed on a different one would exercise a section no subscriber
// receives.
list($art_from, $art_to) = alt_digest_window('weekly');

// A real send row, so the composed links go through the counter exactly as
// they do in a live run.
$wpdb->insert('wp_alt_digest_sends', array(
    'freq' => 'weekly', 'sent_at' => gmdate('Y-m-d H:i:s'),
    'recipients' => 0, 'eligible' => 0));
$art_send_id = (int) $wpdb->insert_id;

// An empty window composes NOTHING: not an empty heading, not a filler line.
$out['articles_empty_window_is_null'] = alt_digest_compose_articles($art_from, $art_to, $art_send_id) === null;

// Somebody who ticked ONLY the articles box.
$confirm_signup('reader@example.com', array('articles'));
$before_quiet = count($mails);
list($sent_quiet, ) = alt_digest_send('weekly');
$out['articles_only_mails_with_no_posts'] = count($mails) - $before_quiet;

/*
  DATED FROM THE REPORTED WINDOW, NOT FROM THE CLOCK.

  $age_days counted back from NOW, which worked while the weekly window was a
  rolling seven days ending today: age 2 was always inside it. The weekly tier
  now reports the previous COMPLETE ISO week, so "two days ago" is inside the
  CURRENT week and outside the reported one, and it lands there or not
  depending on which weekday the suite happens to run. A fixture whose meaning
  changes with the day is a fixture that proves nothing on six days out of
  seven.

  So age 1 is the last day of the reported window and every other age counts
  back from there. The relative ordering the assertions rely on is unchanged,
  and the two deliberately-out-of-window posts (40 days, and a draft) stay out.
*/
$mk = function ($id, $title, $slug, $excerpt, $age_days, $extra = array())
        use ($art_to) {
    $anchor = strtotime($art_to . ' 00:00:00 UTC');
    return (object) array_merge(array(
        'ID' => $id, 'post_title' => $title, 'post_name' => $slug,
        'post_excerpt' => $excerpt, 'post_type' => 'post', 'post_status' => 'publish',
        'post_date_gmt' => gmdate('Y-m-d H:i:s',
                                  $anchor - ($age_days - 1) * DAY_IN_SECONDS),
    ), $extra);
};
$GLOBALS['__posts'] = array(
    // The curly quotation marks are the point. get_the_excerpt() returns
    // display HTML, so they arrive as &#8220; / &#8221;, and the first live
    // render published the entity spelling into the PLAIN TEXT part where
    // nothing will ever turn it back into a quotation mark.
    $mk(11, 'What the WARN data actually says', 'warn-data',
        'A standfirst an editor wrote about &#8220;tell me about yourself&#8221;.', 2),
    // No typed excerpt, so the standfirst has to come from the content. Its
    // first sentence is short; the second is there to prove only the first
    // is taken.
    $mk(12, 'Reading an 8-K', 'reading-an-8k', '', 3, array(
        'post_content' => 'An 8-K is the filing a company makes when '
            . 'something material happens. It is the document behind a large '
            . 'share of the entries in this tracker, and it is public.')),
    // A fourth and fifth in-window post, so the section has MORE than it
    // prints and the caption has to say so rather than implying three was all
    // there was.
    $mk(16, 'A fourth post', 'fourth-post', '', 4, array(
        'post_content' => str_repeat('A very long opening clause that never reaches a full stop and just keeps going ', 6))),
    // The oldest in the window, so it is the one the cut to three drops.
    $mk(17, 'A fifth post', 'fifth-post', 'The fifth standfirst.', 5),
    // A tracker surface published as a post is still not an article.
    $mk(13, 'Sources', 'ai-layoff-tracker/sources', '', 1),
    // Outside the window, and a draft: neither may appear.
    $mk(14, 'Last month', 'last-month', '', 40),
    $mk(15, 'Half written', 'half-written', '', 1, array('post_status' => 'draft')),
);

$art = alt_digest_compose_articles($art_from, $art_to, $art_send_id);
$out['articles_section_composed'] = is_array($art)
    && trim((string) $art['html']) !== '' && trim((string) $art['text']) !== '';
$out['articles_html'] = is_array($art) ? $art['html'] : null;
$out['articles_text'] = is_array($art) ? $art['text'] : null;

// The same person, same period, is now a recipient with something to read.
$before_send = count($mails);
list($sent_articles, ) = alt_digest_send('weekly');
$art_mail = end($mails);
$out['articles_only_mails_with_posts'] = count($mails) - $before_send;
$out['articles_mail_body'] = ($sent_articles > 0 && is_array($art_mail)) ? $art_mail['body'] : '';

// And the relay half: the route that hands addresses to the external sender.
if (function_exists('alt_api_digest_recipients')) {
    // Every stamp, because the guard is per tier now (alt_digest_last_sent_column).
    $wpdb->pdo->exec("UPDATE wp_alt_subscribers SET last_sent_at = NULL,
                      last_sent_daily = NULL, last_sent_weekly = NULL");
    $req = new WP_REST_Request('GET', '/layoffs/v1/digest-recipients');
    $req->set_param('freq', 'weekly');
    $res = alt_api_digest_recipients($req);
    $data = $res->get_data();
    $out['relay_sections'] = array_keys((array) ($data['sections'] ?? array()));
    $out['relay_recipient_lists'] = array_map(
        function ($r) { return $r['lists']; }, (array) ($data['recipients'] ?? array()));
    $out['relay_manage_url'] = $data['manage_url'] ?? null;
    // The claim this route stamps must not make the built in sender stand
    // down for the checks that follow.
    unset($GLOBALS['__options']['alt_digest_external_claim']);
}

// 11b. WHAT THE PAGE ACTUALLY RENDERS IN EVERY alt_dg STATE.
//
// The real renderer, not a slice of the file with PHP stripped: the whole
// point of the terminal-state work is which BRANCH runs, and a fixture that
// strips PHP sees both branches or neither. Rendered before the tables are
// dropped below, because a state panel may read a row.
// The receipt PAYLOAD the confirm handler actually wrote, re-seeded under a
// known token. The scenarios above clear $__transients between them, so the
// original token is long gone by here; what is replayed is the handler's own
// data through the real reader, not a payload this fixture invented.
$__receipt = str_repeat('c', 64);
if (is_array($out['confirm_receipt_store'])) {
    set_transient('alt_dg_r_' . $__receipt, $out['confirm_receipt_store'], 1800);
} else {
    $__receipt = '';
}
$out['rendered'] = array();
foreach (array('default', 'check', 'confirmed', 'updated', 'unsubscribed',
               'expired', 'lists', 'email') as $__state) {
    $_GET = array();
    $_SERVER['REQUEST_URI'] = '/blog/ai-layoff-tracker/'
        . ($__state === 'default' ? '' : '?alt_dg=' . $__state);
    if ($__state !== 'default') $_GET['alt_dg'] = $__state;
    // Only the two states the handler actually issues a receipt for.
    if (($__state === 'confirmed' || $__state === 'updated') && $__receipt !== '') {
        $_GET['alt_r'] = $__receipt;
    }
    $out['rendered'][$__state] = alt_digest_subscribe_form('layoff');
}
// And the confirmed state with the receipt gone, which is what a reader who
// comes back to the URL half an hour later gets.
$_GET = array('alt_dg' => 'confirmed', 'alt_r' => str_repeat('a', 64));
$out['rendered']['confirmed_no_receipt'] = alt_digest_subscribe_form('layoff');
$_GET = array();

/* ------------------------------------------------------------------ */
/* 14. THE TWO LINKS INSIDE AN EMAIL: the public route AND the legacy   */
/*     admin-post.php one, driven as a real request each time.          */
/* ------------------------------------------------------------------ */

$wpdb->pdo->exec('DELETE FROM wp_alt_subscribers');
$GLOBALS['__transients'] = array();
$routes = array();

/**
 * One request at a URL, through the front-end dispatcher rather than by
 * calling the handler directly. This is the whole point: a link in an inbox is
 * a URL, and what has to be proved is that the URL arrives somewhere.
 */
$request = function ($url, $method = 'GET', $post = array(), $referer = '') {
    $_GET = array(); $_POST = $post; $_REQUEST = $post;
    // A browser posting a form sends the page it was on. That page is what
    // makes the unsubscribe redirect interesting, so it is not optional here.
    if ($referer !== '') $_SERVER['HTTP_REFERER'] = $referer;
    else unset($_SERVER['HTTP_REFERER']);
    $parts = parse_url($url);
    $_SERVER['REQUEST_URI'] = $parts['path'] . (isset($parts['query']) ? '?' . $parts['query'] : '');
    $_SERVER['REQUEST_METHOD'] = $method;
    if (isset($parts['query'])) {
        parse_str($parts['query'], $q);
        $_GET = $q;
        $_REQUEST = array_merge($q, $_REQUEST);
    }
    $GLOBALS['__redirect'] = null;
    $result = array('code' => 0, 'redirected' => false, 'state' => '',
                    'body' => '', 'to' => '');
    try {
        // admin-post.php URLs never reach the front-end dispatcher; WordPress
        // fires the admin_post_* action for them. Both are exercised here the
        // way the live install would reach them.
        if (strpos($_SERVER['REQUEST_URI'], 'admin-post.php') !== false) {
            $action = $_REQUEST['action'] ?? '';
            if ($action === 'alt_digest_confirm') alt_digest_confirm();
            elseif ($action === 'alt_digest_unsub') alt_digest_unsubscribe();
        } else {
            alt_digest_public_route_dispatch();
        }
    } catch (AltRedirect $e) {
        $result['redirected'] = true;
        $result['code'] = 302;
        $result['to'] = (string) $e->getMessage();
        $result['state'] = preg_match('/alt_dg=([a-z]+)/', (string) $e->getMessage(), $m) ? $m[1] : '';
    } catch (AltDie $e) {
        $result['code'] = (int) $e->getCode();
        $result['body'] = $e->body;
    }
    return $result;
};

$seed_pending = function ($email) use ($wpdb) {
    $GLOBALS['__transients'] = array();
    $wpdb->pdo->exec('DELETE FROM wp_alt_subscribers WHERE email = ' . $wpdb->pdo->quote($email));
    post_signup($email, array('layoff'));
    return row($email);
};

// The shapes themselves, read from the shipped builders.
$probe = str_repeat('b', 64);
$routes['confirm_url'] = alt_digest_confirm_url($probe);
$routes['unsub_url'] = alt_digest_unsub_url($probe);
$routes['legacy_confirm_url'] = alt_digest_legacy_confirm_url($probe);
$routes['legacy_unsub_url'] = alt_digest_legacy_unsub_url($probe);

// (a) The NEW public path confirms.
$p = $seed_pending('newroute@example.com');
$r = $request(alt_digest_confirm_url($p['confirm_token']));
$routes['public_confirm_result'] = $r['state'];
$routes['public_confirm_status'] = row('newroute@example.com')['status'];
// And the same link a second time is the polite "already used", not an error.
$routes['public_confirm_reuse_result'] = $request(alt_digest_confirm_url($p['confirm_token']))['state'];
// A truncated link with no token at all still reaches the message.
$routes['confirm_without_token_result'] = $request('https://example.test/blog/ai-layoff-tracker/confirm/')['state'];

// (b) The LEGACY admin-post.php path confirms. Same handler, same outcome.
$p = $seed_pending('oldroute@example.com');
$r = $request(alt_digest_legacy_confirm_url($p['confirm_token']));
$routes['legacy_confirm_result'] = $r['state'];
$routes['legacy_confirm_status'] = row('oldroute@example.com')['status'];

// (c) Unsubscribe: public path, by GET. IT MUST NOT UNSUBSCRIBE. A scanner
//     fetching links in a delivered message is the caller this separates out.
$p = $seed_pending('unsubget@example.com');
$r = $request(alt_digest_unsub_url($p['unsub_token']));
$routes['public_unsub_get_code'] = $r['code'];
$routes['public_unsub_get_body'] = $r['body'];
$routes['public_unsub_get_result'] = $r['state'];
$routes['public_unsub_get_status'] = row('unsubget@example.com')['status'];
// And the button on that page, posted the way a browser would post it.
$routes['public_unsub_button_status'] = 'NOT ATTEMPTED';
if (preg_match('/<form[^>]*action="([^"]+)"/', (string) $r['body'], $fm)) {
    $routes['public_unsub_form_action'] = $fm[1];
    $routes['public_unsub_form_is_post'] = (bool) preg_match('/<form[^>]*method="post"/i', (string) $r['body']);
    // The referer a browser sends here is the confirmation page itself, whose
    // URL is the unsubscribe route.
    $posted = $request($fm[1], 'POST', array(
        'action' => 'alt_digest_unsub', 't' => $p['unsub_token'],
        'alt_unsub_confirm' => '1'), alt_digest_unsub_url($p['unsub_token']));
    $routes['public_unsub_button_state'] = $posted['state'];
    $routes['public_unsub_button_to'] = $posted['to'];
    $routes['public_unsub_button_status'] = row('unsubget@example.com')['status'];
}
// A GET on a row that is ALREADY unsubscribed says so rather than asking again.
$routes['public_unsub_get_again_state'] =
    $request(alt_digest_unsub_url($p['unsub_token']))['state'];

// (d) Unsubscribe: public path, by the RFC 8058 one-click POST.
$p = $seed_pending('unsubpost@example.com');
$r = $request(alt_digest_unsub_url($p['unsub_token']), 'POST',
              array('List-Unsubscribe' => 'One-Click'));
$routes['public_unsub_post_code'] = $r['code'];
$routes['public_unsub_post_redirected'] = $r['redirected'];
$routes['public_unsub_post_status'] = row('unsubpost@example.com')['status'];

// (e) Unsubscribe: LEGACY path, by POST. This is the URL sitting in the
//     List-Unsubscribe header of every digest already delivered.
$p = $seed_pending('unsuboldpost@example.com');
$r = $request(alt_digest_legacy_unsub_url($p['unsub_token']), 'POST',
              array('List-Unsubscribe' => 'One-Click'));
$routes['legacy_unsub_post_code'] = $r['code'];
$routes['legacy_unsub_post_status'] = row('unsuboldpost@example.com')['status'];

// (f) And the legacy GET, which must not unsubscribe either. That URL is in
//     the List-Unsubscribe header of every digest already delivered.
$p = $seed_pending('unsuboldget@example.com');
$r = $request(alt_digest_legacy_unsub_url($p['unsub_token']));
$routes['legacy_unsub_get_code'] = $r['code'];
$routes['legacy_unsub_get_body'] = $r['body'];
$routes['legacy_unsub_result'] = $r['state'];
$routes['legacy_unsub_status'] = row('unsuboldget@example.com')['status'];

// (f2) A GET carrying the human marker in its QUERY STRING must still not
//      write anything. The marker is read from $_POST alone for this reason.
$p = $seed_pending('unsubforge@example.com');
$request(alt_digest_unsub_url($p['unsub_token']) . '?alt_unsub_confirm=1');
$routes['forged_marker_get_status'] = row('unsubforge@example.com')['status'];

// (f3) A GET on a token nobody holds reads the way it always has.
$routes['unknown_token_get_state'] =
    $request(alt_digest_unsub_url(str_repeat('e', 64)))['state'];

// (g) A token the purge already deleted, POSTed by a provider. Nothing to do,
//     and saying so with a 4xx would be recorded against the sending domain.
$r = $request(alt_digest_unsub_url(str_repeat('f', 64)), 'POST',
              array('List-Unsubscribe' => 'One-Click'));
$routes['post_unknown_token_code'] = $r['code'];
$routes['post_unknown_token_redirected'] = $r['redirected'];

// (h) The From: identity, taken off a real confirmation and a real digest.
$GLOBALS['__transients'] = array();
$wpdb->pdo->exec('DELETE FROM wp_alt_subscribers');
$before = count($mails);
post_signup('fromline@example.com', array('layoff'));
$confirm_mail = end($mails);
$routes['confirm_mail_headers'] = $confirm_mail['headers'];
$routes['confirm_mail_body'] = $confirm_mail['body'];
$routes['confirm_mail_unsub_token'] = row('fromline@example.com')['unsub_token'];
$from_of = function ($headers) {
    foreach ((array) $headers as $h) {
        if (stripos($h, 'from:') === 0) return $h;
    }
    return '';
};
$routes['confirm_from_line'] = $from_of($confirm_mail['headers']);
$fr = row('fromline@example.com');
$_REQUEST = array('t' => $fr['confirm_token']);
$_SERVER['REQUEST_METHOD'] = 'GET';
drive('alt_digest_confirm');
alt_digest_send('weekly');
$routes['digest_from_line'] = $from_of(end($mails)['headers']);

$out['routes'] = $routes;
$_GET = array(); $_POST = array(); $_REQUEST = array();

/* ------------------------------------------------------------------ */
/* 15. MONDAY: BOTH TIERS RUN, AND NEITHER PASS CONSUMES THE OTHER.     */
/*                                                                      */
/* THE DEFECT, 2026-08-17. The relay picked ONE tier per run and picked  */
/* weekly on a Monday, so every daily subscriber got nothing on a        */
/* Monday. Fixing that alone was not enough: last_sent_at was a single   */
/* column shared by both tiers, so whichever pass ran first stamped it   */
/* and the second pass found the same person "already sent to". The      */
/* guard is per tier now, and this drives both passes to prove it.       */
/* ------------------------------------------------------------------ */

$wpdb->pdo->exec('DELETE FROM wp_alt_subscribers');
$wpdb->pdo->exec('DELETE FROM wp_alt_digest_sends');
$wpdb->pdo->exec('DELETE FROM wp_alt_digest_links');
unset($GLOBALS['__options']['alt_digest_external_claim']);
$monday = array();

/*
  ONE POST IN EACH WINDOW, WHICH IS TWO POSTS NOW AND USED TO BE ONE.

  This carried a single post dated an hour ago, and the comment claimed it was
  inside both windows. That was true while the weekly window was a rolling
  seven days ENDING TODAY. It stopped being true on 2026-08-19, when the weekly
  tier moved to the previous COMPLETE ISO week: a post from today is in this
  week, and this week is not what a weekly edition reports.

  It is not a fixture bug, it is the change itself, and the weekly half of the
  both-tiers subscriber going silent is exactly the symptom a reader would
  have. So the fixture holds one post in each window and the assertion stands
  unchanged.
*/
// The previous complete ISO week, computed here rather than borrowed from
// alt_digest_weekly_window(): this line runs before subscribe.php is loaded,
// and a fixture that cannot build its own dates is a fixture that skips.
$__monday_this_week = strtotime(gmdate('Y-m-d') . ' 00:00:00 UTC')
                    - ((int) gmdate('N') - 1) * 86400;
$__weekly_window = array(gmdate('Y-m-d', $__monday_this_week - 7 * 86400));
$GLOBALS['__posts'] = array(
    (object) array('ID' => 91, 'post_title' => 'A post from today',
                   'post_name' => 'today-post', 'post_excerpt' => 'A standfirst.',
                   'post_type' => 'post', 'post_status' => 'publish',
                   'post_date_gmt' => gmdate('Y-m-d H:i:s', time() - 3600)),
    (object) array('ID' => 92, 'post_title' => 'A post from the reported week',
                   'post_name' => 'last-week-post', 'post_excerpt' => 'A standfirst.',
                   'post_type' => 'post', 'post_status' => 'publish',
                   'post_date_gmt' => $__weekly_window[0] . ' 09:00:00'),
);

$confirm_signup('daily-only@example.com', array('layoff'), 'daily');
$confirm_signup('weekly-only@example.com', array('layoff'), 'weekly');
// One person taking BOTH tiers, by their own two choices: the layoff box
// daily and the articles box weekly. The form carries one frequency, so the
// second is set the way a later preferences change leaves it.
$confirm_signup('both-tiers@example.com', array('layoff', 'articles'), 'daily');
$wpdb->pdo->exec("UPDATE wp_alt_subscribers SET freq_articles = 'weekly'
                  WHERE email = 'both-tiers@example.com'");

/*
  DIGESTS ONLY. Each of the three signups above sent one confirmation email to
  the same address, and counting from zero would score that as a digest and
  make every number here one too high.
*/
$count_all = function ($address) use (&$mails) {
    $n = 0;
    foreach ($mails as $m) { if (($m['to'] ?? '') === $address) $n++; }
    return $n;
};
$baseline = array();
foreach (array('daily-only@example.com', 'weekly-only@example.com',
               'both-tiers@example.com') as $__a) {
    $baseline[$__a] = $count_all($__a);
}
$mails_to = function ($address) use ($count_all, $baseline) {
    return $count_all($address) - (int) ($baseline[$address] ?? 0);
};

// Pass one: the daily tier, which is every day including Monday. On any other
// day of the week this is the whole run.
alt_digest_send('daily');
$monday['after_daily_pass'] = array(
    'daily_only'  => $mails_to('daily-only@example.com'),
    'weekly_only' => $mails_to('weekly-only@example.com'),
    'both_tiers'  => $mails_to('both-tiers@example.com'),
);

// Pass two: the weekly tier, which runs ADDITIONALLY on a Monday.
alt_digest_send('weekly');
$monday['after_weekly_pass'] = array(
    'daily_only'  => $mails_to('daily-only@example.com'),
    'weekly_only' => $mails_to('weekly-only@example.com'),
    'both_tiers'  => $mails_to('both-tiers@example.com'),
);

// Each tier has its own send row. One row for two tiers would report half.
$monday['send_row_freqs'] = array_map(
    function ($r) { return $r['freq']; },
    (array) $wpdb->get_results('SELECT freq FROM wp_alt_digest_sends ORDER BY id', ARRAY_A));

// And the same day again changes nothing: the per tier guard holds inside the
// period, so a re-run cannot put a second copy in anybody's inbox.
alt_digest_send('daily');
alt_digest_send('weekly');
$monday['after_a_rerun'] = array(
    'daily_only'  => $mails_to('daily-only@example.com'),
    'weekly_only' => $mails_to('weekly-only@example.com'),
    'both_tiers'  => $mails_to('both-tiers@example.com'),
);

/* The RELAY path, which is what actually sends today. Same two passes, driven
   through the two keyed routes the GitHub Action calls. */
if (function_exists('alt_api_digest_recipients') && function_exists('alt_api_digest_complete')) {
    $wpdb->pdo->exec('UPDATE wp_alt_subscribers
                      SET last_sent_at = NULL, last_sent_daily = NULL,
                          last_sent_weekly = NULL');
    unset($GLOBALS['__options']['alt_digest_external_claim']);

    $ask = function ($freq) {
        $req = new WP_REST_Request('GET', '/layoffs/v1/digest-recipients');
        $req->set_param('freq', $freq);
        return (array) alt_api_digest_recipients($req)->get_data();
    };
    $addresses = function ($data) {
        return array_map(function ($r) { return $r['email']; },
                         (array) ($data['recipients'] ?? array()));
    };
    $complete = function ($data, $freq) {
        $req = new WP_REST_Request('POST', '/layoffs/v1/digest-complete');
        $req->set_json_params(array(
            'send_id' => (int) ($data['send_id'] ?? 0),
            'freq' => $freq,
            'eligible' => count((array) ($data['recipients'] ?? array())),
            'sent_ids' => array_map(function ($r) { return (int) $r['id']; },
                                    (array) ($data['recipients'] ?? array())),
            'failed' => 0, 'transport' => 'fake',
        ));
        return alt_api_digest_complete($req)->get_data();
    };

    $daily_data = $ask('daily');
    $monday['relay_daily_recipients'] = $addresses($daily_data);
    $complete($daily_data, 'daily');
    // THE ONE THAT MATTERED. The daily pass has just stamped everyone it
    // mailed. The weekly pass must still see its own subscribers, including
    // the person who takes both.
    $weekly_data = $ask('weekly');
    $monday['relay_weekly_recipients'] = $addresses($weekly_data);
    $complete($weekly_data, 'weekly');

    // Neither pass consumed the other's lease.
    $monday['claims_after_both'] = array(
        'daily'  => alt_digest_external_active('daily'),
        'weekly' => alt_digest_external_active('weekly'),
    );
    // And a second ask inside the same period returns nobody, for either tier.
    $monday['relay_daily_rerun'] = $addresses($ask('daily'));
    $monday['relay_weekly_rerun'] = $addresses($ask('weekly'));
    unset($GLOBALS['__options']['alt_digest_external_claim']);
}
$out['monday'] = $monday;
$GLOBALS['__posts'] = array();

// 12. No table, no numbers: UNKNOWN, never a zero.
$wpdb->pdo->exec('DROP TABLE wp_alt_subscribers');
$out['stats_without_table'] = alt_digest_stats();
$wpdb->pdo->exec('DROP TABLE wp_alt_digest_sends');
$wpdb->pdo->exec('DROP TABLE wp_alt_digest_links');
// A send with no tables must not fatal, and must log nothing.
$out['send_without_tables'] = alt_digest_send('weekly');

echo json_encode($out), "\n";
