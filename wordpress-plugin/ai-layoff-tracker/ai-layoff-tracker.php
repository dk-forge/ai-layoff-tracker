<?php
/**
 * Plugin Name: AI Layoff Tracker
 * Description: Tracks verified AI-related and general layoffs from SEC filings and credible news sources.
 * Version: 2.20.87
 * Author: AskTheRecruiter
 */

if (!defined('ABSPATH')) exit;

define('ALT_VERSION', '2.20.87');
define('ALT_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('ALT_PLUGIN_URL', plugin_dir_url(__FILE__));

// The build stamp (which BYTES rendered this page). GUARDED for the same reason
// the generated WARN partial below is: this file is NEW, so on the deploy that
// introduces it this main file can land BEFORE it does, and a hard require of a
// not-yet-uploaded file fatals the whole plugin on every request until it
// arrives (2.19.20). Its absence must degrade to "no stamp", which reads as
// UNKNOWN downstream, and never to a white screen.
$alt_build_stamp_file = ALT_PLUGIN_DIR . 'includes/build-stamp.php';
if (is_readable($alt_build_stamp_file)) {
    require_once $alt_build_stamp_file;
}
if (!function_exists('alt_build_stamp')) {
    function alt_build_stamp() { return ''; }
}
if (!function_exists('alt_build_stamp_comment')) {
    function alt_build_stamp_comment() { return ''; }
}

// Load includes
require_once ALT_PLUGIN_DIR . 'includes/cpt.php';
require_once ALT_PLUGIN_DIR . 'includes/db.php';
require_once ALT_PLUGIN_DIR . 'includes/api.php';
require_once ALT_PLUGIN_DIR . 'includes/company-directory.php';
require_once ALT_PLUGIN_DIR . 'includes/facet-pages.php';
require_once ALT_PLUGIN_DIR . 'includes/report-seo.php';
require_once ALT_PLUGIN_DIR . 'includes/shortcodes.php';
require_once ALT_PLUGIN_DIR . 'includes/export.php';
require_once ALT_PLUGIN_DIR . 'includes/rss.php';
require_once ALT_PLUGIN_DIR . 'includes/contact.php';
require_once ALT_PLUGIN_DIR . 'includes/htaccess.php';
require_once ALT_PLUGIN_DIR . 'includes/subscribe.php';
require_once ALT_PLUGIN_DIR . 'includes/digest-api.php';
require_once ALT_PLUGIN_DIR . 'includes/nav-submenu.php';
// Where the signup renders beyond the two tracker pages (blog posts, company
// profiles, the facet pages, entry permalinks). GUARDED with is_readable for
// the reason spelled out below: this file is NEW, so the deploy that
// introduces it can land this main file first. Its absence must degrade to
// "the signup is on the tracker pages only", which is exactly where it was
// yesterday, and never to a white screen. It declares no function anything
// else calls, so there is no stub accessor to leave behind.
$alt_subscribe_placements = ALT_PLUGIN_DIR . 'includes/subscribe-placements.php';
if (is_readable($alt_subscribe_placements)) {
    require_once $alt_subscribe_placements;
}
// The blog's reading surface (single posts only). GUARDED with is_readable for
// the same reason build-stamp.php and the WARN partial are: this file is NEW,
// so on the deploy that introduces it this main file can land BEFORE it does,
// and a hard require of a not-yet-uploaded include fatals the ENTIRE plugin on
// every request until it arrives (2.19.20). Its absence must degrade to
// "articles keep the old type", never to a white screen. Nothing outside the
// file calls into it - it wires itself to wp_enqueue_scripts - so there is no
// stub accessor to declare here.
$alt_blog_typography = ALT_PLUGIN_DIR . 'includes/blog-typography.php';
if (is_readable($alt_blog_typography)) {
    require_once $alt_blog_typography;
}
// The site CSS rescued out of a plugin masquerading as Hello Dolly, which
// WordPress would overwrite on the next update to the real Hello Dolly, taking
// the blog card grid, the article typography and the mobile fixes with it. Same
// is_readable guard as the file above and for the same reason.
//
// LOAD ORDER IS LOAD-BEARING HERE. It attaches to `wp-block-library` at
// priority 99 exactly as the original did, because blog-reading.css above is
// enqueued at priority 20 as its own later sheet and OVERRIDES this. Print this
// any later and the two-column heading defect returns. See the file's own
// header and docs/LEGACY-hello-dolly-css.md.
$alt_blog_legacy_css = ALT_PLUGIN_DIR . 'includes/blog-legacy-css.php';
if (is_readable($alt_blog_legacy_css)) {
    require_once $alt_blog_legacy_css;
}
// The applause control on single blog posts. GUARDED with is_readable for the
// same reason as the two files above: this file is NEW, so the deploy that
// introduces it can land this main file first, and a hard require of a
// not-yet-uploaded include fatals the ENTIRE plugin on every request until it
// arrives (2.19.20). Its absence must degrade to "articles carry no applause
// control", which is where they were yesterday, and never to a white screen. It
// wires itself to the_content, rest_api_init and wp_enqueue_scripts, so nothing
// outside it calls in and there is no stub accessor to leave behind.
$alt_blog_claps = ALT_PLUGIN_DIR . 'includes/blog-claps.php';
if (is_readable($alt_blog_claps)) {
    require_once $alt_blog_claps;
}
// Generated map of official state WARN list pages (source: railway/sources/warn.py).
// GUARDED: FTP deploys upload files one at a time, so this main plugin file can
// land BEFORE the generated partial does (the mid-upload race the iron rules
// warn about). A hard `require` of a not-yet-uploaded file fatals the ENTIRE
// plugin on every request until the partial arrives (WP recovery-mode email,
// 2.19.20). Include it only if present, and always define the accessor as a
// stub fallback so no caller ever hits an undefined function — WARN rows simply
// omit the state-list link until the real map lands on the next request/deploy.
$alt_warn_urls_partial = ALT_PLUGIN_DIR . 'templates/partials/warn-state-urls.php';
if (is_readable($alt_warn_urls_partial)) {
    require_once $alt_warn_urls_partial;
}
if (!function_exists('alt_state_warn_list_url')) {
    function alt_state_warn_list_url($state) { return ''; }
}
if (!function_exists('alt_state_warn_urls')) {
    function alt_state_warn_urls() { return array(); }
}

/**
 * Schema.org Dataset markup so search + answer engines (Google AI Overviews,
 * ChatGPT, Perplexity) can cite the dataset WITH attribution. Shared by the
 * tracker, press and report pages.
 */
function alt_dataset_jsonld() {
    $now = gmdate('Y-m-d');
    $org = array('@type' => 'Organization', 'name' => 'AskTheRecruiter', 'url' => home_url('/'));
    return array(
        '@context' => 'https://schema.org', '@type' => 'Dataset',
        'name' => 'AI Layoff Tracker', 'alternateName' => 'AskTheRecruiter AI Layoff Tracker',
        'description' => 'A continuously updated, source-linked database of verified job cuts worldwide, flagging the layoffs companies attribute to AI or automation. Every figure links to a primary document: an SEC filing, a state WARN notice, or a named news report.',
        'url' => home_url('/ai-layoff-tracker/'),
        'keywords' => array('layoffs', 'AI layoffs', 'job cuts', 'tech layoffs', 'WARN notices', 'workforce reduction', 'AI job losses', 'layoff tracker', '2026 layoffs'),
        'license' => 'https://creativecommons.org/licenses/by/4.0/', 'isAccessibleForFree' => true,
        'creator' => $org, 'publisher' => $org,
        'temporalCoverage' => (function_exists('alt_live_numbers') ? alt_live_numbers()['start'] : '2015') . '-01-01/' . $now, 'dateModified' => $now,
        'measurementTechnique' => 'Primary-source verification: SEC EDGAR filings, official state WARN notices, EU restructuring records, and named news reports from an allowlist of reviewed outlets.',
        'variableMeasured' => array(
            array('@type' => 'PropertyValue', 'name' => 'Verified job cuts', 'description' => 'Layoffs with a primary source document behind each figure.'),
            array('@type' => 'PropertyValue', 'name' => 'AI-attributed job cuts', 'description' => 'Layoffs the employer named AI or automation as a cause, with a supporting quote on file.'),
            array('@type' => 'PropertyValue', 'name' => 'Announced job cuts', 'description' => 'Company plans at announcement stage, in a separate labeled tier.'),
        ),
        'distribution' => array(
            array('@type' => 'DataDownload', 'encodingFormat' => 'application/json', 'contentUrl' => rest_url('layoffs/v1/query')),
            array('@type' => 'DataDownload', 'encodingFormat' => 'text/csv', 'contentUrl' => admin_url('admin-post.php?action=alt_export_csv')),
        ),
    );
}
function alt_output_jsonld($blocks) {
    foreach ((array) $blocks as $b) {
        echo '<script type="application/ld+json">' . wp_json_encode($b, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";
    }
}

/**
 * The US states with no usable public WARN register, and WHY. These stay dark on
 * the layoff map; we instead show their official BLS unemployment rate (a clearly
 * separate metric) so the map is complete and the gap is explained on click.
 */
function alt_no_register_states() {
    return array(
        'AR' => 'Arkansas treats WARN filings as confidential employer records under its FOIA exemption, so there is no public list to import.',
        'WY' => 'Wyoming tracks filings internally and does not host a public, centralized WARN register.',
        'NH' => 'New Hampshire handles WARN filings as internal business-compliance records, with no usable public feed.',
        'OK' => 'Oklahoma publishes WARN notices through a portal, but with no affected-employee counts, so they cannot become countable rows.',
    );
}

/**
 * Official monthly state unemployment rate (BLS LAUS, seasonally adjusted) for the
 * no-register states — a SEPARATE metric from our verified layoff counts, shown
 * only to give the dark states an authoritative number and a source link. One
 * keyless BLS request (6 series), cached ~2 weeks. Empty on failure (the map then
 * shows the reason + BLS link without a number).
 */
function alt_state_unemployment() {
    $cached = get_transient('alt_state_unemp');
    if (is_array($cached)) return $cached;
    // FIPS-coded BLS LAUS unemployment-rate series -> state code.
    $series = array(
        'LASST050000000000003' => 'AR', 'LASST560000000000003' => 'WY',
        'LASST330000000000003' => 'NH',
        'LASST400000000000003' => 'OK',
    );
    $y = (int) gmdate('Y');
    $resp = wp_remote_post('https://api.bls.gov/publicAPI/v1/timeseries/data/', array(
        'timeout' => 20,
        'headers' => array('Content-Type' => 'application/json'),
        'body' => wp_json_encode(array('seriesid' => array_keys($series),
            'startyear' => (string) ($y - 1), 'endyear' => (string) $y)),
    ));
    $out = array();
    if (!is_wp_error($resp)) {
        $data = json_decode(wp_remote_retrieve_body($resp), true);
        if (isset($data['Results']['series']) && is_array($data['Results']['series'])) {
            foreach ($data['Results']['series'] as $s) {
                $code = isset($series[$s['seriesID']]) ? $series[$s['seriesID']] : '';
                if (!$code || empty($s['data'][0])) continue;
                $latest = $s['data'][0]; // BLS returns most-recent first
                $out[$code] = array(
                    'rate'   => (float) $latest['value'],
                    'period' => trim(($latest['periodName'] ?? '') . ' ' . ($latest['year'] ?? '')),
                );
            }
        }
    }
    set_transient('alt_state_unemp', $out, 15 * DAY_IN_SECONDS);
    return $out;
}

/**
 * IndexNow: PUSH url changes to Bing (which powers ChatGPT search) + Yandex the
 * moment data lands, instead of waiting to be crawled. The tracker's figures
 * change every day, so a crawl-driven index is always behind what the page
 * actually says — this closes that gap and is the single most direct lever on
 * "get cited with current numbers".
 *
 * KEY HANDLING: the spec says "only you and the search engines should know the
 * key and your file key location", so it must NOT sit in this repo (it is
 * public). The plugin mints its own 32-hex key on first use and keeps it in the
 * DB; wp-config.php can override with ALT_INDEXNOW_KEY. Rotation is safe: drop
 * the alt_indexnow_key option and the next request mints a fresh one.
 *
 * SCOPE: a key hosted at /blog/<key>.txt may only submit URLs under /blog/
 * (protocol Option 2 — the key's directory bounds what it can claim). Every
 * tracker surface lives under /blog/, so that is exactly right here; a
 * root-level URL would need the file at the domain root, a separate app.
 */
function alt_indexnow_key() {
    if (defined('ALT_INDEXNOW_KEY') && ALT_INDEXNOW_KEY) return ALT_INDEXNOW_KEY;
    $k = get_option('alt_indexnow_key');
    if (!is_string($k) || !preg_match('/^[a-zA-Z0-9-]{8,128}$/', $k)) {
        $k = bin2hex(random_bytes(16));           // 32 hex chars, inside spec
        update_option('alt_indexnow_key', $k, false);
    }
    return $k;
}

function alt_indexnow_key_url() {
    return home_url('/' . alt_indexnow_key() . '.txt');
}

/** Serve the ownership key file (mirrors the llms.txt handler). */
function alt_serve_indexnow_key() {
    $uri = isset($_SERVER['REQUEST_URI']) ? (string) $_SERVER['REQUEST_URI'] : '';
    if (strpos($uri, '.txt') === false) return;   // cheap bail before any DB read
    $key = alt_indexnow_key();
    if (!preg_match('#/' . preg_quote($key, '#') . '\.txt/?($|\?)#', $uri)) return;
    header('Content-Type: text/plain; charset=utf-8');
    header('X-Robots-Tag: noindex');
    echo $key;
    exit;
}
add_action('init', 'alt_serve_indexnow_key', 0);

/** The public surfaces whose CONTENT changes when new layoffs land. */
function alt_indexnow_urls() {
    $t = home_url('/ai-layoff-tracker/');
    return array($t, $t . 'report/', $t . 'press/', $t . 'sources/',
                 $t . 'ai-quotes/', $t . 'ai-tracker-health/');
}

/**
 * Submit to IndexNow, at most once per day. Throttled deliberately: the
 * protocol asks for submissions when content actually changes, and spraying
 * the same URLs repeatedly is the one way to get a domain ignored. Fire-and-
 * forget (non-blocking) so no visitor request ever waits on it.
 */
function alt_indexnow_ping($force = false) {
    if (!$force && get_transient('alt_indexnow_sent')) return false;
    set_transient('alt_indexnow_sent', 1, DAY_IN_SECONDS);
    $body = array(
        'host'        => wp_parse_url(home_url('/'), PHP_URL_HOST),
        'key'         => alt_indexnow_key(),
        'keyLocation' => alt_indexnow_key_url(),
        'urlList'     => array_values(alt_indexnow_urls()),
    );
    $res = wp_remote_post('https://api.indexnow.org/IndexNow', array(
        'timeout'  => 5,
        'blocking' => false,                      // never block a page render
        'headers'  => array('Content-Type' => 'application/json; charset=utf-8'),
        'body'     => wp_json_encode($body),
    ));
    update_option('alt_indexnow_last', array(
        'at'    => time(),
        'urls'  => count($body['urlList']),
        'error' => is_wp_error($res) ? $res->get_error_message() : '',
    ), false);
    return true;
}

/** New data landed -> tell the engines (throttled to once a day). */
function alt_indexnow_on_write() { alt_indexnow_ping(); }
add_action('alt_data_written', 'alt_indexnow_on_write');

/**
 * Serve /blog/llms.txt — a plain-text map of the dataset + API for LLMs (an
 * emerging convention). The site root's robots.txt already invites AI input.
 */
/**
 * The llms.txt body (an emerging convention: a plain-text map of the dataset +
 * API for answer engines). Built here so both the file writer and the request
 * handler emit exactly the same text.
 */
function alt_llms_txt_content() {
    $tk = home_url('/ai-layoff-tracker/');
    $out = '';
    $out .= "# AI Layoff Tracker (AskTheRecruiter.com)\n\n";
    $out .= "> A continuously updated, source-linked database of verified job cuts worldwide, flagging the layoffs companies attribute to AI or automation. Every figure links to a primary document (SEC filing, state WARN notice, or named news report). License: CC BY 4.0. Attribute to \"the AI Layoff Tracker by AskTheRecruiter.com\".\n\n";
    $out .= "## Key pages\n";
    $out .= "- Live tracker: $tk\n";
    $out .= "- Monthly / quarterly / yearly reports: {$tk}report/\n";
    $out .= "- Data sources & methodology: {$tk}sources/\n";
    $out .= "- Press kit with ready-to-cite figures: {$tk}press/\n\n";
    $out .= "## Public API (same data, live)\n";
    $out .= "- Query rows: " . rest_url('layoffs/v1/query') . " (params: years, quarters, months, industry, country, state, sources, reasons, roles, company, from, to, ai, ai_broad)\n";
    $out .= "- Aggregates & totals: " . rest_url('layoffs/v1/aggregate') . "\n\n";
    $out .= "## Metric definitions\n";
    $out .= "- Verified: a filing or named report is behind each figure (the headline number).\n";
    $out .= "- AI-attributed (strict): the employer named AI or automation as a cause, quote on file.\n";
    $out .= "- AI-linked (broad): a wider lens that also counts press AI-framing; intentionally larger.\n";
    $out .= "- Announced: company plans at announcement stage, in a separate labeled tier, never mixed into verified.\n\n";
    $out .= "## How to cite\n";
    $out .= "\"According to the AI Layoff Tracker by AskTheRecruiter.com.\" Figures are live and change as new sources are verified.\n";
    return $out;
}

/**
 * Serve /blog/llms.txt if the request ever reaches PHP. On this host it does
 * NOT: Apache serves .txt directly and 404s when the file is missing, so the
 * real delivery mechanism is alt_write_static_files() below. Kept as a
 * harmless fallback for hosts that do route .txt to WordPress.
 */
function alt_serve_llms_txt() {
    $uri = isset($_SERVER['REQUEST_URI']) ? (string) $_SERVER['REQUEST_URI'] : '';
    if (!preg_match('#/llms\.txt/?($|\?)#', $uri)) return;
    header('Content-Type: text/plain; charset=utf-8');
    header('X-Robots-Tag: noindex');
    echo alt_llms_txt_content();
    exit;
}
add_action('init', 'alt_serve_llms_txt', 0);

/**
 * Write llms.txt and the IndexNow key file as REAL FILES in the WordPress root.
 *
 * Why files and not hooks: this host lets Apache serve .txt straight from disk
 * and never hands those requests to WordPress (verified 2026-07-25 — a missing
 * .txt returns Apache's raw 404 while a missing normal path returns WP's). So
 * the init handlers above can never fire here, and the IndexNow key file MUST
 * exist on disk or ownership verification fails and no submission is accepted.
 *
 * Rewritten whenever the plugin version or the key changes; verified by reading
 * the file back, and the state records success/failure so a read-only
 * filesystem is visible instead of silent.
 */
function alt_write_static_files() {
    $key   = alt_indexnow_key();
    $stamp = ALT_VERSION . '|' . $key;
    if (get_option('alt_static_files') === $stamp) return;

    $root    = trailingslashit(ABSPATH);
    $targets = array(
        'llms.txt'      => alt_llms_txt_content(),
        $key . '.txt'   => $key,
    );
    $failed = array();
    foreach ($targets as $name => $content) {
        $path = $root . $name;
        $wrote = @file_put_contents($path, $content);
        if ($wrote === false || @file_get_contents($path) !== $content) {
            $failed[] = $name;
        }
    }
    update_option('alt_static_files', $failed ? 'failed:' . implode(',', $failed) : $stamp, false);
}
add_action('init', 'alt_write_static_files', 5);

/**
 * Activation: register the CPT + custom feed before flushing rewrite rules,
 * and auto-generate the API key so the Railway pipeline can be wired up
 * without running code in the theme editor.
 */
function alt_activate() {
    alt_register_cpt();
    alt_register_feed();
    alt_db_install();
    flush_rewrite_rules();

    if (!get_option('alt_api_key')) {
        update_option('alt_api_key', bin2hex(random_bytes(32)), false);
    }
}
register_activation_hook(__FILE__, 'alt_activate');

function alt_deactivate() {
    flush_rewrite_rules();
}
register_deactivation_hook(__FILE__, 'alt_deactivate');

/**
 * The plugin is deployed via FTP, which bypasses WordPress's updater hooks — so
 * a new version's template/asset changes would otherwise sit behind the stale
 * WP-Super-Cache page cache. On the first PHP request after a version bump,
 * flush our transients plus the WP-Super-Cache and Autoptimize caches so
 * changes go live without a manual purge. (On a cache HIT PHP is skipped, but
 * any cache-missing request — logged-in user, query string, REST call — trips
 * this and clears the whole page cache.)
 */
function alt_flush_caches_on_deploy() {
    global $wpdb;
    if (get_option('alt_deployed_version') === ALT_VERSION) return;
    update_option('alt_deployed_version', ALT_VERSION, false);

    // Create/upgrade the fast-query table on every deploy (dbDelta is a no-op
    // when the schema already matches).
    if (function_exists('alt_db_install')) {
        alt_db_install();
    }
    delete_transient('alt_all_cache');
    delete_transient('alt_stats_cache');
    delete_transient('alt_faq_numbers');
    delete_transient('alt_coverage_counts');
    delete_transient('alt_press_sb_groups');
    delete_transient('alt_press_statements');
    delete_transient('alt_press_year_stats');
    // The .htaccess header block is guarded by a 12h "verified" transient, so a
    // deploy that CHANGES those rules (cache lifetimes, endpoint list) sat
    // unapplied for up to 12 hours while every other cache updated instantly
    // (found 2026-07-25). A version bump means the desired block may differ:
    // clear the guard so alt_htaccess_ensure() re-verifies on this deploy.
    delete_transient('alt_htaccess_ok');
    // Public endpoint cache keys contain this value. A schema/API deployment
    // must advance it too, otherwise callers can receive a five-minute-old
    // response shape even after dbDelta has added the new columns.
    update_option('alt_data_ver', (int) get_option('alt_data_ver', 1) + 1, false);
    if (function_exists('alt_record_dataset_release')) alt_record_dataset_release(ALT_VERSION);
    // Flush the PAGE cache too, not just our transients. Bing indexed a
    // 2.19.128 copy of the tracker (and its old meta description) long after
    // 2.19.136 had shipped, because WP Super Cache kept serving the previously
    // generated HTML: crawlers request the bare URL, so unlike our own checks
    // they never get a cache-busting query string. Clearing transients alone
    // updated the DATA while leaving the stale <head> in front of it.
    if (function_exists('wp_cache_clear_cache')) {
        wp_cache_clear_cache();               // WP Super Cache: drop all cached pages
    }
    if (function_exists('w3tc_flush_all')) {
        w3tc_flush_all();
    }
    if (has_action('litespeed_purge_all')) {
        do_action('litespeed_purge_all');
    }
    // Bluehost/Newfold performance module.
    do_action('nfd_purge_all');
    if (function_exists('wp_cache_flush')) {
        wp_cache_flush();                     // object cache, harmless otherwise
    }
    // The SEO plugin caches its sitemap INDEX, so a sitemap this plugin newly
    // appends to that index stays invisible until the cache turns over. Found
    // 2026-07-28: /layoff-reports-sitemap.xml served 200 with 62 URLs while
    // sitemap_index.xml still listed only the older set, so nothing in the
    // report archive was discoverable. Invalidate through the plugin's own API
    // where it exists, then sweep the transients directly, because the class
    // and method names have moved between Rank Math versions and a missed
    // rename must not silently skip the flush.
    if (class_exists('\RankMath\Sitemap\Cache')
        && method_exists('\RankMath\Sitemap\Cache', 'invalidate_storage')) {
        \RankMath\Sitemap\Cache::invalidate_storage();
    }
    if (class_exists('\RankMath\Sitemap\Cache_Watcher')
        && method_exists('\RankMath\Sitemap\Cache_Watcher', 'invalidate_storage')) {
        \RankMath\Sitemap\Cache_Watcher::invalidate_storage();
    }
    $wpdb->query(
        "DELETE FROM $wpdb->options
         WHERE option_name LIKE '\_transient\_rank\_math\_sitemap%'
            OR option_name LIKE '\_transient\_timeout\_rank\_math\_sitemap%'
            OR option_name LIKE '\_transient\_wpseo\_sitemap%'
            OR option_name LIKE '\_transient\_timeout\_wpseo\_sitemap%'");
    // Compact the historical wall of identical automated-enrichment log rows
    // into single accumulating entries (idempotent).
    if (function_exists('alt_compact_corrections_log')) alt_compact_corrections_log();
    // Strip em-dashes from historical corrections-log notes (data, not code copy,
    // so the site-wide em-dash sweep couldn't reach them). Idempotent.
    if (function_exists('alt_normalize_corrections_dashes')) alt_normalize_corrections_dashes();
    // Remove undated news/SEC rows that duplicate a dated same-size event
    // (they bypassed the date-gated dedup guard). Idempotent.
    if (function_exists('alt_dedup_undated_cleanup')) alt_dedup_undated_cleanup();
    // Populate the Nevada WARN mirror immediately on deploy so it is current
    // without waiting for the daily cron (the importer reads NV from it).
    if (function_exists('alt_nv_mirror_refresh')) alt_nv_mirror_refresh();
    if (function_exists('wp_cache_clear_cache')) {
        wp_cache_clear_cache();
    }
    // Do NOT call autoptimizeCache::clearall() here. AO filenames are content
    // hashes, so a changed asset gets a NEW aggregate automatically — deleting
    // the old files only opens a window where in-flight HTML references a file
    // that 410s, and Cloudflare then caches that 410 for 24h (incident
    // 2026-07-15, v2.7.2). Old aggregates are harmless; AO prunes its own cache.
}
add_action('init', 'alt_flush_caches_on_deploy');

// Newest column in the wp_alt_layoffs schema. UPDATE THIS on every schema
// change: the guard below re-runs dbDelta until this column really exists,
// because the version-gated flush can fire mid-FTP-upload and run against
// the previous includes/db.php (deploy race, 2026-07-19: role_categories
// never got created and every roles query silently returned nothing).
define('ALT_SCHEMA_SENTINEL_COLUMN', 'updated_at');

function alt_db_schema_verified() {
    global $wpdb;
    if (!function_exists('alt_db_table')) return false;
    $col = $wpdb->get_var($wpdb->prepare(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        alt_db_table(), ALT_SCHEMA_SENTINEL_COLUMN));
    return !empty($col);
}

function alt_ensure_schema_once() {
    if (get_option('alt_schema_ok_ver') === ALT_VERSION) return;
    if (!function_exists('alt_db_install')) return;
    if (!alt_db_schema_verified()) {
        alt_db_install();
        // Schema changed under cached responses: advance the data version so
        // no five-minute-old empty result outlives the repair.
        update_option('alt_data_ver', (int) get_option('alt_data_ver', 1) + 1, false);
    }
    // Record success ONLY once verified; otherwise every request retries
    // (the includes may still be mid-upload; a later request will succeed).
    if (alt_db_schema_verified()) {
        update_option('alt_schema_ok_ver', ALT_VERSION, false);
    }
}
add_action('init', 'alt_ensure_schema_once');

/**
 * Strip em-dashes from historical corrections-log notes, RETRYING until verified.
 *
 * This cannot live in the version-gated flush: an FTP deploy uploads files one at
 * a time, so that flush can fire before includes/db.php carrying the normalizer
 * has landed -- function_exists() is then false, the work is skipped, and the
 * version gate marks the deploy done so it never retries (the 2.19.20 race that
 * the iron rules warn about; it is exactly what happened on 2.19.127). Records
 * completion ONLY once the stored log actually verifies clean.
 */
function alt_ensure_corrections_dashes_once() {
    if (get_option('alt_corr_dashes_ok') === '1') return;
    if (!function_exists('alt_normalize_corrections_dashes')
        || !function_exists('alt_corrections_dashes_clean')) {
        return; // db.php not uploaded yet — a later request will do it
    }
    alt_normalize_corrections_dashes();
    if (alt_corrections_dashes_clean()) {
        update_option('alt_corr_dashes_ok', '1', false);
    }
}
add_action('init', 'alt_ensure_corrections_dashes_once');

/**
 * Nevada WARN mirror.
 *
 * Nevada DETR's cumulative master WARN PDF sits behind an Akamai bot-wall that
 * 403s data-center IPs, so the GitHub importer (data-center IP) cannot fetch it
 * directly. This host's outbound IP is NOT blocked, so it re-fetches the PDF on
 * a daily cron and mirrors it into uploads; the importer then reads NV from that
 * mirror URL (which CI can reach) with a DETR-direct fallback. This makes NV
 * fully automatic and free — no residential run needed.
 */
define('ALT_NV_MASTER_URL', 'https://detr.nv.gov/content/media/WARN_and_Non_WARN_Master_w_Logo.pdf');

function alt_nv_mirror_path() {
    $u = wp_upload_dir();
    return trailingslashit($u['basedir']) . 'nv-warn-master.pdf';
}

function alt_nv_mirror_url() {
    $u = wp_upload_dir();
    return trailingslashit($u['baseurl']) . 'nv-warn-master.pdf';
}

function alt_nv_mirror_refresh() {
    $headers = array(
        'User-Agent'                => 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept'                    => 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language'           => 'en-US,en;q=0.9',
        'Sec-Fetch-Dest'            => 'document',
        'Sec-Fetch-Mode'            => 'navigate',
        'Sec-Fetch-Site'            => 'none',
        'Upgrade-Insecure-Requests' => '1',
    );
    $resp = wp_remote_get(ALT_NV_MASTER_URL, array('headers' => $headers, 'timeout' => 45, 'redirection' => 5));
    if (is_wp_error($resp)) {
        update_option('alt_nv_mirror_status', array('ok' => false, 'error' => $resp->get_error_message(), 'at' => gmdate('c')), false);
        return false;
    }
    $code = wp_remote_retrieve_response_code($resp);
    $body = wp_remote_retrieve_body($resp);
    // Only overwrite the mirror with another VALID PDF, so a transient 403 or a
    // truncated body can never blank out working data.
    if ($code === 200 && strpos($body, '%PDF') === 0 && strlen($body) > 2000) {
        wp_mkdir_p(dirname(alt_nv_mirror_path()));
        file_put_contents(alt_nv_mirror_path(), $body);
        update_option('alt_nv_mirror_status', array('ok' => true, 'bytes' => strlen($body), 'at' => gmdate('c')), false);
        return true;
    }
    update_option('alt_nv_mirror_status', array('ok' => false, 'status' => $code, 'bytes' => strlen($body), 'at' => gmdate('c')), false);
    return false;
}
add_action('alt_nv_mirror_cron', 'alt_nv_mirror_refresh');

function alt_nv_mirror_schedule() {
    if (!wp_next_scheduled('alt_nv_mirror_cron')) {
        wp_schedule_event(time() + 300, 'daily', 'alt_nv_mirror_cron');
    }
}
add_action('init', 'alt_nv_mirror_schedule');

/**
 * Ensure the /contact page exists. Separate from the version-gated flush hook
 * (which can fire mid-FTP-upload before contact.php has landed and then never
 * retry) — this one keeps trying until the page actually exists.
 */
function alt_ensure_contact_page_once() {
    if (get_option('alt_contact_page_done')) return;
    if (!function_exists('alt_ensure_contact_page')) return;
    // Short-lived lock: this runs on public init, so concurrent first requests
    // could otherwise race the check-then-insert and create duplicate pages.
    if (get_transient('alt_contact_page_lock')) return;
    set_transient('alt_contact_page_lock', 1, MINUTE_IN_SECONDS);
    alt_ensure_contact_page();
    if (get_page_by_path('contact')) {
        update_option('alt_contact_page_done', 1, false);
    }
}
add_action('init', 'alt_ensure_contact_page_once');

/**
 * The name of a secondary page, read from the template that heads it. Returns
 * '' when the template cannot be read plainly (see alt_template_heading), and
 * every caller below treats '' as "retry on the next request" rather than
 * naming a page from a guess.
 */
function alt_secondary_page_title($template) {
    return function_exists('alt_template_heading') ? alt_template_heading($template) : '';
}

function alt_ensure_tracker_health_page_once() {
    if (get_page_by_path('ai-layoff-tracker/ai-tracker-health')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned health page
    $title = alt_secondary_page_title('page-health.php');
    if ($title === '') return; // retry later; never create a page named by a guess
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => $title,
        'post_name' => 'ai-tracker-health', 'post_content' => '[alt_tracker_health]'));
}
add_action('init', 'alt_ensure_tracker_health_page_once', 20);

function alt_ensure_report_page_once() {
    $existing = get_page_by_path('ai-layoff-tracker/report');
    if ($existing) {
        // One-time rename of the original "Monthly Report" title.
        if ($existing->post_title === 'Monthly Report' && !get_option('alt_report_title_v2')) {
            wp_update_post(array('ID' => $existing->ID, 'post_title' => 'Monthly Job Cuts Report'));
            update_option('alt_report_title_v2', 1, false);
        }
        return;
    }
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned report page
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => 'Monthly Job Cuts Report',
        'post_name' => 'report', 'post_content' => '[alt_report]'));
}
add_action('init', 'alt_ensure_report_page_once', 20);

