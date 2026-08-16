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
             OR (consent_talent = 1 AND freq_talent = %s)
             OR (consent_articles = 1 AND freq_articles = %s))
           AND (last_sent_at IS NULL OR last_sent_at < %s)",
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
    );
    return isset($leads[$context]) ? $leads[$context] : '';
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

             THERE IS DELIBERATELY NO prefers-color-scheme BLOCK HERE. It would
             be the obvious next line and it would be wrong: the surfaces that
             have a dark mode all load layoffs.css, so they are already served
             by the var() half of every token above. The one surface relying on
             these literals is the blog, and blog-reading.css declares no dark
             palette at all, while the theme and the two database stylesheets
             pin the article to #fff. A dark box on a permanently white page is
             not dark mode, it is a hole. */ ?>
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
    .alt-digest-privacy { margin-top: 14px; font-size: 13px; }
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
        <p class="alt-digest-intro"><?php if ($lead !== '') echo esc_html($lead) . ' '; ?>A plain email summary of what changed on these trackers: the period's
            headline numbers and the largest new entries, with links back to the source pages. No images,
            no tracking pixels. You confirm your address by clicking a link we email you, and every email
            carries a one-click unsubscribe. Details in the <a href="#alt-digest-privacy">privacy note</a> below.</p>
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
 * A date a reader can read, out of the ISO date the endpoints return.
 *
 * Returns '' for anything that is not a plain YYYY-MM-DD, and every caller
 * treats that as "print no date". A row whose date we do not have prints
 * nothing there: not a zero, not today, not the period's edge.
 */
