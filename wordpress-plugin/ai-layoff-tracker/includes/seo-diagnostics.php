<?php
/**
 * SEO diagnostics — read-only, keyed access to the 404 log and the redirect
 * table that Rank Math keeps in this database.
 *
 * Why this exists. Both numbers that matter here live only in wp-admin: the
 * 404 monitor and the redirection list. A session working from the repo could
 * see neither, so every judgement about "which links are dead" and "what is
 * generating redirect traffic" was a guess against a screenshot. These two
 * routes make both readable from the same keyed API the pipeline already uses,
 * so the answer is measured rather than inferred.
 *
 * Three rules this file keeps.
 *
 * 1. It NEVER writes. No delete, no reset, no redirect creation. Clearing the
 *    404 log destroys the only record of what was hit, and a route that can
 *    clear it is a route that can be called by mistake. Redirects are created
 *    in wp-admin by a human who can see what they are pointing at.
 *
 * 2. It never returns the visitor IP. Rank Math stores one per 404 row and it
 *    is the only personal datum in either table. Nothing in this diagnosis
 *    needs it: cause is read from the URI, the referer and the user agent.
 *
 * 3. Absence of a table is a NAMED STATE, never an empty list. If Rank Math is
 *    inactive, or its 404 monitor was never switched on, the honest answer is
 *    "cannot tell", and a caller that reads that as "no 404s" would close a
 *    real leak as clean. The `state` field carries OK / TABLE_MISSING, and
 *    TABLE_MISSING comes back as HTTP 503 so a script cannot treat it as data.
 */

if (!defined('ABSPATH')) exit;

/**
 * True when a table physically exists. `SHOW TABLES LIKE` is the only check
 * that distinguishes "empty" from "absent"; a SELECT against a missing table
 * returns null for both.
 */
function alt_seo_table_exists($table) {
    global $wpdb;
    $found = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $table));
    return $found === $table;
}

function alt_seo_missing_table_error($table) {
    return new WP_Error(
        'alt_seo_table_missing',
        'Table ' . $table . ' does not exist. Rank Math may be inactive, or this '
            . 'module was never enabled. This is UNKNOWN, not zero.',
        array('status' => 503)
    );
}

/**
 * GET /seo-404s — the Rank Math 404 monitor log.
 *
 * Ordered by hit count so the worst offenders arrive first. `referer` is the
 * field that separates an internal-link defect from an external one, and
 * `user_agent` is the field that separates a reader from a crawler probing for
 * URLs that never existed, so both are returned in full.
 */
function alt_api_seo_404s($request) {
    global $wpdb;
    $table = $wpdb->prefix . 'rank_math_404_logs';
    if (!alt_seo_table_exists($table)) return alt_seo_missing_table_error($table);

    $limit = (int) $request->get_param('limit');
    if ($limit <= 0 || $limit > 2000) $limit = 500;

    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT id, uri, accessed, times_accessed, referer, user_agent
           FROM {$table}
          ORDER BY times_accessed DESC, accessed DESC
          LIMIT %d",
        $limit
    ), ARRAY_A);

    $total_rows = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$table}");
    $total_hits = (int) $wpdb->get_var("SELECT COALESCE(SUM(times_accessed), 0) FROM {$table}");

    return rest_ensure_response(array(
        'state'          => 'OK',
        'distinct_uris'  => $total_rows,
        'total_hits'     => $total_hits,
        'returned'       => count($rows),
        'rows'           => $rows ? $rows : array(),
    ));
}

/**
 * GET /seo-redirects — the Rank Math redirection table.
 *
 * `sources` is stored serialized (an array of pattern/comparison rules), so it
 * is unpacked here rather than handing a caller a PHP-serialized blob to parse.
 * `hits` is the number the diagnosis turns on: a redirect with heavy traffic
 * means something is still pointing at the source URL.
 */
function alt_api_seo_redirects($request) {
    global $wpdb;
    $table = $wpdb->prefix . 'rank_math_redirections';
    if (!alt_seo_table_exists($table)) return alt_seo_missing_table_error($table);

    $rows = $wpdb->get_results(
        "SELECT id, sources, url_to, header_code, hits, status, created, updated, last_accessed
           FROM {$table}
          ORDER BY hits DESC, id ASC",
        ARRAY_A
    );
    if (!$rows) $rows = array();

    $out = array();
    $total_hits = 0;
    foreach ($rows as $row) {
        $sources = maybe_unserialize($row['sources']);
        $patterns = array();
        if (is_array($sources)) {
            foreach ($sources as $source) {
                if (!is_array($source)) continue;
                $patterns[] = array(
                    'pattern'    => isset($source['pattern']) ? (string) $source['pattern'] : '',
                    'comparison' => isset($source['comparison']) ? (string) $source['comparison'] : '',
                );
            }
        }
        $total_hits += (int) $row['hits'];
        $out[] = array(
            'id'            => (int) $row['id'],
            'sources'       => $patterns,
            'url_to'        => (string) $row['url_to'],
            'header_code'   => (int) $row['header_code'],
            'hits'          => (int) $row['hits'],
            'status'        => (string) $row['status'],
            'created'       => (string) $row['created'],
            'updated'       => (string) $row['updated'],
            'last_accessed' => (string) $row['last_accessed'],
        );
    }

    return rest_ensure_response(array(
        'state'      => 'OK',
        'count'      => count($out),
        'total_hits' => $total_hits,
        'rows'       => $out,
    ));
}

function alt_seo_diagnostics_register_routes() {
    register_rest_route('layoffs/v1', '/seo-404s', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_seo_404s',
        'permission_callback' => 'alt_api_permission',
    ));
    register_rest_route('layoffs/v1', '/seo-redirects', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_seo_redirects',
        'permission_callback' => 'alt_api_permission',
    ));
}
add_action('rest_api_init', 'alt_seo_diagnostics_register_routes');