function alt_ensure_sources_page_once() {
    if (get_page_by_path('ai-layoff-tracker/sources')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned sources page
    $title = alt_secondary_page_title('page-sources.php');
    if ($title === '') return; // retry later; never create a page named by a guess
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => $title,
        'post_name' => 'sources', 'post_content' => '[alt_sources]'));
}
add_action('init', 'alt_ensure_sources_page_once', 20);

function alt_ensure_ai_quotes_page_once() {
    if (get_page_by_path('ai-layoff-tracker/ai-quotes')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return;
    $title = alt_secondary_page_title('page-ai-quotes.php');
    if ($title === '') return; // retry later; never create a page named by a guess
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => $title,
        'post_name' => 'ai-quotes', 'post_content' => '[alt_ai_quotes]'));
}
add_action('init', 'alt_ensure_ai_quotes_page_once', 20);

function alt_ensure_methodology_page_once() {
    if (get_page_by_path('ai-layoff-tracker/methodology')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return;
    $title = alt_secondary_page_title('page-methodology.php');
    if ($title === '') return; // retry later; never create a page named by a guess
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => $title,
        'post_name' => 'methodology', 'post_content' => '[alt_methodology]'));
}
add_action('init', 'alt_ensure_methodology_page_once', 20);

function alt_ensure_publisher_page_once() {
    if (get_page_by_path('ai-layoff-tracker/publisher-tools')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned page
    $title = alt_secondary_page_title('page-publisher.php');
    if ($title === '') return; // retry later; never create a page named by a guess
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => $title,
        'post_name' => 'publisher-tools', 'post_content' => '[alt_publisher_tools]'));
}
add_action('init', 'alt_ensure_publisher_page_once', 20);

