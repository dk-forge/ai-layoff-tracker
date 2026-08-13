<?php
if (!defined('ABSPATH')) exit;
$all_reports = get_option('alt_quarterly_reports');
$all_reports = is_array($all_reports) ? $all_reports : array();
krsort($all_reports);
if (!empty($report_id) && isset($all_reports[$report_id])) $report = $all_reports[$report_id];
else $report = !empty($all_reports) ? reset($all_reports) : null;
$live_revision = (int) get_option('alt_data_ver', 1);
$api_base = rest_url('layoffs/v1/');
// Conditional function declarations are evaluated only when execution reaches
// them. Define this renderer before the first table call so the report cannot
// partially render and then fatal on its first breakdown.
if (!function_exists('alt_quarterly_report_table')) {
function alt_quarterly_report_table($rows, $label) {
    if (!is_array($rows) || !$rows) { echo '<p class="alt-muted">No source-supported values for this snapshot.</p>'; return; }
    echo '<table class="alt-report-table"><thead><tr><th scope="col">' . esc_html($label) . '</th><th scope="col">Jobs</th><th scope="col">AI-attributed jobs</th></tr></thead><tbody>';
    foreach (array_slice($rows, 0, 8) as $row) {
        $name = (string) ($row[0] ?? ''); $jobs = (int) ($row[1] ?? 0); $ai = (int) ($row[2] ?? 0);
        echo '<tr><th scope="row">' . esc_html($name) . '</th><td>' . number_format_i18n($jobs) . '</td><td>' . number_format_i18n($ai) . '</td></tr>';
    }
    echo '</tbody></table>';
}
}
?>
<main class="alt-wrap alt-quarterly-report" id="alt-quarterly-report">
<?php if (!$report): ?>
  <header class="alt-report-hero"><p class="alt-eyebrow">AskTheRecruiter · original research</p><h1>State of Layoffs</h1><p>The first quarterly, query-backed report has not been published yet.</p></header>
  <p class="alt-report-note">When published, each report will preserve its own source-scoped data snapshot, coverage status and dataset revision. The live tracker remains available for current records.</p>
<?php else:
  $verified = $report['snapshot']['verified'] ?? array();
  $announced = $report['snapshot']['announced'] ?? array();
  $ai_primary = $report['snapshot']['ai_primary_verified_subset'] ?? array();
  $vt = $verified['totals'] ?? array(); $at = $announced['totals'] ?? array(); $ait = $ai_primary['totals'] ?? array();
  $period = $report['period'] ?? array(); $coverage = $report['coverage_at_publication'] ?? array();
  $degraded = $coverage['degraded_sources'] ?? array();
  $report_api = $api_base . 'reports/quarterly/' . rawurlencode($report['report_id']);
  $appendix_api = $report_api . '/appendix';
  $appendix_csv = admin_url('admin-post.php?action=alt_quarterly_appendix&format=csv&report_id=' . rawurlencode($report['report_id']));
  $appendix_json = admin_url('admin-post.php?action=alt_quarterly_appendix&format=json&report_id=' . rawurlencode($report['report_id']));
