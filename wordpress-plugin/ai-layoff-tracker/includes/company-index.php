<?php
/**
 * THE EMPLOYER BROWSE INDEX: a crawlable, readable path to the company pages.
 *
 * WHY THIS FILE EXISTS. Measured on the live site 2026-08-19: the company
 * sitemap offers 7,500 indexable employer pages. Crawling all 103 facet pages
 * and collecting every /company-layoffs/ link they carry found 3,575 distinct
 * employer pages linked, of which only 1,539 are pages the sitemap offers. So
 * 5,961 of the 7,500 indexable employer pages - 79.5% - were reachable from a
 * sitemap and from nothing else on the site. The tracker page itself, which is
 * where readers actually land, linked to ZERO of them.
 *
 * A sitemap says "this exists". A link says "this matters", and it is also the
 * only one of the two a READER can follow. The facet pages already fixed this
 * for their own dimension, and the comment there names the reason: sibling
 * navigation makes "a connected mesh rather than a hundred pages reachable
 * only from a sitemap". The employer set never got the same treatment because
 * it is two orders of magnitude larger and does not render whole.
 *
 * WHAT THIS IS NOT. It is not an attempt to get more pages indexed, and it
 * adds no page whose purpose is to exist. The 7,500 destination pages are
 * already published and already indexable; this only gives them a path. The
 * letter pages themselves are `noindex, follow` for exactly the reason the
 * weekly report pulses are (report-seo.php) and the sub-floor company pages
 * are (company-directory.php): a pure navigation list carries nothing of its
 * own, and 27 of them in the index would be mass-generated thin pages. `follow`
 * is the entire point - the links out of them are why they exist.
 *
 * The hub at /company-layoffs/ IS indexable, because it carries the published
 * coverage numbers and is a real overview of what the employer index reaches.
 *
 * ROUTING. The existing employer route is `^company-layoffs/([^/]+)/?$`, which
 * cannot match a bare `/company-layoffs/` (the segment needs a character) and
 * cannot match `/company-layoffs/browse/a/` (the segment forbids a slash), so
 * these two rules collide with nothing. `browse` can never be a company slug
 * for the same reason: it would need to be a one-segment path.
 */
if (!defined('ABSPATH')) exit;

/** Every bucket the index offers, in the order it renders them. */
function alt_company_index_buckets() {
    $out = array('0-9');
    foreach (range('a', 'z') as $ch) $out[] = $ch;
    return $out;
}

/**
 * The bucket a slug belongs to. Slugs come from sanitize_title(), so the first
 * character is already lowercase alphanumeric; anything that is not a-z is
 * gathered under one numeric bucket rather than minting a page per digit.
 */
function alt_company_index_bucket($slug) {
    $ch = strtolower(substr((string) $slug, 0, 1));
    return ($ch >= 'a' && $ch <= 'z') ? $ch : '0-9';
}

function alt_company_index_url($bucket = '') {
    $base = home_url('/company-layoffs/');
    return $bucket === '' ? $base : $base . 'browse/' . rawurlencode((string) $bucket) . '/';
}

/**
 * The canonical-slug subquery shared by both readers below.
 *
 * Deliberately the SAME shape as alt_company_directory_indexable_urls(): the
 * same `approved` filter, the same supported-events floor and the same
 * ORDER BY inside GROUP_CONCAT, so the slug this index links to and the slug
 * the sitemap offers can never be two different URLs for one employer. The
 * display name rides along on a 0x1f separator because a company name may
 * legitimately contain a comma and a slug never can.
 */
function alt_company_index_canonical_sql() {
    $directory = alt_company_directory_table();
    $supported = alt_company_directory_supported_events_sql();
    $floor = (int) alt_company_directory_indexable_floor();
    return "SELECT SUBSTRING_INDEX(GROUP_CONCAT(d.slug ORDER BY CHAR_LENGTH(d.slug) ASC, d.id ASC), ',', 1) AS canon_slug,
                   SUBSTRING_INDEX(GROUP_CONCAT(d.display_name ORDER BY CHAR_LENGTH(d.slug) ASC, d.id ASC SEPARATOR 0x1f), 0x1f, 1) AS canon_name
              FROM $directory d
              INNER JOIN ($supported) s ON s.company_key = d.company_key AND s.supported >= $floor
             WHERE d.review_status = 'approved'
             GROUP BY d.company_key";
}

/**
 * How many indexable employer pages sit in each bucket.
 *
 * SIX HOURS AND A STATIC MEMO, matching alt_facet_counts() rather than the
 * 15-minute sitemap cache, and for a reason worth stating: the tracker page
 * reads this to draw its A-Z strip, so unlike the sitemap this is on the
 * hottest path on the site. The query underneath is a GROUP BY across the
 * layoffs, events and source-report tables, which is not something to run at
 * the edge of a shared host every fifteen minutes. The number it returns
 * changes only when an employer crosses the two-entry floor, so a six-hour
 * reading is never meaningfully behind, and alt_data_ver in the key still
 * retires it the moment the data version moves.
 */
