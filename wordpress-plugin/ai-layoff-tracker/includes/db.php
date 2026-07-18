<?php
/**
 * Fast query layer.
 *
 * WordPress postmeta can't filter/aggregate 100K+ layoffs at interactive speed
 * (meta_query does expensive self-JOINs). So we keep a denormalized, indexed
 * table as the query surface. "Rich" entries (SEC/news/curated) still live as
 * `layoffs` CPT posts for their permalink pages and are mirrored here on save;
 * high-volume bulk data (WARN notices) can live here alone.
 *
 * Endpoints backed by this table:
 *   GET layoffs/v1/query      paginated + filtered + sorted rows
 *   GET layoffs/v1/aggregate  filtered totals, top-N, and time series
 */
if (!defined('ABSPATH')) exit;

function alt_db_table() {
    global $wpdb;
    return $wpdb->prefix . 'alt_layoffs';
}

/** Create/upgrade the table. Safe to call repeatedly (dbDelta diffs it). */
function alt_db_install() {
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $table = alt_db_table();
    $charset = $wpdb->get_charset_collate();
    $sql = "CREATE TABLE $table (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        post_id BIGINT UNSIGNED NULL,
        dedup_hash CHAR(32) NOT NULL DEFAULT '',
        company VARCHAR(255) NOT NULL DEFAULT '',
        company_key VARCHAR(255) NOT NULL DEFAULT '',
        ticker VARCHAR(32) NOT NULL DEFAULT '',
        job_count INT UNSIGNED NOT NULL DEFAULT 0,
        layoff_date DATE NULL,
        announcement_date DATE NULL,
        industry VARCHAR(120) NOT NULL DEFAULT '',
        country VARCHAR(64) NOT NULL DEFAULT '',
        employer_country VARCHAR(64) NOT NULL DEFAULT '',
        employer_country_evidence TEXT NULL,
        announcement_evidence TEXT NULL,
        state CHAR(2) NOT NULL DEFAULT '',
        source_type VARCHAR(32) NOT NULL DEFAULT '',
        verification_level VARCHAR(16) NOT NULL DEFAULT '',
        source_name VARCHAR(191) NOT NULL DEFAULT '',
        source_url TEXT NULL,
        ai_explicit TINYINT(1) NOT NULL DEFAULT 0,
        ai_causation VARCHAR(32) NOT NULL DEFAULT 'unknown',
        confidence TINYINT UNSIGNED NOT NULL DEFAULT 0,
        review_status VARCHAR(32) NOT NULL DEFAULT 'legacy_unreviewed',
        announced TINYINT(1) NOT NULL DEFAULT 0,
        edited TINYINT(1) NOT NULL DEFAULT 0,
        ai_language TEXT NULL,
        reason_tags VARCHAR(255) NOT NULL DEFAULT '',
        roles TEXT NULL,
        excerpt TEXT NULL,
        event_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
        PRIMARY KEY (id),
        UNIQUE KEY dedup_hash (dedup_hash),
        KEY layoff_date (layoff_date),
        KEY announcement_date (announcement_date),
        KEY state (state),
        KEY country (country),
        KEY industry (industry),
        KEY source_type (source_type),
        KEY ai_explicit (ai_explicit),
        KEY ai_causation (ai_causation),
        KEY review_status (review_status),
        KEY company_key (company_key),
        /* Read-only announcement-to-later-evidence candidate lookup. This is
         * deliberately not a merge index: candidates remain editorial work. */
        KEY lifecycle_lookup (announced, company_key, job_count, layoff_date),
        KEY post_id (post_id),
        KEY event_id (event_id)
    ) $charset;";
    dbDelta($sql);

    // One canonical event may have many independently preserved reports. The
    // tracker counts the canonical row once; this evidence store keeps every
    // corroborating source instead of throwing duplicates away.
    $events = $wpdb->prefix . 'alt_events';
    $reports = $wpdb->prefix . 'alt_source_reports';
    dbDelta("CREATE TABLE $events (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        event_key CHAR(32) NOT NULL,
        canonical_layoff_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY event_key (event_key), KEY canonical_layoff_id (canonical_layoff_id)
    ) $charset;");
    dbDelta("CREATE TABLE $reports (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        event_id BIGINT UNSIGNED NOT NULL,
        report_key CHAR(32) NOT NULL,
        source_name VARCHAR(191) NOT NULL DEFAULT '',
        source_type VARCHAR(32) NOT NULL DEFAULT '',
        verification_level VARCHAR(16) NOT NULL DEFAULT '',
        source_url TEXT NULL,
        excerpt TEXT NULL,
        evidence_hash CHAR(64) NOT NULL DEFAULT '',
        ai_causation VARCHAR(32) NOT NULL DEFAULT 'unknown',
        ai_language TEXT NULL,
        observed_at DATETIME NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY report_key (report_key), KEY event_id (event_id)
    ) $charset;");

    // Append-only operational telemetry. This begins at deployment rather
    // than reconstructing unrecorded legacy run volumes. It records collector
    // attempts only; it is not a layoff-event or source-evidence store.
    $source_runs = alt_source_runs_table();
    dbDelta("CREATE TABLE $source_runs (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        source VARCHAR(64) NOT NULL DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'degraded',
        entries INT UNSIGNED NOT NULL DEFAULT 0,
        detail VARCHAR(240) NOT NULL DEFAULT '',
        attempted_at DATETIME NOT NULL,
        PRIMARY KEY (id),
        KEY source_attempted_at (source, attempted_at),
        KEY attempted_at (attempted_at)
    ) $charset;");

    // A reviewed identity registry is intentionally separate from raw event
    // names. `company_key` is a useful dedup key, not proof that every name
    // collapsing to it belongs to one legal employer.
    $directory = alt_company_directory_table();
    dbDelta("CREATE TABLE $directory (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        company_key VARCHAR(255) NOT NULL,
        slug VARCHAR(191) NOT NULL,
        display_name VARCHAR(255) NOT NULL,
        aliases LONGTEXT NULL,
        review_status VARCHAR(32) NOT NULL DEFAULT 'pending',
        reviewed_at DATETIME NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY company_key (company_key), UNIQUE KEY slug (slug), KEY review_status (review_status)
    ) $charset;");

    // Separate editorial WARN-transparency register. It is intentionally not
    // joined to layoff tables or aggregate endpoints: notice timing alone is
    // not a layoff count or legal finding.
    $warn_transparency = alt_warn_transparency_table();
    dbDelta("CREATE TABLE $warn_transparency (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        record_key CHAR(32) NOT NULL,
        state CHAR(2) NOT NULL DEFAULT '',
        employer VARCHAR(255) NOT NULL DEFAULT '',
        related_layoff_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
        assessment_status VARCHAR(48) NOT NULL DEFAULT '',
        notice_date DATE NULL,
        affected_date DATE NULL,
        exception_evidence TEXT NULL,
        adjudication_url TEXT NULL,
        source_name VARCHAR(191) NOT NULL DEFAULT '',
        source_url TEXT NULL,
        evidence_excerpt TEXT NULL,
        evidence_hash CHAR(64) NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY record_key (record_key),
        KEY state_status (state, assessment_status), KEY related_layoff_id (related_layoff_id)
    ) $charset;");
}

function alt_events_table() { global $wpdb; return $wpdb->prefix . 'alt_events'; }
function alt_source_reports_table() { global $wpdb; return $wpdb->prefix . 'alt_source_reports'; }
function alt_company_directory_table() { global $wpdb; return $wpdb->prefix . 'alt_company_directory'; }
function alt_source_runs_table() { global $wpdb; return $wpdb->prefix . 'alt_source_runs'; }
function alt_warn_transparency_table() { global $wpdb; return $wpdb->prefix . 'alt_warn_transparency'; }

/**
 * FTP deployment can serve a request while files are still arriving. Keep the
 * collector ledger self-healing: a writer verifies this one additive table
 * before using it, then runs the idempotent dbDelta installer if needed.
 */
function alt_source_runs_table_ready() {
    global $wpdb;
    $table = alt_source_runs_table();
    $exists = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table)));
    if ($exists === $table) return true;
    alt_db_install();
    return $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table;
}

/** Attach a canonical row to an event, creating the event if needed. */
function alt_event_for_layoff($layoff_id) {
    global $wpdb;
    $layoff_id = (int) $layoff_id;
    $row = $wpdb->get_row($wpdb->prepare("SELECT id, event_id, dedup_hash FROM " . alt_db_table() . " WHERE id = %d", $layoff_id));
    if (!$row) return 0;
    if (!empty($row->event_id)) return (int) $row->event_id;
    $key = preg_match('/^[a-f0-9]{32}$/', (string) $row->dedup_hash) ? $row->dedup_hash : md5('event:' . $layoff_id);
    $events = alt_events_table();
    $wpdb->query($wpdb->prepare("INSERT IGNORE INTO $events (event_key, canonical_layoff_id, created_at) VALUES (%s, %d, UTC_TIMESTAMP())", $key, $layoff_id));
    $event_id = (int) $wpdb->get_var($wpdb->prepare("SELECT id FROM $events WHERE event_key = %s", $key));
    if ($event_id) $wpdb->update(alt_db_table(), array('event_id' => $event_id), array('id' => $layoff_id));
    return $event_id;
}

/** Store a source report idempotently; source links are never deleted by dedup. */
function alt_event_add_report($event_id, $source) {
    global $wpdb;
    $event_id = (int) $event_id;
    $url = esc_url_raw($source['source_url'] ?? '');
    $name = sanitize_text_field($source['source_name'] ?? '');
    if (!$event_id || ($url === '' && $name === '')) return 0;
    $key = md5($event_id . '|' . $url . '|' . $name);
    $table = alt_source_reports_table();
    $excerpt = sanitize_textarea_field($source['excerpt'] ?? '');
    $evidence_hash = $excerpt === '' ? '' : hash('sha256', $excerpt);
    $wpdb->query($wpdb->prepare(
        "INSERT IGNORE INTO $table (event_id, report_key, source_name, source_type, verification_level, source_url, excerpt, evidence_hash, ai_causation, ai_language, observed_at) VALUES (%d, %s, %s, %s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())",
        $event_id, $key, $name, sanitize_key($source['source_type'] ?? ''), sanitize_key($source['verification_level'] ?? ''), $url,
        $excerpt, $evidence_hash, alt_normalize_ai_causation($source['ai_causation'] ?? 'unknown'),
        sanitize_text_field($source['ai_language'] ?? '')
    ));
    return (int) $wpdb->insert_id;
}

/** Remove an event graph only after its last canonical row is gone. */
function alt_cleanup_orphan_event($event_id) {
    global $wpdb;
    $event_id = (int) $event_id;
    if (!$event_id) return false;
    $layoffs = alt_db_table();
    if ((int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM $layoffs WHERE event_id = %d", $event_id)) > 0) {
        return false;
    }
    $wpdb->delete(alt_source_reports_table(), array('event_id' => $event_id));
    return (bool) $wpdb->delete(alt_events_table(), array('id' => $event_id));
}

function alt_event_register_report_for_layoff($layoff_id, $source) {
    global $wpdb;
    $event_id = alt_event_for_layoff($layoff_id);
    if ($event_id) {
        // Ensure the canonical row's own original source is retained even
        // when the first event touch is an incoming duplicate, before the
        // background legacy migration reaches that row.
        $canonical = $wpdb->get_row($wpdb->prepare(
            "SELECT source_name, source_type, verification_level, source_url, excerpt, ai_causation, ai_language FROM " . alt_db_table() . " WHERE id = %d", (int) $layoff_id), ARRAY_A);
        if ($canonical) alt_event_add_report($event_id, $canonical);
        alt_event_add_report($event_id, $source);
    }
    return $event_id;
}

function alt_event_sources_for_layoff($layoff_id) {
    global $wpdb;
    $event_id = alt_event_for_layoff($layoff_id);
    if (!$event_id) return array();
    return $wpdb->get_results($wpdb->prepare("SELECT source_name, source_type, verification_level, source_url, excerpt, evidence_hash, ai_causation, ai_language, observed_at FROM " . alt_source_reports_table() . " WHERE event_id = %d ORDER BY id ASC", $event_id), ARRAY_A) ?: array();
}

/** Reason tags are stored as ",tag1,tag2," so a filter is a simple LIKE. */
function alt_db_pack_tags($tags) {
    $tags = array_values(array_filter(array_map('sanitize_key', (array) $tags)));
    return $tags ? ',' . implode(',', $tags) . ',' : '';
}
function alt_db_unpack_tags($packed) {
    $packed = trim((string) $packed, ',');
    return $packed === '' ? array() : explode(',', $packed);
}

/**
 * Editorial suppression list: dedup hashes of entries an editor removed or
 * corrected. Imports re-run daily against the same source data, so a plain
 * delete would be undone on the next run — a suppressed hash is skipped by
 * every ingest path instead. Stored as hash => reason in one option (the
 * list is editorial-scale: dozens, not thousands).
 */
function alt_suppressed_hashes() {
    $v = get_option('alt_suppressed_hashes');
    return is_array($v) ? $v : array();
}

/**
 * Public corrections trail: every /edit and /trash appends here, and the
 * on-page "Data notes & corrections log" renders from it — disclosure is
 * structural, not a manual habit.
 */
function alt_log_correction($action, $ids, $reason, $detail = '') {
    $log = get_option('alt_corrections_log');
    if (!is_array($log)) $log = array();
    $log[] = array(
        'date'   => gmdate('Y-m-d'),
        'action' => $action,
        'count'  => count((array) $ids),
        'reason' => substr((string) $reason, 0, 400),
        'detail' => substr((string) $detail, 0, 200),
    );
    if (count($log) > 200) $log = array_slice($log, -200);
    update_option('alt_corrections_log', $log, false);
}
function alt_suppress_hash($hash, $reason) {
    $hash = substr((string) $hash, 0, 32);
    if ($hash === '') return;
    $list = alt_suppressed_hashes();
    $list[$hash] = substr((string) $reason, 0, 500);
    update_option('alt_suppressed_hashes', $list, false);
}
function alt_is_suppressed($hash) {
    $hash = substr((string) $hash, 0, 32);
    return $hash !== '' && array_key_exists($hash, alt_suppressed_hashes());
}

/**
 * A layoff date is stored only if it is a real calendar date. A bare
 * format regex let "2026-03-32" through, which MySQL coerced to the zero
 * date '0000-00-00' — that then sorted FIRST on ascending sorts, became
 * totals.min_date, and emitted a "0-00" series bucket (super test 2026-07-15).
 */
function alt_db_valid_date($d) {
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $d, $m)) return null;
    if (!checkdate((int) $m[2], (int) $m[3], (int) $m[1])) return null;
    if ((int) $m[1] < 2000) return null; // zero dates & obvious garbage
    return $d;
}