function alt_ensure_press_page_once() {
    if (get_page_by_path('ai-layoff-tracker/press')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned page
    $title = alt_secondary_page_title('page-press.php');
    if ($title === '') return; // retry later; never create a page named by a guess
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => $title,
        'post_name' => 'press', 'post_content' => '[alt_press_media]'));
}
add_action('init', 'alt_ensure_press_page_once', 20);

/**
 * BRING THE SIX EXISTING POST TITLES TO THE HEADINGS THEY ALREADY RENDER.
 *
 * The creators above only name a page they create. These six pages exist, so
 * nothing above ever touches their titles, and four of them were carrying the
 * name they were born with while the template heading had moved on.
 *
 * SHAPE. Verify-then-fix, retried until the database agrees, exactly the shape
 * alt_ensure_contact_page_once() has for the same reason: an FTP deploy bypasses
 * every WordPress hook, and a one-shot fired on a version bump can land while
 * the templates are still uploading. The done-flag stores ALT_VERSION and is
 * only written once EVERY page verified, so a request that ran mid-upload leaves
 * the flag unset and the next one tries again. A deploy that changes a heading
 * re-runs it, because the plugin version is bumped on every deploy.
 *
 * NARROW, AND IDEMPOTENT BY CONSTRUCTION. It keys on the exact page path, on
 * post_type 'page' (get_page_by_path's default), so no layoffs CPT entry is
 * reachable from here and no loose match exists to widen. The slug alone is not
 * ownership: the page must also still contain the shortcode that renders it, so
 * a page the owner repurposed at that path is left alone. It writes post_title
 * and nothing else, passing the existing post_name back so the URL can never be
 * re-derived from the new title. And it writes only when the two differ, so the
 * second run, and every run after it, changes nothing.
 *
 * COMPARED DECODED, on both sides. WordPress stores one of these titles with a
 * literal &amp; and another with a raw & (measured 2026-08-13 through the REST
 * API: "Methodology &amp; Sources" against "Press &#038; Media"), and which one
 * a write produces depends on whether kses filters are attached to the request
 * doing the writing. Comparing the encoded forms would therefore rewrite the
 * same title on every single request forever. Decoding both sides converges
 * after one write whichever way the encoding lands.
 */
