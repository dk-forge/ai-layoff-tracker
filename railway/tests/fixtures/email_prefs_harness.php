<?php
/**
 * Drives includes/subscriber-prefs.php (welcome email, preferences page,
 * per-follow stop, fallback plain text) through the REAL subscribe/confirm
 * handlers. digest_harness.php supplies WordPress stubs and a SQLite $wpdb.
 * Brevo's HTTP API is a recording fake. Prints one JSON object.
 *
 * argv[1] subscribe.php, argv[2] digest-api.php, argv[3] follows.php,
 * argv[4] subscriber-prefs.php. Synthetic addresses only (example.com).
 */
define('ALT_HARNESS_STUBS_ONLY', true);
define('ALT_VERSION', 'test');
$GLOBALS['__http'] = array();
$GLOBALS['__brevo_key'] = '';
$GLOBALS['__actions'] = array();

class WP_Error {}
function is_wp_error($x) { return $x instanceof WP_Error; }
function wp_remote_request($url, $args) {
    $GLOBALS['__http'][] = array('url' => $url, 'method' => $args['method'],
        'headers' => $args['headers'], 'body' => json_decode($args['body'], true));
    return array('code' => 201);
}
function wp_remote_retrieve_response_code($r) { return $r['code']; }
function wp_salt($s = '') { return 'test-salt-not-a-secret'; }
function do_action($tag, ...$a) { if ($tag === 'alt_digest_confirmed') alt_follows_activate(...$a); }
function remove_action(...$a) {}
function alt_brevo_api_key() { return $GLOBALS['__brevo_key']; }
function alt_db_table() { return 'wp_alt_layoffs'; }

$files = $argv;
require __DIR__ . '/digest_harness.php';
require $files[3];
require $files[4];

global $wpdb;
$wpdb->pdo->exec('CREATE TABLE wp_alt_follows (id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscriber_id INTEGER NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT "", url TEXT NOT NULL DEFAULT "",
    status TEXT NOT NULL DEFAULT "pending", created_at TEXT NOT NULL, activated_at TEXT NULL,
    UNIQUE (subscriber_id, kind, value))');
$wpdb->pdo->exec('CREATE TABLE wp_alt_layoffs (id INTEGER PRIMARY KEY, company TEXT, job_count INTEGER,
    announcement_date TEXT, layoff_date TEXT, state TEXT, country TEXT, company_key TEXT,
    superset_of INTEGER DEFAULT 0, updated_at TEXT)');
$GLOBALS['__options']['alt_follows_db_version'] = 'test';

/** Run a handler that ends the request; return what the reader would see. */
function page($fn) {
    $GLOBALS['__redirect'] = null;
    try { $fn(); } catch (AltDie $e) { return array('die' => $e->body, 'redirect' => null); }
    catch (AltRedirect $e) { return array('die' => null, 'redirect' => $GLOBALS['__redirect']); }
    return array('die' => null, 'redirect' => null);
}
function sub($email, $lists, $freq = 'weekly') {
    $GLOBALS['__transients'] = array();
    $_POST = array('alt_digest_nonce' => 'good-nonce', 'alt_ts' => time() - 10,
                   'alt_email' => $email, 'alt_freq' => $freq, 'alt_website' => '');
    foreach ($lists as $l) $_POST['alt_list_' . $l] = '1';
    $_SERVER['REMOTE_ADDR'] = '203.0.113.7';
    $_SERVER['REQUEST_METHOD'] = 'POST';
    drive('alt_digest_subscribe_submit');
    $_POST = array();
}
function confirm($token) {
    $_REQUEST = array('t' => $token);
    $_SERVER['REQUEST_METHOD'] = 'GET';
    return drive('alt_digest_confirm');
}
function mails_to($email) {
    return array_values(array_filter($GLOBALS['__mails'], function ($m) use ($email) { return $m['to'] === $email; }));
}
function prefs_call($token, $method, $post = array()) {
    $_SERVER['REQUEST_METHOD'] = $method;
    $_POST = $post;
    $r = page(function () use ($token) { alt_prefs_handle($token); });
    $_POST = array();
    return $r;
}
function stop_call($token, $method, $post = array()) {
    $_SERVER['REQUEST_METHOD'] = $method;
    $_POST = $post;
    $r = page(function () use ($token) { alt_follow_stop_handle($token); });
    $_POST = array();
    return $r;
}

