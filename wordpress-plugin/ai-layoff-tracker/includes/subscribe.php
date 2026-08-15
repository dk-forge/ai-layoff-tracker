<?php
/**
 * Email digest subscriptions, for BOTH trackers.
 *
 * ONE subscriber list, owned by this plugin, because both plugins run on the
 * same WordPress install and two consent stores for one person is how consent
 * records drift apart. The Talent Intelligence Tracker prints the same form
 * through the guarded render function (function_exists, never a require, so a
 * missing sibling can never fatal either plugin).
 *
 * This is the site's FIRST feature that stores personal data (an email
 * address), so the privacy posture is part of the design, not decoration:
 *
 *   - DOUBLE OPT-IN, no exceptions. A signup stores status=pending and emails
 *     one confirmation link. Nothing else is EVER sent to an unconfirmed
 *     address. The confirm link flips status to confirmed.
 *   - Every email carries a one-click unsubscribe link, token-based, working
 *     without any login, plus List-Unsubscribe / List-Unsubscribe-Post
 *     headers. One click unsubscribes from everything.
 *   - Tokens come from random_bytes() and are compared with hash_equals().
 *     The email address itself NEVER appears in a URL.
 *   - No tracking pixels and no images, deliberately. We cannot tell whether
 *     you opened the email, on purpose: open tracking needs a per-person image
 *     URL, which is the individual-level record we promised not to keep.
 *   - Link clicks are counted in AGGREGATE only: one integer per (send, link),
 *     with no subscriber id, no IP and no user agent stored. The counter
 *     cannot say who clicked, only how many times a link was followed. See
 *     the "Aggregate click counting" section for the full reasoning.
 *   - Retention is bounded: unsubscribed rows and never-confirmed pending
 *     rows are HARD-DELETED after 30 days by the same cron that sends.
 *   - Logs and health output carry COUNTS only, never an address.
 *
 * The "articles" checkbox records consent and nothing more: no mechanism to
 * write or send articles exists yet, so nothing is sent under that consent.
 * Recording it now means we will not have to re-ask when articles exist.
 */

if (!defined('ABSPATH')) exit;

/* ------------------------------------------------------------------ */
/* Store                                                               */
/* ------------------------------------------------------------------ */

function alt_subscribers_table() {
    global $wpdb;
    return $wpdb->prefix . 'alt_subscribers';
}

/** Retention window for unsubscribed + never-confirmed rows, in days. */
if (!defined('ALT_DIGEST_RETENTION_DAYS')) define('ALT_DIGEST_RETENTION_DAYS', 30);

/**
 * Same self-heal guard as alt_source_runs_table_ready(): an FTP deploy can
 * serve a request before dbDelta created the table, so writers verify first.
 */
function alt_subscribers_table_ready() {
    global $wpdb;
    $table = alt_subscribers_table();
    $exists = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table)));
    if ($exists === $table) return true;
    if (function_exists('alt_db_install')) alt_db_install();
    return $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table;
}

function alt_digest_sends_table() {
    global $wpdb;
    return $wpdb->prefix . 'alt_digest_sends';
}

function alt_digest_links_table() {
    global $wpdb;
    return $wpdb->prefix . 'alt_digest_links';
}

/**
 * Does a table exist, WITHOUT trying to create it? The readiness helper above
 * self-heals for WRITERS. Readers (the stats route) must not: a read that
 * quietly installs a table would turn "we cannot see the numbers" into "the
 * numbers are all zero", and those are different answers. Absent table ->
 * UNKNOWN, all the way out to ops_status and the weekly email.
 */
function alt_digest_table_present($table) {
    global $wpdb;
    return $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table;
}

/**
 * 64 hex chars of real randomness. Deliberately NOT derived from the email,
 * the time, or anything an outsider can reconstruct: a guessable token would
 * let a stranger confirm or unsubscribe an address they do not own.
 */
function alt_digest_new_token() {
    return bin2hex(random_bytes(32));
}

/** The three consent flags and their per-flag frequency columns. */
function alt_digest_lists() {
    return array(
        'layoff'   => array('consent' => 'consent_layoff',   'freq' => 'freq_layoff'),
        'talent'   => array('consent' => 'consent_talent',   'freq' => 'freq_talent'),
        'articles' => array('consent' => 'consent_articles', 'freq' => 'freq_articles'),
    );
}

function alt_digest_valid_freq($f) {
    return in_array($f, array('daily', 'weekly'), true) ? $f : 'weekly';
}

/**
 * The window a row must not already have been sent inside, in seconds.
 *
 * Slightly under the nominal period on purpose. A job that ran at 13:00:04
 * yesterday and 12:59:58 today is the same daily cadence, and a strict 24
 * hours would silently skip that person every other day.
 */
function alt_digest_period_seconds($freq) {
    return $freq === 'daily' ? 20 * HOUR_IN_SECONDS : 6 * DAY_IN_SECONDS;
}

/**
 * Who is due for this tier, as ONE definition used by BOTH senders.
 *
 * Confirmed, consented to a list at this frequency, and not already sent to
 * inside the current period. That last clause is what makes two senders safe:
 * the built in wp_mail cron and the external relay (includes/digest-api.php)
 * read this same function, so even if both ran in the same minute nobody
 * receives two copies. A row is due, is sent, is stamped, and is then not due.
 *
 * A 'bounced' row is not confirmed, so a dead mailbox drops out here without
 * any sender needing to know the concept exists.
 */
function alt_digest_due_rows($freq) {
    global $wpdb;
    $table = alt_subscribers_table();
    $cutoff = gmdate('Y-m-d H:i:s', time() - alt_digest_period_seconds($freq));
    return $wpdb->get_results($wpdb->prepare(
        "SELECT * FROM $table WHERE status = 'confirmed'
           AND ((consent_layoff = 1 AND freq_layoff = %s)
             OR (consent_talent = 1 AND freq_talent = %s))
           AND (last_sent_at IS NULL OR last_sent_at < %s)",
        $freq, $freq, $cutoff), ARRAY_A) ?: array();
}

function alt_digest_get_by_email($email) {
    global $wpdb;
    return $wpdb->get_row($wpdb->prepare(
        'SELECT * FROM ' . alt_subscribers_table() . ' WHERE email = %s', $email), ARRAY_A);
}

/**
 * Look a row up by token column. The indexed SELECT narrows to a candidate;
 * hash_equals() then does the actual accept/reject in constant time.
 */