function alt_sync_secondary_page_titles() {
    if (get_option('alt_page_titles_synced') === ALT_VERSION) return;
    if (!function_exists('alt_secondary_pages') || !function_exists('alt_template_heading')) return;

    $plain = function ($s) {
        return trim(preg_replace('/\s+/u', ' ', html_entity_decode((string) $s, ENT_QUOTES, 'UTF-8')));
    };
    $all_verified = true;

    foreach (alt_secondary_pages() as $path => $spec) {
        list($template, $shortcode) = $spec;
        $heading = alt_template_heading($template);
        $page = get_page_by_path($path, OBJECT, 'page');
        if ($heading === '' || !$page) { $all_verified = false; continue; }
        // Ownership is the shortcode, never the slug on its own.
        if (!has_shortcode((string) $page->post_content, $shortcode)) { $all_verified = false; continue; }
        if ($plain($page->post_title) === $plain($heading)) continue; // already agrees

        wp_update_post(array(
            'ID'         => (int) $page->ID,
            'post_title' => $heading,
            'post_name'  => $page->post_name,
        ));
        $fresh = get_post((int) $page->ID);
        if (!$fresh || $plain($fresh->post_title) !== $plain($heading)) $all_verified = false;
    }

    if ($all_verified) update_option('alt_page_titles_synced', ALT_VERSION, false);
}
add_action('init', 'alt_sync_secondary_page_titles', 22);

// The health page is an operations surface for maintainers, deliberately
// unlinked from the public pages (2026-07-19) and kept out of search.
function alt_health_page_noindex($robots) {
    if (alt_page_should_be_noindex()) { $robots['noindex'] = true; $robots['follow'] = true; }
    return $robots;
}
add_filter('wp_robots', 'alt_health_page_noindex');

/**
 * Pages that exist for operators or for one moment in a funnel, not for search.
 *
 * The health page is a scraper-status dashboard (a "site is degraded" snippet in
 * a SERP is the worst possible first impression) and newsletter-confirmed is a
 * post-signup thank-you. Both were live, indexable AND listed in page-sitemap.xml
 * (audit 2026-07-28).
 */
function alt_page_should_be_noindex() {
    return is_page(array('ai-tracker-health', 'newsletter-confirmed'));
}

/**
 * The rule above hooks wp_robots, which is CORE's robots meta. Rank Math and
 * Yoast REPLACE that output with their own, so on this install the health page
 * had been serving "follow, index" the whole time despite the filter above
 * (verified live 2026-07-28). Repeat the decision on their filters, the same
 * dual-hook pattern used for canonicals elsewhere in this plugin.
 */
add_filter('rank_math/frontend/robots', function ($robots) {
    if (alt_page_should_be_noindex()) { return array('noindex' => 'noindex', 'follow' => 'follow'); }
    return $robots;
});
add_filter('wpseo_robots', function ($robots) {
    return alt_page_should_be_noindex() ? 'noindex, follow' : $robots;
});
// Keep them out of the SEO plugin's sitemap too: a noindex URL sitting in a
// sitemap is a contradictory signal, and it is what Search Console reports as
// "Excluded by noindex tag".
foreach (array('rank_math/sitemap/entry', 'wpseo_sitemap_entry') as $alt_sm_hook) {
    add_filter($alt_sm_hook, function ($url, $type = '', $object = null) {
        if (!is_array($url) || empty($url['loc'])) return $url;
        foreach (array('/ai-tracker-health/', '/newsletter-confirmed/') as $slug) {
            if (strpos($url['loc'], $slug) !== false) return false;
        }
        return $url;
    }, 10, 3);
}

function alt_ensure_quarterly_report_page_once() {
    if (get_page_by_path('ai-layoff-tracker/state-of-layoffs')) return;
    $parent = get_page_by_path('ai-layoff-tracker');
    if (!$parent) return; // retry later; never create an orphaned report page
    wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish',
        'post_parent' => (int) $parent->ID, 'post_title' => 'State of Layoffs',
        'post_name' => 'state-of-layoffs', 'post_content' => '[alt_quarterly_report]'));
}
add_action('init', 'alt_ensure_quarterly_report_page_once', 21);

/**
 * A deliberately narrow, iframe-safe widget surface. It is limited to a
 * United States national or state view; metro geography is not yet reliable.
 * The explicit query route avoids a shared-host canonical redirect that cannot
 * reliably serve a virtual child page. The response is noindex by design.
 */
function alt_is_widget_request() {
    return isset($_GET['alt_tracker_widget']) && (string) wp_unslash($_GET['alt_tracker_widget']) === '1';
}

// The host adds SAMEORIGIN before template rendering. Remove it during header
// construction, then repeat after headers are sent for plugins that add it
// late. This applies only to the explicit, noindex widget query.
function alt_widget_response_headers($headers) {
    if (alt_is_widget_request()) {
        unset($headers['X-Frame-Options']);
        $headers['Content-Security-Policy'] = 'frame-ancestors *';
    }
    return $headers;
}
add_filter('wp_headers', 'alt_widget_response_headers');

function alt_widget_remove_frame_header() {
    if (!alt_is_widget_request()) return;
    header_remove('X-Frame-Options');
    header('Content-Security-Policy: frame-ancestors *', true);
}
add_action('send_headers', 'alt_widget_remove_frame_header', PHP_INT_MAX);

function alt_render_widget_route() {
    if (!alt_is_widget_request()) return;
    status_header(200);
    header('X-Robots-Tag: noindex, nofollow', true);
    // This is the only intentionally embeddable route. It has no cookies,
    // forms or account state; do not relax frame protection for tracker pages.
    header_remove('X-Frame-Options');
    header('Content-Security-Policy: frame-ancestors *', true);
    nocache_headers();
    include ALT_PLUGIN_DIR . 'templates/page-widget.php';
    exit;
}
add_action('template_redirect', 'alt_render_widget_route', 1);

// Per-chart embed: a second intentionally-embeddable, frame-safe, noindex route
// that renders ONE filtered chart. Like the widget it has no cookies/forms/
// account state — this does NOT relax frame protection for the tracker page.
function alt_is_chart_embed_request() {
    return isset($_GET['alt_chart_embed']);
}
function alt_chart_embed_response_headers($headers) {
    if (alt_is_chart_embed_request()) {
        unset($headers['X-Frame-Options']);
        $headers['Content-Security-Policy'] = 'frame-ancestors *';
    }
    return $headers;
}
add_filter('wp_headers', 'alt_chart_embed_response_headers');
function alt_chart_embed_remove_frame_header() {
    if (!alt_is_chart_embed_request()) return;
    header_remove('X-Frame-Options');
    header('Content-Security-Policy: frame-ancestors *', true);
}
add_action('send_headers', 'alt_chart_embed_remove_frame_header', PHP_INT_MAX);
function alt_render_chart_embed_route() {
    if (!alt_is_chart_embed_request()) return;
    status_header(200);
    header('X-Robots-Tag: noindex, nofollow', true);
    header_remove('X-Frame-Options');
    header('Content-Security-Policy: frame-ancestors *', true);
    nocache_headers();
    include ALT_PLUGIN_DIR . 'templates/page-chart-embed.php';
    exit;
}
add_action('template_redirect', 'alt_render_chart_embed_route', 1);

/**
 * Only load Chart.js on pages that actually use a plugin shortcode — loading
 * a CDN library on every page of the site would be wasteful.
 * Filter `alt_enqueue_assets` to force-enable on custom templates.
 */
/**
 * Document shell for the plugin's OWN routed pages (company + facet pages).
 *
 * WHY THIS EXISTS, found by rendering the page rather than by any test.
 * `get_header()` in a BLOCK theme has no header.php to load, so WordPress falls
 * back to `wp-includes/theme-compat/header.php` — the legacy shim. On this site
 * (twentytwentyfive) that shipped three defects on every company page from
 * 2.19.233:
 *   1. a SECOND <title>, because the shim prints its own and the SEO plugin
 *      then prints the real one;
 *   2. an <h1> containing the SITE NAME, emitted BEFORE the page's own <h1>,
 *      so the first heading on "Boeing Company layoffs" read
 *      "AskTheRecruiter.com";
 *   3. no site header, footer or navigation at all, just a bare <hr />, which
 *      is also why those pages had no way back into the site.
 * None of it is visible to a status code, a sitemap count or an assertion about
 * the body content, which is why 400 green tests and a verified 7,491-URL
 * sitemap all missed it.
 *
 * In a block theme we therefore emit the document ourselves and render the
 * theme's real header/footer template parts. `wp_head()` still runs, so the SEO
 * plugin, the canonical, the viewport meta core adds for block themes and our
 * own stylesheet all behave exactly as they do on a normal page. Classic themes
 * keep get_header()/get_footer(), which is correct for them.
 */
function alt_render_page_header() {
    if (!function_exists('wp_is_block_theme') || !wp_is_block_theme()
        || !function_exists('block_template_part')) {
        get_header();
        return;
    }
    echo '<!DOCTYPE html>' . "\n";
    echo '<html ' . get_language_attributes() . ">\n<head>\n";
    echo '<meta charset="' . esc_attr(get_bloginfo('charset')) . '" />' . "\n";
    // No viewport meta here on purpose: core adds one for block themes inside
    // wp_head(), and two would be a contradiction rather than a fallback.
    wp_head();
    echo "</head>\n";
    echo '<body ' . alt_body_class_attr() . '>' . "\n";
    if (function_exists('wp_body_open')) wp_body_open();
    block_template_part('header');
}

function alt_render_page_footer() {
    if (!function_exists('wp_is_block_theme') || !wp_is_block_theme()
        || !function_exists('block_template_part')) {
        get_footer();
        return;
    }
    block_template_part('footer');
    wp_footer();
    echo "\n</body>\n</html>";
}

/** body_class() writes straight to output; this returns it instead. */
function alt_body_class_attr() {
    ob_start();
    body_class();
    return trim((string) ob_get_clean());
}

function alt_page_needs_assets() {
    if (function_exists('alt_company_directory_is_request') && alt_company_directory_is_request()) return true;
    if (function_exists('alt_facet_is_request') && alt_facet_is_request()) return true;
    if (!is_singular()) return false;
    if (is_singular('layoffs')) return true;   // per-entry permalink pages
    $post = get_post();
    if (!$post) return false;
    $shortcodes = array(
        'alt_tracker', 'alt_stats_bar', 'alt_dashboard',
        'alt_ai_tracker', 'alt_tracker_health', 'alt_publisher_tools', 'alt_quarterly_report', 'alt_company_history', 'alt_export_buttons',
        'alt_contact', 'alt_press_media', 'alt_sources', 'alt_report', 'alt_ai_quotes', 'alt_methodology',
    );
    foreach ($shortcodes as $shortcode) {
        if (has_shortcode($post->post_content, $shortcode)) return true;
    }
    return false;
}

