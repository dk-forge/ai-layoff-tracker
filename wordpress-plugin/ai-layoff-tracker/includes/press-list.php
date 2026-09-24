<?php
/**
 * Press list: an ADMIN-ONLY table of journalist contacts, and a monthly pitch
 * that is sent ONLY when an admin clicks Send.
 *
 * Owner addition 2026-09-24. The rules, each pinned by tests/test_press_list.py:
 *   - manage_options + nonce on every screen and action; no REST route, no
 *     export. The table holds personal contact data.
 *   - Nothing schedules a send. wp_mail is called in one place, the click
 *     handler, and a contact already pitched for the period is skipped.
 *   - Every email carries an opt-out link; opting out is recorded (status +
 *     timestamp) and a CSV re-import can never re-activate that contact.
 *   - Who is on the list, and on what basis (consent_note), is the owner's
 *     call. There is no scraped or bought list, and there must not be one.
 *
 * The pitch text is the one the daily tick froze (alt_monthly_report_latest,
 * includes/monthly-report.php). Mail goes through wp_mail, which on this
 * install the Brevo plugin carries under its own From identity.
 * Runbook: docs/RUNBOOK_GROWTH.md, "Press list".
 */
if (!defined('ABSPATH')) exit;

function alt_press_table() { global $wpdb; return $wpdb->prefix . 'alt_press_contacts'; }

/** Create/upgrade the table once per plugin version (FTP deploys skip activation). */
function alt_press_install() {
    if (get_option('alt_press_db_version') === ALT_VERSION) return;
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $t = alt_press_table();
    $charset = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE $t (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        name VARCHAR(160) NOT NULL DEFAULT '',
        outlet VARCHAR(160) NOT NULL DEFAULT '',
        email VARCHAR(190) NOT NULL,
        beat VARCHAR(160) NOT NULL DEFAULT '',
        consent_note VARCHAR(255) NOT NULL DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'active',
        optout_token CHAR(32) NOT NULL DEFAULT '',
        last_contacted DATETIME NULL,
        last_pitched_period VARCHAR(7) NOT NULL DEFAULT '',
        opted_out_at DATETIME NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY email (email), KEY status (status)
    ) $charset;");
    update_option('alt_press_db_version', ALT_VERSION, false);
}
add_action('admin_init', 'alt_press_install');

/**
 * Parse an uploaded CSV. A header row is REQUIRED (name,outlet,email,beat,
 * consent_note in any order, email mandatory) so a file with shifted columns
 * cannot store an outlet as an address. Pure.
 */
function alt_press_parse_csv($text) {
    $out = array('rows' => array(), 'rejected' => array(), 'error' => '');
    $lines = preg_split('/\r\n|\n|\r/', trim((string) $text));
    if (!$lines || trim($lines[0]) === '') { $out['error'] = 'empty file'; return $out; }
    $head = array_map(function ($h) { return strtolower(trim($h)); }, str_getcsv(array_shift($lines)));
    if (!in_array('email', $head, true)) {
        $out['error'] = 'the first row must be a header naming an email column';
        return $out;
    }
    foreach ($lines as $i => $line) {
        if (trim($line) === '') continue;
        $cells = str_getcsv($line);
        $row = array();
        foreach (array('name', 'outlet', 'email', 'beat', 'consent_note') as $col) {
            $k = array_search($col, $head, true);
            $row[$col] = ($k !== false && isset($cells[$k])) ? sanitize_text_field($cells[$k]) : '';
        }
        $row['email'] = strtolower(sanitize_email($row['email']));
        if (!is_email($row['email'])) { $out['rejected'][] = $i + 2; continue; }
        $out['rows'][] = $row;
    }
    return $out;
}

