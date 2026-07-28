<?php
if (!defined('ABSPATH')) exit;

/**
 * SEO identity for the dated report pages.
 *
 * Every period report renders from ONE WordPress page via ?period=..., so the
 * SEO plugin canonicalised all of them to the bare /report/ URL: it told Google
 * that ~60 distinct, individually citable reports were duplicates of a single
 * page, and the only report URL in any sitemap was that base page. Net effect
 * before this file (audit 2026-07-28): the whole report archive was invisible
 * to search, including the evergreen "<Month> <Year> layoffs report" pages that
 * are the natural landing point for a reporter searching a past period.
 *
 * What this file does:
 *   - gives each month / quarter / year report a canonical URL of ITS OWN;
 *   - keeps weekly pulses out of the index (52 thin pages a year is exactly the
 *     mass-generated-doorway pattern that costs a domain its standing);
 *   - points the ?scope=us variant at its worldwide twin, so the same period
 *     never competes with itself;
 *   - publishes /layoff-reports-sitemap.xml and appends it to the active SEO
 *     plugin's sitemap index.
 *
 * The dual wpseo_/rank_math_ hooks mirror the company-directory file: whichever
 * SEO plugin is active, one of them is the live one and the other is inert.
 */

/** True only on the page that renders the [alt_report] shortcode. */
function alt_report_is_report_page() {
    if (!is_page()) return false;
    $id = get_queried_object_id();
    if (!$id) return false;
    // Compare permalinks rather than asking has_shortcode(): a shortcode that
    // arrives via a block, pattern or template part is invisible to a
    // post_content scan, and the page would silently lose its canonical.
    return trailingslashit(get_permalink($id))
        === trailingslashit(home_url('/ai-layoff-tracker/report/'));
}

/**
 * Classify the requested period.
 *
 * Returns array(kind, slug) where kind is one of:
 *   'archive'  the report index          -> indexable
 *   'year' | 'quarter' | 'month'         -> indexable, self-canonical
 *   'week'                               -> NOINDEX (thin, 52 a year)
 *   'current'                            -> the bare /report/ URL
 *   'invalid'                            -> NOINDEX (junk or future period)
 */
function alt_report_period_identity() {
    $view = isset($_GET['view']) ? sanitize_text_field(wp_unslash($_GET['view'])) : '';
    if ($view === 'archive') return array('kind' => 'archive', 'slug' => '');

    $raw = isset($_GET['period']) ? sanitize_text_field(wp_unslash($_GET['period'])) : '';
    if ($raw === '') return array('kind' => 'current', 'slug' => '');

    $now_y = (int) gmdate('Y');
    // Nothing beyond the current year can be a real report, and a crawler that
    // finds ?period=2031 must not mint an indexable empty page from it.
    if (preg_match('/^(\d{4})$/', $raw, $m)) {
        $y = (int) $m[1];
        return ($y >= 2015 && $y <= $now_y)
            ? array('kind' => 'year', 'slug' => $raw)
            : array('kind' => 'invalid', 'slug' => '');
    }
    if (preg_match('/^(\d{4})-(0[1-9]|1[0-2])$/', $raw, $m)) {
        $y = (int) $m[1]; $mo = (int) $m[2];
        $future = ($y > $now_y) || ($y === $now_y && $mo > (int) gmdate('n'));
        return ($y >= 2015 && !$future)
            ? array('kind' => 'month', 'slug' => $raw)
            : array('kind' => 'invalid', 'slug' => '');
    }
    if (preg_match('/^(\d{4})-Q([1-4])$/', $raw, $m)) {
        $y = (int) $m[1];
        return ($y >= 2015 && $y <= $now_y)
            ? array('kind' => 'quarter', 'slug' => $raw)
            : array('kind' => 'invalid', 'slug' => '');
    }
    if (preg_match('/^(\d{4})-W(0[1-9]|[1-4]\d|5[0-3])$/', $raw)) {
        return array('kind' => 'week', 'slug' => $raw);
    }
    return array('kind' => 'invalid', 'slug' => '');
}

