<?php
/**
 * A SMALLER COOKIE BANNER ON PHONES (todo#1881 item 3, review B7). Measured on
 * 2026-11-19 at 375x812: the Complianz banner was 422px tall, covering 52% of
 * the first screen of every /blog page, with the headline figure and sign-up
 * line underneath it. This keeps every choice and every word, and changes only
 * spacing and type size: Accept and Deny stay side by side at the SAME size
 * and weight (refusing must be as easy as accepting, GDPR/ePrivacy), each at
 * least 44px tall, with "View preferences" below them.
 *
 * Printed for every front-end /blog page (both trackers and the posts share
 * this WordPress and this banner). Pure CSS, no change to consent behaviour.
 */
if (!defined('ABSPATH')) exit;

function alt_cookie_banner_compact_css() {
    if (is_admin()) return;
    echo "<style id=\"alt-cookie-compact\">@media (max-width:600px){"
        . ".cmplz-cookiebanner{padding:10px 12px!important;row-gap:6px!important;max-height:60vh;overflow:auto}"
        . ".cmplz-cookiebanner .cmplz-header{margin:0!important}"
        . ".cmplz-cookiebanner .cmplz-message{font-size:13px!important;line-height:1.4!important;margin:0!important}"
        . ".cmplz-cookiebanner .cmplz-divider{display:none!important}"
        . ".cmplz-cookiebanner .cmplz-buttons{display:flex!important;flex-direction:row!important;flex-wrap:wrap!important;gap:6px!important;width:100%!important}"
        . ".cmplz-cookiebanner .cmplz-buttons .cmplz-btn{flex:1 1 40%!important;width:auto!important;min-width:0!important;height:auto!important;min-height:44px!important;margin:0!important;padding:6px 8px!important;font-size:14px!important}"
        . ".cmplz-cookiebanner .cmplz-buttons .cmplz-view-preferences,.cmplz-cookiebanner .cmplz-buttons .cmplz-save-preferences{flex-basis:100%!important}"
        . ".cmplz-cookiebanner .cmplz-links{margin:0!important}"
        . "}</style>\n";
}
add_action('wp_head', 'alt_cookie_banner_compact_css', 99);
