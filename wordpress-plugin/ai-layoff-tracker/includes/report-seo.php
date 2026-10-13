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
        // Same rule as the month: a quarter that has not begun is not a report
        // (?period=2026-Q4 in September must not get a self-canonical).
        $y = (int) $m[1]; $q = (int) $m[2];
        $now_q = (int) ceil(((int) gmdate('n')) / 3);
        $future = ($y > $now_y) || ($y === $now_y && $q > $now_q);
        return ($y >= 2015 && !$future)
            ? array('kind' => 'quarter', 'slug' => $raw)
            : array('kind' => 'invalid', 'slug' => '');
    }
    if (preg_match('/^(\d{4})-W(0[1-9]|[1-4]\d|5[0-3])$/', $raw, $m)) {
        // ISO week-year/week, compared against the current ISO week.
        $y = (int) $m[1]; $w = (int) $m[2];
        $now_iy = (int) gmdate('o'); $now_w = (int) gmdate('W');
        $future = ($y > $now_iy) || ($y === $now_iy && $w > $now_w);
        return ($y >= 2015 && !$future)
            ? array('kind' => 'week', 'slug' => $raw)
            : array('kind' => 'invalid', 'slug' => '');
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
        case 'archive':
        case 'year':
        case 'quarter':
        case 'month':   return alt_report_clean_url($id['kind'], $id['slug']);
        default:        return $base;   // current, week, invalid
    }
}

/**
 * PURE apart from home_url. The clean path for an indexable report:
 * /report/archive/, /report/2023/, /report/2023-Q1/, /report/2023-01/.
 *
 * SEO audit 2026-10-12 #4: the sitemap listed ?period= and ?view= URLs, which
 * search engines crawl and index poorly. The old query URLs 301 here
 * (alt_report_redirect_query_url) and the canonical names this path.
 */
function alt_report_clean_url($kind, $slug = '') {
    $base = home_url('/ai-layoff-tracker/report/');
    if ($kind === 'archive') return $base . 'archive/';
    if (!alt_report_clean_slug_ok((string) $slug)) return $base;
    return $base . $slug . '/';
}

/** PURE. A slug the clean-path route accepts: YYYY, YYYY-QN or YYYY-MM. */
function alt_report_clean_slug_ok($slug) {
    return (bool) preg_match('/^\d{4}(?:-Q[1-4]|-(?:0[1-9]|1[0-2]))?$/', (string) $slug);
}

/**
 * The clean paths route to the same WordPress page and hand the period to the
 * template through $_GET, which is what the template and every SEO filter in
 * this file already read. One source of truth, no second parser.
 */
add_action('init', function () {
    add_rewrite_rule('^ai-layoff-tracker/report/(archive|\d{4}(?:-Q[1-4]|-(?:0[1-9]|1[0-2]))?)/?$',
        'index.php?pagename=ai-layoff-tracker/report&alt_rpath=$matches[1]', 'top');
}, 1);
add_filter('query_vars', function ($vars) { $vars[] = 'alt_rpath'; return $vars; });
add_action('parse_request', function ($wp) {
    $p = isset($wp->query_vars['alt_rpath']) ? (string) $wp->query_vars['alt_rpath'] : '';
    if ($p === '') return;
    if ($p === 'archive') { $_GET['view'] = 'archive'; unset($_GET['period']); }
    elseif (alt_report_clean_slug_ok($p)) { $_GET['period'] = $p; unset($_GET['view']); }
});
// WordPress would otherwise "correct" /report/2023/ back to the page's permalink.
add_filter('redirect_canonical', function ($redirect) {
    return ((string) get_query_var('alt_rpath') !== '') ? false : $redirect;
});

/**
 * PURE. Where a query-string report URL should 301 to, or '' to leave it.
 * Only the bare ?period= / ?view=archive forms move; anything with another
 * key (?scope=us, utm tags) stays put and canonicalises to the clean path.
 */
function alt_report_query_redirect_target($get, $kind, $slug) {
    if (!is_array($get) || !$get) return '';
    $keys = array_keys($get);
    sort($keys);
    if ($keys !== array('period') && $keys !== array('view')) return '';
    if (!in_array($kind, array('archive', 'year', 'quarter', 'month'), true)) return '';
    return alt_report_clean_url($kind, $slug);
}