function alt_company_index_counts() {
    global $wpdb;
    static $memo = null;
    if ($memo !== null) return $memo;
    $cache_key = 'alt_company_idx_counts_' . md5((string) get_option('alt_data_ver', 1));
    $cached = get_transient($cache_key);
    if (is_array($cached)) { $memo = $cached; return $memo; }
    $inner = alt_company_index_canonical_sql();
    $rows = $wpdb->get_results(
        "SELECT LEFT(t.canon_slug, 1) AS ch, COUNT(*) AS n FROM ($inner) t GROUP BY ch", ARRAY_A) ?: array();
    $out = array_fill_keys(alt_company_index_buckets(), 0);
    foreach ($rows as $row) {
        $out[alt_company_index_bucket($row['ch'])] += (int) $row['n'];
    }
    set_transient($cache_key, $out, 6 * HOUR_IN_SECONDS);
    $memo = $out;
    return $out;
}

/** The employers in one bucket, as {slug, name}, alphabetically by slug. */
function alt_company_index_entries($bucket) {
    global $wpdb;
    if (!in_array($bucket, alt_company_index_buckets(), true)) return array();
    $cache_key = 'alt_company_idx_' . md5((string) get_option('alt_data_ver', 1) . '|' . $bucket);
    $cached = get_transient($cache_key);
    if (is_array($cached)) return $cached;
    $inner = alt_company_index_canonical_sql();
    // A bucket is one LIKE for a letter, and "everything that is not a letter"
    // for the numeric one. REGEXP rather than 26 NOT LIKEs, and anchored so a
    // slug is judged on its first character only.
    // WHERE and not HAVING: canon_slug is a real column of the derived table t,
    // so this filters before sorting rather than after grouping.
    $where = ($bucket === '0-9') ? "canon_slug NOT REGEXP '^[a-z]'" : 'canon_slug LIKE %s';
    $sql = "SELECT canon_slug, canon_name FROM ($inner) t WHERE $where ORDER BY canon_slug ASC";
    $rows = ($bucket === '0-9')
        ? $wpdb->get_results($sql, ARRAY_A)
        : $wpdb->get_results($wpdb->prepare($sql, $wpdb->esc_like($bucket) . '%'), ARRAY_A);
    $out = array();
    foreach ((array) $rows as $row) {
        $slug = (string) $row['canon_slug'];
        if ($slug === '') continue;
        $out[] = array('slug' => $slug, 'name' => (string) $row['canon_name'], 'url' => alt_company_directory_url($slug));
    }
    set_transient($cache_key, $out, HOUR_IN_SECONDS);
    return $out;
}

/* ---------------------------------------------------------------- routing */

function alt_company_index_register_routes() {
    add_rewrite_rule('^company-layoffs/?$', 'index.php?alt_company_index=hub', 'top');
    add_rewrite_rule('^company-layoffs/browse/([^/]+)/?$', 'index.php?alt_company_index=browse&alt_company_index_bucket=$matches[1]', 'top');
}
add_action('init', 'alt_company_index_register_routes', 1);

add_filter('query_vars', function ($vars) {
    $vars[] = 'alt_company_index';
    $vars[] = 'alt_company_index_bucket';
    return $vars;
});

// FTP deploys never fire an activation hook, so a brand-new rewrite rule would
// 404 until something else happened to flush. Flush once per version, guarded
// by its own option (the shape report-seo.php and company-directory.php use).
add_action('init', function () {
    if (get_option('alt_company_index_rewrite_version') === ALT_VERSION) return;
    flush_rewrite_rules(false);
    update_option('alt_company_index_rewrite_version', ALT_VERSION, false);
}, 99);

/** 'hub', a valid bucket string, or '' when this is not an index request. */
function alt_company_index_current() {
    $kind = (string) get_query_var('alt_company_index');
    if ($kind === 'hub') return 'hub';
    if ($kind !== 'browse') return '';
    $bucket = strtolower(trim((string) get_query_var('alt_company_index_bucket')));
    return in_array($bucket, alt_company_index_buckets(), true) ? $bucket : '';
}

function alt_company_index_is_request() { return alt_company_index_current() !== ''; }

/**
 * An unknown bucket is a 404, not an empty page: `/company-layoffs/browse/zz/`
 * must not mint a valid-looking navigation page from a typo or a crawler guess,
 * which is the rule alt_report_period_identity() applies to `?period=2031`.
 */
