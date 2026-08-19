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
 *                             row's counts, and the tier's own last-sent
 *                             stamp per row id. Takes IDS, never addresses,
 *                             so the recording half of the loop cannot leak
 *                             one.
 *
 *   POST /digest-webhook      NOT key gated, because a provider cannot send
 *                             our key. Verified by the provider's own
 *                             credential and FAILS CLOSED when none is
 *                             configured. A hard bounce or a spam complaint
 *                             stops sending to that address at once.
 *
 *                             TWO PROVIDERS, CHOSEN BY WHAT THE REQUEST
 *                             CARRIES. Resend signs with the Svix scheme and
 *                             sends svix-id / svix-timestamp / svix-signature.
 *                             Brevo sends a plain JSON event and no signature
 *                             at all. The dispatcher reads the request, not an
 *                             environment variable someone has to remember to
 *                             set, so moving provider does not need a code
 *                             change here and running both during a migration
 *                             works.
 *
 * ONE SENDER AT A TIME, ENFORCED TWO WAYS. A list with two senders sends
 * everything twice, which is the fastest way to be marked as spam:
 *
 *   1. A lease. /digest-recipients stamps a claim, and the WP-Cron sender
 *      stands down for any tier claimed within ALT_DIGEST_CLAIM_HOURS. If the
 *      Action stops running, the claim ages out and wp_mail resumes by itself.
 *   2. A per period guard, in BOTH senders. A row already sent to inside this
 *      TIER'S current period is not due, so even two senders racing on the
 *      same minute cannot put two copies in one inbox. The guard is per tier
 *      because Monday runs both, and one shared stamp let the first pass hide
 *      every subscriber from the second (fixed 2026-08-17).
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

    /*
      THE WINDOW, FROM alt_digest_window() AND NOT FROM A COPY OF IT.

      This read `$days = 1 or 7` back from today, so the weekly edition covered
      a rolling seven days ending on the send day. That is a real window and it
      is not a WEEK: it starts on whatever day the cron happens to run, its last
      two days are still filling up while the email describes them, and it can
      never carry a week number anybody can check. The weekly tier now reports
      the previous COMPLETE ISO week. Daily is unchanged. Both definitions live
      in one function so this route and the in-WordPress fallback sender cannot
      describe different windows under the same subject line.
    */
    list($from_date, $to_date) = alt_digest_window($freq);

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
            $sections[$name] = array(
                'html' => $part['html'],
                'text' => $part['text'],
                /*
                  The section's own inbox snippet, composed by the composer
                  for the 130-character ceiling. Passed through as '' when a
                  composer does not supply one, which digest_layout treats as
                  "fall back", never as "no snippet". See
                  alt_digest_fit_preheader and digest_layout.preheader_text.
                */
                'preheader' => isset($part['preheader']) ? (string) $part['preheader'] : '',
                /*
                  THE SECTION'S OWN SUBJECT LINE, and the reason it is composed
                  by the SITE and not by the relay: it carries a FIGURE, and
                  digest_layout may not produce a figure. The owner asked for
                  metric-first subjects ("AI Layoff Tracker: 15,531 verified
                  cuts this week") and every number in one has to come from the
                  same query that built the body, or the subject and the body
                  can disagree about the week's own headline.

                  Absent on an older plugin build, which digest_layout treats
                  as "fall back to the edition label", never as "no subject".
                */
                /*
                  THE SECTION'S FIGURE-AND-UNIT FRAGMENT FOR THE SUBJECT LINE,
                  and the reason it is composed by the SITE: it carries a
                  FIGURE, and digest_layout may not produce one. The relay
                  joins fragments; it never computes a number.

                  `minor` marks a fragment that appears in a subject only when
                  it is the only one there. Absent on an older plugin build,
                  which both senders read as "no metric" and fall back from.
                */
                'metric' => isset($part['metric']) ? (string) $part['metric'] : '',
                'minor'  => !empty($part['minor']),
            );
        }
    }

    // The public archive's copy, taken at COMPOSE time and not from anything
    // the relay renders: it re-composes at send_id 0, so it cannot carry a
    // click URL, and it never sees a recipient. Stored unpublished; it becomes
    // visible when /digest-complete records a real delivery below. See
    // includes/digest-archive.php.
    if (function_exists('alt_edition_capture')) {
        alt_edition_capture($freq, $from_date, $to_date, $send_id);
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

    $response = new WP_REST_Response(array(
        'available'  => true,
        'freq'       => $freq,
        'send_id'    => $send_id,
        'from'       => $from_date,
        'to'         => $to_date,
        // FALLBACK ONLY, and dated even so. The relay composes the real
        // subject in digest_layout.subject_line() and uses this when it
        // cannot; alt_digest_fallback_subject is the same string the
        // in-WordPress sender falls back to, so the two cannot drift.
        'subject'    => alt_digest_fallback_subject($freq, $to_date),
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
        // THE TIER'S OWN STAMP, because on a Monday both tiers run and a
        // shared one let the first pass hide everybody from the second.
        // last_sent_at is written beside it, unread by the guard, so an
        // older plugin build rolled back into place still holds the line.
        $stamp = alt_digest_last_sent_column($freq);
        $stamped = (int) $wpdb->query($wpdb->prepare(
            'UPDATE ' . alt_subscribers_table()
            . " SET $stamp = %s, last_sent_at = %s WHERE id IN ($place)",
            array_merge(array($now, $now), $ids)));
    }
    if ($send_id > 0 && alt_digest_table_present(alt_digest_sends_table())) {
        $wpdb->update(alt_digest_sends_table(),
            array('recipients' => count($ids), 'eligible' => $eligible),
            array('id' => $send_id));
    }
    alt_digest_record_claim($freq);

    // The edition goes public only once messages really went out. A dry run, a
    // preview and a nominated test send all arrive here with no ids, or never
    // arrive at all, so none of them can put a page on the archive.
    if ($ids && function_exists('alt_edition_publish')) {
        alt_edition_publish($send_id, $freq);
    }

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

/* ------------------------------------------------------------------ */
/* Brevo                                                               */
/* ------------------------------------------------------------------ */

/*
 * BREVO DOES NOT SIGN ITS WEBHOOKS. Say it plainly, because every other
 * provider this file has ever spoken to does, and a reader who assumes
 * otherwise will think this endpoint is stronger than it is.
 *
 * Checked against Brevo's own documentation on 2026-08-15: the transactional
 * webhook is a plain JSON POST, and the whole of "Secure webhook calls" offers
 * four things, none of them a signature.
 *
 *   1. a bearer token, from the webhook's `auth` object, sent as
 *      `Authorization: Bearer <token>`;
 *   2. arbitrary custom request headers, from the webhook's `headers` array;
 *   3. basic auth credentials embedded in the webhook URL itself;
 *   4. allowlisting Brevo's published sending CIDR ranges.
 *
 * There is no HMAC, no signing header and no JWT, so there is nothing to
 * verify the BODY against. A shared secret in a header is what is available,
 * and it is what this uses.
 *
 * WHAT THAT BUYS AND WHAT IT DOES NOT. A signature proves a specific payload
 * came from the provider. A bearer token proves only that the caller knows the
 * token, so it is replayable by anyone who has ever seen one request, and TLS
 * is doing all of the confidentiality work. That is a genuinely weaker
 * position than the Svix path below and it is a property of Brevo, not of this
 * code. It is still enormously better than an open endpoint: without it, this
 * URL is a stranger's button for unsubscribing anyone whose address they can
 * guess.
 *
 * THE THREE THINGS DONE ABOUT THE WEAKNESS.
 *
 *   (a) The token is compared with hash_equals, so the comparison does not
 *       leak its length or its prefix to a timing attack.
 *   (b) It is read from a HEADER and never from the query string or the path,
 *       though putting it in the URL is the trick most guides recommend.
 *       Bluehost writes the full request line to an access log, so a secret in
 *       a URL is a secret written to a file we do not control, forever, and
 *       CLAUDE.md's own rule against personal data in query strings is the
 *       same rule for the same reason.
 *   (c) Replay is not defended with a timestamp window, deliberately. Every
 *       action this route can take is idempotent: suppressing an address that
 *       is already suppressed changes nothing and alt_digest_stop_sending
 *       returns false for it. A window tight enough to matter would instead
 *       drop Brevo's own retries and its five minute batch delay, which is a
 *       real harm traded for a theoretical one. The Svix path keeps its window
 *       because there the timestamp is signed and costs nothing.
 */

/** The header name for the token when the bearer header cannot be used. */
if (!defined('ALT_DIGEST_BREVO_TOKEN_HEADER')) {
    define('ALT_DIGEST_BREVO_TOKEN_HEADER', 'x-alt-webhook-token');
}

/**
 * The Brevo webhook token, from wp-config or an option. Absent means this
 * provider's path refuses everything, exactly as an absent Svix secret does.
 */
function alt_digest_brevo_token() {
    if (defined('ALT_DIGEST_BREVO_WEBHOOK_TOKEN') && ALT_DIGEST_BREVO_WEBHOOK_TOKEN) {
        return (string) ALT_DIGEST_BREVO_WEBHOOK_TOKEN;
    }
    return (string) get_option('alt_digest_brevo_webhook_token', '');
}

/**
 * Does this request carry the configured token?
 *
 * TWO ACCEPTED PLACES, and that is not belt and braces. Apache with PHP as
 * CGI or FastCGI drops the Authorization header before PHP ever sees it, which
 * is a well known and silent failure on exactly this kind of shared hosting.
 * If the bearer header were the only route, arming this on Bluehost could fail
 * with a 401 that looks identical to a wrong token, and the operator would
 * have no way to tell those two apart. Brevo can send either an `auth` bearer
 * token or an arbitrary custom header, so both are accepted and the RUNBOOK
 * tells the operator to use the custom header if the bearer one 401s.
 */
function alt_digest_brevo_authenticated($request) {
    $token = alt_digest_brevo_token();
    if ($token === '') return false;

    $presented = array();
    $auth = (string) $request->get_header('authorization');
    if ($auth !== '' && stripos($auth, 'bearer ') === 0) {
        $presented[] = trim(substr($auth, 7));
    }
    $custom = (string) $request->get_header(ALT_DIGEST_BREVO_TOKEN_HEADER);
    if ($custom !== '') $presented[] = trim($custom);

    $ok = false;
    foreach ($presented as $candidate) {
        // No early return: every candidate is compared so the number of
        // comparisons does not depend on which one matched.
        if ($candidate !== '' && hash_equals($token, $candidate)) $ok = true;
    }
    return $ok;
}

/**
 * One Brevo event name to one suppression status, by exact lookup.
 *
 * AN EXACT MAP, NEVER A SUBSTRING TEST. `strpos($event, 'bounce')` reads as
 * obviously right and catches soft_bounce, which is the single most expensive
 * mistake available here: it deletes people whose mailbox was briefly full.
 * Every name below was read from Brevo's transactional webhook event list, and
 * a name that is not in this map changes nothing.
 *
 * The events that deliberately map to NOTHING, with the reason:
 *   soft_bounce, deferred  a transient failure. Not evidence of anything.
 *   blocked                Brevo declined to send because the address is on
 *                          ITS blocklist. That is a consequence of some
 *                          earlier suppression, not new evidence about the
 *                          mailbox, so it must not create a suppression here.
 *   error                  a failure on Brevo's side.
 *   request, delivered     the message went out. Nothing to do.
 *   opened, unique_opened, proxy_open, unique_proxy_open, click
 *                          engagement. NOT recorded, not counted, not stored
 *                          anywhere, per the published privacy note. They fall
 *                          through this map to no action, which is the whole
 *                          of the handling they get.
 *
 * Brevo spells an event one way in the API that SUBSCRIBES to it (hardBounce)
 * and another way in the payload it then DELIVERS (hard_bounce). The lookup is
 * normalised so both spellings resolve, because that asymmetry is exactly the
 * kind of thing that silently stops working after a provider tidies its docs.
 */
function alt_digest_brevo_action($event) {
    $key = strtolower(str_replace(array('_', '-', ' '), '', (string) $event));
    $map = array(
        'hardbounce'   => 'bounced',
        // A permanently undeliverable address: Brevo could not route it at
        // all. Same fact as a hard bounce, recorded as the same status.
        'invalidemail' => 'bounced',
        'invalid'      => 'bounced',
        'spam'         => 'unsubscribed',   // a withdrawal of consent
        'unsubscribed' => 'unsubscribed',   // asked to stop, via Brevo's link
        'unsubscribe'  => 'unsubscribed',
    );
    return isset($map[$key]) ? $map[$key] : '';
}

/**
 * Pull the event objects out of a Brevo body.
 *
 * Brevo delivers one event per POST by default, and the RUNBOOK says to leave
 * it that way. Its optional `batched` mode is real but its delivered payload
 * shape is NOT documented, so all three plausible shapes are accepted rather
 * than guessing one: a bare object, a top level array, and an object wrapping
 * an array. Accepting a shape that never arrives costs nothing. Rejecting the
 * one that does arrive drops bounces silently, which is the failure this whole
 * change exists to prevent.
 */
function alt_digest_brevo_events($body) {
    if (!is_array($body)) return array();
    if (isset($body['event'])) return array($body);
    foreach (array('items', 'events') as $key) {
        if (isset($body[$key]) && is_array($body[$key])) $body = $body[$key];
    }
    $out = array();
    foreach ($body as $item) {
        if (is_array($item) && isset($item['event'])) $out[] = $item;
    }
    return $out;
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

/**
 * The one public entry point. Decides WHICH provider is talking from what the
 * request actually carries, never from configuration.
 *
 * A provider selected by an environment variable is a provider that is wrong
 * every time somebody forgets to change it, and the symptom is silent: bounces
 * stop being processed and nothing anywhere goes red. The request already
 * says who sent it, so it is read rather than assumed. It also means both
 * providers work at once, which is what a migration actually looks like.
 */
function alt_api_digest_webhook($request) {
    $raw = $request->get_body();

    // Svix, and therefore Resend, is identified by its three headers. They are
    // required by the scheme, so their presence is the provider's own claim
    // about itself, and a request carrying them is verified as Svix or refused
    // as Svix. It never falls through to the weaker path on a bad signature.
    if ((string) $request->get_header('svix-signature') !== ''
        || (string) $request->get_header('svix-id') !== '') {
        return alt_digest_webhook_resend($request, $raw);
    }

    $body = json_decode((string) $raw, true);
    if (alt_digest_brevo_events($body)) {
        return alt_digest_webhook_brevo($request, $body);
    }

    // Neither provider. Nothing is acted on and nothing is disclosed.
    return new WP_REST_Response(array('ok' => false), 401);
}

/**
 * Brevo: a plain JSON event, authenticated by the shared token and nothing
 * else, because Brevo offers nothing else. See the long note above
 * alt_digest_brevo_authenticated for what that does and does not prove.
 */
function alt_digest_webhook_brevo($request, $body) {
    if (!alt_digest_brevo_authenticated($request)) {
        // As terse as the Svix refusal, and for the same reason: a failure
        // must not tell a caller whether an address is on the list.
        return new WP_REST_Response(array('ok' => false), 401);
    }
    $stopped = 0;
    foreach (alt_digest_brevo_events($body) as $event) {
        $action = alt_digest_brevo_action($event['event'] ?? '');
        if ($action === '') continue;      // soft bounces and engagement
        $address = sanitize_email((string) ($event['email'] ?? ''));
        if (alt_digest_stop_sending($address, $action)) $stopped++;
    }
    // Counts only, here and in anything that could be logged.
    return new WP_REST_Response(array('ok' => true, 'stopped' => $stopped), 200);
}

/**
 * Resend, via the Svix signature scheme. Unchanged behaviour: this path
 * predates Brevo and Resend remains a supported transport.
 */
function alt_digest_webhook_resend($request, $raw) {
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