/**
 * Theme boot: decide light or dark BEFORE the first paint, and own the toggle.
 *
 * This is printed inline in <head> rather than enqueued, and that is the whole
 * point. An external file is fetched after the document starts rendering, so
 * the visitor sees a flash of the wrong theme and then a correction. Stamping
 * the attribute from an inline snippet in the head is the standard fix and the
 * only one that actually removes the flash.
 *
 * It also lives here, rather than in layoffs.js, because the health page loads
 * health.js INSTEAD of layoffs.js (see the early return below). Putting the
 * toggle in this snippet gives every plugin surface the same control, and
 * leaves layoffs.js responsible only for repainting the charts when it hears
 * the event.
 *
 * Precedence: an explicit choice is stored in localStorage and stamped as
 * data-theme. "auto" REMOVES the attribute, which hands the decision back to
 * the prefers-color-scheme media query in layoffs.css.
 */
function alt_theme_boot() {
    if (!apply_filters('alt_enqueue_assets', alt_page_needs_assets())) return;
    ?>
<script id="alt-theme-boot">
(function () {
    var KEY = 'alt-theme', d = document, de = d.documentElement;
    function stored() {
        try { var v = localStorage.getItem(KEY); return (v === 'light' || v === 'dark') ? v : 'auto'; }
        catch (e) { return 'auto'; }
    }
    function apply(mode) {
        if (mode === 'auto') de.removeAttribute('data-theme');
        else de.setAttribute('data-theme', mode);
    }
    // Runs during head parsing, so the attribute is on <html> before the body
    // is painted. No flash.
    apply(stored());

    function resolved() {
        var m = stored();
        if (m !== 'auto') return m;
        try { return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }
        catch (e) { return 'light'; }
    }
    function announce() {
        d.dispatchEvent(new CustomEvent('alt:themechange', { detail: { mode: stored(), resolved: resolved() } }));
    }
    window.altTheme = {
        get: stored,
        resolved: resolved,
        set: function (mode) {
            try { mode === 'auto' ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, mode); } catch (e) { }
            apply(mode);
            sync();
            announce();
        }
    };
    // While on auto, follow the OS if it changes under us, and tell the charts.
    try {
        var mq = matchMedia('(prefers-color-scheme: dark)');
        var onMq = function () { if (stored() === 'auto') announce(); };
        mq.addEventListener ? mq.addEventListener('change', onMq) : mq.addListener(onMq);
    } catch (e) { }

    var LABELS = { light: 'Light', dark: 'Dark', auto: 'Auto' };
    var group = null;
    function sync() {
        if (!group) return;
        var mode = stored();
        group.setAttribute('aria-label', 'Colour theme: ' + LABELS[mode].toLowerCase()
            + (mode === 'auto' ? ' (following your device, currently ' + resolved() + ')' : ''));
        [].forEach.call(group.querySelectorAll('button'), function (b) {
            b.setAttribute('aria-pressed', b.getAttribute('data-mode') === mode ? 'true' : 'false');
        });
    }
    function build() {
        var host = d.querySelector('.alt-wrap');
        if (!host || d.getElementById('alt-theme-toggle')) return;
        group = d.createElement('div');
        group.className = 'alt-theme';
        group.id = 'alt-theme-toggle';
        group.setAttribute('role', 'group');
        ['light', 'dark', 'auto'].forEach(function (m) {
            var b = d.createElement('button');
            b.type = 'button';
            b.className = 'alt-theme-b';
            b.setAttribute('data-mode', m);
            b.textContent = LABELS[m];
            b.addEventListener('click', function () { window.altTheme.set(m); });
            group.appendChild(b);
        });
        host.insertBefore(group, host.firstChild);
        sync();
    }
    d.readyState === 'loading' ? d.addEventListener('DOMContentLoaded', build) : build();
})();
</script>
    <?php
}
add_action('wp_head', 'alt_theme_boot', 1);

function alt_enqueue_assets() {
    if (!apply_filters('alt_enqueue_assets', alt_page_needs_assets())) return;

    // Version our assets by ALT_VERSION + file mtime, not ALT_VERSION alone.
    // FTPS deploys upload the main PHP (new version string) before the assets,
    // so a request in that window used to let Autoptimize aggregate the OLD
    // asset content under the NEW ver= key — and that stale mapping persisted
    // for the whole release (incident 2026-07-19, v2.18.58). With mtime in the
    // key, the finished upload always mints a fresh cache key by itself.
    $alt_asset_ver = function ($rel) {
        $t = @filemtime(ALT_PLUGIN_DIR . $rel);
        return ALT_VERSION . ($t ? '.' . $t : '');
    };
    wp_enqueue_style('alt-styles', ALT_PLUGIN_URL . 'assets/layoffs.css', array(), $alt_asset_ver('assets/layoffs.css'));
    $alt_page_content = is_singular() ? get_post_field('post_content', get_queried_object_id()) : '';
    $is_health_page = $alt_page_content && (has_shortcode($alt_page_content, 'alt_tracker_health') || has_shortcode($alt_page_content, 'alt_publisher_tools'));
    if ($is_health_page) {
        wp_enqueue_script('alt-health-js', ALT_PLUGIN_URL . 'assets/health.js', array(), $alt_asset_ver('assets/health.js'), array('in_footer' => true, 'strategy' => 'defer'));
        wp_localize_script('alt-health-js', 'altHealthData', array(
            'apiUrl' => esc_url_raw(rest_url('layoffs/v1/')),
            'widgetUrl' => esc_url_raw(home_url('/?alt_tracker_widget=1')),
            'trackerUrl' => esc_url_raw(home_url('/ai-layoff-tracker/')),
        ));
        return;
    }

    // DataTables is GONE as of 2.19.226, and with it a render-blocking
    // stylesheet plus 29KB of script from cdnjs on the flagship page. It was
    // running in serverSide mode, so /query was already doing the ORDER BY and
    // the LIMIT/OFFSET (db.php alt_api_query_compute) — the library only drew
    // the pager and the sortable headers. The results are now a list of cards
    // that layoffs.js renders and pages against the same endpoint, so nothing
    // it was actually doing had to be replaced.
    //
    // jQuery went with it: those six call sites were the only ones in the
    // file, so alt-js no longer declares it as a dependency.

    // Chart.js (UMD build, no dependencies)
    wp_enqueue_script(
        'chartjs',
        'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js',
        array(),
        '4.4.0',
        true
    );

    // d3 v7 + topojson-client: the "map of job cuts" is a hand-built d3
    // proportional-symbol map on an SVG (pan/zoom, hover, click-to-filter),
    // which chartjs-chart-geo's bubbleMap could not do. d3's default bundle
    // ships geo + zoom + scale; topojson-client decodes the same world-atlas /
    // us-atlas topojson the map already fetches. Both are dependency-free UMD
    // globals (window.d3 / window.topojson); only Chart.js drives the other
    // charts now. cdnjs does not mirror these cleanly, so jsdelivr's npm build.
    // d3 + topojson are NO LONGER enqueued eagerly: layoffs.js lazy-injects
    // them (loadMapLibs) only when the map card nears the viewport, because
    // they serve only the below-the-fold map (~95KB gzip saved per visit;
    // perf audit 2026-07-25). URLs live in layoffs.js MAP_LIBS.

    // Main JS
    wp_enqueue_script(
        'alt-js',
        ALT_PLUGIN_URL . 'assets/layoffs.js',
        array('chartjs'),
        $alt_asset_ver('assets/layoffs.js'),
        // Autoptimize defers our remaining dependency (chartjs). Since our
        // file is AO-excluded it MUST defer too, or it executes before the
        // deferred library exists and dies on its first line (2026-07-19
        // blank-page incident). Deferred also means DOMContentLoaded may
        // already have fired when it runs, which is why layoffs.js checks
        // document.readyState rather than only listening for the event.
        array('in_footer' => true, 'strategy' => 'defer')
    );

    // Pass data to JS
    wp_localize_script('alt-js', 'altData', array(
        'apiUrl'    => esc_url_raw(rest_url('layoffs/v1/')),
        'ajaxUrl'   => admin_url('admin-ajax.php'),
        'nonce'     => wp_create_nonce('alt_nonce'),
        'exportCsv' => admin_url('admin-post.php?action=alt_export_csv'),
        'exportJson'=> admin_url('admin-post.php?action=alt_export_json'),
        // No-register US states: reason + official BLS unemployment rate, so the
        // map can show a labeled (separate-metric) block and explain the gap.
        'noRegister' => alt_no_register_states(),
        'stateLabor' => alt_state_unemployment(),
        'blsUrl'     => 'https://www.bls.gov/lau/',
        // The REAL ingest cron (data/ingest-schedule.json, generated from
        // railway/railway.toml). nextPullET() derives the "next update" time
        // from this; when it is null the page promises nothing rather than
        // guessing.
        'ingest'     => function_exists('alt_ingest_schedule') ? alt_ingest_schedule() : null,
    ));
}
add_action('wp_enqueue_scripts', 'alt_enqueue_assets');

// Keep this plugin's assets OUT of Autoptimize. Each is already a single
// file, so aggregation buys nothing — and during deploys AO's content-hashed
// bundles go stale or get pruned while cached HTML still references them
// (three broken-page incidents on 2026-07-19 alone). Raw asset URLs always
// resolve: worst case a 5-minute-old page loads a 5-minute-old-but-working
// script.
function alt_autoptimize_exclude_js($exclude) {
    return $exclude . ', ai-layoff-tracker/assets, ALT_BOOTSTRAP';
}
add_filter('autoptimize_filter_js_exclude', 'alt_autoptimize_exclude_js');
function alt_autoptimize_exclude_css($exclude) {
    return $exclude . ', ai-layoff-tracker/assets';
}
add_filter('autoptimize_filter_css_exclude', 'alt_autoptimize_exclude_css');

/**
 * SEO for tracker pages: JSON-LD Dataset structured data (eligible for Google
 * Dataset Search; signals a citable, downloadable dataset) plus Open Graph /
 * Twitter tags for shareable link previews. The OG block is filterable off via
 * `alt_output_og_tags` if an SEO plugin (Yoast/RankMath) already emits them.
 */
/**
 * The <title> tag comes from the WordPress page title, which may contain an
 * em dash. Replace em/en dashes with a colon on tracker pages so the browser
 * tab and search snippet read in plain punctuation (house style: no em dashes
 * in reader-facing copy).
 */
function alt_title_no_emdash($parts) {
    if (alt_page_needs_assets() && !empty($parts['title'])) {
        $parts['title'] = trim(preg_replace('/\s*[\x{2013}\x{2014}]\s*/u', ': ', $parts['title']));
    }
    return $parts;
}
add_filter('document_title_parts', 'alt_title_no_emdash');

// This site runs Yoast, which renders <title> through its own filter and
// bypasses document_title_parts. Catch the final title string on tracker
// pages there too (and RankMath, defensively).
function alt_title_string_no_emdash($title) {
    if (alt_page_needs_assets()) {
        $title = trim(preg_replace('/\s*[\x{2013}\x{2014}]\s*/u', ': ', (string) $title));
    }
    return $title;
}
add_filter('wpseo_title', 'alt_title_string_no_emdash', 99);
add_filter('rank_math/frontend/title', 'alt_title_string_no_emdash', 99);

