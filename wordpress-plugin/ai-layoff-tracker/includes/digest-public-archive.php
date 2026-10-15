<?php
/**
 * The public digest archive: /ai-layoff-tracker/digest/ and
 * /ai-layoff-tracker/digest/YYYY-MM-DD/ (owner decision 2026-10-15).
 *
 * Each SENT daily or weekly email is saved at send time by
 * railway/digest_archive.post_public_record, through the keyed
 * POST /layoffs/v1/digest-archive. What arrives is already cleaned in Python;
 * this file checks it AGAIN (alt_digest_pub_is_public) and refuses a record
 * that could carry anything belonging to one reader: an address, an
 * unsubscribe or preferences link, a signed query string, or any image other
 * than the edition's own chart PNGs. Two independent gates, because the cost
 * of a miss is a reader's subscription published on the open web.
 *
 * One page per date. When a daily and a weekly edition share a date, the
 * weekly (the larger edition) is the page and a daily never replaces it.
 *
 * The pages are standalone documents in the shared email theme (the same
 * tokens as railway/email_theme.py), server-rendered, no JavaScript. The hub
 * filters by date range with plain GET parameters; a filtered view is
 * noindex and canonicalises to the hub so the filter cannot mint duplicates.
 */
if (!defined('ABSPATH')) exit;

function alt_digest_pub_table() {
    global $wpdb;
    return $wpdb->prefix . 'alt_digest_public';
}

function alt_digest_pub_table_ready() {
    global $wpdb;
    $table = alt_digest_pub_table();
    if ($wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table) {
        return true;
    }
    if (!function_exists('dbDelta')) {
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    }
    if (!function_exists('dbDelta')) return false;
    $charset = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE $table (
        edition_date DATE NOT NULL,
        kind VARCHAR(6) NOT NULL DEFAULT 'daily',
        period_from DATE NULL,
        subject VARCHAR(300) NOT NULL DEFAULT '',
        html LONGTEXT NOT NULL,
        body_text LONGTEXT NOT NULL,
        charts LONGTEXT NULL,
        saved_at DATETIME NOT NULL,
        PRIMARY KEY (edition_date)
    ) $charset;");
    return $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table;
}

/* ------------------------------------------------------------------ */
/* Pure helpers (tested from railway/tests/test_digest_public_archive) */
/* ------------------------------------------------------------------ */

/** PURE. A real calendar date in YYYY-MM-DD, or ''. */
function alt_digest_pub_valid_date($d) {
    $d = trim((string) $d);
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $d, $m)) return '';
    return checkdate((int) $m[2], (int) $m[3], (int) $m[1]) ? $d : '';
}

/**
 * PURE. True only when nothing in the record can belong to one reader.
 * The Python side cleans; this is the second, independent gate.
 */
function alt_digest_pub_is_public($html, $text) {
    $blob = (string) $html . "\n" . (string) $text;
    $low = strtolower($blob);
    if (preg_match('/[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/', $blob)) return false;
    foreach (array('unsub', 'alt_digest_', 'preferences/', 'mailto:', '<script',
                   '<iframe', '<link', '<object', '<embed', '<form', 'url(',
                   'javascript:') as $needle) {
        if (strpos($low, $needle) !== false) return false;
    }
    if (preg_match('/[?&](?:t|token|sig|signature|key|uid|rid|email|e)=/i', $blob)) return false;
    if (preg_match_all('/<img\b[^>]*>/i', (string) $html, $imgs)) {
        foreach ($imgs[0] as $img) {
            if (!preg_match('/^<img src="cid:chart-[1-3]"[^>]*\balt="[^"]+"[^>]*>$/i', $img)) {
                return false;
            }
        }
    }
    return true;
}

