<?php
/**
 * Reviewer-DECLARED superset membership.
 *
 * alt_reconcile_supersets() is a clean-slate recompute: it zeroes the whole
 * `superset_of` column and re-marks rows from its own three rules, reading only
 * rows with `edited = 0`. That is the right shape for a rule, and it left no
 * way to record a DECISION. On 2026-09-21 two independent reviewers ruled that
 * four rows (178740, 178882, 132845, 62215) are staged announcements of one
 * restructuring programme whose latest size is row 176911, and nothing could
 * hold that: a hand-set `superset_of` is erased by the next reconcile, and the
 * primary is `edited = 1`, so no rule will ever see it. 15,200 jobs stacked.
 *
 * The store is one option, `alt_declared_supersets`, keyed by MEMBER id (so a
 * member cannot have two primaries by construction), holding primary_id,
 * reviewer, reason, declared_at and the override flag. The reconciler calls
 * alt_declared_supersets_resolve() AFTER its automatic passes and writes the
 * resolved marks, so a declaration survives every clean slate and no
 * automatic rule can un-mark a declared member.
 *
 * Every downstream surface keys on the `superset_of` column and on nothing
 * else (/aggregate, /query `exclude_supersets`, exports, report and press
 * pages, the company directory), so a declared member is treated exactly like
 * an automatic one: it stays its own row with its own receipt and is not
 * summed. No second definition of "member" is introduced here.
 *
 * Untouched on purpose: WARN's exemption from fuzzy dedup, the dedup hash, the
 * `edited` pin and every automatic rule.
 *
 * The two resolve/validate functions touch no WordPress API, so the tests
 * extract and execute them (railway/tests/test_declared_supersets.py).
 *
 * A new pathname, guarded with is_readable in the entrypoint, for the reason
 * restore-merged.php records: FTPS uploads one file at a time.
 */

if (!defined('ABSPATH')) exit;

