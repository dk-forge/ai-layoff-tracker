<?php
/** Shared origin budgets for public REST callbacks, downloads and forms. */
if (!defined('ABSPATH')) exit;

/** A database lock serializes counters across PHP workers, without object-cache state. */
function alt_public_limit_spend($identity, $limit, $now = null) {
    global $wpdb;
    $now = $now === null ? time() : (int) $now;
    $key = 'rl_alt_public_' . hash_hmac('sha256', $identity, wp_salt('auth'));
    $lock = 'rl_' . substr(hash('sha256', $wpdb->options . $key), 0, 60);
    if ((string) $wpdb->get_var($wpdb->prepare('SELECT GET_LOCK(%s, %d)', $lock, 1)) !== '1') return -1;
    try {
        $raw = $wpdb->get_var($wpdb->prepare("SELECT option_value FROM {$wpdb->options} WHERE option_name = %s", $key));
        if ($wpdb->last_error || ($raw !== null && !preg_match('/^\d+:\d+$/D', $raw))) return -1;
        $parts = $raw === null ? array(0, 0) : array_map('intval', explode(':', $raw));
        [$expires, $count] = $parts;
        if ($expires <= $now) { $expires = $now + 60; $count = 0; }
        if ($count >= $limit) return max(1, $expires - $now);
        $value = $expires . ':' . ($count + 1);
        $saved = $wpdb->query($wpdb->prepare(
            "INSERT INTO {$wpdb->options} (option_name, option_value, autoload) VALUES (%s, %s, 'no') " .
            "ON DUPLICATE KEY UPDATE option_value = VALUES(option_value), autoload = 'no'", $key, $value));
        return $saved === false ? -1 : 0;
    } finally {
        $wpdb->get_var($wpdb->prepare('SELECT RELEASE_LOCK(%s)', $lock));
    }
}

function alt_public_limit_check() {
    $peer = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
    $peer = filter_var($peer, FILTER_VALIDATE_IP) ? inet_ntop(inet_pton($peer)) : 'unknown';
    $budgets = array(array('ip:' . $peer, 120));
    $uid = (int) get_current_user_id();
    if ($uid > 0) $budgets[] = array('user:' . $uid, 60);
    foreach ($budgets as [$identity, $limit]) {
        $retry = alt_public_limit_spend($identity, $limit);
        if ($retry === 0) continue;
        $status = $retry < 0 ? 503 : 429;
        return new WP_REST_Response(array('code' => $retry < 0 ? 'rate_limit_unavailable' : 'rate_limited',
            'message' => 'Please wait and try again.'), $status,
            array('Retry-After' => (string) ($retry < 0 ? 1 : $retry), 'Cache-Control' => 'no-store, private'));
    }
    return null;
}

/** Identify the outer HTTP request without charging internal digest dispatches. */
function alt_public_limit_capture($result, $server, $request) {
    if (defined('REST_REQUEST') && REST_REQUEST && !isset($GLOBALS['alt_public_http_request'])) {
        $GLOBALS['alt_public_http_request'] = $request;
    }
    return $result;
}
add_filter('rest_pre_dispatch', 'alt_public_limit_capture', PHP_INT_MIN, 3);

/** WordPress calls this after permission checks and before the selected callback. */
function alt_public_endpoint_limit($result, $request, $route, $handler) {
    if (!defined('REST_REQUEST') || !REST_REQUEST
            || $request !== ($GLOBALS['alt_public_http_request'] ?? null)
            || $result !== null || strpos($route, '/layoffs/v1/') !== 0
            || ($handler['permission_callback'] ?? null) !== '__return_true') return $result;
    return alt_public_limit_check();
}
add_filter('rest_dispatch_request', 'alt_public_endpoint_limit', 10, 4);

function alt_public_limit_form() {
    $response = alt_public_limit_check();
    if ($response === null) return;
    foreach ($response->get_headers() as $name => $value) header($name . ': ' . $value);
    $message = 'Please wait and try again. <p><a style="display:inline-block;padding:12px;" href="' .
        'https://asktherecruiter.com/?start=1&amp;utm_source=ai-layoff-tracker&amp;utm_medium=referral' .
        '&amp;utm_campaign=public_rate_limit#start-intake">Check my match, free</a></p>';
    wp_die($message, 'Request limit', array('response' => $response->get_status()));
}
foreach (array('alt_export_csv', 'alt_export_json', 'alt_quarterly_appendix', 'alt_contact', 'alt_press_subscribe', 'alt_digest_subscribe', 'alt_follow') as $action) {
    add_action('admin_post_' . $action, 'alt_public_limit_form', 0);
    add_action('admin_post_nopriv_' . $action, 'alt_public_limit_form', 0);
}

/** Keep expired per-identity rows bounded, without resetting active quotas on cache flush. */
function alt_public_limit_cleanup() {
    global $wpdb;
    $wpdb->query($wpdb->prepare("DELETE FROM {$wpdb->options} WHERE option_name LIKE %s " .
        'AND CAST(option_value AS UNSIGNED) <= %d', $wpdb->esc_like('rl_alt_public_') . '%', time()));
}
function alt_public_limit_schedule() {
    if (!wp_next_scheduled('alt_public_limit_cleanup')) {
        wp_schedule_event(time() + 3600, 'hourly', 'alt_public_limit_cleanup');
    }
}
add_action('init', 'alt_public_limit_schedule');
add_action('alt_public_limit_cleanup', 'alt_public_limit_cleanup');

function alt_public_limit_deactivate() {
    global $wpdb;
    wp_clear_scheduled_hook('alt_public_limit_cleanup');
    $wpdb->query($wpdb->prepare("DELETE FROM {$wpdb->options} WHERE option_name LIKE %s",
        $wpdb->esc_like('rl_alt_public_') . '%'));
}
if (function_exists('register_deactivation_hook')) {
    register_deactivation_hook(dirname(__DIR__) . '/ai-layoff-tracker.php', 'alt_public_limit_deactivate');
}
