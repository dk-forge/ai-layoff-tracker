<?php
/** Main filterable tracker table — rendered by [alt_tracker]. */
if (!defined('ABSPATH')) exit;
?>
<div class="alt-wrap alt-tracker-wrap">
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
        <div class="alt-filter alt-filter-actions">
            <button type="button" id="alt-f-reset" class="alt-btn">Reset filters</button>
        </div>
    </div>

    <div id="alt-table-status" class="alt-status" role="status">Loading layoff data…</div>

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