function alt_digest_get_by_token($column, $token) {
    global $wpdb;
    if (!in_array($column, array('confirm_token', 'unsub_token'), true)) return null;
    if (!is_string($token) || !preg_match('/^[a-f0-9]{64}$/', $token)) return null;
    $row = $wpdb->get_row($wpdb->prepare(
        'SELECT * FROM ' . alt_subscribers_table() . " WHERE $column = %s", $token), ARRAY_A);
    if (!$row || !is_string($row[$column] ?? null)) return null;
    if (!hash_equals($row[$column], $token)) return null;
    return $row;
}

/* ------------------------------------------------------------------ */
/* The form (rendered on both tracker pages)                           */
/* ------------------------------------------------------------------ */

/**
 * Render the subscription form. The Talent plugin calls this through
 * function_exists(), so the signature must stay stable.
 *
 * Consent hygiene rules embodied here:
 *   - every checkbox starts UNTICKED; nothing is pre-consented;
 *   - the copy states what you get, that one click unsubscribes, and links
 *     the privacy note;
 *   - submitting with zero boxes ticked is refused politely server-side.
 */
function alt_digest_subscribe_form($context = '') {
    $notice = isset($_GET['alt_dg']) ? sanitize_key($_GET['alt_dg']) : '';
    $messages = array(
        'check'        => array('ok',  'Almost done. We sent you one email with a confirmation link. Nothing is sent until you click it.'),
        'confirmed'    => array('ok',  'Your subscription is confirmed. The next digest will include you.'),
        'updated'      => array('ok',  'Your updated choices are confirmed.'),
        'unsubscribed' => array('ok',  'You are unsubscribed from everything. We delete your address within 30 days.'),
        'lists'        => array('err', 'Pick at least one list before subscribing.'),
        'email'        => array('err', 'That email address does not look right. Please check it and try again.'),
        'rate'         => array('err', 'Too many signups from this connection. Please try again in an hour.'),
        'expired'      => array('err', 'That link has already been used or has expired. Subscribing again sends a fresh one.'),
        'spam'         => array('err', 'That looked like an automated submission. Please try again.'),
        'mail'         => array('err', 'The confirmation email could not be sent. Please try again later.'),
    );
    ob_start();
    ?>
    <?php /* Self-carried styles: this form renders on BOTH tracker pages and
             the talent page does not load this plugin's stylesheet, so the
             component may depend on nothing outside itself (the honeypot in
             particular must be hidden everywhere). Mobile-safe: the email row
             wraps, nothing bleeds horizontally. */ ?>
    <style>
    .alt-digest { margin: 40px 0; padding: 20px; border: 1px solid var(--alt-border); border-radius: 12px; }
    .alt-digest h2 { margin: 0 0 8px; }
    /* !important, and it is not decoration. Both trackers render inside a
       theme that sets `.entry-content p { font-size:1.05rem !important;
       line-height:1.78 !important; margin-bottom:1.2rem !important }`, so
       this paragraph shipped at 16.8px on a 29.9px line and this rule was
       being ignored. On a 375px screen that is eleven lines and 348px of the
       first thing a reader sees after arriving here from the hero button. At
       the size it always asked for, the email field lands on screen instead
       of ending 852px down an 812px screen, which is where it was measured
       before this rule started applying. Restoring the component's own
       intent, not shrinking it.

       The selector is `.alt-digest p.alt-digest-intro` and the extra element
       is load-bearing: !important alone loses here, because between two
       !important declarations specificity still decides and `.entry-content
       p` (0,1,1) outranks `.alt-digest-intro` (0,1,0). The first attempt at
       this fix moved the paragraph by exactly zero pixels. */
    .alt-digest p.alt-digest-intro { margin: 0 0 12px !important; font-size: 14px !important; line-height: 1.55 !important; }
    .alt-digest-form fieldset { border: none; margin: 0 0 12px; padding: 0; }
    .alt-digest-form legend { font-weight: 600; margin-bottom: 6px; padding: 0; }
    .alt-digest-lists label { display: block; margin: 4px 0; font-size: 14px; }
    .alt-digest-freq label { margin-right: 16px; font-size: 14px; }
    .alt-digest-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .alt-digest-row label { font-weight: 600; flex-basis: 100%; margin: 0; }
    .alt-digest-row input[type="email"] { flex: 1 1 220px; min-width: 0; padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px; }
    .alt-digest-status { border: 1px solid var(--alt-tint-border); background: var(--alt-ok-bg); color: var(--alt-ok-ink); border-radius: 10px; padding: 10px 12px; margin: 0 0 12px; font-size: 14px; }
    .alt-digest-status-error { border-color: var(--alt-crit-border); background: var(--alt-red-tint); color: var(--alt-crit); }
    .alt-digest-privacy { margin-top: 14px; font-size: 13px; }
    .alt-digest-privacy p { margin: 8px 0; }
    /* THE LANDING BUDGET ON A PHONE. Both trackers now carry a hero button
       that jumps here, and a jump that puts the email field below the fold is
       the defect wearing the fix's clothes (the press page's own jump menu
       ended 847px down an 812px screen and shipped as a fix). At 375x812 the
       heading, the field and the Subscribe button have 720px between them,
       once the 92px anchor offset is paid. Without these the Subscribe button
       ended 809.7px down that 812px screen: it fitted, by 2.3px, which is
       "it fits until somebody adds a word". With them the email row stops
       wrapping and the whole signup ends 741.7px down, with 70px to spare. */
    @media (max-width: 560px) {
        .alt-digest { padding: 14px; }
        .alt-digest-form fieldset { margin-bottom: 10px; }
        .alt-digest-lists label { margin: 3px 0; }
        .alt-digest-privacy { margin-top: 12px; }
    }
    </style>
    <section class="alt-digest" id="alt-digest">
        <h2>Email digest</h2>
        <?php if ($notice && isset($messages[$notice])) : ?>
            <div class="alt-digest-status <?php echo $messages[$notice][0] === 'err' ? 'alt-digest-status-error' : ''; ?>"
                 role="<?php echo $messages[$notice][0] === 'err' ? 'alert' : 'status'; ?>">
                <?php echo esc_html($messages[$notice][1]); ?>
            </div>
        <?php endif; ?>
        <p class="alt-digest-intro">A plain email summary of what changed on these trackers: the period's
            headline numbers and the largest new entries, with links back to the source pages. No images,
            no tracking pixels. You confirm your address by clicking a link we email you, and every email
            carries a one-click unsubscribe. Details in the <a href="#alt-digest-privacy">privacy note</a> below.</p>
        <form class="alt-digest-form" method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
            <input type="hidden" name="action" value="alt_digest_subscribe">
            <?php wp_nonce_field('alt_digest_subscribe', 'alt_digest_nonce'); ?>
            <input type="hidden" name="alt_ts" value="<?php echo esc_attr(time()); ?>">
            <?php /* honeypot: humans never see or fill this */ ?>
            <div aria-hidden="true" style="position:absolute;left:-9999px;top:-9999px;height:1px;width:1px;overflow:hidden;"><label>Website<input type="text" name="alt_website" tabindex="-1" autocomplete="off"></label></div>

            <fieldset class="alt-digest-lists">
                <legend>What would you like?</legend>
                <?php /* All three start unticked, always. Pre-ticked consent is not consent. */ ?>
                <label><input type="checkbox" name="alt_list_layoff" value="1">
                    AI Layoff Tracker digest: verified layoffs, headline totals, largest new entries.</label>
                <label><input type="checkbox" name="alt_list_talent" value="1">
                    Talent Intelligence Tracker digest: hiring, leadership and compensation signals.</label>
                <label><input type="checkbox" name="alt_list_articles" value="1">
                    Occasional articles and product news.</label>
            </fieldset>

            <fieldset class="alt-digest-freq">
                <legend>How often for the digests?</legend>
                <label><input type="radio" name="alt_freq" value="weekly" checked> Weekly</label>
                <label><input type="radio" name="alt_freq" value="daily"> Daily</label>
            </fieldset>

            <div class="alt-digest-row">
                <label for="alt-digest-email">Your email</label>
                <input type="email" id="alt-digest-email" name="alt_email" required maxlength="190"
                       autocomplete="email" placeholder="you@example.com">
                <button type="submit" class="alt-btn alt-btn-primary" style="padding:8px 18px;border-radius:8px;cursor:pointer;">Subscribe</button>
            </div>
        </form>

        <details class="alt-digest-privacy" id="alt-digest-privacy">
            <summary>Privacy note: what we store and how to erase it</summary>
            <p><strong>What we store:</strong> your email address, the choices above, and timestamps
                (signed up, confirmed, last sent). Nothing else about you. There is no open tracking
                and no tracking pixel, so we cannot tell whether you opened an email.</p>
            <p><strong>About the links:</strong> links in the digest pass through a counter on this
                site that adds 1 to a total for that link and sends you straight on. It records no
                identifier, no IP address and no browser details, so it counts how many times a link
                was followed and can never say who followed it.</p>
            <p><strong>What it is used for:</strong> sending you exactly the emails you ticked, nothing
                else. The address is never shared, sold, or used for any other purpose.</p>
            <p><strong>How to erase it:</strong> click the unsubscribe link in any email. That stops all
                sending immediately, and unsubscribed addresses, along with signups that were never
                confirmed, are hard-deleted automatically after <?php echo (int) ALT_DIGEST_RETENTION_DAYS; ?> days.
                You can also ask via the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>.</p>
        </details>
    </section>
    <?php
    return ob_get_clean();
}
add_shortcode('alt_digest_subscribe', 'alt_digest_subscribe_form');