?>
  <header class="alt-report-hero">
    <p class="alt-eyebrow">AskTheRecruiter · query-backed research snapshot</p>
    <h1><?php echo esc_html($report['title']); ?></h1>
    <p>Entries dated <?php echo esc_html($period['from']); ?> to <?php echo esc_html($period['to']); ?>. Published <?php echo esc_html($report['generated_at']); ?> · dataset revision <?php echo (int) $report['dataset_revision']; ?>.</p>
  </header>
  <?php if ($live_revision !== (int) $report['dataset_revision']): ?>
    <p class="alt-report-alert"><b>Data revision notice:</b> the live tracker is now revision <?php echo $live_revision; ?>. This page preserves the original report snapshot; use the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">live tracker</a> for current records.</p>
  <?php endif; ?>
  <?php if (!empty($degraded)): ?>
    <p class="alt-report-alert"><b>Coverage notice:</b> <?php echo esc_html(implode(', ', $degraded)); ?> was degraded when this snapshot was generated. That is a visible coverage gap, not a zero result.</p>
  <?php endif; ?>
  <section aria-labelledby="alt-report-headline"><h2 id="alt-report-headline">Quarter at a glance</h2><div class="alt-report-metrics">
    <article><strong><?php echo number_format_i18n((int) ($vt['jobs'] ?? 0)); ?></strong><span>Verified job cuts</span><small><?php echo number_format_i18n((int) ($vt['entries'] ?? 0)); ?> source-linked entries</small></article>
    <article><strong><?php echo number_format_i18n((int) ($ait['ai_primary_jobs'] ?? 0)); ?></strong><span>AI-attributed cuts (employer's own words)</span><small><?php echo number_format_i18n((int) ($ait['ai_primary_entries'] ?? 0)); ?> source-confirmed entries</small></article>
    <article><strong><?php echo number_format_i18n((int) ($at['announced_jobs'] ?? 0)); ?></strong><span>Announcement-stage plans</span><small><?php echo number_format_i18n((int) ($at['announced_entries'] ?? 0)); ?> separate source-linked plans</small></article>
  </div></section>
  <p class="alt-report-note">Verified and announcement-stage figures are separate and must not be added together. The AI-attributed figure is a source-confirmed subset of verified entries, not an estimate of all AI-related cuts.</p>
  <section class="alt-report-grid" aria-label="Quarterly breakdowns">
    <div><h2>Largest verified industries</h2><?php alt_quarterly_report_table($verified['top_industries'] ?? array(), 'Industry'); ?></div>
    <div><h2>Largest verified job-location countries</h2><?php alt_quarterly_report_table($verified['top_countries'] ?? array(), 'Country'); ?></div>
    <div><h2>Reasons cited in verified entries</h2><?php alt_quarterly_report_table($verified['reasons'] ?? array(), 'Reason'); ?></div>
  </section>
  <section><h2>Coverage and revision record</h2>
    <p>This is a frozen, server-generated snapshot of the public aggregate queries recorded below. It is not a layoff census, forecast, causal analysis, or claim of national completeness.</p>
    <ul><li>Dataset revision at publication: <?php echo (int) $report['dataset_revision']; ?>.</li><li>Evidence integrity: <?php echo number_format_i18n((int) (($coverage['integrity']['source_reports'] ?? 0))); ?> retained source reports; <?php echo number_format_i18n((int) (($coverage['integrity']['source_report_hashes_remaining'] ?? 0))); ?> retained excerpts awaiting hash backfill.</li><li>Disclosed changes in the 30 days before publication: corrected <?php echo (int) (($coverage['last_30_days_disclosed_changes']['corrected'] ?? 0)); ?>, removed <?php echo (int) (($coverage['last_30_days_disclosed_changes']['removed'] ?? 0)); ?>, merged <?php echo (int) (($coverage['last_30_days_disclosed_changes']['merged'] ?? 0)); ?>.</li></ul>
    <p><a href="<?php echo esc_url($report_api); ?>">Machine-readable frozen report snapshot</a> · <a href="<?php echo esc_url($appendix_api); ?>">Readable JSON appendix</a> · <a href="<?php echo esc_url($appendix_csv); ?>">Download CSV appendix</a> · <a href="<?php echo esc_url($appendix_json); ?>">Download JSON appendix</a> · <a href="<?php echo esc_url($api_base . 'quality-status'); ?>">current quality status</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">live source-linked tracker</a></p>
  </section>
  <section><h2>Methods and limits</h2><p><?php echo esc_html($report['revision_notice']); ?></p><p>Country is affected-job location; it is not employer headquarters. Fields without source support remain blank. A listed source can be a government notice list rather than an individual notice URL, and the live tracker labels that distinction.</p></section>
<?php endif; ?>
</main>