function alt_digest_short_date($iso) {
    $iso = substr(trim((string) $iso), 0, 10);
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $iso, $m)) return '';
    $month = (int) $m[2];
    $day = (int) $m[3];
    if ($month < 1 || $month > 12 || $day < 1 || $day > 31) return '';
    $names = array('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec');
    return $day . ' ' . $names[$month - 1] . ' ' . $m[1];
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
    $req->set_param('date_basis', 'layoff_date');
    /*
      `include` is an OPT-IN allowlist (alt_aggregate_blocks). `include=leaders`
      alone therefore returned `top_countries` as an empty array, which is why
      the country block at the foot of this section could not be built. Both
      blocks this section reads have to be named. `totals` is always computed
      and is not a nameable block, so it does not go here, and an unrecognised
      name falls back to all ~31 statements: do not tidy these into one word.
    */
    $req->set_param('include', 'leaders,top_countries');
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
        $dated = false;
        foreach ($leaders as $l) {
            $l = (array) $l;
            // The date was in the payload all along and never printed, so an
            // entry read as though it happened at some point in the window.
            // A row carrying no date simply shows none.
            $when = alt_digest_short_date($l['layoff_date'] ?? '');
            if ($when !== '') $dated = true;
            $line = ($l['company_name'] ?? '') . ': ' . number_format_i18n((int) ($l['job_count'] ?? 0)) . ' jobs'
                  . (!empty($l['location']) ? ', ' . $l['location'] : '')
                  . ($when !== '' ? ', takes effect ' . $when : '');
            $html .= '<li>' . esc_html($line) . '</li>';
            $text .= '  - ' . $line . "\n";
        }
        $html .= '</ul>';
        if ($dated) {
            $basis = 'Dates above are when the job cuts take effect, and this period uses the same basis. '
                   . 'The tracker page counts by filing date, so its figures for these dates differ.';
            $html .= '<p style="margin:0 0 8px;">' . esc_html($basis) . '</p>';
            $text .= $basis . "\n";
        }
    }

    /*
      ONE YEAR-TO-DATE LINE, AND DELIBERATELY NO PERIOD-OVER-PERIOD DELTA.

      This data revises upward for weeks. Filings and WARN notices arrive
      after the event, so the newest period is always the least complete one
      we hold. A week-on-week or month-on-month line would therefore turn a
      reporting lag into a fall that never happened, which is exactly the
      defect the trend charts already had: an incomplete month drew as a
      collapse. A year-to-date total only grows, so a late arrival corrects
      it rather than inverting it. Do not add a delta here later.

      The year comes from the period's own end date, not from the clock, so a
      run that composes a window is never labelled with a different year. The
      basis matches the section above for the same reason it is named there.
    */
    $year = substr((string) $to, 0, 4);
    if (preg_match('/^\d{4}$/', $year)) {
        $ytd_req = new WP_REST_Request('GET', '/layoffs/v1/aggregate');
        $ytd_req->set_param('from', $year . '-01-01');
        $ytd_req->set_param('to', $to);
        $ytd_req->set_param('date_basis', 'layoff_date');
        // One real block name, because naming none of them costs all of them.
        // Nothing below reads it; `totals` is what this call is for.
        $ytd_req->set_param('include', 'leaders');
        $ytd_res = rest_do_request($ytd_req);
        if ($ytd_res && !$ytd_res->is_error()) {
            $ytd_data = $ytd_res->get_data();
            $ytd_totals = is_array($ytd_data) ? ($ytd_data['totals'] ?? null) : null;
            if (!is_array($ytd_totals) && is_object($ytd_totals)) $ytd_totals = (array) $ytd_totals;
            $ytd_jobs = is_array($ytd_totals) ? (int) ($ytd_totals['jobs'] ?? 0) : 0;
            if ($ytd_jobs > 0) {
                $ytd_line = $year . ' so far: ' . number_format_i18n($ytd_jobs) . ' job cuts.';
                $html .= '<p style="margin:0 0 8px;">' . esc_html($ytd_line) . '</p>';
                $text .= $ytd_line . "\n";
            }
        }
    }

    /*
      WHERE THE JOBS WERE, PLUS THE BUCKET THAT IS NOT A PLACE.

      "Multiple countries" is a real stored value: a global cut announced with
      no per-country split. On the 2026 window it is the second largest line
      on this list and about a sixth of the total. Folding it into a region
      would invent a location for jobs nobody located, and dropping it would
      quietly shrink the world, so it sits on its own line outside the five
      and says what it is.

      This composer sends no country_basis, so these are strict job locations,
      the `country` column rather than the employer's domicile. The list is
      also a top five over rows that carry a country at all, so it does not
      add up to the headline. Both facts are in the copy: a reader who adds
      the lines and finds a gap must be able to see why without asking.
    */
    $top_countries = is_array($data['top_countries'] ?? null) ? $data['top_countries'] : array();
    $named = array();
    $multi = 0;
    foreach ($top_countries as $row) {
        $row = array_values((array) $row);
        $name = trim((string) ($row[0] ?? ''));
        $value = (int) ($row[1] ?? 0);
        if ($name === '' || $value <= 0) continue;
        if (strcasecmp($name, 'Multiple countries') === 0) { $multi = $value; continue; }
        if (count($named) < 5) $named[$name] = $value;
    }
    if ($named) {
        $lead = 'Where the jobs were, by job location:';
        $html .= '<p style="margin:0 0 8px;">' . esc_html($lead) . '</p>'
               . '<ul style="margin:0 0 8px;padding-left:20px;">';
        $text .= $lead . "\n";
        foreach ($named as $name => $value) {
            $line = $name . ': ' . number_format_i18n($value) . ' jobs';
            $html .= '<li>' . esc_html($line) . '</li>';
            $text .= '  - ' . $line . "\n";
        }
        $html .= '</ul>';
        $note = '';
        if ($multi > 0) {
            $note = 'Multiple countries: ' . number_format_i18n($multi) . ' jobs. '
                  . 'That line is global cuts announced with no country split. ';
        }
        $note .= 'These are job locations only, so the list does not add up to the total above.';
        $html .= '<p style="margin:0 0 8px;">' . esc_html($note) . '</p>';
        $text .= $note . "\n";
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
            $dated = false;
            foreach ($rows as $row) {
                $row = (array) $row;
                $line = trim((string) ($row['company'] ?? ''));
                $head = trim((string) ($row['headline'] ?? ''));
                $line = $line !== '' ? ($head !== '' ? $line . ': ' . $head : $line) : $head;
                if ($line === '') continue;
                // The signal's own publication date, which is also what the
                // since/until window selects on. Some signals reach us with
                // no date on the source; those show none rather than borrow
                // the day we captured them.
                $when = alt_digest_short_date($row['published_date'] ?? '');
                if ($when !== '') { $dated = true; $line .= ' (' . $when . ')'; }
                $html .= '<li>' . esc_html($line) . '</li>';
                $text .= '  - ' . $line . "\n";
            }
            $html .= '</ul>';
            if ($dated) {
                $basis = 'Dates above are when the source published. '
                       . 'A signal whose source carries no date shows none.';
                $html .= '<p style="margin:0 0 8px;">' . esc_html($basis) . '</p>';
                $text .= $basis . "\n";
            }
        }
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
        if ($ytd_res && !$ytd_res->is_error()) {
            $ytd_total = (int) (((array) $ytd_res->get_data())['total'] ?? 0);
            if ($ytd_total > 0) {
                $ytd_line = $year . ' so far: ' . number_format_i18n($ytd_total) . ' signals.';
                $html .= '<p style="margin:0 0 8px;">' . esc_html($ytd_line) . '</p>';
                $text .= $ytd_line . "\n";
            }
        }
    }

    $click = alt_digest_track_link($send_id, $url);
    $html .= '<p style="margin:0;"><a href="' . esc_url($click) . '">Open the Talent Intelligence Tracker</a></p>';
    $text .= "Open the tracker: {$url}\n";
    return array('html' => $html, 'text' => $text);
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
function alt_digest_compose_articles($from, $to, $send_id = 0) {
    if (!function_exists('get_posts')) return null;
    $posts = get_posts(array(
        'post_type'           => 'post',
        'post_status'         => 'publish',
        'numberposts'         => 5,
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
        $items[] = array(
            'title' => $title,
            'link'  => $link,
            'blurb' => wp_strip_all_tags(isset($post->post_excerpt) ? $post->post_excerpt : ''),
        );
    }
    if (!$items) return null;

    $html = '<h2 style="font-size:16px;margin:24px 0 8px;">From the blog</h2>'
          . '<ul style="margin:0 0 8px;padding-left:20px;">';
    $text = "From the blog\n";
    foreach ($items as $item) {
        // Counted the same way the other two sections count theirs: a
        // destination that fails the host guard is left unwrapped, never
        // dropped, so counting can never break or relocate a link.
        $click = alt_digest_track_link($send_id, $item['link']);
        $html .= '<li style="margin:0 0 8px;"><a href="' . esc_url($click) . '">'
               . esc_html($item['title']) . '</a>';
        $text .= '  - ' . $item['title'] . "\n";
        if ($item['blurb'] !== '') {
            $html .= '<br>' . esc_html($item['blurb']);
            $text .= '    ' . $item['blurb'] . "\n";
        }
        $html .= '</li>';
        // The plain URL in the text part: a text reader should not be handed a
        // machine shaped URL to squint at.
        $text .= '    ' . $item['link'] . "\n";
    }
    $html .= '</ul>';
    return array('html' => $html, 'text' => $text);
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
 */
function alt_digest_manage_url() {
    return home_url('/ai-layoff-tracker/') . '#alt-digest';
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
        'articles' => alt_digest_compose_articles($from_date, $to_date, $send_id),
    );

    $rows = alt_digest_due_rows($freq);

    $label = $freq === 'daily' ? 'Daily' : 'Weekly';
    $sent = 0;
    foreach ($rows as $row) {
        $parts_html = array();
        $parts_text = array();
        foreach (array('layoff', 'talent', 'articles') as $list) {
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
              . '<a href="' . esc_url($unsub) . '">Unsubscribe with one click</a> (stops everything at once), or '
              . '<a href="' . esc_url(alt_digest_manage_url()) . '">Manage your subscriptions</a> '
              . 'to change which of these you get.</p>'
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
