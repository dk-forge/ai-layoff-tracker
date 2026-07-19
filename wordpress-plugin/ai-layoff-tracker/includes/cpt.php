<?php
/**
 * Custom post type "layoffs" + meta field registration.
 */

if (!defined('ABSPATH')) exit;

function alt_meta_fields() {
    return array(
        'company_name'       => 'string',
        'ticker'             => 'string',
        'job_count'          => 'integer',
        'layoff_date'        => 'string',   // "2025-01-15" ISO format
        'announcement_date'  => 'string',   // public announcement date, when source-supported
        'industry'           => 'string',
        'country'            => 'string',
        'employer_country'   => 'string',   // employer HQ/domicile when stated
        'employer_country_evidence' => 'string',
        'announcement_evidence' => 'string',
        'roles'              => 'string',   // roles/departments affected, when stated
        'role_categories'    => 'string',   // packed fixed-vocabulary role tags, derived/evidence-only
        'roles_evidence'     => 'string',   // exact source phrase behind evidence-extracted categories
        'source_url'         => 'string',
        'source_type'        => 'string',   // "8K" | "press_release" | "news"
        'verification_level' => 'string',   // "gold" | "silver" | "bronze"
        'excerpt'            => 'string',
        'reason_tags'        => 'array',
        'ai_explicit'        => 'boolean',
        'ai_causation'       => 'string',   // primary|contributing|selection|context|denied|unknown
        'confidence'         => 'integer',  // autonomous evidence score, 0-100
        'review_status'      => 'string',   // verified|provisional|legacy_unreviewed
        'ai_language'        => 'string',
        'source_name'        => 'string',
        'dedup_hash'         => 'string',
    );
}

function alt_allowed_reason_tags() {
    return array(
        'ai_automation',
        'revenue_decline',
        'restructuring',
        'merger_acquisition',
        'offshoring',
        'product_discontinuation',
        'cost_reduction',
        'macroeconomic',
        'possible_ai',
    );
}

function alt_allowed_ai_causation() {
    // 'ai_linked' is the Challenger/layoffs.fyi-style BROAD bucket: cuts the
    // company or press tied to AI loosely (funding an AI pivot, AI-driven
    // market disruption, press AI framing). It never sets ai_explicit, so the
    // strict verified-AI totals stay quote-gated; it only feeds the labeled
    // broad comparison measure.
    return array('primary_cause', 'contributing_cause', 'ai_linked', 'selection_or_operations',
        'context_only', 'explicitly_denied', 'unknown');
}

function alt_normalize_ai_causation($value) {
    $value = sanitize_key((string) $value);
    return in_array($value, alt_allowed_ai_causation(), true) ? $value : 'unknown';
}

function alt_allowed_review_statuses() {
    return array('verified', 'provisional', 'legacy_unreviewed');
}

function alt_normalize_review_status($value) {
    $value = sanitize_key((string) $value);
    return in_array($value, alt_allowed_review_statuses(), true) ? $value : 'legacy_unreviewed';
}

function alt_allowed_verification_levels() {
    // 'warn' = a state WARN Act notice (legally-required mass-layoff filing).
    return array('gold', 'warn', 'silver', 'bronze');
}

function alt_allowed_source_types() {
    // 'erm' = Eurofound's European Restructuring Monitor (EU27+Norway,
    // announced restructuring events curated by national correspondents)
    return array('8K', 'warn', 'press_release', 'news', 'erm');
}

function alt_register_cpt() {
    register_post_type('layoffs', array(
        'labels' => array(
            'name'          => 'Layoffs',
            'singular_name' => 'Layoff',
            'add_new_item'  => 'Add New Layoff Entry',
            'edit_item'     => 'Edit Layoff Entry',
            'menu_name'     => 'Layoffs',
        ),
        'public'       => true,
        'show_ui'      => true,
        'show_in_rest' => true, // enables the block editor / admin REST views
        'menu_icon'    => 'dashicons-chart-line',
        'supports'     => array('title', 'custom-fields'),
        'has_archive'  => false,
        'rewrite'      => array('slug' => 'layoff'),
    ));

    foreach (alt_meta_fields() as $key => $type) {
        register_post_meta('layoffs', $key, array(
            'type'         => $type,
            'single'       => true,
            'show_in_rest' => false, // exposed through the custom layoffs/v1 endpoints instead
            'auth_callback' => function () {
                return current_user_can('edit_posts');
            },
        ));
    }
}
add_action('init', 'alt_register_cpt');