if (!function_exists('alt_declared_supersets_resolve')) {

/** The store: member id => declaration. Never anything but an array. */
function alt_declared_supersets() {
    $v = get_option('alt_declared_supersets');
    return is_array($v) ? $v : array();
}

/**
 * Fold the declared memberships into the reconciler's automatic marks.
 *
 * $mark     member id => primary id, as the automatic passes produced it
 * $declared member id => array('primary_id' => N, ...)
 * $live     id => true for every declared member/primary id that still exists
 *
 * Returns array('mark' => ..., 'applied' => [...], 'released' => [...],
 * 'primary_unmarked' => [...], 'repointed' => [...]).
 *
 * Rules, in order:
 *  - a declaration whose member or primary row is gone is RELEASED and named
 *    with the reason; it writes nothing, so a trashed primary's members count
 *    again, visibly;
 *  - a declaration whose primary is itself a declared member is RELEASED as a
 *    chain (the route refuses to store one; this is the second lock);
 *  - otherwise the member is marked, WHATEVER the automatic passes said;
 *  - a declared primary is never left marked as somebody's member;
 *  - an automatic mark that points AT a declared member is re-pointed to that
 *    member's primary, so no chain is ever written.
 */
function alt_declared_supersets_resolve(array $mark, array $declared, array $live) {
    $out = array('mark' => $mark, 'applied' => array(), 'released' => array(),
        'primary_unmarked' => array(), 'repointed' => array());
    $valid = array();
    foreach ($declared as $member => $d) {
        $member  = (int) $member;
        $primary = (int) (is_array($d) ? ($d['primary_id'] ?? 0) : 0);
        $why = '';
        if ($member < 1 || $primary < 1 || $member === $primary) {
            $why = 'malformed declaration';
        } elseif (empty($live[$member])) {
            $why = 'member row no longer exists';
        } elseif (empty($live[$primary])) {
            $why = 'primary row no longer exists, so the member counts again';
        } elseif (isset($declared[$primary]) || isset($declared[(string) $primary])) {
            $why = 'primary is itself a declared member (chain)';
        }
        if ($why !== '') {
            $out['released'][] = array('member_id' => $member, 'primary_id' => $primary, 'why' => $why);
            continue;
        }
        $valid[$member] = $primary;
    }
    foreach ($valid as $member => $primary) {
        $out['mark'][$member] = $primary;
        $out['applied'][] = array('member_id' => $member, 'primary_id' => $primary);
    }
    foreach (array_unique(array_values($valid)) as $primary) {
        if (!empty($out['mark'][$primary])) {
            $out['primary_unmarked'][] = array('primary_id' => (int) $primary, 'was_member_of' => (int) $out['mark'][$primary]);
            unset($out['mark'][$primary]);
        }
    }
    foreach ($out['mark'] as $id => $p) {
        if (isset($valid[$p]) && !isset($valid[$id])) {
            $out['mark'][$id] = $valid[$p];
            $out['repointed'][] = array('id' => (int) $id, 'from' => (int) $p, 'to' => (int) $valid[$p]);
        }
    }
    return $out;
}

/**
 * May this (member, primary) pair be declared? '' = yes, 'unchanged' = it is
 * already declared exactly so (idempotent), anything else = the refusal.
 *
 * $rows is id => array('company_key' => ...) for the rows that exist.
 */
function alt_declared_supersets_validate(array $declared, $member, $primary, array $rows, $allow_key_mismatch = false) {
    $member = (int) $member; $primary = (int) $primary;
    if ($member < 1 || $primary < 1) return 'member and primary must be positive row ids';
    if ($member === $primary) return 'a row cannot be a member of itself';
    if (!isset($rows[$member])) return 'member row does not exist';
    if (!isset($rows[$primary])) return 'primary row does not exist';
    if (isset($declared[$primary])) return 'primary is itself a declared member of ' . (int) $declared[$primary]['primary_id'] . ' (no chains)';
    foreach ($declared as $m => $d) {
        if ((int) ($d['primary_id'] ?? 0) === $member) return 'member is the declared primary of ' . (int) $m . ' (no chains)';
    }
    if (isset($declared[$member])) {
        $cur = (int) ($declared[$member]['primary_id'] ?? 0);
        if ($cur === $primary) return 'unchanged';
        return 'member already has primary ' . $cur . '; remove that declaration first';
    }
    $mk = (string) ($rows[$member]['company_key'] ?? '');
    $pk = (string) ($rows[$primary]['company_key'] ?? '');
    if (!$allow_key_mismatch && ($mk === '' || $mk !== $pk)) {
        return 'company keys differ ("' . $mk . '" vs "' . $pk . '"); pass allow_key_mismatch=1 only if that is intended';
    }
    return '';
}

/** Rows for a set of ids, keyed by id, with the company key recomputed. */
function alt_declared_supersets_rows(array $ids) {
    global $wpdb;
    $ids = array_values(array_unique(array_filter(array_map('intval', $ids))));
    if (!$ids) return array();
    $table = alt_db_table();
    $got = $wpdb->get_results(
        "SELECT id, company, company_key, job_count, layoff_date, source_type, superset_of
         FROM $table WHERE id IN (" . implode(',', $ids) . ")", ARRAY_A) ?: array();
    $out = array();
    foreach ($got as $r) {
        // The stored key can predate a key-function change; the name is the truth.
        if (function_exists('alt_company_key')) $r['company_key'] = alt_company_key($r['company']);
        $out[(int) $r['id']] = $r;
    }
    return $out;
}

function alt_register_declared_supersets_routes() {
    register_rest_route('layoffs/v1', '/declare-superset', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_declare_superset',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
    // Read-only and public, like /corrections: what reviewers declared and
    // whether the live rows reflect it. One request, no page walk; it is what
    // data_integrity's `declared_supersets_reflected` reads.
    register_rest_route('layoffs/v1', '/declared-supersets', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_declared_supersets',
        'permission_callback' => '__return_true',
    ));
}
add_action('rest_api_init', 'alt_register_declared_supersets_routes');

/**
 * Key-protected. Default DRY RUN; apply=1 writes. remove=1 withdraws.
 * Body: members [ids], primary id, reason, reviewer, allow_key_mismatch.
 * Idempotent: re-declaring an identical membership reports `unchanged`.
 */
function alt_api_declare_superset(WP_REST_Request $r) {
    global $wpdb;
    $apply  = (string) $r->get_param('apply') === '1';
    $remove = (string) $r->get_param('remove') === '1';
    $allow  = (string) $r->get_param('allow_key_mismatch') === '1';
    $reason = trim((string) $r->get_param('reason'));
    $reviewer = trim((string) $r->get_param('reviewer'));
    if ($reason === '') return new WP_Error('alt_bad_request', 'reason is required.', array('status' => 400));
    $members = $r->get_param('members');
    if (!is_array($members) || !$members || count($members) > 50) {
        return new WP_Error('alt_bad_request', 'members must contain 1 to 50 row ids.', array('status' => 400));
    }
    $members = array_values(array_unique(array_map('intval', $members)));
    $primary = (int) $r->get_param('primary');
    $declared = alt_declared_supersets();
    $rows = alt_declared_supersets_rows(array_merge($members, array($primary)));
    $out = array('dry_run' => !$apply, 'action' => $remove ? 'remove' : 'declare', 'primary_id' => $primary,
        'declared' => array(), 'unchanged' => array(), 'removed' => array(), 'rejected' => array(),
        'jobs_moved' => 0, 'rows' => array_values($rows));
    $touched = array();
    foreach ($members as $m) {
        if ($remove) {
            if (!isset($declared[$m])) { $out['rejected'][] = array('id' => $m, 'reason' => 'no declaration to remove'); continue; }
            if ($primary && (int) $declared[$m]['primary_id'] !== $primary) {
                $out['rejected'][] = array('id' => $m, 'reason' => 'declared primary is ' . (int) $declared[$m]['primary_id'] . ', not ' . $primary); continue;
            }
            unset($declared[$m]);
            $out['removed'][] = $m; $touched[] = $m;
            $out['jobs_moved'] += (int) ($rows[$m]['job_count'] ?? 0);
            continue;
        }
        $verdict = alt_declared_supersets_validate($declared, $m, $primary, $rows, $allow);
        if ($verdict === 'unchanged') { $out['unchanged'][] = $m; continue; }
        if ($verdict !== '') { $out['rejected'][] = array('id' => $m, 'reason' => $verdict); continue; }
        $declared[$m] = array(
            'primary_id' => $primary, 'reviewer' => substr($reviewer, 0, 120),
            'reason' => substr($reason, 0, 400), 'declared_at' => gmdate('Y-m-d\TH:i:s\Z'),
            'key_mismatch_allowed' => ($allow && (string) $rows[$m]['company_key'] !== (string) $rows[$primary]['company_key']),
        );
        $out['declared'][] = $m; $touched[] = $m;
        if ((int) $rows[$m]['superset_of'] === 0) $out['jobs_moved'] += (int) $rows[$m]['job_count'];
    }
    // All or nothing: a ruling names a set, and half of it applied is a third
    // state nobody ruled on.
    if ($out['rejected']) { $out['dry_run'] = true; $out['refused'] = 'nothing written: every member must be accepted'; return rest_ensure_response($out); }
    if (!$apply || !$touched) return rest_ensure_response($out);

    update_option('alt_declared_supersets', $declared, false);
    $table = alt_db_table();
    foreach ($touched as $m) {
        $wpdb->update($table, array('superset_of' => $remove ? 0 : $primary, 'updated_at' => alt_db_touch_utc()), array('id' => (int) $m));
    }
    if (!$remove && !empty($rows[$primary]['superset_of'])) {
        $wpdb->update($table, array('superset_of' => 0, 'updated_at' => alt_db_touch_utc()), array('id' => $primary));
    }
    if (function_exists('alt_log_correction')) {
        alt_log_correction($remove ? 'superset_removed' : 'superset_declared', $touched, $reason,
            sprintf('%d row(s) %s programme total row %d%s', count($touched),
                $remove ? 'no longer declared part of' : 'declared part of', $primary,
                $allow ? ' (company key mismatch explicitly allowed)' : ''));
    }
    if (function_exists('alt_flush_caches')) alt_flush_caches();
    return rest_ensure_response($out);
}

/** Public, read-only: each declaration beside what the live rows say. */
function alt_api_declared_supersets() {
    $declared = alt_declared_supersets();
    $ids = array();
    foreach ($declared as $m => $d) { $ids[] = (int) $m; $ids[] = (int) ($d['primary_id'] ?? 0); }
    $rows = alt_declared_supersets_rows($ids);
    $list = array();
    foreach ($declared as $m => $d) {
        $m = (int) $m; $p = (int) ($d['primary_id'] ?? 0);
        $list[] = array(
            'member_id' => $m, 'primary_id' => $p,
            'member_exists' => isset($rows[$m]), 'primary_exists' => isset($rows[$p]),
            'member_superset_of' => isset($rows[$m]) ? (int) $rows[$m]['superset_of'] : null,
            'primary_superset_of' => isset($rows[$p]) ? (int) $rows[$p]['superset_of'] : null,
            'member_job_count' => isset($rows[$m]) ? (int) $rows[$m]['job_count'] : null,
            'reviewer' => (string) ($d['reviewer'] ?? ''), 'reason' => (string) ($d['reason'] ?? ''),
            'declared_at' => (string) ($d['declared_at'] ?? ''),
            'key_mismatch_allowed' => !empty($d['key_mismatch_allowed']),
        );
    }
    $resp = rest_ensure_response(array('count' => count($list), 'declarations' => $list));
    $resp->header('Cache-Control', 'no-store');
    return $resp;
}

}
