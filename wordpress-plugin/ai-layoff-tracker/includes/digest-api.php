<?php
/**
 * The server half of the external digest sender.
 *
 * includes/subscribe.php owns the list, the consent, the composition and a
 * wp_mail sender that works. This file exists because wp_mail on shared
 * hosting is the weakest link in a delivery chain: no DKIM alignment worth
 * having, a shared sending IP, and no bounce feedback at all. So a scheduled
 * GitHub Action (railway/digest_send.py) relays the same composed digest
 * through a real provider instead.
 *
 * THREE ROUTES, AND WHY EACH IS SHAPED THIS WAY.
 *
 *   GET  /digest-recipients   keyed. Opens the send row, composes the sections
 *                             ONCE through the same functions the wp_mail
 *                             sender uses, and returns the rows due this
 *                             period. This is the only route in the plugin
 *                             that returns an email address, it is key gated
 *                             exactly as /alert is, and it returns only
 *                             addresses that are CONFIRMED, consented and not
 *                             already sent to in this period.
 *
 *   POST /digest-complete     keyed. Records what actually went out: the send
 *                             row's counts and last_sent_at per row id. Takes
 *                             IDS, never addresses, so the recording half of
 *                             the loop cannot leak one.
 *
 *   POST /digest-webhook      NOT key gated, because a provider cannot send
 *                             our key. Verified by the provider's own HMAC
 *                             signature and FAILS CLOSED when no signing
 *                             secret is configured. A hard bounce or a spam
 *                             complaint stops sending to that address at once.
 *
 * ONE SENDER AT A TIME, ENFORCED TWO WAYS. A list with two senders sends
 * everything twice, which is the fastest way to be marked as spam:
 *
 *   1. A lease. /digest-recipients stamps a claim, and the WP-Cron sender
 *      stands down for any tier claimed within ALT_DIGEST_CLAIM_HOURS. If the
 *      Action stops running, the claim ages out and wp_mail resumes by itself.
 *   2. A per period guard, in BOTH senders. A row whose last_sent_at falls
 *      inside the current period is not due, so even two senders racing on the
 *      same minute cannot put two copies in one inbox.
 */

if (!defined('ABSPATH')) exit;

/** How long one external claim holds the tier. Longer than a missed run, far
 *  shorter than a weekend, so a dead Action self heals over one day. */
if (!defined('ALT_DIGEST_CLAIM_HOURS')) define('ALT_DIGEST_CLAIM_HOURS', 36);

/* ------------------------------------------------------------------ */
/* The lease                                                           */
/* ------------------------------------------------------------------ */

function alt_digest_claim_option() {
    return 'alt_digest_external_claim';
}

function alt_digest_record_claim($freq) {
    $claims = get_option(alt_digest_claim_option(), array());
    if (!is_array($claims)) $claims = array();
    $claims[$freq] = gmdate('c');
    update_option(alt_digest_claim_option(), $claims, false);
}

/**
 * Is an external sender currently handling this tier? Used by the WP-Cron
 * sender to stand down. An unreadable or absent claim means NO, so the
 * fallback direction is "the built in sender keeps working", never silence.
 */
function alt_digest_external_active($freq) {
    $claims = get_option(alt_digest_claim_option(), array());
    if (!is_array($claims) || empty($claims[$freq])) return false;
    $at = strtotime((string) $claims[$freq]);
    if (!$at) return false;
    return (time() - $at) < ALT_DIGEST_CLAIM_HOURS * HOUR_IN_SECONDS;
}

/* ------------------------------------------------------------------ */
/* Who is due                                                          */
/* ------------------------------------------------------------------ */

/*
 * `alt_digest_due_rows()` and `alt_digest_period_seconds()` live in
 * includes/subscribe.php and are used from here. They are deliberately NOT
 * redefined in this file: one definition of who is due is the whole reason two
 * senders are safe, and PHP fatals on a redeclared function, which took the
 * live site down for six minutes on 2026-08-15. tests/test_digest_sender.py
 * now fails on any function declared in two plugin includes.
 */

/* ------------------------------------------------------------------ */
/* GET /digest-recipients                                              */
/* ------------------------------------------------------------------ */