/** PURE. Charts as {n: {alt, png bytes}}; anything that is not a small PNG is dropped. */
function alt_digest_pub_decode_charts($charts) {
    $out = array();
    foreach ((array) $charts as $c) {
        if (!is_array($c)) continue;
        $n = (int) ($c['n'] ?? 0);
        if ($n < 1 || $n > 3) continue;
        $png = base64_decode((string) ($c['png'] ?? ''), true);
        if ($png === false || strlen($png) > 400000 || substr($png, 0, 8) !== "\x89PNG\r\n\x1a\n") continue;
        $out[$n] = array('alt' => (string) ($c['alt'] ?? ''), 'png' => $png);
    }
    ksort($out);
    return $out;
}

/** PURE. The edition body with each inline chart pointed at our own URL. */
function alt_digest_pub_body($html, $chart_base) {
    return preg_replace_callback('/src="cid:chart-([1-3])"/', function ($m) use ($chart_base) {
        return 'src="' . htmlspecialchars($chart_base . 'chart-' . $m[1] . '.png', ENT_QUOTES) . '"';
    }, (string) $html);
}

/** PURE. Rows (newest first) inside [from, to]; an empty bound is open. */
function alt_digest_pub_filter_range($rows, $from, $to) {
    $from = alt_digest_pub_valid_date($from);
    $to = alt_digest_pub_valid_date($to);
    $out = array();
    foreach ((array) $rows as $r) {
        $d = (string) ($r['edition_date'] ?? '');
        if ($from !== '' && $d < $from) continue;
        if ($to !== '' && $d > $to) continue;
        $out[] = $r;
    }
    usort($out, function ($a, $b) { return strcmp($b['edition_date'], $a['edition_date']); });
    return $out;
}

/** PURE. Should an incoming record replace the stored one for that date? */
function alt_digest_pub_should_replace($stored_kind, $incoming_kind) {
    if ($stored_kind === '' || $stored_kind === null) return true;
    if ($stored_kind === 'weekly' && $incoming_kind === 'daily') return false;
    return true;
}

function alt_digest_pub_hub_url() {
    return home_url('/ai-layoff-tracker/digest/');
}

function alt_digest_pub_url($date) {
    return home_url('/ai-layoff-tracker/digest/' . $date . '/');
}

/** PURE given its inputs. NewsArticle + Dataset JSON-LD for one edition. */
function alt_digest_pub_jsonld($row, $url, $image_urls, $saved_iso) {
    $publisher = array('@type' => 'Organization', 'name' => 'AskTheRecruiter',
                       'url' => 'https://asktherecruiter.com/');
    $headline = (string) $row['subject'];
    $from = (string) ($row['period_from'] ?: $row['edition_date']);
    $article = array(
        '@context' => 'https://schema.org',
        '@type' => 'NewsArticle',
        'headline' => mb_substr($headline, 0, 110),
        'datePublished' => $saved_iso,
        'dateModified' => $saved_iso,
        'mainEntityOfPage' => $url,
        'url' => $url,
        'author' => $publisher,
        'publisher' => $publisher,
        'isAccessibleForFree' => true,
    );
    if ($image_urls) $article['image'] = array_values($image_urls);
    $dataset = array(
        '@context' => 'https://schema.org',
        '@type' => 'Dataset',
        'name' => 'AI Layoff Tracker digest figures, ' . $from . ' to ' . $row['edition_date'],
        'description' => 'Verified layoff figures summarised in the AI Layoff Tracker '
            . $row['kind'] . ' email digest for ' . $from . ' to ' . $row['edition_date']
            . ', drawn from SEC filings, state WARN notices and named news reports.',
        'url' => $url,
        'temporalCoverage' => $from . '/' . $row['edition_date'],
        'creator' => $publisher,
        'isAccessibleForFree' => true,
        'license' => 'https://creativecommons.org/licenses/by/4.0/',
        'isPartOf' => array('@type' => 'Dataset', 'name' => 'AI Layoff Tracker',
                            'url' => home_url('/ai-layoff-tracker/')),
    );
    return array($article, $dataset);
}

/* ------------------------------------------------------------------ */
/* Storage                                                             */
/* ------------------------------------------------------------------ */

