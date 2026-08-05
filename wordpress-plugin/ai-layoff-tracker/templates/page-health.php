<?php if (!defined('ABSPATH')) exit; ?>
<main class="alt-wrap alt-health-page" id="alt-health-page">
  <header class="alt-health-hero"><p class="alt-eyebrow">AskTheRecruiter · public operations</p><h1>AI Tracker Health</h1><p>See which data feeds are running, how we check the evidence, where coverage falls short, and what we are working on. When a source goes down we show it as a gap instead of silently counting it as zero.</p><p id="alt-health-updated" role="status">Loading live operational status…</p></header>
  <nav class="alt-health-toc" aria-label="Page contents">
    <a href="#alt-sec-collectors">Collector operations</a>
    <a href="#alt-sec-runs">Recent runs</a>
    <a href="#alt-sec-work">Current work</a>
    <a href="#alt-sec-roadmap">Product roadmap</a>
    <a href="#alt-sec-schedule">Schedule</a>
    <a href="#alt-sec-changes">Change report</a>
  </nav>
  <section class="alt-health-summary" aria-label="Operational summary" id="alt-health-summary"></section>
  <?php
  // OWNER-ONLY: the IndexNow key must not be public (the protocol asks that only
  // you and the search engines know it), so this block renders solely for a
  // logged-in admin. Everything here is already automated; it exists so the
  // owner can verify in Bing Webmaster Tools or fire a manual submission.
  if (current_user_can('manage_options') && function_exists('alt_indexnow_key')) :
      $alt_in_key = alt_indexnow_key();
      $alt_in_loc = alt_indexnow_key_url();
      $alt_in_last = get_option('alt_indexnow_last', array());
  ?>
  <section class="alt-health-section" id="alt-sec-indexnow">
    <h2>IndexNow <span class="alt-health-status alt-health-active">Admin only</span></h2>
    <p>We push new data to Bing (which powers ChatGPT search) and Yandex automatically, at most once a day, whenever the dataset changes. Nothing here needs doing by hand. We show it so you can verify in Bing Webmaster Tools.</p>
    <p><b>Key:</b> <code><?php echo esc_html($alt_in_key); ?></code><br>
       <b>Key file:</b> <a href="<?php echo esc_url($alt_in_loc); ?>"><?php echo esc_html($alt_in_loc); ?></a>
       (must return the key above)<br>
       <b>Last submission:</b>
       <?php if (!empty($alt_in_last['at'])) {
           echo esc_html(gmdate('Y-m-d H:i', (int) $alt_in_last['at']) . ' UTC · ' . (int) $alt_in_last['urls'] . ' URLs'
                . (!empty($alt_in_last['error']) ? ' · error: ' . $alt_in_last['error'] : ' · no error'));
       } else { echo 'not yet sent (fires on the next data change)'; } ?>
    </p>
    <p><b>Manual submission links</b> (one click each, a 200 or 202 means accepted):</p>
    <ul class="alt-health-schedule">
      <?php foreach (alt_indexnow_urls() as $alt_in_u) :
          $alt_in_req = add_query_arg(array(
              'url' => rawurlencode($alt_in_u), 'key' => $alt_in_key,
              'keyLocation' => rawurlencode($alt_in_loc),
          ), 'https://api.indexnow.org/indexnow'); ?>
        <li><a href="<?php echo esc_url($alt_in_req); ?>" target="_blank" rel="noopener"><?php echo esc_html($alt_in_u); ?></a></li>
      <?php endforeach; ?>
    </ul>
    <p class="alt-muted">A key hosted under /blog/ can only submit URLs under /blog/, which is where every tracker page lives.</p>
  </section>
  <?php endif; ?>
  <section class="alt-health-section" id="alt-sec-collectors"><h2>Collector operations</h2><p>Last completed source attempt. Counts are raw candidate documents, not a claim of accepted events.</p><div class="alt-health-table-wrap"><table><thead><tr><th>Source</th><th>Coverage target</th><th>Cadence</th><th>Last pull</th><th>Result</th><th>Status / safe detail</th></tr></thead><tbody id="alt-health-sources"></tbody></table></div></section>
  <section class="alt-health-section" id="alt-sec-runs"><div class="alt-health-run-heading"><div><h2>Recent collector runs</h2><p>Append-only history from this health-ledger release onward. It records source attempts and raw candidates, not accepted events, and never reconstructs earlier runs.</p></div><label for="alt-health-run-days">Window <select id="alt-health-run-days"><option value="7">Last 7 days</option><option value="30" selected>Last 30 days</option><option value="90">Last 90 days</option></select></label></div><div class="alt-health-table-wrap"><table><thead><tr><th>When</th><th>Source</th><th>Status</th><th>Raw candidates</th><th>Safe detail</th></tr></thead><tbody id="alt-health-runs"></tbody></table></div></section>
  <section class="alt-health-section alt-feature-list" id="alt-sec-roadmap" aria-labelledby="alt-feature-list-heading">
    <div class="alt-feature-list-heading"><div><p class="alt-eyebrow">Product roadmap</p><h2 id="alt-feature-list-heading">Features list</h2></div><p>Released capabilities and their rollout state. We show live collector status and errors above. This list does not imply complete country coverage.</p></div>
    <div class="alt-feature-grid">
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Source-linked event records</h3><p>Every published event keeps its cited filing, government notice, company statement or named report; a single layoff event can link to several reports.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>How we decide a layoff is AI-related</h3><p>We keep employer-stated cause, contributing mention, background context and outright denial separate. A model helps extract the text, but exact source quotes and fixed rules decide what we publish.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Deduplication and lifecycle review</h3><p>When several outlets cover the same layoff, we combine them into one event and keep every source link. When an announced cut looks like it later actually happened, an editor reviews the match before anything changes.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Public data and audit tools</h3><p>Filters, exports, record sources, corrections, release ledger, integrity, quality and source-health endpoints are publicly available.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Collector-run ledger</h3><p>From this release on, we keep a record of every source run, how many raw items it found, and any outages. We do not invent history for runs from before we started logging.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Dataset releases and change report</h3><p>Each deployment snapshots the public dataset; this page reports the retained ledger window and disclosed recent corrections, removals, merges and coverage status.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>US announcement reconciliation (internal)</h3><p>Each month we run a like-for-like US employer / announcement / AI-primary reconciliation internally to monitor coverage. We never change tracker totals to match it.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>High-impact editorial review</h3><p>We surface very large, AI-primary and multi-country events for source-based review. We never correct one automatically behind the scenes.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Durable evidence hashes</h3><p>We hash every retained excerpt: new excerpts at write time, and the legacy backlog completed its bounded backfill on July 18, 2026. We report any newly pending hashes live above.</p></article>
      <article><span class="alt-health-status alt-health-in_progress">In progress</span><h3>Adding announcement dates and company headquarters</h3><p>Company-headquarters data shipped July 19, 2026 from a checked, source-verifiable registry; it powers the US-employer views. We still add announcement dates daily from stored evidence. Unknown fields stay blank rather than guessed.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>How complete our coverage is (spot-checked)</h3><p>The first published sample: California WARN, June 2026: 11 of 12 official notices, transcribed independently, matched a tracker event (91.7% sample recall), checked by three independent reviewers against the sealed official notice. A sample is a spot measurement, never a completeness claim; further country-period samples follow the same protocol.</p></article>
      <article><span class="alt-health-status alt-health-pending_permission">Pending review</span><h3>Official national and company IR connectors</h3><p>On July 18, 2026 we admitted the first five reviewed company-owned IR feeds to the versioned registry: Intel, SAP, Cisco, Salesforce and Micron. We retired the Japan EDINET and South Korea OpenDART discovery probes after months live yielded zero layoff rows, because those filings almost never announce layoffs. Worldwide news covers Japan and South Korea instead. We mark a country as covered only after we have built and reviewed its data feed.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Embeddable US widgets</h3><p>A noindex, source-linked US national/state iframe widget links readers to its exact filtered tracker view. Build copyable code on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/publisher-tools/')); ?>">publisher tools page</a>; metro variants remain deliberately out of scope.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Company layoff directory</h3><p>Pages live at /company-layoffs/ and grow automatically. An indexer admits every employer with a clean identity and at least one source-linked event that we count in its own right, rather than folding into a larger one. The same server rules that govern manual review validate each one. We list an employer with two or more such events in the sitemap. An employer below that keeps its page and stays noindex, because the page repeats what the individual entry already says.</p></article>
      <article><span class="alt-health-status alt-health-active">Active</span><h3>Quarterly State of Layoffs report</h3><p>We publish the query-backed HTML report from a fixed server-generated snapshot. We disclose its data revision and its coverage limits.</p></article>
      <article><span class="alt-health-status alt-health-in_progress">In progress</span><h3>WARN transparency dataset</h3><p>The separate evidence-linked research foundation is ready. It will not label an employer non-compliant without verified notice, timing and adjudication evidence.</p></article>
    </div>
  </section>
  <section class="alt-health-grid" id="alt-sec-work"><div class="alt-health-section"><h2>Current work</h2><div id="alt-health-workstreams"></div></div><div class="alt-health-section"><h2>Actionable backlogs</h2><div id="alt-health-backlogs"></div></div></section>
  <section class="alt-health-section" id="alt-sec-schedule"><h2>Schedule and coverage</h2><ul class="alt-health-schedule"><li><b>Railway, twice daily:</b> SEC EDGAR (United States), Google News and global GDELT (worldwide news), and reviewed company IR feeds.</li><li><b>GitHub Actions, daily:</b> US WARN and Eurofound ERM (European Union) at 13:00 UTC; dedupe, quality, evidence-hash and bounded enrichment/recovery jobs.</li><li><b>Monthly:</b> strict US announcement reconciliation (internal coverage check). A red threshold is a coverage alert, not a data-ingest crash.</li><li><b>Retired probes:</b> we stood down the Japan EDINET, South Korea OpenDART and Brazil CVM discovery probes after they yielded zero layoff rows. Worldwide news covers those countries. United Kingdom Companies House access is identity-support only.</li></ul><p>Collector-run telemetry begins with plugin 2.18.21; we do not reconstruct or guess legacy daily pull counts.</p>
  <?php // Live archive-coverage tally (archived / queued / pending / not yet in
        // the Internet Archive), computed from the archive index at render time.
        if (function_exists('alt_archive_coverage_line_html')) echo alt_archive_coverage_line_html(); ?></section>
  <section class="alt-health-section" id="alt-sec-changes"><h2>Rolling dataset change report</h2><p>Snapshot totals begin at ledger inception. We do not label net change as gross additions, because merges, corrections and removals can change the total.</p><div id="alt-health-release-report" aria-live="polite">Loading release and change data…</div></section>
  <p class="alt-health-links">Machine-readable: <a href="<?php echo esc_url(rest_url('layoffs/v1/quality-status')); ?>">quality</a> · <a href="<?php echo esc_url(rest_url('layoffs/v1/integrity-status')); ?>">integrity</a> · <a href="<?php echo esc_url(rest_url('layoffs/v1/source-health')); ?>">source health</a> · <a href="<?php echo esc_url(rest_url('layoffs/v1/source-runs')); ?>">collector runs</a> · <a href="<?php echo esc_url(rest_url('layoffs/v1/dataset-releases')); ?>">release ledger</a></p>
</main>
