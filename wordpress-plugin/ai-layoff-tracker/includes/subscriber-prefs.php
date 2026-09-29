<?php
/**
 * Owner decisions 2026-09-27 (TECHLOG "Email audit"): the welcome email, the
 * per-follow stop link, the preferences page, and the fallback digest's
 * plain-text part. One file so the four share one token scheme.
 *
 * TOKENS. Every link here is `<subscriber id>-<hmac>` (plus a follow id for a
 * stop link). The HMAC is keyed by the site salt AND the row's own
 * unsub_token, a 64-hex secret that has only ever travelled to that mailbox,
 * and it signs the PURPOSE and the SCOPE, so a stop link for one follow cannot
 * be replayed as a preferences link or as a stop for another follow. When the
 * purge deletes the row, every link dies with it.
 *
 * GET NEVER MUTATES. Corporate link scanners fetch every URL in a delivered
 * message (the 2026-08-17 unsubscribe incident, subscribe.php). A GET renders
 * a page with a button; only the POST that button sends changes anything.
 *
 * DOUBLE OPT-IN IS KEPT. The preferences page applies a change that REDUCES
 * mail at once (it is exactly what the unsubscribe link already allows the
 * same token holder), and parks anything that ADDS mail behind the existing
 * confirm-by-email flow (alt_digest_signup's pending_prefs branch).
 *
 * Guarded include: every caller elsewhere uses function_exists().
 * Tests: railway/tests/test_email_owner_decisions.py.
 */
if (!defined('ABSPATH')) exit;

/* ------------------------------------------------------------------ */
/* Tokens                                                              */
/* ------------------------------------------------------------------ */

function alt_prefs_sign($purpose, $row, $scope = '') {
    $salt = function_exists('wp_salt') ? (string) wp_salt('auth') : '';
    $key = $salt . '|' . (string) ($row['unsub_token'] ?? '');
    return hash_hmac('sha256', $purpose . '|' . (int) $row['id'] . '|' . $scope, $key);
}

function alt_prefs_token($row) {
    return (int) $row['id'] . '-' . alt_prefs_sign('prefs', $row);
}

function alt_prefs_url($row) {
    return home_url('/' . alt_digest_link_base() . '/preferences/' . alt_prefs_token($row) . '/');
}

function alt_follow_stop_token($row, $follow_id) {
    return (int) $row['id'] . '-' . (int) $follow_id . '-'
         . alt_prefs_sign('stop-follow', $row, (string) (int) $follow_id);
}

function alt_follow_stop_url($row, $follow_id) {
    return home_url('/' . alt_digest_link_base() . '/stop-follow/'
                    . alt_follow_stop_token($row, $follow_id) . '/');
}

function alt_prefs_row_by_id($id) {
    global $wpdb;
    return $wpdb->get_row($wpdb->prepare(
        'SELECT * FROM ' . alt_subscribers_table() . ' WHERE id = %d', (int) $id), ARRAY_A);
}

/** The CONFIRMED row a preferences token names, or null. Constant-time compare. */
function alt_prefs_verify($token) {
    if (!is_string($token) || !preg_match('/^(\d{1,19})-([a-f0-9]{64})$/', $token, $m)) return null;
    $row = alt_prefs_row_by_id($m[1]);
    if (!$row || empty($row['unsub_token'])) return null;
    if (!hash_equals(alt_prefs_sign('prefs', $row), $m[2])) return null;
    return $row;
}

/** array(row, follow_id) for a stop token, or null. */
function alt_follow_stop_verify($token) {
    if (!is_string($token) || !preg_match('/^(\d{1,19})-(\d{1,19})-([a-f0-9]{64})$/', $token, $m)) return null;
    $row = alt_prefs_row_by_id($m[1]);
    if (!$row || empty($row['unsub_token'])) return null;
    if (!hash_equals(alt_prefs_sign('stop-follow', $row, (string) (int) $m[2]), $m[3])) return null;
    return array($row, (int) $m[2]);
}

/* ------------------------------------------------------------------ */
/* Routing (same public path family as confirm/unsubscribe)            */
/* ------------------------------------------------------------------ */

