<?php
/**
 * Keyed, allowlisted whole-table read for the weekly off-host backup.
 *
 * WHY THIS IS NOT includes/export.php
 * -----------------------------------
 * export.php is the READER download: one table, public, filtered, shaped by
 * alt_db_row_to_array() for humans. It deliberately drops `dedup_hash`, which
 * is the unique key /bulk upserts on, so a file produced from it CANNOT be
 * restored. A backup that cannot be restored is the failure mode this whole
 * change exists to close, so the backup read is a separate route with a
 * separate contract: raw columns, every row, keyset paged, key required.
 *
 * THE PERSONAL-DATA BOUNDARY IS STRUCTURAL, NOT A FILTER
 * -----------------------------------------------------
 * The artifact this feeds lands in a PUBLIC GitHub repo. wp_alt_subscribers
 * holds addresses, consent records and two live tokens; publishing it would be
 * a notifiable breach, not a style violation. So the boundary is an ALLOWLIST
 * of table names in alt_backup_tables(): a table that is not named there
 * cannot be requested, whatever the caller sends. There is no parameter that
 * takes a table name straight through, no wildcard, and no "all tables" mode.
 * alt_backup_forbidden_tables() then names the excluded ones explicitly and
 * alt_backup_tables() is asserted disjoint from it, so a future edit that adds
 * a personal table to the allowlist fails a test instead of shipping.
 *
 * A denylist over CONTENT ("does this look like an email") is not the guard and
 * must never be mistaken for it: excerpt and source_url hold arbitrary prose,
 * so no content rule can be complete. The name allowlist is complete because
 * the set of tables is finite and written down.
 *
 * Keyed like every other operational route (alt_api_permission: the
 * X-Layoff-API-Key header, 503 with no key configured, 403 on a wrong one).
 * Read-only: nothing here writes.
 */

if (!defined('ABSPATH')) exit;

/**
 * Bump when the shape of what this route emits changes in a way a restore has
 * to know about. The backup manifest records it, so a file restored a year
 * later can say whether it predates a change instead of guessing.
 */
if (!defined('ALT_BACKUP_SCHEMA_VERSION')) define('ALT_BACKUP_SCHEMA_VERSION', 1);

/**
 * THE ALLOWLIST. Logical name => how to reach it.
 *
 * `restorable` records the honest state of the return path, and it is not
 * decoration: the recovery runbook reads it. 'bulk' means /bulk rebuilds these
 * rows. 'derived' means the table is rebuilt by re-running a job rather than by
 * replaying the file, so the export is evidence and not the restore path.
 * 'manual' means there is no automated return path today.
 *
 * `optional` tables may legitimately not exist yet on a given deploy (a table
 * ships with the release that introduces it, and FTPS deploys race). A missing
 * optional table is reported as skipped-with-a-reason, never as zero rows:
 * "we could not read it" and "it is empty" are different answers and the
 * backup must not collapse them.
 */
