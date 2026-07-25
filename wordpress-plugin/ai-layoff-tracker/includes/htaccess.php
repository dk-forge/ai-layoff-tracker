<?php
if (!defined('ABSPATH')) exit;

/**
 * Bluehost's Apache appends "Cache-Control: no-cache, no-store, must-revalidate"
 * + "Pragma: no-cache" + "Expires: 0" AFTER PHP's own headers, on every PHP
 * response. The public API and tracker page then go out with TWO Cache-Control
 * headers; browsers merge the directives, no-store wins, and the browser cache
 * layer the plugin builds (max-age=300 API / max-age=180 page) is dead on
 * arrival. (The Cloudflare edge rule survives only because its Edge TTL
 * overrides origin headers.)
 *
 * No WP filter can touch headers injected outside PHP, so the fix lives at the
 * same layer: a mod_headers block in the WP root .htaccess. Apache merges <If>
 * sections after every other config level (server config, vhost, <Location>),
 * so these directives always run last and win. Scope is deliberately narrow:
 * anonymous GET/HEAD on the six public read endpoints (mirrors
 * alt_is_public_read_request — /status keeps its intentional no-store) and the
 * anonymous tracker page. THE_REQUEST is the original request line, immune to
 * WP's rewrite to index.php.
 *
 * Deployed like the contact page: FTP deploys bypass hooks and race mid-upload,
 * so this is a retry-until-verified init hook, not a one-shot. Because a broken
 * .htaccess takes down the whole /blog with 500s, every write is followed by a
 * cache-busted loopback probe; a 5xx (or no answer) restores the previous file
 * content and marks the attempt failed until the next version bump.
 */

function alt_htaccess_block_lines() {
    $rest = wp_parse_url(rest_url('layoffs/v1/'), PHP_URL_PATH);          // /blog/wp-json/layoffs/v1/
    $page = wp_parse_url(home_url('/ai-layoff-tracker/'), PHP_URL_PATH);  // /blog/ai-layoff-tracker/
    $anon = '%{HTTP_COOKIE} !~ /wordpress_logged_in/';
    return array(
        '# Managed by the AI Layoff Tracker plugin (includes/htaccess.php).',
        '# Strips the host-injected duplicate "no-store" Cache-Control/Pragma/Expires',
        '# from the anonymous public read endpoints and the tracker page, then sets',
        '# the single intended header. Manual edits inside this block are overwritten.',
        '<IfModule mod_headers.c>',
        '<If "%{THE_REQUEST} =~ m#^(GET|HEAD) ' . $rest . '(query|aggregate|facets|stats|all|conversion|claims|reconciliation|quality-status)\b# && ' . $anon . '">',
        'Header always unset Cache-Control',
        'Header always unset Pragma',
        'Header always unset Expires',
        'Header unset Pragma',
        'Header unset Expires',
        'Header set Cache-Control "public, max-age=300, s-maxage=300, stale-while-revalidate=600"',
        '</If>',
        '<If "%{THE_REQUEST} =~ m#^(GET|HEAD) ' . $page . '[ ?]# && ' . $anon . '">',
        'Header always unset Cache-Control',
        'Header always unset Pragma',
        'Header always unset Expires',
        'Header unset Pragma',
        'Header unset Expires',
        'Header set Cache-Control "public, max-age=180, s-maxage=300, stale-while-revalidate=600"',
        '</If>',
        '# Plugin assets are URL-fingerprinted (?ver=ALT_VERSION.filemtime), so a',
        '# year-long immutable lifetime is safe: any change mints a new URL.',
        '<If "%{THE_REQUEST} =~ m#^(GET|HEAD) [^ ]*/plugins/ai-layoff-tracker/assets/#">',
        'Header always unset Cache-Control',
        'Header set Cache-Control "public, max-age=31536000, immutable"',
        '</If>',
        '</IfModule>',
    );
}

function alt_htaccess_ensure() {
    if (get_transient('alt_htaccess_ok')) return;
    $state = get_option('alt_htaccess_state', array());
    if (($state['status'] ?? '') === 'failed' && ($state['version'] ?? '') === ALT_VERSION) return;
    if (get_transient('alt_htaccess_lock')) return;
    set_transient('alt_htaccess_lock', 1, MINUTE_IN_SECONDS);

    require_once ABSPATH . 'wp-admin/includes/misc.php';
    if (!function_exists('insert_with_markers')) return;

    $file    = ABSPATH . '.htaccess';
    $desired = alt_htaccess_block_lines();
    if (extract_from_markers($file, 'AI Layoff Tracker') === $desired) {
        update_option('alt_htaccess_state', array('version' => ALT_VERSION, 'status' => 'verified', 'at' => time()), false);
        set_transient('alt_htaccess_ok', 1, 12 * HOUR_IN_SECONDS);
        return;
    }

    $backup = @file_get_contents($file);
    if (!insert_with_markers($file, 'AI Layoff Tracker', $desired)) {
        update_option('alt_htaccess_state', array('version' => ALT_VERSION, 'status' => 'failed', 'reason' => 'write', 'at' => time()), false);
        error_log('[ai-layoff-tracker] could not write cache-header block to ' . $file);
        return;
    }

    // A bad .htaccess 500s the entire install: probe before trusting the write.
    // cb busts the Cloudflare edge rule so the answer comes from origin Apache.
    $probe = wp_remote_get(
        add_query_arg('cb', 'htx' . time(), rest_url('layoffs/v1/stats')),
        array('timeout' => 15, 'user-agent' => 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)')
    );
    $code = is_wp_error($probe) ? 0 : (int) wp_remote_retrieve_response_code($probe);
    if ($code === 0 || $code >= 500) {
        if ($backup !== false) {
            @file_put_contents($file, $backup, LOCK_EX);
        } else {
            insert_with_markers($file, 'AI Layoff Tracker', array());
        }
        update_option('alt_htaccess_state', array('version' => ALT_VERSION, 'status' => 'failed', 'reason' => 'probe', 'code' => $code, 'at' => time()), false);
        error_log('[ai-layoff-tracker] cache-header .htaccess block rolled back: probe returned HTTP ' . $code);
        return;
    }

    update_option('alt_htaccess_state', array('version' => ALT_VERSION, 'status' => 'verified', 'at' => time()), false);
    set_transient('alt_htaccess_ok', 1, 12 * HOUR_IN_SECONDS);
}
add_action('init', 'alt_htaccess_ensure');