/**
 * Insert or update one row, keyed by dedup_hash (falling back to post_id).
 * $row is an associative array of column => value.
 */
function alt_db_upsert(array $row) {
    global $wpdb;
    $table = alt_db_table();

    $data = array(
        'post_id'            => isset($row['post_id']) ? (int) $row['post_id'] : null,
        'dedup_hash'         => substr((string) ($row['dedup_hash'] ?? ''), 0, 32),
        'company'            => substr((string) ($row['company'] ?? ''), 0, 255),
        'company_key'        => substr(function_exists('alt_company_key') ? alt_company_key((string) ($row['company'] ?? '')) : '', 0, 255),
        'ticker'             => substr((string) ($row['ticker'] ?? ''), 0, 32),
        'job_count'          => max(0, (int) ($row['job_count'] ?? 0)),
        'layoff_date'        => alt_db_valid_date((string) ($row['layoff_date'] ?? '')),
        'announcement_date'  => alt_db_valid_date((string) ($row['announcement_date'] ?? '')),
        'industry'           => substr((string) ($row['industry'] ?? ''), 0, 120),
        'country'            => substr((string) ($row['country'] ?? ''), 0, 64),
        'employer_country'   => substr((string) ($row['employer_country'] ?? ''), 0, 64),
        'employer_country_evidence' => sanitize_textarea_field($row['employer_country_evidence'] ?? ''),
        'announcement_evidence' => sanitize_textarea_field($row['announcement_evidence'] ?? ''),
        'state'              => substr((string) ($row['state'] ?? ''), 0, 2),
        'source_type'        => substr((string) ($row['source_type'] ?? ''), 0, 32),
        'verification_level' => substr((string) ($row['verification_level'] ?? ''), 0, 16),
        'source_name'        => substr((string) ($row['source_name'] ?? ''), 0, 191),
        'source_url'         => (string) ($row['source_url'] ?? ''),
        'ai_explicit'        => !empty($row['ai_explicit']) ? 1 : 0,
        'ai_causation'       => function_exists('alt_normalize_ai_causation') ? alt_normalize_ai_causation($row['ai_causation'] ?? 'unknown') : 'unknown',
        'confidence'         => min(100, max(0, (int) ($row['confidence'] ?? 0))),
        'review_status'      => function_exists('alt_normalize_review_status') ? alt_normalize_review_status($row['review_status'] ?? 'legacy_unreviewed') : 'legacy_unreviewed',
        'announced'          => !empty($row['announced']) ? 1 : 0,
        'ai_language'        => (string) ($row['ai_language'] ?? ''),
        'reason_tags'        => alt_db_pack_tags($row['reason_tags'] ?? array()),
        'roles'              => (string) ($row['roles'] ?? ''),
        'excerpt'            => (string) ($row['excerpt'] ?? ''),
    );

    // Editorially suppressed entries never come back through an import.
    if (alt_is_suppressed($data['dedup_hash'])) {
        return 0;
    }

    // Curated company-level industry overrides beat source sector labels.
    if (function_exists('alt_industry_override')) {
        $ovr = alt_industry_override($data['company']);
        if ($ovr !== '') $data['industry'] = $ovr;
    }

    // Find an existing row by dedup_hash first, then post_id.
    $existing = null;
    if ($data['dedup_hash'] !== '') {
        $existing = $wpdb->get_row($wpdb->prepare(
            "SELECT id, edited FROM $table WHERE dedup_hash = %s", $data['dedup_hash']));
    }
    if (!$existing && $data['post_id']) {
        $existing = $wpdb->get_row($wpdb->prepare(
            "SELECT id, edited FROM $table WHERE post_id = %d", $data['post_id']));
    }

    if ($existing) {
        // Editor-corrected rows are pinned: a re-import of the same source
        // row must not overwrite the correction (imports run daily).
        if (!empty($existing->edited)) {
            return (int) $existing->id;
        }
        $wpdb->update($table, $data, array('id' => (int) $existing->id));
        return (int) $existing->id;
    }
    $wpdb->insert($table, $data);
    return (int) $wpdb->insert_id;
}

/** Mirror one `layoffs` CPT post into the table. */
function alt_db_sync_post($post_id) {
    $post_id = (int) $post_id;
    if (get_post_type($post_id) !== 'layoffs' || get_post_status($post_id) !== 'publish') {
        alt_db_delete_by_post($post_id);
        return;
    }
    alt_db_upsert(array(
        'post_id'            => $post_id,
        'dedup_hash'         => get_post_meta($post_id, 'dedup_hash', true),
        'company'            => get_post_meta($post_id, 'company_name', true),
        'ticker'             => get_post_meta($post_id, 'ticker', true),
        'job_count'          => get_post_meta($post_id, 'job_count', true),
        'layoff_date'        => get_post_meta($post_id, 'layoff_date', true),
        'announcement_date'  => get_post_meta($post_id, 'announcement_date', true),
        'industry'           => get_post_meta($post_id, 'industry', true),
        'country'            => get_post_meta($post_id, 'country', true),
        'employer_country'   => get_post_meta($post_id, 'employer_country', true),
        'employer_country_evidence' => get_post_meta($post_id, 'employer_country_evidence', true),
        'announcement_evidence' => get_post_meta($post_id, 'announcement_evidence', true),
        'state'              => get_post_meta($post_id, 'state', true),
        'source_type'        => get_post_meta($post_id, 'source_type', true),
        'verification_level' => get_post_meta($post_id, 'verification_level', true),
        'source_name'        => get_post_meta($post_id, 'source_name', true),
        'source_url'         => get_post_meta($post_id, 'source_url', true),
        'ai_explicit'        => get_post_meta($post_id, 'ai_explicit', true),
        'ai_causation'       => get_post_meta($post_id, 'ai_causation', true),
        'confidence'         => get_post_meta($post_id, 'confidence', true),
        'review_status'      => get_post_meta($post_id, 'review_status', true),
        'announced'          => get_post_meta($post_id, 'announced', true),
        'ai_language'        => get_post_meta($post_id, 'ai_language', true),
        'reason_tags'        => get_post_meta($post_id, 'reason_tags', true),
        'roles'              => get_post_meta($post_id, 'roles', true),
        'excerpt'            => get_post_meta($post_id, 'excerpt', true),
    ));
}

function alt_db_delete_by_post($post_id) {
    global $wpdb;
    $wpdb->delete(alt_db_table(), array('post_id' => (int) $post_id));
}

add_action('save_post_layoffs', function ($post_id) {
    if (wp_is_post_revision($post_id) || wp_is_post_autosave($post_id)) return;
    alt_db_sync_post($post_id);
}, 20);
add_action('trashed_post', function ($post_id) {
    if (get_post_type($post_id) === 'layoffs') alt_db_delete_by_post($post_id);
});
add_action('before_delete_post', function ($post_id) {
    if (get_post_type($post_id) === 'layoffs') alt_db_delete_by_post($post_id);
});

/** Backfill every existing CPT post into the table. Returns rows synced. */
function alt_db_migrate() {
    $ids = get_posts(array(
        'post_type' => 'layoffs', 'post_status' => 'publish',
        'posts_per_page' => -1, 'fields' => 'ids', 'no_found_rows' => true,
    ));
    foreach ($ids as $id) {
        alt_db_sync_post($id);
    }
    return count($ids);
}

/* ------------------------------------------------------------------ */
/* Query builder shared by /query and /aggregate                       */
/* ------------------------------------------------------------------ */

/**
 * Build a parameterized WHERE clause from request filters. `$except` drops one
 * dimension (for slicer charts). Returns array($sql, $params).
 */
function alt_db_where(WP_REST_Request $r, $except = '') {
    global $wpdb;
    $where = array("1=1");
    $params = array();
    // The public UI defaults to effective/filing date. Benchmark callers can
    // explicitly request announcement_date; that date is source-evidenced and
    // never inferred from the effective date.
    $date_col = $r->get_param('date_basis') === 'announcement' ? 'announcement_date' : 'layoff_date';

    $from = $r->get_param('from');
    $to = $r->get_param('to');
    if ($except !== 'date') {
        if ($from && preg_match('/^\d{4}-\d{2}-\d{2}$/', $from)) { $where[] = "$date_col >= %s"; $params[] = $from; }
        if ($to && preg_match('/^\d{4}-\d{2}-\d{2}$/', $to)) { $where[] = "$date_col <= %s"; $params[] = $to; }

        // Multi-select period dimensions: years=2024,2026 quarters=1,3 months=1,2.
        // They AND together (years 2024+2025 with Q1 = Q1 of both years), which
        // is the natural cross-reference behavior.
        $int_in = function ($param, $expr, $min, $max) use (&$where, &$params, $r, $date_col) {
            $vals = array();
            foreach (explode(',', (string) $r->get_param($param)) as $v) {
                $v = (int) trim($v);
                if ($v >= $min && $v <= $max) { $vals[] = $v; }
            }
            if ($vals) {
                $ph = implode(',', array_fill(0, count($vals), '%d'));
                $where[] = "$date_col IS NOT NULL AND $expr IN ($ph)";
                foreach ($vals as $v) { $params[] = $v; }
            }
        };
        $int_in('years', "YEAR($date_col)", 1990, 2100);
        $int_in('quarters', "QUARTER($date_col)", 1, 4);
        $int_in('months', "MONTH($date_col)", 1, 12);
    }

    // Category filters accept comma lists (multi-select cross-referencing).
    // None of the canonical values contain a comma, so the split is safe.
    $str_in = function ($param, $col, $except_key) use (&$where, &$params, $r, $except) {
        if ($except === $except_key) return;
        $vals = array_filter(array_map('trim', explode(',', (string) $r->get_param($param))), 'strlen');
        if ($vals) {
            $ph = implode(',', array_fill(0, count($vals), '%s'));
            $where[] = "$col IN ($ph)";
            foreach ($vals as $v) { $params[] = $v; }
        }
    };
    $str_in('industry', 'industry', 'industry');
    $str_in('country', 'country', 'country');
    $str_in('employer_country', 'employer_country', 'employer_country');
    $str_in('state', 'state', 'state');
    if ($except !== 'reasons') {
        $reasons = array_filter(array_map('sanitize_key', explode(',', (string) $r->get_param('reasons'))));
        if ($reasons) {
            $ors = array();
            foreach ($reasons as $tag) { $ors[] = "reason_tags LIKE %s"; $params[] = '%,' . $tag . ',%'; }
            $where[] = '(' . implode(' OR ', $ors) . ')';
        }
    }
    // `sources` accepts BOTH vocabularies a consumer can see: verification
    // tiers (gold/silver/bronze/warn — what the UI dropdown sends) AND the
    // source_type values every /query row exposes (news/8K/warn/press_release).
    // Matching only the tier column made sources=news silently return 0 rows
    // (super test 2026-07-15).
    $sources = array_filter(array_map('sanitize_text_field', explode(',', (string) $r->get_param('sources'))));
    if ($sources) {
        $ph = implode(',', array_fill(0, count($sources), '%s'));
        $where[] = "(verification_level IN ($ph) OR source_type IN ($ph))";
        foreach ($sources as $s) { $params[] = $s; }
        foreach ($sources as $s) { $params[] = $s; }
    }
    if ($r->get_param('ai') === '1' || $r->get_param('ai') === 'true') { $where[] = "ai_explicit = 1"; }
    if ($r->get_param('ai_primary') === '1' || $r->get_param('ai_primary') === 'true') { $where[] = "ai_causation = 'primary_cause'"; }
    if (($status = sanitize_key((string) $r->get_param('review_status'))) !== '') { $where[] = "review_status = %s"; $params[] = $status; }
    if ($r->get_param('context_missing') === '1' || $r->get_param('context_missing') === 'true') {
        $where[] = "(employer_country = '' OR announcement_date IS NULL)";
    }
    // stage=announced -> announcement-stage only; stage=verified -> filed/reported only
    $stage = (string) $r->get_param('stage');
    if ($stage === 'announced') { $where[] = "announced = 1"; }
    elseif ($stage === 'verified') { $where[] = "announced = 0"; }
    if (($v = $r->get_param('company'))) { $where[] = "company LIKE %s"; $params[] = '%' . $wpdb->esc_like($v) . '%'; }
    if (($v = $r->get_param('keyword'))) { $where[] = "excerpt LIKE %s"; $params[] = '%' . $wpdb->esc_like($v) . '%'; }
    // Unified search box: company OR industry OR excerpt OR state OR country.
    if (($v = $r->get_param('q'))) {
        $like = '%' . $wpdb->esc_like($v) . '%';
        $where[] = "(company LIKE %s OR industry LIKE %s OR excerpt LIKE %s OR state LIKE %s OR country LIKE %s)";
        array_push($params, $like, $like, $like, $like, $like);
    }
    if (($v = $r->get_param('min_jobs')) && (int) $v > 0) { $where[] = "job_count >= %d"; $params[] = (int) $v; }

    return array(implode(' AND ', $where), $params);
}

