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
?>
<main class="alt-wrap alt-press-page">
  <p class="alt-eyebrow">AskTheRecruiter · press &amp; media kit</p>
  <h1>Press &amp; Media Kit</h1>
  <p class="alt-lead"><span class="alt-lead-text">Everything a reporter needs to cite the AI Layoff Tracker: the boilerplate, live quotable figures, how the data is verified, brand assets, and a direct contact. Every number on this page is reproducible from our public API.</span></p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a href="mailto:info@asktherecruiter.com">info@asktherecruiter.com</a></p>

  <h2>Boilerplate</h2>
  <p><b>AskTheRecruiter</b> is the open, evidence-based intelligence platform helping workers understand the changing job market and improve their chances of getting hired. Its <b>AI Layoff Tracker</b> is a continuously updated, source-linked database of verified job cuts worldwide, purpose-built to flag which layoffs companies themselves attribute to AI or automation — every figure clickable back to a primary document.</p>
  <p class="alt-muted"><b>One-line version:</b> "The AI Layoff Tracker by AskTheRecruiter.com — a source-linked database of layoffs worldwide, flagging the ones companies blame on AI."</p>

  <h2>About the AI Layoff Tracker</h2>
  <p>The AI Layoff Tracker is a continuously updated database of verified job cuts worldwide, with a specific focus on flagging which layoffs companies attribute to AI or automation. Every entry links to a primary source: an SEC 8-K filing, a state WARN notice, or a named news report with a direct quote. Live editorial tracking began in January 2026; the database also carries historical records back to 2002 (Europe) and 2015 (US), built from official WARN filings, SEC disclosures and the EU's restructuring monitor, so year-over-year comparisons are possible.</p>

  <h2>What makes it different (story angles)</h2>
  <ul class="alt-method-list">
    <li><b>It beats the big surveys on the AI question.</b> Announcement surveys (Challenger) don't itemize AI. We do — from the employer's own words, with the quote on file — and our AI-attributed count actually <em>exceeds</em> theirs.</li>
    <li><b>Every number is a receipt.</b> Unlike estimate-based trackers, each figure links to a filing or named report. It's a documented floor, not a projection.</li>
    <li><b>It shows where AI is really cutting.</b> A live map, roles-most-impacted, and AI-share-over-time — geographic and functional breakdowns no press-release count offers.</li>
    <li><b>Radical transparency.</b> A public corrections log, open methodology, per-country source list, and reproducible API — the errors it caught are disclosed, not hidden.</li>
  </ul>

  <h2>Press contact</h2>
  <p>For data requests, custom cuts of the dataset, corrections, or comment, use the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a> or email <a href="mailto:info@asktherecruiter.com">info@asktherecruiter.com</a>. Corrections get priority review, and every correction to a published figure is logged publicly on the tracker.</p>

  <h2>Using our data</h2>
  <p>Free for editorial, research, and educational use under CC BY 4.0. Please attribute to asktherecruiter.com and link back where possible.</p>
  <p><b>Suggested attribution:</b> "According to the AI Layoff Tracker by AskTheRecruiter.com..."</p>

  <h2>Key stats by year</h2>
  <p>Live figures from the same database the tracker serves. "AI-attributed" uses our strict standard: the company named AI as a primary or contributing cause, with a supporting quote on file. A broader Challenger-style measure is charted on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-challenger-comparison">US comparison</a> section.</p>
  <div class="alt-health-table-wrap"><table>
    <thead><tr><th>Year</th><th>Verified events</th><th>Job cuts recorded</th><th>AI-attributed cuts (strict)</th></tr></thead>
    <tbody>
    <?php foreach ($alt_press_years as $alt_y) : ?>
      <tr><td><?php echo (int) $alt_y['y']; ?></td><td><?php echo number_format((int) $alt_y['entries']); ?></td><td><?php echo number_format((int) $alt_y['jobs']); ?></td><td><?php echo number_format((int) $alt_y['ai_jobs']); ?></td></tr>
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
  <p class="alt-muted">The wordmark and "atr" mark above may be used to credit the tracker in coverage. For high-resolution PNG/SVG logo files or a specific lockup, email <a href="mailto:info@asktherecruiter.com">info@asktherecruiter.com</a> and we'll send them same-day.</p>

  <h2>Press contact</h2>
  <p>For data requests, custom cuts, corrections, interviews or comment: <a href="mailto:info@asktherecruiter.com"><b>info@asktherecruiter.com</b></a> or the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>. Corrections and reporter requests get priority.</p>
</main>