function alt_prefs_route_dispatch() {
    if (!function_exists('alt_digest_route_request_path')) return;
    $pattern = '#^' . preg_quote(alt_digest_link_base(), '#') . '/(preferences|stop-follow)(?:/(.*))?$#';
    if (!preg_match($pattern, alt_digest_route_request_path(), $m)) return;
    $token = isset($m[2]) ? trim($m[2], '/') : '';
    if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
    nocache_headers();
    if ($m[1] === 'preferences') alt_prefs_handle($token);
    else alt_follow_stop_handle($token);
    exit;
}
add_action('parse_request', 'alt_prefs_route_dispatch', 0);

function alt_prefs_is_post() {
    return strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET')) === 'POST';
}

/** A small, readable, mobile-first page. Same palette as the unsubscribe page. */
function alt_prefs_page($title, $inner) {
    $css = 'body{background:#ffffff}'
         . '.altp{max-width:34em;margin:0 auto;padding:16px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.6;color:#15181d;font-size:17px}'
         . '.altp h1{font-size:22px;margin:0 0 12px}'
         . '.altp fieldset{border:1px solid #c4c9d1;border-radius:8px;margin:0 0 18px;padding:12px 14px}'
         . '.altp legend{font-weight:600;padding:0 4px}'
         . '.altp label{display:flex;gap:10px;align-items:flex-start;padding:8px 0;min-height:44px;cursor:pointer}'
         . '.altp input[type=checkbox],.altp input[type=radio]{width:22px;height:22px;margin:2px 0 0;flex:none}'
         . '.altp button{display:block;width:100%;padding:14px 20px;font-size:17px;font-weight:600;color:#ffffff;background:#0b4f9c;border:0;border-radius:8px;cursor:pointer}'
         . '.altp a{color:#0b4f9c}'
         . '.altp .note{font-size:15px;color:#3d4450}'
         . '.altp :focus-visible{outline:3px solid #0b4f9c;outline-offset:2px}'
         . '@media (min-width:600px){.altp button{display:inline-block;width:auto}}';
    wp_die('<style>' . $css . '</style><main class="altp"><h1>' . esc_html($title) . '</h1>' . $inner . '</main>',
           $title, array('response' => 200));
}

function alt_prefs_dead_link_page() {
    alt_prefs_page('This link no longer works',
        '<p>It may belong to an address that has unsubscribed. You can sign up again on the '
        . '<a href="' . esc_url(home_url('/ai-layoff-tracker/')) . '#alt-digest">tracker page</a>.</p>');
}

/* ------------------------------------------------------------------ */
/* Follows                                                             */
/* ------------------------------------------------------------------ */

function alt_prefs_follows_of($subscriber_id) {
    global $wpdb;
    if (!function_exists('alt_follows_table')) return array();
    return $wpdb->get_results($wpdb->prepare(
        'SELECT id, label, status FROM ' . alt_follows_table()
        . " WHERE subscriber_id = %d AND status IN ('active','pending') ORDER BY label, id",
        (int) $subscriber_id), ARRAY_A) ?: array();
}

function alt_prefs_follow($subscriber_id, $follow_id) {
    global $wpdb;
    if (!function_exists('alt_follows_table')) return null;
    return $wpdb->get_row($wpdb->prepare(
        'SELECT * FROM ' . alt_follows_table() . ' WHERE id = %d AND subscriber_id = %d',
        (int) $follow_id, (int) $subscriber_id), ARRAY_A);
}

function alt_prefs_delete_follow($subscriber_id, $follow_id) {
    global $wpdb;
    return $wpdb->query($wpdb->prepare(
        'DELETE FROM ' . alt_follows_table() . ' WHERE id = %d AND subscriber_id = %d',
        (int) $follow_id, (int) $subscriber_id));
}

/** Stop links for the digest's "What you follow" section: list of [label, url]. */
function alt_follow_stop_links($subscriber_id) {
    $row = alt_prefs_row_by_id($subscriber_id);
    if (!$row || ($row['status'] ?? '') !== 'confirmed') return array();
    $out = array();
    foreach (alt_prefs_follows_of($subscriber_id) as $f) {
        if ($f['status'] !== 'active') continue;
        $out[] = array((string) $f['label'], alt_follow_stop_url($row, $f['id']));
    }
    return $out;
}

