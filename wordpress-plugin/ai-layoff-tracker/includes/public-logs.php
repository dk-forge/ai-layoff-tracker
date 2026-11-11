<?php
/**
 * Two public, citable pages (2.20.306):
 *
 *   /ai-layoff-tracker/corrections/  every correction to a published figure,
 *                                    from the same alt_corrections_log the
 *                                    tracker page and /corrections API read.
 *   /ai-layoff-tracker/update-log/   what changed, newest first, from
 *                                    data/update-log.json, which is DERIVED
 *                                    from docs/release-notes.d by
 *                                    railway/build_update_log.py.
 *
 * Both returned 404 until 2026-11-10. Rendered standalone in the same shell as
 * the public digest archive (alt_digest_pub_css when present), so they carry no
 * theme dependency. Guard: railway/tests/test_public_logs_pages.py.
 */

if (!defined('ABSPATH')) exit;

function alt_public_logs_routes() {
    add_rewrite_rule('^ai-layoff-tracker/corrections/?$', 'index.php?alt_public_log=corrections', 'top');
    add_rewrite_rule('^ai-layoff-tracker/update-log/?$', 'index.php?alt_public_log=update-log', 'top');
    add_rewrite_rule('^layoff-logs-sitemap\.xml$', 'index.php?alt_public_log=sitemap', 'top');
    if (get_option('alt_public_logs_rewrite_ver') !== ALT_VERSION) {
        update_option('alt_public_logs_rewrite_ver', ALT_VERSION, false);
        if (function_exists('alt_request_rewrite_flush')) alt_request_rewrite_flush();
    }
}
// Priority 1: Rank Math adds a catch-all rule on init:1 and 'top' rules match
// in the order added (see includes/digest-public-archive.php, 2026-11-09).
add_action('init', 'alt_public_logs_routes', 1);

add_filter('query_vars', function ($vars) {
    $vars[] = 'alt_public_log';
    return $vars;
});

function alt_public_log_url($which) {
    return home_url('/ai-layoff-tracker/' . ($which === 'update-log' ? 'update-log' : 'corrections') . '/');
}

/**
 * The corrections log with stable per-entry anchors, NEWEST FIRST.
 *
 * Anchors are numbered on the APPEND-ordered array with exactly the rule the
 * tracker page uses (templates/page-tracker.php), so an entry has the same
 * fragment on both pages and never shifts when later corrections land.
 */
function alt_corrections_log_items($log) {
    $log = is_array($log) ? $log : array();
    $alt_log_seq = array();
    $items = array();
    foreach ($log as $c) {
        if (!is_array($c)) continue;
        $alt_ld = preg_replace('/[^0-9-]/', '', (string) ($c['date'] ?? ''));
        if ($alt_ld === '') $alt_ld = 'undated';
        $alt_log_seq[$alt_ld] = isset($alt_log_seq[$alt_ld]) ? $alt_log_seq[$alt_ld] + 1 : 1;
        $c['anchor'] = 'log-' . $alt_ld . '-' . $alt_log_seq[$alt_ld];
        $items[] = $c;
    }
    return array_reverse($items);
}

function alt_public_log_css() {
    $css = function_exists('alt_digest_pub_css') ? alt_digest_pub_css()
        : 'body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.55}'
          . '.w{max-width:600px;margin:0 auto;padding:20px 16px 40px}.muted{color:#4b5563;font-size:14px}'
          . 'ul.list{list-style:none;padding:0;margin:0}ul.list li{padding:10px 0;border-top:1px solid #e5e7eb}';
    return $css . '.w{max-width:760px}ul.list li{overflow-wrap:anywhere}'
        . '.tag{display:inline-block;font-size:12px;font-weight:600;padding:1px 6px;border-radius:4px;'
        . 'border:1px solid currentColor;margin-right:6px}.alt-log-anchor{text-decoration:none;margin-left:4px}';
}

