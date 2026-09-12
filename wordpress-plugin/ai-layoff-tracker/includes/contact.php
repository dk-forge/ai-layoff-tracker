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

/**
 * One line per subject, shown under the select as soon as it is chosen.
 *
 * The label is what a person scans; the hint is what stops them guessing. A
 * label has to stay short enough to read in a dropdown, so it can name the
 * thing without saying what happens to it, who should pick it, or what we will
 * need from them. That is the sentence below.
 *
 * Every key in alt_contact_topics() must have one. alt_contact_topic_hint()
 * falls back to '' rather than to another subject's sentence, because a hint
 * that describes the wrong option is worse than no hint at all.
 */
function alt_contact_topic_hints() {
    return array(
        'tip'         => 'A layoff that is not in the tracker yet. A link to a news report, a filing or the company\'s own post is what lets us verify it.',
        'api'         => 'You want to pull our data into something of your own, or you are asking about bulk access. Tell us roughly what you are building.',
        'app'         => 'Anything about the resume and cover letter tool at asktherecruiter.com: your account, your credits, or something that did not work.',
        'partnership' => 'Sponsorship, advertising, or working together on something. Not a job application.',
        'press'       => 'You are writing about layoffs and want figures, context, or a comment you can quote.',
        'correction'  => 'A number, a date, a company or a country in the tracker that does not match the source. Paste the entry and tell us what it should say.',
        'other'       => 'None of the above. Say what you need in the message and it reaches the same inbox.',
    );
}

function alt_contact_topic_hint($key) {
    $hints = alt_contact_topic_hints();
    return isset($hints[$key]) ? $hints[$key] : '';
}

/**
 * A FORM WHOSE CHALLENGE IS BAKED INTO CACHEABLE HTML IS A BROKEN FORM.
 *
 * The contact form carries three values that are minted per request: the WP
 * nonce, the render timestamp, and the arithmetic token whose answer is held
 * in a 30 minute transient. All three were printed into the page and the page
 * sits behind a shared cache. Measured 2026-09-12: the edge served one render
 * from 19:35 for hours, so every visitor was handed the same token long after
 * its transient had gone, the same nonce on its way to expiring, and a
 * timestamp from before they arrived. The form answered "That looked like
 * spam to us", which is the one reading that sends an honest person away
 * believing they did something wrong.
 *
 * includes/blog-claps.php already learned this and says so in its own comment:
 * "the page is cached, so there is no session to gate on and a nonce would be
 * stale HTML". The contact form never got the same treatment.
 *
 * So the challenge is fetched, not printed. This route is no-store, returns a
 * freshly minted set on every call, and the form asks for one as it loads. The
 * values rendered into the HTML stay exactly as they were and remain the
 * fallback for a visitor with no JavaScript on an uncached page: strictly more
 * works than before, and nothing that worked stops.
 */
function alt_contact_mint_challenge() {
    $a = wp_rand(2, 9);
    $b = wp_rand(2, 9);
    $token = wp_generate_password(16, false, false);
    set_transient('alt_captcha_' . $token, $a + $b, 30 * MINUTE_IN_SECONDS);
    return array(
        'nonce' => wp_create_nonce('alt_contact'),
        'ts'    => time(),
        'token' => $token,
        'a'     => $a,
        'b'     => $b,
    );
}

function alt_api_contact_challenge() {
    $resp = rest_ensure_response(alt_contact_mint_challenge());
    // Every hop, not just ours. A cached challenge is the defect this exists
    // to answer, so nothing may hold it: not the browser, not the edge.
    $resp->header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0');
    $resp->header('Pragma', 'no-cache');
    return $resp;
}

function alt_contact_register_routes() {
    register_rest_route('layoffs/v1', '/contact-challenge', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_contact_challenge',
        // Public by necessity, exactly as /clap is: the visitor is anonymous
        // and the page in front of this is cached. What bounds the form is the
        // challenge itself, the honeypot, the minimum fill time and the per-IP
        // rate limit, none of which a credential would improve.
        'permission_callback' => '__return_true',
    ));
}
add_action('rest_api_init', 'alt_contact_register_routes');