$out = array();

/* 1. WELCOME: exactly one, on confirmation, with the unsubscribe headers. */
sub('welcome@example.com', array('layoff', 'articles'), 'weekly');
$r = row('welcome@example.com');
$out['mails_before_confirm'] = count(mails_to('welcome@example.com'));
$out['confirm1'] = confirm($r['confirm_token']);
$m = mails_to('welcome@example.com');
$out['mails_after_confirm'] = count($m);
$out['welcome'] = end($m);
$out['welcome_prefs_url'] = alt_prefs_url(row('welcome@example.com'));
$out['confirm_again'] = confirm($r['confirm_token']);
$out['mails_after_reclick'] = count(mails_to('welcome@example.com'));
$out['budget_after_one'] = get_option('alt_mail_budget');

/* 1b. A change confirmation is not a new subscriber: no second welcome. */
sub('welcome@example.com', array('layoff', 'articles', 'talent'), 'weekly');
$before = count(mails_to('welcome@example.com'));
$out['change_confirm'] = confirm(row('welcome@example.com')['confirm_token']);
$out['mails_from_change_confirm'] = count(mails_to('welcome@example.com')) - $before;

/* 1c. Budget spent: the welcome is skipped and counted, the confirm still lands. */
$GLOBALS['__options']['alt_mail_budget'] = array('day' => gmdate('Y-m-d'), 'welcome' => ALT_WELCOME_CAP_BASE, 'welcome_skipped' => 0);
sub('capped@example.com', array('layoff'), 'daily');
$out['capped_confirm'] = confirm(row('capped@example.com')['confirm_token']);
$out['capped_status'] = row('capped@example.com')['status'];
$out['capped_mails'] = count(mails_to('capped@example.com'));
$out['capped_budget'] = get_option('alt_mail_budget');
$out['stats_welcome'] = alt_digest_stats()['welcome_mail'];
$GLOBALS['__options']['alt_mail_budget'] = array();

/* 2. PREFERENCES PAGE. */
sub('prefs@example.com', array('layoff', 'articles'), 'weekly');
confirm(row('prefs@example.com')['confirm_token']);
$p = row('prefs@example.com');
$tok = alt_prefs_token($p);
$other = row('welcome@example.com');
$out['prefs_get'] = prefs_call($tok, 'GET');
$out['prefs_get_row_unchanged'] = row('prefs@example.com') == $p;
$out['prefs_bad_token'] = prefs_call(str_replace(substr($tok, -4), '0000', $tok), 'GET');
$out['prefs_foreign_id'] = prefs_call((int) $other['id'] . substr($tok, strpos($tok, '-')), 'GET');
// A GET carrying the save field (a scanner replaying a form) writes nothing.
$_SERVER['REQUEST_METHOD'] = 'GET';
$out['prefs_get_with_fields'] = prefs_call($tok, 'GET', array('alt_prefs_save' => '1', 'alt_freq' => 'monthly', 'alt_list_layoff' => '1'));
$out['prefs_get_with_fields_unchanged'] = row('prefs@example.com') == $p;
// Reduce: drop articles, weekly -> monthly. Applies NOW, sends nothing.
$mails0 = count($GLOBALS['__mails']);
$out['prefs_reduce'] = prefs_call($tok, 'POST', array('alt_prefs_save' => '1', 'alt_list_layoff' => '1', 'alt_freq' => 'monthly'));
$out['after_reduce'] = row('prefs@example.com');
$out['reduce_mails'] = count($GLOBALS['__mails']) - $mails0;
// Add: talent, and daily. Nothing applies until the confirmation click.
$GLOBALS['__transients'] = array();
$mails0 = count($GLOBALS['__mails']);
$out['prefs_add'] = prefs_call($tok, 'POST', array('alt_prefs_save' => '1', 'alt_list_layoff' => '1', 'alt_list_talent' => '1', 'alt_freq' => 'daily'));
$out['after_add'] = row('prefs@example.com');
$out['add_mails'] = array_slice($GLOBALS['__mails'], $mails0);
confirm(row('prefs@example.com')['confirm_token']);
$out['after_add_confirmed'] = row('prefs@example.com');
// None ticked: refused, nothing written.
$snap = row('prefs@example.com');
$out['prefs_none'] = prefs_call($tok, 'POST', array('alt_prefs_save' => '1', 'alt_freq' => 'weekly'));
$out['prefs_none_unchanged'] = row('prefs@example.com') == $snap;
// An unsubscribed row's link is dead.
$wpdb->update('wp_alt_subscribers', array('status' => 'unsubscribed'), array('id' => $other['id']));
$out['prefs_unsubscribed'] = prefs_call(alt_prefs_token($other), 'GET');
$wpdb->update('wp_alt_subscribers', array('status' => 'confirmed'), array('id' => $other['id']));