function alt_db_prep($sql, $params) {
    global $wpdb;
    return $params ? $wpdb->prepare($sql, $params) : $sql;
}

function alt_db_row_to_array($row) {
    return array(
        'id'                 => (int) $row->id,
        'event_id'           => (int) $row->event_id,
        'company_name'       => $row->company,
        'ticker'             => $row->ticker !== '' ? $row->ticker : null,
        'job_count'          => (int) $row->job_count,
        'layoff_date'        => $row->layoff_date ?: '',
        'announcement_date'  => $row->announcement_date ?: '',
        'industry'           => $row->industry,
        'country'            => $row->country,
        'employer_country'   => $row->employer_country,
        'employer_country_evidence' => $row->employer_country_evidence ?: null,
        'announcement_evidence' => $row->announcement_evidence ?: null,
        'state'              => $row->state,
        'source_type'        => $row->source_type,
        'source_name'        => $row->source_name,
        'verification_level' => $row->verification_level,
        'source_url'         => $row->source_url,
        'ai_explicit'        => (bool) $row->ai_explicit,
        'ai_causation'       => $row->ai_causation,
        'confidence'         => (int) $row->confidence,
        'review_status'      => $row->review_status,
        'announced'          => (bool) $row->announced,
        // Transparency: editorially corrected rows are visibly flagged (the
        // correction reason is in the site's public corrections log).
        'edited'             => !empty($row->edited),
        'ai_language'        => $row->ai_language !== '' ? $row->ai_language : null,
        'reason_tags'        => alt_db_unpack_tags($row->reason_tags),
        'roles'              => $row->roles,
        'excerpt'            => $row->excerpt,
        'permalink'          => $row->post_id ? get_permalink((int) $row->post_id) : '',
    );
}

/* ------------------------------------------------------------------ */
/* REST: /query and /aggregate                                         */
/* ------------------------------------------------------------------ */