/* ------------------------------------------------------------------ */
/* Signup handler                                                      */
/* ------------------------------------------------------------------ */

function alt_digest_back_url() {
    $back = wp_get_referer() ?: home_url('/ai-layoff-tracker/');
    return remove_query_arg(array('alt_dg'), $back);
}

function alt_digest_redirect($code) {
    wp_safe_redirect(add_query_arg('alt_dg', $code, alt_digest_back_url()) . '#alt-digest');
    exit;
}

function alt_digest_subscribe_submit() {
    $fail = function ($code) { alt_digest_redirect($code); };

    if (!isset($_POST['alt_digest_nonce']) || !wp_verify_nonce($_POST['alt_digest_nonce'], 'alt_digest_subscribe')) {
        $fail('expired');
    }
    // Honeypot filled or submitted inhumanly fast: a bot.
    if (!empty($_POST['alt_website'])) $fail('spam');
    $ts = (int) ($_POST['alt_ts'] ?? 0);
    if (!$ts || (time() - $ts) < 3) $fail('spam');

    // Per-IP rate limit, same pattern as the contact form: 5 signups/hour.
    $ip = sanitize_text_field($_SERVER['REMOTE_ADDR'] ?? '');
    $rate_key = 'alt_digest_rate_' . md5($ip);
    $count = (int) get_transient($rate_key);
    if ($count >= 5) $fail('rate');
    set_transient($rate_key, $count + 1, HOUR_IN_SECONDS);

    $email = sanitize_email(wp_unslash($_POST['alt_email'] ?? ''));
    if (!is_email($email)) $fail('email');

    $prefs = alt_digest_prefs_from_post($_POST);
    if ($prefs === null) $fail('lists');   // zero boxes ticked: politely refused

    $ok = alt_digest_signup($email, $prefs);
    $fail($ok ? 'check' : 'mail');
}
add_action('admin_post_alt_digest_subscribe', 'alt_digest_subscribe_submit');
add_action('admin_post_nopriv_alt_digest_subscribe', 'alt_digest_subscribe_submit');

/**
 * Consent flags + frequency out of a submitted form. Returns null when no
 * list is ticked: subscribing to nothing is refused, not silently stored.
 */
function alt_digest_prefs_from_post($post) {
    $freq = alt_digest_valid_freq(sanitize_key($post['alt_freq'] ?? 'weekly'));
    $prefs = array(
        'consent_layoff'   => empty($post['alt_list_layoff']) ? 0 : 1,
        'consent_talent'   => empty($post['alt_list_talent']) ? 0 : 1,
        'consent_articles' => empty($post['alt_list_articles']) ? 0 : 1,
        'freq_layoff'      => $freq,
        'freq_talent'      => $freq,
        'freq_articles'    => $freq,
    );
    if (!$prefs['consent_layoff'] && !$prefs['consent_talent'] && !$prefs['consent_articles']) {
        return null;
    }
    return $prefs;
}

/**
 * Store a signup and send THE ONE email a pending address may receive: the
 * confirmation. Three cases:
 *
 *   new address              -> insert status=pending, send confirm
 *   pending / unsubscribed   -> overwrite prefs, fresh token, back to pending,
 *                               resend confirm (throttled per address)
 *   already confirmed        -> the stored prefs DO NOT change yet. The new
 *                               prefs are parked in pending_prefs and applied
 *                               only when THIS confirm link is clicked, so a
 *                               stranger typing your address cannot silently
 *                               alter (or kill) what you receive.
 */