function alt_shortcode_contact() {
    // Arithmetic challenge: the answer is stored server-side under a token, so
    // it never appears in the page source. Minted through the SAME function
    // the /contact-challenge route uses, so the printed fallback and the
    // fetched replacement cannot drift apart.
    $challenge = alt_contact_mint_challenge();
    $a = $challenge['a'];
    $b = $challenge['b'];
    $token = $challenge['token'];

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
                    <select id="alt-c-topic" name="alt_topic" required aria-describedby="alt-c-topic-hint"
                            data-alt-hints="<?php echo esc_attr(wp_json_encode(alt_contact_topic_hints())); ?>">
                        <?php foreach (alt_contact_topics() as $key => $label) : ?>
                            <option value="<?php echo esc_attr($key); ?>"><?php echo esc_html($label); ?></option>
                        <?php endforeach; ?>
                    </select>
                    <?php
                    // Rendered server-side for the option the browser selects by
                    // default, so the hint is right before any script runs and
                    // stays right if none ever does.
                    $first = array_key_first(alt_contact_topics());
                    ?>
                    <span class="alt-contact-note alt-topic-hint" id="alt-c-topic-hint"><?php echo esc_html(alt_contact_topic_hint($first)); ?></span>
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
                <div class="alt-filter alt-link-row">
                    <label for="alt-c-link" id="alt-c-link-label">Link to the source (news report, filing, or company post)</label>
                    <?php
                    // NOT type="url". That makes the browser reject
                    // "example.com/the-article" and refuse to submit the whole
                    // form over a field that is optional, which is what the
                    // owner hit on 2026-09-12. People paste what they copied.
                    // The scheme is added server-side by alt_contact_clean_url()
                    // and the value is still validated there, so nothing is
                    // accepted that was not accepted before.
                    ?>
                    <input type="text" id="alt-c-link" name="alt_link" maxlength="500"
                           inputmode="url" autocomplete="url"
                           placeholder="paste the address, with or without https://">
                    <span class="alt-contact-note alt-tip-note" hidden>Reporting a layoff? A source link lets us verify it against the original and add it automatically. Without one we still read your tip, but it needs a manual check first.</span>
                    <span class="alt-contact-note alt-app-note" hidden>Optional. If something went wrong on a particular page, paste its address here.</span>
                    <span class="alt-contact-note alt-nontip-note">For corrections, paste the entry you're flagging so we can locate it fast.</span>
                </div>
                <div class="alt-filter">
                    <label for="alt-c-msg">Message</label>
                    <textarea id="alt-c-msg" name="alt_message" required rows="6" maxlength="5000" placeholder="Tell us what you need. For corrections, include what the figure should be and the source it comes from."></textarea>
                </div>
                <div class="alt-filter">
                <?php
                // Turnstile first, then reCAPTCHA, then the arithmetic.
                //
                // Turnstile is the right shape for a page behind a cache: the
                // widget fetches its own challenge in the browser at load time,
                // so nothing about it can be baked into stale HTML - the defect
                // the challenge route above exists to work around. It is free,
                // it sends no data to Google, and this site already sits behind
                // Cloudflare, so it introduces no new party.
                //
                // The arithmetic stays as the floor. It needs no account and no
                // key, and a contact form that is one expired credential away
                // from unreachable is worse than a slightly ruder one.
                ?>
                <?php if (defined('ALT_TURNSTILE_SITE_KEY') && ALT_TURNSTILE_SITE_KEY) : ?>
                    <label>Quick check to keep bots out</label>
                    <div class="cf-turnstile" data-sitekey="<?php echo esc_attr(ALT_TURNSTILE_SITE_KEY); ?>"></div>
                    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
                <?php elseif (defined('ALT_RECAPTCHA_SITE_KEY') && ALT_RECAPTCHA_SITE_KEY) : ?>
                    <label>Quick check to keep bots out</label>
                    <div class="g-recaptcha" data-sitekey="<?php echo esc_attr(ALT_RECAPTCHA_SITE_KEY); ?>"></div>
                    <script src="https://www.google.com/recaptcha/api.js" async defer></script>
                <?php else : ?>
                    <label for="alt-c-captcha" id="alt-c-captcha-label"
                          data-alt-question="Quick check to keep bots out: what is %A% + %B%?">Quick check to keep bots out: what is <?php echo (int) $a; ?> + <?php echo (int) $b; ?>?</label>
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
            var hints = {};
            try { hints = JSON.parse(topic.getAttribute('data-alt-hints') || '{}'); } catch (e) { hints = {}; }
            var hintEl = document.getElementById('alt-c-topic-hint');
            // 'app' is the one subject that is not about the tracker at all, so
            // the source-link row stops asking for a news report and asks for
            // the page that went wrong instead. Leaving the tracker wording up
            // is how a form tells someone they picked the wrong option.
            var sync = function () {
                var value = topic.value;
                var isTip = value === 'tip';
                var isApp = value === 'app';
                document.querySelectorAll('.alt-tip-only').forEach(function (el) { el.hidden = !isTip; });
                var show = function (sel, on) {
                    var el = document.querySelector(sel);
                    if (el) el.hidden = !on;
                };
                show('.alt-tip-note', isTip);
                show('.alt-app-note', isApp);
                show('.alt-nontip-note', !isTip && !isApp);
                var linkLabel = document.getElementById('alt-c-link-label');
                if (linkLabel) {
                    linkLabel.textContent = isApp
                        ? 'Link to the page (optional)'
                        : 'Link to the source (news report, filing, or company post)';
                }
                if (hintEl && Object.prototype.hasOwnProperty.call(hints, value)) {
                    hintEl.textContent = hints[value];
                }
            };
            topic.addEventListener('change', sync);
            sync();

            // THE CHALLENGE IS FETCHED, NOT TRUSTED FROM THE HTML.
            //
            // Everything below replaces values that were minted when this page
            // was RENDERED, which behind a shared cache can be hours or days
            // before anyone read it. The nonce, the timestamp and the
            // arithmetic token all expire; the page does not. Until this ran,
            // a visitor served a cached copy was told their message looked
            // like spam.
            //
            // Failure here is silent ON PURPOSE. If the route cannot be
            // reached, the printed values stay in place and the form behaves
            // exactly as it did before: on an uncached page they are valid,
            // and a visitor should never be shown an error about our caching.
            var form = document.querySelector('.alt-contact-form');
            if (!form || !window.fetch) return;
            var put = function (name, value) {
                var el = form.querySelector('[name="' + name + '"]');
                if (el) el.value = value;
            };
            fetch('<?php echo esc_js(esc_url_raw(rest_url('layoffs/v1/contact-challenge'))); ?>', {
                credentials: 'same-origin',
                cache: 'no-store'
            }).then(function (r) {
                return r.ok ? r.json() : null;
            }).then(function (c) {
                if (!c || !c.token) return;
                put('alt_contact_nonce', c.nonce);
                put('alt_ts', c.ts);
                put('alt_token', c.token);
                var label = document.getElementById('alt-c-captcha-label');
                if (label && typeof c.a === 'number' && typeof c.b === 'number') {
                    var tpl = label.getAttribute('data-alt-question') || '';
                    label.textContent = tpl.replace('%A%', c.a).replace('%B%', c.b);
                }
                var answer = document.getElementById('alt-c-captcha');
                // The question just changed under them; an answer to the old
                // one would fail and read as their mistake.
                if (answer) answer.value = '';
            }).catch(function () { /* printed values stand */ });
        })();
        </script>
    </div>
    <?php
    // The contact form renders its own buffer rather than going through
    // alt_template(), so it never carried the build stamp that every other
    // plugin surface emits. Without it nothing can date this page: on
    // 2026-09-12 the subject list was correct at the origin and five days
    // stale at the edge, and the freshness check had no stamp to compare.
    return alt_build_stamp_comment() . ob_get_clean();
}
add_shortcode('alt_contact', 'alt_shortcode_contact');

