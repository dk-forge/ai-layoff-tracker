<?php
/**
 * Reach: feed discovery, GA4 funnel events and share buttons (audit 2026-11-10).
 *
 *  - Advertises the layoffs RSS feed (/feed/layoffs/, includes/rss.php) in
 *    <head> on every front-end page, and as a visible link on the tracker.
 *  - Loads assets/reach.js (deferred, no config) which sends five GA4 events
 *    through the site's existing Google tag. No personal data: see reach.js.
 *  - alt_share_buttons_html(): native Web Share with copy, LinkedIn and X
 *    fallbacks for company and facet (state) pages. No third-party script.
 *
 * GUARDED include in the main file (is_readable). Tests: railway/tests/test_reach.py.
 */

if (!defined('ABSPATH')) exit;

function alt_reach_feed_url() {
    return home_url('/feed/layoffs/');
}

function alt_reach_feed_link() {
    if (is_admin()) return;
    echo '<link rel="alternate" type="application/rss+xml" title="'
        . esc_attr__('AI Layoff Tracker: latest layoffs', 'ai-layoff-tracker')
        . '" href="' . esc_url(alt_reach_feed_url()) . '" />' . "\n";
}
add_action('wp_head', 'alt_reach_feed_link', 3);

function alt_reach_feed_visible_link() {
    return '<p class="alt-feed-link"><a href="' . esc_url(alt_reach_feed_url())
        . '" type="application/rss+xml">RSS feed of new layoff entries</a></p>';
}

function alt_reach_enqueue() {
    if (is_admin()) return;
    $ver = defined('ALT_VERSION') ? ALT_VERSION : '0';
    wp_enqueue_script('alt-reach', ALT_PLUGIN_URL . 'assets/reach.js', array(), $ver,
        array('in_footer' => true, 'strategy' => 'defer'));
}
add_action('wp_enqueue_scripts', 'alt_reach_enqueue');

/**
 * Share row. $title is the prefilled share text (the page heading); $url
 * defaults to the current page URL without its query string. The LinkedIn and
 * X links work without JavaScript; reach.js adds native share and copy.
 */
function alt_share_buttons_html($title, $url = '') {
    if ($url === '' && !empty($_SERVER['HTTP_HOST']) && isset($_SERVER['REQUEST_URI'])) {
        $path = strtok((string) wp_unslash($_SERVER['REQUEST_URI']), '?');
        $url = (is_ssl() ? 'https://' : 'http://') . sanitize_text_field(wp_unslash($_SERVER['HTTP_HOST'])) . $path;
    }
    $url = esc_url_raw($url);
    $attrs = ' data-alt-share data-alt-share-title="' . esc_attr($title) . '"';
    if ($url !== '') $attrs .= ' data-alt-share-url="' . esc_url($url) . '"';
    $li = 'https://www.linkedin.com/sharing/share-offsite/?url=' . rawurlencode($url);
    $x = 'https://x.com/intent/post?url=' . rawurlencode($url) . '&text=' . rawurlencode($title);
    return '<div class="alt-share" role="group" aria-label="Share this page"' . $attrs . '>'
        . '<button type="button" class="alt-btn alt-btn-sm" data-alt-share-kind="native" hidden>Share</button>'
        . '<button type="button" class="alt-btn alt-btn-sm" data-alt-share-kind="copy">Copy link</button>'
        . '<a class="alt-btn alt-btn-sm" data-alt-share-kind="linkedin" href="' . esc_url($li) . '" target="_blank" rel="noopener nofollow">LinkedIn</a>'
        . '<a class="alt-btn alt-btn-sm" data-alt-share-kind="x" href="' . esc_url($x) . '" target="_blank" rel="noopener nofollow">X</a>'
        . '<span class="alt-share-status" data-alt-share-status role="status" aria-live="polite"></span>'
        . '</div>';
}