function alt_digest_signup($email, array $prefs) {
    global $wpdb;
    if (!alt_subscribers_table_ready()) return false;
    $table = alt_subscribers_table();
    $now = gmdate('Y-m-d H:i:s');
    $row = alt_digest_get_by_email($email);
    $confirm = alt_digest_new_token();

    if (!$row) {
        $wpdb->insert($table, array_merge($prefs, array(
            'email'         => $email,
            'status'        => 'pending',
            'confirm_token' => $confirm,
            'unsub_token'   => alt_digest_new_token(),
            'created_at'    => $now,
        )));
    } elseif ($row['status'] === 'confirmed') {
        $wpdb->update($table, array(
            'pending_prefs' => wp_json_encode($prefs),
            'confirm_token' => $confirm,
        ), array('id' => $row['id']));
    } else {
        $wpdb->update($table, array_merge($prefs, array(
            'status'          => 'pending',
            'confirm_token'   => $confirm,
            'unsubscribed_at' => null,
        )), array('id' => $row['id']));
    }

    // Per-address resend throttle so the form cannot be used to bombard a
    // third party with confirmation mail. Keyed by hash, never the address.
    $throttle = 'alt_digest_confirm_' . md5($email);
    if (get_transient($throttle)) return true;   // stored fine; mail already on its way
    set_transient($throttle, 1, 15 * MINUTE_IN_SECONDS);

    $fresh = alt_digest_get_by_email($email);
    return alt_digest_send_confirm_email($email, $confirm, $fresh ? $fresh['unsub_token'] : '');
}

/* ------------------------------------------------------------------ */
/* Confirm + unsubscribe (token links, no login, email never in a URL) */
/* ------------------------------------------------------------------ */

function alt_digest_confirm_url($token) {
    return add_query_arg(array('action' => 'alt_digest_confirm', 't' => $token), admin_url('admin-post.php'));
}

function alt_digest_unsub_url($token) {
    return add_query_arg(array('action' => 'alt_digest_unsub', 't' => $token), admin_url('admin-post.php'));
}

function alt_digest_confirm() {
    global $wpdb;
    $token = (string) ($_REQUEST['t'] ?? '');
    $row = alt_digest_get_by_token('confirm_token', $token);
    if (!$row) alt_digest_redirect('expired');   // used, expired, or guessed

    $update = array(
        'confirm_token' => null,                  // single use
        'confirmed_at'  => gmdate('Y-m-d H:i:s'),
        'status'        => 'confirmed',
    );
    $was_change = false;
    if ($row['status'] === 'confirmed' && !empty($row['pending_prefs'])) {
        $parked = json_decode((string) $row['pending_prefs'], true);
        if (is_array($parked)) {
            foreach (alt_digest_lists() as $cols) {
                if (isset($parked[$cols['consent']])) $update[$cols['consent']] = (int) $parked[$cols['consent']];
                if (isset($parked[$cols['freq']]))    $update[$cols['freq']] = alt_digest_valid_freq($parked[$cols['freq']]);
            }
        }
        $update['pending_prefs'] = null;
        $was_change = true;
    }
    $wpdb->update(alt_subscribers_table(), $update, array('id' => $row['id']));
    alt_digest_redirect($was_change ? 'updated' : 'confirmed');
}
add_action('admin_post_alt_digest_confirm', 'alt_digest_confirm');
add_action('admin_post_nopriv_alt_digest_confirm', 'alt_digest_confirm');

/**
 * One click, everything stops. IDEMPOTENT: the same link clicked twice (or a
 * mail client prefetching it after the first click) lands on the same
 * confirmation, never an error. The token stays valid so links in older
 * emails keep working until the purge deletes the row.
 *
 * Serves both the human GET from the email footer and the mailbox provider's
 * RFC 8058 one-click POST (List-Unsubscribe-Post).
 */
function alt_digest_unsubscribe() {
    global $wpdb;
    $token = (string) ($_REQUEST['t'] ?? '');
    $row = alt_digest_get_by_token('unsub_token', $token);
    if ($row && $row['status'] !== 'unsubscribed') {
        $wpdb->update(alt_subscribers_table(), array(
            'status'          => 'unsubscribed',
            'unsubscribed_at' => gmdate('Y-m-d H:i:s'),
            'pending_prefs'   => null,
            'confirm_token'   => null,
        ), array('id' => $row['id']));
    }
    if (!$row) alt_digest_redirect('expired');
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
        // RFC 8058 one-click: a mailbox provider POSTs; no redirect wanted.
        status_header(200);
        echo 'Unsubscribed.';
        exit;
    }
    alt_digest_redirect('unsubscribed');
}
add_action('admin_post_alt_digest_unsub', 'alt_digest_unsubscribe');
add_action('admin_post_nopriv_alt_digest_unsub', 'alt_digest_unsubscribe');

/* ------------------------------------------------------------------ */
/* Mail                                                                */
/* ------------------------------------------------------------------ */

function alt_digest_from_header() {
    return array();   // wp_mail defaults; kept as a hook point for a From: override
}

/**
 * The ONLY email a pending address ever receives.
 */
function alt_digest_send_confirm_email($email, $confirm_token, $unsub_token) {
    $confirm_url = alt_digest_confirm_url($confirm_token);
    $body = "You (or someone typing your address) asked for the email digest at asktherecruiter.com.\n\n"
          . "Confirm by clicking this link:\n\n"
          . $confirm_url . "\n\n"
          . "Nothing is sent until you confirm. If you did not request this, ignore this email: "
          . "the signup is deleted automatically after " . ALT_DIGEST_RETENTION_DAYS . " days.\n";
    $headers = alt_digest_from_header();
    if ($unsub_token !== '') {
        $body .= "\nAlready changed your mind? One click stops everything:\n" . alt_digest_unsub_url($unsub_token) . "\n";
        $headers = array_merge($headers, alt_digest_list_unsub_headers($unsub_token));
    }
    return wp_mail($email, 'Confirm your tracker digest subscription', $body, $headers);
}

function alt_digest_list_unsub_headers($unsub_token) {
    return array(
        'List-Unsubscribe: <' . alt_digest_unsub_url($unsub_token) . '>',
        'List-Unsubscribe-Post: List-Unsubscribe=One-Click',
    );
}

/* ------------------------------------------------------------------ */
/* Aggregate click counting (counts only, and no open-rate pixel)      */
/* ------------------------------------------------------------------ */

/**
 * WHY THERE IS NO OPEN-RATE PIXEL, AND WHY THERE NEVER WILL BE.
 *
 * Open tracking needs a per-person image URL, which means the thing we told
 * every subscriber we do not have: a record tying an individual address to an
 * individual action. It is also not a measurement. Roughly half of inboxes
 * (Apple Mail Privacy Protection, Gmail's image proxy, most corporate
 * scanners) fetch remote images before a human sees the message, so an "open
 * rate" is part readers and part machines with no way to separate them, and
 * the number moves when a mail client updates rather than when interest does.
 *
 * So this file measures three things that are facts: how many messages we
 * DELIVERED (the send log), how many times a link was FOLLOWED (the counter
 * below), and how many people UNSUBSCRIBED after a send. A future session that
 * wants engagement numbers should improve those three, not add a pixel.
 *
 * The counter itself is aggregate by construction: one integer per
 * (send_id, link). No subscriber id, no IP, no user agent, no per-click row.
 * Two identical clicks and two different people clicking are the same event
 * to this store, which is the point.
 */

