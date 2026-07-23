<?php if (!defined('ABSPATH')) exit;
/**
 * One-pager report: a static, citable, print/social-ready summary for a single
 * reporting period. Rendered SERVER-SIDE so the numbers are in the HTML , 
 * citable, indexable, screenshot-ready without waiting on JS.
 *
 * Periods (all via ?period=, since 'p' is WP's reserved post-ID var):
 *   ?period=YYYY-MM     a month   (default = latest COMPLETE month)
 *   ?period=YYYY        a full year → the "Year in Review" wrap-up
 *   ?period=YYYY-Www    an ISO week → the "Weekly Pulse"
 *   ?view=archive       the index of every available report
 * Scope: ?scope=us (default worldwide, our differentiator).
 */
global $wpdb; $alt_t = alt_db_table();

$alt_MONTHS = array(1=>'January','February','March','April','May','June','July','August','September','October','November','December');
$alt_report_url = home_url('/ai-layoff-tracker/report/');

/* ---- URL builder (shared by every mode) -------------------------------- */
$alt_us = isset($_GET['scope']) && $_GET['scope'] === 'us';
$alt_url = function ($period, $scope = null) use ($alt_report_url, $alt_us) {
    $args = array('period' => (string) $period);
    $s = $scope !== null ? $scope : ($alt_us ? 'us' : 'world');
    if ($s === 'us') $args['scope'] = 'us';
    return esc_url(add_query_arg($args, $alt_report_url));
};
$alt_arch_url = function () use ($alt_report_url, $alt_us) {
    $args = array('view' => 'archive');
    if ($alt_us) $args['scope'] = 'us';
    return esc_url(add_query_arg($args, $alt_report_url));
};

/* ===== ARCHIVE / INDEX MODE ============================================== */
if (isset($_GET['view']) && $_GET['view'] === 'archive') :
    $alt_now_y = (int) gmdate('Y'); $alt_now_m = (int) gmdate('n');
    // ISO week label for the "this week" shortcut
    $alt_wk = new DateTime('now', new DateTimeZone('UTC'));
    $alt_wk_slug = $alt_wk->format('o-\WW');
    ?>
    <main class="alt-wrap alt-report-page">
  <?php if (function_exists("alt_dataset_jsonld") && !defined("ALT_REPORT_LD_DONE")) { define("ALT_REPORT_LD_DONE", 1); alt_output_jsonld(array(alt_dataset_jsonld())); } ?>
      <nav class="alt-report-tabs" aria-label="Report views">
        <div class="alt-report-tabrow">
          <span class="alt-report-tablabel">Scope</span>
          <a class="alt-report-tab<?php echo (!$alt_us ? ' on' : ''); ?>" href="<?php echo esc_url(add_query_arg(array('view'=>'archive'), $alt_report_url)); ?>">🌐 World</a>
          <a class="alt-report-tab<?php echo ($alt_us ? ' on' : ''); ?>" href="<?php echo esc_url(add_query_arg(array('view'=>'archive','scope'=>'us'), $alt_report_url)); ?>">🇺🇸 US only</a>
        </div>
      </nav>
      <article class="alt-onepager alt-report-archive">
        <header class="alt-op-masthead">
          <span class="alt-op-brand"><span class="alt-brand-mark">atr</span> AskTheRecruiter.com</span>
          <span class="alt-op-period">Job Cuts Reports · full archive · <?php echo $alt_us ? '🇺🇸 US only' : '🌐 Worldwide'; ?></span>
          <span class="alt-op-asof">Every month, quarter and year, each a standalone, citable page.</span>
        </header>
        <p class="alt-arch-intro">Pick any period below. Every report renders live from the same verified database and carries its own methodology and citation line. Start with the <a href="<?php echo $alt_url($alt_wk_slug); ?>">latest weekly pulse</a>.</p>
        <div class="alt-arch-grid">
        <?php for ($yy = $alt_now_y; $yy >= 2023; $yy--) :
            $m_hi = ($yy === $alt_now_y) ? $alt_now_m : 12; ?>
          <section class="alt-arch-col">
            <h3><a href="<?php echo $alt_url($yy); ?>"><?php echo $yy; ?> <span class="alt-arch-year-tag">Year in review →</span></a></h3>
            <ul class="alt-arch-months">
            <?php for ($mi = $m_hi; $mi >= 1; $mi--) : ?>
              <li><a href="<?php echo $alt_url(sprintf('%04d-%02d', $yy, $mi)); ?>"><?php echo esc_html($alt_MONTHS[$mi]); ?></a></li>
            <?php endfor; ?>
            </ul>
          </section>
        <?php endfor; ?>
        </div>
        <footer class="alt-op-footer">
          <p><b>Cite as:</b> "AskTheRecruiter.com Job Cuts Report, [period]." · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">Live tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Sources</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press kit</a></p>
        </footer>
      </article>
    </main>
    <?php
    return; // archive mode is self-contained
