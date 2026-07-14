<?php
/** Main filterable tracker table — rendered by [alt_tracker]. */
if (!defined('ABSPATH')) exit;

$alt_csv  = admin_url('admin-post.php?action=alt_export_csv');
$alt_json = admin_url('admin-post.php?action=alt_export_json');
$alt_api  = rest_url('layoffs/v1/all');
$alt_dl   = '<svg class="alt-dl-ico" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg>';
?>
<div class="alt-wrap alt-tracker-wrap">

    <div class="alt-toolbar">
        <div class="alt-toolbar-info">
            <span class="alt-toolbar-title">Layoff database</span>
            <span class="alt-toolbar-sub">Verified from SEC filings &amp; credible news · updated twice daily</span>
        </div>
        <div class="alt-toolbar-actions">
            <a class="alt-btn alt-btn-primary" href="<?php echo esc_url($alt_csv); ?>"><?php echo $alt_dl; ?> Download CSV</a>
            <a class="alt-btn" href="<?php echo esc_url($alt_json); ?>"><?php echo $alt_dl; ?> JSON</a>
        </div>
    </div>

    <div class="alt-filters-card">
        <div class="alt-filters-head">
            <span class="alt-filters-title">Filter the data</span>
            <button type="button" id="alt-f-reset" class="alt-btn alt-btn-sm">Reset filters</button>
        </div>
        <div class="alt-filters" id="alt-filters">
            <div class="alt-filter">
                <label for="alt-f-from">From</label>
                <input type="date" id="alt-f-from">
            </div>
            <div class="alt-filter">
                <label for="alt-f-to">To</label>
                <input type="date" id="alt-f-to">
            </div>
            <div class="alt-filter">
                <label for="alt-f-industry">Industry</label>
                <select id="alt-f-industry"><option value="">All industries</option></select>
            </div>
            <div class="alt-filter">
                <label for="alt-f-country">Country</label>
                <select id="alt-f-country"><option value="">All countries</option></select>
            </div>
            <div class="alt-filter">
                <label for="alt-f-reasons">Reason tags</label>
                <select id="alt-f-reasons" multiple size="4">
                    <option value="ai_automation">AI / automation</option>
                    <option value="possible_ai">Possible AI</option>
                    <option value="revenue_decline">Revenue decline</option>
                    <option value="restructuring">Restructuring</option>
                    <option value="merger_acquisition">Merger / acquisition</option>
                    <option value="offshoring">Offshoring</option>
                    <option value="product_discontinuation">Product discontinued</option>
                    <option value="cost_reduction">Cost reduction</option>
                    <option value="macroeconomic">Macroeconomic</option>
                </select>
            </div>
            <div class="alt-filter">
                <label for="alt-f-verification">Verification</label>
                <select id="alt-f-verification" multiple size="3">
                    <option value="gold">Gold (SEC 8-K)</option>
                    <option value="silver">Silver (press release)</option>
                    <option value="bronze">Bronze (news)</option>
                </select>
            </div>
            <div class="alt-filter">
                <label for="alt-f-company">Company</label>
                <input type="text" id="alt-f-company" placeholder="e.g. Amazon">
            </div>
            <div class="alt-filter">
                <label for="alt-f-keyword">Keyword</label>
                <input type="text" id="alt-f-keyword" placeholder="Search excerpts">
            </div>
            <div class="alt-filter">
                <label for="alt-f-minjobs">Min job count</label>
                <input type="number" id="alt-f-minjobs" min="0" step="1" placeholder="0">
            </div>
            <div class="alt-filter alt-filter-toggle">
                <label><input type="checkbox" id="alt-f-ai"> AI-attributed only</label>
            </div>
        </div>
    </div>

    <div id="alt-table-status" class="alt-status" role="status">Loading layoff data…</div>

    <div class="alt-table-scroll">
        <table id="alt-table" class="display" style="width:100%">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Company</th>
                    <th>Jobs</th>
                    <th>Industry</th>
                    <th>Country</th>
                    <th>Reasons</th>
                    <th>Verification</th>
                    <th>AI</th>
                    <th>Source</th>
                </tr>
            </thead>
        </table>
    </div>

    <p class="alt-tracker-foot">
        Free to use with attribution to <strong>asktherecruiter.com</strong>. Journalists &amp; researchers can query the live API at
        <code><?php echo esc_html($alt_api); ?></code>.
    </p>
</div>
