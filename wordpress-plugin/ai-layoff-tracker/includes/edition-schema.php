<?php
/**
 * NewsArticle markup for archived digest editions (owner ask 2026-09-29:
 * "SEO and dates"). Each permanent edition page tells search engines and
 * Google News when it was published and when it last changed.
 *
 * datePublished = the edition's published_at. dateModified = the newest
 * correction date (alt_edition_add_correction), else datePublished. Nothing is
 * printed for an unknown or unpublished edition.
 * Guard: railway/tests/test_edition_news_schema.py.
 */
if (!defined('ABSPATH')) exit;

/** PURE. Edition row + URL in, NewsArticle array out ([] when not publishable). */
function alt_edition_news_jsonld($row, $url, $label, $publisher, $home) {
    if (!is_array($row) || empty($row['published_at'])) return array();
    $ts = strtotime((string) $row['published_at'] . ' UTC');
    if (!$ts) return array();
    $mod = $ts;
    foreach ((array) ($row['corrections'] ?? array()) as $c) {
        $t = is_array($c) ? strtotime((string) ($c['at'] ?? '') . ' 00:00:00 UTC') : false;
        if ($t && $t > $mod) $mod = $t;
    }
    $kind = (($row['freq'] ?? '') === 'monthly') ? 'Monthly' : 'Weekly';
    $headline = 'AI Layoff Tracker ' . $kind . ' Digest: ' . trim((string) $label);
    if (strlen($headline) > 110) $headline = rtrim(substr($headline, 0, 109)) . "\u{2026}";
    return array(
        '@context'            => 'https://schema.org',
        '@type'               => 'NewsArticle',
        'headline'            => $headline,
        'datePublished'       => gmdate('Y-m-d\TH:i:s\Z', $ts),
        'dateModified'        => gmdate('Y-m-d\TH:i:s\Z', $mod),
        'mainEntityOfPage'    => (string) $url,
        'isAccessibleForFree' => true,
        'author'              => array('@type' => 'Organization', 'name' => (string) $publisher, 'url' => (string) $home),
        'publisher'           => array('@type' => 'Organization', 'name' => (string) $publisher, 'url' => (string) $home),
    );
}

add_action('wp_head', function () {
    if (!function_exists('alt_edition_current') || !function_exists('alt_edition_url')) return;
    $row = alt_edition_current();
    if (!$row) return;
    $ld = alt_edition_news_jsonld($row, alt_edition_url($row['freq'], $row['slug']),
        function_exists('alt_edition_label') ? alt_edition_label($row) : (string) $row['slug'],
        'AskTheRecruiter.com', home_url('/'));
    if (!$ld) return;
    echo '<script type="application/ld+json">' . wp_json_encode($ld, JSON_UNESCAPED_SLASHES | JSON_HEX_TAG) . "</script>\n";
}, 20);