function alt_register_query_routes() {
    register_rest_route('layoffs/v1', '/query', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_query',
        'permission_callback' => '__return_true',
    ));
    register_rest_route('layoffs/v1', '/aggregate', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_aggregate',
        'permission_callback' => '__return_true',
    ));
    // Distinct filter values + date range, for populating dropdowns/period pills
    // without loading every row.
    register_rest_route('layoffs/v1', '/facets', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_facets',
        'permission_callback' => '__return_true',
    ));
    // Key-protected: backfill existing CPT posts into the table. Idempotent.
    register_rest_route('layoffs/v1', '/migrate', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_migrate',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected, resumable migration of legacy rows into canonical events
    // and source reports. `after_id` makes it safe to call repeatedly.
    register_rest_route('layoffs/v1', '/event-migrate', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_event_migrate',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected: bulk table-only upsert (for high-volume WARN data that
    // shouldn't create a CPT post per row). Idempotent by dedup_hash.
    register_rest_route('layoffs/v1', '/bulk', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_bulk',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected: re-normalize country/industry across table + posts.
    register_rest_route('layoffs/v1', '/cleanup', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_cleanup',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected: editorial removal of specific entries (bad extractions,
    // confirmed duplicates). Trashes CPT posts (recoverable in wp-admin) and
    // deletes table-only rows by table id.
    register_rest_route('layoffs/v1', '/trash', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_trash',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected: collapse confirmed duplicate rows while retaining every
    // source report on the surviving canonical event.
    register_rest_route('layoffs/v1', '/merge-events', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_merge_events',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected: drop table-only WARN rows ahead of a clean re-import.
    // (Corrected counts change the dedup hash, so upsert alone would leave the
    // old wrong rows behind as duplicates.) CPT-backed rows are untouched.
    register_rest_route('layoffs/v1', '/bulk-purge', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_bulk_purge',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected: editorial field corrections (pins the row + suppresses
    // the original source hash so imports can't revert it). Requires `reason`.
    register_rest_route('layoffs/v1', '/edit', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_edit',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected automated evidence refresh. Unlike /edit this does not
    // suppress a source hash or pin the row: it only replaces the derived AI
    // classification after the worker has re-read the linked source.
    register_rest_route('layoffs/v1', '/reclassify', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_reclassify',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected, evidence-bounded enrichment of public announcement date
    // and employer domicile. This never guesses from job location or replaces
    // an existing value without a new exact source quote.
    register_rest_route('layoffs/v1', '/enrich-context', array(
        'methods' => 'POST', 'callback' => 'alt_api_enrich_context',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Read-only public operational transparency, plus a key-protected writer
    // used by the autonomous collectors after each source attempt.
    register_rest_route('layoffs/v1', '/source-health', array(
        array('methods' => 'GET', 'callback' => 'alt_api_source_health_get', 'permission_callback' => '__return_true'),
        array('methods' => 'POST', 'callback' => 'alt_api_source_health_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
    // Append-only collector-attempt ledger. It begins with this deployment;
    // legacy volume is intentionally not reconstructed or guessed.
    register_rest_route('layoffs/v1', '/source-runs', array(
        'methods' => 'GET', 'callback' => 'alt_api_source_runs', 'permission_callback' => '__return_true',
        'args' => array(
            'source' => array('type' => 'string', 'default' => ''),
            'days' => array('type' => 'integer', 'default' => 30),
            'per_page' => array('type' => 'integer', 'default' => 50),
        ),
    ));
    // Public aggregate-only integrity telemetry for journalists and ops.
    register_rest_route('layoffs/v1', '/integrity-status', array(
        'methods' => 'GET', 'callback' => 'alt_api_integrity_status', 'permission_callback' => '__return_true',
    ));
    register_rest_route('layoffs/v1', '/source-evidence-hash-backfill', array(
        'methods' => 'POST', 'callback' => 'alt_api_source_evidence_hash_backfill',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Repairs only the event graph's internal retained-source link from an
    // already stored canonical-row URL. It never fetches a publisher page or
    // alters event facts, classifications, or visible source URLs.
    register_rest_route('layoffs/v1', '/source-report-link-backfill', array(
        'methods' => 'POST', 'callback' => 'alt_api_source_report_link_backfill',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // A keyed, success-anchored cursor for the bounded historical GDELT
    // recovery worker. It advances only after a complete window succeeds, so
    // an upstream rate limit is retried rather than skipped for years.
    register_rest_route('layoffs/v1', '/historical-gdelt-cursor', array(
        array('methods' => 'GET', 'callback' => 'alt_api_historical_gdelt_cursor_get',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
        array('methods' => 'POST', 'callback' => 'alt_api_historical_gdelt_cursor_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
    // A compact, machine-readable view of operational health, retained-source
    // integrity and the openly scoped quality roadmap. It deliberately names
    // pending/blocked work instead of turning an absent connector into a
    // misleading coverage claim.
    register_rest_route('layoffs/v1', '/quality-status', array(
        'methods' => 'GET', 'callback' => 'alt_api_quality_status', 'permission_callback' => '__return_true',
    ));
    register_rest_route('layoffs/v1', '/dataset-releases', array(
        'methods' => 'GET', 'callback' => 'alt_api_dataset_releases', 'permission_callback' => '__return_true',
    ));
    // Immutable, server-generated quarterly research snapshots. The writer
    // accepts a quarter identifier only; it never accepts client-supplied
    // totals or model-written findings.
    register_rest_route('layoffs/v1', '/reports/quarterly', array(
        array('methods' => 'GET', 'callback' => 'alt_api_quarterly_reports', 'permission_callback' => '__return_true'),
        array('methods' => 'POST', 'callback' => 'alt_api_quarterly_report_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
    register_rest_route('layoffs/v1', '/reports/quarterly/(?P<report_id>\\d{4}-Q[1-4])', array(
        'methods' => 'GET', 'callback' => 'alt_api_quarterly_report_get', 'permission_callback' => '__return_true',
    ));
    // Read-only triage list. This flags records for editorial attention; it
    // never changes a count, classification, source, or publication status.
    register_rest_route('layoffs/v1', '/review-queue', array(
        'methods' => 'GET', 'callback' => 'alt_api_review_queue', 'permission_callback' => '__return_true',
        'args' => array(
            'per_page' => array('type' => 'integer', 'default' => 50),
            'page' => array('type' => 'integer', 'default' => 1),
        ),
    ));
    // Read-only, deliberately narrow lifecycle candidates. A candidate is
    // never a merge decision: it is a same-company/same-count/source-supported
    // announcement followed by a later reported/filing record in the same
    // job-location country. Editors must verify retained evidence before using
    // the existing keyed /merge-events endpoint.
    register_rest_route('layoffs/v1', '/announcement-lifecycle-candidates', array(
        'methods' => 'GET', 'callback' => 'alt_api_announcement_lifecycle_candidates', 'permission_callback' => '__return_true',
        'args' => array('per_page' => array('type' => 'integer', 'default' => 50)),
    ));
    register_rest_route('layoffs/v1', '/benchmarks/challenger', array(
        array('methods' => 'GET', 'callback' => 'alt_api_challenger_benchmarks', 'permission_callback' => '__return_true'),
        array('methods' => 'POST', 'callback' => 'alt_api_challenger_benchmark_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
    // Country-period recall samples are public methodology records, not a
    // completeness claim. A benchmark cannot be posted without an openly
    // reviewable independent reference set.
    register_rest_route('layoffs/v1', '/benchmarks/recall', array(
        array('methods' => 'GET', 'callback' => 'alt_api_recall_benchmarks', 'permission_callback' => '__return_true'),
        array('methods' => 'POST', 'callback' => 'alt_api_recall_benchmark_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
    // Separate, source-evidenced WARN timing/adjudication register. It never
    // affects layoff/AI totals and uses “violation” only after adjudication.
    register_rest_route('layoffs/v1', '/warn-transparency', array(
        array('methods' => 'GET', 'callback' => 'alt_api_warn_transparency_get', 'permission_callback' => '__return_true'),
        array('methods' => 'POST', 'callback' => 'alt_api_warn_transparency_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
}

/**
 * Apply evidence-derived fields to existing records without treating an
 * automated reassessment as an editorial correction. Primary/contributing AI
 * claims require a non-trivial exact quote supplied by the worker; workers
 * independently verify that quote against newly fetched source text.
 */
function alt_api_reclassify(WP_REST_Request $r) {
    global $wpdb;
    $items = $r->get_param('items');
    if (!is_array($items)) return new WP_Error('alt_bad_request', 'items must be an array.', array('status' => 400));
    $table = alt_db_table();
    $out = array('updated' => array(), 'not_found' => array(), 'rejected' => array());
    foreach ($items as $item) {
        $id = (int) ($item['id'] ?? 0);
        $row = $id ? $wpdb->get_row($wpdb->prepare("SELECT id, post_id FROM $table WHERE id = %d", $id)) : null;
        if (!$row) { $out['not_found'][] = $id; continue; }
        $cause = alt_normalize_ai_causation($item['ai_causation'] ?? 'unknown');
        $quote = trim((string) ($item['ai_language'] ?? ''));
        if (in_array($cause, array('primary_cause', 'contributing_cause'), true) && strlen($quote) < 12) {
            $out['rejected'][] = $id;
            continue;
        }
        $data = array(
            'ai_causation' => $cause,
            'ai_explicit' => in_array($cause, array('primary_cause', 'contributing_cause'), true) ? 1 : 0,
            'ai_language' => $quote,
            'confidence' => min(100, max(0, (int) ($item['confidence'] ?? 0))),
            'review_status' => 'verified',
        );
        if ($wpdb->update($table, $data, array('id' => $id)) === false) {
            return new WP_Error('alt_db_error', 'Reclassification update failed: ' . $wpdb->last_error, array('status' => 500));
        }
        if (!empty($row->post_id)) {
            foreach ($data as $key => $value) update_post_meta((int) $row->post_id, $key, $value);
        }
        $out['updated'][] = $id;
    }
    if (!empty($out['updated'])) alt_log_correction('reclassified', $out['updated'], 'Automated source-evidence reassessment');
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

/** Apply only source-quoted context fields that are presently blank. */
function alt_api_enrich_context(WP_REST_Request $r) {
    global $wpdb;
    $items = $r->get_param('items');
    if (!is_array($items)) return new WP_Error('alt_bad_request', 'items must be an array.', array('status' => 400));
    $table = alt_db_table();
    $out = array('updated' => array(), 'not_found' => array(), 'rejected' => array());
    foreach ($items as $item) {
        $id = (int) ($item['id'] ?? 0);
        $row = $id ? $wpdb->get_row($wpdb->prepare("SELECT id, post_id, employer_country, announcement_date FROM $table WHERE id = %d", $id)) : null;
        if (!$row) { $out['not_found'][] = $id; continue; }
        $data = array();
        $domicile = function_exists('alt_normalize_country') ? alt_normalize_country((string) ($item['employer_country'] ?? '')) : '';
        $domicile_evidence = trim((string) ($item['employer_country_evidence'] ?? ''));
        if ($row->employer_country === '' && $domicile !== '' && strlen($domicile_evidence) >= 12) {
            $data['employer_country'] = $domicile;
            $data['employer_country_evidence'] = sanitize_textarea_field($domicile_evidence);
        }
        $announcement_date = alt_db_valid_date((string) ($item['announcement_date'] ?? ''));
        $announcement_evidence = trim((string) ($item['announcement_evidence'] ?? ''));
        if (empty($row->announcement_date) && $announcement_date && strlen($announcement_evidence) >= 12) {
            $data['announcement_date'] = $announcement_date;
            $data['announcement_evidence'] = sanitize_textarea_field($announcement_evidence);
        }
        if (!$data) { $out['rejected'][] = $id; continue; }
        if ($wpdb->update($table, $data, array('id' => $id)) === false) {
            return new WP_Error('alt_db_error', 'Context enrichment failed: ' . $wpdb->last_error, array('status' => 500));
        }
        if (!empty($row->post_id)) foreach ($data as $key => $value) update_post_meta((int) $row->post_id, $key, $value);
        $out['updated'][] = $id;
    }
    if (!empty($out['updated'])) alt_log_correction('enriched', $out['updated'], 'Automated source-evidence context enrichment');
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

function alt_api_source_health_get() {
    $health = get_option('alt_source_health');
    return rest_ensure_response(is_array($health) ? $health : array());
}

function alt_api_source_health_post(WP_REST_Request $r) {
    global $wpdb;
    $source = sanitize_key((string) $r->get_param('source'));
    if ($source === '') return new WP_Error('alt_bad_request', 'source is required.', array('status' => 400));
    if (!alt_source_runs_table_ready()) {
        return new WP_Error('alt_db_error', 'Collector-run telemetry table is unavailable after migration retry.', array('status' => 500));
    }
    $health = get_option('alt_source_health');
    if (!is_array($health)) $health = array();
    $health[$source] = array(
        'status' => in_array($r->get_param('status'), array('ok', 'running', 'degraded'), true)
            ? $r->get_param('status') : 'degraded',
        'entries' => max(0, (int) $r->get_param('entries')),
        'checked_at' => gmdate('c'),
        'detail' => substr(sanitize_text_field((string) $r->get_param('detail')), 0, 240),
    );
    update_option('alt_source_health', $health, false);
    // Each successful health write is also a retained operational attempt.
    // This has no path to alter layoff rows, events or source reports.
    $logged = $wpdb->insert(alt_source_runs_table(), array(
        'source' => $source,
        'status' => $health[$source]['status'],
        'entries' => $health[$source]['entries'],
        'detail' => $health[$source]['detail'],
        'attempted_at' => gmdate('Y-m-d H:i:s'),
    ), array('%s', '%s', '%d', '%s', '%s'));
    if ($logged === false) {
        return new WP_Error('alt_db_error', 'Could not retain collector-run telemetry: ' . $wpdb->last_error, array('status' => 500));
    }
    return rest_ensure_response(array($source => $health[$source]));
}

/** Public, bounded history of collector attempts recorded after ledger inception. */
function alt_api_source_runs(WP_REST_Request $r) {
    global $wpdb;
    $days = min(90, max(1, (int) $r->get_param('days')));
    $per_page = min(200, max(1, (int) $r->get_param('per_page')));
    $source = sanitize_key((string) $r->get_param('source'));
    $since = gmdate('Y-m-d H:i:s', time() - ($days * DAY_IN_SECONDS));
    $table = alt_source_runs_table();
    if ($source !== '') {
        $rows = $wpdb->get_results($wpdb->prepare(
            "SELECT source, status, entries, detail, attempted_at FROM $table WHERE source = %s AND attempted_at >= %s ORDER BY id DESC LIMIT %d",
            $source, $since, $per_page), ARRAY_A);
    } else {
        $rows = $wpdb->get_results($wpdb->prepare(
            "SELECT source, status, entries, detail, attempted_at FROM $table WHERE attempted_at >= %s ORDER BY id DESC LIMIT %d",
            $since, $per_page), ARRAY_A);
    }
    $rows = is_array($rows) ? $rows : array();
    foreach ($rows as &$row) {
        $row['attempted_at'] = gmdate('c', strtotime($row['attempted_at'] . ' UTC'));
        $row['entries'] = (int) $row['entries'];
    }
    unset($row);
    return rest_ensure_response(array(
        'methodology' => 'Append-only collector-attempt telemetry begins with plugin 2.18.21. Counts are raw candidate documents from each source attempt, not accepted events or a reconstruction of historical activity.',
        'since' => gmdate('c', strtotime($since . ' UTC')),
        'through' => gmdate('c'),
        'source' => $source,
        'runs' => $rows,
    ));
}

function alt_api_integrity_status() {
    global $wpdb;
    $layoffs = alt_db_table();
    $events = alt_events_table();
    $reports = alt_source_reports_table();
    $total = (int) $wpdb->get_var("SELECT COUNT(*) FROM $layoffs");
    $migrated = (int) $wpdb->get_var("SELECT COUNT(*) FROM $layoffs WHERE event_id > 0");
    $event_count = (int) $wpdb->get_var("SELECT COUNT(*) FROM $events");
    $report_count = (int) $wpdb->get_var("SELECT COUNT(*) FROM $reports");
    // A canonical event can retain several reports. Count the events with at
    // least one linkable source separately from raw report volume so the
    // public integrity view can disclose any citation gap rather than imply
    // that a report count alone proves every event has a usable source link.
    $events_with_linked_source = (int) $wpdb->get_var(
        "SELECT COUNT(DISTINCT event_id) FROM $reports WHERE source_url <> ''"
    );
    // Keep a tiny, already-public row-level sample actionable for researchers
    // and editors. This is not an alternate query surface or a claim that a
    // missing internal source-report link means the canonical row has no URL.
    $source_link_gap_samples = $wpdb->get_results(
        "SELECT l.id, l.event_id, l.company, l.layoff_date, l.source_name, l.source_url
         FROM $layoffs l
         LEFT JOIN (SELECT DISTINCT event_id FROM $reports WHERE source_url <> '') linked
           ON linked.event_id = l.event_id
         WHERE l.event_id > 0 AND linked.event_id IS NULL
         ORDER BY l.id ASC LIMIT 5", ARRAY_A) ?: array();
    $hashable_reports = (int) $wpdb->get_var("SELECT COUNT(*) FROM $reports WHERE excerpt <> ''");
    $hashed_reports = (int) $wpdb->get_var("SELECT COUNT(*) FROM $reports WHERE excerpt <> '' AND evidence_hash <> ''");
    // These are deliberately completeness counters, not inferred values.
    // A blank industry is common in structured WARN notices. A blank US state
    // means the source did not identify the affected-job location; never use
    // an employer HQ, office footprint, or brand knowledge to fill it.
    $missing_industry = (int) $wpdb->get_var("SELECT COUNT(*) FROM $layoffs WHERE industry = ''");
    $us_job_location_rows = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COUNT(*) FROM $layoffs WHERE country = %s", 'United States'));
    $us_rows_missing_state = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COUNT(*) FROM $layoffs WHERE country = %s AND state = ''", 'United States'));
    return rest_ensure_response(array(
        'canonical_events' => $event_count,
        'source_reports' => $report_count,
        'canonical_events_with_linked_source_reports' => $events_with_linked_source,
        'canonical_events_without_linked_source_reports' => max(0, $event_count - $events_with_linked_source),
        'source_link_rule' => 'A cited source means at least one retained event-source report has a public URL. Events without a link remain a visible integrity gap; source-report volume alone is not treated as proof of complete citation coverage.',
        'source_link_gap_samples' => array_map(function ($row) {
            return array(
                'id' => (int) $row['id'],
                'event_id' => (int) $row['event_id'],
                'company_name' => (string) $row['company'],
                'layoff_date' => (string) $row['layoff_date'],
                'source_name' => (string) $row['source_name'],
                'source_url' => (string) $row['source_url'],
            );
        }, $source_link_gap_samples),
        'hashable_source_reports' => $hashable_reports,
        'hashed_source_reports' => $hashed_reports,
        'source_report_hashes_remaining' => max(0, $hashable_reports - $hashed_reports),
        'canonical_rows_total' => $total,
        'canonical_rows_migrated' => $migrated,
        'canonical_rows_remaining' => max(0, $total - $migrated),
        'migration_complete' => $total === $migrated,
        'metadata_completeness' => array(
            'rows_missing_industry' => $missing_industry,
            'industry_rule' => 'Industry remains blank unless the source supports it or a reviewed, cited official entity mapping is available; structured WARN notices commonly omit it.',
            'us_job_location_rows' => $us_job_location_rows,
            'us_rows_with_known_job_location_state' => max(0, $us_job_location_rows - $us_rows_missing_state),
            'us_rows_missing_job_location_state' => $us_rows_missing_state,
            'state_rule' => 'US state is the affected-job location only. It remains blank for national or unspecified announcements; employer domicile and headquarters are never substituted.',
        ),
        'generated_at' => gmdate('c'),
    ));
}

/**
 * Backfill hashes only from the evidence excerpts already retained locally.
 * No source URL is fetched and no source/excerpt/classification is modified.
 */
function alt_api_source_evidence_hash_backfill(WP_REST_Request $r) {
    global $wpdb;
    $limit = min(1000, max(1, (int) ($r->get_param('limit') ?: 500)));
    $reports = alt_source_reports_table();
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT id, excerpt FROM $reports WHERE excerpt <> '' AND evidence_hash = '' ORDER BY id ASC LIMIT %d", $limit), ARRAY_A) ?: array();
    $updated = 0;
    foreach ($rows as $row) {
        $ok = $wpdb->update($reports, array('evidence_hash' => hash('sha256', (string) $row['excerpt'])), array('id' => (int) $row['id']));
        if ($ok === false) return new WP_Error('alt_db_error', 'Evidence-hash backfill failed: ' . $wpdb->last_error, array('status' => 500, 'updated' => $updated));
        if ($ok) $updated++;
    }
    $remaining = (int) $wpdb->get_var("SELECT COUNT(*) FROM $reports WHERE excerpt <> '' AND evidence_hash = ''");
    return rest_ensure_response(array('updated' => $updated, 'remaining' => $remaining, 'scope' => 'Hashes are derived from already-retained excerpts only; external pages are not fetched.'));
}

/**
 * Restore a missing link in an existing canonical event's retained-source
 * graph from the canonical row's already-published source fields. This is a
 * repair of the evidence relationship only: it never requests the external
 * URL, changes a row, or treats a source name as a source URL.
 */
function alt_api_source_report_link_backfill(WP_REST_Request $r) {
    global $wpdb;
    $limit = min(1000, max(1, (int) ($r->get_param('limit') ?: 500)));
    $layoffs = alt_db_table();
    $reports = alt_source_reports_table();
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT l.id, l.event_id, l.source_name, l.source_type, l.verification_level,
                l.source_url, l.excerpt, l.ai_causation, l.ai_language
         FROM $layoffs l
         LEFT JOIN (SELECT DISTINCT event_id FROM $reports WHERE source_url <> '') linked
           ON linked.event_id = l.event_id
         WHERE l.event_id > 0 AND l.source_url <> '' AND linked.event_id IS NULL
         ORDER BY l.id ASC LIMIT %d", $limit), ARRAY_A) ?: array();
    $updated = 0;
    foreach ($rows as $row) {
        $event_id = (int) $row['event_id'];
        if (!$event_id) continue;
        if (!alt_event_add_report($event_id, $row)) {
            return new WP_Error('alt_db_error', 'Retained source-link backfill failed: ' . $wpdb->last_error, array('status' => 500, 'updated' => $updated));
        }
        $updated++;
    }
    $remaining = (int) $wpdb->get_var(
        "SELECT COUNT(DISTINCT l.event_id)
         FROM $layoffs l
         LEFT JOIN (SELECT DISTINCT event_id FROM $reports WHERE source_url <> '') linked
           ON linked.event_id = l.event_id
         WHERE l.event_id > 0 AND l.source_url <> '' AND linked.event_id IS NULL"
    );
    if ($updated && function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response(array(
        'updated' => $updated,
        'remaining' => $remaining,
        'scope' => 'Restored event-source links from already-retained canonical-row URLs only; no external page was fetched and no layoff fact or source URL was changed.',
    ));
}

function alt_api_historical_gdelt_cursor_get() {
    $cursor = get_option('alt_historical_gdelt_cursor');
    $cursor = is_array($cursor) ? $cursor : array();
    return rest_ensure_response(array(
        'next_start' => preg_match('/^\d{4}-\d{2}-\d{2}$/', (string) ($cursor['next_start'] ?? '')) ? $cursor['next_start'] : '',
        'updated_at' => (string) ($cursor['updated_at'] ?? ''),
        'scope' => 'Advances only after a successful bounded GDELT historical window; failed windows remain next for retry.',
    ));
}

function alt_api_historical_gdelt_cursor_post(WP_REST_Request $r) {
    $next = alt_db_valid_date((string) $r->get_param('next_start'));
    if (!$next) return new WP_Error('alt_bad_request', 'next_start must be a valid YYYY-MM-DD date.', array('status' => 400));
    update_option('alt_historical_gdelt_cursor', array('next_start' => $next, 'updated_at' => gmdate('c')), false);
    return alt_api_historical_gdelt_cursor_get();
}

/** Public quality and change-reporting status for researchers and operations. */
function alt_api_quality_status() {
    $health = get_option('alt_source_health');
    $log = get_option('alt_corrections_log');
    $health = is_array($health) ? $health : array();
    $log = is_array($log) ? $log : array();
    $since = gmdate('Y-m-d', strtotime('-30 days'));
    // This is the disclosed correction trail, not an invented ingest count:
    // legacy rows have no immutable created-at timestamp yet, so additions
    // cannot be reported honestly until the dataset-version ledger lands.
    $changes = array('corrected' => 0, 'removed' => 0, 'merged' => 0, 'reclassified' => 0, 'enriched' => 0);
    foreach ($log as $entry) {
        if (($entry['date'] ?? '') < $since) continue;
        $action = sanitize_key($entry['action'] ?? '');
        if (isset($changes[$action])) $changes[$action] += max(0, (int) ($entry['count'] ?? 0));
        elseif ($action === 'edited') $changes['corrected'] += max(0, (int) ($entry['count'] ?? 0));
    }
    $integrity = alt_api_integrity_status()->get_data();
    return rest_ensure_response(array(
        'generated_at' => gmdate('c'),
        'dataset_revision' => (int) get_option('alt_data_ver', 1),
        'last_30_days_disclosed_changes' => $changes,
        'source_health' => $health,
        'integrity' => $integrity,
        'workstreams' => array(
            array('id' => 'operational_monitoring', 'status' => 'active', 'scope' => 'Collector health, integrity and workflow failures'),
            array('id' => 'canonical_source_evidence', 'status' => 'complete', 'scope' => 'Canonical events retain all known source reports'),
            array('id' => 'durable_evidence_retention', 'status' => 'active', 'scope' => 'SHA-256 retained-excerpt hashes; bounded legacy backfill, not publisher-page archiving'),
            array('id' => 'challenger_reconciliation', 'status' => 'active', 'scope' => 'Public monthly strict US benchmark; source-evidenced announcement-date backfill continues'),
            array('id' => 'announcement_and_domicile_enrichment', 'status' => 'active', 'scope' => 'Daily exact-source-quote enrichment; legacy rows are never inferred'),
            array('id' => 'industry_and_job_location_metadata', 'status' => 'active', 'scope' => 'Public completeness telemetry identifies blank industry and affected-job-state fields; enrichment requires source evidence or a reviewed cited official entity mapping, never headquarters inference'),
            array('id' => 'country_recall_benchmarks', 'status' => 'active', 'scope' => 'Public country-period recall protocol and retained samples; no country completeness claim'),
            array('id' => 'high_impact_editorial_review', 'status' => 'active', 'scope' => 'Read-only queue for very large, AI-primary and multi-country events; editorial decisions remain manual'),
            array('id' => 'dataset_release_ledger', 'status' => 'active', 'scope' => 'Immutable release snapshots from this deployment forward; no invented legacy addition counts'),
            array('id' => 'company_directory', 'status' => 'in_progress', 'scope' => 'Reviewed, source-linked company pages only; no company page is published until a reviewed registry mapping meets its evidence threshold'),
            array('id' => 'quarterly_state_of_layoffs', 'status' => 'in_progress', 'scope' => 'Server-generated immutable quarterly snapshots; the first report is published only after the scheduled or keyed snapshot workflow succeeds'),
            array('id' => 'warn_transparency_dataset', 'status' => 'in_progress', 'scope' => 'Separate evidence-linked timing/adjudication research dataset; never included in layoff or AI totals'),
            array('id' => 'national_connectors_and_ir_feeds', 'status' => 'pending_permission', 'scope' => 'Only free, permitted and tested official/IR interfaces are promoted live'),
        ),
    ));
}

/** Public release ledger. It begins at deployment because legacy rows lack immutable ingest timestamps. */
function alt_api_dataset_releases() {
    $releases = get_option('alt_dataset_releases');
    return rest_ensure_response(array(
        'methodology' => 'Release snapshots begin when this ledger is deployed. They record dataset revision and retained-record totals, while corrections remain in the public corrections trail; historical addition counts are not reconstructed.',
        'releases' => is_array($releases) ? array_values($releases) : array(),
        'generated_at' => gmdate('c'),
    ));
}

/** Return the stored report list without recomputing historical facts. */
function alt_api_quarterly_reports() {
    $reports = get_option('alt_quarterly_reports');
    $reports = is_array($reports) ? $reports : array();
    krsort($reports);
    return rest_ensure_response(array(
        'methodology' => 'Quarterly reports are immutable, server-generated snapshots of fixed tracker queries. They are not a completeness claim, forecast, or model-written editorial analysis.',
        'reports' => array_values($reports),
        'generated_at' => gmdate('c'),
    ));
}

function alt_api_quarterly_report_get(WP_REST_Request $r) {
    $report_id = (string) $r->get_param('report_id');
    $reports = get_option('alt_quarterly_reports');
    $report = is_array($reports) && isset($reports[$report_id]) ? $reports[$report_id] : null;
    if (!$report) return new WP_Error('alt_not_found', 'Quarterly report not found.', array('status' => 404));
    return rest_ensure_response($report);
}

/** Strictly derive a calendar-quarter date interval from a stable report id. */
function alt_quarterly_report_window($report_id) {
    if (!preg_match('/^(\\d{4})-Q([1-4])$/', (string) $report_id, $m)) return null;
    $year = (int) $m[1]; $quarter = (int) $m[2];
    if ($year < 2015 || $year > ((int) gmdate('Y') + 1)) return null;
    $month = (($quarter - 1) * 3) + 1;
    $start = sprintf('%04d-%02d-01', $year, $month);
    $end = gmdate('Y-m-t', strtotime($start . ' +2 months'));
    return array('from' => $start, 'to' => $end, 'year' => $year, 'quarter' => $quarter);
}

/** Compute an aggregate through the same filter and calculation path as the UI. */
function alt_quarterly_report_aggregate($params) {
    $request = new WP_REST_Request('GET', '/layoffs/v1/aggregate');
    foreach ($params as $key => $value) $request->set_param($key, $value);
    return alt_api_aggregate_compute($request);
}

/**
 * Store one immutable, query-backed quarterly snapshot. A caller cannot pass
 * totals, prose, sources, or findings: all factual content is recomputed from
 * the live indexed dataset at this timestamp. Later corrections are disclosed
 * by comparing the stored revision with the live dataset revision.
 */
function alt_api_quarterly_report_post(WP_REST_Request $r) {
    $report_id = sanitize_text_field((string) $r->get_param('report_id'));
    $window = alt_quarterly_report_window($report_id);
    if (!$window) return new WP_Error('alt_bad_request', 'report_id must be a calendar quarter such as 2026-Q2.', array('status' => 400));
    $reports = get_option('alt_quarterly_reports');
    $reports = is_array($reports) ? $reports : array();
    if (isset($reports[$report_id])) {
        return new WP_Error('alt_conflict', 'Quarterly reports are immutable; this report_id already exists.', array('status' => 409));
    }
    $base = array('from' => $window['from'], 'to' => $window['to']);
    $verified_query = array_merge($base, array('stage' => 'verified'));
    $announced_query = array_merge($base, array('stage' => 'announced'));
    $ai_primary_query = array_merge($verified_query, array('ai_primary' => '1'));
    $quality = alt_api_quality_status()->get_data();
    $health = is_array($quality['source_health'] ?? null) ? $quality['source_health'] : array();
    $degraded = array();
    foreach ($health as $source => $status) if (($status['status'] ?? '') === 'degraded') $degraded[] = (string) $source;
    $status = sanitize_key((string) $r->get_param('publication_status'));
    if (!in_array($status, array('published', 'draft_generated'), true)) $status = 'published';
    $reports[$report_id] = array(
        'report_id' => $report_id,
        'publication_status' => $status,
        'title' => 'State of Layoffs — ' . $report_id,
        'period' => array('from' => $window['from'], 'to' => $window['to'], 'date_basis' => 'layoff_date'),
        'generated_at' => gmdate('c'),
        'dataset_revision' => (int) ($quality['dataset_revision'] ?? get_option('alt_data_ver', 1)),
        'plugin_version' => defined('ALT_VERSION') ? ALT_VERSION : '',
        'methodology_version' => 'quarterly-report-v1',
        'query_manifest' => array(
            'verified' => $verified_query,
            'announced' => $announced_query,
            'ai_primary_verified_subset' => $ai_primary_query,
        ),
        'snapshot' => array(
            'verified' => alt_quarterly_report_aggregate($verified_query),
            'announced' => alt_quarterly_report_aggregate($announced_query),
            'ai_primary_verified_subset' => alt_quarterly_report_aggregate($ai_primary_query),
        ),
        'coverage_at_publication' => array(
            'source_health' => $health,
            'degraded_sources' => $degraded,
            'integrity' => $quality['integrity'] ?? array(),
            'last_30_days_disclosed_changes' => $quality['last_30_days_disclosed_changes'] ?? array(),
        ),
        'limitations' => array(
            'This is a source-linked event snapshot, not a complete census of layoffs in any country.',
            'Verified and announcement-stage cuts are separate series and must not be added together.',
            'Industry, job-location state, employer domicile and AI causation remain blank or excluded when the source does not support them.',
            'A degraded source at publication is a visible coverage gap, not a zero result.',
        ),
        'revision_notice' => 'This frozen report preserves the dataset revision at publication. The live tracker may later change through corrections, source additions, deduplication or enrichment.',
    );
    krsort($reports);
    update_option('alt_quarterly_reports', $reports, false);
    return rest_ensure_response($reports[$report_id]);
}

/** Called only on a versioned plugin deployment after schema/cache initialization. */
function alt_record_dataset_release($version) {
    global $wpdb;
    $releases = get_option('alt_dataset_releases');
    if (!is_array($releases)) $releases = array();
    $revision = (int) get_option('alt_data_ver', 1);
    $key = $version . '|' . $revision;
    if (isset($releases[$key])) return;
    $releases[$key] = array(
        'released_at' => gmdate('c'), 'plugin_version' => (string) $version,
        'dataset_revision' => $revision,
        'canonical_rows' => (int) $wpdb->get_var('SELECT COUNT(*) FROM ' . alt_db_table()),
        'canonical_events' => (int) $wpdb->get_var('SELECT COUNT(*) FROM ' . alt_events_table()),
        'source_reports' => (int) $wpdb->get_var('SELECT COUNT(*) FROM ' . alt_source_reports_table()),
        'scope' => 'Snapshot only; additions before ledger inception are not inferred.',
    );
    krsort($releases); update_option('alt_dataset_releases', array_slice($releases, 0, 100, true), false);
}

/**
 * Public, evidence-preserving editorial triage queue.
 *
 * This is intentionally a queue rather than an automatic correction rule:
 * the triggers identify events whose count, causation claim, or geography
 * merits a human look. Existing review_status is reported, not overwritten.
 */
function alt_api_review_queue(WP_REST_Request $r) {
    global $wpdb;
    $per_page = min(100, max(1, (int) $r->get_param('per_page')));
    $page = max(1, (int) $r->get_param('page'));
    $offset = ($page - 1) * $per_page;
    $layoffs = alt_db_table();
    $reports = alt_source_reports_table();
    $where = "(l.job_count >= 5000 OR l.ai_causation = 'primary_cause' OR l.country = 'Multiple countries')";
    $total = (int) $wpdb->get_var("SELECT COUNT(*) FROM $layoffs l WHERE $where");
    $sql = "SELECT l.*, (SELECT COUNT(*) FROM $reports r WHERE r.event_id = l.event_id) AS retained_source_count
        FROM $layoffs l
        WHERE $where
        ORDER BY l.job_count DESC, l.id DESC
        LIMIT %d OFFSET %d";
    $rows = $wpdb->get_results($wpdb->prepare($sql, $per_page, $offset)) ?: array();
    $items = array();
    foreach ($rows as $row) {
        $item = alt_db_row_to_array($row);
        $triggers = array();
        if ((int) $row->job_count >= 5000) $triggers[] = 'very_large_event';
        if ($row->ai_causation === 'primary_cause') $triggers[] = 'ai_primary_claim';
        if ($row->country === 'Multiple countries') $triggers[] = 'multi_country_event';
        $item['review_triggers'] = $triggers;
        $item['retained_source_count'] = (int) $row->retained_source_count;
        $items[] = $item;
    }
    return rest_ensure_response(array(
        'methodology' => array(
            'purpose' => 'Editorial triage only; appearing here does not mean a record is inaccurate or automatically changed.',
            'triggers' => array('very_large_event' => 'job_count >= 5,000', 'ai_primary_claim' => 'source-quoted AI primary-cause classification', 'multi_country_event' => 'single event reported across multiple countries'),
            'source_safeguard' => 'Every item links to its retained event-source reports; review must preserve sources and record any correction in the public corrections trail.',
        ),
        'total' => $total,
        'page' => $page,
        'per_page' => $per_page,
        'items' => $items,
        'generated_at' => gmdate('c'),
    ));
}

/**
 * Conservative, read-only queue for reconciling an announced plan with a
 * later filing or report. It intentionally requires an exact count and a
 * source-evidenced announcement date, and it never changes rows, event IDs,
 * source reports, or published totals. Similar company news is not enough.
 */
function alt_api_announcement_lifecycle_candidates(WP_REST_Request $r) {
    global $wpdb;
    $per_page = min(100, max(1, (int) $r->get_param('per_page')));
    $table = alt_db_table();
    // A later record can be a filing or independently reported execution. We
    // require a concrete job-location country; never infer state/country from
    // headquarters. When both states are known, they must also agree.
    $sql = "SELECT
            a.id AS announcement_id, a.event_id AS announcement_event_id,
            a.company AS company, a.job_count AS job_count,
            a.announcement_date AS announcement_date, a.country AS country,
            a.state AS announcement_state, a.source_name AS announcement_source_name,
            a.source_type AS announcement_source_type, a.source_url AS announcement_source_url,
            b.id AS later_record_id, b.event_id AS later_event_id,
            b.layoff_date AS later_record_date, b.state AS later_record_state,
            b.source_name AS later_source_name, b.source_type AS later_source_type,
            b.source_url AS later_source_url
        FROM $table a
        INNER JOIN $table b ON b.company_key = a.company_key
            AND b.job_count = a.job_count
            AND b.announced = 0
            AND b.layoff_date >= a.announcement_date
            AND b.layoff_date <= DATE_ADD(a.announcement_date, INTERVAL 365 DAY)
            AND b.country = a.country
            AND (a.state = '' OR b.state = '' OR a.state = b.state)
        WHERE a.announced = 1
            AND a.announcement_date <> ''
            AND a.company_key <> ''
            AND a.country <> ''
            AND a.source_url <> ''
            AND b.source_url <> ''
            AND a.event_id <> b.event_id
            AND a.source_url <> b.source_url
        ORDER BY a.announcement_date DESC, a.id DESC
        LIMIT %d";
    $rows = $wpdb->get_results($wpdb->prepare($sql, $per_page), ARRAY_A) ?: array();
    return rest_ensure_response(array(
        'methodology' => array(
            'purpose' => 'Read-only editorial candidates for a possible lifecycle relationship between a source-linked announcement and a later filing or reported record.',
            'deterministic_screen' => 'Same normalized company, exact job count, same non-empty job-location country, source-evidenced announcement date, later non-announced record within 365 days, and compatible known state.',
            'not_a_merge_rule' => 'Candidates are not merged automatically. An editor must compare retained source reports, timing, geography and scope, then use the keyed merge endpoint only for the same underlying event.',
            'source_safeguard' => 'No candidate operation removes or rewrites a source report. A confirmed merge retains all reports on the canonical event.',
        ),
        'total_returned' => count($rows),
        'items' => $rows,
        'generated_at' => gmdate('c'),
    ));
}

/** Public retained reconciliation history; never a command to alter totals. */
function alt_api_challenger_benchmarks() {
    $records = get_option('alt_challenger_benchmarks');
    if (!is_array($records)) return rest_ensure_response(array());
    // Legacy setup records predate report_month. Present one authoritative
    // record per official report month, preferring the newer record that
    // explicitly names that month. This does not rewrite history or totals;
    // it prevents an API consumer from mistaking a setup duplicate for a
    // second independent Challenger publication.
    $by_month = array();
    foreach ($records as $record) {
        if (!is_array($record)) continue;
        $month = (string) ($record['report_month'] ?? '');
        if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $month)) {
            $month = substr((string) ($record['recorded_at'] ?? ''), 0, 7);
        }
        if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $month)) continue;
        if (!isset($by_month[$month]) || !empty($record['report_month'])) {
            $record['report_month'] = $month;
            $by_month[$month] = $record;
        }
    }
    krsort($by_month);
    return rest_ensure_response(array_values($by_month));
}

function alt_api_challenger_benchmark_post(WP_REST_Request $r) {
    $year = (int) $r->get_param('year');
    $report_month = (string) $r->get_param('report_month');
    if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $report_month)) $report_month = gmdate('Y-m');
    $benchmark = max(0, (int) $r->get_param('challenger_ai_jobs_ytd'));
    $tracker = max(0, (int) $r->get_param('tracker_ai_primary_announced_us_employer_jobs_ytd'));
    $url = esc_url_raw($r->get_param('benchmark_url'));
    if ($year < 2015 || $year > 2100 || !$benchmark || !$url) {
        return new WP_Error('alt_bad_request', 'year, benchmark URL and positive Challenger total are required.', array('status' => 400));
    }
    $records = get_option('alt_challenger_benchmarks');
    if (!is_array($records)) $records = array();
    // One retained public comparator per official report month.
    $key = $report_month;
    $records[$key] = array(
        'year' => $year, 'report_month' => $report_month, 'recorded_at' => gmdate('c'), 'benchmark' => 'Challenger, Gray & Christmas',
        'benchmark_url' => $url, 'challenger_ai_jobs_ytd' => $benchmark,
        'tracker_ai_primary_announced_us_employer_jobs_ytd' => $tracker,
        'tracker_ai_cited_announced_us_job_location_jobs_ytd' => max(0, (int) $r->get_param('tracker_ai_cited_announced_us_job_location_jobs_ytd')),
        'variance' => round(($tracker - $benchmark) / $benchmark, 4),
        'definition' => 'Strict: US employer + source-evidenced announcement date + announced + AI primary + canonical event. Diagnostic figure is not Challenger-comparable.',
    );
    krsort($records); update_option('alt_challenger_benchmarks', array_slice($records, 0, 24, true), false);
    return rest_ensure_response($records[$key]);
}

/** Public recall sample history. Empty means no current measured sample—not zero coverage. */
function alt_api_recall_benchmarks() {
    $records = get_option('alt_recall_benchmarks');
    return rest_ensure_response(array(
        'methodology' => array(
            'meaning' => 'Recall is the share of a disclosed independent reference-event sample matched to a canonical tracker event in the same country and period. It is a sample measurement, not national completeness or accuracy.',
            'admission_rule' => 'Each record must link to an openly reviewable reference set, state its country and period, and retain numerator and denominator. Samples are not combined across countries or periods.',
            'matching_rule' => 'A match requires the same underlying event after source-preserving canonical deduplication; similar company news alone is not sufficient.',
        ),
        'benchmarks' => is_array($records) ? array_values($records) : array(),
        'generated_at' => gmdate('c'),
    ));
}

/** Retain a reproducible country-period recall sample after an independent review. */
function alt_api_recall_benchmark_post(WP_REST_Request $r) {
    $country = alt_normalize_country((string) $r->get_param('country'));
    $start = alt_db_valid_date((string) $r->get_param('period_start'));
    $end = alt_db_valid_date((string) $r->get_param('period_end'));
    $reference = max(0, (int) $r->get_param('reference_events'));
    $matched = max(0, (int) $r->get_param('matched_events'));
    $reference_set_url = esc_url_raw((string) $r->get_param('reference_set_url'));
    $basis = sanitize_key((string) $r->get_param('reference_basis'));
    if ($country === '' || $country === 'Multiple countries' || !$start || !$end || $end < $start || !$reference || $matched > $reference || !$reference_set_url || !in_array($basis, array('independent_manual_sample', 'public_dataset_sample'), true)) {
        return new WP_Error('alt_bad_request', 'country, valid period, positive reference count, bounded match count, public reference-set URL and allowed basis are required.', array('status' => 400));
    }
    $records = get_option('alt_recall_benchmarks');
    if (!is_array($records)) $records = array();
    $key = sanitize_title($country) . '|' . $start . '|' . $end;
    $records[$key] = array(
        'country' => $country, 'period_start' => $start, 'period_end' => $end,
        'reference_basis' => $basis, 'reference_set_url' => $reference_set_url,
        'reference_events' => $reference, 'matched_events' => $matched,
        'sample_recall' => round($matched / $reference, 4),
        'methodology_version' => '1.0', 'recorded_at' => gmdate('c'),
        'disclosure' => 'Sample recall only; not a country completeness or accuracy claim.',
    );
    krsort($records); update_option('alt_recall_benchmarks', array_slice($records, 0, 100, true), false);
    return rest_ensure_response($records[$key]);
}

/** WARN transparency statuses separate timing observations from legal findings. */
function alt_warn_transparency_statuses() {
    return array('notice_recorded_60_plus_days', 'short_notice_exception_stated', 'short_notice_unresolved', 'court_adjudicated_warn_violation');
}

/** Public read-only register; it is deliberately outside layoff and AI metrics. */
function alt_api_warn_transparency_get() {
    global $wpdb;
    $table = alt_warn_transparency_table();
    $rows = $wpdb->get_results("SELECT id, state, employer, related_layoff_id, assessment_status, notice_date, affected_date, exception_evidence, adjudication_url, source_name, source_url, evidence_excerpt, evidence_hash, created_at FROM $table ORDER BY created_at DESC, id DESC LIMIT 500", ARRAY_A) ?: array();
    return rest_ensure_response(array(
        'methodology' => array(
            'scope' => 'Separate source-evidenced WARN timing/adjudication register. It is not included in layoff or AI totals, charts, exports or compliance rates.',
            'legal_safeguard' => 'A short notice interval is not labelled a violation. Only court_adjudicated_warn_violation requires and may state an adjudication source.',
            'allowed_statuses' => alt_warn_transparency_statuses(),
            'evidence_safeguard' => 'Each record retains a cited source and hash of its stored excerpt; the hash is not a source-page archive.',
        ),
        'records' => $rows, 'generated_at' => gmdate('c'),
    ));
}

/** Keyed, evidence-bounded editorial writer for the separate WARN register. */
function alt_api_warn_transparency_post(WP_REST_Request $r) {
    global $wpdb;
    $status = sanitize_key((string) $r->get_param('assessment_status'));
    $state = function_exists('alt_normalize_state') ? alt_normalize_state((string) $r->get_param('state')) : '';
    $employer = sanitize_text_field((string) $r->get_param('employer'));
    $source_name = sanitize_text_field((string) $r->get_param('source_name'));
    $source_url = esc_url_raw((string) $r->get_param('source_url'));
    $excerpt = sanitize_textarea_field((string) $r->get_param('evidence_excerpt'));
    if (!$state || !$employer || !$source_name || !$source_url || strlen($excerpt) < 12 || !in_array($status, alt_warn_transparency_statuses(), true)) return new WP_Error('alt_bad_request', 'state, employer, allowed assessment_status, source name/URL and a non-trivial evidence excerpt are required.', array('status' => 400));
    $notice_date = alt_db_valid_date((string) $r->get_param('notice_date'));
    $affected_date = alt_db_valid_date((string) $r->get_param('affected_date'));
    $exception_evidence = sanitize_textarea_field((string) $r->get_param('exception_evidence'));
    $adjudication_url = esc_url_raw((string) $r->get_param('adjudication_url'));
    $adjudication_evidence = sanitize_textarea_field((string) $r->get_param('adjudication_evidence'));
    $timing_status = in_array($status, array('notice_recorded_60_plus_days', 'short_notice_exception_stated', 'short_notice_unresolved'), true);
    if ($timing_status && (!$notice_date || !$affected_date)) return new WP_Error('alt_bad_request', 'Timing labels require source-evidenced notice_date and affected_date.', array('status' => 400));
    $days = $timing_status ? (int) floor((strtotime($affected_date) - strtotime($notice_date)) / DAY_IN_SECONDS) : null;
    if ($timing_status && $days < 0) return new WP_Error('alt_bad_request', 'affected_date cannot precede notice_date.', array('status' => 400));
    if ($status === 'notice_recorded_60_plus_days' && $days < 60) return new WP_Error('alt_bad_request', 'This label requires a recorded interval of at least 60 days.', array('status' => 400));
    if (in_array($status, array('short_notice_exception_stated', 'short_notice_unresolved'), true) && $days >= 60) return new WP_Error('alt_bad_request', 'Short-notice labels require a recorded interval below 60 days.', array('status' => 400));
    if ($status === 'short_notice_exception_stated' && strlen($exception_evidence) < 12) return new WP_Error('alt_bad_request', 'An explicit source excerpt stating the exception is required.', array('status' => 400));
    if ($status === 'court_adjudicated_warn_violation' && (!$adjudication_url || strlen($adjudication_evidence) < 12)) return new WP_Error('alt_bad_request', 'A court/adjudication URL and evidence excerpt are required before using the violation label.', array('status' => 400));
    $key = md5(implode('|', array($state, strtolower($employer), $status, $source_url, $notice_date, $affected_date, $adjudication_url)));
    $table = alt_warn_transparency_table();
    $data = array('record_key' => $key, 'state' => $state, 'employer' => $employer, 'related_layoff_id' => max(0, (int) $r->get_param('related_layoff_id')), 'assessment_status' => $status, 'notice_date' => $notice_date ?: null, 'affected_date' => $affected_date ?: null, 'exception_evidence' => $exception_evidence, 'adjudication_url' => $adjudication_url, 'source_name' => $source_name, 'source_url' => $source_url, 'evidence_excerpt' => $excerpt, 'evidence_hash' => hash('sha256', $excerpt), 'created_at' => gmdate('Y-m-d H:i:s'));
    $wpdb->query($wpdb->prepare("INSERT IGNORE INTO $table (record_key, state, employer, related_layoff_id, assessment_status, notice_date, affected_date, exception_evidence, adjudication_url, source_name, source_url, evidence_excerpt, evidence_hash, created_at) VALUES (%s, %s, %s, %d, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", $data['record_key'], $data['state'], $data['employer'], $data['related_layoff_id'], $data['assessment_status'], $data['notice_date'], $data['affected_date'], $data['exception_evidence'], $data['adjudication_url'], $data['source_name'], $data['source_url'], $data['evidence_excerpt'], $data['evidence_hash'], $data['created_at']));
    if ($wpdb->last_error) return new WP_Error('alt_db_error', 'WARN transparency record could not be saved.', array('status' => 500));
    $row = $wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE record_key = %s", $key), ARRAY_A);
    return rest_ensure_response($row ?: $data);
}

function alt_api_trash(WP_REST_Request $r) {
    global $wpdb;
    $table = alt_db_table();
    $reason = (string) $r->get_param('reason');
    $out = array('trashed_posts' => array(), 'deleted_rows' => array(), 'orphan_events_cleaned' => array(), 'not_found' => array(), 'suppressed' => 0);

    // `ids` are TABLE row ids — the `id` field the public /query API returns.
    // Rows mirrored from a CPT post get the post trashed (hooks remove the
    // row); table-only rows (bulk WARN) are deleted directly. Either way the
    // dedup hash goes on the suppression list so the daily imports (which
    // re-scrape the same source data) cannot resurrect the entry.
    foreach ((array) $r->get_param('ids') as $tid) {
        $tid = (int) $tid;
        $row = $tid ? $wpdb->get_row($wpdb->prepare(
            "SELECT id, post_id, event_id, dedup_hash FROM $table WHERE id = %d", $tid)) : null;
        if (!$row) {
            $out['not_found'][] = $tid;
            continue;
        }
        if ($row->dedup_hash) {
            alt_suppress_hash($row->dedup_hash, 'trashed: ' . $reason);
            $out['suppressed']++;
        }
        if ($row->post_id) {
            wp_trash_post((int) $row->post_id);
            $wpdb->delete($table, array('id' => (int) $row->id)); // belt & braces
            $out['trashed_posts'][] = (int) $row->post_id;
        } else {
            $wpdb->delete($table, array('id' => (int) $row->id));
            $out['deleted_rows'][] = (int) $row->id;
        }
        if (alt_cleanup_orphan_event((int) $row->event_id)) $out['orphan_events_cleaned'][] = (int) $row->event_id;
    }

    // Direct id spaces still accepted for completeness.
    foreach ((array) $r->get_param('post_ids') as $pid) {
        $pid = (int) $pid;
        if ($pid && get_post_type($pid) === 'layoffs') {
            wp_trash_post($pid);
            $out['trashed_posts'][] = $pid;
        } elseif ($pid) {
            $out['not_found'][] = $pid;
        }
    }
    foreach ((array) $r->get_param('row_ids') as $rid) {
        $rid = (int) $rid;
        $deleted = $rid ? $wpdb->delete($table, array('id' => $rid, 'post_id' => null)) : 0;
        if ($deleted) { $out['deleted_rows'][] = $rid; } elseif ($rid) { $out['not_found'][] = $rid; }
    }

    if (!empty($out['trashed_posts']) || !empty($out['deleted_rows'])) {
        alt_log_correction('removed', array_merge($out['trashed_posts'], $out['deleted_rows']), $reason);
    }
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

/** Merge LLM-confirmed duplicate rows without throwing away their evidence. */
function alt_api_merge_events(WP_REST_Request $r) {
    global $wpdb;
    $table = alt_db_table();
    $events = alt_events_table();
    $reports = alt_source_reports_table();
    $reason = trim((string) $r->get_param('reason'));
    $out = array('merged_rows' => array(), 'not_found' => array(), 'rejected' => array());
    foreach ((array) $r->get_param('merges') as $merge) {
        $keeper_id = (int) ($merge['keeper_id'] ?? 0);
        $keeper = $keeper_id ? $wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id = %d", $keeper_id), ARRAY_A) : null;
        if (!$keeper) { $out['not_found'][] = $keeper_id; continue; }
        $keeper_event = alt_event_register_report_for_layoff($keeper_id, $keeper);
        if (!$keeper_event) { $out['rejected'][] = $keeper_id; continue; }
        foreach (array_unique(array_map('intval', (array) ($merge['duplicate_ids'] ?? array()))) as $duplicate_id) {
            if (!$duplicate_id || $duplicate_id === $keeper_id) continue;
            $duplicate = $wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id = %d", $duplicate_id), ARRAY_A);
            if (!$duplicate) { $out['not_found'][] = $duplicate_id; continue; }
            $duplicate_event = alt_event_for_layoff($duplicate_id);
            alt_event_add_report($keeper_event, $duplicate);
            if ($duplicate_event && $duplicate_event !== $keeper_event) {
                $old_reports = $wpdb->get_results($wpdb->prepare("SELECT source_name, source_type, verification_level, source_url, excerpt, ai_causation, ai_language FROM $reports WHERE event_id = %d", $duplicate_event), ARRAY_A);
                foreach ($old_reports as $report) alt_event_add_report($keeper_event, $report);
                $wpdb->delete($reports, array('event_id' => $duplicate_event));
                $wpdb->delete($events, array('id' => $duplicate_event));
            }
            if (!empty($duplicate['dedup_hash'])) alt_suppress_hash($duplicate['dedup_hash'], 'merged: ' . $reason);
            if (!empty($duplicate['post_id'])) wp_trash_post((int) $duplicate['post_id']);
            $wpdb->delete($table, array('id' => $duplicate_id));
            $out['merged_rows'][] = $duplicate_id;
        }
    }
    if (!empty($out['merged_rows'])) {
        alt_log_correction('merged', $out['merged_rows'], $reason ?: 'Confirmed duplicate sources merged into canonical event');
        if (function_exists('alt_flush_caches')) alt_flush_caches();
    }
    return rest_ensure_response($out);
}

function alt_api_bulk_purge(WP_REST_Request $r) {
    global $wpdb;
    // `edited = 0`: editor-corrected rows are pinned — the purge+reimport
    // cycle must not throw a correction away (the original bad source row is
    // separately blocked by the suppression list).
    $deleted = (int) $wpdb->query(
        "DELETE FROM " . alt_db_table() . " WHERE source_type = 'warn' AND post_id IS NULL AND edited = 0");
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response(array('deleted' => $deleted));
}

/**
 * Key-protected editorial correction of specific fields on specific rows.
 * Every edit: (1) suppresses the row's ORIGINAL dedup hash — so the daily
 * import of the same (wrong) source data can't re-create it, (2) re-hashes
 * the row to a derived value, (3) pins the row with edited=1 — so purge and
 * upsert leave it alone. `reason` is required (goes in the suppression list
 * and the workflow audit log).
 */
function alt_api_edit(WP_REST_Request $r) {
    global $wpdb;
    $table = alt_db_table();
    $reason = trim((string) $r->get_param('reason'));
    if ($reason === '') {
        return new WP_Error('alt_bad_request', 'reason is required.', array('status' => 400));
    }
    $edits = $r->get_param('edits');
    if (!is_array($edits)) {
        return new WP_Error('alt_bad_request', 'edits must be an array of {id, fields}.', array('status' => 400));
    }

    $allowed = array('company', 'job_count', 'layoff_date', 'industry', 'country', 'employer_country', 'state', 'ai_explicit', 'ai_causation', 'confidence', 'review_status', 'announced', 'source_url', 'excerpt');
    $out = array('edited' => array(), 'not_found' => array(), 'rejected' => array());

    foreach ($edits as $e) {
        $id = (int) ($e['id'] ?? 0);
        $fields = is_array($e['fields'] ?? null) ? $e['fields'] : array();
        $row = $id ? $wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id = %d", $id), ARRAY_A) : null;
        if (!$row) { $out['not_found'][] = $id; continue; }

        $data = array();
        foreach ($fields as $k => $v) {
            if (!in_array($k, $allowed, true)) { continue; }
            switch ($k) {
                case 'job_count':   $data[$k] = max(0, (int) $v); break;
                case 'layoff_date': $data[$k] = alt_db_valid_date((string) $v); break;
                case 'country':     $data[$k] = function_exists('alt_normalize_country') ? alt_normalize_country((string) $v) : (string) $v; break;
                case 'employer_country': $data[$k] = function_exists('alt_normalize_country') ? alt_normalize_country((string) $v) : (string) $v; break;
                case 'industry':    $data[$k] = function_exists('alt_normalize_industry') ? alt_normalize_industry((string) $v) : (string) $v; break;
                case 'state':       $data[$k] = substr(strtoupper((string) $v), 0, 2); break;
                case 'ai_explicit':
                case 'announced':   $data[$k] = !empty($v) ? 1 : 0; break;
                case 'confidence':  $data[$k] = min(100, max(0, (int) $v)); break;
                case 'ai_causation': $data[$k] = alt_normalize_ai_causation($v); break;
                case 'review_status': $data[$k] = alt_normalize_review_status($v); break;
                default:            $data[$k] = (string) $v;
            }
        }
        if (!$data) { $out['rejected'][] = $id; continue; }

        if (!empty($row['dedup_hash']) && empty($row['edited'])) {
            alt_suppress_hash($row['dedup_hash'], 'edited: ' . $reason);
            $data['dedup_hash'] = md5('edited:' . $row['dedup_hash']);
        }
        $data['edited'] = 1;
        if (isset($data['company'])) {
            $data['company_key'] = substr(function_exists('alt_company_key') ? alt_company_key($data['company']) : '', 0, 255);
        }
        // FAIL LOUDLY (iron rule): a silent false from $wpdb->update (e.g. a
        // missing column after a failed migration) must not report success.
        $updated = $wpdb->update($table, $data, array('id' => $id));
        if ($updated === false) {
            return new WP_Error('alt_db_error', 'Update failed on id ' . $id . ': ' . $wpdb->last_error,
                array('status' => 500, 'edited_so_far' => $out['edited']));
        }

        // Keep the CPT mirror consistent for rich entries.
        if (!empty($row['post_id'])) {
            $meta_map = array('company' => 'company_name', 'job_count' => 'job_count', 'layoff_date' => 'layoff_date',
                'industry' => 'industry', 'country' => 'country', 'employer_country' => 'employer_country', 'state' => 'state',
                'ai_explicit' => 'ai_explicit', 'ai_causation' => 'ai_causation', 'confidence' => 'confidence', 'review_status' => 'review_status', 'source_url' => 'source_url');
            foreach ($meta_map as $col => $meta) {
                if (array_key_exists($col, $data)) { update_post_meta((int) $row['post_id'], $meta, $data[$col]); }
            }
        }
        $out['edited'][] = $id;
        $edited_fields = array_unique(array_merge($edited_fields ?? array(), array_keys($data)));
    }

    if (!empty($out['edited'])) {
        alt_log_correction('corrected', $out['edited'], $reason,
            'fields: ' . implode(', ', array_diff($edited_fields ?? array(), array('edited', 'dedup_hash', 'company_key'))));
    }
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

function alt_api_bulk(WP_REST_Request $r) {
    $entries = $r->get_param('entries');
    if (!is_array($entries)) {
        return new WP_Error('alt_bad_request', 'entries must be an array.', array('status' => 400));
    }
    $upserted = 0;
    foreach ($entries as $e) {
        if (!is_array($e)) continue;
        $hash = substr((string) ($e['dedup_hash'] ?? ''), 0, 32);
        $company = trim((string) ($e['company_name'] ?? ''));
        if ($hash === '' || $company === '') continue;
        $row = array(
            'post_id'            => null,
            'dedup_hash'         => $hash,
            'company'            => $company,
            'ticker'             => $e['ticker'] ?? '',
            'job_count'          => $e['job_count'] ?? 0,
            'layoff_date'        => $e['layoff_date'] ?? '',
            'industry'           => function_exists('alt_normalize_industry') ? alt_normalize_industry((string) ($e['industry'] ?? '')) : ($e['industry'] ?? ''),
            'country'            => function_exists('alt_normalize_country') ? alt_normalize_country((string) ($e['country'] ?? '')) : ($e['country'] ?? ''),
            'employer_country'   => function_exists('alt_normalize_country') ? alt_normalize_country((string) ($e['employer_country'] ?? '')) : ($e['employer_country'] ?? ''),
            'state'              => function_exists('alt_normalize_state') ? alt_normalize_state((string) ($e['state'] ?? '')) : ($e['state'] ?? ''),
            'source_type'        => in_array($e['source_type'] ?? '', alt_allowed_source_types(), true) ? $e['source_type'] : 'news',
            'verification_level' => in_array($e['verification_level'] ?? '', alt_allowed_verification_levels(), true) ? $e['verification_level'] : 'bronze',
            'source_name'        => $e['source_name'] ?? '',
            'source_url'         => $e['source_url'] ?? '',
            'ai_explicit'        => !empty($e['ai_explicit']),
            'ai_causation'       => alt_normalize_ai_causation($e['ai_causation'] ?? 'unknown'),
            'confidence'         => min(100, max(0, (int) ($e['confidence'] ?? 0))),
            'review_status'      => alt_normalize_review_status($e['review_status'] ?? 'legacy_unreviewed'),
            'announced'          => !empty($e['announced']),
            'ai_language'        => $e['ai_language'] ?? '',
            'reason_tags'        => $e['reason_tags'] ?? array(),
            'roles'              => $e['roles'] ?? '',
            'excerpt'            => $e['excerpt'] ?? '',
        );
        $id = alt_db_upsert($row);
        // Bulk WARN rows are canonical events too. Registering here keeps the
        // evidence graph complete immediately after an import instead of
        // waiting for the daily legacy migration. The report insert is
        // idempotent, so a re-import retains rather than duplicates evidence.
        if ($id) alt_event_register_report_for_layoff($id, $row);
        if ($id) $upserted++;
    }
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response(array('received' => count($entries), 'upserted' => $upserted));
}

function alt_api_facets(WP_REST_Request $r) {
    return alt_api_cached('facets', $r, function () {
        global $wpdb;
        $t = alt_db_table();
        $range = $wpdb->get_row("SELECT MIN(layoff_date) mn, MAX(layoff_date) mx FROM $t WHERE layoff_date > '2000-01-01'");
        return array(
            'industries' => $wpdb->get_col("SELECT DISTINCT industry FROM $t WHERE industry <> '' ORDER BY industry") ?: array(),
            'countries'  => $wpdb->get_col("SELECT DISTINCT country FROM $t WHERE country <> '' ORDER BY country") ?: array(),
            'states'     => $wpdb->get_col("SELECT DISTINCT state FROM $t WHERE state <> '' ORDER BY state") ?: array(),
            'sources'    => array_values(array_unique(array_merge(
                $wpdb->get_col("SELECT DISTINCT verification_level FROM $t WHERE verification_level <> ''") ?: array(),
                $wpdb->get_col("SELECT DISTINCT source_type FROM $t WHERE source_type <> ''") ?: array()
            ))),
            'min_date'   => $range ? $range->mn : null,
            'max_date'   => $range ? $range->mx : null,
        );
    });
}
add_action('rest_api_init', 'alt_register_query_routes');

function alt_api_migrate(WP_REST_Request $r) {
    alt_db_install();
    $synced = alt_db_migrate();
    global $wpdb;
    $count = (int) $wpdb->get_var("SELECT COUNT(*) FROM " . alt_db_table());
    return rest_ensure_response(array('synced' => $synced, 'table_rows' => $count));
}

function alt_api_event_migrate(WP_REST_Request $r) {
    global $wpdb;
    $after = max(0, (int) $r->get_param('after_id'));
    $limit = min(1000, max(1, (int) ($r->get_param('limit') ?: 500)));
    $table = alt_db_table();
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT id, source_name, source_type, verification_level, source_url, excerpt, ai_causation, ai_language FROM $table WHERE event_id = 0 AND id > %d ORDER BY id ASC LIMIT %d",
        $after, $limit), ARRAY_A) ?: array();
    $last = $after;
    foreach ($rows as $row) {
        $last = (int) $row['id'];
        alt_event_register_report_for_layoff($last, $row);
    }
    $remaining = (int) $wpdb->get_var("SELECT COUNT(*) FROM $table WHERE event_id = 0");
    return rest_ensure_response(array('processed' => count($rows), 'last_id' => $last, 'remaining' => $remaining));
}

/**
 * Key-protected data hygiene: re-normalize country + industry across the fast
 * table (one UPDATE per distinct value, so 100K rows is still fast) and across
 * CPT post meta. Idempotent; run after normalizer rules change.
 */
function alt_api_cleanup(WP_REST_Request $r) {
    global $wpdb;
    $table = alt_db_table();
    $changed = array('country' => 0, 'industry' => 0, 'posts' => 0);

    foreach (array('country' => 'alt_normalize_country', 'industry' => 'alt_normalize_industry') as $col => $fn) {
        if (!function_exists($fn)) continue;
        $values = $wpdb->get_col("SELECT DISTINCT $col FROM $table WHERE $col <> ''");
        foreach ($values ?: array() as $old) {
            $new = call_user_func($fn, $old);
            if ($new !== $old) {
                $changed[$col] += (int) $wpdb->query($wpdb->prepare(
                    "UPDATE $table SET $col = %s WHERE $col = %s", $new, $old));
            }
        }
    }

    // Curated company-level industry overrides (Booking.com et al) — applied
    // to already-imported rows; new rows get them at upsert time.
    if (function_exists('alt_industry_override')) {
        $ovr_companies = $wpdb->get_col("SELECT DISTINCT company FROM $table");
        $changed['industry_overrides'] = 0;
        foreach ($ovr_companies ?: array() as $co) {
            $ovr = alt_industry_override($co);
            if ($ovr !== '') {
                $changed['industry_overrides'] += (int) $wpdb->query($wpdb->prepare(
                    "UPDATE $table SET industry = %s WHERE company = %s AND industry <> %s AND edited = 0",
                    $ovr, $co, $ovr));
            }
        }
    }

    // Date sanity: a filing typo like "2050-12-31" or "3030-03-30" must not
    // define the tracker's visible range. Implausible dates are cleared (the
    // entry stays listed, just undated). WARN effective dates run at most
    // about a year out, so allow 18 months of headroom.
    $changed['dates'] = (int) $wpdb->query(
        "UPDATE $table SET layoff_date = NULL
         WHERE layoff_date > DATE_ADD(CURDATE(), INTERVAL 18 MONTH)
            OR layoff_date < '2015-01-01'");

    // CPT posts (a few hundred, not the bulk rows) — keep meta consistent.
    $ids = get_posts(array(
        'post_type' => 'layoffs', 'post_status' => 'publish',
        'posts_per_page' => -1, 'fields' => 'ids', 'no_found_rows' => true,
    ));
    $date_ceiling = gmdate('Y-m-d', strtotime('+18 months'));
    foreach ($ids as $id) {
        $dirty = false;
        foreach (array('country' => 'alt_normalize_country', 'industry' => 'alt_normalize_industry') as $key => $fn) {
            if (!function_exists($fn)) continue;
            $old = (string) get_post_meta($id, $key, true);
            $new = call_user_func($fn, $old);
            if ($key === 'country' && $new === '' && get_post_meta($id, 'verification_level', true) === 'gold') {
                $new = 'United States';
            }
            if ($new !== $old) { update_post_meta($id, $key, $new); $dirty = true; }
        }
        $date = (string) get_post_meta($id, 'layoff_date', true);
        if ($date !== '' && ($date > $date_ceiling || $date < '2015-01-01')) {
            update_post_meta($id, 'layoff_date', '');
            $dirty = true;
        }
        if ($dirty) { alt_db_sync_post($id); $changed['posts']++; }
    }

    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($changed);
}

/**
 * Something in the stack (WP core nocache, a host cache plugin) appends
 * "Cache-Control: no-cache, no-store" + "Expires: 0" to REST responses, which
 * overrides our max-age and disables browser caching. Two-layer suppression
 * for anonymous GETs on the public read endpoints only.
 */
function alt_is_public_read_request() {
    if (is_user_logged_in()) return false;
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') return false;
    $uri = $_SERVER['REQUEST_URI'] ?? '';
    foreach (array('query', 'aggregate', 'facets', 'stats', 'all') as $ep) {
        if (strpos($uri, 'layoffs/v1/' . $ep) !== false) return true;
    }
    return false;
}
add_filter('rest_send_nocache_headers', function ($send) {
    return alt_is_public_read_request() ? false : $send;
});
// Anything that calls WP's nocache_headers() (core, host cache plugins) goes
// through this filter — swap the no-store set for our cacheable one.
add_filter('nocache_headers', function ($headers) {
    if (alt_is_public_read_request()) {
        return array('Cache-Control' => 'public, max-age=60');
    }
    return $headers;
}, 999);

/**
 * Micro-cache for the public read endpoints. Nearly every visitor issues the
 * identical default requests, so a 5-minute transient keyed by (params + data
 * version) collapses thousands of MySQL round-trips into one. Any write bumps
 * alt_data_ver (see alt_flush_caches), instantly orphaning stale entries.
 */
function alt_api_cached($tag, WP_REST_Request $r, $compute) {
    $params = $r->get_query_params();
    unset($params['_'], $params['cb']); // cache-buster noise
    ksort($params);
    $key = 'altq_' . md5($tag . '|' . (int) get_option('alt_data_ver', 1) . '|' . wp_json_encode($params));

    $payload = get_transient($key);
    if ($payload === false) {
        $payload = call_user_func($compute);
        set_transient($key, $payload, 5 * MINUTE_IN_SECONDS);
    }
    $resp = rest_ensure_response($payload);
    $resp->header('Cache-Control', 'public, max-age=60');
    return $resp;
}

function alt_api_query(WP_REST_Request $r) {
    return alt_api_cached('query', $r, function () use ($r) {
        return alt_api_query_compute($r);
    });
}

function alt_api_query_compute(WP_REST_Request $r) {
    global $wpdb;
    $table = alt_db_table();
    list($where, $params) = alt_db_where($r);

    $sortable = array('layoff_date', 'job_count', 'company', 'country', 'state', 'industry');
    $sort = in_array($r->get_param('sort'), $sortable, true) ? $r->get_param('sort') : 'layoff_date';
    $dir = strtolower((string) $r->get_param('dir')) === 'asc' ? 'ASC' : 'DESC';

    $per = min(200, max(1, (int) ($r->get_param('per_page') ?: 25)));
    $page = max(1, (int) ($r->get_param('page') ?: 1));
    $offset = ($page - 1) * $per;

    $total = (int) $wpdb->get_var(alt_db_prep("SELECT COUNT(*) FROM $table WHERE $where", $params));
    // Undated rows always sort LAST (MySQL would otherwise put NULLs first on
    // ascending date sorts, burying real oldest entries under blanks).
    $order = ($sort === 'layoff_date')
        ? "(layoff_date IS NULL) ASC, layoff_date $dir, id DESC"
        : "$sort $dir, id DESC";
    $rows = $wpdb->get_results(alt_db_prep(
        "SELECT * FROM $table WHERE $where ORDER BY $order LIMIT %d OFFSET %d",
        array_merge($params, array($per, $offset))
    ));

    return array(
        'total'    => $total,
        'page'     => $page,
        'per_page' => $per,
        'data'     => array_map('alt_db_row_to_array', $rows ?: array()),
    );
}

function alt_api_aggregate(WP_REST_Request $r) {
    return alt_api_cached('aggregate', $r, function () use ($r) {
        return alt_api_aggregate_compute($r);
    });
}

function alt_api_aggregate_compute(WP_REST_Request $r) {
    global $wpdb;
    $table = alt_db_table();
    list($where, $params) = alt_db_where($r);

    // Headline totals
    $totals = $wpdb->get_row(alt_db_prep(
        "SELECT COUNT(*) entries, COALESCE(SUM(job_count),0) jobs,
                SUM(ai_explicit) ai_entries,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs,
                SUM(CASE WHEN ai_causation='primary_cause' THEN 1 ELSE 0 END) ai_primary_entries,
                COALESCE(SUM(CASE WHEN ai_causation='primary_cause' THEN job_count END),0) ai_primary_jobs,
                SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN 1 ELSE 0 END) ai_verified_entries,
                COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) ai_verified_jobs,
                SUM(announced) announced_entries,
                COALESCE(SUM(CASE WHEN announced=1 THEN job_count END),0) announced_jobs,
                COUNT(DISTINCT company_key) companies,
                COUNT(DISTINCT NULLIF(industry,'')) industries,
                COUNT(DISTINCT NULLIF(country,'')) countries,
                COUNT(DISTINCT NULLIF(state,'')) states,
                MIN(CASE WHEN layoff_date > '2000-01-01' THEN layoff_date END) min_date,
                MAX(layoff_date) max_date
         FROM $table WHERE $where", $params));

    // Top-N helpers (each slicer ignores its own dimension). Each entry is
    // [label, total jobs, AI-attributed jobs] so bars can show the AI share.
    $topN = function ($col, $except) use ($wpdb, $table, $r) {
        list($w, $p) = alt_db_where($r, $except);
        $sql = "SELECT $col k, SUM(job_count) v,
                       COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) a
                FROM $table
                WHERE $w AND $col <> '' GROUP BY $col ORDER BY v DESC LIMIT 12";
        $rows = $wpdb->get_results(alt_db_prep($sql, $p));
        $out = array();
        foreach ($rows ?: array() as $row) { $out[] = array($row->k, (int) $row->v, (int) $row->a); }
        return $out;
    };

    // Reason breakdown (9 fixed tags → one SUM each)
    $reason_tags = array('ai_automation','possible_ai','revenue_decline','restructuring',
        'merger_acquisition','offshoring','product_discontinuation','cost_reduction','macroeconomic');
    list($rw, $rp) = alt_db_where($r, 'reasons');
    $reasons = array();
    foreach ($reason_tags as $tag) {
        $val = (int) $wpdb->get_var(alt_db_prep(
            "SELECT COALESCE(SUM(job_count),0) FROM $table WHERE $rw AND reason_tags LIKE %s",
            array_merge($rp, array('%,' . $tag . ',%'))));
        if ($val > 0) $reasons[] = array($tag, $val);
    }

    // Monthly series (all jobs + AI jobs) for trend + cumulative charts.
    // CONCAT(YEAR,LPAD(MONTH)) avoids '%' so it's safe whether or not this SQL
    // is run through $wpdb->prepare (which would otherwise eat DATE_FORMAT's %).
    $months = $wpdb->get_results(alt_db_prep(
        "SELECT CONCAT(YEAR(layoff_date),'-',LPAD(MONTH(layoff_date),2,'0')) m,
                SUM(job_count) jobs,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs
         FROM $table WHERE $where AND layoff_date > '2000-01-01'
         GROUP BY m ORDER BY m ASC", $params));
    $series = array();
    foreach ($months ?: array() as $row) {
        $series[] = array('month' => $row->m, 'jobs' => (int) $row->jobs, 'ai_jobs' => (int) $row->ai_jobs);
    }

    // Largest single events
    list($w2, $p2) = alt_db_where($r);
    $top_events = $wpdb->get_results(alt_db_prep(
        "SELECT company, job_count, layoff_date, ai_explicit, state, country
         FROM $table WHERE $w2 ORDER BY job_count DESC, id DESC LIMIT 10", $p2));
    $leaders = array();
    foreach ($top_events ?: array() as $row) {
        $leaders[] = array(
            'company_name' => $row->company, 'job_count' => (int) $row->job_count,
            'layoff_date' => $row->layoff_date ?: '', 'ai_explicit' => (bool) $row->ai_explicit,
            'state' => $row->state, 'country' => $row->country,
        );
    }

    return array(
        'totals' => array(
            'jobs'       => (int) $totals->jobs,
            'entries'    => (int) $totals->entries,
            'ai_jobs'    => (int) $totals->ai_jobs,
            'ai_primary_entries' => (int) $totals->ai_primary_entries,
            'ai_primary_jobs' => (int) $totals->ai_primary_jobs,
            'ai_verified_jobs'    => (int) $totals->ai_verified_jobs,
            'ai_verified_entries' => (int) $totals->ai_verified_entries,
            'announced_entries' => (int) $totals->announced_entries,
            'announced_jobs'    => (int) $totals->announced_jobs,
            'ai_entries' => (int) $totals->ai_entries,
            'companies'  => (int) $totals->companies,
            'industries' => (int) $totals->industries,
            'countries'  => (int) $totals->countries,
            'states'     => (int) $totals->states,
            'min_date'   => $totals->min_date,
            'max_date'   => $totals->max_date,
        ),
        'top_industries' => $topN('industry', 'industry'),
        'top_countries'  => $topN('country', 'country'),
        'top_states'     => $topN('state', 'state'),
        'reasons'        => $reasons,
        'series'         => $series,
        'leaders'        => $leaders,
    );
}
