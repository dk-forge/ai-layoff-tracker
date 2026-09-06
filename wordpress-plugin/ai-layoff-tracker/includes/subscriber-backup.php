<?php
/**
 * The ONE route that may read wp_alt_subscribers, and it can only ever emit
 * ciphertext.
 *
 * THE GAP THIS CLOSES
 * -------------------
 * includes/backup.php exports every table the plugin owns to a PUBLIC GitHub
 * release, and it excludes wp_alt_subscribers on purpose: addresses, consent
 * records and two live tokens. Correct, and the consequence was that the
 * subscriber list and its consent records existed in exactly ONE place, on a
 * shared Bluehost account, with a host migration coming. Consent records have
 * legal weight; losing them is worse than losing the addresses.
 *
 * WHY THIS IS NOT A NEW ENTRY IN alt_backup_tables()
 * -------------------------------------------------
 * Because that allowlist is the structural boundary, and it stays complete:
 * /backup-table still 400s on `subscribers` and alt_backup_forbidden_tables()
 * still names it. Widening the allowlist would have made the personal-data
 * boundary a property of what the CALLER asked for. This route is a separate
 * contract with a different promise: it does not have a mode that returns
 * rows. There is no `format=json`, no debug branch, no dry-run that prints a
 * sample. The only exit that carries data is the sealed one.
 *
 * WHO CAN READ WHAT IT PRODUCES
 * -----------------------------
 * Only the holder of the private key. The host seals with a PUBLIC key
 * deployed alongside this file, so a host that is compromised, a runner, a
 * backup of the ciphertext, and this repository can all WRITE and MOVE the
 * backup and none of them can open it.
 *
 * DISARMED UNTIL THE OWNER SHIPS A KEY. With no recipient key on disk the
 * route answers 503 and says what to do. That is deliberate: a backup that
 * silently sealed to nobody, or to a key nobody holds, is the failure this
 * whole file exists to avoid, and 503 is the state a session can read.
 */

if (!defined('ABSPATH')) exit;

// The pure sealer. GUARDED with is_readable for the reason every other new
// include here is: an FTPS deploy can land this file first, and a hard require
// of a not-yet-uploaded include fatals the ENTIRE plugin on every request until
// it arrives (2.19.20). Its absence must degrade to "the subscriber backup route
// answers 503", never to a white screen.
$alt_sbk_seal_file = ALT_PLUGIN_DIR . 'includes/subscriber-backup-seal.php';
if (is_readable($alt_sbk_seal_file)) {
    require_once $alt_sbk_seal_file;
}

/**
 * Bump when the shape of the sealed payload changes in a way a restore has to
 * know about. It is recorded inside the container AND covered by its MAC, so a
 * file opened in three years can say whether it predates a change.
 */
if (!defined('ALT_SUBSCRIBER_BACKUP_SCHEMA')) define('ALT_SUBSCRIBER_BACKUP_SCHEMA', 1);

/**
 * Where the recipient PUBLIC key lives once the owner arms this.
 * Committed to the repository and deployed with the plugin, exactly like the
 * data files next to it, because a public key is not a secret and putting it
 * in a WordPress option would mean the host could change who the backup is
 * readable by without anything noticing.
 */
function alt_sbk_key_path() {
    return ALT_PLUGIN_DIR . 'data/subscriber-backup.pub.pem';
}

/** The recipient key text, or '' when this is still disarmed. */
function alt_sbk_public_key() {
    $path = alt_sbk_key_path();
    if (!is_readable($path)) return '';
    $pem = file_get_contents($path);
    return is_string($pem) ? trim($pem) : '';
}

/**
 * The COLUMN ALLOWLIST, pinned exactly as includes/backup.php pins every other
 * table's, and for the same reason: the day somebody adds a column, this goes
 * red and a human reads the schema, instead of the column riding along inside
 * a container nobody opens until the host is already gone.
 *
 * Every column IS exported here. That is the difference between this route and
 * every other one: the point of a consent record is that it is complete, so a
 * partial subscriber backup would be worse than none. The two tokens are in
 * it, which is precisely why the payload never exists outside the envelope.
 */
