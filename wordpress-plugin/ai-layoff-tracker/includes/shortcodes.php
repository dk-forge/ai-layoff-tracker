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
    return alt_template('page-tracker.php');
}
add_shortcode('alt_tracker', 'alt_shortcode_tracker');

function alt_shortcode_dashboard() {
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
    <p class="alt-intro">Tracking verified layoffs across the economy, flagging the ones companies attribute to AI.</p>
    <div class="alt-period" id="alt-period" role="group" aria-label="Time period" style="display:none">
        <div class="alt-period-years" id="alt-period-years"></div>
        <div class="alt-period-refine">
            <select id="alt-period-quarter" aria-label="Quarter">
                <option value="">All quarters</option>
                <option value="1">Q1 (Jan–Mar)</option>
                <option value="2">Q2 (Apr–Jun)</option>
                <option value="3">Q3 (Jul–Sep)</option>
                <option value="4">Q4 (Oct–Dec)</option>
            </select>
            <select id="alt-period-month" aria-label="Month">
                <option value="">All months</option>
                <option value="1">January</option>
                <option value="2">February</option>
                <option value="3">March</option>
                <option value="4">April</option>
                <option value="5">May</option>
                <option value="6">June</option>
                <option value="7">July</option>
                <option value="8">August</option>
                <option value="9">September</option>
                <option value="10">October</option>
                <option value="11">November</option>
                <option value="12">December</option>
            </select>
        </div>
    </div>
    <div class="alt-stats-bar" id="alt-stats-bar">
        <div class="alt-stat-card">
            <span class="alt-stat-value" id="alt-stat-total">—</span>
            <span class="alt-stat-label">Jobs cut (tracked)</span>
            <span class="alt-stat-sub" id="alt-stat-total-entries"></span>
        </div>
        <div class="alt-stat-card alt-stat-card-ai">
            <span class="alt-stat-value" id="alt-stat-ai">—</span>
            <span class="alt-stat-label">Explicitly AI-attributed</span>
            <span class="alt-stat-sub" id="alt-stat-ai-entries"></span>
        </div>
        <div class="alt-stat-card">
            <span class="alt-stat-value" id="alt-stat-companies">—</span>
            <span class="alt-stat-label">Companies</span>
            <span class="alt-stat-sub" id="alt-stat-companies-sub"></span>
        </div>
        <div class="alt-stat-card">
            <span class="alt-stat-value" id="alt-stat-industries">—</span>
            <span class="alt-stat-label">Industries</span>
            <span class="alt-stat-sub"></span>
        </div>
        <div class="alt-stat-card">
            <span class="alt-stat-value" id="alt-stat-countries">—</span>
            <span class="alt-stat-label">Countries</span>
            <span class="alt-stat-sub"></span>
        </div>
    </div>
    <div class="alt-stats-meta" id="alt-stats-meta">
        <span class="alt-updated" id="alt-last-updated"></span>
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