function alt_report_redirect_query_url() {
    if ((string) get_query_var('alt_rpath') !== '' || !alt_report_is_report_page()) return;
    $id = alt_report_period_identity();
    $to = alt_report_query_redirect_target($_GET, $id['kind'], $id['slug']);
    if ($to === '') return;
    wp_safe_redirect($to, 301);
    exit;
}
add_action('template_redirect', 'alt_report_redirect_query_url', 1);

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
        return 'Every AskTheRecruiter job cuts report by month, quarter and year: '
             . 'citable pages built from verified layoffs, each figure linked to its source.';
    }
    if ($label === '') return $desc;
    return alt_seo_cap_description('Verified job cuts in ' . $label . ' by company, industry, '
         . 'country and US state, plus AI-attributed layoffs. Every figure links to its source.');
}
add_filter('rank_math/frontend/description', 'alt_report_seo_description', 5);
add_filter('wpseo_metadesc', 'alt_report_seo_description', 5);

/**
 * Every report URL worth indexing: the archive hub, each year, each COMPLETE
 * quarter and month. Weeks are excluded on purpose (see the file header).
 * 2023 is the floor because that is where the archive UI itself starts.
 */
function alt_report_indexable_urls() {
    $urls = array(alt_report_clean_url('archive'));
    $now_y = (int) gmdate('Y');
    $now_m = (int) gmdate('n');
    for ($y = 2023; $y <= $now_y; $y++) {
        $urls[] = alt_report_clean_url('year', (string) $y);
        $m_hi = ($y === $now_y) ? $now_m : 12;
        for ($q = 1; $q <= 4; $q++) {
            // Only quarters that have fully elapsed; a part-quarter report would
            // be resubmitted with different numbers every day.
            if ($y === $now_y && ($q * 3) > $m_hi) break;
            $urls[] = alt_report_clean_url('quarter', sprintf('%04d-Q%d', $y, $q));
        }
        for ($m = 1; $m <= $m_hi; $m++) {
            $urls[] = alt_report_clean_url('month', sprintf('%04d-%02d', $y, $m));
        }
    }
    return $urls;
}

/**
 * PURE. A report URL's lastmod: the latest entry date among the months it
 * covers ($months is 'YYYY-MM' => date). The archive hub covers every month.
 */
function alt_report_url_lastmod($url, $months) {
    if (!preg_match('#/report/([^/]+)/$#', (string) $url, $m)) return '';
    $slug = $m[1];
    $pick = array();
    foreach ((array) $months as $ym => $d) {
        $ym = (string) $ym;
        if ($slug === 'archive' || $ym === $slug || substr($ym, 0, 4) === $slug) { $pick[] = $d; continue; }
        if (preg_match('/^(\d{4})-Q([1-4])$/', $slug, $q) && substr($ym, 0, 4) === $q[1]) {
            $mo = (int) substr($ym, 5, 2);
            if ((int) ceil($mo / 3) === (int) $q[2]) $pick[] = $d;
        }
    }
    return alt_sitemap_max_date($pick);
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
    alt_request_rewrite_flush();
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
    $months = alt_sitemap_lastmod_by('month');
    foreach (alt_report_indexable_urls() as $url) {
        echo alt_sitemap_url_line($url, alt_report_url_lastmod($url, $months));
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

/**
 * Visible H1 for dated reports. The theme's post-title block printed the page
 * name "Monthly Job Cuts Report" as the H1 on every archive, year, quarter,
 * month and week URL while each <title> named its own period (2026-10-13). The
 * H1 is now the head of that period's title ("Q1 2026 Layoffs Report"), only
 * for the queried report page itself, so menus and other posts are untouched.
 */
function alt_report_heading_text() {
    $title = alt_report_seo_title('');
    if ($title === '') return '';
    $cut = strpos($title, ': ');
    return $cut === false ? $title : substr($title, 0, $cut);
}
function alt_report_filter_post_title($title, $post_id = 0) {
    if (is_admin() || !$post_id || (int) $post_id !== (int) get_queried_object_id()) return $title;
    if (!alt_report_is_report_page()) return $title;
    $h = alt_report_heading_text();
    return $h === '' ? $title : esc_html($h);
}
add_filter('the_title', 'alt_report_filter_post_title', 10, 2);
