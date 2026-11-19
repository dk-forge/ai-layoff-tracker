<?php
/**
 * The AskTheRecruiter sign-up line on the employer pages, and the phone bar.
 *
 * Owner request 2026-11-17: the employer index (/company-layoffs/) and the
 * company pages are read by people who have often just lost a job, and the
 * only route to the product was the header button, which blog-legacy-css.php
 * hides under 600px. So one plain line near the top of each, and on phones a
 * small closable bar. tests/test_atr_signup_cta.py pins the copy and the tags.
 *
 * Destination: the free match check (/resume-score). It costs nothing at
 * every free-tier dial setting, because the score is computed with no model
 * call, so "free" is true. No time is promised: the product itself says the
 * read takes up to a minute.
 *
 * Copy is a condition, never a statement about the reader or the employer.
 * nofollow on our own link, for the reason the next-step block gives.
 */
if (!defined('ABSPATH')) exit;

function alt_atr_cta_url($campaign) {
    $campaign = preg_replace('/[^a-z0-9_-]/', '', strtolower((string) $campaign));
    return add_query_arg(array(
        'utm_source'   => 'ai-layoff-tracker',
        'utm_medium'   => 'referral',
        'utm_campaign' => $campaign !== '' ? $campaign : 'directory',
    ), rtrim(alt_resume_cta_base(), '/') . '/resume-score');
}

function alt_atr_cta_line_html($campaign, $company = '') {
    $company = trim((string) $company);
    $lead = $company !== ''
        ? 'Affected by a layoff at ' . esc_html($company) . '?'
        : 'Affected by a layoff?';
    return '<aside class="alt-atr-cta" aria-label="Resume help">'
        . '<b>' . $lead . '</b> Check how your resume fits your next role. Free, no card. '
        . '<a href="' . esc_url(alt_atr_cta_url($campaign)) . '" target="_blank" rel="noopener nofollow">'
        . 'Check my resume</a></aside>';
}

/**
 * The same line for a country, state or industry page (todo#1881 item 1): the
 * lead names the place or sector the reader came for, the destination and
 * the promise stay the same, and the facet rides in utm_content.
 */
function alt_atr_cta_facet_html($dim, $display) {
    $dim = in_array($dim, array('country', 'state', 'industry'), true) ? $dim : 'country';
    $where = 'in ' . esc_html($display);
    $url = add_query_arg('utm_content', sanitize_title((string) $display), alt_atr_cta_url('facet_' . $dim));
    return '<aside class="alt-atr-cta" aria-label="Resume help">'
        . '<b>Affected by a layoff ' . $where . '?</b> Check how your resume fits your next role. Free, no card. '
        . '<a href="' . esc_url($url) . '" target="_blank" rel="noopener nofollow">'
        . 'Check my resume</a></aside>';
}

function alt_atr_cta_is_tracker_page() {
    // The flagship [alt_tracker] page too (set by alt_shortcode_tracker).
    return !empty($GLOBALS['alt_tracker_rendered'])
        || (function_exists('alt_company_index_is_request') && alt_company_index_is_request())
        || (function_exists('alt_company_directory_is_request') && alt_company_directory_is_request())
        || alt_atr_cta_is_tracker_route(isset($_SERVER['REQUEST_URI']) ? (string) $_SERVER['REQUEST_URI'] : '');
}

/**
 * Every routed tracker page (methodology, sources, press, editions, reports,
 * country/state/industry pages...), not only the dashboard and employer pages.
 * Finish line 2026-11-18 (run 44386250165): those pages had no visible sign-up
 * route under 600px, where the header button is hidden.
 */
function alt_atr_cta_is_tracker_route($uri) {
    $path = (string) parse_url((string) $uri, PHP_URL_PATH);
    return (bool) preg_match('#/(ai-layoff-tracker|company-layoffs|country-layoffs|state-layoffs|industry-layoffs|layoff)(/|$)#', $path);
}

/**
 * Phones only (the header button is visible above 600px). The bar sits in the
 * page's own flow space: body gets padding-bottom equal to the bar, so the last
 * line of content is never covered. Closing it is remembered per browser; the
 * storage call is wrapped because private windows throw.
 */
function alt_atr_cta_sticky_bar() {
    if (!alt_atr_cta_is_tracker_page()) return;
    $url = alt_atr_cta_url('sticky_bar');
    ?>
<style id="alt-atr-bar-css">
.alt-atr-cta{margin:1rem 0;padding:.7rem .9rem;border:1px solid currentColor;border-color:rgba(127,127,127,.4);border-radius:8px;line-height:1.5}
.alt-atr-cta a{font-weight:600;text-decoration:underline}
.alt-atr-bar{position:fixed;left:0;right:0;bottom:0;z-index:999;display:flex;align-items:center;gap:.5rem;padding:.5rem 16px calc(.5rem + env(safe-area-inset-bottom));background:#0f2b46;color:#fff;box-shadow:0 -2px 8px rgba(0,0,0,.2);transition:transform .2s ease}
.alt-atr-bar a{flex:1;display:flex;align-items:center;justify-content:center;min-height:44px;border-radius:6px;background:#fff;color:#0f2b46;font-weight:700;text-decoration:none}
.alt-atr-bar a:focus-visible,.alt-atr-bar button:focus-visible{outline:3px solid #ffbf47;outline-offset:2px}
.alt-atr-bar button{min-width:44px;min-height:44px;border:0;border-radius:6px;background:transparent;color:#fff;font-size:1.5rem;line-height:1;cursor:pointer}
body.alt-atr-bar-on{padding-bottom:calc(64px + env(safe-area-inset-bottom))}
.alt-atr-bar[hidden]{display:none}
body.alt-atr-bar-on #alt-roo-feedback .alt-roo-btn{bottom:calc(76px + env(safe-area-inset-bottom))}
body.alt-atr-bar-on .alt-roo-dialog{bottom:calc(132px + env(safe-area-inset-bottom))}
@media (min-width:601px){.alt-atr-bar{display:none}body.alt-atr-bar-on{padding-bottom:0}body.alt-atr-bar-on #alt-roo-feedback .alt-roo-btn{bottom:16px}body.alt-atr-bar-on .alt-roo-dialog{bottom:72px}}
@media (prefers-reduced-motion:reduce){.alt-atr-bar{transition:none}}
@media print{.alt-atr-bar{display:none}}
</style>
<div class="alt-atr-bar" id="alt-atr-bar" role="region" aria-label="Resume help" hidden>
    <a href="<?php echo esc_url($url); ?>" target="_blank" rel="noopener nofollow">Adapt my resume, free</a>
    <button type="button" aria-label="Close" id="alt-atr-bar-close">&times;</button>
</div>
    <?php
}
// Priority 5: before WordPress prints footer scripts at 20, so the bar exists when atr-bar.js runs.
add_action('wp_footer', 'alt_atr_cta_sticky_bar', 5);

/** The bar's show/close logic is a file, not an inline body (test_shortcode_scripts_are_enqueued.py). */
function alt_atr_cta_enqueue() {
    if (!alt_atr_cta_is_tracker_page()) return;
    wp_enqueue_script('alt-atr-bar', ALT_PLUGIN_URL . 'assets/atr-bar.js', array(), ALT_VERSION, true);
}
add_action('wp_enqueue_scripts', 'alt_atr_cta_enqueue');