/**
 * Accept an address the way a person pastes it.
 *
 * esc_url_raw() on a bare "example.com/article" returns '', so before this the
 * field had to be typed with a scheme or the link was silently dropped - and
 * the input was type="url", so the browser refused to submit the form at all
 * over an OPTIONAL field. People paste what they copied, including addresses
 * their browser showed them without the scheme.
 *
 * Only http and https are ever produced. A value carrying any other scheme is
 * rejected outright rather than repaired, because "javascript:" with https
 * glued on the front is not a link, and this string ends up in an email a
 * person will click.
 */
function alt_contact_clean_url($raw) {
    $raw = trim((string) $raw);
    if ($raw === '') return '';
    if (preg_match('#^[a-zA-Z][a-zA-Z0-9+.-]*:#', $raw)) {
        if (!preg_match('#^https?://#i', $raw)) return '';
    } else {
        $raw = 'https://' . ltrim($raw, '/');
    }
    $clean = esc_url_raw($raw, array('http', 'https'));
    $host = parse_url($clean, PHP_URL_HOST);
    // A host with no dot is not an address someone pasted from the web; it is
    // usually a sentence that wandered into the wrong field.
    if (!$host || strpos($host, '.') === false) return '';
    return $clean;
}

/**
 * The arithmetic challenge, in one place, because two callers reach it: the
 * normal path and a Turnstile verification we could not reach.
 *
 * An EXPIRED token and a WRONG answer are different outcomes and must stay
 * different. "That looked like spam to us" told the owner he had failed a test
 * he had actually passed, when the truth was that the page he was reading had
 * been cached for hours and its token was long gone.
 */