/**
 * Hosts a digest link may point at. Our own site only. Everything the digest
 * links to is built from home_url(), so this list is the whole world the
 * redirect can reach; the filter exists for a future first-party subdomain,
 * not for third parties.
 */
function alt_digest_link_hosts() {
    $hosts = array();
    $home = wp_parse_url(home_url('/'), PHP_URL_HOST);
    if (is_string($home) && $home !== '') {
        $hosts[] = strtolower($home);
        // Accept the www/non-www sibling of our own host, nothing else.
        $hosts[] = strpos($home, 'www.') === 0
            ? strtolower(substr($home, 4)) : 'www.' . strtolower($home);
    }
    $hosts = apply_filters('alt_digest_link_hosts', $hosts);
    return array_values(array_unique(array_filter(array_map('strtolower', (array) $hosts))));
}

/**
 * The open-redirect guard, and the only place a destination is judged.
 *
 * A link counter that will forward a visitor anywhere is a phishing relay
 * wearing our domain name, and that is strictly worse than having no counter:
 * the abuse is served from a URL readers have been taught to trust. So the
 * destination must be an absolute http(s) URL on one of OUR hosts, with no
 * credentials in it (https://ourhost@evil.example is a classic bypass, and
 * wp_parse_url reads the host correctly, but a stored URL carrying a user or
 * pass has no legitimate reason to exist here). Checked when the link is
 * STORED at compose time, and checked AGAIN when it is redeemed, so a row that
 * somehow reached the table by another path still cannot be followed.
 */
function alt_digest_link_allowed($url) {
    if (!is_string($url) || $url === '' || strlen($url) > 600) return false;
    $parts = wp_parse_url($url);
    if (!is_array($parts)) return false;
    if (!isset($parts['scheme']) || !in_array(strtolower($parts['scheme']), array('http', 'https'), true)) return false;
    if (isset($parts['user']) || isset($parts['pass'])) return false;
    if (empty($parts['host'])) return false;
    return in_array(strtolower($parts['host']), alt_digest_link_hosts(), true);
}

function alt_digest_link_hash($url) {
    return md5((string) $url);
}

function alt_digest_click_url($send_id, $url) {
    return add_query_arg(
        array('s' => (int) $send_id, 'l' => alt_digest_link_hash($url)),
        rest_url('layoffs/v1/click')
    );
}

/**
 * Register a link for a send and return the first-party URL to put in the
 * email. A destination that fails the guard is NOT wrapped and NOT stored: the
 * reader gets the plain link, so a counting decision can never break or
 * relocate a link. Returns the original URL when the tables are not there yet.
 */
function alt_digest_track_link($send_id, $url) {
    global $wpdb;
    $send_id = (int) $send_id;
    if ($send_id <= 0 || !alt_digest_link_allowed($url)) return $url;
    if (!alt_digest_table_present(alt_digest_links_table())) return $url;
    $wpdb->query($wpdb->prepare(
        'INSERT IGNORE INTO ' . alt_digest_links_table() .
        ' (send_id, link_hash, url, clicks) VALUES (%d, %s, %s, 0)',
        $send_id, alt_digest_link_hash($url), $url));
    return alt_digest_click_url($send_id, $url);
}

/**
 * Redirect handler. Takes an id and a hash, never a URL: there is no parameter
 * a caller can put a destination into. The destination comes out of the row we
 * wrote ourselves, is re-validated, and is emitted through wp_safe_redirect,
 * which is a third independent gate on the host.
 */
function alt_api_digest_click($request) {
    global $wpdb;
    $home = home_url('/');
    $send_id = (int) $request->get_param('s');
    $hash = (string) $request->get_param('l');
    if ($send_id <= 0 || !preg_match('/^[a-f0-9]{32}$/', $hash)) {
        wp_safe_redirect($home, 302);
        exit;
    }
    if (!alt_digest_table_present(alt_digest_links_table())) {
        wp_safe_redirect($home, 302);
        exit;
    }
    $row = $wpdb->get_row($wpdb->prepare(
        'SELECT id, url FROM ' . alt_digest_links_table() .
        ' WHERE send_id = %d AND link_hash = %s', $send_id, $hash), ARRAY_A);
    // Unknown pair, or a stored destination that no longer passes the host
    // guard: go home. Never echo the parameter back, never follow it.
    $url = ($row && alt_digest_link_allowed($row['url'])) ? $row['url'] : $home;

    // Rate limit the COUNTER, not the reader. The destination is always one of
    // our own pages, so refusing to redirect would only break a real reader's
    // link while doing nothing for abuse; what is worth protecting is the
    // number. Above the ceiling the visit still lands, uncounted. The key is a
    // hash of the address in a transient that expires, exactly as the signup
    // limiter does; nothing about the visitor reaches the click store.
    if ($row && $url !== $home) {
        $ip = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
        $key = 'alt_digest_click_' . md5($ip);
        $hits = (int) get_transient($key);
        set_transient($key, $hits + 1, 5 * MINUTE_IN_SECONDS);
        if ($hits < 60) {
            $wpdb->query($wpdb->prepare(
                'UPDATE ' . alt_digest_links_table() . ' SET clicks = clicks + 1 WHERE id = %d',
                (int) $row['id']));
        }
    }
    wp_safe_redirect($url, 302);
    exit;
}

/* ------------------------------------------------------------------ */
/* Digest composition (reads the trackers' own public APIs)            */
/* ------------------------------------------------------------------ */

/**
 * Compose the layoff-tracker section for the period. Reads the plugin's own
 * public /aggregate endpoint through the REST layer (rest_do_request), so the
 * digest can never disagree with what the tracker page itself serves.
 * Returns array('html' => ..., 'text' => ...) or null when there is nothing
 * to say (or the endpoint failed; a broken digest is worse than none).
 */
