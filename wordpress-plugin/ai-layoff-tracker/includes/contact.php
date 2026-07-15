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
    return array(
        'correction'  => 'Data correction',
        'tip'         => 'Report a layoff we\'re missing',
        'press'       => 'Press / journalist inquiry',
        'api'         => 'API or dataset access',
        'partnership' => 'Partnership / advertising',
        'other'       => 'Something else',
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
        'rate'    => 'Too many messages from this connection — please try again in an hour.',
        'fields'  => 'Please fill in your name, a valid email, and a message.',
        'mail'    => 'Sorry — the message could not be sent. Please email us directly.',
        'expired' => 'The form expired. Please try again.',
    );

    ob_start();
    ?>
    <div class="alt-wrap alt-contact-wrap">
        <?php if ($sent) : ?>
            <div class="alt-status alt-contact-ok" role="status">
                <strong>Thanks — your message is on its way.</strong>
                We read everything and reply to corrections fastest.
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
                <div class="alt-filter">
                    <label for="alt-c-link">Link to the tracker entry or source (optional)</label>
                    <input type="url" id="alt-c-link" name="alt_link" maxlength="500" placeholder="https://">
                    <span class="alt-contact-note">For corrections, paste the entry you're flagging so we can locate it fast.</span>
                </div>
                <div class="alt-filter">
                    <label for="alt-c-msg">Message</label>
                    <textarea id="alt-c-msg" name="alt_message" required rows="6" maxlength="5000" placeholder="Tell us what you need. For corrections, include what the figure should be and the source it comes from."></textarea>
                </div>
                <div class="alt-filter">
                    <label for="alt-c-captcha">Spam check: what is <?php echo (int) $a; ?> + <?php echo (int) $b; ?>?</label>
                    <input type="number" id="alt-c-captcha" name="alt_captcha" required inputmode="numeric" autocomplete="off">
                </div>
                <div class="alt-filter alt-contact-submit">
                    <button type="submit" class="alt-btn alt-btn-primary">Send message</button>
                </div>
            </div>
            <p class="alt-contact-note">We reply within 3 business days — corrections get priority, and fixes are logged publicly on the tracker. You can also email <a href="mailto:<?php echo esc_attr(ALT_CONTACT_TO); ?>"><?php echo esc_html(ALT_CONTACT_TO); ?></a> directly.</p>
        </form>
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

    // Arithmetic challenge (answer stored server-side under the token).
    $token = preg_replace('/[^a-zA-Z0-9]/', '', (string) ($_POST['alt_token'] ?? ''));
    $expected = get_transient('alt_captcha_' . $token);
    delete_transient('alt_captcha_' . $token); // single use
    if ($expected === false) $fail('expired');
    if ((int) ($_POST['alt_captcha'] ?? -1) !== (int) $expected) $fail('spam');

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
        '[ATR Contact] ' . $topic . ' — ' . $name,
        $body,
        array('Reply-To: ' . $name . ' <' . $email . '>')
    );

    if (!$ok) $fail('mail');
    wp_safe_redirect(add_query_arg('alt_sent', '1', $back));
    exit;
}
add_action('admin_post_alt_contact', 'alt_contact_submit');
add_action('admin_post_nopriv_alt_contact', 'alt_contact_submit');

/**
 * Auto-create the /contact page on deploy if it doesn't exist yet (FTP deploys
 * can't create WP pages, so the plugin does it on the first request after a
 * version bump — same trigger as the cache flush).
 */
function alt_ensure_contact_page() {
    if (get_page_by_path('contact')) return;
    wp_insert_post(array(
        'post_type'    => 'page',
        'post_status'  => 'publish',
        'post_title'   => 'Contact',
        'post_name'    => 'contact',
        'post_content' => "<!-- wp:paragraph --><p>Questions, corrections, press inquiries, or a layoff we should be tracking — use the form below and it goes straight to our inbox.</p><!-- /wp:paragraph -->\n\n<!-- wp:shortcode -->[alt_contact]<!-- /wp:shortcode -->",
    ));
}
