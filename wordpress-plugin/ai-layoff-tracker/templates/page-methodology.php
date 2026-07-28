<?php if (!defined('ABSPATH')) exit;
/**
 * Standalone methodology page. The detailed version of what used to live in the
 * collapsed #alt-metric-definitions block on the tracker. The tracker keeps a
 * short overview that links here; this is the full, formatted reference for
 * journalists and researchers.
 */
$alt_cov = function_exists('alt_coverage_counts') ? alt_coverage_counts() : array('states' => 48);
?>
<main class="alt-wrap alt-method-page">
  <p class="alt-eyebrow">AskTheRecruiter · AI Layoff Tracker</p>
  <h1>Methodology &amp; sources</h1>
  <p class="alt-lead"><span class="alt-lead-text">How every number on this tracker is collected, verified, classified and counted. Written for journalists and researchers who need to check a figure before they cite it. Nothing here is estimated into existence; every published number traces to a primary source.</span></p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>">AI, in their own words</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press kit</a></p>

  <nav class="alt-method-toc" aria-label="On this page">
    <b>On this page:</b>
    <a href="#m-cards">What the numbers mean</a> ·
    <a href="#m-sources">Where the data comes from</a> ·
    <a href="#m-extract">Extraction &amp; checks</a> ·
    <a href="#m-ai">How the AI tag works</a> ·
    <a href="#m-reasons">Reason tags</a> ·
    <a href="#m-roles">Roles most impacted</a> ·
    <a href="#m-coverage">Coverage &amp; limits</a> ·
    <a href="#m-differ">Why our totals differ</a> ·
    <a href="#m-audit">Self-audit</a> ·
    <a href="#m-use">Using the data</a>
  </nav>

  <section class="alt-method-sec" id="m-cards">
    <h2>What the summary cards mean</h2>
    <p><b>Verified job cuts</b> is the main figure: cuts with a filing or independently reported source behind them. <b>Explicitly AI-attributed</b> is a subset of Verified job cuts where the source explicitly names AI as a cause. <b>Announced job cuts</b> is a separate announcement-history figure: source-linked plans reported at announcement stage. A later filing or report is linked or merged when confidently matched; an unmatched announcement is <b>not</b> a claim that cuts remain unexecuted. Announced cuts are not counted in Verified or AI-attributed totals, so the cards do not double-count.</p>
    <p><b>Geography in the cards.</b> Country and US-state filters describe the documented location of affected jobs, not an employer's headquarters or every place it operates. A national announcement without a source-supported job-location state remains state-unspecified rather than being assigned to a state by inference.</p>
    <p><b>What this is.</b> A continuously updated, source-linked database of publicly reported layoffs worldwide. It records the source, evidence quote, event status and revision history so every figure can be independently checked. It is not a claim of complete coverage in every country.</p>
  </section>

  <section class="alt-method-sec" id="m-sources">
    <h2>Where the data comes from</h2>
    <p>Sources are always labeled on the entry:</p>
    <ul class="alt-method-list">
      <li><span class="alt-badge alt-badge-gold">SEC filing</span> Legal 8-K and 6-K filings pulled from SEC EDGAR full-text search. Strongest evidence; US public companies and foreign private issuers that file with the SEC.</li>
      <li><span class="alt-badge alt-badge-warn">WARN notice</span> State government mass-layoff filings from <?php echo (int) $alt_cov['states']; ?> covered US states.</li>
      <li><span class="alt-badge alt-badge-silver">Press release</span> Reviewed investor-relations and newsroom feeds (the "Press release" source in the tracker's filter).</li>
      <li><span class="alt-badge alt-badge-bronze">News</span> Named reports discovered through GDELT and Google News, retained only when the record has usable evidence. Eurofound ERM is a separately labeled, thresholded European announcement source.</li>
    </ul>
    <p><b>How often it updates.</b> News and SEC filings: twice daily (morning and after US market close, ET). WARN notices: daily at 11 AM ET, sweeping every covered state. An automated anomaly review runs daily at noon ET, flagging statistically unusual entries (very large single notices, same company filing in several states, weak source links) for human inspection before anyone else finds them. A monthly self-audit re-opens a random sample of published rows and re-checks each against its own source.</p>
  </section>

  <section class="alt-method-sec" id="m-extract">
    <h2>How entries are extracted and checked</h2>
    <p>Discovery searches a dialect-aware vocabulary (layoffs, redundancies, retrenchment, dismissals, sackings, workforce reduction and more than thirty other phrasings) across GDELT's 65-language translated index, so coverage that never uses the word "layoff" still surfaces. News and filings are machine-extracted; core facts must appear in the source text. Counts parse conservatively (ranges resolve to the lower bound). Countries and industries normalize through fixed vocabularies; implausible values are rejected. New records carry an evidence confidence and publication status. Exact fingerprints, same-company guards and cross-source comparison prevent double counting; uncertain candidates remain provisional instead of silently inflating verified totals. WARN filings skip the language model and remain exempt from fuzzy dedup because one employer can legally file several distinct notices.</p>
  </section>

  <section class="alt-method-sec" id="m-reasons">
    <h2>Reason tags</h2>
    <p>Each event can carry one or more reason tags, assigned only when the stored source text explicitly supports them; an event whose source states no reason stays untagged rather than guessed. The fixed vocabulary: <b>AI: company-stated</b> (employer names AI/automation, quote on file), <b>AI-linked (broad)</b> (press ties the cuts to AI without the employer saying it), <b>Revenue decline</b>, <b>Restructuring</b>, <b>Merger / acquisition</b>, <b>Offshoring</b>, <b>Product discontinued</b>, <b>Cost reduction</b>, <b>Macroeconomic</b>, <b>Plant / site closure</b>, <b>Bankruptcy / insolvency</b>, and <b>Government / public sector</b> (public-sector workforce actions such as federal reductions in force; a private contractor losing government work does not qualify). Tags are filterable on the tracker and returned in the API as <code>reason_tags</code>.</p>
  </section>

  <section class="alt-method-sec" id="m-ai">
    <h2>How the AI tag works</h2>
    <p>We distinguish AI as a <em>primary cause</em>, a contributing cause, a selection/operations tool, background context, and an explicit denial. Only primary or contributing cause classifications may be AI-attributed, and each must carry an exact supporting quote found in the source text. AI investment, future automation projections, and AI used to select workers do not qualify by themselves. Alongside the strict tag we also maintain a separately labeled <b>AI-linked, broad</b> measure that counts looser attributions, cuts made while funding an AI pivot, AI-driven market disruption, and press AI framing. The broad measure is surfaced in the <code>ai_broad_jobs</code> API field; it is never mixed into the strict verified-AI totals. Every strict AI attribution is published with its quote on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>">AI, in their own words</a> page.</p>
  </section>

  <section class="alt-method-sec" id="m-roles">
    <h2>How "Roles most impacted" works</h2>
    <p>When a source names which teams were cut (for example "laying off customer-support and recruiting staff"), a model reads that stored text and maps it to a fixed set of role categories; a second independent pass must agree, and a supporting quote must be present, before the category is stored. Nothing is inferred from a company's industry or guessed. Each bar shows the <b>total job cuts</b> attributed to that team, and the orange segment plus the 🤖 figure show how many of those were <b>AI-linked</b>, so a bar with no orange is job cuts we could not tie to AI, not an error. This chart covers <em>only</em> the minority of records whose source actually named the teams affected, so it is a sample of where cuts land, never a breakdown of the full total.</p>
  </section>

  <section class="alt-method-sec" id="m-coverage">
    <h2>Coverage and honest limitations</h2>
    <p>US depth is greatest because of WARN and SEC sources. Europe has structured coverage of large announcements through Eurofound ERM. Outside those live collectors, country-level coverage is currently worldwide news discovery and any explicitly reviewed company newsroom feed; named filing systems such as SEDAR+, RNS, ASX, TDnet and HKEXnews are research candidates, not silently assumed feeds. WARN and ERM have their own thresholds and geography rules, so they should not be summed as if they were a complete national census. Multi-state and multi-country events can overlap; the entry and source fields disclose that risk. Entries dated in the future are announced or filed but not yet completed. Filtering the table by a country also includes cuts by employers <em>headquartered</em> there whose layoff spanned multiple countries (each such row stays labeled with its true "Multiple countries" scope, never recounted as that country alone); the headline totals stay on the stricter job-location basis, so they are never inflated by a global figure.</p>
    <h3 id="alt-counting-basis">The two counting bases, side by side</h3>
    <p>Both numbers below are correct; they answer different questions. We publish the stricter one and disclose the other, so anyone comparing us with an external estimate can compare like with like.</p>
    <?php if (function_exists('alt_basis_table_html')) echo alt_basis_table_html('United States'); ?>
    <p><b>What we exclude.</b> Rumored or unsourced layoffs; layoffs with no stated job count; forward-looking projections (e.g. "could cost X jobs by 2050") rather than announced or executed cuts; and retrospective summary articles that would double-count events already tracked.</p>
  </section>

  <section class="alt-method-sec" id="m-differ">
    <h2>Why our totals differ from other headline numbers</h2>
    <p>Three kinds of trackers measure three different things. Government statistics (BLS) count <em>every</em> separation in the economy, millions per month, with no event-level detail. Announcement surveys count corporate <em>intentions</em>: when a CEO announces "20,000 cuts over the next two years," the full 20,000 lands in their total that day, even though much of it may come through attrition, get scaled back, or never produce a single filing. This tracker counts only what has a <em>verifiable document or quoted primary source behind it</em>: the WARN notices and SEC filings that appear as those 20,000 cuts actually execute, plus reported cuts with a named-outlet source.</p>
    <p>Treat our verified figure as a documented floor: smaller than the estimates, but every single number is clickable back to a legal filing or named outlet. Since July 2026 we also track <em>announcement-stage</em> cuts as their own labeled tier ("Announced", tagged in the table and shown as a separate headline number) so both questions are answered on one page, and unlike the announcement surveys, every announcement here links to its source too.</p>
    <p><b>Where the uncounted cuts go.</b> US reporting law leaves large, legal gaps no receipts-based tracker can see, and naming them is part of being honest about what our floor is. The federal WARN Act requires a public notice only when a single site loses 50 or more people at an employer of 100 or more, so a company that spreads the same cuts across many smaller offices files nothing. Employers can also skip the public notice entirely by paying wages in place of the 60-day warning, so that layoff never reaches a state database. A global "reducing headcount by 10,000" announcement often resolves to far fewer US filings once overseas cuts, natural attrition, and voluntary buyouts, none of which file WARN, are separated out. Small businesses and contractor terminations rarely generate any filing or news at all. The economy-wide total for those uncounted cuts comes from statistical estimates such as the US Bureau of Labor Statistics surveys and weekly unemployment-claims data, not from documents naming an employer; we do not restate those estimates as tracker rows, because a number we cannot trace to a source is exactly what this tracker exists not to publish.</p>
    <p>Measured like-for-like against the public trackers by category, the result is not always that we are smaller: we run <em>higher</em> than WARN-only aggregators (we add SEC and named news on top of the same notices), <em>at or above</em> tech-event trackers by job volume, and <em>at or above</em> the announcement AI surveys on our broad measure with a quote on every entry; we run <em>lower</em> only on all-industry totals, where the gap is receiptless cuts (federal-workforce reductions, buyouts, attrition, small closings that file nothing) that we do not claim because we cannot source them.</p>
  </section>

  <section class="alt-method-sec" id="m-audit">
    <h2>The tracker audits itself</h2>
    <p>Once a month, an automated audit draws a random sample of already published rows, re-opens each row's own cited source, and checks that the source still supports that company, that count, and that date. The result is written to the public health ledger whether it is flattering or not. A mismatch is flagged for human review through the corrections process; it is never silently edited.</p>
    <?php
    $alt_sh = get_option('alt_source_health');
    $alt_audit = is_array($alt_sh) && isset($alt_sh['source_audit']) ? $alt_sh['source_audit'] : null;
    if (is_array($alt_audit) && !empty($alt_audit['detail'])) : ?>
    <p class="alt-method-audit"><b>Latest audit result:</b> <?php echo esc_html($alt_audit['detail']); ?><?php if (!empty($alt_audit['checked_at'])) : ?> <span class="alt-muted">(checked <?php echo esc_html(gmdate('M j, Y', strtotime($alt_audit['checked_at']))); ?>)</span><?php endif; ?></p>
    <?php endif; ?>
    <p>Independent verification needs no permission: every row links to its source, and the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-tracker-health/')); ?>">health page</a> shows each collector's live status.</p>
  </section>

  <section class="alt-method-sec" id="m-use">
    <h2>Using the data</h2>
    <p><b>How to phrase a citation.</b> Our totals are what is documented under this methodology: a verifiable floor, not a census of every layoff that happened. The accurate phrasing is <em>"According to AskTheRecruiter's AI Layoff Tracker, N job cuts are documented for [period]"</em> rather than <em>"there were exactly N layoffs."</em> No tracker of any kind observes every layoff; ours is the one where each counted cut can be traced to its document.</p>
    <p>Free with attribution to <b>asktherecruiter.com</b> (CC BY 4.0). The CSV and JSON buttons download exactly what your current filters show (or the full dataset when unfiltered); each chart offers its own image or data download. Programmatic access: <code>GET /blog/wp-json/layoffs/v1/query</code> (paginated; filter params match the page: years, quarters, months, industry, country, state, sources, reasons, q, from, to) and <code>GET /blog/wp-json/layoffs/v1/aggregate</code> for totals and breakdowns. Corrections get priority via the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>, and every fix is disclosed in the corrections log on the tracker.</p>
  </section>
</main>
