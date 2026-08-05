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
        job_count_max INT UNSIGNED NOT NULL DEFAULT 0,
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
        role_categories VARCHAR(255) NOT NULL DEFAULT '',
        roles_evidence TEXT NULL,
        excerpt TEXT NULL,
        event_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
        /* Superset dedup: when a company-wide news/announced total and its
         * site-level WARN rows document the SAME event, the smaller rows point
         * at the primary (most-complete) row's id here and are EXCLUDED from
         * job totals, so one real event is counted once, not twice. 0 = counts
         * normally (a standalone row or the primary of a group). */
        superset_of BIGINT UNSIGNED NOT NULL DEFAULT 0,
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
        KEY event_id (event_id),
        KEY superset_of (superset_of)
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

    // Permanent-archive index for source URLs. Keyed by md5(source_url) so the
    // many WARN rows that share one state source file store ONE snapshot, while
    // one-per-row news/SEC/ERM URLs store one each. This is additive telemetry:
    // it never joins into a layoff count and a missing/failed row here only
    // means "no second link yet", never a broken row. Status is one of
    // 'archived' (a permanent Wayback permalink exists in archived_url),
    // 'pending' (queued/rate-limited, retried) or 'unavailable' (genuinely not
    // archivable after repeated attempts; reported honestly, not retried
    // forever).
    $archive = alt_archive_table();
    dbDelta("CREATE TABLE $archive (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        url_hash CHAR(32) NOT NULL,
        source_url TEXT NULL,
        archived_url TEXT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        attempts INT UNSIGNED NOT NULL DEFAULT 0,
        checked_at DATETIME NULL,
        archived_at DATETIME NULL,
        PRIMARY KEY (id),
        UNIQUE KEY url_hash (url_hash),
        KEY status (status),
        KEY status_checked (status, checked_at)
    ) $charset;");

    // Digest subscribers: ONE shared list for BOTH trackers (see
    // includes/subscribe.php for the consent model). The first personal data
    // this site stores, so the shape is deliberately minimal: an address, the
    // consent flags, per-flag frequency, double-opt-in state, and two random
    // tokens so no URL ever carries the address itself. Rows never linger:
    // unsubscribed and never-confirmed rows are hard-deleted after
    // ALT_DIGEST_RETENTION_DAYS by the digest cron.
    $subscribers = $wpdb->prefix . 'alt_subscribers';
    dbDelta("CREATE TABLE $subscribers (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        email VARCHAR(190) NOT NULL,
        consent_layoff TINYINT(1) NOT NULL DEFAULT 0,
        consent_talent TINYINT(1) NOT NULL DEFAULT 0,
        consent_articles TINYINT(1) NOT NULL DEFAULT 0,
        freq_layoff VARCHAR(6) NOT NULL DEFAULT 'weekly',
        freq_talent VARCHAR(6) NOT NULL DEFAULT 'weekly',
        freq_articles VARCHAR(6) NOT NULL DEFAULT 'weekly',
        status VARCHAR(12) NOT NULL DEFAULT 'pending',
        confirm_token CHAR(64) NULL,
        unsub_token CHAR(64) NOT NULL,
        pending_prefs TEXT NULL,
        created_at DATETIME NOT NULL,
        confirmed_at DATETIME NULL,
        unsubscribed_at DATETIME NULL,
        last_sent_at DATETIME NULL,
        PRIMARY KEY (id),
        UNIQUE KEY email (email),
        KEY status (status),
        KEY confirm_token (confirm_token),
        KEY unsub_token (unsub_token),
        KEY status_created (status, created_at)
    ) $charset;");

    // Digest send log. One row per send RUN (not per recipient), so the stats
    // route can answer "when did the last digest go out and to how many" from
    // stored fact rather than from a guess. Counts only: this table has no
    // column that could hold an address, deliberately.
    $digest_sends = $wpdb->prefix . 'alt_digest_sends';
    dbDelta("CREATE TABLE $digest_sends (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        freq VARCHAR(6) NOT NULL DEFAULT 'weekly',
        sent_at DATETIME NOT NULL,
        recipients INT UNSIGNED NOT NULL DEFAULT 0,
        eligible INT UNSIGNED NOT NULL DEFAULT 0,
        PRIMARY KEY (id),
        KEY sent_at (sent_at)
    ) $charset;");

    // Aggregate click counter for digest links. The row is created when the
    // digest is COMPOSED, so the redirect can only ever resolve a link this
    // site already put in that send. The counter is a single integer per
    // (send_id, link): there is no subscriber id, no IP, no user agent and no
    // per-click row here, so the store cannot answer "who clicked" even in
    // principle. See includes/subscribe.php for why there is no open pixel.
    $digest_links = $wpdb->prefix . 'alt_digest_links';
    dbDelta("CREATE TABLE $digest_links (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        send_id BIGINT UNSIGNED NOT NULL,
        link_hash CHAR(32) NOT NULL,
        url VARCHAR(600) NOT NULL,
        clicks INT UNSIGNED NOT NULL DEFAULT 0,
        PRIMARY KEY (id),
        UNIQUE KEY send_link (send_id, link_hash)
    ) $charset;");
}

function alt_events_table() { global $wpdb; return $wpdb->prefix . 'alt_events'; }
function alt_source_reports_table() { global $wpdb; return $wpdb->prefix . 'alt_source_reports'; }
function alt_company_directory_table() { global $wpdb; return $wpdb->prefix . 'alt_company_directory'; }
function alt_source_runs_table() { global $wpdb; return $wpdb->prefix . 'alt_source_runs'; }
function alt_warn_transparency_table() { global $wpdb; return $wpdb->prefix . 'alt_warn_transparency'; }
function alt_archive_table() { global $wpdb; return $wpdb->prefix . 'alt_archive'; }

/**
 * Stable key for a source URL in the archive store. Many WARN rows share one
 * source file, so the archive is keyed by URL (not by row) and one snapshot
 * covers every row citing that file. Trim only — the URL is stored as sent so
 * the availability check and the render both hash the same string.
 */
function alt_archive_url_key($url) {
    return md5(trim((string) $url));
}

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

/**
 * Same self-heal guard for the source-archive index: an FTP deploy can serve a
 * request before dbDelta has created the new table, so a writer verifies it and
 * runs the idempotent installer if needed before using it.
 */
function alt_archive_table_ready() {
    global $wpdb;
    $table = alt_archive_table();
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
    $date   = gmdate('Y-m-d');
    $reason = substr((string) $reason, 0, 400);
    $detail = substr((string) $detail, 0, 200);
    $n      = count((array) $ids);
    // Collapse repeat automated passes: the batched enrichment jobs (industry
    // classification, reason-tag backfill) log one row per 200-item batch and
    // run many times a day, which buried the meaningful corrections (merges,
    // removals, count fixes) AND blew the 200-entry cap, evicting them. A
    // same-day entry with identical action/reason/detail now accumulates its
    // count in place instead of adding a new row, so one line reads
    // "3,000 entries enriched" rather than fifteen "200 entries enriched".
    foreach ($log as &$e) {
        if (($e['date'] ?? '') === $date && ($e['action'] ?? '') === $action
            && ($e['reason'] ?? '') === $reason && ($e['detail'] ?? '') === $detail) {
            $e['count'] = (int) ($e['count'] ?? 0) + $n;
            update_option('alt_corrections_log', $log, false);
            return;
        }
    }
    unset($e);
    $log[] = array('date' => $date, 'action' => $action, 'count' => $n, 'reason' => $reason, 'detail' => $detail);
    if (count($log) > 200) $log = array_slice($log, -200);
    update_option('alt_corrections_log', $log, false);
}

/**
 * Provenance of the corrections in the log, computed from the entries' own
 * recorded text and nothing else. An entry counts as internally originated
 * only when its stored action/reason/detail explicitly names an internal
 * audit or automated check, and as externally originated only when it
 * explicitly names an outside report. An entry matching neither (or,
 * ambiguously, both) is counted UNRECORDED, never assigned a guessed origin.
 * The log does not carry a structured origin field, so this is the computable
 * share; the remainder is disclosed as unrecorded rather than split.
 */
function alt_corrections_provenance() {
    $log = get_option('alt_corrections_log');
    if (!is_array($log)) $log = array();
    $internal_markers = array('automated', 'audit', 'dedup', 'backfill',
        'reconciliation', 'legacy repair', 'duplicate cleanup', 'parser',
        'self-audit', 'importer');
    $external_markers = array('reader', 'contact page', 'reported to us',
        'external report', 'user report', 'tip');
    $out = array('entries' => count($log), 'internal' => 0, 'external' => 0, 'unrecorded' => 0);
    foreach ($log as $e) {
        if (!is_array($e)) { $out['unrecorded']++; continue; }
        $text = strtolower(($e['action'] ?? '') . ' ' . ($e['reason'] ?? '') . ' ' . ($e['detail'] ?? ''));
        $int = $ext = false;
        foreach ($internal_markers as $m) { if (strpos($text, $m) !== false) { $int = true; break; } }
        foreach ($external_markers as $m) { if (strpos($text, $m) !== false) { $ext = true; break; } }
        if ($int && !$ext)      $out['internal']++;
        elseif ($ext && !$int)  $out['external']++;
        else                    $out['unrecorded']++;
    }
    return $out;
}

/**
 * One-time compaction of the EXISTING corrections log: merge already-stored
 * rows that share date+action+reason+detail (the historical wall of identical
 * "200 entries enriched" lines) into single accumulating entries, preserving
 * order by first occurrence. Idempotent; safe to run on every deploy.
 */
function alt_compact_corrections_log() {
    $log = get_option('alt_corrections_log');
    if (!is_array($log) || !$log) return;
    $out = array();
    $index = array();
    foreach ($log as $e) {
        $key = ($e['date'] ?? '') . '|' . ($e['action'] ?? '') . '|' . ($e['reason'] ?? '') . '|' . ($e['detail'] ?? '');
        if (isset($index[$key])) {
            $out[$index[$key]]['count'] = (int) ($out[$index[$key]]['count'] ?? 0) + (int) ($e['count'] ?? 0);
        } else {
            $index[$key] = count($out);
            $out[] = $e;
        }
    }
    if (count($out) !== count($log)) update_option('alt_corrections_log', $out, false);
}

/**
 * House style is "no em-dashes in UI copy", but the corrections log is DATA:
 * historical notes were written with em-dashes before that rule existed, and they
 * render verbatim on the tracker. A code change can't reach them, so normalize
 * the stored strings instead. A SPACED em/en dash is a clause break (-> comma);
 * any remaining one is a joiner or range (-> hyphen, so "2015-2017" stays a
 * range). Idempotent: once converted no dashes remain, so re-running is a no-op.
 */
function alt_normalize_corrections_dashes() {
    $log = get_option('alt_corrections_log');
    if (!is_array($log) || !$log) return;
    $changed = false;
    foreach ($log as $i => $e) {
        if (!is_array($e)) continue;
        // Normalize EVERY string field, not just reason/detail: log entries have
        // varied over time and a dash in any of them renders on the tracker.
        foreach ($e as $f => $val) {
            if (!is_string($val) || $val === '') continue;
            $new = preg_replace('/\s+[\x{2014}\x{2013}]\s+/u', ', ', $val);
            $new = preg_replace('/[\x{2014}\x{2013}]/u', '-', (string) $new);
            if ($new !== null && $new !== $val) {
                $log[$i][$f] = $new;
                $changed = true;
            }
        }
    }
    if ($changed) update_option('alt_corrections_log', $log, false);
}

/** True when no corrections-log string still carries an em/en dash. */
function alt_corrections_dashes_clean() {
    $log = get_option('alt_corrections_log');
    if (!is_array($log)) return true;
    foreach ($log as $e) {
        if (!is_array($e)) continue;
        foreach ($e as $val) {
            if (is_string($val) && preg_match('/[\x{2014}\x{2013}]/u', $val)) return false;
        }
    }
    return true;
}

/**
 * One-time (idempotent) removal of UNDATED news/SEC/press rows that duplicate a
 * DATED event of the same company and headcount. Blank-date rows bypassed the
 * date-gated fuzzy dedup guard, so e.g. an undated "Volkswagen 50,000" sat next
 * to the real dated one (both on the public leaderboard). An undated row whose
 * exact company_key + job_count already exists on a dated row is unambiguously
 * that event re-posted without a date. Never touches edited/pinned rows or
 * structured WARN/ERM. Logged to the public corrections trail.
 */
