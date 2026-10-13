<?php
/**
 * Article JSON-LD for the indexable dated reports (month, quarter, year), so the
 * monthly roundup is read as an article built on the tracker's dataset. The
 * headline repeats the page title (alt_report_seo_title) because the report
 * covers every verified job cut, not only AI-attributed ones. Week and invalid periods are noindex and get nothing.
 *
 * Dates are honest: datePublished is the first day the period covers (the page
 * exists and fills from then), dateModified is the latest entry date inside the
 * period, read from the same per-month lastmods the report sitemap uses.
 */

/** PURE apart from home_url. The node, or null for a kind we do not mark up. */
function alt_report_article_node($kind, $slug, $label, $url, $modified) {
    if ($kind === 'month')        $start = $slug . '-01';
    elseif ($kind === 'quarter')  $start = substr($slug, 0, 4) . '-' . sprintf('%02d', ((int) substr($slug, 6, 1) - 1) * 3 + 1) . '-01';
    elseif ($kind === 'year')     $start = $slug . '-01-01';
    else return null;
    $org = array('@type' => 'Organization', 'name' => 'AskTheRecruiter', 'url' => home_url('/'));
    $node = array(
        '@context'         => 'https://schema.org',
        '@type'            => 'Article',
        'headline'         => $label . ($kind === 'year' ? ' Layoffs in Review' : ' Layoffs Report') . ': Verified Job Cuts',
        'datePublished'    => $start,
        'mainEntityOfPage' => $url,
        'url'              => $url,
        'author'           => $org,
        'publisher'        => $org,
        'isBasedOn'        => array('@id' => home_url('/ai-layoff-tracker/') . '#dataset'),
        'license'          => 'https://creativecommons.org/licenses/by/4.0/',
    );
    if (is_string($modified) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $modified)) $node['dateModified'] = $modified;
    return $node;
}

function alt_report_article_schema() {
    if (!function_exists('alt_report_is_report_page') || !alt_report_is_report_page()) return;
    $id = alt_report_period_identity();
    $url = alt_report_canonical_url();
    $mod = '';
    if (function_exists('alt_sitemap_lastmod_by') && function_exists('alt_report_url_lastmod')) {
        $mod = (string) alt_report_url_lastmod($url, alt_sitemap_lastmod_by('month'));
    }
    $node = alt_report_article_node($id['kind'], $id['slug'], alt_report_period_label($id), $url, $mod);
    if (!$node) return;
    echo '<script type="application/ld+json">' . wp_json_encode($node, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) . "</script>\n";
}
add_action('wp_head', 'alt_report_article_schema', 22);