endif;

/* ===== SINGLE-PERIOD MODE =============================================== */
// Allow letters so ISO-week 'W' survives sanitization.
$alt_p = isset($_GET['period']) ? preg_replace('/[^0-9A-Za-z\-]/', '', (string) $_GET['period']) : '';
$alt_is_year = false; $alt_is_week = false; $alt_is_quarter = false; $alt_y = 0; $alt_mo = 0; $alt_wknum = 0; $alt_q = 0;

if (preg_match('/^(\d{4})-W(\d{1,2})$/i', $alt_p, $mm)) {
    $alt_is_week = true; $alt_y = (int) $mm[1]; $alt_wknum = max(1, min(53, (int) $mm[2]));
} elseif (preg_match('/^(\d{4})-Q([1-4])$/i', $alt_p, $mm)) {
    $alt_is_quarter = true; $alt_y = (int) $mm[1]; $alt_q = (int) $mm[2];
} elseif (preg_match('/^(\d{4})-(\d{1,2})$/', $alt_p, $mm)) {
    $alt_y = (int) $mm[1]; $alt_mo = max(1, min(12, (int) $mm[2]));
} elseif (preg_match('/^(\d{4})$/', $alt_p, $mm)) {
    $alt_is_year = true; $alt_y = (int) $mm[1];
} else {
    $alt_last = strtotime(gmdate('Y-m-01') . ' -1 day');
    $alt_y = (int) gmdate('Y', $alt_last); $alt_mo = (int) gmdate('n', $alt_last);
}
if ($alt_y < 2015 || $alt_y > (int) gmdate('Y') + 1) { $alt_y = (int) gmdate('Y'); }

