<?php if (!defined('ABSPATH')) exit;
/**
 * Public "Data Sources" page — the verifiable directory of every pipeline the
 * tracker pulls from. Built for journalists and researchers: each US state
 * WARN registry is a live link (rendered straight from the same
 * alt_state_warn_urls() map the importer stamps onto notices, so it can never
 * drift from what we actually scrape), alongside the federal, EU, and news
 * sources. Linked from the tracker headline ("why this is verified") and the
 * methodology FAQ.
 */
$alt_state_names = array(
    'AK' => 'Alaska', 'AL' => 'Alabama', 'AZ' => 'Arizona', 'CA' => 'California',
    'CO' => 'Colorado', 'CT' => 'Connecticut', 'DC' => 'District of Columbia',
    'DE' => 'Delaware', 'FL' => 'Florida', 'GA' => 'Georgia', 'HI' => 'Hawaii',
    'IA' => 'Iowa', 'ID' => 'Idaho', 'IL' => 'Illinois', 'IN' => 'Indiana',
    'KS' => 'Kansas', 'KY' => 'Kentucky', 'LA' => 'Louisiana', 'MD' => 'Maryland',
    'ME' => 'Maine', 'MI' => 'Michigan', 'MO' => 'Missouri', 'MT' => 'Montana',
    'ND' => 'North Dakota', 'NE' => 'Nebraska', 'NJ' => 'New Jersey',
    'NM' => 'New Mexico', 'NY' => 'New York', 'OH' => 'Ohio', 'OK' => 'Oklahoma',
    'OR' => 'Oregon', 'PA' => 'Pennsylvania', 'RI' => 'Rhode Island',
    'SC' => 'South Carolina', 'SD' => 'South Dakota', 'TN' => 'Tennessee',
    'TX' => 'Texas', 'UT' => 'Utah', 'VA' => 'Virginia', 'VT' => 'Vermont',
    'WA' => 'Washington', 'WI' => 'Wisconsin',
);
$alt_state_urls = function_exists('alt_state_warn_urls') ? alt_state_warn_urls() : array();
ksort($alt_state_urls);
?>
<main class="alt-wrap alt-sources-page">
  <p class="alt-eyebrow">AskTheRecruiter · AI Layoff Tracker</p>
  <h1>Data Sources</h1>
  <p class="alt-lead"><span class="alt-lead-text">Every number in the tracker traces back to one of the sources below — an official government filing, a legally required layoff notice, an EU restructuring record, or a named news report. Nothing is estimated or modeled into existence. This page lists each pipeline, with a live link so you can check the raw source yourself.</span></p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-metric-definitions">Methodology</a> · <a href="https://github.com/dk-forge/ai-layoff-tracker/blob/main/railway/sources/warn.py" target="_blank" rel="noopener">Source code (state parsers)</a></p>

  <h2>United States — federal filings</h2>
  <p><b>SEC EDGAR full-text search.</b> We search <a href="https://efts.sec.gov/LATEST/search-index?q=%22reduction%20in%20force%22&forms=8-K" target="_blank" rel="noopener">every 8-K and 6-K filing</a> twice daily across layoff phrasings, including Item 2.05 exit-cost disclosures. SEC filings are structured and are imported with no AI processing. All 50 states are represented in the tracker through these filings and through news, even where a state publishes no WARN data of its own.</p>

  <h2>United States — state WARN registries (<?php echo count($alt_state_urls); ?> states)</h2>
  <p>The federal WARN Act requires large employers to file advance notice of mass layoffs and plant closings with their state's dislocated-worker unit. We import those official notices daily from every state that publishes usable per-notice data. Each link below is the state's own official WARN program or database page — the exact source our importer reads.</p>
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
  <p><b>Why <?php echo count($alt_state_urls); ?> states and not 50.</b> These are the states that publish citable per-notice WARN data. The rest cannot be included through no fault of ours: Hawaii and Oklahoma publish WARN notices without headcounts, and Missouri and New Mexico publish nothing at the notice level. Oregon anonymizes some employers as facility or street names in its own official list; we record those rows faithfully rather than guessing the employer. This is the ceiling of what US states actually make public.</p>

  <h2>European Union, Norway &amp; the UK (historically)</h2>
  <p><b>European Restructuring Monitor (Eurofound).</b> The <a href="https://apps.eurofound.europa.eu/restructuring-events/" target="_blank" rel="noopener">ERM</a>, run by the EU agency Eurofound, records per-company restructuring announcements compiled by national correspondents who screen 58 designated business-media titles daily. We import them daily with attribution. Because ERM records announcement-stage figures, its entries feed our <b>Announced</b> tier, not the verified headline.</p>

  <h2>Worldwide — news coverage, every country</h2>
  <p><b>GDELT global news index.</b> <a href="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/" target="_blank" rel="noopener">GDELT</a> machine-translates press coverage from 65+ languages (Le Monde, Handelsblatt, Nikkei, Globo and thousands more), searched twice daily for layoff coverage in any country. <b>NewsAPI</b> supplements it. Only articles from an editorially maintained trusted-outlet allowlist are ingested — we never crawl the open web. That allowlist is public in the <a href="https://github.com/dk-forge/ai-layoff-tracker" target="_blank" rel="noopener">repository</a>. Press articles are read by the DeepSeek-V3 model, which extracts company, count, date, country and any explicit AI attribution; countries and industries then normalize through fixed vocabularies, counts and dates pass hard validation, and duplicates are checked against the existing data.</p>

  <h2>Official-source research (not yet live)</h2>
  <p>Discovery probes exist for Japan (<a href="https://disclosure2.edinet-fsa.go.jp/" target="_blank" rel="noopener">EDINET</a>), South Korea (<a href="https://opendart.fss.or.kr/" target="_blank" rel="noopener">OpenDART</a>) and Brazil (CVM). These are maintained as official-source candidates and are named as live only after a stable public interface, tests and source-health monitoring exist. Countries such as Canada (SEDAR+), the UK (RNS), Australia (ASX), India (NSE/BSE), Hong Kong (HKEXnews), Singapore (SGXNet) and others are on the same roadmap. Until then, layoffs in those countries surface through GDELT news coverage in local languages.</p>

  <h2>How verification works</h2>
  <p>WARN and ERM records are imported with <b>no AI processing</b> because they are already structured. For news, the model extracts the facts and a second independent model pass audits classifications daily, with a full-dataset audit monthly. Label corrections apply only when two independent passes agree; numeric changes and removals always require a human. Every correction discloses itself in the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-data-sources">corrections log</a>. The live status of each collector is on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-tracker-health/')); ?>">tracker health page</a>.</p>
</main>
