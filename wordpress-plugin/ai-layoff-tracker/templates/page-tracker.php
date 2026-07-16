<?php
/** Main filterable tracker — rendered by [alt_tracker]. */
if (!defined('ABSPATH')) exit;

$alt_csv  = admin_url('admin-post.php?action=alt_export_csv');
$alt_json = admin_url('admin-post.php?action=alt_export_json');
$alt_api  = rest_url('layoffs/v1/query');
$alt_dl   = '<svg class="alt-dl-ico" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg>';
?>
<div class="alt-wrap alt-tracker-wrap alt-dashboard">

    <?php $alt_cov = alt_coverage_counts(); ?>
    <p class="alt-lead">Verified layoffs worldwide, across all industries and causes, with the ones companies explicitly blame on AI flagged and quoted. Every entry links to its primary source: SEC 8-K filings, official WARN notices from <b><?php echo (int) $alt_cov['states']; ?> US states</b>, the EU's official restructuring database, and credible news from <b>more than 200 trusted newsrooms</b> across five continents and <b><?php echo (int) $alt_cov['countries']; ?> countries</b>. Use the country, US-state, industry and date filters to scope the data to your region.</p>

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
    <p class="alt-narrative" id="alt-narrative"></p>

    <div id="alt-dashboard-status" class="alt-status" role="status" style="display:none"></div>

    <div class="alt-stats-bar" id="alt-stats-bar">
        <div class="alt-stat-card">
            <span class="alt-stat-value" id="alt-stat-total">—</span>
            <span class="alt-stat-label">Verified job cuts</span>
            <span class="alt-stat-desc">Filed or reported. This is the headline number.</span>
            <span class="alt-stat-sub" id="alt-stat-total-entries"></span>
        </div>
        <div class="alt-stat-card">
            <span class="alt-stat-value" id="alt-stat-announced">—</span>
            <span class="alt-stat-label">Announced job cuts</span>
            <span class="alt-stat-desc"><b>Separate number.</b> Cuts a company has announced but not yet filed or executed. <b>Not part of the Verified total</b> at left.</span>
            <span class="alt-stat-sub" id="alt-stat-announced-sub"></span>
        </div>
        <div class="alt-stat-card alt-stat-card-ai">
            <span class="alt-stat-value" id="alt-stat-ai">—</span>
            <span class="alt-stat-label">Explicitly AI-attributed</span>
            <span class="alt-stat-desc">How many of the Verified <b>and</b> Announced cuts a company blamed on AI. A lens over both, not a third bucket.</span>
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
    <p class="alt-stats-note">How to read these three numbers: <b>Verified</b> and <b>Announced</b> are two stages, and they never overlap. A cut is counted in exactly one of them, so the Announced figure is <b>not</b> part of the Verified total and nothing is double-counted. <b>Explicitly AI-attributed</b> is not a third bucket. It is a lens across the other two, counting how many of those verified and announced cuts a company openly blamed on AI.</p>
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
        <button type="button" class="alt-qv" data-qv="ai">✦ AI-attributed</button>
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
        <!-- Hidden state holders: quick-view pills are the visible controls -->
        <input type="checkbox" id="alt-f-ai" hidden>
        <input type="checkbox" id="alt-f-announced" hidden>
    </div>

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
                <div class="alt-chart-h">By country <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-countries" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-barlist" id="alt-bars-countries"></div>
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
            <div id="alt-active-filters" class="alt-active-filters" style="display:none"></div>
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

    <details class="alt-methodology">
        <summary>Methodology &amp; sources (for journalists &amp; researchers)</summary>
        <div class="alt-method-body">
            <p><b>What this is.</b> A continuously updated database of verified layoffs worldwide, all industries and all causes, with the subset that companies <em>explicitly</em> attribute to AI flagged and quoted. Every entry links to a primary source so every figure can be independently checked.</p>

            <p><b>Where the data comes from.</b> Four source tiers, always labeled on the entry:
            <span class="alt-badge alt-badge-gold">SEC filing</span> legal 8-K filings pulled from SEC EDGAR full-text search (strongest evidence; US public companies).
            <span class="alt-badge alt-badge-warn">WARN notice</span> state government mass-layoff filings, collected from ~25 US states that publish machine-readable data (legally required, exact headcounts and dates).
            <span class="alt-badge alt-badge-silver">Press release</span> official company statements.
            <span class="alt-badge alt-badge-bronze">News</span> credible outlets worldwide via the open GDELT news index, restricted to ~75 trusted publications across every continent (Reuters, Bloomberg, BBC, The Guardian, SCMP, Economic Times, and similar).</p>

            <p><b>How often it updates.</b> News and SEC filings: twice daily (morning and after US market close, ET). WARN notices: daily at 11 AM ET, sweeping every covered state. An automated anomaly review runs daily at noon ET, flagging statistically unusual entries (very large single notices, same company filing in several states, weak source links) for human inspection before anyone else finds them.</p>

            <p><b>How entries are extracted and checked.</b> News and filings are machine-extracted; the core facts (company, headcount, date, any AI quote) must appear in the source text. Counts parse conservatively (ranges resolve to the lower bound). Countries and industries are normalized to fixed vocabularies; implausible values (a single notice above 100,000 workers, dates outside 2015 to 18 months out) are rejected. Three dedup layers prevent double counting: an exact fingerprint, a same-company 30-day guard for news, and a cross-outlet sweep that keeps the best-sourced version of an event. WARN filings skip the language model entirely (the forms are already structured) and are exempt from fuzzy dedup because one company can legitimately file several notices at once.</p>

            <p><b>How the AI tag works.</b> An entry is marked <em>Explicitly AI-attributed</em> only when the source <em>explicitly names</em> AI, machine learning, automation, or robotics as a reason for the cuts. We store and display the <em>exact quote</em>. We never infer AI from vague "efficiency" language, so treat the AI figure as a defensible floor, not a ceiling.</p>

            <p><b>Coverage and honest limitations.</b> Coverage is worldwide, but US depth is greatest because only the US has government filing systems (WARN, EDGAR); other countries top out at Press release or News verification. About 25 states publish usable WARN data; the rest either publish none or their sites resist automated collection. Most states publish one official list rather than per-notice pages, so those source links are labeled "(list)"; exact per-notice links are used wherever a state provides them. WARN filings contain no industry or reason field, so industry and reason charts mostly reflect SEC- and news-sourced entries. Employers with remote or multi-state workforces sometimes file the same restructuring in several states with overlapping counts; figures are shown exactly as each state published them. Entries dated in the future are legally filed but not yet executed and carry an <span class="alt-upcoming">upcoming</span> tag.</p>

            <p><b>What we exclude.</b> Rumored or unsourced layoffs; layoffs with no stated job count; forward-looking projections (e.g. "could cost X jobs by 2050") rather than announced or executed cuts; and retrospective summary articles that would double-count events already tracked.</p>

            <p><b>Why our totals differ from other headline numbers.</b> Three kinds of trackers measure three different things. Government statistics (BLS) count <em>every</em> separation in the economy, millions per month, with no event-level detail. Announcement surveys (Challenger, Gray &amp; Christmas; the WSJ and TrueUp trackers) count corporate <em>intentions</em>: when a CEO announces "20,000 cuts over the next two years," the full 20,000 lands in their total that day, even though much of it may come through attrition, get scaled back, or never produce a single filing. This tracker counts only what has a <em>verifiable document or quoted primary source behind it</em>: the WARN notices and SEC filings that appear as those 20,000 cuts actually execute, plus reported cuts with a named-outlet source. A worked example: in the first half of 2026, announcement surveys reported roughly 443,600 US job cuts (Challenger, through June); verified filings and sourced reports here totaled <span id="alt-worked-ours">about 175,000</span> for the same period, both correct answers to different questions. Theirs answers "what are companies saying?" Ours answers "what can you prove?" Treat our verified figure as a documented floor: smaller than the estimates, but every single number is clickable back to a legal filing or named outlet. Since July 2026 we also track <em>announcement-stage</em> cuts as their own labeled tier ("Announced", tagged in the table and shown as a separate headline number) so both questions are answered on one page, and unlike the announcement surveys, every announcement here links to its source too.</p>

            <p><b>Using the data.</b> Free with attribution to <b>asktherecruiter.com</b>. The CSV and JSON buttons download exactly what your current filters show (or the full dataset when unfiltered); each chart offers its own image or data download. Programmatic access: <code>GET /blog/wp-json/layoffs/v1/query</code> (paginated; filter params match the page: years, quarters, months, industry, country, state, sources, reasons, q, from, to) and <code>GET /blog/wp-json/layoffs/v1/aggregate</code> for totals and breakdowns. Corrections get priority via the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a> or info@asktherecruiter.com, and every fix is disclosed in the corrections log below.</p>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>Which countries are in which region tab?</summary>
        <div class="alt-method-body" id="alt-region-defs">
            <p>The region tabs are views over the worldwide data. The full country list for each tab loads here.</p>
        </div>
    </details>

    <section class="alt-methodology alt-faq" itemscope>
        <h2 class="alt-detail-h" style="font-size:19px;margin:0 0 10px">Frequently asked questions</h2>
        <?php foreach (alt_faq_items() as $qa) : ?>
        <details class="alt-faq-item">
            <summary><?php echo esc_html($qa[0]); ?></summary>
            <div class="alt-method-body"><p><?php echo esc_html($qa[1]); ?></p></div>
        </details>
        <?php endforeach; ?>
    </section>

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
        <summary>Databases &amp; sources we pull, by region</summary>
        <div class="alt-method-body">
            <p><b>United States.</b> <a href="https://efts.sec.gov/LATEST/search-index?q=%22reduction%20in%20force%22&dateRange=custom&forms=8-K" target="_blank" rel="noopener">SEC EDGAR full-text search</a> for 8-K filings, searched twice daily across 12 layoff phrasings, plus official state <b>WARN notices from 41 states</b>, imported daily. The complete per-state list of portals and parsers is public in <a href="https://github.com/dk-forge/ai-layoff-tracker/blob/main/railway/sources/warn.py" target="_blank" rel="noopener">our source code</a>. The remaining states publish no usable per-notice data: HI and OK omit headcounts, and MO and NM publish nothing.</p>
            <p><b>European Union, Norway, and the UK historically.</b> The <a href="https://apps.eurofound.europa.eu/restructuring-events/" target="_blank" rel="noopener">European Restructuring Monitor</a> from Eurofound, an EU agency. These are per-company restructuring announcements compiled by national correspondents who screen 58 designated business media titles daily. We import them daily with attribution. Because ERM records announcement-stage figures, its entries feed our Announced tier.</p>
            <p><b>Worldwide, every country.</b> The <a href="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/" target="_blank" rel="noopener">GDELT global news index</a> machine-translates press coverage from 65+ languages (Le Monde, Handelsblatt, Nikkei, Globo and thousands more) and we search it twice daily for layoff coverage in any country, alongside <a href="https://newsapi.org" target="_blank" rel="noopener">NewsAPI</a>. Only articles from an editorially maintained trusted-outlet list are ingested, and that list is also public in the repository.</p>
            <p><b>What the AI does and does not do.</b> WARN and ERM records are imported with <em>no AI processing</em>, because they are already structured. For press articles, the DeepSeek-V3 model reads the article text and extracts the company, the count, the date, the country, and any explicit AI attribution. Countries and industries then normalize through fixed vocabularies, counts and dates pass hard validation rules, and duplicates are checked against the existing data. A second, independent model pass audits classifications every day, and a full-dataset audit runs monthly. Label corrections apply only when two independent passes agree. Numeric changes and removals always require a human. Every correction discloses itself in the log below.</p>
            <p><b>Why 41 US states and not 50.</b> All 50 states appear in the tracker through SEC filings and news, but WARN <em>notices</em> come from 41 states because that is how many publish usable per-notice data. The rest cannot be included through no fault of ours: Hawaii and Oklahoma publish WARN notices without headcounts, and Missouri and New Mexico publish nothing citable at the notice level. 41 is the ceiling of what US states actually make public, and we are at it.</p>
            <p><b>Why the country count grows over time.</b> The number of countries is not a setting we can raise; it reflects where large, press-covered layoffs have actually happened in our window. GDELT already searches every country on earth in 65+ languages, so a country appears the moment a credible outlet there covers a qualifying layoff. As events occur and as we add more trusted local outlets (the list grew from 106 to 153 in July 2026), the count rises on its own. This is honest by design: we show the countries where verifiable events exist, not a padded list.</p>
            <p><b>Known gaps, stated plainly.</b> A few countries publish official per-company redundancy records we do not ingest yet, including Belgium's FPS Employment collective-dismissal reports, Italy's weekly CIGS decree lists, and Sweden's varsel statistics. They are on the roadmap. Most countries, including Germany and Mexico, treat employer identity in redundancy filings as confidential, so press coverage through GDELT in local languages is the primary source there. Events too small for any press coverage, any WARN threshold, or the ERM threshold of 100 jobs will not appear in any tracker, including this one.</p>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>Data notes &amp; corrections log</summary>
        <div class="alt-method-body">
            <p>Errors are corrected openly, not silently. Every correction to published figures is dated and described here, newest first, and corrected rows are also flagged <code>edited: true</code> in the API. The list scrolls, because it grows a little every day as the data self-corrects.</p>
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
</div>