/**
 * /stop-follow/<token>/. GET asks, POST stops. Idempotent: a follow already
 * gone answers "stopped" on both.
 */
function alt_follow_stop_handle($token) {
    $hit = alt_follow_stop_verify((string) $token);
    if (!$hit) alt_prefs_dead_link_page();
    list($row, $follow_id) = $hit;
    $follow = alt_prefs_follow($row['id'], $follow_id);
    $prefs_link = '<p class="note"><a href="' . esc_url(alt_prefs_url($row)) . '">See everything you get</a></p>';
    if (!$follow) {
        alt_prefs_page('Already stopped', '<p>You no longer follow this.</p>' . $prefs_link);
    }
    $label = (string) $follow['label'];
    if (!alt_prefs_is_post() || empty($_POST['alt_follow_stop_confirm'])) {
        alt_prefs_page('Stop following ' . $label . '?',
            '<p>The digest stops listing new entries for ' . esc_html($label)
            . '. Everything else you get keeps arriving.</p>'
            . '<form method="post" action="' . esc_url(alt_follow_stop_url($row, $follow_id)) . '">'
            . '<input type="hidden" name="alt_follow_stop_confirm" value="1">'
            . '<button type="submit">Yes, stop following ' . esc_html($label) . '</button></form>'
            . $prefs_link);
    }
    alt_prefs_delete_follow($row['id'], $follow_id);
    alt_prefs_page('Stopped', '<p>You no longer follow ' . esc_html($label) . '.</p>' . $prefs_link);
}

/* ------------------------------------------------------------------ */
/* Preferences page                                                    */
/* ------------------------------------------------------------------ */

function alt_prefs_freq_rank($f) {
    return array('monthly' => 1, 'weekly' => 2, 'daily' => 3)[alt_digest_valid_freq($f)];
}

/**
 * Split a requested preference set into what applies NOW (only ever less
 * mail) and what must wait for the confirmation click (anything more).
 * Pure. $row is the stored row, $wanted the alt_digest_prefs_from_post shape.
 * Returns array('now' => prefs, 'adds' => bool, 'stopped' => list keys).
 */
function alt_prefs_split($row, array $wanted) {
    $now = array();
    $stopped = array();
    $adds = false;
    $old_f = alt_digest_valid_freq($row['freq_layoff'] ?? 'weekly');
    $new_f = alt_digest_valid_freq($wanted['freq_layoff'] ?? 'weekly');
    $f_now = alt_prefs_freq_rank($new_f) < alt_prefs_freq_rank($old_f) ? $new_f : $old_f;
    if (alt_prefs_freq_rank($new_f) > alt_prefs_freq_rank($old_f)) $adds = true;
    foreach (alt_digest_lists() as $key => $cols) {
        $had = !empty($row[$cols['consent']]);
        $wants = !empty($wanted[$cols['consent']]);
        if (!$had && $wants) $adds = true;
        if ($had && !$wants) $stopped[] = $key;
        $now[$cols['consent']] = ($had && $wants) ? 1 : 0;
        $now[$cols['freq']] = $f_now;
    }
    return array('now' => $now, 'adds' => $adds, 'stopped' => $stopped);
}