function alt_dedup_undated_cleanup() {
    global $wpdb;
    $t = alt_db_table();
    $dups = $wpdb->get_results(
        "SELECT a.id, a.post_id FROM $t a
         WHERE a.layoff_date IS NULL
           AND a.source_type IN ('news','8K','press_release')
           AND a.edited = 0 AND a.company_key <> '' AND a.job_count > 0
           AND EXISTS (
             SELECT 1 FROM $t b
             WHERE b.id <> a.id AND b.company_key = a.company_key
               AND b.job_count = a.job_count AND b.layoff_date IS NOT NULL
               AND b.source_type IN ('news','8K','press_release','erm'))
         LIMIT 2000");
    if (!$dups) return;
    $removed = array();
    foreach ($dups as $d) {
        if (!empty($d->post_id)) {
            wp_trash_post((int) $d->post_id);          // cascades to the table row
        } else {
            $wpdb->delete($t, array('id' => (int) $d->id));
        }
        $removed[] = (int) $d->id;
    }
    if ($removed && function_exists('alt_log_correction')) {
        alt_log_correction('removed', $removed,
            'Undated duplicate cleanup: news/SEC rows with no date that duplicate a dated event of the same company and headcount (they had bypassed the date-gated dedup guard).');
    }
    if (function_exists('alt_flush_caches')) alt_flush_caches();
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
    // Upper bound: reject a date implausibly far in the future. Announced or
    // filed closures can legitimately be dated a couple of years out (a
    // scheduled plant closure), so the ceiling is generous (~today + 3y); this
    // only catches a mis-parsed year (a "by 2050" projection, a typo'd 2082)
    // that would otherwise land as a phantom far-future spike in the trend and
    // conversion charts. Rejected -> the row stores undated (dropped from the
    // month series) rather than the whole row being lost.
    if ($d > gmdate('Y-m-d', strtotime('+3 years'))) return null;
    return $d;
}

/**
 * Insert or update one row, keyed by dedup_hash (falling back to post_id).
 * $row is an associative array of column => value.
 */
/**
 * Collapse invisible separators inside a company name.
 *
 * A no-break space, narrow no-break space, zero-width space or BOM renders
 * exactly like a normal space but makes the name UNSEARCHABLE: a reader typing
 * "Carl Zeiss Meditec" never matches the stored "Carl<U+202F>Zeiss Meditec",
 * and the row never groups with that company's other entries. Eurofound rows
 * carry these, and nothing on screen reveals it. Applied at the single write
 * choke point so no collector can reintroduce it.
 *
 * Dashes and other real punctuation are deliberately left alone: an en dash in
 * "Energoremont - Bobov dol JSC" is the source's own spelling, not a defect.
 */
function alt_normalize_company_ws($name) {
    $name = (string) $name;
    $clean = preg_replace('/[\x{00A0}\x{1680}\x{2000}-\x{200B}\x{202F}\x{205F}\x{2060}\x{3000}\x{FEFF}]/u', ' ', $name);
    if ($clean === null) return trim($name);   // invalid UTF-8: leave as-is
    $clean = preg_replace('/\s+/u', ' ', $clean);
    return $clean === null ? trim($name) : trim($clean);
}

function alt_db_upsert(array $row) {
    global $wpdb;
    $table = alt_db_table();

    $data = array(
        'post_id'            => isset($row['post_id']) ? (int) $row['post_id'] : null,
        'dedup_hash'         => substr((string) ($row['dedup_hash'] ?? ''), 0, 32),
        'company'            => substr(alt_normalize_company_ws($row['company'] ?? ''), 0, 255),
        'company_key'        => substr(function_exists('alt_company_key') ? alt_company_key(alt_normalize_company_ws($row['company'] ?? '')) : '', 0, 255),
        'ticker'             => substr((string) ($row['ticker'] ?? ''), 0, 32),
        'job_count'          => max(0, (int) ($row['job_count'] ?? 0)),
        'job_count_max'      => max((int) ($row['job_count'] ?? 0), (int) ($row['job_count_max'] ?? 0)),
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

    // Derive fixed-vocabulary role categories from the row's own stated roles
    // text. When nothing is derivable the key is OMITTED, not blanked: a daily
    // re-import (WARN/ERM rows carry no roles text) must not erase categories
    // the evidence-only backfill extracted from the stored excerpt.
    if (function_exists('alt_normalize_roles')) {
        $derived_roles = alt_db_pack_tags(alt_normalize_roles((string) $data['roles']));
        if ($derived_roles !== '') $data['role_categories'] = $derived_roles;
    }

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
        // An import that carries NO industry (structured WARN rows never do)
        // must not blank a value already on the row — the daily WARN upsert
        // would otherwise erase every /industry-backfill fill overnight.
        // Clearing an industry deliberately goes through /edit (pinned).
        if ($data['industry'] === '') {
            unset($data['industry']);
        }
        // Same rule for the filing/announcement date: a re-import that carries
        // no notice date (a state that lists only the effective date) must not
        // erase a date already on the row. Clearing goes through /edit (pinned).
        if (isset($data['announcement_date']) && $data['announcement_date'] === '') {
            unset($data['announcement_date']);
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
        'job_count_max'      => get_post_meta($post_id, 'job_count_max', true),
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
 * Every request param that NARROWS the result set in alt_db_where().
 *
 * One list, because two lists drift. `alt_export_is_filtered()` kept its own
 * copy and had fallen 6 params behind (2026-07-30): ai_primary, employer_country,
 * review_status, context_missing, industry_missing, roles_missing. A CSV or JSON
 * export narrowed by any of those therefore downloaded as
 * `ai-layoff-tracker-<date>.csv` — the filename that means "the whole dataset" —
 * so a partial extract was labelled complete. On a product whose entire promise
 * is provenance, that is the same class of defect as an unguarded page-level SUM.
 *
 * Deliberately EXCLUDED: `date_basis` and `country_basis` re-interpret the other
 * filters rather than narrowing anything on their own, and `except` is internal
 * slicer plumbing. Pinned against alt_db_where's source by
 * railway/tests/test_filter_param_contract.py, which fails if a new filter is
 * read here without being listed.
 */
function alt_filter_param_names() {
    return array(
        'years', 'quarters', 'months', 'from', 'to',
        'industry', 'country', 'employer_country', 'state',
        'sources', 'reasons', 'roles',
        'q', 'company', 'keyword', 'min_jobs', 'stage',
        'ai', 'ai_broad', 'ai_primary', 'review_status',
        'context_missing', 'industry_missing', 'roles_missing',
        'company_key', 'sourced', 'exclude_supersets',
    );
}

/**
 * Build a parameterized WHERE clause from request filters. `$except` drops one
 * dimension (for slicer charts). Returns array($sql, $params).
 *
 * NOTE: the public routes register no `args` schema, so an unrecognised param
 * name is accepted and silently ignored — `?states=NV` returns the whole corpus
 * rather than Nevada. The accepted names are exact and documented in
 * docs/ARCHITECTURE.md "Filter model"; plurals are deliberately not aliased.
 *
 * `$alias` is the name the CALLER gave the layoffs table in its own FROM clause.
 * Every filter above `sourced` uses bare column names, which bind correctly
 * whether or not the table is aliased — but `sourced` correlates a subquery back
 * to the outer row, and a correlated reference has to name something that is
 * actually in scope. MySQL HIDES the real table name once an alias is given, so
 * `wp_alt_layoffs.event_id` is an unknown-column error inside
 * /conversion's `FROM $table a`. Callers that alias must say so; the one that
 * does is alt_api_conversion_compute().
 */
function alt_db_where(WP_REST_Request $r, $except = '', $alias = '') {
    global $wpdb;
    $where = array("1=1");
    $params = array();
    // What a correlated subquery must call the outer row.
    $self = ($alias !== '') ? $alias : alt_db_table();
    // Date basis for period filtering:
    //   (default)      -> layoff_date: when the layoff takes EFFECT (our
    //                     conservative floor; what the public UI shows).
    //   announcement   -> announcement_date ONLY (strict, source-evidenced;
    //                     used by benchmark/reconciliation callers that must
    //                     compare against genuine announcement-stage dates and
    //                     deliberately exclude rows without one).
    //   notice         -> COALESCE(announcement_date, layoff_date): when it was
    //                     FILED/announced where known, else effective. This is
    //                     the apples-to-apples basis for comparing against WARN
    //                     aggregators that count by filing date; it never drops
    //                     a row for lacking a filing date.
    $db_basis = (string) $r->get_param('date_basis');
    if ($db_basis === 'announcement') {
        $date_col = 'announcement_date';
    } elseif ($db_basis === 'notice') {
        $date_col = 'COALESCE(announcement_date, layoff_date)';
    } else {
        $date_col = 'layoff_date';
    }

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
    // country_basis=employer mirrors date_basis: the country filter then
    // matches the evidenced employer domicile where one is recorded, falling
    // back to the stated job location only for rows with no recorded domicile.
    // This is the Survey-comparable employer basis (a US-HQ company's
    // multi-country cut counts; a foreign-HQ company's US cut does not). The
    // plain country param stays job-location, and employer_country stays
    // domicile-only (the strict comparator's gate) — neither changes meaning.
    if ($except !== 'country') {
        $countries = array_filter(array_map('trim', explode(',', (string) $r->get_param('country'))), 'strlen');
        if ($countries) {
            $ph = implode(',', array_fill(0, count($countries), '%s'));
            if ($r->get_param('country_basis') === 'employer') {
                $where[] = "(employer_country IN ($ph) OR (employer_country = '' AND country IN ($ph)))";
                foreach ($countries as $v) { $params[] = $v; }
            } elseif ($r->get_param('country_basis') === 'any') {
                // Inclusive/discovery basis (the front-end default): a country
                // matches if the jobs are located there OR the employer is
                // domiciled there. This is what surfaces a US-HQ company's
                // global cut (labeled "Multiple countries") under a US filter,
                // instead of hiding it. Each row keeps its true country label,
                // so a global figure is never silently recounted as US-only.
                $where[] = "(country IN ($ph) OR employer_country IN ($ph))";
                foreach ($countries as $v) { $params[] = $v; }
            } else {
                $where[] = "country IN ($ph)";
            }
            foreach ($countries as $v) { $params[] = $v; }
        }
    }
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
    // `roles` filters by fixed role-category slug (packed as ',slug,' in
    // role_categories, same shape as reason_tags). Multi-select is OR'd: a row
    // that named ANY of the chosen teams matches. 'unknown' is queue
    // bookkeeping and is never an accepted filter value.
    if ($except !== 'roles') {
        $roles = array_filter(array_map('sanitize_key', explode(',', (string) $r->get_param('roles'))),
                              function ($s) { return $s !== '' && $s !== 'unknown'; });
        if ($roles) {
            $ors = array();
            foreach ($roles as $slug) { $ors[] = "role_categories LIKE %s"; $params[] = '%,' . $slug . ',%'; }
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
    // ai_broad matches the ai_broad_jobs aggregate definition exactly: the
    // explicit employer-quote tag OR the loose Survey/sector trackers-style
    // ai_linked tier. It filters ROWS, unlike the always-present aggregate
    // columns, so benchmark queries can scope totals to the broad AI basis.
    if ($r->get_param('ai_broad') === '1' || $r->get_param('ai_broad') === 'true') { $where[] = "(ai_explicit = 1 OR ai_causation = 'ai_linked')"; }
    if (($status = sanitize_key((string) $r->get_param('review_status'))) !== '') { $where[] = "review_status = %s"; $params[] = $status; }
    if ($r->get_param('context_missing') === '1' || $r->get_param('context_missing') === 'true') {
        $where[] = "(employer_country = '' OR announcement_date IS NULL)";
    }
    // Role-extraction queue: rows never checked for role categories that have
    // SOME stored text to read (a row with neither roles nor excerpt can never
    // be evidence-enriched, so it never enters the bounded queue). Checked
    // rows carry at least the ',unknown,' marker and drop out.
    // EXCLUDE structured sources (WARN legal forms, Eurofound ERM templates):
    // they state company/count/date/location but NEVER which teams were cut, so
    // every one resolves to 'unknown' — leaving them in bloated the queue with
    // ~45K futile rows and starved the news rows where roles can actually be
    // found. Roles come only from free-text sources (news, SEC 8-K, press).
    if ($r->get_param('roles_missing') === '1' || $r->get_param('roles_missing') === 'true') {
        $where[] = "role_categories = '' AND source_type NOT IN ('warn','erm')"
                 . " AND (COALESCE(roles,'') <> '' OR COALESCE(excerpt,'') <> '')";
    }
    // Blank-industry candidates for the bounded classification backfill (and
    // anyone auditing the disclosed metadata backlog).
    if ($r->get_param('industry_missing') === '1' || $r->get_param('industry_missing') === 'true') {
        $where[] = "industry = ''";
    }
    // stage=announced -> announcement-stage only; stage=verified -> filed/reported only
    $stage = (string) $r->get_param('stage');
    if ($stage === 'announced') { $where[] = "announced = 1"; }
    elseif ($stage === 'verified') { $where[] = "announced = 0"; }
    if (($v = $r->get_param('company'))) { $where[] = "company LIKE %s"; $params[] = '%' . $wpdb->esc_like($v) . '%'; }
    // `company_key` is the EXACT normalized employer identity; `company` above is
    // a LIKE substring match. A per-employer PAGE must use this one: `company`
    // would publish Metabolix's and Metaswitch's cuts on the page titled "Meta
    // layoffs". Comma-joined like the other multi-selects.
    if ($except !== 'company_key') {
        $keys = array_filter(array_map('trim', explode(',', (string) $r->get_param('company_key'))), 'strlen');
        if ($keys) {
            $ph = implode(',', array_fill(0, count($keys), '%s'));
            $where[] = "company_key IN ($ph)";
            foreach ($keys as $v) { $params[] = $v; }
        }
    }
    // `sourced=1` is the evidence gate the company pages publish under: the row
    // is the CANONICAL row of a merged event AND that event still retains at
    // least one reachable source URL. Anything else is either a duplicate view
    // of an event already shown, or an event we can no longer point a reader at
    // — neither belongs on a page whose whole claim is "every row has a source".
    if ($r->get_param('sourced') === '1' || $r->get_param('sourced') === 'true') {
        $events_t = alt_events_table();
        $reports_t = alt_source_reports_table();
        $where[] = "event_id > 0"
            . " AND EXISTS (SELECT 1 FROM $events_t alt_e"
            . " WHERE alt_e.id = $self.event_id AND alt_e.canonical_layoff_id = $self.id)"
            . " AND EXISTS (SELECT 1 FROM $reports_t alt_r"
            . " WHERE alt_r.event_id = $self.event_id AND alt_r.source_url <> '')";
    }
    // `exclude_supersets=1` drops rows already folded into a more complete row
    // for the same event by /reconcile-supersets (a company-wide news total and
    // its per-site WARN rows are ONE event). /aggregate and the report pages
    // have always appended `AND superset_of = 0` by hand; naming it as a filter
    // lets a caller ask for count-once semantics instead of re-deriving them,
    // which is how the company page used to double-count a rollup plus members.
    if ($r->get_param('exclude_supersets') === '1' || $r->get_param('exclude_supersets') === 'true') {
        $where[] = "superset_of = 0";
    }
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
        'job_count_max'      => (int) ($row->job_count_max ?: $row->job_count),
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
        // A WARN row always has an official state LIST page (derived from its
        // state) in addition to whatever source_url holds. When source_url is
        // an exact per-notice page, the front-end shows both; when it already
        // IS the list, the two match and only one link renders.
        'source_list_url'    => ($row->source_type === 'warn' && function_exists('alt_state_warn_list_url'))
                                ? alt_state_warn_list_url($row->state) : '',
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
        // Fixed-vocabulary role categories. 'unknown' is queue bookkeeping
        // ("evidence checked, roles not stated"), not a public category.
        'role_categories'    => array_values(array_diff(alt_db_unpack_tags($row->role_categories ?? ''), array('unknown'))),
        'roles_evidence'     => ($row->roles_evidence ?? '') !== '' ? $row->roles_evidence : null,
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
    // Announced-to-verified conversion series: per announcement month, how
    // many announced jobs later show verified same-company records.
    register_rest_route('layoffs/v1', '/conversion', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_conversion',
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
    // Public: macro-context unemployment-claims backdrop (national + state).
    // Served from a cached option; refreshed by the keyed ingest below. This is
    // LABELED CONTEXT (BLS/DOL claims), never summed into layoff counts.
    register_rest_route('layoffs/v1', '/claims', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_claims_get',
        'permission_callback' => '__return_true',
    ));
    register_rest_route('layoffs/v1', '/claims-ingest', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_claims_ingest',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Private working memory for the daily competitor-weaning loop (tracker_diff):
    // which companies were ever resolved only by chasing a reference list, the
    // independent-recall history, and which outlets keep closing gaps. Keyed POST
    // only — this state stays in the DB, never in the repo or Actions logs.
    register_rest_route('layoffs/v1', '/tracker-meta', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_tracker_meta',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected: superset dedup (default DRY-RUN; apply=1 to write). Marks
    // a company-wide news total or its site-level WARN rows as a subset of the
    // same event's most-complete row so one event is counted once.
    register_rest_route('layoffs/v1', '/reconcile-supersets', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_reconcile_supersets',
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
    // Key-protected, evidence-bounded role-category extraction. Like
    // /enrich-context it only fills BLANK fields and never pins a row or
    // suppresses a hash; unlike /edit it cannot touch counts, dates, sources
    // or AI labels. 'unknown' marks a checked row whose stored evidence does
    // not state the affected roles, so the bounded daily queue drains.
    register_rest_route('layoffs/v1', '/enrich-roles', array(
        'methods' => 'POST', 'callback' => 'alt_api_enrich_roles',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Key-protected, blank-only industry fill restricted to the closed
    // canonical vocabulary. It never overwrites a non-blank industry, never
    // pins rows or touches dedup hashes, and rejects any label outside
    // alt_industry_vocabulary() — an automated classifier must not mint labels.
    register_rest_route('layoffs/v1', '/industry-backfill', array(
        'methods' => 'POST', 'callback' => 'alt_api_industry_backfill',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Source archiving (Internet Archive / Wayback). Two key-protected endpoints
    // drive the resumable backfill: /archive-candidates hands out the next batch
    // of DISTINCT un-archived source URLs (any row type, including brand-new
    // rows), /archive-record stores the resulting permanent snapshot per URL.
    // /archive-coverage is a public read-only coverage tally for the health page.
    register_rest_route('layoffs/v1', '/archive-candidates', array(
        'methods' => 'GET', 'callback' => 'alt_api_archive_candidates',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
        'args' => array(
            'limit' => array('type' => 'integer', 'default' => 200),
            'retry_hours' => array('type' => 'integer', 'default' => 72),
        ),
    ));
    register_rest_route('layoffs/v1', '/archive-record', array(
        'methods' => 'POST', 'callback' => 'alt_api_archive_record',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    register_rest_route('layoffs/v1', '/archive-coverage', array(
        'methods' => 'GET', 'callback' => 'alt_api_archive_coverage', 'permission_callback' => '__return_true',
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
    // A readable appendix built only from the immutable stored report record;
    // it never calls the live aggregate queries or exposes a new raw-data feed.
    register_rest_route('layoffs/v1', '/reports/quarterly/(?P<report_id>\\d{4}-Q[1-4])/appendix', array(
        'methods' => 'GET', 'callback' => 'alt_api_quarterly_report_appendix_get', 'permission_callback' => '__return_true',
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
    // Public-tip intake queue. Tips are LEADS, never sources: a member of the
    // public points us at a URL, and the process_tips worker independently
    // verifies it (fetch + double-confirm + allowlist gate) before anything is
    // published. GET(keyed) lists tips by status for the worker; POST(keyed)
    // updates a tip's status. Public submission is NOT a REST route: it flows
    // through the captcha-protected /contact form, so this endpoint adds no new
    // unauthenticated write surface.
    // Press-brief subscribers. Opt-in only (a captcha'd form on the press page).
    // GET(keyed) lists them for the monthly-brief composer; POST(keyed) is unused
    // externally. Public signup flows through admin-post, not a REST write.
    register_rest_route('layoffs/v1', '/press-subscribers', array(
        'methods' => 'GET', 'callback' => 'alt_api_press_subs_get',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    register_rest_route('layoffs/v1', '/tips', array(
        array('methods' => 'GET', 'callback' => 'alt_api_tips_get',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
        array('methods' => 'POST', 'callback' => 'alt_api_tips_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
    // URL-level "already ingested?" pre-check for collectors. The ingest
    // pipeline overlaps its pull windows on purpose (a 36h GDELT window on a
    // twice-daily cadence), so the SAME article URL reaches the extractor ~3
    // times; the identical re-read adds zero evidence (the source-report
    // INSERT IGNOREs the duplicate hash) but costs an LLM call every time.
    // POST {urls:[...]} -> {seen:[...]} lets a collector skip exactly those,
    // BEFORE extraction. A NEW outlet covering the same event has a new URL,
    // is never in `seen`, and still extracts fully into a corroborating
    // source report - this endpoint can only skip re-reads, never evidence.
    register_rest_route('layoffs/v1', '/seen-urls', array(
        'methods' => 'POST', 'callback' => 'alt_api_seen_urls',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
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
    register_rest_route('layoffs/v1', '/benchmarks/survey', array(
        array('methods' => 'GET', 'callback' => 'alt_api_survey_benchmarks', 'permission_callback' => '__return_true'),
        array('methods' => 'POST', 'callback' => 'alt_api_survey_benchmark_post',
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
    // Distinct captured company names — powers the self-growing watchlist (every
    // company we've ever captured becomes one we keep monitoring for new rounds).
    // Public: company names are facts; no counts/dates/sources exposed here.
    register_rest_route('layoffs/v1', '/companies', array(
        'methods' => 'GET', 'callback' => 'alt_api_companies', 'permission_callback' => '__return_true',
    ));
    // Separate, source-evidenced WARN timing/adjudication register. It never
    // affects layoff/AI totals and uses “violation” only after adjudication.
    register_rest_route('layoffs/v1', '/warn-transparency', array(
        array('methods' => 'GET', 'callback' => 'alt_api_warn_transparency_get', 'permission_callback' => '__return_true'),
        array('methods' => 'POST', 'callback' => 'alt_api_warn_transparency_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
    // Reviewed company-directory registry writer. It admits identity mappings
    // only; page publication is still decided at render time from live
    // source-linked canonical events, and the server refuses an 'approved'
    // mapping whose evidence support is below the indexability threshold.
    register_rest_route('layoffs/v1', '/company-directory', array(
        array('methods' => 'GET', 'callback' => 'alt_api_company_directory_get', 'permission_callback' => '__return_true'),
        array('methods' => 'POST', 'callback' => 'alt_api_company_directory_post',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false'),
    ));
    // Automated admission under a published deterministic policy: the server
    // selects unmapped company keys whose evidence support is comfortably
    // above the manual threshold and whose display name passes identity
    // sanity checks, then runs them through the SAME admission validator as
    // the manual writer. No page can appear below the evidence threshold.
    register_rest_route('layoffs/v1', '/company-directory/autopilot', array(
        'methods' => 'POST', 'callback' => 'alt_api_company_directory_autopilot',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
}

/**
 * Public, read-only registry listing: reviewed mappings and their evidence
 * support.
 *
 * PAGED since the indexer covers every employer rather than a curated few.
 * Unbounded, this returned one row per company page in a single response, which
 * was a reasonable shape at 29 companies and a multi-megabyte reply at the real
 * employer count. `status` narrows to one side of the indexability floor.
 */
// $r is untyped on purpose: a typed `WP_REST_Request $r = null` is an implicit
// nullable parameter, which PHP 8.4 deprecates and would log on every request.
function alt_api_company_directory_get($r = null) {
    global $wpdb;
    $directory = alt_company_directory_table();
    $per_page = 200; $page = 1; $status = '';
    if ($r) {
        $per_page = min(1000, max(1, (int) ($r->get_param('per_page') ?: 200)));
        $page = max(1, (int) ($r->get_param('page') ?: 1));
        $status = sanitize_key((string) $r->get_param('status'));
    }
    $statuses = in_array($status, array('approved', 'noindex'), true)
        ? array($status) : array('approved', 'noindex');
    $ph = implode(',', array_fill(0, count($statuses), '%s'));
    $total = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COUNT(*) FROM $directory WHERE review_status IN ($ph)", $statuses));
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT slug, display_name, review_status, reviewed_at FROM $directory
         WHERE review_status IN ($ph) ORDER BY display_name ASC, id ASC LIMIT %d OFFSET %d",
        array_merge($statuses, array($per_page, ($page - 1) * $per_page))), ARRAY_A) ?: array();
    $out = array();
    foreach ($rows as $row) {
        $out[] = array(
            'slug' => $row['slug'],
            'display_name' => $row['display_name'],
            'review_status' => $row['review_status'],
            'reviewed_at' => $row['reviewed_at'],
            'url' => alt_company_directory_url($row['slug']),
        );
    }
    $floor = function_exists('alt_company_directory_indexable_floor')
        ? alt_company_directory_indexable_floor() : 2;
    return rest_ensure_response(array(
        'methodology' => 'Company pages exist only for admitted identity mappings, added by editor review or by a '
            . 'published automated evidence-threshold policy (autopilot-v2), and render only source-linked canonical '
            . 'events. A listed mapping is an identity record, not a completeness claim for that employer. An employer '
            . "with at least $floor such events is offered to search engines; one below that keeps its page and is "
            . 'marked noindex, because that page repeats what the individual entry already says.',
        'coverage' => function_exists('alt_company_directory_coverage') ? alt_company_directory_coverage() : null,
        'total' => $total,
        'page' => $page,
        'per_page' => $per_page,
        'mappings' => $out,
    ));
}

/**
 * Keyed registry writer. Each mapping is a reviewed identity decision:
 * company_key -> public slug/display name. The server independently counts
 * source-linked canonical events for the key and refuses 'approved' below
 * the two-event indexability threshold (and 'noindex' below one), so a
 * mapping can never will a page into existence without retained evidence.
 */
function alt_api_company_directory_post(WP_REST_Request $r) {
    $reason = trim((string) $r->get_param('reason'));
    if ($reason === '') {
        return new WP_Error('alt_bad_request', 'reason is required.', array('status' => 400));
    }
    $mappings = $r->get_param('mappings');
    if (!is_array($mappings) || !$mappings) {
        return new WP_Error('alt_bad_request', 'mappings must be a non-empty array.', array('status' => 400));
    }
    $out = alt_company_directory_admit_mappings($mappings);
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

/** Shared admission validator used by both the manual writer and autopilot. */
function alt_company_directory_admit_mappings(array $mappings) {
    global $wpdb;
    $directory = alt_company_directory_table();
    $layoffs = alt_db_table(); $events = alt_events_table(); $reports = alt_source_reports_table();
    $out = array('admitted' => array(), 'rejected' => array());
    foreach ($mappings as $m) {
        $key = trim((string) ($m['company_key'] ?? ''));
        $slug = sanitize_title((string) ($m['slug'] ?? ''));
        $name = sanitize_text_field((string) ($m['display_name'] ?? ''));
        $status = sanitize_key((string) ($m['review_status'] ?? ''));
        if ($key === '' || $slug === '' || $name === '' || !in_array($status, array('approved', 'noindex', 'pending'), true)) {
            $out['rejected'][] = array('mapping' => $m, 'why' => 'company_key, slug, display_name and a valid review_status are required');
            continue;
        }
        // Server-side evidence count: source-linked canonical events only —
        // the SAME helper the page, the sitemap and the coverage report use, so
        // the count that admits a page and the count that indexes it cannot
        // drift apart. (function_exists is the FTP-deploy race guard:
        // company-directory.php can be mid-upload while this file is already new.)
        $floor = function_exists('alt_company_directory_indexable_floor')
            ? alt_company_directory_indexable_floor() : 2;
        $supported = function_exists('alt_company_directory_supported_count')
            ? alt_company_directory_supported_count($key)
            : (int) $wpdb->get_var($wpdb->prepare(
                "SELECT COUNT(*) FROM $layoffs l INNER JOIN $events e ON e.id = l.event_id AND e.canonical_layoff_id = l.id
                 WHERE l.company_key = %s AND l.event_id > 0 AND l.superset_of = 0
                 AND EXISTS (SELECT 1 FROM $reports r2 WHERE r2.event_id = l.event_id AND r2.source_url <> '')", $key));
        if ($status === 'approved' && $supported < $floor) {
            $out['rejected'][] = array('company_key' => $key, 'why' => "approved requires >=$floor source-linked canonical events; found $supported");
            continue;
        }
        if ($status === 'noindex' && $supported < 1) {
            $out['rejected'][] = array('company_key' => $key, 'why' => "noindex requires >=1 source-linked canonical event; found $supported");
            continue;
        }
        $slug_owner = $wpdb->get_var($wpdb->prepare(
            "SELECT company_key FROM $directory WHERE slug = %s", $slug));
        if ($slug_owner !== null && $slug_owner !== $key) {
            $out['rejected'][] = array('company_key' => $key, 'why' => "slug '$slug' already belongs to another mapping");
            continue;
        }
        $now = current_time('mysql', true);
        $existing = $wpdb->get_var($wpdb->prepare("SELECT id FROM $directory WHERE company_key = %s", $key));
        $data = array(
            'company_key' => $key, 'slug' => $slug, 'display_name' => $name,
            'aliases' => isset($m['aliases']) ? wp_json_encode(array_map('sanitize_text_field', (array) $m['aliases'])) : null,
            'review_status' => $status,
            'reviewed_at' => in_array($status, array('approved', 'noindex'), true) ? $now : null,
            'updated_at' => $now,
        );
        if ($existing) {
            $wpdb->update($directory, $data, array('id' => (int) $existing));
        } else {
            $data['created_at'] = $now;
            $wpdb->insert($directory, $data);
        }
        if ($wpdb->last_error) {
            $out['rejected'][] = array('company_key' => $key, 'why' => 'database error: ' . $wpdb->last_error);
            continue;
        }
        $out['admitted'][] = array(
            'company_key' => $key, 'slug' => $slug, 'review_status' => $status,
            'source_linked_canonical_events' => $supported,
            'url' => alt_company_directory_url($slug),
        );
    }
    return $out;
}

/** Identity sanity gate for automated admission. Returns '' when the name is usable. */
function alt_company_directory_name_rejection($name) {
    $name = trim((string) $name);
    $length = function_exists('mb_strlen') ? mb_strlen($name) : strlen($name);
    if ($length < 2 || $length > 64) return 'display name length outside 2-64 characters';
    if (!preg_match('/\p{L}/u', $name)) return 'display name contains no letters';
    if (count(preg_split('/\s+/', $name)) > 6) return 'display name reads like a sentence, not an identity';
    $lower = function_exists('mb_strtolower') ? mb_strtolower($name) : strtolower($name);
    $generic = array('multiple companies', 'multiple', 'various', 'various companies', 'various employers',
        'unknown', 'undisclosed', 'not disclosed', 'n/a', 'company', 'companies', 'employer', 'employers',
        'several', 'several companies', 'several firms', 'firm', 'firms', 'tbd', 'not specified',
        'unnamed', 'unnamed company', 'confidential', 'staffing agency', 'tech companies',
        'a major tech company', 'major tech company');
    if (in_array($lower, $generic, true)) return 'generic, non-identifying company name';
    // Extraction placeholders arrive in many spellings ('Unknown Co',
    // 'Unknown Company', 'Various Employers Inc') that all normalize to the
    // same company_key — compare in key space too so variants cannot slip
    // around the exact-match list.
    if (function_exists('alt_company_key')) {
        $generic_keys = array_filter(array_map('alt_company_key', $generic));
        $name_key = alt_company_key($name);
        if ($name_key === '' || in_array($name_key, $generic_keys, true)) {
            return 'generic, non-identifying company name (normalized match)';
        }
    }
    return '';
}

/**
 * Park a key the autopilot cannot safely admit as a 'pending' directory row.
 * Pending rows never render or list publicly, but they satisfy the candidate
 * query's NOT EXISTS — so a perpetually unadmittable key stops occupying a
 * candidate slot on every weekly run and waits for manual review instead.
 */
function alt_company_directory_park_pending($key, $name) {
    global $wpdb;
    $directory = alt_company_directory_table();
    if ($wpdb->get_var($wpdb->prepare("SELECT id FROM $directory WHERE company_key = %s", $key))) return;
    $name = sanitize_text_field((string) $name);
    $display = $name !== '' ? (function_exists('mb_substr') ? mb_substr($name, 0, 190) : substr($name, 0, 190)) : $key;
    $slug = sanitize_title($display);
    if ($slug === '' || $wpdb->get_var($wpdb->prepare("SELECT id FROM $directory WHERE slug = %s", $slug))) {
        $slug = 'pending-' . substr(md5($key), 0, 12);
        if ($wpdb->get_var($wpdb->prepare("SELECT id FROM $directory WHERE slug = %s", $slug))) return;
    }
    $now = current_time('mysql', true);
    $wpdb->insert($directory, array(
        'company_key' => $key, 'slug' => $slug, 'display_name' => $display,
        'review_status' => 'pending', 'reviewed_at' => null,
        'created_at' => $now, 'updated_at' => $now,
    ));
}

/**
 * The employer indexer: one page per employer with retained evidence.
 *
 * WHAT CHANGED AND WHY (2026-07-31). This ran weekly, admitted at most 25
 * companies a run, and only considered keys with >=3 source-linked events. The
 * INDEXABILITY gate was never the problem — the audit found it sound — the
 * THROUGHPUT was: 29 employers had a page against ~41k distinct employer names
 * in the table, and 17 of the 24 largest employers by event count had none.
 * At 25 a week the backlog outran the indexer permanently.
 *
 * So the floor drops to ONE source-linked canonical event, which is the floor
 * for a page EXISTING, and the review_status now records which side of the
 * indexability floor the employer falls on:
 *   >= alt_company_directory_indexable_floor()  -> 'approved' (indexable, sitemapped)
 *   exactly 1                                   -> 'noindex'  (page renders, not indexed)
 *   0                                           -> no row, no page, 404
 * Zero is a real floor and not a formality: with no retained source URL there
 * is nothing on the page to link to, and a page whose only claim is "every row
 * has a source" cannot be built out of rows that have none.
 *
 * PENDING ROWS ARE RECONSIDERED, and this is not a detail. The v1 rule parked
 * any key whose qualifying rows disagreed on the company name, which selects
 * almost exactly the largest employers: Boeing files as "Boeing", "Boeing Co",
 * "Boeing Company", "The Boeing Company" and two misspellings, so 324 events
 * bought it a `pending` row and no page. Dropping that rule was not enough,
 * because a pending row still satisfied "already mapped" and the indexer never
 * looked at it again — the fix for the rule would have silently excluded every
 * employer the old rule had already caught. Only 'approved'/'noindex' counts as
 * mapped now. This cannot promote junk: the identity sanity gate still runs, so
 * a key parked for a generic or unusable name fails again and stays pending.
 *
 * RESUMABLE, because one pass cannot finish inside a shared-host request. Each
 * call takes the next `limit` unmapped keys in company_key order and returns
 * `next_cursor`; the workflow loops until `complete` comes back true. Ordering
 * by key (not by event count) is what makes the cursor stable: admitting a row
 * removes it from the candidate set, so an ORDER BY on a count that changes
 * under ingest would skip employers silently.
 *
 * The Actions run log plus this response are the audit trail; the policy string
 * is returned every run.
 */
function alt_api_company_directory_autopilot(WP_REST_Request $r) {
    global $wpdb;
    $min_events = max(1, min(10, (int) ($r->get_param('min_events') ?: 1)));
    $limit = max(1, min(500, (int) ($r->get_param('limit') ?: 200)));
    $after_key = (string) $r->get_param('after_key');
    // Idempotency: a workflow retry after an ambiguous gateway error replays
    // the stored response instead of admitting a second batch, so one run can
    // never exceed its documented cap or lose its audit record.
    $token = sanitize_key((string) $r->get_param('run_token'));
    if ($token !== '') {
        $prior = get_option('alt_directory_autopilot_last');
        if (is_array($prior) && ($prior['token'] ?? '') === $token && isset($prior['response'])) {
            return rest_ensure_response($prior['response']);
        }
    }
    $directory = alt_company_directory_table();
    $layoffs = alt_db_table(); $events = alt_events_table(); $reports = alt_source_reports_table();
    $candidates = $wpdb->get_results($wpdb->prepare(
        "SELECT l.company_key, COUNT(*) supported
         FROM $layoffs l INNER JOIN $events e ON e.id = l.event_id AND e.canonical_layoff_id = l.id
         WHERE l.event_id > 0 AND l.company_key <> '' AND l.superset_of = 0
           AND l.company_key > %s
           AND EXISTS (SELECT 1 FROM $reports r2 WHERE r2.event_id = l.event_id AND r2.source_url <> '')
           AND NOT EXISTS (SELECT 1 FROM $directory d WHERE d.company_key = l.company_key
                           AND d.review_status IN ('approved','noindex'))
         GROUP BY l.company_key HAVING COUNT(*) >= %d
         ORDER BY l.company_key ASC LIMIT %d", $after_key, $min_events, $limit), ARRAY_A) ?: array();
    $mappings = array(); $skipped = array(); $names_by_key = array();
    $supported_by_key = array(); $last_key = $after_key;
    $floor = function_exists('alt_company_directory_indexable_floor')
        ? alt_company_directory_indexable_floor() : 2;
    foreach ($candidates as $candidate) {
        $key = $candidate['company_key'];
        $last_key = $key;
        $supported_by_key[$key] = (int) $candidate['supported'];
        // Name candidates come ONLY from the qualifying evidence rows — the
        // same canonical, source-linked set the threshold counted — never
        // from unrelated rows that happen to share the normalized key.
        //
        // MOST FREQUENTLY REPORTED name wins. The docstring has always said so;
        // the code took whatever row a DISTINCT happened to return first, which
        // is not the same thing and is not stable. Ties break on the SHORTER
        // name, which is the plain brand ("Boeing" over "Boeing Company").
        $names = $wpdb->get_col($wpdb->prepare(
            "SELECT l.company FROM $layoffs l
             INNER JOIN $events e ON e.id = l.event_id AND e.canonical_layoff_id = l.id
             WHERE l.company_key = %s AND l.event_id > 0 AND l.company <> '' AND l.superset_of = 0
             AND EXISTS (SELECT 1 FROM $reports r2 WHERE r2.event_id = l.event_id AND r2.source_url <> '')
             GROUP BY l.company ORDER BY COUNT(*) DESC, CHAR_LENGTH(l.company) ASC, l.company ASC", $key)) ?: array();
        $name = sanitize_text_field((string) ($names[0] ?? ''));
        $names_by_key[$key] = $name;
        // Spelling variants across an employer's own filings ("Boeing" /
        // "Boeing Company" / "The Boeing Co") are NORMAL, not an identity
        // problem — they are exactly what company_key exists to collapse, and
        // parking on any disagreement denied a page to precisely the large,
        // heavily-reported employers the pages are most useful for. The page
        // prints each row's own reported name, so a reader sees the variants.
        // What still parks is a name that fails the sanity gate below.
        $why = alt_company_directory_name_rejection($name);
        if ($why !== '') {
            $skipped[] = array('company_key' => $key, 'why' => $why . '; parked pending manual identity review');
            alt_company_directory_park_pending($key, $name);
            continue;
        }
        $slug = sanitize_title($name);
        if ($slug === '') {
            $skipped[] = array('company_key' => $key, 'why' => 'name produces an empty slug; parked pending manual identity review');
            alt_company_directory_park_pending($key, $name);
            continue;
        }
        // The thin-content decision, made here and recorded in the row: an
        // employer at or above the floor is offered to the index, one below it
        // still gets a page and is marked noindex. Neither is a judgement about
        // the employer; it is a judgement about whether THIS URL adds anything
        // the entry permalink does not already say.
        $indexable = $supported_by_key[$key] >= $floor;
        $mappings[] = array('company_key' => $key, 'slug' => $slug, 'display_name' => $name,
                            'review_status' => $indexable ? 'approved' : 'noindex');
    }
    $out = $mappings ? alt_company_directory_admit_mappings($mappings) : array('admitted' => array(), 'rejected' => array());
    // Validator-rejected keys (e.g. slug owned by another mapping) are parked
    // too, so they stop consuming candidate slots on every future run.
    foreach ($out['rejected'] as $rejected) {
        if (!empty($rejected['company_key'])) {
            alt_company_directory_park_pending($rejected['company_key'], $names_by_key[$rejected['company_key']] ?? '');
        }
    }
    $out['skipped_identity_checks'] = $skipped;
    $out['candidates_considered'] = count($candidates);
    // Resumption state. `complete` is true only when this run saw fewer
    // candidates than it asked for, which is the only reliable end-of-set
    // signal: admitted and parked keys both leave the candidate set, but a key
    // that can do neither would otherwise be re-read forever, so the caller
    // advances past it with the cursor rather than looping on it.
    $out['next_cursor'] = $last_key;
    $out['complete'] = count($candidates) < $limit;
    $out['index_floor_events'] = $floor;
    $out['policy'] = "autopilot-v2: unmapped company keys with >=$min_events source-linked canonical events "
        . '(canonical row of a merged event, retaining a source URL, superset members excluded), named by the '
        . "most frequently reported company name for the key, passing identity sanity checks, with a unique slug. "
        . "Admitted 'approved' (indexable, sitemapped) at >=$floor such events and 'noindex' (page renders, "
        . 'stays out of the index) below that; validated by the same server-side admission rules as manual '
        . 'review. Unadmittable keys are parked as pending for manual review.';
    // Flush BEFORE reading coverage: the coverage numbers are cached against
    // alt_data_ver, so computing them first would report the state this run
    // started from and make a working indexer look stalled.
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    if (function_exists('alt_company_directory_coverage')) {
        $out['coverage'] = alt_company_directory_coverage();
    }
    if ($token !== '') {
        update_option('alt_directory_autopilot_last', array('token' => $token, 'response' => $out), false);
    }
    return rest_ensure_response($out);
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
    // Callers may label the batch (e.g. the curated employer-domicile
    // registry) so the public corrections trail names the actual basis
    // instead of implying a source-page re-read.
    $reason = sanitize_text_field((string) $r->get_param('reason'));
    if (!empty($out['updated'])) alt_log_correction('enriched', $out['updated'], $reason !== '' ? $reason : 'Automated source-evidence context enrichment');
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

/**
 * Fill only blank role_categories from already-stored source evidence.
 * Items: {id, categories: [vocab slugs] or ['unknown'], evidence: "exact
 * stored-text quote"}. Real categories require a non-trivial evidence quote;
 * 'unknown' records "checked, source doesn't say" with no quote. Existing
 * categories (extractor-stated or an earlier pass) are never overwritten.
 */
function alt_api_enrich_roles(WP_REST_Request $r) {
    global $wpdb;
    $items = $r->get_param('items');
    if (!is_array($items)) return new WP_Error('alt_bad_request', 'items must be an array.', array('status' => 400));
    $table = alt_db_table();
    $vocab = function_exists('alt_role_categories') ? array_keys(alt_role_categories()) : array();
    $out = array('updated' => array(), 'marked_unknown' => array(), 'not_found' => array(), 'rejected' => array());
    foreach ($items as $item) {
        $id = (int) ($item['id'] ?? 0);
        $row = $id ? $wpdb->get_row($wpdb->prepare("SELECT id, post_id, role_categories FROM $table WHERE id = %d", $id)) : null;
        if (!$row) { $out['not_found'][] = $id; continue; }
        if ((string) $row->role_categories !== '') { $out['rejected'][] = $id; continue; }
        $cats = array_values(array_unique(array_intersect(
            array_map('sanitize_key', (array) ($item['categories'] ?? array())),
            array_merge($vocab, array('unknown'))
        )));
        if (!$cats) { $out['rejected'][] = $id; continue; }
        $real = array_values(array_diff($cats, array('unknown')));
        $evidence = trim((string) ($item['evidence'] ?? ''));
        // The same minimum-quote invariant as every other evidence field: no
        // category claim is stored without its supporting stored-text phrase.
        if ($real && strlen($evidence) < 12) { $out['rejected'][] = $id; continue; }
        $data = array('role_categories' => alt_db_pack_tags($real ?: array('unknown')));
        if ($real) $data['roles_evidence'] = sanitize_textarea_field($evidence);
        if ($wpdb->update($table, $data, array('id' => $id)) === false) {
            return new WP_Error('alt_db_error', 'Role enrichment failed on id ' . $id . ': ' . $wpdb->last_error, array('status' => 500));
        }
        if (!empty($row->post_id)) {
            foreach ($data as $key => $value) update_post_meta((int) $row->post_id, $key, $value);
        }
        if ($real) { $out['updated'][] = $id; } else { $out['marked_unknown'][] = $id; }
    }
    $reason = sanitize_text_field((string) $r->get_param('reason'));
    // Only rows given REAL categories enter the public corrections trail;
    // 'unknown' markers are queue bookkeeping, not a data change.
    if (!empty($out['updated'])) {
        alt_log_correction('enriched', $out['updated'], $reason !== '' ? $reason : 'Automated role-category extraction from stored source evidence');
    }
    if ((!empty($out['updated']) || !empty($out['marked_unknown'])) && function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

/**
 * Fill ONLY blank industries with canonical-vocabulary labels. The daily
 * worker (railway/industry_backfill.py) classifies from company identity +
 * the retained excerpt and double-confirms with an independent model pass;
 * this endpoint enforces the parts the server can enforce: blank-only, closed
 * vocabulary, no other field touched. Rows are NOT pinned — the fill survives
 * the daily WARN upsert because alt_db_upsert no longer blanks industry, and
 * a purge-reload simply returns the row to the visible backlog.
 */
function alt_api_industry_backfill(WP_REST_Request $r) {
    global $wpdb;
    $items = $r->get_param('items');
    if (!is_array($items)) return new WP_Error('alt_bad_request', 'items must be an array of {id, industry}.', array('status' => 400));
    if (count($items) > 2000) return new WP_Error('alt_bad_request', 'at most 2000 items per call.', array('status' => 400));
    $vocabulary = function_exists('alt_industry_vocabulary') ? alt_industry_vocabulary() : array();
    if (!$vocabulary) return new WP_Error('alt_server_error', 'industry vocabulary unavailable.', array('status' => 500));
    $table = alt_db_table();
    $out = array('filled' => array(), 'skipped_not_blank' => array(), 'rejected' => array(), 'not_found' => array());
    foreach ($items as $item) {
        $id = (int) ($item['id'] ?? 0);
        $row = $id ? $wpdb->get_row($wpdb->prepare("SELECT id, post_id, industry FROM $table WHERE id = %d", $id)) : null;
        if (!$row) { $out['not_found'][] = $id; continue; }
        if ($row->industry !== '') { $out['skipped_not_blank'][] = $id; continue; }
        $industry = function_exists('alt_normalize_industry')
            ? alt_normalize_industry(sanitize_text_field((string) ($item['industry'] ?? '')))
            : '';
        // The normalizer's Title-Case fallback is for source-supplied sectors;
        // model-classified fills must land exactly on a canonical label.
        if ($industry === '' || !in_array($industry, $vocabulary, true)) { $out['rejected'][] = $id; continue; }
        // FAIL LOUDLY (iron rule): a silent false must not report success.
        if ($wpdb->update($table, array('industry' => $industry), array('id' => (int) $row->id)) === false) {
            return new WP_Error('alt_db_error', 'Industry backfill failed on id ' . $id . ': ' . $wpdb->last_error,
                array('status' => 500, 'filled_so_far' => $out['filled']));
        }
        if (!empty($row->post_id)) update_post_meta((int) $row->post_id, 'industry', $industry);
        $out['filled'][] = $id;
    }
    $out['remaining_blank'] = (int) $wpdb->get_var("SELECT COUNT(*) FROM $table WHERE industry = ''");
    if (!empty($out['filled'])) {
        alt_log_correction('enriched', $out['filled'],
            'Automated industry classification: company identity + retained excerpt, double-confirmed by two model passes, fixed vocabulary, blank fields only');
        if (function_exists('alt_flush_caches')) alt_flush_caches();
    }
    return rest_ensure_response($out);
}

/**
 * Collectors we deliberately retired. Declared here (not in the stored ledger)
 * so retirement is self-healing: even if an old cron writes a 'degraded' row,
 * the GET below coerces it to a benign 'retired' state. Keeps the health page
 * honest (a retired source is not a breakage) without needing a keyed write.
 */
function alt_retired_sources() {
    // source => array(retired_on (UTC date), reason). The DATE matters: a run
    // POSTed AFTER it means the collector was deliberately switched back on and
    // must never be masked; a run before it is just the last gasp before
    // retirement (a 'within N days' window instead wrongly un-retired every
    // source for its first N days — caught 2026-07-25).
    return array(
        // Date moved 2026-07-25 -> 2026-07-30. The retirement was silently VOID for
        // five weeks: news_catchup.py kept POSTing health under this id every
        // Monday, and a fresh checked_at is always AFTER the retirement date, so
        // the masking loop below hit its `continue` and the public health page
        // went on advertising a retired collector as live. news_catchup.py now
        // reports under its own id; this later date covers its final post
        // (2026-07-27) so the frozen row finally masks. Retiring a source is
        // THREE steps: drop it from cron.py, add it here, and stop every
        // remaining path that posts health under the id.
        'newsapi' => array('2026-07-30', 'Retired 2026-07-25. Replaced by keyless Google News RSS discovery, whose headlines carry the headcount even for paywalled marquee layoffs. Worldwide news coverage continues via GDELT + Google News.'),
        // JP/KR/BR filing probes: after months live they ingested zero layoff rows
        // (those filings essentially never announce layoffs); coverage comes from
        // worldwide news + ERM. Discovery gated off (RUN_DISCOVERY_PROBES) and the
        // schedule disabled 2026-07-24. Marked retired so their last-run rows never
        // age into a false "stale" alarm.
        'edinet_jp' => array('2026-07-24', 'Retired 2026-07-24. Japan filing probe ingested zero layoff rows; Japan is covered through worldwide news. Client kept, re-runnable on demand.'),
        'opendart_kr' => array('2026-07-24', 'Retired 2026-07-24. South Korea filing probe ingested zero layoff rows; South Korea is covered through worldwide news. Client kept, re-runnable on demand.'),
        'cvm_br' => array('2026-07-24', 'Retired 2026-07-24. Brazil filing probe ingested zero layoff rows; Brazil is covered through worldwide news. Client kept, re-runnable on demand.'),
    );
}

/*
  THE ONE MASKED READ, and the reason it is a function of its own.

  Retiring a collector is THREE steps, and the third is "stop every remaining
  path that posts health under the id". There is a fourth failure the rule did
  not name: a SECOND reader of the same option that does not apply the mask.
  /source-health went through the masking loop below; /quality-status read
  get_option('alt_source_health') raw, and the public Health page fetches
  /quality-status. So on 2026-08-04 the two endpoints described the same four
  collectors differently at the same instant, and the retired ones were the
  ones the page showed as "ok". alt_api_quarterly_report_post() freezes this
  map into an immutable artifact, so the next quarterly report would have
  recorded them as live coverage permanently.

  Every reader of alt_source_health now goes through here.
*/
function alt_source_health_masked() {
    $health = get_option('alt_source_health');
    if (!is_array($health)) $health = array();
    // Coerce any retired collector to a permanent, benign 'retired' state with a
    // fresh timestamp, so no consumer (health page, ops_status, digest) reads it
    // as degraded OR stale. 'retired' is a declared status, not a run claim.
    foreach (alt_retired_sources() as $src => $meta) {
        if (!isset($health[$src])) continue;
        list($retired_on, $why) = $meta;
        // Ran AFTER the retirement date => deliberately switched back on; show
        // its real status. (Reactivating permanently means also removing the
        // source from alt_retired_sources() in the same change.)
        $ts  = strtotime((string) ($health[$src]['checked_at'] ?? ''));
        $cut = strtotime($retired_on . ' 23:59:59 UTC');
        if ($ts && $cut && $ts > $cut && ($health[$src]['status'] ?? '') !== 'retired') {
            continue;
        }
        // Keep the REAL last-run timestamp: fabricating a fresh checked_at made
        // the health page claim a months-idle collector was checked "just now".
        $health[$src]['status'] = 'retired';
        $health[$src]['detail'] = $why;
    }
    return $health;
}

function alt_api_source_health_get() {
    return rest_ensure_response(alt_source_health_masked());
}

/**
 * The ONE writer of a source's health row. Both the keyed REST reporter and
 * any in-plugin reporter (the digest mailer's cron) go through here, so the
 * "no raw reader outside the mask" guard keeps a single merge-one-row-back
 * read to reason about. Everything else in the option is left untouched.
 */
function alt_source_health_record($source, $status, $entries, $detail) {
    $health = get_option('alt_source_health');
    if (!is_array($health)) $health = array();
    $health[$source] = array(
        'status' => in_array($status, array('ok', 'running', 'degraded', 'retired'), true)
            ? $status : 'degraded',
        'entries' => max(0, (int) $entries),
        'checked_at' => gmdate('c'),
        'detail' => substr(sanitize_text_field((string) $detail), 0, 240),
    );
    update_option('alt_source_health', $health, false);
    return $health[$source];
}

function alt_api_source_health_post(WP_REST_Request $r) {
    global $wpdb;
    $source = sanitize_key((string) $r->get_param('source'));
    if ($source === '') return new WP_Error('alt_bad_request', 'source is required.', array('status' => 400));
    if (!alt_source_runs_table_ready()) {
        return new WP_Error('alt_db_error', 'Collector-run telemetry table is unavailable after migration retry.', array('status' => 500));
    }
    $health = array();
    $health[$source] = alt_source_health_record(
        $source, $r->get_param('status'), (int) $r->get_param('entries'), (string) $r->get_param('detail'));
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
    // A blank industry is common in structured WARN notices; the bounded daily
    // /industry-backfill worker fills them conservatively (company identity +
    // retained excerpt, closed vocabulary, blank-when-uncertain). A blank US
    // state means the source did not identify the affected-job location; never
    // use an employer HQ, office footprint, or brand knowledge to fill it.
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
            'industry_rule' => 'Industry is filled only from the company identity and retained source excerpt, restricted to the fixed vocabulary, double-confirmed by two independent model passes, and left blank when uncertain; structured WARN notices commonly omit it, so a visible backlog remains until the bounded daily backfill reaches those rows. Fills are disclosed in the public corrections trail.',
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
    // Masked, not raw: this is what the public Health page renders, and a
    // retired collector must not appear here as "ok". See
    // alt_source_health_masked().
    $health = alt_source_health_masked();
    $log = get_option('alt_corrections_log');
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
            array('id' => 'survey_reconciliation', 'status' => 'active', 'scope' => 'Public monthly strict US benchmark; source-evidenced announcement-date backfill continues'),
            array('id' => 'announcement_and_domicile_enrichment', 'status' => 'active', 'scope' => 'Daily exact-source-quote enrichment; legacy rows are never inferred'),
            array('id' => 'industry_and_job_location_metadata', 'status' => 'active', 'scope' => 'Public completeness telemetry identifies blank industry and affected-job-state fields; a bounded daily backfill classifies blank industries from company identity and the retained excerpt only (fixed vocabulary, double-confirmed, blank when uncertain), while job-location state still requires source evidence and never headquarters inference'),
            array('id' => 'country_recall_benchmarks', 'status' => 'active', 'scope' => 'Public country-period recall protocol and retained samples; no country completeness claim'),
            array('id' => 'high_impact_editorial_review', 'status' => 'active', 'scope' => 'Read-only queue for very large, AI-primary and multi-country events; editorial decisions remain manual'),
            array('id' => 'dataset_release_ledger', 'status' => 'active', 'scope' => 'Immutable release snapshots from this deployment forward; no invented legacy addition counts'),
            array('id' => 'company_directory', 'status' => 'active', 'scope' => 'Source-linked company pages that grow automatically: a weekly autopilot (autopilot-v1) admits companies at three or more source-linked canonical events with a clean identity, through the same server-side admission rules and two-event indexability threshold as manual review; indexable pages are sitemap-listed'),
            array('id' => 'quarterly_state_of_layoffs', 'status' => 'active', 'scope' => 'Server-generated immutable quarterly snapshots; the first report (2026-Q2) is published from a frozen snapshot with its data revision and coverage limits disclosed'),
            array('id' => 'warn_transparency_dataset', 'status' => 'in_progress', 'scope' => 'Separate evidence-linked timing/adjudication research dataset; never included in layoff or AI totals'),
            array('id' => 'national_connectors_and_ir_feeds', 'status' => 'pending_permission', 'scope' => 'First five reviewed company-owned IR feeds admitted to the versioned registry on 2026-07-18; live collection state is reported by source health above. Official national connectors remain pending permitted interfaces'),
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
    $report = alt_quarterly_report_by_id($report_id);
    if (!$report) return new WP_Error('alt_not_found', 'Quarterly report not found.', array('status' => 404));
    return rest_ensure_response($report);
}

/** Shared immutable lookup for HTML/REST/download appendix consumers. */
function alt_quarterly_report_by_id($report_id) {
    $reports = get_option('alt_quarterly_reports');
    return is_array($reports) && isset($reports[$report_id]) ? $reports[$report_id] : null;
}

/** A compact, stable appendix shape that contains only fields already frozen. */
function alt_quarterly_report_appendix_data($report) {
    $snapshot = is_array($report['snapshot'] ?? null) ? $report['snapshot'] : array();
    return array(
        'appendix_version' => 1,
        'report_id' => (string) ($report['report_id'] ?? ''),
        'title' => (string) ($report['title'] ?? ''),
        'publication_status' => (string) ($report['publication_status'] ?? ''),
        'generated_at' => (string) ($report['generated_at'] ?? ''),
        'dataset_revision' => (int) ($report['dataset_revision'] ?? 0),
        'period' => $report['period'] ?? array(),
        'query_manifest' => $report['query_manifest'] ?? array(),
        'coverage_at_publication' => $report['coverage_at_publication'] ?? array(),
        'limitations' => $report['limitations'] ?? array(),
        'snapshot' => array(
            'verified' => $snapshot['verified'] ?? array(),
            'announced' => $snapshot['announced'] ?? array(),
            'ai_primary_verified_subset' => $snapshot['ai_primary_verified_subset'] ?? array(),
        ),
        'appendix_scope' => 'Frozen aggregate tables and time series only. This appendix does not regenerate values from the live database and is not a raw event export.',
    );
}

function alt_api_quarterly_report_appendix_get(WP_REST_Request $r) {
    $report = alt_quarterly_report_by_id((string) $r->get_param('report_id'));
    if (!$report) return new WP_Error('alt_not_found', 'Quarterly report not found.', array('status' => 404));
    return rest_ensure_response(alt_quarterly_report_appendix_data($report));
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
        'title' => 'State of Layoffs: ' . $report_id,
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
/**
 * Append a public tip to the intake queue. Called server-side from the
 * captcha-protected contact form, never from an unauthenticated REST route.
 * Bounded so a flood cannot grow the option unbounded.
 */
/**
 * Is this a tip link the ingest runner may be asked to fetch?
 *
 * The runner-side gate is railway/safe_fetch.py and it is the real one. This
 * is the intake side of the same rule, and it is here because a queue entry is
 * a standing instruction: whatever lands in alt_tips_queue is what
 * process_tips.py will go and fetch, on a schedule, later, with WP_API_KEY and
 * OPENROUTER_API_KEY in its environment. esc_url_raw is not that gate, it
 * happily passes http://127.0.0.1:8080/ and http://169.254.169.254/ because
 * those are perfectly well-formed URLs, and it permits ftp:, mailto: and the
 * rest of the default protocol list besides.
 *
 * Literal-address only, deliberately: PHP cannot see what a hostname will
 * resolve to at fetch time and pretending otherwise here would invite someone
 * to trust it instead of the runner-side check.
 */
function alt_tip_url_allowed($url) {
    $url = trim((string) $url);
    if ($url === '') return true;                       // optional field
    $parts = wp_parse_url($url);
    $scheme = strtolower($parts['scheme'] ?? '');
    if ($scheme !== 'http' && $scheme !== 'https') return false;
    $host = strtolower(trim($parts['host'] ?? '', '[]'));
    if ($host === '') return false;
    if ($host === 'localhost' || substr($host, -6) === '.local') return false;
    if (filter_var($host, FILTER_VALIDATE_IP) === false) return true;
    return filter_var($host, FILTER_VALIDATE_IP,
        FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) !== false;
}

function alt_tips_append($company, $source_url, $email, $note, $attachment = '') {
    if (!alt_tip_url_allowed($source_url)) return false;
    $q = get_option('alt_tips_queue');
    if (!is_array($q)) $q = array();
    $q[] = array(
        'id'         => (string) (count($q) + 1) . '-' . substr(md5($source_url . microtime()), 0, 8),
        'company'    => substr((string) $company, 0, 160),
        'source_url' => esc_url_raw((string) $source_url),
        'email'      => sanitize_email((string) $email),
        'note'       => substr((string) $note, 0, 500),
        'attachment' => substr((string) $attachment, 0, 300),
        'status'     => 'new',
        'received'   => gmdate('c'),
    );
    if (count($q) > 500) $q = array_slice($q, -500);   // keep the newest
    update_option('alt_tips_queue', $q, false);
    return true;
}

function alt_press_subscribe($email, $name, $outlet) {
    $email = sanitize_email($email);
    if (!is_email($email)) return false;
    $subs = get_option('alt_press_subscribers');
    if (!is_array($subs)) $subs = array();
    foreach ($subs as $sx) { if (($sx['email'] ?? '') === $email) return true; } // dedupe
    $subs[] = array('email' => $email, 'name' => substr((string) $name, 0, 120),
                    'outlet' => substr((string) $outlet, 0, 160), 'joined' => gmdate('c'),
                    'status' => 'active');
    if (count($subs) > 5000) $subs = array_slice($subs, -5000);
    update_option('alt_press_subscribers', $subs, false);
    return true;
}

function alt_api_press_subs_get(WP_REST_Request $r) {
    $subs = get_option('alt_press_subscribers');
    $subs = is_array($subs) ? array_values(array_filter($subs, function ($s) {
        return ($s['status'] ?? 'active') === 'active';
    })) : array();
    return array('subscribers' => $subs, 'count' => count($subs));
}

/**
 * Which of these source URLs are already in the record (main rows OR retained
 * source reports)? Read-only; used by collectors to skip re-extracting the
 * exact same article on overlapping pull windows. Caps at 500 URLs per call.
 */
function alt_api_seen_urls(WP_REST_Request $r) {
    global $wpdb;
    $urls = $r->get_param('urls');
    if (!is_array($urls)) return array('seen' => array());
    $urls = array_values(array_unique(array_filter(array_map(function ($u) {
        $u = esc_url_raw(trim((string) $u));
        return (strlen($u) > 11 && strpos($u, 'http') === 0) ? $u : '';
    }, array_slice($urls, 0, 500)))));
    if (!$urls) return array('seen' => array());
    $ph = implode(',', array_fill(0, count($urls), '%s'));
    $seen = $wpdb->get_col($wpdb->prepare(
        "SELECT source_url FROM " . alt_db_table() . " WHERE source_url IN ($ph)", $urls));
    $seen2 = $wpdb->get_col($wpdb->prepare(
        "SELECT source_url FROM " . alt_source_reports_table() . " WHERE source_url IN ($ph)", $urls));
    return array('seen' => array_values(array_unique(array_merge($seen ?: array(), $seen2 ?: array()))));
}

/* ------------------------------------------------------------------ */
/* Source archiving (Internet Archive / Wayback) — see archive_backfill.py */
/* ------------------------------------------------------------------ */

// Rounds a source URL is retried before it is recorded 'unavailable' (dead or
// bot-walled) instead of retried forever. The daily backfill retries 'pending'
// rows on a spacing window, so this is roughly a week of attempts.
if (!defined('ALT_ARCHIVE_MAX_ATTEMPTS')) define('ALT_ARCHIVE_MAX_ATTEMPTS', 5);
// The re-check cadence, defined ONCE and read by BOTH sides of the promise:
// the candidate query below (what the daily cron actually hands out) and
// alt_archive_next_check_date() (the "next check by <date>" the listing pages
// print beside a row with no Wayback snapshot yet). One definition, so the
// sentence a reader sees and the schedule the cron keeps cannot drift apart.
// RETRY_HOURS spaces 'pending' retries; RECHECK_DAYS is the weekly re-check of
// 'unavailable' URLs (never given up). DAILY_RUN_UTC is when archive-backfill
// actually runs and MUST match the cron in .github/workflows/archive-backfill.yml
// ('25 5 * * *'); railway/tests/test_archive_promise.py pins that equality, and
// data_integrity's archive_recheck_cadence invariant fails CI when the live
// data shows the cadence is not being kept.
if (!defined('ALT_ARCHIVE_RETRY_HOURS')) define('ALT_ARCHIVE_RETRY_HOURS', 72);
if (!defined('ALT_ARCHIVE_RECHECK_DAYS')) define('ALT_ARCHIVE_RECHECK_DAYS', 7);
if (!defined('ALT_ARCHIVE_DAILY_RUN_UTC')) define('ALT_ARCHIVE_DAILY_RUN_UTC', '05:25');

/**
 * Key-protected: return the next batch of DISTINCT source URLs that still need
 * a permanent archive. The gap is computed by LEFT JOIN against the archive
 * index, so this covers EVERY row type (WARN / news / SEC / ERM) and — crucially
 * — a brand-new row's source URL appears here automatically until it is
 * archived, with no ingest-path change. That is how forward coverage is
 * guaranteed: the daily backfill drains whatever /add and /bulk have written.
 *
 * A URL is returned when it has no archive row yet, or when its row is 'pending'
 * (a previous save was rate-limited/in-flight) and older than the retry window.
 * 'archived' and 'unavailable' URLs drop out, so the job is naturally resumable.
 */
function alt_api_archive_candidates(WP_REST_Request $r) {
    global $wpdb;
    if (!alt_archive_table_ready()) {
        return new WP_Error('alt_db_error', 'Archive index unavailable after migration retry.', array('status' => 500));
    }
    $limit = min(500, max(1, (int) ($r->get_param('limit') ?: 200)));
    $retry_hours = min(720, max(1, (int) ($r->get_param('retry_hours') ?: ALT_ARCHIVE_RETRY_HOURS)));
    $retry_before = gmdate('Y-m-d H:i:s', time() - $retry_hours * HOUR_IN_SECONDS);
    // NEVER give up: an 'unavailable' URL is re-checked WEEKLY forever, because a
    // source not yet in Wayback today may be crawled next month — so every row
    // eventually gets its archive or an honest, freshly-timestamped disclaimer.
    $weekly_before = gmdate('Y-m-d H:i:s', time() - ALT_ARCHIVE_RECHECK_DAYS * DAY_IN_SECONDS);
    $layoffs = alt_db_table();
    $archive = alt_archive_table();
    // DISTINCT source URLs missing an archive, 'pending' and due for retry, or
    // 'unavailable' and due for its weekly re-check. The MD5 join matches the
    // PHP/Python url_hash (md5 of the trimmed URL). NB: the literal percent in
    // LIKE 'http%' is doubled to '%%' because this string is run through
    // $wpdb->prepare (a bare % is read as a placeholder).
    // NEVER-CHECKED FIRST (newest layoff date among them), then OLDEST LAST
    // ATTEMPT first. This ordering is what makes the pages' "next check by
    // <date>" promise keepable: the old "newest layoff date first" ordering
    // starved older-dated pending rows whenever more than one batch was due —
    // the same freshly-restamped top slice cycled every 72h while everything
    // ranked below the batch size was never retried again. Oldest-attempt-first
    // is round-robin fairness: every due URL is retried within
    // (due pool / daily throughput) days of becoming eligible, which is the
    // arithmetic the archive_recheck_cadence data-integrity invariant holds
    // the live data to.
    $sql = "SELECT l.source_url
            FROM $layoffs l
            LEFT JOIN $archive a ON a.url_hash = MD5(TRIM(l.source_url))
            WHERE l.source_url <> '' AND l.source_url LIKE 'http%%'
              AND (a.url_hash IS NULL
                   OR (a.status = 'pending' AND (a.checked_at IS NULL OR a.checked_at < %s))
                   OR (a.status = 'unavailable' AND (a.checked_at IS NULL OR a.checked_at < %s)))
            GROUP BY l.source_url
            ORDER BY (MIN(a.checked_at) IS NULL) DESC, MIN(a.checked_at) ASC, MAX(l.layoff_date) DESC
            LIMIT %d";
    $urls = $wpdb->get_col($wpdb->prepare($sql, $retry_before, $weekly_before, $limit)) ?: array();
    return rest_ensure_response(array(
        'urls' => array_values($urls),
        'limit' => $limit,
        'coverage' => alt_archive_coverage_counts(),
    ));
}

/**
 * Live US counting-basis comparison, for the methodology and press pages.
 *
 * Two correct answers to two different questions, computed fresh from the table
 * so they can never go stale or disagree with the tracker:
 *   - job_location: jobs physically in the country (the PUBLIC HEADLINE basis)
 *   - employer_any: job-location OR employer domicile, so a US-headquartered
 *     employer's multi-country cut is included (the basis that matches how
 *     announcement surveys count, and the basis any external comparison must use)
 * The delta is exactly the multi-country cuts by employers domiciled here.
 * Cached for an hour and invalidated by the dataset version.
 */
function alt_country_basis_compare($country = 'United States', $year = null) {
    global $wpdb;
    $year = $year ? (int) $year : (int) gmdate('Y');
    $key  = 'alt_basis_cmp_' . md5($country . '|' . $year . '|' . (int) get_option('alt_data_ver', 1));
    $hit  = get_transient($key);
    if (is_array($hit)) return $hit;

    $t = alt_db_table();
    $strict = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COALESCE(SUM(job_count),0) FROM $t
         WHERE superset_of = 0 AND YEAR(layoff_date) = %d AND country = %s", $year, $country));
    $any = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COALESCE(SUM(job_count),0) FROM $t
         WHERE superset_of = 0 AND YEAR(layoff_date) = %d
           AND (country = %s OR employer_country = %s)", $year, $country, $country));
    $out = array(
        'country'       => $country,
        'year'          => $year,
        'job_location'  => $strict,
        'employer_any'  => $any,
        'difference'    => max(0, $any - $strict),
        'as_of'         => gmdate('c'),
    );
    set_transient($key, $out, HOUR_IN_SECONDS);
    return $out;
}

/**
 * Renders the basis comparison as a self-updating table. Used on methodology
 * and press so an external comparison can never be quoted against the wrong
 * number. Every figure is live; nothing here is hardcoded.
 */
function alt_basis_table_html($country = 'United States', $year = null) {
    $c = alt_country_basis_compare($country, $year);
    $f = function ($n) { return number_format((int) $n); };
    ob_start(); ?>
    <div class="alt-health-table-wrap">
    <table class="alt-basis-table">
      <thead><tr><th>Counting basis</th><th><?php echo esc_html($c['country'] . ' ' . $c['year']); ?></th><th>What it counts</th></tr></thead>
      <tbody>
        <tr><th>Job location <span class="alt-muted">(verified + announced, as the tracker's location totals count)</span></th>
            <td><b><?php echo esc_html($f($c['job_location'])); ?></b></td>
            <td>Only jobs physically located in <?php echo esc_html($c['country']); ?>. The stricter, more conservative basis, so a global figure can never inflate it.</td></tr>
        <tr><th>Employer basis <span class="alt-muted">(verified + announced, for like-for-like survey comparison)</span></th>
            <td><b><?php echo esc_html($f($c['employer_any'])); ?></b></td>
            <td>Job location <em>or</em> employer domicile, so a <?php echo esc_html($c['country']); ?>-headquartered employer's multi-country cut is included. This is how announcement surveys count, so it is the only fair basis to compare us against one.</td></tr>
        <tr><th>Difference</th>
            <td><b><?php echo esc_html($f($c['difference'])); ?></b></td>
            <td>Multi-country cuts by employers headquartered in <?php echo esc_html($c['country']); ?>. Each stays labeled &ldquo;Multiple countries&rdquo; in the data and is never silently recounted as <?php echo esc_html($c['country']); ?>-only.</td></tr>
      </tbody>
    </table>
    </div>
    <p class="alt-muted">Figures update automatically as records are verified. Compare like with like: quoting our job-location headline against a survey that counts by employer will understate us by the difference above, and the reverse will overstate us.</p>
    <?php
    return ob_get_clean();
}

/**
 * THE ONE SENTENCE THAT RECONCILES THE TWO TOTALS THIS SITE PUBLISHES.
 *
 * Rows are dated by the day a cut takes EFFECT, and WARN notices are filed
 * weeks ahead by law, so a calendar-year window legitimately holds cuts dated
 * later in the year. That gives two correct totals for one year:
 *
 *   to-date   what has taken effect as of today
 *   calendar  the whole window, to-date plus the part still ahead
 *
 * Both were live on 2026-08-04 and they disagreed by 33,939: the tracker home
 * page headlined 484,468 for 2026 while the press page, the FAQPage JSON-LD
 * and the citeline all published 450,529 for the same year. Neither number was
 * wrong. Publishing them on two surfaces with no stated relationship is what
 * was wrong, and the press page is the surface built to be quoted.
 *
 * So the rule, and it is one rule for every surface: a sentence about "so far"
 * or "as of today" quotes the to-date figure; a sentence naming the whole
 * window quotes the calendar figure and prints THIS sentence beside it. Both
 * page-tracker.php and page-press.php render this function's output verbatim,
 * and renderStats() in layoffs.js rebuilds the identical string on the client,
 * so the wording cannot drift between the two surfaces one edit at a time.
 *
 * @param int    $to_date   verified jobs whose effective date has arrived
 * @param int    $calendar  verified jobs across the whole window
 * @param string $as_of     rendered date the to-date figure is cut at
 * @param string $period    label for the window, e.g. "2026"
 * @return string plain text, no markup, safe to esc_html() at the call site
 */
function alt_period_split_sentence($to_date, $calendar, $as_of, $period) {
    $to_date  = max(0, (int) $to_date);
    $calendar = max(0, (int) $calendar);
    $later    = max(0, $calendar - $to_date);
    // Nothing ahead means nothing to reconcile, and a sentence explaining a
    // zero remainder is noise. Callers hide the line on an empty string.
    if ($later <= 0) return '';
    return number_format($to_date) . ' have taken effect as of ' . $as_of
        . '. The other ' . number_format($later)
        . ' are on notices already filed for effective dates later in ' . $period
        . '. Together they make the ' . number_format($calendar) . ' total for ' . $period . '.';
}

/**
 * Descriptive WARN notice-gap distribution, computed from the main table's own
 * recorded dates and nothing else. For US WARN rows, announcement_date holds
 * the state-recorded notice/received date and layoff_date the effective date
 * (sources/warn.py sets announcement_date only when the notice date exists and
 * does not postdate the effective date). The gap between them is how much
 * advance notice the record shows.
 *
 * DESCRIPTIVE, NEVER A VERDICT. The federal WARN Act's 60-day period
 * (29 U.S.C. 2102(a)) has lawful exceptions (29 U.S.C. 2102(b); 20 C.F.R.
 * 639.9) that only a court may adjudicate (29 U.S.C. 2104), so a gap shorter
 * than 60 days is reported as exactly that: shorter than 60 days. No figure
 * here labels any employer non-compliant, and this function is unrelated to
 * the separate editorial WARN transparency register.
 *
 * Rows missing either date, or whose effective date precedes the notice date,
 * are EXCLUDED AND COUNTED, never imputed. So are rows whose two dates are
 * IDENTICAL: when a state publishes only one date column, the importer stores
 * that date in both fields (sources/warn.py falls back to the notice/received
 * column for layoff_date), so a zero gap cannot be distinguished from a
 * genuine same-day notice. Nine states rendered as "median 0 days, 100%
 * shorter than 60" on this metric's first live render for exactly that
 * reason; treating them as measured zero notice would have published a wrong
 * number. Aggregated as a (state, gap) histogram so exact medians compute
 * without loading every row; cached for 6 hours keyed on the dataset version.
 */
function alt_warn_notice_gap_stats() {
    global $wpdb;
    // Keyed on plugin version too, so a deploy that changes this function's
    // output shape can never be served a stale cached array of the old shape.
    $key = 'alt_notice_gap_' . md5(ALT_VERSION . '|' . (int) get_option('alt_data_ver', 1));
    $hit = get_transient($key);
    if (is_array($hit)) return $hit;

    $t = alt_db_table();
    $scope = "source_type = 'warn' AND country = 'United States' AND state <> ''";
    $hist = $wpdb->get_results(
        "SELECT state, DATEDIFF(layoff_date, announcement_date) AS gap, COUNT(*) AS n
         FROM $t
         WHERE $scope AND announcement_date IS NOT NULL AND layoff_date IS NOT NULL
           AND announcement_date < layoff_date
         GROUP BY state, gap", ARRAY_A) ?: array();
    $missing = (int) $wpdb->get_var(
        "SELECT COUNT(*) FROM $t
         WHERE $scope AND (announcement_date IS NULL OR layoff_date IS NULL)");
    $reversed = (int) $wpdb->get_var(
        "SELECT COUNT(*) FROM $t
         WHERE $scope AND announcement_date IS NOT NULL AND layoff_date IS NOT NULL
           AND announcement_date > layoff_date");
    $same_date = (int) $wpdb->get_var(
        "SELECT COUNT(*) FROM $t
         WHERE $scope AND announcement_date IS NOT NULL AND layoff_date IS NOT NULL
           AND announcement_date = layoff_date");

    $per_state = array();
    $overall = array();
    foreach ($hist as $h) {
        $st = strtoupper((string) $h['state']);
        $gap = (int) $h['gap'];
        $n = (int) $h['n'];
        if (!isset($per_state[$st])) $per_state[$st] = array();
        $per_state[$st][$gap] = ($per_state[$st][$gap] ?? 0) + $n;
        $overall[$gap] = ($overall[$gap] ?? 0) + $n;
    }

    // Exact median and share-under-60 from a gap=>count histogram.
    $summarise = function ($h) {
        ksort($h);
        $n = array_sum($h);
        if ($n < 1) return null;
        $under = 0;
        foreach ($h as $gap => $c) { if ($gap < 60) $under += $c; }
        $lo_rank = (int) floor(($n + 1) / 2);   // 1-based middle (lower on even n)
        $hi_rank = (int) ceil(($n + 1) / 2);
        $lo = $hi = null;
        $seen = 0;
        foreach ($h as $gap => $c) {
            $seen += $c;
            if ($lo === null && $seen >= $lo_rank) $lo = $gap;
            if ($hi === null && $seen >= $hi_rank) { $hi = $gap; break; }
        }
        return array(
            'n'           => $n,
            'median_days' => ($lo + $hi) / 2,
            'under_60'    => $under,
            'under_60_pct'=> $under / $n,
        );
    };

    $states = array();
    foreach ($per_state as $st => $h) {
        $s = $summarise($h);
        if ($s) $states[$st] = $s;
    }
    uasort($states, function ($a, $b) { return $b['n'] <=> $a['n']; });

    $out = array(
        'overall'  => $summarise($overall),
        'states'   => $states,
        'excluded' => array('missing_dates' => $missing,
                            'effective_precedes_notice' => $reversed,
                            'same_date_ambiguous' => $same_date),
        'as_of'    => gmdate('c'),
    );
    set_transient($key, $out, 6 * HOUR_IN_SECONDS);
    return $out;
}

/**
 * Renders the notice-gap distribution for the methodology page. Every figure
 * is computed by alt_warn_notice_gap_stats(); nothing is typed. States with
 * fewer than 25 datable notices fold into the overall figures only, so no
 * thin-sample median is presented as if it described a state.
 */
function alt_notice_gap_table_html() {
    $s = alt_warn_notice_gap_stats();
    if (!is_array($s) || empty($s['overall'])) return '';
    $o = $s['overall'];
    $floor = 25;
    $pct = function ($x) { return number_format($x * 100, 1) . '%'; };
    $days = function ($d) { return rtrim(rtrim(number_format((float) $d, 1), '0'), '.'); };
    ob_start(); ?>
    <p>Across <b><?php echo number_format((int) $o['n']); ?></b> US WARN notices that record an
    official notice date and a later, distinct effective date, the median recorded notice period is
    <b><?php echo esc_html($days($o['median_days'])); ?> days</b>, and
    <b><?php echo esc_html($pct($o['under_60_pct'])); ?></b>
    (<?php echo number_format((int) $o['under_60']); ?> notices) record a gap shorter than the
    federal 60-day period.</p>
    <p>Excluded and counted, never guessed: <?php echo number_format((int) $s['excluded']['missing_dates']); ?> notices
    missing one of the two dates; <?php echo number_format((int) $s['excluded']['same_date_ambiguous']); ?> whose
    stored notice and effective dates are identical (several states publish a single date, which the
    importer stores in both fields, so a zero gap cannot be told apart from a genuine same-day
    notice)<?php if ((int) $s['excluded']['effective_precedes_notice'] > 0) : ?>; and
    <?php echo number_format((int) $s['excluded']['effective_precedes_notice']); ?> whose recorded
    effective date precedes the notice date<?php endif; ?>. This makes the shorter-than-60 share
    conservative: real same-day notices, if any, are excluded rather than counted against employers.</p>
    <div class="alt-health-table-wrap">
    <table class="alt-basis-table alt-notice-gap-table">
      <thead><tr><th>State</th><th>Notices with both dates</th><th>Median days of notice</th><th>Share shorter than 60 days</th></tr></thead>
      <tbody>
      <?php foreach ($s['states'] as $st => $row) :
          if ((int) $row['n'] < $floor) continue; ?>
        <tr><th><?php echo esc_html($st); ?></th>
            <td><?php echo number_format((int) $row['n']); ?></td>
            <td><?php echo esc_html($days($row['median_days'])); ?></td>
            <td><?php echo esc_html($pct($row['under_60_pct'])); ?></td></tr>
      <?php endforeach; ?>
      </tbody>
    </table>
    </div>
    <p class="alt-muted">States with fewer than <?php echo (int) $floor; ?> datable notices are included
    in the overall figures but not listed separately. Figures recompute automatically as notices arrive.</p>
    <?php
    return ob_get_clean();
}

/**
 * Wilson 95% score interval for k successes in n trials, as [lo, hi] fractions.
 * Deterministic arithmetic on committed inputs — the interval the measurement
 * pages print is computed, never typed.
 */
function alt_wilson_interval($k, $n, $z = 1.959964) {
    $k = (int) $k; $n = (int) $n;
    if ($n <= 0) return array(0.0, 0.0);
    $p = $k / $n;
    $z2 = $z * $z;
    $den = 1 + $z2 / $n;
    $centre = ($p + $z2 / (2 * $n)) / $den;
    $half = ($z * sqrt(($p * (1 - $p) + $z2 / (4 * $n)) / $n)) / $den;
    return array(max(0.0, $centre - $half), min(1.0, $centre + $half));
}

/**
 * The committed SEC Item 2.05 gold-set measurement, for the tracker page's
 * "how complete is that, measured?" paragraph. Read from
 * data/recall-measurement.json — a render copy of railway/recall_measurement.json
 * written by recall_precision.py (weekly recall-precision.yml) so the page
 * follows the measurement instead of hardcoding "24 of 57". Returns null when
 * the file is missing or malformed, and the caller renders NOTHING rather than
 * a stale typed number. The figure is a frozen-set regression measurement, not
 * "our recall" — the caller must keep the caveats beside it (see
 * docs/RECALL_BENCHMARK_PROTOCOL.md).
 */
function alt_recall_measurement() {
    $path = ALT_PLUGIN_DIR . 'data/recall-measurement.json';
    if (!is_readable($path)) return null;
    $j = json_decode((string) file_get_contents($path), true);
    if (!is_array($j)) return null;
    $matched = (int) ($j['matched'] ?? -1);
    $ref = (int) ($j['reference_events'] ?? 0);
    if ($ref <= 0 || $matched < 0 || $matched > $ref) return null;
    list($lo, $hi) = alt_wilson_interval($matched, $ref);
    $out = array(
        'matched'   => $matched,
        'reference' => $ref,
        'pct'       => (int) round(100 * $matched / $ref),
        'lo_pct'    => (int) round(100 * $lo),
        'hi_pct'    => (int) round(100 * $hi),
    );
    $p = isset($j['precision_verbatim']) && is_array($j['precision_verbatim'])
        ? $j['precision_verbatim'] : null;
    if ($p && (int) ($p['checked'] ?? 0) > 0 && (int) ($p['ok'] ?? -1) >= 0
        && (int) $p['ok'] <= (int) $p['checked']) {
        $out['precision_ok'] = (int) $p['ok'];
        $out['precision_checked'] = (int) $p['checked'];
    }
    return $out;
}

/**
 * The ingest schedule, read from data/ingest-schedule.json — generated from
 * railway/railway.toml (the cron that actually runs) by
 * railway/generate_ingest_schedule.py, and drift-guarded by
 * tests/test_ingest_schedule.py. Same contract as alt_recall_measurement():
 * missing or malformed file returns null and every caller renders NOTHING,
 * because an absent schedule is honest and a stale typed one is not.
 */
function alt_ingest_schedule() {
    $path = ALT_PLUGIN_DIR . 'data/ingest-schedule.json';
    if (!is_readable($path)) return null;
    $j = json_decode((string) file_get_contents($path), true);
    if (!is_array($j) || empty($j['utc_hours']) || !is_array($j['utc_hours'])) return null;
    $hours = array();
    foreach ($j['utc_hours'] as $h) {
        $h = (int) $h;
        if ($h >= 0 && $h <= 23) $hours[] = $h;
    }
    if (!$hours) return null;
    sort($hours);
    $minute = (int) ($j['utc_minute'] ?? 0);
    if ($minute < 0 || $minute > 59) $minute = 0;
    return array('utc_hours' => array_values(array_unique($hours)), 'utc_minute' => $minute);
}

/** Next scheduled ingest as a UTC unix timestamp, or null without a schedule. */
function alt_next_ingest_utc() {
    $s = alt_ingest_schedule();
    if (!$s) return null;
    $now = time();
    for ($d = 0; $d <= 1; $d++) {
        foreach ($s['utc_hours'] as $h) {
            $t = gmmktime($h, $s['utc_minute'], 0,
                (int) gmdate('n', $now), (int) gmdate('j', $now) + $d, (int) gmdate('Y', $now));
            if ($t > $now) return $t;
        }
    }
    return null;
}

/**
 * "9 AM & 6 PM EDT" style label computed from the UTC schedule for today —
 * DST-correct by construction (the cron is UTC-fixed, so the Eastern clock
 * time shifts with daylight saving; the old typed label did not).
 */
function alt_ingest_times_label() {
    $s = alt_ingest_schedule();
    if (!$s) return '';
    try {
        $parts = array();
        $abbr = '';
        foreach ($s['utc_hours'] as $h) {
            $dt = new DateTime(gmdate('Y-m-d') . sprintf(' %02d:%02d', $h, $s['utc_minute']), new DateTimeZone('UTC'));
            $dt->setTimezone(new DateTimeZone('America/New_York'));
            $parts[] = $dt->format($s['utc_minute'] ? 'g:i A' : 'g A');
            $abbr = $dt->format('T');
        }
        return implode(' & ', $parts) . ' ' . $abbr;
    } catch (Exception $e) {
        return '';
    }
}

/** Shared coverage tally for the candidate response and the public endpoint. */
function alt_archive_coverage_counts() {
    global $wpdb;
    $layoffs = alt_db_table();
    $archive = alt_archive_table();
    $distinct_total = (int) $wpdb->get_var(
        "SELECT COUNT(DISTINCT source_url) FROM $layoffs WHERE source_url <> '' AND source_url LIKE 'http%'");
    $rows = $wpdb->get_results("SELECT status, COUNT(*) AS n FROM $archive GROUP BY status", ARRAY_A) ?: array();
    $by = array('archived' => 0, 'pending' => 0, 'unavailable' => 0);
    foreach ($rows as $row) {
        $s = (string) $row['status'];
        if (isset($by[$s])) $by[$s] = (int) $row['n'];
    }
    $archived = $by['archived'];
    // 'queued' is a source URL the layoffs table cites that has no archive row
    // yet: it enters the next daily backfill run automatically. Derived, never
    // stored, so it can briefly read low if the archive index still holds rows
    // for URLs whose layoff rows were purged — hence the max(0,...).
    $queued = max(0, $distinct_total - ($archived + $by['pending'] + $by['unavailable']));
    // The oldest last-attempt among URLs still awaiting a snapshot. This is the
    // number that makes the pages' "we re-check weekly" sentence falsifiable:
    // data_integrity's archive_recheck_cadence invariant reads it from the
    // public /archive-coverage endpoint and FAILS when it exceeds the cadence.
    // JOINED to the layoffs table on purpose: the archive index keeps rows for
    // URLs whose layoff rows were later purged or re-sourced, the backfill
    // correctly never retries those orphans (they are not candidates), and an
    // orphan's frozen timestamp must not redden a promise no page is making.
    // Same join shape the candidate query runs daily.
    $oldest = $wpdb->get_var(
        "SELECT MIN(a.checked_at)
           FROM $layoffs l
           JOIN $archive a ON a.url_hash = MD5(TRIM(l.source_url))
          WHERE l.source_url <> '' AND l.source_url LIKE 'http%'
            AND a.status IN ('pending','unavailable')");
    return array(
        'distinct_source_urls' => $distinct_total,
        'archived' => $archived,
        'pending' => $by['pending'],
        'unavailable' => $by['unavailable'],
        'queued' => $queued,
        'coverage_pct' => $distinct_total > 0 ? round(100 * $archived / $distinct_total, 1) : 0.0,
        'oldest_unarchived_checked_at' => $oldest ? (string) $oldest : null,
        'recheck_days' => (int) ALT_ARCHIVE_RECHECK_DAYS,
    );
}

/**
 * The next date (UTC, Y-m-d) the archive backfill will actually re-attempt a
 * source URL in the given state. DERIVED from the real schedule — the daily
 * archive-backfill run at ALT_ARCHIVE_DAILY_RUN_UTC, the 'pending' retry
 * spacing and the weekly 'unavailable' re-check — never typed, so the date a
 * reader sees is a promise the crons keep. A URL with no archive row yet
 * ('queued') is picked up by the next daily run.
 */
function alt_archive_next_check_date($status, $checked_at = '') {
    $now = time();
    $eligible = $now;
    $checked = $checked_at !== '' ? strtotime($checked_at . ' UTC') : false;
    if ($checked !== false && $checked > 0) {
        if ($status === 'pending') {
            $eligible = $checked + ALT_ARCHIVE_RETRY_HOURS * HOUR_IN_SECONDS;
        } elseif ($status === 'unavailable') {
            $eligible = $checked + ALT_ARCHIVE_RECHECK_DAYS * DAY_IN_SECONDS;
        }
    }
    if ($eligible < $now) $eligible = $now;
    list($run_h, $run_m) = array_map('intval', explode(':', ALT_ARCHIVE_DAILY_RUN_UTC));
    $run = gmmktime($run_h, $run_m, 0,
        (int) gmdate('n', $eligible), (int) gmdate('j', $eligible), (int) gmdate('Y', $eligible));
    if ($run < $eligible) $run += DAY_IN_SECONDS;
    return gmdate('Y-m-d', $run);
}

/** One archive-index row for a single source URL (the entry permalink page). */
function alt_archive_lookup($source_url) {
    global $wpdb;
    $source_url = trim((string) $source_url);
    if ($source_url === '' || strpos($source_url, 'http') !== 0) return null;
    $table = alt_archive_table();
    if ($wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) !== $table) {
        return null;
    }
    $row = $wpdb->get_row($wpdb->prepare(
        "SELECT archived_url, status, checked_at FROM $table WHERE url_hash = %s",
        alt_archive_url_key($source_url)), ARRAY_A);
    return is_array($row) ? $row : null;
}

/**
 * Reader-facing archive state for one row, shared by every server-rendered
 * listing surface (company pages, facet pages, entry permalinks) so they all
 * say the same thing the tracker's own cards do: the permanent Wayback link
 * when one exists, otherwise an honest note with the REAL next-check date.
 * Returns '' when the row has no archivable URL (e.g. a WARN row whose only
 * source is the state register link itself is still archived by URL, so it
 * gets the note too — '' is only for rows with no http source at all).
 */
function alt_archive_note_html(array $row) {
    $url = trim((string) ($row['source_url'] ?? ''));
    if ($url === '' || strpos($url, 'http') !== 0) return '';
    $archived = trim((string) ($row['archived_url'] ?? ''));
    if ($archived !== '') {
        return '<a href="' . esc_url($archived) . '" target="_blank" rel="noopener nofollow" '
            . 'title="A copy saved by the Internet Archive, for when the original page has moved or gone">'
            . 'Archived copy (Wayback Machine)</a>';
    }
    $next = alt_archive_next_check_date(
        (string) ($row['archive_status'] ?? 'queued'),
        (string) ($row['archive_checked_at'] ?? ''));
    return '<span class="alt-muted alt-archive-note">'
        . 'No archive snapshot yet. We re-check weekly; next check by ' . esc_html($next) . '.</span>';
}

/**
 * One-line, live archive-coverage summary for the methodology and health
 * pages. Every count is computed from the archive index at render time (held
 * in a 15-minute transient); nothing here is typed.
 */
function alt_archive_coverage_line_html() {
    $c = get_transient('alt_archive_cov_line');
    if (!is_array($c)) {
        if (!function_exists('alt_archive_coverage_counts')) return '';
        $c = alt_archive_coverage_counts();
        set_transient('alt_archive_cov_line', $c, 15 * MINUTE_IN_SECONDS);
    }
    if ((int) $c['distinct_source_urls'] <= 0) return '';
    $f = function ($n) { return number_format((int) $n); };
    return '<p class="alt-muted alt-archive-coverage"><b>Source-link preservation, measured live:</b> '
        . $f($c['archived']) . ' of ' . $f($c['distinct_source_urls'])
        . ' distinct source links (' . esc_html(number_format((float) $c['coverage_pct'], 1))
        . '%) have a permanent Internet Archive (Wayback Machine) snapshot. Of the rest, '
        . $f($c['queued']) . ' are queued for the next daily archiving run, '
        . $f($c['pending']) . ' have a capture requested and are retried every '
        . (int) (ALT_ARCHIVE_RETRY_HOURS / 24) . ' days, and '
        . $f($c['unavailable']) . ' are not in the Internet Archive yet and are re-checked weekly, '
        . 'forever. Rows without a snapshot say so on the page, with the date of their next check.</p>';
}

/**
 * Key-protected: record archive results. Body: { items: [ { url, archived_url,
 * status } ] }. Upserts one row per url_hash (dedup across shared WARN files is
 * free). status must be one of archived/pending/unavailable; an 'archived' item
 * must carry a real archived_url or it is downgraded to 'pending' (never fake a
 * link). Attempts increment so a URL that never archives becomes 'unavailable'
 * once the worker has tried it enough times, and is then reported honestly
 * instead of retried forever. Best-effort cache flush so freshly archived
 * links appear on the tracker.
 */
function alt_api_archive_record(WP_REST_Request $r) {
    global $wpdb;
    if (!alt_archive_table_ready()) {
        return new WP_Error('alt_db_error', 'Archive index unavailable after migration retry.', array('status' => 500));
    }
    $items = $r->get_param('items');
    if (!is_array($items)) return new WP_Error('alt_bad_request', 'items must be an array of {url, archived_url, status}.', array('status' => 400));
    if (count($items) > 2000) return new WP_Error('alt_bad_request', 'at most 2000 items per call.', array('status' => 400));
    $table = alt_archive_table();
    $now = gmdate('Y-m-d H:i:s');
    $out = array('archived' => 0, 'pending' => 0, 'unavailable' => 0, 'rejected' => array());
    $any_archived = false;
    foreach ($items as $item) {
        $url = trim((string) ($item['url'] ?? ''));
        if ($url === '' || strpos($url, 'http') !== 0) { $out['rejected'][] = $url; continue; }
        $status = (string) ($item['status'] ?? '');
        if (!in_array($status, array('archived', 'pending', 'unavailable'), true)) { $out['rejected'][] = $url; continue; }
        $archived_url = esc_url_raw(trim((string) ($item['archived_url'] ?? '')));
        // Never store an 'archived' status without a real permalink.
        if ($status === 'archived' && $archived_url === '') $status = 'pending';
        $hash = alt_archive_url_key($url);
        $existing = $wpdb->get_row($wpdb->prepare(
            "SELECT id, attempts FROM $table WHERE url_hash = %s", $hash));
        $attempts = ($existing ? (int) $existing->attempts : 0) + 1;
        // Don't retry forever: a URL that has failed to archive after this many
        // rounds is recorded 'unavailable' (dead / bot-walled) so it drops out
        // of the candidate query and is reported honestly rather than faked. A
        // worker may also send 'unavailable' outright on a definitive signal.
        if ($status === 'pending' && $attempts >= ALT_ARCHIVE_MAX_ATTEMPTS) $status = 'unavailable';
        $data = array(
            'source_url' => $url,
            'status' => $status,
            'attempts' => $attempts,
            'checked_at' => $now,
        );
        $fmt = array('%s', '%s', '%d', '%s');
        if ($status === 'archived') {
            $data['archived_url'] = $archived_url;
            $data['archived_at'] = $now;
            $fmt[] = '%s'; $fmt[] = '%s';
        }
        if ($existing) {
            $ok = $wpdb->update($table, $data, array('id' => (int) $existing->id), $fmt, array('%d'));
        } else {
            $data['url_hash'] = $hash;
            $fmt[] = '%s';
            $ok = $wpdb->insert($table, $data, $fmt);
        }
        if ($ok === false) {
            return new WP_Error('alt_db_error', 'Archive record failed for ' . $url . ': ' . $wpdb->last_error, array('status' => 500));
        }
        $out[$status] = ($out[$status] ?? 0) + 1;
        if ($status === 'archived') $any_archived = true;
    }
    $out['coverage'] = alt_archive_coverage_counts();
    // Newly archived links should appear on the tracker without waiting out the
    // server cache TTL. Best-effort; a failed flush never fails the record.
    if ($any_archived && function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

/** Public, read-only archive-coverage summary for the health page. */
function alt_api_archive_coverage() {
    global $wpdb;
    $table = alt_archive_table();
    if ($wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) !== $table) {
        return rest_ensure_response(array(
            'distinct_source_urls' => 0, 'archived' => 0, 'pending' => 0,
            'unavailable' => 0, 'queued' => 0, 'coverage_pct' => 0.0,
            'oldest_unarchived_checked_at' => null,
            'recheck_days' => (int) ALT_ARCHIVE_RECHECK_DAYS,
        ));
    }
    return rest_ensure_response(alt_archive_coverage_counts());
}

function alt_api_tips_get(WP_REST_Request $r) {
    $want = sanitize_key($r->get_param('status') ?: 'new');
    $per  = min(100, max(1, (int) ($r->get_param('per_page') ?: 25)));
    $q = get_option('alt_tips_queue');
    $q = is_array($q) ? $q : array();
    $out = array();
    foreach ($q as $t) {
        if (($t['status'] ?? 'new') === $want) { $out[] = $t; if (count($out) >= $per) break; }
    }
    return array('tips' => $out, 'total_new' => count(array_filter($q, function ($t) {
        return ($t['status'] ?? 'new') === 'new';
    })));
}

function alt_api_tips_post(WP_REST_Request $r) {
    $id = (string) $r->get_param('id');
    $status = sanitize_key((string) $r->get_param('status'));
    $note = substr((string) $r->get_param('note'), 0, 300);
    $allowed = array('new', 'posted', 'review', 'rejected', 'duplicate');
    if ($id === '' || !in_array($status, $allowed, true)) {
        return new WP_Error('alt_bad_request', 'id and a valid status are required.', array('status' => 400));
    }
    $q = get_option('alt_tips_queue');
    $q = is_array($q) ? $q : array();
    $found = false;
    foreach ($q as &$t) {
        if (($t['id'] ?? '') === $id) {
            $t['status'] = $status;
            if ($note) $t['note'] = $note;
            $t['processed'] = gmdate('c');
            $found = true;
            break;
        }
    }
    unset($t);
    if (!$found) return array('updated' => false, 'not_found' => $id);
    update_option('alt_tips_queue', $q, false);
    return array('updated' => true, 'id' => $id, 'status' => $status);
}

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
function alt_api_companies(WP_REST_Request $r) {
    global $wpdb;
    $table = $wpdb->prefix . 'alt_layoffs';
    $since = sanitize_text_field((string) $r->get_param('since'));   // YYYY-MM-DD
    $limit = min(50000, max(10, (int) ($r->get_param('limit') ?: 20000)));
    $q = trim((string) $r->get_param('q'));   // typeahead prefix/substring
    $has_since = (bool) preg_match('/^\d{4}-\d{2}-\d{2}$/', $since);
    $ckey = 'alt_companies_' . md5(($has_since ? $since : 'all') . '_' . $limit . '_' . strtolower($q));
    $cached = get_transient($ckey);
    if ($cached !== false) return new WP_REST_Response($cached, 200);
    // Typeahead: when a query is given, rank names that START with it first
    // (what a searcher expects) then any substring match, so "Cre" surfaces
    // "Cree Lighting" ahead of an incidental mid-name match.
    if ($q !== '') {
        $like = '%' . $wpdb->esc_like($q) . '%';
        $pre  = $wpdb->esc_like($q) . '%';
        $sql = $wpdb->prepare(
            "SELECT company FROM $table WHERE company <> '' AND company LIKE %s "
            . "GROUP BY company ORDER BY (company LIKE %s) DESC, MAX(layoff_date) DESC LIMIT %d",
            $like, $pre, $limit);
    } elseif ($has_since) {
        $sql = $wpdb->prepare("SELECT company FROM $table WHERE company <> '' AND layoff_date >= %s "
            . "GROUP BY company ORDER BY MAX(layoff_date) DESC LIMIT %d", $since, $limit);
    } else {
        $sql = $wpdb->prepare("SELECT company FROM $table WHERE company <> '' "
            . "GROUP BY company ORDER BY MAX(layoff_date) DESC LIMIT %d", $limit);
    }
    $rows = $wpdb->get_col($sql);
    $out = array('companies' => array_values(array_filter(array_map('strval', (array) $rows))),
                 'count' => is_array($rows) ? count($rows) : 0);
    set_transient($ckey, $out, HOUR_IN_SECONDS);
    return new WP_REST_Response($out, 200);
}

function alt_api_survey_benchmarks() {
    $records = get_option('alt_survey_benchmarks');
    if (!is_array($records)) return rest_ensure_response(array());
    // Legacy setup records predate report_month. Present one authoritative
    // record per official report month, preferring the newer record that
    // explicitly names that month. This does not rewrite history or totals;
    // it prevents an API consumer from mistaking a setup duplicate for a
    // second independent Survey publication.
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

function alt_api_survey_benchmark_post(WP_REST_Request $r) {
    $year = (int) $r->get_param('year');
    $report_month = (string) $r->get_param('report_month');
    if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $report_month)) $report_month = gmdate('Y-m');
    $reference_month = (string) $r->get_param('reference_month');
    if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $reference_month)) $reference_month = $report_month;
    $benchmark = max(0, (int) $r->get_param('survey_ai_jobs_ytd'));
    $benchmark_month = max(0, (int) $r->get_param('survey_ai_jobs_month'));
    $tracker = max(0, (int) $r->get_param('tracker_ai_primary_announced_us_employer_jobs_ytd'));
    $tracker_month = max(0, (int) $r->get_param('tracker_ai_primary_announced_us_employer_jobs_month'));
    $url = esc_url_raw($r->get_param('benchmark_url'));
    if ($year < 2015 || $year > 2100 || !$benchmark || !$url) {
        return new WP_Error('alt_bad_request', 'year, benchmark URL and positive Survey total are required.', array('status' => 400));
    }
    $records = get_option('alt_survey_benchmarks');
    if (!is_array($records)) $records = array();
    // One retained public comparator per official report month.
    $key = $report_month;
    $records[$key] = array(
        'year' => $year, 'reference_month' => $reference_month, 'report_month' => $report_month, 'recorded_at' => gmdate('c'), 'benchmark' => 'Announcement survey',
        'benchmark_url' => $url, 'survey_ai_jobs_ytd' => $benchmark,
        'survey_ai_jobs_month' => $benchmark_month,
        'tracker_ai_primary_announced_us_employer_jobs_month' => $tracker_month,
        'tracker_ai_primary_announced_us_employer_jobs_ytd' => $tracker,
        'tracker_ai_cited_announced_us_job_location_jobs_month' => max(0, (int) $r->get_param('tracker_ai_cited_announced_us_job_location_jobs_month')),
        'tracker_ai_cited_announced_us_job_location_jobs_ytd' => max(0, (int) $r->get_param('tracker_ai_cited_announced_us_job_location_jobs_ytd')),
        // All-cuts comparator pair (nullable: Survey totals parse
        // fail-soft, and older records predate these fields).
        'survey_total_jobs_month' => $r->get_param('survey_total_jobs_month') === null ? null : max(0, (int) $r->get_param('survey_total_jobs_month')),
        'survey_total_jobs_ytd' => $r->get_param('survey_total_jobs_ytd') === null ? null : max(0, (int) $r->get_param('survey_total_jobs_ytd')),
        'tracker_announced_us_employer_jobs_month' => $r->get_param('tracker_announced_us_employer_jobs_month') === null ? null : max(0, (int) $r->get_param('tracker_announced_us_employer_jobs_month')),
        'tracker_announced_us_employer_jobs_ytd' => $r->get_param('tracker_announced_us_employer_jobs_ytd') === null ? null : max(0, (int) $r->get_param('tracker_announced_us_employer_jobs_ytd')),
        'monthly_variance' => $benchmark_month ? round(($tracker_month - $benchmark_month) / $benchmark_month, 4) : null,
        'variance' => round(($tracker - $benchmark) / $benchmark, 4),
        'definition' => 'Strict AI pair: US employer + source-evidenced announcement date + announced + AI primary + canonical event, against Survey AI-attributed cuts. All-cuts pair: same strict gates without the AI requirement, against Survey total announced cuts. Diagnostic figure is not Survey-comparable.',
    );
    krsort($records); update_option('alt_survey_benchmarks', array_slice($records, 0, 24, true), false);
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

    $allowed = array('company', 'job_count', 'layoff_date', 'industry', 'country', 'employer_country', 'state', 'ai_explicit', 'ai_causation', 'confidence', 'review_status', 'announced', 'source_url', 'excerpt', 'reason_tags');
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
                case 'reason_tags':
                    $data[$k] = alt_db_pack_tags(array_values(array_intersect(
                        array_map('sanitize_key', (array) $v),
                        function_exists('alt_allowed_reason_tags') ? alt_allowed_reason_tags() : array()
                    )));
                    break;
                case 'company':     $data[$k] = alt_normalize_company_ws($v); break;
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
            // Filing/announcement date, kept alongside the effective date so
            // the tracker can bucket either way (structured WARN rows now carry
            // both). alt_db_upsert validates it and never blanks an existing
            // value on re-import.
            'announcement_date'  => $e['announcement_date'] ?? '',
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
    // Canonical-pointer repair: a WARN purge + reload deletes rows and
    // re-imports them with NEW ids while the bulk writer re-links them to the
    // retained events — leaving each event's canonical_layoff_id dangling at
    // the deleted id. Every canonical JOIN (company pages, sitemap, directory
    // admission counts, review queue) then misses those rows. Re-point each
    // dangling event at its lowest surviving row; events with no surviving
    // rows keep their retained reports and stay untouched.
    $events = alt_events_table();
    $repaired = (int) $wpdb->query(
        "UPDATE $events e
         JOIN (
             SELECT e2.id AS eid, MIN(l2.id) AS new_canon
             FROM $events e2
             LEFT JOIN $table lc ON lc.id = e2.canonical_layoff_id
             JOIN $table l2 ON l2.event_id = e2.id
             WHERE lc.id IS NULL
             GROUP BY e2.id
             LIMIT 20000
         ) fix ON fix.eid = e.id
         SET e.canonical_layoff_id = fix.new_canon");
    if ($repaired > 0 && function_exists('alt_flush_caches')) alt_flush_caches();
    $remaining = (int) $wpdb->get_var("SELECT COUNT(*) FROM $table WHERE event_id = 0");
    return rest_ensure_response(array('processed' => count($rows), 'last_id' => $last, 'remaining' => $remaining, 'canonical_repaired' => $repaired));
}

/**
 * Superset dedup: when a company-wide news/announced total AND its site-level
 * WARN rows document the SAME layoff, both currently sum into job totals (the
 * ~5% double-count concentrated in Spirit/Amazon/Verizon/Meta...). This marks
 * the smaller side of each overlap as a subset of the larger (most-complete)
 * primary row via `superset_of`, so one real event is counted ONCE.
 *
 * Conservative matching (never drops a standalone layoff): a group forms only
 * when, for one company_key, a news/erm/8K/press total of >=200 sits within 45
 * days of a WARN row and is >= half the sum of the WARN rows IN THAT WINDOW
 * (i.e. plausibly the same event). The larger of {news total, windowed WARN
 * sum} stays; the smaller side's rows get superset_of = primary id. Idempotent.
 * $dry_run reports without writing.
 *
 * The window is the whole point of pass (1) and it used to be applied
 * inconsistently, which is how the Spirit regression of 2026-07-30 happened:
 * "is there a WARN row within 45 days" was asked per row, but the >=50% test
 * and the marking both used the company's ALL-TIME WARN sum. That denominator
 * only ever grows, so every match sat on a fuse: Spirit's May-2026 news total
 * of 4,000 covers 6,109 jobs of May-2026 WARN sites, but was measured against
 * 8,922 jobs of Spirit WARN notices reaching back to 2020, and the moment that
 * all-time sum crossed 8,000 the news row silently stopped being a subset and
 * started stacking (+4,000, US-2026 7,069 -> 11,069). The same bug marked WARN
 * rows from unrelated YEARS as members of one news total in the other
 * direction. Both sides are now scoped to the +/-45-day window.
 *
 * 2.19.235 goes one step further and makes the mistake unwritable rather than
 * merely fixed: pass (1) can no longer compute a sum at all. Its denominator
 * comes only from alt_dedup_window(), whose constructor IS the window filter,
 * and the >=50% verdict lives only in alt_dedup_subset_verdict(), which throws
 * if handed anything that is not window-scoped. `$warn` — the company's whole
 * history — stays in scope for grouping and is never summed.
 */
// The widest window a superset denominator may ever span. A "window" of two
// years is not a window; it is an all-time sum wearing a parameter.
if (!defined('ALT_DEDUP_MAX_WINDOW_DAYS')) define('ALT_DEDUP_MAX_WINDOW_DAYS', 200);
// The window pass (1) actually uses. One number, one place.
if (!defined('ALT_DEDUP_WINDOW_DAYS')) define('ALT_DEDUP_WINDOW_DAYS', 45);

/**
 * The ONLY legal way to build a denominator for a superset plausibility test.
 *
 * WHY THIS FUNCTION EXISTS AT ALL. On 2026-07-30 the reconciler asked "is there
 * a WARN row within ±45 days of this news report" per row, and then tested
 * plausibility — and marked rows — against the company's ALL-TIME WARN sum. The
 * numerator described a fortnight; the denominator described six years. That
 * sum only ever grows, so every already-matched pair sat on a fuse: Spirit's
 * margin was 38 jobs, and the day the all-time sum crossed 8,000 the news row
 * silently stopped being a subset and started stacking (+4,000 on a published
 * page). 64 companies were double-counting 60,367 jobs and 43 companies had
 * 113,786 real jobs suppressed to zero, Boeing's genuine 17,000 among them.
 *
 * The 2.19.227 fix scoped the comparison correctly. It did not stop anyone
 * writing the same line again, because the unwindowed row set was still sitting
 * in scope one variable away. THIS is what stops it: the constructor of the
 * denominator IS the window filter. There is no argument you can pass to get an
 * unwindowed sum out of it, no default window, and a window wide enough to be
 * an all-time sum in disguise is rejected outright.
 *
 * Returns a WINDOW: rows inside it, their sum, the largest of them, and the
 * scope that produced them, carried together so a later comparison cannot lose
 * track of what the number describes.
 *
 * @throws InvalidArgumentException on a missing centre or an absent/absurd window.
 */
function alt_dedup_window(array $rows, $center_date, $window_days) {
    $center = $center_date ? strtotime((string) $center_date) : false;
    if ($center === false) {
        throw new InvalidArgumentException(
            'alt_dedup_window: a window needs a centre date. Got ' . var_export($center_date, true));
    }
    $days = (int) $window_days;
    if ($days <= 0 || $days > ALT_DEDUP_MAX_WINDOW_DAYS) {
        throw new InvalidArgumentException(
            'alt_dedup_window: window_days must be 1..' . ALT_DEDUP_MAX_WINDOW_DAYS . ', got ' . $days
            . '. A denominator that spans everything is the 2026-07-30 Spirit defect.');
    }
    $in = array(); $sum = 0; $largest = null;
    foreach ($rows as $row) {
        $t = empty($row['layoff_date']) ? false : strtotime((string) $row['layoff_date']);
        if ($t === false) continue;
        if (abs(($center - $t) / 86400) > $days) continue;
        $in[] = $row;
        $sum += (int) $row['job_count'];
        if (!$largest || (int) $row['job_count'] > (int) $largest['job_count']) $largest = $row;
    }
    return array(
        'rows'        => $in,
        'sum'         => $sum,
        'largest'     => $largest,
        'window_days' => $days,
        'center'      => (string) $center_date,
        'scoped'      => true,   // the marker alt_dedup_subset_verdict demands
    );
}

/**
 * Is $candidate_jobs plausibly the same event as the rows in $window?
 *
 * The ≥50% test and the primary/member decision live here and NOWHERE else, and
 * this function refuses to answer unless its denominator came out of
 * alt_dedup_window(). Hand it a plain array — an all-time sum, a company total,
 * anything not window-scoped — and it throws rather than returning a verdict
 * that looks right and is measured against the wrong thing.
 *
 * Returns '' (no verdict: nothing in the window, or not plausibly the same
 * event), 'candidate_is_primary' (the candidate is the most-complete figure, so
 * the window's rows are its subsets) or 'candidate_is_member' (the window is
 * more complete, so the candidate is the subset).
 *
 * @throws InvalidArgumentException when the denominator is not window-scoped.
 */
function alt_dedup_subset_verdict($candidate_jobs, $window, $min_share = 0.5) {
    if (!is_array($window) || empty($window['scoped']) || empty($window['window_days'])) {
        throw new InvalidArgumentException(
            'alt_dedup_subset_verdict: the denominator must come from alt_dedup_window(). '
            . 'A cumulative or company-total sum is not a denominator for a plausibility test — '
            . 'that is the 2026-07-30 Spirit defect, and it published a wrong number for months.');
    }
    $sum = (int) $window['sum'];
    if ($sum <= 0 || !$window['rows']) return '';
    if ((int) $candidate_jobs < $sum * $min_share) return '';
    return ((int) $candidate_jobs >= $sum) ? 'candidate_is_primary' : 'candidate_is_member';
}

function alt_reconcile_supersets($dry_run = true, $detail = false, $probe = '') {
    global $wpdb;
    $table = alt_db_table();
    $rows = $wpdb->get_results(
        "SELECT id, company, company_key, source_type, job_count, layoff_date, ai_explicit, state, superset_of
         FROM $table WHERE company_key <> '' AND job_count > 0 AND edited = 0", ARRAY_A) ?: array();
    $by = array();
    $before = 0;
    foreach ($rows as $r) { $before += (int) $r['job_count']; $by[$r['company_key']][] = $r; }
    $mark = array();      // member id => primary id (the row it's a subset of)
    $excluded = 0;
    // EDGAR writes source_type '8K' (uppercase — see sources/edgar.py and the
    // 8K literals elsewhere in this file). A strict in_array against '8k' never
    // matched, so every SEC filing was invisible to this dedup and an 8-K
    // company-wide total stacked on its own WARN sites forever. Compare folded.
    $news_types = array('news', 'erm', '8k', 'press_release');
    foreach ($by as $grp) {
        $warn = array(); $news = array();
        foreach ($grp as $r) {
            $st = strtolower((string) $r['source_type']);
            if ($st === 'warn' && $r['layoff_date']) {
                $warn[] = $r;
            } elseif (in_array($st, $news_types, true) && $r['layoff_date']) {
                $news[] = $r;
            }
        }
        // (1) A news/announced company-wide total sitting on top of its own
        //     site-level WARN rows (Spirit/Amazon/Verizon...). Both the test and
        //     the marking use ONLY the WARN rows within +/-45 days of the news
        //     report — the rows that actually document the same event.
        if ($warn && $news) {
            foreach ($news as $nr) {
                $nc = (int) $nr['job_count'];
                if ($nc < 200) continue;
                // The denominator is CONSTRUCTED by the window, not filtered
                // after the fact: alt_dedup_window() is the only thing here that
                // can produce a sum, and it cannot produce an unwindowed one.
                // $warn (the company's whole history) is deliberately never
                // summed in this scope — see the Spirit note on those helpers.
                $near = alt_dedup_window($warn, $nr['layoff_date'], ALT_DEDUP_WINDOW_DAYS);
                $verdict = alt_dedup_subset_verdict($nc, $near);
                if ($verdict === '') continue;         // nothing near, or not the same event
                if ($verdict === 'candidate_is_primary') {
                    // News total is the most-complete figure -> exclude the WARN sites.
                    foreach ($near['rows'] as $w) {
                        if (empty($mark[$w['id']])) { $mark[$w['id']] = (int) $nr['id']; $excluded += (int) $w['job_count']; }
                    }
                } else {
                    // Windowed WARN sum is more complete -> exclude the news total.
                    if (empty($mark[$nr['id']])) { $mark[$nr['id']] = (int) $near['largest']['id']; $excluded += $nc; }
                }
            }
        }
        // (2) news-vs-news duplicate: the SAME company + the EXACT SAME headcount
        //     within ~150 days is the same event reported twice (announcement +
        //     later coverage), which the ±30-day fuzzy dedup misses — e.g.
        //     Coinbase 700 on both May 5 (announced/AI) and Jul 24. Keep the
        //     richest row (AI-flagged, else earliest date); mark the rest a subset.
        if (count($news) >= 2) {
            $by_count = array();
            foreach ($news as $nr) {
                if (!empty($mark[$nr['id']])) continue;   // already a subset of a WARN primary
                $by_count[(int) $nr['job_count']][] = $nr;
            }
            foreach ($by_count as $dupes) {
                if (count($dupes) < 2) continue;
                usort($dupes, function ($a, $b) {
                    $ai = (int) $b['ai_explicit'] - (int) $a['ai_explicit'];   // AI-flagged wins the primary slot
                    if ($ai) return $ai;
                    $d = strcmp((string) $a['layoff_date'], (string) $b['layoff_date']);  // else earliest date
                    return $d !== 0 ? $d : ((int) $a['id'] - (int) $b['id']);
                });
                $primary = $dupes[0];
                for ($i = 1, $n = count($dupes); $i < $n; $i++) {
                    $m = $dupes[$i];
                    if (abs((strtotime($m['layoff_date']) - strtotime($primary['layoff_date'])) / 86400) > 150) continue;
                    if (empty($mark[$m['id']])) { $mark[$m['id']] = (int) $primary['id']; $excluded += (int) $m['job_count']; }
                }
            }
        }
        // (3) within-WARN duplicate: same company + same STATE + EXACT same count
        //     (>=100) within ~90 days is a notice + its refiled revision, not two
        //     real events (Tyson: 1,761 Amarillo TX on both Jan 20 and Feb 24).
        //     Keep the earliest; mark the rest. The >=100 floor protects the
        //     legitimately-coincidental tiny multi-site filings (six sites of "2").
        if (count($warn) >= 2) {
            $wkey = array();
            foreach ($warn as $w) {
                if (!empty($mark[$w['id']]) || (int) $w['job_count'] < 100) continue;
                $wkey[$w['state'] . '|' . (int) $w['job_count']][] = $w;
            }
            foreach ($wkey as $dupes) {
                if (count($dupes) < 2) continue;
                usort($dupes, function ($a, $b) {
                    $d = strcmp((string) $a['layoff_date'], (string) $b['layoff_date']);
                    return $d !== 0 ? $d : ((int) $a['id'] - (int) $b['id']);
                });
                $primary = $dupes[0];
                for ($i = 1, $n = count($dupes); $i < $n; $i++) {
                    $m = $dupes[$i];
                    if (abs((strtotime($m['layoff_date']) - strtotime($primary['layoff_date'])) / 86400) > 90) continue;
                    if (empty($mark[$m['id']])) { $mark[$m['id']] = (int) $primary['id']; $excluded += (int) $m['job_count']; }
                }
            }
        }
    }
    // What this run CHANGES versus what is already stored. The marking is a
    // clean-slate recompute, so a silent drift (a pair that quietly stops
    // matching and starts double-counting, which is exactly how the Spirit
    // regression went unseen) shows up here as a non-zero `changes` on a day
    // nothing should have moved. Cheap to compute, and it makes a dry-run a
    // real diff instead of three totals.
    $changed = array();
    foreach ($rows as $r) {
        $now = isset($mark[$r['id']]) ? (int) $mark[$r['id']] : 0;
        $was = (int) $r['superset_of'];
        if ($now === $was) continue;
        $changed[] = array(
            'id'          => (int) $r['id'],
            'company'     => (string) $r['company'],
            'company_key' => (string) $r['company_key'],
            'layoff_date' => $r['layoff_date'],
            'state'       => (string) $r['state'],
            'source_type' => (string) $r['source_type'],
            'job_count'   => (int) $r['job_count'],
            'was'         => $was,
            'now'         => $now,
        );
    }
    if (!$dry_run) {
        $wpdb->query("UPDATE $table SET superset_of = 0 WHERE superset_of <> 0");  // clean slate, then re-mark
        foreach ($mark as $id => $primary) {
            $wpdb->update($table, array('superset_of' => (int) $primary), array('id' => (int) $id));
        }
        if (function_exists('alt_flush_caches')) alt_flush_caches();
    }
    $out = array(
        'dry_run'        => (bool) $dry_run,
        'members_marked' => count($mark),
        'jobs_before'    => (int) $before,
        'jobs_excluded'  => (int) $excluded,
        'jobs_after'     => (int) ($before - $excluded),
        'changes'        => count($changed),
    );
    // Bounded: this is an ops diagnostic on a keyed endpoint, not a data feed.
    // Compare `changes` against count($out['changed']) before reading the list
    // as complete — a truncated list once made a working fix look broken.
    if ($detail) $out['changed'] = array_slice($changed, 0, 2000);
    // `probe` answers the question this function could never be asked before:
    // what does the reconciler actually SEE for one employer? It shows the rows
    // it loaded, the company_key it grouped them under (rows that look like the
    // same employer but key differently never meet), and the mark each one
    // gets. Working that out from the outside cost most of a session.
    if ($probe !== '') {
        $hits = array();
        foreach ($rows as $r) {
            if (stripos((string) $r['company'], $probe) === false) continue;
            $hits[] = array(
                'id'          => (int) $r['id'],
                'company'     => (string) $r['company'],
                'company_key' => (string) $r['company_key'],
                'layoff_date' => $r['layoff_date'],
                'state'       => (string) $r['state'],
                'source_type' => (string) $r['source_type'],
                'job_count'   => (int) $r['job_count'],
                'was'         => (int) $r['superset_of'],
                'now'         => isset($mark[$r['id']]) ? (int) $mark[$r['id']] : 0,
            );
            if (count($hits) >= 200) break;
        }
        $out['probed'] = $hits;
    }
    return $out;
}

/** Key-protected. Default DRY-RUN; pass apply=1 to actually mark rows. */
function alt_api_reconcile_supersets(WP_REST_Request $r) {
    $dry = $r->get_param('apply') !== '1';
    return rest_ensure_response(alt_reconcile_supersets(
        $dry, $r->get_param('detail') === '1', (string) $r->get_param('probe')));
}

/** Public: return the cached unemployment-claims backdrop payload (or empty). */
function alt_api_claims_get() {
    $data = get_option('alt_claims_data', array());
    return rest_ensure_response(is_array($data) ? $data : array());
}

/** Key-protected: store the claims payload built by railway/sources/claims.py. */
function alt_api_claims_ingest(WP_REST_Request $r) {
    $body = $r->get_json_params();
    if (!is_array($body) || empty($body['national'])) {
        return new WP_Error('alt_bad_request', 'Expected a claims payload with a national series.', array('status' => 400));
    }
    update_option('alt_claims_data', $body, false);
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response(array(
        'stored'          => true,
        'updated'         => isset($body['updated']) ? $body['updated'] : gmdate('c'),
        'national_months' => is_array($body['national']['initial'] ?? null) ? count($body['national']['initial']) : 0,
        'states'          => is_array($body['states'] ?? null) ? count($body['states']) : 0,
    ));
}

/**
 * Working memory for the competitor-weaning loop. Merge-and-return: the caller
 * POSTs {add_resolved: [names], add_wins: {domain: n}, record_ind: {d, ind, total}}
 * (any subset) and always receives the full state back, so one keyed call both
 * reads and writes. Bounded: resolved and win domains are maps (no unbounded
 * growth per run), the independence history keeps the last 180 daily points.
 */
function alt_api_tracker_meta(WP_REST_Request $r) {
    $body = $r->get_json_params();
    if (!is_array($body)) $body = array();
    $meta = get_option('alt_tracker_meta');
    if (!is_array($meta)) $meta = array();
    $meta += array('resolved' => array(), 'wins' => array(), 'ind_history' => array());
    foreach ((array) ($body['add_resolved'] ?? array()) as $name) {
        $k = sanitize_text_field((string) $name);
        if ($k !== '' && !isset($meta['resolved'][$k])) $meta['resolved'][$k] = gmdate('Y-m-d');
    }
    foreach ((array) ($body['add_wins'] ?? array()) as $domain => $n) {
        $d = sanitize_text_field((string) $domain);
        if ($d !== '') $meta['wins'][$d] = (int) ($meta['wins'][$d] ?? 0) + max(1, (int) $n);
    }
    // Bound the maps, not just the history: wins keys carry an outlet+country
    // suffix (higher cardinality), and resolved grows with every chase. Keep
    // the most recent 500 resolved and the 300 highest win counts.
    if (count($meta['resolved']) > 500) {
        arsort($meta['resolved']);                       // newest dates first
        $meta['resolved'] = array_slice($meta['resolved'], 0, 500, true);
    }
    if (count($meta['wins']) > 300) {
        arsort($meta['wins']);                           // biggest counts first
        $meta['wins'] = array_slice($meta['wins'], 0, 300, true);
    }
    if (!empty($body['record_ind']) && is_array($body['record_ind'])) {
        $pt = array(
            'd'     => sanitize_text_field((string) ($body['record_ind']['d'] ?? gmdate('Y-m-d'))),
            'ind'   => (float) ($body['record_ind']['ind'] ?? 0),
            'total' => (float) ($body['record_ind']['total'] ?? 0),
        );
        // one point per day: replace today's entry instead of appending twice
        $meta['ind_history'] = array_values(array_filter($meta['ind_history'],
            function ($p) use ($pt) { return ($p['d'] ?? '') !== $pt['d']; }));
        $meta['ind_history'][] = $pt;
        $meta['ind_history'] = array_slice($meta['ind_history'], -180);
    }
    // Per-run spend records from the Railway cron. Railway can neither commit
    // nor be log-harvested, so cron.py posts each run's metered cost (with a
    // per-collector breakdown) here, and spend.py --harvest in the daily
    // balance job reads them back into the committed railway/spend_jobs.json.
    // Whitelisted scalar fields + a bounded numeric 'sources' map; keyed by
    // run_id so a re-post replaces rather than duplicates. Last 240 runs
    // (~4 months at 2/day) — a ledger, not an archive.
    if (!isset($meta['spend_runs']) || !is_array($meta['spend_runs'])) {
        $meta['spend_runs'] = array();
    }
    if (!empty($body['add_spend_run']) && is_array($body['add_spend_run'])) {
        $in  = $body['add_spend_run'];
        $rec = array(
            'job'    => sanitize_text_field((string) ($in['job'] ?? 'railway-cron')),
            'date'   => sanitize_text_field((string) ($in['date'] ?? gmdate('Y-m-d'))),
            'run_id' => sanitize_text_field((string) ($in['run_id'] ?? '')),
            'cost_usd' => round((float) ($in['cost_usd'] ?? 0), 6),
            'calls'  => (int) ($in['calls'] ?? 0),
            'prompt_tokens'     => (int) ($in['prompt_tokens'] ?? 0),
            'completion_tokens' => (int) ($in['completion_tokens'] ?? 0),
        );
        foreach (array('cached_prompt_tokens', 'items', 'stored', 'changed',
                       'gate_false_drops') as $k) {
            if (isset($in[$k]) && is_numeric($in[$k])) $rec[$k] = (int) $in[$k];
        }
        if (!empty($in['gate_mode'])) {
            $rec['gate_mode'] = sanitize_text_field((string) $in['gate_mode']);
        }
        if ($rec['run_id'] === '') $rec['run_id'] = $rec['date'] . 'T' . gmdate('Hi');
        if (!empty($in['sources']) && is_array($in['sources'])) {
            $sources = array();
            foreach (array_slice($in['sources'], 0, 20, true) as $name => $s) {
                if (!is_array($s)) continue;
                $row = array(
                    'cost_usd' => round((float) ($s['cost_usd'] ?? 0), 6),
                    'calls'    => (int) ($s['calls'] ?? 0),
                    'kept'     => (int) ($s['kept'] ?? 0),
                    'dropped'  => (int) ($s['dropped'] ?? 0),
                );
                foreach (array('items', 'stored') as $sk) {
                    if (isset($s[$sk]) && is_numeric($s[$sk])) $row[$sk] = (int) $s[$sk];
                }
                $sources[sanitize_text_field((string) $name)] = $row;
            }
            if ($sources) $rec['sources'] = $sources;
        }
        $meta['spend_runs'] = array_values(array_filter($meta['spend_runs'],
            function ($p) use ($rec) { return ($p['run_id'] ?? '') !== $rec['run_id']; }));
        $meta['spend_runs'][] = $rec;
        $meta['spend_runs'] = array_slice($meta['spend_runs'], -240);
    }
    update_option('alt_tracker_meta', $meta, false);
    return rest_ensure_response($meta);
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

    // Role categories for legacy rows whose STATED roles text is keyword-
    // mappable (new rows derive at upsert time). One UPDATE per distinct
    // freeform value; rows whose roles live only in the excerpt stay blank
    // here — the bounded evidence-only backfill owns those.
    if (function_exists('alt_normalize_roles')) {
        $changed['role_categories'] = 0;
        $role_values = $wpdb->get_col("SELECT DISTINCT roles FROM $table WHERE COALESCE(roles,'') <> '' AND role_categories = ''");
        foreach ($role_values ?: array() as $roles_text) {
            $packed = alt_db_pack_tags(alt_normalize_roles($roles_text));
            if ($packed !== '') {
                $changed['role_categories'] += (int) $wpdb->query($wpdb->prepare(
                    "UPDATE $table SET role_categories = %s WHERE roles = %s AND role_categories = ''",
                    $packed, $roles_text));
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
 * Two layers add nocache headers to REST responses; each needs its own fix.
 *
 * 1. WP-side (core nocache + any cache plugin calling nocache_headers()):
 *    suppressed by the two filters below for anonymous reads on the public
 *    endpoints.
 * 2. Bluehost's Apache appends "Cache-Control: no-cache, no-store,
 *    must-revalidate" + "Pragma: no-cache" + "Expires: 0" AFTER PHP's headers
 *    on every PHP response — producing a DUPLICATE Cache-Control that makes
 *    browsers treat the response as no-store. Proven host-side, not WP-side
 *    (2026-07-19): a direct request to a plugin file that exits before WP
 *    loads still carries the trio, and so does an origin-direct curl that
 *    bypasses Cloudflare and the Railway root proxy. No PHP filter can strip
 *    it; alt_htaccess_ensure() (includes/htaccess.php) overrides it with a
 *    mod_headers block in the WP root .htaccess, which Apache merges after
 *    its own config.
 */
function alt_is_public_read_request() {
    if (is_user_logged_in()) return false;
    // HEAD mirrors GET cacheability (RFC 9110); everything else stays nocache.
    if (!in_array($_SERVER['REQUEST_METHOD'] ?? '', array('GET', 'HEAD'), true)) return false;
    $uri = $_SERVER['REQUEST_URI'] ?? '';
    foreach (array('query', 'aggregate', 'facets', 'stats', 'all', 'conversion') as $ep) {
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
        set_transient($key, $payload, 30 * MINUTE_IN_SECONDS);
    }
    $resp = rest_ensure_response($payload);
    // The expensive compute (esp. /aggregate: ~30 SQL statements over 100K+ rows)
    // is cached SERVER-side for 30 minutes, so a normal visitor almost never lands
    // on a cold recompute — the main cause of the slow first load. The browser/edge
    // Cache-Control stays at 5 minutes, so edge staleness after a data write is
    // unchanged. A data-changing write bumps alt_data_ver, which changes every
    // transient key immediately, so a longer server TTL can never serve a number a
    // write has superseded (bounded by writes, not by TTL).
    $resp->header('Cache-Control', 'public, max-age=300, s-maxage=300, stale-while-revalidate=600');
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
    // ascending date sorts, burying real oldest entries under blanks). On the
    // default "newest first" (DESC), FUTURE-effective rows (upcoming WARN dates,
    // announced plans dated months out) also sort LAST — otherwise a 2026-12-31
    // effective date tops the table and a skimming reporter mistakes a future
    // plan for today's news. They stay visible (and flagged "upcoming"), just
    // below the most recent layoffs that have actually happened.
    if ($sort === 'layoff_date') {
        $order = ($dir === 'DESC')
            ? "(layoff_date IS NULL) ASC, (layoff_date > CURDATE()) ASC, layoff_date DESC, id DESC"
            : "(layoff_date IS NULL) ASC, layoff_date ASC, id DESC";
    } else {
        $order = "$sort $dir, id DESC";
    }
    $rows = $wpdb->get_results(alt_db_prep(
        "SELECT * FROM $table WHERE $where ORDER BY $order LIMIT %d OFFSET %d",
        array_merge($params, array($per, $offset))
    ));

    return array(
        'total'    => $total,
        'page'     => $page,
        'per_page' => $per,
        'data'     => alt_attach_archived_urls(alt_attach_event_sources(array_map('alt_db_row_to_array', $rows ?: array()))),
    );
}

/**
 * A short human location for a row: the US state code where present, otherwise
 * the (non-US) country. Deliberately NOT city-level — state + country is enough
 * to show that several rows for one company are distinct filings. Returns ''
 * when only a generic country is known, so callers can omit it.
 */
function alt_short_location($state, $country) {
    $state = strtoupper(trim((string) $state));
    $country = trim((string) $country);
    if ($state !== '') return $state;
    if ($country !== '' && strcasecmp($country, 'United States') !== 0
        && strcasecmp($country, 'Multiple countries') !== 0) {
        return $country;
    }
    return '';
}

/**
 * Attach each row's OTHER retained sources for the same event as
 * `additional_sources` (so a merged event shows, e.g., the official WARN
 * notice AND the news article that corroborated it — not just the one primary
 * link). One batched query over the page's event_ids (the company-directory
 * pattern), never a per-row query. A source is "additional" when its URL is
 * non-empty and differs from the row's own primary source_url (and its state
 * WARN list URL, which already renders separately); duplicate URLs collapse.
 */
function alt_attach_event_sources(array $data) {
    if (!$data) return $data;
    global $wpdb;
    $reports = alt_source_reports_table();
    $event_ids = array();
    foreach ($data as $row) {
        if (!empty($row['event_id'])) $event_ids[(int) $row['event_id']] = true;
    }
    if (!$event_ids) return $data;
    $ids = array_keys($event_ids);
    $ph = implode(',', array_fill(0, count($ids), '%d'));
    $found = $wpdb->get_results($wpdb->prepare(
        "SELECT event_id, source_name, source_type, source_url FROM $reports
          WHERE event_id IN ($ph) AND source_url <> '' ORDER BY id ASC", $ids), ARRAY_A) ?: array();
    $by_event = array();
    foreach ($found as $rep) {
        $by_event[(int) $rep['event_id']][] = $rep;
    }
    foreach ($data as &$row) {
        $row['additional_sources'] = array();
        $eid = (int) ($row['event_id'] ?? 0);
        if (!$eid || empty($by_event[$eid])) continue;
        // The row's own primary link and (for WARN) its state list link already
        // render on their own; don't repeat them in the corroboration list.
        $seen = array();
        foreach (array($row['source_url'] ?? '', $row['source_list_url'] ?? '') as $u) {
            if ($u !== '') $seen[$u] = true;
        }
        foreach ($by_event[$eid] as $rep) {
            $url = (string) $rep['source_url'];
            if ($url === '' || isset($seen[$url])) continue;
            $seen[$url] = true;
            $row['additional_sources'][] = array(
                'source_name' => (string) $rep['source_name'],
                'source_type' => (string) $rep['source_type'],
                'source_url'  => $url,
            );
        }
    }
    unset($row);
    return $data;
}

/**
 * Attach each row's permanent Internet Archive (Wayback) snapshot as
 * `archived_url` when one exists. One batched, indexed lookup over the page's
 * distinct source URLs (the alt_attach_event_sources pattern) — never a
 * per-row query. Rows whose source is not yet archived simply carry no
 * `archived_url`, so the front-end shows the second link only when it resolves
 * (never a broken link). Fail-open: if the archive table is missing or the
 * lookup errors, every row is returned unchanged.
 */
function alt_attach_archived_urls(array $data) {
    if (!$data) return $data;
    global $wpdb;
    $table = alt_archive_table();
    // Guard against the deploy race (table not yet created): read the schema
    // rather than self-heal here — this is a hot read path, and a missing
    // second link is harmless until the next backfill fills it in.
    if ($wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) !== $table) {
        return $data;
    }
    // Collect the distinct source URLs on this page and map each to its hash.
    $by_hash = array();
    foreach ($data as $row) {
        $url = trim((string) ($row['source_url'] ?? ''));
        if ($url !== '' && strpos($url, 'http') === 0) {
            $by_hash[alt_archive_url_key($url)] = true;
        }
    }
    if (!$by_hash) return $data;
    $hashes = array_keys($by_hash);
    $ph = implode(',', array_fill(0, count($hashes), '%s'));
    // Fetch ALL statuses (not just archived) + the last-checked timestamp, so a
    // row without a Wayback copy yet can show an honest, dated disclaimer instead
    // of nothing: "no permanent archive yet, re-checked weekly, last checked X".
    $found = $wpdb->get_results($wpdb->prepare(
        "SELECT url_hash, archived_url, status, checked_at FROM $table
          WHERE url_hash IN ($ph)", $hashes), ARRAY_A) ?: array();
    $snap = array();
    foreach ($found as $r) { $snap[$r['url_hash']] = $r; }
    foreach ($data as &$row) {
        $url = trim((string) ($row['source_url'] ?? ''));
        if ($url === '' || strpos($url, 'http') !== 0) continue;
        $h = alt_archive_url_key($url);
        if (isset($snap[$h])) {
            $rec = $snap[$h];
            if (($rec['status'] ?? '') === 'archived' && !empty($rec['archived_url'])) {
                $row['archived_url'] = $rec['archived_url'];
            }
            $row['archive_status'] = (string) ($rec['status'] ?? 'queued');
            $row['archive_checked_at'] = (string) ($rec['checked_at'] ?? '');
        } else {
            // Has a source URL but no archive attempt recorded yet — it enters
            // the backfill queue automatically and is captured on the next run.
            $row['archive_status'] = 'queued';
            $row['archive_checked_at'] = '';
        }
    }
    unset($row);
    return $data;
}

function alt_api_aggregate(WP_REST_Request $r) {
    return alt_api_cached('aggregate', $r, function () use ($r) {
        return alt_api_aggregate_compute($r);
    });
}

/**
 * The blocks alt_api_aggregate_compute() can build, as an opt-in list.
 *
 * WHY THIS EXISTS. The full aggregate is ~31 SQL statements, and most of them
 * are per-tag loops nothing but the tracker's own charts read: `reasons` is 10
 * separate SUMs, `top_roles` is one per role category, and `map_states` /
 * `map_countries` re-run `top_states` / `top_countries` at a bigger LIMIT. On
 * the flagship page that is paid once and cached; measured against production
 * on 2026-08-01 it is 8.1s for `country=United States` and 19.0s with the
 * `sourced=1` evidence gate, against a shared host that returned 504 twice on
 * 2026-07-31. A server-rendered facet page cannot wear that on a cold cache.
 *
 * `totals` is not optional: every other block is reported against it, and a
 * caller that could drop the denominator while keeping a numerator is the
 * scope-mixing this file spent 2026-07-30 removing.
 *
 * DEFAULT IS EVERYTHING THAT EXISTED BEFORE THIS PARAM. `include` is read only
 * from an explicit request param, so /aggregate with no `include` returns
 * byte-identical output to before.
 *
 * `facet_counts` is the one exception and is OPT-IN ONLY. It is new, nothing
 * that reads /aggregate today expects it, and it is three grouped COUNTs over
 * the whole table. Defaulting it on would have put that cost on the flagship
 * tracker page's cold aggregate to serve a block only the facet-page sitemap
 * reads. A new block should earn its place in the default, not inherit it.
 */
function alt_aggregate_blocks() {
    return array_merge(alt_aggregate_default_blocks(), array('facet_counts'));
}

function alt_aggregate_default_blocks() {
    return array('concentration', 'top_industries', 'top_countries', 'top_states',
                 'map_states', 'map_countries', 'top_roles', 'source_types',
                 'reasons', 'series', 'leaders', 'repeat_companies');
}

function alt_api_aggregate_compute(WP_REST_Request $r) {
    global $wpdb;
    $table = alt_db_table();
    // Opt-in block list. An unrecognised name is dropped rather than honoured,
    // so a typo narrows nothing silently — it is simply not in the allowlist,
    // and an `include` that names no valid block falls back to everything.
    $include = null;
    $raw_include = (string) $r->get_param('include');
    if ($raw_include !== '') {
        $asked = array_filter(array_map('sanitize_key', explode(',', $raw_include)));
        $valid = array_values(array_intersect($asked, alt_aggregate_blocks()));
        if ($valid) $include = $valid;
    }
    $want = function ($block) use ($include) {
        return in_array($block, $include === null ? alt_aggregate_default_blocks() : $include, true);
    };
    list($where, $params) = alt_db_where($r);
    // Superset-deduped WHERE: excludes rows marked as a subset of the same
    // event's primary (a company-wide news total sitting on top of its WARN
    // sites, or vice versa), so JOB TOTALS count each event once. Applied to the
    // headline, the bar-list breakdowns, and the monthly series — but NOT to the
    // largest-single-rows list or the repeat-rounds (frequency) view, which are
    // row-level and would lose real site-level detail if members were hidden.
    $where_dd = $where . ' AND superset_of = 0';

    /*
      TODAY, AS THE PAGE MEANS IT.

      This tracker dates a row by the date the cuts TAKE EFFECT, and WARN
      notices are filed with effective dates weeks ahead by law. So a window
      that ends on 31 December legitimately contains rows that have not
      happened yet, and a caption saying "so far" over that window is a
      different quantity from the one it names.

      Site timezone, matching every other dateline on the page
      (alt_signal_board_periods, the citeline). Format-checked before it is
      inlined because it goes into SQL as a literal: the SELECT list sits
      ahead of the WHERE clause, so a placeholder here would have to be
      threaded in front of every existing $params entry.
    */
    $today_sql = current_time('Y-m-d');
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $today_sql)) $today_sql = gmdate('Y-m-d');

    // Headline totals
    $totals = $wpdb->get_row(alt_db_prep(
        "SELECT COUNT(*) entries, COALESCE(SUM(job_count),0) jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' THEN job_count END),0) to_date_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' AND announced=1 THEN job_count END),0) to_date_announced_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' AND ai_explicit=1 AND announced=0 THEN job_count END),0) to_date_ai_verified_jobs,
                SUM(ai_explicit) ai_entries,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs,
                SUM(CASE WHEN ai_causation='primary_cause' THEN 1 ELSE 0 END) ai_primary_entries,
                COALESCE(SUM(CASE WHEN ai_causation='primary_cause' THEN job_count END),0) ai_primary_jobs,
                SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN 1 ELSE 0 END) ai_verified_entries,
                COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) ai_verified_jobs,
                SUM(CASE WHEN ai_explicit=1 AND announced=1 THEN 1 ELSE 0 END) ai_announced_entries,
                COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=1 THEN job_count END),0) ai_announced_jobs,
                SUM(CASE WHEN ai_explicit=1 OR ai_causation='ai_linked' THEN 1 ELSE 0 END) ai_broad_entries,
                COALESCE(SUM(CASE WHEN ai_explicit=1 OR ai_causation='ai_linked' THEN job_count END),0) ai_broad_jobs,
                SUM(announced) announced_entries,
                COALESCE(SUM(CASE WHEN announced=1 THEN job_count END),0) announced_jobs,
                SUM(CASE WHEN role_categories NOT IN ('', ',unknown,') THEN 1 ELSE 0 END) roles_known_entries,
                COALESCE(SUM(CASE WHEN role_categories NOT IN ('', ',unknown,') THEN job_count END),0) roles_known_jobs,
                COUNT(DISTINCT company_key) companies,
                COUNT(DISTINCT NULLIF(industry,'')) industries,
                COUNT(DISTINCT NULLIF(country,'')) countries,
                COUNT(DISTINCT NULLIF(state,'')) states,
                MIN(CASE WHEN layoff_date > '2000-01-01' THEN layoff_date END) min_date,
                MAX(layoff_date) max_date
         FROM $table WHERE $where_dd", $params));

    // ONE ROW'S CONTRIBUTION TO THIS HEADLINE.
    //
    // Every published number on this site is a SUM, and a sum tells you nothing
    // about whether one row is carrying it. That is how a misparsed count
    // ("9,891 … (2 from RI)" read as 98,912), a state TEST notice (AT&T 78,788)
    // and a by-2050 projection (Coal India 73,800) each moved a headline before
    // a human noticed. This block publishes the largest SINGLE counted row for
    // exactly the filter set that produced $totals, so a consumer can bound one
    // row's share of the figure it is about to quote.
    //
    // THE CO-SCOPING IS THE POINT, and it is why this is computed here rather
    // than left to the caller. It uses $where_dd — the same WHERE, the same
    // params, the same superset-deduped population as `totals.jobs` — and ships
    // in the same response. A caller therefore cannot accidentally measure a
    // row against a differently-scoped denominator, which is precisely the
    // 2026-07-30 Spirit defect one level up (a ±45-day numerator tested against
    // an all-time sum). `headline_jobs` is repeated inside the block on purpose:
    // it is the denominator this numerator belongs to, travelling with it.
    $conc = $want('concentration') ? $wpdb->get_row(alt_db_prep(
        "SELECT id, company, job_count, layoff_date, source_type
         FROM $table WHERE $where_dd ORDER BY job_count DESC, id ASC LIMIT 1", $params)) : null;

    // Top-N helpers (each slicer ignores its own dimension). Each entry is
    // [label, total jobs, AI-attributed jobs, RESERVED, verified jobs,
    // verified AI jobs].
    //
    // WHY THE SHAPE IS THAT AWKWARD, and why the verified pair is not simply
    // put at [1]/[2]:
    //
    //   * INDEX 3 IS SPOKEN FOR. renderBarList() in layoffs.js reads entry[3]
    //     as a DISPLAY LABEL (the country flag, the friendly source-type
    //     name), and top_industries / top_states are handed to it unmapped.
    //     A number appended there prints as the name of the bar. It stays
    //     null so `e[3] || e[0]` keeps falling back to the label.
    //
    //   * [1] AND [2] CANNOT MOVE. This same block is published, under a
    //     `stage=announced` query, as the announced section of the quarterly
    //     appendix CSV (export.php). Redefining [1] as "announced = 0" would
    //     zero every announced row in a published artifact. Two bases have to
    //     coexist, so both are carried and each reader picks the one that
    //     matches the number beside it.
    //
    // THE DEFECT THIS FIXES. The dashboard's bar cards drew [1], which is
    // verified PLUS announced, directly beside a headline tile counting
    // verified only. On 2026-08-04 the visible country bars summed to about
    // 757,000 against a published headline of 444,871, roughly 70% over, with
    // nothing on the card saying the two were different quantities. The bars
    // now draw [4] and the card states the basis.
    //
    // ORDER BY stays on the all-jobs total: the facet pages and the appendix
    // CSV read this block in that order and would be silently resorted
    // otherwise. layoffs.js re-sorts its copy by the verified value.
    //
    // WHICH IS WHY THE LIMIT WENT FROM 24 TO 60. Ordering by one basis and
    // drawing another means the cut-off can drop a row that qualifies on the
    // basis being drawn. It did: in the 2026 view Taiwan had 701 verified cuts
    // and sat outside the all-jobs top 24, so it would have vanished from a
    // list it belonged in. At 60 the dimensions this feeds are effectively
    // whole (19 industries, 50 states, 58 countries), so the cut-off cannot
    // choose on the wrong basis. renderBarList still shows at most 24.
    $topN = function ($col, $except, $limit = 60) use ($wpdb, $table, $r) {
        list($w, $p) = alt_db_where($r, $except);
        $sql = "SELECT $col k, SUM(job_count) v,
                       COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) a,
                       COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) vv,
                       COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) av
                FROM $table
                WHERE $w AND superset_of = 0 AND $col <> '' GROUP BY $col ORDER BY v DESC LIMIT " . max(1, (int) $limit);
        $rows = $wpdb->get_results(alt_db_prep($sql, $p));
        $out = array();
        foreach ($rows ?: array() as $row) {
            $out[] = array($row->k, (int) $row->v, (int) $row->a, null, (int) $row->vv, (int) $row->av);
        }
        return $out;
    };

    // Per-value EVENT COUNTS for the three facet dimensions, as
    // {dimension: {value: entries}}, uncapped.
    //
    // Its own block rather than a fourth element on the $topN triple, and that
    // is not a style preference: renderBarList() in layoffs.js already reads
    // index [3] of these rows as a DISPLAY LABEL (the country flag, the source
    // type's friendly name), and `top_industries` / `top_states` are handed to
    // it unmapped. Appending the count there would have silently printed "1,384"
    // as the name of a bar. A named block cannot collide with a positional one.
    //
    // COUNT(*), not SUM(job_count): the facet pages' index floor is a count of
    // EVENTS for the same reason the company floor is (a job-count floor indexes
    // only the big employers), and this is the number that decides which facet
    // URLs enter the sitemap.
    $facet_counts = array();
    if ($want('facet_counts')) {
        foreach (array('country', 'state', 'industry') as $facet_col) {
            $rows = $wpdb->get_results(alt_db_prep(
                "SELECT $facet_col k, COUNT(*) n FROM $table
                  WHERE $where_dd AND $facet_col <> '' GROUP BY $facet_col", $params));
            $bucket = array();
            foreach ($rows ?: array() as $row) { $bucket[(string) $row->k] = (int) $row->n; }
            $facet_counts[$facet_col] = $bucket;
        }
    }

    // Reason breakdown (9 fixed tags → one SUM each)
    $reason_tags = array('ai_automation','possible_ai','revenue_decline','restructuring',
        'merger_acquisition','offshoring','product_discontinuation','cost_reduction','macroeconomic','closure');
    list($rw, $rp) = alt_db_where($r, 'reasons');
    $reasons = array();
    /*
      SAME SHAPE AS THE topN BLOCKS, and for the same reason: the doughnut
      drew index [1], which is verified PLUS announced, beside a headline
      counting verified only. On 2026-08-04 the slices summed to 660,320
      against a published 444,871. The verified pair goes at [4]/[5] here too
      so the front end can call verifiedBasis() on it unchanged, and index
      [2] is AI-attributed jobs, which is what the appendix CSV and the
      quarterly report table have always read that column as.
    */
    foreach ($want('reasons') ? $reason_tags : array() as $tag) {
        $row = $wpdb->get_row(alt_db_prep(
            "SELECT COALESCE(SUM(job_count),0) jobs,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs,
                    COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) av
             FROM $table WHERE $rw AND superset_of = 0 AND reason_tags LIKE %s",
            array_merge($rp, array('%,' . $tag . ',%'))));
        $val = $row ? (int) $row->jobs : 0;
        if ($val > 0) $reasons[] = array($tag, $val, (int) $row->ai_jobs, null, (int) $row->v, (int) $row->av);
    }

    // Role categories most impacted, one bounded SUM per fixed-vocabulary tag
    // (same LIKE-over-packed-tags shape as the reasons breakdown — a row
    // naming several teams counts in each). [label, jobs, AI-attributed jobs]
    // matches the topN triple so the same bar list can chart AI-vs-all.
    // 'unknown' (checked, roles not stated) is deliberately not charted.
    $top_roles = array();
    if ($want('top_roles') && function_exists('alt_role_categories')) {
        foreach (alt_role_categories() as $slug => $label) {
            // Carries the same six-slot shape as $topN (see its note): the
            // roles card is drawn by the same renderBarList and must be able
            // to draw the same verified basis as its neighbours.
            $row = $wpdb->get_row(alt_db_prep(
                "SELECT COALESCE(SUM(job_count),0) v,
                        COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) a,
                        COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) vv,
                        COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) av
                 FROM $table WHERE $where_dd AND role_categories LIKE %s",
                array_merge($params, array('%,' . $slug . ',%'))));
            if ($row && (int) $row->v > 0) $top_roles[] = array($label, (int) $row->v, (int) $row->a, null, (int) $row->vv, (int) $row->av);
        }
        usort($top_roles, function ($x, $y) { return $y[1] - $x[1]; });
    }

    // Monthly series (all jobs + AI jobs) for trend + cumulative charts.
    // CONCAT(YEAR,LPAD(MONTH)) avoids '%' so it's safe whether or not this SQL
    // is run through $wpdb->prepare (which would otherwise eat DATE_FORMAT's %).
    $months = !$want('series') ? array() : $wpdb->get_results(alt_db_prep(
        "SELECT CONCAT(YEAR(layoff_date),'-',LPAD(MONTH(layoff_date),2,'0')) m,
                SUM(job_count) jobs,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs,
                COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) verified_jobs,
                COALESCE(SUM(CASE WHEN announced=1 THEN job_count END),0) announced_jobs,
                COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) ai_verified_jobs,
                COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=1 THEN job_count END),0) ai_announced_jobs,
                COALESCE(SUM(CASE WHEN ai_explicit=1 OR ai_causation='ai_linked' THEN job_count END),0) ai_broad_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' THEN job_count END),0) td_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' AND ai_explicit=1 THEN job_count END),0) td_ai_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' AND announced=0 THEN job_count END),0) td_verified_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' AND announced=1 THEN job_count END),0) td_announced_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' AND ai_explicit=1 AND announced=0 THEN job_count END),0) td_ai_verified_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' AND ai_explicit=1 AND announced=1 THEN job_count END),0) td_ai_announced_jobs,
                COALESCE(SUM(CASE WHEN layoff_date <= '$today_sql' AND (ai_explicit=1 OR ai_causation='ai_linked') THEN job_count END),0) td_ai_broad_jobs
         FROM $table WHERE $where_dd AND layoff_date > '2000-01-01'
         GROUP BY m ORDER BY m ASC", $params));
    $series = array();
    foreach ($months ?: array() as $row) {
        $s = array(
            'month' => $row->m, 'jobs' => (int) $row->jobs, 'ai_jobs' => (int) $row->ai_jobs,
            'verified_jobs' => (int) $row->verified_jobs, 'announced_jobs' => (int) $row->announced_jobs,
            'ai_verified_jobs' => (int) $row->ai_verified_jobs, 'ai_announced_jobs' => (int) $row->ai_announced_jobs,
            'ai_broad_jobs' => (int) $row->ai_broad_jobs,
        );
        /*
          THE MONTH THE CLOCK IS STILL INSIDE, cut at today.

          A month bucket is a bucket of EFFECTIVE dates, so the current month
          holds notices already filed for dates later this month. On
          2026-08-04 the August bucket held 35,362 verified cuts of which
          21,776 had taken effect: the chart drew the first number under a
          caption reading "4 of 31 days so far", and the This-month card a
          few pixels away published the second.

          `to_date` is emitted ONLY when the two differ, which in practice is
          the in-progress month and nothing else. Every completed month keeps
          the payload it always had, and a consumer that ignores the key gets
          exactly the previous behaviour.
        */
        if ((int) $row->td_jobs !== (int) $row->jobs) {
            $s['to_date'] = array(
                'as_of' => $today_sql,
                'jobs' => (int) $row->td_jobs, 'ai_jobs' => (int) $row->td_ai_jobs,
                'verified_jobs' => (int) $row->td_verified_jobs, 'announced_jobs' => (int) $row->td_announced_jobs,
                'ai_verified_jobs' => (int) $row->td_ai_verified_jobs, 'ai_announced_jobs' => (int) $row->td_ai_announced_jobs,
                'ai_broad_jobs' => (int) $row->td_ai_broad_jobs,
            );
        }
        $series[] = $s;
    }

    // Largest single events. Location is surfaced so several rows for the same
    // company (e.g. a company that legally filed WARN notices in six different
    // cities/states) read as the distinct events they are, not as duplicates.
    list($w2, $p2) = alt_db_where($r);
    $top_events = !$want('leaders') ? array() : $wpdb->get_results(alt_db_prep(
        "SELECT company, job_count, layoff_date, ai_explicit, state, country, post_id
         FROM $table WHERE $w2 ORDER BY job_count DESC, id DESC LIMIT 10", $p2));
    $leaders = array();
    foreach ($top_events ?: array() as $row) {
        $leaders[] = array(
            'company_name' => $row->company, 'job_count' => (int) $row->job_count,
            'layoff_date' => $row->layoff_date ?: '', 'ai_explicit' => (bool) $row->ai_explicit,
            'state' => $row->state, 'country' => $row->country,
            'location' => alt_short_location($row->state, $row->country),
            // The signal board's Largest-event cells link to the entry's own
            // permalink page (the citable unit) when one exists; rows without
            // a CPT post fall back to the company click-filter. Additive key:
            // every consumer reads leaders by name, never by position.
            'permalink' => $row->post_id ? (string) get_permalink((int) $row->post_id) : '',
        );
    }

    // Companies with multiple rounds in the filtered period: the serial-cuts
    // view no aggregator offers (frequency, not size).
    // MAX(company) picks the alphabetically-last raw NAME VARIANT in each
    // company_key group, which mislabels big groups: Amazon's key also holds
    // "Twitch"/"Amazon Fresh" variants that sort after "Amazon", so the chart
    // showed "Twitch - 89 rounds". Resolve the label from the company directory
    // (which knows the canonical "Amazon" for the key), falling back to the raw
    // name only when the directory has no entry.
    $repeat_rows = !$want('repeat_companies') ? array() : $wpdb->get_results(alt_db_prep(
        "SELECT company_key, MAX(company) company, COUNT(*) n, COALESCE(SUM(job_count),0) jobs
         FROM $table WHERE $where AND company_key <> ''
         GROUP BY company_key HAVING COUNT(*) >= 2
         ORDER BY n DESC, jobs DESC LIMIT 24", $params));
    $repeat = array();
    if ($repeat_rows) {
        $dir_names = array();
        $keys = array();
        foreach ($repeat_rows as $rr) { if ($rr->company_key !== '') $keys[] = $rr->company_key; }
        if ($keys) {
            $dir = alt_company_directory_table();
            $ph = implode(',', array_fill(0, count($keys), '%s'));
            $dir_rows = $wpdb->get_results(alt_db_prep(
                "SELECT company_key, display_name FROM $dir WHERE company_key IN ($ph)", $keys));
            foreach ($dir_rows ?: array() as $d) {
                if ($d->display_name !== '') $dir_names[$d->company_key] = $d->display_name;
            }
        }
        foreach ($repeat_rows as $rr) {
            $label = isset($dir_names[$rr->company_key]) ? $dir_names[$rr->company_key] : $rr->company;
            $repeat[] = array($label, (int) $rr->n, (int) $rr->jobs);
        }
    }

    return array(
        'repeat_companies' => $repeat,
        // See the block comment above: numerator and denominator are produced by
        // ONE query pair over ONE filter set, and travel together.
        'concentration' => array(
            'largest_row_jobs'        => $conc ? (int) $conc->job_count : 0,
            'largest_row_company'     => $conc ? (string) $conc->company : '',
            'largest_row_id'          => $conc ? (int) $conc->id : 0,
            'largest_row_date'        => $conc && $conc->layoff_date ? (string) $conc->layoff_date : '',
            'largest_row_source_type' => $conc ? (string) $conc->source_type : '',
            'headline_jobs'           => (int) $totals->jobs,
            'headline_entries'        => (int) $totals->entries,
            'basis' => 'Largest single superset-deduped row in this exact filter set, with the headline it contributes to. Same WHERE, same params, one response: a share computed from these two numbers cannot mix scopes.',
        ),
        'totals' => array(
            'jobs'       => (int) $totals->jobs,
            'entries'    => (int) $totals->entries,
            'ai_jobs'    => (int) $totals->ai_jobs,
            'ai_primary_entries' => (int) $totals->ai_primary_entries,
            'ai_primary_jobs' => (int) $totals->ai_primary_jobs,
            'ai_verified_jobs'    => (int) $totals->ai_verified_jobs,
            'ai_verified_entries' => (int) $totals->ai_verified_entries,
            'ai_announced_jobs'    => (int) $totals->ai_announced_jobs,
            'ai_announced_entries' => (int) $totals->ai_announced_entries,
            'ai_broad_jobs'        => (int) $totals->ai_broad_jobs,
            'ai_broad_entries'     => (int) $totals->ai_broad_entries,
            'announced_entries' => (int) $totals->announced_entries,
            'announced_jobs'    => (int) $totals->announced_jobs,
            /*
              THE SAME WINDOW, CUT AT TODAY. Every caption that says "YTD" or
              "so far" is about this pair, not about `jobs`/`announced_jobs`.
              A 2026 window ran 33,939 verified cuts ahead of itself on
              2026-08-04, all of them real filed notices with effective dates
              later in the year, and the hero published the larger figure under
              a to-date wording while the FAQ JSON-LD on the same page
              published the smaller one. Both numbers are shipped so a caption
              can name the one it actually means and show the remainder.
            */
            'to_date_jobs'             => (int) $totals->to_date_jobs,
            'to_date_announced_jobs'   => (int) $totals->to_date_announced_jobs,
            'to_date_ai_verified_jobs' => (int) $totals->to_date_ai_verified_jobs,
            'as_of'                    => $today_sql,
            // Coverage denominator for the roles chart: only events whose
            // sources actually name the affected teams carry categories.
            'roles_known_entries' => (int) $totals->roles_known_entries,
            'roles_known_jobs'    => (int) $totals->roles_known_jobs,
            'ai_entries' => (int) $totals->ai_entries,
            'companies'  => (int) $totals->companies,
            'industries' => (int) $totals->industries,
            'countries'  => (int) $totals->countries,
            'states'     => (int) $totals->states,
            'min_date'   => $totals->min_date,
            'max_date'   => $totals->max_date,
        ),
        'top_industries' => $want('top_industries') ? $topN('industry', 'industry') : array(),
        'top_countries'  => $want('top_countries') ? $topN('country', 'country') : array(),
        'top_states'     => $want('top_states') ? $topN('state', 'state') : array(),
        // Uncapped-ish sets for the map so every state/country with data shows
        // a bubble (the top-24 lists above are for the ranked bar cards).
        'map_states'     => $want('map_states') ? $topN('state', 'state', 60) : array(),
        'map_countries'  => $want('map_countries') ? $topN('country', 'country', 260) : array(),
        'top_roles'      => $top_roles,
        'facet_counts'   => $facet_counts,
        'source_types'   => $want('source_types') ? $topN('source_type', 'sources') : array(),
        'reasons'        => $reasons,
        'series'         => $series,
        'leaders'        => $leaders,
    );
}

function alt_api_conversion(WP_REST_Request $r) {
    return alt_api_cached('conversion', $r, function () use ($r) {
        return alt_api_conversion_compute($r);
    });
}

/**
 * Announced-to-verified conversion by announcement month.
 *
 * For every announced-tier row (a company's stated plan), sum the verified
 * rows (announced = 0: filings and reported records) from the SAME normalized
 * company dated AFTER the announcement anchor and within `window_months`.
 * Matched jobs are capped at each announcement's own count, so one plan can
 * never convert above 100%. Matching is deliberately company + date-window
 * only — the same conservative screen family as the read-only lifecycle
 * candidate queue — and this endpoint changes no rows, events or totals.
 *
 * Anchor: the source-evidenced announcement_date where one exists, otherwise
 * the announced row's recorded date. Months whose full window has not elapsed
 * are labeled `maturing`; future-dated plans are `pending` — a low figure
 * there means "too early", never "plans abandoned".
 */
function alt_api_conversion_compute(WP_REST_Request $r) {
    global $wpdb;
    $table = alt_db_table();
    $window = (int) ($r->get_param('window_months') ?: 6);
    $window = min(24, max(1, $window));
    $anchor = 'COALESCE(a.announcement_date, a.layoff_date)';

    // Row filters (country/industry/state/ai/sources...) scope the ANNOUNCED
    // side only. Verified matches stay unfiltered on purpose: execution of a
    // multi-country plan can surface anywhere WARN/SEC/news records it.
    // Date filters are excluded and re-applied against the anchor below.
    // 'a' is this query's alias for the layoffs table; alt_db_where needs it so a
    // correlated filter (sourced) points at a name that is still in scope here.
    list($fw, $params) = alt_db_where($r, 'date', 'a');
    $conds = "a.announced = 1 AND a.company_key <> '' AND a.job_count > 0"
        . " AND $anchor IS NOT NULL AND $anchor > '2000-01-01'";
    $anchor_params = array();
    $from = (string) $r->get_param('from');
    $to = (string) $r->get_param('to');
    if ($from && preg_match('/^\d{4}-\d{2}-\d{2}$/', $from)) { $conds .= " AND $anchor >= %s"; $anchor_params[] = $from; }
    if ($to && preg_match('/^\d{4}-\d{2}-\d{2}$/', $to)) { $conds .= " AND $anchor <= %s"; $anchor_params[] = $to; }

    // Parameter binding follows SQL text order: the correlated subquery's
    // window (SELECT list) first, then the WHERE filters.
    $all_params = array_merge(array($window), $anchor_params, $params);
    $sql = "SELECT t.m,
                COUNT(*) announced_entries,
                COALESCE(SUM(t.announced_jobs),0) announced_jobs,
                COALESCE(SUM(LEAST(t.announced_jobs, t.verified_after)),0) matched_jobs,
                SUM(CASE WHEN t.verified_after > 0 THEN 1 ELSE 0 END) matched_entries
            FROM (
                SELECT CONCAT(YEAR($anchor),'-',LPAD(MONTH($anchor),2,'0')) m,
                       a.job_count announced_jobs,
                       (SELECT COALESCE(SUM(b.job_count),0)
                          FROM $table b
                         WHERE b.company_key = a.company_key
                           AND b.announced = 0
                           AND b.layoff_date > $anchor
                           AND b.layoff_date <= DATE_ADD($anchor, INTERVAL %d MONTH)) verified_after
                  FROM $table a
                 WHERE $conds AND $fw
            ) t
            GROUP BY t.m
            ORDER BY t.m ASC";
    $rows = $wpdb->get_results(alt_db_prep($sql, $all_params)) ?: array();

    $now_month = gmdate('Y-m');
    $series = array();
    foreach ($rows as $row) {
        $announced = (int) $row->announced_jobs;
        $matched = (int) $row->matched_jobs;
        if ((string) $row->m > $now_month) {
            $status = 'pending';
        } elseif (strtotime($row->m . '-01 +' . (1 + $window) . ' months') <= time()) {
            $status = 'complete';
        } else {
            $status = 'maturing';
        }
        $series[] = array(
            'month' => $row->m,
            'announced_entries' => (int) $row->announced_entries,
            'announced_jobs' => $announced,
            'matched_entries' => (int) $row->matched_entries,
            'matched_jobs' => $matched,
            'conversion_pct' => $announced > 0 ? round(100 * $matched / $announced, 1) : null,
            'status' => $status,
        );
    }

    return array(
        'window_months' => $window,
        'series' => $series,
        'methodology' => array(
            'question' => 'Of the jobs companies announced they would cut, how many later show verified follow-through?',
            'matching' => 'Deliberately conservative: verified records (announced = 0: WARN filings, SEC filings, sourced reports) from the same normalized company, dated after the announcement anchor and within window_months. Matched jobs are capped at each announcement\'s own count, so no single plan can convert above 100%.',
            'anchor' => 'The announcement month uses the source-evidenced announcement date where one exists, otherwise the announced row\'s recorded date (often the planned effective date), which can only understate conversion, never inflate it.',
            'status_labels' => 'complete = the full window has elapsed for every announcement in the month; maturing = the window is still open, so the figure is expected to rise; pending = plans dated to a future month, which cannot have converted yet.',
            'not_an_execution_audit' => 'A match is company-level corroboration inside a time window, not a per-person reconciliation. Unmatched announced jobs may still have happened through attrition, in geographies without filing systems, or below WARN thresholds; matched jobs can include an unrelated later round at the same company.',
            'filters' => 'Row filters (country, industry, state, ai, sources, from, to) scope the announced side only; verified matches are intentionally unfiltered because execution can be recorded in a different place than the announcement.',
        ),
        'generated_at' => gmdate('c'),
    );
}

/**
 * Server-side bootstrap for the tracker page's first paint.
 *
 * Each REST call costs ~1.2s of WordPress boot on this host even when the
 * result is cached, and the tracker fires facets + aggregate + query before
 * it can render anything. This computes those exact three default-filter
 * responses through the SAME REST callbacks the endpoints use — payloads,
 * transient micro-cache (alt_api_cached) and filter semantics are shared,
 * never duplicated — so templates/page-tracker.php can inline the result as
 * window.ALT_BOOTSTRAP and the first paint needs zero API round-trips.
 *
 * The front-end uses each piece only when the request it was about to make
 * matches the recorded *_params exactly (deep links, saved session filters
 * and year rollover therefore fall back to live fetches), so the bootstrap
 * can never show different numbers than the API would.
 */
function alt_tracker_bootstrap_payload() {
    if (!class_exists('WP_REST_Request')) return null;

    // Mirrors the front-end default scope: every load starts on the current
    // year ("All time" is one click away). Site timezone, like the site copy.
    $year = (string) current_time('Y');
    $aggregate_params = array('years' => $year);
    // Mirrors the results list's first request: newest first, 25 per page.
    // These params must stay byte-identical to what queryParams() builds in
    // layoffs.js, or takeBoot() rejects the payload and the zero-fetch first
    // paint silently becomes a fetch.
    $query_params = array(
        'years'    => $year,
        'per_page' => '25',
        'page'     => '1',
        'sort'     => 'layoff_date',
        'dir'      => 'desc',
    );

    $call = function ($handler, $route, $params) {
        $req = new WP_REST_Request('GET', '/layoffs/v1/' . $route);
        $req->set_query_params($params);
        $resp = call_user_func($handler, $req);
        if (is_wp_error($resp)) return null;
        return ($resp instanceof WP_REST_Response) ? $resp->get_data() : $resp;
    };

    $facets    = $call('alt_api_facets', 'facets', array());
    $aggregate = $call('alt_api_aggregate', 'aggregate', $aggregate_params);
    $query     = $call('alt_api_query', 'query', $query_params);
    // All-or-nothing: a partial bootstrap is worse than none (the front-end
    // would render some surfaces instantly and fetch the rest, out of step).
    if (!is_array($facets) || !is_array($aggregate) || !is_array($query)) return null;

    // The signal board's four period columns, through the SAME cached
    // aggregate handler (alt_api_cached, 30-min transient) the strip's
    // client-side fetches hit — the server render and the JS repaint share
    // one compute and one cache key set. `include=leaders` keeps each call
    // to the totals block plus one leaders query instead of the full ~31
    // statements. Board failure never voids the main bootstrap: the front
    // end falls back to fetching, exactly like a deep-linked view.
    $board = array();
    foreach (alt_signal_board_periods() as $bk => $bp) {
        $bp['include'] = 'leaders';
        $bd = $call('alt_api_aggregate', 'aggregate', $bp);
        if (!is_array($bd) || !isset($bd['totals'])) { $board = null; break; }
        $board[$bk] = array(
            'params' => $bp,
            'totals' => $bd['totals'],
            'leader' => (isset($bd['leaders'][0]) && is_array($bd['leaders'][0])) ? $bd['leaders'][0] : null,
        );
    }

    return array(
        'ver'              => defined('ALT_VERSION') ? ALT_VERSION : '',
        'facets'           => $facets,
        'facets_params'    => new stdClass(),
        'aggregate'        => $aggregate,
        'aggregate_params' => $aggregate_params,
        'query'            => $query,
        'query_params'     => $query_params,
        'board'            => $board ?: null,
    );
}

/**
 * The signal board's period scopes (Today / This week / This month / YTD),
 * all stage=verified so the four columns AND their largest-event picks share
 * one basis — the same rule the narrative strip has always applied (an
 * announced 50K plan must not headline a 9K verified week). Site timezone,
 * like every dateline on the page.
 */
function alt_signal_board_periods() {
    $now  = (int) current_time('timestamp');
    $iso  = function ($ts) { return date('Y-m-d', $ts); };
    $year = (string) current_time('Y');
    return array(
        'today' => array('from' => $iso($now), 'to' => $iso($now), 'stage' => 'verified'),
        'week'  => array('from' => $iso($now - 6 * 86400), 'to' => $iso($now), 'stage' => 'verified'),
        'month' => array('from' => date('Y-m-01', $now), 'to' => $iso($now), 'stage' => 'verified'),
        /*
          A REAL YEAR-TO-DATE. This column is labelled "<year> YTD" and used to
          be scoped `years=<year>`, the whole calendar year. Because rows are
          dated by EFFECTIVE date and WARN notices are filed weeks ahead, that
          window carried cuts that have not happened: 33,939 of them on
          2026-08-04. Ending it at today makes the label true. The front end's
          P.ytd in layoffs.js must stay byte-identical to this or the
          bootstrap is rejected and the board silently refetches.
        */
        'ytd'   => array('from' => date('Y-01-01', $now), 'to' => $iso($now), 'stage' => 'verified'),
    );
}