function alt_company_index_prepare_request() {
    if ((string) get_query_var('alt_company_index') === '') return;
    if (!alt_company_index_is_request()) {
        global $wp_query;
        $wp_query->set_404();
        status_header(404);
        if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
        nocache_headers();
        return;
    }
    // Same ten minutes the rendered company pages carry, and for the same
    // reason: these are crawlable URLs on a shared host, and the data behind
    // them is already held in a 15-minute transient.
    if (!headers_sent()) header('Cache-Control: public, max-age=600');
}
add_action('template_redirect', 'alt_company_index_prepare_request', 1);

add_filter('template_include', function ($template) {
    if (!alt_company_index_is_request()) return $template;
    $custom = ALT_PLUGIN_DIR . 'templates/page-company-index.php';
    return file_exists($custom) ? $custom : $template;
});

/* -------------------------------------------------------------------- SEO */

function alt_company_index_title_text() {
    $cur = alt_company_index_current();
    if ($cur === 'hub') return 'Layoffs by employer: browse every company record';
    return 'Employers starting with ' . strtoupper($cur) . ': layoff records';
}

function alt_company_index_description_text() {
    $cur = alt_company_index_current();
    $counts = alt_company_index_counts();
    if ($cur === 'hub') {
        $total = array_sum($counts);
        return 'Browse ' . number_format($total) . ' employers with source-linked layoff records, A to Z. '
             . 'Every entry links to the filing, WARN notice or named report behind it.';
    }
    $n = (int) ($counts[$cur] ?? 0);
    return number_format($n) . ' employer' . ($n === 1 ? '' : 's') . ' starting with ' . strtoupper($cur)
         . ', each with source-linked layoff records on this site.';
}

/**
 * Only the hub is offered to the index. A letter page is navigation and
 * nothing else, so it is `noindex, follow` on the same reasoning that keeps
 * weekly report pulses and sub-floor company pages out: the links are the
 * value, the page is not.
 */
function alt_company_index_is_indexable() { return alt_company_index_current() === 'hub'; }

add_filter('wp_robots', function ($robots) {
    if (alt_company_index_is_request() && !alt_company_index_is_indexable()) $robots['noindex'] = true;
    return $robots;
});
add_filter('wpseo_robots', function ($robots) {
    if (!alt_company_index_is_request()) return $robots;
    return alt_company_index_is_indexable() ? $robots : 'noindex,follow';
});
add_filter('rank_math/frontend/robots', function ($robots) {
    if (!alt_company_index_is_request()) return $robots;
    return alt_company_index_is_indexable() ? $robots : array('noindex', 'follow');
});

function alt_company_index_filter_canonical($canonical) {
    if (!alt_company_index_is_request()) return $canonical;
    return alt_company_index_url(alt_company_index_current() === 'hub' ? '' : alt_company_index_current());
}
add_filter('wpseo_canonical', 'alt_company_index_filter_canonical');
add_filter('rank_math/frontend/canonical', 'alt_company_index_filter_canonical');

function alt_company_index_filter_title($title) {
    return alt_company_index_is_request() ? alt_company_index_title_text() : $title;
}
add_filter('wpseo_title', 'alt_company_index_filter_title', 5);
add_filter('rank_math/frontend/title', 'alt_company_index_filter_title', 5);
add_filter('document_title_parts', function ($parts) {
    if (alt_company_index_is_request()) $parts['title'] = alt_company_index_title_text();
    return $parts;
}, 5);

function alt_company_index_filter_description($desc) {
    return alt_company_index_is_request() ? alt_company_index_description_text() : $desc;
}
add_filter('wpseo_metadesc', 'alt_company_index_filter_description', 5);
add_filter('rank_math/frontend/description', 'alt_company_index_filter_description', 5);

/** Fallback for an install with no SEO plugin (the shape the sibling files use). */
add_action('wp_head', function () {
    if (!alt_company_index_is_request()) return;
    if (defined('WPSEO_VERSION') || class_exists('RankMath')) return;
    echo '<meta name="description" content="' . esc_attr(alt_company_index_description_text()) . '" />' . "\n";
    if (alt_company_index_is_indexable()) {
        echo '<link rel="canonical" href="' . esc_url(alt_company_index_filter_canonical('')) . '" />' . "\n";
    } else {
        echo '<meta name="robots" content="noindex, follow" />' . "\n";
    }
}, 1);

/**
 * The hub joins the company sitemap. The letter pages deliberately do not:
 * a sitemap entry for a noindex page is a contradiction, and the crawl path
 * they provide runs through the hub's own links.
 */
add_filter('alt_company_sitemap_urls', function ($urls) {
    array_unshift($urls, alt_company_index_url());
    return $urls;
});