/** The canonical URL for the current report request (worldwide scope always). */
function alt_report_canonical_url() {
    $base = home_url('/ai-layoff-tracker/report/');
    $id = alt_report_period_identity();
    // ?scope=us is deliberately dropped: the US cut of a period is a filtered
    // view of the same report, so it consolidates into the worldwide URL rather
    // than competing with it for the same query.
    switch ($id['kind']) {
        case 'archive': return add_query_arg(array('view' => 'archive'), $base);
        case 'year':
        case 'quarter':
        case 'month':   return add_query_arg(array('period' => $id['slug']), $base);
        default:        return $base;   // current, week, invalid
    }
}

function alt_report_filter_canonical($canonical) {
    if (!alt_report_is_report_page()) return $canonical;
    return alt_report_canonical_url();
}
add_filter('wpseo_canonical', 'alt_report_filter_canonical');
add_filter('rank_math/frontend/canonical', 'alt_report_filter_canonical');

function alt_report_filter_robots($robots) {
    if (!alt_report_is_report_page()) return $robots;
    $kind = alt_report_period_identity()['kind'];
    if ($kind === 'week' || $kind === 'invalid') {
        return array('noindex' => 'noindex', 'follow' => 'follow');
    }
    return $robots;
}
add_filter('rank_math/frontend/robots', 'alt_report_filter_robots');
// Yoast passes a plain string here, not Rank Math's keyed array.
add_filter('wpseo_robots', function ($robots) {
    if (!alt_report_is_report_page()) return $robots;
    $kind = alt_report_period_identity()['kind'];
    return ($kind === 'week' || $kind === 'invalid') ? 'noindex, follow' : $robots;
});

/**
 * Fallback for installs with no SEO plugin: emit the canonical (and a robots
 * meta when the period must stay out of the index) ourselves. Guarded so we
 * never print a second canonical alongside an SEO plugin's own.
 */
function alt_report_head_fallback() {
    if (!alt_report_is_report_page()) return;
    if (defined('WPSEO_VERSION') || class_exists('RankMath')) return;
    echo '<link rel="canonical" href="' . esc_url(alt_report_canonical_url()) . '" />' . "\n";
    $kind = alt_report_period_identity()['kind'];
    if ($kind === 'week' || $kind === 'invalid') {
        echo '<meta name="robots" content="noindex, follow" />' . "\n";
    }
}
add_action('wp_head', 'alt_report_head_fallback', 1);

/** Human label for a period slug: "June 2026", "Q2 2026", "2025". */
function alt_report_period_label($id) {
    static $months = array(1=>'January','February','March','April','May','June',
        'July','August','September','October','November','December');
    $slug = $id['slug'];
    switch ($id['kind']) {
        case 'year':    return $slug;
        case 'quarter': return substr($slug, 5) . ' ' . substr($slug, 0, 4);
        case 'month':   return $months[(int) substr($slug, 5, 2)] . ' ' . substr($slug, 0, 4);
        case 'week':    return 'Week ' . substr($slug, 6) . ', ' . substr($slug, 0, 4);
    }
    return '';
}

/**
 * Per-period title and description.
 *
 * Every dated report used to serve the SAME title, "Monthly Job Cuts Report" —
 * wrong on the quarterly and yearly ones, and identical across ~60 URLs, which
 * is the fastest way to have a whole archive filed as duplicates. Making those
 * URLs indexable without fixing this would have made the problem bigger, not
 * smaller.
 */
function alt_report_seo_title($title) {
    if (!alt_report_is_report_page()) return $title;
    $id = alt_report_period_identity();
    $us = (isset($_GET['scope']) && $_GET['scope'] === 'us') ? 'US ' : '';
    $label = alt_report_period_label($id);
    switch ($id['kind']) {
        case 'archive':
            return 'Layoff Reports Archive: Every Month, Quarter and Year';
        case 'year':
            return $label . ' ' . $us . 'Layoffs in Review: Verified Job Cuts';
        case 'quarter':
        case 'month':
            return $label . ' ' . $us . 'Layoffs Report: Verified Job Cuts';
        case 'week':
            return $label . ' ' . $us . 'Layoffs: Weekly Pulse';
    }
    return $title;
}
add_filter('rank_math/frontend/title', 'alt_report_seo_title', 5);
add_filter('wpseo_title', 'alt_report_seo_title', 5);