function alt_contact_check_arithmetic($fail) {
    $token = preg_replace('/[^a-zA-Z0-9]/', '', (string) ($_POST['alt_token'] ?? ''));
    $expected = get_transient('alt_captcha_' . $token);
    delete_transient('alt_captcha_' . $token); // single use
    if ($expected === false) $fail('expired');
    if ((int) ($_POST['alt_captcha'] ?? -1) !== (int) $expected) $fail('spam');
}

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

    if (defined('ALT_TURNSTILE_SECRET') && ALT_TURNSTILE_SECRET) {
        $ts_resp = wp_remote_post('https://challenges.cloudflare.com/turnstile/v0/siteverify', array(
            'timeout' => 8,
            'body' => array(
                'secret'   => ALT_TURNSTILE_SECRET,
                'response' => (string) ($_POST['cf-turnstile-response'] ?? ''),
                'remoteip' => $_SERVER['REMOTE_ADDR'] ?? '',
            )));
        // THREE STATES, NOT TWO. A verifier we could not REACH has returned no
        // verdict, and treating that as spam tells an honest person they failed
        // a test that never ran. It also cannot fall back to the arithmetic:
        // when Turnstile is configured the arithmetic field is not rendered, so
        // there is nothing for the visitor to have answered, and asking for it
        // here would reject everyone.
        //
        // So an unreachable verifier lets the message through, and says so in
        // the mail. What still bounds the form in that window is everything
        // that never left this host: the honeypot, the three second minimum
        // fill time, and the three per hour per IP limit below. The trade is
        // deliberate. A contact form that silently drops real messages during
        // somebody else's outage is the worse failure, because nobody finds
        // out - not the sender, who was told they looked like spam, and not us.
        $ts_ok = null;
        if (!is_wp_error($ts_resp)) {
            $body = json_decode((string) wp_remote_retrieve_body($ts_resp), true);
            $ts_ok = !empty($body['success']);
        }
        if ($ts_ok === false) $fail('spam');
        if ($ts_ok === null) $GLOBALS['alt_contact_unverified'] = true;
    } elseif (defined('ALT_RECAPTCHA_SECRET') && ALT_RECAPTCHA_SECRET) {
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
        alt_contact_check_arithmetic($fail);
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
    $link  = alt_contact_clean_url(wp_unslash($_POST['alt_link'] ?? ''));
    $msg   = sanitize_textarea_field(wp_unslash($_POST['alt_message'] ?? ''));

    if ($name === '' || !is_email($email) || $msg === '') $fail('fields');

    $body = "Topic: $topic\nName: $name\nEmail: $email\n";
    // Said out loud, in the one place a person will read it. A message that
    // arrived while the bot check was unreachable is not a message we verified,
    // and the reader deserves to know which of the two they are holding.
    if (!empty($GLOBALS['alt_contact_unverified'])) {
        $body .= "Note: the bot check could not be reached when this was sent, so it is UNVERIFIED.\n";
    }
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
