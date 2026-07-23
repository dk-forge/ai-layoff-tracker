<?php if (!defined('ABSPATH')) exit;
// Year-by-year stats straight from the fast table, cached an hour. The press
// page must never show a number the tracker itself cannot reproduce.
$alt_press_years = get_transient('alt_press_year_stats');
if (!is_array($alt_press_years)) {
    global $wpdb;
    $alt_t = alt_db_table();
    $alt_press_years = $wpdb->get_results(
        "SELECT YEAR(layoff_date) y, COUNT(*) entries, COALESCE(SUM(job_count),0) jobs,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs
         FROM $alt_t WHERE layoff_date >= '2015-01-01' AND layoff_date <= CURDATE()
         GROUP BY YEAR(layoff_date) ORDER BY y DESC", ARRAY_A) ?: array();
    set_transient('alt_press_year_stats', $alt_press_years, HOUR_IN_SECONDS);
}

// Data-backed soundbite LIBRARY, grouped, live, source-reproducible sentences,
// one per chart/metric across two periods (this year to date + latest month)
// plus a per-region/country set. No em-dashes. Cached hourly; raw text stored
// (the template esc_html()s at render).
$alt_sb_groups = get_transient('alt_press_sb_groups');
if (!is_array($alt_sb_groups)) {
    global $wpdb; $alt_t = alt_db_table();
    $alt_tk = home_url('/ai-layoff-tracker/');
    $alt_y = (int) gmdate('Y');
    $alt_ytd_from = sprintf('%04d-01-01', $alt_y); $alt_ytd_to = gmdate('Y-m-d');
    $alt_lm = strtotime(gmdate('Y-m-01') . ' -1 day');
    $alt_m_from = gmdate('Y-m-01', $alt_lm); $alt_m_to = gmdate('Y-m-t', $alt_lm);
    $alt_m_label = gmdate('F Y', $alt_lm);
    $alt_lk = function ($args) use ($alt_tk) { return esc_url(add_query_arg($args, $alt_tk)); };
    $alt_stmap = array('AL'=>'Alabama','AK'=>'Alaska','AZ'=>'Arizona','AR'=>'Arkansas','CA'=>'California','CO'=>'Colorado','CT'=>'Connecticut','DE'=>'Delaware','DC'=>'Washington, D.C.','FL'=>'Florida','GA'=>'Georgia','HI'=>'Hawaii','ID'=>'Idaho','IL'=>'Illinois','IN'=>'Indiana','IA'=>'Iowa','KS'=>'Kansas','KY'=>'Kentucky','LA'=>'Louisiana','ME'=>'Maine','MD'=>'Maryland','MA'=>'Massachusetts','MI'=>'Michigan','MN'=>'Minnesota','MS'=>'Mississippi','MO'=>'Missouri','MT'=>'Montana','NE'=>'Nebraska','NV'=>'Nevada','NH'=>'New Hampshire','NJ'=>'New Jersey','NM'=>'New Mexico','NY'=>'New York','NC'=>'North Carolina','ND'=>'North Dakota','OH'=>'Ohio','OK'=>'Oklahoma','OR'=>'Oregon','PA'=>'Pennsylvania','RI'=>'Rhode Island','SC'=>'South Carolina','SD'=>'South Dakota','TN'=>'Tennessee','TX'=>'Texas','UT'=>'Utah','VT'=>'Vermont','VA'=>'Virginia','WA'=>'Washington','WV'=>'West Virginia','WI'=>'Wisconsin','WY'=>'Wyoming');

    // Query helpers (columns are fixed literals, not user input).
    $alt_stats = function ($from, $to, $cty) use ($wpdb, $alt_t) {
        // v = verified job cuts; aiv = strict AI (employer's own words); aib = the
        // broad AI-linked measure (matches the ai_broad_jobs aggregate exactly:
        // ai_explicit OR ai_causation='ai_linked'). Both AI measures share the
        // verified-tier (announced=0) denominator so their percentages compare.
        $sql = "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                       COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) aiv,
                       COALESCE(SUM(CASE WHEN (ai_explicit=1 OR ai_causation='ai_linked') AND announced=0 THEN job_count END),0) aib
                FROM $alt_t WHERE layoff_date BETWEEN %s AND %s";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_top = function ($col, $from, $to, $cty) use ($wpdb, $alt_t) {
        $sql = "SELECT $col k, SUM(job_count) j FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND $col <> ''";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        $sql .= " GROUP BY $col ORDER BY j DESC LIMIT 1";
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_bigcut = function ($from, $to, $cty) use ($wpdb, $alt_t) {
        $sql = "SELECT company, job_count FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND job_count > 0";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        $sql .= " ORDER BY job_count DESC, id DESC LIMIT 1";
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_toprole = function ($from, $to) use ($wpdb, $alt_t) {
        if (!function_exists('alt_role_categories')) return null;
        $best = null; $bj = 0; $bs = '';
        foreach (alt_role_categories() as $slug => $lab) {
            $j = (int) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(job_count),0) FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND role_categories LIKE %s", $from, $to, '%,' . $slug . ',%'));
            if ($j > $bj) { $bj = $j; $best = $lab; $bs = $slug; }
        }
        return $best ? array('label' => $best, 'slug' => $bs, 'j' => $bj) : null;
    };

    // Build one period's chart soundbites (worldwide).
    $alt_period_items = function ($from, $to, $when, $periodarg, $reportlink) use ($alt_stats, $alt_top, $alt_bigcut, $alt_toprole, $alt_lk, $alt_stmap) {
        $items = array();
        $s = $alt_stats($from, $to, ''); $v = (int) ($s->v ?? 0); $aiv = (int) ($s->aiv ?? 0); $aib = (int) ($s->aib ?? 0);
        $pct = $v ? round(100 * $aiv / $v) : 0; $pctb = $v ? round(100 * $aib / $v) : 0;
        if ($v) $items[] = array('label' => 'Headline', 'text' => 'In ' . $when . ', the AI Layoff Tracker verified ' . number_format($v) . ' job cuts worldwide. ' . $pct . '% named AI in the employer\'s own words (verified); a broader ' . $pctb . '% carry some AI link (broad measure).', 'link' => $alt_lk($periodarg), 'linklabel' => 'the live total');
        $ind = $alt_top('industry', $from, $to, '');
        if ($ind && $ind->k) $items[] = array('label' => 'Top industry', 'text' => $ind->k . ' was the hardest-hit industry in ' . $when . ', with ' . number_format((int) $ind->j) . ' recorded job cuts.', 'link' => $alt_lk(array_merge($periodarg, array('industry' => $ind->k))), 'linklabel' => 'the industry chart');
        $ctry = $alt_top('country', $from, $to, '');
        if ($ctry && $ctry->k) $items[] = array('label' => 'Top country', 'text' => $ctry->k . ' led the world in recorded job cuts in ' . $when . ', with ' . number_format((int) $ctry->j) . '.', 'link' => $alt_lk(array_merge($periodarg, array('country' => $ctry->k))), 'linklabel' => 'the world map');
        $st = $alt_top('state', $from, $to, 'United States');
        if ($st && $st->k) $items[] = array('label' => 'Top US state', 'text' => (isset($alt_stmap[$st->k]) ? $alt_stmap[$st->k] : $st->k) . ' recorded the most US layoffs in ' . $when . ', with ' . number_format((int) $st->j) . '.', 'link' => $alt_lk(array_merge($periodarg, array('country' => 'United States', 'state' => $st->k))), 'linklabel' => 'the US map');
        $r = $alt_toprole($from, $to);
        if ($r) $items[] = array('label' => 'Roles hit hardest', 'text' => $r['label'] . ' was the job function hit hardest by layoffs in ' . $when . ', across ' . number_format($r['j']) . ' cuts where the source named the team affected.', 'link' => $alt_lk(array_merge($periodarg, array('roles' => $r['slug']))), 'linklabel' => 'the roles chart');
        $big = $alt_bigcut($from, $to, '');
        if ($big && $big->company) $items[] = array('label' => 'Largest single cut', 'text' => 'The single largest layoff in ' . $when . ' was ' . $big->company . ', at ' . number_format((int) $big->job_count) . ' jobs.', 'link' => $alt_lk(array_merge($periodarg, array('company' => $big->company))), 'linklabel' => 'the event');
        return $items;
    };

    $alt_sb_groups = array();
    $ytd_items = $alt_period_items($alt_ytd_from, $alt_ytd_to, $alt_y . ' so far', array('years' => $alt_y), '');
    if ($ytd_items) $alt_sb_groups[] = array('id' => 'sb-ytd', 'title' => $alt_y . ' year to date', 'items' => $ytd_items);
    $m_items = $alt_period_items($alt_m_from, $alt_m_to, $alt_m_label, array('years' => $alt_y, 'months' => (int) gmdate('n', $alt_lm)), '');
    if ($m_items) $alt_sb_groups[] = array('id' => 'sb-month', 'title' => 'Latest complete month (' . $alt_m_label . ')', 'items' => $m_items);

    // Per-region / country (year to date). Worldwide first, then key markets.
    $alt_places = array(
        array('World', '', 'Worldwide, '),
        array('the United States', 'United States', 'In the United States, '),
        array('Germany', 'Germany', 'In Germany, '),
        array('the United Kingdom', 'United Kingdom', 'In the United Kingdom, '),
        array('France', 'France', 'In France, '),
        array('Canada', 'Canada', 'In Canada, '),
        array('Australia', 'Australia', 'In Australia, '),
        array('India', 'India', 'In India, '),
    );
    $geo_items = array();
    foreach ($alt_places as $p) {
        $s = $alt_stats($alt_ytd_from, $alt_ytd_to, $p[1]); $v = (int) ($s->v ?? 0); $aiv = (int) ($s->aiv ?? 0); $aib = (int) ($s->aib ?? 0);
        $pct = $v ? round(100 * $aiv / $v) : 0; $pctb = $v ? round(100 * $aib / $v) : 0;
        if ($v > 0) $geo_items[] = array('label' => $p[0], 'text' => $p[2] . number_format($v) . ' job cuts have been recorded in ' . $alt_y . ': ' . $pct . '% attributed to AI in the employer\'s own words (verified), ' . $pctb . '% under the broader AI-linked measure.', 'link' => $alt_lk($p[1] === '' ? array('years' => $alt_y) : array('years' => $alt_y, 'country' => $p[1])), 'linklabel' => 'the data');
    }
    if ($geo_items) $alt_sb_groups[] = array('id' => 'sb-geo', 'title' => 'By region and country (' . $alt_y . ')', 'items' => $geo_items);

    set_transient('alt_press_sb_groups', $alt_sb_groups, HOUR_IN_SECONDS);
}
?>
<main class="alt-wrap alt-press-page">
  <?php if (function_exists('alt_dataset_jsonld') && !defined('ALT_PRESS_LD_DONE')) { define('ALT_PRESS_LD_DONE', 1); alt_output_jsonld(array(alt_dataset_jsonld())); } ?>
  <p class="alt-eyebrow">AskTheRecruiter · press &amp; media kit</p>
  <h1>Press &amp; Media Kit</h1>
  <p class="alt-lead"><span class="alt-lead-text">Everything a reporter needs to cite the AI Layoff Tracker: the boilerplate, live quotable figures, how the data is verified, brand assets, and a direct contact. Every number on this page is reproducible from our public API.</span></p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a href="<?php echo esc_url(home_url('/contact/')); ?>">Contact us</a></p>

  <p class="alt-verify-cta"><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>"><b>How we verify every number:</b> read the full methodology and source list &rarr;</a></p>

  <nav class="alt-press-toc" aria-label="On this page">
    <span class="alt-toc-label">On this page</span>
    <a href="#alt-boilerplate">Boilerplate</a>
    <a href="#alt-why-cite">Why cite us</a>
    <a href="#alt-key-stats">Key stats</a>
    <a href="#alt-dataset">The dataset &amp; API</a>
    <a href="#alt-brand">Brand assets</a>
    <a href="#alt-soundbites"><b>Ready-to-use soundbites &darr;</b></a>
    &middot; <a href="#alt-evidence-ladder"><b>AI evidence ladder &darr;</b></a>
    &middot; <a href="#alt-press-statements"><b>Press statements &darr;</b></a>
  </nav>

  <h2 id="alt-boilerplate">Boilerplate</h2>
  <p><b>AskTheRecruiter</b> is the open, evidence-based intelligence platform helping workers understand the changing job market and improve their chances of getting hired. Its <b>AI Layoff Tracker</b> is a continuously updated, source-linked database of verified job cuts worldwide, purpose-built to flag which layoffs companies themselves attribute to AI or automation, every figure clickable back to a primary document.</p>
  <p class="alt-muted"><b>One-line version:</b> "The AI Layoff Tracker by AskTheRecruiter.com, a source-linked database of layoffs worldwide, flagging the ones companies blame on AI."</p>

  <h2>About the AI Layoff Tracker</h2>
  <p>The AI Layoff Tracker is a continuously updated database of verified job cuts worldwide, with a specific focus on flagging which layoffs companies attribute to AI or automation. Every entry links to a primary source: an SEC 8-K filing, a state WARN notice, or a named news report with a direct quote. Live editorial tracking began in January 2026; the database also carries historical records back to 2002 (Europe) and 2015 (US), built from official WARN filings, SEC disclosures and the EU's restructuring monitor, so year-over-year comparisons are possible.</p>

  <h2 id="alt-why-cite">Why it's worth citing</h2>
  <div class="alt-health-table-wrap"><table class="alt-sources-table alt-angles-table">
    <thead><tr><th>The angle</th><th>Why it's a story</th></tr></thead>
    <tbody>
      <tr><td><b>We break out the AI cuts</b></td><td>Most layoff trackers give you one lump-sum number and stop. We flag the cuts a company itself pinned on AI or automation, each with the employer's own quote on file, so "AI-attributed" becomes a figure a reporter can source instead of guess at.</td></tr>
      <tr><td><b>Every number is a receipt</b></td><td>Estimate-based trackers hand you a figure. We hand you the document behind it: an SEC filing, a WARN notice, or a named report. It's a floor you can prove, not a projection.</td></tr>
      <tr><td><b>We count each cut once, on the day it happens</b></td><td>Every layoff is dated by when it takes effect, not when its notice was filed, and de-duplicated so one event is never summed twice. That is why we land within about 10 percent of independent WARN trackers. A tracker reporting several times higher is usually adding a company-wide headcount onto every state filing, which counts the same people over and over.</td></tr>
      <tr><td><b>We show where AI is cutting</b></td><td>A live world map, the teams hit hardest, and AI's rising share month over month: the geographic and functional detail a press release can't give a reporter.</td></tr>
      <tr><td><b>We audit our own completeness</b></td><td>We keep a standing checklist of 51 of the most significant layoffs major outlets have covered and re-check our database against it every week. We currently carry every one of them. Any gap is a finding we chase and backfill, not a number we quietly round up to.</td></tr>
      <tr><td><b>Nothing is hidden</b></td><td>A public corrections log, open methodology, the full source list, and an API anyone can reproduce. When we catch an error, we publish it.</td></tr>
    </tbody>
  </table></div>

  <h2>Press contact</h2>
  <p>For data requests, custom cuts of the dataset, corrections, or comment, use the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>. Press and reporter requests get priority, and every correction to a published figure is logged publicly on the tracker.</p>

  <h2>Using our data</h2>
  <p>Free for editorial, research, and educational use under CC BY 4.0. Please attribute to asktherecruiter.com and link back where possible.</p>
  <p><b>Suggested attribution:</b> "According to the AI Layoff Tracker by AskTheRecruiter.com..."</p>

  <h2 id="alt-key-stats">Key stats by year</h2>
  <p>Live figures from the same database the tracker serves. "AI-attributed" uses our strict standard: the company named AI as a primary or contributing cause, with a supporting quote on file. A separate broader measure (looser AI-linked attributions) is available in the <code>ai_broad_jobs</code> API field.</p>
  <?php $alt_lu = function_exists('alt_data_last_updated_label') ? alt_data_last_updated_label() : ''; ?>
  <?php if ($alt_lu) : ?><p class="alt-muted"><b>Data last updated:</b> <?php echo esc_html($alt_lu); ?>, the moment the underlying database last changed (a new filing/notice/report was added), not the time you loaded this page.</p><?php endif; ?>
  <div class="alt-health-table-wrap"><table class="alt-press-table">
    <thead><tr><th>Year</th><th class="num">Verified layoffs</th><th class="num">Job cuts recorded</th><th class="num">AI-attributed (strict)</th></tr></thead>
    <tbody>
    <?php foreach ($alt_press_years as $alt_y) : ?>
      <tr><td><b><?php echo (int) $alt_y['y']; ?></b></td><td class="num"><?php echo number_format((int) $alt_y['entries']); ?></td><td class="num"><?php echo number_format((int) $alt_y['jobs']); ?></td><td class="num"><?php echo number_format((int) $alt_y['ai_jobs']); ?></td></tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <p>Coverage depth varies by year: 2015 to 2023 is primarily official US WARN filings; from 2024 on, worldwide news, SEC filings and European Restructuring Monitor coverage deepen. Methodology and per-country sources are documented on the tracker itself.</p>

  <h2>Editorial independence</h2>
  <p>The tracker is a data product of AskTheRecruiter.com. Its numbers are produced by fixed, published rules: counts come only from linked primary documents, AI labels require the employer's own words, and no figure is adjusted for any commercial purpose. The full methodology, the per-country source list, the public corrections log and the collection code are open for inspection, and the dataset can be reproduced from the public API by anyone.</p>

  <h2 id="alt-dataset">Access the full dataset</h2>
  <p>Filtered or full CSV and JSON exports are on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">tracker page</a>. The public REST API serves the same data live: <code>GET /blog/wp-json/layoffs/v1/query</code> and <code>GET /blog/wp-json/layoffs/v1/aggregate</code>. Company pages with stable, linkable URLs live under <code>/company-layoffs/</code> (for example, a reporter can cite one company's full source-linked history at a permanent address).</p>

  <h2 id="alt-brand">Brand assets</h2>
  <div class="alt-brand-kit">
    <span class="alt-brand-lockup">
      <span class="alt-brand-mark" aria-hidden="true">atr</span>
      <span class="alt-brand-word">Ask The Recruiter</span>
    </span>
    <ul class="alt-brand-colors">
      <li><span class="alt-swatch" style="background:#4f7257"></span> Primary green <code>#4F7257</code></li>
      <li><span class="alt-swatch" style="background:#d4a574"></span> Accent <code>#D4A574</code></li>
      <li><span class="alt-swatch" style="background:#16181d"></span> Ink <code>#16181D</code></li>
    </ul>
  </div>
  <p class="alt-muted">The wordmark and "atr" mark above may be used to credit the tracker in coverage. For high-resolution PNG or SVG logo files or a specific lockup, ask through the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a> and we'll send them the same day.</p>

  <?php if ($alt_sb_groups) : ?>
  <h2 id="alt-soundbites">Ready-to-use soundbites</h2>
  <p>Live, source-backed one-liners a reporter can drop straight into a story. Every figure updates automatically from the tracker and links to the exact chart behind it. Copy, cite, done. Attribute to "the AI Layoff Tracker by AskTheRecruiter.com."</p>
  <p class="alt-sb-disclaimer"><b>Two AI measures, always labeled.</b> <b>Verified</b> counts only cuts where the employer named AI in its own words, with the quote on file. The <b>broad measure</b> also counts looser AI-linked cases (an AI pivot underway, press AI-framing) and is always larger. We show both so you can pick the standard your story needs; they are never merged, and both use the same verified-tier base.</p>
    <?php foreach ($alt_sb_groups as $alt_g) : ?>
  <h3 id="<?php echo esc_attr($alt_g['id']); ?>" class="alt-sb-grouptitle"><?php echo esc_html($alt_g['title']); ?></h3>
  <div class="alt-soundbites">
      <?php foreach ($alt_g['items'] as $alt_sb) : ?>
    <figure class="alt-soundbite">
      <span class="alt-sb-label"><?php echo esc_html($alt_sb['label']); ?></span>
      <blockquote class="alt-sb-text"><?php echo esc_html($alt_sb['text']); ?></blockquote>
      <figcaption class="alt-sb-actions">
        <button type="button" class="alt-btn alt-btn-sm alt-sb-copy">Copy</button>
        <a class="alt-sb-link" href="<?php echo $alt_sb['link']; ?>">&#128202; See <?php echo esc_html($alt_sb['linklabel']); ?> &rarr;</a>
      </figcaption>
    </figure>
      <?php endforeach; ?>
  </div>
    <?php endforeach; ?>
  <p class="alt-muted">Figures are current live values and change as new sources are verified. Every number is reproducible from the public API.</p>
  <?php endif; ?>

<?php
// ---------------------------------------------------------------------------
// AI EVIDENCE LADDER + PRESS STATEMENTS
//
// Soundbites are one sentence. Reporters also need a paragraph they can paste
// into a pitch, with the filtered view already built so the claim can be
// checked in one click. Everything below is generated from live data, cached
// hourly, and every statement carries the preset link that reproduces it.
// ---------------------------------------------------------------------------
$alt_ps = get_transient('alt_press_statements');
if (!is_array($alt_ps)) {
    global $wpdb; $alt_pt = alt_db_table();
    $alt_ptk = home_url('/ai-layoff-tracker/');
    $alt_plk = function ($args) use ($alt_ptk) { return esc_url(add_query_arg($args, $alt_ptk)); };
    $alt_pn = function ($v) { return number_format((int) $v); };

    // Evidence tiers. These are not new labels: they are the ai_causation values
    // already stored on every row, surfaced so a reporter can choose the
    // strictness their story needs instead of trusting one blended number.
    $alt_tiers = $wpdb->get_row(
        "SELECT COALESCE(SUM(CASE WHEN ai_causation='primary_cause' AND announced=0 THEN job_count END),0) t1,
                COALESCE(SUM(CASE WHEN ai_causation='contributing_cause' AND announced=0 THEN job_count END),0) t2,
                COALESCE(SUM(CASE WHEN ai_causation='ai_linked' AND announced=0 THEN job_count END),0) t3
         FROM $alt_pt WHERE YEAR(layoff_date) = " . (int) gmdate('Y'));

    // One period's figures.
    $alt_pstats = function ($from, $to) use ($wpdb, $alt_pt) {
        return $wpdb->get_row($wpdb->prepare(
            "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                    COALESCE(SUM(CASE WHEN announced=1 THEN job_count END),0) a,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) ai,
                    COUNT(DISTINCT CASE WHEN announced=0 THEN company_key END) co
             FROM $alt_pt WHERE layoff_date BETWEEN %s AND %s", $from, $to));
    };
    $alt_ptopcol = function ($col, $from, $to, $ai_only) use ($wpdb, $alt_pt) {
        $extra = $ai_only ? " AND ai_explicit=1" : "";
        return $wpdb->get_row($wpdb->prepare(
            "SELECT $col k, SUM(job_count) j FROM $alt_pt
             WHERE layoff_date BETWEEN %s AND %s AND $col <> '' AND announced=0 $extra
             GROUP BY $col ORDER BY j DESC LIMIT 1", $from, $to));
    };
    $alt_pbig = function ($from, $to) use ($wpdb, $alt_pt) {
        return $wpdb->get_row($wpdb->prepare(
            "SELECT company, job_count, country FROM $alt_pt
             WHERE layoff_date BETWEEN %s AND %s AND announced=0 AND job_count > 0
             ORDER BY job_count DESC, id DESC LIMIT 1", $from, $to));
    };
    $alt_stn = array('AL'=>'Alabama','AK'=>'Alaska','AZ'=>'Arizona','AR'=>'Arkansas','CA'=>'California','CO'=>'Colorado','CT'=>'Connecticut','DE'=>'Delaware','DC'=>'Washington, D.C.','FL'=>'Florida','GA'=>'Georgia','HI'=>'Hawaii','ID'=>'Idaho','IL'=>'Illinois','IN'=>'Indiana','IA'=>'Iowa','KS'=>'Kansas','KY'=>'Kentucky','LA'=>'Louisiana','ME'=>'Maine','MD'=>'Maryland','MA'=>'Massachusetts','MI'=>'Michigan','MN'=>'Minnesota','MS'=>'Mississippi','MO'=>'Missouri','MT'=>'Montana','NE'=>'Nebraska','NV'=>'Nevada','NH'=>'New Hampshire','NJ'=>'New Jersey','NM'=>'New Mexico','NY'=>'New York','NC'=>'North Carolina','ND'=>'North Dakota','OH'=>'Ohio','OK'=>'Oklahoma','OR'=>'Oregon','PA'=>'Pennsylvania','RI'=>'Rhode Island','SC'=>'South Carolina','SD'=>'South Dakota','TN'=>'Tennessee','TX'=>'Texas','UT'=>'Utah','VT'=>'Vermont','VA'=>'Virginia','WA'=>'Washington','WV'=>'West Virginia','WI'=>'Wisconsin','WY'=>'Wyoming');

    // Build the statement set for one cadence.
    $alt_build = function ($from, $to, $label, $linkargs) use ($alt_pstats, $alt_ptopcol, $alt_pbig, $alt_plk, $alt_pn, $alt_stn) {
        $s = $alt_pstats($from, $to);
        $v = (int) ($s->v ?? 0); $a = (int) ($s->a ?? 0);
        $ai = (int) ($s->ai ?? 0); $co = (int) ($s->co ?? 0);
        if ($v <= 0) return array();
        $out = array();
        $pct = $v > 0 ? round(100 * $ai / $v) : 0;

        // A short window can legitimately contain no explicit AI attribution.
        // Saying "0 (0%)" reads like a broken statistic; saying so plainly, and
        // explaining WHY it lags, is both more honest and more quotable.
        $aiclause = $ai > 0
            ? sprintf('Of those, %s carry the employer\'s own words naming AI or automation as a cause (%d%% of the documented total).',
                      $alt_pn($ai), $pct)
            : 'None of them carries an explicit AI attribution from the employer yet. That is normal for a short window: WARN notices and filings record a cut\'s size, date and location, not its cause, so an AI attribution usually arrives later with the company\'s own statement.';
        $out[] = array(
            'label' => 'The documented floor',
            'text'  => sprintf(
                'For %s, %s job cuts are documented worldwide: every one traceable to an SEC filing, a state WARN notice, or a named news report, counted on the day the cut takes effect. %s A further %s sit in the separately labeled announced tier, which is company plans at announcement stage and is never mixed into the documented figure. Announcement surveys count intentions on the day they are announced, including multi-year plans and receiptless separations; this figure counts what has a paper trail behind it, so treat it as a floor you can verify rather than an estimate.',
                $label, $alt_pn($v), $aiclause, $alt_pn($a)),
            'link' => $alt_plk($linkargs), 'linklabel' => 'the exact rows behind this figure');

        $st = $alt_ptopcol('state', $from, $to, false);
        if ($st && $st->k && isset($alt_stn[$st->k])) {
            $stai = $alt_ptopcol('state', $from, $to, true);
            $aitxt = ($stai && $stai->k === $st->k)
                ? sprintf(' Within that, %s jobs carry an explicit AI attribution from the employer.', $alt_pn($stai->j))
                : '';
            $out[] = array(
                'label' => 'Localized: top US state',
                'text'  => sprintf(
                    '%s recorded the largest documented job-cut total of any US state for %s, at %s jobs across filings and named reports.%s Every row links to the state\'s own WARN notice or the company\'s SEC filing, so a regional desk can name the employers, the effective dates and the affected sites without waiting for a national survey.',
                    $alt_stn[$st->k], $label, $alt_pn($st->j), $aitxt),
                'link' => $alt_plk(array_merge($linkargs, array('country' => 'United States', 'state' => $st->k))),
                'linklabel' => $alt_stn[$st->k] . ' rows');
        }

        $ind = $alt_ptopcol('industry', $from, $to, false);
        if ($ind && $ind->k) {
            $out[] = array(
                'label' => 'Sector concentration',
                'text'  => sprintf(
                    '%s absorbed the largest share of documented job cuts for %s, at %s jobs. Sector labels here come from the company plus its own retained source text, are drawn from a fixed vocabulary, and are only written when two independent passes agree, so the breakdown can be reproduced rather than taken on trust.',
                    $ind->k, $label, $alt_pn($ind->j)),
                'link' => $alt_plk(array_merge($linkargs, array('industry' => $ind->k))),
                'linklabel' => $ind->k . ' rows');
        }

        $big = $alt_pbig($from, $to);
        if ($big && $big->company) {
            $out[] = array(
                'label' => 'Largest single documented cut',
                'text'  => sprintf(
                    'The largest single documented cut for %s is %s, at %s jobs. It appears here only because a filing or a named report puts the number on the record, and the entry links straight to that document, so the figure can be checked at source before it is quoted.',
                    $label, $big->company, $alt_pn($big->job_count)),
                'link' => $alt_plk(array_merge($linkargs, array('company' => $big->company))),
                'linklabel' => $big->company . ' entries');
        }
        return $out;
    };

    $alt_y2 = (int) gmdate('Y');
    $alt_wk_from = gmdate('Y-m-d', strtotime('-7 days'));
    $alt_wk_to   = gmdate('Y-m-d');
    $alt_lmts    = strtotime(gmdate('Y-m-01') . ' -1 day');
    $alt_mo_from = gmdate('Y-m-01', $alt_lmts); $alt_mo_to = gmdate('Y-m-t', $alt_lmts);
    $alt_mo_lab  = gmdate('F Y', $alt_lmts);

    $alt_ps = array(
        'generated' => gmdate('j F Y, H:i') . ' UTC',
        'tiers'     => array(
            't1' => (int) ($alt_tiers->t1 ?? 0),
            't2' => (int) ($alt_tiers->t2 ?? 0),
            't3' => (int) ($alt_tiers->t3 ?? 0),
            'year' => $alt_y2,
        ),
        'sets' => array(
            array('id' => 'weekly', 'title' => 'This week', 'sub' => 'rolling 7 days to ' . gmdate('j F Y'),
                  'items' => $alt_build($alt_wk_from, $alt_wk_to, 'the last seven days',
                                        array('from' => $alt_wk_from, 'to' => $alt_wk_to))),
            array('id' => 'monthly', 'title' => $alt_mo_lab, 'sub' => 'complete calendar month',
                  'items' => $alt_build($alt_mo_from, $alt_mo_to, $alt_mo_lab,
                                        array('from' => $alt_mo_from, 'to' => $alt_mo_to))),
            array('id' => 'yearly', 'title' => $alt_y2 . ' year to date', 'sub' => '1 January to today',
                  'items' => $alt_build(sprintf('%04d-01-01', $alt_y2), gmdate('Y-m-d'), $alt_y2 . ' so far',
                                        array('years' => $alt_y2))),
        ),
    );

    // Rolling archive: every earlier month this year and each prior year, so a
    // statement stays reachable after its cadence rolls over.
    $alt_arch = array();
    for ($i = 2; $i <= 13; $i++) {
        $ts = strtotime(gmdate('Y-m-01') . " -$i month");
        $f = gmdate('Y-m-01', $ts); $t = gmdate('Y-m-t', $ts);
        $st = $alt_pstats($f, $t);
        if ((int) ($st->v ?? 0) <= 0) continue;
        $alt_arch[] = array('label' => gmdate('F Y', $ts), 'v' => (int) $st->v, 'ai' => (int) $st->ai,
                            'link' => $alt_plk(array('from' => $f, 'to' => $t)));
    }
    for ($yy = $alt_y2 - 1; $yy >= $alt_y2 - 6; $yy--) {
        $st = $alt_pstats(sprintf('%04d-01-01', $yy), sprintf('%04d-12-31', $yy));
        if ((int) ($st->v ?? 0) <= 0) continue;
        $alt_arch[] = array('label' => 'Full year ' . $yy, 'v' => (int) $st->v, 'ai' => (int) $st->ai,
                            'link' => $alt_plk(array('years' => $yy)));
    }
    $alt_ps['archive'] = $alt_arch;
    set_transient('alt_press_statements', $alt_ps, HOUR_IN_SECONDS);
}
?>

  <h2 id="alt-evidence-ladder">The AI evidence ladder</h2>
  <p>The hardest question about any AI layoff number is what counts as AI. We answer it by never publishing a single blended figure. Every entry already stores how directly the employer tied the cut to AI, so you can pick the standard your story needs and see exactly what falls in or out at each step.</p>
  <div class="alt-health-table-wrap"><table class="alt-sources-table">
    <thead><tr><th>Tier</th><th>What has to be true</th><th><?php echo (int) $alt_ps['tiers']['year']; ?> jobs<br><small>verified tier</small></th><th>Preset view</th></tr></thead>
    <tbody>
      <tr>
        <td><b>Tier 1</b><br><small>AI named as the cause</small></td>
        <td>The employer states AI or automation is <b>the</b> reason for the cut, with the exact quote on file.</td>
        <td><b><?php echo number_format($alt_ps['tiers']['t1']); ?></b></td>
        <td><a href="<?php echo esc_url(add_query_arg(array('years' => $alt_ps['tiers']['year'], 'ai_primary' => '1'), home_url('/ai-layoff-tracker/'))); ?>">Tier 1 only &rarr;</a></td>
      </tr>
      <tr>
        <td><b>Tier 2</b><br><small>AI named among the causes</small></td>
        <td>The employer names AI as <b>a</b> contributing cause alongside others, again with the quote on file.</td>
        <td><b><?php echo number_format($alt_ps['tiers']['t2']); ?></b></td>
        <td><a href="<?php echo esc_url(add_query_arg(array('years' => $alt_ps['tiers']['year'], 'ai' => '1'), home_url('/ai-layoff-tracker/'))); ?>">Tier 1 + 2 &rarr;</a></td>
      </tr>
      <tr>
        <td><b>Tier 3</b><br><small>AI-linked, no direct statement</small></td>
        <td>No employer statement. An AI pivot is underway, or the press framed the cut that way. Reported separately and <b>never</b> merged into the tiers above.</td>
        <td><b><?php echo number_format($alt_ps['tiers']['t3']); ?></b></td>
        <td><a href="<?php echo esc_url(add_query_arg(array('years' => $alt_ps['tiers']['year'], 'ai_broad' => '1'), home_url('/ai-layoff-tracker/'))); ?>">Tiers 1 + 2 + 3 &rarr;</a></td>
      </tr>
    </tbody>
  </table></div>
  <p class="alt-muted">Counts are <b>verified-tier</b> jobs (announced-stage plans excluded) for rows where the employer's stated causation is on record, so they are a subset of the headline AI figure rather than a restatement of it. Our headline AI figure is <b>Tiers 1 and 2 only</b>: the employer's own words. Investment in AI, a future automation projection, or AI used to select who goes does not qualify by itself. If you want the wider lens, cite Tier 3 explicitly and say so.</p>

  <h2 id="alt-press-statements">Press statements</h2>
  <p>Written to be pasted straight into a pitch or a story, with the maths already done. Each one carries the preset view that reproduces it, so an editor can check the claim in a single click. Figures are live and regenerate hourly; the wording stays stable.</p>
  <p class="alt-muted"><b>Generated <?php echo esc_html($alt_ps['generated']); ?>.</b> Weekly, monthly and year-to-date versions run in parallel, and each period drops into the archive at the bottom when it rolls over, so nothing you have already quoted disappears.</p>

  <?php foreach ($alt_ps['sets'] as $alt_set) : if (empty($alt_set['items'])) continue; ?>
  <h3 id="alt-ps-<?php echo esc_attr($alt_set['id']); ?>" class="alt-sb-grouptitle"><?php echo esc_html($alt_set['title']); ?> <small class="alt-muted">(<?php echo esc_html($alt_set['sub']); ?>)</small></h3>
  <div class="alt-soundbites">
    <?php foreach ($alt_set['items'] as $alt_it) : ?>
    <figure class="alt-soundbite alt-press-statement">
      <span class="alt-sb-label"><?php echo esc_html($alt_it['label']); ?></span>
      <blockquote class="alt-sb-text"><?php echo esc_html($alt_it['text']); ?></blockquote>
      <figcaption class="alt-sb-actions">
        <button type="button" class="alt-btn alt-btn-sm alt-sb-copy">Copy statement</button>
        <a class="alt-sb-link" href="<?php echo $alt_it['link']; ?>">&#128202; Open <?php echo esc_html($alt_it['linklabel']); ?> &rarr;</a>
      </figcaption>
    </figure>
    <?php endforeach; ?>
  </div>
  <?php endforeach; ?>

  <?php if (!empty($alt_ps['archive'])) : ?>
  <details class="alt-methodology" id="alt-ps-archive">
    <summary>Statement archive (earlier months and years)</summary>
    <div class="alt-method-body">
      <p>Every period keeps its own preset view, so a figure you quoted last quarter stays reachable and checkable.</p>
      <div class="alt-health-table-wrap"><table class="alt-sortable alt-sources-table">
        <thead><tr><th>Period</th><th>Documented job cuts</th><th>AI, employer's own words</th><th>Preset view</th></tr></thead>
        <tbody>
        <?php foreach ($alt_ps['archive'] as $alt_a) : ?>
          <tr>
            <th><?php echo esc_html($alt_a['label']); ?></th>
            <td><?php echo number_format($alt_a['v']); ?></td>
            <td><?php echo number_format($alt_a['ai']); ?></td>
            <td><a href="<?php echo $alt_a['link']; ?>">Open this period &rarr;</a></td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table></div>
    </div>
  </details>
  <?php endif; ?>
</main>
