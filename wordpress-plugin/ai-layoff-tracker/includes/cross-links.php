<?php
/**
 * LINKS TO THE SIBLING HIRING TRACKER (todo#1881 item 5). The owner runs both
 * trackers on this WordPress; a reader on "Amazon layoffs" or "Germany
 * layoffs" should be one click from the same company or place in the Talent
 * Intelligence Tracker, and back.
 *
 * NAVIGATION ONLY, NO PAIRED FIGURES. TIT's includes/cross_tracker.php
 * measured on 2026-07-30 that pairing the two datasets by name publishes wrong
 * claims (US Bank vs Piraeus Bank, Tesla vs a supplier), so this prints a link
 * and the target's own name, never "X cut N while hiring M".
 *
 * ONLY TO PAGES THAT EXIST. data/cross-links.json is the intersection of the
 * two live sitemaps, so no link is a 404. Ambiguous slugs are left out there.
 */
if (!defined('ABSPATH')) exit;

const ALT_TIT_BASE = '/talent-intelligence-tracker/';

function alt_cross_links_data() {
    static $data = null;
    if ($data !== null) return $data;
    $data = array('companies' => array(), 'countries' => array(), 'industries' => array());
    $path = ALT_PLUGIN_DIR . 'data/cross-links.json';
    if (is_readable($path)) {
        $raw = json_decode((string) file_get_contents($path), true);
        if (is_array($raw)) $data = array_merge($data, $raw);
    }
    $data['companies'] = array_flip((array) $data['companies']);
    $data['countries'] = array_flip((array) $data['countries']);
    return $data;
}

/** The sibling's pages for one ALT company slug or facet: list of [url, label]. */
function alt_cross_links_targets($kind, $slug, $display) {
    $d = alt_cross_links_data();
    $slug = sanitize_title((string) $slug);
    $base = home_url(ALT_TIT_BASE);
    if ($kind === 'company' && isset($d['companies'][$slug])) {
        return array(array($base . 'company/' . $slug . '/', (string) $display));
    }
    if ($kind === 'country' && isset($d['countries'][$slug])) {
        return array(array($base . 'country/' . $slug . '/', (string) $display));
    }
    if ($kind === 'industry' && !empty($d['industries'][$slug])) {
        $out = array();
        foreach ((array) $d['industries'][$slug] as $pair) {
            $out[] = array($base . 'industry/' . $pair[0] . '/', (string) $pair[1]);
        }
        return $out;
    }
    return array();
}

function alt_cross_links_html($kind, $slug, $display) {
    $targets = alt_cross_links_targets($kind, $slug, $display);
    if (!$targets) return '';
    $links = array();
    foreach ($targets as $t) {
        $links[] = '<a href="' . esc_url($t[0]) . '">' . esc_html($t[1]) . ' in the hiring tracker</a>';
    }
    return '<p class="alt-cross-links"><b>Who is hiring?</b> ' . implode(' · ', $links) . '</p>';
}