function alt_digest_pub_get($date) {
    global $wpdb;
    if (!alt_digest_pub_table_ready()) return null;
    $row = $wpdb->get_row($wpdb->prepare(
        'SELECT * FROM ' . alt_digest_pub_table() . ' WHERE edition_date = %s', $date), ARRAY_A);
    return $row ?: null;
}

function alt_digest_pub_all() {
    global $wpdb;
    if (!alt_digest_pub_table_ready()) return array();
    $rows = $wpdb->get_results('SELECT edition_date, kind, period_from, subject, saved_at FROM '
        . alt_digest_pub_table() . ' ORDER BY edition_date DESC LIMIT 2000', ARRAY_A);
    return is_array($rows) ? $rows : array();
}

function alt_api_digest_archive($request) {
    $p = $request->get_json_params();
    if (!is_array($p)) return new WP_Error('alt_bad', 'JSON body required', array('status' => 400));
    $date = alt_digest_pub_valid_date($p['date'] ?? '');
    $kind = in_array(($p['kind'] ?? ''), array('daily', 'weekly'), true) ? $p['kind'] : '';
    $html = (string) ($p['html'] ?? '');
    $text = (string) ($p['text'] ?? '');
    $subject = trim(wp_strip_all_tags((string) ($p['subject'] ?? '')));
    if ($date === '' || $kind === '' || $html === '' || $subject === '') {
        return new WP_Error('alt_bad', 'date, kind, subject and html are required', array('status' => 400));
    }
    if (strlen($html) > 400000 || strlen($text) > 200000) {
        return new WP_Error('alt_bad', 'record too large', array('status' => 413));
    }
    if (!alt_digest_pub_is_public($html, $text)) {
        return new WP_Error('alt_private', 'record carries reader-specific content; refused',
                            array('status' => 422));
    }
    if (!alt_digest_pub_table_ready()) {
        return new WP_Error('alt_table', 'archive table unavailable', array('status' => 503));
    }
    $stored = alt_digest_pub_get($date);
    if ($stored && !alt_digest_pub_should_replace($stored['kind'], $kind)) {
        return array('ok' => true, 'kept' => $stored['kind'], 'url' => alt_digest_pub_url($date));
    }
    $charts = array();
    foreach (alt_digest_pub_decode_charts($p['charts'] ?? array()) as $n => $c) {
        $charts[] = array('n' => $n, 'alt' => $c['alt'], 'png' => base64_encode($c['png']));
    }
    global $wpdb;
    $wpdb->replace(alt_digest_pub_table(), array(
        'edition_date' => $date,
        'kind' => $kind,
        'period_from' => alt_digest_pub_valid_date($p['period_from'] ?? '') ?: null,
        'subject' => mb_substr($subject, 0, 300),
        'html' => $html,
        'body_text' => $text,
        'charts' => wp_json_encode($charts),
        'saved_at' => current_time('mysql', true),
    ));
    if (function_exists('alt_indexnow_submit_urls')) {
        alt_indexnow_submit_urls(array(alt_digest_pub_url($date), alt_digest_pub_hub_url()),
                                 'alt_indexnow_digest_last');
    }
    return array('ok' => true, 'url' => alt_digest_pub_url($date), 'charts' => count($charts));
}

