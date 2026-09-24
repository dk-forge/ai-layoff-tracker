<?php
/**
 * BREVO CONTACT MIRROR for the digest subscriber list (owner decision
 * 2026-09-24).
 *
 * wp_alt_subscribers stays the SOURCE OF TRUTH: it decides who is sent a
 * digest, and nothing in this file changes that. Brevo gets a COPY of each
 * CONFIRMED subscriber, placed on the Brevo lists that match what they took,
 * so the owner can see list sizes and run his own campaigns from Brevo.
 *
 * Rules this file keeps, each with a test in
 * railway/tests/test_brevo_subscriber_sync.py:
 *
 *   - A PENDING (double opt-in not yet clicked) row is NEVER sent to Brevo.
 *     It has consented to nothing. Only status=confirmed is linked.
 *   - Any other status (unsubscribed, bounced) UNLINKS every configured list
 *     and never creates a contact that was not there.
 *   - The partner-offers list is linked only for a confirmed row whose
 *     consent_partners is 1. Consent is never inferred for anyone.
 *   - A failure here NEVER breaks subscribe/confirm/unsubscribe: every call
 *     is wrapped, short-timeout, and the outcome is written to a private
 *     status option with COUNTS and an HTTP code only, never an address.
 *     The owner reads it in the keyed digest stats payload (`brevo_mirror`).
 *     It is deliberately NOT in the source-health ledger, which renders on the
 *     PUBLIC health page and has staleness ceilings an event-driven mirror
 *     cannot meet.
 *
 * GUARDED INCLUDE: callers use function_exists(), so a deploy that lands the
 * callers before this file is a no-op, not a fatal.
 */

if (!defined('ABSPATH')) exit;

/*
 * List ids. Owner's final ids 2026-09-24: 15 Layoff Daily, 16 Layoff Weekly,
 * 17 Talent Daily, 18 Talent Weekly, 20 Partner Offers. There are NO monthly
 * lists by owner decision: a monthly-tier subscriber goes on the WEEKLY list
 * of their tracker. Override any id with a wp-config constant or the
 * `alt_brevo_list_ids` option (an array with the same keys); 0 means skip.
 */
function alt_brevo_list_ids() {
    $ids = array(
        'layoff_daily'  => 15,
        'layoff_weekly' => 16,
        'talent_daily'  => 17,
        'talent_weekly' => 18,
        'partners'      => 20,
    );
    $opt = get_option('alt_brevo_list_ids', array());
    foreach ($ids as $k => $v) {
        $const = 'ALT_BREVO_LIST_' . strtoupper($k);
        if (defined($const)) {
            $ids[$k] = (int) constant($const);
        } elseif (is_array($opt) && isset($opt[$k])) {
            $ids[$k] = (int) $opt[$k];
        }
    }
    return $ids;
}

/**
 * The API key. The official Brevo WordPress plugin (Sendinblue "mailin") is
 * installed and keeps its v3 key in the `sib_main_option` array under
 * `access_key`; that is reused so the owner does not paste a second copy.
 * A wp-config ALT_BREVO_API_KEY wins when set. '' means not configured.
 */
function alt_brevo_api_key() {
    if (defined('ALT_BREVO_API_KEY') && ALT_BREVO_API_KEY) return trim((string) ALT_BREVO_API_KEY);
    $sib = get_option('sib_main_option', array());
    if (is_array($sib)) {
        foreach (array('access_key', 'api_key') as $k) {
            if (!empty($sib[$k]) && is_string($sib[$k]) && strpos($sib[$k], 'xkeysib-') === 0) {
                return trim($sib[$k]);
            }
        }
    }
    return '';
}

/**
 * PURE: which lists a subscriber row belongs on, and which it must leave.
 * Returns array('create' => bool, 'link' => int[], 'unlink' => int[]).
 * 'create' is true only for a confirmed row: nothing else may bring a
 * contact into existence at Brevo.
 */
function alt_brevo_plan($row, $marketing_optout = false) {
    $ids = alt_brevo_list_ids();
    $all = array_values(array_unique(array_filter(array_map('intval', $ids))));
    $link = array();
    $confirmed = is_array($row) && ($row['status'] ?? '') === 'confirmed';
    if ($confirmed && !$marketing_optout) {
        foreach (array('layoff', 'talent') as $t) {
            if (empty($row['consent_' . $t])) continue;
            $freq = (string) ($row['freq_' . $t] ?? 'weekly');
            // Monthly has no list of its own: owner decision, weekly list.
            $key = $t . '_' . ($freq === 'daily' ? 'daily' : 'weekly');
            if (!empty($ids[$key])) $link[] = (int) $ids[$key];
        }
        if (!empty($row['consent_partners']) && !empty($ids['partners'])) {
            $link[] = (int) $ids['partners'];
        }
    }
    $link = array_values(array_unique($link));
    return array(
        'create' => $confirmed,
        'link'   => $link,
        'unlink' => array_values(array_diff($all, $link)),
    );
}