/** The email body for one contact. Pure. */
function alt_press_email_body($contact, $pitch, $optout_url) {
    $first = trim((string) strtok(trim((string) ($contact['name'] ?? '')), ' '));
    $hello = $first !== '' ? 'Hi ' . $first . ',' : 'Hello,';
    return $hello . "\n\n"
        . "The AI Layoff Tracker's monthly report is out. The summary is below, and every figure links to its source.\n\n"
        . trim((string) $pitch) . "\n\n"
        . "Happy to pull a custom cut of the data for a story.\n\n"
        . "AskTheRecruiter.com\n\n"
        . "--\nYou received this because your address is on our press list. "
        . "To opt out, open this link and confirm; we will not email you again: " . $optout_url . "\n";
}

function alt_press_optout_url($contact) {
    return add_query_arg('alt_press_optout', (int) $contact['id'] . '.' . $contact['optout_token'], home_url('/'));
}

/** Admin screen: Tools > Press list. */
add_action('admin_menu', function () {
    add_management_page('Press list', 'Press list', 'manage_options', 'alt-press-list', 'alt_press_admin_page');
});

function alt_press_admin_page() {
    if (!current_user_can('manage_options')) wp_die('Not allowed.');
    global $wpdb;
    $t = alt_press_table();
    $rows = $wpdb->get_results("SELECT * FROM $t ORDER BY status ASC, outlet ASC, name ASC LIMIT 2000", ARRAY_A) ?: array();
    $latest = get_option('alt_monthly_report_latest');
    $period = is_array($latest) ? (string) ($latest['period'] ?? '') : '';
    $post = esc_url(admin_url('admin-post.php'));
    echo '<div class="wrap"><h1>Press list</h1>';
    if (isset($_GET['alt_msg'])) echo '<div class="notice notice-info"><p>' . esc_html(wp_unslash($_GET['alt_msg'])) . '</p></div>';
    echo '<p>Journalists who agreed to hear from us, or whose press address is published for this purpose. Record the basis in the consent note. Nothing here sends on its own: a pitch goes out only when you click Send, once per contact per month, with an opt-out link.</p>';
    if ($period) {
        echo '<h2>Pitch for ' . esc_html($latest['label'] ?? $period) . '</h2><textarea readonly rows="10" style="width:100%">' . esc_textarea((string) ($latest['pitch'] ?? '')) . '</textarea>';
    } else {
        echo '<p><b>No monthly pitch has been generated yet.</b> The daily tick creates it on the first business day of the month.</p>';
    }
    echo '<form method="post" action="' . $post . '">';
    wp_nonce_field('alt_press_send');
    echo '<input type="hidden" name="action" value="alt_press_send"><table class="widefat striped"><thead><tr><th></th><th>Name</th><th>Outlet</th><th>Email</th><th>Beat</th><th>Basis</th><th>Status</th><th>Last contacted</th></tr></thead><tbody>';
    foreach ($rows as $r) {
        $can = $r['status'] === 'active' && $period !== '' && $r['last_pitched_period'] !== $period;
        echo '<tr><td>' . ($can ? '<input type="checkbox" name="ids[]" value="' . (int) $r['id'] . '">' : '') . '</td><td>' . esc_html($r['name']) . '</td><td>' . esc_html($r['outlet'])
            . '</td><td>' . esc_html($r['email']) . '</td><td>' . esc_html($r['beat']) . '</td><td>' . esc_html($r['consent_note'])
            . '</td><td>' . esc_html($r['status']) . '</td><td>' . esc_html((string) $r['last_contacted']) . '</td></tr>';
    }
    echo '</tbody></table><p><button class="button button-primary" type="submit"' . ($period ? '' : ' disabled') . '>Send the monthly pitch to the ticked contacts</button></p></form>';
    echo '<h2>Add a contact</h2><form method="post" action="' . $post . '">';
    wp_nonce_field('alt_press_add');
    echo '<input type="hidden" name="action" value="alt_press_add">';
    foreach (array('name' => 'Name', 'outlet' => 'Outlet', 'email' => 'Email', 'beat' => 'Beat', 'consent_note' => 'Basis (how they agreed / where the address is published)') as $k => $label) {
        echo '<p><label>' . esc_html($label) . '<br><input type="' . ($k === 'email' ? 'email' : 'text') . '" name="' . $k . '"' . ($k === 'email' ? ' required' : '') . ' style="width:30em"></label></p>';
    }
    echo '<p><button class="button" type="submit">Add</button></p></form>';
    echo '<h2>Press-page signups</h2><p>Reporters who asked for the monthly brief on the press page have opted in. Copy them onto this list:</p><form method="post" action="' . $post . '">';
    wp_nonce_field('alt_press_import_signups');
    echo '<input type="hidden" name="action" value="alt_press_import_signups"><button class="button" type="submit">Copy press-page signups</button></form>';
    echo '<h2>Import CSV</h2><p>Header row required: name,outlet,email,beat,consent_note. Existing addresses are updated; an opted-out contact stays opted out.</p><form method="post" enctype="multipart/form-data" action="' . $post . '">';
    wp_nonce_field('alt_press_import');
    echo '<input type="hidden" name="action" value="alt_press_import"><input type="file" name="csv" accept=".csv,text/csv" required> <button class="button" type="submit">Import</button></form></div>';
}

