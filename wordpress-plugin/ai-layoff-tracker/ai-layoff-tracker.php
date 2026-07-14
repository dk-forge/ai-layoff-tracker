<?php
/**
 * Plugin Name: AI Layoff Tracker
 * Description: Tracks verified AI-related and general layoffs from SEC filings and credible news sources.
 * Version: 1.3.0
 * Author: AskTheRecruiter
 */

if (!defined('ABSPATH')) exit;

define('ALT_VERSION', '1.3.0');
define('ALT_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('ALT_PLUGIN_URL', plugin_dir_url(__FILE__));

// Load includes
require_once ALT_PLUGIN_DIR . 'includes/cpt.php';
require_once ALT_PLUGIN_DIR . 'includes/api.php';
require_once ALT_PLUGIN_DIR . 'includes/shortcodes.php';
require_once ALT_PLUGIN_DIR . 'includes/export.php';
require_once ALT_PLUGIN_DIR . 'includes/rss.php';

/**
 * Activation: register the CPT + custom feed before flushing rewrite rules,
 * and auto-generate the API key so the Railway pipeline can be wired up
 * without running code in the theme editor.
 */
function alt_activate() {
    alt_register_cpt();
    alt_register_feed();
    flush_rewrite_rules();

    if (!get_option('alt_api_key')) {
        update_option('alt_api_key', bin2hex(random_bytes(32)), false);
    }
}
register_activation_hook(__FILE__, 'alt_activate');

function alt_deactivate() {
    flush_rewrite_rules();
}
register_deactivation_hook(__FILE__, 'alt_deactivate');

/**
 * Only load DataTables/Chart.js on pages that actually use a plugin shortcode
 * — loading two CDN libraries on every page of the site would be wasteful.
 * Filter `alt_enqueue_assets` to force-enable on custom templates.
 */
function alt_page_needs_assets() {
    if (!is_singular()) return false;
    $post = get_post();
    if (!$post) return false;
    $shortcodes = array(
        'alt_tracker', 'alt_stats_bar', 'alt_dashboard',
        'alt_ai_tracker', 'alt_company_history', 'alt_export_buttons',
    );
    foreach ($shortcodes as $shortcode) {
        if (has_shortcode($post->post_content, $shortcode)) return true;
    }
    return false;
}

function alt_enqueue_assets() {
    if (!apply_filters('alt_enqueue_assets', alt_page_needs_assets())) return;

    wp_enqueue_style('alt-styles', ALT_PLUGIN_URL . 'assets/layoffs.css', array(), ALT_VERSION);

    // DataTables
    wp_enqueue_style(
        'datatables-css',
        'https://cdnjs.cloudflare.com/ajax/libs/datatables/1.10.21/css/jquery.dataTables.min.css',
        array(),
        '1.10.21'
    );
    wp_enqueue_script(
        'datatables-js',
        'https://cdnjs.cloudflare.com/ajax/libs/datatables/1.10.21/js/jquery.dataTables.min.js',
        array('jquery'),
        '1.10.21',
        true
    );

    // Chart.js (UMD build, no dependencies)
    wp_enqueue_script(
        'chartjs',
        'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js',
        array(),
        '4.4.0',
        true
    );

    // Main JS
    wp_enqueue_script(
        'alt-js',
        ALT_PLUGIN_URL . 'assets/layoffs.js',
        array('jquery', 'datatables-js', 'chartjs'),
        ALT_VERSION,
        true
    );

    // Pass data to JS
    wp_localize_script('alt-js', 'altData', array(
        'apiUrl'    => esc_url_raw(rest_url('layoffs/v1/')),
        'ajaxUrl'   => admin_url('admin-ajax.php'),
        'nonce'     => wp_create_nonce('alt_nonce'),
        'exportCsv' => admin_url('admin-post.php?action=alt_export_csv'),
        'exportJson'=> admin_url('admin-post.php?action=alt_export_json'),
    ));
}
add_action('wp_enqueue_scripts', 'alt_enqueue_assets');

/**
 * SEO for tracker pages: JSON-LD Dataset structured data (eligible for Google
 * Dataset Search; signals a citable, downloadable dataset) plus Open Graph /
 * Twitter tags for shareable link previews. The OG block is filterable off via
 * `alt_output_og_tags` if an SEO plugin (Yoast/RankMath) already emits them.
 */
function alt_seo_head() {
    if (!alt_page_needs_assets()) return;

    $page_url = get_permalink();
    if (!$page_url) $page_url = home_url('/');
    $title = 'AI Layoff Tracker — Live Data on Jobs Lost to AI & Automation';
    $desc  = 'A continuously updated tracker of verified layoffs across the economy — flagging which ones companies attribute to AI. Sourced from SEC filings and credible news, with the exact quote and primary source link for every entry.';

    $schema = array(
        '@context'            => 'https://schema.org',
        '@type'               => 'Dataset',
        'name'                => 'AI Layoff Tracker',
        'alternateName'       => 'AI Layoffs Tracker',
        'description'         => $desc,
        'url'                 => $page_url,
        'keywords'            => array('AI layoffs', 'layoffs', 'jobs lost to AI', 'AI job losses', 'AI layoff tracker', 'automation layoffs', 'tech layoffs'),
        'license'             => 'https://creativecommons.org/licenses/by/4.0/',
        'isAccessibleForFree' => true,
        'temporalCoverage'    => '2024-01-01/..',
        'creator'             => array(
            '@type' => 'Organization',
            'name'  => 'AskTheRecruiter',
            'url'   => home_url('/'),
        ),
        'distribution'        => array(
            array('@type' => 'DataDownload', 'encodingFormat' => 'text/csv',         'contentUrl' => admin_url('admin-post.php?action=alt_export_csv')),
            array('@type' => 'DataDownload', 'encodingFormat' => 'application/json', 'contentUrl' => admin_url('admin-post.php?action=alt_export_json')),
        ),
    );

    echo "\n<script type=\"application/ld+json\">" . wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";

    if (apply_filters('alt_output_og_tags', true)) {
        echo '<meta property="og:type" content="website">' . "\n";
        echo '<meta property="og:title" content="' . esc_attr($title) . '">' . "\n";
        echo '<meta property="og:description" content="' . esc_attr($desc) . '">' . "\n";
        echo '<meta property="og:url" content="' . esc_url($page_url) . '">' . "\n";
        echo '<meta name="twitter:card" content="summary_large_image">' . "\n";
        echo '<meta name="twitter:title" content="' . esc_attr($title) . '">' . "\n";
        echo '<meta name="twitter:description" content="' . esc_attr($desc) . '">' . "\n";
    }
}
add_action('wp_head', 'alt_seo_head', 20);

/**
 * Small admin page (Tools → AI Layoff Tracker) showing the API key the
 * Railway pipeline authenticates with, plus entry counts.
 */
function alt_register_admin_page() {
    add_management_page(
        'AI Layoff Tracker',
        'AI Layoff Tracker',
        'manage_options',
        'alt-settings',
        'alt_render_admin_page'
    );
}
add_action('admin_menu', 'alt_register_admin_page');

function alt_render_admin_page() {
    if (!current_user_can('manage_options')) return;

    if (isset($_POST['alt_regenerate_key']) && check_admin_referer('alt_regenerate_key')) {
        update_option('alt_api_key', bin2hex(random_bytes(32)), false);
        echo '<div class="notice notice-success"><p>New API key generated. Update WP_API_KEY in Railway.</p></div>';
    }

    $key   = alt_get_api_key();
    $count = wp_count_posts('layoffs');
    $total = isset($count->publish) ? (int) $count->publish : 0;
    ?>
    <div class="wrap">
        <h1>AI Layoff Tracker</h1>
        <p><strong><?php echo esc_html(number_format_i18n($total)); ?></strong> published layoff entries.</p>
        <h2>Pipeline API key</h2>
        <p>Copy this value into the Railway environment variable <code>WP_API_KEY</code>.
           Requests must send it in the <code>X-Layoff-API-Key</code> header.</p>
        <input type="text" readonly class="regular-text code" style="width:520px"
               value="<?php echo esc_attr($key); ?>" onfocus="this.select();">
        <?php if (defined('AI_LAYOFF_API_KEY') && AI_LAYOFF_API_KEY) : ?>
            <p><em>Note: <code>AI_LAYOFF_API_KEY</code> is defined in wp-config.php and overrides the stored option.</em></p>
        <?php endif; ?>
        <form method="post" style="margin-top:12px;">
            <?php wp_nonce_field('alt_regenerate_key'); ?>
            <button type="submit" name="alt_regenerate_key" value="1" class="button"
                    onclick="return confirm('Regenerate the key? The Railway pipeline will stop authenticating until WP_API_KEY is updated.');">
                Regenerate key
            </button>
        </form>
        <h2>Endpoints</h2>
        <ul style="list-style:disc;padding-left:20px;">
            <li><code>POST <?php echo esc_html(rest_url('layoffs/v1/add')); ?></code> (key required)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/check-duplicate')); ?></code> (key required)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/all')); ?></code> (public)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/stats')); ?></code> (public)</li>
            <li><code>GET <?php echo esc_html(rest_url('layoffs/v1/company/{name}')); ?></code> (public)</li>
        </ul>
    </div>
    <?php
}