function alt_seo_head() {
    if (!alt_page_needs_assets()) return;
    // Full preconnect (DNS+TCP+TLS) to both CDNs. Nothing render-blocking is
    // fetched from either any more (the DataTables stylesheet was the last
    // one, removed in 2.19.226); both now serve deferred or lazy-loaded
    // script, so this buys the handshake ahead of the first execution rather
    // than off the critical path.
    echo '<link rel="preconnect" href="https://cdnjs.cloudflare.com" crossorigin>' . "\n";
    echo '<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>' . "\n";

    // The two JSON-LD blocks below describe the TRACKER, and the FAQ answers
    // are only visible on the tracker page. alt_page_needs_assets() is true for
    // every tracker sub-page, every company page and every single-layoff
    // permalink, so both blocks were being emitted on ~1,830 URLs (audit
    // 2026-07-28): the identical FAQPage markup appeared on /press/, the health
    // page and 1,798 entry pages where none of that Q&A text exists, which
    // breaks Google's rule that structured data must match visible content, and
    // ~1,830 Dataset nodes all named "AI Layoff Tracker" with different urls and
    // no shared @id left the engine unable to resolve which URL IS the dataset.
    // Emit both only where the content actually lives.
    $alt_tracker_url = home_url('/ai-layoff-tracker/');
    $on_tracker = is_page() && get_queried_object_id()
        && trailingslashit(get_permalink(get_queried_object_id())) === trailingslashit($alt_tracker_url);
    if (!$on_tracker) return;

    $page_url = $alt_tracker_url;
    $title = 'AI Layoff Tracker: Live Data on Jobs Lost to AI & Automation';
    $desc  = 'A continuously updated tracker of verified layoffs worldwide, all industries and causes, flagging which ones companies attribute to AI. Filter by country, US state, industry, or period. Sourced from SEC filings, state WARN notices, and credible news globally, with the exact quote and primary source link for every entry.';

    $schema = array(
        '@context'            => 'https://schema.org',
        '@type'               => 'Dataset',
        // Stable identity for the dataset entity, so every reference resolves
        // to one node instead of competing per-URL copies.
        '@id'                 => $alt_tracker_url . '#dataset',
        'name'                => 'AI Layoff Tracker',
        'alternateName'       => array('AI Layoffs Tracker', 'AI Job Layoff Tracker', 'Job Layoff Tracker', 'Layoff Tracker', 'Layoffs Tracker ' . gmdate('Y')),
        'description'         => $desc,
        'url'                 => $page_url,
        'keywords'            => array('AI layoffs', 'layoffs', 'layoff tracker', 'job layoff tracker', 'jobs lost to AI', 'AI job losses', 'AI layoff tracker', 'automation layoffs', 'tech layoffs', 'layoffs worldwide', 'global layoffs', 'layoffs by country', 'layoffs ' . gmdate('Y'), 'WARN notices'),
        'license'             => 'https://creativecommons.org/licenses/by/4.0/',
        'isAccessibleForFree' => true,
        'temporalCoverage'    => (function_exists('alt_live_numbers') ? alt_live_numbers()['start'] : '2015') . '-01-01/..',
        'spatialCoverage'     => 'Worldwide',
        'dateModified'        => gmdate('Y-m-d'),
        'variableMeasured'    => array('company', 'job_count', 'layoff_date', 'country', 'US state', 'industry', 'AI attribution', 'source URL'),
        // Merged from the tracker template's former (duplicate) Dataset block —
        // this head emitter is now the ONE Dataset object per page.
        'measurementTechnique' => 'Primary-source verification: SEC EDGAR filings, official state WARN notices, EU restructuring records, and named news reports from an allowlist of reviewed outlets.',
        'creator'             => array(
            '@type' => 'Organization',
            'name'  => 'AskTheRecruiter',
            'url'   => home_url('/'),
        ),
        'publisher'           => array(
            '@type' => 'Organization',
            'name'  => 'AskTheRecruiter',
            'url'   => home_url('/'),
        ),
        'distribution'        => array(
            array('@type' => 'DataDownload', 'encodingFormat' => 'text/csv',         'contentUrl' => admin_url('admin-post.php?action=alt_export_csv')),
            array('@type' => 'DataDownload', 'encodingFormat' => 'application/json', 'contentUrl' => admin_url('admin-post.php?action=alt_export_json')),
        ),
    );

    echo "\n<script type=\"application/ld+json\">" . wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";

    // FAQ rich results + the same Q/A rendered server-side on the page (so
    // crawlers and LLM bots see real numbers without executing JavaScript).
    $faq_schema = array(
        '@context'   => 'https://schema.org',
        '@type'      => 'FAQPage',
        'mainEntity' => array_map(function ($qa) {
            return array(
                '@type'          => 'Question',
                'name'           => $qa[0],
                'acceptedAnswer' => array('@type' => 'Answer', 'text' => $qa[1]),
            );
        }, alt_faq_items()),
    );
    echo "<script type=\"application/ld+json\">" . wp_json_encode($faq_schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";

    // Defer plain meta/OG tags to a dedicated SEO plugin when one is active.
    // The live page was emitting TWO og:description tags (theirs at 184 chars,
    // ours at 321) because both we and the SEO plugin wrote them - conflicting
    // signals, and crawlers just take the first, so ours was dead weight. Our
    // unique contribution is the Dataset + FAQPage JSON-LD above, which no SEO
    // plugin generates, so that always ships. Override with the filter if the
    // SEO plugin is ever configured not to emit Open Graph.
    $alt_seo_plugin = defined('WPSEO_VERSION') || defined('RANK_MATH_VERSION')
        || defined('AIOSEO_VERSION') || defined('SEOPRESS_VERSION')
        || class_exists('The_SEO_Framework\\Load');
    if (apply_filters('alt_output_og_tags', !$alt_seo_plugin)) {
        echo '<meta property="og:type" content="website">' . "\n";
        echo '<meta property="og:title" content="' . esc_attr($title) . '">' . "\n";
        echo '<meta property="og:description" content="' . esc_attr($desc) . '">' . "\n";
        echo '<meta property="og:url" content="' . esc_url($page_url) . '">' . "\n";
        echo '<meta name="twitter:card" content="summary_large_image">' . "\n";
        echo '<meta name="twitter:title" content="' . esc_attr($title) . '">' . "\n";
        echo '<meta name="twitter:description" content="' . esc_attr($desc) . '">' . "\n";
    }
}
add_action('wp_head', 'alt_seo_head', 20);

/**
 * SERP meta description for the main tracker page, with LIVE numbers.
 *
 * Evidence (2026-07 SERP research, TECHLOG): every data-page competitor winning
 * our head terms leads with an imperative verb + a live figure + the current
 * year + a freshness cue; Google truncates by pixels (~155 desktop / ~120
 * mobile) and rewrites ~65% of descriptions, but keeps ones that match on-page
 * content, and explicitly ENCOURAGES programmatic page-specific descriptions
 * for data sites. So: numbers first (inside the mobile window), our unique
 * primary-source claim as the payload, figures from the same hour-cached
 * alt_live_numbers() the on-page FAQ quotes (description matches body = fewer
 * rewrites), rounded DOWN so the claim can never overstate or go stale upward.
 *
 * Rank Math owns the description tag site-wide; we feed copy through its
 * filter instead of emitting a second tag (the 2.19.133 duplicate-OG lesson).
 * If Rank Math is inactive these filters simply never fire.
 */
function alt_tracker_meta_description($desc) {
    if (!is_page('ai-layoff-tracker')) return $desc;
    if (!function_exists('alt_live_numbers')) return $desc;
    $n = alt_live_numbers();
    // Early-year guard: with small totals the injected line reads worse than
    // the static field, so only take over once the figures carry weight.
    if (empty($n['jobs']) || (int) $n['jobs'] < 50000 || (int) $n['ai_jobs'] < 5000) return $desc;
    // Round DOWN, and round down from the SMALLER of the two bases. A "N+"
    // claim is only defensible if it sits under every figure on the page it
    // describes, and the page publishes its totals on the filing basis while
    // these figures are counted on the effective one. A 0 means the second
    // query found nothing, which is a reason to fall back to the one basis we
    // do have rather than floor the description to zero.
    $jobs_basis = ((int) ($n['jobs_filed'] ?? 0) > 0)
        ? min((int) $n['jobs'], (int) $n['jobs_filed']) : (int) $n['jobs'];
    $ai_basis   = ((int) ($n['ai_jobs_filed'] ?? 0) > 0)
        ? min((int) $n['ai_jobs'], (int) $n['ai_jobs_filed']) : (int) $n['ai_jobs'];
    $jobs = (int) (floor($jobs_basis / 10000) * 10000);
    $ai   = (int) (floor($ai_basis / 1000) * 1000);
    return sprintf(
        'Layoff tracker, updated daily: %s+ jobs cut in %d, %s+ tied to AI. Every number links to an SEC filing, WARN notice, or news report. Free.',
        number_format($jobs), (int) $n['y'], number_format($ai));
}
add_filter('rank_math/frontend/description', 'alt_tracker_meta_description', 20);
// Keep the social-card copy identical to the SERP copy.
add_filter('rank_math/opengraph/facebook/og_description', 'alt_tracker_meta_description', 20);
add_filter('rank_math/opengraph/twitter/twitter_description', 'alt_tracker_meta_description', 20);

/**
 * Is this request one of THIS tracker's pages?
 *
 * Everything below narrows on this deliberately. ONE WordPress install serves
 * both trackers and the whole blog, and the wrong og:image is a site-wide
 * default (Rank Math falls back to the site icon, a 512x512 crop, for every
 * page on the site). Fixing the default would silently restyle the sibling
 * tracker and every article. So we override per page, for our own URLs only,
 * and leave the shared default exactly as the owner set it.
 */
function alt_is_tracker_surface() {
    if (is_singular('layoffs')) return true;
    if (!is_page()) return false;
    $id = get_queried_object_id();
    if (!$id) return false;
    $path = wp_parse_url(get_permalink($id), PHP_URL_PATH);
    if (!$path) return false;
    $base = wp_parse_url(home_url('/ai-layoff-tracker/'), PHP_URL_PATH);
    return $base && 0 === strpos(trailingslashit($path), $base);
}

/**
 * The 1200x630 social card. Static by design: a rendered figure inside an image
 * is a number no cache ever refreshes, so the card carries the tracker's name
 * and its promise and lets the og:description carry the live numbers.
 */
function alt_social_card_url() {
    return ALT_PLUGIN_URL . 'assets/social-card.png?v=' . ALT_VERSION;
}

/**
 * Serve the real card instead of the shared 512x512 site-icon crop.
 *
 * The page already declared twitter:card=summary_large_image, so every share of
 * this tracker asked for a wide card and handed back a square icon: X and
 * LinkedIn then fall back to the small-summary layout, and the link renders as
 * a generic favicon tile.
 */
function alt_og_image($image) {
    return alt_is_tracker_surface() ? alt_social_card_url() : $image;
}
add_filter('rank_math/opengraph/facebook/og_image', 'alt_og_image', 20);
add_filter('rank_math/opengraph/facebook/og_image_secure_url', 'alt_og_image', 20);
add_filter('rank_math/opengraph/twitter/twitter_image', 'alt_og_image', 20);
add_filter('rank_math/opengraph/facebook/og_image_width', function ($w) {
    return alt_is_tracker_surface() ? 1200 : $w;
}, 20);
add_filter('rank_math/opengraph/facebook/og_image_height', function ($h) {
    return alt_is_tracker_surface() ? 630 : $h;
}, 20);
add_filter('rank_math/opengraph/facebook/og_image_type', function ($t) {
    return alt_is_tracker_surface() ? 'image/png' : $t;
}, 20);

/**
 * "Updated daily" has to be true in the metadata too.
 *
 * The page said "updated daily" four times in its own copy, and its Dataset
 * node carried a live dateModified, while the Article and WebPage nodes beside
 * it were frozen at the day the WordPress page was last hand-edited (2026-07-14)
 * and credited to a Person named "admin". The data changes twice a day; the
 * post row does not. So derive the date from the last actual write to the
 * table (alt_last_write, the same timestamp the on-page freshness label uses),
 * and attribute the page to the organisation that publishes it rather than to
 * a WordPress login name.
 *
 * Never invents a date: with no recorded write, every node is left untouched.
 */
function alt_json_ld_freshness($data, $jsonld = null) {
    if (!alt_is_tracker_surface() || !is_array($data)) return $data;
    $ts = (int) get_option('alt_last_write', 0);
    if ($ts <= 0) return $data;
    $iso = gmdate('c', $ts);

    // Prefer the site's existing Organization node so we point at one entity
    // rather than minting a competing publisher.
    $org = null;
    foreach ($data as $node) {
        if (!is_array($node) || empty($node['@type'])) continue;
        $types = (array) $node['@type'];
        if (in_array('Organization', $types, true) && !empty($node['@id'])) {
            $org = array('@id' => $node['@id']);
            break;
        }
    }
    if (null === $org) {
        $org = array('@type' => 'Organization', 'name' => get_bloginfo('name'), 'url' => home_url('/'));
    }

    foreach ($data as $key => $node) {
        if (!is_array($node) || empty($node['@type'])) continue;
        $types = (array) $node['@type'];
        if (!array_intersect($types, array('Article', 'NewsArticle', 'BlogPosting', 'WebPage', 'CollectionPage', 'ItemPage'))) {
            continue;
        }
        $data[$key]['dateModified'] = $iso;
        if (array_intersect($types, array('Article', 'NewsArticle', 'BlogPosting'))) {
            $data[$key]['author']    = $org;
            $data[$key]['publisher'] = $org;
            $data[$key]['image']     = array(
                '@type'  => 'ImageObject',
                'url'    => alt_social_card_url(),
                'width'  => 1200,
                'height' => 630,
            );
        }
    }
    return $data;
}
add_filter('rank_math/json_ld', 'alt_json_ld_freshness', 20, 2);

// og:updated_time is emitted from the post's modified date and was showing the
// same frozen 2026-07-14 stamp. Same source of truth as the JSON-LD above.
function alt_og_modified_time($t) {
    if (!alt_is_tracker_surface()) return $t;
    $ts = (int) get_option('alt_last_write', 0);
    return $ts > 0 ? gmdate('c', $ts) : $t;
}
add_filter('rank_math/opengraph/facebook/og_updated_time', 'alt_og_modified_time', 20);
add_filter('rank_math/opengraph/facebook/article_modified_time', 'alt_og_modified_time', 20);

/**
 * FAQ content shared by the FAQPage JSON-LD (wp_head) and the on-page FAQ
 * section (template) — one source so Google's "must match visible text" rule
 * holds. Numbers come from the live table, cached an hour.
 */
/**
 * Live headline figures (current-year job cuts + the AI-attributed subset),
 * cached an hour. Shared by the on-page FAQ and the SEO meta description so both
 * quote the SAME numbers - Google's "description must reflect the page" rule.
 */
// Declared in the PLUGIN, not a template: a template can be included more
// than once per request, and a function declaration there fatals the second
// time through (it took the press page down with a 500).
if (!function_exists('alt_country_flag')) {
/**
 * Country flag for press copy. Regional-indicator emoji, so it degrades to two
 * letters on platforms without flag glyphs (Windows) rather than to a blank box.
 * The country name is always printed alongside, so the flag is decoration and
 * never the only carrier of meaning.
 */
function alt_country_flag($country) {
    static $map = array(
        'World' => "\xF0\x9F\x8C\x90", 'Worldwide' => "\xF0\x9F\x8C\x90",
        'United States' => 'US', 'Germany' => 'DE', 'United Kingdom' => 'GB',
        'France' => 'FR', 'Canada' => 'CA', 'Australia' => 'AU', 'India' => 'IN',
        'Ireland' => 'IE', 'Netherlands' => 'NL', 'Spain' => 'ES', 'Italy' => 'IT',
        'Poland' => 'PL', 'Sweden' => 'SE', 'Norway' => 'NO', 'Denmark' => 'DK',
        'Finland' => 'FI', 'Belgium' => 'BE', 'Austria' => 'AT', 'Switzerland' => 'CH',
        'Portugal' => 'PT', 'Japan' => 'JP', 'South Korea' => 'KR', 'China' => 'CN',
        'Brazil' => 'BR', 'Mexico' => 'MX', 'Singapore' => 'SG', 'Israel' => 'IL',
        'New Zealand' => 'NZ', 'South Africa' => 'ZA', 'Nigeria' => 'NG',
        'Czechia' => 'CZ', 'Romania' => 'RO', 'Hungary' => 'HU', 'Greece' => 'GR',
    );
    $c = trim((string) $country);
    if (!isset($map[$c])) return '';
    $v = $map[$c];
    if (strlen($v) !== 2 || !ctype_upper($v)) return $v;   // already an emoji
    $flag = '';
    foreach (str_split($v) as $ch) {
        // html_entity_decode, not mb_convert_encoding(HTML-ENTITIES): that
        // idiom is deprecated on PHP 8.2+ and would emit notices on every load.
        $flag .= html_entity_decode('&#' . (127397 + ord($ch)) . ';', ENT_QUOTES, 'UTF-8');
    }
    return $flag;
}
}

function alt_live_numbers() {
    $n = get_transient('alt_faq_numbers');
    if (!is_array($n)) {
        global $wpdb;
        $t = alt_db_table();
        $y = (int) gmdate('Y');
        // The copy built from this row says "verified ... so far": announced-tier
        // rows are excluded (the FAQ itself promises they are never mixed into
        // verified totals), and future-dated effective dates (WARN files ahead)
        // don't count toward "so far". Keeps this answer consistent with the
        // press page's documented-floor figure for the same window.
        //
        // THE BASIS THIS ANSWER IS COUNTED ON, AND WHY IT IS NOT THE PAGE'S.
        //
        // YEAR(layoff_date) is the EFFECTIVE basis and it is deliberate. The
        // tracker page this FAQ is printed on defaults to the FILING basis
        // (date_basis=notice) since 2.20.4, so these are two answers to two
        // different questions sitting inches apart. Measured live on
        // 2026-08-12, before this comment existed: this query published
        // 479,410 verified job cuts for 2026 inside FAQPage JSON-LD while the
        // cite line a few pixels below published 445,869 for the same year and
        // the same geography. 33,541 apart, 7.5 percent, both worded "so far
        // in 2026 ... worldwide", and the structured-data one is the one a
        // search engine quotes with none of the page around it.
        //
        // Two ways to close that. This is the one taken: KEEP the basis, NAME
        // it, in both places.
        //
        //  * The question is "how many layoffs have there been in <year> so
        //    far", and the plain reading of that is cuts that have happened,
        //    not notices that were filed. That is an effective-date question.
        //    Same reasoning that kept to_date_* on this basis in 2.20.11
        //    instead of moving it along with the default.
        //  * These figures are also the press page's and the report page's
        //    documented floor for the same window, and 2.20.11 pinned those
        //    surfaces' receipt links to date_basis=effective for exactly that
        //    reason. Moving this one alone would put the structured data on a
        //    third footing rather than a shared one.
        //  * This function has no WP_REST_Request to take a basis from. It is
        //    an hour-long transient rendered into the head. "Follow the page
        //    default" would mean following a constant that has already moved
        //    once, silently changing a published, search-quoted number with no
        //    label to explain the move. A basis written down here changes only
        //    when somebody edits here.
        //
        // So the SQL stays and alt_faq_items() states the basis in the answer
        // text, in the same words the hero and the cite line use, and says the
        // page's own totals answer the other question.
        // railway/tests/test_date_basis_default.py section 4b derives the label
        // from THIS column, so the words cannot outlive a change to the SQL.
        $row = $wpdb->get_row($wpdb->prepare(
            "SELECT COUNT(*) entries, COALESCE(SUM(job_count),0) jobs,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs
             FROM $t WHERE superset_of = 0 AND announced = 0
               AND YEAR(layoff_date) = %d AND layoff_date <= %s",
            $y, gmdate('Y-m-d')));
        // THE SAME WINDOW ON THE PAGE'S OWN BASIS, for the meta description's
        // floor and for nothing else.
        //
        // The FAQ answers an effective-date question and says so (above). The
        // SERP description makes a LOOSER claim, "N+ jobs cut in <year>", with
        // no room in 155 pixels to name a basis, so the only thing that keeps
        // it honest is being a floor under every figure a reader can see on the
        // page. Rounding down 10,000 was doing that against the FAQ's number
        // only. On 2026-08-12 the effective to-date figure was 479,410 and the
        // filed one 445,869: floor-of-479,410 is 470,000, which is ABOVE the
        // cite line. Nothing enforced the gap and nothing measured it.
        //
        // So the same window is measured on both bases here, in the same hour
        // transient (one extra indexed COUNT per hour, and the description then
        // floors on the smaller). COALESCE(announcement_date, layoff_date) is
        // alt_db_date_col()'s 'notice' expression written out: this file cannot
        // call it without a WP_REST_Request, and a hand-typed copy of a date
        // basis is the exact defect 2.20.11 and 2.20.12 were both about, so it
        // is named here and pinned by test_date_basis_default.py section 4b.
        $row_filed = $wpdb->get_row($wpdb->prepare(
            "SELECT COUNT(*) entries, COALESCE(SUM(job_count),0) jobs,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs
             FROM $t WHERE superset_of = 0 AND announced = 0
               AND YEAR(COALESCE(announcement_date, layoff_date)) = %d
               AND layoff_date <= %s",
            $y, gmdate('Y-m-d')));
        // MIN(layoff_date) is guarded against the sentinel/zero dates that a bad
        // parse can leave behind, so the published coverage start is a real event.
        $all = $wpdb->get_row(
            "SELECT COUNT(*) entries,
                    MIN(CASE WHEN layoff_date > '2000-01-01' THEN layoff_date END) min_date
             FROM $t WHERE superset_of = 0");
        // Coverage counts are NOT recomputed here. This function used to run
        // its own COUNT(DISTINCT country) and COUNT(DISTINCT state) over every
        // row, which produced 58 countries (the "Multiple countries" bucket is
        // not a country) and 50 states (that is every state appearing in ANY
        // row, while the sentence quoting it is about WARN notices). Both went
        // out inside FAQPage JSON-LD. One helper owns these two numbers now.
        $cov = alt_coverage_counts();
        $n = array(
            'y'         => $y,
            'entries'   => $row ? (int) $row->entries : 0,
            'jobs'      => $row ? (int) $row->jobs : 0,
            'ai_jobs'   => $row ? (int) $row->ai_jobs : 0,
            // The same window counted on the page's own basis. Used ONLY as the
            // meta description's floor; no visible copy quotes these, because a
            // second unlabelled total is the defect, not the fix.
            'jobs_filed'    => $row_filed ? (int) $row_filed->jobs : 0,
            'ai_jobs_filed' => $row_filed ? (int) $row_filed->ai_jobs : 0,
            'all'       => $all ? (int) $all->entries : 0,
            'countries' => (int) $cov['countries'],
            'states'    => (int) $cov['states'],
            // The dataset actually reaches back to 2002; every surface used to
            // hardcode 2015, understating our own coverage by 13 years and
            // ~18,000 events. Derive it instead of asserting it.
            'start'     => ($all && $all->min_date) ? substr($all->min_date, 0, 4) : '2015',
        );
        set_transient('alt_faq_numbers', $n, HOUR_IN_SECONDS);
    }
    return $n;
}

function alt_faq_items() {
    $n = alt_live_numbers();
    $f = function ($v) { return number_format((float) $v); };
    return array(
        array('What is the AI Layoff Tracker?',
            'A free, continuously updated layoff tracker covering verified job cuts worldwide across all industries and causes. It flags which layoffs companies explicitly attribute to AI or automation. Every entry links to a primary source: a SEC 8-K filing, a US state WARN notice, or a named news outlet with the exact quote.'),
        // The basis wording here is not decoration. This answer is the one that
        // ships as FAQPage JSON-LD, and a search engine quotes it with none of
        // the page around it, so it has to carry its own basis the way the
        // hero, the cite line and the at-a-glance board carry theirs. Both
        // phrases are byte-identical to the ones the rest of the page writes
        // ("counted by effective date" is BASIS_COPY.effective.headline in
        // layoffs.js; "counted by filing date" is $alt_hero_basis in
        // page-tracker.php), and "not meant to match" is the board footnote's
        // wording for the same situation. See alt_live_numbers() for why this
        // figure stayed on the effective basis and what the gap measured.
        array('How many layoffs have there been in ' . $n['y'] . ' so far?',
            'So far in ' . $n['y'] . ' the tracker holds ' . $f($n['entries']) . ' verified layoff entries totaling ' . $f($n['jobs']) . ' job cuts worldwide, counted by effective date: the day each cut takes effect, with anything dated later than today left out. Companies explicitly blamed AI for ' . $f($n['ai_jobs']) . ' of those cuts. The totals on the tracker page itself are counted by filing date by default, which is a different question and a different number for the same year, so the two are not meant to match; the date basis switch on the page moves between them. Totals update daily as new filings and reports are verified.'),
        array('Where does the layoff data come from?',
            'Four kinds of sources. SEC 8-K filings, searched twice daily. Official WARN notices from ' . alt_warn_states_phrase() . ', imported daily with no AI processing. The European Restructuring Monitor, which is Eurofound\'s official per-company database of announced restructuring across the EU27, Norway and historically the UK (imported daily and credited to Eurofound; because these are announcement-stage figures, they feed the separately labeled "Announced" tier and never the verified totals). And worldwide press coverage in 65+ languages through the GDELT news index plus Google News, read across 45 national editions. The dataset spans ' . $n['start'] . ' to the present across ' . $f($n['countries']) . ' countries, ' . $f($n['all']) . ' entries in total.'),
        array('What sources do you use?',
            'Official government filings and legally required notices first: every SEC 8-K/6-K filing, official WARN mass-layoff notices from ' . alt_warn_states_phrase() . ' (each a live link on our Data Sources page), and the EU\'s Eurofound restructuring monitor. Worldwide, we add named news coverage in 65+ languages from an editorially maintained trusted-outlet allowlist. Nothing is estimated; every number links back to one of these. The Data Sources page lists each one, with links to check the raw source yourself.',
            array('ai-layoff-tracker/sources/', 'See the full Data Sources page &rarr;')),
        array('How is this different from other layoff trackers?',
            'Announcement surveys count corporate intentions on the day of the announcement. This job layoff tracker counts what has a verifiable document or quoted primary source behind it, so it is a documented floor rather than an estimate. Announcement-stage cuts are also tracked, but in a separately labeled tier that is never mixed into the verified totals.'),
        array('Why is our number different from other layoff trackers?',
            'Three reasons, and all of them point toward a number you can check. First, we require a document behind every row, so a cut with no filing and no named report never enters the total. Second, we are deliberately conservative and land within about 10 percent of independent WARN trackers, so our figure is a floor you can trust rather than a high estimate. Third, we never inflate a total by counting a company-wide headcount on every state filing: when one notice lists a nationwide figure, we count only the jobs in that state, so one layoff is never summed several times. A tracker reporting several times higher is usually doing exactly that.'),
        array('What if a source only says "up to" a number?',
            'We record the figure the source states and keep its qualifying words with the entry, because inventing a lower number would be a guess and dropping the entry would hide a real cut. So a report of "up to 600 roles" is stored as 600 with that wording retained, which makes it a ceiling rather than a measured total. This is the one place our figures can read high, so we name it rather than bury it. Where a source gives a true range ("400 to 500"), we take the lower bound and keep the upper bound in the data as well.'),
        array('How do you check your own accuracy?',
            'By auditing ourselves against our own sources. Every month an automated audit draws a random, stratified sample of published entries and re-opens every cited source to confirm the company, the number and the date. Entries from official filings and notices consistently match exactly; anything that fails is corrected or removed, usually the same day, and the correction is disclosed in the log below. The latest audit result is always published live on the Tracker Health page, so the number you see there is current, not a snapshot.',
            array('ai-layoff-tracker/ai-tracker-health/', 'See the latest audit result &rarr;')),
        array('Can journalists and researchers use this data?',
            'Yes, free with attribution to asktherecruiter.com (CC BY 4.0). Filtered or full CSV and JSON downloads are on the page, and a public REST API serves the same data. Corrected entries are publicly flagged, and every correction to published figures is disclosed in the on-page corrections log.'),
        array('How often is the tracker updated?',
            'Continuously. News and SEC filings are collected twice daily (morning and after US market close, ET); official WARN notices and Eurofound ERM records import daily; and the daily summary, stats, charts and table read live data on every page load. The Tracker Health page shows every collector\'s latest run in real time.'),
        array('What is the difference between "verified" and "announced" job cuts?',
            'Verified cuts have a filing or independently reported source behind them: a WARN notice, an SEC filing, or a named outlet\'s report of cuts taking place. Announced cuts are company plans reported at announcement stage, tracked in their own labeled tier and never mixed into the verified totals, because announced plans can shrink, stretch over years, or partially happen through attrition.'),
        array('How do I report an error?',
            'Use the contact page and corrections get priority. Every entry links to its primary source, so you can check any number against the underlying document.'),
    );
}

/**
 * THE coverage counts. Every surface that publishes "N countries" or "N US
 * states" reads this function and nothing else.
 *
 * Why it is written down: the same two claims used to be computed in three
 * places and all three disagreed on the live page. The FAQ (and the FAQPage
 * JSON-LD built from it, so this shipped as structured data) said WARN notices
 * came from 50 US states, because it counted DISTINCT state over EVERY row
 * including news and SEC entries, which is not a WARN claim at all. The
 * methodology block said "48 US states and DC" by counting the configured
 * register map, whose 48 keys ALREADY include DC, so DC was counted twice and
 * no such 48th state exists. The coverage ribbon said 47, from this function,
 * which is the only one of the three that measures what the sentence claims:
 * jurisdictions that have actually produced WARN rows.
 *
 * Countries excludes the "Multiple countries" bucket, which is a placeholder
 * for events we could not localise, not a place.
 *
 * Fields:
 *   countries  real countries present in the data
 *   states     WARN jurisdictions with data, DC included (the ribbon figure)
 *   us_states  the same, minus DC, so copy can say "N states and DC" honestly
 *   dc         whether DC is among them
 *   first      earliest event date, for the coverage ribbon
 * Cached an hour; the write path drops the transient on ingest.
 */
function alt_coverage_counts() {
    $c = get_transient('alt_coverage_counts');
    // isset() guard: a transient written before a field existed must recompute
    // rather than hand a surface an empty value for up to an hour.
    if (is_array($c) && isset($c['first']) && isset($c['us_states'])) return $c;
    global $wpdb;
    $t = alt_db_table();
    $countries = (int) $wpdb->get_var(
        "SELECT COUNT(DISTINCT country) FROM $t WHERE country <> '' AND country <> 'Multiple countries'");
    $states = (int) $wpdb->get_var(
        "SELECT COUNT(DISTINCT state) FROM $t WHERE source_type = 'warn' AND state <> ''");
    // DC is a WARN jurisdiction but not a state, and the difference is the
    // whole reason the old "48 US states and DC" line was wrong. Derive it.
    $dc = 'DC' === (string) $wpdb->get_var(
        "SELECT state FROM $t WHERE source_type = 'warn' AND state = 'DC' LIMIT 1");
    // First record date for the coverage ribbon. Derived, never typed; the
    // same date bound alt_db_valid_date enforces on the way in.
    $first = (string) $wpdb->get_var(
        "SELECT MIN(layoff_date) FROM $t WHERE layoff_date IS NOT NULL");
    $c = array(
        'countries' => $countries,
        'states'    => $states,
        'us_states' => max(0, $states - ($dc ? 1 : 0)),
        'dc'        => $dc,
        'first'     => $first,
    );
    set_transient('alt_coverage_counts', $c, HOUR_IN_SECONDS);
    return $c;
}

/**
 * The WARN coverage claim as a sentence fragment, so no surface has to
 * reassemble it and get the DC arithmetic wrong again. Returns e.g.
 * "46 US states and DC" (or plain "N US states" if DC ever drops out).
 */
function alt_warn_states_phrase() {
    $c = alt_coverage_counts();
    if (!empty($c['dc'])) {
        return number_format_i18n((int) $c['us_states']) . ' US states and DC';
    }
    return number_format_i18n((int) $c['states']) . ' US states';
}

/**
 * Render single layoff entries (/blog/layoff/{company}-{date}) with the plugin's
 * own template so each event has a clean, citable permalink page.
 */
function alt_single_template($template) {
    if (is_singular('layoffs')) {
        $custom = ALT_PLUGIN_DIR . 'templates/single-layoff.php';
        if (file_exists($custom)) {
            return $custom;
        }
    }
    return $template;
}
add_filter('single_template', 'alt_single_template');

/**
 * Small admin page (Tools → AI Layoff Tracker) showing the API key the
 * Railway pipeline authenticates with, plus entry counts.
 */
function alt_register_admin_page() {
    add_management_page(
        'AI Layoff Tracker',
        'AI Layoff Tracker',
        'manage_options',
        'alt-settings',
        'alt_render_admin_page'
    );
}
add_action('admin_menu', 'alt_register_admin_page');

// Site-admin QoL (2026-07-27): Complianz ("Website Scan") and Rank Math ("SEO
// Details") each add a wide column to the Posts list (edit.php). Under the core
// table-layout:auto they steal all the horizontal space and squeeze the Title
// column until it wraps one word per line. A hard min-width floor on Title is
// the robust lever - the browser can never shrink it below that - plus a cap on
// the two heavy plugin columns. Scoped to admin_head-edit.php ONLY, so it can
// never affect the front end or any other admin screen. Pure CSS, no markup.
add_action('admin_head-edit.php', 'alt_fix_posts_list_column_widths');
function alt_fix_posts_list_column_widths() {
    echo '<style id="alt-posts-list-fix">'
        . '.wp-list-table .column-title{min-width:220px;width:24%;}'
        . '.wp-list-table .column-title a.row-title{word-break:normal;overflow-wrap:anywhere;}'
        . '.wp-list-table .column-cmplz_scan,'
        . '.wp-list-table .column-rank_math_seo_details{max-width:120px;overflow:hidden;text-overflow:ellipsis;}'
        . '</style>';
}

function alt_render_admin_page() {
    if (!current_user_can('manage_options')) return;

    if (isset($_POST['alt_regenerate_key']) && check_admin_referer('alt_regenerate_key')) {
        update_option('alt_api_key', bin2hex(random_bytes(32)), false);
        echo '<div class="notice notice-success"><p>New API key generated. Update WP_API_KEY in Railway.</p></div>';
    }

    $key   = alt_get_api_key();
    $count = wp_count_posts('layoffs');
    $total = isset($count->publish) ? (int) $count->publish : 0;
    ?>
    <div class="wrap">
        <h1>AI Layoff Tracker</h1>
        <p><strong><?php echo esc_html(number_format_i18n($total)); ?></strong> published layoff entries.</p>
        <h2>Pipeline API key</h2>
        <p>Copy this value into the Railway environment variable <code>WP_API_KEY</code>.
           Requests must send it in the <code>X-Layoff-API-Key</code> header.</p>
        <input type="text" readonly class="regular-text code" style="width:520px"
               value="<?php echo esc_attr($key); ?>" onfocus="this.select();">
        <?php if (defined('AI_LAYOFF_API_KEY') && AI_LAYOFF_API_KEY) : ?>
            <p><em>Note: <code>AI_LAYOFF_API_KEY</code> is defined in wp-config.php and overrides the stored option.</em></p>
        <?php endif; ?>
        <form method="post" style="margin-top:12px;">
            <?php wp_nonce_field('alt_regenerate_key'); ?>
            <button type="submit" name="alt_regenerate_key" value="1" class="button"
                    onclick="return confirm('Regenerate the key? The Railway pipeline will stop authenticating until WP_API_KEY is updated.');">
                Regenerate key
            </button>
        </form>
        <h2>Endpoints</h2>
        <ul style="list-style:disc;padding-left:20px;">
            <li><code>POST <?php echo esc_html(rest_url('layoffs/v1/add')); ?></code> (key required)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/check-duplicate')); ?></code> (key required)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/all')); ?></code> (public)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/stats')); ?></code> (public)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/company/{name}')); ?></code> (public)</li>
        </ul>
    </div>
    <?php
}