function alt_digest_compose_layoff($from, $to, $send_id = 0) {
    if (!function_exists('rest_do_request')) return null;
    $req = new WP_REST_Request('GET', '/layoffs/v1/aggregate');
    $req->set_param('from', $from);
    $req->set_param('to', $to);
    $req->set_param('include', 'leaders');
    $res = rest_do_request($req);
    if (!$res || $res->is_error()) return null;
    $data = $res->get_data();
    $totals = is_array($data) ? ($data['totals'] ?? null) : null;
    if (!is_array($totals) && is_object($totals)) $totals = (array) $totals;
    if (!$totals || (int) ($totals['entries'] ?? 0) === 0) return null;

    $url = home_url('/ai-layoff-tracker/');
    $jobs = number_format_i18n((int) ($totals['jobs'] ?? 0));
    $entries = number_format_i18n((int) ($totals['entries'] ?? 0));
    $companies = number_format_i18n((int) ($totals['companies'] ?? 0));
    $html = '<h2 style="font-size:16px;margin:24px 0 8px;">AI Layoff Tracker</h2>'
          . '<p style="margin:0 0 8px;">' . esc_html($entries) . ' verified entries totalling '
          . esc_html($jobs) . ' job cuts across ' . esc_html($companies) . ' companies in this period.</p>';
    $text = "AI Layoff Tracker\n{$entries} verified entries totalling {$jobs} job cuts across {$companies} companies in this period.\n";
    $leaders = array_slice(is_array($data['leaders'] ?? null) ? $data['leaders'] : array(), 0, 5);
    if ($leaders) {
        $html .= '<ul style="margin:0 0 8px;padding-left:20px;">';
        foreach ($leaders as $l) {
            $l = (array) $l;
            $line = ($l['company_name'] ?? '') . ': ' . number_format_i18n((int) ($l['job_count'] ?? 0)) . ' jobs'
                  . (!empty($l['location']) ? ', ' . $l['location'] : '');
            $html .= '<li>' . esc_html($line) . '</li>';
            $text .= '  - ' . $line . "\n";
        }
        $html .= '</ul>';
    }
    // Counted link. The plain URL stays in the text part: a text reader should
    // not be handed a machine-shaped URL to squint at, and one counted copy per
    // send is enough to know whether the section is read at all.
    $click = alt_digest_track_link($send_id, $url);
    $html .= '<p style="margin:0;"><a href="' . esc_url($click) . '">Open the AI Layoff Tracker</a></p>';
    $text .= "Open the tracker: {$url}\n";
    return array('html' => $html, 'text' => $text);
}

/**
 * Compose the talent-tracker section, again through the REST layer. The
 * talent plugin is a SEPARATE plugin on the same install; if it is inactive
 * its namespace does not resolve and this quietly returns null.
 */
function alt_digest_compose_talent($from, $to, $send_id = 0) {
    if (!function_exists('rest_do_request')) return null;
    $agg = new WP_REST_Request('GET', '/talent/v1/aggregate');
    $agg->set_param('since', $from);
    $agg->set_param('until', $to);
    $agg->set_param('include', 'fresh');
    $res = rest_do_request($agg);
    if (!$res || $res->is_error()) return null;
    $data = (array) $res->get_data();
    $total = (int) ($data['total'] ?? 0);
    if ($total === 0) return null;

    $url = home_url('/talent-intelligence-tracker/');
    $companies = number_format_i18n((int) ($data['companies'] ?? 0));
    $verified = number_format_i18n((int) ($data['verified'] ?? 0));
    $totalf = number_format_i18n($total);
    $html = '<h2 style="font-size:16px;margin:24px 0 8px;">Talent Intelligence Tracker</h2>'
          . '<p style="margin:0 0 8px;">' . esc_html($totalf) . ' new signals from ' . esc_html($companies)
          . ' companies in this period, ' . esc_html($verified) . ' verified against primary documents.</p>';
    $text = "Talent Intelligence Tracker\n{$totalf} new signals from {$companies} companies in this period, {$verified} verified against primary documents.\n";

    $q = new WP_REST_Request('GET', '/talent/v1/query');
    $q->set_param('since', $from);
    $q->set_param('until', $to);
    $q->set_param('per_page', 5);
    $qres = rest_do_request($q);
    if ($qres && !$qres->is_error()) {
        $qdata = (array) $qres->get_data();
        $rows = array_slice(is_array($qdata['rows'] ?? null) ? $qdata['rows'] : array(), 0, 5);
        if ($rows) {
            $html .= '<ul style="margin:0 0 8px;padding-left:20px;">';
            foreach ($rows as $row) {
                $row = (array) $row;
                $line = trim((string) ($row['company'] ?? ''));
                $head = trim((string) ($row['headline'] ?? ''));
                $line = $line !== '' ? ($head !== '' ? $line . ': ' . $head : $line) : $head;
                if ($line === '') continue;
                $html .= '<li>' . esc_html($line) . '</li>';
                $text .= '  - ' . $line . "\n";
            }
            $html .= '</ul>';
        }
    }
    $click = alt_digest_track_link($send_id, $url);
    $html .= '<p style="margin:0;"><a href="' . esc_url($click) . '">Open the Talent Intelligence Tracker</a></p>';
    $text .= "Open the tracker: {$url}\n";
    return array('html' => $html, 'text' => $text);
}

/* ------------------------------------------------------------------ */
/* Sending                                                             */
/* ------------------------------------------------------------------ */

/**
 * Send one frequency tier's digests. HARD RULE, tested: recipients are rows
 * with status='confirmed' AND the list's consent flag AND that flag's
 * frequency matching $freq. A pending or unsubscribed row can never match.
 *
 * Returns array(sent, recipients_considered) as counts. Never logs an address.
 */
