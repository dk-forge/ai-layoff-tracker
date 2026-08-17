<?php
/**
 * Test harness for includes/blog-claps.php: WordPress stubs plus a SQLite
 * backed $wpdb, driving the REAL functions end to end. Same shape as
 * fixtures/digest_harness.php, with one difference that matters: the database
 * is a FILE, not :memory:, because the headline claim about this feature is
 * that two simultaneous taps do not lose a count, and you cannot demonstrate
 * that inside one process holding a private in-memory database.
 *
 *   argv[1]  absolute path to includes/blog-claps.php
 *   argv[2]  absolute path to the SQLite file
 *   argv[3]  mode, see the switch at the bottom
 *   argv[4+] mode arguments
 *
 * Every mode prints one JSON object.
 */

error_reporting(E_ALL & ~E_DEPRECATED);

define('ABSPATH', '/tmp/');
define('MINUTE_IN_SECONDS', 60);
define('HOUR_IN_SECONDS', 3600);
define('DAY_IN_SECONDS', 86400);
define('OBJECT', 'OBJECT');
define('ARRAY_A', 'ARRAY_A');

$GLOBALS['__transients'] = array();
$GLOBALS['__queries'] = array();
$GLOBALS['__routes'] = array();
$GLOBALS['__filters'] = array();
$GLOBALS['__actions'] = array();
$GLOBALS['__enqueued'] = array();
$GLOBALS['__inline'] = array();
$GLOBALS['__posts'] = array();

function add_action($tag, $fn, $prio = 10, $args = 1) { $GLOBALS['__actions'][] = array($tag, $fn, $prio); }
function add_filter($tag, $fn, $prio = 10, $args = 1) { $GLOBALS['__filters'][] = array($tag, $fn, $prio); }
function register_rest_route($ns, $route, $args) { $GLOBALS['__routes'][] = array($ns, $route, $args); }
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function number_format_i18n($n) { return number_format((float) $n); }
function wp_json_encode($d) { return json_encode($d); }
function home_url($p = '') { return 'https://example.test/blog' . $p; }
function rest_url($path = '') { return 'https://example.test/blog/wp-json/' . ltrim($path, '/'); }
/**
 * The transient store keeps the TTL alongside the value so a test can assert
 * the throttle key EXPIRES rather than persisting. get_transient must still
 * return the bare value: returning the wrapper made `(int) get_transient(...)`
 * evaluate to 1 forever, which silently disabled the throttle inside the
 * harness and only inside it. That is the shape of harness defect that reads as
 * a passing feature, so the unwrap lives here and the tests read
 * $GLOBALS['__transients'] directly when they want the TTL.
 */
function get_transient($k) {
    if (!array_key_exists($k, $GLOBALS['__transients'])) return false;
    return $GLOBALS['__transients'][$k]['value'];
}
function set_transient($k, $v, $ttl = 0) { $GLOBALS['__transients'][$k] = array('value' => $v, 'ttl' => $ttl); return true; }
function is_admin() { return false; }
function is_feed() { return false; }
function is_embed() { return false; }
function doing_filter($f) { return false; }
function is_singular($t = '') { return true; }
function in_the_loop() { return true; }
function is_main_query() { return true; }
function get_the_ID() { return (int) ($GLOBALS['__current_post'] ?? 0); }
function wp_enqueue_style(...$a) { $GLOBALS['__enqueued'][] = array('style', $a[0], $a[1] ?? '', $a[3] ?? ''); }
function wp_enqueue_script(...$a) { $GLOBALS['__enqueued'][] = array('script', $a[0], $a[1] ?? '', $a[3] ?? ''); }
function wp_add_inline_script($h, $code, $pos = 'after') { $GLOBALS['__inline'][] = array($h, $code, $pos); }

/**
 * get_transient returns the stored value. The harness keeps the TTL alongside
 * it so a test can assert the throttle key expires rather than persisting, so
 * unwrap here and let the test read $GLOBALS['__transients'] directly.
 */