function alt_prefs_form($row, $notice = '') {
    $names = alt_digest_list_names();
    $freq = alt_digest_valid_freq($row['freq_layoff'] ?? 'weekly');
    $html = $notice;
    $html .= '<p>Change what you get and press Save. Anything that stops or slows mail applies at once. '
           . 'Anything that adds mail is emailed to you to confirm first.</p>'
           . '<form method="post" action="' . esc_url(alt_prefs_url($row)) . '">'
           . '<input type="hidden" name="alt_prefs_save" value="1">'
           . '<fieldset><legend>Lists</legend>';
    foreach (alt_digest_lists() as $key => $cols) {
        $html .= '<label><input type="checkbox" name="alt_list_' . esc_attr($key) . '" value="1"'
               . (!empty($row[$cols['consent']]) ? ' checked' : '') . '> <span>'
               . esc_html($names[$key]) . '</span></label>';
    }
    $html .= '</fieldset><fieldset><legend>How often</legend>';
    $opts = array('daily' => 'Daily', 'weekly' => 'Weekly (Monday)');
    if (alt_digest_monthly_enabled()) $opts['monthly'] = 'Monthly (the 1st)';
    foreach ($opts as $v => $label) {
        $html .= '<label><input type="radio" name="alt_freq" value="' . esc_attr($v) . '"'
               . ($freq === $v ? ' checked' : '') . '> <span>' . esc_html($label) . '</span></label>';
    }
    $html .= '</fieldset>';
    $follows = alt_prefs_follows_of($row['id']);
    if ($follows) {
        $html .= '<fieldset><legend>Companies and states you follow</legend>';
        foreach ($follows as $f) {
            $html .= '<label><input type="checkbox" name="alt_keep_follow[]" value="' . (int) $f['id'] . '" checked> <span>'
                   . esc_html($f['label']) . ($f['status'] === 'pending' ? ' (waiting for your confirmation)' : '')
                   . '</span></label>';
        }
        $html .= '</fieldset>';
    }
    $html .= '<button type="submit">Save</button></form>'
           . '<p class="note">To stop everything, use the unsubscribe link at the foot of any digest: '
           . '<a href="' . esc_url(alt_digest_unsub_url($row['unsub_token'])) . '">unsubscribe</a>.</p>';
    return $html;
}

/** /preferences/<token>/. GET shows the form; POST saves it. */
function alt_prefs_handle($token) {
    global $wpdb;
    $row = alt_prefs_verify((string) $token);
    if (!$row || ($row['status'] ?? '') !== 'confirmed') alt_prefs_dead_link_page();
    if (!alt_prefs_is_post() || empty($_POST['alt_prefs_save'])) {
        alt_prefs_page('Your email preferences', alt_prefs_form($row));
    }
    $wanted = alt_digest_prefs_from_post($_POST);
    if ($wanted === null) {
        alt_prefs_page('Your email preferences', alt_prefs_form($row,
            '<p role="alert"><strong>Tick at least one list, or use the unsubscribe link below to stop everything.</strong></p>'));
    }
    $said = array();
    // Follows: only removal is possible here, so it always applies at once.
    $keep = array_map('intval', (array) ($_POST['alt_keep_follow'] ?? array()));
    foreach (alt_prefs_follows_of($row['id']) as $f) {
        if (!in_array((int) $f['id'], $keep, true)) {
            alt_prefs_delete_follow($row['id'], $f['id']);
            $said[] = 'Stopped following ' . $f['label'] . '.';
        }
    }
    $split = alt_prefs_split($row, $wanted);
    $changed_now = false;
    foreach ($split['now'] as $col => $v) {
        if ((string) $row[$col] !== (string) $v) $changed_now = true;
    }
    if ($changed_now) {
        $wpdb->update(alt_subscribers_table(), $split['now'], array('id' => $row['id']));
        alt_digest_mirror($row['email']);
        $said[] = 'Saved. Less mail applies from now on.';
    }
    if ($split['adds']) {
        // The existing double opt-in: parks the whole wanted set and emails a
        // confirmation link. Nothing that ADDS mail applies without that click.
        alt_digest_signup($row['email'], $wanted, !empty($row['consent_partners']) ? 1 : 0);
        $said[] = 'Check your inbox: what you added starts when you click the confirmation link we just sent.';
    }
    if (!$said) $said[] = 'Nothing changed.';
    $fresh = alt_prefs_row_by_id($row['id']) ?: $row;
    $notice = '<div role="status">';
    foreach ($said as $s) $notice .= '<p><strong>' . esc_html($s) . '</strong></p>';
    alt_prefs_page('Your email preferences', alt_prefs_form($fresh, $notice . '</div>'));
}

/* ------------------------------------------------------------------ */
/* Welcome email                                                       */
/* ------------------------------------------------------------------ */