function alt_digest_send($freq) {
    global $wpdb;
    $freq = alt_digest_valid_freq($freq);
    // An external relay claimed this tier recently, so it is the sender and
    // this one stands down. The claim ages out (ALT_DIGEST_CLAIM_HOURS), so a
    // relay that stops running hands sending back here by itself rather than
    // leaving the list silent. See includes/digest-api.php.
    if (function_exists('alt_digest_external_active') && alt_digest_external_active($freq)) {
        return array(0, 0);
    }
    if (!alt_subscribers_table_ready()) return array(0, 0);
    $table = alt_subscribers_table();

    $days = $freq === 'daily' ? 1 : 7;
    $to_date = gmdate('Y-m-d');
    $from_date = gmdate('Y-m-d', time() - $days * DAY_IN_SECONDS);

    // Open the send row BEFORE composing, because the counted links carry its
    // id. recipients is written at the end, from what actually went out, so a
    // run that dies mid-loop leaves a row that under-reports rather than one
    // that claims a delivery that never happened.
    $send_id = 0;
    if (alt_digest_table_present(alt_digest_sends_table())) {
        $wpdb->insert(alt_digest_sends_table(), array(
            'freq' => $freq, 'sent_at' => gmdate('Y-m-d H:i:s'),
            'recipients' => 0, 'eligible' => 0,
        ));
        $send_id = (int) $wpdb->insert_id;
    }

    // Compose each tracker's section ONCE per run, not per recipient.
    $sections = array(
        'layoff' => alt_digest_compose_layoff($from_date, $to_date, $send_id),
        'talent' => alt_digest_compose_talent($from_date, $to_date, $send_id),
        // 'articles' deliberately absent: that consent flag records intent
        // only. No article-writing mechanism exists, so nothing sends. Do not
        // add a sender here without an actual editorial pipeline behind it.
    );

    $rows = alt_digest_due_rows($freq);

    $label = $freq === 'daily' ? 'Daily' : 'Weekly';
    $sent = 0;
    foreach ($rows as $row) {
        $parts_html = array();
        $parts_text = array();
        foreach (array('layoff', 'talent') as $list) {
            $cols = alt_digest_lists()[$list];
            if ((int) $row[$cols['consent']] === 1 && $row[$cols['freq']] === $freq && $sections[$list]) {
                $parts_html[] = $sections[$list]['html'];
                $parts_text[] = $sections[$list]['text'];
            }
        }
        if (!$parts_html) continue;   // nothing to say to this person today

        $unsub = alt_digest_unsub_url($row['unsub_token']);
        // Text-first HTML: no images, no pixels, no external assets. See the
        // file header for why tracking is deliberately absent.
        $html = '<div style="font-family:sans-serif;max-width:600px;color:#1a1a1a;">'
              . implode('', $parts_html)
              . '<hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px;">'
              . '<p style="font-size:12px;color:#555;">You get this because you confirmed a digest '
              . 'subscription at asktherecruiter.com. '
              . '<a href="' . esc_url($unsub) . '">Unsubscribe with one click</a> (stops everything at once).</p>'
              . '</div>';
        $headers = array_merge(
            array('Content-Type: text/html; charset=UTF-8'),
            alt_digest_from_header(),
            alt_digest_list_unsub_headers($row['unsub_token'])
        );
        if (wp_mail($row['email'], '[AskTheRecruiter] ' . $label . ' tracker digest', $html, $headers)) {
            $sent++;
            $wpdb->update($table, array('last_sent_at' => gmdate('Y-m-d H:i:s')), array('id' => $row['id']));
        }
    }
    if ($send_id > 0) {
        // A run with no eligible recipient is not a send. Drop the row rather
        // than log a zero: "last digest sent to 0" would read as a delivery
        // failure when nothing was due to go out at all.
        if ($sent === 0 && !$rows) {
            $wpdb->query($wpdb->prepare(
                'DELETE FROM ' . alt_digest_sends_table() . ' WHERE id = %d', $send_id));
            if (alt_digest_table_present(alt_digest_links_table())) {
                $wpdb->query($wpdb->prepare(
                    'DELETE FROM ' . alt_digest_links_table() . ' WHERE send_id = %d', $send_id));
            }
        } else {
            $wpdb->update(alt_digest_sends_table(),
                array('recipients' => $sent, 'eligible' => count($rows)),
                array('id' => $send_id));
        }
    }
    return array($sent, count($rows));
}

/* ------------------------------------------------------------------ */
/* Purge (the erase promise, kept by a machine)                        */
/* ------------------------------------------------------------------ */

/**
 * Hard-delete what the privacy note says we delete:
 *   - unsubscribed rows older than the retention window (dated from the
 *     unsubscribe click), and
 *   - pending rows never confirmed within the window (dated from signup).
 * Confirmed rows are never touched. Returns the number of rows deleted.
 */
function alt_digest_purge() {
    global $wpdb;
    if (!alt_subscribers_table_ready()) return 0;
    $table = alt_subscribers_table();
    $cutoff = gmdate('Y-m-d H:i:s', time() - ALT_DIGEST_RETENTION_DAYS * DAY_IN_SECONDS);
    $n = 0;
    // 'bounced' is here with 'unsubscribed' deliberately. A mailbox the
    // provider says does not exist is an address we will never send to again,
    // so holding it past the retention window would keep personal data for no
    // purpose, which is the one thing the privacy note promises not to do.
    $n += (int) $wpdb->query($wpdb->prepare(
        "DELETE FROM $table WHERE status IN ('unsubscribed', 'bounced') AND unsubscribed_at IS NOT NULL AND unsubscribed_at < %s", $cutoff));
    $n += (int) $wpdb->query($wpdb->prepare(
        "DELETE FROM $table WHERE status = 'pending' AND confirmed_at IS NULL AND created_at < %s", $cutoff));
    return $n;
}

/* ------------------------------------------------------------------ */
/* Cron + health                                                       */
/* ------------------------------------------------------------------ */

/**
 * Daily driver. WP-Cron is TRAFFIC-DEPENDENT: it only fires when the site
 * gets a request, so on a quiet day the send can slip by hours. Both tracker
 * pages get steady crawler + reader traffic, so in practice it fires daily;
 * the health ceiling (3 days) is sized for that reality, not for a promise
 * WP-Cron cannot make.
 *
 * Weekly digests go out on Mondays (UTC) from this same daily hook, so there
 * is exactly one schedule to monitor.
 */
function alt_digest_cron_run() {
    list($sent_d, $recip_d) = alt_digest_send('daily');
    $sent_w = 0; $recip_w = 0;
    if (gmdate('N') === '1') {
        list($sent_w, $recip_w) = alt_digest_send('weekly');
    }
    $purged = alt_digest_purge();

    // Health: a mailer that silently stops mailing must not look healthy.
    // The row is stamped HERE, on COMPLETION of the send run, never before,
    // so a fatal mid-run leaves checked_at old and the staleness ceiling
    // (railway ops_status/health_digest, 3 days) turns it red. COUNTS ONLY:
    // no address ever enters health output or logs. Goes through the single
    // health writer (function_exists-guarded for the mid-FTP-upload race).
    if (function_exists('alt_source_health_record')) {
        alt_source_health_record('digest_mailer', 'ok', (int) ($sent_d + $sent_w),
            sprintf('daily: %d sent of %d eligible; weekly: %d sent of %d eligible; purged %d rows',
                    $sent_d, $recip_d, $sent_w, $recip_w, $purged));
    }
}
add_action('alt_digest_cron', 'alt_digest_cron_run');

/* ------------------------------------------------------------------ */
/* Stats (keyed, read only, counts only)                               */
/* ------------------------------------------------------------------ */

/**
 * Every number the owner's surfaces show about this list, as COUNTS.
 *
 * Two rules hold this function together:
 *
 *   1. No address, ever. There is no column selected here that holds one, no
 *      branch that returns one, and no error path that echoes one. The test
 *      asserts no '@' appears anywhere in the serialised payload.
 *   2. Absent table is UNKNOWN, not zero. On an install where the digest has
 *      not deployed yet, "0 subscribers" is a claim (nobody signed up) and it
 *      is false; the truth is that we cannot see. So a missing table returns
 *      available=false with every count null, and the readers downstream print
 *      UNKNOWN. This is the single most repeated lesson in this codebase.
 *
 * Rates are over rows we still HOLD. Unsubscribed and never-confirmed rows are
 * hard-deleted after ALT_DIGEST_RETENTION_DAYS (the erase promise), so the
 * confirm rate is a rate over the retained window, not over all time, and it
 * says so in the payload rather than pretending otherwise.
 */