if ($alt_is_week) {
    // ISO week → Monday..Sunday. setISODate handles year boundaries + overflow.
    $wd = new DateTime('now', new DateTimeZone('UTC')); $wd->setISODate($alt_y, $alt_wknum);
    $alt_from = $wd->format('Y-m-d');
    $we = clone $wd; $we->modify('+6 days'); $alt_to = $we->format('Y-m-d');
    $alt_label = 'Week of ' . $wd->format('M j, Y');
    $pw = clone $wd; $pw->modify('-7 days');
    $alt_pfrom = $pw->format('Y-m-d'); $pe = clone $pw; $pe->modify('+6 days'); $alt_pto = $pe->format('Y-m-d');
    $alt_plabel = 'week of ' . $pw->format('M j'); $alt_pnoun = 'prior week';
    $alt_slug = $wd->format('o-\WW');           // canonical ISO slug (week-year aware)
    $alt_prev_slug = $pw->format('o-\WW');
    $nw = clone $wd; $nw->modify('+7 days'); $alt_next_slug = $nw->format('o-\WW');
    $alt_kind = 'Weekly Pulse';
} elseif ($alt_is_quarter) {
    $alt_q_m = ($alt_q - 1) * 3 + 1;            // first month of the quarter
    $alt_from = sprintf('%04d-%02d-01', $alt_y, $alt_q_m);
    $alt_to = gmdate('Y-m-t', strtotime(sprintf('%04d-%02d-01', $alt_y, $alt_q_m + 2)));
    $alt_label = 'Q' . $alt_q . ' ' . $alt_y;
    $pq = $alt_q - 1; $pqy = $alt_y; if ($pq < 1) { $pq = 4; $pqy--; }
    $pqm = ($pq - 1) * 3 + 1;
    $alt_pfrom = sprintf('%04d-%02d-01', $pqy, $pqm);
    $alt_pto = gmdate('Y-m-t', strtotime(sprintf('%04d-%02d-01', $pqy, $pqm + 2)));
    $alt_plabel = 'Q' . $pq . ' ' . $pqy; $alt_pnoun = 'prior quarter';
    $alt_slug = sprintf('%04d-Q%d', $alt_y, $alt_q);
    $alt_prev_slug = sprintf('%04d-Q%d', $pqy, $pq);
    $nq = $alt_q + 1; $nqy = $alt_y; if ($nq > 4) { $nq = 1; $nqy++; }
    $alt_next_slug = sprintf('%04d-Q%d', $nqy, $nq);
    $alt_kind = 'Quarterly';
} elseif ($alt_is_year) {
    $alt_from = sprintf('%04d-01-01', $alt_y); $alt_to = sprintf('%04d-12-31', $alt_y);
    $alt_label = (string) $alt_y;
    $alt_pfrom = sprintf('%04d-01-01', $alt_y - 1); $alt_pto = sprintf('%04d-12-31', $alt_y - 1);
    $alt_plabel = (string) ($alt_y - 1); $alt_pnoun = 'prior year';
    $alt_slug = (string) $alt_y;
    $alt_prev_slug = (string) ($alt_y - 1); $alt_next_slug = (string) ($alt_y + 1);
    $alt_kind = 'Year in Review';
} else {
    $alt_from = sprintf('%04d-%02d-01', $alt_y, $alt_mo);
    $alt_to = gmdate('Y-m-t', strtotime($alt_from));
    $alt_label = $alt_MONTHS[$alt_mo] . ' ' . $alt_y;
    $alt_pt = strtotime($alt_from . ' -1 month');
    $alt_pfrom = gmdate('Y-m-01', $alt_pt); $alt_pto = gmdate('Y-m-t', $alt_pt);
    $alt_plabel = $alt_MONTHS[(int) gmdate('n', $alt_pt)] . ' ' . gmdate('Y', $alt_pt); $alt_pnoun = 'prior month';
    $alt_slug = sprintf('%04d-%02d', $alt_y, $alt_mo);
    $alt_prev_slug = gmdate('Y-m', $alt_pt);
    $nt = strtotime($alt_from . ' +1 month'); $alt_next_slug = gmdate('Y-m', $nt);
    $alt_kind = 'Monthly';
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
                COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) ai_verified_jobs,
                COALESCE(SUM(job_count),0) all_jobs,
                COUNT(DISTINCT NULLIF(country,'')) countries
         FROM $t WHERE layoff_date BETWEEN %s AND %s$geo", $from, $to), ARRAY_A);
}
} // end function_exists guard

$alt_geo = $alt_us ? " AND country = 'United States'" : '';
// Every figure on this report links to the tracker filtered to the SAME period
// (and dimension), so a reader can go from any number straight to the rows and
// sources behind it - the report is a summary, the link is the receipt.
$alt_rlink = function ($extra = array()) use ($alt_from, $alt_to, $alt_us) {
    $args = array('from' => $alt_from, 'to' => $alt_to);
    if ($alt_us) { $args['country'] = 'United States'; }
    return esc_url(add_query_arg(array_merge($args, $extra), home_url('/ai-layoff-tracker/')));
};
$alt_cur = alt_report_period_stats($alt_from, $alt_to, $alt_us);
$alt_prev = alt_report_period_stats($alt_pfrom, $alt_pto, $alt_us);
$alt_v = (int) ($alt_cur['verified_jobs'] ?? 0);
$alt_pv = (int) ($alt_prev['verified_jobs'] ?? 0);
$alt_ai = (int) ($alt_cur['ai_jobs'] ?? 0);
$alt_ai_v = (int) ($alt_cur['ai_verified_jobs'] ?? 0);   // AI ∩ verified (clean subset)
$alt_delta = $alt_pv > 0 ? round(100 * ($alt_v - $alt_pv) / $alt_pv) : null;
// % of the headline (verified) number that the employer blamed on AI.
$alt_ai_pct = $alt_v > 0 ? round(100 * $alt_ai_v / max(1, $alt_v)) : 0;