/** Private status record: counts and an HTTP code, never an address. */
function alt_brevo_record($result, $code = 0) {
    $s = get_option('alt_brevo_sync_status', array());
    if (!is_array($s)) $s = array();
    $s['last_result'] = $result;
    $s['last_code'] = (int) $code;
    $s['last_at'] = gmdate('c');
    $s['counts'] = isset($s['counts']) && is_array($s['counts']) ? $s['counts'] : array();
    $s['counts'][$result] = (int) ($s['counts'][$result] ?? 0) + 1;
    if ($result === 'failed') $s['last_failure_at'] = $s['last_at'];
    update_option('alt_brevo_sync_status', $s, false);
}

function alt_brevo_sync_status() {
    $s = get_option('alt_brevo_sync_status', array());
    if (!is_array($s)) $s = array();
    $s['configured'] = alt_brevo_api_key() !== '';
    return $s;
}

/** One HTTP call. Returns the status code, 0 on a transport failure. */
function alt_brevo_call($method, $path, $body, $key) {
    $resp = wp_remote_request('https://api.brevo.com/v3' . $path, array(
        'method'  => $method,
        'timeout' => 5,
        'headers' => array(
            'api-key'      => $key,
            'accept'       => 'application/json',
            'content-type' => 'application/json',
        ),
        'body'    => wp_json_encode($body),
    ));
    if (is_wp_error($resp)) return 0;
    return (int) wp_remote_retrieve_response_code($resp);
}

function alt_brevo_optout_hash($email) {
    return hash('sha256', strtolower(trim((string) $email)));
}

function alt_brevo_is_marketing_optout($email) {
    $set = get_option('alt_brevo_marketing_optout', array());
    return is_array($set) && isset($set[alt_brevo_optout_hash($email)]);
}

/**
 * Mirror one subscriber row. Returns 'synced', 'unlinked', 'skipped',
 * 'unconfigured' or 'failed'. Never throws.
 */
function alt_brevo_sync_row($row) {
    try {
        if (!is_array($row) || empty($row['email'])) return 'skipped';
        $email = (string) $row['email'];
        $plan = alt_brevo_plan($row, alt_brevo_is_marketing_optout($email));
        $key = alt_brevo_api_key();
        if ($key === '') { alt_brevo_record('unconfigured'); return 'unconfigured'; }

        $enc = '/contacts/' . rawurlencode($email);
        if ($plan['create']) {
            $body = array('email' => $email, 'updateEnabled' => true);
            if ($plan['link']) $body['listIds'] = $plan['link'];
            if (defined('ALT_BREVO_SEND_ATTRIBUTES') && ALT_BREVO_SEND_ATTRIBUTES) {
                // Opt in: Brevo rejects attributes that do not exist in the
                // account, so these are sent only once the owner has made them.
                $trackers = array();
                $tiers = array();
                foreach (array('layoff', 'talent') as $t) {
                    if (empty($row['consent_' . $t])) continue;
                    $trackers[] = $t;
                    $tiers[] = $t . ':' . (string) ($row['freq_' . $t] ?? 'weekly');
                }
                $body['attributes'] = array(
                    'ATR_TRACKERS' => implode(',', $trackers),
                    'ATR_TIER'     => implode(',', $tiers),
                );
            }
            $code = alt_brevo_call('POST', '/contacts', $body, $key);
            if ($code < 200 || $code >= 300) { alt_brevo_record('failed', $code); return 'failed'; }
            if ($plan['unlink']) {
                $code = alt_brevo_call('PUT', $enc, array('unlinkListIds' => $plan['unlink']), $key);
                if ($code < 200 || $code >= 300) { alt_brevo_record('failed', $code); return 'failed'; }
            }
            alt_brevo_record('synced', $code);
            return 'synced';
        }
        if (($row['status'] ?? '') === 'pending') return 'skipped';   // consented to nothing yet
        // Left: unlink everything, and never create a contact to do it. A 404
        // means Brevo never had them, which is the outcome asked for.
        $code = $plan['unlink'] ? alt_brevo_call('PUT', $enc, array('unlinkListIds' => $plan['unlink']), $key) : 204;
        if ($code === 404 || ($code >= 200 && $code < 300)) {
            alt_brevo_record('unlinked', $code);
            return 'unlinked';
        }
        alt_brevo_record('failed', $code);
        return 'failed';
    } catch (Throwable $e) {
        // No message: an exception string could carry the address.
        if (function_exists('alt_brevo_record')) alt_brevo_record('failed', 0);
        return 'failed';
    }
}