/*
 * Welcome mails per UTC day, out of Brevo's 300/day. The rest is the digest's.
 *
 * Owner ruling 2026-09-28: the cap starts at 40 and steps up to 100 by itself
 * when signups grow, checked once a day (at the UTC day roll-over). It steps
 * up when, on any of the last 3 completed days, welcome demand (sent +
 * skipped) was >= 30, AND the previous day's reader sends as recorded
 * (digest recipients + welcomes + confirmations) + 60 fit in Brevo's 300.
 * Once raised it stays raised (no flapping). Defining ALT_WELCOME_DAILY_CAP
 * (wp-config) is the manual override and always wins.
 */
const ALT_WELCOME_CAP_BASE = 40;
const ALT_WELCOME_CAP_RAISED = 100;
const ALT_WELCOME_DEMAND_TRIGGER = 30;
const ALT_BREVO_DAILY_LIMIT = 300;
const ALT_MAIL_HISTORY_DAYS = 7;

/**
 * Pure decision. $history: array(day => array(welcome, welcome_skipped,
 * confirm, digest)) of COMPLETED days; $raised_on: the day it was raised or ''.
 * Returns array(cap, reason, raised_on).
 */
function alt_welcome_cap_decide($history, $raised_on, $today, $override = null) {
    if ($override !== null) {
        return array((int) $override, 'manual override (ALT_WELCOME_DAILY_CAP)', (string) $raised_on);
    }
    if ((string) $raised_on !== '') {
        return array(ALT_WELCOME_CAP_RAISED, 'auto-raised to ' . ALT_WELCOME_CAP_RAISED . ' on ' . $raised_on, (string) $raised_on);
    }
    $t = strtotime($today . ' 00:00:00 UTC');
    $demand = false;
    for ($i = 1; $i <= 3; $i++) {
        $d = $history[gmdate('Y-m-d', $t - $i * 86400)] ?? null;
        if (is_array($d) && (int) ($d['welcome'] ?? 0) + (int) ($d['welcome_skipped'] ?? 0) >= ALT_WELCOME_DEMAND_TRIGGER) {
            $demand = true;
        }
    }
    $y = $history[gmdate('Y-m-d', $t - 86400)] ?? array();
    $y_total = (int) ($y['digest'] ?? 0) + (int) ($y['welcome'] ?? 0) + (int) ($y['confirm'] ?? 0);
    $room = $y_total + (ALT_WELCOME_CAP_RAISED - ALT_WELCOME_CAP_BASE) <= ALT_BREVO_DAILY_LIMIT;
    if ($demand && $room) {
        return array(ALT_WELCOME_CAP_RAISED, 'auto-raised to ' . ALT_WELCOME_CAP_RAISED . ' on ' . $today, $today);
    }
    $why = !$demand
        ? 'default; welcome demand under ' . ALT_WELCOME_DEMAND_TRIGGER . '/day on each of the last 3 days'
        : 'default; demand met but yesterday used ' . $y_total . ' of ' . ALT_BREVO_DAILY_LIMIT . ', no room for +60';
    return array(ALT_WELCOME_CAP_BASE, $why, '');
}

/** Digest recipients recorded in the sends log for one UTC day (0 when unseen). */
function alt_mail_digest_recipients_on($day) {
    global $wpdb;
    if (!function_exists('alt_digest_sends_table') || !function_exists('alt_digest_table_present')) return 0;
    if (!alt_digest_table_present(alt_digest_sends_table())) return 0;
    return (int) $wpdb->get_var($wpdb->prepare(
        'SELECT COALESCE(SUM(recipients), 0) FROM ' . alt_digest_sends_table()
        . ' WHERE sent_at >= %s AND sent_at < %s',
        $day . ' 00:00:00', gmdate('Y-m-d', strtotime($day . ' 00:00:00 UTC') + 86400) . ' 00:00:00'));
}

/**
 * The plugin's reader-mail ledger for today, rolled over (and the cap
 * re-decided) on the first read of a new UTC day. Persists on roll-over.
 */
