<?php if (!defined('ABSPATH')) exit;
/**
 * Public "Data Sources" page, the verifiable directory of every pipeline the
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
// States not yet in the automated WARN feed, in plain English, the gap is
// disclosed, not hidden. Each row: [state, reason, status, source URL].
// Two honest buckets: (A) publishes public data we haven't wired an importer
// for yet, and (B) no usable public register at all (confidential or unposted),
// where cuts reach the tracker only via SEC filings and named news.
// Each row: [state, reason, status, source URL, 2-letter code]. The code lets us
// attach the official BLS unemployment rate (a separate context metric) below.
$alt_gap_states = array(
    // (A) Publishes, but not fully countable
    array('Oklahoma', 'The Employment Security Commission publishes WARN notices through an interactive portal. The public listing carries only employer, location, notice date and notice type. No affected-employee count appears anywhere in the data. Because we will not invent a number, those notices cannot become countable rows. Oklahoma cuts still reach the tracker through SEC filings and named news, and the importer will pick up the portal automatically if OESC ever publishes headcounts.', 'Publishes notices, no public headcounts', 'https://www.employoklahoma.gov/Participants/s/warnnotices', 'OK'),
    array('West Virginia', 'WorkForce WV is imported and its cumulative summary PDFs are fully parsed. But the newest summary the state has published stops at 3 January 2025. Everything since then is posted as an individual notice letter. Most of those are image-only scans with no machine-readable text, so the affected-employee count exists only as pixels. We read every letter that has a text layer. We skip the scans rather than guess at a number, so West Virginia notices from 2025 onward are currently under-counted. Those cuts still reach the tracker through SEC filings and named news.', 'Publishes notices, most recent ones are image scans', 'https://workforcewv.org/job-seeker/layoffs-downsizing/warn-listing/', 'WV'),
    // (B) No usable public register
    array('Arkansas', 'Treats WARN filings as confidential employer records. The Division of Workforce Services receives them but is barred from releasing company-level data under the Arkansas FOIA exemption, so there is no public list to import. Arkansas cuts still reach the tracker when a company files with the SEC or a named outlet reports them.', 'Confidential by law', 'https://dws.arkansas.gov/', 'AR'),
    array('Wyoming', 'The Department of Workforce Services tracks filings internally but does not host a public, centralized WARN register. Wyoming cuts reach the tracker through SEC filings and named regional news instead.', 'No public register', 'https://dws.wyo.gov/', 'WY'),
    array('New Hampshire', 'NH Employment Security handles WARN filings as internal business-compliance records and does not publish a usable public feed. New Hampshire cuts reach the tracker through SEC filings and named news instead.', 'No public register', 'https://www.nhes.nh.gov/', 'NH'),
);
$alt_unemp = function_exists('alt_state_unemployment') ? alt_state_unemployment() : array();
?>
<main class="alt-wrap alt-sources-page">
  <p class="alt-eyebrow">AskTheRecruiter · AI Layoff Tracker</p>
  <h1>Data Sources</h1>
  <p class="alt-lead"><span class="alt-lead-text">Every number in the tracker traces back to one of the sources below. That means an official government filing, a legally required layoff notice, an EU restructuring record, or a named news report. Nothing is estimated or modeled into existence. Each row links to the raw source so you can check it yourself.</span></p>
  <?php /* This row said "Methodology" and went to #alt-metric-definitions on
       the DASHBOARD - the short summary - so the one page with a methodology
       in its own H1 was unreachable from the sibling row of the page next to
       it. Four labels across the tracker pointed at one subject and two of
       them did not arrive at it. The label is now the same words the dashboard
       and the press page already use for this destination, "How we count", and
       it goes to the page. */ ?>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">How we count</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>"><?php echo esc_html(alt_page_link_label('page-ai-quotes.php', 'AI layoffs, in the employer\'s own words')); ?></a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press kit and soundbites</a> · <a href="https://github.com/dk-forge/ai-layoff-tracker/blob/main/railway/sources/warn.py" target="_blank" rel="noopener">Source code</a></p>
  <?php $alt_lu = function_exists('alt_data_last_updated_label') ? alt_data_last_updated_label() : ''; ?>
  <?php if ($alt_lu) : ?><p class="alt-muted"><b>Data last updated:</b> <?php echo esc_html($alt_lu); ?> (the last time the database actually changed). Live collector status is on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-tracker-health/')); ?>">health page</a>. Note: <b>this source list is a reference.</b> It changes only when we add or remove a collector, which happens on a deploy, not every day. So it is honest for the list to stay the same between updates.</p><?php endif; ?>

  <nav class="alt-src-toc" aria-label="On this page">
    <b>On this page:</b>
    <a href="#alt-src-glance">Sources at a glance</a> &middot;
    <a href="#alt-state-warn">US state WARN</a> &middot;
    <a href="#alt-src-gaps">States not in the feed yet</a> &middot;
    <a href="#alt-src-global">Why most countries appear through news</a> &middot;
    <a href="#alt-src-news">Worldwide news outlets</a> &middot;
    <a href="#alt-src-catalogue">Every publisher we researched</a> &middot;
    <a href="#alt-src-verify">How verification works</a> &middot;
    <a href="#alt-ai-rubric">AI rubric</a>
  </nav>

  <h2 id="alt-src-glance">Every source at a glance</h2>
  <div class="alt-health-table-wrap"><table class="alt-sortable alt-sources-table">
    <thead><tr><th>Source</th><th>Region / scope</th><th>What it is</th><th>Tier it feeds</th><th>Link</th></tr></thead>
    <tbody>
      <tr>
        <td><b>SEC EDGAR</b></td><td>US public companies + foreign filers</td>
        <td>Every 8-K / 6-K filing, searched twice daily for layoff language (incl. Item 2.05 exit costs). Structured, no AI processing.</td>
        <td>Verified</td>
        <td><a href="https://efts.sec.gov/LATEST/search-index?q=%22reduction%20in%20force%22&forms=8-K" target="_blank" rel="noopener">Full-text search &#8599;</a></td>
      </tr>
      <tr>
        <td><b>State WARN notices</b></td><td><?php echo (count($alt_state_urls) - (isset($alt_state_urls['DC']) ? 1 : 0)); ?> US state registries + DC that we read</td>
        <td>Official mass-layoff notices employers must file with the state. Imported daily, no AI processing. Full list below.</td>
        <td>Verified</td>
        <td><a href="#alt-state-warn">See all <?php echo count($alt_state_urls); ?> &darr;</a></td>
      </tr>
      <tr>
        <td><b>Hawaii WARN notices (OCR)</b></td><td>Hawaii</td>
        <td>Hawaii posts each notice as a scanned image PDF. So we read the scan with OCR, character recognition software, to recover the affected-employee count the state gives in the letter. We use only a clearly stated count. A notice without one, or with a redacted total, is left out, never estimated. Every row links its source PDF.</td>
        <td>Verified</td>
        <td><a href="https://labor.hawaii.gov/wdc/real-time-warn-updates/" target="_blank" rel="noopener">HI WDC WARN notices &#8599;</a></td>
      </tr>
      <tr>
        <td><b>Quebec collective dismissals</b></td><td>Quebec, Canada</td>
        <td>Official monthly notices employers must file with Quebec's Ministere de l'Emploi et de la Solidarite sociale (MESS) for a collective dismissal. Parsed from the ministry's monthly PDFs, no AI processing.</td>
        <td>Verified</td>
        <td><a href="https://www.quebec.ca/gouvernement/ministeres-organismes/emploi-solidarite-sociale/publications" target="_blank" rel="noopener">MESS publications &#8599;</a></td>
      </tr>
      <tr>
        <td><b>Mazowieckie collective dismissals</b></td><td>Mazovia region, Poland</td>
        <td>Official monthly notifications employers must file with the regional labour office (WUP Warszawa) before a collective redundancy. It is the only one of Poland's 16 voivodeship offices that publishes employers by name. Parsed from the office's monthly register posts, no AI processing.</td>
        <td>Verified</td>
        <td><a href="https://wupwarszawa.praca.gov.pl/urzad/dla-mediow" target="_blank" rel="noopener">WUP Warszawa register &#8599;</a></td>
      </tr>
      <tr>
        <td><b>Eurofound ERM</b></td><td>EU27, Norway, UK (historically)</td>
        <td>The EU's official European Restructuring Monitor, per-company restructuring announcements from national correspondents.</td>
        <td>Announced</td>
        <td><a href="https://apps.eurofound.europa.eu/restructuring-events/" target="_blank" rel="noopener">ERM database &#8599;</a></td>
      </tr>
      <tr>
        <td><b>GDELT news index</b></td><td>Worldwide, every country</td>
        <td>Global news in 65+ languages, searched twice daily. Allowlist of trusted outlets only, never open-web crawling.</td>
        <td>Verified (named report)</td>
        <td><a href="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/" target="_blank" rel="noopener">About GDELT &#8599;</a></td>
      </tr>
      <tr>
        <td><b>Google News</b></td><td>Worldwide</td>
        <td>Supplements GDELT for recent coverage. Headlines carry the headcount even when the linked article is paywalled, so marquee layoffs are not missed. We read <b>45 national editions</b> (US, UK, DE, FR, JP, BR, IN and more). That way we search each market in its own language and its own outlets, not through a US lens. Same trusted-outlet standard. Editions rotate across the twice-daily runs, so we sweep the full set about every six days.</td>
        <td>Verified (named report)</td>
        <td><a href="https://news.google.com" target="_blank" rel="noopener">Google News &#8599;</a></td>
      </tr>
      <tr>
        <td><b>Local-language market sweep</b></td><td>25 markets, in their own languages</td>
        <td>Searches each market in its own words rather than in English, twice daily. An English query put to a German or Spanish edition returns the worldwide English feed, not that country's news. So this sweep carries a phrase set written per language and per market, from German, French and Spanish to Arabic, Russian, Turkish and Ukrainian. A free locality check runs before any article is read by a model, so foreign stories are dropped rather than paid for. Layoff tracker products and compiled tallies are excluded by design; only individual reporting is ever read.</td>
        <td>Verified (named report)</td>
        <td><a href="https://news.google.com" target="_blank" rel="noopener">Google News &#8599;</a></td>
      </tr>
      <tr>
        <td><b>Regional news feeds</b><br><span class="alt-muted">Pacific · Francophone Africa · Caribbean</span></td><td>~50 low-volume countries</td>
        <td>Five regional publishers' own RSS feeds, read twice daily, covering countries too small for a dedicated sweep. <b>RNZ Pacific</b> and the <b>Pacific Island Times</b> cover the Pacific islands (Fiji, Papua New Guinea, Samoa, Tonga, Vanuatu, Solomon Islands, Guam, Palau, Micronesia and more). <b>Financial Afrik</b> and <b>Jeune Afrique</b> cover Francophone Africa in French (Senegal, Ivory Coast, Cameroon, Morocco, Tunisia, Mali and more). <b>Caribbean News Global</b> covers the Caribbean (Saint Lucia, Jamaica, Barbados, Guyana and more). Only stories carrying collective-layoff language in English or French are read further. The publication decides nothing: the article text itself determines the country and count, through the same extraction and verification as every other source. Compiled layoff tallies are excluded by design.</td>
        <td>Verified (named report)</td>
        <td><a href="https://www.rnz.co.nz/international/pacific" target="_blank" rel="noopener">RNZ Pacific &#8599;</a></td>
      </tr>
      <tr>
        <td><b>National publisher feeds</b><br><span class="alt-muted">15 countries, one publisher each</span></td><td>Egypt · Colombia · Ethiopia · Kazakhstan · Ghana · Pakistan · Jordan · Iraq · Jamaica · Nepal · Papua New Guinea · Paraguay · Sri Lanka · Serbia · Peru</td>
        <td>The leading business or national publisher in each of fifteen mid-sized economies, read twice daily from the publisher's own feed. These are countries where a national news edition returns the worldwide English feed and no regional service covers them, so nothing local was ever being requested. One publisher per country, chosen by measurement: every candidate was fetched first hand and ten of twenty-five were unusable, each for a reason printed in the publisher catalogue below. Only stories carrying collective-layoff language in English, Spanish, Russian or Serbian are read further. The publication decides nothing: the article text itself determines the country and the count, through the same extraction and verification as every other source. Compiled layoff tallies are excluded by design.</td>
        <td>Verified (named report)</td>
        <td><a href="#alt-src-catalogue">See the catalogue &darr;</a></td>
      </tr>
      <tr>
        <td><b>International news feeds</b><br><span class="alt-muted">NewsData.io · Marketaux · Finnhub</span></td><td>Worldwide, Europe-weighted</td>
        <td>Extends the news net into non-English outlets (German, French, Dutch, Spanish, Italian) so European cuts surface without waiting for English coverage. Every candidate runs through the same extraction, de-duplication and verification as the rest.</td>
        <td>Verified (named report)</td>
        <td><a href="https://newsdata.io" target="_blank" rel="noopener">NewsData.io &#8599;</a></td>
      </tr>
      <tr>
        <td><b>US federal RIFs (OPM)</b></td><td>US federal agencies</td>
        <td>Official executed Reduction-in-Force separations from OPM's EHRI workforce dataset, grouped by agency and month. This is the documented floor for federal layoffs. Announced or deferred-resignation federal cuts arrive through the news feed instead. No AI processing.</td>
        <td>Verified</td>
        <td><a href="https://data.opm.gov/explore-data/analytics/workforce-changes" target="_blank" rel="noopener">OPM workforce data &#8599;</a></td>
      </tr>
      <tr>
        <td><b>Company IR &amp; newsroom feeds</b></td><td>Reviewed employer/exchange feeds</td>
        <td>A reviewed allowlist of company investor-relations and newsroom RSS feeds, checked twice daily so a layoff a company discloses in its own release is caught even before wire pickup. Runs through the same extraction and verification as the rest.</td>
        <td>Verified (named report)</td>
        <td><span class="alt-muted">Reviewed feed list</span></td>
      </tr>
      <tr>
        <td><b>Distress &amp; insolvency signals</b></td><td>US bankruptcy &middot; UK insolvency</td>
        <td>CourtListener US bankruptcy petitions and Companies House UK insolvency filings flag employers in distress. We then run those employers through the news pipeline. A layoff only enters the tracker when a sourced, counted report confirms it. The filing itself is a lead, not a count.</td>
        <td>Signal (feeds verification)</td>
        <td><a href="https://www.courtlistener.com" target="_blank" rel="noopener">CourtListener &#8599;</a></td>
      </tr>
      <tr>
        <td><b>BLS LAUS</b></td><td>US states without a public WARN register</td>
        <td>Official monthly state unemployment rate from the Bureau of Labor Statistics. A separate context metric (not a layoff count), shown only for states that publish no usable notices, so every state carries an authoritative sourced number.</td>
        <td>Context (labeled)</td>
        <td><a href="https://www.bls.gov/lau/" target="_blank" rel="noopener">BLS LAUS &#8599;</a></td>
      </tr>
      <tr>
        <td>EDINET / OpenDART / CVM</td><td>Japan · South Korea · Brazil</td>
        <td>Official corporate-filing systems. We <em>retired</em> them as discovery probes after months live yielded zero layoff rows, because these filings essentially never announce layoffs. Worldwide news covers Japan, South Korea and Brazil instead. Client kept, re-runnable on demand.</td>
        <td>Retired probe</td>
        <td><a href="https://disclosure2.edinet-fsa.go.jp/" target="_blank" rel="noopener">EDINET &#8599;</a></td>
      </tr>
    </tbody>
  </table></div>
  <p class="alt-muted"><b>Verified</b> means a filing or a named report is behind it. That is the headline number. <b>Announced</b> means a company plan reported at the announcement stage, before it takes effect. We keep it in a separate tier and never mix it into the verified total.</p>

  <h2 id="alt-state-warn">US state WARN registries we read (<?php echo (count($alt_state_urls) - (isset($alt_state_urls['DC']) ? 1 : 0)); ?> states + DC)</h2>
  <p>The federal WARN Act requires large employers to file advance notice of mass layoffs with their state's dislocated-worker unit. We import those official notices daily from every state that publishes usable per-notice data. Each link is the state's own official WARN page, the exact source our importer reads.</p>
  <?php /*
     TWO COUNTS OF ONE THING, AND NEITHER OF THEM SAID WHICH IT WAS.

     This page counted alt_state_warn_urls(), the registries the importer
     reads. The dashboard ribbon and the methodology page count
     alt_warn_states_phrase(), which is distinct states PRESENT IN THE DATA.
     Those are different questions and on 2026-08-10 they gave different
     answers on the same tracker, one page apart, with no basis stated on
     either: "47 states + DC" here, "46 US states + DC" there. A journalist
     checking the WARN claim across two of our own pages found two numbers and
     no way to tell which one to cite.

     Neither number is wrong and neither moves. What was missing is the label,
     so both are now named here, on the page that shows the list, next to the
     list. The comment on alt_warn_states_phrase() says it exists "so no
     surface has to reassemble it and get the DC arithmetic wrong again"; the
     reconciliation below is read from that same function rather than
     recomputed, for the same reason.
  */
  $alt_filed_phrase = function_exists('alt_warn_states_phrase') ? alt_warn_states_phrase() : '';
  if ($alt_filed_phrase) : ?>
  <p class="alt-muted"><b>Two counts, and they answer different questions.</b> The <?php echo (count($alt_state_urls) - (isset($alt_state_urls['DC']) ? 1 : 0)); ?> states and DC above are the registries we <em>read</em>, every day. Elsewhere on the tracker you will see <b><?php echo esc_html($alt_filed_phrase); ?></b>: that is the narrower count of jurisdictions whose notices are actually <em>in</em> the database so far. A registry we read that has not yet published a notice we could count appears in the first number and not the second.</p>
  <?php endif; ?>
  <?php if ($alt_state_urls) : ?>
  <div class="alt-health-table-wrap"><table class="alt-sortable alt-sources-table alt-warn-table">
    <thead><tr><th>State</th><th>Official WARN registry (direct link)</th><th>We re-import</th></tr></thead>
    <tbody>
    <?php foreach ($alt_state_urls as $alt_code => $alt_url) :
        $alt_name = isset($alt_state_names[$alt_code]) ? $alt_state_names[$alt_code] : $alt_code; ?>
      <tr>
        <td><?php echo esc_html($alt_name); ?> <span class="alt-muted">(<?php echo esc_html($alt_code); ?>)</span></td>
        <td><a href="<?php echo esc_url($alt_url); ?>" target="_blank" rel="noopener"><?php echo esc_html(preg_replace('#^https?://(www\.)?#', '', rtrim($alt_url, '/'))); ?> &#8599;</a></td>
        <td class="alt-warn-cadence">Daily · 11am ET</td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <p class="alt-muted">Each state publishes on its own schedule: some daily, some weekly, some quarterly. We re-import every state <b>daily at 11am ET</b>, so a state's newest posted notices appear here within a day. Where a state offers a page for each notice, the entry links straight to it. Otherwise the link goes to the state's official WARN list or data file.</p>
  <?php else : ?>
  <p class="alt-muted">The state WARN registry list is being generated and will appear on the next update.</p>
  <?php endif; ?>

  <h2 id="alt-src-gaps">States not yet in the automated WARN feed, and why</h2>
  <p>All 50 states already appear in the tracker through SEC filings and news. The gap is only in state WARN <em>notices</em>. Each state below links to where it publishes (or an explanation of why it doesn't), in plain terms:</p>
  <div class="alt-health-table-wrap"><table class="alt-sortable alt-sources-table alt-gap-table">
    <thead><tr><th>State</th><th>Why it isn't in the WARN feed yet</th><th>Status</th><th>Where it publishes</th><th>Official unemployment (BLS)</th></tr></thead>
    <tbody>
    <?php foreach ($alt_gap_states as $alt_g) :
        $alt_gs = isset($alt_g[3]) ? $alt_g[3] : '';
        $alt_code = isset($alt_g[4]) ? $alt_g[4] : '';
        $alt_u = ($alt_code && isset($alt_unemp[$alt_code])) ? $alt_unemp[$alt_code] : null;
        $alt_cls = (strpos($alt_g[2], 'Publishes') === 0) ? 'alt-gap-progress' : 'alt-gap-none'; ?>
      <tr>
        <td><b><?php echo esc_html($alt_g[0]); ?></b></td>
        <td><?php echo esc_html($alt_g[1]); ?></td>
        <td><span class="alt-gap-status <?php echo $alt_cls; ?>"><?php echo esc_html($alt_g[2]); ?></span></td>
        <td><?php if ($alt_gs) : ?><a href="<?php echo esc_url($alt_gs); ?>" target="_blank" rel="noopener"><?php echo esc_html(preg_replace('#^https?://(www\.)?#', '', rtrim($alt_gs, '/'))); ?> &#8599;</a><?php else : ?><span class="alt-muted">n/a</span><?php endif; ?></td>
        <td class="alt-warn-cadence"><?php if ($alt_u) : ?><a href="https://www.bls.gov/eag/eag.<?php echo esc_attr(strtolower($alt_code)); ?>.htm" target="_blank" rel="noopener"><?php echo esc_html(number_format((float) $alt_u['rate'], 1)); ?>% <span class="alt-muted">(<?php echo esc_html($alt_u['period']); ?>)</span> &#8599;</a><?php else : ?><span class="alt-muted">n/a</span><?php endif; ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <p class="alt-muted"><b>"Publishes notices, no public headcounts"</b> states post WARN notices without a per-employer employee count. Those notices cannot become countable rows, because we never invent a number. <b>"No public register"</b> and <b>"Confidential by law"</b> states keep WARN filings internal. In both cases those cuts still reach the tracker through SEC filings and named news, never invented and never estimated. The <b>unemployment column is a separate official metric</b>. It is the state's monthly BLS rate, not a layoff count. We show it so every state carries an authoritative, sourced number even where individual notices are not public.</p>

  <?php if (file_exists(ALT_PLUGIN_DIR . 'templates/partials/scan-scope.php')) include ALT_PLUGIN_DIR . 'templates/partials/scan-scope.php'; ?>

  <h2 id="alt-src-global">Why most countries appear through news, not a registry</h2>
  <p>Almost every country requires employers to notify a labour authority before a mass layoff. But most treat those filings as <b>confidential</b>. They publish totals only, never a public list of which companies are cutting. Only <b>US states</b>, <b>Quebec</b> and <b>Poland's Mazovia region</b> publish a public, per-employer notice register we can read directly. The Mazovia register is WUP Warszawa, and a 2026 survey of all 16 Polish voivodeship labour offices found it is the only one that names employers. Everywhere else, the honest options are two. One is the EU's <b>Eurofound ERM</b>, which compiles large restructuring events from national correspondents. The other is a <b>reviewed allowlist of that country's news outlets</b>. That is why a German or Japanese layoff reaches this tracker through a named news report rather than a government file. The government has the file. It just does not make it public. We link each country's official labour authority below, so you can check the filing requirement, and its confidentiality, yourself.</p>
  <?php if (file_exists(ALT_PLUGIN_DIR . 'templates/partials/global-authorities-table.php')) include ALT_PLUGIN_DIR . 'templates/partials/global-authorities-table.php'; ?>

  <h2 id="alt-src-news">Worldwide news, every country &amp; outlet we scan<?php if (!empty($alt_scan_countries)) : ?> (<?php echo number_format((int) $alt_scan_countries); ?> countries, <?php echo number_format((int) $alt_scan_outlets); ?> outlets)<?php endif; ?></h2>
  <p>Beyond official filings, we watch a reviewed allowlist of reputable news outlets in every country, in 65+ languages. We check them twice daily through GDELT and Google News, never the open web. The full list is below, built straight from the collector's own configuration, so it <b>updates automatically whenever a source is added</b>. Each country also shows which official register, if any, we pull directly.</p>
  <?php if (file_exists(ALT_PLUGIN_DIR . 'templates/partials/country-sources-table.php')) : ?>
  <?php include ALT_PLUGIN_DIR . 'templates/partials/country-sources-table.php'; ?>
  <?php else : ?>
  <p class="alt-muted">The full country &amp; outlet list is being generated and will appear on the next update.</p>
  <?php endif; ?>

  <?php /* The publisher research, connected and not. Generated from
       railway/data/source_catalogue.json by generate_source_catalogue.py, so
       a refusal keeps its measured evidence instead of living in a chat log. */ ?>
  <?php if (file_exists(ALT_PLUGIN_DIR . 'templates/partials/source-catalogue-table.php')) : ?>
  <?php include ALT_PLUGIN_DIR . 'templates/partials/source-catalogue-table.php'; ?>
  <?php else : ?>
  <h2 id="alt-src-catalogue">Every publisher we researched, connected or not</h2>
  <p class="alt-muted">The publisher catalogue is being generated and will appear on the next update.</p>
  <?php endif; ?>

  <h2 id="alt-src-verify">How verification works</h2>
  <div class="alt-health-table-wrap"><table class="alt-sortable alt-sources-table">
    <thead><tr><th>Source type</th><th>How it's handled</th></tr></thead>
    <tbody>
      <tr><td>WARN &amp; ERM (structured)</td><td>Imported as-is, with <b>no AI processing</b>. Company, count and date come straight off the official record.</td></tr>
      <tr><td>News &amp; SEC (text)</td><td>A model extracts the facts. A second independent model pass must agree, and a supporting quote must be present. Countries and industries normalize to fixed lists. Counts and dates pass hard validation.</td></tr>
      <tr><td>Corrections</td><td>Label fixes need two passes to agree. <b>Numeric changes and removals always require a human.</b> We log every correction publicly.</td></tr>
    </tbody>
  </table></div>
  <p>Live collector status is on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-tracker-health/')); ?>">tracker health page</a>. The running corrections log is on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-data-sources">tracker itself</a>.</p>

  <h2 id="alt-ai-rubric">How we classify an "AI-attributed" layoff (the rubric)</h2>
  <p>This is the number most likely to be quoted, so here is the exact, testable standard behind it. We report <b>what the employer said</b>, not our own judgment of cause. <b>We never assert in our own voice that AI caused a layoff.</b></p>
  <div class="alt-health-table-wrap"><table class="alt-sortable alt-sources-table">
    <thead><tr><th>Tier</th><th>What qualifies</th><th>Example language</th><th>Counts as&hellip;</th></tr></thead>
    <tbody>
      <tr><td><b>Verified (strict)</b></td><td>The employer names AI/automation as a <b>primary or contributing cause</b> of the cut, and we hold the <b>exact quote</b> from a primary source.</td><td>&ldquo;these roles are being eliminated as AI now performs this work&rdquo;; &ldquo;automation has reduced our need for&hellip;&rdquo;</td><td>Verified AI &#10003;</td></tr>
      <tr><td><b>Broad (wider lens)</b></td><td>Looser AI framing tied to the cut: cutting <i>while</i> funding an AI pivot, or press describing it as AI-driven, without a clean causal quote.</td><td>&ldquo;restructuring to invest in AI&rdquo;; &ldquo;reallocating toward AI priorities&rdquo;; press: &ldquo;amid its AI push&rdquo;</td><td>Broad only (labeled separately, never merged)</td></tr>
      <tr><td>Not counted</td><td>AI investment, future automation projections, or AI used to <i>select</i> who to cut. None of these is a stated cause of the cut.</td><td>&ldquo;we&rsquo;re hiring for AI roles&rdquo;; &ldquo;used an algorithm to rank performance&rdquo;</td><td>Neither</td></tr>
      <tr><td>Denied</td><td>The employer explicitly says the cuts were <b>not</b> due to AI.</td><td>&ldquo;this is unrelated to AI&rdquo;</td><td>Neither (recorded as denial)</td></tr>
    </tbody>
  </table></div>
  <p class="alt-muted">Two honest caveats. (1) The phrase &ldquo;restructuring around AI&rdquo; is sometimes PR cover for ordinary cost-cutting. The <b>broad</b> tier records the framing. It does not verify the cause. (2) Companies rarely say &ldquo;replaced by AI&rdquo; outright, so the strict measure is deliberately conservative. The broad measure exists precisely to show the wider, looser universe alongside it. <b>We always report the two separately and never add them together.</b></p>
  <p class="alt-muted" style="margin-top:8px">Tip: click any column header to sort a table.</p>
</main>
<style>
  .alt-sources-page { font-size: 15.5px; line-height: 1.6; }
  .alt-sources-page h2 { font-size: 21px; margin: 30px 0 10px; scroll-margin-top: 80px; }
  .alt-sources-page .alt-health-table-wrap { border: 1px solid var(--alt-grid); border-radius: 10px; overflow: auto; max-height: 660px; margin: 6px 0 16px; }
  .alt-sources-page table { width: 100%; border-collapse: collapse; font-size: 14.5px; }
  .alt-sources-page table th { text-align: left; font-size: 11.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--alt-muted); font-weight: 700; padding: 9px 14px; border-bottom: 2px solid var(--alt-grid); background: var(--alt-surface-2); position: sticky; top: 0; z-index: 1; }
  .alt-sources-page table td { padding: 10px 14px; border-bottom: 1px solid var(--alt-grid); vertical-align: top; line-height: 1.5; }
  .alt-sources-page table tbody tr:hover { background: var(--alt-surface-2); }
  .alt-sortable thead th:not([data-nosort]) { cursor: pointer; }
  .alt-sortable thead th:not([data-nosort])::after { content: ' \2195'; opacity: .3; font-size: 10px; }
  .alt-sortable thead th[data-sort="asc"]::after { content: ' \2191'; opacity: 1; }
  .alt-sortable thead th[data-sort="desc"]::after { content: ' \2193'; opacity: 1; }