function alt_api_digest_recipients($request) {
    global $wpdb;
    $freq = alt_digest_valid_freq((string) $request->get_param('freq'));

    // Absent table is UNKNOWN, never an empty list. "Nobody is subscribed" and
    // "we cannot see the list" are different facts, and a sender told the
    // first when the second is true reports a successful send of nothing.
    if (!alt_digest_table_present(alt_subscribers_table())) {
        return new WP_REST_Response(array(
            'available' => false,
            'reason'    => 'the subscriber table does not exist on this install',
        ), 200);
    }

    $days = $freq === 'daily' ? 1 : 7;
    $to_date = gmdate('Y-m-d');
    $from_date = gmdate('Y-m-d', time() - $days * DAY_IN_SECONDS);

    // The send row is opened BEFORE composition because the counted links
    // carry its id, exactly as the wp_mail sender does it.
    $send_id = 0;
    if (alt_digest_table_present(alt_digest_sends_table())) {
        $wpdb->insert(alt_digest_sends_table(), array(
            'freq' => $freq, 'sent_at' => gmdate('Y-m-d H:i:s'),
            'recipients' => 0, 'eligible' => 0,
        ));
        $send_id = (int) $wpdb->insert_id;
    }

    // Composed by the SAME functions the built in sender uses, which read the
    // site's own public endpoints. A section the endpoints cannot supply is
    // absent from this payload, and the sender omits it rather than inventing
    // a figure to fill the space.
    $sections = array();
    foreach (array('layoff'   => 'alt_digest_compose_layoff',
                   'talent'   => 'alt_digest_compose_talent',
                   'articles' => 'alt_digest_compose_articles') as $name => $fn) {
        $part = function_exists($fn) ? $fn($from_date, $to_date, $send_id) : null;
        if (is_array($part) && !empty($part['html']) && !empty($part['text'])) {
            $sections[$name] = array('html' => $part['html'], 'text' => $part['text']);
        }
    }

    $recipients = array();
    foreach (alt_digest_due_rows($freq) as $row) {
        $lists = array();
        // ALL THREE. A list missing from this loop is an address the external
        // sender is never handed, which is exactly how the articles box spent
        // its first months: confirmed subscribers, counted by nothing, mailed
        // by nobody. It is driven off alt_digest_lists() by hand rather than
        // by iteration so that adding a fourth box is a deliberate edit here.
        foreach (array('layoff', 'talent', 'articles') as $list) {
            $cols = alt_digest_lists()[$list];
            if ((int) $row[$cols['consent']] === 1 && $row[$cols['freq']] === $freq) {
                $lists[] = $list;
            }
        }
        // Nothing composed for any list this person takes: not a recipient.
        $has = false;
        foreach ($lists as $list) { if (isset($sections[$list])) $has = true; }
        if (!$has) continue;
        $recipients[] = array(
            'id'        => (int) $row['id'],
            'email'     => (string) $row['email'],
            'unsub_url' => alt_digest_unsub_url($row['unsub_token']),
            'lists'     => $lists,
        );
    }

    alt_digest_record_claim($freq);

    // A run that composed nothing, or found nobody, leaves no send row behind.
    // "Last digest sent to 0" reads as a delivery failure when in fact nothing
    // was due to go out at all.
    if ($send_id > 0 && !$recipients) {
        $wpdb->query($wpdb->prepare(
            'DELETE FROM ' . alt_digest_sends_table() . ' WHERE id = %d', $send_id));
        if (alt_digest_table_present(alt_digest_links_table())) {
            $wpdb->query($wpdb->prepare(
                'DELETE FROM ' . alt_digest_links_table() . ' WHERE send_id = %d', $send_id));
        }
        $send_id = 0;
    }

    $label = $freq === 'daily' ? 'Daily' : 'Weekly';
    $response = new WP_REST_Response(array(
        'available'  => true,
        'freq'       => $freq,
        'send_id'    => $send_id,
        'from'       => $from_date,
        'to'         => $to_date,
        'subject'    => '[AskTheRecruiter] ' . $label . ' tracker digest',
        'sections'   => $sections,
        // Where a reader changes WHAT they get rather than stopping
        // everything. Built here, from home_url(), so the relay never carries
        // a hard coded site address it could get wrong or out of date.
        'manage_url' => function_exists('alt_digest_manage_url') ? alt_digest_manage_url() : '',
        'recipients' => $recipients,
    ), 200);
    // Addresses are never cached, at the edge or anywhere else.
    $response->header('Cache-Control', 'no-store, max-age=0, private');
    return $response;
}