function alt_report_seo_description($desc) {
    if (!alt_report_is_report_page()) return $desc;
    $id = alt_report_period_identity();
    $label = alt_report_period_label($id);
    if ($id['kind'] === 'archive') {
        return 'Every AskTheRecruiter job cuts report, by month, quarter and year. '
             . 'Each one is a standalone, citable page built from verified layoffs '
             . 'with a primary source behind every number.';
    }
    if ($label === '') return $desc;
    return 'Verified job cuts recorded in ' . $label . ': totals by company, industry, '
         . 'country and US state, plus the layoffs employers themselves attributed to AI. '
         . 'Every figure links to the filing, WARN notice or named report behind it.';
}
add_filter('rank_math/frontend/description', 'alt_report_seo_description', 5);
add_filter('wpseo_metadesc', 'alt_report_seo_description', 5);

/**
 * Every report URL worth indexing: the archive hub, each year, each COMPLETE
 * quarter and month. Weeks are excluded on purpose (see the file header).
 * 2023 is the floor because that is where the archive UI itself starts.
 */
function alt_report_indexable_urls() {
    $base = home_url('/ai-layoff-tracker/report/');
    $urls = array(add_query_arg(array('view' => 'archive'), $base));
    $now_y = (int) gmdate('Y');
    $now_m = (int) gmdate('n');
    for ($y = 2023; $y <= $now_y; $y++) {
        $urls[] = add_query_arg(array('period' => (string) $y), $base);
        $m_hi = ($y === $now_y) ? $now_m : 12;
        for ($q = 1; $q <= 4; $q++) {
            // Only quarters that have fully elapsed; a part-quarter report would
            // be resubmitted with different numbers every day.
            if ($y === $now_y && ($q * 3) > $m_hi) break;
            $urls[] = add_query_arg(array('period' => sprintf('%04d-Q%d', $y, $q)), $base);
        }
        for ($m = 1; $m <= $m_hi; $m++) {
            $urls[] = add_query_arg(array('period' => sprintf('%04d-%02d', $y, $m)), $base);
        }
    }
    return $urls;
}

function alt_report_sitemap_url() { return home_url('/layoff-reports-sitemap.xml'); }
add_action('init', function () {
    add_rewrite_rule('^layoff-reports-sitemap\.xml$', 'index.php?alt_report_sitemap=1', 'top');
}, 1);
add_filter('query_vars', function ($vars) { $vars[] = 'alt_report_sitemap'; return $vars; });

// FTP deploys never fire an activation hook, so a brand-new rewrite rule would
// 404 until something else happened to flush. Flush once per version, guarded
// by its own option so this does not depend on another module doing it.
add_action('init', function () {
    if (get_option('alt_report_rewrite_version') === ALT_VERSION) return;
    flush_rewrite_rules(false);
    update_option('alt_report_rewrite_version', ALT_VERSION, false);
}, 99);

function alt_report_render_sitemap() {
    if ((string) get_query_var('alt_report_sitemap') === '') return;
    if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
    status_header(200);
    header('Content-Type: application/xml; charset=UTF-8');
    header('X-Robots-Tag: noindex, follow');
    echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
    echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
    foreach (alt_report_indexable_urls() as $url) {
        echo '  <url><loc>' . esc_url($url) . '</loc></url>' . "\n";
    }
    echo '</urlset>';
    exit;
}
add_action('template_redirect', 'alt_report_render_sitemap', 0);

function alt_report_sitemap_index_entry($xml) {
    return $xml . '<sitemap><loc>' . esc_url(alt_report_sitemap_url()) . '</loc></sitemap>' . "\n";
}
add_filter('wpseo_sitemap_index', 'alt_report_sitemap_index_entry');
add_filter('rank_math/sitemap/index', 'alt_report_sitemap_index_entry');
