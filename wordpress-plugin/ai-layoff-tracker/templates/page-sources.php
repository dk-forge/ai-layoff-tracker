<?php if (!defined('ABSPATH')) exit;
/**
 * Public "Data Sources" page — the verifiable directory of every pipeline the
 * tracker pulls from, rendered as scannable tables. The US state WARN registry
 * links come straight from the same alt_state_warn_urls() map the importer
 * stamps onto notices, so they can never drift from what we actually scrape.
 * Linked from the tracker headline ("why this is verified"), the lead bar, and
 * the methodology FAQ.
 */
$alt_state_names = array(
    'AK' => 'Alaska', 'AL' => 'Alabama', 'AZ' => 'Arizona', 'CA' => 'California',
    'CO' => 'Colorado', 'CT' => 'Connecticut', 'DC' => 'District of Columbia',
    'DE' => 'Delaware', 'FL' => 'Florida', 'GA' => 'Georgia', 'HI' => 'Hawaii',
    'IA' => 'Iowa', 'ID' => 'Idaho', 'IL' => 'Illinois', 'IN' => 'Indiana',
    'KS' => 'Kansas', 'KY' => 'Kentucky', 'LA' => 'Louisiana', 'MA' => 'Massachusetts',
    'MD' => 'Maryland', 'ME' => 'Maine', 'MI' => 'Michigan', 'MN' => 'Minnesota',
    'MO' => 'Missouri', 'MT' => 'Montana', 'MS' => 'Mississippi', 'NC' => 'North Carolina',
    'NV' => 'Nevada', 'NH' => 'New Hampshire', 'WV' => 'West Virginia', 'WY' => 'Wyoming',
    'ND' => 'North Dakota', 'NE' => 'Nebraska', 'NJ' => 'New Jersey',
    'NM' => 'New Mexico', 'NY' => 'New York', 'OH' => 'Ohio', 'OK' => 'Oklahoma',
    'OR' => 'Oregon', 'PA' => 'Pennsylvania', 'RI' => 'Rhode Island',
    'SC' => 'South Carolina', 'SD' => 'South Dakota', 'TN' => 'Tennessee',
    'TX' => 'Texas', 'UT' => 'Utah', 'VA' => 'Virginia', 'VT' => 'Vermont',
    'WA' => 'Washington', 'WI' => 'Wisconsin',
);
$alt_state_urls = function_exists('alt_state_warn_urls') ? alt_state_warn_urls() : array();
ksort($alt_state_urls);
// States we cannot fully cover, in plain English — so the gap is disclosed, not hidden.
$alt_gap_states = array(
    array('Hawaii', 'Posts some WARN notices without saying how many people are affected. We will not invent a headcount, so those cannot become countable rows.', 'Headcount often missing'),
    array('Oklahoma', 'Posts some WARN notices without a headcount, same as Hawaii. Nothing to count without the number.', 'Headcount often missing'),
    array('Missouri', 'Does not publish layoff notices to the public at the individual-notice level at all.', 'Nothing published'),
    array('New Mexico', 'Does not publish layoff notices to the public at the individual-notice level at all.', 'Nothing published'),
    array('Arkansas', 'Treats WARN filings as confidential employer records. The Division of Workforce Services receives them but is barred from releasing company-level data under the Arkansas FOIA exemption, so there is no public list to import. Arkansas cuts still reach the tracker when a company files with the SEC or a named outlet reports them.', 'Confidential by law'),
);
?>
<main class="alt-wrap alt-sources-page">
  <p class="alt-eyebrow">AskTheRecruiter · AI Layoff Tracker</p>
  <h1>Data Sources</h1>
  <p class="alt-lead"><span class="alt-lead-text">Every number in the tracker traces back to one of the sources below — an official government filing, a legally required layoff notice, an EU restructuring record, or a named news report. Nothing is estimated or modeled into existence. Each row links to the raw source so you can check it yourself.</span></p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-metric-definitions">Methodology</a> · <a href="https://github.com/dk-forge/ai-layoff-tracker/blob/main/railway/sources/warn.py" target="_blank" rel="noopener">Source code</a></p>

  <h2>Every source at a glance</h2>
  <div class="alt-health-table-wrap"><table class="alt-sources-table">
    <thead><tr><th>Source</th><th>Region / scope</th><th>What it is</th><th>Tier it feeds</th><th>Link</th></tr></thead>
    <tbody>
      <tr>
        <td><b>SEC EDGAR</b></td><td>US public companies + foreign filers</td>
        <td>Every 8-K / 6-K filing, searched twice daily for layoff language (incl. Item 2.05 exit costs). Structured — no AI processing.</td>
        <td>Verified</td>
        <td><a href="https://efts.sec.gov/LATEST/search-index?q=%22reduction%20in%20force%22&forms=8-K" target="_blank" rel="noopener">Full-text search &#8599;</a></td>
      </tr>
      <tr>
        <td><b>State WARN notices</b></td><td><?php echo count($alt_state_urls); ?> US states + DC</td>
        <td>Official mass-layoff notices employers must file with the state. Imported daily, no AI processing. Full list below.</td>
        <td>Verified</td>
        <td><a href="#alt-state-warn">See all <?php echo count($alt_state_urls); ?> &darr;</a></td>
      </tr>
      <tr>
        <td><b>Eurofound ERM</b></td><td>EU27, Norway, UK (historically)</td>
        <td>The EU's official European Restructuring Monitor — per-company restructuring announcements from national correspondents.</td>
        <td>Announced</td>
        <td><a href="https://apps.eurofound.europa.eu/restructuring-events/" target="_blank" rel="noopener">ERM database &#8599;</a></td>
      </tr>
      <tr>
        <td><b>GDELT news index</b></td><td>Worldwide, every country</td>
        <td>Global news in 65+ languages, searched twice daily. Allowlist of trusted outlets only — never open-web crawling.</td>
        <td>Verified (named report)</td>
        <td><a href="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/" target="_blank" rel="noopener">About GDELT &#8599;</a></td>
      </tr>
      <tr>
        <td><b>NewsAPI</b></td><td>Worldwide</td>
        <td>Supplements GDELT for recent English-language coverage, same trusted-outlet allowlist.</td>
        <td>Verified (named report)</td>
        <td><a href="https://newsapi.org" target="_blank" rel="noopener">NewsAPI &#8599;</a></td>
      </tr>
      <tr>
        <td>EDINET / OpenDART / CVM</td><td>Japan · South Korea · Brazil</td>
        <td>Official corporate-filing systems. Discovery probes only — <em>not live</em> until a stable interface, tests and health monitoring exist.</td>
        <td>Research candidate</td>
        <td><a href="https://disclosure2.edinet-fsa.go.jp/" target="_blank" rel="noopener">EDINET &#8599;</a></td>
      </tr>
    </tbody>
  </table></div>
  <p class="alt-muted"><b>Verified</b> = a filing or named report is behind it (the headline number). <b>Announced</b> = a company plan reported at announcement stage, kept in a separate tier and never mixed into the verified total.</p>

  <h2 id="alt-state-warn">US state WARN registries (<?php echo count($alt_state_urls); ?> states)</h2>
  <p>The federal WARN Act requires large employers to file advance notice of mass layoffs with their state's dislocated-worker unit. We import those official notices daily from every state that publishes usable per-notice data. Each link is the state's own official WARN page — the exact source our importer reads.</p>
  <?php if ($alt_state_urls) : ?>
  <div class="alt-health-table-wrap"><table class="alt-sources-table">
    <thead><tr><th>State</th><th>Official WARN registry</th></tr></thead>
    <tbody>
    <?php foreach ($alt_state_urls as $alt_code => $alt_url) :
        $alt_name = isset($alt_state_names[$alt_code]) ? $alt_state_names[$alt_code] : $alt_code; ?>
      <tr>
        <td><?php echo esc_html($alt_name); ?> <span class="alt-muted">(<?php echo esc_html($alt_code); ?>)</span></td>
        <td><a href="<?php echo esc_url($alt_url); ?>" target="_blank" rel="noopener"><?php echo esc_html(preg_replace('#^https?://(www\.)?#', '', $alt_url)); ?></a></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php else : ?>
  <p class="alt-muted">The state WARN registry list is being generated and will appear on the next update.</p>
  <?php endif; ?>

  <h2>States we can't fully cover yet — and why</h2>
  <p>All 50 states already appear in the tracker through SEC filings and news. The gap is only in state WARN <em>notices</em>, and here is exactly why, in plain terms:</p>
  <div class="alt-health-table-wrap"><table class="alt-sources-table">
    <thead><tr><th>State</th><th>Why it isn't in the WARN list</th><th>Status</th></tr></thead>
    <tbody>
    <?php foreach ($alt_gap_states as $alt_g) : ?>
      <tr><td><b><?php echo esc_html($alt_g[0]); ?></b></td><td><?php echo esc_html($alt_g[1]); ?></td><td><?php echo esc_html($alt_g[2]); ?></td></tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <p class="alt-muted">"Nothing published" and "no headcount" states can't be fixed with code — they need public-records requests to the state. The custom-scraper states are an engineering task we're working through.</p>

  <?php if (file_exists(ALT_PLUGIN_DIR . 'templates/partials/scan-scope.php')) include ALT_PLUGIN_DIR . 'templates/partials/scan-scope.php'; ?>
  <h2>Worldwide news — every country &amp; outlet we scan<?php if (!empty($alt_scan_countries)) : ?> (<?php echo number_format((int) $alt_scan_countries); ?> countries, <?php echo number_format((int) $alt_scan_outlets); ?> outlets)<?php endif; ?></h2>
  <p>Beyond official filings, we monitor a curated allowlist of reputable news outlets in every country, in 65+ languages, twice daily via GDELT and NewsAPI — never the open web. The full list is below, generated straight from the collector's own configuration, so it <b>updates automatically whenever a source is added</b>. Each country also shows which official register (if any) we pull directly.</p>
  <?php if (file_exists(ALT_PLUGIN_DIR . 'templates/partials/country-sources-table.php')) : ?>
  <?php include ALT_PLUGIN_DIR . 'templates/partials/country-sources-table.php'; ?>
  <?php else : ?>
  <p class="alt-muted">The full country &amp; outlet list is being generated and will appear on the next update.</p>
  <?php endif; ?>

  <h2>How verification works</h2>
  <div class="alt-health-table-wrap"><table class="alt-sources-table">
    <thead><tr><th>Source type</th><th>How it's handled</th></tr></thead>
    <tbody>
      <tr><td>WARN &amp; ERM (structured)</td><td>Imported as-is with <b>no AI processing</b> — company, count and date come straight off the official record.</td></tr>
      <tr><td>News &amp; SEC (text)</td><td>A model extracts the facts; a second independent model pass must agree, and a supporting quote must be present. Countries/industries normalize to fixed lists; counts and dates pass hard validation.</td></tr>
      <tr><td>Corrections</td><td>Label fixes need two passes to agree; <b>numeric changes and removals always require a human</b>. Every correction is logged publicly.</td></tr>
    </tbody>
  </table></div>
  <p>Live collector status is on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-tracker-health/')); ?>">tracker health page</a>; the running corrections log is on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-data-sources">tracker itself</a>.</p>
</main>