function alt_backup_tables() {
    global $wpdb;
    return array(
        // The curated corpus. This is the one that cost real money to produce.
        'layoffs' => array(
            'table' => $wpdb->prefix . 'alt_layoffs',
            'pk' => 'id',
            'restorable' => 'bulk',
            'optional' => false,
        ),
        // The evidence graph. Rebuildable from layoffs by the event migration,
        // but a rebuild re-derives keys, so keeping the rows is cheaper.
        'events' => array(
            'table' => $wpdb->prefix . 'alt_events',
            'pk' => 'id',
            'restorable' => 'derived',
            'optional' => false,
        ),
        'source_reports' => array(
            'table' => $wpdb->prefix . 'alt_source_reports',
            'pk' => 'id',
            'restorable' => 'derived',
            'optional' => false,
        ),
        // Permanent-archive index. Every row here is a Wayback capture that
        // was rate-limited into existence over about a week; re-earning them
        // costs another week, so this is worth more than its size suggests.
        'archive' => array(
            'table' => $wpdb->prefix . 'alt_archive',
            'pk' => 'id',
            'restorable' => 'manual',
            'optional' => false,
        ),
        // Reviewed employer identities. Human review, not derivable.
        'company_directory' => array(
            'table' => $wpdb->prefix . 'alt_company_directory',
            'pk' => 'id',
            'restorable' => 'manual',
            'optional' => false,
        ),
        // Editorial WARN-transparency register. Human adjudication.
        'warn_transparency' => array(
            'table' => $wpdb->prefix . 'alt_warn_transparency',
            'pk' => 'id',
            'restorable' => 'manual',
            'optional' => false,
        ),
        // Collector telemetry. This is the history behind the health page and
        // every staleness verdict; losing it makes "has this source ever
        // worked" unanswerable.
        'source_runs' => array(
            'table' => $wpdb->prefix . 'alt_source_runs',
            'pk' => 'id',
            'restorable' => 'manual',
            'optional' => false,
        ),
        // Published digest editions. These render public archive pages, so
        // losing them 404s URLs that have been linked.
        'digest_editions' => array(
            'table' => $wpdb->prefix . 'alt_digest_editions',
            'pk' => 'id',
            'restorable' => 'manual',
            'optional' => true,
        ),
        // COUNTS ONLY. Read the schema before assuming otherwise: the columns
        // are (id, freq, sent_at, recipients, eligible). There is no address
        // column and no recipient id, deliberately, so this is a per-RUN log
        // and not a per-person one. It is in the allowlist for that reason.
        'digest_sends' => array(
            'table' => $wpdb->prefix . 'alt_digest_sends',
            'pk' => 'id',
            'restorable' => 'manual',
            'optional' => true,
        ),
        // AGGREGATE CLICK COUNTERS. Columns are (id, send_id, link_hash, url,
        // clicks). No subscriber id, no IP, no user agent, no per-click row, so
        // the store cannot answer "who clicked" even in principle. `url` is a
        // destination this site composed and allow-listed, never a per-recipient
        // tokenised link: alt_digest_track_link() stores the plain destination
        // and hands the READER a /click?s=&l= wrapper built from a send id and
        // a hash of the URL.
        'digest_links' => array(
            'table' => $wpdb->prefix . 'alt_digest_links',
            'pk' => 'id',
            'restorable' => 'manual',
            'optional' => true,
        ),
        // Two integers: a post id and a count. There is nowhere here to record
        // who, when, or from where.
        'post_claps' => array(
            'table' => $wpdb->prefix . 'alt_post_claps',
            'pk' => 'post_id',
            'restorable' => 'manual',
            'optional' => true,
        ),
    );
}

/**
 * Tables this plugin owns that are DELIBERATELY not backed up, and why. Naming
 * them is the point: an exclusion nobody wrote down is an exclusion the next
 * session re-litigates, and an exclusion the tests cannot check.
 *
 * The reason strings are read by the recovery runbook and by
 * tests/test_backup_personal_data.py.
 */
function alt_backup_forbidden_tables() {
    global $wpdb;
    return array(
        $wpdb->prefix . 'alt_subscribers' =>
            'Personal data: email addresses, consent records, and two live '
            . 'tokens (confirm_token, unsub_token). The backup artifact is '
            . 'published to a PUBLIC repository, so this table can never be in '
            . 'it. A private destination is an owner decision that has not been '
            . 'made; see docs/RECOVERY.md.',
    );
}

/** The spec for a requested logical name, or null. Null is the only refusal. */
function alt_backup_table_spec($name) {
    $tables = alt_backup_tables();
    $name = (string) $name;
    return isset($tables[$name]) ? $tables[$name] : null;
}

/** True when the table physically exists. Absent != empty; callers must differ. */
function alt_backup_table_exists($table) {
    global $wpdb;
    return $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table;
}

