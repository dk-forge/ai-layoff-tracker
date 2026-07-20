<?php if (!defined('ABSPATH')) exit;
/**
 * One-pager report: a static, citable, print/social-ready summary for a single
 * reporting period (a month like 2026-06, or a full year like 2026). Rendered
 * SERVER-SIDE so the numbers are in the HTML — citable, indexable, and
 * screenshot-ready without waiting on JS. Period comes from ?p=YYYY-MM / ?p=YYYY
 * (default = latest COMPLETE month, so a reporter never lands on an in-progress
 * total). This is the "compete with Challenger" flagship: one dominant number,
 * a tight supporting hierarchy, and a fixed methodology/citation footer.
 *
 * v1 renders live from the fast table (a complete past month is already stable);
 * the frozen-snapshot + PDF + social-PNG generation is the next phase.
 */
global $wpdb; $alt_t = alt_db_table();

/* ---- period parsing ---------------------------------------------------- */
$alt_MONTHS = array(1=>'January','February','March','April','May','June','July','August','September','October','November','December');
// NB: 'p' is WordPress's reserved post-ID query var (triggers a canonical
// redirect), so the period param is 'period'.
$alt_p = isset($_GET['period']) ? preg_replace('/[^0-9\-]/', '', (string) $_GET['period']) : '';
$alt_is_year = false; $alt_y = 0; $alt_mo = 0;

if (preg_match('/^(\d{4})-(\d{1,2})$/', $alt_p, $mm)) {
    $alt_y = (int) $mm[1]; $alt_mo = max(1, min(12, (int) $mm[2]));
} elseif (preg_match('/^(\d{4})$/', $alt_p, $mm)) {
    $alt_is_year = true; $alt_y = (int) $mm[1];
} else {
    // default: latest COMPLETE month (first of this month minus a day)
    $alt_last = strtotime(gmdate('Y-m-01') . ' -1 day');
    $alt_y = (int) gmdate('Y', $alt_last); $alt_mo = (int) gmdate('n', $alt_last);
}
if ($alt_y < 2015 || $alt_y > (int) gmdate('Y') + 1) { $alt_y = (int) gmdate('Y'); }

if ($alt_is_year) {
    $alt_from = sprintf('%04d-01-01', $alt_y); $alt_to = sprintf('%04d-12-31', $alt_y);
    $alt_label = (string) $alt_y;
    $alt_pfrom = sprintf('%04d-01-01', $alt_y - 1); $alt_pto = sprintf('%04d-12-31', $alt_y - 1);
    $alt_plabel = (string) ($alt_y - 1); $alt_pnoun = 'prior year';
    $alt_slug = (string) $alt_y;
} else {
    $alt_from = sprintf('%04d-%02d-01', $alt_y, $alt_mo);
    $alt_to = gmdate('Y-m-t', strtotime($alt_from));
    $alt_label = $alt_MONTHS[$alt_mo] . ' ' . $alt_y;
    $alt_pt = strtotime($alt_from . ' -1 month');
    $alt_pfrom = gmdate('Y-m-01', $alt_pt); $alt_pto = gmdate('Y-m-t', $alt_pt);
    $alt_plabel = $alt_MONTHS[(int) gmdate('n', $alt_pt)] . ' ' . gmdate('Y', $alt_pt); $alt_pnoun = 'prior month';
    $alt_slug = sprintf('%04d-%02d', $alt_y, $alt_mo);
}

