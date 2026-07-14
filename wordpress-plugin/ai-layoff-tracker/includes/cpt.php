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
        'industry'           => 'string',
        'country'            => 'string',
        'roles'              => 'string',   // roles/departments affected, when stated
        'source_url'         => 'string',
        'source_type'        => 'string',   // "8K" | "press_release" | "news"
        'verification_level' => 'string',   // "gold" | "silver" | "bronze"
        'excerpt'            => 'string',
        'reason_tags'        => 'array',
        'ai_explicit'        => 'boolean',
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

function alt_allowed_verification_levels() {
    return array('gold', 'silver', 'bronze');
}

function alt_allowed_source_types() {
    return array('8K', 'press_release', 'news');
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