function alt_public_log_shell($title, $desc, $canonical, $body_html) {
    $tracker = home_url('/ai-layoff-tracker/');
    $nav = '<p class="bar"><a href="' . esc_url($tracker) . '">AI Layoff Tracker</a>'
        . ' &middot; <a href="' . esc_url(alt_public_log_url('corrections')) . '">Corrections log</a>'
        . ' &middot; <a href="' . esc_url(alt_public_log_url('update-log')) . '">Update log</a>'
        . ' &middot; <a href="' . esc_url(home_url('/ai-layoff-tracker/methodology/')) . '">Methodology</a></p>';
    $ld = array(
        '@context' => 'https://schema.org', '@type' => 'WebPage',
        'name' => $title, 'description' => $desc, 'url' => $canonical,
        'isPartOf' => array('@type' => 'WebSite', 'name' => 'AI Layoff Tracker', 'url' => $tracker),
    );
    return '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<meta name="color-scheme" content="light dark">'
        . '<title>' . esc_html($title) . '</title>'
        . '<meta name="description" content="' . esc_attr($desc) . '">'
        . '<meta name="robots" content="index,follow">'
        . '<link rel="canonical" href="' . esc_url($canonical) . '">'
        . '<script type="application/ld+json">' . wp_json_encode($ld, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_HEX_TAG) . '</script>'
        . '<style>' . alt_public_log_css() . '</style></head><body><div class="w">'
        . $nav . '<div class="card">' . $body_html . '</div>'
        . '<p class="muted">Spotted something off? Send it through the <a href="'
        . esc_url(home_url('/contact/')) . '">contact page</a> and corrections get priority.</p>'
        . '</div>'
        . (function_exists('alt_build_stamp_comment') ? alt_build_stamp_comment() : '')
        . '</body></html>';
}

function alt_public_log_render_corrections($log) {
    $items = alt_corrections_log_items($log);
    $api = rest_url('layoffs/v1/corrections');
    $html = '<p class="wm">AI Layoff Tracker</p><h1>Corrections log</h1>'
        . '<p>Every change to a published figure is listed here, newest first: entries removed, merged or '
        . 'corrected, the reason, and the jobs it moved when that was recorded. Nothing is corrected without '
        . 'being disclosed, because each edit and removal writes to this log as it happens. The same entries '
        . 'are on the <a href="' . esc_url(home_url('/ai-layoff-tracker/')) . '">tracker page</a> and in the '
        . 'public API at <a href="' . esc_url($api) . '"><code>/wp-json/layoffs/v1/corrections</code></a>.</p>';
    if (!$items) {
        $html .= '<p class="muted">No corrections are recorded yet.</p>';
    } else {
        $html .= '<p class="muted">' . count($items) . ' entr' . (count($items) === 1 ? 'y' : 'ies')
            . ' retained (the most recent 200).</p><ul class="list">';
        foreach ($items as $c) {
            $count = max(0, (int) ($c['count'] ?? 0));
            $jobs = (array_key_exists('jobs', $c) && is_numeric($c['jobs']))
                ? ', ' . number_format(max(0, (int) $c['jobs'])) . ' job' . (((int) $c['jobs'] === 1) ? '' : 's') : '';
            $detail = !empty($c['detail']) ? ' (' . esc_html($c['detail']) . ')' : '';
            $html .= '<li id="' . esc_attr($c['anchor']) . '"><b>' . esc_html($c['date'] ?? '') . ': '
                . $count . ' entr' . ($count === 1 ? 'y' : 'ies') . ' ' . esc_html($c['action'] ?? '')
                . $jobs . $detail . '.</b> ' . esc_html($c['reason'] ?? '')
                . ' <a class="alt-log-anchor" href="#' . esc_attr($c['anchor']) . '" aria-label="Link to this correction">#</a></li>';
        }
        $html .= '</ul>';
    }
    $html .= '<p class="muted">Four corrections made on 2026-07-15, before this log was automated, are listed in the '
        . '<a href="' . esc_url(home_url('/ai-layoff-tracker/#log-2026-07-15-s1')) . '">corrections section of the tracker page</a>. '
        . 'Changes to how the tracker works, rather than to a figure, are in the '
        . '<a href="' . esc_url(alt_public_log_url('update-log')) . '">update log</a>.</p>';
    return alt_public_log_shell(
        'Corrections log | AI Layoff Tracker',
        'Every correction to a published figure in the AI Layoff Tracker, newest first, with the reason and the jobs it moved.',
        alt_public_log_url('corrections'), $html);
}