function alt_welcome_budget_status() {
    $b = get_option('alt_mail_budget', array());
    if (!is_array($b)) $b = array();
    $today = gmdate('Y-m-d');
    $history = (isset($b['history']) && is_array($b['history'])) ? $b['history'] : array();
    $raised_on = (string) ($b['raised_on'] ?? '');
    $rolled = ($b['day'] ?? '') !== $today || !isset($b['welcome_cap_effective']);
    if (($b['day'] ?? '') !== $today) {
        if (!empty($b['day'])) {
            $history[$b['day']] = array(
                'welcome'         => (int) ($b['welcome'] ?? 0),
                'welcome_skipped' => (int) ($b['welcome_skipped'] ?? 0),
                'confirm'         => (int) ($b['confirm'] ?? 0),
                'digest'          => alt_mail_digest_recipients_on($b['day']),
            );
        }
        $b = array('day' => $today, 'welcome' => 0, 'welcome_skipped' => 0, 'confirm' => 0);
    }
    ksort($history);
    $history = array_slice($history, -ALT_MAIL_HISTORY_DAYS, null, true);
    list($cap, $reason, $raised_on) = alt_welcome_cap_decide(
        $history, $raised_on, $today, defined('ALT_WELCOME_DAILY_CAP') ? ALT_WELCOME_DAILY_CAP : null);
    $b['history'] = $history;
    $b['raised_on'] = $raised_on;
    $b['welcome_cap'] = $cap;
    $b['welcome_cap_effective'] = $cap;
    $b['welcome_cap_reason'] = $reason;
    $b['brevo_daily_limit'] = ALT_BREVO_DAILY_LIMIT;
    if ($rolled) update_option('alt_mail_budget', $b, false);
    return $b;
}

/** Count one reader mail the plugin sent (e.g. 'confirm') in today's ledger. */
function alt_mail_budget_record($kind) {
    $b = alt_welcome_budget_status();
    $b[$kind] = (int) ($b[$kind] ?? 0) + 1;
    update_option('alt_mail_budget', $b, false);
}

/** The next scheduled send for a tier, in New York time (railway/digest_slot.py SEND_TIMES). */
function alt_welcome_next_send($freq, $now = null) {
    $tz = new DateTimeZone('America/New_York');
    $t = new DateTime('@' . (int) ($now === null ? time() : $now));
    $t->setTimezone($tz);
    $freq = alt_digest_valid_freq($freq);
    $slot = array('daily' => array(6, 7), 'weekly' => array(7, 37), 'monthly' => array(9, 7))[$freq];
    $c = clone $t;
    $c->setTime($slot[0], $slot[1]);
    for ($i = 0; $i < 40; $i++) {
        $ok = $c > $t
            && ($freq !== 'weekly' || $c->format('N') === '1')
            && ($freq !== 'monthly' || $c->format('j') === '1');
        if ($ok) return $c->format('l j M Y');
        $c->modify('+1 day');
        $c->setTime($slot[0], $slot[1]);
    }
    return '';
}

function alt_welcome_body($row, $prefs_url) {
    $names = alt_digest_list_names();
    $lines = '';
    $freqs = array();
    foreach (alt_digest_lists() as $key => $cols) {
        if (empty($row[$cols['consent']])) continue;
        $f = alt_digest_valid_freq($row[$cols['freq']] ?? 'weekly');
        $freqs[$f] = true;
        $lines .= '  - ' . $names[$key] . ($key === 'articles' ? '' : ', ' . $f) . "\n";
    }
    $next = '';
    foreach (array('daily', 'weekly', 'monthly') as $f) {
        if (isset($freqs[$f])) { $next = alt_welcome_next_send($f); break; }
    }
    return "You're in. Thanks for confirming your subscription at asktherecruiter.com.\n\n"
         . "You get:\n" . $lines . "\n"
         . ($next !== '' ? "Your first edition is due " . $next . " (New York time).\n\n" : '')
         . "Change lists, frequency or follows here:\n" . $prefs_url . "\n\n"
         . "Every edition has a one-click unsubscribe at the foot.\n\n"
         . "AskTheRecruiter.com, 601 Van Ness Ave, San Francisco, CA 94102.\n";
}

/**
 * One welcome per confirmation. The caller (alt_digest_confirm) has already
 * won the single-use confirm_token claim, so a re-click never reaches here.
 * Skipped, and counted as skipped, once today's cap is spent.
 */
