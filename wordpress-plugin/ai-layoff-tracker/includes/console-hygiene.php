<?php
/**
 * Two console errors on every /blog page (todo#1881 item 8, review B2 + B3).
 *
 * 1. WORDFENCE'S ATTACK-DATA SYNC TAG. Wordfence prints
 *    <script src="//…/blog/?wordfence_syncAttackData=<microtime>"> into the
 *    head when it has WAF data to push. The page cache then freezes that tag
 *    into every cached page, the URL answers 500 text/html, the browser
 *    refuses it on MIME type, and the sync never runs from a cached page
 *    anyway. Measured on 40 of 42 tracker loads on 2026-11-18. Wordfence's
 *    own cron still sends the data; only the front-end tag goes.
 *
 * 2. "Failed to resolve module specifier @wordpress/interactivity". The
 *    header's navigation block enqueues its view module while the body
 *    renders. On the plugin's virtual routes (company, country, state,
 *    industry and digest pages, every TIT sub-page) that happens after the
 *    import map has already printed, so the map is missing and the module
 *    cannot load. Enqueueing the same module in wp_enqueue_scripts puts its
 *    dependency in the import map. Enqueueing is idempotent, so pages where
 *    it already worked are unchanged.
 *
 * One file for the whole /blog install: TIT runs on the same WordPress.
 */
if (!defined('ABSPATH')) exit;

function alt_drop_wordfence_sync_tag() {
    if (!class_exists('wordfence')) return;
    // Wordfence registers it as the STRING 'wordfence::addSyncAttackDataAjax'
    // (wordfenceClass.php, veryFirstAction, when more than 10 loopback syncs
    // have failed), and remove_action must name it the same way.
    foreach (array('wp_head', 'login_head') as $hook) {
        remove_action($hook, 'wordfence::addSyncAttackDataAjax');
    }
}
add_action('wp_loaded', 'alt_drop_wordfence_sync_tag', 99);

function alt_enqueue_navigation_view_early() {
    if (is_admin() || !function_exists('wp_enqueue_script_module')) return;
    wp_enqueue_script_module('@wordpress/block-library/navigation/view');
}
add_action('wp_enqueue_scripts', 'alt_enqueue_navigation_view_early', 1);
