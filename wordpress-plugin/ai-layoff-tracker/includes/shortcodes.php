<?php
/**
 * Shortcodes:
 *   [alt_tracker]                            Full filterable DataTables table
 *   [alt_stats_bar]                          Headline stats
 *   [alt_dashboard]                          All charts
 *   [alt_ai_tracker]                         AI displacement view
 *   [alt_company_history company="amazon"]   Per-company timeline
 *   [alt_export_buttons]                     CSV + JSON downloads
 */

if (!defined('ABSPATH')) exit;

/**
 * Render a template file with local variables, returning the output.
 */
function alt_template($file, $vars = array()) {
    $path = ALT_PLUGIN_DIR . 'templates/' . $file;
    if (!file_exists($path)) {
        return '<!-- AI Layoff Tracker: missing template ' . esc_html($file) . ' -->';
    }
    if (!empty($vars)) {
        extract($vars, EXTR_SKIP); // phpcs:ignore WordPress.PHP.DontExtract
    }
    ob_start();
    include $path;
    return ob_get_clean();
}

function alt_shortcode_tracker() {
    $GLOBALS['alt_tracker_rendered'] = true;
    return alt_template('page-tracker.php');
}
add_shortcode('alt_tracker', 'alt_shortcode_tracker');

function alt_shortcode_dashboard() {
    // The tracker embeds the same charts (same element IDs); rendering both on
    // one page would duplicate IDs and leave the second set dead.
    if (!empty($GLOBALS['alt_tracker_rendered'])) {
        return '<!-- alt_dashboard skipped: alt_tracker already renders these charts on this page -->';
    }
    return alt_template('page-dashboard.php');
}
add_shortcode('alt_dashboard', 'alt_shortcode_dashboard');

function alt_shortcode_ai_tracker() {
    return alt_template('page-ai-tracker.php');
}
add_shortcode('alt_ai_tracker', 'alt_shortcode_ai_tracker');

function alt_shortcode_company_history($atts) {
    $atts = shortcode_atts(array('company' => ''), $atts, 'alt_company_history');
    $company = sanitize_text_field($atts['company']);
    if ($company === '') {
        return '<p class="alt-error">[alt_company_history] needs a company attribute, e.g. [alt_company_history company="amazon"].</p>';
    }
    return alt_template('page-company.php', array('company' => $company));
}
add_shortcode('alt_company_history', 'alt_shortcode_company_history');

function alt_shortcode_stats_bar() {
    ob_start();
    ?>
    <div class="alt-header">
        <span class="alt-live"><span class="alt-live-dot" aria-hidden="true"></span> Live · updated <span id="alt-live-time">twice daily (ET)</span></span>
        <p class="alt-subtitle">Verified layoffs across the economy, with the ones companies explicitly blame on AI flagged and quoted. Every entry links to its primary source: SEC filings and credible news.</p>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('alt_stats_bar', 'alt_shortcode_stats_bar');

function alt_shortcode_export_buttons() {
    $csv_url  = admin_url('admin-post.php?action=alt_export_csv');
    $json_url = admin_url('admin-post.php?action=alt_export_json');
    ob_start();
    ?>
    <div class="alt-export-buttons">
        <a class="alt-btn alt-btn-primary" href="<?php echo esc_url($csv_url); ?>">Download CSV</a>
        <a class="alt-btn" href="<?php echo esc_url($json_url); ?>">Download JSON</a>
        <p class="alt-export-note">Free to use with attribution to asktherecruiter.com.
           Journalists can also query the public API at
           <code><?php echo esc_html(rest_url('layoffs/v1/all')); ?></code>.</p>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('alt_export_buttons', 'alt_shortcode_export_buttons');
