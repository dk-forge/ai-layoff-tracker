<?php
/**
 * Contact page: [alt_contact] shortcode + submission handler.
 *
 * Mails submissions to info@asktherecruiter.com. Spam defenses (no external
 * service needed): honeypot field, arithmetic challenge, minimum-fill-time
 * check, nonce, and a per-IP rate limit.
 */

if (!defined('ABSPATH')) exit;

define('ALT_CONTACT_TO', 'info@asktherecruiter.com');

function alt_contact_topics() {
    // Alphabetical, with the catch-all pinned last: a person scanning a list
    // looks for their own words, and "Something Else" is the one option that
    // is only correct once every other line has been ruled out.
    //
    // The labels say what the person is bringing us, not what we call it
    // internally. "Data correction" made someone guess whose data; "API or
    // dataset access" means nothing to a reader who has never used an API.
    return array(
        'tip'         => 'A Layoff You Are Missing',
        'api'         => 'Access to the Data or API',
        'app'         => 'Help With the Resume Tool',
        'partnership' => 'Partnership or Advertising',
        'press'       => 'Press or Media Enquiry',
        'correction'  => 'Something in the Tracker Looks Wrong',
        'other'       => 'Something Else',
    );
}

function alt_shortcode_contact() {
    // Arithmetic challenge: store the answer server-side, keyed by a token,
    // so the correct answer never appears in the page source.
    $a = wp_rand(2, 9);
    $b = wp_rand(2, 9);
    $token = wp_generate_password(16, false, false);
    set_transient('alt_captcha_' . $token, $a + $b, 30 * MINUTE_IN_SECONDS);

    $sent  = isset($_GET['alt_sent']);
    $error = isset($_GET['alt_error']) ? sanitize_key($_GET['alt_error']) : '';
    $messages = array(
        'spam'    => 'That looked like spam to us. Please try again (check the math question).',
        'rate'    => 'Too many messages from this connection. Please try again in an hour.',
        'fields'  => 'Please fill in your name, a valid email, and a message.',
        'mail'    => 'Sorry, the message could not be sent. Please email us directly.',
        'expired' => 'The form expired. Please try again.',
    );

    ob_start();
    ?>
    <div class="alt-wrap alt-contact-wrap">
        <?php if ($sent) : ?>
            <div class="alt-status alt-contact-ok" role="status">
                <strong>Thanks, your message is on its way.</strong>
            </div>
        <?php elseif ($error && isset($messages[$error])) : ?>
            <div class="alt-status alt-status-error" role="alert"><?php echo esc_html($messages[$error]); ?></div>
        <?php endif; ?>

        <form class="alt-contact-form" method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
            <input type="hidden" name="action" value="alt_contact">
            <?php wp_nonce_field('alt_contact', 'alt_contact_nonce'); ?>
            <input type="hidden" name="alt_token" value="<?php echo esc_attr($token); ?>">
            <input type="hidden" name="alt_ts" value="<?php echo esc_attr(time()); ?>">
            <!-- honeypot: humans never see or fill this -->
            <div class="alt-hp" aria-hidden="true"><label>Website<input type="text" name="alt_website" tabindex="-1" autocomplete="off"></label></div>

            <div class="alt-contact-grid">
                <div class="alt-filter">
                    <label for="alt-c-topic">Subject</label>
                    <select id="alt-c-topic" name="alt_topic" required>
                        <?php foreach (alt_contact_topics() as $key => $label) : ?>
                            <option value="<?php echo esc_attr($key); ?>"><?php echo esc_html($label); ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div class="alt-filter">
                    <label for="alt-c-name">Your name</label>
                    <input type="text" id="alt-c-name" name="alt_name" required maxlength="120" autocomplete="name">
                </div>
                <div class="alt-filter">
                    <label for="alt-c-email">Your email</label>
                    <input type="email" id="alt-c-email" name="alt_email" required maxlength="200" autocomplete="email" placeholder="you@example.com">
                    <span class="alt-contact-note">So we can reply. We never share this.</span>
                </div>
                <div class="alt-filter">
                    <label for="alt-c-org">Outlet / company (optional)</label>
                    <input type="text" id="alt-c-org" name="alt_org" maxlength="160" autocomplete="organization">
                </div>
                <div class="alt-filter alt-tip-only" hidden>
                    <label for="alt-c-tipco">Company that had the layoff</label>
                    <input type="text" id="alt-c-tipco" name="alt_tip_company" maxlength="160" placeholder="e.g. Acme Corp">
                </div>
                <div class="alt-filter">
                    <label for="alt-c-link">Link to the source (news report, filing, or company post)</label>
                    <input type="url" id="alt-c-link" name="alt_link" maxlength="500" placeholder="https://">
                    <span class="alt-contact-note alt-tip-note" hidden>Reporting a layoff? A source link lets us verify it against the original and add it automatically. Without one we still read your tip, but it needs a manual check first.</span>
                    <span class="alt-contact-note alt-nontip-note">For corrections, paste the entry you're flagging so we can locate it fast.</span>
                </div>
                <div class="alt-filter">
                    <label for="alt-c-msg">Message</label>
                    <textarea id="alt-c-msg" name="alt_message" required rows="6" maxlength="5000" placeholder="Tell us what you need. For corrections, include what the figure should be and the source it comes from."></textarea>
                </div>
                <div class="alt-filter">
                <?php if (defined('ALT_RECAPTCHA_SITE_KEY') && ALT_RECAPTCHA_SITE_KEY) : ?>
                    <label>Quick check to keep bots out</label>
                    <div class="g-recaptcha" data-sitekey="<?php echo esc_attr(ALT_RECAPTCHA_SITE_KEY); ?>"></div>
                    <script src="https://www.google.com/recaptcha/api.js" async defer></script>
                <?php else : ?>
                    <label for="alt-c-captcha">Quick check to keep bots out: what is <?php echo (int) $a; ?> + <?php echo (int) $b; ?>?</label>
                    <input type="number" id="alt-c-captcha" name="alt_captcha" required inputmode="numeric" autocomplete="off">
                <?php endif; ?>
                </div>
                <div class="alt-filter alt-contact-submit">
                    <button type="submit" class="alt-btn alt-btn-primary">Send message</button>
                </div>
            </div>
            <p class="alt-contact-note">We usually reply within 3 business days, and corrections get looked at first. Anything we fix gets logged publicly on the tracker, so you can see it was handled.</p>
        </form>
        <script>
        (function () {
            var topic = document.getElementById('alt-c-topic');
            if (!topic) return;
            var sync = function () {
                var isTip = topic.value === 'tip';
                document.querySelectorAll('.alt-tip-only').forEach(function (el) { el.hidden = !isTip; });
                var tn = document.querySelector('.alt-tip-note'), nn = document.querySelector('.alt-nontip-note');
                if (tn) tn.hidden = !isTip;
                if (nn) nn.hidden = isTip;
            };
            topic.addEventListener('change', sync);
            sync();
        })();
        </script>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('alt_contact', 'alt_shortcode_contact');

function alt_contact_submit() {
    $back = wp_get_referer() ?: home_url('/contact/');
    $back = remove_query_arg(array('alt_sent', 'alt_error'), $back);
    $fail = function ($code) use ($back) {
        wp_safe_redirect(add_query_arg('alt_error', $code, $back));
        exit;
    };

    if (!isset($_POST['alt_contact_nonce']) || !wp_verify_nonce($_POST['alt_contact_nonce'], 'alt_contact')) {
        $fail('expired');
    }

    // Honeypot filled or form submitted inhumanly fast -> bot.
    if (!empty($_POST['alt_website'])) $fail('spam');
    $ts = (int) ($_POST['alt_ts'] ?? 0);
    if (!$ts || (time() - $ts) < 3) $fail('spam');

    if (defined('ALT_RECAPTCHA_SECRET') && ALT_RECAPTCHA_SECRET) {
        // Google reCAPTCHA v2 verification (enabled by defining the keys).
        $rc = wp_remote_post('https://www.google.com/recaptcha/api/siteverify', array(
            'timeout' => 8,
            'body' => array(
                'secret'   => ALT_RECAPTCHA_SECRET,
                'response' => (string) ($_POST['g-recaptcha-response'] ?? ''),
                'remoteip' => $_SERVER['REMOTE_ADDR'] ?? '',
            )));
        $rc_ok = false;
        if (!is_wp_error($rc)) { $rc_body = json_decode((string) wp_remote_retrieve_body($rc), true); $rc_ok = !empty($rc_body['success']); }
        if (!$rc_ok) $fail('spam');
    } else {
        // Arithmetic challenge (answer stored server-side under the token).
        $token = preg_replace('/[^a-zA-Z0-9]/', '', (string) ($_POST['alt_token'] ?? ''));
        $expected = get_transient('alt_captcha_' . $token);
        delete_transient('alt_captcha_' . $token); // single use
        if ($expected === false) $fail('expired');
        if ((int) ($_POST['alt_captcha'] ?? -1) !== (int) $expected) $fail('spam');
    }

    // Per-IP rate limit: 3 messages/hour.
    $ip = sanitize_text_field($_SERVER['REMOTE_ADDR'] ?? '');
    $rate_key = 'alt_contact_rate_' . md5($ip);
    $count = (int) get_transient($rate_key);
    if ($count >= 3) $fail('rate');
    set_transient($rate_key, $count + 1, HOUR_IN_SECONDS);

    $topics = alt_contact_topics();
    $topic_key = sanitize_key($_POST['alt_topic'] ?? 'other');
    $topic = $topics[$topic_key] ?? 'Something else';
    $name  = sanitize_text_field(wp_unslash($_POST['alt_name'] ?? ''));
    $email = sanitize_email(wp_unslash($_POST['alt_email'] ?? ''));
    $org   = sanitize_text_field(wp_unslash($_POST['alt_org'] ?? ''));
    $link  = esc_url_raw(wp_unslash($_POST['alt_link'] ?? ''));
    $msg   = sanitize_textarea_field(wp_unslash($_POST['alt_message'] ?? ''));

    if ($name === '' || !is_email($email) || $msg === '') $fail('fields');

    $body = "Topic: $topic\nName: $name\nEmail: $email\n";
    if ($org)  $body .= "Outlet/company: $org\n";
    if ($link) $body .= "Related link: $link\n";
    $body .= "\nMessage:\n$msg\n\n--\nSent from the AI Layoff Tracker contact form\nIP: $ip";

    $ok = wp_mail(
        ALT_CONTACT_TO,
        '[ATR Contact] ' . $topic . ': ' . $name,
        $body,
        array('Reply-To: ' . $name . ' <' . $email . '>')
    );

    // A tip that names a layoff AND gives a source link is enqueued for the
    // hands-off processor (which verifies it against the source before anything
    // publishes). Tips without a link still email us; they just cannot enter the
    // automated path, because a lead with no source cannot be verified.
    if ($topic_key === 'tip' && $link !== '' && function_exists('alt_tips_append')) {
        // Prefer an explicit company field; fall back to the outlet/company box.
        $tip_company = sanitize_text_field(wp_unslash($_POST['alt_tip_company'] ?? '')) ?: $org;
        alt_tips_append($tip_company, $link, $email, $msg);
    }

    if (!$ok) $fail('mail');
    wp_safe_redirect(add_query_arg('alt_sent', '1', $back));
    exit;
}
add_action('admin_post_alt_contact', 'alt_contact_submit');
add_action('admin_post_nopriv_alt_contact', 'alt_contact_submit');

/**
 * Press-brief opt-in. Double-safety: honeypot + the same arithmetic captcha as
 * the contact form. Stores the email in the plugin's subscriber list; the
 * monthly brief is composed and sent from there. Opt-in only, with a clear
 * source, so it stays CAN-SPAM clean.
 */
function alt_press_subscribe_submit() {
    $back = wp_get_referer() ?: home_url('/ai-layoff-tracker/press/');
    if (!empty($_POST['alt_hp'])) { wp_safe_redirect(add_query_arg('alt_sub', '1', $back)); exit; }
    $token = sanitize_text_field($_POST['alt_captcha_token'] ?? '');
    $answer = (int) ($_POST['alt_captcha'] ?? -1);
    $expected = get_transient('alt_captcha_' . $token);
    if ($expected === false || (int) $expected !== $answer) {
        wp_safe_redirect(add_query_arg('alt_sub_err', 'spam', $back)); exit;
    }
    delete_transient('alt_captcha_' . $token);
    $email = sanitize_email(wp_unslash($_POST['alt_sub_email'] ?? ''));
    if (!is_email($email)) { wp_safe_redirect(add_query_arg('alt_sub_err', 'email', $back)); exit; }
    if (function_exists('alt_press_subscribe')) {
        alt_press_subscribe($email, sanitize_text_field(wp_unslash($_POST['alt_sub_name'] ?? '')),
                             sanitize_text_field(wp_unslash($_POST['alt_sub_outlet'] ?? '')));
    }
    wp_safe_redirect(add_query_arg('alt_sub', '1', $back)); exit;
}
add_action('admin_post_alt_press_subscribe', 'alt_press_subscribe_submit');
add_action('admin_post_nopriv_alt_press_subscribe', 'alt_press_subscribe_submit');

/**
 * Auto-create the /contact page on deploy if it doesn't exist yet (FTP deploys
 * can't create WP pages, so the plugin does it on the first request after a
 * version bump — same trigger as the cache flush).
 */
function alt_contact_intro_html() {
    return "<!-- wp:paragraph --><p>Tell us about a layoff we have missed, something in the tracker that looks wrong, or anything else. Pick the closest subject below and it comes straight to us.</p><!-- /wp:paragraph -->\n\n<!-- wp:shortcode -->[alt_contact]<!-- /wp:shortcode -->";
}

function alt_ensure_contact_page() {
    if (get_page_by_path('contact')) return;
    wp_insert_post(array(
        'post_type'    => 'page',
        'post_status'  => 'publish',
        'post_title'   => 'Contact',
        'post_name'    => 'contact',
        'post_content' => alt_contact_intro_html(),
    ));
}

/**
 * Refresh the stored /contact intro to the current copy. The create hook will
 * not touch a page that already exists, so without this the intro on the live
 * site is frozen at whatever wording shipped the day the page was created.
 *
 * The option is keyed by copy REVISION, not by a bare "done" flag: a plain flag
 * closes the door behind the first migration, which is why the v2 copy sat live
 * after the wording moved on. Bump ALT_CONTACT_INTRO_REV whenever
 * alt_contact_intro_html() changes, and add the superseded sentence to the list
 * below so the guard still recognises the page as ours.
 *
 * The guard is what protects an owner edit: we only overwrite content that is
 * still verbatim one of OUR shipped intros. Anything hand-written on the page
 * stops the migration and stays.
 */
define('ALT_CONTACT_INTRO_REV', 3);

function alt_contact_intro_shipped_phrases() {
    return array(
        'goes straight to our inbox',
        'Got a question, a correction, a press request',
    );
}

function alt_contact_intro_migrate() {
    if ((int) get_option('alt_contact_intro_rev') >= ALT_CONTACT_INTRO_REV) return;
    $p = get_page_by_path('contact');
    if (!$p) return;
    foreach (alt_contact_intro_shipped_phrases() as $phrase) {
        if (strpos((string) $p->post_content, $phrase) !== false) {
            wp_update_post(array('ID' => $p->ID, 'post_content' => alt_contact_intro_html()));
            break;
        }
    }
    update_option('alt_contact_intro_rev', ALT_CONTACT_INTRO_REV, false);
}
add_action('init', 'alt_contact_intro_migrate', 21);