add_action('rest_api_init', 'alt_backup_register_routes');
function alt_backup_register_routes() {
    register_rest_route('layoffs/v1', '/backup-manifest', array(
        'methods' => 'GET',
        'callback' => 'alt_api_backup_manifest',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    register_rest_route('layoffs/v1', '/backup-table', array(
        'methods' => 'GET',
        'callback' => 'alt_api_backup_table',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
}

/**
 * What there is to back up, and how much of it, without moving any of it.
 * The weekly job reads this FIRST so its drift check has a row count that does
 * not depend on having walked the table successfully.
 */
function alt_api_backup_manifest() {
    global $wpdb;
    $out = array();
    foreach (alt_backup_tables() as $name => $spec) {
        if (!alt_backup_table_exists($spec['table'])) {
            // UNKNOWN, not zero. An optional table that has not shipped yet is
            // a different fact from a table that shipped and holds nothing.
            $out[$name] = array(
                'rows' => null,
                'state' => $spec['optional'] ? 'absent_optional' : 'absent_unexpected',
                'restorable' => $spec['restorable'],
            );
            continue;
        }
        $out[$name] = array(
            'rows' => (int) $wpdb->get_var('SELECT COUNT(*) FROM ' . $spec['table']),
            'state' => 'present',
            'restorable' => $spec['restorable'],
        );
    }
    $excluded = array();
    foreach (alt_backup_forbidden_tables() as $table => $why) {
        // The name of the table and the reason, never a row count: a count is
        // still a fact about a personal-data table and this response is written
        // into a log.
        $excluded[] = array('table' => $table, 'reason' => $why);
    }
    $r = rest_ensure_response(array(
        'schema_version' => ALT_BACKUP_SCHEMA_VERSION,
        'plugin_version' => defined('ALT_VERSION') ? ALT_VERSION : '',
        'build' => function_exists('alt_build_stamp') ? alt_build_stamp() : '',
        'generated_at' => gmdate('c'),
        'tables' => $out,
        'excluded' => $excluded,
    ));
    $r->header('Cache-Control', 'no-store, max-age=0');
    return $r;
}

/**
 * One keyset page of one allowlisted table, raw columns.
 *
 * Keyset and not OFFSET for the same reason /changed-rows is: an import
 * landing mid-walk shifts every later offset, which silently drops rows. On a
 * backup a silently dropped row is the whole defect.
 */
function alt_api_backup_table(WP_REST_Request $r) {
    global $wpdb;

    $name = (string) $r->get_param('table');
    $spec = alt_backup_table_spec($name);
    if ($spec === null) {
        return new WP_Error(
            'alt_backup_table_not_allowed',
            'Unknown table. This route serves an allowlist and nothing else; '
            . 'see alt_backup_tables(). Allowed: ' . implode(', ', array_keys(alt_backup_tables())) . '.',
            array('status' => 400)
        );
    }
    if (!alt_backup_table_exists($spec['table'])) {
        return new WP_Error(
            'alt_backup_table_absent',
            'That table does not exist on this install.',
            array('status' => $spec['optional'] ? 404 : 500)
        );
    }

    $limit = (int) $r->get_param('limit');
    if ($limit <= 0) $limit = 1000;
    $limit = min(5000, $limit);

    $pk = $spec['pk'];
    $after = (int) $r->get_param('after');

    // One extra row is how we learn there is a next page without a second query.
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT * FROM {$spec['table']} WHERE {$pk} > %d ORDER BY {$pk} ASC LIMIT %d",
        $after, $limit + 1
    ), ARRAY_A);
    if (!is_array($rows)) $rows = array();

    $next_after = null;
    if (count($rows) > $limit) {
        $rows = array_slice($rows, 0, $limit);
        $last = end($rows);
        $next_after = (int) $last[$pk];
    }

    $resp = rest_ensure_response(array(
        'table' => $name,
        'pk' => $pk,
        'schema_version' => ALT_BACKUP_SCHEMA_VERSION,
        'rows' => $rows,
        'next_after' => $next_after,
    ));
    $resp->header('Cache-Control', 'no-store, max-age=0');
    return $resp;
}