function alt_harness_transient_value($k) {
    $raw = $GLOBALS['__transients'][$k] ?? false;
    return is_array($raw) && array_key_exists('value', $raw) ? $raw['value'] : $raw;
}

class WP_Error {
    public $code; public $message; public $data;
    public function __construct($code = '', $message = '', $data = array()) {
        $this->code = $code; $this->message = $message; $this->data = $data;
    }
    public function get_error_code() { return $this->code; }
    public function get_error_message() { return $this->message; }
}

class WP_REST_Response {
    public $data; public $status; public $headers = array();
    public function __construct($data = null, $status = 200) { $this->data = $data; $this->status = $status; }
    public function header($k, $v) { $this->headers[$k] = $v; }
    public function get_data() { return $this->data; }
    public function get_status() { return $this->status; }
}

class WP_REST_Request {
    public $params = array();
    public function __construct($params = array()) { $this->params = $params; }
    public function get_param($k) { return $this->params[$k] ?? null; }
    public function set_param($k, $v) { $this->params[$k] = $v; }
}

/** The site's posts, as a test sets them up. */
function get_post($id) {
    $id = (int) $id;
    return $GLOBALS['__posts'][$id] ?? null;
}

function alt_harness_add_post($id, $type = 'post', $status = 'publish', $password = '') {
    $p = new stdClass();
    $p->ID = (int) $id;
    $p->post_type = $type;
    $p->post_status = $status;
    $p->post_password = $password;
    $GLOBALS['__posts'][(int) $id] = $p;
}

/**
 * dbDelta, translated for SQLite. The DDL under test is MySQL, so strip what
 * SQLite does not spell: UNSIGNED, and the charset/collate tail after the
 * closing paren. Nothing else is rewritten, so the column list the test reads
 * back out of the database is the column list the plugin actually declares.
 */
function dbDelta($sql) {
    global $wpdb;
    $sql = preg_replace('/\bUNSIGNED\b/i', '', $sql);
    $sql = preg_replace('/\)\s*[^)]*$/', ')', trim(rtrim(trim($sql), ';')));
    $sql = preg_replace('/^CREATE TABLE\b/i', 'CREATE TABLE IF NOT EXISTS', $sql);
    $wpdb->pdo->exec($sql);
    return array();
}

/** SQLite-backed wpdb double over a FILE, so several processes share one row. */
class FakeWpdb {
    public $prefix = 'wp_';
    public $pdo;
    public function __construct($path) {
        $this->pdo = new PDO('sqlite:' . $path);
        $this->pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        // Without a busy timeout a concurrent writer gets SQLITE_BUSY and the
        // test would measure the harness rather than the statement.
        $this->pdo->exec('PRAGMA busy_timeout = 20000');
        $this->pdo->exec('PRAGMA journal_mode = WAL');
    }
    public function get_charset_collate() { return 'DEFAULT CHARACTER SET utf8mb4'; }
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
        $GLOBALS['__queries'][] = $sql;
        if (preg_match("/SHOW TABLES LIKE '(.+)'/", $sql, $m)) {
            $st = $this->pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name=" . $this->pdo->quote($m[1]));
            $r = $st->fetchColumn();
            return $r === false ? null : $r;
        }
        $r = $this->pdo->query($sql)->fetchColumn();
        return $r === false ? null : $r;
    }
    public function get_row($sql, $output = OBJECT) {
        $GLOBALS['__queries'][] = $sql;
        $r = $this->pdo->query($sql)->fetch(PDO::FETCH_ASSOC);
        if (!$r) return null;
        return $output === ARRAY_A ? $r : (object) $r;
    }
    public function get_results($sql, $output = OBJECT) {
        $GLOBALS['__queries'][] = $sql;
        $rows = $this->pdo->query($sql)->fetchAll(PDO::FETCH_ASSOC);
        if ($output === ARRAY_A) return $rows;
        return array_map(function ($r) { return (object) $r; }, $rows);
    }
    public function query($sql) {
        $GLOBALS['__queries'][] = $sql;
        // MySQL's INSERT IGNORE spells the same intent as SQLite's INSERT OR IGNORE.
        $sql = preg_replace('/^\s*INSERT IGNORE\b/i', 'INSERT OR IGNORE', $sql);
        return $this->pdo->exec($sql);
    }
}

