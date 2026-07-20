<?php
/**
 * Per-company history — rendered by [alt_company_history company="..."].
 * $company is provided by alt_template().
 */
if (!defined('ABSPATH')) exit;
if (!isset($company)) $company = '';
?>
<div class="alt-wrap alt-company-history" data-company="<?php echo esc_attr($company); ?>">
    <h2 class="alt-company-title"><?php echo esc_html(ucwords($company)); ?> layoff history</h2>
    <div class="alt-company-summary" id="alt-company-summary">Loading…</div>

    <div class="alt-chart-card alt-chart-card-wide">
        <h3>Layoff rounds over time</h3>
        <div class="alt-chart-box"><canvas id="alt-chart-company"></canvas></div>
    </div>

    <table id="alt-company-table" class="alt-plain-table">
        <thead>
            <tr><th>Date</th><th>Jobs</th><th>Reasons</th><th>Verification</th><th>Source</th></tr>
        </thead>
        <tbody></tbody>
    </table>
</div>