$alt_largest = $wpdb->get_results($wpdb->prepare(
    "SELECT company, job_count, layoff_date, country, state, ai_explicit
     FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND job_count > 0$alt_geo
     ORDER BY job_count DESC, id DESC LIMIT 5", $alt_from, $alt_to), ARRAY_A) ?: array();
// AI attributions for this period, WITH the employer's exact words. This is the
// receipt behind the "blamed on AI" number: a reader sees the actual sentence,
// the tier, and a link to the source. Verified tier, quote present, biggest first.
$alt_ai_quotes = $wpdb->get_results($wpdb->prepare(
    "SELECT company, job_count, layoff_date, country, state, ai_language, ai_causation, source_url
     FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND ai_explicit = 1 AND announced = 0
       AND ai_language <> ''$alt_geo
     ORDER BY job_count DESC, id DESC LIMIT 40", $alt_from, $alt_to), ARRAY_A) ?: array();
$alt_inds = $wpdb->get_results($wpdb->prepare(
    "SELECT industry, COALESCE(SUM(job_count),0) j FROM $alt_t
     WHERE layoff_date BETWEEN %s AND %s AND industry <> ''$alt_geo
     GROUP BY industry ORDER BY j DESC LIMIT 5", $alt_from, $alt_to), ARRAY_A) ?: array();
$alt_ind_max = 0; foreach ($alt_inds as $i) { $alt_ind_max = max($alt_ind_max, (int) $i['j']); }

/* ---- Year in Review extras: top companies (aggregated) + month-by-month - */
$alt_top_co = array(); $alt_months_series = array(); $alt_mseries_max = 0;
if ($alt_is_year) {
    $alt_top_co = $wpdb->get_results($wpdb->prepare(
        "SELECT company, COALESCE(SUM(job_count),0) j, COUNT(*) n,
                MAX(ai_explicit) any_ai
         FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND company <> ''$alt_geo
         GROUP BY company ORDER BY j DESC LIMIT 8", $alt_from, $alt_to), ARRAY_A) ?: array();
    $alt_top_co_max = 0; foreach ($alt_top_co as $c) { $alt_top_co_max = max($alt_top_co_max, (int) $c['j']); }
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT MONTH(layoff_date) m,
                COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai
         FROM $alt_t WHERE layoff_date BETWEEN %s AND %s$alt_geo
         GROUP BY MONTH(layoff_date)", $alt_from, $alt_to), ARRAY_A) ?: array();
    $by_m = array(); foreach ($rows as $r) { $by_m[(int) $r['m']] = $r; }
    $m_hi = ($alt_y === (int) gmdate('Y')) ? (int) gmdate('n') : 12;
    for ($mi = 1; $mi <= $m_hi; $mi++) {
        $v = (int) ($by_m[$mi]['v'] ?? 0); $ai = (int) ($by_m[$mi]['ai'] ?? 0);
        $alt_months_series[] = array('m' => $mi, 'v' => $v, 'ai' => $ai);
        $alt_mseries_max = max($alt_mseries_max, $v);
    }
}

/* ---- tab periods ------------------------------------------------------- */
$alt_years = range((int) gmdate('Y'), 2023);
$alt_view_year = $alt_y;
// This-week slug for the weekly tab.
$alt_thisweek = (new DateTime('now', new DateTimeZone('UTC')))->format('o-\WW');
// Reports are stamped in New York (Eastern) time, the newsroom-standard zone.
// Honest: show when the DATA last changed (last ingest), not the page-load time.
// Fall back to render time only if nothing has ever been written.
$alt_stamp = (function_exists('alt_data_last_updated_label') ? alt_data_last_updated_label() : '')
    ?: (new DateTime('now', new DateTimeZone('America/New_York')))->format('M j, Y · g:i A T');
?>
<main class="alt-wrap alt-report-page">
  <?php if (function_exists("alt_dataset_jsonld") && !defined("ALT_REPORT_LD_DONE")) { define("ALT_REPORT_LD_DONE", 1); alt_output_jsonld(array(alt_dataset_jsonld())); } ?>
  <nav class="alt-report-tabs" aria-label="Report period">
    <div class="alt-report-tabrow">
      <span class="alt-report-tablabel">View</span>
      <a class="alt-report-tab<?php echo ($alt_is_week ? ' on' : ''); ?>" href="<?php echo $alt_url($alt_thisweek); ?>">Weekly pulse</a>
      <a class="alt-report-tab" href="<?php echo $alt_arch_url(); ?>">🗓 All reports</a>
    </div>
    <div class="alt-report-tabrow">
      <span class="alt-report-tablabel">Scope</span>
      <a class="alt-report-tab<?php echo (!$alt_us ? ' on' : ''); ?>" href="<?php echo $alt_url($alt_slug, 'world'); ?>">🌐 World</a>
      <a class="alt-report-tab<?php echo ($alt_us ? ' on' : ''); ?>" href="<?php echo $alt_url($alt_slug, 'us'); ?>">🇺🇸 US only</a>
    </div>
    <div class="alt-report-tabrow">
      <span class="alt-report-tablabel">Year</span>
      <?php foreach ($alt_years as $yy) : ?>
        <a class="alt-report-tab<?php echo (($yy === $alt_view_year && $alt_is_year) ? ' on' : ''); ?>" href="<?php echo $alt_url($yy); ?>"><?php echo $yy; ?></a>
      <?php endforeach; ?>
    </div>
    <div class="alt-report-tabrow">
      <span class="alt-report-tablabel">Quarter</span>
      <?php for ($qi = 1; $qi <= 4; $qi++) :
          if ($alt_view_year === (int) gmdate('Y') && $qi > (int) ceil(gmdate('n') / 3)) break;
          $qon = ($alt_is_quarter && $qi === $alt_q); ?>
        <a class="alt-report-tab<?php echo ($qon ? ' on' : ''); ?>" href="<?php echo $alt_url(sprintf('%04d-Q%d', $alt_view_year, $qi)); ?>">Q<?php echo $qi; ?></a>
      <?php endfor; ?>
    </div>
    <div class="alt-report-tabrow">
      <span class="alt-report-tablabel"><?php echo $alt_view_year; ?></span>
      <?php for ($mi = 1; $mi <= 12; $mi++) :
          if ($alt_view_year === (int) gmdate('Y') && $mi > (int) gmdate('n')) break;
          $on = (!$alt_is_year && !$alt_is_week && !$alt_is_quarter && $mi === $alt_mo); ?>
        <a class="alt-report-tab<?php echo ($on ? ' on' : ''); ?>" href="<?php echo $alt_url(sprintf('%04d-%02d', $alt_view_year, $mi)); ?>"><?php echo substr($alt_MONTHS[$mi], 0, 3); ?></a>
      <?php endfor; ?>
      <a class="alt-report-tab<?php echo ($alt_is_year ? ' on' : ''); ?>" href="<?php echo $alt_url($alt_view_year); ?>">Full year</a>
    </div>
  </nav>

  <div class="alt-report-nav">
    <a class="alt-report-pn" href="<?php echo $alt_url($alt_prev_slug); ?>" rel="prev">← <?php echo esc_html(ucfirst($alt_pnoun)); ?></a>
    <div class="alt-report-exports" data-report-exports>
      <button type="button" class="alt-btn alt-report-print">⬇ PDF</button>
      <button type="button" class="alt-btn alt-report-png">🖼 PNG</button>
    </div>
    <a class="alt-report-pn alt-report-pn-next" href="<?php echo $alt_url($alt_next_slug); ?>" rel="next">Next →</a>
  </div>

  <article class="alt-onepager" id="alt-report-card" data-slug="<?php echo esc_attr($alt_slug); ?>">
    <header class="alt-op-masthead">
      <span class="alt-op-brand"><span class="alt-brand-mark">atr</span> AskTheRecruiter.com</span>
      <span class="alt-op-period"><?php echo esc_html($alt_kind); ?> Job Cuts Report · <?php echo esc_html($alt_label); ?> · <?php echo $alt_us ? '🇺🇸 US only' : '🌐 Worldwide'; ?></span>
      <span class="alt-op-asof">Data as of <?php echo esc_html($alt_stamp); ?> · AskTheRecruiter.com</span>
    </header>

    <div class="alt-op-headline">
      <div class="alt-op-twobox">
        <div class="alt-op-box alt-op-box-overall">
          <a class="alt-op-figlink" href="<?php echo $alt_rlink(); ?>" target="_blank" rel="noopener" title="See the rows behind this number"><div class="alt-op-big"><?php echo number_format($alt_v); ?></div></a>
          <div class="alt-op-boxlabel"><?php echo $alt_us ? 'US ' : 'Worldwide '; ?>verified job cuts<?php echo $alt_is_week ? ' this week' : ''; ?>
            <?php if ($alt_delta !== null) : ?>
              <span class="alt-op-delta <?php echo ($alt_delta >= 0 ? 'up' : 'down'); ?>"><?php echo ($alt_delta >= 0 ? '▲' : '▼') . ' ' . abs($alt_delta) . '%'; ?> vs <?php echo esc_html($alt_plabel); ?></span>
            <?php endif; ?>
          </div>
          <div class="alt-op-boxnote">The main number, every figure traces to a filing or named report.</div>
        </div>
        <div class="alt-op-box alt-op-box-ai">
          <a class="alt-op-figlink" href="<?php echo $alt_rlink(array('ai' => '1')); ?>" target="_blank" rel="noopener" title="See every AI-attributed cut this period"><div class="alt-op-big alt-op-big-ai"><?php echo number_format($alt_ai_v); ?></div></a>
          <div class="alt-op-boxlabel">🤖 blamed on AI by the employer
            <span class="alt-op-aipct"><?php echo $alt_ai_pct; ?>% of the total</span>
          </div>
          <div class="alt-op-boxnote">AI or automation named as a cause, in the company's own words.</div>
        </div>
      </div>
      <p class="alt-op-figs-note">Every figure below is a live link: click any number, company or industry to open the exact rows and sources behind it, filtered to this period.</p>
      <div class="alt-op-sub">Across <?php echo number_format((int) ($alt_cur['verified_events'] ?? 0)); ?> separate verified layoff events<?php echo $alt_us ? '' : ' in ' . number_format((int) ($alt_cur['countries'] ?? 0)) . ' countries'; ?><?php echo ($alt_ai > $alt_ai_v) ? ' · ' . number_format($alt_ai) . ' AI-attributed including announced plans' : ''; ?>.</div>
    </div>

    <?php if ($alt_ai_quotes) : ?>
    <section class="alt-op-block alt-op-aiwords">
      <h3>AI, in the employer's own words <span class="alt-op-aiwords-sub"><?php echo count($alt_ai_quotes); ?> attribution<?php echo count($alt_ai_quotes) === 1 ? '' : 's'; ?> this period, each with its source</span></h3>
      <p class="alt-op-aiwords-intro">This is the receipt behind the number above. Every cut we count as AI carries the company's own statement, quoted verbatim, and a link to where they said it. Nothing here is inferred.</p>
      <ul class="alt-op-quotes">
        <?php foreach ($alt_ai_quotes as $qq) :
            $tier = ($qq['ai_causation'] === 'primary_cause') ? 'AI named as the cause' : 'AI named among the causes';
            $loc = trim(($qq['state'] ? $qq['state'] . ' · ' : '') . ($qq['country'] ?: ''));
        ?>
        <li class="alt-op-quote">
          <div class="alt-op-quote-head">
            <b><?php echo esc_html($qq['company']); ?></b>
            <span class="alt-op-quote-meta"><?php echo number_format((int) $qq['job_count']); ?> jobs · <?php echo esc_html($qq['layoff_date']); ?><?php echo $loc ? ' · ' . esc_html($loc) : ''; ?></span>
            <span class="alt-op-quote-tier alt-op-tier-<?php echo $qq['ai_causation'] === 'primary_cause' ? 'primary' : 'contrib'; ?>"><?php echo esc_html($tier); ?></span>
          </div>
          <blockquote class="alt-op-quote-text">&ldquo;<?php echo esc_html(trim(rtrim(trim($qq['ai_language']), '. '), "\"'\xe2\x80\x9c\xe2\x80\x9d")); ?>&rdquo;</blockquote>
          <?php if ($qq['source_url']) : ?>
          <a class="alt-op-quote-src" href="<?php echo esc_url($qq['source_url']); ?>" target="_blank" rel="noopener">See the source &rarr;</a>
          <?php endif; ?>
        </li>
        <?php endforeach; ?>
      </ul>
      <p class="alt-op-aiwords-foot"><a href="<?php echo esc_url(add_query_arg(array('years' => substr($alt_from,0,4), 'ai' => '1'), home_url('/ai-layoff-tracker/'))); ?>" target="_blank" rel="noopener">Open every AI-attributed cut in the tracker, filtered &rarr;</a></p>
    </section>
    <?php endif; ?>

    <?php if ($alt_is_year && $alt_months_series) : ?>
    <section class="alt-op-block alt-op-yearbars">
      <h3>Month by month, verified cuts in <?php echo esc_html($alt_label); ?></h3>
      <div class="alt-op-bars">
      <?php foreach ($alt_months_series as $ms) :
          $w = $alt_mseries_max > 0 ? max(2, round(100 * $ms['v'] / $alt_mseries_max)) : 0;
          $aiw = $ms['v'] > 0 ? min(100, round(100 * $ms['ai'] / max(1, $ms['v']))) : 0; ?>
        <div class="alt-op-bar"><span class="alt-op-barname"><?php echo substr($alt_MONTHS[$ms['m']], 0, 3); ?></span>
          <span class="alt-op-bartrack"><span class="alt-op-barfill" style="width:<?php echo $w; ?>%"></span></span>
          <span class="alt-op-barval"><?php echo number_format($ms['v']); ?><?php echo $ms['ai'] > 0 ? ' <span class="alt-op-barai">🤖' . $aiw . '%</span>' : ''; ?></span></div>
      <?php endforeach; ?>
      </div>
    </section>
    <?php endif; ?>

    <div class="alt-op-grid">
      <section class="alt-op-block">
        <h3><?php echo $alt_is_year ? 'Biggest employers cut (full year)' : 'Biggest single cuts'; ?></h3>
        <?php if ($alt_is_year && $alt_top_co) : ?>
        <table class="alt-op-table"><tbody>
        <?php foreach ($alt_top_co as $c) : ?>
          <tr><td class="alt-op-co"><?php echo esc_html($c['company']); ?><?php echo ((int) $c['n'] > 1) ? ' <span class="alt-muted">· ' . (int) $c['n'] . ' events</span>' : ''; ?><?php echo !empty($c['any_ai']) ? ' 🤖' : ''; ?></td>
              <td class="alt-op-num"><?php echo number_format((int) $c['j']); ?></td></tr>
        <?php endforeach; ?>
        </tbody></table>
        <?php else : ?>
        <table class="alt-op-table"><tbody>
        <?php foreach ($alt_largest as $r) :
            $loc = alt_short_location($r['state'], $r['country']); ?>
          <tr><td class="alt-op-co"><a href="<?php echo $alt_rlink(array('company' => $r['company'])); ?>" target="_blank" rel="noopener"><?php echo esc_html($r['company']); ?></a><?php echo $loc ? ' <span class="alt-muted">· ' . esc_html($loc) . '</span>' : ''; ?><?php echo !empty($r['ai_explicit']) ? ' 🤖' : ''; ?></td>
              <td class="alt-op-num"><?php echo number_format((int) $r['job_count']); ?></td></tr>
        <?php endforeach; ?>
        <?php if (!$alt_largest) : ?><tr><td colspan="2" class="alt-muted">No cuts recorded for this period.</td></tr><?php endif; ?>
        </tbody></table>
        <?php endif; ?>
      </section>

      <section class="alt-op-block">
        <h3>Top industries</h3>
        <div class="alt-op-bars">
        <?php foreach ($alt_inds as $i) : $w = $alt_ind_max > 0 ? max(4, round(100 * (int) $i['j'] / $alt_ind_max)) : 0; ?>
          <a class="alt-op-bar alt-op-bar-link" href="<?php echo $alt_rlink(array('industry' => $i['industry'])); ?>" target="_blank" rel="noopener"><span class="alt-op-barname"><?php echo esc_html($i['industry']); ?></span>
            <span class="alt-op-bartrack"><span class="alt-op-barfill" style="width:<?php echo $w; ?>%"></span></span>
            <span class="alt-op-barval"><?php echo number_format((int) $i['j']); ?></span></a>
        <?php endforeach; ?>
        <?php if (!$alt_inds) : ?><p class="alt-muted">No industry-tagged cuts for this period.</p><?php endif; ?>
        </div>
      </section>
    </div>

    <footer class="alt-op-footer">
      <p><b>Methodology:</b> Verified cuts have a primary source behind each figure, an SEC filing, a state WARN notice, or a named news report with a quote. AI attribution requires the employer's own words. Machine-extracted numbers are double-checked and every correction is <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>#alt-corrections">disclosed openly</a>.</p>
      <p><b>Cite as:</b> "AskTheRecruiter.com <?php echo esc_html($alt_kind); ?> Job Cuts Report, <?php echo esc_html($alt_label); ?> (accessed <?php echo esc_html($alt_stamp); ?>)." · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">Live tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Sources</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press kit</a></p>
    </footer>
  </article>
</main>