function alt_sbk_columns() {
    return array(
        'id', 'email',
        'consent_layoff', 'consent_talent', 'consent_articles',
        'freq_layoff', 'freq_talent', 'freq_articles',
        'status', 'confirm_token', 'unsub_token', 'pending_prefs',
        'created_at', 'confirmed_at', 'unsubscribed_at',
        'last_sent_at', 'last_sent_daily', 'last_sent_weekly', 'last_sent_monthly',
    );
}

add_action('rest_api_init', 'alt_sbk_register_routes');
function alt_sbk_register_routes() {
    register_rest_route('layoffs/v1', '/subscriber-backup', array(
        'methods' => 'GET',
        'callback' => 'alt_api_subscriber_backup',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Readable state WITHOUT moving anything: is a key deployed, which one, how
    // many rows there are to seal. A session can answer "is this armed" without
    // asking the host to produce a backup, and the answer names no subscriber.
    register_rest_route('layoffs/v1', '/subscriber-backup-status', array(
        'methods' => 'GET',
        'callback' => 'alt_api_subscriber_backup_status',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
}

/** Shared refusals, so the two routes cannot drift apart on what "ready" means. */
function alt_sbk_not_ready() {
    if (!function_exists('alt_sbk_seal')) {
        return new WP_Error('alt_sbk_no_sealer',
            'includes/subscriber-backup-seal.php is not on this install, so nothing can be sealed. '
            . 'This is normally a deploy that landed half its files; it resolves on the next one.',
            array('status' => 503));
    }
    if (alt_sbk_public_key() === '') {
        return new WP_Error('alt_sbk_disarmed',
            'No recipient public key is deployed, so this route is DISARMED and will not read the table. '
            . 'Arming it is the owner\'s step: generate an RSA-4096 keypair, keep the private half off '
            . 'this host and out of the repository, commit the public half to '
            . 'wordpress-plugin/ai-layoff-tracker/data/subscriber-backup.pub.pem, and deploy. '
            . 'See docs/RUNBOOK.md "back up the subscriber list".',
            array('status' => 503));
    }
    if (!function_exists('alt_subscribers_table') || !alt_subscribers_table_ready()) {
        return new WP_Error('alt_sbk_no_table',
            'The subscriber table is not present on this install. That is UNKNOWN, not empty.',
            array('status' => 503));
    }
    return null;
}

/**
 * Is it armed, and how much is there. Moves nothing.
 *
 * A row COUNT is reported here and deliberately not in the public backup
 * manifest. The difference is the audience: this route is keyed and its answer
 * goes to the owner's own machine, whereas /backup-manifest is read into a
 * public Actions log where a count is still a fact about a personal-data table.
 */
function alt_api_subscriber_backup_status() {
    global $wpdb;
    $pem = alt_sbk_public_key();
    $armed = ($pem !== '' && function_exists('alt_sbk_seal'));
    $fingerprint = '';
    $key_error = '';
    if ($pem !== '' && function_exists('alt_sbk_fingerprint')) {
        try {
            $fingerprint = alt_sbk_fingerprint($pem);
        } catch (Exception $e) {
            $armed = false;
            $key_error = $e->getMessage();
        }
    }
    // A COUNT, never rows. The variable is named for the count on purpose:
    // `$rows` in this file means row DATA and nothing else, so a test can read
    // "does any response carry $rows" and get a true answer.
    $row_count = null;
    if (function_exists('alt_subscribers_table') && alt_subscribers_table_ready()) {
        $row_count = (int) $wpdb->get_var('SELECT COUNT(*) FROM ' . alt_subscribers_table());
    }
    $r = rest_ensure_response(array(
        'armed' => $armed,
        'key_fingerprint' => $fingerprint,
        'key_error' => $key_error,
        'rows' => $row_count,     // null means UNKNOWN, never zero
        'schema_version' => ALT_SUBSCRIBER_BACKUP_SCHEMA,
        'plugin_version' => defined('ALT_VERSION') ? ALT_VERSION : '',
        'columns' => alt_sbk_columns(),
    ));
    $r->header('Cache-Control', 'no-store, max-age=0');
    return $r;
}

/**
 * The whole subscriber table, sealed. One response, because the table is small
 * (hundreds of rows) and a paged envelope would mean either one key per page,
 * which multiplies the thing that must not leak, or a shared key held across
 * requests, which means storing it. Neither is worth it below the cap.
 */
function alt_api_subscriber_backup(WP_REST_Request $req) {
    global $wpdb;

    $bad = alt_sbk_not_ready();
    if ($bad !== null) return $bad;

    $table = alt_subscribers_table();
    $columns = alt_sbk_columns();

    $rows = $wpdb->get_results('SELECT * FROM ' . $table . ' ORDER BY id ASC', ARRAY_A);
    if (!is_array($rows)) {
        return new WP_Error('alt_sbk_read_failed',
            'The subscriber table could not be read. UNKNOWN, not empty.',
            array('status' => 500));
    }

    // The cap is a guard against sealing something that is not what we think it
    // is, not a capacity limit. If this table is ever six figures, somebody has
    // to look before a backup silently doubles in shape.
    if (count($rows) > 100000) {
        return new WP_Error('alt_sbk_too_large',
            'The subscriber table is larger than this route was designed for. Stopping on purpose.',
            array('status' => 500));
    }

    $lines = array();
    foreach ($rows as $row) {
        // LAYER 2, same discipline as the public export: a column nobody has
        // pinned FAILS the run. Here it matters more, not less: an unreviewed
        // column in a personal-data table is exactly the thing a human should
        // see before it is sealed into a file that outlives the schema.
        $unknown = array_diff(array_keys($row), $columns);
        if ($unknown) {
            return new WP_Error('alt_sbk_unpinned_column',
                'The subscriber table returned column(s) ' . implode(', ', $unknown)
                . ' that alt_sbk_columns() does not pin. THE BACKUP HAS STOPPED ON PURPOSE. '
                . 'Read the new column before doing anything else, then add it here and to '
                . 'railway/subscriber_backup.py. Do not widen this check.',
                array('status' => 500));
        }
        $ordered = array();
        foreach ($columns as $c) {
            $ordered[$c] = array_key_exists($c, $row) ? $row[$c] : null;
        }
        $lines[] = wp_json_encode($ordered);
    }
    $payload = implode("\n", $lines);
    if ($lines) $payload .= "\n";

    try {
        $container = alt_sbk_seal($payload, alt_sbk_public_key(), array(
            'schema_version' => ALT_SUBSCRIBER_BACKUP_SCHEMA,
            'rows' => count($rows),
            'columns' => $columns,
            'plugin_version' => defined('ALT_VERSION') ? ALT_VERSION : '',
        ));
    } catch (Exception $e) {
        // The message is about the KEY or the crypto, never about a row.
        return new WP_Error('alt_sbk_seal_failed',
            'Sealing failed, so nothing is returned: ' . $e->getMessage(),
            array('status' => 500));
    }

    // Everything readable is gone before the response is built. $payload held
    // every address on the list for the length of one request and nothing else
    // in this file may see it.
    $payload = null;
    $lines = null;
    $rows = null;

    $resp = rest_ensure_response($container);
    $resp->header('Cache-Control', 'no-store, max-age=0');
    // Belt and braces against an intermediary caching ciphertext under a URL a
    // second reader could replay. It is ciphertext, and it still should not sit
    // in a shared cache.
    $resp->header('Pragma', 'no-cache');
    return $resp;
}