add_action('rest_api_init', function () {
    register_rest_route('layoffs/v1', '/digest-archive', array(
        'methods' => 'POST',
        'callback' => 'alt_api_digest_archive',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
});

/* ------------------------------------------------------------------ */
/* Routes                                                              */
/* ------------------------------------------------------------------ */

add_action('init', function () {
    add_rewrite_rule('^ai-layoff-tracker/digest/?$', 'index.php?alt_digest_pub=hub', 'top');
    add_rewrite_rule('^ai-layoff-tracker/digest/([0-9]{4}-[0-9]{2}-[0-9]{2})/?$',
                     'index.php?alt_digest_pub=page&alt_digest_date=$matches[1]', 'top');
    add_rewrite_rule('^ai-layoff-tracker/digest/([0-9]{4}-[0-9]{2}-[0-9]{2})/chart-([1-3])\.png$',
                     'index.php?alt_digest_pub=chart&alt_digest_date=$matches[1]&alt_digest_chart=$matches[2]', 'top');
    add_rewrite_rule('^layoff-digest-sitemap\.xml$', 'index.php?alt_digest_pub=sitemap', 'top');
    if (get_option('alt_digest_pub_rewrite_ver') !== ALT_VERSION) {
        update_option('alt_digest_pub_rewrite_ver', ALT_VERSION, false);
        if (function_exists('alt_request_rewrite_flush')) alt_request_rewrite_flush();
    }
}, 2);

add_filter('query_vars', function ($vars) {
    $vars[] = 'alt_digest_pub';
    $vars[] = 'alt_digest_date';
    $vars[] = 'alt_digest_chart';
    return $vars;
});

function alt_digest_pub_css() {
    // The shared email theme tokens (railway/email_theme.py), as page CSS.
    return ':root{color-scheme:light dark}'
        . 'body{margin:0;background:#f3f4f6;color:#111827;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.55}'
        . '.w{max-width:600px;margin:0 auto;padding:20px 16px 40px}'
        . '.bar{font-size:14px;margin:0 0 14px}.bar a{color:#1d4ed8}'
        . '.card{background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;padding:20px}'
        . 'h1{font-size:24px;line-height:1.25;margin:2px 0 6px}'
        . '.wm{font-variant:small-caps;letter-spacing:.08em;font-size:12px;font-weight:600;color:#4b5563;margin:0}'
        . '.muted{color:#4b5563;font-size:14px}'
        . 'a{color:#1d4ed8}'
        . 'ul.list{list-style:none;padding:0;margin:0}ul.list li{padding:10px 0;border-top:1px solid #e5e7eb}'
        . 'ul.list li:first-child{border-top:0}'
        . 'form.f{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin:0 0 16px}'
        . 'form.f label{font-size:13px;color:#4b5563;display:flex;flex-direction:column;gap:4px}'
        . 'form.f input{font:inherit;padding:6px 8px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;color:#111827}'
        . 'form.f button{font:inherit;padding:7px 14px;border:0;border-radius:8px;background:#1d4ed8;color:#fff;cursor:pointer}'
        . '.ed{overflow-x:auto}.ed img{max-width:100%;height:auto}'
        . '.nav{display:flex;justify-content:space-between;gap:12px;margin:16px 0 0;font-size:14px}'
        . '@media (prefers-color-scheme: dark){'
        . 'body{background:#0b1220;color:#e5e7eb}.card{background:#111a2e;border-color:#111a2e}'
        . '.wm,.muted,form.f label{color:#9ca3af}a,.bar a{color:#93c5fd}'
        . 'ul.list li{border-color:#1f2a44}form.f input{background:#0b1220;color:#e5e7eb;border-color:#1f2a44}'
        . 'form.f button{background:#93c5fd;color:#0b1220}'
        . '}';
}

function alt_digest_pub_head($title, $desc, $canonical, $robots, $jsonld = array()) {
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<meta name="color-scheme" content="light dark">'
        . '<title>' . esc_html($title) . '</title>'
        . '<meta name="description" content="' . esc_attr($desc) . '">'
        . '<meta name="robots" content="' . esc_attr($robots) . '">'
        . '<link rel="canonical" href="' . esc_url($canonical) . '">';
    foreach ($jsonld as $node) {
        echo '<script type="application/ld+json">'
            . wp_json_encode($node, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) . '</script>';
    }
    echo '<style>' . alt_digest_pub_css();
    // The email body's own dark-mode classes, so an edition reads in dark too.
    if (function_exists('alt_digest_pub_email_dark_css')) echo alt_digest_pub_email_dark_css();
    echo '</style></head><body><div class="w">'
        . '<p class="bar"><a href="' . esc_url(home_url('/ai-layoff-tracker/')) . '">AI Layoff Tracker</a>'
        . ' &middot; <a href="' . esc_url(alt_digest_pub_hub_url()) . '">Digest archive</a></p>';
}

function alt_digest_pub_email_dark_css() {
    return '@media (prefers-color-scheme: dark){'
        . '.ed .et-page{background-color:#0b1220!important}'
        . '.ed .et-card{background-color:#111a2e!important;border-color:#111a2e!important}'
        . '.ed .et-card p,.ed .et-card td,.ed .et-card li,.ed .et-card h2,.ed .et-card h3{color:#e5e7eb!important}'
        . '.ed .et-muted{color:#9ca3af!important}.ed .et-card a{color:#93c5fd!important}'
        . '.ed .et-rule{border-color:#1f2a44!important}'
        . '.ed [style*="background-color:#ecfdf3"]{background-color:#0f2a1d!important}'
        . '.ed [bgcolor="#e4e7ec"]{background-color:#26324d!important}'
        . '.ed [style*="background-color:#f3f4f6"]{background-color:#0b1220!important}'
        . '.ed [style*="background-color:#ffffff"]{background-color:#111a2e!important}'
        . '}';
}

function alt_digest_pub_signup_line() {
    return '<p class="muted">Get the digest by email, free: <a href="'
        . esc_url(home_url('/ai-layoff-tracker/#alt-digest')) . '">sign up on the tracker</a>.</p>';
}

function alt_digest_pub_render_page($row) {
    $date = $row['edition_date'];
    $url = alt_digest_pub_url($date);
    $charts = json_decode((string) $row['charts'], true) ?: array();
    $images = array();
    foreach ($charts as $c) $images[] = $url . 'chart-' . (int) $c['n'] . '.png';
    $saved = mysql2date('c', $row['saved_at'] . ' +00:00', false);
    $saved = $saved ?: gmdate('c', strtotime($row['saved_at'] . ' UTC'));
    $title = $row['subject'] . ' | AI Layoff Tracker digest';
    $desc = 'The AI Layoff Tracker ' . $row['kind'] . ' email digest for '
        . ($row['period_from'] ? $row['period_from'] . ' to ' : '') . $date
        . ': verified layoffs, the week in charts and the top stories with sources.';
    alt_digest_pub_head($title, $desc, $url, 'index,follow',
                        alt_digest_pub_jsonld($row, $url, $images, $saved));
    echo '<p class="wm">AskTheRecruiter</p><h1>' . esc_html($row['subject']) . '</h1>'
        . '<p class="muted">' . esc_html(ucfirst($row['kind'])) . ' edition, sent '
        . esc_html($date) . '. This is the public copy of the email.</p>';
    // Stored HTML passed both gates at save time; rendered as saved.
    echo '<div class="ed">' . alt_digest_pub_body($row['html'], $url) . '</div>';
    $all = alt_digest_pub_all();
    $older = $newer = null;
    foreach ($all as $r) {
        if ($r['edition_date'] < $date && $older === null) $older = $r;
        if ($r['edition_date'] > $date) $newer = $r;
    }
    echo '<p class="nav"><span>';
    if ($older) echo '<a href="' . esc_url(alt_digest_pub_url($older['edition_date'])) . '">Older: ' . esc_html($older['edition_date']) . '</a>';
    echo '</span><span>';
    if ($newer) echo '<a href="' . esc_url(alt_digest_pub_url($newer['edition_date'])) . '">Newer: ' . esc_html($newer['edition_date']) . '</a>';
    echo '</span></p>' . alt_digest_pub_signup_line() . '</div></body></html>';
}

function alt_digest_pub_render_hub() {
    $from = alt_digest_pub_valid_date($_GET['from'] ?? '');
    $to = alt_digest_pub_valid_date($_GET['to'] ?? '');
    $filtered = ($from !== '' || $to !== '');
    $rows = alt_digest_pub_filter_range(alt_digest_pub_all(), $from, $to);
    $hub = alt_digest_pub_hub_url();
    $jsonld = array(array(
        '@context' => 'https://schema.org', '@type' => 'CollectionPage',
        'name' => 'AI Layoff Tracker digest archive', 'url' => $hub,
    ));
    alt_digest_pub_head('Digest archive | AI Layoff Tracker',
        'Every AI Layoff Tracker email digest, by date: verified layoffs, charts and the top stories with sources.',
        $hub, $filtered ? 'noindex,follow' : 'index,follow', $jsonld);
    echo '<p class="wm">AskTheRecruiter</p><h1>Digest archive</h1>'
        . '<p class="muted">Every edition of the AI Layoff Tracker email, newest first.</p>'
        . '<form class="f" method="get" action="' . esc_url($hub) . '">'
        . '<label>From<input type="date" name="from" value="' . esc_attr($from) . '"></label>'
        . '<label>To<input type="date" name="to" value="' . esc_attr($to) . '"></label>'
        . '<button type="submit">Filter</button>';
    if ($filtered) echo ' <a href="' . esc_url($hub) . '">Clear</a>';
    echo '</form><div class="card">';
    if (!$rows) {
        echo '<p class="muted">' . ($filtered ? 'No editions in that range.' : 'No editions yet.') . '</p>';
    } else {
        echo '<ul class="list">';
        foreach ($rows as $r) {
            echo '<li><a href="' . esc_url(alt_digest_pub_url($r['edition_date'])) . '">'
                . esc_html($r['subject']) . '</a><br><span class="muted">'
                . esc_html($r['edition_date']) . ', ' . esc_html($r['kind']) . ' edition</span></li>';
        }
        echo '</ul>';
    }
    echo '</div>' . alt_digest_pub_signup_line() . '</div></body></html>';
}

add_action('template_redirect', function () {
    $mode = (string) get_query_var('alt_digest_pub');
    if ($mode === '') return;
    if ($mode === 'sitemap') {
        status_header(200);
        header('Content-Type: application/xml; charset=UTF-8');
        header('X-Robots-Tag: noindex, follow');
        echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n"
            . '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
        $all = alt_digest_pub_all();
        $line = function ($loc, $lm) {
            return function_exists('alt_sitemap_url_line') ? alt_sitemap_url_line($loc, $lm)
                : '  <url><loc>' . esc_url($loc) . '</loc></url>' . "\n";
        };
        echo $line(alt_digest_pub_hub_url(), $all ? substr($all[0]['saved_at'], 0, 10) : '');
        foreach ($all as $r) echo $line(alt_digest_pub_url($r['edition_date']), substr($r['saved_at'], 0, 10));
        echo '</urlset>';
        exit;
    }
    if ($mode === 'hub') {
        status_header(200);
        header('Content-Type: text/html; charset=UTF-8');
        alt_digest_pub_render_hub();
        exit;
    }
    $date = alt_digest_pub_valid_date(get_query_var('alt_digest_date'));
    $row = $date !== '' ? alt_digest_pub_get($date) : null;
    if (!$row) {
        global $wp_query;
        $wp_query->set_404();
        status_header(404);
        return;
    }
    if ($mode === 'chart') {
        $charts = alt_digest_pub_decode_charts(json_decode((string) $row['charts'], true) ?: array());
        $n = (int) get_query_var('alt_digest_chart');
        if (!isset($charts[$n])) { status_header(404); exit; }
        status_header(200);
        header('Content-Type: image/png');
        header('Cache-Control: public, max-age=31536000, immutable');
        echo $charts[$n]['png'];
        exit;
    }
    status_header(200);
    header('Content-Type: text/html; charset=UTF-8');
    alt_digest_pub_render_page($row);
    exit;
}, 1);

function alt_digest_pub_sitemap_index_entry($xml) {
    return $xml . '<sitemap><loc>' . esc_url(home_url('/layoff-digest-sitemap.xml')) . '</loc></sitemap>' . "\n";
}
add_filter('wpseo_sitemap_index', 'alt_digest_pub_sitemap_index_entry');
add_filter('rank_math/sitemap/index', 'alt_digest_pub_sitemap_index_entry');