/* ------------------------------------------------------------------ */
/* POST /digest-complete                                               */
/* ------------------------------------------------------------------ */

/**
 * Record what went out. Takes row IDS, never addresses: the recording half of
 * the loop has no reason to see one, so it is built unable to.
 */
function alt_api_digest_complete($request) {
    global $wpdb;
    $body = $request->get_json_params();
    if (!is_array($body)) $body = array();
    $send_id = (int) ($body['send_id'] ?? 0);
    $freq = alt_digest_valid_freq((string) ($body['freq'] ?? 'weekly'));
    $eligible = max(0, (int) ($body['eligible'] ?? 0));
    $failed = max(0, (int) ($body['failed'] ?? 0));
    $ids = array();
    foreach ((array) ($body['sent_ids'] ?? array()) as $id) {
        $id = (int) $id;
        if ($id > 0) $ids[] = $id;
    }
    $ids = array_values(array_unique($ids));

    $stamped = 0;
    if ($ids && alt_digest_table_present(alt_subscribers_table())) {
        $now = gmdate('Y-m-d H:i:s');
        $place = implode(',', array_fill(0, count($ids), '%d'));
        $stamped = (int) $wpdb->query($wpdb->prepare(
            'UPDATE ' . alt_subscribers_table() . " SET last_sent_at = %s WHERE id IN ($place)",
            array_merge(array($now), $ids)));
    }
    if ($send_id > 0 && alt_digest_table_present(alt_digest_sends_table())) {
        $wpdb->update(alt_digest_sends_table(),
            array('recipients' => count($ids), 'eligible' => $eligible),
            array('id' => $send_id));
    }
    alt_digest_record_claim($freq);

    // Health, stamped here because this is the moment the run is known to have
    // finished. Counts only, as everywhere that touches this list.
    if (function_exists('alt_source_health_record')) {
        alt_source_health_record('digest_mailer', $failed ? 'degraded' : 'ok', count($ids),
            sprintf('%s: %d sent of %d eligible, %d failed, via %s',
                    $freq, count($ids), $eligible, $failed,
                    sanitize_key((string) ($body['transport'] ?? 'external'))));
    }
    return new WP_REST_Response(array(
        'ok' => true, 'recorded' => count($ids), 'stamped' => $stamped), 200);
}

/* ------------------------------------------------------------------ */
/* POST /digest-webhook (bounces and complaints)                       */
/* ------------------------------------------------------------------ */

/**
 * The signing secret, from wp-config or an option. Absent means this endpoint
 * refuses everything: an unauthenticated webhook that acts on a payload is a
 * stranger's button for unsubscribing anyone whose address they can guess.
 */
function alt_digest_webhook_secret() {
    if (defined('ALT_DIGEST_WEBHOOK_SECRET') && ALT_DIGEST_WEBHOOK_SECRET) {
        return (string) ALT_DIGEST_WEBHOOK_SECRET;
    }
    return (string) get_option('alt_digest_webhook_secret', '');
}

/**
 * Verify a Svix style signature, which is what Resend and several others use.
 * Signed content is "<id>.<timestamp>.<body>", HMAC-SHA256 with the decoded
 * secret, base64. The timestamp is checked against a five minute window so a
 * captured request cannot be replayed later.
 */