/* 3. FOLLOWS: stop links, GET asks, POST stops, scoped tokens. */
$sid = (int) $p['id'];
$wpdb->insert('wp_alt_follows', array('subscriber_id' => $sid, 'kind' => 'company', 'value' => 'acme',
    'label' => 'Acme Corp', 'url' => 'https://example.test/blog/company-layoffs/acme/', 'status' => 'active', 'created_at' => gmdate('Y-m-d H:i:s')));
$fa = $wpdb->insert_id;
$wpdb->insert('wp_alt_follows', array('subscriber_id' => $sid, 'kind' => 'state', 'value' => 'TX',
    'label' => 'Texas', 'url' => 'https://example.test/blog/state-layoffs/texas/', 'status' => 'active', 'created_at' => gmdate('Y-m-d H:i:s')));
$fb = $wpdb->insert_id;
$wpdb->insert('wp_alt_layoffs', array('id' => 9001, 'company' => 'Acme Corp', 'job_count' => 120,
    'announcement_date' => '2026-09-20', 'state' => 'TX', 'country' => 'United States', 'company_key' => 'acme',
    'superset_of' => 0, 'updated_at' => '2026-09-20 10:00:00'));
$sec = alt_follows_section_for($sid, '2026-09-14', '2026-09-20');
$out['section'] = $sec;
$out['stop_url_a'] = alt_follow_stop_url($p, $fa);
$tokA = alt_follow_stop_token($p, $fa);
$out['prefs_get_follows'] = prefs_call($tok, 'GET');
$out['stop_get'] = stop_call($tokA, 'GET');
$out['stop_get_follow_kept'] = (bool) alt_prefs_follow($sid, $fa);
// Replaying A's signature against B's id is refused.
$forged = $sid . '-' . $fb . substr($tokA, strrpos($tokA, '-'));
$out['stop_forged'] = stop_call($forged, 'POST', array('alt_follow_stop_confirm' => '1'));
$out['stop_forged_follow_kept'] = (bool) alt_prefs_follow($sid, $fb);
// A preferences token is not a stop token.
$out['stop_with_prefs_token'] = stop_call($sid . '-' . $fa . '-' . substr($tok, strpos($tok, '-') + 1), 'POST', array('alt_follow_stop_confirm' => '1'));
$out['stop_post'] = stop_call($tokA, 'POST', array('alt_follow_stop_confirm' => '1'));
$out['stop_post_follow_gone'] = !alt_prefs_follow($sid, $fa);
$out['stop_post_other_kept'] = (bool) alt_prefs_follow($sid, $fb);
$out['stop_post_again'] = stop_call($tokA, 'POST', array('alt_follow_stop_confirm' => '1'));
// Unticking a follow on the preferences page stops it.
prefs_call($tok, 'POST', array('alt_prefs_save' => '1', 'alt_list_layoff' => '1', 'alt_list_talent' => '1', 'alt_freq' => 'daily'));
$out['prefs_untick_follow_gone'] = !alt_prefs_follow($sid, $fb);

