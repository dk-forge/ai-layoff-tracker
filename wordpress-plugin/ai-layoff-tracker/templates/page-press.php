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
  <p class="alt-eyebrow">AskTheRecruiter · press &amp; media</p>
  <h1>Press &amp; Media</h1>

  <h2>About the AI Layoff Tracker</h2>
  <p>The AI Layoff Tracker is a continuously updated database of verified job cuts worldwide, with a specific focus on flagging which layoffs companies attribute to AI or automation. Every entry links to a primary source: an SEC 8-K filing, a state WARN notice, or a named news report with a direct quote. Live editorial tracking began in January 2026; the database also carries historical records back to 2015, built from official WARN filings and SEC disclosures, so year-over-year comparisons are possible.</p>

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
</main>
