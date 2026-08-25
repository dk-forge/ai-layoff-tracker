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
 *   - THIS FILE embeds no tracking pixel and no image, and that has not
 *     changed. What DID change on 2026-08-16 is what happens after the
 *     message leaves us: the owner turned on open and click tracking at the
 *     mail provider, and Brevo injects its own pixel and rewrites links at
 *     the relay. So the provider CAN tell whether an email was opened, and we
 *     can read that. Every reader-facing string that used to promise
 *     otherwise has been corrected. Since 2.20.107 they are all DERIVED from
 *     ALT_RELAY_TRACKING below rather than typed, because they are coupled to
 *     a dashboard setting no code here can read, and four independent copies
 *     of an unverifiable claim is four chances to drift. Keep our own message
 *     clean anyway: it is what makes the tracking removable by changing
 *     provider rather than by unpicking templates, and
 *     assert_message_is_clean enforces it.
 *   - THE OWNER HAS DECIDED TO TURN THE RELAY'S TRACKING OFF (2026-08-19),
 *     for the open pixel's 2026 legal position in France and Italy and
 *     because Apple Mail Privacy Protection made the number meaningless. It
 *     cannot be done by halves: Brevo has no setting, no plan and no header
 *     that stops opens while keeping clicks, and that was researched rather
 *     than assumed. It costs no click data anyway, because every click figure
 *     here comes from alt_digest_track_link() below and never from Brevo.
 *     docs/RUNBOOK.md "Open and click tracking" holds the flip procedure, the
 *     evidence, and the design note for a future consent flow.
 *   - THE CONFIRMATION EMAIL IS MEASURED TOO, and that is the sharpest edge
 *     of the above. Measured 2026-08-17 on a real send: the received message
 *     carried Brevo's open pixel twice, injected at the relay. A digest goes
 *     to somebody who ticked a box; the confirmation goes to an address in
 *     status=pending, which by the design in THIS FILE has consented to
 *     nothing at all. So an open event is created against that address
 *     BEFORE permission exists, and it is created even for a person who
 *     never confirms. No test in this repo can see it: our own message
 *     embeds no image and assert_message_is_clean still passes, because the
 *     pixel is added after we hand the message over.
 *     It cannot be exempted from here, and that was checked rather than
 *     assumed. The confirmation goes out through wp_mail (see
 *     alt_digest_send_confirm_email), which the Brevo WordPress plugin
 *     replaces; that plugin exposes no per-message tracking control. Brevo's
 *     ONLY per-recipient control is `contactPixelTrackingConsent`, a field on
 *     the HTTP API call POST /v3/smtp/email, and neither of our two paths
 *     makes that call: the confirmation goes through the WP plugin and the
 *     digest goes over the SMTP relay (DIGEST_TRANSPORT=smtp), whose envelope
 *     has nowhere to put the field. Turning tracking off outright is an
 *     Enterprise-plan request on Brevo's side. So the only lever that exists
 *     today is account-wide, in the dashboard, and it would take the digest's
 *     deliberate measuring with it. The reader is therefore TOLD, in the
 *     signup form's privacy note, that this one message is measured before
 *     they have agreed to anything. docs/RUNBOOK.md "Open and click tracking"
 *     holds the options and what each one costs.
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
 * WHETHER THE MAIL RELAY MEASURES ANYTHING. The PHP twin of
 * railway/digest_layout.py RELAY_TRACKING_ON, and the ONLY place this side
 * says so. Every reader-facing string about measurement is derived from it,
 * as is the open_tracking field in the /subscriber-stats payload.
 *
 * ONE CONSTANT FOR OPENS AND CLICKS TOGETHER, WHICH LOOKS WRONG AND IS NOT.
 * Brevo cannot separate them. Researched against Brevo's help centre, its
 * OpenAPI spec and the WordPress plugin source on 2026-08-19: no setting, no
 * plan and no SMTP header disables the open pixel while leaving click
 * tracking on. The spec has no trackOpens and no clickTracking field at all;
 * the one tracking control in the whole API is `contactPixelTrackingConsent`,
 * documented as consent "for open (pixel) and click tracking". The relay
 * measures both or neither, so a constant per mechanism would model a state
 * that cannot exist.
 *
 * TURNING IT OFF COSTS NO CLICK DATA, and that was checked rather than
 * assumed. Nothing in this product has ever consumed a Brevo engagement
 * event: alt_digest_brevo_action() in digest-api.php maps opened,
 * unique_opened, proxy_open, unique_proxy_open and click to no action at all.
 * Every click figure we report comes from alt_digest_track_link() below,
 * a first-party counter applied at composition time, one integer per
 * (send_id, link), no subscriber id, no IP, no user agent. No provider
 * setting can reach it.
 *
 * IT IS A STATED BELIEF AND NOT A PASSING CHECK, exactly like its twin.
 * Nothing here can read the Brevo dashboard, so this can be wrong. What the
 * constant buys is that it can only be wrong ONCE. Before 2.20.107 the form
 * copy, the privacy note and the stats payload were three independent
 * hand-typed claims, and the 2026-08-16 change left the last of them
 * reporting open_tracking=none for three days while every send was measured.
 *
 * To change it: docs/RUNBOOK.md "Open and click tracking" holds the
 * procedure. The dashboard moves FIRST, this constant second, because
 * over-disclosing for an hour is safe and under-disclosing is the violation.
 */
if (!defined('ALT_RELAY_TRACKING')) define('ALT_RELAY_TRACKING', true);

/**
 * The always-visible sentence under the Subscribe button.
 *
 * The two facts that must survive any rewrite: what is recorded about a
 * reader, and that unsubscribing stops it. While the relay measures, a third
 * fact is owed, that the confirmation email is measured before the reader has
 * agreed to anything, because that message goes to a status=pending row. Once
 * the relay stops, that clause has nothing left to describe and must go: an
 * unconfirmed address is then never measured at all, and a warning about a
 * pixel nobody sends any more is its own kind of false.
 *
 * Keep it short. It sits below the Subscribe button precisely so it costs
 * the phone fold nothing, and railway/signup_fold.py is how you find out
 * what a rewrite costs. See docs/RUNBOOK.md "Open and click tracking".
 */
function alt_digest_tracking_line() {
    if (ALT_RELAY_TRACKING) {
        return 'Our mail provider records whether you open an email and which links '
             . 'you follow, including the confirmation email, which is measured before '
             . 'you have agreed to anything. Unsubscribing stops the sending and the '
             . 'recording together.';
    }
    return 'Our mail provider records nothing about how you read our emails, and adds '
         . 'no invisible image. Links pass through a counter on this site that stores '
         . 'no identifier and can never say who followed one. Unsubscribing stops the '
         . 'sending and the counting together.';
}

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
 * The column holding when this ONE tier last went out.
 *
 * THE DEFECT THIS ANSWERS, 2026-08-17. There was one column, last_sent_at,
 * and both tiers read it. Monday is the day both tiers send, so the first
 * pass stamped the row and the second pass found the same person already
 * sent to. A subscriber who takes the layoff list daily and the articles
 * list weekly then received one email on a Monday instead of two, and
 * nothing anywhere said so.
 *
 * The frequency is validated before it reaches the SQL, and the only two
 * values it can hold are named here, so no caller can steer this at a column
 * of its own choosing.
 */
function alt_digest_last_sent_column($freq) {
    return alt_digest_valid_freq($freq) === 'daily'
        ? 'last_sent_daily' : 'last_sent_weekly';
}

/**
 * Who is due for this tier, as ONE definition used by BOTH senders.
 *
 * Confirmed, consented to a list at this frequency, and not already sent to
 * inside THIS TIER'S current period. That last clause is what makes two
 * senders safe: the built in wp_mail cron and the external relay
 * (includes/digest-api.php) read this same function, so even if both ran in
 * the same minute nobody receives two copies. A row is due, is sent, is
 * stamped, and is then not due.
 *
 * Per tier, so the two passes of a Monday cannot suppress each other. The
 * tiers are separate subscriptions and each one keeps its own clock.
 *
 * A 'bounced' row is not confirmed, so a dead mailbox drops out here without
 * any sender needing to know the concept exists.
 */
function alt_digest_due_rows($freq) {
    global $wpdb;
    $table = alt_subscribers_table();
    $stamp = alt_digest_last_sent_column($freq);
    $cutoff = gmdate('Y-m-d H:i:s', time() - alt_digest_period_seconds($freq));
    return $wpdb->get_results($wpdb->prepare(
        "SELECT * FROM $table WHERE status = 'confirmed'
           AND ((consent_layoff = 1 AND freq_layoff = %s)
             OR (consent_talent = 1 AND freq_talent = %s)
             OR (consent_articles = 1 AND freq_articles = %s))
           AND ($stamp IS NULL OR $stamp < %s)",
        $freq, $freq, $freq, $cutoff), ARRAY_A) ?: array();
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
 * Where a signup is being rendered, and the one sentence that changes with it.
 *
 * $context has been a parameter of alt_digest_subscribe_form() since the form
 * was written and did nothing at all until 2026-08-15: the tracker passed
 * 'layoff' and the body never read it. It matters now because the signup no
 * longer renders only on the two tracker pages. A reader who arrived on an
 * article about resume length, or on one employer's history page, has not been
 * told what this site tracks, and the tracker's own intro ("what changed on
 * these trackers") assumes they were.
 *
 * So each context adds ONE plain sentence in front of the shared intro, saying
 * where the reader is in relation to the thing being offered. Nothing else
 * about the form varies: same lists, same consent, same route, same handler.
 * An unknown or empty context returns '', which is the tracker's own behaviour
 * and the safe default for any caller that has not been updated.
 */
function alt_digest_context_lead($context) {
    $leads = array(
        // The tracker pages say it themselves, at length, above the form.
        'layoff'  => '',
        'post'    => 'We also run a layoff tracker, built from company filings and official notices.',
        'company' => 'This employer is one part of a layoff record we keep and check.',
        'facet'   => 'This page is one slice of a layoff record we keep and check.',
        'entry'   => 'This entry is one row in a layoff record we keep and check.',
        // The archive page says at length what an edition is, directly
        // above this form, exactly as the tracker pages do. A lead here
        // would repeat it, and every lead is copy the phone-fold budget
        // pays for on the OTHER surfaces too (railway/signup_fold.py
        // hashes the longest one). So this list's entry is silence.
        'editions' => '',
    );
    return isset($leads[$context]) ? $leads[$context] : '';
}

/* ------------------------------------------------------------------ */
/* What a reader sees AFTER acting: the four terminal states           */
/* ------------------------------------------------------------------ */

/**
 * THE DEFECT THIS ANSWERS, 2026-08-16. The owner completed the double opt-in
 * for real: form, confirmation mail through Brevo, link click, address
 * confirmed. It worked, and the page he landed on printed "Your subscription
 * is confirmed" AND THEN THE WHOLE EMPTY SIGNUP FORM UNDERNEATH IT, with a
 * blank email field and a Subscribe button.
 *
 * To a person who has just subscribed, a blank subscribe form reads as "it did
 * not work, do it again". The ones who believe it submit twice, which parks a
 * new pending_prefs row and sends a second confirmation for an address that is
 * already confirmed. So the empty form is not only confusing, it manufactures
 * the exact traffic it looks like it is asking for.
 *
 * FOUR STATES REPLACE THE FORM rather than sitting above it, and they are the
 * four where showing the form again is an instruction to repeat something that
 * already succeeded:
 *
 *   check         we just emailed you. Submitting again sends nothing new
 *                 (the per-address resend throttle holds for 15 minutes) and
 *                 reads as though the first attempt failed.
 *   confirmed     you are subscribed. This is the one the owner hit.
 *   updated       same, with your changed choices applied.
 *   unsubscribed  everything has stopped. A Subscribe button under that
 *                 sentence is an invitation to undo an action on purpose.
 *
 * EVERY OTHER STATE KEEPS THE FORM, because every other state is a thing the
 * reader has to do again: a bad address, no list ticked, a rate limit, a
 * spam-trap hit, a mail failure, and a stale link.
 *
 * NOTHING ABOUT THE MECHANISM MOVES. Double opt-in is untouched, the tokens
 * are untouched, the handlers are untouched. This is what the page shows.
 */
function alt_digest_terminal_states() {
    return array('check', 'confirmed', 'updated', 'unsubscribed');
}

/**
 * The three lists, named the way a confirmation reads them back.
 *
 * Shorter than the sentences on the form's own checkboxes on purpose: a
 * checkbox has to say what you are agreeing to, and a receipt has to be
 * scannable. Same keys as alt_digest_lists(), which is what stops a list
 * existing in one place and not the other.
 */
function alt_digest_list_names() {
    return array(
        'layoff'   => 'AI Layoff Tracker digest',
        'talent'   => 'Talent Intelligence Tracker digest',
        'articles' => 'Occasional articles and product news',
    );
}

/**
 * HOW THE CONFIRMATION PAGE KNOWS WHAT THEY SUBSCRIBED TO, WITHOUT KNOWING WHO
 * THEY ARE.
 *
 * The confirm handler holds the row. The page it redirects to does not, and it
 * must not: the address may never travel in a URL (that is a guard in
 * railway/tests/test_digest_subscription.py) and there is no session here.
 *
 * So the handler leaves a RECEIPT: a random 64-hex token in the URL, and a
 * transient holding the three list flags, the frequency, and the row's
 * unsubscribe token so the panel can offer a working one-click link. Thirty
 * minutes, then it is gone.
 *
 * WHAT IS NOT IN IT: the address, the row id, and anything else that could
 * name a person. Someone who reads the URL out of a browser history learns
 * which digests were picked and can unsubscribe, which is exactly what the
 * email they just clicked already let them do. Nothing new is exposed.
 *
 * A MISSING OR EXPIRED RECEIPT IS NOT AN ERROR. The panel then says the state
 * plainly and offers the same two links, minus the readout it cannot honestly
 * produce. It never guesses at preferences.
 */
function alt_digest_make_receipt($row) {
    if (!is_array($row)) return '';
    $lists = array();
    foreach (alt_digest_lists() as $key => $cols) {
        if (!empty($row[$cols['consent']])) $lists[] = $key;
    }
    $token = alt_digest_new_token();
    set_transient('alt_dg_r_' . $token, array(
        'lists' => $lists,
        'freq'  => alt_digest_valid_freq($row['freq_layoff'] ?? 'weekly'),
        'unsub' => (string) ($row['unsub_token'] ?? ''),
    ), 30 * MINUTE_IN_SECONDS);
    return $token;
}

function alt_digest_read_receipt($token) {
    if (!is_string($token) || !preg_match('/^[a-f0-9]{64}$/', $token)) return null;
    $data = get_transient('alt_dg_r_' . $token);
    return is_array($data) ? $data : null;
}

/**
 * The same page with the state parameters stripped, i.e. the plain form.
 *
 * Built from REQUEST_URI and left RELATIVE on purpose. home_url() plus
 * REQUEST_URI double-prefixes on this install, where WordPress lives at
 * /blog and REQUEST_URI already carries it, and a wrong absolute URL here
 * would send a reader who wants to change their choices to a 404.
 */
function alt_digest_form_url() {
    $here = isset($_SERVER['REQUEST_URI']) ? (string) wp_unslash($_SERVER['REQUEST_URI']) : '';
    if ($here === '') $here = home_url('/ai-layoff-tracker/');
    return remove_query_arg(array('alt_dg', 'alt_r'), $here) . '#alt-digest';
}

/**
 * When the first one lands, stated from the schedule rather than invented.
 *
 * .github/workflows/digest-send.yml sends the daily tier at 6:00 AM Eastern
 * seven days a week and the weekly look-back at 7:30 AM Eastern on Mondays, so
 * these two sentences are true today. The slots are stated in Eastern rather
 * than UTC because that is what the reader experiences and what the owner
 * asked for; the workflow carries two candidate UTC cron lines per slot (10:00
 * / 11:00 and 11:30 / 12:30) and railway/digest_slot.py picks the real one, so
 * daylight saving does not move the morning. If those slots move, this moves
 * with them. Neither sentence names a time, which is why the 2026-08-19 move
 * changed nothing a reader sees.
 */
function alt_digest_cadence_sentence($freq) {
    return $freq === 'daily'
        ? 'Daily digests go out each morning, so your first one arrives tomorrow.'
        : 'Weekly digests go out on Monday mornings, so your first one arrives on the next Monday.';
}

/**
 * The panel that stands where the form stood.
 *
 * Returns finished HTML, built here rather than written inline in the
 * template, and that is deliberate rather than stylistic: the rendered tests
 * slice this component out of its own file and strip PHP, so a second branch
 * of inline markup would leave BOTH branches in the fixture and every
 * measurement after it would be of a page nobody is served.
 */
function alt_digest_state_panel($code, $receipt) {
    if (!in_array($code, alt_digest_terminal_states(), true)) return '';
    $out = '<div class="alt-digest-panel">';

    if ($code === 'check') {
        $out .= '<p>It should arrive within a minute or two. If it does not, look in '
              . 'your spam folder: it is the first message we have sent you, so nothing '
              . 'has taught your mail provider to trust us yet.</p>';
        $out .= '<p class="alt-digest-panel-actions">'
              . '<a href="' . esc_url(alt_digest_form_url()) . '">Used the wrong address?</a>'
              . '</p>';
        return $out . '</div>';
    }

    if ($code === 'unsubscribed') {
        $out .= '<p>Nothing else will be sent. Every digest you were on has stopped, '
              . 'and no other list carries your address.</p>';
        $out .= '<p class="alt-digest-panel-actions">'
              . '<a href="' . esc_url(alt_digest_form_url()) . '">Changed your mind?</a>'
              . '</p>';
        return $out . '</div>';
    }

    // confirmed / updated. Read the choices back from the receipt.
    $names = alt_digest_list_names();
    if ($receipt && !empty($receipt['lists'])) {
        $out .= '<p class="alt-digest-panel-lead">Here is what you will get:</p>';
        $out .= '<ul class="alt-digest-panel-list">';
        foreach ($receipt['lists'] as $key) {
            if (!isset($names[$key])) continue;
            $out .= '<li>' . esc_html($names[$key]) . '</li>';
        }
        $out .= '</ul>';
        $out .= '<p>' . esc_html(alt_digest_cadence_sentence($receipt['freq'] ?? 'weekly')) . '</p>';
    } else {
        // No receipt: say the state, promise nothing about the contents.
        $out .= '<p>Your choices are stored and the next digest will include you.</p>';
    }
    $out .= '<p class="alt-digest-panel-actions">'
          . '<a href="' . esc_url(alt_digest_form_url()) . '">Change your choices</a>';
    if ($receipt && !empty($receipt['unsub'])) {
        $out .= '<a href="' . esc_url(alt_digest_unsub_url($receipt['unsub'])) . '">Unsubscribe</a>';
    }
    $out .= '</p>';
    return $out . '</div>';
}

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
    $context = sanitize_key((string) $context);
    $lead = alt_digest_context_lead($context);
    $notice = isset($_GET['alt_dg']) ? sanitize_key($_GET['alt_dg']) : '';
    $receipt = alt_digest_read_receipt(isset($_GET['alt_r']) ? (string) $_GET['alt_r'] : '');
    $panel = alt_digest_state_panel($notice, $receipt);
    $messages = array(
        'check'        => array('ok',  'Almost done. We sent you one email with a confirmation link. Nothing is sent until you click it.'),
        'confirmed'    => array('ok',  'Your subscription is confirmed.'),
        'updated'      => array('ok',  'Your updated choices are confirmed.'),
        'unsubscribed' => array('ok',  'You are unsubscribed from everything. We delete your address within 30 days.'),
        'lists'        => array('err', 'Pick at least one list before subscribing.'),
        'email'        => array('err', 'That email address does not look right. Please check it and try again.'),
        'rate'         => array('err', 'Too many signups from this connection. Please try again in an hour.'),
        // NOT "expired or used", which reads as a failure for what is almost
        // always a success. A confirm token is cleared the moment it is spent,
        // so the overwhelming case for landing here is a link clicked twice,
        // or clicked after a mail scanner already followed it.
        'expired'      => array('ok',  'That link has already been used, which usually means you are confirmed already. If you are not sure, subscribing again sends a fresh one.'),
        'spam'         => array('err', 'That looked like an automated submission. Please try again.'),
        'mail'         => array('err', 'The confirmation email could not be sent. Please try again later.'),
    );
    ob_start();
    ?>
    <?php /* Self-carried styles: this form renders on BOTH tracker pages and
             the talent page does not load this plugin's stylesheet, so the
             component may depend on nothing outside itself (the honeypot in
             particular must be hidden everywhere). Mobile-safe: the email row
             wraps, nothing bleeds horizontally.

             THAT CLAIM WAS NOT TRUE UNTIL 2026-08-15, and it only stopped
             mattering because the form had nowhere to go. Every colour below
             was a bare var(--alt-*), and those tokens live in layoffs.css,
             which alt_page_needs_assets() enqueues on tracker surfaces and on
             nothing else. The submit button was `.alt-btn .alt-btn-primary`,
             defined in the same file. Put this component on a blog post, where
             that stylesheet is not loaded, and a bare var() with no fallback
             resolves to the unset value: no border on the box, no fill on the
             button, a stock grey browser button, and one hard-coded #ccc on
             the email field that measures 1.6:1 on white and fails WCAG 1.4.11
             wherever it is.

             The fix is one indirection. Every colour is a component token that
             READS the site token and carries the site's own light literal as
             its fallback, so a surface that loads layoffs.css is unchanged to
             the byte (the var resolves, the fallback is never used) and a
             surface that does not gets the light palette those literals came
             from. The button self-carries its fill rather than borrowing a
             class, so .alt-btn:hover cannot repaint its edge either.

             THERE IS DELIBERATELY NO prefers-color-scheme BLOCK HERE, AND
             THAT IS STILL RIGHT, BUT IT CARRIES A CONDITION THE CONSUMING PAGE
             HAS TO MEET.

             The condition: this component is dark-safe on any surface that
             DECLARES the --alt-* site tokens above. A surface that does not
             declare them gets the light palette, every time, whatever the
             reader's theme. That is correct on a page which is itself light,
             and it is a 1.02:1 hole on a page which is dark.

             Surfaces that satisfy it today:
               - the tracker, health, sources, press, company, facet and entry
                 pages, which load layoffs.css
               - the SIBLING product's dashboard, which loads dashboard.css and
                 declares the thirteen --alt-* names explicitly, pointed at its
                 own theme-aware --tit-* tokens (talent-intelligence-tracker
                 1.83.2)
             Surfaces that do not, correctly:
               - single blog posts. blog-reading.css declares no dark palette,
                 and the theme plus the two database stylesheets pin the
                 article to #fff. A dark box on a permanently white page is not
                 dark mode, it is a hole.

             THIS COMMENT USED TO SAY "the surfaces that have a dark mode all
             load layoffs.css". That was true when written and false eight days
             later: 2.20.60 put this form on the pages readers land on, which
             includes the sibling's dashboard, a dark surface that has never
             loaded layoffs.css. Thirteen tokens fell through to light literals
             on a #14161b ground and the sibling's scheduled contrast audit went
             red the next morning - seven labels, two legends and one summary at
             1.02:1. Neither repository was wrong read on its own. The defect
             existed only where the two plugins met, which is why it survived
             every check either side ran.

             So the reasoning is written as a CONDITION rather than a fact now,
             and tests/test_digest_form_token_contract.py fails when a surface
             renders this form without answering the tokens it reads. Adding a
             prefers-color-scheme block here would still be wrong: it would
             hard-code one dark palette into a component that is meant to take
             the host page's, and it would paint the blog dark. The fix for a
             new dark surface is for that surface to answer. */ ?>
    <style>
    .alt-digest {
        --alt-dg-edge: var(--alt-border, #e2e3e8);
        --alt-dg-ink: var(--alt-ink, #16181d);
        --alt-dg-field-edge: var(--alt-control-border, #838893);
        --alt-dg-field-bg: var(--alt-surface, #ffffff);
        --alt-dg-btn-bg: var(--alt-blue, #1f6fd0);
        --alt-dg-btn-bg-hover: var(--alt-blue-dark, #1c5cab);
        --alt-dg-btn-ink: var(--alt-on-accent, #ffffff);
        --alt-dg-ok-bg: var(--alt-ok-bg, #dff3df);
        --alt-dg-ok-ink: var(--alt-ok-ink, #165d28);
        --alt-dg-ok-edge: var(--alt-tint-border, #cfdad0);
        --alt-dg-err-bg: var(--alt-red-tint, #fdeeee);
        --alt-dg-err-ink: var(--alt-crit, #b3261e);
        --alt-dg-err-edge: var(--alt-crit-border, #e6b6b3);
        margin: 40px 0; padding: 20px;
        border: 1px solid var(--alt-dg-edge); border-radius: 12px;
        color: var(--alt-dg-ink);
    }
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
    /* THE CONSENT ROWS ARE 44px, AND THEY ARE 44px EVERYWHERE.
       A browser-drawn checkbox is 13x13 and cannot be resized without
       replacing it, so the LABEL is the target: it already wraps the box and
       its own sentence, and giving the label the height gives the box a 44px
       row to be hit in. Same treatment layoffs.css section 5 applies to these
       exact two selectors, brought inside the component.

       IT HAD TO COME INSIDE, because layoffs.css is where it lived and
       layoffs.css is not on a blog post. Measured on the blog fixture at 375,
       414, 768 and 1280 before this rule: every checkbox and every radio
       13.0 x 13.0, while the email field beside them was already 44.0. The
       floor in layoffs.css is also scoped `@media (max-width: 767px)`, so
       even on a tracker page these three consent boxes were 13px at a desk.

       UNCONDITIONAL, unlike the tracker's own floor, and that is a deliberate
       difference rather than an oversight. This component already gives the
       email field and the Subscribe button min-height:44px at every width, on
       the reasoning that owning a control's size makes it one size everywhere;
       a 44px field sitting above a 13px consent box in the same panel is that
       reasoning applied to half the form. WCAG 2.5.5 is not width-scoped
       either. The cost is that the tracker page's own signup grows by about
       70px at a desk, which is stated here because it is a visible change to a
       surface this brief was not about.

       margin goes to 0 and the spacing becomes `gap`: two 44px rows sharing a
       collapsed 4px margin is the mis-tap the height was bought to prevent,
       and a consent box is the worst place on the site to take a wrong tap. */
    .alt-digest-lists { display: flex; flex-direction: column; gap: 8px; }
    .alt-digest-lists label {
        display: flex; align-items: center; gap: 10px;
        min-height: 44px; margin: 0; font-size: 14px;
    }
    /* The frequency pair stays on ONE line, so this is inline-flex on the
       labels rather than a flex column on the fieldset: a <legend> is a flex
       item like any other and turning the fieldset into a row would seat
       "How often for the digests?" beside the two choices. 16px between them
       clears the 8px adjacency floor twice over. */
    .alt-digest-freq label {
        display: inline-flex; align-items: center; gap: 10px;
        min-height: 44px; margin: 0 16px 0 0; font-size: 14px;
    }
    /* A 13px box in a flex row is a flex item, and flex items shrink. */
    .alt-digest-lists input, .alt-digest-freq input { flex: none; }
    /* THE LINKS INSIDE THE SENTENCES, which are the other thing a thumb aims
       at in here: the "privacy note" jump in the intro and the contact-page
       link in the privacy note. 44px is the wrong answer for a word inside a
       paragraph (it opens a 44px hole in the sentence), and WCAG 2.5.5 and
       2.5.8 both carry the exception for a target "constrained by the
       line-height of non-target text". Vertical padding on a display:inline
       box hit-tests and does NOT enter the line-box calculation, so the hit
       area grows and the copy does not move. Measured at 18.0px tall at
       1280px before this; 32px after, clearing 2.5.8's 24px AA minimum. */
    .alt-digest a { padding: 7px 0; }
    .alt-digest-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .alt-digest-row label { font-weight: 600; flex-basis: 100%; margin: 0; }
    /* border-box, declared by the component rather than inherited.
       A control's height and its 44px floor are only the same number under
       border-box, and nothing guarantees it: layoffs.css sets it globally on
       tracker surfaces, blog-reading.css sets it on `.entry-content > *`
       (the section, not the field two levels inside it), and the site's own
       WPCode rule only sets it below 1024px. Measured on the blog fixture
       before this rule: min-height:44px applied to the CONTENT box and the
       field rendered 62.0px, which passes a 44px floor while being a
       different size on the blog than on the tracker for no reason a reader
       could name. Owning it makes the control one size everywhere. */
    .alt-digest, .alt-digest *, .alt-digest *::before, .alt-digest *::after { box-sizing: border-box; }
    /* 16px is not a type choice. Below it iOS Safari zooms the whole page when
       the field takes focus, and a zoomed page is a horizontal-overflow report
       from a reader who only tapped an email box. 44px is WCAG 2.5.5. */
    .alt-digest-row input[type="email"] {
        flex: 1 1 220px; min-width: 0; min-height: 44px;
        padding: 8px 10px; font: inherit; font-size: 16px; line-height: 1.3;
        border: 1px solid var(--alt-dg-field-edge); border-radius: 8px;
        background: var(--alt-dg-field-bg); color: var(--alt-dg-ink);
    }
    /* Self-carried, rather than .alt-btn .alt-btn-primary from layoffs.css:
       those classes are absent on every surface this form has just been added
       to, and .alt-btn:hover repaints a control's edge in --alt-chart-dim,
       which is ~1.2:1 on a light fill. */
    .alt-digest-submit {
        display: inline-flex; align-items: center; justify-content: center;
        min-height: 44px; min-width: 44px; padding: 8px 18px;
        font: inherit; font-size: 14px; font-weight: 600; line-height: 1.2;
        border: 1px solid var(--alt-dg-btn-bg); border-radius: 8px;
        background: var(--alt-dg-btn-bg); color: var(--alt-dg-btn-ink);
        cursor: pointer;
    }
    .alt-digest-submit:hover { background: var(--alt-dg-btn-bg-hover); border-color: var(--alt-dg-btn-bg-hover); }
    .alt-digest-submit:focus-visible { outline: 2px solid var(--alt-dg-btn-bg); outline-offset: 2px; }
    .alt-digest-status { border: 1px solid var(--alt-dg-ok-edge); background: var(--alt-dg-ok-bg); color: var(--alt-dg-ok-ink); border-radius: 10px; padding: 10px 12px; margin: 0 0 12px; font-size: 14px; }
    .alt-digest-status-error { border-color: var(--alt-dg-err-edge); background: var(--alt-dg-err-bg); color: var(--alt-dg-err-ink); }
    /* THE TERMINAL-STATE PANEL. It stands where the form stood, so it owns the
       same two obligations the form has: every control it draws clears 44px,
       and nothing in it can push the page sideways.

       The actions are links, not buttons, and they are deliberately quieter
       than the confirmation above them: the reader has finished, and the two
       ways to change their mind are there for the minority who want one. They
       are still full targets - a standalone action is not a word inside a
       sentence, so the 2.5.5 exception the intro's links rely on does not
       apply here and they take the height in full. 20px apart, well clear of
       the 8px adjacency floor, because "Change your choices" and
       "Unsubscribe" are the worst possible pair to mis-tap between. */
    .alt-digest-panel { margin-top: 4px; font-size: 14px; line-height: 1.55; }
    .alt-digest-panel p { margin: 0 0 10px; font-size: 14px; line-height: 1.55; }
    .alt-digest-panel-lead { font-weight: 600; }
    .alt-digest-panel-list { margin: 0 0 10px; padding-left: 1.2em; }
    .alt-digest-panel-list li { margin: 2px 0; }
    .alt-digest-panel-actions {
        display: flex; flex-wrap: wrap; gap: 20px; align-items: center; margin: 0;
    }
    /* The component already gives every anchor 7px of vertical padding for the
       words inside its sentences. These are not inside a sentence, so they get
       a box: inline-flex plus the floor, which the padding rule alone cannot
       reach because vertical padding on an inline box does not make it tall. */
    .alt-digest-panel-actions a {
        display: inline-flex; align-items: center; min-height: 44px;
        padding: 7px 0; text-decoration: underline;
    }
    /* The same cascade trap the intro fell into, and the same answer. Both
       trackers render inside a theme that declares `.entry-content p` at
       (0,1,1) !important, so a (0,1,0) rule on this paragraph never enters the
       argument and it comes out at the article's body size: the quietest
       sentence in the block set louder than the heading of the thing it
       belongs to. The extra element makes this (0,2,1). */
    .alt-digest p.alt-digest-tracking { margin: 14px 0 0 !important; font-size: 13px !important; line-height: 1.5 !important; }
    .alt-digest-privacy { margin-top: 8px; font-size: 13px; }
    .alt-digest-privacy p { margin: 8px 0; }
    /* A disclosure control is a control: the summary line is the whole hit
       area, not the seven words inside it. It sits BELOW the submit button, so
       this height is free against the phone-fold budget below. */
    .alt-digest-privacy summary { display: flex; align-items: center; min-height: 44px; cursor: pointer; }
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
        /* 220px of flex-basis plus the 8px gap plus a 106px button is 334px,
           and the content box inside a 375px phone is 311px, so the row wrapped
           and the Subscribe button landed 15px BELOW the fold after the jump.
           Measured on the live page at 2.20.52, not in a fixture: the local
           harness renders this component 375px wide because it has no theme
           gutter, so it never wrapped there and reported a pass. 140px still
           grows to ~197px on that screen. */
        .alt-digest-row input[type="email"] { flex-basis: 140px; }
        .alt-digest-form fieldset { margin-bottom: 10px; }
        /* NOT `.alt-digest-lists label { margin: 3px 0 }`, which is what stood
           here. The rows are spaced by the fieldset's 8px gap now, and a
           margin on top of it would push two 44px consent rows 14px apart in
           the one place on the page with the least room. */
        .alt-digest-lists { gap: 8px; }
        .alt-digest p.alt-digest-tracking { margin-top: 12px !important; }
        .alt-digest-privacy { margin-top: 8px; }
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
        <?php /* THE FORM IS NOT RENDERED IN A TERMINAL STATE. See
                 alt_digest_terminal_states(): an empty Subscribe form under
                 "your subscription is confirmed" reads as "it did not work,
                 do it again", and the readers who believe it submit twice.
                 The panel is built in PHP rather than written inline here so
                 that stripping PHP out of this file leaves exactly ONE branch
                 - the form - which is what the rendered tests measure. */ ?>
        <?php if ($panel !== '') : echo $panel; else : ?>
        <?php /* WHAT THIS PARAGRAPH IS ALLOWED TO CARRY, AND WHY IT IS SHORT.
                 It is the only prose inside the phone-fold budget. Everything
                 from the heading to the Subscribe button has to fit one 812px
                 screen after the #alt-digest jump, and this paragraph is the
                 one part of the block whose height is written rather than laid
                 out: at 2.20.75 it was eleven lines and 238.6px of a 720px
                 budget, and the copy edit that made it eleven lines is what
                 put the email field 862.4px down an 812px screen.

                 So it says what the email IS, what confirming costs, and
                 since 2.20.119 the one thing a reader arriving from a digest
                 footer needs: that this same form is where a subscription is
                 CHANGED, and that the boxes are a replacement rather than an
                 addition. That last pair of sentences is the landing half of
                 the footer fix (railway/digest_layout.py _footer), and it
                 renders for everyone because it is true for everyone, and it
                 was measured before it shipped: 95.2px of headroom left on the
                 tightest surface, against the 80px the measurement requires.

                 THE TRACKING DISCLOSURE IS NEITHER TRIMMED NOR
                 HIDDEN: it moved to .alt-digest-tracking below the form, in
                 the flow, visible without opening anything, where it costs the
                 budget nothing because the budget ends at the Subscribe
                 button. Anything added back here is paid for in pixels from
                 the one screen a reader gets, so measure before you write:
                 python3 railway/signup_fold.py */ ?>
        <p class="alt-digest-intro"><?php if ($lead !== '') echo esc_html($lead) . ' '; ?>A plain email summary of what changed on these trackers:
            headline numbers, the largest new entries, and links to the sources. You confirm your address
            by clicking a link we email you, and one click unsubscribes.
            Already subscribed? Use this form to change what you get. The boxes replace what you had.</p>
        <?php /* The context rides on the FORM, not on the <section>. The
                 section's opening tag is matched by a regex in
                 tests/test_digest_route_is_findable.py that reads the signup's
                 own <h2> out of this file, and `[^>]*` inside that pattern
                 cannot survive a PHP echo, whose `?>` is a literal `>`. */ ?>
        <form class="alt-digest-form" data-alt-context="<?php echo esc_attr($context); ?>"
              method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
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
                <button type="submit" class="alt-digest-submit">Subscribe</button>
            </div>
        </form>
        <?php endif; ?>

        <?php /* THE TRACKING DISCLOSURE, IN THE FLOW AND OUT OF THE BUDGET.
                 It carries the two facts a reader has to be told before they
                 type an address: the mail provider records opens and link
                 follows, and unsubscribing stops both. It renders for
                 everyone, in every state, with nothing to open - a paragraph,
                 not a summary - and it sits below the Subscribe button, which
                 is where the phone-fold budget ends. It was a clause inside
                 the intro until 2.20.76, where it was costing 96px of the one
                 screen a phone reader gets. Moving it cost the reader nothing.
                 The longer version stays inside the disclosure below, which is
                 where the provider is named and the mechanism explained. */ ?>
        <?php /* THE CONFIRMATION CLAUSE BELONGS IN THIS SENTENCE, not only in
                 the disclosure below. "An email" reads as the digest, so a
                 reader assumes the recording starts once they have agreed. It
                 starts with the message that ASKS them, which goes to a
                 pending row that has consented to nothing (file docblock).
                 This paragraph is below the Subscribe button, so the added
                 clause costs the phone fold nothing; check with
                 python3 railway/signup_fold.py before moving it up.
                 The sentence itself is DERIVED from ALT_RELAY_TRACKING since
                 2.20.107, so it cannot disagree with the privacy note or the
                 stats payload; the clause drops out on its own when opens go
                 off, because an unmeasured confirmation email needs no
                 warning. */ ?>
        <p class="alt-digest-tracking"><?php echo esc_html(alt_digest_tracking_line()); ?></p>

        <?php /* READ IT BEFORE YOU GIVE US AN ADDRESS, and cite it afterwards.
                 Every edition is kept at a permanent public URL, so a reader
                 can see exactly what arrives before subscribing, and anybody
                 quoting a figure has something to point at. This is also the
                 archive's main internal link: the form renders on the tracker
                 pages, blog posts, company profiles and facet pages, and a
                 page reachable only from a sitemap gets a weak signal. The
                 link renders only once something is actually archived. */ ?>
        <?php if (function_exists('alt_edition_any') && alt_edition_any()) : ?>
        <p class="alt-digest-tracking">You can <a href="<?php echo esc_url(alt_edition_index_url()); ?>">read every
            past edition</a> first. Each one is kept permanently, exactly as it was sent.</p>
        <?php endif; ?>

        <details class="alt-digest-privacy" id="alt-digest-privacy">
            <summary>Privacy note: what we store and how to erase it</summary>
            <p><strong>What we store:</strong> your email address, the choices above, and timestamps
                (signed up, confirmed, last sent). Nothing else about you.</p>
            <?php /* THE DURABLE HOME OF THE PROMISE, and the reason it is written here rather
                     than only in an email footer. A footer is true for one message and then it
                     is gone; a reader who wants to check what we do six months from now has
                     nowhere to look. There is a well-known outlet that promised no open
                     tracking in a 2019 launch letter and whose current privacy policy no longer
                     repeats it, so the promise survives only in the memory of people who read
                     the letter. That is the failure this block exists to avoid.
                     CNIL's 2026 recommendation also asks that pixels be disclosed in the
                     privacy policy even when they are exempt, as good practice.
                     NOTE: this site has no separate privacy policy page. The theme footer links
                     /privacy on the root domain, which is a SEPARATE Railway app currently
                     serving a "coming soon" placeholder with no privacy content at all. So this
                     note IS the site's privacy disclosure for the digest, and it is the only
                     one this repo can edit. See docs/RUNBOOK.md "Open and click tracking". */ ?>
            <?php if (ALT_RELAY_TRACKING) : ?>
            <p><strong>What our mail provider records:</strong> whether you opened an email and which
                links you followed, tied to your address. That is Brevo, the service that delivers these
                emails, and it works by adding a small invisible image and by routing links through its
                own address. We read it to see which sections people use. Unsubscribing stops the sending
                and the measuring at the same time, and erasing your row removes it from our side.</p>
            <p><strong>The confirmation email is measured too:</strong> the same invisible image is in the
                one message that asks your permission. If you open it, Brevo records that against your
                address before you have agreed to anything, and it records it even if you then never
                confirm. We would exempt that message if we could. Brevo offers no way to switch its
                measuring off for a single email, and the one setting that exists covers every email we
                send or none of them. If you would rather not be measured at all, do not open it. Nothing
                else is ever sent to an unconfirmed address, and the signup is deleted from our side after
                <?php echo (int) ALT_DIGEST_RETENTION_DAYS; ?> days.</p>
            <?php else : ?>
            <p><strong>We do not record whether you open an email.</strong> There is no invisible image
                in anything we send you, and our mail provider is set not to add one. That covers every
                message, including the one that asks you to confirm. So opening an email from us, or
                leaving it unread, records nothing anywhere.</p>
            <p><strong>Our mail provider records nothing about you at all.</strong> That is Brevo, the
                service that delivers these emails. It is set not to measure opens and not to measure
                link follows, so it holds no record of what you did with a message. It still reports
                whether a message could be delivered, which is how a dead address stops being mailed.</p>
            <p><strong>Why we stopped measuring opens:</strong> it was never a good measurement. Apple
                Mail loads remote images for you before you have read anything, so an open was recorded
                whether or not a person opened the message. A number that cannot tell a reader from a
                mail server is not worth taking from you.</p>
            <?php endif; ?>
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
    // alt_r as well as alt_dg: a stale receipt riding a resubmit would make the
    // next page describe the PREVIOUS action.
    return remove_query_arg(array('alt_dg', 'alt_r'), $back);
}

/**
 * $receipt is the opaque token from alt_digest_make_receipt(), or ''. It names
 * no person: see that function for what the transient behind it holds.
 */
function alt_digest_redirect($code, $receipt = '') {
    $args = array('alt_dg' => $code);
    if (is_string($receipt) && $receipt !== '') $args['alt_r'] = $receipt;
    wp_safe_redirect(add_query_arg($args, alt_digest_back_url()) . '#alt-digest');
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
 * WHAT A RESUBMISSION ACTUALLY DOES TO A CONFIRMED SUBSCRIBER, ITEMISED.
 *
 * alt_digest_prefs_from_post() above builds the WHOLE preference set from the
 * boxes that were ticked, and every box on the form starts unticked, always
 * (pre-ticked consent is not consent). The same form is the only way to change
 * a subscription, and the digest footer sends readers to it. So a subscriber on
 * all three lists who arrives wanting to ADD one, ticks that one box and
 * confirms, LOSES the other two. Nothing read their current lists, so nothing
 * could warn them, and from their side a digest they still want simply stops.
 * The intro copy has said "the boxes replace what you had" since 2.20.119; a
 * sentence on a page is a warning, not a guard.
 *
 * This is the guard, and it is a DIFFERENCE rather than a state readout, which
 * is the only reason it can exist at all. THE PAGE MAY NOT KNOW ANY OF THIS.
 * It has no session, the address may never travel in a URL (a guard in
 * railway/tests/test_digest_subscription.py), and the manage link in the digest
 * footer carries ONE URL for the whole send (digest-api.php, read at
 * railway/digest_send.py), so it cannot be per-recipient without moving that
 * payload contract. Prefilling the form from a link would also hand a
 * link-holder the answer to "which digests does this person take", which the
 * unsubscribe token in the same footer does not: the worst that one can do is
 * stop mail. See alt_digest_manage_url().
 *
 * The confirmation email has no such problem. It goes to the one mailbox that
 * owns the record, it is already on the mandatory path of every change (the
 * pending_prefs branch of alt_digest_signup() applies nothing until the link in
 * it is clicked), and it costs the signup form's phone-fold budget nothing.
 * So the loss is spelled out there, list by list, before it can happen.
 *
 * Keys are alt_digest_lists() keys. `stopping` is the consequential one and is
 * printed first. Frequency is read from freq_layoff, the same representative
 * alt_digest_make_receipt() uses, because the form sets one value for all three.
 */
function alt_digest_change_delta($row, array $prefs) {
    $delta = array('stopping' => array(), 'starting' => array(), 'keeping' => array(),
                   'freq_from' => '', 'freq_to' => '');
    if (!is_array($row)) return $delta;
    foreach (alt_digest_lists() as $key => $cols) {
        $had   = !empty($row[$cols['consent']]);
        $wants = !empty($prefs[$cols['consent']]);
        if ($had && !$wants)     $delta['stopping'][] = $key;
        elseif (!$had && $wants) $delta['starting'][] = $key;
        elseif ($had && $wants)  $delta['keeping'][] = $key;
    }
    $from = alt_digest_valid_freq(isset($row['freq_layoff']) ? $row['freq_layoff'] : 'weekly');
    $to   = alt_digest_valid_freq(isset($prefs['freq_layoff']) ? $prefs['freq_layoff'] : 'weekly');
    if ($from !== $to) {
        $delta['freq_from'] = $from;
        $delta['freq_to']   = $to;
    }
    return $delta;
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
 *
 * ON THAT THIRD PATH THE CONFIRMATION EMAIL ITEMISES THE CHANGE, and that is
 * the guard against the silent loss written up on alt_digest_change_delta():
 * the boxes replace the stored set, so a subscriber adding one list drops the
 * rest. The email names what stops before it can stop. It is the right place
 * for it because it is the only surface here that knows both halves and is
 * proven to reach the person who owns the row.
 *
 * KNOWN GAP, DELIBERATELY NOT PAPERED OVER. The per-address resend throttle
 * below returns before the mail is built, so a SECOND change submitted within
 * fifteen minutes parks its prefs and mints a fresh token with no email to
 * describe them. Nothing un-itemised can be applied by it, because minting
 * that token invalidated the link in the first email, so the worst case is a
 * reader with no working link for fifteen minutes rather than a change they
 * were not shown. Fixing that means a distinct notice code on the form, which
 * is a new message in a fold-measured block; it is not this change.
 */
function alt_digest_signup($email, array $prefs) {
    global $wpdb;
    if (!alt_subscribers_table_ready()) return false;
    $table = alt_subscribers_table();
    $now = gmdate('Y-m-d H:i:s');
    $row = alt_digest_get_by_email($email);
    $confirm = alt_digest_new_token();
    // Null for every path where nothing can be lost: a new address, or a
    // pending/unsubscribed row being rebuilt from scratch. Non-null only on the
    // confirmed branch below, where the submitted boxes REPLACE a stored set.
    $delta = null;

    if (!$row) {
        $wpdb->insert($table, array_merge($prefs, array(
            'email'         => $email,
            'status'        => 'pending',
            'confirm_token' => $confirm,
            'unsub_token'   => alt_digest_new_token(),
            'created_at'    => $now,
        )));
    } elseif ($row['status'] === 'confirmed') {
        // Computed BEFORE the update, from the row as it stands, because after
        // it the only record of what this person had is the parked JSON's
        // complement and nothing reads it that way.
        $delta = alt_digest_change_delta($row, $prefs);
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
    return alt_digest_send_confirm_email($email, $confirm, $fresh ? $fresh['unsub_token'] : '', $delta);
}

/* ------------------------------------------------------------------ */
/* Confirm + unsubscribe (token links, no login, email never in a URL) */
/* ------------------------------------------------------------------ */

/**
 * THE TWO LINKS THAT LIVE INSIDE AN EMAIL, AND WHY THEY LEFT wp-admin.
 *
 * Until 2.20.77 both were
 * `/blog/wp-admin/admin-post.php?action=alt_digest_confirm&t=<64 hex>`.
 * Nothing was wrong with it mechanically, and everything was wrong with it as
 * the only link in a first-contact message. A person reads `wp-admin` in an
 * email from a sender they have never heard from as administrative at best and
 * as phishing at worst. A filter reads an admin path plus a long opaque token
 * in a first-contact message as a shape it has seen before, and plenty of
 * corporate filters rewrite or strip links to admin paths outright. The
 * confirmation IS the funnel: nobody is ever sent a digest until they click
 * that one link, so a link a reader does not trust and a filter does not pass
 * produces no complaint and no error, only a list that quietly stays empty.
 *
 * The new shape is a path on the page the reader was just standing on:
 *
 *   https://asktherecruiter.com/blog/ai-layoff-tracker/confirm/<token>/
 *   https://asktherecruiter.com/blog/ai-layoff-tracker/unsubscribe/<token>/
 *
 * WHY A PATH AND NOT A REWRITE RULE. Both are "pretty". A rewrite rule only
 * exists once the rewrite table has been flushed, and FTP deploys here bypass
 * every WordPress hook that would flush it. The company and facet pages solve
 * that with a version-gated self-healing flush, which is right for a page that
 * can be a few minutes late. It is not right for a link that has already been
 * emailed: the window where the rule is missing is a window where a real
 * reader's confirmation link 404s, and that reader is not coming back. So
 * alt_digest_public_route_dispatch() reads REQUEST_URI itself, on
 * `parse_request`, before WordPress decides the URL is a 404. It needs no
 * rewrite rule, no flush and no activation hook, and it is therefore correct
 * on the first request after an upload rather than the first request after a
 * flush. tests/test_digest_link_identity.py holds that.
 *
 * THE OLD URLS KEEP WORKING FOREVER, and that matters more than the new ones.
 * Confirmation links of the old shape were emailed to real addresses, and the
 * old unsubscribe URL is in the `List-Unsubscribe` header of every digest
 * already delivered, where Gmail and Yahoo POST to it with no human present.
 * A link that 404s because we prettified the route is strictly worse than an
 * ugly link that works. The admin_post_ hooks below stay registered, both
 * shapes reach the same two handlers, and a test exercises the old one.
 */
/**
 * The one place the route's base is written. The builder below and the matcher
 * in alt_digest_public_route_dispatch() have to agree about it forever, and two
 * literals that must agree is how a link gets minted at one path and answered
 * at another.
 */
function alt_digest_link_base() {
    return 'ai-layoff-tracker';
}

function alt_digest_link_path($verb, $token) {
    return '/' . alt_digest_link_base() . '/' . $verb . '/' . rawurlencode((string) $token) . '/';
}

function alt_digest_confirm_url($token) {
    return home_url(alt_digest_link_path('confirm', $token));
}

function alt_digest_unsub_url($token) {
    return home_url(alt_digest_link_path('unsubscribe', $token));
}

/**
 * The pre-2.20.77 shapes. Nothing MINTS these any more. They exist so the
 * tests can drive the exact URL that is sitting in somebody's inbox, rather
 * than a copy of it written out again in the test and free to drift.
 */
function alt_digest_legacy_confirm_url($token) {
    return add_query_arg(array('action' => 'alt_digest_confirm', 't' => $token), admin_url('admin-post.php'));
}

function alt_digest_legacy_unsub_url($token) {
    return add_query_arg(array('action' => 'alt_digest_unsub', 't' => $token), admin_url('admin-post.php'));
}

/**
 * The request path with the WordPress install's own prefix removed, so the
 * matcher below reads `ai-layoff-tracker/confirm/...` on an install at /blog
 * and on one at the root. Query string dropped: the token is in the path.
 */
function alt_digest_route_request_path() {
    $uri = isset($_SERVER['REQUEST_URI']) ? (string) wp_unslash($_SERVER['REQUEST_URI']) : '';
    $path = (string) parse_url($uri, PHP_URL_PATH);
    $path = rawurldecode($path);
    $home = (string) wp_parse_url(home_url('/'), PHP_URL_PATH);
    if ($home !== '' && $home !== '/' && strpos($path, $home) === 0) {
        $path = substr($path, strlen($home));
    }
    return trim($path, '/');
}

/**
 * Hand a public confirm/unsubscribe URL to the same handler admin-post.php
 * would have reached.
 *
 * The token is matched loosely on purpose. A mail client that wraps or
 * truncates the URL should land on the plain "that link has already been used"
 * message, which is almost always true and reads as reassurance. A 404 page
 * tells the same reader nothing and looks like the site is broken.
 */
function alt_digest_public_route_dispatch() {
    $pattern = '#^' . preg_quote(alt_digest_link_base(), '#')
             . '/(confirm|unsubscribe)(?:/(.*))?$#';
    if (!preg_match($pattern, alt_digest_route_request_path(), $m)) {
        return;
    }
    $token = isset($m[2]) ? trim($m[2], '/') : '';
    // Only when the path carries one: a legacy-style `?t=` on this path is
    // then still honoured, because the handlers read $_REQUEST.
    if ($token !== '') $_REQUEST['t'] = $token;
    // Every token is unique, so nothing here is ever a cache hit. Say so
    // anyway: a cached confirmation page would confirm the wrong person.
    if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
    nocache_headers();
    if ($m[1] === 'confirm') {
        alt_digest_confirm();
    } else {
        alt_digest_unsubscribe();
    }
    exit;   // unreachable: both handlers end the request themselves
}
add_action('parse_request', 'alt_digest_public_route_dispatch', 0);

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
    // Read the row back rather than reasoning about $update: on the change
    // path the stored preferences are whatever the parked JSON turned out to
    // contain, and the panel must read back what is stored, not what was sent.
    $final = alt_digest_get_by_email($row['email']);
    alt_digest_redirect($was_change ? 'updated' : 'confirmed',
                        alt_digest_make_receipt($final));
}
add_action('admin_post_alt_digest_confirm', 'alt_digest_confirm');
add_action('admin_post_nopriv_alt_digest_confirm', 'alt_digest_confirm');

/**
 * Where an unsubscribe ends, stated absolutely rather than taken from the
 * referer.
 *
 * alt_digest_redirect() returns the reader to wp_get_referer(), which is right
 * for the signup form: it is submitted FROM the page the reader should land
 * back on. The unsubscribe is not. Its confirmation page lives at the
 * unsubscribe URL itself, so the button's POST carries that URL as its
 * referer, and returning there re-enters the same handler. The row is already
 * unsubscribed by then, so the handler redirects again, to the same referer,
 * forever. This names the destination instead.
 */
function alt_digest_unsub_redirect($code) {
    wp_safe_redirect(add_query_arg(array('alt_dg' => $code),
                                   home_url('/ai-layoff-tracker/')) . '#alt-digest');
    exit;
}

/**
 * The page a reader lands on after following an unsubscribe link in an email.
 *
 * ONE CLICK, AND NOTHING TO FILL IN. No address to retype, no login, no
 * JavaScript: a reader may open this in a stripped down client, and a page
 * whose only button needs a script is a page where nothing stops.
 *
 * The token is the credential and it is already in the URL the reader
 * followed, so this carries it forward in a hidden field. There is no nonce:
 * a logged out nonce proves nothing an attacker could not also obtain, it
 * expires, and an expired nonce here means a reader who wanted out cannot get
 * out. Anyone who can POST this form already knows a 64 character secret that
 * only ever travelled to one mailbox.
 */
function alt_digest_unsub_confirm_page($token) {
    $action = alt_digest_unsub_url($token);
    $wrap = 'max-width:34em;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'
          . '"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.6;color:#15181d;';
    $button = 'display:inline-block;padding:14px 26px;font-size:17px;font-weight:600;'
            . 'color:#ffffff;background:#0b4f9c;border:0;border-radius:8px;cursor:pointer;';
    $html = '<div style="' . esc_attr($wrap) . '">'
          . '<h1 style="font-size:22px;margin:0 0 12px;">Unsubscribe from the '
          . 'AskTheRecruiter digest?</h1>'
          . '<p style="margin:0 0 20px;">One click stops every digest on this address. '
          . 'We delete the address within ' . (int) ALT_DIGEST_RETENTION_DAYS . ' days.</p>'
          . '<form method="post" action="' . esc_url($action) . '">'
          . '<input type="hidden" name="action" value="alt_digest_unsub">'
          . '<input type="hidden" name="t" value="' . esc_attr($token) . '">'
          . '<input type="hidden" name="alt_unsub_confirm" value="1">'
          . '<button type="submit" style="' . esc_attr($button) . '">Yes, unsubscribe me</button>'
          . '</form>'
          . '<p style="margin:20px 0 0;font-size:15px;">'
          . '<a href="' . esc_url(home_url('/ai-layoff-tracker/')) . '">'
          . 'No, keep sending it</a></p>'
          . '</div>';
    wp_die($html, 'Unsubscribe', array('response' => 200));
}

/**
 * One click, everything stops. IDEMPOTENT: the same link followed twice lands
 * on the same answer, never an error. The token stays valid so links in older
 * emails keep working until the purge deletes the row.
 *
 * A GET NEVER CHANGES THE ROW, AND THAT IS THE WHOLE POINT OF THE SHAPE.
 *
 * THE DEFECT THIS ANSWERS, 2026-08-17. This wrote the row before it looked at
 * the request method, so any GET unsubscribed. The confirmation email carried
 * the unsubscribe URL in its body, one line under the confirm URL, and Brevo
 * rewrites every link at the relay. A corporate link scanner that fetches the
 * URLs in a delivered message therefore confirmed the address and then
 * unsubscribed it, with nobody present. That reader never learns it happened,
 * never receives what they asked for, and never complains. This file already
 * knew scanners follow these links: the 'expired' copy says so out loud.
 *
 * So the two callers are separated by the only thing that tells them apart:
 *
 *   GET   renders a page with one button. Nothing is written.
 *   POST  writes the row. A provider gets a bare 200, as RFC 8058 requires,
 *         and a reader who pressed the button gets the same page every other
 *         terminal state uses. The two are told apart by a field the button
 *         posts, so a provider that posts nothing else keeps its 200.
 */
function alt_digest_unsubscribe() {
    global $wpdb;
    $token = (string) ($_REQUEST['t'] ?? '');
    $row = alt_digest_get_by_token('unsub_token', $token);

    if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET')) !== 'POST') {
        // A used or purged token reads the same as it always has, and an
        // address already unsubscribed is not asked to confirm it twice.
        if (!$row) alt_digest_unsub_redirect('expired');
        if ($row['status'] === 'unsubscribed') alt_digest_unsub_redirect('unsubscribed');
        alt_digest_unsub_confirm_page($row['unsub_token']);   // ends the request
    }

    if ($row && $row['status'] !== 'unsubscribed') {
        $wpdb->update(alt_subscribers_table(), array(
            'status'          => 'unsubscribed',
            'unsubscribed_at' => gmdate('Y-m-d H:i:s'),
            'pending_prefs'   => null,
            'confirm_token'   => null,
        ), array('id' => $row['id']));
    }

    // THE MACHINE CASE IS ANSWERED FIRST, AND THAT ORDER IS THE POINT.
    //
    // RFC 8058: the provider POSTs to the List-Unsubscribe URL with no human
    // present, no browser session, and no obligation to follow a redirect. It
    // wants a 2xx and nothing else. Until 2.20.77 an unknown token fell into
    // alt_digest_redirect('expired') BEFORE this branch, so a provider POSTing
    // a token the 30 day purge had already deleted got a 302 to a web page.
    // It cannot act on that, it may record it as a failed unsubscribe, and a
    // failed unsubscribe is counted against the sending domain by the two
    // providers that require this header in the first place. There is also
    // nothing to tell it: whether the row is gone or was never there, the
    // outcome it asked for is already true.
    //
    // The marker is read from $_POST alone. A query string cannot forge it,
    // so no GET can reach the human branch by dressing itself up as one.
    if (empty($_POST['alt_unsub_confirm'])) {
        wp_die('Unsubscribed.', 'Unsubscribed', array('response' => 200));
    }
    if (!$row) alt_digest_unsub_redirect('expired');
    alt_digest_unsub_redirect('unsubscribed');
}
add_action('admin_post_alt_digest_unsub', 'alt_digest_unsubscribe');
add_action('admin_post_nopriv_alt_digest_unsub', 'alt_digest_unsubscribe');

/* ------------------------------------------------------------------ */
/* Mail                                                                */
/* ------------------------------------------------------------------ */

/**
 * WHO THE CONFIRMATION EMAIL COMES FROM.
 *
 * This returned array() until 2.20.77, so wp_mail used its own default. What
 * that default RESOLVED to on this install was not the WordPress default:
 * measured on 2026-08-17 by sending a real confirmation and reading the
 * received message, the address was already `newsletter@asktherecruiter.com`,
 * not `wordpress@asktherecruiter.com`. The Brevo plugin routes wp_mail here
 * and substitutes its own configured sender. The alert emails show the moment
 * it started: 13:31 UTC on 2026-08-16 they came from `wordpress@`, and by
 * 23:54 the same job's mail came from `newsletter@`.
 *
 * So the address was never the defect. THE DISPLAY NAME IS. The received
 * message carried a bare address and no name at all, beside a subject that
 * leads with the brand. A reader scanning an inbox for a name they recognise
 * gets an address, and a bare address on first contact is one of the cheapest
 * signals a filter has.
 *
 * WHY THIS ADDRESS AND NOT ANOTHER. It is the one the mail provider has
 * authenticated, and it is the one the digest itself sends as through
 * DIGEST_FROM. A From on any other mailbox breaks DKIM and SPF alignment,
 * which makes the deliverability problem worse rather than better, and it
 * teaches a subscriber to recognise a sender the digest does not use.
 *
 * NO EMOJI AND NO GRAPHICAL CHARACTER IN THE DISPLAY NAME, ever. Gmail treats
 * one there as interface spoofing and it is the single placement with a
 * documented hard block. tests/test_digest_link_identity.py holds that.
 *
 * THIS HEADER DOES NOT REACH THE READER. MEASURED, 2026-08-17, ON 2.20.77.
 *
 * Read this before you believe the three lines below do anything. A real
 * confirmation was sent from the live form after 2.20.77 deployed, and the
 * received message still carried a bare `newsletter@asktherecruiter.com` with
 * no display name. Brevo replaces the whole From line, not only the address.
 *
 * How that was established, so the next person can redo it rather than trust
 * it: Gmail's `from:` operator matches words in the display name as well as
 * the address, and `from:Trackers` returns nothing, while `from:UpdraftPlus`
 * returns messages whose ADDRESS contains no such word. The control that makes
 * that meaningful is `from:Backed`, a word in those same subjects, which
 * returns nothing: the operator is not leaking into the subject line, so the
 * absence of "Trackers" is a fact about the From header.
 *
 * SO WHY IS IT STILL HERE, when a header that is silently discarded is worse
 * than no header because the file looks configured? Because this docblock is
 * what stops it looking configured, and because the value is the correct one
 * the moment the relay changes. `assert_message_is_clean` and the RUNBOOK both
 * treat the Brevo coupling as reversible by swapping provider; on the day that
 * happens, deleting this would silently hand readers `WordPress
 * <wordpress@...>` again. It states the intended identity in code, and it
 * costs nothing while the relay overrules it.
 *
 * THE ONLY LEVER THAT CHANGES WHAT A READER SEES IS THE BREVO DASHBOARD. Set
 * the sender name there. Do not try a different header, do not try a
 * `wp_mail_from_name` filter hoping to win a race with a plugin that replaces
 * wp_mail wholesale, and above all do not change the ADDRESS to something the
 * relay will accept: an unaligned From is a worse outcome than an unnamed one.
 * RUNBOOK "the confirmation email's From line" carries the check.
 *
 * What the test asserts is what we HAND to wp_mail, which is still worth
 * holding: one From line, the aligned address, and no graphical character in
 * the name. It does not claim the reader sees it, and it must never be
 * rewritten to claim that.
 */
if (!defined('ALT_DIGEST_FROM_EMAIL')) define('ALT_DIGEST_FROM_EMAIL', 'newsletter@asktherecruiter.com');
if (!defined('ALT_DIGEST_FROM_NAME'))  define('ALT_DIGEST_FROM_NAME', 'AskTheRecruiter.com');
if (!defined('ALT_DIGEST_REPLY_TO'))   define('ALT_DIGEST_REPLY_TO', 'info@asktherecruiter.com');

function alt_digest_from_header() {
    return array(
        'From: ' . ALT_DIGEST_FROM_NAME . ' <' . ALT_DIGEST_FROM_EMAIL . '>',
        // A reply to a confirmation reaches a person. newsletter@ is a relay
        // mailbox; info@ is the address the contact page already publishes.
        'Reply-To: ' . ALT_DIGEST_REPLY_TO,
    );
}

/**
 * THE SUBJECT LINE OF THE ONLY EMAIL A PENDING ADDRESS EVER RECEIVES.
 *
 * The brand leads, because this message is the whole funnel. Nobody is sent a
 * digest until they click the link inside it, so an unrecognised subject in a
 * crowded inbox does not produce a complaint or an error: it produces a list
 * that quietly stays empty while every check in this repo reads green. A
 * reader who just typed their address on asktherecruiter.com is scanning for
 * that name, and "Confirm your tracker digest subscription" does not carry it.
 *
 * A function rather than a literal at the call site so there is one definition
 * and the tests read THIS rather than a copy of the words
 * (railway/tests/test_digest_subscription.py).
 */
function alt_digest_confirm_subject() {
    return 'AskTheRecruiter.com: confirm your tracker digest subscription';
}

/**
 * THE SUBJECT WHEN THE ROW ALREADY EXISTS AND THIS IS A CHANGE.
 *
 * Two literals, not one with a variable in it, and each in its own function
 * for the same reason alt_digest_confirm_subject() is one: the tests read
 * THESE rather than a copy of the words.
 *
 * The second one exists because "confirm your change" and "confirm a change
 * that stops a digest" are different messages to the person scanning an inbox,
 * and the second is the one somebody has to open. A reader who ticked one box
 * meaning to ADD a list is about to lose the others, and the subject is the
 * first and cheapest place to say so. The body says which ones.
 */
function alt_digest_change_subject() {
    return 'AskTheRecruiter.com: confirm your digest change';
}

function alt_digest_change_stops_subject() {
    return 'AskTheRecruiter.com: confirm a change that stops a digest';
}

/**
 * The three sections of the change email, in consequence order.
 *
 * Stopping first, deliberately. It is the only part a reader can be harmed by
 * missing, and the reader this exists for believes they are ADDING something,
 * so a message that opens with what they are gaining confirms what they
 * already think and gets skimmed.
 *
 * Names come from alt_digest_list_names(), which is also what the confirmation
 * panel reads back, so the email and the page cannot call one list two things.
 */
function alt_digest_change_lines($delta) {
    $names = alt_digest_list_names();
    $out = '';
    $sections = array('Stopping' => 'stopping', 'Starting' => 'starting',
                      'Still sending' => 'keeping');
    foreach ($sections as $label => $key) {
        if (empty($delta[$key])) continue;
        $out .= '  ' . $label . ":\n";
        foreach ($delta[$key] as $list) {
            $out .= '    - ' . (isset($names[$list]) ? $names[$list] : $list) . "\n";
        }
    }
    if (!empty($delta['freq_to'])) {
        $out .= '  How often: ' . $delta['freq_to']
              . ' (was ' . $delta['freq_from'] . ")\n";
    }
    return $out;
}

/**
 * The body of the one email that authorises a change, and the guard against
 * the silent loss described on alt_digest_change_delta().
 *
 * $delta is null for a signup (new address, or a pending / unsubscribed row
 * being rebuilt), where nothing can be lost because nothing is stored yet.
 * That body is unchanged.
 *
 * ONE LINK, STILL. It is tempting to offer a second one here ("add these
 * without removing anything"), and it would be as mailbox-proof as the first.
 * It is wrong for the reason the unsubscribe link left this message on
 * 2026-08-17: Brevo rewrites every link at the relay and corporate scanners
 * follow them, so two links means a machine decides which of two outcomes the
 * subscriber gets, with nobody present. One link, and the reader's other
 * option is to not click it.
 */
function alt_digest_confirm_body($confirm_url, $delta = null) {
    if (!is_array($delta)) {
        return "You (or someone typing your address) asked for the email digest at asktherecruiter.com.\n\n"
             . "Confirm by clicking this link:\n\n"
             . $confirm_url . "\n\n"
             . "Nothing is sent until you confirm. If you did not request this, ignore this email: "
             . "the signup is deleted automatically after " . ALT_DIGEST_RETENTION_DAYS . " days.\n";
    }
    $body = "You (or someone typing your address) asked to change what asktherecruiter.com sends you.\n\n"
          . "Nothing has changed yet. Clicking the link below applies exactly this:\n\n"
          . alt_digest_change_lines($delta) . "\n";
    if (!empty($delta['stopping'])) {
        $body .= "The signup form replaces your choices rather than adding to them, so every list "
               . "you did not tick is in the stopping section above.\n\n"
               . "If that is not what you meant, do not click this link. Nothing changes, and you "
               . "can fill the form in again with every list you want ticked, including the ones "
               . "you already have.\n\n";
    }
    $body .= "Apply the change by clicking this link:\n\n"
           . $confirm_url . "\n\n"
           . "If you did not ask for this, ignore this email. Nothing changes without that click, "
           . "and everything you get today keeps arriving.\n";
    return $body;
}

/**
 * The ONLY email a pending address ever receives.
 *
 * AND THE ONE WE CANNOT KEEP UNMEASURED. wp_mail here is the Brevo WordPress
 * plugin, which injects an open pixel at the relay and offers no per-message
 * opt-out; the field that would carry one (`contactPixelTrackingConsent`)
 * exists only on Brevo's HTTP API, which this path does not call. So an open
 * of THIS message is recorded against an address that has consented to
 * nothing. The signup form's privacy note says so in those terms. Do not
 * "fix" it by embedding anything of ours in the body: our message is clean and
 * that is what keeps the tracking removable by changing provider. See the file
 * docblock and docs/RUNBOOK.md "Open and click tracking".
 */
function alt_digest_send_confirm_email($email, $confirm_token, $unsub_token, $delta = null) {
    $confirm_url = alt_digest_confirm_url($confirm_token);
    $body = alt_digest_confirm_body($confirm_url, $delta);
    // A change that takes something away is a different message from one that
    // only adds, and both are different from a first signup. See the three
    // subject functions above.
    if (is_array($delta)) {
        $subject = empty($delta['stopping'])
            ? alt_digest_change_subject() : alt_digest_change_stops_subject();
    } else {
        $subject = alt_digest_confirm_subject();
    }
    $headers = alt_digest_from_header();
    /*
      NO UNSUBSCRIBE LINK IN THIS BODY, REMOVED 2026-08-17. It used to sit one
      line under the confirm link: "Already changed your mind? One click stops
      everything", and then the URL. Brevo rewrites every link at the relay,
      so a corporate scanner fetching the URLs in this message followed the
      confirm link and then the unsubscribe link, confirming an address and
      immediately unsubscribing it with nobody present. A GET can no longer
      write the row, which makes that harmless. Cutting the link makes it
      impossible.

      Nobody reading this message needs the link anyway. They have agreed to
      nothing yet, and ignoring the email is already the way to stop: the row
      is deleted after the retention window. The List-Unsubscribe header below
      is untouched, so any client that offers a stop button still has one.
    */
    if ($unsub_token !== '') {
        $headers = array_merge($headers, alt_digest_list_unsub_headers($unsub_token));
    }
    return wp_mail($email, $subject, $body, $headers);
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

/**
 * A THIRD-PARTY DESTINATION WE ARE WILLING TO PUT IN AN EMAIL.
 *
 * This is NOT alt_digest_link_allowed with the host check removed, and the
 * difference is the whole point. That function guards the click COUNTER, which
 * redirects from our own domain and therefore must never accept a destination
 * we do not own: an open redirect wearing our name is worse than no counter.
 *
 * This one guards an `<a href>` and nothing else. The reader's client goes
 * straight to the outlet, our domain is not in the path, and there is no
 * redirect to abuse. What still has to be true is that the value is an
 * ordinary absolute web address: a scheme a mail client will not treat as
 * script or as a local file, no embedded credentials (the
 * https://ourhost@evil.example shape), a real host, and a sane length.
 *
 * It exists for the hiring-signal list, whose rows quote somebody else's
 * headline and whose only honest destination is somebody else's article.
 */
function alt_digest_external_link_ok($url) {
    if (!is_string($url) || $url === '' || strlen($url) > 600) return false;
    $parts = wp_parse_url($url);
    if (!is_array($parts)) return false;
    if (!isset($parts['scheme'])
        || !in_array(strtolower($parts['scheme']), array('http', 'https'), true)) return false;
    if (isset($parts['user']) || isset($parts['pass'])) return false;
    if (empty($parts['host'])) return false;
    // A host with no dot is not a public name; it is localhost, an intranet
    // label, or a typo, and none of the three belongs in a reader's inbox.
    return strpos($parts['host'], '.') !== false;
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

/*
  alt_digest_short_date() lived here and rendered "18 Aug 2026". It is gone,
  and so is the second date format it put in the email. Every date a reader
  meets now comes from alt_digest_date_range, which spells the month out, so a
  row date and a window label are written the same way.
*/

/**
 * The window a section is about, spelled out for a reader.
 *
 * WHY EVERY BLOCK CALLS THIS. Until 2026-08-17 the layoff section said "in
 * this period" and then, four lines later, printed a year-to-date total, and
 * then a country list scoped to the PERIOD directly underneath it. The
 * arithmetic was right and the email still read wrong: nothing in the country
 * block stated its own window, so adjacency answered the question, and
 * adjacency put the block under the year figure. The owner read it as a
 * breakdown of the year and asked whether the maths was broken.
 *
 * Adjacency is the wrong mechanism for a reason that outlives that one bug. It
 * fails the moment somebody quotes a line, forwards a fragment, or reads on a
 * phone narrow enough that the grouping stops being visible. So every figure
 * in the digest names its own window, and this is where the words come from.
 *
 * Returns '' for anything that is not a pair of plain YYYY-MM-DD dates, and
 * the composer treats that as "compose nothing". A section that cannot say
 * what it covers does not go out.
 */
function alt_digest_date_range($from, $to) {
    $a = substr(trim((string) $from), 0, 10);
    $b = substr(trim((string) $to), 0, 10);
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $a, $ma)) return '';
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $b, $mb)) return '';
    $names = array('January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December');
    $ay = (int) $ma[1]; $am = (int) $ma[2]; $ad = (int) $ma[3];
    $by = (int) $mb[1]; $bm = (int) $mb[2]; $bd = (int) $mb[3];
    if ($am < 1 || $am > 12 || $bm < 1 || $bm > 12) return '';
    if ($ad < 1 || $ad > 31 || $bd < 1 || $bd > 31) return '';
    /*
      MONTH FIRST, AND THE OWNER ASKED FOR IT IN THOSE WORDS.

      This rendered "10 to 16 August 2026" and he read a live send and said it
      is hard to read: "Should be Weekly edition, Week 33, August 10 - 16 2026.
      So it's easier to read." He is right and the reason is structural rather
      than a preference. In the old shape the reader meets two bare numerals
      before anything tells them what unit they are, and the month arrives
      after the range has already been parsed. Month first fixes the unit
      before the numbers arrive, which is why it is the US convention and why
      every US statistical release uses it.

      THE FOUR SHAPES, and each is the shortest form that stays unambiguous:

        one day               August 16, 2026
        inside one month      August 10-16, 2026
        across two months     August 31 - September 6, 2026
        across two years      December 28, 2026 - January 3, 2027

      The hyphen is TIGHT between two numerals and SPACED between two
      multi-word dates, which is the standard typographic rule for a range and
      also the only way "August 31 - September 6" does not read as one date.
      It is a plain hyphen and never an em-dash: em-dashes are banned in UI
      copy here, and an en-dash is one more character a mail client can mangle.

      A COMMA BEFORE THE YEAR, always, because the month-day-year form takes
      one and dropping it is the single most common way this format is got
      wrong.
    */
    if ($a === $b) return $names[$am - 1] . ' ' . $ad . ', ' . $ay;
    if ($ay !== $by) {
        return $names[$am - 1] . ' ' . $ad . ', ' . $ay . ' - '
             . $names[$bm - 1] . ' ' . $bd . ', ' . $by;
    }
    if ($am !== $bm) {
        return $names[$am - 1] . ' ' . $ad . ' - '
             . $names[$bm - 1] . ' ' . $bd . ', ' . $by;
    }
    return $names[$am - 1] . ' ' . $ad . '-' . $bd . ', ' . $by;
}

/**
 * THE SAME WINDOW, WORDED TO SIT INSIDE A SENTENCE.
 *
 * WHAT THE OWNER READ, AND HE WAS RIGHT. "This doesn't make sense how it is:
 * dates, locations, countries." The dates half of that is this line, which
 * went out in five places in one send:
 *
 *     All 8 entries in 17 to 18 August 2026 are verified
 *
 * "in 17 to 18 August 2026" is not English. alt_digest_date_range() returns a
 * LABEL, and a label is the right thing when it stands alone in front of a
 * caption ("17 to 18 August 2026, verified only, ranked by job count"). Drop
 * the same label after a preposition and it reads as machine output, which is
 * the one thing a citable product cannot afford.
 *
 * So this is the other form, and it carries its own preposition. A caller
 * writes "posts we published " . $span, never "published in " . $span. Two
 * shapes, because two grammars: a window can be named or it can be entered.
 *
 *   one day        on 18 August 2026
 *   two days       on 17 and 18 August 2026
 *   longer         between 11 and 18 August 2026
 *
 * The two-day case is not a flourish. A daily digest covers exactly two dates,
 * so it is the shape most subscribers see, and "between 17 and 18 August" is
 * wrong about it: nothing lies between two consecutive days.
 *
 * Returns '' on anything alt_digest_date_range() cannot read, and every caller
 * treats that the way it treats an unreadable range, by composing nothing.
 */
function alt_digest_span_phrase($from, $to) {
    $a = substr(trim((string) $from), 0, 10);
    $b = substr(trim((string) $to), 0, 10);
    $range = alt_digest_date_range($a, $b);
    if ($range === '') return '';
    if ($a === $b) return 'on ' . $range;
    $names = array('January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December');
    preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $a, $ma);
    preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $b, $mb);
    $ay = (int) $ma[1]; $am = (int) $ma[2]; $ad = (int) $ma[3];
    $by = (int) $mb[1]; $bm = (int) $mb[2]; $bd = (int) $mb[3];
    /*
      THE SENTENCE FORM OF THE SAME WINDOW, rebuilt for the month-first label.

      A range LABEL and a range inside a sentence are two grammars, which is
      why there are two functions; the label is "August 10-16, 2026" and a
      caller writing "posts we published " . $span needs "between August 10 and
      16, 2026". Swapping a hyphen for the word "and" is not enough once the
      month leads, because "August 10 and 16, 2026" needs the month spoken once
      and a cross-month range needs it spoken twice.

      The two-day case is not a flourish. A daily edition covers exactly two
      dates, so it is the shape most subscribers see, and "between August 17
      and 18" is wrong about it: nothing lies between two consecutive days.
    */
    if ($ay === $by && $am === $bm) {
        $pair = $names[$am - 1] . ' ' . $ad . ' and ' . $bd . ', ' . $by;
    } elseif ($ay === $by) {
        $pair = $names[$am - 1] . ' ' . $ad . ' and '
              . $names[$bm - 1] . ' ' . $bd . ', ' . $by;
    } else {
        $pair = $names[$am - 1] . ' ' . $ad . ', ' . $ay . ' and '
              . $names[$bm - 1] . ' ' . $bd . ', ' . $by;
    }
    $ta = strtotime($a . ' 00:00:00 UTC');
    $tb = strtotime($b . ' 00:00:00 UTC');
    if ($ta !== false && $tb !== false && ($tb - $ta) === DAY_IN_SECONDS) {
        return 'on ' . $pair;
    }
    return 'between ' . $pair;
}

/**
 * THE WEEK, NUMBERED THE ONLY WAY A NUMBER CAN BE CHECKED: ISO-8601.
 *
 * WHAT THE OWNER READ. "the week to 19 August 2026", off a rolling seven days
 * ending on the send day. That is a Wednesday-to-Wednesday window, it belongs
 * to no week anybody recognises, and its last two days were still filling up
 * while the email described them.
 *
 * WHY ISO AND NOT A SUNDAY START. The first ask was Sunday to Saturday, and
 * the owner settled on ISO once the collision was put in front of him: ISO
 * week numbers start on MONDAY, so a Sunday-start week would have needed a
 * second, US-specific numbering rule (the CDC's MMWR convention is the only
 * published one) that disagrees with ISO for a day of every week. This is a
 * worldwide tracker. ISO is the international standard, the number is correct
 * by definition rather than by convention, and one reader in Frankfurt and
 * one in Denver hold the same "week 33".
 *
 * THE YEAR IS THE ISO YEAR AND NOT THE CALENDAR YEAR, which is the defect
 * that ships silently and surfaces once a year. ISO week 1 is the week holding
 * the first Thursday of January, so 1 January 2027 is a Friday and sits in
 * week 53 of ISO year 2026, and 31 December 2029 is a Monday and sits in week
 * 1 of ISO year 2030. PHP spells them `W` and `o`; `Y` beside `W` is the bug.
 * tests/test_digest_week_numbering.py pins real boundary dates in both
 * directions, and pins the PHP and the Python against each other.
 *
 * The YTD block is deliberately NOT touched by any of this. "YTD 2026" is the
 * calendar year, 1 January onward, because that is what every other surface we
 * publish means by a year, and an annual total that quietly became an ISO year
 * would disagree with all of them.
 */
function alt_digest_iso_week($date) {
    $d = substr(trim((string) $date), 0, 10);
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $d)) return null;
    $ts = strtotime($d . ' 00:00:00 UTC');
    if ($ts === false) return null;
    return array((int) gmdate('o', $ts), (int) gmdate('W', $ts));
}

/** "Week 33". The bare number, for the one place that pairs it with the dates
 *  itself. Nothing prints this alone: see alt_digest_edition_label. */
function alt_digest_week_label($date) {
    $iso = alt_digest_iso_week($date);
    return $iso === null ? '' : 'Week ' . $iso[1];
}

/**
 * A FIGURE, WITH ITS THOUSANDS SEPARATORS, FROM ONE DEFINITION WE CONTROL.
 *
 * WHAT WENT OUT, AND IT TOOK TWO SCREENSHOTS TO BELIEVE. The owner's Gmail
 * inbox showed, in the SAME message:
 *
 *     subject   16,842 verified job cuts \xc2\xb7 1,376 hiring signals \xc2\xb7 Aug 10-16
 *     preview   582 of 1376 verified against a primary document, from 1324 companies.
 *
 * 1376 formatted in the subject and unformatted in the preview, on both Gmail
 * iOS and Gmail desktop. This session first reported it as UNKNOWN and
 * probably the client's snippet extraction, which was wrong and was lazy: a
 * client that stripped separators would have stripped them from the subject in
 * the same message, and it did not.
 *
 * WHY THIS IS A FUNCTION RATHER THAN A HUNT FOR THE CALL SITE.
 * number_format_i18n() reads $wp_locale->number_format['thousands_sep'] when a
 * $wp_locale exists and falls back to PHP's number_format() when one does not,
 * and it passes the result through a filter any plugin or theme may hook. So
 * its output depends on a locale object and a filter chain that this file does
 * not own and cannot see from a test. For prose that is fine. For a FIGURE a
 * reporter may quote it is not: a separator is not decoration, it is what makes
 * a five-digit number readable at a glance, and the one line where that matters
 * most is the one a reader sees before deciding to open.
 *
 * So the digest formats its own numbers. ASCII comma, always, no locale, no
 * filter. That is a deliberate narrowing: this product publishes in English and
 * every other surface of it already spells figures this way.
 *
 * tests/test_digest_figures_are_formatted.py scans every composed string for
 * an integer of four digits or more carrying no separator and fails on one.
 */
function alt_digest_number($n) {
    return number_format((float) $n, 0, '.', ',');
}

/**
 * "Aug 10-16", "Aug 31 - Sep 6", "Aug 19". A window as an inbox reads it.
 *
 * WHY THE ISO WEEK CAME OUT OF THE SUBJECT. The owner read "2026 Week 33:
 * 16,842 verified job cuts" and said: "normal people dont care about week 33."
 * He is right, and the reason is worth writing down because the week number is
 * not wrong and has not been deleted. It is PRECISE FOR CITATION and OPAQUE
 * FOR SKIMMING. A researcher quoting us wants 2026-W33, which sorts and cannot
 * be misread. A person deciding whether to open an email wants to know which
 * days it is about, and has to translate a week number to get there.
 *
 * So the week number moved to where people cite and the dates stayed where
 * people skim. 2026-W33 is still the archive URL, still the edition's own
 * dateline, and still in the cite-this block. Only the subject changed.
 *
 * THE YEAR IS DROPPED, deliberately: the inbox already stamps every message
 * with its date, and those six characters buy more as part of the metric. The
 * year is still on every surface where a figure is quoted rather than skimmed,
 * which is the same division of labour as the week number.
 *
 * ABBREVIATED MONTHS, because this is the one string in the product written
 * for a 45-character truncation rather than for a reader with the whole line.
 * Everywhere else spells the month in full.
 *
 * A WEEKLY NAMES ITS WINDOW AND A DAILY NAMES ITS DAY, and that distinction is
 * load bearing. A weekly edition sends on the 19th about the 10th to the 16th,
 * so putting the send date on it would make a false claim about when the
 * figures are from. Callers pass the window they mean; see
 * alt_digest_subject_period.
 */
function alt_digest_short_range($from, $to) {
    $a = substr(trim((string) $from), 0, 10);
    $b = substr(trim((string) $to), 0, 10);
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $a, $ma)) return '';
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $b, $mb)) return '';
    $short = array('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec');
    $am = (int) $ma[2]; $ad = (int) $ma[3];
    $bm = (int) $mb[2]; $bd = (int) $mb[3];
    if ($am < 1 || $am > 12 || $bm < 1 || $bm > 12) return '';
    if ($ad < 1 || $ad > 31 || $bd < 1 || $bd > 31) return '';
    if ($a === $b) return $short[$am - 1] . ' ' . $ad;
    // Tight hyphen between two numerals, spaced between two month-and-day
    // pairs: the standard typographic rule for a range, and the only way
    // "Aug 31 - Sep 6" does not read as one date.
    if ($am === $bm && $ma[1] === $mb[1]) return $short[$am - 1] . ' ' . $ad . '-' . $bd;
    return $short[$am - 1] . ' ' . $ad . ' - ' . $short[$bm - 1] . ' ' . $bd;
}

/**
 * The period token a SUBJECT carries, and the one place that decides which
 * window a tier names.
 *
 * A WEEKLY NAMES ITS WINDOW. "Aug 10-16" for an edition that sends on the
 * 19th, because the figures are from the 10th to the 16th and a single date
 * would claim otherwise. The owner first proposed the send date here and it
 * was talked back: a weekly named by its send day is a false claim about when
 * its figures are from, every week, in the line most people only ever see.
 *
 * A DAILY NAMES ITS DAY. "Aug 19", not the two-day collection window, which is
 * the masthead convention: a front page carries the publication date and the
 * stories inside state their own spans. The edition's dateline still shows the
 * full window it covers.
 *
 * DO NOT FLATTEN THESE INTO ONE RULE in a later consistency pass. They look
 * like an inconsistency and they are the point.
 */
function alt_digest_subject_period($freq, $from, $to) {
    return (alt_digest_valid_freq($freq) === 'weekly')
        ? alt_digest_short_range($from, $to)
        : alt_digest_short_range($to, $to);
}

/**
 * "2026 Week 33". The week identified WITHOUT its dates, for the subject line.
 *
 * WHY THE YEAR IS HERE AND NOT IN alt_digest_week_label(). Inside the edition
 * the number always sits beside the dates it covers, so the year is already
 * on the line and repeating it would read as machine output. A SUBJECT has no
 * room for the dates, so the week number is travelling alone, and "Week 33"
 * alone is ambiguous across years and unsortable in a mailbox holding two
 * years of them. Year first, so a mailbox sorted by subject sorts by edition.
 *
 * IT IS THE ISO YEAR AND NOT THE CALENDAR YEAR, and that is the trap: the week
 * of 28 December 2026 to 3 January 2027 is 2026 Week 53, and the week of 31
 * December 2029 is 2030 Week 1. Reading the calendar year beside an ISO week
 * ships silently and is found the following January.
 */
function alt_digest_week_id($date) {
    $iso = alt_digest_iso_week($date);
    return $iso === null ? '' : $iso[0] . ' Week ' . $iso[1];
}

/**
 * "Week 33, 10 to 16 August 2026". THE NUMBER NEVER TRAVELS WITHOUT ITS DATES.
 *
 * A bare "Week 33" is a label a reader has to look up, and two readers on two
 * conventions look it up differently. The dates make it self-checking, and
 * they are the same alt_digest_date_range() shape as every other date in this
 * email rather than a second format. This is the line at the top of the
 * edition, in the masthead, and in the subject, so all three agree by
 * construction.
 */
function alt_digest_edition_label($from, $to) {
    $range = alt_digest_date_range($from, $to);
    if ($range === '') return '';
    $id = alt_digest_week_id($from);
    if ($id === '') return $range;
    /*
      THE SUBJECT'S PERIOD TOKEN IS A LITERAL PREFIX OF THIS LABEL, and that is
      the whole point of the shape.

      A subject reads "2026 Week 33: 16,842 verified job cuts". The edition's
      dateline, the masthead and the archived copy read "2026 Week 33 · August
      10-16". A reader moving from the inbox to the archive meets the same
      words in the same order, so the two surfaces are visibly the same
      edition rather than two things that happen to be about one week.

      THE TRAILING YEAR IS DROPPED WHEN THE ISO YEAR ALREADY LEADS AND THEY
      AGREE, because "2026 Week 33 · August 10-16, 2026" says 2026 twice on one
      line. It is KEPT whenever they can disagree, which is the only time a
      reader needs both: the week of 28 December 2026 renders "2026 Week 53 ·
      December 28, 2026 - January 3, 2027", and 31 December 2029 renders "2030
      Week 1 · December 31, 2029 - January 6, 2030". Those are the two shapes
      where dropping a year would publish a wrong one.

      A MIDDLE DOT AND NOT A COMMA. U+00B7 is a geometric character every
      client renders as text; an emoji here would be furniture. The date
      already carries commas of its own, so a comma here gives no hierarchy.
    */
    $iso = alt_digest_iso_week($from);
    $fy = (int) substr((string) $from, 0, 4);
    $ty = (int) substr((string) $to, 0, 4);
    if ($iso !== null && $iso[0] === $fy && $iso[0] === $ty) {
        // The same range with its trailing ", YYYY" removed. Built by trimming
        // the shared formatter rather than by a second date formatter, so
        // there is still exactly one place that spells a month.
        $trimmed = preg_replace('/,\s*\d{4}$/', '', $range);
        if ($trimmed !== null && $trimmed !== '') $range = $trimmed;
    }
    return $id . " \xc2\xb7 " . $range;
}

/**
 * THE PREVIOUS COMPLETE ISO WEEK, which is what a weekly edition may report.
 *
 * The weekly tier fires on Mondays and an ISO week ends on Sunday, so the week
 * that closed yesterday is complete, is never provisional at its edges, and
 * its number is settled. Any other send day still gets the last week that
 * actually finished, because a tier forced with DIGEST_FREQ on a Thursday must
 * not invent a Thursday-to-Thursday window.
 *
 * THE COST, STATED. Figures are up to two days older than the rolling window
 * they replace. That is the trade: this data revises upward for weeks as
 * filings and WARN notices arrive, so the last two days of the old window were
 * always the emptiest part of it, and reporting them as a week was reporting
 * a collection lag as a fall.
 *
 * Returns array($from, $to) as Y-m-d, both inclusive.
 */
function alt_digest_weekly_window($now = null) {
    $now = ($now === null) ? time() : (int) $now;
    // gmdate('N') is 1 for Monday through 7 for Sunday, so this lands on the
    // Monday of the week we are currently IN, and one week back from there is
    // the Monday of the last week that finished.
    $monday_this_week = strtotime(gmdate('Y-m-d', $now) . ' 00:00:00 UTC')
                      - ((int) gmdate('N', $now) - 1) * DAY_IN_SECONDS;
    $from = $monday_this_week - 7 * DAY_IN_SECONDS;
    return array(gmdate('Y-m-d', $from), gmdate('Y-m-d', $from + 6 * DAY_IN_SECONDS));
}

/**
 * The window a tier reports, in ONE place, because three callers had it.
 *
 * includes/digest-api.php (the relay's payload), alt_digest_send() (the
 * in-WordPress sender) and the tests each computed `$days = 1 or 7` off the
 * clock. Three copies of a window definition is three chances for the relay
 * and the fallback sender to describe different weeks in the same subject
 * line, which is precisely the class of drift alt_digest_subject_line already
 * exists to close.
 *
 * DAILY IS UNCHANGED, deliberately. A daily edition covers yesterday and
 * today, it is provisional and says so, and moving it to "the previous
 * complete day" would make the morning email describe the day before
 * yesterday. The two tiers answer different questions and only the weekly one
 * had a week to be wrong about.
 */
function alt_digest_window($freq, $now = null) {
    $now = ($now === null) ? time() : (int) $now;
    if (alt_digest_valid_freq($freq) === 'weekly') return alt_digest_weekly_window($now);
    return array(gmdate('Y-m-d', $now - DAY_IN_SECONDS), gmdate('Y-m-d', $now));
}

/**
 * WHICH REGION A COUNTRY SITS IN, or nothing at all.
 *
 * THE OWNER'S QUESTION was whether the geography block should be worldwide,
 * the United States, or both, and whether there should be a regional
 * breakdown. The answer to the first is both, as two headline figures. This
 * answers the second.
 *
 * IT IS AN ALLOWLIST AND THE FALLBACK IS NOT A GUESS. alt_normalize_country()
 * returns an unknown single country UNCHANGED rather than dropping it, which
 * is the right call for the database and means this map can never be complete
 * by construction. A country this does not know returns '', the caller puts it
 * in a stated "Elsewhere" line, and nothing is silently filed under a
 * continent it may not be on. tests/test_digest_regions.py walks the live
 * facet vocabulary and fails on an unmapped name, so the list is maintained by
 * a failing test rather than by memory.
 *
 * THESE ARE BUSINESS GROUPINGS AND THE EMAIL SAYS SO. "Asia Pacific" and
 * "Middle East and Africa" are not UN M49 regions; M49 has Asia, Oceania and
 * Africa as separate top-level groups and no APAC at all. A reader
 * reconciling against a UN table would find us "wrong", so the caption names
 * the grouping as ours. The United States and the United Kingdom are pulled
 * out as their own lines because the owner asked for them by name, not
 * because they are regions.
 *
 * "MULTIPLE COUNTRIES" IS REFUSED HERE, LOUDLY. It is the stored bucket for a
 * cross-border cut announced with no per-country split. It has no job
 * location, so folding it into any region would invent one and double-count
 * the jobs against the region that really holds them. It returns '' and the
 * caller gives it a line of its own outside the regional table.
 */
function alt_digest_region_of($country) {
    $c = trim((string) $country);
    if ($c === '') return '';
    if (strcasecmp($c, 'Multiple countries') === 0) return '';
    static $map = null;
    if ($map === null) {
        $map = array();
        $regions = array(
            'United States' => array('United States'),
            'Canada' => array('Canada'),
            // THE UNITED KINGDOM LINE MEANS THE UNITED KINGDOM. Jersey, Guernsey
            // and the Isle of Man are Crown Dependencies and not part of it, and
            // the first render of this block printed a line labelled "United
            // Kingdom" whose only member was Jersey. They sit in Europe, which is
            // where they are, and the UK line now means what it says.
            'United Kingdom' => array('United Kingdom'),
            'Europe' => array(
                'Guernsey', 'Isle of Man', 'Jersey',
                'Austria', 'Belgium', 'Bosnia and Herzegovina', 'Bulgaria', 'Croatia',
                'Cyprus', 'Czechia', 'Denmark', 'Estonia', 'Finland', 'France',
                'Germany', 'Greece', 'Hungary', 'Iceland', 'Ireland', 'Italy',
                'Latvia', 'Liechtenstein', 'Lithuania', 'Luxembourg', 'Malta',
                'Moldova', 'Monaco', 'Montenegro', 'Netherlands', 'North Macedonia',
                'Norway', 'Poland', 'Portugal', 'Romania', 'Serbia', 'Slovakia',
                'Slovenia', 'Spain', 'Sweden', 'Switzerland', 'Ukraine',
            ),
            'Asia Pacific' => array(
                'Australia', 'Bangladesh', 'Cambodia', 'China', 'Hong Kong', 'India',
                'Indonesia', 'Japan', 'Korea', 'Laos', 'Macau', 'Malaysia', 'Mongolia',
                'Myanmar', 'Nepal', 'New Zealand', 'Pakistan', "People's Republic of China",
                'Philippines', 'Singapore', 'South Korea', 'Sri Lanka', 'Taiwan',
                'Thailand', 'Vietnam',
            ),
            'Latin America' => array(
                'Argentina', 'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Costa Rica',
                'Dominican Republic', 'Ecuador', 'El Salvador', 'Guatemala', 'Honduras',
                'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Puerto Rico',
                'Uruguay', 'Venezuela',
            ),
            'Middle East and Africa' => array(
                'Algeria', 'Bahrain', 'Botswana', 'Egypt', 'Ethiopia', 'Ghana', 'Israel',
                'Jordan', 'Kenya', 'Kuwait', 'Lebanon', 'Morocco', 'Nigeria', 'Oman',
                'Qatar', 'Saudi Arabia', 'South Africa', 'Tanzania', 'Tunisia',
                'Türkiye', 'Turkey', 'Uganda', 'United Arab Emirates', 'Zambia',
                'Zimbabwe',
            ),
        );
        foreach ($regions as $region => $countries) {
            foreach ($countries as $one) $map[alt_digest_lower($one)] = $region;
        }
    }
    $key = alt_digest_lower($c);
    return isset($map[$key]) ? $map[$key] : '';
}

/** The order regions are printed in, US first because the US is the priority
 *  audience and its figure is already a headline. A region with no jobs in the
 *  window is not printed at all. */
function alt_digest_region_order() {
    return array('United States', 'Canada', 'United Kingdom', 'Europe',
                 'Asia Pacific', 'Latin America', 'Middle East and Africa');
}

/**
 * A DIRECTION IN WORDS AND IN A GLYPH, or nothing when there is no comparison.
 *
 * WHY THIS EXISTS AT ALL, AND IT OVERRIDES A RULE THIS FILE USED TO HOLD. The
 * year-to-date block used to carry a comment ending "Do not add a delta here
 * later", on the grounds that this data revises upward for weeks and a
 * week-on-week line would turn a reporting lag into a fall that never
 * happened. That reasoning is still true and the conclusion no longer follows,
 * for two reasons.
 *
 * First, the window changed. The old weekly window ended on the send day, so a
 * delta compared a window with zero days of settling against one with seven.
 * The window is now the previous COMPLETE ISO week, so it compares two days of
 * settling against nine. The asymmetry is smaller and, more importantly, it is
 * the same asymmetry every week, so the series is comparable with itself.
 *
 * Second, the owner asked for it, and it is the standard shape for a
 * periodic labour-market release: the count, the change on the prior period
 * and the dominant reason, in that order, in the headline.
 *
 * WHAT MAKES IT HONEST is not the arithmetic, it is the sentence that follows
 * it in the composer: the newer week is the less complete one and usually
 * rises. That is stated once, next to the comparison, and it is why this
 * returns the pieces rather than a finished sentence.
 *
 * A zero prior figure returns no percentage, because a change from nothing has
 * no scale. It still returns the direction, which is a real fact.
 *
 * Returns array('word', 'glyph', 'pct') or null. The glyph is a GEOMETRIC
 * character and never an emoji: an emoji in an email is furniture that half
 * the clients render as a coloured picture and the other half as a box.
 */
function alt_digest_change($now, $before) {
    $now = (int) $now; $before = (int) $before;
    if ($before <= 0 && $now <= 0) return null;
    if ($now === $before) return array('level with', '=', '');
    $up = $now > $before;
    $pct = '';
    if ($before > 0) {
        $share = 100 * abs($now - $before) / $before;
        // Below one per cent a rounded figure reads as no change at all, which
        // is not what happened. One decimal, and only there.
        $pct = ($share < 1 ? number_format($share, 1) : (string) round($share)) . '%';
    }
    return array($up ? 'up' : 'down', $up ? "\xe2\x96\xb2" : "\xe2\x96\xbc", $pct);
}

/**
 * A PLACE A READER RECOGNISES, out of the three columns the row really has.
 *
 * WHAT WENT OUT. "RNDC of Kentucky, LLC (KY, takes effect 17 Aug 2026)". The
 * leaders payload carries `state`, `country` and `location`, and this email
 * printed `location`, which for a WARN row is the two-letter postal code and
 * nothing else. So the biggest-cuts table said "KY" while the country table
 * two blocks below said "United States", and the same email named one place
 * two ways, one of them in a vocabulary only an American reader can decode.
 *
 * The state code is expanded through alt_us_state_names(), api.php's single
 * definition, which is also where the state pages take their slugs from. It is
 * guarded because this file is loaded by harnesses that do not load api.php,
 * and an unresolvable code falls back to the stored code rather than to
 * nothing: a reader who sees "KY, United States" has lost a detail, and a
 * reader who sees no place at all has lost the fact.
 *
 * `location` is used only when it is not simply repeating the country, which
 * is how a news-path row carries a city.
 *
 * AN EMPTY RESULT IS A REAL ANSWER and the caller says so out loud. Around a
 * third of verified job cuts sit on entries with no country recorded, the
 * headline already says that, and a row that quietly showed nothing let a
 * reader assume the place was obvious.
 */
function alt_digest_place($state, $country, $location) {
    $state = trim((string) $state);
    $country = trim((string) $country);
    $location = trim((string) $location);
    /*
      "Multiple countries" IS NOT A COUNTRY. It is the stored bucket for a
      global cut announced with no per-country split, and the country table in
      this same section already gives it a line of its own. Appended to a state
      it produced "(California, Multiple countries, takes effect 11 August
      2026)", which is not a place anybody lives. It is held back and spoken as
      what it is, either as a qualifier after a real place or on its own.
    */
    $unsplit = (strcasecmp($country, 'Multiple countries') === 0);
    if ($unsplit) $country = '';
    $parts = array();
    if ($state !== '') {
        $names = function_exists('alt_us_state_names') ? alt_us_state_names() : array();
        $code = strtoupper(preg_replace('/[^A-Za-z]/', '', $state));
        $parts[] = isset($names[$code]) ? $names[$code] : $state;
    } elseif ($location !== '' && strcasecmp($location, $country) !== 0
              && strcasecmp($location, 'Multiple countries') !== 0) {
        $parts[] = $location;
    }
    if ($country !== '') $parts[] = $country;
    if ($unsplit) {
        $parts[] = $parts ? 'plus other countries' : 'Multiple countries, no split given';
    }
    return implode(', ', $parts);
}

/**
 * ISO 3166-1 alpha-2 to a country name a reader recognises.
 *
 * WHY THIS IS SEPARATE FROM alt_normalize_country(). That function is the
 * layoff side's vocabulary gate: /add, /edit, /bulk and the public country
 * FILTER all pass through it, so anything it maps changes stored data and
 * changes what a filter returns. It deliberately knows only `us` and `uk`
 * among two-letter codes, and it deliberately leaves `Georgia` alone because
 * folding it would lose a country to save a US state. Teaching it that `CA` is
 * Canada and `IN` is India would reinterpret every ambiguous two-letter value
 * anyone has ever typed into a layoff row, in a column where `CA` far more
 * often means California.
 *
 * The talent side has no such ambiguity, because the column is not free text.
 * `/talent/v1/query` emits ISO 3166-1 alpha-2 by construction, and the same
 * row carries `state` separately: measured over 200 live rows on 2026-08-20,
 * every row with a `state` also had `country` = `US`, and no row had a state
 * under any other country. So the codes can be resolved here, safely, without
 * touching the gate the layoff data goes through.
 *
 * AN UNKNOWN CODE RETURNS EMPTY rather than the code itself. "(BA, The Sun,
 * 19 August 2026)" is not a place; it is our storage format leaking into a
 * reader's inbox, and the caller has a true sentence to print instead. The
 * list below is the full current alpha-2 assignment, so this should not
 * happen; it is written as the safe answer rather than the expected one.
 */
function alt_digest_iso2_country_name($code) {
    $code = strtoupper(trim((string) $code));
    if (!preg_match('/^[A-Z]{2}$/', $code)) return '';
    static $names = null;
    if ($names === null) {
        $names = array(
        'AD' => 'Andorra', 'AE' => 'UAE', 'AF' => 'Afghanistan',
        'AG' => 'Antigua and Barbuda', 'AI' => 'Anguilla', 'AL' => 'Albania',
        'AM' => 'Armenia', 'AO' => 'Angola', 'AQ' => 'Antarctica',
        'AR' => 'Argentina', 'AS' => 'American Samoa', 'AT' => 'Austria',
        'AU' => 'Australia', 'AW' => 'Aruba', 'AX' => 'Aland Islands',
        'AZ' => 'Azerbaijan', 'BA' => 'Bosnia and Herzegovina',
        'BB' => 'Barbados', 'BD' => 'Bangladesh', 'BE' => 'Belgium',
        'BF' => 'Burkina Faso', 'BG' => 'Bulgaria', 'BH' => 'Bahrain',
        'BI' => 'Burundi', 'BJ' => 'Benin', 'BL' => 'Saint Barthelemy',
        'BM' => 'Bermuda', 'BN' => 'Brunei', 'BO' => 'Bolivia',
        'BQ' => 'Caribbean Netherlands', 'BR' => 'Brazil', 'BS' => 'Bahamas',
        'BT' => 'Bhutan', 'BV' => 'Bouvet Island', 'BW' => 'Botswana',
        'BY' => 'Belarus', 'BZ' => 'Belize', 'CA' => 'Canada',
        'CC' => 'Cocos Islands', 'CD' => 'DR Congo',
        'CF' => 'Central African Republic', 'CG' => 'Republic of the Congo',
        'CH' => 'Switzerland', 'CI' => 'Ivory Coast', 'CK' => 'Cook Islands',
        'CL' => 'Chile', 'CM' => 'Cameroon', 'CN' => 'China',
        'CO' => 'Colombia', 'CR' => 'Costa Rica', 'CU' => 'Cuba',
        'CV' => 'Cape Verde', 'CW' => 'Curacao', 'CX' => 'Christmas Island',
        'CY' => 'Cyprus', 'CZ' => 'Czechia', 'DE' => 'Germany',
        'DJ' => 'Djibouti', 'DK' => 'Denmark', 'DM' => 'Dominica',
        'DO' => 'Dominican Republic', 'DZ' => 'Algeria', 'EC' => 'Ecuador',
        'EE' => 'Estonia', 'EG' => 'Egypt', 'EH' => 'Western Sahara',
        'ER' => 'Eritrea', 'ES' => 'Spain', 'ET' => 'Ethiopia',
        'FI' => 'Finland', 'FJ' => 'Fiji', 'FK' => 'Falkland Islands',
        'FM' => 'Micronesia', 'FO' => 'Faroe Islands', 'FR' => 'France',
        'GA' => 'Gabon', 'GB' => 'United Kingdom', 'GD' => 'Grenada',
        'GE' => 'Georgia', 'GF' => 'French Guiana', 'GG' => 'Guernsey',
        'GH' => 'Ghana', 'GI' => 'Gibraltar', 'GL' => 'Greenland',
        'GM' => 'Gambia', 'GN' => 'Guinea', 'GP' => 'Guadeloupe',
        'GQ' => 'Equatorial Guinea', 'GR' => 'Greece',
        'GS' => 'South Georgia and the South Sandwich Islands',
        'GT' => 'Guatemala', 'GU' => 'Guam', 'GW' => 'Guinea-Bissau',
        'GY' => 'Guyana', 'HK' => 'Hong Kong',
        'HM' => 'Heard Island and McDonald Islands', 'HN' => 'Honduras',
        'HR' => 'Croatia', 'HT' => 'Haiti', 'HU' => 'Hungary',
        'ID' => 'Indonesia', 'IE' => 'Ireland', 'IL' => 'Israel',
        'IM' => 'Isle of Man', 'IN' => 'India',
        'IO' => 'British Indian Ocean Territory', 'IQ' => 'Iraq',
        'IR' => 'Iran', 'IS' => 'Iceland', 'IT' => 'Italy', 'JE' => 'Jersey',
        'JM' => 'Jamaica', 'JO' => 'Jordan', 'JP' => 'Japan', 'KE' => 'Kenya',
        'KG' => 'Kyrgyzstan', 'KH' => 'Cambodia', 'KI' => 'Kiribati',
        'KM' => 'Comoros', 'KN' => 'Saint Kitts and Nevis',
        'KP' => 'North Korea', 'KR' => 'South Korea', 'KW' => 'Kuwait',
        'KY' => 'Cayman Islands', 'KZ' => 'Kazakhstan', 'LA' => 'Laos',
        'LB' => 'Lebanon', 'LC' => 'Saint Lucia', 'LI' => 'Liechtenstein',
        'LK' => 'Sri Lanka', 'LR' => 'Liberia', 'LS' => 'Lesotho',
        'LT' => 'Lithuania', 'LU' => 'Luxembourg', 'LV' => 'Latvia',
        'LY' => 'Libya', 'MA' => 'Morocco', 'MC' => 'Monaco',
        'MD' => 'Moldova', 'ME' => 'Montenegro', 'MF' => 'Saint Martin',
        'MG' => 'Madagascar', 'MH' => 'Marshall Islands',
        'MK' => 'North Macedonia', 'ML' => 'Mali', 'MM' => 'Myanmar',
        'MN' => 'Mongolia', 'MO' => 'Macao', 'MP' => 'Northern Mariana Islands',
        'MQ' => 'Martinique', 'MR' => 'Mauritania', 'MS' => 'Montserrat',
        'MT' => 'Malta', 'MU' => 'Mauritius', 'MV' => 'Maldives',
        'MW' => 'Malawi', 'MX' => 'Mexico', 'MY' => 'Malaysia',
        'MZ' => 'Mozambique', 'NA' => 'Namibia', 'NC' => 'New Caledonia',
        'NE' => 'Niger', 'NF' => 'Norfolk Island', 'NG' => 'Nigeria',
        'NI' => 'Nicaragua', 'NL' => 'Netherlands', 'NO' => 'Norway',
        'NP' => 'Nepal', 'NR' => 'Nauru', 'NU' => 'Niue',
        'NZ' => 'New Zealand', 'OM' => 'Oman', 'PA' => 'Panama',
        'PE' => 'Peru', 'PF' => 'French Polynesia', 'PG' => 'Papua New Guinea',
        'PH' => 'Philippines', 'PK' => 'Pakistan', 'PL' => 'Poland',
        'PM' => 'Saint Pierre and Miquelon', 'PN' => 'Pitcairn Islands',
        'PR' => 'Puerto Rico', 'PS' => 'Palestine', 'PT' => 'Portugal',
        'PW' => 'Palau', 'PY' => 'Paraguay', 'QA' => 'Qatar',
        'RE' => 'Reunion', 'RO' => 'Romania', 'RS' => 'Serbia',
        'RU' => 'Russia', 'RW' => 'Rwanda', 'SA' => 'Saudi Arabia',
        'SB' => 'Solomon Islands', 'SC' => 'Seychelles', 'SD' => 'Sudan',
        'SE' => 'Sweden', 'SG' => 'Singapore', 'SH' => 'Saint Helena',
        'SI' => 'Slovenia', 'SJ' => 'Svalbard and Jan Mayen',
        'SK' => 'Slovakia', 'SL' => 'Sierra Leone', 'SM' => 'San Marino',
        'SN' => 'Senegal', 'SO' => 'Somalia', 'SR' => 'Suriname',
        'SS' => 'South Sudan', 'ST' => 'Sao Tome and Principe',
        'SV' => 'El Salvador', 'SX' => 'Sint Maarten', 'SY' => 'Syria',
        'SZ' => 'Eswatini', 'TC' => 'Turks and Caicos Islands',
        'TD' => 'Chad', 'TF' => 'French Southern Territories', 'TG' => 'Togo',
        'TH' => 'Thailand', 'TJ' => 'Tajikistan', 'TK' => 'Tokelau',
        'TL' => 'Timor-Leste', 'TM' => 'Turkmenistan', 'TN' => 'Tunisia',
        'TO' => 'Tonga', 'TR' => 'Turkey', 'TT' => 'Trinidad and Tobago',
        'TV' => 'Tuvalu', 'TW' => 'Taiwan', 'TZ' => 'Tanzania',
        'UA' => 'Ukraine', 'UG' => 'Uganda',
        'UM' => 'United States Minor Outlying Islands',
        'US' => 'United States', 'UY' => 'Uruguay', 'UZ' => 'Uzbekistan',
        'VA' => 'Vatican City', 'VC' => 'Saint Vincent and the Grenadines',
        'VE' => 'Venezuela', 'VG' => 'British Virgin Islands',
        'VI' => 'United States Virgin Islands', 'VN' => 'Vietnam',
        'VU' => 'Vanuatu', 'WF' => 'Wallis and Futuna', 'WS' => 'Samoa',
        'YE' => 'Yemen', 'YT' => 'Mayotte', 'ZA' => 'South Africa',
        'ZM' => 'Zambia', 'ZW' => 'Zimbabwe',
        );
    }
    return isset($names[$code]) ? $names[$code] : '';
}

/**
 * WHERE A HIRING SIGNAL IS, in the layoff side's words and shape.
 *
 * THE DEFECT. A hiring-signal row read "Evri is launching a 10,000 role hiring
 * spree ... (10,000 jobs, The Sun, 19 August 2026)". The biggest-cuts row two
 * blocks up reads "Blueprint Medicines (Massachusetts, United States, takes
 * effect 18 August 2026)". So the email answered "where" for every cut and for
 * no hire, and a reader meeting a 10,000-role spree could not tell whether it
 * was in the United Kingdom or in India. The outlet is not the answer: The Sun
 * is a British paper that reports on hiring in other countries, and inferring
 * a place from a masthead is a guess dressed as a fact.
 *
 * THE COLUMNS ARE REAL AND SO IS THEIR ABSENCE. Measured over 200 live rows on
 * 2026-08-20: 114 carry a country, 86 carry none, and the 86 carry no city and
 * no region either, so there is nothing to fall back to. That is 43% of rows
 * printing "location not recorded", which is a lot, and it is the true number.
 * It is stated rather than left blank for the same reason alt_digest_place
 * states it: a silent row lets a reader assume the place was obvious, and the
 * gap is a fact about our coverage that the person reading has a right to.
 *
 * The state code is expanded only under the United States, which is the only
 * country the talent rows carry one for.
 */
function alt_digest_talent_place($row) {
    $row = (array) $row;
    $raw = trim((string) ($row['country'] ?? ''));
    // ISO alpha-2 first, then the layoff side's gate, so a row that arrives
    // carrying a spelled-out name is still spoken the same way the cuts are.
    $country = alt_digest_iso2_country_name($raw);
    if ($country === '' && $raw !== '' && function_exists('alt_normalize_country')) {
        $country = (string) alt_normalize_country($raw);
        // A value the gate did not recognise comes back unchanged. A bare
        // two-letter code that got this far is storage, not a place.
        if (preg_match('/^[A-Za-z]{2}$/', $country)) $country = '';
    }
    $parts = array();
    $state = trim((string) ($row['state'] ?? ''));
    if ($state !== '' && $country === 'United States') {
        $names = function_exists('alt_us_state_names') ? alt_us_state_names() : array();
        $code = strtoupper(preg_replace('/[^A-Za-z]/', '', $state));
        $parts[] = isset($names[$code]) ? $names[$code] : $state;
    }
    if ($country !== '') $parts[] = $country;
    return implode(', ', $parts);
}

/**
 * WHEN THE FIGURES WERE TRUE, in the same date shape as everything else.
 *
 * api.php's alt_data_last_updated_label() formats the same option as
 * "Aug 18, 2026 · 2:22 PM EDT". That is right for a web page a reader is
 * looking at in a browser. Inside this email it was a THIRD date format, next
 * to "17 to 18 August 2026" and "18 Aug 2026", in the one block whose whole
 * job is to be copied into somebody else's article.
 *
 * UTC, because the collection cron runs in UTC and the gap between it and the
 * send is the fact the line exists to state. Ingest finishes near 22:00 UTC
 * and the digest goes out at 6:00 AM Eastern (10:00 UTC under EDT, 11:00 under
 * EST), so a reader is holding figures about twelve hours old, and nothing in
 * the email said so.
 *
 * Reads the option directly rather than reformatting api.php's string, because
 * parsing a formatted date back out of prose is how a timezone gets lost.
 * Returns '' when the option is missing, and the caller prints no sentence.
 */
function alt_digest_data_cut_label() {
    $ts = function_exists('get_option') ? (int) get_option('alt_last_write', 0) : 0;
    if ($ts > 0) {
        $day = alt_digest_date_range(gmdate('Y-m-d', $ts), gmdate('Y-m-d', $ts));
        if ($day !== '') return $day . ' at ' . gmdate('H:i', $ts) . ' UTC';
    }
    /*
      THE FALLBACK, AND IT IS ONE PLACE ON PURPOSE. api.php's own label spells
      the date its own way, so it is the degraded path rather than the normal
      one. It is resolved HERE so the sentence under the headline and the
      citation at the foot can never disagree about whether we have a stamp:
      two call sites with two fallbacks is how one of them ends up silent.
    */
    return function_exists('alt_data_last_updated_label')
        ? (string) alt_data_last_updated_label() : '';
}

/**
 * THE SUBJECT LINE, AND THERE ARE TWO SENDERS THAT HAVE TO AGREE ON IT.
 *
 * WHAT WENT OUT ON 2026-08-18. "[AskTheRecruiter] Daily tracker digest". No
 * date anywhere in it, while the body said 17 to 18 August 2026. A digest
 * whose whole pitch is that every figure names its own window shipped the one
 * line a reader sees first with no window at all, and a mailbox holding a
 * month of them cannot tell one from another.
 *
 * THE TWO SENDERS. railway/digest_send.py relays through Brevo and composes
 * its subject in digest_layout.subject_line(). alt_digest_send() in this file
 * is the in-WordPress wp_mail sender, which takes over whenever the relay has
 * not claimed the tier (see alt_digest_external_active), and it composed its
 * own. They disagreed: one named the trackers and dated the window, the other
 * said "Daily tracker digest". Which subject a subscriber got depended on
 * which process happened to be sending, which is not a thing a reader should
 * be able to notice.
 *
 * So this is a PORT of digest_layout.subject_line, deliberately line for line,
 * and tests/test_digest_subject_agreement.py drives both implementations over
 * the same inputs and fails on any difference. Change one, change the other,
 * in the same commit.
 *
 * $headings are the sections' own first lines, in order, exactly as the Python
 * side reads them; a section that cannot name itself is skipped by both.
 * $fallback is what the site would have said anyway, used unchanged whenever
 * this cannot do better, so a failure here is never a subject-less email.
 */
function alt_digest_period_phrase($from, $to, $freq) {
    if (strtolower(trim((string) $freq)) === 'weekly') {
        // "Week 33, 10 to 16 August 2026". The number never travels without
        // its dates. See alt_digest_edition_label.
        return alt_digest_edition_label($from, $to);
    }
    return alt_digest_date_range($to, $to);
}

/** Characters, not bytes: the 78 ceiling is a reading limit and the tracker
 *  names are ASCII today but the ceiling must not tighten if one stops being. */
function alt_digest_chars($s) {
    return function_exists('mb_strlen') ? mb_strlen((string) $s, 'UTF-8') : strlen((string) $s);
}

function alt_digest_subject_line($freq, $from, $to, $headings, $fallback,
                                 $parts = array()) {
    /*
      ONE PATTERN FOR ALL THREE STREAMS:

          <figure> <unit> \xc2\xb7 <period>

          16,842 verified job cuts \xc2\xb7 Aug 10-16
          1,376 hiring signals \xc2\xb7 Aug 10-16
          2 new posts \xc2\xb7 Aug 10-16
          16,842 verified job cuts \xc2\xb7 1,376 hiring signals \xc2\xb7 Aug 10-16
          1,101 verified job cuts \xc2\xb7 Aug 19
          150 hiring signals \xc2\xb7 Aug 19

      THIS LINE HAS BEEN REWRITTEN FOUR TIMES AND EVERY CHANGE CAME FROM AN
      INBOX RATHER THAN FROM REASONING. Worth recording, because the pattern in
      the mistakes is the lesson.

      1. "AI Layoff Tracker: 16,842 verified cuts this week" made a reader who
         never opened it take away sixteen thousand AI-attributed cuts from a
         week whose AI figure was zero. A brand beside a raw count reads as a
         count of that brand's metric.
      2. Leading with the site name meant Gmail on mobile showed the sender's
         name and nothing else: "all you see is asktherecruiter.com."
      3. Leading with the ISO week was honest and opaque: "normal people dont
         care about week 33."
      4. Leading with the DATE made every edition honest and made the SET
         unusable. The owner's own inbox screenshot showed four messages all
         beginning "Aug 10-16:", indistinguishable in a list, with the word
         that told them apart arriving after the part that was identical on
         every one.

      SO THE METRIC LEADS AND THE PERIOD TRAILS. The first word now differs on
      every edition, the period is still present and still honest, and
      truncation eats the DATE rather than the news, which is the correct thing
      to lose because the inbox stamps the date already.

      A WEEKLY NAMES ITS WINDOW AND A DAILY NAMES ITS DAY, unchanged. See
      alt_digest_subject_period for why that asymmetry must survive a
      consistency pass.

      NO EMOJI, AND THE REASON IS RECORDED SO IT IS NOT REVISITED. The owner
      asked. This product is cited as a primary source and its register is
      measured and factual, which is the register that makes the numbers
      trusted; a glyph in the subject trades that for a moment's attention.
      Once the metric leads, the figures differentiate the editions better than
      any icon could, which was the only real argument for one. A screen reader
      also has to make sense of the line, and "chart increasing" read aloud in
      front of a job-cut figure is worse than nothing.

      THE ACCURACY PROPERTY IS UNCHANGED THROUGH ALL FOUR REWRITES, which is
      the argument for having written it as a property rather than a string. No
      tracker brand appears in this line, so nothing juxtaposes a brand with a
      raw count. tests/test_digest_subject_never_inflates_ai.py holds it:

          A READER WHO SEES ONLY THE SUBJECT MUST NOT COME AWAY WITH A LARGER
          AI FIGURE THAN THE EMAIL REPORTS.

      THE PERIOD IS THE SAME STRING THE ARCHIVE OPENS WITH. It is a SUFFIX of
      the subject and a PREFIX of the archived edition's title, so a reader
      moving from the inbox to the archive meets the same words. The archive
      adds the year because that page is cited; the subject drops it because
      that line is skimmed and the inbox stamps it.

      THE TWO UNITS READ DIFFERENTLY BECAUSE THEY ARE DIFFERENT, and a future
      consistency pass must not flatten them. The layoff tracker counts
      VERIFIED JOB CUTS, each with a filing or a named report behind it. The
      talent tracker counts HIRING SIGNALS, which deliberately means something
      weaker: a published indication, mostly unverified.

      $parts is a list of array('metric' => ..., 'minor' => bool) in the site's
      own section order. The blog's metric is MINOR: it is the least important
      of the three numbers, the line is already at its ceiling, and it appears
      only when it is the only thing the message carries.
    */
    $major = array(); $minor = array();
    foreach ((array) $parts as $part) {
        $part = (array) $part;
        $metric = trim((string) ($part['metric'] ?? ''));
        if ($metric === '') continue;
        if (!empty($part['minor'])) $minor[] = $metric; else $major[] = $metric;
    }
    $metrics = $major ? $major : $minor;

    $period = alt_digest_subject_period($freq, $from, $to);

    if ($metrics && $period !== '') {
        $dot = "\xc2\xb7";
        // Two at most. A third metric would run the line past any client's
        // display width and buys nothing a reader can see.
        $line = implode(' ' . $dot . ' ', array_slice($metrics, 0, 2))
              . ' ' . $dot . ' ' . $period;
        /*
          THE CEILING IS 100 AND NOT 78, DELIBERATELY. The combined line runs
          to about 83 characters and the owner chose it knowing Gmail on mobile
          truncates near 45. The old 78-character rule was sized for a subject
          meant to be read whole; this one is meant to be read from the left
          and completed by the preheader, which is composed for exactly that.
        */
        if (alt_digest_chars($line) <= 100) return $line;
        // One metric rather than a truncated two. A subject cut mid-figure
        // publishes a wrong number in the line most people only ever see.
        $line = $metrics[0] . ' ' . $dot . ' ' . $period;
        if (alt_digest_chars($line) <= 100) return $line;
    }

    /*
      NOTHING COULD SUPPLY A FIGURE, so the edition label, and failing that the
      site's own dated fallback. A bare date is not a subject.
    */
    $names = array();
    foreach ((array) $headings as $h) {
        $h = trim((string) $h);
        if ($h !== '') $names[] = $h;
    }
    $phrase = alt_digest_period_phrase($from, $to, $freq);
    if (!$names || $phrase === '') return $fallback;
    $subject = $names[0] . ', ' . $phrase;
    if (alt_digest_chars($subject) > 100) $subject = $phrase;
    return alt_digest_chars($subject) <= 100 ? $subject : $fallback;
}

/** What the SITE calls a section: its own first line, nothing else. The Python
 *  side reads the identical thing (digest_layout.section_heading). */
/**
 * A POST TITLE CUT TO THE SUBJECT'S BUDGET, ON A WORD BOUNDARY OR NOT AT ALL.
 *
 * WHY A CEILING AT ALL. alt_digest_subject_line() joins the metric to the
 * period with a middle dot and refuses anything over 100 characters, falling
 * back to the section heading. A 96-character headline would therefore not be
 * shortened, it would VANISH, and the subject would read "From the blog,
 * 2026 Week 33". Losing the whole title to protect the last six characters of
 * it is the wrong trade.
 *
 * 80, NOT 100. The longest period token this composes beside is
 * "Aug 31 - Sep 6" at 14 characters, plus three for the separator. 80 leaves
 * room for that and for the daily form, so a title that fits here fits the
 * subject on every day of the year rather than on most of them.
 *
 * THE CUT IS ON A WORD BOUNDARY AND IS MARKED. A headline severed mid-word is
 * a different headline; an ellipsis says a reader is holding the front of one.
 * If there is no space to cut at, the title is returned whole and the subject
 * line's own fallback decides, because inventing a hyphenation here would be
 * worse than deferring to a rule that already exists.
 *
 * THIS IS NOT THE FIGURE RULE AND DOES NOT WEAKEN IT. "A subject is never cut
 * mid-figure" is about numbers, where a truncation publishes a wrong one. A
 * title carries no arithmetic, and the ellipsis is the reader's signal.
 */
function alt_digest_subject_title($title, $max = 80) {
    $title = trim(preg_replace('/\s+/', ' ', (string) $title));
    if ($title === '' || alt_digest_chars($title) <= $max) return $title;
    $cut = function_exists('mb_substr') ? mb_substr($title, 0, $max - 1, 'UTF-8')
                                        : substr($title, 0, $max - 1);
    $space = strrpos($cut, ' ');
    if ($space === false || $space < 12) return $title;
    // U+2026, one character rather than three dots, so the ceiling arithmetic
    // above is the arithmetic a client applies.
    return rtrim(substr($cut, 0, $space), " ,;:-") . "\xe2\x80\xa6";
}

function alt_digest_section_heading($text) {
    foreach (preg_split('/\r\n|\r|\n/', (string) $text) as $line) {
        $line = trim($line);
        if ($line !== '') return $line;
    }
    return '';
}

/**
 * The dateless subject, which is now only ever a FALLBACK, and dated even so.
 *
 * Both senders use this when alt_digest_subject_line cannot compose (an
 * unreadable window, or no section that can name itself). It carries the day
 * it goes out, because "the subject must carry the date" is the requirement
 * and a fallback is still a subject somebody receives.
 */
function alt_digest_fallback_subject($freq, $to) {
    $label = (strtolower(trim((string) $freq)) === 'weekly') ? 'Weekly' : 'Daily';
    $stamp = alt_digest_date_range($to, $to);
    return '[AskTheRecruiter] ' . $label . ' tracker digest'
         . ($stamp === '' ? '' : ', ' . $stamp);
}

/**
 * A ranked list as an aligned two-column table, in both body parts.
 *
 * WHY A TABLE AND NOT A BULLET LIST. A column of figures a reader has to hunt
 * for down a ragged right edge is the thing that makes a data email feel like
 * work. The label wraps, the figure does not, and the figure is right aligned
 * by the `align` ATTRIBUTE rather than by CSS, because Outlook draws mail with
 * Word and Word honours the attribute while ignoring half of the properties.
 *
 * NO STYLE IS WRITTEN HERE. Each cell carries a `data-alt` role and
 * railway/digest_layout.py turns that into the inline style, so the design
 * lives in one file and this one decides only what a line MEANS. The role is
 * stripped once it has been read.
 *
 * $rows is a list of array('label', 'figure', 'url' optional). The last row
 * loses its rule, so a block does not end on a line that looks like the start
 * of the next one.
 */
/**
 * TWO HEADLINE FIGURES SIDE BY SIDE, WHICH IS THE OWNER'S "LETS DO BOTH".
 *
 * THE QUESTION. Should the headline be worldwide, or the United States, or
 * both? The United States is the stated first priority, and the geography
 * block answered it with a flat top-five country list in which one line was
 * the US and the other four were small. That buries the number the reader came
 * for and it makes the world look like a rounding error on it.
 *
 * BOTH, AS TWO HEADLINES. They sit in one two-cell table so a reader meets
 * them together and can see which is which without scrolling, and so the
 * comparison a reader is going to make anyway is one we made explicitly and
 * labelled, rather than one they assembled out of a list.
 *
 * THE PROPERTY THAT MAKES THAT SAFE, and it is the caller's job to keep it:
 * BOTH CELLS MUST BE THE SAME QUANTITY ON THE SAME BASIS. Two figures printed
 * side by side are read as comparable whether or not they are. Both come out
 * of the SAME /aggregate response, both are the verified tier, both are strict
 * job location, and the scope line under the pair says all of that once for
 * both. There is deliberately no way to hand this function two cells from two
 * queries.
 *
 * WHY A TABLE AND NOT TWO STACKED BLOCKS. Stacked, the second figure reads as
 * a subtotal of the first, which is exactly the adjacency fault this file has
 * logged three times. Two cells at 50% are equals. It is a presentational
 * table with `role="presentation"`, it is fluid, and it needs no media query,
 * so it survives a forward that deletes the head.
 *
 * $cells is a list of array('label', 'figure', 'foot'), two of them. The foot
 * is the change line and may be empty. No style is written here: each cell
 * carries a `data-alt` role and railway/digest_layout.py decides how it looks.
 */
function alt_digest_stat_pair($cells) {
    $cells = array_values(array_filter((array) $cells));
    if (count($cells) !== 2) return array('', '');
    $html = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
          . '<tr>';
    $text = '';
    foreach ($cells as $i => $cell) {
        $label = (string) ($cell['label'] ?? '');
        $figure = (string) ($cell['figure'] ?? '');
        $unit = (string) ($cell['unit'] ?? '');
        $foot = (string) ($cell['foot'] ?? '');
        $role = ($i === 0) ? 'pair-left' : 'pair-right';
        /*
          THE UNIT SITS ON THE CELL, UNDER THE FIGURE, AND THAT IS NOT
          DECORATION. The first render of this block put the geography in the
          eyebrow and the number under it, and the words "verified job cuts"
          only in the scope sentence below both cells. So a screenshot of the
          pair, which is the thing a reporter takes, carried two numbers and no
          unit. The single-stat block this replaced never had that problem
          because its eyebrow WAS the unit. Both facts are needed here, so the
          cell carries three lines: what geography, what number, what it counts.
        */
        $url = trim((string) ($cell['url'] ?? ''));
        // THE NUMBER IS THE LINK, because the number is what a reader points
        // at. The label above it stays plain text: two anchors in one cell
        // give a screen reader two destinations for one fact.
        $shown = esc_html($figure);
        if ($url !== '') $shown = '<a href="' . esc_url($url) . '">' . $shown . '</a>';
        $html .= '<td width="50%" data-alt="' . $role . '">'
               . '<p data-alt="kicker">' . esc_html($label) . '</p>'
               . '<p data-alt="stat-pair">' . $shown . '</p>'
               . ($unit !== '' ? '<p data-alt="unit">' . esc_html($unit) . '</p>' : '')
               . ($foot !== '' ? '<p data-alt="change">' . esc_html($foot) . '</p>' : '')
               . '</td>';
        $text .= '  ' . $label . ': ' . $figure
               . ($unit !== '' ? ' ' . $unit : '')
               . ($foot !== '' ? ' (' . $foot . ')' : '') . "\n";
    }
    return array($html . '</tr></table>', $text);
}

function alt_digest_rank_table($rows) {
    $rows = array_values($rows);
    if (!$rows) return array('', '');
    $html = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">';
    $text = '';
    $last = count($rows) - 1;
    foreach ($rows as $i => $row) {
        $edge = ($i === $last) ? '-last' : '';
        $label = esc_html((string) $row['label']);
        if (!empty($row['url'])) {
            $label = '<a href="' . esc_url($row['url']) . '">' . $label . '</a>';
        }
        /*
          THE QUALIFIERS SIT OUTSIDE THE LINK, and that is why they are a
          separate field rather than more label.

          The biggest-cuts row is "Blueprint Medicines (Massachusetts, United
          States, takes effect 18 August 2026)". All of it used to be the
          anchor text, so a mobile reader met three underlined lines of blue,
          and a screen reader announced the whole parenthesis as the name of
          the destination. Link text should say where the link goes. Here that
          is the company, and the place and the date are facts about the row.
        */
        $suffix = trim((string) ($row['suffix'] ?? ''));
        if ($suffix !== '') $label .= ' ' . esc_html($suffix);
        /*
          THE SUPPORTING SOURCE LINK, AFTER THE QUALIFIERS AND OUTSIDE THE
          COMPANY ANCHOR. The company name links to the citable unit we host
          (the entry page, or the tracker filtered to that company). This is a
          SECOND link to the filing or report itself, which is the destination
          a reporter checking us actually follows, and it is the one link the
          bulk-import rows could never carry an entry page for. It is a plain
          external `<a href>`, already vetted by alt_digest_external_link_ok in
          the caller, and never routed through the first-party click counter:
          an outlet URL cannot pass that counter's host guard, correctly, so it
          is handed over plain exactly as the hiring-signal list does. Its text
          is the word "Source", so the link says where it goes, and it renders
          only when the row carries one.
        */
        $source_url = trim((string) ($row['source_url'] ?? ''));
        if ($source_url !== '') {
            $label .= ' <a href="' . esc_url($source_url) . '" data-alt="source-link">Source</a>';
        }
        $html .= '<tr>'
               . '<td data-alt="label' . $edge . '">' . $label . '</td>'
               . '<td data-alt="figure' . $edge . '" align="right" width="34%">'
               . esc_html((string) $row['figure']) . '</td></tr>';
        $text .= '  ' . $row['label']
               . ($suffix !== '' ? ' ' . $suffix : '')
               . ': ' . $row['figure'] . "\n";
        // The plain destination, never the counted one: a text reader should
        // not be handed a machine-shaped URL to squint at.
        if (!empty($row['plain_url'])) $text .= '    ' . $row['plain_url'] . "\n";
        // The source, on its own line in the text part, labelled so a reader
        // knows it points at the filing or report rather than at us.
        if ($source_url !== '') $text .= '    Source: ' . $source_url . "\n";
    }
    return array($html . '</table>', $text);
}

/**
 * A RANKED DIMENSION AS ONE LINE, because most of them do not earn a table.
 *
 * WHY THIS EXISTS. The layoff edition printed six blocks in the same shape: a
 * heading, a caption restating the window, a table of rows, and a note. On the
 * live week of 10-16 August that came to 772 words, and the owner's reading was
 * that the email answers "what happened" while the site answers "show me
 * everything behind it", and it was doing both and neither cleanly. Geography
 * and industry are the two dimensions a reader SKIMS rather than studies, so
 * they are the two that become a line.
 *
 * NOTHING IS DROPPED EXCEPT FURNITURE. Every label keeps its link, so the
 * per-row destinations added on 2026-08-19 all survive and every one of them
 * still names its window and its basis. A row with no url renders as plain
 * text, which is how the unplaced residual stays unlinked: there is no filter
 * for an empty country and a link that quietly showed something else would be
 * worse than none.
 *
 * THE TEXT PART CARRIES NO URLS, which is what alt_digest_rank_table already
 * did for these two dimensions: a text reader should not be handed a
 * machine-shaped URL to squint at once per region.
 *
 * THE CALLER OWNS THE SENTENCE. This returns only the series, so the window,
 * the tier and the geography basis are written by the caller INTO the same
 * line. That is the rule this file will not bend: a line of this email lifted
 * out on its own is still true and still says what it covers, and a bare
 * "United States 10,132" lifted out says neither.
 */
function alt_digest_inline_series($rows) {
    $rows = array_values($rows);
    if (!$rows) return array('', '');
    // U+00B7, the same separator the dateline and the subject line use. Not an
    // emoji and not an en dash: one character every client already renders.
    $sep = " \xc2\xb7 ";
    $html = array();
    $text = array();
    foreach ($rows as $row) {
        $label = esc_html((string) $row['label']);
        if (!empty($row['url'])) {
            $label = '<a href="' . esc_url($row['url']) . '">' . $label . '</a>';
        }
        $html[] = $label . ' ' . esc_html((string) $row['figure']);
        $text[] = (string) $row['label'] . ' ' . (string) $row['figure'];
    }
    return array(implode($sep, $html), implode($sep, $text));
}

/**
 * How much of a headline a ranked list actually accounts for, said in numbers.
 *
 * THE DEFECT THIS REPLACES. The country block used to end with a fixed
 * sentence: "These are job locations only, so the list does not add up to the
 * total above." On the first live send the list added up EXACTLY, so the email
 * told the reader something they could see was untrue, on the day the data was
 * at its cleanest. Fixed prose around variable data is right on average and
 * wrong in particular cases, which is the worst way for a data product to be
 * wrong: it is only ever caught by the reader who checked.
 *
 * So the shortfall is computed and named. When the lines reconcile, this
 * returns '' and the block ends with no caveat at all, because there is
 * nothing to warn about. When they do not, the reader is told by how much and
 * for which of the two possible reasons.
 *
 * $shown    total of the lines actually printed
 * $covered  total across every value the endpoint returned for this dimension
 * $headline the verified figure the block sits under
 * $unit     'job cut', SINGULAR; alt_digest_count pluralises it
 * $missing  what an uncovered row lacks, e.g. 'no country recorded'
 * $span     the window as a prepositional phrase, because this line has to
 *           stand on its own too. alt_digest_span_phrase, not the label form:
 *           it lands inside a sentence here, never in front of one.
 */
/**
 * WHERE A HEADLINE FIGURE COUNTS, in the fewest words that are true.
 *
 * THE DEFECT THIS FIXES, found by the owner reading the delivered email of
 * 2026-08-16. The redesign named four things every figure must state: the
 * window, the tier, the date basis and the geography. Three of them reached
 * the headline. The block read:
 *
 *     Verified job cuts
 *     13,658
 *     10 to 17 August 2026, counted by the date the cuts take effect.
 *
 * and his question was one word long: where. The country table lower down did
 * carry a geography basis, but it carried it for the table. A reader who
 * quotes the 13,658 takes none of it, which is the exact adjacency failure
 * this whole rewrite exists to remove, one dimension over.
 *
 * WHY "WORLDWIDE" IS NOT ALLOWED TO STAND ALONE. The composers send no
 * `country` parameter, so alt_db_where() adds no country clause and the query
 * counts every row in the window. That is worldwide. It is also worldwide in
 * a way a reader would not guess: rows carrying NO country at all are in the
 * total too. Measured on the live week of 2026-08-16, 8,989 of 13,658
 * verified job cuts sat on entries with a country and 4,669 did not. A bare
 * "worldwide" implies a placed total and quietly overstates what we know.
 *
 * SO THE SECOND HALF IS MEASURED, NOT WRITTEN DOWN. $covered is the sum of
 * the verified column across every country the endpoint returned, and the
 * cut-off is 60 values against 58 live countries, so it is the whole set. A
 * window where every verified cut carries a country says "worldwide" and
 * nothing more. Fixed prose around variable data is the fault this file keeps
 * logging, and it is no better on this dimension than on the last one.
 */
function alt_digest_geo_scope($headline, $covered) {
    return ((int) $headline > (int) $covered)
        ? 'worldwide including entries with no country recorded'
        : 'worldwide';
}

function alt_digest_reconcile_note($shown, $covered, $headline, $unit, $missing, $span) {
    $shown = (int) $shown; $covered = (int) $covered; $headline = (int) $headline;
    if ($shown === $headline) return '';
    $parts = array();
    $parts[] = 'These lines cover ' . alt_digest_number($shown) . ' of the '
             . alt_digest_count($headline, 'verified ' . $unit) . ' '
             . $span . '.';
    $ranked = $covered - $shown;
    if ($ranked > 0) {
        $parts[] = alt_digest_number($ranked)
                 . alt_digest_verb($ranked, ' more sits', ' more sit')
                 . ' below the lines shown.';
    }
    $unclassified = $headline - $covered;
    if ($unclassified > 0) {
        $parts[] = alt_digest_number($unclassified)
                 . alt_digest_verb($unclassified, ' is on an entry with ',
                                                  ' are on entries with ')
                 . $missing . '.';
    }
    return implode(' ', $parts);
}

/**
 * "1 job", "4,320 jobs". A count and its noun, agreeing.
 *
 * Small, and it earns its place: the country block printed "1 jobs" on the
 * first render of the rewrite, on the "Multiple countries" line, which is
 * exactly the line a sceptical reader looks at hardest.
 */
function alt_digest_jobs_phrase($n) {
    return alt_digest_count($n, 'job', 'jobs');
}

/**
 * A COUNT AND THE NOUN IT GOVERNS, AGREEING. The general case of the above.
 *
 * WHY THIS IS A FUNCTION AND NOT A HABIT. The owner read a delivered digest
 * on 2026-08-18 and found three disagreements in one message: "1 of the 5
 * companies listed ... link to an entry page", "1 more sit below the lines
 * shown", and, on any window holding a single entry, "All 1 entries ... are
 * verified, across 1 companies". alt_digest_jobs_phrase already existed and
 * already carried a comment saying this exact class of error is what a
 * sceptical reader looks at hardest. It was applied to ONE noun. Every other
 * count in the file interpolated a number in front of a hard-coded plural.
 *
 * A digest that wants to be quoted cannot read as machine output, and a
 * disagreeing verb is the cheapest possible tell. So the count and the word
 * it governs are built together, here, and
 * tests/test_digest_singular_plural.py renders every block with a count of
 * exactly one and fails on a "1 <plural>" anywhere in either part.
 */
function alt_digest_count($n, $singular, $plural = null) {
    $n = (int) $n;
    if ($plural === null) $plural = $singular . 's';
    return alt_digest_number($n) . ' ' . ($n === 1 ? $singular : $plural);
}

/** The verb (or any word) a count governs. `alt_digest_verb(1,'sits','sit')`. */
function alt_digest_verb($n, $singular, $plural) {
    return ((int) $n === 1) ? $singular : $plural;
}

/**
 * THE INBOX SNIPPET, COMPOSED FOR ITS CEILING INSTEAD OF BORROWED.
 *
 * WHAT WENT WRONG. digest_layout.py used to build the preheader by walking
 * the sections and taking the first summary sentence that fitted 130
 * characters. On 2026-08-17 the layoff lede grew a measured geography clause
 * and reached 143, so the walk went past it and took the TALENT section's
 * sentence. The digest went out with a subject leading "AI Layoff Tracker"
 * beside a snippet reading "1,332 new hiring signals". Those two lines are
 * everything a recipient sees before deciding whether to open, and they
 * described different trackers.
 *
 * The lede was not too long. A body sentence has no length budget and should
 * not acquire one just because something else borrows it. The mechanism was
 * wrong: a preheader has ONE purpose and ONE hard ceiling, so it is composed
 * here, from the same figures, for that ceiling.
 *
 * HOW IT DEGRADES, AND WHY EVERY RUNG IS STILL TRUE. $required is the part
 * that may never be dropped: the figure, its tier and its window. A figure
 * with no scope is not an acceptable snippet at any length. $optional is
 * dropped from the TAIL until the line fits, so a long window eats the basis
 * clause before it eats the geography, and a line that still will not fit
 * returns '' so digest_layout falls back deliberately rather than by
 * accident. Tail-dropping rather than skipping, because skipping a middle
 * clause and keeping a later one produces a sentence nobody wrote.
 *
 * Measured in CHARACTERS and not bytes. PREHEADER_MAX is a character count on
 * the Python side, company and country names carry accents, and counting an
 * "á" as two would silently tighten the ceiling on exactly the lines most
 * likely to need the room.
 */
function alt_digest_fit_preheader($required, $optional, $max = 130) {
    $len = function ($s) {
        return function_exists('mb_strlen') ? mb_strlen($s, 'UTF-8') : strlen($s);
    };
    // AN EMPTY OPTIONAL CLAUSE IS NOT A CLAUSE. A caller that computes one
    // conditionally passes '' rather than branching at the call site, and
    // joining that produced a stray ", ." at the end of the snippet.
    $optional = array_values(array_filter(
        array_map('trim', is_array($optional) ? $optional : array()), 'strlen'));
    for ($keep = count($optional); $keep >= 0; $keep--) {
        $line = $required;
        for ($i = 0; $i < $keep; $i++) $line .= ', ' . $optional[$i];
        $line .= '.';
        if ($len($line) <= $max) return $line;
    }
    return '';
}

/**
 * THE FIVE TALENT SIGNALS WORTH THE SLOT, out of the forty we asked for.
 *
 * THE RULE IS ONE LINE: a signal that names a number of jobs outranks one
 * that does not, and among those the larger number wins. Everything else
 * keeps the endpoint's own order, which is materiality then recency.
 *
 * WHY NOT A SCORE. The obvious next step is to weigh headcount against
 * funding_amount_usd and confidence into one number, and it is the wrong
 * step. Ranking dollars against people needs an exchange rate between them
 * that nobody in this repo can defend, and a weighted score is a figure this
 * file invented, which is the one thing it may not do. Jobs are the unit both
 * trackers are about, so jobs are the unit that sorts. A funding round with
 * no headcount is not demoted for being a funding round; it is ordered below
 * a stated headcount because it states no jobs.
 *
 * LANGUAGE: THE FIRST ANSWER WAS WRONG AND THE LIVE DATA SAID SO. The
 * reasoning was that the untranslated headline reached the top of the live
 * send on recency, so ranking by jobs would push it down. Rendered against
 * the real week to 2026-08-17 it did the opposite: a Thai headline naming
 * 2,000 jobs came SECOND and a Spanish one naming 80 came third, because
 * they are genuinely material and materiality is what the new ranking
 * rewards. A worldwide tracker surfacing worldwide signals is working
 * correctly, and the digest was still unreadable.
 *
 * SO ONE ROW IS EXCLUDED, ON SCRIPT AND NEVER ON LANGUAGE. The schema has no
 * language column, so detecting language here would be a guess. Detecting
 * SCRIPT is not a guess: a headline containing no Latin letter at all cannot
 * be read by any subscriber to an English-language digest, so it occupies one
 * of five slots and delivers nothing. That is a fact about the reader, not a
 * judgement about the signal, and the signal keeps its place in the tracker
 * and on its own page.
 *
 * A LATIN-SCRIPT HEADLINE IN ANOTHER LANGUAGE STILL SHIPS. Spanish,
 * Portuguese and German lines carry the employer, the numbers and usually
 * enough cognates to be worth a slot, and dropping them would narrow this
 * summary to the English-speaking world while the tracker underneath it is
 * not narrow. If the other repo ever ships a language field, revisit this on
 * that field rather than on a regex.
 *
 * `headcount` is read defensively: absent, null and zero all mean "names no
 * number", and none of them may be treated as a measured zero.
 */
/**
 * ASCII-fold a name to comparable tokens, WITHOUT the intl extension.
 *
 * `Normalizer::normalize` would be the obvious call and it is not available:
 * intl is not guaranteed on this host, and WordPress core's `remove_accents`
 * is not loaded by the composer test harness. A function that exists in
 * production and not in the test is a function no test covers, so the mapping
 * is spelled here and both run the identical code.
 *
 * The tokens dropped at the end are the parts that differ between a company
 * as STORED and the same company as WRITTEN in a headline: legal forms
 * (Inc, Bhd, GmbH, S.A.), and the leading articles that a Romance-language
 * headline carries and a database field does not. "ATLAN Holdings Bhd" and
 * "Atlan Holdings" have to reach the same tokens or the comparison is a
 * string equality test wearing a hat.
 */
function alt_digest_name_tokens($value) {
    $s = (string) $value;
    // Curly to straight, so "Yuno's" and "Yuno's" fold together, and the
    // ampersand to the word, so "Brasfield & Gorrie" matches either spelling.
    $s = str_replace(array("\xe2\x80\x99", "\xe2\x80\x98", "\xc2\xb4"), "'", $s);
    $s = str_replace('&', ' and ', $s);
    $from = array(
        'à','á','â','ã','ä','å','ā','ă','ą','ç','ć','č','ď','đ','è','é','ê','ë',
        'ē','ĕ','ė','ę','ě','ğ','ģ','ì','í','î','ï','ī','į','ı','ķ','ļ','ľ','ł',
        'ñ','ń','ņ','ň','ò','ó','ô','õ','ö','ø','ō','ŏ','ő','ŕ','ř','ś','ş','š',
        'ţ','ť','ù','ú','û','ü','ū','ŭ','ů','ű','ų','ý','ÿ','ź','ż','ž','æ','œ',
        'ß','þ','ð',
    );
    $to = array(
        'a','a','a','a','a','a','a','a','a','c','c','c','d','d','e','e','e','e',
        'e','e','e','e','e','g','g','i','i','i','i','i','i','i','k','l','l','l',
        'n','n','n','n','o','o','o','o','o','o','o','o','o','r','r','s','s','s',
        't','t','u','u','u','u','u','u','u','u','u','y','y','z','z','z','ae','oe',
        'ss','th','d',
    );
    $s = str_replace($from, $to, alt_digest_lower($s));
    $s = preg_replace('/[^a-z0-9]+/', ' ', $s);
    $drop = array(
        'inc' => 1, 'incorporated' => 1, 'corp' => 1, 'corporation' => 1,
        'co' => 1, 'company' => 1, 'llc' => 1, 'lp' => 1, 'llp' => 1,
        'ltd' => 1, 'limited' => 1, 'plc' => 1, 'gmbh' => 1, 'ag' => 1,
        'sa' => 1, 'nv' => 1, 'bv' => 1, 'ab' => 1, 'oy' => 1, 'oyj' => 1,
        'as' => 1, 'spa' => 1, 'srl' => 1, 'sas' => 1, 'pty' => 1, 'bhd' => 1,
        'sdn' => 1, 'pte' => 1, 'fze' => 1, 'holdings' => 1, 'holding' => 1,
        'group' => 1, 'the' => 1, 'a' => 1, 'an' => 1, 'la' => 1, 'le' => 1,
        'el' => 1, 'los' => 1, 'las' => 1, 'les' => 1, 'de' => 1, 'del' => 1,
        'di' => 1, 'da' => 1, 'do' => 1,
    );
    $out = array();
    foreach (explode(' ', trim($s)) as $token) {
        if ($token === '' || isset($drop[$token])) continue;
        $out[] = $token;
    }
    return $out;
}

/**
 * Lowercase a UTF-8 string without mb_string, which is also not guaranteed.
 *
 * Only the accented Latin range matters here, because everything else is
 * either already ASCII or is about to be discarded by the script filter.
 */
function alt_digest_lower($s) {
    $s = strtolower((string) $s);
    $upper = array('À','Á','Â','Ã','Ä','Å','Ā','Ă','Ą','Ç','Ć','Č','Ď','Đ','È',
                   'É','Ê','Ë','Ē','Ĕ','Ė','Ę','Ě','Ğ','Ģ','Ì','Í','Î','Ï','Ī',
                   'Į','İ','Ķ','Ļ','Ľ','Ł','Ñ','Ń','Ņ','Ň','Ò','Ó','Ô','Õ','Ö',
                   'Ø','Ō','Ŏ','Ő','Ŕ','Ř','Ś','Ş','Š','Ţ','Ť','Ù','Ú','Û','Ü',
                   'Ū','Ŭ','Ů','Ű','Ų','Ý','Ź','Ż','Ž','Æ','Œ','Þ','Ð');
    $lower = array('à','á','â','ã','ä','å','ā','ă','ą','ç','ć','č','ď','đ','è',
                   'é','ê','ë','ē','ĕ','ė','ę','ě','ğ','ģ','ì','í','î','ï','ī',
                   'į','i','ķ','ļ','ľ','ł','ñ','ń','ņ','ň','ò','ó','ô','õ','ö',
                   'ø','ō','ŏ','ő','ŕ','ř','ś','ş','š','ţ','ť','ù','ú','û','ü',
                   'ū','ŭ','ů','ű','ų','ý','ź','ż','ž','æ','œ','þ','ð');
    return str_replace($upper, $lower, $s);
}

/**
 * DOES THIS HEADLINE ALREADY NAME THIS COMPANY?
 *
 * THE DEFECT THIS ANSWERS. The list printed `company: headline` on every row,
 * and a headline is written to open with the company, so the live send of
 * 2026-08-18 repeated the name on five rows out of five:
 *
 *     Banco do Brasil: Banco do Brasil anuncia 680 novas vagas ...
 *
 * MEASURED, over the real week 2026-08-11 to 2026-08-18, 1,411 signals:
 * 1,090 headlines (77.2%) open with the stored company name once both sides
 * are folded, another 172 (12.2%) name it mid-sentence, 47 (3.3%) do not name
 * it at all, and 56 (4.0%) carry no company. So the label is redundant on
 * about nine rows in ten and load bearing on the rest.
 *
 * WHICH IS WHY THE LABEL IS DROPPED CONDITIONALLY AND NOT ALWAYS. The 3.3%
 * are the rows where the label is doing all of the work, and they are not
 * marginal cases: "Arcos Dorados" over a headline about a McDonald's opening
 * in Costa Rica, "SILQ" over "ShopUp's parent platform raises $100m", "Auger"
 * over "This former Amazon exec is moving his startup's HQ to Texas". Dropping
 * the label always would leave those three rows naming nobody.
 *
 * AND WHY THE HEADLINE IS NEVER TRIMMED. Cutting the name out of the headline
 * is the naive fix and it mangles the 12.2% that name the company mid
 * sentence: "Le PSG va recruter 3 joueurs" becomes "va recruter 3 joueurs".
 * A headline is a sentence somebody wrote. We quote it or we do not.
 *
 * THE MATCH IS DELIBERATELY CONSERVATIVE, because the two mistakes cost very
 * different amounts. Failing to spot a match leaves one row reading the way
 * every row read before this change, which is a blemish. Spotting a match
 * that is not there deletes the only identification the row had. So this
 * requires EVERY token of the company, contiguously, in order: a partial
 * overlap ("Dangote Refinery" against "Dangote Petroleum Refinery &
 * Petrochemicals FZE") keeps its label rather than gambling on it.
 *
 * It is a token comparison and not `strpos`, so it survives the ways the two
 * spellings differ in the live data: accents ("Sudamericana de Lácteos"),
 * legal suffixes ("Theta Edge Bhd" in a headline reading "Theta Edge"),
 * possessives ("Yuno's $45 million Series B"), curly apostrophes, and the
 * ampersand written either way.
 */
function alt_digest_headline_names_company($company, $headline) {
    $needle = alt_digest_name_tokens($company);
    $hay = alt_digest_name_tokens($headline);
    // A company that folds to nothing is a company we cannot compare. Say no,
    // and the caller keeps whatever label it has.
    if (!$needle || !$hay) return false;
    $n = count($needle);
    $limit = count($hay) - $n;
    for ($i = 0; $i <= $limit; $i++) {
        if (array_slice($hay, $i, $n) === $needle) return true;
    }
    return false;
}

function alt_digest_talent_rank($rows, $limit) {
    $rows = array_values(is_array($rows) ? $rows : array());
    $keyed = array();
    foreach ($rows as $index => $row) {
        $r = (array) $row;
        /*
          MOSTLY not Latin, not "contains no Latin at all". The first version
          of this test asked whether the headline held any Latin letter, and
          the live week walked straight through it: a Thai headline naming
          2,000 jobs reads "...คิกออฟ True Customer Day 2026", so an embedded
          English brand name made it pass while the sentence stayed
          unreadable. So it is a SHARE of the letters, which is still script
          and still deterministic. Latin at or above half is readable enough
          to be worth a slot; that Thai line is about a quarter.

          Checked on the headline and not the company, because the headline is
          the part carrying the meaning: a Latin-script headline about a
          company whose own name is not Latin still reads.
        */
        $head = (string) ($r['headline'] ?? '');
        if ($head !== '') {
            $letters = preg_match_all('/\p{L}/u', $head);
            $latin = preg_match_all('/\p{Latin}/u', $head);
            if ($letters > 0 && $latin < 0.5 * $letters) continue;
        }
        $jobs = isset($r['headcount']) ? (int) $r['headcount'] : 0;
        // The endpoint's position is the tiebreak, so a row we cannot rank
        // keeps exactly the standing the tracker itself gave it.
        $keyed[] = array($jobs > 0 ? 1 : 0, $jobs, -$index, $row);
    }
    usort($keyed, function ($a, $b) {
        if ($a[0] !== $b[0]) return $b[0] - $a[0];
        if ($a[1] !== $b[1]) return $b[1] - $a[1];
        return $b[2] - $a[2];
    });
    $out = array();
    foreach (array_slice($keyed, 0, max(0, (int) $limit)) as $entry) {
        $out[] = $entry[3];
    }
    return $out;
}

/**
 * THE TRACKER, OPENED ON THE FIGURE THE READER JUST READ.
 *
 * THE DEFECT. The email shipped a caveat: "The tracker page counts by filing
 * date, not by effective date, so its totals for these dates differ." That is
 * honest, and it is also an admission that the click meant to PROVE the
 * figure is the click that contradicts it. On a product whose pitch is that
 * every number can be checked, that is the worst possible link.
 *
 * WHAT WAS VERIFIED, IN A REAL BROWSER, AND NOT BY curl. A deep-linked load
 * is server-rendered without figures and computed by JS, so fetching the HTML
 * proves nothing and would have been a false pass. Driven live on
 * 2026-08-17 against the week 2026-08-09 to 2026-08-16: `/aggregate` gives
 * jobs 16,726 minus announced 3,016 = 13,710 verified, and the page loaded on
 * the URL this builds shows 13,710, the range label "Aug 9, 2026 to Aug 16,
 * 2026", and the basis toggle reading "counted by effective date" with
 * aria-pressed set on it. The page's own JS writes these same names back into
 * the address bar as a user changes filters, so they round-trip.
 *
 * THE PARAMETER NAMES DIFFER FROM THE API'S, AND THAT IS THE TRAP. The
 * /aggregate endpoint takes `date_basis=layoff_date`. The PAGE accepts only
 * `effective` or `notice` and silently ignores anything else, which would
 * leave the reader on the filing basis: the exact discrepancy this link
 * exists to remove, delivered by the link that promised to remove it. They
 * mean the same quantity. Do not "tidy" them into one spelling.
 *
 * WHY THE EMPTY PARAMETERS ARE NOT CLUTTER. The page restores a returning
 * visitor's saved filters from sessionStorage BEFORE it reads the URL, and a
 * key present-but-empty clears that control while a key absent leaves their
 * old filter ANDed into our number. So every filter this link does not set is
 * set to nothing on purpose. Both forms were checked live on a clean session.
 *
 * WHAT IS STILL NOT GUARANTEED, and why no sentence claims otherwise. The
 * page can be told to SET `ai`, `ai_broad` and `stage` from a URL but not to
 * clear them, so a reader who ticked "AI only" earlier in the same session
 * lands on a smaller number. That cannot be fixed from here. The email
 * therefore drops the false caveat and makes no claim of reconciliation in
 * its place: a silent correct link beats a promise with an exception.
 */
function alt_digest_tracker_url($from, $to, $filters = array()) {
    $from = substr(trim((string) $from), 0, 10);
    $to = substr(trim((string) $to), 0, 10);
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $from)) return home_url('/ai-layoff-tracker/');
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $to)) return home_url('/ai-layoff-tracker/');
    $pairs = array(
        'from=' . rawurlencode($from),
        'to=' . rawurlencode($to),
        // The page's spelling of the composer's `layoff_date`. See above.
        // NEVER OMITTED, on any link this function builds, including the
        // filtered ones added on 2026-08-19. The page defaults to the FILING
        // basis, so a link built from an effective-basis figure and carrying no
        // basis lands on a page showing a different number under a label
        // promising the same one. That defect has been fixed twice on the press
        // page and once here; tests/test_digest_link_basis.py now fails on any
        // digest link that does not name it.
        'date_basis=' . rawurlencode(alt_digest_layoff_basis('link')),
    );
    /*
      Cleared, not omitted, and the trailing `=` is written by hand.

      add_query_arg() drops the `=` from an empty value, so the first live
      preview emitted `&years&quarters&months&country` rather than
      `&years=&quarters=`. URLSearchParams does read a bare key as an empty
      value, so that URL happened to work, but it worked by accident: the
      whole point of these keys is that the page can tell "present and empty",
      which clears the control, from "absent", which leaves a returning
      reader's saved filter ANDed into our number. A form that depends on a
      parser's tolerance for a malformed pair is not a form to ship on a link
      whose job is to reproduce a published figure. Built as a string so the
      bytes are the bytes.
    */
    /*
      A FILTER IS SET OR IT IS CLEARED, and either way the key is written.

      $filters carries the one or two controls a particular link is about: a
      country list for a regional line, an industry for an industry line. Every
      OTHER control is still written empty, because "present and empty" is what
      clears a returning reader's saved filter and "absent" is what leaves it
      ANDed into the number we just published. A link whose whole job is to
      reproduce a figure cannot leave a stale filter in the sum.

      WHAT THE HEADLINE ON THAT PAGE WILL SAY. The tracker's headline stats run
      on the STRICT job-location basis (assets/layoffs.js, currentParams), which
      is the same basis every figure in this section counts on, so a country
      link reproduces the figure beside it exactly. The results TABLE below that
      headline uses `country_basis=any`, which unions employer domicile, so it
      lists more rows than the headline counts. That is the page's documented
      and intentional behaviour, it is labelled there, and it is why these links
      promise a VIEW and a headline rather than a row count.
    */
    $set = array();
    foreach ((array) $filters as $key => $value) {
        $value = is_array($value) ? implode(',', $value) : (string) $value;
        if (trim($value) === '') continue;
        $set[$key] = $value;
    }
    foreach (array('years', 'quarters', 'months', 'country', 'industry', 'state',
                   'sources', 'reasons', 'roles', 'company', 'keyword',
                   'min_jobs', 'q') as $blank) {
        $pairs[] = $blank . '=' . (isset($set[$blank]) ? rawurlencode($set[$blank]) : '');
    }
    return home_url('/ai-layoff-tracker/') . '?' . implode('&', $pairs);
}

/**
 * THE TALENT TRACKER, ON THIS WINDOW, AND OPTIONALLY ON ONE CATEGORY.
 *
 * THE DEFECT IT FIXES. The talent section's only link read "Open the Talent
 * Intelligence Tracker for August 10-16, 2026" and pointed at the bare page,
 * which opens on the tracker's own default window. The label promised a
 * window the URL did not carry. That is the same class of fault
 * alt_digest_tracker_url() exists for, one tracker over.
 *
 * THE PARAMETER NAMES ARE THE TALENT PLUGIN'S, NOT THIS ONE'S, and they are
 * deliberately not guessed. That page reads `since` and `until` for the
 * window, `pillar` for the four-value category vocabulary, and `funding=1`
 * as a predicate rather than a pillar, because a funding round is a field on
 * a row and not a category of row. There is no `date_basis` here and there
 * must not be: the talent tracker has one date, the day the source published.
 *
 * WHAT IS DELIBERATELY NOT COPIED FROM alt_digest_tracker_url(). That function
 * writes every unused filter as a bare `key=`, so a returning reader's saved
 * filter is CLEARED rather than left ANDed into our figure. Whether the talent
 * page honours an empty value the same way is UNVERIFIED from this repo, and
 * writing keys on a guess would be worse than not writing them: a parameter
 * the page does not understand can select nothing at all. So this writes only
 * the parameters it means. The consequence is stated rather than hidden: a
 * reader who left a filter set on that page may see a smaller number than the
 * one beside the link. Verify the clearing behaviour on the live page before
 * closing that gap, and close it here when it is known.
 *
 * THE TALENT TRACKER IS A SEPARATE PLUGIN. This composes a URL for it and
 * reads its REST API, which is what this composer has always done. Nothing
 * here edits it, and a change to how that page parses a URL belongs there.
 */
/**
 * THE ONE BASIS THE LAYOFF DIGEST COUNTS ON, IN BOTH ITS SPELLINGS.
 *
 * WHY THIS FUNCTION EXISTS RATHER THAN TWO STRING LITERALS.
 *
 * Every figure in the layoff section is counted on the EFFECTIVE basis, the
 * day the jobs end. The composer asks /aggregate for it as
 * `date_basis=layoff_date`, which is that endpoint's column name. The tracker
 * page spells the same basis `date_basis=effective`, which is that page's
 * control value. Two names, one basis, and until now they were four separate
 * string literals in four places with nothing but a comment holding them
 * together.
 *
 * THAT IS EXACTLY THE DRIFT THIS REPO KEEPS PAYING FOR. The link losing its
 * basis has been fixed on the press page twice and in this composer once. The
 * next form of the same defect is not a missing parameter, it is a link that
 * still carries a basis while the figures beside it have quietly moved to a
 * different one, and no assertion in the suite could have caught that: the
 * link would still name A basis, and the test would still be green.
 *
 * So the query spelling and the link spelling are members of ONE array. A
 * change to either is a change to this function, and
 * tests/test_digest_link_basis.py reads the composer's real /aggregate
 * requests and its real anchors and fails when the pair they use is not the
 * pair this returns.
 *
 * $for is 'query' for the REST parameter and 'link' for the page's control.
 * An unknown key returns '', which reaches a caller as a missing parameter
 * rather than as a wrong one.
 */
function alt_digest_layoff_basis($for) {
    $basis = array('query' => 'layoff_date', 'link' => 'effective');
    return isset($basis[$for]) ? $basis[$for] : '';
}

/**
 * THE ONE ENTRY THAT IS THE WHOLE STORY, when there is one.
 *
 * WHAT THIS ANSWERS. An external editorial review read a week whose worldwide
 * total was ~61% one employer, and essentially all of the AI-attributed cuts
 * that same one employer, and found that fact buried below the AI block, the
 * source split and two tables. A reader who skims the top of the edition
 * leaves believing AI attribution surged across many employers, when it was a
 * single event. So when one entry dominates, it is surfaced immediately under
 * the two headline figures, in one plain sentence, keyed on the data and not
 * hard-coded to any company.
 *
 * TWO TRIGGERS, EITHER SUFFICES:
 *   - the largest single entry is >= SHARE_FLOOR of the worldwide total that
 *     CONTAINS it (a "concentrated" week); OR
 *   - a single verified entry accounts for essentially all of the week's
 *     AI-attributed verified cuts (the sole AI-attribution driver), which is
 *     the misread the review actually caught.
 *
 * TIER IS NEVER MIXED. A verified entry's share is taken against the verified
 * worldwide total the headline shows; an announced entry sits OUTSIDE that
 * total, so its share is taken against the announced-inclusive one, and the
 * sentence names which denominator it used. A share is only ever
 * entry / (a total that contains the entry).
 *
 * RETURNS array('event' => <sentence or ''>, 'interpretation' => <sentence or
 * ''>, 'concentrated' => bool). Both sentences are '' when no entry dominates,
 * because a line that always fires is decoration - the same discipline
 * alt_digest_composition_note() follows. The event sentence names the window,
 * so a line lifted out on its own still says what it covers.
 */
function alt_digest_dominant_event($leaders, $ver_jobs, $all_jobs,
                                   $ai_verified_jobs, $range) {
    $empty = array('event' => '', 'interpretation' => '', 'concentrated' => false);
    $leaders = is_array($leaders) ? $leaders : array();
    // The single largest entry by job count. db.php orders leaders by
    // job_count DESC, but the maximum is taken defensively rather than trusting
    // position, because a share is too load-bearing to rest on an ordering.
    $top = null;
    foreach ($leaders as $l) {
        $l = (array) $l;
        $jobs = (int) ($l['job_count'] ?? 0);
        if ($jobs <= 0) continue;
        if ($top === null || $jobs > (int) $top['job_count']) $top = $l;
    }
    if ($top === null) return $empty;
    $jobs = (int) $top['job_count'];
    $company = trim((string) ($top['company_name'] ?? ''));
    if ($company === '' || $range === '') return $empty;

    $tier_known = array_key_exists('announced', $top);
    $announced = !empty($top['announced']);
    $ai = !empty($top['ai_explicit']);

    if ($tier_known && $announced) {
        $denom = (int) $all_jobs;
        $denom_label = 'the ' . alt_digest_number($all_jobs)
                     . ' job cuts worldwide once announced estimates are included';
        $tier_word = 'announced ';
    } else {
        $denom = (int) $ver_jobs;
        $denom_label = 'the ' . alt_digest_number($ver_jobs)
                     . ' verified job cuts worldwide';
        $tier_word = $tier_known ? 'verified ' : '';
    }
    if ($denom <= 0) return $empty;

    $share = 100.0 * $jobs / $denom;
    $SHARE_FLOOR = 40.0;
    $concentrated = ($share >= $SHARE_FLOOR);

    // THE AI-ATTRIBUTION DRIVER. A single verified, employer-attributed entry
    // that is essentially all of the week's AI-attributed verified cuts. The
    // 0.80 floor lets one entry among a few small others still count as "the
    // driver" without claiming to be the whole of it; the wording below says
    // "all" only when it literally is.
    $ai_driver = ($ai && !$announced && (int) $ai_verified_jobs > 0
                  && $jobs >= 0.80 * (int) $ai_verified_jobs);

    if (!$concentrated && !$ai_driver) return $empty;

    $place = alt_digest_place($top['state'] ?? '', $top['country'] ?? '',
                              $top['location'] ?? '');
    $where = ($place !== '') ? (' in ' . $place) : '';
    // A whole-number percent: above the 40% floor there is no sub-1% case the
    // decimal branch elsewhere guards, so this reads as a share and not a
    // measurement pretending to precision it does not have.
    $pct = (string) round($share) . '%';

    // The window leads the sentence so the whole line carries a year, which is
    // the property every figure-bearing line in this section holds.
    $event = 'One entry dominated ' . $range . ': ' . $company . '\'s '
           . alt_digest_number($jobs) . ' ' . $tier_word . 'job cuts' . $where
           . ' were ' . $pct . ' of ' . $denom_label;
    if ($ai_driver) {
        $all_or_most = ($jobs >= (int) $ai_verified_jobs) ? 'all' : 'most';
        $event .= ', and account for ' . $all_or_most
                . ' of the week\'s AI-attributed cuts';
    }
    $event .= '.';

    // ONE DERIVED SENTENCE OF INTERPRETATION, and it is derived, never a guess.
    // What changed this week beyond the numbers: whether the total is one
    // employer's decision or a broad shift. Three cases, each read off the same
    // two facts the event line used.
    if ($concentrated) {
        $interp = 'This week the worldwide total is one employer\'s story '
                . 'rather than a broad shift across many.';
    } elseif ($ai_driver) {
        $interp = 'This week\'s AI attribution came from a single employer, '
                . 'not a broad shift across many.';
    } else {
        $interp = '';
    }

    return array('event' => $event, 'interpretation' => $interp,
                 'concentrated' => $concentrated);
}

function alt_digest_talent_url($from, $to, $filters = array()) {
    $base = home_url('/talent-intelligence-tracker/');
    $from = substr(trim((string) $from), 0, 10);
    $to = substr(trim((string) $to), 0, 10);
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $from)) return $base;
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $to)) return $base;
    $pairs = array('since=' . rawurlencode($from), 'until=' . rawurlencode($to));
    foreach ((array) $filters as $key => $value) {
        $value = is_array($value) ? implode(',', $value) : (string) $value;
        if (trim($value) === '') continue;
        $pairs[] = rawurlencode((string) $key) . '=' . rawurlencode($value);
    }
    return $base . '?' . implode('&', $pairs);
}

/**
 * WHAT SHAPE THIS PERIOD HAS, DERIVED, or nothing at all.
 *
 * THE GAP THIS FILLS. Read cold, the digest's figures are now impeccably
 * scoped: every number states its window, its tier, its date basis and its
 * geography. And no number says what it MEANS. "The biggest cuts this week
 * were food, retail and logistics, not technology" is already sitting in the
 * industry table, and no line said it. That is the distance between a data
 * dump and something a person forwards.
 *
 * THE RULE THAT MAKES IT SAFE: IT IS DERIVED, NEVER WRITTEN. A sentence like
 * that as prose in a template is wrong the first week the data changes shape,
 * which is the fixed-prose-around-variable-data fault this file has now
 * logged four times. So every word of it is computed from the SAME rows the
 * table above it prints, and it returns '' whenever the period has no shape
 * worth naming. A line that always fires is decoration.
 *
 * WHEN IT SAYS NOTHING, and each floor is here for a reason:
 *
 *   - Fewer than MIN_RANKED industries. "The three largest" out of three is
 *     not a finding, it is the list read aloud.
 *   - The classified rows cover less than COVER_FLOOR of the headline. The
 *     composition of the classified part is not the composition of the
 *     period, and asserting it would be the one thing this file may not do.
 *     Measured live on 2026-08-17 that coverage was 95%; on a thin window it
 *     is a third, and on a third this line must not appear.
 *   - The top three are less than CONCENTRATION of what was classified. A
 *     top three that is 35% of a long tail is not a shape.
 *
 * THE TECHNOLOGY CLAUSE is a documented editorial rule and not a hidden one:
 * this product is the AI Layoff Tracker, so technology is the sector its
 * reader is actually asking about. It fires only when technology is present
 * in the data AND ranked outside the top three, it prints technology's real
 * rank and real share, and it asserts nothing about what anybody expected.
 * If technology is not in the data we say nothing about it rather than
 * reporting a zero we did not measure.
 *
 * $block is the raw top_industries payload, because the ranked list the
 * caller holds has already been cut to five and a rank of ninth cannot be
 * read off a list of five.
 */
function alt_digest_composition_note($block, $headline, $span) {
    $MIN_RANKED = 4;
    $COVER_FLOOR = 0.6;
    $CONCENTRATION = 0.5;

    $all = array();
    foreach ((is_array($block) ? $block : array()) as $row) {
        $row = array_values((array) $row);
        $name = trim((string) ($row[0] ?? ''));
        $value = (int) ($row[4] ?? 0);   // the verified tier, as everywhere
        if ($name === '' || $value <= 0) continue;
        $all[$name] = $value;
    }
    arsort($all, SORT_NUMERIC);
    if (count($all) < $MIN_RANKED) return array('', '');

    $covered = array_sum($all);
    $headline = (int) $headline;
    if ($headline <= 0 || $covered < $COVER_FLOOR * $headline) return array('', '');

    $names = array_keys($all);
    $top3 = array_slice($names, 0, 3);
    $top3_jobs = 0;
    foreach ($top3 as $n) $top3_jobs += $all[$n];
    if ($top3_jobs < $CONCENTRATION * $covered) return array('', '');

    $line = $top3[0] . ', ' . $top3[1] . ' and ' . $top3[2]
          . ' are the three largest, ' . round(100 * $top3_jobs / $covered)
          . '% of the ' . alt_digest_number($covered)
          . ' verified job cuts we classified by industry ' . $span . '.';
    $tech = '';

    // Rank is 1-based and read off the FULL list, which is why this function
    // takes the raw block rather than the five rows the caller printed.
    $rank = 0; $tech_key = '';
    foreach ($names as $i => $n) {
        // The stored label is matched case-insensitively and then the REAL
        // key is kept: looking the value up by the literal 'Technology' after
        // a case-insensitive match is how you read an undefined index.
        if (strcasecmp($n, 'Technology') === 0) { $rank = $i + 1; $tech_key = $n; break; }
    }
    if ($rank > 3) {
        $ordinals = array(4 => 'fourth', 5 => 'fifth', 6 => 'sixth', 7 => 'seventh',
                          8 => 'eighth', 9 => 'ninth', 10 => 'tenth');
        // Past tenth the word is worse than the numeral, so the numeral wins.
        $place = isset($ordinals[$rank]) ? $ordinals[$rank] : ('number ' . $rank);
        $share = 100 * $all[$tech_key] / $covered;
        // A share that rounds to 0% would read as "technology is absent", and
        // it is not: it is present and small. One decimal below 1%.
        $shown = $share < 1 ? number_format($share, 1) : (string) round($share);
        /*
          RETURNED SEPARATELY, AND THAT IS THE WHOLE CHANGE HERE.

          "Technology is ninth, at 1%" was appended to the sentence above and
          rendered with it, in grey, at note size. The owner read the delivered
          email and picked that clause out as the most striking thing in it,
          thrown away. He is right: on a tracker named for AI, the sector every
          reader assumes is being cut ranking ninth is a finding, and it was
          set as the tail of another finding.

          It comes back as its own string so the composer can give it its own
          weight. Nothing about how it LOOKS is decided here; the composer
          marks it and railway/digest_layout.py styles it, as everywhere else
          in this file. The two floors are unchanged: it fires only when
          technology is present in the data AND ranked outside the top three,
          and it asserts nothing about what anybody expected.
        */
        $tech = 'Technology is ' . $place . ', at ' . $shown . '%.';
    }
    return array($line, $tech);
}

/**
 * THE CITATION. What a reporter has to write down to quote a figure in here.
 *
 * WHY AN EMAIL NEEDS ONE AT ALL. Every other surface we publish is a live
 * page: a reader who quotes it can go back and re-read it. This email is a
 * SNAPSHOT. The figures were read once, at compose time, and they never move
 * again, while the database behind them keeps moving. So the email is the one
 * surface where the number and the source have already been separated by the
 * time anybody quotes it, and it was the one surface carrying no citation.
 *
 * WHAT THE STANDARDS ACTUALLY ASK FOR, and why this is three facts and not a
 * paragraph. Chicago says to include an access date "for a source that does
 * not list a date of publication, posting, or revision", preferring a
 * last-modified stamp where one exists. APA 7 asks for a retrieval date only
 * when a source "is designed to change over time" and is not archived. The
 * FORCE11 data-citation principles ask for enough specificity to identify the
 * exact timeslice cited. The World Bank's own guidance publishes TWO forms, a
 * long one for a bibliography and a short "Source: ..." one for a chart
 * footer, which is the split used here: the source line lives under the
 * figure, and this block is the bibliography entry.
 *
 * So a reader gets all three: the window (which timeslice), the read date
 * (Chicago's access date, APA's retrieval date, and honest because this
 * snapshot really was taken then), and the last-modified stamp. Publishing
 * the last-modified stamp is what discharges the obligation properly; the
 * read date is what makes the frozen copy in their inbox verifiable.
 *
 * THE URL IS PLAIN TEXT AND NOT A LINK AT ALL, which took two goes to get
 * right. It cannot be click-wrapped: a citation is a string somebody PASTES,
 * and /wp-json/layoffs/v1/click?s=7&l=<hash> in a published story puts a
 * counter URL into the record instead of our address. The first attempt was
 * therefore a bare <a href> to the canonical page, and
 * test_digest_subscription caught it: the digest may not carry an uncounted
 * link to a destination it also links to through the counter, because then
 * the count means nothing. That guard is right and the exception was wrong.
 *
 * A citation is not a control. It is a reference string, the reader already
 * has a counted "Open the AI Layoff Tracker" link directly above it, and the
 * site's own cite box renders its URL in a <code> block rather than as a
 * link for the same reason. So this is escaped text. Do not make it an
 * anchor later: it would be the third route to one page and it would silently
 * hollow out the click counter.
 *
 * $label is alt_data_last_updated_label()'s, when api.php is loaded and the
 * table has ever been written to. An empty one prints NO last-changed
 * sentence rather than a guess, and the provisional sentence still goes out,
 * because that one is true whether or not we can date the last write.
 */
function alt_digest_cite_note($name, $range, $url, $read_date, $label) {
    /*
      THE LAST-MODIFIED STAMP IS PART OF THE REFERENCE, not a sentence after
      it. Chicago prefers a last-modified date and asks for an access date
      alongside it; APA asks for the retrieval date on a source designed to
      change. Both belong in the string somebody pastes, so both are in it.

      A missing stamp drops that clause and keeps the rest. It is not filled
      in from the access date: those are different facts, and conflating them
      would claim the database changed at the moment we happened to read it.
    */
    $cite = $name . ', AskTheRecruiter.com. Figures for ' . $range
          . ((string) $label !== '' ? ', as of ' . $label : '')
          . ', accessed ' . $read_date . '.';
    $note = array();
    /*
      "Usually rises, and a correction can lower it" is the honest pair, and
      the second half is not hedging. Late filings and WARN notices arrive for
      weeks after the event, so a recent window grows. But the public
      corrections log is full of rows that SHRANK: one Rhode Island notice
      went from 9,891 to 2 because it stated a company-wide figure under one
      state. Writing "only rises" would have been the fixed-prose fault this
      file keeps logging, one dimension over.
    */
    $note[] = 'Filings and notices keep arriving, so a recent window is '
            . 'provisional: it usually rises, and a correction can lower it.';
    return array($cite, $url, implode(' ', $note));
}

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
    /*
      WHICH DATE THIS SECTION IS ABOUT, written down instead of inherited.

      This composer sent no date_basis, so alt_db_date_col() gave it the
      server default, `layoff_date`, the date the cuts take effect. The
      tracker PAGE defaults to `notice`, COALESCE(announcement_date,
      layoff_date), the filing date. So the digest and the page it links to
      have always meant different windows, and the digest named neither.

      Naming the effective basis is not a coin toss. leaders[] carries
      layoff_date and no announcement_date, so asking for the notice basis
      would select rows by one date and then print another. alt_db_date_col()
      records what that costs: a view labelled 2026 that drew 2027 buckets.
      Here the window and the printed dates are the same quantity, and the
      copy below says which one it is.
    */
    $req->set_param('date_basis', alt_digest_layoff_basis('query'));
    /*
      `include` is an OPT-IN allowlist (alt_aggregate_blocks). `include=leaders`
      alone therefore returned `top_countries` as an empty array, which is why
      the country block at the foot of this section could not be built. Both
      blocks this section reads have to be named. `totals` is always computed
      and is not a nameable block, so it does not go here, and an unrecognised
      name falls back to all ~31 statements: do not tidy these into one word.

      `top_industries` and `source_types` joined the list on 2026-08-17. They
      are the two blocks that make this email actionable for somebody who is
      not already watching the tracker: an industry is what a recruiter or a
      job hunter recognises as their own patch, and the source split is the
      provenance a reporter needs before quoting anything. Both come out of
      the SAME response as the headline, so they cannot describe a different
      filter set than the number they sit under.

      `top_states`, `reasons` and `top_roles` joined the list on 2026-08-25,
      and each answers a question a reader of a layoff tracker asks and the
      section could not answer: which US state, why the employer said, and
      which teams. They render below in the same verified-tier, windowed,
      top-five style as `top_industries`, out of this SAME response, so none of
      them can describe a different window or tier than the headline. Two of
      them OVERLAP by construction and their blocks say so: `reasons` and
      `top_roles` are LIKE-over-packed-tags, an entry can carry several, so
      they do not sum to the headline and carry no reconciliation note.
      `top_states` is a US-only subset for the same reason.
    */
    $req->set_param('include', 'leaders,top_countries,top_industries,source_types,top_states,reasons,top_roles');
    $res = rest_do_request($req);
    if (!$res || $res->is_error()) return null;
    $data = $res->get_data();
    $totals = is_array($data) ? ($data['totals'] ?? null) : null;
    if (!is_array($totals) && is_object($totals)) $totals = (array) $totals;
    if (!$totals || (int) ($totals['entries'] ?? 0) === 0) return null;

    /*
      NO SECTION WITHOUT A WINDOW. Every figure below names the dates it
      covers, and the words come from here. The caller builds these two dates
      itself, so this cannot fail in practice; if it ever does, the section is
      dropped rather than sent with a figure whose scope a reader would have to
      infer. That is the whole point of the rewrite.
    */
    $range = alt_digest_date_range($from, $to);
    if ($range === '') return null;
    // The same window worded to sit inside a sentence. Two forms, because the
    // label goes in front of a caption and this one goes after a preposition.
    // See alt_digest_span_phrase for the sentence the owner sent back.
    $span = alt_digest_span_phrase($from, $to);
    if ($span === '') return null;

    $url = home_url('/ai-layoff-tracker/');
    /*
      WHICH TIER THIS SENTENCE COUNTS, and why it is now two sentences.

      This read "{entries} verified entries totalling {jobs} job cuts across
      {companies} companies", off `totals.entries` and `totals.jobs`. Both of
      those are verified PLUS announced. Measured on 2026-08-16 over
      2026-01-01..2026-08-15: jobs 971,479 against announced_jobs 463,348, so
      the word "verified" sat on a figure that was 48% announced, and entries
      3,384 against announced_entries 604. The tracker page's hero publishes
      `jobs - announced_jobs` under the label "verified job cuts", so the
      digest and the page it links to printed different quantities under the
      same word, and the digest's was the larger one.

      The fix is the shape the hero already uses (owner decision 2026-08-14):
      the VERIFIED figure leads, the announced-inclusive total follows as a
      labelled companion, and alt_announced_tier_sentence() says what the
      second tier is, verbatim and shared with page-tracker, page-press and
      page-report. So a reader meeting an announcement estimate elsewhere
      meets both tiers here rather than neither.

      COMPANIES MOVED TO THE SECOND SENTENCE, and that is not cosmetic.
      `companies` is COUNT(DISTINCT company_key) over the whole filtered set
      (db.php), with no announced/verified split shipped, so it is an
      announced-INCLUSIVE count. Leaving it in the first sentence would put a
      two-tier number inside a clause the word "verified" governs, which is
      the mixed-scope defect this file keeps logging. Do not move it back
      without a verified_companies field to move it with.

      When the window holds no announced rows the two tiers are the same
      number, so printing both would be the same figure twice under two
      labels. That branch says so in words instead: "All N entries in RANGE
      are verified... The window holds no announced estimates." A reader
      learns the tier is empty, which is a fact, rather than meeting a
      companion figure identical to the one above it.
    */
    $all_jobs = (int) ($totals['jobs'] ?? 0);
    $all_entries = (int) ($totals['entries'] ?? 0);
    $ann_jobs = (int) ($totals['announced_jobs'] ?? 0);
    $ann_entries = (int) ($totals['announced_entries'] ?? 0);
    $ver_jobs = max(0, $all_jobs - $ann_jobs);
    $ver_entries = max(0, $all_entries - $ann_entries);
    $companies_n = (int) ($totals['companies'] ?? 0);
    $has_announced = ($ann_jobs > 0 || $ann_entries > 0);

    /*
      THE TOP FIVE ON THE TIER WE ACTUALLY PRINT, WHICH MEANS RE-SORTING.

      The endpoint orders these rows by column [1], the announced-inclusive
      total, because that is what the tracker page's bar charts draw. This
      block prints column [4], the verified tier, so taking the endpoint's
      first five would label a list "the largest" that is not sorted by the
      number beside it. On the live week of 2026-08-16 that put Media and
      Entertainment second on 75 verified jobs, above Food and Hospitality on
      2,505. The rows are re-sorted here, and only then cut to five.

      IT IS DECLARED AND CALLED UP HERE, ABOVE THE HEADLINE, because the
      headline needs its third return value. `$covered` is what tells
      alt_digest_geo_scope() whether "worldwide" is the whole story for this
      window or whether some of the total sits on entries we cannot place.
      The tables themselves are still printed further down, in reading order.
    */
    $verified_split = function ($block) {
        $all = array(); $multi = 0; $covered = 0;
        foreach ((is_array($block) ? $block : array()) as $row) {
            $row = array_values((array) $row);
            $name = trim((string) ($row[0] ?? ''));
            // Column 4 is the verified tier. Column 1 includes announced.
            $value = (int) ($row[4] ?? 0);
            if ($name === '' || $value <= 0) continue;
            $covered += $value;
            if (strcasecmp($name, 'Multiple countries') === 0) { $multi = $value; continue; }
            $all[$name] = $value;
        }
        arsort($all, SORT_NUMERIC);
        /*
          THE WHOLE MAP, NOT THE TOP FIVE. It used to slice here, and the
          regional grouping added on 2026-08-19 cannot be built from five rows:
          a region is the sum of every country in it, and Europe read off the
          top five would be Germany alone. The callers that want a top five
          slice it themselves, one line later, which is also where a reader can
          see that they do.
        */
        return array($all, $multi, $covered);
    };
    list($countries_all, $multi, $covered) = $verified_split($data['top_countries'] ?? null);
    $named = array_slice($countries_all, 0, 5, true);

    /*
      THE UNITED STATES FIGURE, OUT OF THE SAME RESPONSE AS THE WORLDWIDE ONE.

      THE OWNER'S DECISION, and it is not a toss-up any more: "Lets do both as
      we need both showing." Two headline figures, the United States and
      worldwide, side by side, both labelled.

      WHY IT IS READ OFF top_countries AND NOT FETCHED. A second /aggregate
      call with country=United States would be a second query, at a second
      moment, and nothing would hold it to the same tier or the same basis as
      the figure beside it. Two numbers printed side by side are read as
      comparable whether or not they are, so they are taken from ONE response:
      column [4] of the country row is SUM(job_count) WHERE announced = 0, the
      identical quantity the worldwide headline counts, and the country column
      is the strict job location rather than the employer's domicile. They are
      the same tier, the same window, the same basis and the same read, by
      construction rather than by care.

      Column [5] is the same row's ai_verified_jobs, which is where the US half
      of the AI pair comes from, for the same reason and with the same
      guarantee.
    */
    $us_jobs = 0; $us_ai = 0;
    foreach ((is_array($data['top_countries'] ?? null) ? $data['top_countries'] : array()) as $row) {
        $row = array_values((array) $row);
        if (strcasecmp(trim((string) ($row[0] ?? '')), 'United States') !== 0) continue;
        $us_jobs = (int) ($row[4] ?? 0);
        $us_ai = (int) ($row[5] ?? 0);
        break;
    }

    /*
      THE WEEK BEFORE, AND THIS REVERSES A RULE THIS FILE USED TO HOLD.

      The year-to-date block still carries the comment that argued against a
      period-over-period delta: this data revises upward for weeks, so a
      week-on-week line risks turning a collection lag into a fall that never
      happened. See alt_digest_change() for why that conclusion no longer
      follows and what makes the comparison honest instead. The short version
      is that the window is now a COMPLETE week rather than one ending on the
      send day, so both sides of the comparison have settled for a known and
      equal-by-construction difference of seven days, and the sentence under
      the pair says which side is the less complete one.

      ONLY ON A SEVEN DAY WINDOW. The daily tier covers two days, is
      provisional by design and says so, and a day-on-day delta on it would be
      noise dressed as a finding. The window's own length is the gate, so the
      composer does not need to be told which tier it is composing for.

      A FAILED CALL PRINTS NO COMPARISON. It does not print a zero, it does not
      carry the previous week forward, and it does not fall back to a different
      window. An absent comparison is an absent line.
    */
    $prior_us = null; $prior_all = null; $prior_label = '';
    $ft = strtotime($from . ' 00:00:00 UTC');
    $tt = strtotime($to . ' 00:00:00 UTC');
    if ($ft !== false && $tt !== false && ($tt - $ft) === 6 * DAY_IN_SECONDS) {
        $p_from = gmdate('Y-m-d', $ft - 7 * DAY_IN_SECONDS);
        $p_to = gmdate('Y-m-d', $tt - 7 * DAY_IN_SECONDS);
        $p_req = new WP_REST_Request('GET', '/layoffs/v1/aggregate');
        $p_req->set_param('from', $p_from);
        $p_req->set_param('to', $p_to);
        $p_req->set_param('date_basis', alt_digest_layoff_basis('query'));
        $p_req->set_param('include', 'top_countries');
        $p_res = rest_do_request($p_req);
        if ($p_res && !$p_res->is_error()) {
            $p_data = $p_res->get_data();
            $p_tot = is_array($p_data) ? ($p_data['totals'] ?? null) : null;
            if (!is_array($p_tot) && is_object($p_tot)) $p_tot = (array) $p_tot;
            if (is_array($p_tot)) {
                $prior_all = max(0, (int) ($p_tot['jobs'] ?? 0) - (int) ($p_tot['announced_jobs'] ?? 0));
                $prior_us = 0;
                foreach ((is_array($p_data['top_countries'] ?? null) ? $p_data['top_countries'] : array()) as $row) {
                    $row = array_values((array) $row);
                    if (strcasecmp(trim((string) ($row[0] ?? '')), 'United States') !== 0) continue;
                    $prior_us = (int) ($row[4] ?? 0);
                    break;
                }
                $prior_label = alt_digest_week_label($p_from);
            }
        }
    }
    /*
      IS THE PERCENTAGE LIKE FOR LIKE YET. This data revises UPWARD for weeks:
      filings and WARN notices arrive after the event, so the newest window is
      always the least complete one we hold. A weekly digest composes one to
      three days after its window closes, and the comparison week has had seven
      more days to settle by construction. Publishing a confident "-42%" that
      rests on a window with barely any days to settle turns a collection lag
      into a fall that never happened - exactly the misread an editorial review
      flagged.

      So the NUMBER is withheld until the current window has settled at least a
      full week, which is the earliest most of its late arrivals are in. Before
      that the DIRECTION is still stated (it is the sign of a real difference)
      but the number is replaced by a visible "early, not like for like" flag,
      and the maturity sentence lower down quantifies the exact day gap either
      way. This is deliberately conservative: on the intended Monday send the
      current window has settled two or three days against the prior week's
      nine or ten, which is not comparable, and the reader is told so rather
      than handed a precise-looking figure.

      $settle_days is the current window's own age, computed from its end date
      against the day the digest composes. A run forced on another day says
      whatever is true that day. It is read once here so the change phrase and
      the maturity note cannot disagree about it.
    */
    $PCT_MIN_SETTLE_DAYS = 7;
    $settle_days = null;
    $now_ts = strtotime(gmdate('Y-m-d') . ' 00:00:00 UTC');
    $end_ts = strtotime($to . ' 00:00:00 UTC');
    if ($now_ts !== false && $end_ts !== false) {
        $settle_days = (int) floor(($now_ts - $end_ts) / DAY_IN_SECONDS);
    }
    $pct_like_for_like = ($settle_days !== null && $settle_days >= $PCT_MIN_SETTLE_DAYS);

    /*
      THE DIRECTION IN WORDS AND IN A GLYPH, and the words work without it.

      $with_glyph is false for the LEAD, because a triangle inside a sentence
      is read aloud by a screen reader as "black down pointing triangle" and is
      silent in a plain-text part that has no room for it. The figure block
      carries the glyph, where it is a mark beside a number rather than a word
      inside a clause. Both halves say the same thing, which is the point: the
      glyph is redundant on purpose, so nothing is lost when a client, a
      reader or a text part drops it.
    */
    $change_phrase = function ($now, $before, $with_glyph = true)
            use ($prior_label, $pct_like_for_like) {
        if ($before === null) return '';
        $c = alt_digest_change($now, $before);
        if ($c === null) return '';
        list($word, $glyph, $pct) = $c;
        // "from Week 32", matching the lead word for word. The lead and the
        // figure block state the same comparison and must not spell it two ways.
        $on = ($prior_label === '') ? 'the week before' : ('from ' . $prior_label);
        if ($word === 'level with') {
            $words = 'level with ' . $on;
        } elseif ($pct === '') {
            // No base to take a percentage of (the prior window was zero).
            // State the direction without a number, and without the settling
            // flag: this is about an absent denominator, not about maturity.
            $words = $word . ' ' . $on;
        } elseif (!$pct_like_for_like) {
            // The number would rest on a window too fresh to compare. State
            // the direction and flag it, never the figure. See the note above.
            $words = $word . ' ' . $on . ' (early, not like for like)';
        } else {
            $words = $word . ' ' . $pct . ' ' . $on;
        }
        return $with_glyph ? ($glyph . ' ' . $words) : $words;
    };

    /*
      THE EDITION LINE, AND THE LEAD UNDER IT.

      WHAT THE OWNER READ AND WHAT HE SAID. "The whole weekly newsletter is
      confusing." He is right, and the complaints he listed are symptoms rather
      than the fault: the message opened on a figure, then a provenance
      sentence, then a tier sentence, then a buried AI line, then three tables.
      Nothing told him what had happened. A reader has to be able to learn the
      story in two lines and stop there.

      So the section now opens the way a data edition opens. A DATELINE naming
      the week, the tier and the basis. A LEAD of at most three short sentences,
      every word of which is DERIVED from the same response the tables below
      print. Then a WHY IT MATTERS line, which is Axios's, and which is
      deliberately a statement about the METRIC rather than about this week: a
      sentence that explains what an explicit AI attribution is cannot become
      false when the data moves, and a sentence that characterised the week
      would be the fixed-prose-around-variable-data fault this file has now
      logged five times.

      THE LEAD IS BUILT FROM CLAUSES THAT CAN EACH BE ABSENT. No comparison, no
      comparison clause. The floors that govern the composition sentence are
      unchanged and it is still allowed to say nothing.
    */
    // A MIDDLE DOT AND NOT AN EMOJI. U+00B7 is a geometric character every
    // client and every terminal already renders; an emoji used as furniture is
    // a coloured picture in half of them and a box in the other half.
    $sep = " \xc2\xb7 ";
    /*
      "PROVISIONAL" IS IN THE DATELINE, WHICH IS AHEAD OF EVERY FIGURE.

      The maturity sentence lower down qualifies the two headline figures. It
      cannot qualify the lead, which states a direction one line below this and
      is the part most likely to be quoted on its own. A dateline is where a
      data edition states the status of its whole run, so it states it here,
      once, before a reader has read a number.
    */
    $dateline = alt_digest_edition_label($from, $to) . $sep . 'verified job cuts'
              . $sep . 'counted by the date the cuts take effect'
              . $sep . 'provisional';

    $lead = array();
    $us_change = $change_phrase($us_jobs, $prior_us, false);
    $all_change = $change_phrase($ver_jobs, $prior_all, false);
    /*
      THE LEAD OPENS ON ITS WINDOW, and that is a rule and not a style choice.
      A line of this email lifted out on its own has to still be true and still
      say what it covers, which is the property this whole section is built to
      hold; the first render of the lead stated two figures and no window at
      all. It is the edition label, so the lead, the dateline above it, the
      masthead and the subject all name the same week in the same words.
    */
    /*
      SHORT SENTENCES, ONE FACT EACH, AND THE DATE OUT OF THE WAY.

      WHAT HE READ AND WHAT HE SAID ABOUT IT. "In Week 33, 10 to 16 August
      2026, employers verified 10,132 job cuts in the United States, up 53% on
      Week 32." He flagged it as not easy to read, and the fault is structural:
      three facts and two comparisons in one breath, with an eight-word date
      range wedged between the preposition and the subject, so a reader has
      parsed a date before they know what the sentence is about.

      The full range moves out. The dateline directly above already carries it,
      the masthead carries it, and the subject carries it, so a third copy in
      the lead is the reader's tax for our tidiness. What stays is the week and
      its YEAR: "Week 33" alone is ambiguous across years, and this line has to
      remain true when somebody quotes it on its own, which is the property
      every line of this section is built to hold.

      THE TWO GEOGRAPHIES SPLIT INTO TWO SENTENCES, because they are two facts
      and because they can point in opposite directions. On the live week of
      10 to 16 August the United States was up 53% while the world was down
      51%, and a single sentence carrying both reads as an error the reader has
      caught rather than a summary.
    */
    $opening = 'In Week ' . (($iso = alt_digest_iso_week($from)) ? $iso[1] : '')
             . ' of ' . (($iso) ? $iso[0] : substr((string) $to, 0, 4))
             . ', employers verified ';
    if ($us_change !== '' && $us_jobs > 0) {
        $lead[] = $opening . alt_digest_number($us_jobs) . ' US job cuts, '
                . $us_change . '.';
        /*
          THE WORLDWIDE DIRECTION IS ITS OWN SENTENCE, AND IT HAS TO BE.

          The first render of this lead named only the United States and its
          direction, and the pair of figures underneath read "up 53%" beside
          "down 51%" in the same week. Both were correct: the prior week held a
          very large non-US cut. A lead that states one direction over a block
          showing two opposite ones does not read as a summary, it reads as an
          error the reader has caught. The two figures were made equals on
          purpose, so the lead treats them as equals.
        */
        if ($all_change !== '') {
            $lead[] = 'Worldwide, verified job cuts totalled '
                    . alt_digest_number($ver_jobs) . ', '
                    . $all_change . '.';
        } else {
            $lead[] = 'Worldwide, verified job cuts totalled '
                    . alt_digest_number($ver_jobs) . '.';
        }
    } else {
        $lead[] = $opening . alt_digest_number($us_jobs) . ' US job cuts.';
        $lead[] = 'Worldwide, verified job cuts totalled '
                . alt_digest_number($ver_jobs) . '.';
    }
    $ai_jobs_lead = (int) ($totals['ai_verified_jobs'] ?? 0);
    /*
      THE THIRD SENTENCE IS THE SIGNATURE METRIC, AND IT STAYS IN THE LEAD.

      The editorial standard is explicit that a zero week is not skipped, not
      moved below the fold and not softened. What it may NOT do is read as
      this week's news, because half the complete weeks of 2026 recorded zero,
      so it is stated as a measurement and its base rate lives with the figure
      in its own block below.

      "No employer explicitly named AI" and never "AI caused no layoffs": a
      null has two possible causes, a real absence and an instrument too weak
      to see it, and this product's AI-causation classifier has a precision
      that is currently UNKNOWN pending human review.

      THE "WHY IT MATTERS" LINE THAT USED TO BE HERE HAS MOVED to sit under the
      AI figure, which is where the owner put it in his own draft and where it
      belongs: it explains that figure, not the two above it.
    */
    $lead[] = ($ai_jobs_lead > 0)
        ? 'Employers explicitly named AI on '
          . alt_digest_number($ai_jobs_lead) . ' of the worldwide total.'
        : 'No employer explicitly named AI as a reason.';

    $html = '<h2>AI Layoff Tracker</h2>'
          . '<p data-alt="dateline">' . esc_html($dateline) . '</p>'
          . '<p data-alt="lead">' . esc_html(implode(' ', $lead)) . '</p>';
    // The dateline is in BOTH parts. A plain-text reader is not owed a shorter
    // email, only an unstyled one.
    $text = "AI Layoff Tracker\n" . $dateline . "\n"
          . implode(' ', $lead) . "\n";

    /*
      THE DENSE RECONCILIATION IS GATHERED, NOT SCATTERED.  (editorial trim)

      An editorial review found the edition read like a methodology note: the
      residual arithmetic that tells a reader how a figure was built - which
      rows link to a page, how much of the classified total the printed lines
      cover - was interleaved between the tables it qualifies, so the body was a
      third longer than the story needed. Those notes are collected here as they
      are computed and printed once, together, in a "Data notes" section just
      before the methodology, so the tables stay skimmable and nothing a caveat
      carried is lost. What STAYS beside its figure is the caveat a reader is
      doing arithmetic against as they read it: the provisional/like-for-like
      note and the missing-country sum under the two headlines. Only the
      build-detail residue moves.
    */
    $data_notes = array();

    /*
      THE TWO HEADLINES. See alt_digest_stat_pair for why they are one table
      and for the property the caller has to keep. The scope line under them
      states, ONCE and for both, the four things a figure has to carry: the
      tier, the window, the geography basis and the date basis.

      THIS IS WHERE "worldwide including entries with no country recorded"
      STOPPED BEING SAID THREE TIMES. It appeared in the headline scope, in the
      snippet, and again in the year block, in three phrasings, and the fact it
      carried is a real and important one: about a third of verified cuts sit
      on entries we cannot place. It is now said ONCE, here, in its own
      sentence, immediately under the two figures it actually qualifies, which
      is also the only place a reader is doing the subtraction that makes it
      matter.
    */
    /*
      THE TWO MOST IMPORTANT NUMBERS IN THE EDITION WERE THE ONLY ONES A
      READER COULD NOT CLICK. Every ranked row below them links to a tracker
      view that reproduces it; these did not, which is precisely backwards.

      The United States figure carries a country filter, the worldwide one
      carries none, and both carry this window and `date_basis=effective`. The
      page's headline stat runs on the strict job-location basis, the same
      basis these count on, so each link lands on a page whose headline is the
      number that was clicked. See alt_digest_tracker_url.
    */
    list($pair_html, $pair_text) = alt_digest_stat_pair(array(
        array('label' => 'United States',
              'figure' => alt_digest_number($us_jobs),
              'unit' => alt_digest_verb($us_jobs, 'verified job cut', 'verified job cuts'),
              'foot' => $change_phrase($us_jobs, $prior_us),
              'url' => alt_digest_track_link($send_id, alt_digest_tracker_url(
                           $from, $to, array('country' => 'United States')))),
        array('label' => 'Worldwide',
              'figure' => alt_digest_number($ver_jobs),
              'unit' => alt_digest_verb($ver_jobs, 'verified job cut', 'verified job cuts'),
              'foot' => $change_phrase($ver_jobs, $prior_all),
              'url' => alt_digest_track_link($send_id,
                           alt_digest_tracker_url($from, $to))),
    ));
    // THE PREPOSITIONAL FORM. "in August 10-16, 2026" is a label dropped after
    // a preposition, which is the machine-output reading the owner sent back
    // once already. See alt_digest_span_phrase.
    $scope = 'Both figures are verified job cuts ' . $span
           . ', counted where the jobs were and by the date the cuts take effect.';
    $unplaced = max(0, $ver_jobs - $covered);
    if ($unplaced > 0) {
        $reconcile = alt_digest_number($unplaced) . ' of the '
                   . alt_digest_count($ver_jobs, 'verified job cut')
                   . alt_digest_verb($unplaced, ' sits', ' sit')
                   . ' on entries with no country recorded. The United States figure '
                   . 'and the regions below therefore do not sum to the worldwide one.';
    } else {
        $reconcile = 'Every verified cut in this window carries a country, so the '
                   . 'regions below sum to the worldwide figure.';
    }
    /*
      WHAT MAKES THE COMPARISON HONEST, AND IT IS NOT THE ARITHMETIC.

      This file used to refuse a period-over-period delta outright, because the
      data revises upward for weeks and a fall can be a collection lag rather
      than a fall. The refusal is lifted (see alt_digest_change) and the reason
      for it is not, so the reason is PRINTED, next to the two figures that
      carry the direction, and only when a direction was actually printed.

      The two numbers are not invented and not rounded prose: they are the days
      each window has had to settle, computed from this window's own end date
      against the day the digest composes. On the intended Monday send they are
      two and nine. A run forced on another day says whatever is true that day.
    */
    /*
      THE WORD "PROVISIONAL" IS NO LONGER TRADED AWAY FOR THE ASYMMETRY.

      This used to REPLACE the provisional sentence with the day-count one
      whenever a comparison was printed, so the one edition that states a
      direction was the one edition that never used the word, and never said
      the figure usually rises. The owner read "down 51% from Week 32" as a
      collapse. A large part of that 51% is collection lag: Week 33 had had
      three days to settle and Week 32 had had ten.

      So the two sentences are ADDITIVE now. The first marks the window
      provisional and names both directions a correction can move it. The
      second is the asymmetry made concrete, which is stronger than a generic
      caveat because it hands the reader the actual gap, and it says in plain
      words that the comparison is not yet like for like.

      IT SITS FIRST IN THE QUALIFIER PARAGRAPH, directly under the two figures
      that carry the direction, rather than after the country reconciliation.
      A caveat a reader meets after an unrelated sentence about country
      coverage is a caveat in fine print.
    */
    $maturity = 'Filings and notices keep arriving, so this window is '
              . 'provisional: it usually rises, and a correction can lower it.';
    // Reuses $settle_days computed above, so the day gap the maturity note
    // states and the like-for-like gate on the percentage cannot disagree.
    if ($prior_all !== null && $settle_days !== null && $settle_days >= 0) {
        $maturity .= ' The comparison is not yet like for like: this week has had '
                  . alt_digest_count($settle_days, 'day') . ' to settle against '
                  . alt_digest_count($settle_days + 7, 'day') . ' for the week before it.';
    }
    /*
      TWO PARAGRAPHS, AND THIS REVERSES A NOTE THIS FILE USED TO HOLD.

      They were joined to stop five consecutive grey paragraphs stacking under
      the headline. Two is not five, and the two sentences answer different
      questions: one says the figures are provisional and the comparison is not
      yet like for like, the other says how much of the total carries no
      country. Run together, the provisional caveat became the front half of a
      sentence about country coverage, which is how a caveat ends up read as
      fine print. The maturity note goes first and alone, directly under the
      pair of figures that carries the direction it qualifies.
    */
    $html .= $pair_html
           . '<p data-alt="scope">' . esc_html($scope) . '</p>';
    $text .= "\n" . $pair_text . $scope . "\n";

    /*
      WHAT HAPPENED, IN ONE LINE, WHEN ONE ENTRY IS THE WHOLE STORY.

      An editorial review read a week that was ~61% one employer, and
      essentially all of the AI-attributed cuts that same employer, and found
      the fact buried below the AI block and two tables. A reader who skims the
      top left believing AI attribution had surged across many employers. So a
      dominant entry is surfaced HERE, immediately under the two headline
      figures, as one plain sentence, followed by one derived sentence of what
      that means for the week. Both are keyed on the data: on a week with no
      dominant entry alt_digest_dominant_event returns empty and nothing prints,
      because a line that always fires is decoration. See that function for the
      >=40% and sole-AI-driver triggers and for why the tiers are never mixed.
    */
    $dominant = alt_digest_dominant_event(
        $data['leaders'] ?? null, $ver_jobs, $all_jobs,
        (int) ($totals['ai_verified_jobs'] ?? 0), $range);
    if ($dominant['event'] !== '') {
        $html .= '<p data-alt="finding">' . esc_html($dominant['event']) . '</p>';
        $text .= $dominant['event'] . "\n";
    }
    if ($dominant['interpretation'] !== '') {
        $html .= '<p data-alt="standfirst">'
               . esc_html($dominant['interpretation']) . '</p>';
        $text .= $dominant['interpretation'] . "\n";
    }

    if ($maturity !== '') {
        $html .= '<p data-alt="note">' . esc_html($maturity) . '</p>';
        $text .= $maturity . "\n";
    }
    if ($reconcile !== '') {
        $html .= '<p data-alt="note">' . esc_html($reconcile) . '</p>';
        $text .= $reconcile . "\n";
    }

    /*
      THE YEAR TO DATE, FETCHED HERE AND RENDERED AT THE FOOT.

      WHY IT MOVED UP, AND ONLY THE FETCH MOVED. The AI block below has to
      print the cumulative figure beside the week's own, and it sits near the
      top of the edition while the year block sits at the bottom. One call,
      read twice, is the only way those two numbers cannot disagree; a second
      query would be a second moment and a second chance to differ.

      THE YEAR IS THE CALENDAR YEAR AND IS NOT TOUCHED BY THE ISO WEEK WORK.
      "2026" here means 1 January onward, because that is what every other
      surface we publish means by a year, and an annual total that quietly
      became an ISO year would disagree with all of them. The ISO year and the
      calendar year differ for a few days each January; when a window straddles
      that, the edition names both rather than picking one.

      The year comes from the period's own end date, not from the clock, so a
      run that composes a window is never labelled with a different year.
    */
    $ytd = array('ok' => false, 'jobs' => 0, 'ai' => 0, 'range' => '',
                 'unplaced' => 0, 'year' => '');
    $ytd_year = substr((string) $to, 0, 4);
    if (preg_match('/^\d{4}$/', $ytd_year)) {
        $ytd_req = new WP_REST_Request('GET', '/layoffs/v1/aggregate');
        $ytd_req->set_param('from', $ytd_year . '-01-01');
        $ytd_req->set_param('to', $to);
        $ytd_req->set_param('date_basis', alt_digest_layoff_basis('query'));
        /*
          `top_countries`, because this headline needs its OWN geography
          measurement. Borrowing the period's would be the adjacency fault
          again: a week where every cut is placed says nothing about a year
          where tens of thousands are not. `include` is an opt-in allowlist,
          so the block has to be named or it comes back empty.
        */
        $ytd_req->set_param('include', 'top_countries');
        $ytd_res = rest_do_request($ytd_req);
        $ytd_range = alt_digest_date_range($ytd_year . '-01-01', $to);
        if ($ytd_res && !$ytd_res->is_error() && $ytd_range !== '') {
            $ytd_data = $ytd_res->get_data();
            $ytd_totals = is_array($ytd_data) ? ($ytd_data['totals'] ?? null) : null;
            if (!is_array($ytd_totals) && is_object($ytd_totals)) $ytd_totals = (array) $ytd_totals;
            if (is_array($ytd_totals)) {
                $ytd_jobs = max(0, (int) ($ytd_totals['jobs'] ?? 0)
                                 - (int) ($ytd_totals['announced_jobs'] ?? 0));
                list(, , $ytd_covered) = $verified_split($ytd_data['top_countries'] ?? null);
                $ytd = array(
                    'ok' => $ytd_jobs > 0,
                    'jobs' => $ytd_jobs,
                    'ai' => (int) ($ytd_totals['ai_verified_jobs'] ?? 0),
                    'range' => $ytd_range,
                    'unplaced' => max(0, $ytd_jobs - $ytd_covered),
                    'year' => $ytd_year,
                );
            }
        }
    }

    /*
      THE FRIENDLY NAMES FOR THE COLLECTORS, DECLARED ONCE AND UP HERE.

      Two blocks read it now: the AI block's detection-power line, which names
      which collectors reported, and the provenance line below, which counts
      what each produced. It lives above both so the two cannot name the same
      collector two ways. "8K" is a form number and "warn" is lower case in the
      column, and neither is a thing to print at a reader.
    */
    $source_names = array(
        'warn' => 'state WARN filings',
        '8K'   => 'SEC 8-K filings',
        'news' => 'named news reports',
    );


    /*
      THE SIGNATURE METRIC, WHICH IS ALSO THE HARDEST BLOCK IN THE EDITION.

      WHAT THE OWNER READ, three paragraphs down, in the same grey small print
      as a reconciliation note: "No verified job cuts worldwide between 12 and
      19 August 2026 carry an explicit AI attribution from the employer." On a
      product called the AI Layoff Tracker, the figure the product is named
      after was set as a negative, in passing, below three qualifiers.

      HIS INSTRUCTION: "I would also use 'AI-attributed cuts: 0' every day. It
      gives the tracker a consistent signature metric and makes the purpose of
      the product immediately obvious." So this block is present in every
      edition, in the same place, whatever the value.

      AND THE MEASUREMENT THAT SHAPES IT, from docs/EDITORIAL-STANDARD.md 5.1.
      Across the 32 complete ISO weeks of 2026 to 16 August, exactly 16
      recorded zero. When it is non-zero it is almost always a single entry,
      and one week holds 49% of the whole year's total. A zero week is the
      MODAL week. Three consequences, and all three are load bearing:

        1. IT CANNOT CARRY A DELTA. "Down from last week" is meaningless on a
           series that is mostly zero, and a three-week run of zeros has
           already happened twice this year without meaning anything. So this
           block reports CUMULATIVELY, with the period's own value as context
           beside it, and never as a change.

        2. A ZERO IS NEVER PRINTED ALONE. Three things travel with it: the
           parent total it is zero OF, the year-to-date value and share which
           shows the metric is normally non-zero, and the count of entries we
           actually read. That last is the one that matters: a zero is only
           informative if the instrument could have detected the thing, and on
           a tracker named for AI a reader who suspects the detector is broken
           is asking the right question. The answer has to be in the email.

        3. IT SAYS WHAT WAS DETECTED, NEVER WHAT HAPPENED. "No employer
           explicitly attributed a cut to AI" and never "AI caused no
           layoffs". A null has two possible causes, a real absence and an
           instrument too weak to see it, and conflating them is the standard
           overclaim in every nothing-happened story. There is also a live
           reason to take the weaker branch: the precision of the AI-causation
           classifier is currently UNKNOWN pending a human review of the
           contested rows, and this repository says so in terms.

      THE BASE RATE IS A DATED MEASUREMENT AND NOT A LIVE CLAIM, which is why
      it can be written down. "Of the 32 complete weeks of 2026 measured to 16
      August, 16 recorded none" does not go stale; it only gets older. A live
      claim in its place ("about half of all weeks") would be fixed prose
      around variable data, which is the fault this file keeps logging. The
      figures beside it, the year-to-date total and its share, ARE live and
      come from the same response the year block prints. Re-measure the base
      rate when the year turns; the constants are named below so it is one
      edit.

      IT IS NOT A HEADLINE PAIR. The two-cell shape is for two figures a
      reader is meant to compare, and the United States AI figure against the
      worldwide one is not that comparison: both are almost always zero and
      setting them side by side at 28px would give the emptiest fact in the
      edition the most space in it. One line, always the same shape, carrying
      the period's value and the cumulative one.
    */
    $AI_BASE_WEEKS = 32;
    $AI_BASE_ZERO = 16;
    $AI_BASE_ASOF = 'August 16';

    $ai_jobs = (int) ($totals['ai_verified_jobs'] ?? 0);
    $ai_entries = (int) ($totals['ai_verified_entries'] ?? 0);

    // THE SIGNATURE LINE. The period's value and the cumulative one, adjacent,
    // because a line reading "0" on its own most weeks trains a reader to skip
    // it, and a skipped line is a dead line. The middle dot is a geometric
    // character, never an emoji.
    /*
      "this week" on a weekly edition and "today" on a daily one, off the
      window's own length, so the composer does not have to be told which tier
      it is composing for. A generic "this period" is the word nobody says.
    */
    $ft2 = strtotime($from . ' 00:00:00 UTC');
    $tt2 = strtotime($to . ' 00:00:00 UTC');
    $wname = 'this period';
    if ($ft2 !== false && $tt2 !== false) {
        if (($tt2 - $ft2) === 6 * DAY_IN_SECONDS) $wname = 'this week';
        elseif (($tt2 - $ft2) === DAY_IN_SECONDS) $wname = 'today';
    }
    $ai_signature = alt_digest_number($ai_jobs) . ' ' . $wname;
    if ($ytd['ok']) {
        $ai_signature .= " \xc2\xb7 " . alt_digest_number($ytd['ai'])
                       . ' in ' . $ytd['year'] . ' so far';
    }
    $html .= '<h3>AI-attributed cuts</h3>'
           . '<p data-alt="signature">' . esc_html($ai_signature) . '</p>';
    $text .= "\nAI-attributed cuts\n" . $ai_signature . "\n";

    /*
      THE DENOMINATOR AND THE DETECTION POWER, IN ONE SENTENCE EACH.

      "We reviewed 76 entries dated August 10-16, 2026" is what turns a bare
      zero into a measurement. It is the count of entries the window holds,
      which is the count the classifier ran over, and it is stated before the
      result rather than after it.
    */
    $ai_lines = array();
    $ai_lines[] = 'We reviewed ' . alt_digest_count($all_entries, 'entry', 'entries')
                . ' dated ' . $range . ', ' . alt_digest_number($ver_jobs)
                . ' verified job cuts between them.';
    $ai_lines[] = ($ai_jobs > 0)
        ? 'Employers explicitly named AI as a reason on '
          . alt_digest_count($ai_entries, 'entry', 'entries') . ', covering '
          . alt_digest_count($ai_jobs, 'verified job cut') . '.'
        : 'No employer explicitly named AI as a reason on any of them.';
    // THE BASE RATE, IN THE SAME BREATH, so the lead never has to hedge. It is
    // dated, so it is true whenever it is read.
    $ai_lines[] = 'Explicit attribution is rare and arrives in bursts: of the '
                . $AI_BASE_WEEKS . ' complete weeks of 2026 measured to '
                . $AI_BASE_ASOF . ', ' . $AI_BASE_ZERO . ' recorded none.';
    if ($ytd['ok'] && $ytd['jobs'] > 0) {
        $ai_share = 100 * $ytd['ai'] / $ytd['jobs'];
        $shown = $ai_share > 0 && $ai_share < 1
            ? number_format($ai_share, 1) : (string) round($ai_share);
        $ai_lines[] = 'So far in ' . $ytd['year'] . ' employers have attributed '
                    . alt_digest_count($ytd['ai'], 'verified job cut')
                    . ' to AI, ' . $shown . '% of the year\'s total.';
    }
    $html .= '<p data-alt="note">' . esc_html(implode(' ', $ai_lines)) . '</p>';
    $text .= implode(' ', $ai_lines) . "\n";

    /*
      WHY THAT MATTERS. The owner's own wording, kept because it is better than
      the defensive hedge it replaces, with the methodological limit stated in
      the last clause rather than apologised for. Every sentence is about the
      METRIC and not about this period, so none of it can become false when the
      data moves. That is the same rule the composition finding follows.
    */
    $ai_why = 'Why that matters: zero AI-attributed cuts does not mean AI played '
            . 'no role. It means no employer in these records explicitly cited AI '
            . 'as a reason. This tracker measures employer disclosure, not the '
            . 'effect of automation on employment.';
    if ($ai_jobs > 0) {
        $ai_why = 'Why that matters: this counts only cuts an employer explicitly '
                . 'named AI for. It is the floor under any estimate of AI driven '
                . 'job loss, never the ceiling. This tracker measures employer '
                . 'disclosure, not the effect of automation on employment.';
    }
    $html .= '<p data-alt="why">' . esc_html($ai_why) . '</p>';
    $text .= $ai_why . "\n";

    /*
      THE INBOX SNIPPET, composed for its own ceiling rather than borrowed
      from the line above. The lede is 143 characters once the geography
      clause is on it, and the ceiling is 130, which is how a live send ended
      up with this tracker's name in the subject and the talent tracker's
      figure in the snippet. See alt_digest_fit_preheader.

      IT LEADS WITH THE UNITED STATES because that is the priority audience and
      because the subject line carries the week rather than a figure. The
      worldwide total is the first optional clause, so a long window drops the
      basis before it drops the second headline.
    */

    $snapshot = '';
    /*
      WHERE THE ROWS BEHIND THAT FIGURE CAME FROM, DIRECTLY UNDER IT.

      THIS SENTENCE DID NOT MOVE BECAUSE IT READ BADLY. It moved because of
      where it was. It used to sit at the FOOT of the section, below three
      tables, as the last line before the year-to-date block, and it is the
      provenance of the figure at the TOP. A reader who screenshots the
      headline, or quotes it, or stops reading after the first screen, took
      the number and left its sourcing behind. That is the adjacency failure
      this section already fixed for windows and tiers, on the one dimension
      the owner says the whole product is differentiated by: a figure that
      cannot be traced is not a citable figure.

      The convention is not ours. ProPublica's news-apps guide is the
      bluntest published version of it: under every display of data, show the
      sources, beneath the visualisation rather than in a credits block at
      the bottom. Datawrapper's annotate guidance asks for the source NAME
      and the source URL together, because the name is how a reader judges
      how much to trust the number. Our World in Data require a reuser to
      credit both them and the underlying provider. Naming state WARN, SEC
      and named news reports here does both jobs at once: it says who
      collected it and who published it first.

      It is one sentence, and that is the budget. An opened newsletter gets
      tens of seconds. Attribution that is not terse does not get read, and
      an unread citation is worth nothing.

      IT IS ITS OWN SECTION NOW, "Source quality", because the owner set the
      edition's hierarchy and named it as a step in it: number, AI
      attribution, source quality, biggest cuts, geography, industries, year
      to date, methodology. It is the block that tells a reader how much to
      trust everything under it, and a clause hanging off the headline was the
      wrong rank for that.

      THE COLUMN IS [4], the verified tier, the same quantity as the headline,
      for the same reason the country and industry blocks read it. Friendly names, because "8K" is a form number and "warn" is
      lower case in the column. The shortfall clause no longer says "above":
      it is above these lines now, so it names the window instead, which is
      what every other line in this section already does.
    */
    $provenance = '';
    $sources = array(); $src_shown = 0;
    $top_source = ''; $top_source_jobs = 0;
    foreach ((is_array($data['source_types'] ?? null) ? $data['source_types'] : array()) as $row) {
        $row = array_values((array) $row);
        $key = trim((string) ($row[0] ?? ''));
        $value = (int) ($row[4] ?? 0);
        if ($key === '' || $value <= 0) continue;
        $label = isset($source_names[$key]) ? $source_names[$key] : $key;
        $sources[] = alt_digest_number($value) . ' from ' . $label;
        // The LARGEST collector, for the preview line. The full split is far
        // too long for a snippet and the fitter was dropping it whole; one
        // collector is the fact a reporter checks first and it fits.
        if ($value > $top_source_jobs) {
            $top_source_jobs = $value;
            $top_source = alt_digest_number($value) . ' of them from ' . $label;
        }
        $src_shown += $value;
    }
    if ($sources) {
        $src_line = 'Where these came from, ' . $range . ', verified only: '
                  . implode(', ', $sources) . '.';
        if ($src_shown !== $ver_jobs) {
            $src_line .= ' That covers ' . alt_digest_number($src_shown) . ' of the '
                       . alt_digest_count($ver_jobs, 'verified job cut') . ' in '
                       . $range . '.';
        }
        $provenance = $src_line;
    }

    /*
      WHEN THESE FIGURES WERE TRUE, NEXT TO THE FIGURE AND NOT IN A FOOTER.

      The email is a SNAPSHOT and it read like a live page. Ingest finishes
      near 22:00 UTC and the send runs at 6:00 AM Eastern (10:00 UTC under EDT,
      11:00 under EST), so a reader opening this at breakfast holds numbers
      about twelve hours old. The citation at the foot has always carried the
      stamp; the citation is also the block a general reader never reaches.

      Two facts, two short sentences, because they are genuinely different: the
      database stopped moving at one time and we read it at another. Neither is
      guessed. A build that cannot date the last write prints only the second,
      which is still true.
    */
    $cut = alt_digest_data_cut_label();
    $composed = alt_digest_date_range(gmdate('Y-m-d'), gmdate('Y-m-d'));
    if ($composed !== '') {
        $composed .= ' at ' . gmdate('H:i') . ' UTC';
        $asof = ($cut !== '' ? 'The database last changed ' . $cut . '. ' : '')
              . 'This digest was composed ' . $composed . ', and every figure '
              . 'in it is the snapshot taken then.';
        // HELD FOR THE FOOT. "About this snapshot" is the last block before
        // the citation, because when the figures were read is methodology and
        // not provenance: it belongs with the provisional note and the
        // citation rather than beside the source split.
        $snapshot = $asof;
    }
    if ($provenance !== '') {
        $html .= '<h3>Source quality</h3>'
               . '<p data-alt="source">' . esc_html($provenance) . '</p>';
        $text .= "\nSource quality\n" . $provenance . "\n";
    }

    /*
      THE SECOND TIER, AND WHY IT IS STATED EVEN WHEN IT IS EMPTY.

      The site publishes that verified and announced are never mixed. A reader
      can only rely on that if the email says which one they are looking at
      AND what the other one holds. When the window has no announced rows at
      all, saying so is a fact, not filler: it tells the reader the figure
      above is the whole set rather than a slice they have to go and check.
    */
    if ($has_announced) {
        $tier = 'There ' . alt_digest_verb($all_entries, 'is', 'are') . ' '
              . alt_digest_count($all_entries, 'entry', 'entries') . ' '
              . $span . ', ' . alt_digest_number($ver_entries)
              . ' of them verified. '
              . 'Including announced estimates, the same window holds '
              . alt_digest_count($all_jobs, 'job cut') . ' across '
              . alt_digest_count($companies_n, 'company', 'companies') . '.';
    } else {
        $tier = ($all_entries === 1
                    ? 'The one entry ' . $span . ' is verified'
                    : 'All ' . alt_digest_number($all_entries) . ' entries '
                      . $span . ' are verified')
              . ', across ' . alt_digest_count($companies_n, 'company', 'companies')
              . '. The window holds no announced estimates.';
    }
    if (function_exists('alt_announced_tier_sentence')) {
        $tier .= ' ' . alt_announced_tier_sentence();
    }
    $html .= '<p data-alt="note">' . esc_html($tier) . '</p>';
    $text .= $tier . "\n";


    /*
      THE ENTRIES, EACH ONE LINKED TO ITS OWN PAGE.

      The permalink was in the leaders payload from the start and was never
      printed. It is the single most useful field in this email for the two
      audiences that need to cite us: an entry page names the filing or the
      report the row came from, so a reporter can check us before quoting us
      and a blogger has something to link. Adding it costs one field.
    */
    $leaders = array_slice(is_array($data['leaders'] ?? null) ? $data['leaders'] : array(), 0, 5);
    if ($leaders) {
        $rows = array();
        $linked = 0;
        $filtered = 0;
        $sourced = 0;
        $announced_rows = 0;
        // Whether the payload can answer the tier question AT ALL. Absence of
        // the field is UNKNOWN and must never render as "none are announced":
        // an /aggregate served by a plugin build older than the one that added
        // the column returns leaders without it, and a caption reading
        // "verified only" over an announced row is a worse lie than the mixed
        // caption this replaced.
        $tier_known = false;
        foreach ($leaders as $l) {
            $l = (array) $l;
            /*
              THE DATE THE CUTS TAKE EFFECT, IN THE EMAIL'S ONE DATE SHAPE.

              This used alt_digest_short_date and printed "18 Aug 2026" two
              lines under a caption reading "17 to 18 August 2026". One message,
              two spellings of the same month, in the block a reader looks at
              hardest. Every date in this email is now "18 August 2026", which
              is what alt_digest_date_range gives for a single day.

              A row carrying no date still shows none, rather than borrowing
              the window's edge.
            */
            $day = substr((string) ($l['layoff_date'] ?? ''), 0, 10);
            $when = alt_digest_date_range($day, $day);
            $label = trim((string) ($l['company_name'] ?? ''));
            if ($label === '') continue;
            $detail = array();
            /*
              WHERE, IN WORDS A READER OUTSIDE THE UNITED STATES CAN READ.
              See alt_digest_place. An empty place is stated rather than left
              blank: a third of verified cuts sit on entries with no country,
              the headline says so, and a silent row let a reader assume the
              place was obvious.
            */
            $place = alt_digest_place($l['state'] ?? '', $l['country'] ?? '',
                                      $l['location'] ?? '');
            $detail[] = ($place !== '') ? $place : 'location not recorded';
            if ($when !== '') $detail[] = 'takes effect ' . $when;
            if (!empty($l['ai_explicit'])) $detail[] = 'AI attributed';
            /*
              THE TIER, ON THE ROW, AND WHY THIS LIST IS NOT FILTERED INSTEAD.

              THE DEFECT. This table is the most-read block in the email and
              it was the last one still mixing tiers. Every other ranked block
              was moved to the verified column when it was found that they
              printed the announced-inclusive tier under a verified headline.
              This one was skipped, because the tier was not in the payload:
              db.php's leaders query selected no `announced` column, so the
              composer had no way to tell. Live on 2026-08-17 the SECOND row
              of this table, Paramount Skydance at 2,500, is announced, and it
              is not inside the 13,658 stated above it. "Verified and announced
              together" labelled that correctly and it was still wrong: a
              reader who adds the top rows gets a number that cannot reconcile
              with the headline, and cannot see which row to subtract.

              THE CHOICE, AND IT IS NOT THE ONE THE OTHER BLOCKS MADE. The
              country and industry lists became verified-only. This one does
              not. Those blocks BREAK DOWN the headline, so they have to sum
              to it. This one answers a different question, "what were the
              biggest cuts this week", and filtering it to verified would hide
              the largest cut of the week whenever that cut is an announcement,
              which is often. The site's published rule is that announced is a
              separate, LABELLED tier never merged into a verified TOTAL. A
              ranked list is not a total. So the row says which tier it is, the
              caption says how many are outside the headline, and the reader
              can do the subtraction we were previously hiding from them.

              Only the announced rows are marked. Marking both would put a
              word on every line to distinguish a minority, and the caption
              names the default.
            */
            if (array_key_exists('announced', $l)) {
                $tier_known = true;
                if (!empty($l['announced'])) { $detail[] = 'announced'; $announced_rows++; }
            }
            $permalink = trim((string) ($l['permalink'] ?? ''));
            $row = array(
                'label'  => $label,
                // Outside the anchor, so the link text is the company name.
                // See alt_digest_rank_table.
                'suffix' => $detail ? '(' . implode(', ', $detail) . ')' : '',
                'figure' => alt_digest_jobs_phrase((int) ($l['job_count'] ?? 0)),
            );
            /*
              THE SUPPORTING SOURCE LINK, WHERE THE ROW CARRIES A USABLE URL.

              This is the link the older note below said we could not build, and
              it was right for the counter and wrong for the reader. The counter
              (alt_digest_link_allowed) admits our own hosts only, correctly, so
              an outlet URL cannot be routed through it. But a PLAIN `<a href>`
              straight to the outlet is a different object with a different
              guard, alt_digest_external_link_ok, which the hiring-signal list
              has used since 2026-08-20. So a WARN row with no entry page can
              still carry the one citation that matters: the state labour
              department filing it was scraped from. It is additive to the
              company link, never a replacement, and counted separately so the
              basis sentence can say how many rows a reader can trace to source.
            */
            $source_url = trim((string) ($l['source_url'] ?? ''));
            if ($source_url !== '' && alt_digest_external_link_ok($source_url)) {
                $row['source_url'] = $source_url;
                $sourced++;
            }
            if ($permalink !== '' && alt_digest_link_allowed($permalink)) {
                $row['url'] = alt_digest_track_link($send_id, $permalink);
                $row['plain_url'] = $permalink;
                $linked++;
            } else {
                /*
                  NO ENTRY PAGE, SO THE TRACKER VIEW INSTEAD, AND NOT NOTHING.

                  A notice that arrived through the bulk import path has
                  post_id => null by construction and will never acquire a
                  permalink, so five rows used to ship with one link between
                  them. An entry page is the better destination where one
                  exists, because it names the filing behind the row; where
                  none exists, the tracker filtered to this company on this
                  window and this basis is still a real destination that
                  reproduces the row, and it is strictly better than plain text.

                  The company name is the filter value. It is the same string
                  the row prints, it goes through the page's `company` control,
                  and the link carries date_basis like every other link this
                  file builds. It is counted separately from $linked, because
                  the sentence below distinguishes the two destinations and
                  must not start claiming entry pages that do not exist.
                */
                $row['url'] = alt_digest_track_link($send_id, alt_digest_tracker_url(
                    $from, $to, array('company' => $label)));
                $filtered++;
            }
            $rows[] = $row;
        }
        if ($rows) {
            /*
              THE CAPTION IS COMPUTED, because "verified and announced
              together" was fixed prose around variable data: it is false on
              any week where every leader is verified, which is most weeks.
              Same fault, and same fix, as the country block's reconciliation
              note. When some rows ARE announced it says how many and that
              they sit outside the headline, so the reader can subtract.
            */
            if (!$tier_known) {
                // UNKNOWN, said out loud. See $tier_known above.
                $caption = $range . ', ranked by job count. This list can include '
                         . 'announcements, which sit outside the verified figure above.';
            } elseif ($announced_rows > 0) {
                $caption = $range . ', ranked by job count. '
                         . $announced_rows . ' of these ' . count($rows)
                         . alt_digest_verb($announced_rows,
                               ' is an announcement, marked below, and sits',
                               ' are announcements, marked below, and sit')
                         . ' outside the verified figure above.';
            } else {
                $caption = $range . ', verified only, ranked by job count.';
            }
            $html .= '<h3>Biggest cuts</h3>'
                   . '<p data-alt="caption">' . esc_html($caption) . '</p>';
            $text .= "\nBiggest cuts\n" . $caption . "\n";
            list($t_html, $t_text) = alt_digest_rank_table($rows);
            $html .= $t_html;
            $text .= $t_text;
            /*
              THE SAME RULE AGAIN: SAY ONLY WHAT IS TRUE OF THIS LIST.

              Not every row has a page. A WARN filing that arrived through the
              bulk path has no `layoffs` post behind it, so it carries no
              permalink and gets no link. Claiming "each company links to its
              own entry page" on a list where two of five do not is the fixed
              prose fault, and a reporter who follows the claim and finds no
              link has caught us being careless with a smaller thing than the
              numbers.
            */
            $basis = array();
            $count = count($rows);
            if ($linked === $count) {
                $basis[] = 'Each company above links to its own entry page, which names '
                         . 'the filing or report behind the row.';
            } elseif ($linked > 0) {
                /*
                  "NO PAGE OF THEIR OWN YET" WAS THE WRONG WORD, and the wrong
                  word was the load-bearing one. "Yet" promises a page is
                  coming. None is. alt_api_bulk() writes every row with
                  post_id => null, by construction, so a notice that arrived
                  through the bulk import path never acquires a `layoffs` post
                  and never acquires a permalink. That is a fact about how the
                  row was collected, not a backlog.
                  ("Bulk import" and not "state WARN import": the same path
                  carries state WARN, Hawaii and California backfills, federal
                  RIF notices and the European Restructuring Monitor.)

                  THE FILING ITSELF IS NOW LINKED SEPARATELY, which reverses
                  half of what this note used to say. It read "we cannot link
                  the filing itself", on two grounds: the leaders query carried
                  no source_url, and alt_digest_link_allowed() admits our own
                  hosts only. The second is still true and is the reason the
                  COUNTER cannot carry an outlet URL. But a plain, uncounted
                  `<a href>` is a different object with its own guard,
                  alt_digest_external_link_ok(), and db.php now ships source_url
                  in the payload, so the "Source" link beside each row points
                  straight at the state labour department filing or the report.
                  What remains true is the ENTRY PAGE half: a bulk-import row has
                  no `layoffs` post and so no first-party permalink, which is
                  what the company name falls back to the company-filter for.
                */
                $basis[] = $linked . ' of the ' . $count . ' companies listed '
                         . $span . alt_digest_verb($linked, ' links', ' link')
                         . ' to an entry page naming the filing or report behind the '
                         . 'row. '
                         . alt_digest_verb($count - $linked, 'The other one arrived',
                                                             'The rest arrived')
                         . ' through a bulk filing import, which builds no page, so '
                         . alt_digest_verb($count - $linked, 'it links', 'they link')
                         . ' to the tracker filtered to that company.';
            }
            /*
              HOW MANY ROWS A READER CAN TRACE STRAIGHT TO SOURCE, computed and
              named the same way $linked is, because a fixed sentence would be
              false on any week where a row carries no usable URL. The "Source"
              links point at the outlet or the filing itself, which is the
              citation a reporter checks first and the one the entry-page link
              cannot always provide.
            */
            if ($sourced > 0) {
                $basis[] = $sourced === $count
                    ? 'Every row also carries a "Source" link to the filing or '
                      . 'report it was drawn from.'
                    : $sourced . ' of the ' . $count . ' also '
                      . alt_digest_verb($sourced, 'carries', 'carry')
                      . ' a "Source" link to the filing or report behind the row.';
            }
            /*
              THE CAVEAT THAT USED TO BE HERE IS GONE, because it is no longer
              true. It read "The tracker page counts by filing date, not by
              effective date, so its totals for these dates differ", which was
              honest and was also an admission that the link at the foot of
              this section contradicted the figure at the top of it. The link
              now carries this window and this basis, verified in a browser
              against the live week, so the discrepancy it warned about does
              not occur. See alt_digest_tracker_url.

              NOTHING REPLACES IT. A sentence claiming the two now agree would
              be a promise with an exception hiding in it: a reader who ticked
              "AI only" earlier in the same browser session keeps that filter,
              and the page cannot be told to clear it from a URL. A silent
              correct link is worth more than a claim we cannot fully honour.
              The $dated flag existed only to gate that caveat and is gone with
              it. Restore both only if the link stops reconciling.
            */
            if ($basis) {
                // MOVED TO "Data notes". This is build detail - which rows have
                // an entry page and why the rest do not - not a caveat a reader
                // does arithmetic against while reading the table. It is
                // collected and printed once with the other residuals.
                $data_notes[] = implode(' ', $basis);
            }
        }
    }

    /*
      WHERE THE JOBS WERE, AS REGIONS, AND THE TWO LINES THAT ARE NOT REGIONS.

      WHAT IT WAS. A flat top five countries. On the live week that read United
      States, Multiple countries, Germany, Brazil, Canada: one line the reader
      came for and four that are not a picture of the world. The owner asked
      for a regional breakdown and named the buckets he wanted.

      EVERY LINE IS LINKED, which is the fourth complaint. A region links to
      the tracker filtered to exactly the countries that made up that line, on
      this window and this date basis, so the page's headline reproduces the
      figure beside it. The country list is the one this window actually holds
      rather than the whole region, because a link that adds countries with no
      rows would still be correct and would stop being a reproduction of THIS
      line.

      THE TWO LINES THAT ARE NOT REGIONS, and both are printed rather than
      hidden, which is standard practice rather than an apology: the OECD's
      development statistics carry an explicit unallocated line so that the
      components sum to the total.

        "Multiple countries" is the stored bucket for a cross-border cut
        announced with no per-country split. It has no job location. Folding it
        into Asia Pacific or Europe would invent one and double-count the jobs
        against the region that really holds them, so it is refused by
        alt_digest_region_of() and given a line of its own.

        "No country recorded" is the third of the headline that sits on entries
        we cannot place. It carries NO LINK, because there is no filter for an
        empty country and a link that quietly showed something else would be
        worse than none. The sentence under the two headlines already said how
        many; this line is where it lands in the arithmetic.

      SO THE COLUMN SUMS TO THE WORLDWIDE HEADLINE, exactly, every week. That
      is the property alt_digest_reconcile_note() used to have to apologise for
      not having.

      A COUNTRY THIS DOES NOT KNOW GOES TO "Elsewhere" AND IS NOT GUESSED.
      alt_normalize_country() passes an unrecognised single country through
      unchanged, so the region map cannot be complete by construction. See
      alt_digest_region_of().

      THE GROUPING IS OURS AND THE CAPTION SAYS SO. "Asia Pacific" and "Middle
      East and Africa" are business groupings, not UN M49 statistical regions,
      and a reader reconciling against a UN table would otherwise find us
      wrong.
    */
    if ($countries_all || $multi > 0 || $covered < $ver_jobs) {
        /*
          ONE LINE, AND THE CAPTION IS ITS OPENING CLAUSE.

          This was a caption, a seven row table and a note. It is a dimension a
          reader skims, so it is now a series on a single line and the caption
          is the sentence that series sits inside. Nothing a caveat carried has
          been dropped: the window, the tier and the geography basis are all
          still in front of the figures, which is the property that matters,
          because a line lifted out on its own still says what it covers.
        */
        $caption = $range . ', verified job cuts, counted where the jobs were '
                 . 'rather than where the employer is based';

        $region_jobs = array();
        $region_countries = array();
        foreach ($countries_all as $name => $value) {
            $region = alt_digest_region_of($name);
            if ($region === '') $region = 'Elsewhere';
            if (!isset($region_jobs[$region])) {
                $region_jobs[$region] = 0;
                $region_countries[$region] = array();
            }
            $region_jobs[$region] += $value;
            $region_countries[$region][] = $name;
        }
        $rows = array();
        $shown = 0;
        /*
          THE UNITED STATES IS PINNED FIRST AND THE REST IS RANKED.

          A block headed "Where the jobs were" is read as a ranking, and the
          first render printed a FIXED order in which Latin America at 476 sat
          below Europe at 321. A table sorted by nothing a reader can see is a
          table they have to re-sort in their head.

          The US keeps the top line whatever its size, because it is the stated
          priority audience and because it is already a headline above; a reader
          looking for it should not have to hunt down a ranked list for it. It
          is a pinned row and not a claim about magnitude, and the figure beside
          it says which.

          "Elsewhere" is last of the regions because it is a residual and not a
          place, and the two non-regions follow it.
        */
        $order = array();
        foreach (alt_digest_region_order() as $region) {
            if (!empty($region_jobs[$region])) $order[] = $region;
        }
        $pinned = array_values(array_filter($order, function ($r) {
            return $r === 'United States'; }));
        $rest = array_values(array_filter($order, function ($r) {
            return $r !== 'United States'; }));
        usort($rest, function ($a, $b) use ($region_jobs) {
            return $region_jobs[$b] <=> $region_jobs[$a];
        });
        $order = array_merge($pinned, $rest);
        if (!empty($region_jobs['Elsewhere'])) $order[] = 'Elsewhere';
        foreach ($order as $region) {
            if (empty($region_jobs[$region])) continue;
            /*
              THE UNIT IS IN THE CAPTION, ONCE, NOT ON EVERY ITEM. On a line
              the whole point of which is that it is one line, "10,132 jobs .
              476 jobs . 371 jobs" spends a sixth of its words repeating a
              word the clause in front of it already said. The separators
              still carry thousands, which is not negotiable.
            */
            $rows[] = array(
                'label'  => $region,
                'figure' => alt_digest_number($region_jobs[$region]),
                'url'    => alt_digest_track_link($send_id, alt_digest_tracker_url(
                                $from, $to,
                                array('country' => $region_countries[$region]))),
            );
            $shown += $region_jobs[$region];
        }
        if ($multi > 0) {
            $rows[] = array(
                'label'  => 'Multiple countries, no split given',
                'figure' => alt_digest_number($multi),
                'url'    => alt_digest_track_link($send_id, alt_digest_tracker_url(
                                $from, $to, array('country' => 'Multiple countries'))),
            );
            $shown += $multi;
        }
        $unplaced_rows = max(0, $ver_jobs - $covered);
        if ($unplaced_rows > 0) {
            // No url. See the docblock: there is no filter for an empty country.
            $rows[] = array('label' => 'No country recorded',
                            'figure' => alt_digest_number($unplaced_rows));
            $shown += $unplaced_rows;
        }
        list($c_html, $c_text) = alt_digest_inline_series($rows);
        /*
          THE RECONCILIATION, WHICH ON THIS BLOCK IS NOW ALWAYS EXACT. It is
          still computed rather than asserted: a line claiming the column adds
          up would be fixed prose around variable data, and if a future change
          ever breaks the property this says so instead of lying about it.
        */
        $note = alt_digest_reconcile_note($shown, $ver_jobs, $ver_jobs, 'job cut',
                                          'no country recorded', $span);
        $tail = '. Regions are our own grouping.' . ($note === '' ? '' : ' ' . $note);
        $html .= '<h3>Where the jobs were</h3>'
               . '<p data-alt="series">' . esc_html($caption . ': ') . $c_html
               . esc_html($tail) . '</p>';
        $text .= "\nWhere the jobs were\n" . $caption . ': ' . $c_text . $tail . "\n";
    }

    /*
      WHICH INDUSTRIES, which is the block a recruiter or a job hunter reads
      first. Same verified tier, same window, same reconciliation rule. The
      "Multiple countries" special case cannot occur on this dimension, and
      the closure simply returns nothing for it.
    */
    list($industries_all, , $ind_covered) = $verified_split($data['top_industries'] ?? null);
    /*
      THREE, NOT FIVE, AND ON ONE LINE. The fourth and fifth rows of this
      table were never the finding; the derived composition note underneath
      is, and it reads the WHOLE block rather than the printed slice, so its
      arithmetic is unaffected by how many rows are shown. The shortfall note
      below still measures what the printed lines cover, so cutting two rows
      makes the caveat larger and truer rather than hiding anything.
    */
    $industries = array_slice($industries_all, 0, 3, true);
    if (count($industries) > 1) {
        $caption = $range . ', verified job cuts, by the industry we classified '
                 . 'the employer into';
        $rows = array(); $shown = 0;
        foreach ($industries as $name => $value) {
            // EVERY LINE LINKED, and to this window and this basis. The
            // industry filter is a plain string match on the same normalised
            // vocabulary the label is printed from, so the page's headline
            // reproduces the figure beside it. See alt_digest_tracker_url.
            $rows[] = array(
                'label'  => $name,
                'figure' => alt_digest_number($value),
                'url'    => alt_digest_track_link($send_id, alt_digest_tracker_url(
                                $from, $to, array('industry' => $name))),
            );
            $shown += $value;
        }
        list($i_html, $i_text) = alt_digest_inline_series($rows);
        $html .= '<h3>Which industries</h3>'
               . '<p data-alt="series">' . esc_html($caption . ': ') . $i_html
               . esc_html('.') . '</p>';
        $text .= "\nWhich industries\n" . $caption . ': ' . $i_text . ".\n";
        /*
          THE ONE LINE IN THIS EMAIL THAT SAYS WHAT A NUMBER MEANS. It sits
          here, under the table it is derived from, because that table is its
          evidence: a reader who doubts it can check it against the rows
          immediately above. It computes itself from the raw block and returns
          nothing when the period has no shape worth naming. See
          alt_digest_composition_note for the three floors and why each exists.
        */
        list($shape, $tech) = alt_digest_composition_note($data['top_industries'] ?? null,
                                                          $ver_jobs, $span);
        /*
          THE SHAPE SENTENCE IS COMPUTED AND NO LONGER PRINTED, and that is a
          deliberate editorial cut rather than a deletion.

          It read "Food & Hospitality, Aerospace & Defense and Retail &
          E-commerce are the three largest, 90% of the 12,348 verified job
          cuts we classified by industry between August 10 and 16, 2026." Every
          word of it is now visible in the line directly above: the three names
          in order, with their figures, under a caption that names the window
          and the tier, and with the coverage note below stating the
          denominator. It was reading the list back to the reader.

          THE TECHNOLOGY CLAUSE STAYS, because it is the only part that says
          something the list does not: technology's real rank and share when it
          is ranked OUTSIDE the three shown. That is the finding a reader of an
          AI layoff tracker came for, and on a three-row list it fires more
          often than it did on a five-row one, not less.

          $shape is still computed because it is the same call, it costs
          nothing, and alt_digest_composition_note's floors decide whether the
          period has a shape worth naming at all. Its return is what the
          technology clause is gated on.
        */
        if ($tech !== '') {
            $html .= '<p data-alt="finding">' . esc_html($tech) . '</p>';
            $text .= $tech . "\n";
        }
        // MOVED TO "Data notes". The unclassified-industry residual is the same
        // build-detail class as the entry-page basis above: it says how much of
        // the headline the three printed rows cover. It is still computed here,
        // from the whole block rather than the printed slice, so its arithmetic
        // is unchanged; only where it prints moved.
        $note = alt_digest_reconcile_note($shown, $ind_covered, $ver_jobs, 'job cut',
                                          'no industry recorded', $span);
        if ($note !== '') {
            $data_notes[] = $note;
        }
    }

    /*
      BY US STATE, WHICH IS THE DIMENSION THE WARN PATH IS RICHEST IN. A US
      state files the notice, so the `state` column is populated for the WARN
      backbone of this tracker and for any placed US row; column [4] is the
      verified tier, the SAME quantity every ranked block in this section reads,
      so this cannot describe a different tier than the headline.

      IT IS A SUBSET, NOT A BREAKDOWN, AND CARRIES NO RECONCILIATION NOTE. These
      are US states only, so the column is a slice of the worldwide headline and
      was never meant to sum to it. Asserting it summed would be the fixed-prose
      fault; saying nothing is the truth. The caption names it "US" so a reader
      does not read the slice as the whole.

      THE CODES ARE EXPANDED THROUGH alt_us_state_names(), api.php's single
      definition and the very map alt_digest_place() and the state pages use, so
      "CA" reads "California" here exactly as it does everywhere else we publish.
      An unrecognised code (a territory the map does not carry) prints unchanged
      rather than being guessed at, and the link carries the code the page's
      `state` control accepts.
    */
    list($states_all, , ) = $verified_split($data['top_states'] ?? null);
    $states = array_slice($states_all, 0, 5, true);
    if (count($states) > 1) {
        $state_map = function_exists('alt_us_state_names') ? alt_us_state_names() : array();
        $caption = $range . ', verified US job cuts, by the state where the '
                 . 'notice was filed';
        $rows = array();
        foreach ($states as $code => $value) {
            $code = strtoupper((string) $code);
            $rows[] = array(
                'label'  => isset($state_map[$code]) ? $state_map[$code] : $code,
                'figure' => alt_digest_number($value),
                'url'    => alt_digest_track_link($send_id, alt_digest_tracker_url(
                                $from, $to, array('state' => $code))),
            );
        }
        list($s_html, $s_text) = alt_digest_inline_series($rows);
        $html .= '<h3>By US state</h3>'
               . '<p data-alt="series">' . esc_html($caption . ': ') . $s_html
               . esc_html('.') . '</p>';
        $text .= "\nBy US state\n" . $caption . ': ' . $s_text . ".\n";
    }

    /*
      WHY, BY THE REASON TAG THE EMPLOYER OR REPORT GAVE. Same verified tier
      (column [4]), same window, out of the same response.

      IT OVERLAPS BY CONSTRUCTION, so it carries no reconciliation note. The
      reason tags are a fixed vocabulary and an entry can hold SEVERAL (a row
      tagged both "restructuring" and "cost reduction" counts in each, db.php
      builds this as a LIKE over packed tags), so these lines do not partition
      the headline and must not claim to. The caption says so in the fewest
      words that are true: "an entry can carry more than one".

      THE TWO AI TAGS KEEP THE TRACKER'S OWN LABELS. "Reason tag: AI or
      automation" and "Reason tag: AI press-linked" are the page's spellings
      (REASON_LABELS, assets/layoffs.js), and they are deliberately NOT the
      names on the AI stat tiles: the tiles count ai_explicit/ai_causation
      columns and these count reason_tags, which are different quantities, and a
      reader who meets the AI reason here should meet it spelled exactly as the
      page spells it. This inline map mirrors that JS map the same way
      $source_names above is a local copy of the collector names: there is no
      PHP definition to share, so it is kept here with this note against drift.
    */
    list($reasons_all, , ) = $verified_split($data['reasons'] ?? null);
    $reasons_top = array_slice($reasons_all, 0, 5, true);
    if (count($reasons_top) > 1) {
        $reason_names = array(
            'ai_automation'           => 'Reason tag: AI or automation',
            'possible_ai'             => 'Reason tag: AI press-linked',
            'revenue_decline'         => 'Revenue decline',
            'restructuring'           => 'Restructuring',
            'merger_acquisition'      => 'Merger / acquisition',
            'offshoring'              => 'Offshoring',
            'product_discontinuation' => 'Product discontinued',
            'cost_reduction'          => 'Cost reduction',
            'macroeconomic'           => 'Macroeconomic',
            'closure'                 => 'Plant / site closure',
        );
        $caption = $range . ', verified job cuts, by the reason the employer or '
                 . 'report gave, and an entry can carry more than one';
        $rows = array();
        foreach ($reasons_top as $tag => $value) {
            $tag = (string) $tag;
            $rows[] = array(
                'label'  => isset($reason_names[$tag]) ? $reason_names[$tag] : $tag,
                'figure' => alt_digest_number($value),
                'url'    => alt_digest_track_link($send_id, alt_digest_tracker_url(
                                $from, $to, array('reasons' => $tag))),
            );
        }
        list($r_html, $r_text) = alt_digest_inline_series($rows);
        $html .= '<h3>Why</h3>'
               . '<p data-alt="series">' . esc_html($caption . ': ') . $r_html
               . esc_html('.') . '</p>';
        $text .= "\nWhy\n" . $caption . ': ' . $r_text . ".\n";
    }

    /*
      ROLES MOST AFFECTED. Same verified tier (column [4]), same window, same
      response. top_roles arrives ALREADY keyed by its human label, because
      db.php builds it from alt_role_categories(), so nothing is mapped for
      display.

      IT OVERLAPS like the reason tags and for the same reason: an entry naming
      several teams counts in each, so it does not sum to the headline and
      carries no reconciliation note. The caption says "an entry can name
      several".

      THE LINK NEEDS THE SLUG, WHICH IS THE REVERSE OF alt_role_categories().
      The roles filter on the page sends slugs, not labels (assets/layoffs.js
      keeps the same reverse map for exactly this reason), so the slug is
      derived from api.php's one definition rather than hand-kept. When that map
      is not loaded the row renders WITHOUT a link rather than a wrong one, which
      is the same graceful degrade the leaders block makes for a missing page.
    */
    list($roles_all, , ) = $verified_split($data['top_roles'] ?? null);
    $roles_top = array_slice($roles_all, 0, 5, true);
    if (count($roles_top) > 1) {
        $role_slug = array();
        if (function_exists('alt_role_categories')) {
            foreach (alt_role_categories() as $slug => $label) {
                $role_slug[$label] = $slug;
            }
        }
        $caption = $range . ', verified job cuts, by the roles affected, and an '
                 . 'entry can name several';
        $rows = array();
        foreach ($roles_top as $label => $value) {
            $label = (string) $label;
            $row = array(
                'label'  => $label,
                'figure' => alt_digest_number($value),
            );
            if (isset($role_slug[$label])) {
                $row['url'] = alt_digest_track_link($send_id, alt_digest_tracker_url(
                                  $from, $to, array('roles' => $role_slug[$label])));
            }
            $rows[] = $row;
        }
        list($ro_html, $ro_text) = alt_digest_inline_series($rows);
        $html .= '<h3>Roles most affected</h3>'
               . '<p data-alt="series">' . esc_html($caption . ': ') . $ro_html
               . esc_html('.') . '</p>';
        $text .= "\nRoles most affected\n" . $caption . ': ' . $ro_text . ".\n";
    }

    /*
      The provenance sentence used to be here, at the foot, three tables below
      the figure it explains. It is now directly under that figure. See the
      block above the announced-tier note for why moving it was the point.

      THE YEAR TO DATE, AND WHY IT MOVED TO THE BOTTOM.

      It used to sit in the middle of the section, directly above a country
      list scoped to the PERIOD. The country list stated no window of its own,
      so the year figure above it supplied one by adjacency, and the owner
      read the block as a breakdown of the year. Every figure names its own
      window now, so the ambiguity is already gone; putting the only
      year-scoped line at the FOOT of a run of period-scoped ones removes the
      chance to misread it a second way.

      STILL DELIBERATELY NO PERIOD-OVER-PERIOD DELTA. This data revises upward
      for weeks: filings and WARN notices arrive after the event, so the
      newest period is always the least complete one we hold. A week-on-week
      line would turn a reporting lag into a fall that never happened. A
      year-to-date total only grows, so a late arrival corrects it rather than
      inverting it. Do not add a delta here later.

      The year comes from the period's own end date, not from the clock, so a
      run that composes a window is never labelled with a different year, and
      the tier matches the headline for the reason spelled out above. If
      either figure ever changes tier, change BOTH in the same edit.
    */
    if ($ytd['ok']) {
        /*
          RENDERED HERE, FETCHED ABOVE. The AI block quotes the same
          `$ytd['ai']` from the same response, so the cumulative figure in the
          signature line and the one in this block cannot disagree.

          THE HEADING IS "2026 YTD" and not "YTD 2026". A reader scanning
          headings meets the year first, which is the same month-first
          principle the date format now follows: fix the unit before the
          abbreviation arrives.

          STILL DELIBERATELY NO DELTA ON THIS FIGURE. A year-to-date total only
          grows, so a late arrival corrects it rather than inverting it, and a
          year-on-year line would compare a complete year against a partial
          one. The week-on-week comparison above is a different object and has
          its own justification; see alt_digest_change.
        */
        $ytd_scope = $ytd['range'] . ', worldwide, counted by the date the cuts take effect.';
        $html .= '<h3>' . esc_html($ytd['year']) . ' YTD</h3>'
               . '<p data-alt="stat">' . esc_html(alt_digest_number($ytd['jobs'])) . '</p>'
               . '<p data-alt="unit">'
               . esc_html(alt_digest_verb($ytd['jobs'], 'verified job cut',
                                          'verified job cuts')) . '</p>'
               . '<p data-alt="scope">' . esc_html($ytd_scope) . '</p>';
        $text .= "\n{$ytd['year']} YTD\n"
               . alt_digest_count($ytd['jobs'], 'verified job cut') . ', '
               . $ytd_scope . "\n";
        if ($ytd['ai'] > 0) {
            $ytd_ai_line = 'Of those, ' . alt_digest_number($ytd['ai'])
                         . alt_digest_verb($ytd['ai'], ' was', ' were')
                         . ' attributed to AI by the employer, '
                         . $ytd['range'] . ', worldwide.';
            $html .= '<p data-alt="note">' . esc_html($ytd_ai_line) . '</p>';
            $text .= $ytd_ai_line . "\n";
        }
        if ($ytd['unplaced'] > 0) {
            // NAMES ITS OWN SUBJECT. It used to read "Of those, ..." and sat
            // below the AI line, so "those" pointed at the AI subset rather
            // than at the year. Two lines beginning "Of those" in one block is
            // one line too many.
            $ytd_note = alt_digest_number($ytd['unplaced']) . ' of the '
                      . alt_digest_count($ytd['jobs'], 'verified job cut')
                      . alt_digest_verb($ytd['unplaced'], ' sits', ' sit')
                      . ' on entries with no country recorded, ' . $ytd['range'] . '.';
            $html .= '<p data-alt="note">' . esc_html($ytd_note) . '</p>';
            $text .= $ytd_note . "\n";
        }
    }

    // Counted link. The plain URL stays in the text part: a text reader should
    // not be handed a machine-shaped URL to squint at, and one counted copy per
    // send is enough to know whether the section is read at all.
    // THE LINK LANDS ON THIS WINDOW AND THIS BASIS, so the click that is meant
    // to prove the figure shows the figure. See alt_digest_tracker_url for what
    // was verified in a browser and for the two spellings of the basis.
    $open = alt_digest_tracker_url($from, $to);
    $click = alt_digest_track_link($send_id, $open);
    /*
      DESCRIPTIVE LINK TEXT, because "Open the tracker on this week" was
      awkward English and, worse, meant nothing once the line was quoted on
      its own. This link does not land on the tracker's default view: it
      carries THIS window and THIS date basis, so the label says which window.
      A reader who forwards the line, or a screen reader that reads links out
      of context, gets a destination they can identify.
    */
    $link_text = 'Open the tracker for ' . $range;
    $html .= '<p><a href="' . esc_url($click) . '">' . esc_html($link_text) . '</a></p>';
    $text .= "\n{$link_text}:\n{$open}\n";

    /*
      THE EDITION'S OWN PERMALINK, WHICH THE EMAIL HAS NEVER OFFERED.

      This edition is archived at a stable URL the moment it is sent, and no
      message ever linked to it. That is the one link a journalist actually
      needs: the tracker link above lands on a live view that will have moved
      by the time anybody follows a citation, and this one is the record as it
      was published. The section is now short by design, so the full record
      has to be one click away rather than in the message.

      THE SLUG IS DERIVED, NOT LOOKED UP. alt_edition_slug() is the archive's
      own single definition and is a pure function of the tier and the window,
      so this cannot name a different edition than the one being captured.
      Guarded with function_exists for the same reason the tier sentence is:
      this file is loaded by harnesses that do not load digest-archive.php,
      and an absent archive prints no line rather than a broken link.

      IT IS DELIBERATELY NOT A COUNTED LINK. The counted wrapper exists to
      tell us whether the tracker link is followed at all; a second counted
      link in the same paragraph buys nothing and puts a redirect between a
      citation and the thing it cites.

      A TEST SEND HAS NO PUBLISHED EDITION and this link will 404 for it. That
      is correct and is not worth a branch: the edition publishes in the same
      request that sends the real message, so every recipient of a real
      edition has it, and a nominated test send is not an edition.
    */
    if (function_exists('alt_edition_slug') && function_exists('alt_edition_url')) {
        /*
          THE TIER IS DERIVED FROM THE WINDOW, not passed in, and it is the
          SAME derivation the week-on-week comparison above already uses: a
          seven day window is the weekly edition and anything else is not.
          The composer has never been told which tier it is composing for, and
          giving it a second way to find out is a second thing that can
          disagree with the first.
        */
        $freq_hint = ($ft !== false && $tt !== false && ($tt - $ft) === 6 * DAY_IN_SECONDS)
                   ? 'weekly' : 'daily';
        $edition_slug = alt_edition_slug($freq_hint, $from, $to);
        if ($edition_slug !== '') {
            $edition_url = alt_edition_url($freq_hint, $edition_slug);
            $edition_text = 'Read this edition in the archive';
            $html .= '<p><a href="' . esc_url($edition_url) . '">'
                   . esc_html($edition_text) . '</a></p>';
            $text .= "\n{$edition_text}:\n{$edition_url}\n";
        }
    }

    /*
      THE BIBLIOGRAPHY ENTRY, AT THE FOOT, WHERE ONE BELONGS.

      Read date: TODAY IN UTC, not the window's end. Those are different
      facts and conflating them is exactly the sort of thing this section
      keeps being wrong about. `$to` is the last day the figures COVER. The
      read date is the day they were pulled out of the database, which for a
      digest is the day it composes, one day after the window closes. UTC
      because that is the zone the send cron runs in, and rendered through
      alt_digest_date_range so it is the same "17 August 2026" shape as every
      other date in the email rather than a second format.

      The stamp comes from api.php's alt_data_last_updated_label(), the same
      function the press kit prints, so the email and the press kit cannot
      disagree about when the data last moved. Guarded with function_exists
      for the same reason alt_announced_tier_sentence() is: this file is
      loaded by harnesses that do not load api.php, and an absent stamp
      prints nothing rather than a guess.
    */
    $cite_label = alt_digest_data_cut_label();
    /*
      THE ACCESS DATE NOW CARRIES A CLOCK, because the day on its own was not
      the fact a reader needed. Ingest finishes near 22:00 UTC and this digest
      goes out at 6:00 AM Eastern (10:00 UTC under EDT, 11:00 under EST), so the
      figures are about twelve hours old when they land. A bare date implies
      they were read this morning.
    */
    $read_date = alt_digest_date_range(gmdate('Y-m-d'), gmdate('Y-m-d'));
    if ($read_date !== '') $read_date .= ' at ' . gmdate('H:i') . ' UTC';
    /*
      ABOUT THIS SNAPSHOT: the methodology block, last, exactly where the owner
      put it when he set the edition's fixed hierarchy. Two facts a reader
      needs before quoting anything and neither of which belongs beside a
      figure: when the database last moved, and when we read it. The
      provisional note is NOT here; it travels with the figures it qualifies,
      which is where a reader is doing the arithmetic it warns about.

      IT IS PRINTED EVEN WHEN IT HAS LITTLE TO SAY, because a fixed template is
      the point: a section that disappears on a quiet day makes the edition
      unskimmable, and the reader who learned where to look has to learn again.
    */
    /*
      DATA NOTES: the residual arithmetic, once, together, ahead of the
      methodology. See the $data_notes docblock near the top for why these were
      pulled out of the tables they sit between. The section is OMITTED when
      there is nothing to reconcile - unlike the fixed methodology blocks below
      it, a "Data notes" heading over no notes is a heading about nothing. Each
      note already names its own window, so a note lifted out still says what it
      covers. It sits before "About this snapshot" because it is about the
      figures, and the snapshot and citation are about the reading of them.
    */
    if ($data_notes) {
        $html .= '<h3>Data notes</h3>';
        $text .= "\nData notes\n";
        foreach ($data_notes as $dn) {
            $html .= '<p data-alt="note">' . esc_html($dn) . '</p>';
            $text .= $dn . "\n";
        }
    }

    if ($snapshot !== '') {
        $html .= '<h3>About this snapshot</h3>'
               . '<p data-alt="note">' . esc_html($snapshot) . '</p>';
        $text .= "\nAbout this snapshot\n" . $snapshot . "\n";
    }

    if ($read_date !== '') {
        list($cite, $cite_url, $cite_note) = alt_digest_cite_note(
            'AI Layoff Tracker', $range, $url, $read_date, $cite_label);
        /*
          WHAT THE OWNER SAW, AND IT WAS THE MARKUP RATHER THAN THE WORDS.

          This block used `data-alt="kicker"`. In digest_layout.py that variant
          is documented as "the eyebrow over a headline figure": 11px,
          uppercase, letterspaced, grey, and `margin:0 0 4px` because it is
          meant to sit tight above a 34px number. Here it sat above 13px grey
          note text, so the LABEL rendered smaller than the thing it labelled
          and in exactly the same grey, with none of the top space every other
          block label in this email gets from `h3`. It read as a stray
          fragment, not as a heading: a bare heading over more small print,
          two lines from the section rule that starts the next tracker.

          It was also the only block label in the message that was not a real
          heading element, so a screen reader moving by heading skipped the
          citation entirely.

          And the citation string had the URL concatenated onto the end of the
          sentence inside ONE paragraph: "... accessed 18 August 2026.
          https://...". A reference somebody is meant to SELECT and paste
          should not have to be separated from a sentence first, and the run-on
          is what makes a client's autolinker swallow the trailing full stop.

          So: a real `h3`, like every other block, and the URL on its own line.
          It is STILL plain text and still not an anchor. See the docblock on
          alt_digest_cite_note for why that is deliberate and must stay.
        */
        /*
          THE PROVISIONAL NOTE IS NOT PRINTED HERE ANY MORE. It moved to sit
          beside the two headline figures, which is where a reader is doing the
          arithmetic it warns about, and where the owner asked for it. Printing
          it in both places said the same thing twice in one email, which is
          the repetition he called heavy. `$cite_note` is still RETURNED by
          alt_digest_cite_note and the talent composer still prints it; only
          this call site stops.
        */
        $html .= '<h3>Cite this</h3>'
               . '<p data-alt="note">' . esc_html($cite) . '</p>'
               . '<p data-alt="note">' . esc_html($cite_url) . '</p>';
        $text .= "\nCite this\n" . $cite . "\n" . $cite_url . "\n";
    }
    /*
      THIS SECTION'S FRAGMENT FOR THE SUBJECT, BOUND TO ITS OWN UNIT.

      WHAT SHIPPED ON 2026-08-19 AND WHY IT WAS THE MOST SERIOUS DEFECT IN THE
      REBUILD. The subject read "AI Layoff Tracker: 16,842 verified cuts this
      week". Metric first, inside the character budget, composed from the same
      query as the body. And a reader who never opened it took away sixteen
      thousand AI-attributed cuts from a week whose AI figure was ZERO. The one
      line that reaches the largest audience inflated the metric the product is
      named after from nothing to five figures, on its most quoted surface,
      while every line inside the edition was scrupulous about it.

      THE DEFECT WAS THE JUXTAPOSITION, not the numbers: a brand name beside an
      unqualified count reads as a count of that brand's metric, whatever the
      figures are and whichever tier is sending. So the fix is structural
      rather than a wording change. The subject now leads with the SITE and
      never with a tracker (alt_digest_subject_line), so there is no brand for
      a count to attach to, and this section contributes only a figure wearing
      its unit.

      THE UNIT IS "verified job cuts" AND A CONSISTENCY PASS MAY NOT FLATTEN
      IT. Each of these has a filing or a named report behind it. The talent
      tracker's "hiring signals" deliberately means something weaker, a
      published indication that is mostly unverified, and calling verified cuts
      "signals" would give away the product's whole differentiator.
    */
    $metric = alt_digest_number($ver_jobs) . ' verified job cuts';

    /*
      THE PREHEADER COMPLETES A TRUNCATED SUBJECT RATHER THAN RESTATING IT.

      The owner chose a ~78 character subject knowing Gmail on mobile cuts
      around 45. That truncation lands mid-figure and drops the second metric
      entirely, so the preview line is where the rest of the thought has to
      live. It used to open with the same United States figure the subject's
      first metric already implies, which spent the one recovery slot on a
      repeat.

      So it leads with the two things a truncated subject cannot carry: the AI
      figure, which is the one a reader is most likely to get wrong from the
      subject alone, and the United States split, which is the owner's stated
      first priority and appears nowhere in the subject.
    */
    /*
      THE PREVIEW ADDS, IT NEVER REPEATS. That is the only rule this line has.

      The subject now carries the worldwide figure and the window, so a preview
      restating either spends the one recovery slot a reader gets on something
      already on screen. The owner's inbox screenshot showed exactly that
      failure on two of three streams.

      So this carries the three facts the subject cannot: the AI figure, which
      is the number a reader is most likely to get wrong from a subject alone
      and the one this product is named after; the United States split, which
      is the stated first priority; and the company count, which says how
      concentrated the week was. The window is NOT here any more.
    */
    $preheader = alt_digest_fit_preheader(
        alt_digest_count($ai_jobs, 'cut') . ' attributed to AI',
        array(alt_digest_number($us_jobs) . ' in the United States',
              'across ' . alt_digest_count($companies_n, 'company', 'companies'),
              // A FOURTH CLAUSE, because the desktop client shows about 140
              // characters and this line ran out at 75. What follows a preview
              // that runs out is the body, and the body starts with the
              // masthead, so the owner's desktop inbox read "... across 73
              // companies. AskTheRecruiter.c...". The provenance is the right
              // thing to spend the room on: it is the fact a reporter checks
              // first and it is nowhere in the subject.
              $top_source));
    return array('html' => $html, 'text' => $text, 'preheader' => $preheader,
                 'metric' => $metric);
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

    // Same rule as the layoff section: a block that cannot state its own
    // window does not go out. See alt_digest_date_range for why.
    $range = alt_digest_date_range($from, $to);
    if ($range === '') return null;
    // The prepositional form of the same window. See alt_digest_span_phrase.
    $span = alt_digest_span_phrase($from, $to);
    if ($span === '') return null;

    $url = home_url('/talent-intelligence-tracker/');
    $companies_n = (int) ($data['companies'] ?? 0);
    $verified_n = (int) ($data['verified'] ?? 0);
    $verified = alt_digest_number($verified_n);
    $totalf = alt_digest_number($total);
    /*
      WHERE, AND WHY THIS ONE SAYS LESS THAN THE LAYOFF SECTION'S.

      Same defect, same fix: this composer sends no country parameter, so the
      count is worldwide, and until 2026-08-17 the headline never said so.

      It stops at "worldwide" and does not add the layoff section's measured
      "including entries with no country recorded", because here that clause
      would be unmeasured. The talent aggregate returns `by_country` capped at
      40 values against 84 live countries, so a shortfall against the total
      cannot tell an unplaced signal from one below the cut-off. An unmeasured
      caveat is the same fault as a fixed one. If that endpoint ever ships a
      placed/unplaced split, use alt_digest_geo_scope() here too.
    */
    $scope = $range . ', worldwide, counted by the date the source published.';
    /*
      THE UNIT SITS UNDER THE FIGURE, NOT ABOVE IT, and this is not cosmetic.

      This printed an eyebrow reading "New hiring signals", then the number.
      In the same message the layoff section prints a number and then "verified
      job cuts", so the two headline figures were built in opposite orders, and
      a reader comparing them had to notice that "1,376" and "16,842" count
      completely different things from labels sitting on opposite sides.

      A HIRING SIGNAL IS NOT A JOB AND IS NOT A CUT. It is a published
      indication that a company is hiring, mostly unverified, and one signal
      may name hundreds of jobs or none. The layoff tracker's unit has a filing
      or a named report behind every row. Setting the two side by side without
      binding each number to its own unit is the single most misleading thing
      this email can do, and it is why the subject line carries the units too.
    */
    $html = '<h2>Talent Intelligence Tracker</h2>'
          . '<p data-alt="stat">' . esc_html($totalf) . '</p>'
          . '<p data-alt="unit">'
          . esc_html(alt_digest_verb($total, 'new hiring signal', 'new hiring signals'))
          . '</p>'
          . '<p data-alt="scope">' . esc_html($scope) . '</p>';
    /*
      WHAT THE UNIT IS, IN THE READER'S WORDS, BESIDE THE FIGURE IT COUNTS.

      THE DEFECT THE OWNER READ. "1,379 hiring signals" sat above a ranked list
      whose top row named 2,200 jobs. Nothing in the message said those two
      numbers count different things, so the only available reading is that the
      week held 1,379 jobs and one employer supplied 2,200 of them. The rule
      was already written down in the comment above this one, and a rule that
      lives only in a comment is a rule the reader never gets.

      IT IS NOT THE VERIFIED SPLIT AND DOES NOT REPLACE IT. The sentence below
      says how many signals carry a primary document, which is a different
      question: this one says what ONE of them is. Both are short and both
      travel with the figure, because a reader who quotes the headline takes
      whatever is next to it and nothing else.
    */
    $unit_note = 'A hiring signal is one sourced employer update, not one job. '
               . 'Job counts below are the roles named in that update.';
    $html .= '<p data-alt="note">' . esc_html($unit_note) . '</p>';
    $lede = alt_digest_count($total, 'new hiring signal') . ', ' . $scope;
    // The same rule as the layoff section, same reason. This lede happens to
    // fit today; composing the snippet anyway means it keeps fitting when
    // somebody adds a clause to the body, which is exactly how the other one
    // broke. See alt_digest_fit_preheader.
    /*
      THE PREVIEW ADDS, IT NEVER REPEATS. This read "1,376 new hiring signals,
      August 10-16" beside a subject reading "1,376 hiring signals · Aug 10-16",
      which is the same sentence twice, and the owner saw it in his own inbox.

      THE VERIFIED SPLIT IS THE SECOND-MOST-USEFUL FACT ABOUT THIS TRACKER and
      it is the one a sceptical reader wants first. A hiring signal is a
      published indication, mostly unverified; how many carry a primary
      document behind them is exactly what the headline figure does not say.
      The company count follows, because a thousand signals from thirty
      companies is a different week from a thousand from six hundred.
    */
    $preheader = alt_digest_fit_preheader(
        $verified . ' of ' . $totalf . ' verified against a primary document',
        array('from ' . alt_digest_count($companies_n, 'company', 'companies')));
    $text = "Talent Intelligence Tracker\n{$lede}\n" . $unit_note . "\n";
    $detail = 'From ' . alt_digest_count($companies_n, 'company', 'companies') . ', '
            . $range . '. ' . $verified . ' of the ' . $totalf . ' '
            /*
              THE VERB AGREES WITH THE COUNT IN FRONT OF IT, which is the
              verified figure and not the total. This read the total, so a live
              send published "1 of the 186 are verified against primary
              documents". The verified count is one on most days, so this was
              the sentence a sceptical reader met most often.
            */
            . alt_digest_verb($verified_n, 'is', 'are')
            . ' verified against a primary document. The rest are published '
            . 'indications we have not confirmed.';
    $html .= '<p data-alt="note">' . esc_html($detail) . '</p>';
    $text .= $detail . "\n";

    /*
      ASK FOR MORE THAN FIVE, BECAUSE THE FIVE THAT ARRIVE ARE THE WRONG FIVE.

      THE DEFECT. This asked for 5 rows and printed them. A live send led with
      an untranslated Spanish headline and two funding rounds while a signal
      naming 2,200 jobs created sat below the fold of the list. The obvious
      diagnosis, "it is sorted by recency", is wrong and the real one matters:
      /talent/v1/query already DEFAULTS to sort=notable, so this was already
      getting materiality first. The problem is that materiality is saturated.
      Measured live over the week to 2026-08-16: 1,349 signals, of which 264
      are graded high, 1,082 medium and 3 routine. A grade that 99.8% of rows
      pass is not a ranking, so the tiebreak, recency, decided the list. And
      recency is close to random in a weekly digest, because every row in it
      is from the same week by construction.

      WHY NOT sort=largest, WHICH THE ENDPOINT DOES HONOUR. Only 64 of those
      1,349 rows carry a headcount at all, and MySQL sorts NULLs last on DESC,
      so that parameter returns five headcount stories and nothing else can
      ever compete for a slot. It replaces one bad ranking with a narrower one.

      SO THE RANKING IS DONE HERE, over a wider fetch, on a field already on
      every row. See alt_digest_talent_rank.
    */
    $q = new WP_REST_Request('GET', '/talent/v1/query');
    $q->set_param('since', $from);
    $q->set_param('until', $to);
    $q->set_param('per_page', 40);
    $qres = rest_do_request($q);
    if ($qres && !$qres->is_error()) {
        $qdata = (array) $qres->get_data();
        $rows = alt_digest_talent_rank(
            is_array($qdata['rows'] ?? null) ? $qdata['rows'] : array(), 5);
        if ($rows) {
            /*
              THE CAPTION CARRIES THE LANGUAGE ANSWER, ONCE, FOR THE WHOLE
              LIST. Two of the five rows in the live send of 2026-08-18 were
              Portuguese and Spanish, and in an English digest they read as
              unfinished work rather than as worldwide coverage.

              MEASURED before choosing, over 2026-08-11 to 2026-08-18: 1,411
              signals, of which 64 (4.5%) are already excluded on script. Of
              the 77 that name a headcount, and so of the only rows this list
              can ever show, 17 are Latin-script and not English. Those 17 are
              22% of the rows and 74% of the jobs named. Two of the top five by
              size and four of the top ten. Dropping non-English rows would
              delete three quarters of the biggest signals of the week to tidy
              a fifth of the list, so it is not done.

              THE ROW IS NOT LABELLED WITH A LANGUAGE EITHER, because we do not
              store one and would have to infer it from the headline. That is
              the same class of guess the script filter had to be corrected for
              once, and a short headline is the worst case for it: a stopword
              classifier run over this week could not decide 68 of 1,347
              Latin-script headlines, German and Portuguese among them. Naming
              a language we guessed is a claim the reader cannot check, in a
              product whose whole pitch is that every claim can be checked.

              SO THE ROW CARRIES ITS SOURCE, WHICH IS STORED AND NOT INFERRED,
              and the caption says plainly that the headline is a quotation.
              A reader who meets a Portuguese line then knows why it is there
              and who published it, and a reporter gets the outlet they need to
              go and check it. `source_name` is present on 100% of the week's
              rows; a row missing it prints nothing rather than a placeholder.
            */
            /*
              "THE TRACKER'S OWN ORDER" MEANT NOTHING TO A READER. It is the
              order the endpoint returned, which is newest first, and saying so
              costs three words and stops the caption gesturing at an internal
              detail nobody outside this repo can check.
            */
            $caption = $range . ', the signals naming the most jobs first, then '
                     . 'newest first. Each headline is quoted as its source '
                     . 'published it, in that source\'s own language.';
            $html .= '<h3>Biggest hiring signals</h3>'
                   . '<p data-alt="caption">' . esc_html($caption) . '</p>'
                   . '<ul>';
            $text .= "\nBiggest hiring signals\n" . $caption . "\n";
            $undated = 0;
            foreach ($rows as $row) {
                $row = (array) $row;
                /*
                  THE LABEL ONLY WHEN THE HEADLINE DOES NOT ALREADY CARRY IT.
                  See alt_digest_headline_names_company for the measurement and
                  for why this is not a prefix strip and not an unconditional
                  drop. With no headline the label IS the row, and with no
                  company the headline is.
                */
                $co = trim((string) ($row['company'] ?? ''));
                $head = trim((string) ($row['headline'] ?? ''));
                if ($head === '') {
                    $line = $co;
                } elseif ($co === '' || alt_digest_headline_names_company($co, $head)) {
                    $line = $head;
                } else {
                    $line = $co . ': ' . $head;
                }
                if ($line === '') continue;
                // The signal's own publication date, which is also what the
                // since/until window selects on. Some signals reach us with
                // no date on the source; those show none rather than borrow
                // the day we captured them.
                $pub = substr((string) ($row['published_date'] ?? ''), 0, 10);
                $when = alt_digest_date_range($pub, $pub);
                /*
                  THE NUMBER THAT DID THE RANKING IS SHOWN, because a list
                  claiming to lead with the biggest signals and printing no
                  size is asking to be taken on trust. A row naming no jobs
                  shows none: this is the stored headcount, never a guess, and
                  a zero here means "the source stated no number", not "zero
                  jobs", so it is omitted rather than printed as a measurement.
                */
                $facts = array();
                $jobs = isset($row['headcount']) ? (int) $row['headcount'] : 0;
                if ($jobs > 0) $facts[] = alt_digest_jobs_phrase($jobs);
                /*
                  WHERE, WHICH THIS LIST DID NOT SAY UNTIL 2026-08-20.

                  The biggest-cuts table two blocks up prints "(Massachusetts,
                  United States, takes effect 18 August 2026)" on every row.
                  This one printed jobs, outlet and date, so the email answered
                  "where" for every cut and for no hire, and a reader meeting a
                  10,000-role spree could not tell whether it was in the United
                  Kingdom or in India.

                  A ROW WITH NO PLACE SAYS SO, in the same words the cuts use.
                  43% of live rows carry no country, and they carry no city and
                  no region either, so there is nothing to fall back to and
                  nothing to infer from. Guessing from the outlet's own country
                  is the one tempting move and it is wrong: The Sun is a
                  British paper that reports hiring in other countries.
                */
                $place = alt_digest_talent_place($row);
                $facts[] = ($place !== '') ? $place : 'location not recorded';
                // WHO PUBLISHED IT. The row's own stored outlet, never
                // derived from the URL and never guessed: a row that carries
                // no source name prints no source, in the same way a row that
                // carries no date prints no date.
                $outlet = trim((string) ($row['source_name'] ?? ''));
                if ($outlet !== '') $facts[] = $outlet;
                if ($when !== '') { $facts[] = $when; } else { $undated++; }
                /*
                  THE HEADLINE IS A LINK, and until 2026-08-20 it was the only
                  list in this email that was not.

                  Every layoff block links each row to the thing that lets a
                  reader check it. These rows shipped as plain text, so the one
                  block whose whole content is somebody else's reporting was
                  the one block a reader could not follow.

                  IT LINKS TO THE SOURCE, not to us, and that follows the rule
                  alt_digest_rank_table states: link text should say where the
                  link goes. The visible text here IS the outlet's headline,
                  quoted as they published it, so the article is the only
                  destination that text honestly promises. `source_url` is
                  present on 100% of live rows.

                  NOT COUNTED, AND NOT PRETENDED TO BE. alt_digest_track_link
                  wraps first-party destinations only, by design, because a
                  counter that forwards anywhere is an open redirect on our own
                  domain. An external link is handed over plain rather than
                  routed through a guard it cannot pass.

                  WHERE A ROW SOMEHOW CARRIES NO USABLE SOURCE, the fallback is
                  the talent tracker filtered to that company and window, which
                  is the same fallback the biggest-cuts table uses when a row
                  has no entry page. That one IS first-party, so it is counted.
                */
                $src = trim((string) ($row['source_url'] ?? ''));
                $href = '';
                $plain = '';
                if (alt_digest_external_link_ok($src)) {
                    $href = $src;
                    $plain = $src;
                } elseif ($co !== '') {
                    $plain = alt_digest_talent_url($from, $to,
                        array('company' => $co));
                    $href = alt_digest_track_link($send_id, $plain);
                }
                $shown = esc_html($line);
                if ($href !== '') {
                    $shown = '<a href="' . esc_url($href) . '">' . $shown . '</a>';
                }
                if ($facts) {
                    // Outside the anchor, exactly as alt_digest_rank_table
                    // keeps its qualifiers outside: a screen reader should not
                    // announce the parenthesis as the name of the destination.
                    $shown .= ' ' . esc_html('(' . implode(', ', $facts) . ')');
                    $line .= ' (' . implode(', ', $facts) . ')';
                }
                $html .= '<li>' . $shown . '</li>';
                $text .= '  - ' . $line . "\n";
                // The plain destination, never the counted one: a text reader
                // should not be handed a machine-shaped URL to squint at.
                if ($plain !== '') $text .= '    ' . $plain . "\n";
            }
            $html .= '</ul>';
            /*
              THE CAVEAT ONLY WHEN IT IS TRUE, AND COUNTED WHEN IT IS.

              This used to print "A signal whose source carries no date shows
              none" whenever ANY row was dated, which is almost always, and
              so it appeared on sends where every row carried a date. That is
              the same fault the layoff country block had: fixed prose around
              variable data, correct on average and wrong in the particular
              case a reader happens to check.
            */
            if ($undated > 0) {
                // Agreement, because "1 of the signals show no date" is the
                // same carelessness as "1 jobs" and lands on the same reader.
                $basis = ($undated === 1)
                    ? ('One signal listed ' . $span . ' shows no date, because the '
                       . 'source carries none. We do not substitute the day we captured it.')
                    : ($undated . ' signals listed ' . $span . ' show no date, because '
                       . 'the source carries none. We do not substitute the day we '
                       . 'captured them.');
                $html .= '<p data-alt="note">' . esc_html($basis) . '</p>';
                $text .= $basis . "\n";
            }
        }
    }

    /*
      OTHER TALENT ACTIVITY, BECAUSE THE FORM PROMISES IT AND THE EMAIL DID NOT.

      The signup checkbox reads "hiring, leadership and compensation signals".
      The digest delivered hiring and nothing else, so two thirds of what a
      subscriber consented to was invisible in every edition they received.

      EACH COUNT IS ITS OWN QUERY, ON THIS WINDOW, AGAINST THE TALENT PLUGIN'S
      OWN VOCABULARY. Leadership and pay are pillars, a closed four-value list
      the pipeline always sets. A funding round is NOT a pillar: it is a
      predicate over the amount and stage fields, which is why it is asked for
      as `funding=1` and not as a category name. These are the same three
      specifications that page's own "I'm looking for" control offers, so a
      count here and the view the reader lands on are the same question.

      THEY OVERLAP BY DESIGN AND THE LINE SAYS SO. A funded employer can also
      be hiring, and a pay change can sit on a row that is also a leadership
      move. Summing them, or subtracting them from the headline, would be
      arithmetic on sets that are not disjoint. The caption states it rather
      than leaving a reader to add three numbers and find they do not fit.

      THE COUNT ONLY, NEVER THE DOLLARS. The talent tracker's funding AMOUNTS
      are known to be materially wrong: fund raises and IPOs are counted as
      company rounds and one stored figure is off by more than an order of
      magnitude. That is the sibling repo's defect to fix. Publishing a count
      of rounds does not depend on it; publishing a total raised would.

      A FAILED CALL PRINTS NO LINE, and this is the difference that matters. An
      endpoint that cannot answer is UNKNOWN, and a category rendered as "0"
      because a request failed is a measurement we did not make, published as
      one we did. A real zero from a working call is a real zero and prints.
    */
    $activity = array();
    foreach (array(
        array('Leadership moves', 'pillar', 'leadership_change'),
        array('Funding rounds', 'funding', '1'),
        array('Pay and benefits changes', 'pillar', 'rewards_comp'),
    ) as $cat) {
        list($cat_label, $cat_key, $cat_value) = $cat;
        $creq = new WP_REST_Request('GET', '/talent/v1/aggregate');
        $creq->set_param('since', $from);
        $creq->set_param('until', $to);
        $creq->set_param('include', 'fresh');
        $creq->set_param($cat_key, $cat_value);
        $cres = rest_do_request($creq);
        if (!$cres || $cres->is_error()) continue;
        $cdata = (array) $cres->get_data();
        // array_key_exists, not isset: a null total is an answer we cannot
        // read, and isset() would quietly turn it into a zero.
        if (!array_key_exists('total', $cdata)) continue;
        /*
          A FILTER THE ENDPOINT IGNORED RETURNS THE HEADLINE, AND THAT IS THE
          FAILURE THIS LINE EXISTS FOR.

          MEASURED AGAINST THE LIVE ROUTE ON 2026-08-19, not reasoned about.
          /talent/v1/aggregate does not validate these values: it drops one it
          does not recognise and answers with the UNFILTERED total. Over the
          window 2026-08-10 to 2026-08-16, where the unfiltered total is 1,387:

            pillar=leadership_change    846   honoured
            funding=1                   182   honoured
            pillar=rewards_comp          97   honoured
            pillar=company_development  229   honoured
            pillar=leadership_chang   1,387   IGNORED - one character short
            pillar=hiring_expansion   1,387   IGNORED - not a pillar at all
            pillar=                   1,387   IGNORED
            funding=0                 1,387   IGNORED
            funding=banana            1,387   IGNORED

          So a one-character typo here, or the sibling plugin renaming a pillar,
          publishes "Leadership moves 1,387" - the worldwide headline, wearing a
          category label, as a measurement. That is strictly worse than a wrong
          zero: a zero invites a question and a plausible large number does not.
          The error is SILENT, it is in the other repo's gift to cause, and no
          call fails, so the failed-call guard above cannot see it.

          THE TEST IS EQUALITY WITH THE HEADLINE, because that is the exact
          signature of the fault and this composer already holds the headline.
          It costs no extra request.

          WHAT IT GIVES UP, STATED PLAINLY: a genuine week in which every single
          signal fell into one category would be suppressed. Three categories
          cannot all equal the total, the categories overlap rather than
          partition, and the observed shares are 61%, 13% and 7%, so that week
          is not one this data produces. A suppressed true line costs a line. A
          published headline-in-disguise costs a number, and this product is
          built on the numbers being checkable.

          OMITTED AND NOT ZEROED. This is UNKNOWN - we did not measure the
          category - and the rule this file keeps is that absence of a signal is
          never a pass and never a zero.
        */
        if ((int) $cdata['total'] === $total) continue;
        $activity[] = array(
            'label'  => $cat_label,
            'figure' => alt_digest_number((int) $cdata['total']),
            'url'    => alt_digest_track_link($send_id, alt_digest_talent_url(
                            $from, $to, array($cat_key => $cat_value))),
        );
    }
    if ($activity) {
        list($act_html, $act_text) = alt_digest_inline_series($activity);
        // The heading above already says what this is. See the region and
        // industry lines in the layoff section for the same shape.
        $act_caption = $range . ', worldwide';
        $act_tail = '. These categories overlap with the hiring signals above '
                  . 'and with each other, so they do not sum to the headline.';
        $html .= '<h3>Other talent activity</h3>'
               . '<p data-alt="series">' . esc_html($act_caption . ': ') . $act_html
               . esc_html($act_tail) . '</p>';
        $text .= "\nOther talent activity\n" . $act_caption . ': '
               . $act_text . $act_tail . "\n";
    }

    // One year-to-date line, for the reason spelled out in
    // alt_digest_compose_layoff: this data revises upward, so any
    // period-over-period delta manufactures a fall out of a reporting lag.
    // Year to date only grows. Do not add a delta here later either.
    $year = substr((string) $to, 0, 4);
    if (preg_match('/^\d{4}$/', $year)) {
        $ytd_req = new WP_REST_Request('GET', '/talent/v1/aggregate');
        $ytd_req->set_param('since', $year . '-01-01');
        $ytd_req->set_param('until', $to);
        $ytd_req->set_param('include', 'fresh');
        $ytd_res = rest_do_request($ytd_req);
        $ytd_range = alt_digest_date_range($year . '-01-01', $to);
        if ($ytd_res && !$ytd_res->is_error() && $ytd_range !== '') {
            $ytd_total = (int) (((array) $ytd_res->get_data())['total'] ?? 0);
            if ($ytd_total > 0) {
                $ytd_scope = $ytd_range
                           . ', worldwide, counted by the date the source published.';
                // "2026 YTD", the year first, matching the layoff section. A
                // reader scanning headings meets the year before the
                // abbreviation, which is the same principle the month-first
                // date format follows.
                $html .= '<h3>' . esc_html($year) . ' YTD</h3>'
                       . '<p data-alt="stat">' . esc_html(alt_digest_number($ytd_total)) . '</p>'
                       . '<p data-alt="unit">'
                       . esc_html(alt_digest_verb($ytd_total, 'hiring signal',
                                                  'hiring signals')) . '</p>'
                       . '<p data-alt="scope">' . esc_html($ytd_scope) . '</p>';
                $text .= "\n{$year} YTD\n"
                       . alt_digest_count($ytd_total, 'hiring signal') . ', '
                       . $ytd_scope . "\n";
            }
        }
    }

    /*
      THE LINK CARRIES THE WINDOW THE LABEL PROMISES. It used to point at the
      bare page, which opens on the tracker's own default window, under a label
      reading "for August 10-16, 2026". See alt_digest_talent_url.

      $url, the unparameterised page, is still what the citation below prints,
      and deliberately: a bibliography entry names the work, and the window it
      covers is already a separate field in that entry.
    */
    $open = alt_digest_talent_url($from, $to);
    $click = alt_digest_track_link($send_id, $open);
    $link_text = 'Open the Talent Intelligence Tracker for ' . $range;
    $html .= '<p><a href="' . esc_url($click) . '">' . esc_html($link_text) . '</a></p>';
    $text .= "\n{$link_text}:\n{$open}\n";

    /*
      THIS SECTION IS AS CITABLE AS THE OTHER ONE, and until now only one of
      them said so. A reader who quotes a hiring-signal figure out of this
      email has the same problem a reader quoting a layoff figure has: the
      email is a snapshot and the database behind it keeps moving.

      NO "AS OF" STAMP HERE, and that is honest absence rather than an
      oversight. The layoff citation carries one because api.php publishes the
      layoff table's last write. The talent endpoints publish no equivalent, so
      this cites the window and the access time, which are the two facts we
      really have. Do not fill the gap with the layoff tracker's stamp: they
      are separate databases on separate ingest schedules.

      Plain text, not an anchor, for the reason spelled out on
      alt_digest_cite_note: a citation is a string somebody pastes, and a
      counted link in a published story records our click counter instead of
      our address.
    */
    $read_date = alt_digest_date_range(gmdate('Y-m-d'), gmdate('Y-m-d'));
    if ($read_date !== '') {
        $read_date .= ' at ' . gmdate('H:i') . ' UTC';
        list($cite, $cite_url, $cite_note) = alt_digest_cite_note(
            'Talent Intelligence Tracker', $range, $url, $read_date, '');
        $html .= '<h3>Cite this</h3>'
               . '<p data-alt="note">' . esc_html($cite) . '</p>'
               . '<p data-alt="note">' . esc_html($cite_url) . '</p>';
        $text .= "\nCite this\n" . $cite . "\n" . $cite_url . "\n";
    }
    /*
      ITS OWN SUBJECT AND ITS OWN METRIC FRAGMENT, EACH BOUND TO ITS UNIT.

      "hiring signals" is not "jobs" and not "cuts", and the combined edition's
      subject sets this figure beside the layoff tracker's. Two numbers side by
      side are read as the same quantity unless each says what it counts, so
      the unit lives inside the fragment rather than being implied by position.
    */
    $metric = alt_digest_count($total, 'hiring signal');
    return array('html' => $html, 'text' => $text, 'preheader' => $preheader,
                 'metric' => $metric);
}

/**
 * Compose the articles section: the site's OWN posts published in the period.
 *
 * WHY THIS EXISTS. The form has offered three boxes since it shipped, and only
 * two of them could ever be composed. Somebody who ticked ONLY "occasional
 * articles and product news" confirmed their address through double opt in,
 * was never counted as a recipient by either sender, and received nothing,
 * forever. A consent box with no sender behind it is a promise kept only in
 * the database.
 *
 * The source is WordPress posts, which is the only editorial supply the site
 * actually has, and it is read deliberately narrowly:
 *
 *   post_type 'post' ONLY. Every tracker surface (the tracker itself, health,
 *   sources, press, methodology, the reports) is a PAGE created by
 *   ai-layoff-tracker.php, and the entries are the 'layoffs' CPT, so neither
 *   can reach this list. The permalink check below is a SECOND gate, for the
 *   day somebody publishes a surface as a post.
 *
 *   The post's OWN excerpt, or none. An excerpt WordPress assembled from the
 *   first 55 words of the body is not a standfirst an editor wrote, and a
 *   title with no blurb is the honest shape when nobody wrote one.
 *
 * Returns null when the window holds no posts. An absent section is ABSENT:
 * no heading over a "nothing published this period" line. The reader learns
 * the same thing from silence, and we do not spend their attention saying it.
 */
/**
 * ONE LINE THAT SAYS WHY A POST IS WORTH A CLICK, or no line at all.
 *
 * THE DEFECT. This section shipped as a bare list of titles and URLs, and it
 * is the section a general reader is most likely to actually read. It DID
 * print a blurb, from `$post->post_excerpt`, and that field is empty on every
 * post on this blog: WordPress only fills it when an editor types one by
 * hand, and otherwise builds the excerpt from the post's own opening words at
 * render time. So the code looked right and the email was a list of links.
 * Measured live on 2026-08-17: 10 of 10 recent posts have a rendered excerpt,
 * 320 to 410 characters, and 0 of them reached the email.
 *
 * NOTHING HERE IS INVENTED, which is the only reason a fallback is allowed at
 * all. An auto-built excerpt is a verbatim trim of the post's own first
 * words, not a summary written by anything. This takes its FIRST SENTENCE,
 * because 340 characters under every item is the wall the nine-second budget
 * cannot pay for, and a sentence is a unit the author chose.
 *
 * A sentence longer than the cap is cut at a WORD boundary and marked. Never
 * mid-word, and the ellipsis is there so a reader can see that the author did
 * not stop there.
 */
function alt_digest_standfirst($text) {
    /*
      ENTITIES ARE DECODED, and this was found in a live preview rather than
      by reasoning. get_the_excerpt() returns display HTML, so a post whose
      opening line contains a curly quotation mark arrives as `&#8220;`.
      wp_strip_all_tags removes TAGS and leaves entities alone, so the first
      render of this feature published:

          ... little more than &#8220;tell me about yourself&#8221; and a
          vague sense...

      in the plain-text part, where nothing will ever turn it back into a
      quotation mark. Decoding happens here, after the tags have gone and
      before anything is measured, so the character count that decides the cap
      counts characters a reader sees rather than entity spellings. The HTML
      part re-escapes on the way out through esc_html, as it does for every
      other string in this file.
    */
    $text = html_entity_decode((string) $text, ENT_QUOTES, 'UTF-8');
    $text = trim(preg_replace('/\s+/', ' ', $text));
    if ($text === '') return '';
    /*
      TWO PASSES AT A WHOLE SENTENCE BEFORE ANY CUTTING, which is the owner's
      "it prints a truncated first sentence" answered at the cause. A complete
      sentence is a unit the author wrote; a severed one is neither a summary
      nor a quotation, and the research is blunt about it (front-load the point
      and let the opening carry it, which a truncation does neither of).

      So: the first sentence if it fits the reading budget; failing that the
      first sentence even when it is long, because a long complete thought
      beats a short broken one; and only when the author's opening sentence is
      longer than $hard do we cut, at a word boundary, marked.
    */
    $cap = 160;
    $hard = 240;
    // A full stop followed by a space and a capital is the shape; an
    // abbreviation like "U.S. layoffs" does not match it, which is the point.
    if (preg_match('/^(.{20,' . $cap . '}?[.!?])\s+[A-Z0-9"\']/u', $text, $m)) {
        return trim($m[1]);
    }
    if (preg_match('/^(.{20,' . $hard . '}?[.!?])\s+[A-Z0-9"\']/u', $text, $m)) {
        return trim($m[1]);
    }
    if (strlen($text) <= $cap) return $text;
    $cut = substr($text, 0, $cap);
    $space = strrpos($cut, ' ');
    if ($space !== false && $space > 40) $cut = substr($cut, 0, $space);
    return rtrim($cut, " ,;:.") . '...';
}

function alt_digest_compose_articles($from, $to, $send_id = 0) {
    if (!function_exists('get_posts')) return null;
    /*
      FETCH MORE THAN WE PRINT, so the caption can say how many there were.
      Three items with a standfirst each is a readable block; five is a wall,
      and this section competes with two others in a message a reader gives
      tens of seconds to. But "the three newest" is only honest if we know
      whether there were more, so the query ceiling is above the print limit.
    */
    $posts = get_posts(array(
        'post_type'           => 'post',
        'post_status'         => 'publish',
        'numberposts'         => 12,
        'orderby'             => 'date',
        'order'               => 'DESC',
        'has_password'        => false,
        'ignore_sticky_posts' => true,
        'suppress_filters'    => false,
        'date_query'          => array(array(
            'column'    => 'post_date_gmt',
            'after'     => $from,
            'before'    => $to . ' 23:59:59',
            'inclusive' => true,
        )),
    ));
    if (!is_array($posts) || !$posts) return null;

    $surface = home_url('/ai-layoff-tracker/');
    $items = array();
    foreach ($posts as $post) {
        $title = wp_strip_all_tags(get_the_title($post));
        $link = (string) get_permalink($post);
        if ($title === '' || !alt_digest_link_allowed($link)) continue;
        if (strpos($link, $surface) === 0) continue;   // a surface, not an article
        /*
          THE STANDFIRST, AND WHY THE FALLBACK IS NOT A GUESS.

          `post_excerpt` is the excerpt an editor typed, and on this blog
          nobody ever has: it is empty on every post, which is why this
          section shipped as a bare list of links while the code that prints
          a blurb sat right there looking correct. get_the_excerpt() is
          WordPress's own answer, returning the typed one when there is one
          and otherwise a verbatim trim of the post's opening words. Neither
          branch writes a sentence: one is the editor's, the other is the
          author's own first words.

          Guarded, because the harness that drives this composer stubs
          get_posts and get_permalink and need not stub everything. A missing
          function costs the standfirst, never the item.
        */
        $blurb = wp_strip_all_tags(isset($post->post_excerpt) ? $post->post_excerpt : '');
        if (trim($blurb) === '' && function_exists('get_the_excerpt')) {
            $blurb = wp_strip_all_tags((string) get_the_excerpt($post));
        }
        /*
          TWO FACTS PER ITEM, BOTH MEASURED, NEITHER WRITTEN.

          The date is the post's own publication date, rendered through
          alt_digest_date_range so it is the same "14 August 2026" shape as
          every other date in this email rather than a second format. It makes
          an item self-contained once somebody quotes or forwards one line,
          which is the doctrine the rest of this section already follows.

          The read time is COUNTED off the post's own body at 220 words a
          minute, and it is omitted entirely when the body cannot be counted.
          It is not an invented figure and it is not a guess: it is a word
          count and a stated divisor. It earns the line because the one thing
          a curated link block can promise a reader is how much of their time
          a click costs, and a promise you cannot keep small is worth making
          only when it is honestly small.
        */
        $when = alt_digest_date_range(
            substr((string) (isset($post->post_date_gmt) ? $post->post_date_gmt : ''), 0, 10),
            substr((string) (isset($post->post_date_gmt) ? $post->post_date_gmt : ''), 0, 10));
        $meta = array();
        if ($when !== '') $meta[] = $when;
        $words = 0;
        if (isset($post->post_content) && function_exists('str_word_count')) {
            $words = (int) str_word_count(wp_strip_all_tags((string) $post->post_content));
        }
        if ($words > 0) {
            $minutes = max(1, (int) round($words / 220));
            $meta[] = alt_digest_count($minutes, 'min read', 'min read');
        }
        $items[] = array(
            'title' => $title,
            'link'  => $link,
            'blurb' => alt_digest_standfirst($blurb),
            'meta'  => implode(', ', $meta),
        );
    }
    if (!$items) return null;

    /*
      THREE, AND SAY SO WHEN THERE WERE MORE.

      Five titles with a standfirst each is a wall, and this section sits
      below two others in a message a reader gives tens of seconds to. Three
      with a reason to click beats five without one. The caption states the
      window like every other block in this email, and it names the true
      total rather than implying three is all there was.

      RECENCY IS THE SORT, and it is named rather than dressed up. There is no
      engagement signal in this repo to rank on, and inventing a relevance
      score out of nothing would be exactly the thing this file refuses to do
      with figures. "Newest first" is what it is.
    */
    $found = count($items);
    $items = array_slice($items, 0, 3);
    $range = alt_digest_date_range($from, $to);
    // The prepositional form, because every clause here ends in the window.
    // See alt_digest_span_phrase for the sentence the owner sent back.
    $span = alt_digest_span_phrase($from, $to);
    $shown = count($items);
    $caption = $found > $shown
        ? ($shown === 1
            ? 'The newest of ' . $found . ' posts we published ' . $span . '.'
            : 'The ' . $shown . ' newest of ' . $found . ' posts we published '
              . $span . '.')
        : ($found === 1
            ? 'One post published ' . $span . '.'
            // "All 2 posts we published" spends its first word on a claim
            // nobody doubted. The count is the fact.
            : $found . ' posts published ' . $span . ', newest first.');

    /*
      THE FRAMING THE OWNER ASKED FOR, WHICH IS ONE SENTENCE.

      HIS COMPLAINT, VERBATIM IN SUBSTANCE: "Two blog posts appear with no
      framing. They are just there." He is right. The section had a heading and
      a count, and neither says what these are or why they follow three blocks
      of layoff statistics. A reader who has just read a week of figures meets
      two titles and has to work out the relationship themselves.

      IT IS FIXED PROSE AND THAT IS ALLOWED HERE, because it makes no claim
      about the items. It says what the section IS, which cannot stop being
      true when the posts change; the count, the window and the ordering are
      still measured and still live in the caption below it. Compare the "why
      it matters" line in the layoff section, which is a statement about the
      metric for exactly the same reason.
    */
    $standfirst = 'What we wrote around the numbers: analysis and explainers '
                . 'from the tracker team.';
    // `standfirst`, not `lead`. The lead variant is the 18px opening of the
    // layoff edition, and at that size this line outweighed the article titles
    // under it, which is the wrong hierarchy for a block whose job is to get a
    // reader into one of those titles.
    $html = '<h2>From the blog</h2>'
          . '<p data-alt="standfirst">' . esc_html($standfirst) . '</p>';
    $text = "From the blog\n" . $standfirst . "\n";
    if ($range !== '') {
        $html .= '<p data-alt="caption">' . esc_html($caption) . '</p>';
        $text .= $caption . "\n";
    }
    /*
      An articles-only subscriber exists and gets a message whose FIRST and
      only section is this one, so this section has to be able to write the
      inbox snippet too. The caption already states the count and the window,
      which is the whole job, so it is reused rather than reworded. It is
      still passed through the fitter: a caption is written for a body and
      this is the one place a ceiling applies.
    */
    /*
      THE PREVIEW ADDS, IT NEVER REPEATS. This reused the caption, so a subject
      reading "2 new posts \xc2\xb7 Aug 10-16" sat beside a preview reading "2 posts
      published between August 10 and 16, 2026", which is the same sentence
      twice. The owner saw it in his own inbox.

      A COUNT OF POSTS IS NOT A REASON TO OPEN ONE. The newest post's own title
      is, and it is the single thing the subject's figure cannot carry. It is
      the author's words, not ours, and a second title is added only when it
      fits, because a snippet is never truncated mid-title.

      AND THE SUBJECT NOW CARRIES THAT TITLE, so this gives it up. The subject
      led with "2 new posts", which is a count of things the reader has not
      seen and no reason to open any of them, and the preview carried the
      headline that was. Leading the subject with the headline is the right way
      round, and it makes the old preview an exact repeat of the subject in the
      one case where both are shown: the articles-only subscriber, who is the
      only reader whose subject this metric ever reaches.

      SO THE PREVIEW MOVES ONE DOWN THE LIST. It offers the SECOND title, and
      the count of whatever is below that, which is again the thing the subject
      cannot carry. On a single-post edition there is no second title and the
      post's own standfirst goes in the slot: the author's summary of the piece
      the subject just named, which adds rather than repeats.
    */
    $preheader = '';
    if ($items) {
        $titles = array();
        foreach ($items as $item) $titles[] = $item['title'];
        array_shift($titles);
        if ($titles) {
            $rest = (count($titles) > 1)
                ? array('and ' . alt_digest_count(count($titles) - 1, 'more post'))
                : array();
            $preheader = alt_digest_fit_preheader('Also: ' . $titles[0], $rest);
        } else {
            $blurb = trim((string) ($items[0]['blurb'] ?? ''));
            $preheader = ($blurb === '') ? ''
                       : alt_digest_fit_preheader($blurb, array());
        }
    }
    /*
      THE BREAKUP THE OWNER ASKED FOR, AND WHY IT IS A TABLE.

      This was a `<ul>`: three titles, each with a `<br>` and a severed
      sentence hanging under it, at one size, in one colour, with a bullet in
      front. Nothing in it said where one item ended and the next began except
      the bullet, and a bullet is the weakest separator in an email because it
      is the one thing a client is most likely to restyle.

      Each item is now its own cell with a hairline `border-top`, and the
      separation is therefore a rule the reader can see rather than a glyph
      they have to infer. That choice is measured, not aesthetic: `<table>` is
      at 100% client support and `<hr>` at 72.97% (caniemail), and empty
      spacer rows do not reliably keep their height (Email on Acid), so every
      gap here is cell padding and every break is a cell border. The first
      item carries no rule, because a rule directly under the caption would
      read as the end of the caption rather than the start of a list.

      NO STYLE IS WRITTEN HERE, as everywhere else in this file. The cell says
      what it IS with data-alt and railway/digest_layout.py decides what that
      looks like, so the design lives in one file and this one decides only
      what a line means.
    */
    $html .= '<table role="presentation" width="100%" cellpadding="0" '
           . 'cellspacing="0" border="0">';
    foreach ($items as $i => $item) {
        // Counted the same way the other two sections count theirs: a
        // destination that fails the host guard is left unwrapped, never
        // dropped, so counting can never break or relocate a link.
        $click = alt_digest_track_link($send_id, $item['link']);
        $html .= '<tr><td data-alt="' . ($i === 0 ? 'item-first' : 'item') . '">'
               . '<p data-alt="item-title"><a href="' . esc_url($click) . '">'
               . esc_html($item['title']) . '</a></p>';
        $text .= '  - ' . $item['title'] . "\n";
        if ($item['blurb'] !== '') {
            $html .= '<p data-alt="item-blurb">' . esc_html($item['blurb']) . '</p>';
            $text .= '    ' . $item['blurb'] . "\n";
        }
        if ($item['meta'] !== '') {
            $html .= '<p data-alt="item-meta">' . esc_html($item['meta']) . '</p>';
            $text .= '    ' . $item['meta'] . "\n";
        }
        $html .= '</td></tr>';
        // The plain URL in the text part: a text reader should not be handed a
        // machine shaped URL to squint at.
        $text .= '    ' . $item['link'] . "\n";
    }
    $html .= '</table>';
    /*
      A MINOR METRIC. The post count is the least important of the three
      numbers and the combined subject is already at its ceiling, so it reaches
      a subject only when it is the ONLY thing the message carries, which is
      the articles-only subscriber, who exists.
    */
    /*
      THE HEADLINE IS THIS STREAM'S METRIC.

      "2 new posts \xc2\xb7 Aug 10-16" is too generic to earn an open: it names a
      quantity of things the reader cannot see and no reason to want any of
      them. The post's own title is the metric here, in the same way a job
      count is the layoff section's, and it is the author's words rather than
      ours. No brand prefix and no "From the blog:" label: the sender column
      already carries the brand, and a category label in front of a headline
      spends the characters Gmail truncates on saying nothing.

      ONE TITLE, NEVER A CONCATENATION. Two headlines joined by a dot is a
      subject a reader parses instead of reads, and the second one is always
      cut. The lead is the newest post, which is the sort this composer prints
      and states; there is no engagement signal in this repo to rank on, and
      inventing one to pick a "best" title would be the fixed-prose-around-
      variable-data fault in a new place. The rest of the edition is named in
      the preview line directly above.

      STILL 'minor'. A post title must never displace a tracker figure for a
      subscriber who takes both, which is what that flag governs, and nothing
      about leading with the headline changes that ordering.
    */
    return array('html' => $html, 'text' => $text, 'preheader' => $preheader,
                 'metric' => alt_digest_subject_title($items ? $items[0]['title'] : ''),
                 'minor' => true);
}

/* ------------------------------------------------------------------ */
/* Sending                                                             */
/* ------------------------------------------------------------------ */

/**
 * Where a reader changes WHAT they get, as opposed to stopping everything.
 *
 * It is the signup form's own anchor, and that is the whole design.
 * Re-submitting the form updates preferences through the SAME double opt in
 * that created them, so a change needs the mailbox, and there is deliberately
 * no token authenticated preferences route: a long lived link in a million
 * inboxes that edits a record without proving the mailbox is a bigger surface
 * than the problem it solves.
 *
 * THE MECHANISM SURVIVED A COMPLAINT ON 2026-08-19. THE COPY DID NOT.
 *
 * The owner followed his own digest footer and reported "I can't really
 * manage", on all three emails. He was right, and the fault was never here:
 * the footer said "Manage your subscriptions", which names a preference
 * centre, and this returns a signup form. A reader promised a preference
 * centre and shown a Subscribe button concludes the feature is broken, and
 * stops looking.
 *
 * Both halves of that gap were closed IN COPY, not in mechanism:
 *   - the footer now names the form and the three steps, and warns that the
 *     change needs a confirmation click (railway/digest_layout.py _footer);
 *   - the form's own intro now says, to everyone, that this is where a
 *     subscription is changed and that the boxes REPLACE rather than add.
 *
 * That second sentence is load bearing and is not decoration.
 * alt_digest_prefs_from_post() builds the WHOLE preference set from the boxes
 * that were ticked, so a subscriber on all three lists who ticks only
 * `articles` intending to add it loses the other two. Nothing in the flow
 * warned them, and a footgun a reader cannot see is worse than an ugly form.
 *
 * WHY NOT A TOKEN LINK, given the complaint. Still the docblock's reasoning
 * above, plus a second thing the outage-shaped version of this argument
 * misses: the pending_prefs branch of alt_digest_signup() means a stranger
 * who types your address CANNOT alter what you receive. A possession-only
 * preference link trades that away. If it is ever built, it needs a
 * per-recipient URL, which means the payload contract in digest-api.php and
 * railway/digest_send.py both move; it is not a copy change wearing a
 * token's clothes.
 */
function alt_digest_manage_url() {
    return home_url('/ai-layoff-tracker/') . '#alt-digest';
}

/**
 * THE FOOTER'S PROMISES, IN ONE DEFINITION, BECAUSE THERE ARE THREE FOOTERS.
 *
 * A digest footer is composed three times: twice by the relay's renderer
 * (railway/digest_layout.py, once for HTML and once for plain text) and once
 * here, by the wp_mail fallback below. Which one a reader gets depends on
 * whether an external relay has claimed the tier, which is infrastructure
 * state a reader cannot see. So the sentences have to be identical.
 *
 * They were not, the first time they were edited. "Manage your subscriptions"
 * was withdrawn on 2026-08-19 because it named a preference centre that does
 * not exist; the relay copy was corrected and this one went on making the
 * withdrawn promise until a grep found it. Its test asserted the fallback
 * "offers it too", which is a presence check, so it stayed green while the
 * two senders told readers different things.
 *
 * Same reasoning as ALT_RELAY_TRACKING and alt_digest_window(): a claim that
 * exists once can only be wrong ONCE. This function is the authority, because
 * the manage URL and the signup form it points at live in this file.
 * FOOTER_BLOCKS in railway/digest_layout.py is its mirror, and
 * railway/tests/test_digest_sender.py extracts both sets and fails on any
 * difference. Add a sentence in one place and CI is red before a reader ever
 * sees two versions of it.
 *
 * The anchor is the substring the HTML turns into a link, and the relay's
 * text part follows the same sentence with a bare URL. Writing the wording
 * once is what stops the two renderings naming different destinations.
 */
function alt_digest_footer_blocks($unsub_url, $manage_url = '') {
    $blocks = array(
        array(
            'url' => '',
            'anchor' => '',
            'sentences' => array(
                'You get this because you confirmed a digest subscription at asktherecruiter.com.',
            ),
        ),
        array(
            'url' => $unsub_url,
            'anchor' => 'Unsubscribe with one click',
            'sentences' => array(
                'Unsubscribe with one click, which stops everything at once.',
            ),
        ),
    );
    // OMITTED RATHER THAN RENDERED WITHOUT A LINK. A promise with nowhere to
    // go is worse than silence, and the relay drops it the same way when a
    // payload carries no manage URL.
    if ($manage_url) {
        $blocks[] = array(
            'url' => $manage_url,
            'anchor' => 're-enter your address on the signup form',
            'sentences' => array(
                'To change what you get, re-enter your address on the signup form and tick the lists you want.',
                'The change applies when you confirm by email.',
            ),
        );
    }
    return $blocks;
}

/**
 * The fallback sender's footer, built from the blocks above and from nothing
 * else. No reader-facing sentence is typed in alt_digest_send(), which is the
 * property the test checks: prose that is not here cannot reach an inbox.
 */
function alt_digest_footer_html($unsub_url, $manage_url = '') {
    $out = array();
    foreach (alt_digest_footer_blocks($unsub_url, $manage_url) as $block) {
        $text = esc_html(implode(' ', $block['sentences']));
        if ($block['url'] && $block['anchor']) {
            // The anchor is escaped the same way before it is looked for, so a
            // sentence is never linked against a string the reader will not
            // see. A wording change that loses the anchor ships the sentence
            // unlinked rather than a half rendered tag.
            $needle = esc_html($block['anchor']);
            $pos = strpos($text, $needle);
            if ($pos !== false) {
                $text = substr_replace(
                    $text,
                    '<a href="' . esc_url($block['url']) . '">' . $needle . '</a>',
                    $pos, strlen($needle));
            }
        }
        $out[] = $text;
    }
    return '<p style="font-size:12px;color:#555;">' . implode(' ', $out) . '</p>';
}

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
        'articles' => alt_digest_compose_articles($from_date, $to_date, $send_id),
    );

    // The public archive's copy, taken at COMPOSE time and not from any
    // message: it re-composes at send_id 0, so it cannot carry a click URL,
    // and it never sees a recipient. It is stored unpublished and becomes
    // visible only when this run records a delivery below. See
    // includes/digest-archive.php.
    if (function_exists('alt_edition_capture')) {
        alt_edition_capture($freq, $from_date, $to_date, $send_id);
    }

    $rows = alt_digest_due_rows($freq);

    $fallback_subject = alt_digest_fallback_subject($freq, $to_date);
    $sent = 0;
    foreach ($rows as $row) {
        $parts_html = array();
        $parts_text = array();
        // The sections' own first lines, in the order they appear, which is
        // what names the trackers in the subject. Collected per recipient
        // because the sections are: this list is what THIS person consented
        // to, so the subject names what is actually inside their message.
        $headings = array();
        $subject_parts = array();
        foreach (array('layoff', 'talent', 'articles') as $list) {
            $cols = alt_digest_lists()[$list];
            if ((int) $row[$cols['consent']] === 1 && $row[$cols['freq']] === $freq && $sections[$list]) {
                $parts_html[] = $sections[$list]['html'];
                $parts_text[] = $sections[$list]['text'];
                $headings[] = alt_digest_section_heading($sections[$list]['text']);
                // EVERY section this person gets, in the site's order, so the
                // combined form can see both trackers. Matches the relay exactly.
                $subject_parts[] = array(
                    'metric' => (string) ($sections[$list]['metric'] ?? ''),
                    'minor'  => !empty($sections[$list]['minor']),
                );
            }
        }
        if (!$parts_html) continue;   // nothing to say to this person today
        $subject = alt_digest_subject_line($freq, $from_date, $to_date, $headings,
                                           $fallback_subject, $subject_parts);

        $unsub = alt_digest_unsub_url($row['unsub_token']);
        // Text-first HTML: no images, no pixels, no external assets. See the
        // file header for why tracking is deliberately absent.
        /*
          THE PREVIEW LINE, WHICH THIS SENDER DID NOT HAVE AT ALL.

          The relay's own renderer (railway/digest_layout.render_html) has
          emitted a hidden preheader since it was written; this fallback
          sender never did, so a message that went out through wp_mail showed
          the client's own guess in the preview slot, which is where "View this
          email in your browser" comes from.

          It matters more now than it did. The subject leads with the brand,
          which costs about twenty characters the From name already supplies,
          so Gmail on mobile truncates near 45 and the tail of the subject is
          dropped. The preview is the one slot left to complete it.

          Hidden, and FIRST, so it is the text the client picks up. The colour
          matches the surrounding page for the clients that ignore display:none.
        */
        $preheader = '';
        foreach (array('layoff', 'talent', 'articles') as $list) {
            $cols = alt_digest_lists()[$list];
            if ((int) $row[$cols['consent']] === 1 && $row[$cols['freq']] === $freq
                && $sections[$list] && !empty($sections[$list]['preheader'])) {
                $preheader = (string) $sections[$list]['preheader'];
                break;
            }
        }
        $hidden = ($preheader === '') ? '' :
            '<div style="display:none;max-height:0;max-width:0;overflow:hidden;'
            . 'opacity:0;font-size:1px;line-height:1px;color:#ffffff;'
            . 'mso-hide:all;">' . esc_html($preheader) . '</div>';
        $html = $hidden
              . '<div style="font-family:sans-serif;max-width:600px;color:#1a1a1a;">'
              . implode('', $parts_html)
              . '<hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px;">'
              // NOT ONE READER-FACING WORD IS TYPED HERE ANY MORE. This is the
              // wp_mail fallback and it used to compose its own footer, which
              // made it a second copy of a promise the relay also makes, in a
              // different language, with nothing keeping the two in step. It
              // now renders alt_digest_footer_blocks(), the single definition
              // the relay's FOOTER_BLOCKS mirrors and a test compares.
              . alt_digest_footer_html($unsub, alt_digest_manage_url())
              . '</div>';
        $headers = array_merge(
            array('Content-Type: text/html; charset=UTF-8'),
            alt_digest_from_header(),
            alt_digest_list_unsub_headers($row['unsub_token'])
        );
        if (wp_mail($row['email'], $subject, $html, $headers)) {
            $sent++;
            // The TIER's own stamp is what the guard reads. last_sent_at is
            // written beside it and is not read here any more: it is what an
            // older plugin build would guard on, so a rollback still holds.
            $now = gmdate('Y-m-d H:i:s');
            $wpdb->update($table, array(
                alt_digest_last_sent_column($freq) => $now,
                'last_sent_at' => $now,
            ), array('id' => $row['id']));
        }
    }
    // The edition goes public only once a message actually went out. A run
    // that sent nothing leaves its captured row unpublished and invisible.
    if ($sent > 0 && function_exists('alt_edition_publish')) {
        alt_edition_publish($send_id, $freq);
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
 * is exactly one schedule to monitor. BOTH tiers run on a Monday, and both
 * reach their own subscribers: until 2026-08-17 the two calls below shared
 * one last-sent column, so the daily call stamped every row it mailed and the
 * weekly call then found the same people already sent to. The guard is per
 * tier now (alt_digest_last_sent_column), so this reads the way it always
 * looked like it read.
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
        // WAS A HARDCODED 'none' AND WAS FALSE FROM 2026-08-16 TO 2.20.107.
        // It was written in 2.19.274 to mean "this plugin embeds no open
        // pixel", which is still true and is still enforced. But the field is
        // named open_tracking in a payload about the mailing list, so it reads
        // as a claim about the emails a subscriber receives, and those HAVE
        // been measured at the relay since the owner turned it on. It now
        // reports the state we believe the provider is in, from the same
        // constant the reader-facing copy uses, so the operator payload cannot
        // disagree with the published note. 'provider' means the relay adds a
        // pixel we did not put there; 'none' means nobody measures opens.
        'open_tracking' => ALT_RELAY_TRACKING ? 'provider' : 'none',
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

/**
 * The in-WordPress fallback sender's slot, and it now runs AFTER the real one.
 *
 * This WP-Cron tick is the standby: .github/workflows/digest-send.yml is the
 * sender, at 6:00 AM Eastern daily (10:00 UTC under EDT, 11:00 under EST) and
 * 7:30 AM Eastern on Mondays for the weekly. The external job claims the tier
 * first and this fallback finds the claim and stands down for the day, so the
 * ordering below is the one it always wanted. Until 2026-08-19 the workflow ran
 * at 13:10 UTC, ten minutes AFTER this tick, so on a day WP-Cron actually fired
 * on time the fallback got there first and the external sender was the one that
 * stood down.
 *
 * The claim ages out after ALT_DIGEST_CLAIM_HOURS, so if the workflow stops
 * firing this fallback resumes by itself rather than waiting to be re-armed.
 *
 * 13:00 UTC is kept deliberately. It is not a mirror of the sender's slot and
 * must not be re-pointed at one: the fallback's job is to be LATE enough that
 * the real sender has already claimed the day, and WP-Cron is traffic-
 * dependent anyway, so its scheduled time is a floor rather than a promise.
 */
function alt_digest_cron_schedule() {
    if (!wp_next_scheduled('alt_digest_cron')) {
        // 13:00 UTC: morning US East, and after the external sender's 6:00 AM
        // Eastern slot, so the fallback finds the day already claimed.
        $first = strtotime('today 13:00 UTC');
        if ($first < time()) $first = strtotime('tomorrow 13:00 UTC');
        wp_schedule_event($first, 'daily', 'alt_digest_cron');
    }
}
add_action('init', 'alt_digest_cron_schedule');
