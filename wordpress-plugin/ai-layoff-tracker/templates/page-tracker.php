<?php
/** Main filterable tracker — rendered by [alt_tracker]. */
if (!defined('ABSPATH')) exit;

$alt_csv  = admin_url('admin-post.php?action=alt_export_csv');
$alt_json = admin_url('admin-post.php?action=alt_export_json');
$alt_api  = rest_url('layoffs/v1/query');
$alt_dl   = '<svg class="alt-dl-ico" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg>';
?>
<div class="alt-wrap alt-tracker-wrap alt-dashboard">

    <div id="alt-dashboard-status" class="alt-status" role="status" style="display:none"></div>

    <div class="alt-stats-bar" id="alt-stats-bar">
        <div class="alt-stat-card">
            <span class="alt-stat-value" id="alt-stat-total">—</span>
            <span class="alt-stat-label">Jobs cut (all causes)</span>
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
    <div class="alt-range-wrap">
        <button type="button" class="alt-range-btn" id="alt-range-btn" aria-expanded="false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
            <span id="alt-range-label">Date range</span>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
        </button>
        <span class="alt-range-note-data" id="alt-range-note"></span>
        <div class="alt-range-pop" id="alt-range-pop" hidden>
            <div class="alt-filter">
                <label for="alt-f-from">From</label>
                <input type="date" id="alt-f-from" max="2026-12-31">
            </div>
            <div class="alt-filter">
                <label for="alt-f-to">To</label>
                <input type="date" id="alt-f-to" max="2026-12-31">
            </div>
            <button type="button" class="alt-btn alt-btn-sm" id="alt-range-clear">Clear dates</button>
        </div>
    </div>

    <div class="alt-toolbar2">
        <div class="alt-search-wrap">
            <svg class="alt-search-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
            <input type="search" id="alt-search" placeholder="Search company, industry, keyword…" autocomplete="off" aria-label="Search">
        </div>
        <label class="alt-sort"><span>Sort</span>
            <select id="alt-sort">
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="largest">Largest cuts</option>
                <option value="smallest">Smallest cuts</option>
            </select>
        </label>
    </div>

    <div class="alt-quickviews">
        <span class="alt-qv-label">Quick views:</span>
        <button type="button" class="alt-qv" data-qv="ai">✦ AI-attributed</button>
        <button type="button" class="alt-qv" data-qv="month">This month</button>
        <button type="button" class="alt-qv" data-qv="largest">Largest cuts</button>
        <button type="button" class="alt-qv" data-qv="sec">SEC-verified</button>
        <button type="button" class="alt-qv" data-qv="tech">Tech industry</button>
    </div>

    <div class="alt-filterbar">
        <div class="alt-filterbar-row">
            <div class="alt-filter" data-dd="Years" data-empty="All years">
                <label for="alt-f-years">Years</label>
                <select id="alt-f-years" multiple></select>
            </div>
            <div class="alt-filter" data-dd="Quarters" data-empty="All quarters">
                <label for="alt-f-quarters">Quarters</label>
                <select id="alt-f-quarters" multiple>
                    <option value="1">Q1 (Jan–Mar)</option>
                    <option value="2">Q2 (Apr–Jun)</option>
                    <option value="3">Q3 (Jul–Sep)</option>
                    <option value="4">Q4 (Oct–Dec)</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Months" data-empty="All months">
                <label for="alt-f-months">Months</label>
                <select id="alt-f-months" multiple>
                    <option value="1">January</option><option value="2">February</option>
                    <option value="3">March</option><option value="4">April</option>
                    <option value="5">May</option><option value="6">June</option>
                    <option value="7">July</option><option value="8">August</option>
                    <option value="9">September</option><option value="10">October</option>
                    <option value="11">November</option><option value="12">December</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Industries" data-empty="All industries">
                <label for="alt-f-industry">Industries</label>
                <select id="alt-f-industry" multiple></select>
            </div>
            <div class="alt-filter" data-dd="Countries" data-empty="All countries">
                <label for="alt-f-country">Countries</label>
                <select id="alt-f-country" multiple></select>
            </div>
            <div class="alt-filter" data-dd="US states" data-empty="All states">
                <label for="alt-f-state">US states</label>
                <select id="alt-f-state" multiple></select>
            </div>
            <div class="alt-filter" data-dd="Sources" data-empty="All sources">
                <label for="alt-f-verification">Sources</label>
                <select id="alt-f-verification" multiple>
                    <option value="gold">SEC filing (8-K)</option>
                    <option value="warn">WARN notice</option>
                    <option value="silver">Press release</option>
                    <option value="bronze">News</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Reasons" data-empty="All reasons">
                <label for="alt-f-reasons">Reasons</label>
                <select id="alt-f-reasons" multiple>
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
                <label for="alt-f-company">Company</label>
                <input type="text" id="alt-f-company" placeholder="e.g. Amazon">
            </div>
            <div class="alt-filter">
                <label for="alt-f-keyword">Keyword in excerpt</label>
                <input type="text" id="alt-f-keyword" placeholder="Search excerpts">
            </div>
            <div class="alt-filter">
                <label for="alt-f-minjobs">Min job count</label>
                <input type="number" id="alt-f-minjobs" min="0" step="1" placeholder="0">
            </div>
            <div class="alt-filter alt-filter-reset">
                <label>&nbsp;</label>
                <button type="button" id="alt-f-reset" class="alt-btn alt-btn-reset">Reset all filters</button>
            </div>
        </div>
        <!-- Hidden state holder: the "AI-attributed" quick-view pill is the visible control -->
        <input type="checkbox" id="alt-f-ai" hidden>
    </div>

    <?php $alt_expand = '<button type="button" class="alt-expand" aria-label="Expand chart" title="Expand"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg></button>'; ?>
    <div class="alt-minigrid">
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Jobs cut per month <span class="alt-chart-sub" id="alt-trend-range"></span></div>
                <?php echo $alt_expand; ?>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-weekly"></canvas></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">By industry <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <?php echo $alt_expand; ?>
            </div>
            <div class="alt-barlist" id="alt-bars-industries"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Reasons cited <span class="alt-chart-sub">tap to filter</span></div>
                <?php echo $alt_expand; ?>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-reasons"></canvas></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">By US state <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <?php echo $alt_expand; ?>
            </div>
            <div class="alt-barlist" id="alt-bars-states"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">By country <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <?php echo $alt_expand; ?>
            </div>
            <div class="alt-barlist" id="alt-bars-countries"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Cumulative AI-attributed cuts <span class="alt-chart-sub" id="alt-cum-range"></span></div>
                <?php echo $alt_expand; ?>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-ai-cumulative"></canvas></div>
        </div>
    </div>

    <div class="alt-count-row" id="alt-count-row">
        <div class="alt-count-left">
            <span id="alt-table-count" class="alt-count-strong">Loading…</span>
            <div id="alt-active-filters" class="alt-active-filters" style="display:none"></div>
        </div>
        <div class="alt-toolbar-actions">
            <a class="alt-btn alt-btn-sm" href="<?php echo esc_url($alt_csv); ?>"><?php echo $alt_dl; ?> CSV</a>
            <a class="alt-btn alt-btn-sm" href="<?php echo esc_url($alt_json); ?>"><?php echo $alt_dl; ?> JSON</a>
        </div>
    </div>

    <div id="alt-table-status" class="alt-status" role="status" style="display:none"></div>

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
                    <th>Source</th>
                    <th>AI</th>
                    <th>Link</th>
                </tr>
            </thead>
        </table>
    </div>

    <details class="alt-methodology">
        <summary>Methodology &amp; sources</summary>
        <div class="alt-method-body">
            <p><b>How entries are collected.</b> Layoffs are pulled from SEC EDGAR 8-K filings, US state WARN Act notices, and credible news coverage worldwide (via the open GDELT news index), plus a set of manually verified cases. Each entry is machine-extracted, and the core facts (company, job count, date, and any AI attribution) always come straight from the source text. The only field we infer is location: a company that files an 8-K is a US registrant, so SEC entries with no stated country are marked US.</p>
            <p><b>How the AI tag works.</b> An entry is marked <em>Explicitly AI-attributed</em> only when the source <em>explicitly names</em> AI, machine learning, automation, or robotics as a reason for the cuts. We store and display the <em>exact quote</em>. If a source doesn't name AI, the entry is still listed, just not flagged as AI. We never infer AI from vague "efficiency" language.</p>
            <p><b>Verification tiers.</b> <span class="alt-badge alt-badge-gold">SEC filing</span> is a legal 8-K the company filed (strongest). <span class="alt-badge alt-badge-warn">WARN notice</span> is a state mass-layoff filing (legally required, US-only). <span class="alt-badge alt-badge-silver">Press release</span> is an official company statement. <span class="alt-badge alt-badge-bronze">News</span> is a credible outlet (Reuters, Bloomberg, CNBC, etc.).</p>
            <p><b>Coverage.</b> US WARN notices cover ~22 states that publish machine-readable data. There is <em>no international equivalent of WARN or EDGAR</em>, so non-US layoffs come from news and top out at Press release or News verification. We label every entry's source so you always know the strength of the evidence.</p>
            <p><b>What WARN notices do and don't contain.</b> A WARN filing states the employer, headcount, dates, and location, but <em>not</em> the industry or the reason, so industry and reason charts mostly reflect SEC- and news-sourced entries. Employers with remote or multi-state workforces sometimes file the same restructuring in several states, each with its own official count, so state-level figures can overlap for those companies. Counts are shown exactly as each state published them.</p>
            <p><b>What we exclude.</b> Rumored or unsourced layoffs; layoffs with no stated job count; and "AI" claims that are forward-looking plans rather than executed cuts.</p>
            <p><b>Filed vs. happened.</b> WARN law requires employers to file 60+ days before cuts take effect, so entries dated in the future are <em>planned and legally filed</em>, not yet executed. They carry an <span class="alt-upcoming">upcoming</span> tag in the table until their effective date arrives.</p>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>Data notes &amp; corrections log</summary>
        <div class="alt-method-body">
            <p>Errors are corrected openly, not silently. Recent corrections:</p>
            <p><b>Jul 14, 2026.</b> Fixed a count-parsing error affecting 6 WARN entries whose official filings contain annotations in the headcount field (e.g. Rhode Island's "9,891 Remote Workers (2 from RI)" had been read as 98,912). Counts now parse the first number in the field; ranges resolve to the lower bound. All affected rows were reloaded and totals recomputed.</p>
            <p><b>Jul 14, 2026.</b> Country names normalized ("US"/"USA" → United States) and multi-country phrases ("India and US", "Global") consolidated into a single "Multiple countries" bucket to prevent double counting.</p>
            <p>Spotted something off? Every entry links to its primary source so you can check us — corrections are welcome via the contact page.</p>
        </div>
    </details>

    <div class="alt-cite-box">
        <span class="alt-detail-h">Cite this tracker</span>
        <code id="alt-cite-text">AI Layoff Tracker, AskTheRecruiter.com. Accessed <span id="alt-cite-date"></span>. Data from SEC EDGAR 8-K filings, US state WARN notices, and credible news outlets.</code>
        <button type="button" class="alt-btn alt-btn-sm" id="alt-cite-copy">Copy</button>
    </div>

    <div class="alt-journalist">
        <div class="alt-journalist-text">
            <strong>Built for journalists &amp; researchers</strong>
            <p>Free to use with attribution to <strong>asktherecruiter.com</strong>. Every figure links to a primary source. Query the full dataset live via our API.</p>
        </div>
        <code class="alt-journalist-api"><?php echo esc_html('GET ' . wp_make_link_relative($alt_api)); ?></code>
    </div>
</div>