function alt_press_back($msg) {
    wp_safe_redirect(add_query_arg(array('page' => 'alt-press-list', 'alt_msg' => rawurlencode($msg)), admin_url('tools.php')));
    exit;
}

function alt_press_upsert(array $row) {
    global $wpdb;
    $t = alt_press_table();
    // Status is NOT in the UPDATE list: an opted-out contact stays opted out.
    return $wpdb->query($wpdb->prepare(
        "INSERT INTO $t (name, outlet, email, beat, consent_note, status, optout_token, created_at)
         VALUES (%s, %s, %s, %s, %s, 'active', %s, %s)
         ON DUPLICATE KEY UPDATE name = VALUES(name), outlet = VALUES(outlet), beat = VALUES(beat), consent_note = VALUES(consent_note)",
        $row['name'], $row['outlet'], $row['email'], $row['beat'], $row['consent_note'],
        wp_generate_password(32, false, false), current_time('mysql', true)));
}

function alt_press_admin_add() {
    if (!current_user_can('manage_options')) wp_die('Not allowed.');
    check_admin_referer('alt_press_add');
    $row = array();
    foreach (array('name', 'outlet', 'beat', 'consent_note') as $k) $row[$k] = sanitize_text_field(wp_unslash($_POST[$k] ?? ''));
    $row['email'] = strtolower(sanitize_email(wp_unslash($_POST['email'] ?? '')));
    if (!is_email($row['email'])) alt_press_back('That email address is not valid.');
    alt_press_upsert($row);
    alt_press_back('Contact saved.');
}
add_action('admin_post_alt_press_add', 'alt_press_admin_add');

function alt_press_admin_import() {
    if (!current_user_can('manage_options')) wp_die('Not allowed.');
    check_admin_referer('alt_press_import');
    $file = $_FILES['csv']['tmp_name'] ?? '';
    if (!$file || !is_uploaded_file($file) || filesize($file) > 1048576) alt_press_back('Upload a CSV under 1 MB.');
    $parsed = alt_press_parse_csv(file_get_contents($file));
    if ($parsed['error']) alt_press_back('Import refused: ' . $parsed['error'] . '.');
    $n = 0;
    foreach ($parsed['rows'] as $row) { if (alt_press_upsert($row) !== false) $n++; }
    // alt_press_upsert: INSERT ... ON DUPLICATE KEY UPDATE, never touching status.
    alt_press_back(sprintf('Imported %d contacts; %d rows rejected for an invalid address.', $n, count($parsed['rejected'])));
}
add_action('admin_post_alt_press_import', 'alt_press_admin_import');