function alt_update_log_entries() {
    $path = ALT_PLUGIN_DIR . 'data/update-log.json';
    if (!is_readable($path)) return array();
    $data = json_decode((string) file_get_contents($path), true);
    return (is_array($data) && isset($data['entries']) && is_array($data['entries'])) ? $data['entries'] : array();
}

function alt_public_log_render_update_log($entries) {
    $entries = is_array($entries) ? $entries : array();
    $html = '<p class="wm">AI Layoff Tracker</p><h1>Update log</h1>'
        . '<p>What changed in the tracker, newest first, and the release each change shipped in. '
        . 'Corrections to individual figures are in the <a href="' . esc_url(alt_public_log_url('corrections'))
        . '">corrections log</a>.</p>';
    if (!$entries) {
        $html .= '<p class="muted">No released changes are listed yet.</p>';
    } else {
        $html .= '<ul class="list">';
        foreach ($entries as $e) {
            if (!is_array($e)) continue;
            $slug = preg_replace('/[^a-z0-9-]/', '', strtolower((string) ($e['slug'] ?? '')));
            $area = trim((string) ($e['area'] ?? ''));
            $html .= '<li id="' . esc_attr('u-' . $slug) . '"><b>' . esc_html($e['date'] ?? '') . '</b> '
                . '<span class="muted">version ' . esc_html($e['version'] ?? '') . ($area !== '' ? ', ' . esc_html($area) : '') . '</span><br>'
                . '<span class="tag">' . esc_html($e['type'] ?? '') . '</span>' . esc_html($e['text'] ?? '')
                . ' <a class="alt-log-anchor" href="#' . esc_attr('u-' . $slug) . '" aria-label="Link to this change">#</a></li>';
        }
        $html .= '</ul>';
    }
    return alt_public_log_shell(
        'Update log | AI Layoff Tracker',
        'What changed in the AI Layoff Tracker, newest first, with the release each change shipped in.',
        alt_public_log_url('update-log'), $html);
}

/** The two pages with their lastmod (newest dated entry each), for the sitemap. */
function alt_public_logs_sitemap_xml($log, $entries) {
    $newest = function ($dates) {
        $dates = array_filter(array_map(function ($d) {
            $d = substr((string) $d, 0, 10);
            return preg_match('/^\d{4}-\d{2}-\d{2}$/', $d) ? $d : '';
        }, $dates));
        return $dates ? max($dates) : '';
    };
    $pages = array(
        alt_public_log_url('corrections') => $newest(array_column(is_array($log) ? $log : array(), 'date')),
        alt_public_log_url('update-log')  => $newest(array_column(is_array($entries) ? $entries : array(), 'date')),
    );
    $xml = '<?xml version="1.0" encoding="UTF-8"?>' . "\n"
        . '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
    foreach ($pages as $url => $lastmod) {
        $xml .= '<url><loc>' . esc_url($url) . '</loc>' . ($lastmod !== '' ? '<lastmod>' . $lastmod . '</lastmod>' : '') . '</url>' . "\n";
    }
    return $xml . '</urlset>';
}

function alt_public_logs_sitemap_index_entry($xml) {
    return $xml . '<sitemap><loc>' . esc_url(home_url('/layoff-logs-sitemap.xml')) . '</loc></sitemap>' . "\n";
}
add_filter('wpseo_sitemap_index', 'alt_public_logs_sitemap_index_entry');
add_filter('rank_math/sitemap/index', 'alt_public_logs_sitemap_index_entry');

add_action('template_redirect', function () {
    $which = get_query_var('alt_public_log');
    if ($which === 'sitemap') {
        status_header(200);
        header('Content-Type: application/xml; charset=UTF-8');
        header('X-Robots-Tag: noindex, follow');
        echo alt_public_logs_sitemap_xml(get_option('alt_corrections_log'), alt_update_log_entries());
        exit;
    }
    if ($which !== 'corrections' && $which !== 'update-log') return;
    status_header(200);
    header('Content-Type: text/html; charset=utf-8');
    // Short shared-cache life, like the tracker page: a correction should
    // reach readers within minutes, not hours.
    header('Cache-Control: public, max-age=60, s-maxage=60');
    echo $which === 'corrections'
        ? alt_public_log_render_corrections(get_option('alt_corrections_log'))
        : alt_public_log_render_update_log(alt_update_log_entries());
    exit;
});
