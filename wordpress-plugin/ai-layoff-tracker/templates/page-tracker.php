<?php
/** Main filterable tracker — rendered by [alt_tracker]. */
if (!defined('ABSPATH')) exit;

$alt_csv  = admin_url('admin-post.php?action=alt_export_csv');
$alt_json = admin_url('admin-post.php?action=alt_export_json');
$alt_api  = rest_url('layoffs/v1/query');
$alt_dl   = '<svg class="alt-dl-ico" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg>';
$alt_challenger_records = get_option('alt_challenger_benchmarks');
$alt_challenger_records = is_array($alt_challenger_records) ? array_values($alt_challenger_records) : array();
usort($alt_challenger_records, function($a, $b) {
    $a_period = (string) (!empty($a['report_month']) ? $a['report_month'] : substr((string) ($a['recorded_at'] ?? ''), 0, 7));
    $b_period = (string) (!empty($b['report_month']) ? $b['report_month'] : substr((string) ($b['recorded_at'] ?? ''), 0, 7));
    return strcmp($b_period, $a_period);
});
// One retained reconciliation per official report month. A later write with an
// explicit report_month supersedes an earlier setup record for that same month.
$alt_challenger_by_period = array();
foreach ($alt_challenger_records as $alt_challenger_record) {
    $alt_period = !empty($alt_challenger_record['report_month'])
        ? (string) $alt_challenger_record['report_month']
        : substr((string) ($alt_challenger_record['recorded_at'] ?? ''), 0, 7);
    if ($alt_period === '') $alt_period = 'recorded-' . count($alt_challenger_by_period);
    if (!isset($alt_challenger_by_period[$alt_period]) || !empty($alt_challenger_record['report_month'])) {
        $alt_challenger_by_period[$alt_period] = $alt_challenger_record;
    }
}
$alt_challenger_records = array_values($alt_challenger_by_period);
$alt_challenger_chart = array();
foreach (array_reverse($alt_challenger_records) as $alt_challenger_record) {
    $alt_challenger_chart[] = array(
        // Challenger publishes the prior month's announcements. Keep the
        // announcement reference month separate from the report publication
        // month so the chart cannot visually shift events a month late.
        'period' => !empty($alt_challenger_record['reference_month']) ? $alt_challenger_record['reference_month'] : (!empty($alt_challenger_record['report_month']) ? $alt_challenger_record['report_month'] : substr((string) ($alt_challenger_record['recorded_at'] ?? ''), 0, 7)),
        'challenger_month' => array_key_exists('challenger_ai_jobs_month', $alt_challenger_record) ? max(0, (int) $alt_challenger_record['challenger_ai_jobs_month']) : null,
        'tracker_month' => array_key_exists('tracker_ai_primary_announced_us_employer_jobs_month', $alt_challenger_record) ? max(0, (int) $alt_challenger_record['tracker_ai_primary_announced_us_employer_jobs_month']) : null,
        'challenger_ytd' => max(0, (int) ($alt_challenger_record['challenger_ai_jobs_ytd'] ?? 0)),
        'tracker_ytd' => max(0, (int) ($alt_challenger_record['tracker_ai_primary_announced_us_employer_jobs_ytd'] ?? 0)),
        // All-cuts comparator pair; null when a record predates the fields or
        // the fail-soft Challenger totals parse was unavailable.
        'challenger_total_month' => isset($alt_challenger_record['challenger_total_jobs_month']) && $alt_challenger_record['challenger_total_jobs_month'] !== null ? max(0, (int) $alt_challenger_record['challenger_total_jobs_month']) : null,
        'challenger_total_ytd' => isset($alt_challenger_record['challenger_total_jobs_ytd']) && $alt_challenger_record['challenger_total_jobs_ytd'] !== null ? max(0, (int) $alt_challenger_record['challenger_total_jobs_ytd']) : null,
        'tracker_all_month' => isset($alt_challenger_record['tracker_announced_us_employer_jobs_month']) && $alt_challenger_record['tracker_announced_us_employer_jobs_month'] !== null ? max(0, (int) $alt_challenger_record['tracker_announced_us_employer_jobs_month']) : null,
        'tracker_all_ytd' => isset($alt_challenger_record['tracker_announced_us_employer_jobs_ytd']) && $alt_challenger_record['tracker_announced_us_employer_jobs_ytd'] !== null ? max(0, (int) $alt_challenger_record['tracker_announced_us_employer_jobs_ytd']) : null,
    );
}
?>
<div class="alt-wrap alt-tracker-wrap alt-dashboard">

    <?php $alt_cov = alt_coverage_counts(); ?>
    <div class="alt-narrative" id="alt-narrative"></div>
    <?php include ALT_PLUGIN_DIR . 'templates/partials/scan-scope.php'; ?>
    <p class="alt-lead"><span class="alt-lead-text">Track source-linked layoffs worldwide. We monitor <b><?php echo number_format((int) $alt_scan_outlets); ?> reviewed news outlets across <?php echo number_format((int) $alt_scan_countries); ?> countries</b> in 65+ languages, plus <b>every SEC 8-K filing, all 50 US states (WARN notices from 41), and EU restructuring records</b>, twice daily. Filter by country, industry, source or reason; AI labels appear only where the evidence supports them.</span><span class="alt-lead-links"><a class="alt-method-link" href="#alt-metric-definitions">Methodology</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a class="alt-method-link" href="#alt-challenger-comparison">US comparison</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press &amp; media</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/publisher-tools/')); ?>">Embed this tracker</a></span></p>
    <p class="alt-filter-context">Choose filters to scope the results. Every number, chart and row below updates to match.</p>
    <div class="alt-tabs" id="alt-tabs" role="tablist" aria-label="Region">
        <button type="button" class="alt-tab alt-tab-world" data-tab="world">🌐 World</button>
        <button type="button" class="alt-tab alt-tab-usa" data-tab="usa">🇺🇸 USA</button>
        <button type="button" class="alt-tab alt-tab-canada" data-tab="canada">🇨🇦 Canada</button>
        <button type="button" class="alt-tab alt-tab-latam" data-tab="latam">🌎 Latin America</button>
        <button type="button" class="alt-tab alt-tab-europe" data-tab="europe">🇪🇺 Europe</button>
        <button type="button" class="alt-tab alt-tab-uk" data-tab="uk">🇬🇧 UK</button>
        <button type="button" class="alt-tab alt-tab-mideast" data-tab="mideast">🌅 Middle East</button>
        <button type="button" class="alt-tab alt-tab-africa" data-tab="africa">🌍 Africa</button>
        <button type="button" class="alt-tab alt-tab-asia" data-tab="asia">🌏 Asia</button>
        <button type="button" class="alt-tab alt-tab-aus" data-tab="aus">🇦🇺 Australia</button>
    </div>


    <div id="alt-dashboard-status" class="alt-status" role="status" style="display:none"></div>

    <div class="alt-toolbar2">
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
                    <input type="date" id="alt-f-from">
                </div>
                <div class="alt-filter">
                    <label for="alt-f-to">To</label>
                    <input type="date" id="alt-f-to">
                </div>
                <button type="button" class="alt-btn alt-btn-sm" id="alt-range-clear">Clear dates</button>
            </div>
        </div>
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
        <button type="button" class="alt-qv" data-qv="month">This month</button>
        <button type="button" class="alt-qv" data-qv="largest">Largest cuts</button>
        <button type="button" class="alt-qv" data-qv="sec">SEC-verified</button>
        <button type="button" class="alt-qv" data-qv="announced">Announced only</button>
        <button type="button" class="alt-qv" data-qv="tech">Tech industry</button>
        <button type="button" id="alt-f-reset" class="alt-btn alt-btn-reset alt-qv-reset">Reset all filters</button>
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
                    <option value="gold">SEC filing (8-K/6-K)</option>
                    <option value="warn">WARN notice</option>
                    <option value="silver">Press release</option>
                    <option value="bronze">News</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Reasons" data-empty="All reasons">
                <label for="alt-f-reasons">Reasons</label>
                <select id="alt-f-reasons" multiple>
                    <option value="ai_automation">AI: company-stated (specific)</option>
                    <option value="possible_ai">AI-linked (broad)</option>
                    <option value="revenue_decline">Revenue decline</option>
                    <option value="restructuring">Restructuring</option>
                    <option value="merger_acquisition">Merger / acquisition</option>
                    <option value="offshoring">Offshoring</option>
                    <option value="product_discontinuation">Product discontinued</option>
                    <option value="cost_reduction">Cost reduction</option>
                    <option value="macroeconomic">Macroeconomic</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Roles" data-empty="All roles">
                <label for="alt-f-roles">Roles most impacted</label>
                <select id="alt-f-roles" multiple>
                    <?php foreach (alt_role_categories() as $alt_rk => $alt_rlabel) : ?>
                    <option value="<?php echo esc_attr($alt_rk); ?>"><?php echo esc_html($alt_rlabel); ?></option>
                    <?php endforeach; ?>
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
        </div>
        <!-- Hidden state holders: quick-view pills are the visible controls -->
        <input type="checkbox" id="alt-f-ai" hidden>
        <input type="checkbox" id="alt-f-announced" hidden>
    </div>

    <!-- Active-filter summary. Sits directly under the filter controls and
         sticks to the top as you scroll down past them (so what's filtered
         stays visible through the whole page), then re-docks here on the way
         back up. Empty (display:none) when no filters are set. -->
    <div id="alt-active-filters" class="alt-active-filters alt-active-filters--sticky" style="display:none"></div>

    <section class="alt-results-summary" aria-labelledby="alt-results-summary-title">
        <div class="screen-reader-text" id="alt-results-summary-title" role="heading" aria-level="2">Results summary</div>
        <div class="alt-stats-bar" id="alt-stats-bar">
            <div class="alt-stat-card alt-fam-verified">
                <span class="alt-stat-value" id="alt-stat-total">—</span>
                <span class="alt-stat-label">Verified job cuts</span>
                <span class="alt-stat-desc">Filed or reported. The main number. <a class="alt-why-verified" href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>" target="_blank" rel="noopener">Why this is verified &rarr;</a></span>
                <span class="alt-stat-sub" id="alt-stat-total-entries"></span>
            </div>
            <div class="alt-stat-card alt-fam-announced">
                <span class="alt-stat-value" id="alt-stat-announced">—</span>
                <span class="alt-stat-label">Announced job cuts (planned)</span>
                <span class="alt-stat-desc">Company plans at announcement stage, not yet in Verified.</span>
                <span class="alt-stat-sub" id="alt-stat-announced-sub"></span>
            </div>
            <div class="alt-stat-card alt-fam-all">
                <span class="alt-stat-value" id="alt-stat-all">—</span>
                <span class="alt-stat-label">Verified + announced job cuts</span>
                <span class="alt-stat-desc">Both tiers together: everything filed, reported, or planned in the period.</span>
                <span class="alt-stat-sub" id="alt-stat-all-sub"></span>
            </div>
            <div class="alt-stat-card">
                <span class="alt-stat-value-row"><span class="alt-stat-value" id="alt-stat-companies">—</span><span class="alt-stat-label">Companies</span></span>
                <span class="alt-stat-desc">Coverage in this view.</span>
                <span class="alt-stat-line"><b id="alt-stat-industries">—</b> <span id="alt-stat-industries-label">industries</span></span>
                <span class="alt-stat-line"><b id="alt-stat-countries">—</b> <span id="alt-stat-countries-label">countries</span></span>
                <span class="alt-stat-line"><b id="alt-stat-states">—</b> <span id="alt-stat-states-label">US states</span></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-fam-verified">
                <span class="alt-stat-value" id="alt-stat-ai">—</span>
                <span class="alt-stat-label">🤖 AI-linked verified cuts (specific)</span>
                <span class="alt-stat-desc">Part of Verified, in the employer's own words: statements like "AI now handles this work" or "replaced by AI."</span>
                <span class="alt-stat-sub" id="alt-stat-ai-sub"></span>
                <span class="alt-stat-sub" id="alt-stat-ai-share-line"></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-fam-announced">
                <span class="alt-stat-value" id="alt-stat-ai-announced">—</span>
                <span class="alt-stat-label">🤖 AI-linked planned cuts (announced)</span>
                <span class="alt-stat-desc">Part of Announced: plans citing AI, like "cutting roles as we adopt AI."</span>
                <span class="alt-stat-sub" id="alt-stat-ai-announced-sub"></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-fam-all">
                <span class="alt-stat-value" id="alt-stat-ai-broad">—</span>
                <span class="alt-stat-label">🤖 AI-linked, broad (verified + announced)</span>
                <span class="alt-stat-desc">Part of All job cuts: anything the company or press tied to AI, like "amid AI push" or "AI pivot."</span>
                <span class="alt-stat-sub" id="alt-stat-ai-broad-sub"></span>
                <span class="alt-stat-sub" id="alt-stat-ai-broad-share-line"></span>
            </div>
        </div>
        <nav class="alt-stats-links" aria-label="About these results">
            <a class="alt-method-link" href="#alt-metric-definitions">What these numbers mean</a>
            <a class="alt-method-link" href="#alt-challenger-comparison">Why US figures differ from Challenger</a>
            <a class="alt-method-link" href="#alt-data-sources">Where do we get this data?</a>
            <a class="alt-btn alt-btn-sm" href="<?php echo esc_url(home_url('/ai-layoff-tracker/publisher-tools/')); ?>">Want to embed this tracker on your site? Get the free widget →</a>
        </nav>
    </section>

    <?php $alt_expand = '<button type="button" class="alt-expand" aria-label="Expand chart" title="Expand"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg></button>'; ?>
    <div class="alt-minigrid">
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Jobs cut per month <span class="alt-chart-sub" id="alt-trend-range"></span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-weekly" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-weekly"></canvas></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">By industry <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-industries" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-barlist" id="alt-bars-industries"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Reasons cited <span class="alt-chart-sub">tap to filter</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-reasons" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-reasons"></canvas></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">By US state <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-states" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-barlist" id="alt-bars-states"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h" id="alt-country-chart-title">By country <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-countries" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-barlist" id="alt-bars-countries"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">Largest single job cuts <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-leaders" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-leaders"></div>
        </div>
        <div class="alt-mini">
            <div class="alt-chart-head"><div class="alt-chart-h">Repeat layoffs <span class="alt-chart-sub">companies with 2+ rounds in this period · tap to filter</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-repeat" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-repeat"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">AI share of Verified, monthly <span class="alt-chart-sub">how attribution is trending</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-ai-share-trend" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-chart-box"><canvas id="alt-chart-ai-share-trend"></canvas></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">By data source <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-sourcetypes" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-sourcetypes"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">This year vs last year <span class="alt-chart-sub">verified cuts · select 2+ years to compare more</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-yoy" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-chart-box"><canvas id="alt-chart-yoy"></canvas></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">AI intensity by industry <span class="alt-chart-sub">share of each industry's cuts blamed on AI · industries under 1,000 cuts excluded</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-ai-intensity" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-ai-intensity"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">Roles most impacted <span class="alt-chart-sub" id="alt-roles-sub">Each bar is total job cuts for that team; the <span class="alt-ai-key"></span> orange part and 🤖 number are the AI-linked share. From only the reports that named which teams were cut.</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-roles" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-roles"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Cumulative AI-attributed cuts <span class="alt-chart-sub" id="alt-cum-range"></span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-ai-cumulative" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-ai-cumulative"></canvas></div>
        </div>
    </div>

    <div class="alt-count-row" id="alt-count-row">
        <div class="alt-count-left">
            <span id="alt-table-count" class="alt-count-strong">Loading…</span>
        </div>
        <div class="alt-toolbar-actions">
            <a class="alt-btn alt-btn-sm" id="alt-export-csv" href="<?php echo esc_url($alt_csv); ?>"><?php echo $alt_dl; ?> <span id="alt-export-csv-label">CSV</span></a>
            <a class="alt-btn alt-btn-sm" id="alt-export-json" href="<?php echo esc_url($alt_json); ?>"><?php echo $alt_dl; ?> <span id="alt-export-json-label">JSON</span></a>
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


    <section class="alt-methodology alt-faq" itemscope>
        <div class="alt-detail-h" role="heading" aria-level="2" style="font-size:19px;margin:0 0 10px">Frequently asked questions</div>
        <?php foreach (alt_faq_items() as $qa) : ?>
        <details class="alt-faq-item">
            <summary><?php echo esc_html($qa[0]); ?></summary>
            <div class="alt-method-body"><p><?php echo esc_html($qa[1]); ?><?php
                if (isset($qa[2]) && is_array($qa[2])) {
                    echo ' <a href="' . esc_url(home_url('/' . ltrim($qa[2][0], '/'))) . '">' . wp_kses($qa[2][1], array()) . '</a>';
                } ?></p></div>
        </details>
        <?php endforeach; ?>
    <details class="alt-methodology" id="alt-metric-definitions">
        <summary>Methodology &amp; sources (for journalists &amp; researchers)</summary>
        <div class="alt-method-body">
            <p><b>What the summary cards mean.</b> <b>Verified job cuts</b> is the main figure: cuts with a filing or independently reported source behind them. <b>Explicitly AI-attributed</b> is a subset of Verified job cuts where the source explicitly names AI as a cause. <b>Announced job cuts</b> is a separate announcement-history figure: source-linked plans reported at announcement stage. A later filing or report is linked or merged when confidently matched; an unmatched announcement is <b>not</b> a claim that cuts remain unexecuted. Announced cuts are not counted in Verified or AI-attributed totals, so the cards do not double-count.</p>
            <p><b>Geography in the cards.</b> Country and US-state filters describe the documented location of affected jobs, not an employer's headquarters or every place it operates. A national announcement without a source-supported job-location state remains state-unspecified rather than being assigned to a state by inference.</p>
            <p><b>What this is.</b> A continuously updated, source-linked database of publicly reported layoffs worldwide. It records the source, evidence quote, event status and revision history so every figure can be independently checked. It is not a claim of complete coverage in every country.</p>

            <p><b>Where the data comes from.</b> Sources are always labeled on the entry:
            <span class="alt-badge alt-badge-gold">SEC filing</span> legal 8-K and 6-K filings pulled from SEC EDGAR full-text search (strongest evidence; US public companies and foreign private issuers that file with the SEC).
            <span class="alt-badge alt-badge-warn">WARN notice</span> state government mass-layoff filings from <?php echo (int) $alt_cov['states']; ?> covered US states.
            <span class="alt-badge alt-badge-silver">Company statement</span> reviewed investor-relations and newsroom feeds.
            <span class="alt-badge alt-badge-bronze">News</span> named reports discovered through GDELT and NewsAPI, then retained only when the record has usable evidence. Eurofound ERM is a separately labeled, thresholded European announcement source.</p>

            <p><b>How often it updates.</b> News and SEC filings: twice daily (morning and after US market close, ET). WARN notices: daily at 11 AM ET, sweeping every covered state. An automated anomaly review runs daily at noon ET, flagging statistically unusual entries (very large single notices, same company filing in several states, weak source links) for human inspection before anyone else finds them.</p>

            <p><b>How entries are extracted and checked.</b> Discovery searches a dialect-aware vocabulary (layoffs, redundancies, retrenchment, dismissals, sackings, workforce reduction and more than thirty other phrasings) across GDELT's 65-language translated index, so coverage that never uses the word "layoff" still surfaces. News and filings are machine-extracted; core facts must appear in the source text. Counts parse conservatively (ranges resolve to the lower bound). Countries and industries normalize through fixed vocabularies; implausible values are rejected. New records carry an evidence confidence and publication status. Exact fingerprints, same-company guards and cross-source comparison prevent double counting; uncertain candidates remain provisional instead of silently inflating verified totals. WARN filings skip the language model and remain exempt from fuzzy dedup because one employer can legally file several distinct notices.</p>

            <p><b>How the AI tag works.</b> We distinguish AI as a <em>primary cause</em>, a contributing cause, a selection/operations tool, background context, and an explicit denial. Only primary or contributing cause classifications may be AI-attributed, and each must carry an exact supporting quote found in the source text. AI investment, future automation projections, and AI used to select workers do not qualify by themselves. Alongside the strict tag we also maintain a separately labeled <b>AI-linked, broad (Challenger-style)</b> measure that counts loose attributions the way Challenger and layoffs.fyi do &mdash; cuts made while funding an AI pivot, AI-driven market disruption, and press AI framing. The broad measure appears only on the US comparison charts and in the <code>ai_broad_jobs</code> API field; it is never mixed into the strict verified-AI totals.</p>

            <p><b>How "Roles most impacted" works.</b> When a source names which teams were cut (for example "laying off customer-support and recruiting staff"), a model reads that stored text and maps it to a fixed set of role categories; a second independent pass must agree, and a supporting quote must be present, before the category is stored. Nothing is inferred from a company's industry or guessed. Each bar shows the <b>total job cuts</b> attributed to that team, and the orange segment plus the 🤖 figure show how many of those were <b>AI-linked</b> — so a bar with no orange is job cuts we could not tie to AI, not an error. This chart covers <em>only</em> the minority of records whose source actually named the teams affected, so it is a sample of where cuts land, never a breakdown of the full total.</p>
            <p><b>Coverage and honest limitations.</b> US depth is greatest because of WARN and SEC sources. Europe has structured coverage of large announcements through Eurofound ERM. Outside those live collectors, country-level coverage is currently worldwide news discovery and any explicitly reviewed company newsroom feed; named filing systems such as SEDAR+, RNS, ASX, TDnet and HKEXnews are research candidates, not silently assumed feeds. WARN and ERM have their own thresholds and geography rules, so they should not be summed as if they were a complete national census. Multi-state and multi-country events can overlap; the entry and source fields disclose that risk. Entries dated in the future are announced or filed but not yet completed.</p>

            <p><b>What we exclude.</b> Rumored or unsourced layoffs; layoffs with no stated job count; forward-looking projections (e.g. "could cost X jobs by 2050") rather than announced or executed cuts; and retrospective summary articles that would double-count events already tracked.</p>

            <p><b>Why our totals differ from other headline numbers.</b> Three kinds of trackers measure three different things. Government statistics (BLS) count <em>every</em> separation in the economy, millions per month, with no event-level detail. Announcement surveys (Challenger, Gray &amp; Christmas; the WSJ and TrueUp trackers) count corporate <em>intentions</em>: when a CEO announces "20,000 cuts over the next two years," the full 20,000 lands in their total that day, even though much of it may come through attrition, get scaled back, or never produce a single filing. This tracker counts only what has a <em>verifiable document or quoted primary source behind it</em>: the WARN notices and SEC filings that appear as those 20,000 cuts actually execute, plus reported cuts with a named-outlet source. A worked example: in the first half of 2026, announcement surveys reported roughly 443,600 US job cuts (Challenger, through June); verified filings and sourced reports here totaled <span id="alt-worked-ours">about 175,000</span> for the same period, both correct answers to different questions. Theirs answers "what are companies saying?" Ours answers "what can you prove?" Treat our verified figure as a documented floor: smaller than the estimates, but every single number is clickable back to a legal filing or named outlet. Since July 2026 we also track <em>announcement-stage</em> cuts as their own labeled tier ("Announced", tagged in the table and shown as a separate headline number) so both questions are answered on one page, and unlike the announcement surveys, every announcement here links to its source too.</p>

            <p><b>Using the data.</b> Free with attribution to <b>asktherecruiter.com</b>. The CSV and JSON buttons download exactly what your current filters show (or the full dataset when unfiltered); each chart offers its own image or data download. Programmatic access: <code>GET /blog/wp-json/layoffs/v1/query</code> (paginated; filter params match the page: years, quarters, months, industry, country, state, sources, reasons, q, from, to) and <code>GET /blog/wp-json/layoffs/v1/aggregate</code> for totals and breakdowns. Corrections get priority via the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a> or info@asktherecruiter.com, and every fix is disclosed in the corrections log below.</p>
        </div>
    </details>
    <details class="alt-methodology" id="alt-data-sources">
        <summary>Where do we get this data? Every source, by country</summary>
        <div class="alt-method-body">
            <p>Official government filings and notices are collected directly (SEC EDGAR incl. Item 2.05 exit-cost filings, WARN notices from 44 US jurisdictions, Eurofound ERM for the EU, discovery probes for Japan, South Korea and Brazil), press-release wires and reviewed company IR feeds are monitored, and 499 reviewed news outlets across 198 countries surface coverage through GDELT's 65-language index and NewsAPI — allowlist-only, never crawled directly. Every published event links to its source.</p>
            <?php include ALT_PLUGIN_DIR . 'templates/partials/country-sources-table.php'; ?>
        </div>
    </details>
    <div class="alt-mini alt-chart-card alt-conversion-card" id="alt-conversion-card">
        <div class="alt-chart-head">
            <div class="alt-chart-h">Do announced cuts actually happen? <span class="alt-chart-sub">share of each month's announced job cuts that show verified records (filings or sourced reports) from the same company within 6 months. Matches are capped per announcement, so a month can never exceed 100%.</span></div>
            <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-conversion" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><button type="button" class="alt-chart-dl" data-dl="alt-chart-conversion" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
        </div>
        <div class="alt-chart-box"><canvas id="alt-chart-conversion" aria-label="Announced-to-verified conversion by announcement month"></canvas></div>
        <p class="alt-muted" id="alt-conversion-note" style="display:none"></p>
    </div>
    <details class="alt-methodology" id="alt-challenger-comparison">
        <summary>US AI-announcement reconciliation with Challenger</summary>
        <div class="alt-method-body">
            <p><b>Why the figures differ.</b> The cards above are scoped by the job-location country filter, while Challenger measures announcements by US-based employers. They are therefore not a like-for-like Challenger total. This is a transparent coverage comparison, not an accuracy score and not a command to change our totals. Two labeled pairs are compared, each updated automatically when Challenger publishes its monthly report: <b>Challenger AI cuts vs AskTheRecruiter announced AI cuts (strict)</b>, and <b>Challenger all announced cuts vs AskTheRecruiter announced US cuts</b>. The strict AskTheRecruiter figures include only canonical events with a source-evidenced announcement date, a US-based employer and announcement-stage status (plus AI as the primary stated cause for the AI pair). The wider job-location/any-AI figure is diagnostic only and is not comparable to Challenger.</p>
            <p><b>The teal "AI-linked, broad (US job location)" line</b> measures AI the way Challenger and layoffs.fyi do: it adds events where the company or press tied the cuts to AI loosely, including layoffs made while funding an AI pivot and AI-driven market disruption. Our strict AI tag (the employer's own words, quote on file) stays separate and unchanged; the broad line exists so the two counting philosophies can be compared side by side on the same chart.</p>
            <p><b>The orange "US-employer basis (Challenger-comparable)" line</b> fixes the remaining scope mismatch: Challenger counts announced cuts by US-headquartered employers, while our country filter is job location, so a US company's multi-country cut (for example Oracle's 21,000) is invisible to the plain US view. This line counts an event when its recorded employer domicile is the United States, and falls back to US job location only for events with no recorded domicile. Domicile comes from source-evidenced enrichment or from a curated registry of deterministic, publicly referenced headquarters facts; where the headquarters is genuinely ambiguous the field stays blank rather than guessed.</p>
            <?php if ($alt_challenger_records) : ?>
            <?php if (count($alt_challenger_chart) >= 2) : ?>
            <div class="alt-challenger-chart">
                <canvas id="alt-chart-challenger-monthly" data-points="<?php echo esc_attr(wp_json_encode($alt_challenger_chart)); ?>" aria-label="Monthly Challenger and strict tracker AI-announcement comparison"></canvas>
            </div>
            <p class="alt-muted">Monthly, source-linked announcement figures. This is a coverage reconciliation, not an accuracy score.</p>
            <div class="alt-challenger-chart">
                <canvas id="alt-chart-challenger-reconciliation" data-points="<?php echo esc_attr(wp_json_encode($alt_challenger_chart)); ?>" aria-label="Cumulative year-to-date Challenger and strict tracker AI-announcement comparison"></canvas>
            </div>
            <p class="alt-muted">Cumulative year-to-date values use the same reference months and official reports.</p>
            <?php else : ?>
            <p class="alt-muted">The first official comparison is retained below. A cumulative month-by-month trend will appear automatically after a second official report month is recorded.</p>
            <?php endif; ?>
            <div class="alt-source-health alt-challenger-table">
                <table>
                    <thead><tr><th>Announcement month</th><th>Challenger AI cuts (month)</th><th>AskTheRecruiter AI cuts, strict (month)</th><th>Monthly AI gap</th><th>Challenger AI cuts (YTD)</th><th>AskTheRecruiter AI cuts, strict (YTD)</th><th>YTD AI gap</th><th>Challenger all cuts (month)</th><th>AskTheRecruiter announced US cuts (month)</th><th>Official report</th></tr></thead>
                    <tbody>
                    <?php foreach ($alt_challenger_records as $alt_benchmark) :
                        $alt_challenger_total = max(0, (int) ($alt_benchmark['challenger_ai_jobs_ytd'] ?? 0));
                        $alt_tracker_total = max(0, (int) ($alt_benchmark['tracker_ai_primary_announced_us_employer_jobs_ytd'] ?? 0));
                        $alt_gap = max(0, $alt_challenger_total - $alt_tracker_total);
                        $alt_has_monthly = array_key_exists('challenger_ai_jobs_month', $alt_benchmark) && array_key_exists('tracker_ai_primary_announced_us_employer_jobs_month', $alt_benchmark);
                        $alt_challenger_month = $alt_has_monthly ? max(0, (int) $alt_benchmark['challenger_ai_jobs_month']) : null;
                        $alt_tracker_month = $alt_has_monthly ? max(0, (int) $alt_benchmark['tracker_ai_primary_announced_us_employer_jobs_month']) : null;
                        $alt_monthly_gap = $alt_has_monthly ? max(0, $alt_challenger_month - $alt_tracker_month) : null;
                        $alt_period = !empty($alt_benchmark['reference_month']) ? $alt_benchmark['reference_month'] : (!empty($alt_benchmark['report_month']) ? $alt_benchmark['report_month'] : substr((string) ($alt_benchmark['recorded_at'] ?? ''), 0, 10));
                    ?>
                        <tr>
                            <td><?php echo esc_html($alt_period ?: 'Recorded comparison'); ?></td>
                            <td><?php echo $alt_has_monthly ? number_format($alt_challenger_month) : '—'; ?></td>
                            <td><?php echo $alt_has_monthly ? number_format($alt_tracker_month) : '—'; ?></td>
                            <td><?php echo $alt_has_monthly ? number_format($alt_monthly_gap) . ' fewer qualifying tracker records' : '—'; ?></td>
                            <td><?php echo number_format($alt_challenger_total); ?></td>
                            <td><?php echo number_format($alt_tracker_total); ?></td>
                            <td><?php echo number_format($alt_gap); ?> fewer qualifying tracker records</td>
                            <td><?php echo isset($alt_benchmark['challenger_total_jobs_month']) && $alt_benchmark['challenger_total_jobs_month'] !== null ? number_format((int) $alt_benchmark['challenger_total_jobs_month']) : '—'; ?></td>
                            <td><?php echo isset($alt_benchmark['tracker_announced_us_employer_jobs_month']) && $alt_benchmark['tracker_announced_us_employer_jobs_month'] !== null ? number_format((int) $alt_benchmark['tracker_announced_us_employer_jobs_month']) : '—'; ?></td>
                            <td><?php if (!empty($alt_benchmark['benchmark_url'])) : ?><a href="<?php echo esc_url($alt_benchmark['benchmark_url']); ?>" target="_blank" rel="noopener">Challenger report</a><?php else : ?>—<?php endif; ?></td>
                        </tr>
                    <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
            <p>The current gap principally reflects incomplete source-evidenced announcement-date and employer-domicile enrichment, plus different source mixes. It does <b>not</b> mean that untracked events are false, that tracked events are wrong, or that the tracker is complete. Each monthly report remains available here even when the workflow flags a large gap for investigation.</p>
            <?php else : ?>
            <p>No retained Challenger comparison is available yet. This is a reporting setup state, not evidence of zero layoffs.</p>
            <?php endif; ?>
        </div>
    </details>
    <details class="alt-methodology">
        <summary>Which countries are in which region tab?</summary>
        <div class="alt-method-body" id="alt-region-defs">
            <p>The region tabs are views over the worldwide data. The full country list for each tab loads here.</p>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>How our numbers compare to other trackers</summary>
        <div class="alt-method-body">
            <p>Different trackers measure different things. Here are the factual differences, so you can pick the right number for your purpose.</p>
            <p><b><a href="https://www.challengergray.com/press/press-releases/" target="_blank" rel="noopener">Challenger, Gray &amp; Christmas</a></b> reports monthly totals of <em>announced</em> US job cuts, compiled from press reports and company statements, including estimates and multi-year plans. It is published as monthly press releases with no per-event public database. Because announcements exceed executed cuts, Challenger's totals run above any verified-event count, including ours.</p>
            <p><b><a href="https://www.wsj.com/economy/jobs" target="_blank" rel="noopener">WSJ layoffs coverage</a></b> is editorially selected major announcements with newsroom verification. There is no downloadable dataset, and coverage is selective by design.</p>
            <p><b><a href="https://www.trueup.io/layoffs" target="_blank" rel="noopener">TrueUp</a></b> and <b><a href="https://layoffs.fyi" target="_blank" rel="noopener">Layoffs.fyi</a></b> are technology-sector trackers built from announcements and crowdsourced reports, and they are downloadable. Their scope corresponds to our <em>Technology industry</em> filter, not our all-industry total.</p>
            <p><b>Official statistics</b> such as <a href="https://www.bls.gov/jlt/" target="_blank" rel="noopener">US BLS JOLTS</a> (all separations economy-wide, millions per month), <a href="https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/redundancies" target="_blank" rel="noopener">UK ONS redundancies</a>, and <a href="https://ec.europa.eu/eurostat" target="_blank" rel="noopener">Eurostat</a> are survey-based aggregates with no company-level detail. Event trackers measure a different universe and will not match them.</p>
            <p><b>This tracker</b> puts verified events only in the headline totals (filings and sourced reports, each one linked), keeps announcement-stage figures in a separately labeled tier, discloses corrections automatically below, and publishes its data and code. When our number differs from a tracker above, the difference is definitional, and both definitions are stated here so either number can be used correctly.</p>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>Known gaps &amp; why the country count changes</summary>
        <div class="alt-method-body">
            <p>The full directory of every pipeline — the SEC, all state WARN registries with live links, Eurofound ERM, and the news index — lives on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data Sources page</a>. The disclosures below cover what is <em>not</em> yet included.</p>
            <p><b>Why the country count grows over time.</b> The number of countries is not a setting we can raise; it reflects where large, press-covered layoffs have actually happened in our window. GDELT already searches every country on earth in 65+ languages, so a country appears the moment a credible outlet there covers a qualifying layoff. As events occur and as we add more trusted local outlets, the count rises on its own. This is honest by design: we show the countries where verifiable events exist, not a padded list.</p>
            <p><b>Known gaps, stated plainly.</b> We do not yet operate direct connectors for Canada SEDAR+, UK RNS, ASX, TDnet/EDINET, NSE/BSE, HKEXnews, SGXNet, SENS, DART or TASE; they are maintained as official-source research candidates and will be named as live only after a stable public interface, tests and source-health monitoring exist. A few countries also publish official per-company redundancy records we do not ingest yet, including Belgium's FPS Employment collective-dismissal reports, Italy's weekly CIGS decree lists, and Sweden's varsel statistics. Most countries, including Germany and Mexico, treat employer identity in redundancy filings as confidential, so press coverage through GDELT in local languages is the primary source there. Events too small for any press coverage, any WARN threshold, or the ERM threshold of 100 jobs will not appear in any tracker, including this one.</p>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>Data notes &amp; corrections log</summary>
        <div class="alt-method-body">
            <p>Errors are corrected openly, not silently. Every correction to published figures is dated and described here, newest first, and corrected rows are also flagged <code>edited: true</code> in the API. The list scrolls, because it grows a little every day as the data self-corrects.</p>
            <p>For reproducible monitoring, the machine-readable <a href="<?php echo esc_url(rest_url('layoffs/v1/quality-status')); ?>">quality status endpoint</a> reports dataset revision, recent corrections, collector health, retained-source integrity and the status of each coverage workstream. Pending work is shown as pending—not silently treated as coverage.</p>
            <ul class="alt-corrections-scroll">
                <?php
                // The log renders from the actual audit trail: every /edit and
                // /trash appends to alt_corrections_log, so nothing can be
                // corrected without being disclosed. Newest first.
                $alt_corr = get_option('alt_corrections_log');
                foreach (is_array($alt_corr) ? array_reverse($alt_corr) : array() as $c) : ?>
                <li><b><?php echo esc_html($c['date']); ?>: <?php echo (int) $c['count']; ?> entr<?php echo ((int) $c['count'] === 1) ? 'y' : 'ies'; ?> <?php echo esc_html($c['action']); ?><?php echo $c['detail'] ? ' (' . esc_html($c['detail']) . ')' : ''; ?>.</b> <?php echo esc_html($c['reason']); ?></li>
                <?php endforeach; ?>
                <li><b>2026-07-15: Florida test rows removed, 87,600 jobs.</b> Florida's official WARN export contains internal test entries, which are fictitious notices sharing one WARN number and using non-existent zip codes. Eight such rows were removed, the largest a fake 78,788-worker "AT&amp;T" notice that briefly ranked as our biggest entry. Our importer now skips test-named rows, and each removed row is permanently blocked from re-import.</li>
                <li><b>2026-07-15: Country assigned to 88 news and SEC entries.</b> These rows had no country recorded, which hid them from the regional views and country charts, though they were always in the worldwide totals. Each was resolved from its own source article. The largest were Oracle (30,000, spanning the US, India, Canada, Mexico and Uruguay, so "Multiple countries") and BBC (2,000, United Kingdom).</li>
                <li><b>2026-07-15: Ideal US Talent Systems RI corrected from 9,891 to 2.</b> The Rhode Island notice states the company-wide figure with only 2 RI employees affected, and the per-state filings for DC, GA, IL and VA are already separate entries. Counting the company-wide total under RI double-counted the event.</li>
                <li><b>2026-07-15: Ten non-events removed.</b> These were SEC-filing extraction mistakes: severance dollar figures and workforce-reduction percentages misread as headcounts, WARN Act boilerplate clauses from acquisition agreements, and three duplicate rows of one Meta story carrying wrong dates.</li>
            </ul>
            <p>Spotted something off? Every entry links to its primary source so you can check us. Send corrections through the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a> or to <a href="mailto:info@asktherecruiter.com">info@asktherecruiter.com</a>, and they get priority.</p>
        </div>
    </details>
    </section>

    <div class="alt-cite-box">
        <span class="alt-detail-h">Cite this tracker</span>
        <code id="alt-cite-text">AI Layoff Tracker, AskTheRecruiter.com. Accessed <span id="alt-cite-date"></span>. Data from SEC EDGAR 8-K filings, US state WARN notices, and credible news outlets.</code>
        <button type="button" class="alt-btn alt-btn-sm" id="alt-cite-copy">Copy</button>
    </div>

    <div class="alt-journalist">
        <div class="alt-journalist-text">
            <strong>Built for journalists &amp; researchers</strong>
            <p>Free to use with attribution to <strong>asktherecruiter.com</strong>. Every figure links to a primary source. Query the full dataset live through our API, and reach the editors at <a href="<?php echo esc_url(home_url('/contact/')); ?>">our contact page</a>, where corrections get priority.</p>
        </div>
        <code class="alt-journalist-api"><?php echo esc_html('GET ' . wp_make_link_relative($alt_api)); ?></code>
    </div>

    <footer class="alt-provenance" aria-label="Tracker provenance">
        <span>Tracker release <b>v<?php echo esc_html(ALT_VERSION); ?></b></span>
        <span id="alt-provenance-quality" aria-live="polite">Dataset status loading…</span>
        <a class="alt-method-link" href="#alt-metric-definitions">Methodology</a>
        <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press &amp; media</a>
    </footer>
</div>
