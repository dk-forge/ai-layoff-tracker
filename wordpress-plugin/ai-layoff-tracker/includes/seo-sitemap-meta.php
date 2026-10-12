<?php
/**
 * Shared SEO plumbing for the plugin's own sitemaps and meta (SEO audit
 * 2026-10-12, items 2, 5 and 10).
 *
 *  - <lastmod> on every self-served sitemap. 7,700 company pages and ~180
 *    facet/report/edition URLs carried no lastmod, so Google had no way to
 *    tell which of them changed; the tracker's freshness was invisible.
 *    lastmod is the date of the latest entry behind the URL, never "now".
 *  - One cap for generated meta descriptions (155 chars, cut at a word).
 *  - One publisher Organization for Article/NewsArticle markup. The name is
 *    the brand, "Ask The Recruiter", never a person.
 *
 * Guard: railway/tests/test_seo_sitemap_meta.py.
 */
if (!defined('ABSPATH')) exit;

/** The brand every Article/NewsArticle node is published and authored by. */
function alt_publisher_name() { return 'Ask The Recruiter'; }

/** PURE apart from home_url/site icon. Organization node with a logo. */
function alt_publisher_org() {
    $logo = function_exists('get_site_icon_url') ? (string) get_site_icon_url(512) : '';
    if ($logo === '' && function_exists('alt_social_card_url')) $logo = alt_social_card_url();
    $org = array('@type' => 'Organization', 'name' => alt_publisher_name(), 'url' => 'https://asktherecruiter.com/');
    if ($logo !== '') $org['logo'] = array('@type' => 'ImageObject', 'url' => $logo);
    return $org;
}

/**
 * PURE. A generated meta description capped at $max characters, cut at the
 * last word boundary and closed with an ellipsis. Short text is returned as is.
 */
function alt_seo_cap_description($text, $max = 155) {
    $text = trim(preg_replace('/\s+/u', ' ', (string) $text));
    if ($text === '' || mb_strlen($text, 'UTF-8') <= $max) return $text;
    $cut = mb_substr($text, 0, $max - 1, 'UTF-8');
    $sp = mb_strrpos($cut, ' ', 0, 'UTF-8');
    if ($sp !== false && $sp > (int) ($max * 0.6)) $cut = mb_substr($cut, 0, $sp, 'UTF-8');
    return rtrim($cut, " ,;:.-\u{2013}\u{2014}") . "\u{2026}";
}

/** PURE. A Y-m-d (or datetime) string normalised to a W3C date, or ''. */
function alt_sitemap_lastmod_value($date) {
    $date = trim((string) $date);
    if (!preg_match('/^(\d{4}-\d{2}-\d{2})/', $date, $m)) return '';
    if ($m[1] < '2000-01-01') return '';
    $today = gmdate('Y-m-d');
    return $m[1] > $today ? $today : $m[1];
}

/** PURE. One sitemap <url> line, with <lastmod> only when the date is known. */
function alt_sitemap_url_line($loc, $lastmod = '') {
    $lm = alt_sitemap_lastmod_value($lastmod);
    return '  <url><loc>' . esc_url($loc) . '</loc>'
        . ($lm !== '' ? '<lastmod>' . $lm . '</lastmod>' : '')
        . '</url>' . "\n";
}

/** PURE. The newest of a list of dates ('' when none is valid). */
function alt_sitemap_max_date($dates) {
    $best = '';
    foreach ((array) $dates as $d) {
        $d = alt_sitemap_lastmod_value($d);
        if ($d > $best) $best = $d;
    }
    return $best;
}

/**
 * SQL for "when this entry last changed": its last edit, else the date it was
 * announced, else its layoff date. Never later than today (a future effective
 * date is not a change to the page).
 */
function alt_sitemap_entry_date_sql($alias = 'l') {
    $a = preg_replace('/[^a-z_]/', '', (string) $alias);
    return "LEAST(CURDATE(), GREATEST(COALESCE(DATE($a.updated_at), '1970-01-01'),"
         . " COALESCE($a.announcement_date, '1970-01-01'), COALESCE($a.layoff_date, '1970-01-01')))";
}

/**
 * value => latest entry date, for one grouping column. Cached against
 * alt_data_ver like the sitemaps that read it, so it never outlives a write.
 */
function alt_sitemap_lastmod_by($column) {
    static $memo = array();
    $allowed = array('company_key', 'country', 'state', 'industry', 'month');
    if (!in_array($column, $allowed, true)) return array();
    if (isset($memo[$column])) return $memo[$column];
    global $wpdb;
    $key = 'alt_sm_lastmod_' . $column . '_' . md5((string) get_option('alt_data_ver', 1));
    $cached = get_transient($key);
    if (is_array($cached)) return $memo[$column] = $cached;
    $table = alt_db_table();
    $expr = alt_sitemap_entry_date_sql('l');
    $group = ($column === 'month') ? "DATE_FORMAT(l.layoff_date, '%Y-%m')" : "l.$column";
    $rows = $wpdb->get_results(
        "SELECT $group AS k, MAX($expr) AS d FROM $table l
          WHERE l.superset_of = 0 AND $group IS NOT NULL AND $group <> ''
          GROUP BY k", ARRAY_A) ?: array();
    $out = array();
    foreach ($rows as $r) {
        $d = alt_sitemap_lastmod_value($r['d'] ?? '');
        if ($d !== '') $out[(string) $r['k']] = $d;
    }
    set_transient($key, $out, 6 * HOUR_IN_SECONDS);
    return $memo[$column] = $out;
}
