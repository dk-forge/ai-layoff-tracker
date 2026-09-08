<?php
/**
 * False-merge restoration route.
 *
 * This deliberately lives at a new pathname. On the 2.20.179 deploy the host
 * served the new entrypoint/version while continuing to execute stale cached
 * bytecode for includes/db.php; the file had been retransferred, but this route
 * was absent from the public REST registry. A new include forces compilation.
 */

if (!defined('ABSPATH')) exit;

function alt_register_restore_merged_route() {
    register_rest_route('layoffs/v1', '/restore-merged-rows', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_restore_merged_rows_fresh',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
}
add_action('rest_api_init', 'alt_register_restore_merged_route');

// Use a new function name as well as a new pathname. A worker executing cached
// 2.20.179 db.php bytecode may still declare alt_api_restore_merged_rows(); a
// distinct callback keeps that stale declaration from colliding with the
// freshly compiled repair include.
if (!function_exists('alt_api_restore_merged_rows_fresh')) {
function alt_api_restore_merged_rows_fresh(WP_REST_Request $r) {
    global $wpdb;
    $reason = trim((string) $r->get_param('reason'));
    if ($reason === '') {
        return new WP_Error('alt_bad_request', 'reason is required.', array('status' => 400));
    }
    $entries = $r->get_param('entries');
    if (!is_array($entries) || !$entries || count($entries) > 50) {
        return new WP_Error('alt_bad_request', 'entries must contain 1 to 50 source-proven rows.', array('status' => 400));
    }
    $table = alt_db_table();
    $out = array('restored' => array(), 'restored_rows' => array(), 'rejected' => array(),
        'jobs_restored' => 0);
    foreach ($entries as $e) {
        if (!is_array($e)) { $out['rejected'][] = array('id' => 0, 'reason' => 'entry is not an object'); continue; }
        $hash = strtolower(substr((string) ($e['dedup_hash'] ?? ''), 0, 32));
        $company = trim((string) ($e['company_name'] ?? ''));
        $jobs = (int) ($e['job_count'] ?? 0);
        if (!preg_match('/^[a-f0-9]{32}$/', $hash) || $company === '' || $jobs < 1) {
            $out['rejected'][] = array('id' => (int) ($e['original_id'] ?? 0), 'reason' => 'valid dedup_hash, company_name and positive job_count required');
            continue;
        }
        $suppressed = alt_suppressed_hashes();
        $suppression_reason = (string) ($suppressed[$hash] ?? '');
        if (strpos($suppression_reason, 'merged:') !== 0) {
            $out['rejected'][] = array('id' => (int) ($e['original_id'] ?? 0), 'reason' => 'hash is not suppressed by a merge');
            continue;
        }
        $existing = (int) $wpdb->get_var($wpdb->prepare("SELECT id FROM $table WHERE dedup_hash = %s", $hash));
        if ($existing) {
            $out['rejected'][] = array('id' => (int) ($e['original_id'] ?? 0), 'reason' => 'hash already exists', 'existing_id' => $existing);
            continue;
        }
        $row = array(
            'post_id' => null, 'dedup_hash' => $hash, 'company' => $company,
            'ticker' => $e['ticker'] ?? '', 'job_count' => $jobs,
            'job_count_max' => $e['job_count_max'] ?? $jobs,
            'layoff_date' => $e['layoff_date'] ?? '',
            'announcement_date' => $e['announcement_date'] ?? '',
            'industry' => function_exists('alt_normalize_industry') ? alt_normalize_industry((string) ($e['industry'] ?? '')) : ($e['industry'] ?? ''),
            'country' => function_exists('alt_normalize_country') ? alt_normalize_country((string) ($e['country'] ?? '')) : ($e['country'] ?? ''),
            'employer_country' => function_exists('alt_normalize_country') ? alt_normalize_country((string) ($e['employer_country'] ?? '')) : ($e['employer_country'] ?? ''),
            'employer_country_evidence' => $e['employer_country_evidence'] ?? '',
            'announcement_evidence' => $e['announcement_evidence'] ?? '',
            'state' => function_exists('alt_normalize_state') ? alt_normalize_state((string) ($e['state'] ?? '')) : ($e['state'] ?? ''),
            'source_type' => in_array($e['source_type'] ?? '', alt_allowed_source_types(), true) ? $e['source_type'] : 'news',
            'verification_level' => in_array($e['verification_level'] ?? '', alt_allowed_verification_levels(), true) ? $e['verification_level'] : 'bronze',
            'source_name' => $e['source_name'] ?? '', 'source_url' => $e['source_url'] ?? '',
            'ai_explicit' => !empty($e['ai_explicit']),
            'ai_causation' => alt_normalize_ai_causation($e['ai_causation'] ?? 'unknown'),
            'confidence' => min(100, max(0, (int) ($e['confidence'] ?? 0))),
            'review_status' => alt_normalize_review_status($e['review_status'] ?? 'legacy_unreviewed'),
            'announced' => !empty($e['announced']), 'ai_language' => $e['ai_language'] ?? '',
            'reason_tags' => $e['reason_tags'] ?? array(), 'roles' => $e['roles'] ?? '',
            'excerpt' => $e['excerpt'] ?? '',
        );
        $id = alt_db_upsert($row, true);
        if (!$id) {
            $out['rejected'][] = array('id' => (int) ($e['original_id'] ?? 0), 'reason' => 'insert failed while suppression remained armed');
            continue;
        }
        $restore_state = array();
        if (!empty($e['edited'])) $restore_state['edited'] = 1;
        if (array_key_exists('role_categories', $e)) {
            $restore_state['role_categories'] = alt_db_pack_tags($e['role_categories']);
        }
        if (array_key_exists('roles_evidence', $e)) {
            $restore_state['roles_evidence'] = sanitize_textarea_field($e['roles_evidence']);
        }
        if ($restore_state) {
            $restore_state['updated_at'] = alt_db_touch_utc();
            if ($wpdb->update($table, $restore_state, array('id' => $id)) === false) {
                $wpdb->delete($table, array('id' => $id));
                $out['rejected'][] = array('id' => (int) ($e['original_id'] ?? 0), 'reason' => 'restored governance state could not be preserved');
                continue;
            }
        }
        $event_id = alt_event_register_report_for_layoff($id, $row);
        if (!$event_id) {
            $wpdb->delete($table, array('id' => $id));
            $out['rejected'][] = array('id' => (int) ($e['original_id'] ?? 0), 'reason' => 'source report could not be registered');
            continue;
        }
        unset($suppressed[$hash]);
        if (!update_option('alt_suppressed_hashes', $suppressed, false)) {
            $wpdb->delete($table, array('id' => $id));
            alt_cleanup_orphan_event((int) $event_id);
            $out['rejected'][] = array('id' => (int) ($e['original_id'] ?? 0), 'reason' => 'merge suppression could not be cleared');
            continue;
        }
        $stored = $wpdb->get_row($wpdb->prepare("SELECT id, company, job_count, layoff_date, country, source_type, source_name, source_url, dedup_hash FROM $table WHERE id = %d", $id), ARRAY_A);
        $out['restored'][] = (int) $id;
        $out['restored_rows'][] = $stored ?: array('id' => (int) $id, 'dedup_hash' => $hash);
        $out['jobs_restored'] += $jobs;
    }
    if ($out['restored']) {
        alt_log_correction('restored', $out['restored'], $reason,
            sprintf('%d jobs restored across %d source-proven rows after false automated merges',
                $out['jobs_restored'], count($out['restored'])));
        if (function_exists('alt_flush_caches')) alt_flush_caches();
    }
    return rest_ensure_response($out);
}
}
