<?php
/**
 * Follow a company or a US state; matching new rows ride in the digest.
 *
 * Owner scope 2026-09-24, item 5. A follow is a row in wp_alt_follows tied to
 * a subscriber id. It reuses the EXISTING consent machinery rather than adding
 * a second one (tests/test_follow_alerts.py):
 *
 *   - The form calls alt_digest_signup(), which sends the digest's own
 *     confirmation email. The follow is stored `pending`.
 *   - alt_digest_confirm() fires `alt_digest_confirmed`; only then does
 *     alt_follows_activate() make that subscriber's pending follows active.
 *   - Only ACTIVE follows of CONFIRMED subscribers are read, so the existing
 *     unsubscribe stops follow mail too. alt_follows_cleanup() deletes follows
 *     whose subscriber is gone or no longer confirmed, daily.
 *
 * The section is composed HERE (figures never come from the relay) and handed
 * per recipient as `follow_section`; both senders append it after the
 * sections the reader consented to, for layoff-list readers only.
 * Runbook: docs/RUNBOOK_GROWTH.md, "Follow alerts".
 */
if (!defined('ABSPATH')) exit;

function alt_follows_table() { global $wpdb; return $wpdb->prefix . 'alt_follows'; }

function alt_follows_install() {
    if (get_option('alt_follows_db_version') === ALT_VERSION) return;
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $t = alt_follows_table();
    $charset = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE $t (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        subscriber_id BIGINT UNSIGNED NOT NULL,
        kind VARCHAR(16) NOT NULL,
        value VARCHAR(191) NOT NULL,
        label VARCHAR(255) NOT NULL DEFAULT '',
        url VARCHAR(255) NOT NULL DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        created_at DATETIME NOT NULL,
        activated_at DATETIME NULL,
        PRIMARY KEY (id), UNIQUE KEY sub_target (subscriber_id, kind, value), KEY status (status)
    ) $charset;");
    update_option('alt_follows_db_version', ALT_VERSION, false);
}
add_action('init', 'alt_follows_install', 5);

/** The small form. $kind 'company' (value = company_key) or 'state' (value = 2-letter code). */
function alt_follow_form_html($kind, $value, $label) {
    $sent = isset($_GET['alt_follow']) && $_GET['alt_follow'] === 'sent';
    $out = '<section class="alt-follow" aria-labelledby="alt-follow-h"><h2 id="alt-follow-h">Follow ' . esc_html($label) . '</h2>';
    if ($sent) {
        return $out . '<p role="status">Check your inbox. The follow starts when you click the confirmation link.</p></section>';
    }
    return $out . '<p>Get new entries for ' . esc_html($label) . ' in the weekly digest. We email you a confirmation link first; unsubscribe any time.</p>'
        . '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">'
        . '<input type="hidden" name="action" value="alt_follow">'
        . '<input type="hidden" name="alt_follow_kind" value="' . esc_attr($kind) . '">'
        . '<input type="hidden" name="alt_follow_value" value="' . esc_attr($value) . '">'
        . '<input type="text" name="alt_hp" class="alt-hp" tabindex="-1" autocomplete="off" aria-hidden="true">'
        . '<label>Email <input type="email" name="alt_follow_email" required autocomplete="email"></label> '
        . '<button type="submit" class="alt-btn">Follow</button></form></section>';
}

/** Resolve a follow target to [label, url] or null. Never trusts the POST label. */
function alt_follow_resolve($kind, $value) {
    global $wpdb;
    if ($kind === 'company') {
        if (!function_exists('alt_company_directory_table')) return null;
        $row = $wpdb->get_row($wpdb->prepare(
            'SELECT slug, display_name FROM ' . alt_company_directory_table()
            . " WHERE company_key = %s AND review_status IN ('approved','noindex') LIMIT 1", $value), ARRAY_A);
        return $row ? array($row['display_name'], alt_company_directory_url($row['slug'])) : null;
    }
    if ($kind === 'state' && function_exists('alt_facet_catalogue')) {
        $cat = alt_facet_catalogue();
        $code = strtoupper($value);
        return isset($cat['state'][$code]) ? array((string) $cat['state'][$code], alt_facet_url('state', $cat['state'][$code])) : null;
    }
    return null;
}

function alt_follow_submit() {
    global $wpdb;
    $back = wp_get_referer() ?: home_url('/ai-layoff-tracker/');
    if (!empty($_POST['alt_hp'])) { wp_safe_redirect($back); exit; }
    $kind = sanitize_key(wp_unslash($_POST['alt_follow_kind'] ?? ''));
    $value = sanitize_text_field(wp_unslash($_POST['alt_follow_value'] ?? ''));
    $email = strtolower(sanitize_email(wp_unslash($_POST['alt_follow_email'] ?? '')));
    if (!in_array($kind, array('company', 'state'), true) || !is_email($email)) { wp_safe_redirect($back); exit; }
    $target = alt_follow_resolve($kind, $value);
    if (!$target || !function_exists('alt_digest_signup')) { wp_safe_redirect($back); exit; }
    if ($kind === 'state') $value = strtoupper($value);

    // Keep every list the reader already has and add the layoff list, so the
    // change the confirmation email itemises is "starting" or "keeping", never
    // a silent loss (alt_digest_change_delta()).
    $row = alt_digest_get_by_email($email);
    $prefs = array();
    foreach (alt_digest_lists() as $cols) {
        $prefs[$cols['consent']] = ($row && $row['status'] === 'confirmed') ? (int) $row[$cols['consent']] : 0;
        $prefs[$cols['freq']] = ($row && $row['status'] === 'confirmed') ? alt_digest_accepted_freq($row[$cols['freq']]) : 'weekly';
    }
    $prefs['consent_layoff'] = 1;
    alt_digest_signup($email, $prefs);   // the digest's own double opt-in

    $sub = alt_digest_get_by_email($email);
    if ($sub) {
        $wpdb->query($wpdb->prepare(
            'INSERT IGNORE INTO ' . alt_follows_table() . ' (subscriber_id, kind, value, label, url, status, created_at)
             VALUES (%d, %s, %s, %s, %s, %s, %s)',
            (int) $sub['id'], $kind, $value, $target[0], $target[1], 'pending', gmdate('Y-m-d H:i:s')));
        // INSERT IGNORE: a follow already stored (pending or active) is left
        // exactly as it is, so a stranger re-submitting cannot reset it.
    }
    wp_safe_redirect(add_query_arg('alt_follow', 'sent', $back) . '#alt-follow-h');
    exit;
}
add_action('admin_post_alt_follow', 'alt_follow_submit');
add_action('admin_post_nopriv_alt_follow', 'alt_follow_submit');