/** Copy the opted-in press-page signups (alt_press_subscribers) onto the list. */
function alt_press_admin_import_signups() {
    if (!current_user_can('manage_options')) wp_die('Not allowed.');
    check_admin_referer('alt_press_import_signups');
    $n = 0;
    foreach ((array) get_option('alt_press_subscribers', array()) as $sub) {
        if (($sub['status'] ?? 'active') !== 'active' || !is_email($sub['email'] ?? '')) continue;
        alt_press_upsert(array('name' => (string) ($sub['name'] ?? ''), 'outlet' => (string) ($sub['outlet'] ?? ''),
            'email' => strtolower((string) $sub['email']), 'beat' => '',
            'consent_note' => 'Signed up for the monthly brief on the press page, ' . substr((string) ($sub['joined'] ?? ''), 0, 10)));
        $n++;
    }
    alt_press_back(sprintf('Copied %d press-page signups.', $n));
}
add_action('admin_post_alt_press_import_signups', 'alt_press_admin_import_signups');

/** The ONLY sender. Runs on an admin's click, for the ticked contacts. */
function alt_press_admin_send() {
    if (!current_user_can('manage_options')) wp_die('Not allowed.');
    check_admin_referer('alt_press_send');
    $latest = get_option('alt_monthly_report_latest');
    $period = is_array($latest) ? (string) ($latest['period'] ?? '') : '';
    if ($period === '' || empty($latest['pitch'])) alt_press_back('No monthly pitch to send yet.');
    $ids = array_values(array_filter(array_map('intval', (array) ($_POST['ids'] ?? array()))));
    if (!$ids) alt_press_back('Tick at least one contact.');
    global $wpdb;
    $t = alt_press_table();
    $in = implode(',', array_fill(0, count($ids), '%d'));
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT * FROM $t WHERE id IN ($in) AND status = 'active' AND last_pitched_period <> %s",
        array_merge($ids, array($period))), ARRAY_A) ?: array();
    $sent = 0;
    $subject = 'AI Layoff Tracker monthly report: ' . ($latest['label'] ?? $period);
    foreach ($rows as $c) {
        $body = alt_press_email_body($c, $latest['pitch'], alt_press_optout_url($c));
        if (wp_mail($c['email'], $subject, $body, array('Content-Type: text/plain; charset=UTF-8'))) {
            $wpdb->update($t, array('last_contacted' => current_time('mysql', true), 'last_pitched_period' => $period),
                          array('id' => (int) $c['id']));
            $sent++;
        }
    }
    alt_press_back(sprintf('Sent %d of %d ticked; opted-out or already pitched this month were skipped.', $sent, count($ids)));
}
add_action('admin_post_alt_press_send', 'alt_press_admin_send');

/**
 * Opt-out: GET shows a confirm button, POST records it. A GET alone never
 * changes anything, because mail scanners prefetch links.
 */
function alt_press_optout_route() {
    if (!isset($_GET['alt_press_optout'])) return;
    $raw = sanitize_text_field(wp_unslash($_GET['alt_press_optout']));
    list($id, $tok) = array_pad(explode('.', $raw, 2), 2, '');
    global $wpdb;
    $t = alt_press_table();
    $row = $wpdb->get_row($wpdb->prepare("SELECT id, optout_token, status FROM $t WHERE id = %d", (int) $id), ARRAY_A);
    $ok = $row && $tok !== '' && hash_equals((string) $row['optout_token'], (string) $tok);
    nocache_headers();
    header('Content-Type: text/html; charset=utf-8');
    header('X-Robots-Tag: noindex');
    if (!$ok) { echo '<p>This opt-out link is not valid.</p>'; exit; }
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
        $wpdb->update($t, array('status' => 'opted_out', 'opted_out_at' => current_time('mysql', true)), array('id' => (int) $row['id']));
        echo '<p>Done. You are off the AI Layoff Tracker press list and we will not email you again.</p>';
        exit;
    }
    echo '<form method="post"><p>Stop press emails from the AI Layoff Tracker?</p><button type="submit">Yes, opt me out</button></form>';
    exit;
}
add_action('template_redirect', 'alt_press_optout_route', 0);
