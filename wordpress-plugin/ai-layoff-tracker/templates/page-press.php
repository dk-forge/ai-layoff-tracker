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

// Data-backed soundbites — one live, source-reproducible sentence per chart,
// each linking to the exact filtered view behind it. Cached hourly. Raw text is
// stored (no HTML); the template esc_html()s at render.
$alt_soundbites = get_transient('alt_press_soundbites');
if (!is_array($alt_soundbites)) {
    global $wpdb; $alt_t = alt_db_table();
    $alt_tk = home_url('/ai-layoff-tracker/');
    $alt_y = (int) gmdate('Y');
    $alt_ytd_from = sprintf('%04d-01-01', $alt_y); $alt_ytd_to = gmdate('Y-m-d');
    $alt_lm = strtotime(gmdate('Y-m-01') . ' -1 day');
    $alt_m_from = gmdate('Y-m-01', $alt_lm); $alt_m_to = gmdate('Y-m-t', $alt_lm);
    $alt_m_label = gmdate('F Y', $alt_lm);
    $alt_lk = function ($args) use ($alt_tk) { return esc_url(add_query_arg($args, $alt_tk)); };
    $alt_soundbites = array();

    $alt_tot = $wpdb->get_row($wpdb->prepare(
        "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) aiv
         FROM $alt_t WHERE layoff_date BETWEEN %s AND %s", $alt_ytd_from, $alt_ytd_to));
    $alt_v = (int) ($alt_tot->v ?? 0); $alt_aiv = (int) ($alt_tot->aiv ?? 0);
    $alt_aipct = $alt_v ? round(100 * $alt_aiv / $alt_v) : 0;
    if ($alt_v) $alt_soundbites[] = array('label' => 'Headline · ' . $alt_y . ' so far',
        'text' => 'So far in ' . $alt_y . ', the AI Layoff Tracker has verified ' . number_format($alt_v) . ' job cuts worldwide — ' . $alt_aipct . '% of them attributed to AI or automation by the employer.',
        'link' => $alt_lk(array('years' => $alt_y)), 'linklabel' => 'the live total');

    $alt_ind = $wpdb->get_row($wpdb->prepare("SELECT industry, SUM(job_count) j FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND industry <> '' GROUP BY industry ORDER BY j DESC LIMIT 1", $alt_ytd_from, $alt_ytd_to));
    if ($alt_ind && $alt_ind->industry) $alt_soundbites[] = array('label' => 'By industry · ' . $alt_y,
        'text' => $alt_ind->industry . ' is the hardest-hit industry in ' . $alt_y . ', with ' . number_format((int) $alt_ind->j) . ' recorded job cuts.',
        'link' => $alt_lk(array('years' => $alt_y, 'industry' => $alt_ind->industry)), 'linklabel' => 'the industry chart');

    $alt_ctry = $wpdb->get_row($wpdb->prepare("SELECT country, SUM(job_count) j FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND country <> '' GROUP BY country ORDER BY j DESC LIMIT 1", $alt_ytd_from, $alt_ytd_to));
    if ($alt_ctry && $alt_ctry->country) $alt_soundbites[] = array('label' => 'By country · ' . $alt_y,
        'text' => $alt_ctry->country . ' leads the world in recorded job cuts in ' . $alt_y . ', with ' . number_format((int) $alt_ctry->j) . '.',
        'link' => $alt_lk(array('years' => $alt_y, 'country' => $alt_ctry->country)), 'linklabel' => 'the world map');

    $alt_stmap = array('AL'=>'Alabama','AK'=>'Alaska','AZ'=>'Arizona','AR'=>'Arkansas','CA'=>'California','CO'=>'Colorado','CT'=>'Connecticut','DE'=>'Delaware','DC'=>'Washington, D.C.','FL'=>'Florida','GA'=>'Georgia','HI'=>'Hawaii','ID'=>'Idaho','IL'=>'Illinois','IN'=>'Indiana','IA'=>'Iowa','KS'=>'Kansas','KY'=>'Kentucky','LA'=>'Louisiana','ME'=>'Maine','MD'=>'Maryland','MA'=>'Massachusetts','MI'=>'Michigan','MN'=>'Minnesota','MS'=>'Mississippi','MO'=>'Missouri','MT'=>'Montana','NE'=>'Nebraska','NV'=>'Nevada','NH'=>'New Hampshire','NJ'=>'New Jersey','NM'=>'New Mexico','NY'=>'New York','NC'=>'North Carolina','ND'=>'North Dakota','OH'=>'Ohio','OK'=>'Oklahoma','OR'=>'Oregon','PA'=>'Pennsylvania','RI'=>'Rhode Island','SC'=>'South Carolina','SD'=>'South Dakota','TN'=>'Tennessee','TX'=>'Texas','UT'=>'Utah','VT'=>'Vermont','VA'=>'Virginia','WA'=>'Washington','WV'=>'West Virginia','WI'=>'Wisconsin','WY'=>'Wyoming');
    $alt_st = $wpdb->get_row($wpdb->prepare("SELECT state, SUM(job_count) j FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND country = 'United States' AND state <> '' GROUP BY state ORDER BY j DESC LIMIT 1", $alt_ytd_from, $alt_ytd_to));
    if ($alt_st && $alt_st->state) $alt_soundbites[] = array('label' => 'By US state · ' . $alt_y,
        'text' => 'In the US, ' . (isset($alt_stmap[$alt_st->state]) ? $alt_stmap[$alt_st->state] : $alt_st->state) . ' has the most recorded layoffs in ' . $alt_y . ' (' . number_format((int) $alt_st->j) . ').',
        'link' => $alt_lk(array('years' => $alt_y, 'country' => 'United States', 'state' => $alt_st->state)), 'linklabel' => 'the US map');

    if (function_exists('alt_role_categories')) {
        $alt_best_role = null; $alt_best_j = 0; $alt_best_slug = '';
        foreach (alt_role_categories() as $alt_slug => $alt_rlabel) {
            $alt_rj = (int) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(job_count),0) FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND role_categories LIKE %s", $alt_ytd_from, $alt_ytd_to, '%,' . $alt_slug . ',%'));
            if ($alt_rj > $alt_best_j) { $alt_best_j = $alt_rj; $alt_best_role = $alt_rlabel; $alt_best_slug = $alt_slug; }
        }
        if ($alt_best_role && $alt_best_j > 0) $alt_soundbites[] = array('label' => 'Roles hit hardest · ' . $alt_y,
            'text' => $alt_best_role . ' is the job function hit hardest by layoffs in ' . $alt_y . ', across ' . number_format($alt_best_j) . ' cuts where the source named the team affected.',
            'link' => $alt_lk(array('years' => $alt_y, 'roles' => $alt_best_slug)), 'linklabel' => 'the roles chart');
    }

    $alt_big = $wpdb->get_row($wpdb->prepare("SELECT company, job_count FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND job_count > 0 ORDER BY job_count DESC, id DESC LIMIT 1", $alt_ytd_from, $alt_ytd_to));
    if ($alt_big && $alt_big->company) $alt_soundbites[] = array('label' => 'Largest single cut · ' . $alt_y,
        'text' => 'The single largest layoff of ' . $alt_y . ' so far is ' . $alt_big->company . ' (' . number_format((int) $alt_big->job_count) . ' jobs).',
        'link' => $alt_lk(array('years' => $alt_y, 'company' => $alt_big->company)), 'linklabel' => 'the event');

    $alt_mind = $wpdb->get_row($wpdb->prepare("SELECT industry, SUM(job_count) j FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND industry <> '' GROUP BY industry ORDER BY j DESC LIMIT 1", $alt_m_from, $alt_m_to));
    $alt_mbig = $wpdb->get_row($wpdb->prepare("SELECT company, job_count FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND job_count > 0 ORDER BY job_count DESC, id DESC LIMIT 1", $alt_m_from, $alt_m_to));
    if ($alt_mind && $alt_mind->industry && $alt_mbig && $alt_mbig->company) $alt_soundbites[] = array('label' => 'Latest month · ' . $alt_m_label,
        'text' => 'In ' . $alt_m_label . ', ' . $alt_mind->industry . ' led job cuts with ' . number_format((int) $alt_mind->j) . ', and the biggest single cut was ' . $alt_mbig->company . ' (' . number_format((int) $alt_mbig->job_count) . ').',
        'link' => esc_url(home_url('/ai-layoff-tracker/report/?period=' . gmdate('Y-m', $alt_lm))), 'linklabel' => 'the monthly report');

    set_transient('alt_press_soundbites', $alt_soundbites, HOUR_IN_SECONDS);
}
?>
<main class="alt-wrap alt-press-page">
  <p class="alt-eyebrow">AskTheRecruiter · press &amp; media kit</p>
  <h1>Press &amp; Media Kit</h1>
  <p class="alt-lead"><span class="alt-lead-text">Everything a reporter needs to cite the AI Layoff Tracker: the boilerplate, live quotable figures, how the data is verified, brand assets, and a direct contact. Every number on this page is reproducible from our public API.</span></p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a href="<?php echo esc_url(home_url('/contact/')); ?>">Contact us</a></p>

  <?php if ($alt_soundbites) : ?>
  <h2 id="alt-soundbites">Ready-to-use soundbites</h2>
  <p>Live, source-backed one-liners a reporter can drop straight into a story — each figure updates automatically from the tracker and links to the exact chart behind it. Copy, cite, done. (Every number is reproducible from our public API.)</p>
  <div class="alt-soundbites">
    <?php foreach ($alt_soundbites as $alt_sb) : ?>
    <figure class="alt-soundbite">
      <span class="alt-sb-label"><?php echo esc_html($alt_sb['label']); ?></span>
      <blockquote class="alt-sb-text">“<?php echo esc_html($alt_sb['text']); ?>”</blockquote>
      <figcaption class="alt-sb-actions">
        <button type="button" class="alt-btn alt-btn-sm alt-sb-copy">Copy</button>
        <a class="alt-sb-link" href="<?php echo $alt_sb['link']; ?>">📊 See <?php echo esc_html($alt_sb['linklabel']); ?> &rarr;</a>
      </figcaption>
    </figure>
    <?php endforeach; ?>
  </div>
  <p class="alt-muted">Attribution: “According to the AI Layoff Tracker by AskTheRecruiter.com.” Figures shown are the current live values and change as new sources are verified.</p>
  <?php endif; ?>

  <h2>Boilerplate</h2>
  <p><b>AskTheRecruiter</b> is the open, evidence-based intelligence platform helping workers understand the changing job market and improve their chances of getting hired. Its <b>AI Layoff Tracker</b> is a continuously updated, source-linked database of verified job cuts worldwide, purpose-built to flag which layoffs companies themselves attribute to AI or automation — every figure clickable back to a primary document.</p>
  <p class="alt-muted"><b>One-line version:</b> "The AI Layoff Tracker by AskTheRecruiter.com — a source-linked database of layoffs worldwide, flagging the ones companies blame on AI."</p>

  <h2>About the AI Layoff Tracker</h2>
  <p>The AI Layoff Tracker is a continuously updated database of verified job cuts worldwide, with a specific focus on flagging which layoffs companies attribute to AI or automation. Every entry links to a primary source: an SEC 8-K filing, a state WARN notice, or a named news report with a direct quote. Live editorial tracking began in January 2026; the database also carries historical records back to 2002 (Europe) and 2015 (US), built from official WARN filings, SEC disclosures and the EU's restructuring monitor, so year-over-year comparisons are possible.</p>

  <h2>Why it's worth citing</h2>
  <div class="alt-health-table-wrap"><table class="alt-sources-table alt-angles-table">
    <thead><tr><th>The angle</th><th>Why it's a story</th></tr></thead>
    <tbody>
      <tr><td><b>We break out the AI cuts</b></td><td>Most layoff trackers give you one lump-sum number and stop. We flag the cuts a company itself pinned on AI or automation, each with the employer's own quote on file, so "AI-attributed" becomes a figure a reporter can source instead of guess at.</td></tr>
      <tr><td><b>Every number is a receipt</b></td><td>Estimate-based trackers hand you a figure. We hand you the document behind it: an SEC filing, a WARN notice, or a named report. It's a floor you can prove, not a projection.</td></tr>
      <tr><td><b>We show where AI is cutting</b></td><td>A live world map, the teams hit hardest, and AI's rising share month over month: the geographic and functional detail a press release can't give a reporter.</td></tr>
      <tr><td><b>Nothing is hidden</b></td><td>A public corrections log, open methodology, the full source list, and an API anyone can reproduce. When we catch an error, we publish it.</td></tr>
    </tbody>
  </table></div>

  <h2>Press contact</h2>
  <p>For data requests, custom cuts of the dataset, corrections, or comment, use the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>. Press and reporter requests get priority, and every correction to a published figure is logged publicly on the tracker.</p>

  <h2>Using our data</h2>
  <p>Free for editorial, research, and educational use under CC BY 4.0. Please attribute to asktherecruiter.com and link back where possible.</p>
  <p><b>Suggested attribution:</b> "According to the AI Layoff Tracker by AskTheRecruiter.com..."</p>

  <h2>Key stats by year</h2>
  <p>Live figures from the same database the tracker serves. "AI-attributed" uses our strict standard: the company named AI as a primary or contributing cause, with a supporting quote on file. A separate broader measure (looser AI-linked attributions) is available in the <code>ai_broad_jobs</code> API field.</p>
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

  <h2>Access the full dataset</h2>
  <p>Filtered or full CSV and JSON exports are on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">tracker page</a>. The public REST API serves the same data live: <code>GET /blog/wp-json/layoffs/v1/query</code> and <code>GET /blog/wp-json/layoffs/v1/aggregate</code>. Company pages with stable, linkable URLs live under <code>/company-layoffs/</code> (for example, a reporter can cite one company's full source-linked history at a permanent address).</p>

  <h2>Brand assets</h2>
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
</main>
