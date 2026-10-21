<?php
/**
 * ROO, THE FLOATING FEEDBACK WIDGET, ON EVERY /blog PAGE (owner ruling 2026-10-21).
 *
 * The ruling is recorded in asktherecruiter-sandbox docs/DECISIONS.md "Roo
 * feedback on every surface". Roo is AskTheRecruiter's mascot; on the blog it
 * opens a 1-5 star form whose entry goes to the SAME pipeline as the app's
 * feedback: POST /api/feedback/site on asktherecruiter.com (the same origin as
 * this install, so no CORS is involved), stored as a support ticket and emailed
 * to the owner, tagged product=blog with the page path. Spam defence is the
 * app's own: a honeypot plus Cloudflare Turnstile with the app's PUBLIC site key
 * (no secret lives here; the backend holds the secret). Turnstile allows by
 * hostname, and the blog shares asktherecruiter.com with the app.
 *
 * WHO SEES IT is decided in the browser by assets/roo-feedback.js: everyone
 * until 2027-02-01, then a sticky 50% from a random id kept in localStorage
 * (never sent anywhere). That rule is a mirror of the sandbox helper; this file
 * only puts the assets and the config on the page.
 *
 * CONFIG RIDES A data- ATTRIBUTE, NEVER AN INLINE SCRIPT. Autoptimize sweeps
 * inline config objects (the localize-script kind) into a bundle that loads after the file
 * that needs them, so the script would return on its first line and nothing
 * would error (talent-intelligence-tracker CLAUDE.md, gotcha 10). The assets
 * directory is already in this plugin's Autoptimize exclude.
 *
 * Nothing is stored by WordPress: no table, no option, no request handler.
 */

if (!defined('ABSPATH')) {
    exit;
}

/** The app's public Turnstile site key (the one sign-in uses). Public by design. */
const ALT_ROO_TURNSTILE_SITE_KEY = '0x4AAAAAAFNr5EblnHCy1YGq';

function alt_roo_feedback_config() {
    return array(
        'endpoint' => '/api/feedback/site',
        'product'  => 'blog',
        'siteKey'  => ALT_ROO_TURNSTILE_SITE_KEY,
    );
}

function alt_roo_feedback_enqueue() {
    if (is_admin()) {
        return;
    }
    $ver = defined('ALT_VERSION') ? ALT_VERSION : '0';
    wp_enqueue_style('alt-roo-feedback', ALT_PLUGIN_URL . 'assets/roo-feedback.css', array(), $ver);
    wp_enqueue_script('alt-roo-feedback', ALT_PLUGIN_URL . 'assets/roo-feedback.js', array(), $ver, true);
}
add_action('wp_enqueue_scripts', 'alt_roo_feedback_enqueue');

function alt_roo_feedback_root() {
    if (is_admin()) {
        return;
    }
    echo '<div id="alt-roo-feedback" data-alt-roo="'
        . esc_attr(wp_json_encode(alt_roo_feedback_config()))
        . '"></div>';
}
add_action('wp_footer', 'alt_roo_feedback_root', 5);
