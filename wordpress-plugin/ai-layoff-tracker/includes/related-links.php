<?php
/**
 * "Related" link row on every tracker shortcode page (2.20.255, #446 item 4).
 *
 * ONE map, here. Owner ruling 2026-10-14: Dashboard -> Methodology, Data
 * Sources, Tracker; Registry -> Tracker; Tracker -> Dashboard, Registry,
 * Methodology; every page -> Data Sources (the Sources page cannot link to
 * itself). Printed server-side from alt_template(), so crawlers and no-JS
 * readers see it. Link text only, no intro or FAQ copy (the owner writes that).
 */
if (!defined('ABSPATH')) exit;

/** Target key => array(label, path under the blog home). */
function alt_related_links_targets() {
    return array(
        'tracker'     => array('Tracker', 'ai-layoff-tracker/'),
        'dashboard'   => array('Dashboard', 'ai-layoffs-dashboard/'),
        'registry'    => array('US WARN Registry', 'ai-layoff-tracker/us-warn-registry/'),
        'methodology' => array('Methodology', 'ai-layoff-tracker/methodology/'),
        'sources'     => array('Data Sources', 'ai-layoff-tracker/sources/'),
        'report'      => array('Monthly Report', 'ai-layoff-tracker/report/'),
        'quarterly'   => array('State of Layoffs', 'ai-layoff-tracker/state-of-layoffs/'),
        'press'       => array('Press', 'ai-layoff-tracker/press/'),
        'health'      => array('Tracker Health', 'ai-layoff-tracker/ai-tracker-health/'),
    );
}

/** Template file => ordered target keys. Data Sources is added last where missing. */
function alt_related_links_map() {
    return array(
        'page-dashboard.php'          => array('methodology', 'sources', 'tracker'),
        'page-us-registry.php'        => array('tracker'),
        'page-tracker.php'            => array('dashboard', 'registry', 'methodology'),
        'page-methodology.php'        => array('tracker', 'dashboard'),
        'page-sources.php'            => array('tracker', 'methodology', 'health'),
        'page-ai-quotes.php'          => array('tracker', 'methodology'),
        'page-report.php'             => array('tracker', 'dashboard', 'quarterly'),
        'page-quarterly-report.php'   => array('tracker', 'report'),
        'page-press.php'              => array('tracker', 'report'),
        'page-publisher.php'          => array('tracker', 'press'),
        'page-health.php'             => array('tracker', 'methodology'),
        'page-ai-tracker.php'         => array('tracker', 'dashboard', 'methodology'),
    );
}

/** Pure: the row for a template, '' when unmapped. */
function alt_related_links_html($file, $base) {
    $map = alt_related_links_map();
    if (!isset($map[$file])) return '';
    $keys = $map[$file];
    if ($file !== 'page-sources.php' && !in_array('sources', $keys, true)) $keys[] = 'sources';
    $targets = alt_related_links_targets();
    $base = rtrim((string) $base, '/') . '/';
    $items = array();
    foreach (array_unique($keys) as $k) {
        if (!isset($targets[$k])) continue;
        $items[] = '<li><a href="' . esc_url($base . $targets[$k][1]) . '">' . esc_html($targets[$k][0]) . '</a></li>';
    }
    if (!$items) return '';
    return '<nav class="alt-related" aria-label="Related pages" style="margin:24px 0 8px">'
         . '<p style="font-weight:700;margin:0 0 6px">Related</p>'
         . '<ul style="list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 16px">'
         . implode('', $items) . '</ul></nav>';
}

/** Pure: inside the last </main> when there is one, else appended. */
function alt_related_insert($out, $row) {
    $at = strrpos($out, '</main>');
    return $at === false ? $out . $row : substr($out, 0, $at) . $row . substr($out, $at);
}

/** alt_template() hook. No once-flag: every render carries it. */
function alt_related_links_template($file, $out) {
    $row = alt_related_links_html($file, home_url('/'));
    return $row === '' ? $out : alt_related_insert($out, $row);
}
