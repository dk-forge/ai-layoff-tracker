<?php
/**
 * THE SITE HEADER'S SIGN-UP LINK CARRIES THIS TRACKER'S SOURCE (todo#1881
 * item 2, review B8). The header CTA is a theme menu link tagged
 * utm_source=blog&utm_medium=nav&utm_campaign=header-cta on every /blog page,
 * so a sign-up that started on a tracker page was counted as "blog". On this
 * tracker's pages the source becomes ai-layoff-tracker (the scheme #691 set
 * for every other ALT CTA); medium and campaign stay, so the slot is still
 * readable. Other blog pages are untouched.
 */
if (!defined('ABSPATH')) exit;

function alt_header_cta_retag($html) {
    if (strpos($html, 'utm_source=blog') === false) return $html;
    return preg_replace(
        '#(href="https://asktherecruiter\.com/[^"]*?[?&](?:amp;|\#038;)?)utm_source=blog((?:&|&amp;|&\#038;)utm_medium=nav)#',
        '$1utm_source=ai-layoff-tracker$2',
        $html
    );
}

/**
 * Two paths, one rewrite: theme-rendered pages (the hub) go through this
 * filter; the virtual routes retag their buffered header in
 * alt_render_page_header(). The regex only touches an asktherecruiter.com
 * link tagged utm_source=blog&utm_medium=nav, so block type does not matter.
 */
function alt_header_cta_filter($block_content, $block) {
    // Cheap test first: this runs for every block on every page.
    if (strpos($block_content, 'utm_source=blog') === false) return $block_content;
    static $ours = null;
    if ($ours === null) $ours = function_exists('alt_page_needs_assets') && alt_page_needs_assets();
    return $ours ? alt_header_cta_retag($block_content) : $block_content;
}
add_filter('render_block', 'alt_header_cta_filter', 20, 2);
