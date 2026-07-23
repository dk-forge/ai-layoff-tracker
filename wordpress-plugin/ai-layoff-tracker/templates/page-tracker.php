<?php
/** Main filterable tracker, rendered by [alt_tracker]. */
if (!defined('ABSPATH')) exit;

$alt_csv  = admin_url('admin-post.php?action=alt_export_csv');
$alt_json = admin_url('admin-post.php?action=alt_export_json');
$alt_api  = rest_url('layoffs/v1/query');
$alt_dl   = '<svg class="alt-dl-ico" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg>';

// --- Structured data (Schema.org) so search + answer engines (Google AI
// Overviews, ChatGPT, Perplexity) can cite the dataset WITH attribution. ---
$alt_now_ld = gmdate('Y-m-d');
$alt_org_ld = array('@type' => 'Organization', 'name' => 'AskTheRecruiter', 'url' => home_url('/'));
$alt_ld = array();
$alt_ld[] = array(
    '@context' => 'https://schema.org', '@type' => 'Dataset',
    'name' => 'AI Layoff Tracker', 'alternateName' => 'AskTheRecruiter AI Layoff Tracker',
    'description' => 'A continuously updated, source-linked database of verified job cuts worldwide, flagging the layoffs companies attribute to AI or automation. Every figure links to a primary document: an SEC filing, a state WARN notice, or a named news report.',
    'url' => home_url('/ai-layoff-tracker/'),
    'keywords' => array('layoffs', 'AI layoffs', 'job cuts', 'tech layoffs', 'WARN notices', 'workforce reduction', 'AI job losses', 'layoff tracker', '2026 layoffs'),
    'license' => 'https://creativecommons.org/licenses/by/4.0/', 'isAccessibleForFree' => true,
    'creator' => $alt_org_ld, 'publisher' => $alt_org_ld,
    'temporalCoverage' => (function_exists('alt_live_numbers') ? alt_live_numbers()['start'] : '2015') . '-01-01/' . $alt_now_ld, 'dateModified' => $alt_now_ld,
    'measurementTechnique' => 'Primary-source verification: SEC EDGAR filings, official state WARN notices, EU restructuring records, and named news reports from an allowlist of reviewed outlets.',
    'variableMeasured' => array(
        array('@type' => 'PropertyValue', 'name' => 'Verified job cuts', 'description' => 'Layoffs with a primary source document behind each figure.'),
        array('@type' => 'PropertyValue', 'name' => 'AI-attributed job cuts', 'description' => 'Layoffs the employer named AI or automation as a cause, with a supporting quote on file.'),
        array('@type' => 'PropertyValue', 'name' => 'Announced job cuts', 'description' => 'Company plans at announcement stage, in a separate labeled tier.'),
    ),
    'distribution' => array(
        array('@type' => 'DataDownload', 'encodingFormat' => 'application/json', 'contentUrl' => rest_url('layoffs/v1/query')),
        array('@type' => 'DataDownload', 'encodingFormat' => 'text/csv', 'contentUrl' => admin_url('admin-post.php?action=alt_export_csv')),
    ),
);
if (function_exists('alt_faq_items')) {
    $alt_qa_ld = array();
    foreach (alt_faq_items() as $alt_f) {
        $alt_q = is_array($alt_f) ? (string) ($alt_f[0] ?? '') : '';
        $alt_a = is_array($alt_f) ? (string) ($alt_f[1] ?? '') : '';
        if ($alt_q !== '' && $alt_a !== '') $alt_qa_ld[] = array('@type' => 'Question',
            'name' => wp_strip_all_tags($alt_q),
            'acceptedAnswer' => array('@type' => 'Answer', 'text' => wp_strip_all_tags($alt_a)));
    }
    if ($alt_qa_ld) $alt_ld[] = array('@context' => 'https://schema.org', '@type' => 'FAQPage', 'mainEntity' => $alt_qa_ld);
}
?>
<?php if (!defined('ALT_TRACKER_LD_DONE')) { define('ALT_TRACKER_LD_DONE', 1); // emit once even if the shortcode renders twice
    foreach ($alt_ld as $alt_block) {
        echo '<script type="application/ld+json">' . wp_json_encode($alt_block, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . '</script>' . "\n";
    }
} ?>
<div class="alt-wrap alt-tracker-wrap alt-dashboard">

    <?php $alt_cov = alt_coverage_counts(); ?>
    <div class="alt-narrative" id="alt-narrative"></div>
    <?php include ALT_PLUGIN_DIR . 'templates/partials/scan-scope.php'; ?>
    <?php $alt_warn_states = function_exists('alt_state_warn_urls') ? count(alt_state_warn_urls()) : 42; ?>
    <p class="alt-lead"><span class="alt-lead-text">Track source-linked layoffs worldwide. We monitor <b><?php echo number_format((int) $alt_scan_outlets); ?> reviewed news outlets across <?php echo number_format((int) $alt_scan_countries); ?> countries</b> in 65+ languages, plus <b>every SEC 8-K filing, all 50 US states (direct WARN feeds from <?php echo (int) $alt_warn_states; ?>), and EU restructuring records</b>, twice daily. Filter by country, industry, source or reason; AI labels appear only where the evidence supports them.</span><span class="alt-lead-links"><a class="alt-report-star" href="<?php echo esc_url(home_url('/ai-layoff-tracker/report/')); ?>">★ Monthly report (1-pager)</a> · <a class="alt-method-link" href="#alt-metric-definitions">Methodology</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press &amp; media</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/publisher-tools/')); ?>">Embed this tracker</a></span></p>
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
        <div class="alt-datebasis-wrap" role="group" aria-label="Count layoffs by">
            <span class="alt-datebasis-label">Count layoffs by:</span>
            <span class="alt-datebasis-switch">
            <button type="button" class="alt-datebasis-opt alt-datebasis-on" data-basis="effective" aria-pressed="true"
                title="Counts each layoff on the day the cut takes effect, the day the jobs actually end. This is our default.">When it takes effect</button>
            <button type="button" class="alt-datebasis-opt" data-basis="notice" aria-pressed="false"
                title="Counts each layoff on the day its notice was filed or announced. This is the basis most other trackers use.">When it was filed</button>
            </span>
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
        <div class="alt-filterbar-reset">
            <button type="button" id="alt-f-reset" class="alt-btn alt-btn-reset">Reset all filters</button>
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
                <span class="alt-stat-value" id="alt-stat-total">…</span>
                <span class="alt-stat-label">Verified job cuts</span>
                <span class="alt-stat-desc">Filed or reported, counted on the day each cut takes effect. The main number. <a class="alt-why-verified" href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>" target="_blank" rel="noopener">Why this is verified &rarr;</a></span>
                <span class="alt-stat-sub" id="alt-stat-total-entries"></span>
            </div>
            <div class="alt-stat-card alt-fam-announced">
                <span class="alt-stat-value" id="alt-stat-announced">…</span>
                <span class="alt-stat-label">Announced job cuts (planned)</span>
                <span class="alt-stat-desc">Company plans at announcement stage, not yet in Verified.</span>
                <span class="alt-stat-sub" id="alt-stat-announced-sub"></span>
            </div>
            <div class="alt-stat-card alt-fam-all">
                <span class="alt-stat-value" id="alt-stat-all">…</span>
                <span class="alt-stat-label">Verified + announced job cuts</span>
                <span class="alt-stat-desc">Both tiers together: everything filed, reported, or planned in the period. An announced plan often becomes a verified filing later, so this can count one cut in both stages; it is not a tally of distinct people.</span>
                <span class="alt-stat-sub" id="alt-stat-all-sub"></span>
            </div>
            <div class="alt-stat-card">
                <span class="alt-stat-value-row"><span class="alt-stat-value" id="alt-stat-companies">…</span><span class="alt-stat-label">Companies</span></span>
                <span class="alt-stat-desc">Coverage in this view.</span>
                <span class="alt-stat-line"><b id="alt-stat-industries">…</b> <span id="alt-stat-industries-label">industries</span></span>
                <span class="alt-stat-line"><b id="alt-stat-countries">…</b> <span id="alt-stat-countries-label">countries</span></span>
                <span class="alt-stat-line"><b id="alt-stat-states">…</b> <span id="alt-stat-states-label">US states</span></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-fam-verified">
                <span class="alt-stat-value" id="alt-stat-ai">…</span>
                <span class="alt-stat-label">🤖 AI cuts, verified (specific)</span>
                <span class="alt-stat-desc">Verified-tier cuts in the employer's own words: statements like "AI now handles this work" or "replaced by AI."</span>
                <span class="alt-stat-sub" id="alt-stat-ai-sub"></span>
                <span class="alt-stat-sub" id="alt-stat-ai-share-line"></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-fam-announced">
                <span class="alt-stat-value" id="alt-stat-ai-announced">…</span>
                <span class="alt-stat-label">🤖 AI cuts, announced (planned)</span>
                <span class="alt-stat-desc">Announced-tier plans that cite AI, like "cutting roles as we adopt AI."</span>
                <span class="alt-stat-sub" id="alt-stat-ai-announced-sub"></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-fam-total">
                <span class="alt-stat-value" id="alt-stat-ai-total">…</span>
                <span class="alt-stat-label">🤖 AI cuts, total (specific)</span>
                <span class="alt-stat-desc">Verified + announced added together: cuts the employer or plan explicitly named AI for. This is the two boxes to the left, summed.</span>
                <span class="alt-stat-sub" id="alt-stat-ai-total-sub"></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-stat-card-broad">
                <span class="alt-stat-value" id="alt-stat-ai-broad">…</span>
                <span class="alt-stat-label">🤖 AI-linked, broad (wider lens)</span>
                <span class="alt-stat-desc"><b>A different, looser measure</b>, a wider lens that also counts press AI-framing ("amid AI push," "AI pivot"), not just the employer's own words. It is intentionally larger than the total on the left, so it does <b>not</b> add up with the boxes above.</span>
                <span class="alt-stat-sub" id="alt-stat-ai-broad-sub"></span>
                <span class="alt-stat-sub" id="alt-stat-ai-broad-share-line"></span>
            </div>
        </div>
        <nav class="alt-stats-links alt-stats-links-box" aria-label="About these results">
            <span class="alt-stats-links-label">New here? Start with:</span>
            <a class="alt-method-link" href="#alt-metric-definitions">What these numbers mean</a>
            <a class="alt-method-link" href="#alt-data-sources">Where do we get this data?</a>
            <a class="alt-method-link" href="#alt-corrections">How we catch &amp; fix errors</a>
        </nav>
    </section>

    <details class="alt-why-lower">
        <summary class="alt-why-summary">Why our number is lower, and why it&rsquo;s the one to cite</summary>
        <div class="alt-why-body">
        <p class="alt-why-lead">Announcement surveys count what companies <em>say</em>. We count what you can <em>prove</em>. Every figure on this page clicks through to a legal filing or a named report. So our total is a <strong>documented floor</strong>: smaller than the headline estimates by design, and verifiable by design.</p>
        <div class="alt-why-grid">
            <div class="alt-why-item"><b>They book multi-year plans on day one.</b> A &ldquo;20,000 over two years&rdquo; announcement lands in their total instantly. We add each cut as its WARN notice or SEC filing actually appears.</div>
            <div class="alt-why-item"><b>They fold in receiptless separations.</b> Buyouts, attrition, and federal-workforce reductions that name no company and file nothing. Hundreds of thousands of jobs with no document to link. We don&rsquo;t claim what we can&rsquo;t source.</div>
            <div class="alt-why-item"><b>We don&rsquo;t pad to match a bigger headline.</b> A number a journalist can verify is worth more than a bigger one they can&rsquo;t. Nothing here is estimated into existence.</div>
            <div class="alt-why-item"><b>On AI, the thing this tracker exists for,</b> every flagged cut carries the employer&rsquo;s own words naming AI: quotable, clickable, and held to a standard the estimates don&rsquo;t apply to themselves.</div>
        </div>
        <p class="alt-why-quality">Every figure links to a primary source. Machine-extracted numbers are double-checked by a second independent pass, numeric changes and removals always require a human, and <b>every correction is disclosed in the <a href="#alt-corrections">open log</a></b>. Nothing is quietly edited.</p>
        <p class="alt-why-foot"><a href="#alt-metric-definitions">See the full methodology &rarr;</a> &middot; Every number, every source, one click away.</p>
        </div>
    </details>

    <?php $alt_expand = '<button type="button" class="alt-expand" aria-label="Expand chart" title="Expand"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg></button>'; ?>
    <div class="alt-minigrid">
        <div class="alt-mini alt-chart-card alt-map-card" id="alt-map-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">The map of job cuts <span class="alt-chart-sub"><b style="color:#2f6fd0">blue</b> = all job cuts &middot; <b style="color:#d0431a">red</b> = AI-linked cuts (sits inside) &middot; circle size = number of jobs &middot; hover for exact numbers, expand &#10530; for a bigger view &middot; only cuts with a named country or state are plotted; the rest are counted in the totals but not on the map</span></div>
                <span class="alt-chart-btns">
                    <span class="alt-map-toggle">
                        <button type="button" class="alt-map-scope alt-map-scope-on" data-scope="world">World</button>
                        <button type="button" class="alt-map-scope" data-scope="us">US states</button>
                    </span>
                    <button type="button" class="alt-chart-dl" data-dl="alt-chart-aimap" data-kind="png" aria-label="Download map as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?>
                </span>
            </div>
            <div class="alt-chart-box alt-map-box"><div id="alt-chart-aimap" aria-label="AI-attributed layoffs by geography"></div></div>
            <p class="alt-map-total alt-muted" id="alt-map-total"></p>
            <p class="alt-map-empty alt-muted" id="alt-map-note" style="display:none"></p>
        </div>
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
            <div class="alt-chart-head"><div class="alt-chart-h">AI intensity by industry <span class="alt-chart-sub">share of each industry's cuts the employer attributed to AI · industries under 1,000 cuts excluded</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-ai-intensity" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-ai-intensity"></div>
        </div>
        <div class="alt-mini alt-chart-card" id="alt-roles-card">
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

            <p><b>How the AI tag works.</b> We distinguish AI as a <em>primary cause</em>, a contributing cause, a selection/operations tool, background context, and an explicit denial. Only primary or contributing cause classifications may be AI-attributed, and each must carry an exact supporting quote found in the source text. AI investment, future automation projections, and AI used to select workers do not qualify by themselves. Alongside the strict tag we also maintain a separately labeled <b>AI-linked, broad</b> measure that counts looser attributions, cuts made while funding an AI pivot, AI-driven market disruption, and press AI framing. The broad measure is surfaced in the <code>ai_broad_jobs</code> API field; it is never mixed into the strict verified-AI totals.</p>

            <p><b>How "Roles most impacted" works.</b> When a source names which teams were cut (for example "laying off customer-support and recruiting staff"), a model reads that stored text and maps it to a fixed set of role categories; a second independent pass must agree, and a supporting quote must be present, before the category is stored. Nothing is inferred from a company's industry or guessed. Each bar shows the <b>total job cuts</b> attributed to that team, and the orange segment plus the 🤖 figure show how many of those were <b>AI-linked</b>, so a bar with no orange is job cuts we could not tie to AI, not an error. This chart covers <em>only</em> the minority of records whose source actually named the teams affected, so it is a sample of where cuts land, never a breakdown of the full total.</p>
            <p><b>Coverage and honest limitations.</b> US depth is greatest because of WARN and SEC sources. Europe has structured coverage of large announcements through Eurofound ERM. Outside those live collectors, country-level coverage is currently worldwide news discovery and any explicitly reviewed company newsroom feed; named filing systems such as SEDAR+, RNS, ASX, TDnet and HKEXnews are research candidates, not silently assumed feeds. WARN and ERM have their own thresholds and geography rules, so they should not be summed as if they were a complete national census. Multi-state and multi-country events can overlap; the entry and source fields disclose that risk. Entries dated in the future are announced or filed but not yet completed. Filtering the table by a country also includes cuts by employers <em>headquartered</em> there whose layoff spanned multiple countries (each such row stays labeled with its true "Multiple countries" scope, never recounted as that country alone); the headline totals stay on the stricter job-location basis, so they are never inflated by a global figure.</p>

            <p><b>What we exclude.</b> Rumored or unsourced layoffs; layoffs with no stated job count; forward-looking projections (e.g. "could cost X jobs by 2050") rather than announced or executed cuts; and retrospective summary articles that would double-count events already tracked.</p>

            <p><b>Why our totals differ from other headline numbers.</b> Three kinds of trackers measure three different things. Government statistics (BLS) count <em>every</em> separation in the economy, millions per month, with no event-level detail. Announcement surveys count corporate <em>intentions</em>: when a CEO announces "20,000 cuts over the next two years," the full 20,000 lands in their total that day, even though much of it may come through attrition, get scaled back, or never produce a single filing. This tracker counts only what has a <em>verifiable document or quoted primary source behind it</em>: the WARN notices and SEC filings that appear as those 20,000 cuts actually execute, plus reported cuts with a named-outlet source. A worked example: in the first half of 2026, announcement surveys reported roughly 443,600 US job cuts; verified filings and sourced reports here totaled <span id="alt-worked-ours">about 175,000</span> for the same period, both correct answers to different questions. Theirs answers "what are companies saying?" Ours answers "what can you prove?" Treat our verified figure as a documented floor: smaller than the estimates, but every single number is clickable back to a legal filing or named outlet. Since July 2026 we also track <em>announcement-stage</em> cuts as their own labeled tier ("Announced", tagged in the table and shown as a separate headline number) so both questions are answered on one page, and unlike the announcement surveys, every announcement here links to its source too.</p>

            <p><b>Using the data.</b> Free with attribution to <b>asktherecruiter.com</b>. The CSV and JSON buttons download exactly what your current filters show (or the full dataset when unfiltered); each chart offers its own image or data download. Programmatic access: <code>GET /blog/wp-json/layoffs/v1/query</code> (paginated; filter params match the page: years, quarters, months, industry, country, state, sources, reasons, q, from, to) and <code>GET /blog/wp-json/layoffs/v1/aggregate</code> for totals and breakdowns. Corrections get priority via the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>, and every fix is disclosed in the corrections log below.</p>
        </div>
    </details>
    <details class="alt-methodology" id="alt-data-sources">
        <summary>Where do we get this data? Every source, by country</summary>
        <div class="alt-method-body">
            <p>Official government filings and notices are collected directly (SEC EDGAR incl. Item 2.05 exit-cost filings, WARN notices from <?php echo (int) $alt_warn_states; ?> US states and DC, Eurofound ERM for the EU, discovery probes for Japan, South Korea and Brazil), press-release wires and reviewed company IR feeds are monitored, and <?php echo number_format((int) $alt_scan_outlets); ?> reviewed news outlets across <?php echo number_format((int) $alt_scan_countries); ?> countries surface coverage through GDELT's 65-language index and NewsAPI, allowlist-only, never crawled directly. Every published event links to its source. For the handful of US states that publish no usable WARN register (Arkansas, Wyoming, New Hampshire, Missouri, Hawaii, Oklahoma), we also show their official monthly BLS unemployment rate as a clearly separate context metric, sourced and dated, never mixed into the layoff counts. <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">See the full source directory</a>.</p>
            <?php include ALT_PLUGIN_DIR . 'templates/partials/country-sources-table.php'; ?>
        </div>
    </details>
    <details class="alt-methodology alt-conversion-card" id="alt-conversion-card" open>
        <summary>Do announced cuts actually happen?</summary>
        <div class="alt-method-body">
            <p class="alt-muted" style="margin-top:0">Share of each month's announced job cuts that show verified records (filings or sourced reports) from the same company within 6 months. Matches are capped per announcement, so a month can never exceed 100%.</p>
            <div class="alt-chart-box"><canvas id="alt-chart-conversion" aria-label="Announced-to-verified conversion by announcement month"></canvas></div>
            <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-conversion" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><button type="button" class="alt-chart-dl" data-dl="alt-chart-conversion" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button></span>
            <p class="alt-muted" id="alt-conversion-note" style="display:none"></p>
        </div>
    </details>
    <details class="alt-methodology">
        <summary>Which countries are in which region tab?</summary>
        <div class="alt-method-body" id="alt-region-defs">
            <p>The region tabs are views over the worldwide data. The full country list for each tab loads here.</p>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>Why our numbers differ from other trackers</summary>
        <div class="alt-method-body">
            <p><b>Every tracker measures a different thing, so the numbers should differ.</b> We count <em>verified events</em>: cuts with a filing or named-outlet source behind them, each one clickable. The big announcement trackers count <em>corporate intentions</em>. Neither is wrong; they answer different questions. Our total sits below the headline announcement estimates, and the gap is fully explainable, here is exactly why, and why we treat it as a feature, not a shortfall.</p>

            <p><b>1 &middot; They book multi-year plans on day one; we count cuts as they happen.</b> When a company announces "20,000 cuts over two years," the announcement trackers record all 20,000 that day. We add each cut as its WARN notice or SEC filing actually appears. Over a year that is a large, permanent gap, their figure is a forecast, ours is an execution ledger.</p>

            <p><b>2 &middot; They include separations that name no event.</b> Announcement totals fold in voluntary buyouts, deferred resignations, and attrition programs, including large federal-workforce reductions that file no WARN notice and name no company. In 2025 that was roughly <b>250,000–300,000 jobs</b> of the announcement total alone. There is no document or named source to link, so we do not claim it.</p>

            <p><b>3 &middot; They count cuts no outlet ever named.</b> Announcement surveys aggregate press mentions and estimates we cannot reproduce. We only publish what traces to a source, so an unsourced cut never enters our total.</p>

            <p><b>4 &middot; We date each cut by when it takes effect, not when it was filed.</b> Most trackers count a layoff on the day its WARN notice is filed or the cut is announced. We count it on the day the jobs actually end, because that is what a worker lives through and what a labor-market reader wants to measure. The two bases answer different questions: filing date asks "when did we hear about it," effective date asks "when did it happen." The gap is small and can fall either way; in 2026 the effective-date basis runs slightly higher, because more notices were filed in 2025 for cuts that land in 2026 than were filed in 2026 for cuts landing in 2027. We store both dates, so any figure here can be recounted on either basis.</p>
            <p><b>The bottom line, stated plainly.</b> Our verified figure is a <em>documented floor</em>, smaller than the estimates, but every single number clicks through to a legal filing or a named report. We deliberately do <b>not</b> pad it to match a headline estimate, because a number a journalist can verify is worth more than a bigger one they cannot. And on the measure this tracker exists for, <b>layoffs companies attribute to AI</b>, our count actually <em>exceeds</em> the headline announcement trackers every year, because we surface AI attributions from primary sources they never itemize.</p>

            <p><b>Where each kind of tracker fits:</b></p>
            <ul class="alt-method-list">
                <li><b>Announcement surveys</b>, monthly totals of <em>announced</em> US cuts from press reports and company statements, including estimates and multi-year plans. Typically published as press releases; no per-event public database.</li>
                <li><b>Editorial newsroom trackers</b>, selected major announcements with newsroom verification. No downloadable dataset; selective by design.</li>
                <li><b>Sector trackers</b>, technology-focused trackers built from announcements and crowdsourced reports. Their scope matches our <em>Technology</em> filter, not our all-industry total.</li>
                <li><b>Official statistics</b>, <a href="https://www.bls.gov/jlt/" target="_blank" rel="noopener">US BLS JOLTS</a>, <a href="https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/redundancies" target="_blank" rel="noopener">UK ONS</a>, <a href="https://ec.europa.eu/eurostat" target="_blank" rel="noopener">Eurostat</a> count <em>all</em> separations economy-wide (millions/month) with no company detail. A different universe entirely.</li>
                <li><b>This tracker</b>, verified events in the headline, announcement-stage figures in a separate labeled tier, corrections logged openly, data and code public. When our number differs, the difference is definitional, and both definitions are stated here so either can be cited correctly.</li>
            </ul>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>Known gaps &amp; why the country count changes</summary>
        <div class="alt-method-body">
            <p>The full directory of every pipeline, the SEC, all state WARN registries with live links, Eurofound ERM, and the news index, lives on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data Sources page</a>. The disclosures below cover what is <em>not</em> yet included.</p>
            <p><b>Why the country count grows over time.</b> The number of countries is not a setting we can raise; it reflects where large, press-covered layoffs have actually happened in our window. GDELT already searches every country on earth in 65+ languages, so a country appears the moment a credible outlet there covers a qualifying layoff. As events occur and as we add more trusted local outlets, the count rises on its own. This is honest by design: we show the countries where verifiable events exist, not a padded list.</p>
            <p><b>Known gaps, stated plainly.</b> We do not yet operate direct connectors for Canada SEDAR+, UK RNS, ASX, TDnet/EDINET, NSE/BSE, HKEXnews, SGXNet, SENS, DART or TASE; they are maintained as official-source research candidates and will be named as live only after a stable public interface, tests and source-health monitoring exist. A few countries also publish official per-company redundancy records we do not ingest yet, including Belgium's FPS Employment collective-dismissal reports, Italy's weekly CIGS decree lists, and Sweden's varsel statistics. Most countries, including Germany and Mexico, treat employer identity in redundancy filings as confidential, so press coverage through GDELT in local languages is the primary source there. Events too small for any press coverage, any WARN threshold, or the ERM threshold of 100 jobs will not appear in any tracker, including this one.</p>
        </div>
    </details>

    <details class="alt-methodology" id="alt-corrections" open>
        <summary>Data notes &amp; corrections log</summary>
        <div class="alt-method-body">
            <p class="alt-corrections-framing"><b>Why this log is a feature, not a warning.</b> Many early entries are the pipeline catching and fixing its own extraction bugs during pre-launch QA, which is the point: a system that finds and discloses its own errors is more trustworthy than one that hides them.</p>
            <p>Errors are corrected openly, not silently. Every correction to published figures is dated and described here, newest first, and corrected rows are also flagged <code>edited: true</code> in the API. The list scrolls, because it grows a little every day as the data self-corrects.</p>
            <p>For reproducible monitoring, the machine-readable <a href="<?php echo esc_url(rest_url('layoffs/v1/quality-status')); ?>">quality status endpoint</a> reports dataset revision, recent corrections, collector health, retained-source integrity and the status of each coverage workstream. Pending work is shown as pending, not silently treated as coverage.</p>
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
            <p>Spotted something off? Every entry links to its primary source so you can check us. Send corrections through the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a> and they get priority.</p>
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