function alt_digest_webhook_verified($request, $raw) {
    $secret = alt_digest_webhook_secret();
    if ($secret === '') return false;

    $id = (string) $request->get_header('svix-id');
    $ts = (string) $request->get_header('svix-timestamp');
    $sig = (string) $request->get_header('svix-signature');
    if ($id === '' || $ts === '' || $sig === '') return false;
    if (!ctype_digit($ts) || abs(time() - (int) $ts) > 300) return false;

    $raw_secret = strpos($secret, 'whsec_') === 0 ? substr($secret, 6) : $secret;
    $decoded = base64_decode($raw_secret, true);
    if ($decoded === false) $decoded = $raw_secret;
    $expected = base64_encode(hash_hmac('sha256', "$id.$ts.$raw", $decoded, true));

    // The header may carry several space separated "v1,<sig>" values during a
    // secret rotation. Any one matching is a valid signature.
    foreach (explode(' ', $sig) as $candidate) {
        $parts = explode(',', $candidate, 2);
        if (count($parts) === 2 && hash_equals($expected, $parts[1])) return true;
    }
    return false;
}

/**
 * Stop sending to an address the provider told us is dead or angry.
 *
 * A hard bounce and a spam complaint both end sending immediately. They are
 * recorded as distinct statuses because they are distinct facts: 'bounced' is
 * a mailbox that does not exist, 'unsubscribed' is a person who asked us to
 * stop. Both carry unsubscribed_at, so the retention purge erases them on the
 * same 30 day promise as any other departure.
 *
 * A SOFT bounce (a full mailbox, a transient defer) changes nothing. Removing
 * someone because their inbox was full for an hour is data loss dressed as
 * hygiene.
 */
function alt_digest_stop_sending($email, $status) {
    global $wpdb;
    if (!is_email($email)) return false;
    if (!in_array($status, array('bounced', 'unsubscribed'), true)) return false;
    if (!alt_digest_table_present(alt_subscribers_table())) return false;
    $row = alt_digest_get_by_email($email);
    if (!$row || $row['status'] === 'unsubscribed') return false;
    return (bool) $wpdb->update(alt_subscribers_table(), array(
        'status'          => $status,
        'unsubscribed_at' => gmdate('Y-m-d H:i:s'),
        'pending_prefs'   => null,
        'confirm_token'   => null,
    ), array('id' => $row['id']));
}

function alt_api_digest_webhook($request) {
    $raw = $request->get_body();
    if (!alt_digest_webhook_verified($request, $raw)) {
        // Deliberately terse. A verification failure tells a caller nothing
        // about whether an address is on the list.
        return new WP_REST_Response(array('ok' => false), 401);
    }
    $body = json_decode((string) $raw, true);
    if (!is_array($body)) return new WP_REST_Response(array('ok' => false), 400);

    $type = (string) ($body['type'] ?? '');
    $data = is_array($body['data'] ?? null) ? $body['data'] : array();
    $to = $data['to'] ?? array();
    if (is_string($to)) $to = array($to);

    $action = '';
    if ($type === 'email.complained') {
        $action = 'unsubscribed';       // treated as a withdrawal of consent
    } elseif ($type === 'email.bounced') {
        $bounce = is_array($data['bounce'] ?? null) ? $data['bounce'] : array();
        $kind = strtolower((string) ($bounce['type'] ?? ''));
        // Permanent only. A transient defer is not a reason to drop anyone.
        if ($kind === '' || strpos($kind, 'permanent') !== false || strpos($kind, 'hard') !== false) {
            $action = 'bounced';
        }
    }
    $stopped = 0;
    if ($action !== '') {
        foreach ((array) $to as $address) {
            if (alt_digest_stop_sending(sanitize_email((string) $address), $action)) $stopped++;
        }
    }
    // Counts only in the response and in anything that could be logged.
    return new WP_REST_Response(array('ok' => true, 'stopped' => $stopped), 200);
}

/* ------------------------------------------------------------------ */
/* Routes                                                              */
/* ------------------------------------------------------------------ */

function alt_digest_api_register_routes() {
    register_rest_route('layoffs/v1', '/digest-recipients', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_digest_recipients',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    register_rest_route('layoffs/v1', '/digest-complete', array(
        'methods'             => 'POST',
        'callback'            => 'alt_api_digest_complete',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    register_rest_route('layoffs/v1', '/digest-webhook', array(
        'methods'             => 'POST',
        'callback'            => 'alt_api_digest_webhook',
        'permission_callback' => '__return_true',   // verified by HMAC, fails closed
    ));
}
add_action('rest_api_init', 'alt_digest_api_register_routes');
