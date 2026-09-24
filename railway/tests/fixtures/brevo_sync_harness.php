<?php
/**
 * Drives includes/brevo-sync.php through the REAL subscribe/confirm/
 * unsubscribe handlers (digest_harness.php supplies WordPress stubs and a
 * SQLite $wpdb). The Brevo API is a recording fake: every call is captured,
 * and a scenario can make it fail. Prints one JSON object.
 *
 * argv[1] subscribe.php, argv[2] digest-api.php, argv[3] brevo-sync.php
 */
define('ALT_HARNESS_STUBS_ONLY', true);
$GLOBALS['__brevo_calls'] = array();
$GLOBALS['__brevo_fail'] = false;

class WP_Error {}
function is_wp_error($x) { return $x instanceof WP_Error; }
function wp_remote_request($url, $args) {
    $GLOBALS['__brevo_calls'][] = array('method' => $args['method'], 'url' => $url,
        'body' => json_decode($args['body'], true), 'timeout' => $args['timeout']);
    if ($GLOBALS['__brevo_fail'] === 'transport') return new WP_Error();
    if ($GLOBALS['__brevo_fail'] === 'throw') throw new RuntimeException('boom reader@example.com');
    return array('code' => $GLOBALS['__brevo_fail'] ? 500 : ($args['method'] === 'POST' ? 201 : 204));
}
function wp_remote_retrieve_response_code($r) { return $r['code']; }

$brevo = $argv[3];
require __DIR__ . '/digest_harness.php';
require $brevo;

function calls_reset() { $GLOBALS['__brevo_calls'] = array(); }
function calls() { return $GLOBALS['__brevo_calls']; }
function signup_as($email, $lists, $freq = 'weekly', $partners = false) {
    $GLOBALS['__transients'] = array();   // no rate limit / resend throttle between steps
    $_POST = array('alt_digest_nonce' => 'good-nonce', 'alt_ts' => time() - 10,
                   'alt_email' => $email, 'alt_freq' => $freq, 'alt_website' => '');
    foreach ($lists as $l) $_POST['alt_list_' . $l] = '1';
    if ($partners) $_POST['alt_partners'] = '1';
    $_SERVER['REMOTE_ADDR'] = '203.0.113.' . rand(1, 250);
    $_SERVER['REQUEST_METHOD'] = 'POST';
    return drive('alt_digest_subscribe_submit');
}
function confirm_as($email) {
    $r = row($email);
    $_REQUEST = array('t' => $r['confirm_token']);
    $_SERVER['REQUEST_METHOD'] = 'GET';
    return drive('alt_digest_confirm');
}
function unsub_as($email) {
    $r = row($email);
    $_REQUEST = array('t' => $r['unsub_token']);
    $_POST = array('alt_unsub_confirm' => '1');
    $_SERVER['REQUEST_METHOD'] = 'POST';
    return drive('alt_digest_unsubscribe');
}

$out = array();
$GLOBALS['__options']['sib_main_option'] = array('access_key' => 'xkeysib-test-0000');

// The form: partner box present, unticked.
$html = alt_digest_subscribe_form('');
$out['form_has_partner_box'] = (bool) preg_match('/<input type="checkbox" name="alt_partners" value="1" form="alt-digest-form-\d+">/', $html);
$out['form_partner_box_checked'] = (bool) preg_match('/name="alt_partners"[^>]*checked/', $html);
$out['form_mentions_partners_in_privacy'] = strpos($html, 'selected partners') !== false;

// 1. Pending signup: nothing reaches Brevo.
calls_reset();
$out['pending_signup'] = signup_as('a@example.com', array('layoff'), 'daily');
$out['pending_calls'] = calls();
$out['pending_partner_col'] = (int) row('a@example.com')['consent_partners'];

// 2. Confirm: created with the right list, the rest unlinked; no partner list.
calls_reset();
$out['confirm_a'] = confirm_as('a@example.com');
$out['confirm_calls'] = calls();

// 3. Partner ticked + monthly talent: talent weekly list (18) + partner (20).
signup_as('b@example.com', array('talent'), 'monthly', true);
$out['b_pending_partner_col'] = (int) row('b@example.com')['consent_partners'];
calls_reset();
confirm_as('b@example.com');
$out['b_confirm_calls'] = calls();
$out['b_partner_stamp'] = row('b@example.com')['partners_consent_at'];

// 4. Untick partner via the preference form (confirmed change path).
signup_as('b@example.com', array('talent'), 'monthly', false);
calls_reset();
confirm_as('b@example.com');
$out['b_untick_calls'] = calls();
$b = row('b@example.com');
$out['b_after_untick'] = array((int) $b['consent_partners'], $b['partners_consent_at']);

// 5. Unsubscribe: unlink every list, never a create.
calls_reset();
$out['unsub_a'] = unsub_as('a@example.com');
$out['unsub_calls'] = calls();

// 6. API failure (500, transport, exception): flow unaffected, status recorded.
foreach (array('http' => true, 'transport' => 'transport', 'throw' => 'throw') as $name => $mode) {
    $GLOBALS['__brevo_fail'] = $mode;
    $email = "f$name@example.com";
    signup_as($email, array('layoff'));
    $res = confirm_as($email);
    $out['fail_' . $name] = array($res, row($email)['status']);
}
$GLOBALS['__brevo_fail'] = false;
$out['status_option'] = get_option('alt_brevo_sync_status');

// 7. No key: silent no-op with a marker.
unset($GLOBALS['__options']['sib_main_option']);
calls_reset();
signup_as('c@example.com', array('layoff'));
$out['nokey_confirm'] = confirm_as('c@example.com');
$out['nokey_calls'] = calls();
$out['nokey_status'] = get_option('alt_brevo_sync_status')['last_result'];
$GLOBALS['__options']['sib_main_option'] = array('access_key' => 'xkeysib-test-0000');

// 8. Backfill: confirmed rows only, in batches, idempotent shape.
calls_reset();
$b1 = alt_brevo_backfill_batch(0, 2);
$b2 = alt_brevo_backfill_batch((int) $b1['next_after_id'], 2);
$out['backfill'] = array($b1, $b2);
$out['backfill_posts'] = count(array_filter(calls(), function ($c) { return $c['method'] === 'POST'; }));

// 9. Brevo campaign unsubscribe webhook: lists unlinked, digest NOT stopped.
$GLOBALS['__options']['alt_digest_brevo_webhook_token'] = 'tok';
signup_as('d@example.com', array('layoff'));
confirm_as('d@example.com');
calls_reset();
$req = new WP_REST_Request('POST', '/layoffs/v1/digest-webhook');
$hdr = new class($req) extends WP_REST_Request {
    public function __construct($r) {}
    public function get_header($k) { return strtolower($k) === 'authorization' ? 'Bearer tok' : ''; }
    public function get_body() { return json_encode(array('event' => 'unsubscribe', 'email' => 'd@example.com',
        'camp_id' => 7, 'list_id' => array(15))); }
};
$resp = alt_api_digest_webhook($hdr);
$out['camp_unsub_status'] = row('d@example.com')['status'];
$out['camp_unsub_calls'] = calls();
$out['camp_unsub_resp'] = $resp->data;
// A later preference change must not relink the Brevo lists.
signup_as('d@example.com', array('layoff', 'talent'));
calls_reset();
confirm_as('d@example.com');
$out['after_optout_calls'] = calls();

$out['logs_have_address'] = strpos(json_encode(get_option('alt_brevo_sync_status')), '@') !== false;
echo json_encode($out), "\n";
