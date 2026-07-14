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
            <span class="alt-toolbar-sub">Verified from SEC filings &amp; credible news · updated twice daily (morning &amp; after market close, ET)</span>
        </div>
        <div class="alt-toolbar-actions">
            <a class="alt-btn alt-btn-primary" href="<?php echo esc_url($alt_csv); ?>"><?php echo $alt_dl; ?> Download CSV</a>
            <a class="alt-btn" href="<?php echo esc_url($alt_json); ?>"><?php echo $alt_dl; ?> JSON</a>
        </div>
    </div>

    <div class="alt-dashboard alt-overview">
        <div id="alt-dashboard-status" class="alt-status" role="status" style="display:none"></div>
        <div class="alt-overview-hint">Click any bar or slice to filter everything below: the charts, the totals, and the company table all move together.</div>
        <div id="alt-active-filters" class="alt-active-filters" style="display:none"></div>
        <div class="alt-chart-grid">
            <div class="alt-chart-card alt-chart-card-wide">
                <div class="alt-chart-h">Jobs cut per week <span class="alt-chart-sub">rolling 52 weeks</span></div>
                <div class="alt-chart-box"><canvas id="alt-chart-weekly"></canvas></div>
            </div>
            <div class="alt-chart-card">
                <div class="alt-chart-h">Top industries <span class="alt-chart-sub">by total job losses</span></div>
                <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-industries"></canvas></div>
            </div>
            <div class="alt-chart-card">
                <div class="alt-chart-h">Reasons cited <span class="alt-chart-sub">jobs by reason tag</span></div>
                <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-reasons"></canvas></div>
            </div>
            <div class="alt-chart-card">
                <div class="alt-chart-h">Top countries <span class="alt-chart-sub">by total job losses</span></div>
                <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-countries"></canvas></div>
            </div>
            <div class="alt-chart-card">
                <div class="alt-chart-h">Cumulative AI-attributed cuts <span class="alt-chart-sub">acceleration curve</span></div>
                <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-ai-cumulative"></canvas></div>
            </div>
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
                <label for="alt-f-state">US state</label>
                <select id="alt-f-state"><option value="">All states</option></select>
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
                <label for="alt-f-verification">Source type</label>
                <select id="alt-f-verification" multiple size="4">
                    <option value="gold">SEC filing (8-K)</option>
                    <option value="warn">WARN notice</option>
                    <option value="silver">Press release</option>
                    <option value="bronze">News</option>
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

    <div class="alt-legend">
        <span class="alt-legend-item"><span class="alt-badge alt-badge-gold">SEC filing</span> official 8-K, strongest</span>
        <span class="alt-legend-item"><span class="alt-badge alt-badge-warn">WARN notice</span> state mass-layoff filing</span>
        <span class="alt-legend-item"><span class="alt-badge alt-badge-silver">Press release</span> company announcement</span>
        <span class="alt-legend-item"><span class="alt-badge alt-badge-bronze">News</span> credible outlet</span>
        <span class="alt-legend-hint">Tap any row for the exact quote &amp; source ↓</span>
    </div>

    <div id="alt-table-status" class="alt-status" role="status">Loading layoff data…</div>
    <div id="alt-table-count" class="alt-table-count"></div>

    <div class="alt-table-scroll">
        <table id="alt-table" class="display" style="width:100%">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Company</th>
                    <th>Employees</th>
                    <th>Industry</th>
                    <th>Country</th>
                    <th>Reasons</th>
                    <th>Source type</th>
                    <th>AI</th>
                    <th>Source</th>
                </tr>
            </thead>
        </table>
    </div>

    <details class="alt-methodology">
        <summary>Methodology &amp; sources</summary>
        <div class="alt-method-body">
            <p><b>How entries are collected.</b> Layoffs are pulled from SEC EDGAR 8-K filings and from credible news coverage worldwide (via the open GDELT news index), plus a set of manually verified cases. Each entry is machine-extracted, and the core facts (company, job count, date, and any AI attribution) always come straight from the source text. The only field we infer is location: a company that files an 8-K is a US registrant, so SEC entries with no stated country are marked US.</p>
            <p><b>How the AI tag works.</b> An entry is marked <em>Explicitly AI-attributed</em> only when the source <em>explicitly names</em> AI, machine learning, automation, or robotics as a reason for the cuts. We store and display the <em>exact quote</em>. If a source doesn't name AI, the entry is still listed, just not flagged as AI. We never infer AI from vague "efficiency" language.</p>
            <p><b>Verification tiers.</b> <span class="alt-badge alt-badge-gold">SEC filing</span> is a legal 8-K the company filed (strongest). <span class="alt-badge alt-badge-silver">Press release</span> is an official company statement. <span class="alt-badge alt-badge-bronze">News</span> is a credible outlet (Reuters, Bloomberg, CNBC, etc.).</p>
            <p><b>Global coverage limitation.</b> There is <em>no international equivalent of SEC EDGAR</em>. For non-US companies, the verification ceiling is Press release or News, never SEC filing. We label every entry's source type so you always know the strength of the evidence.</p>
            <p><b>What we exclude.</b> Rumored or unsourced layoffs; layoffs with no stated job count; and "AI" claims that are forward-looking plans (e.g. "could be replaced by 2030") rather than executed cuts.</p>
        </div>
    </details>

    <div class="alt-cite-box">
        <span class="alt-detail-h">Cite this tracker</span>
        <code id="alt-cite-text">AI Layoff Tracker, AskTheRecruiter.com. Accessed <span id="alt-cite-date"></span>. Data from SEC EDGAR 8-K filings and credible news outlets.</code>
        <button type="button" class="alt-btn alt-btn-sm" id="alt-cite-copy">Copy</button>
    </div>

    <p class="alt-tracker-foot">
        Free to use with attribution to <strong>asktherecruiter.com</strong>. Journalists &amp; researchers can query the live API at
        <code><?php echo esc_html($alt_api); ?></code>.
    </p>
</div>