/** Mirror whatever the table now says about this address. Never throws. */
function alt_brevo_sync_email($email) {
    try {
        if (!function_exists('alt_digest_get_by_email')) return 'skipped';
        $row = alt_digest_get_by_email($email);
        if (!$row) return 'skipped';
        return alt_brevo_sync_row($row);
    } catch (Throwable $e) {
        return 'failed';
    }
}

/**
 * Brevo told us this contact unsubscribed from a MARKETING CAMPAIGN.
 * Owner decision 2026-09-24: that only takes them off the Brevo lists. It
 * does NOT stop digests, whose consent is managed on the site; the digest
 * email carries its own one-click unsubscribe. The opt-out is remembered (as
 * a hash, never the address) so a later preference change does not relink.
 */
function alt_brevo_campaign_unsubscribed($email) {
    try {
        $email = (string) $email;
        if ($email === '') return 'skipped';
        $set = get_option('alt_brevo_marketing_optout', array());
        if (!is_array($set)) $set = array();
        $set[alt_brevo_optout_hash($email)] = gmdate('Y-m-d');
        update_option('alt_brevo_marketing_optout', $set, false);
        $row = function_exists('alt_digest_get_by_email') ? alt_digest_get_by_email($email) : null;
        if (!$row) $row = array('email' => $email, 'status' => 'unsubscribed');
        return alt_brevo_sync_row($row);
    } catch (Throwable $e) {
        return 'failed';
    }
}

/**
 * One batch of the backfill: confirmed rows by id, idempotent (POST with
 * updateEnabled plus unlink is a set operation, so a rerun changes nothing).
 * Returns counts and the next cursor; next_after_id null means done.
 */
function alt_brevo_backfill_batch($after_id = 0, $limit = 100) {
    global $wpdb;
    $limit = max(1, min(200, (int) $limit));
    $out = array('processed' => 0, 'synced' => 0, 'failed' => 0, 'other' => 0, 'next_after_id' => null);
    if (!function_exists('alt_subscribers_table')) return $out;
    $rows = $wpdb->get_results($wpdb->prepare(
        'SELECT * FROM ' . alt_subscribers_table()
        . " WHERE status = 'confirmed' AND id > %d ORDER BY id ASC LIMIT %d",
        (int) $after_id, $limit), ARRAY_A);
    foreach ((array) $rows as $row) {
        $r = alt_brevo_sync_row($row);
        $out['processed']++;
        if ($r === 'synced') $out['synced']++;
        elseif ($r === 'failed') $out['failed']++;
        else $out['other']++;
        $out['next_after_id'] = (int) $row['id'];
    }
    if (count((array) $rows) < $limit) $out['next_after_id'] = null;
    return $out;
}

/** REST: POST /layoffs/v1/brevo-backfill?after_id=0&limit=100, API-key gated. */
function alt_api_brevo_backfill($request) {
    $after = (int) $request->get_param('after_id');
    $limit = (int) ($request->get_param('limit') ?: 100);
    if (alt_brevo_api_key() === '') {
        return new WP_REST_Response(array('ok' => false, 'reason' => 'brevo api key not configured'), 503);
    }
    return new WP_REST_Response(array_merge(array('ok' => true), alt_brevo_backfill_batch($after, $limit)), 200);
}

function alt_brevo_register_routes() {
    register_rest_route('layoffs/v1', '/brevo-backfill', array(
        'methods'             => 'POST',
        'callback'            => 'alt_api_brevo_backfill',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
}
add_action('rest_api_init', 'alt_brevo_register_routes');

if (defined('WP_CLI') && WP_CLI) {
    /** wp alt-brevo-backfill [--batch=100] : mirror every confirmed subscriber. */
    WP_CLI::add_command('alt-brevo-backfill', function ($args, $assoc) {
        $after = 0; $tot = array('processed' => 0, 'synced' => 0, 'failed' => 0);
        do {
            $b = alt_brevo_backfill_batch($after, (int) ($assoc['batch'] ?? 100));
            foreach ($tot as $k => $v) $tot[$k] += $b[$k];
            $after = $b['next_after_id'];
        } while ($after !== null);
        WP_CLI::success(sprintf('processed %d, synced %d, failed %d',
            $tot['processed'], $tot['synced'], $tot['failed']));
    });
}