$CLAPS = $argv[1];
$DBFILE = $argv[2];
$MODE = $argv[3] ?? 'observe';

$wpdb = new FakeWpdb($DBFILE);
$GLOBALS['wpdb'] = $wpdb;

require_once $CLAPS;

function out($d) { echo json_encode($d), "\n"; }

/**
 * THE CONTROL. This is the same increment written the wrong way: read the count
 * into PHP, add, write it back. It exists so the concurrency test can prove it
 * is capable of catching a lost update, rather than passing because sixteen
 * processes happened to take turns. The sleep makes the window deterministic
 * instead of leaving it to the scheduler.
 */
function alt_claps_add_read_modify_write($post_id, $amount) {
    global $wpdb;
    $table = alt_claps_table();
    $wpdb->query($wpdb->prepare(
        'INSERT IGNORE INTO ' . $table . ' (post_id, claps) VALUES (%d, 0)', (int) $post_id));
    $current = (int) $wpdb->get_var($wpdb->prepare(
        'SELECT claps FROM ' . $table . ' WHERE post_id = %d', (int) $post_id));
    usleep(2000);
    $wpdb->query($wpdb->prepare(
        'UPDATE ' . $table . ' SET claps = %d WHERE post_id = %d',
        $current + (int) $amount, (int) $post_id));
    return $current + (int) $amount;
}

