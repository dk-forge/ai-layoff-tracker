<?php
/**
 * Trust tiers (owner-approved names, 2026-10-11). docs/VERIFICATION_TIERS.md.
 *
 *   verified  an official primary document: SEC 8-K, state WARN notice,
 *             federal RIF record, other government/regulatory filing.
 *   reported  news or press (GDELT, outlets, company press releases,
 *             Eurofound ERM, which is curated from press reports).
 *   measured  our own measurement (job-board scans). NEVER a layoff event,
 *             so the layoff mapper below can never return it.
 *
 * The tier is DERIVED from source_type, never stored, so it cannot drift from
 * the row. verification_level can only DOWNGRADE (bronze is never verified);
 * it can never upgrade: a news row carrying 'gold' stays reported. That is on
 * purpose: /bulk coerces an unknown source_type (e.g. 'filing') to 'news'
 * while keeping its level, and an unverifiable claim of 'gold' must not buy
 * the paid-worthy label.
 *
 * Pure: no WordPress functions, so railway/tests/test_trust_tiers.py runs it
 * through the php CLI.
 */

function alt_trust_tiers() {
    return array('verified', 'reported', 'measured');
}

/** source_type values that are official primary documents (lowercased). */
function alt_trust_official_source_types() {
    return array('8k', 'warn', 'federal_rif', 'filing');
}

function alt_trust_tier($source_type, $verification_level) {
    $st = strtolower(trim((string) $source_type));
    $lv = strtolower(trim((string) $verification_level));
    if (in_array($st, alt_trust_official_source_types(), true) && $lv !== 'bronze') {
        return 'verified';
    }
    return 'reported';
}

/**
 * The same rule as SQL, for the `tier` filter and the `tiers` aggregate.
 * $prefix is a table alias with its dot ('l.') or ''. MySQL's default
 * collation is case-insensitive, matching the strtolower above.
 */
function alt_trust_tier_sql($prefix = '') {
    $p = preg_replace('/[^A-Za-z0-9_.]/', '', (string) $prefix);
    return "(CASE WHEN {$p}source_type IN ('8K','warn','federal_rif','filing')"
         . " AND {$p}verification_level <> 'bronze' THEN 'verified' ELSE 'reported' END)";
}

/** Plain-text labels for UI (no em-dashes). */
function alt_trust_tier_labels() {
    return array('verified' => 'Verified', 'reported' => 'Reported', 'measured' => 'Measured');
}