</style>
<script>
(function () {
  function num(s) { var n = parseFloat((s || '').replace(/[^0-9.\-]/g, '')); return isNaN(n) ? null : n; }
  document.querySelectorAll('table.alt-sortable').forEach(function (table) {
    var ths = table.querySelectorAll('thead th');
    ths.forEach(function (th, ci) {
      if (th.hasAttribute('data-nosort')) return;
      th.addEventListener('click', function () {
        var tb = table.querySelector('tbody'); if (!tb) return;
        var rows = Array.prototype.slice.call(tb.querySelectorAll('tr'));
        var asc = th.getAttribute('data-sort') !== 'asc';
        ths.forEach(function (o) { if (o !== th) o.removeAttribute('data-sort'); });
        th.setAttribute('data-sort', asc ? 'asc' : 'desc');
        rows.sort(function (a, b) {
          var av = (a.cells[ci] ? a.cells[ci].textContent : '').trim();
          var bv = (b.cells[ci] ? b.cells[ci].textContent : '').trim();
          var an = num(av), bn = num(bv), cmp;
          if (an !== null && bn !== null) cmp = an - bn;
          else cmp = av.localeCompare(bv, undefined, { numeric: true, sensitivity: 'base' });
          return asc ? cmp : -cmp;
        });
        rows.forEach(function (r) { tb.appendChild(r); });
      });
    });
  });
})();
</script>