/* ---- period stats (verified = announced=0; AI = strict ai_explicit) ----- */
if (!function_exists('alt_report_period_stats')) {
function alt_report_period_stats($from, $to, $us_only = false) {
    global $wpdb; $t = alt_db_table();
    $geo = $us_only ? " AND country = 'United States'" : '';
    return $wpdb->get_row($wpdb->prepare(
        "SELECT COUNT(*) events,
                COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) verified_jobs,
                SUM(CASE WHEN announced=0 THEN 1 ELSE 0 END) verified_events,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs,
                COALESCE(SUM(job_count),0) all_jobs,
                COUNT(DISTINCT NULLIF(country,'')) countries
         FROM $t WHERE layoff_date BETWEEN %s AND %s$geo", $from, $to), ARRAY_A);
}
} // end function_exists guard

// Scope: World (default — worldwide coverage is the differentiator) or US-only.
$alt_us = isset($_GET['scope']) && $_GET['scope'] === 'us';
$alt_geo = $alt_us ? " AND country = 'United States'" : '';

$alt_cur = alt_report_period_stats($alt_from, $alt_to, $alt_us);
$alt_prev = alt_report_period_stats($alt_pfrom, $alt_pto, $alt_us);
$alt_v = (int) ($alt_cur['verified_jobs'] ?? 0);
$alt_pv = (int) ($alt_prev['verified_jobs'] ?? 0);
$alt_ai = (int) ($alt_cur['ai_jobs'] ?? 0);
$alt_delta = $alt_pv > 0 ? round(100 * ($alt_v - $alt_pv) / $alt_pv) : null;
$alt_ai_pct = $alt_v > 0 ? round(100 * $alt_ai / max(1, (int) $alt_cur['all_jobs'])) : 0;

// The Challenger box is ALWAYS US-vs-US for the SAME period, no matter what the
// headline scope is — Challenger has no global figure, so mixing scopes (world
// headline vs US announced) would be a data-integrity bug. This is the US
// verified total for the exact same month/year the box will cite.
$alt_us_stats = $alt_us ? $alt_cur : alt_report_period_stats($alt_from, $alt_to, true);
$alt_us_verified = (int) ($alt_us_stats['verified_jobs'] ?? 0);

$alt_largest = $wpdb->get_results($wpdb->prepare(
    "SELECT company, job_count, layoff_date, country, state, ai_explicit
     FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND job_count > 0$alt_geo
     ORDER BY job_count DESC, id DESC LIMIT 5", $alt_from, $alt_to), ARRAY_A) ?: array();
$alt_inds = $wpdb->get_results($wpdb->prepare(
    "SELECT industry, COALESCE(SUM(job_count),0) j FROM $alt_t
     WHERE layoff_date BETWEEN %s AND %s AND industry <> ''$alt_geo
     GROUP BY industry ORDER BY j DESC LIMIT 5", $alt_from, $alt_to), ARRAY_A) ?: array();
$alt_ind_max = 0; foreach ($alt_inds as $i) { $alt_ind_max = max($alt_ind_max, (int) $i['j']); }

/* ---- Challenger reconciliation for the same period (if on file) --------- */
$alt_ch = null;
if (!$alt_is_year) {
    $alt_bench = get_option('alt_challenger_benchmarks');
    if (is_array($alt_bench)) foreach ($alt_bench as $b) {
        $ref = (string) ($b['reference_month'] ?? '');
        if ($ref === $alt_slug && isset($b['challenger_total_jobs_month'])) { $alt_ch = (int) $b['challenger_total_jobs_month']; break; }
    }
}

/* ---- tab periods ------------------------------------------------------- */
$alt_report_url = home_url('/ai-layoff-tracker/report/');
$alt_years = range((int) gmdate('Y'), 2023);
$alt_view_year = $alt_y;
// Tab/scope link builder — preserves the current scope (World/US) across tabs,
// and lets the scope toggle keep the current period.
$alt_url = function ($period, $scope = null) use ($alt_report_url, $alt_us) {
    $args = array('period' => (string) $period);
    $s = $scope !== null ? $scope : ($alt_us ? 'us' : 'world');
    if ($s === 'us') $args['scope'] = 'us';
    return esc_url(add_query_arg($args, $alt_report_url));
};
?>
<main class="alt-wrap alt-report-page">
  <nav class="alt-report-tabs" aria-label="Report period">
    <div class="alt-report-tabrow">
      <span class="alt-report-tablabel">Scope</span>
      <a class="alt-report-tab<?php echo (!$alt_us ? ' on' : ''); ?>" href="<?php echo $alt_url($alt_slug, 'world'); ?>">🌐 World</a>
      <a class="alt-report-tab<?php echo ($alt_us ? ' on' : ''); ?>" href="<?php echo $alt_url($alt_slug, 'us'); ?>">🇺🇸 US only</a>
    </div>
    <div class="alt-report-tabrow">
      <span class="alt-report-tablabel">Year</span>
      <?php foreach ($alt_years as $yy) : ?>
        <a class="alt-report-tab<?php echo ($yy === $alt_view_year ? ' on' : ''); ?>" href="<?php echo $alt_url($yy); ?>"><?php echo $yy; ?></a>
      <?php endforeach; ?>
    </div>
    <div class="alt-report-tabrow">
      <span class="alt-report-tablabel"><?php echo $alt_view_year; ?></span>
      <?php for ($mi = 1; $mi <= 12; $mi++) :
          if ($alt_view_year === (int) gmdate('Y') && $mi > (int) gmdate('n')) break;
          $on = (!$alt_is_year && $mi === $alt_mo); ?>
        <a class="alt-report-tab<?php echo ($on ? ' on' : ''); ?>" href="<?php echo $alt_url(sprintf('%04d-%02d', $alt_view_year, $mi)); ?>"><?php echo substr($alt_MONTHS[$mi], 0, 3); ?></a>
      <?php endfor; ?>
      <a class="alt-report-tab<?php echo ($alt_is_year ? ' on' : ''); ?>" href="<?php echo $alt_url($alt_view_year); ?>">Full year</a>
    </div>
  </nav>

  <article class="alt-onepager">
    <header class="alt-op-masthead">
      <span class="alt-op-brand"><span class="alt-brand-mark">atr</span> AI Layoff Tracker</span>
      <span class="alt-op-period"><?php echo esc_html($alt_label); ?> report · <?php echo $alt_us ? '🇺🇸 US only' : '🌐 Worldwide'; ?></span>
      <span class="alt-op-asof">Data as of <?php echo esc_html(gmdate('M j, Y')); ?> · AskTheRecruiter.com</span>
    </header>

    <div class="alt-op-headline">
      <div class="alt-op-big"><?php echo number_format($alt_v); ?></div>
      <div class="alt-op-biglabel"><?php echo $alt_us ? 'US ' : 'worldwide '; ?>verified job cuts in <?php echo esc_html($alt_label); ?>
        <?php if ($alt_delta !== null) : ?>
          <span class="alt-op-delta <?php echo ($alt_delta >= 0 ? 'up' : 'down'); ?>"><?php echo ($alt_delta >= 0 ? '▲' : '▼') . ' ' . abs($alt_delta) . '%'; ?> vs <?php echo esc_html($alt_plabel); ?></span>
        <?php endif; ?>
      </div>
      <div class="alt-op-sub">🤖 <b><?php echo number_format($alt_ai); ?></b> explicitly blamed on AI by the employer (<?php echo $alt_ai_pct; ?>% of cuts) · <?php echo number_format((int) ($alt_cur['verified_events'] ?? 0)); ?> verified layoffs<?php echo $alt_us ? '' : ', ' . number_format((int) ($alt_cur['countries'] ?? 0)) . ' countries'; ?></div>
    </div>

    <?php
    // Data-integrity QA: Challenger is US-only, so this box is ALWAYS US-vs-US
    // for the SAME period — $alt_us_verified is the US verified total for the
    // exact month the Challenger figure ($alt_ch, keyed on $alt_slug) covers.
    // We never compare Challenger against the worldwide headline.
    if ($alt_ch !== null) : ?>
    <p class="alt-op-challenger<?php echo $alt_us ? '' : ' alt-op-challenger-aside'; ?>">
      <b>US vs Challenger<?php echo $alt_us ? '' : ' <span class="alt-op-usonly">(US only — the headline above is worldwide)</span>'; ?>:</b>
      <b><?php echo number_format($alt_us_verified); ?></b> US verified cuts vs Challenger's <b><?php echo number_format($alt_ch); ?></b> announced (US) for <?php echo esc_html($alt_label); ?>.
      Ours is a <em>verified</em> count (every figure links to a filing or named report), so it runs below their announcement estimate by design — <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-challenger-comparison">why they differ</a>.</p>
    <?php endif; ?>

    <div class="alt-op-grid">
      <section class="alt-op-block">
        <h3>Biggest single cuts</h3>
        <table class="alt-op-table"><tbody>
        <?php foreach ($alt_largest as $r) :
            $loc = alt_short_location($r['state'], $r['country']); ?>
          <tr><td class="alt-op-co"><?php echo esc_html($r['company']); ?><?php echo $loc ? ' <span class="alt-muted">· ' . esc_html($loc) . '</span>' : ''; ?><?php echo !empty($r['ai_explicit']) ? ' 🤖' : ''; ?></td>
              <td class="alt-op-num"><?php echo number_format((int) $r['job_count']); ?></td></tr>
        <?php endforeach; ?>
        <?php if (!$alt_largest) : ?><tr><td colspan="2" class="alt-muted">No cuts recorded for this period.</td></tr><?php endif; ?>
        </tbody></table>
      </section>

      <section class="alt-op-block">
        <h3>Top industries</h3>
        <div class="alt-op-bars">
        <?php foreach ($alt_inds as $i) : $w = $alt_ind_max > 0 ? max(4, round(100 * (int) $i['j'] / $alt_ind_max)) : 0; ?>
          <div class="alt-op-bar"><span class="alt-op-barname"><?php echo esc_html($i['industry']); ?></span>
            <span class="alt-op-bartrack"><span class="alt-op-barfill" style="width:<?php echo $w; ?>%"></span></span>
            <span class="alt-op-barval"><?php echo number_format((int) $i['j']); ?></span></div>
        <?php endforeach; ?>
        <?php if (!$alt_inds) : ?><p class="alt-muted">No industry-tagged cuts for this period.</p><?php endif; ?>
        </div>
      </section>
    </div>

    <footer class="alt-op-footer">
      <p><b>Methodology:</b> Verified cuts have a primary source behind each figure — an SEC filing, a state WARN notice, or a named news report with a quote. AI attribution requires the employer's own words. Machine-extracted numbers are double-checked and every correction is <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-corrections">disclosed openly</a>.</p>
      <p><b>Cite as:</b> "AI Layoff Tracker, AskTheRecruiter.com — <?php echo esc_html($alt_label); ?> (accessed <?php echo esc_html(gmdate('M j, Y')); ?>)." · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">Live tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Sources</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press kit</a></p>
    </footer>
  </article>
</main>