function alt_digest_send_welcome($row) {
    if (!is_array($row) || ($row['status'] ?? '') !== 'confirmed') return false;
    $b = alt_welcome_budget_status();
    if ((int) $b['welcome'] >= (int) $b['welcome_cap_effective']) {
        $b['welcome_skipped'] = (int) $b['welcome_skipped'] + 1;
        update_option('alt_mail_budget', $b, false);
        return false;
    }
    $headers = array_merge(alt_digest_from_header(), alt_digest_list_unsub_headers($row['unsub_token']));
    $ok = wp_mail($row['email'], 'AskTheRecruiter.com: you are subscribed',
                  alt_welcome_body($row, alt_prefs_url($row)), $headers);
    if ($ok) {
        $b['welcome'] = (int) $b['welcome'] + 1;
        update_option('alt_mail_budget', $b, false);
    }
    return (bool) $ok;
}

/* ------------------------------------------------------------------ */
/* Fallback digest: HTML + plain text                                  */
/* ------------------------------------------------------------------ */

/** The fallback footer as text, from the same blocks as the HTML. */
function alt_digest_footer_text($unsub_url, $manage_url = '') {
    $out = array();
    foreach (alt_digest_footer_blocks($unsub_url, $manage_url) as $block) {
        $t = implode(' ', $block['sentences']);
        if ($block['url']) $t = rtrim($t, '.') . ":\n" . $block['url'];
        $out[] = $t;
    }
    return implode("\n\n", $out);
}

/**
 * Deliver one fallback digest with BOTH parts.
 *
 * The Brevo WordPress plugin replaces wp_mail() wholesale and hands Brevo one
 * body, so `phpmailer_init`/AltBody never reaches it. So when the Brevo key is
 * present (alt_brevo_api_key, the same key the contact mirror uses) this goes
 * to Brevo's transactional API directly, which takes htmlContent AND
 * textContent: the same provider and account the relay's SMTP uses. Without a
 * key (plugin removed, core wp_mail) the AltBody hook DOES work, so it is set.
 */
function alt_digest_deliver($to, $subject, $html, $text, $unsub_token) {
    $key = function_exists('alt_brevo_api_key') ? alt_brevo_api_key() : '';
    if ($key !== '' && function_exists('wp_remote_request')) {
        $body = array(
            'sender'      => array('name' => ALT_DIGEST_FROM_NAME, 'email' => ALT_DIGEST_FROM_EMAIL),
            'to'          => array(array('email' => $to)),
            'replyTo'     => array('email' => ALT_DIGEST_REPLY_TO),
            'subject'     => $subject,
            'htmlContent' => $html,
            'textContent' => $text,
            'headers'     => array(
                'List-Unsubscribe'      => '<' . alt_digest_unsub_url($unsub_token) . '>',
                'List-Unsubscribe-Post' => 'List-Unsubscribe=One-Click',
            ),
        );
        try {
            $resp = wp_remote_request('https://api.brevo.com/v3/smtp/email', array(
                'method'  => 'POST',
                'timeout' => 15,
                'headers' => array('api-key' => $key, 'Content-Type' => 'application/json',
                                   'Accept' => 'application/json'),
                'body'    => wp_json_encode($body),
            ));
            if (!(function_exists('is_wp_error') && is_wp_error($resp))) {
                $code = (int) wp_remote_retrieve_response_code($resp);
                if ($code >= 200 && $code < 300) return true;
            }
        } catch (Throwable $e) { /* fall through to wp_mail; never log the address */ }
    }
    $alt = function ($phpmailer) use ($text) { $phpmailer->AltBody = $text; };
    if (function_exists('add_action')) add_action('phpmailer_init', $alt);
    $headers = array_merge(array('Content-Type: text/html; charset=UTF-8'), alt_digest_from_header(),
                           alt_digest_list_unsub_headers($unsub_token));
    $ok = wp_mail($to, $subject, $html, $headers);
    if (function_exists('remove_action')) remove_action('phpmailer_init', $alt);
    return $ok;
}