/** Fired by alt_digest_confirm(): the reader clicked the link in their own inbox. */
function alt_follows_activate($subscriber_id) {
    global $wpdb;
    $wpdb->update(alt_follows_table(),
        array('status' => 'active', 'activated_at' => gmdate('Y-m-d H:i:s')),
        array('subscriber_id' => (int) $subscriber_id, 'status' => 'pending'));
}
add_action('alt_digest_confirmed', 'alt_follows_activate');

/**
 * Rows for one subscriber's active follows in the digest window. "New" means
 * written in the window (updated_at) or announced/effective in it, because a
 * WARN notice is usually filed for a date weeks ahead. Ten per send, biggest
 * first, superset members excluded like every other count.
 */
function alt_follows_matches($subscriber_id, $from, $to) {
    global $wpdb;
    $f = alt_follows_table(); $s = alt_subscribers_table(); $t = alt_db_table();
    $follows = $wpdb->get_results($wpdb->prepare(
        "SELECT f.kind, f.value, f.label, f.url FROM $f f INNER JOIN $s s ON s.id = f.subscriber_id
          WHERE f.subscriber_id = %d AND f.status = 'active' AND s.status = 'confirmed'", (int) $subscriber_id), ARRAY_A) ?: array();
    $out = array(); $seen = array();
    foreach ($follows as $fw) {
        $col = $fw['kind'] === 'company' ? 'company_key' : 'state';
        $rows = $wpdb->get_results($wpdb->prepare(
            "SELECT id, company, job_count, COALESCE(announcement_date, layoff_date) d, state, country FROM $t
              WHERE superset_of = 0 AND $col = %s
                AND (updated_at BETWEEN %s AND %s OR COALESCE(announcement_date, layoff_date) BETWEEN %s AND %s)
              ORDER BY job_count DESC, id DESC LIMIT 10",
            $fw['value'], $from . ' 00:00:00', $to . ' 23:59:59', $from, $to), ARRAY_A) ?: array();
        foreach ($rows as $r) {
            if (isset($seen[$r['id']])) continue;
            $seen[$r['id']] = true;
            $out[] = array('follow' => $fw['label'], 'company' => $r['company'], 'jobs' => (int) $r['job_count'],
                           'date' => (string) $r['d'], 'place' => $r['state'] ?: $r['country'], 'url' => $fw['url']);
            if (count($out) >= 10) break 2;
        }
    }
    return $out;
}

/** Compose the per-recipient section. Pure. Null when there is nothing to say. */
function alt_follow_section(array $rows) {
    if (!$rows) return null;
    $html = '<h2>What you follow</h2><ul>';
    $text = "What you follow\n";
    foreach ($rows as $r) {
        $bits = array((string) $r['company']);
        if ((int) ($r['jobs'] ?? 0) > 0) $bits[] = number_format((int) $r['jobs']) . ' jobs';
        if (!empty($r['date'])) $bits[] = (string) $r['date'];
        if (!empty($r['place'])) $bits[] = (string) $r['place'];
        $line = implode(', ', $bits);
        $html .= '<li>' . esc_html($line) . ' (<a href="' . esc_url($r['url']) . '">' . esc_html($r['follow']) . '</a>)</li>';
        $text .= '- ' . $line . ' (' . $r['follow'] . '): ' . $r['url'] . "\n";
    }
    return array('html' => $html . '</ul>', 'text' => rtrim($text));
}

/** What the senders call. Guarded so a missing table is "no section", never a fatal. */
function alt_follows_section_for($subscriber_id, $from, $to) {
    if (get_option('alt_follows_db_version') === false) return null;
    return alt_follow_section(alt_follows_matches($subscriber_id, $from, $to));
}

/**
 * Daily: drop follows whose subscriber is gone, or unsubscribed (an ACTIVE
 * follow of a non-confirmed row can only mean they left). A PENDING follow of
 * a pending subscriber waits 30 days for its confirmation click, the same
 * window as the subscriber retention purge.
 */
function alt_follows_cleanup() {
    global $wpdb;
    $f = alt_follows_table(); $s = alt_subscribers_table();
    $wpdb->query("DELETE f FROM $f f LEFT JOIN $s s ON s.id = f.subscriber_id
                   WHERE s.id IS NULL
                      OR (s.status <> 'confirmed' AND (f.status = 'active'
                          OR f.created_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 30 DAY)))");
}
add_action('alt_follows_cleanup', 'alt_follows_cleanup');
add_action('init', function () {
    if (!wp_next_scheduled('alt_follows_cleanup')) {
        wp_schedule_event(time() + HOUR_IN_SECONDS, 'daily', 'alt_follows_cleanup');
    }
}, 30);