switch ($MODE) {

case 'install':
    alt_claps_install();
    $cols = $wpdb->pdo->query('PRAGMA table_info(' . alt_claps_table() . ')')->fetchAll(PDO::FETCH_ASSOC);
    out(array('table' => alt_claps_table(), 'columns' => $cols));
    break;

// bump <post_id> <times> <amount>: the REAL function, one process.
case 'bump':
    alt_harness_add_post((int) $argv[4]);
    $times = (int) $argv[5];
    $amount = (int) ($argv[6] ?? 1);
    $last = 0;
    for ($i = 0; $i < $times; $i++) $last = alt_claps_add((int) $argv[4], $amount);
    out(array('last' => $last));
    break;

// rmw <post_id> <times>: the read-modify-write control, one process.
case 'rmw':
    $times = (int) $argv[5];
    for ($i = 0; $i < $times; $i++) alt_claps_add_read_modify_write((int) $argv[4], 1);
    out(array('done' => $times));
    break;

case 'total':
    out(array('claps' => alt_claps_count((int) $argv[4])));
    break;

// batch <id,id,id>: run the set helper and report how many statements it took.
case 'batch':
    $ids = array_map('intval', explode(',', (string) $argv[4]));
    alt_claps_table_ready();               // warm the readiness check first
    $GLOBALS['__queries'] = array();
    $counts = alt_claps_counts($ids);
    out(array('counts' => $counts, 'queries' => $GLOBALS['__queries']));
    break;

// endpoint <post_id> <n>: drive the REAL REST callback.
case 'endpoint':
    // A post of every shape a caller might aim at.
    alt_harness_add_post(101, 'post', 'publish');
    alt_harness_add_post(102, 'post', 'draft');
    alt_harness_add_post(103, 'post', 'private');
    alt_harness_add_post(104, 'page', 'publish');
    alt_harness_add_post(105, 'layoffs', 'publish');
    alt_harness_add_post(106, 'attachment', 'publish');
    alt_harness_add_post(107, 'post', 'publish', 'hunter2');
    $_SERVER['REMOTE_ADDR'] = $argv[6] ?? '203.0.113.9';
    $_SERVER['HTTP_USER_AGENT'] = 'HarnessAgent/9.9';
    $req = new WP_REST_Request(array('id' => (int) $argv[4], 'n' => (int) ($argv[5] ?? 1)));
    $res = alt_api_clap($req);
    if ($res instanceof WP_Error) {
        out(array('error' => $res->get_error_code(), 'message' => $res->get_error_message(),
                  'status' => (int) ($res->data['status'] ?? 0),
                  'rows' => $wpdb->pdo->query('SELECT * FROM ' . alt_claps_table())->fetchAll(PDO::FETCH_ASSOC)));
    } else {
        out(array('data' => $res->get_data(), 'status' => $res->get_status(),
                  'headers' => $res->headers,
                  'transients' => $GLOBALS['__transients'],
                  'rows' => $wpdb->pdo->query('SELECT * FROM ' . alt_claps_table())->fetchAll(PDO::FETCH_ASSOC)));
    }
    break;

// throttle <post_id> <calls>: hammer one address and report what stuck.
case 'throttle':
    alt_harness_add_post(101, 'post', 'publish');
    $_SERVER['REMOTE_ADDR'] = '198.51.100.4';
    $calls = (int) $argv[5];
    $counted = 0;
    for ($i = 0; $i < $calls; $i++) {
        $res = alt_api_clap(new WP_REST_Request(array('id' => (int) $argv[4], 'n' => 1)));
        if (!($res instanceof WP_Error) && !empty($res->get_data()['counted'])) $counted++;
    }
    out(array('counted' => $counted,
              'claps' => alt_claps_count((int) $argv[4]),
              'transients' => $GLOBALS['__transients']));
    break;

// phrase <count> [placeholder]: the count sentence, straight from the shipped
// function. The wording has ONE definition and the test compares the markup's
// templates against it rather than against a copy written in Python.
case 'phrase':
    $ph = isset($argv[5]) && $argv[5] !== '' ? $argv[5] : null;
    out(array('phrase' => alt_claps_count_phrase((int) $argv[4], $ph)));
    break;

// render <post_id>: the markup, plus the whole database afterwards.
case 'render':
    alt_harness_add_post(101, 'post', 'publish');
    alt_harness_add_post(102, 'post', 'draft');
    $_SERVER['REMOTE_ADDR'] = '198.51.100.77';
    $_SERVER['HTTP_USER_AGENT'] = 'RenderAgent/1.2';
    $html = alt_claps_render((int) $argv[4]);
    $tables = $wpdb->pdo->query("SELECT name FROM sqlite_master WHERE type='table'")->fetchAll(PDO::FETCH_COLUMN);
    $dump = array();
    foreach ($tables as $t) {
        if (strpos($t, 'sqlite_') === 0) continue;
        $dump[$t] = $wpdb->pdo->query('SELECT * FROM "' . $t . '"')->fetchAll(PDO::FETCH_ASSOC);
    }
    out(array('html' => $html, 'dump' => $dump));
    break;

case 'routes':
    // add_action only RECORDS here, so fire rest_api_init the way WordPress
    // would. Without this the route list is empty and the test that counts the
    // public write endpoints passes by measuring nothing.
    foreach ($GLOBALS['__actions'] as $a) {
        if ($a[0] === 'rest_api_init' && is_callable($a[1])) call_user_func($a[1]);
    }
    out(array('routes' => array_map(function ($r) {
        return array('ns' => $r[0], 'route' => $r[1],
                     'methods' => $r[2]['methods'] ?? '',
                     'callback' => $r[2]['callback'] ?? '',
                     'permission' => is_string($r[2]['permission_callback'] ?? '')
                        ? $r[2]['permission_callback'] : 'closure');
    }, $GLOBALS['__routes']),
    'filters' => $GLOBALS['__filters'],
    'actions' => $GLOBALS['__actions']));
    break;

default:
    out(array('error' => 'unknown mode ' . $MODE));
}