/* 4. FALLBACK SENDER: both parts, through Brevo's API when a key is set. */
$GLOBALS['__brevo_key'] = 'xkeysib-test-not-real';
$GLOBALS['__http'] = array();
$mails0 = count($GLOBALS['__mails']);
$wpdb->pdo->exec("UPDATE wp_alt_subscribers SET last_sent_daily = NULL, last_sent_weekly = NULL, last_sent_at = NULL");
$out['fallback_send'] = alt_digest_send('daily');
$out['fallback_http'] = $GLOBALS['__http'];
$out['fallback_wp_mail'] = count($GLOBALS['__mails']) - $mails0;
$out['fallback_prefs_url'] = alt_prefs_url(row('prefs@example.com'));
$out['fallback_unsub'] = alt_digest_unsub_url(row('prefs@example.com')['unsub_token']);
// Without a key it stays on wp_mail, and still sends.
$GLOBALS['__brevo_key'] = '';
$wpdb->pdo->exec("UPDATE wp_alt_subscribers SET last_sent_daily = NULL, last_sent_at = NULL");
$mails0 = count($GLOBALS['__mails']);
$out['nokey_send'] = alt_digest_send('daily');
$out['nokey_wp_mail'] = count($GLOBALS['__mails']) - $mails0;

/* 5. Next send day, from the schedule, in New York time. */
$sat = strtotime('2026-09-26 15:00:00 UTC');   // Saturday
$out['next'] = array(
    'weekly'  => alt_welcome_next_send('weekly', $sat),
    'daily'   => alt_welcome_next_send('daily', $sat),
    'monthly' => alt_welcome_next_send('monthly', $sat),
    'daily_before_slot' => alt_welcome_next_send('daily', strtotime('2026-09-28 09:00:00 UTC')),
);


/* 9. ADAPTIVE WELCOME CAP (owner ruling 2026-09-28). */
$td = gmdate('Y-m-d');
$ago = function ($n) { return gmdate('Y-m-d', time() - $n * 86400); };
$h = function ($w, $sk = 0, $c = 0, $d = 0) { return array('welcome' => $w, 'welcome_skipped' => $sk, 'confirm' => $c, 'digest' => $d); };
$out['cap_quiet'] = alt_welcome_cap_decide(array($ago(1) => $h(10, 0, 12, 100)), '', $td);
$out['cap_grow'] = alt_welcome_cap_decide(array($ago(3) => $h(25, 5), $ago(1) => $h(5, 0, 10, 150)), '', $td);
$out['cap_old_demand'] = alt_welcome_cap_decide(array($ago(4) => $h(40, 10), $ago(1) => $h(5)), '', $td);
$out['cap_no_room'] = alt_welcome_cap_decide(array($ago(2) => $h(40, 5), $ago(1) => $h(40, 0, 40, 170)), '', $td);
$out['cap_edge_room'] = alt_welcome_cap_decide(array($ago(1) => $h(30, 0, 40, 170)), '', $td);
$out['cap_sticky'] = alt_welcome_cap_decide(array(), '2026-09-01', $td);
$out['cap_override'] = alt_welcome_cap_decide(array(), '2026-09-01', $td, 55);
// Roll-over through the real ledger: yesterday's counters become history,
// digest recipients come from the sends log, and the raise persists.
$GLOBALS['__options']['alt_mail_budget'] = array('day' => $ago(1), 'welcome' => 28, 'welcome_skipped' => 4, 'confirm' => 35,
    'history' => array('2026-01-01' => $h(1), '2026-01-02' => $h(1), '2026-01-03' => $h(1), '2026-01-04' => $h(1),
                       '2026-01-05' => $h(1), '2026-01-06' => $h(1), '2026-01-07' => $h(1)));
$out['rolled'] = alt_welcome_budget_status();
$out['rolled_saved'] = get_option('alt_mail_budget');
$out['stats_cap'] = array_intersect_key(alt_digest_stats(), array('welcome_cap_effective' => 1, 'welcome_cap_reason' => 1));
$c0 = (int) get_option('alt_mail_budget')['confirm'];
sub('confirmcount@example.com', array('layoff'), 'weekly');
$out['confirm_recorded'] = (int) get_option('alt_mail_budget')['confirm'] - $c0;
echo json_encode($out);