function alt_digest_stats() {
    global $wpdb;
    $out = array(
        'available'  => false,
        'reason'     => 'the subscriber table does not exist on this install',
        'as_of'      => gmdate('c'),
        'confirmed'  => null,
        'pending'    => null,
        'unsubscribed' => null,
        'bounced'    => null,
        'signups_retained' => null,
        'confirm_rate' => null,
        'confirmed_last_7_days' => null,
        'frequency'  => null,
        'last_send'  => null,
        'open_tracking' => 'none',
        'basis'      => 'counts over retained rows; unsubscribed and never confirmed rows are '
                      . 'hard deleted after ' . (int) ALT_DIGEST_RETENTION_DAYS . ' days',
    );
    if (!alt_digest_table_present(alt_subscribers_table())) return $out;
    $subs = alt_subscribers_table();

    $out['available'] = true;
    $out['reason'] = '';
    $count = function ($where) use ($wpdb, $subs) {
        return (int) $wpdb->get_var("SELECT COUNT(*) FROM $subs WHERE $where");
    };
    $confirmed = $count("status = 'confirmed'");
    $out['confirmed'] = array(
        'total'    => $confirmed,
        'layoff'   => $count("status = 'confirmed' AND consent_layoff = 1"),
        'talent'   => $count("status = 'confirmed' AND consent_talent = 1"),
        'articles' => $count("status = 'confirmed' AND consent_articles = 1"),
    );
    $out['pending'] = $count("status = 'pending'");
    $out['unsubscribed'] = $count("status = 'unsubscribed'");
    // Counted apart from unsubscribed because they are different facts: one is
    // a person who asked us to stop, the other is a mailbox that does not
    // exist. Rolling them together would read as readers leaving.
    $out['bounced'] = $count("status = 'bounced'");
    $retained = (int) $wpdb->get_var("SELECT COUNT(*) FROM $subs");
    $out['signups_retained'] = $retained;
    $out['confirm_rate'] = $retained > 0 ? round($confirmed / $retained, 4) : null;

    $week_ago = gmdate('Y-m-d H:i:s', time() - 7 * DAY_IN_SECONDS);
    $out['confirmed_last_7_days'] = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COUNT(*) FROM $subs WHERE status = 'confirmed' AND confirmed_at >= %s", $week_ago));

    // Daily vs weekly over CONFIRMED rows. Frequency is stored per list, so a
    // row counts as daily when any list it consented to is set to daily. One
    // person is counted once either way, so the two add up to the confirmed
    // total and cannot double count someone who picked both trackers.
    $daily = $count("status = 'confirmed' AND ("
        . "(consent_layoff = 1 AND freq_layoff = 'daily') OR "
        . "(consent_talent = 1 AND freq_talent = 'daily') OR "
        . "(consent_articles = 1 AND freq_articles = 'daily'))");
    $out['frequency'] = array('daily' => $daily, 'weekly' => max(0, $confirmed - $daily));

    $out['last_send'] = alt_digest_last_send_stats();
    return $out;
}

/**
 * The last digest run: when, how many messages went out, how many link clicks
 * that send has drawn, and how many people unsubscribed in the 48 hours after
 * it. Returns null when the log exists but holds no send yet, which is a
 * different statement from "we cannot see" and is why the caller keeps
 * available=true around it.
 */
function alt_digest_last_send_stats() {
    global $wpdb;
    if (!alt_digest_table_present(alt_digest_sends_table())) return null;
    $row = $wpdb->get_row('SELECT id, freq, sent_at, recipients, eligible FROM '
        . alt_digest_sends_table() . ' ORDER BY sent_at DESC, id DESC LIMIT 1', ARRAY_A);
    if (!$row) return null;

    $clicks = null;
    if (alt_digest_table_present(alt_digest_links_table())) {
        $clicks = (int) $wpdb->get_var($wpdb->prepare(
            'SELECT COALESCE(SUM(clicks), 0) FROM ' . alt_digest_links_table()
            . ' WHERE send_id = %d', (int) $row['id']));
    }

    $unsubs = null;
    if (alt_digest_table_present(alt_subscribers_table())) {
        $until = gmdate('Y-m-d H:i:s', strtotime($row['sent_at'] . ' UTC') + 48 * 3600);
        $unsubs = (int) $wpdb->get_var($wpdb->prepare(
            'SELECT COUNT(*) FROM ' . alt_subscribers_table()
            . ' WHERE unsubscribed_at IS NOT NULL AND unsubscribed_at >= %s AND unsubscribed_at < %s',
            $row['sent_at'], $until));
    }

    return array(
        'send_id'          => (int) $row['id'],
        'freq'             => (string) $row['freq'],
        'sent_at'          => (string) $row['sent_at'],
        'recipients'       => (int) $row['recipients'],
        'eligible'         => (int) $row['eligible'],
        'clicks'           => $clicks,
        'unsubscribes_48h' => $unsubs,
    );
}

/**
 * Routes. /subscriber-stats is key gated exactly as /alert and
 * /press-subscribers are (alt_api_permission, X-Layoff-API-Key header, fails
 * closed when no key is configured). /click is public because a link in an
 * email cannot carry a key; its safety comes from taking no destination.
 */
function alt_digest_register_routes() {
    register_rest_route('layoffs/v1', '/subscriber-stats', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_subscriber_stats',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    register_rest_route('layoffs/v1', '/click', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_digest_click',
        'permission_callback' => '__return_true',
        'args'                => array(
            's' => array('required' => true),
            'l' => array('required' => true),
        ),
    ));
}
add_action('rest_api_init', 'alt_digest_register_routes');

function alt_api_subscriber_stats($request) {
    $res = new WP_REST_Response(alt_digest_stats(), 200);
    // Never cached at the edge: these are operational numbers read by a
    // session at the moment it asks, and a stale count read as current is the
    // same class of error as a zero read as UNKNOWN.
    $res->header('Cache-Control', 'no-store, max-age=0');
    return $res;
}

function alt_digest_cron_schedule() {
    if (!wp_next_scheduled('alt_digest_cron')) {
        // 13:00 UTC: morning US East, so a "daily" digest reads as today's.
        $first = strtotime('today 13:00 UTC');
        if ($first < time()) $first = strtotime('tomorrow 13:00 UTC');
        wp_schedule_event($first, 'daily', 'alt_digest_cron');
    }
}
add_action('init', 'alt_digest_cron_schedule');
