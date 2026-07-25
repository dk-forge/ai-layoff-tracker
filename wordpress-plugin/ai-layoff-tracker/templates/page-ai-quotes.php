<?php if (!defined('ABSPATH')) exit;
/**
 * "AI, in their own words", the quote wall.
 *
 * Every layoff we count as AI carries the employer's own statement in
 * ai_language. This page surfaces all of them as a filterable, server-rendered
 * wall (rendered in the HTML, so it is citable and indexable): company, jobs,
 * date, industry, the causation tier, the verbatim quote, and a source link.
 * It is the single most quotable asset the tracker owns for the AI angle.
 *
 * Filters via query params, all optional: years=YYYY, industry=Label,
 * tier=primary|contributing, country=Name, q=text.
 */
global $wpdb; $alt_t = alt_db_table();

$alt_year   = isset($_GET['years']) && preg_match('/^\d{4}$/', $_GET['years']) ? (int) $_GET['years'] : 0;
$alt_ind    = isset($_GET['industry']) ? sanitize_text_field(wp_unslash($_GET['industry'])) : '';
$alt_tier   = isset($_GET['tier']) ? sanitize_key($_GET['tier']) : '';
$alt_country = isset($_GET['country']) ? sanitize_text_field(wp_unslash($_GET['country'])) : '';
$alt_q      = isset($_GET['q']) ? sanitize_text_field(wp_unslash($_GET['q'])) : '';
// Sort: newest first is the default (press wants the latest attribution);
// company A-Z and largest-first are one click. Letter = alphabet-strip filter.
$alt_sort   = isset($_GET['sort']) && in_array($_GET['sort'], array('az', 'jobs'), true) ? $_GET['sort'] : 'recent';
$alt_letter = isset($_GET['letter']) && preg_match('/^[A-Z]$/', strtoupper((string) $_GET['letter']))
    ? strtoupper((string) $_GET['letter']) : '';

// Require a real quote (>=8 non-space chars), so a stray/empty ai_language never
// renders as bare "" on this page (the whole page's promise is a verbatim quote).
$where = array("ai_explicit = 1", "CHAR_LENGTH(TRIM(ai_language)) >= 8");
$params = array();
if ($alt_year)    { $where[] = "YEAR(layoff_date) = %d"; $params[] = $alt_year; }
if ($alt_ind)     { $where[] = "industry = %s"; $params[] = $alt_ind; }
if ($alt_country) { $where[] = "country = %s"; $params[] = $alt_country; }
if ($alt_tier === 'primary')      { $where[] = "ai_causation = 'primary_cause'"; }
elseif ($alt_tier === 'contributing') { $where[] = "ai_causation = 'contributing_cause'"; }
if ($alt_q) { $where[] = "(company LIKE %s OR ai_language LIKE %s)"; $params[] = '%' . $wpdb->esc_like($alt_q) . '%'; $params[] = '%' . $wpdb->esc_like($alt_q) . '%'; }
if ($alt_letter) { $where[] = "company LIKE %s"; $params[] = $wpdb->esc_like($alt_letter) . '%'; }
$where_sql = implode(' AND ', $where);

$alt_total = (int) $wpdb->get_var(alt_db_prep("SELECT COUNT(*) FROM $alt_t WHERE $where_sql", $params));
$alt_jobs  = (int) $wpdb->get_var(alt_db_prep("SELECT COALESCE(SUM(job_count),0) FROM $alt_t WHERE $where_sql", $params));
$LIMIT = 300;
$alt_order = 'layoff_date DESC, job_count DESC';                    // recent (default)
if ($alt_sort === 'az')   { $alt_order = 'company ASC, layoff_date DESC'; }
if ($alt_sort === 'jobs') { $alt_order = 'job_count DESC, layoff_date DESC'; }
$alt_rows = $wpdb->get_results(alt_db_prep(
    "SELECT company, job_count, layoff_date, country, state, industry, ai_language, ai_causation, source_url, source_type
     FROM $alt_t WHERE $where_sql ORDER BY $alt_order LIMIT $LIMIT", $params), ARRAY_A) ?: array();

// Alphabet strip: only letters that actually have a quoted attribution become
// links (clicking a dead letter would land on an empty wall). One cheap query
// over the ~100-row AI subset.
$alt_letters = $wpdb->get_col("SELECT DISTINCT UPPER(LEFT(company,1)) FROM $alt_t WHERE ai_explicit=1 AND ai_language<>''");
$alt_letters = array_flip(array_filter($alt_letters, function ($l) { return preg_match('/^[A-Z]$/', (string) $l); }));

// Filter chips: the years and tiers that actually have quotes, so a click never
// leads to an empty wall.
$alt_years = $wpdb->get_col("SELECT DISTINCT YEAR(layoff_date) y FROM $alt_t WHERE ai_explicit=1 AND ai_language<>'' ORDER BY y DESC");
$alt_base = home_url('/ai-layoff-tracker/ai-quotes/');
$chip = function ($label, $args, $active) use ($alt_base) {
    $url = empty($args) ? $alt_base : esc_url(add_query_arg($args, $alt_base));
    return '<a class="alt-qw-chip' . ($active ? ' alt-qw-chip-on' : '') . '" href="' . $url . '">' . esc_html($label) . '</a>';
};
$src_label = function ($t) {
    $m = array('sec_8k' => 'SEC filing', 'warn' => 'WARN notice', 'news' => 'News', 'press_release' => 'Company statement', 'erm' => 'EU ERM');
    return $m[$t] ?? 'Source';
};
?>
<main class="alt-wrap alt-qw">
  <p class="alt-eyebrow">AskTheRecruiter · AI Layoff Tracker</p>
  <h1>AI layoffs, in the employer's own words</h1>
  <p class="alt-lead"><span class="alt-lead-text">Every layoff we attribute to AI carries the company's own statement, quoted verbatim, with a link to where they said it. This is the receipt behind the AI number: not inference, not press framing, the employer's words. Filter it, quote it, check it.</span></p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/#alt-metric-definitions')); ?>">How the AI tag works</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press kit</a></p>

  <div class="alt-qw-summary">
    <b><?php echo number_format($alt_total); ?></b> AI attributions<?php echo $alt_total > $LIMIT ? ' (showing the ' . $LIMIT . ' most recent)' : ''; ?> · <b><?php echo number_format($alt_jobs); ?></b> jobs · <?php echo $alt_year ? esc_html($alt_year) : 'all-time'; ?> · each with the employer's quote and its source.
  </div>

  <div class="alt-qw-filters" aria-label="Filter the AI attributions">
    <div class="alt-qw-chiprow"><span class="alt-qw-chiplabel">Year</span>
      <?php echo $chip('All', array_filter(array('industry' => $alt_ind, 'tier' => $alt_tier, 'country' => $alt_country)), !$alt_year);
      foreach ($alt_years as $y) { echo $chip($y, array_filter(array('years' => (int) $y, 'industry' => $alt_ind, 'tier' => $alt_tier, 'country' => $alt_country)), $alt_year === (int) $y); } ?>
    </div>
    <div class="alt-qw-chiprow"><span class="alt-qw-chiplabel">Attribution</span>
      <?php echo $chip('Any', array_filter(array('years' => $alt_year, 'industry' => $alt_ind, 'country' => $alt_country)), !$alt_tier);
      echo $chip('AI named as the cause', array_filter(array('years' => $alt_year, 'industry' => $alt_ind, 'country' => $alt_country, 'tier' => 'primary')), $alt_tier === 'primary');
      echo $chip('AI named among causes', array_filter(array('years' => $alt_year, 'industry' => $alt_ind, 'country' => $alt_country, 'tier' => 'contributing')), $alt_tier === 'contributing'); ?>
    </div>
    <div class="alt-qw-chiprow"><span class="alt-qw-chiplabel">Sort</span>
      <?php $alt_keep = array_filter(array('years' => $alt_year, 'industry' => $alt_ind, 'tier' => $alt_tier, 'country' => $alt_country, 'letter' => $alt_letter));
      echo $chip('Newest first', $alt_keep, $alt_sort === 'recent');
      echo $chip('Company A to Z', array_merge($alt_keep, array('sort' => 'az')), $alt_sort === 'az');
      echo $chip('Largest first', array_merge($alt_keep, array('sort' => 'jobs')), $alt_sort === 'jobs'); ?>
    </div>
    <div class="alt-qw-chiprow alt-qw-alpha"><span class="alt-qw-chiplabel">Company</span>
      <?php $alt_keep_s = array_filter(array('years' => $alt_year, 'industry' => $alt_ind, 'tier' => $alt_tier, 'country' => $alt_country, 'sort' => $alt_sort === 'recent' ? '' : $alt_sort));
      echo $chip('All', $alt_keep_s, !$alt_letter);
      foreach (range('A', 'Z') as $alt_l) {
          if (isset($alt_letters[$alt_l])) {
              echo $chip($alt_l, array_merge($alt_keep_s, array('letter' => $alt_l)), $alt_letter === $alt_l);
          } else {
              echo '<span class="alt-qw-chip alt-qw-chip-dead">' . esc_html($alt_l) . '</span>';
          }
      } ?>
    </div>
    <?php if ($alt_ind || $alt_country || $alt_q) : ?>
    <div class="alt-qw-chiprow"><span class="alt-qw-chiplabel">Active</span>
      <?php if ($alt_ind) echo $chip('Industry: ' . $alt_ind . ' ✕', array_filter(array('years' => $alt_year, 'tier' => $alt_tier, 'country' => $alt_country)), false);
      if ($alt_country) echo $chip('Country: ' . $alt_country . ' ✕', array_filter(array('years' => $alt_year, 'tier' => $alt_tier, 'industry' => $alt_ind)), false);
      if ($alt_q) echo $chip('“' . $alt_q . '” ✕', array_filter(array('years' => $alt_year, 'tier' => $alt_tier, 'industry' => $alt_ind, 'country' => $alt_country)), false); ?>
    </div>
    <?php endif; ?>
  </div>

  <?php if (!$alt_rows) : ?>
    <p class="alt-muted">No AI attributions match this filter. <a href="<?php echo esc_url($alt_base); ?>">Clear filters</a>.</p>
  <?php else : ?>
  <ul class="alt-qw-list">
    <?php foreach ($alt_rows as $r) :
      $primary = $r['ai_causation'] === 'primary_cause';
      $tier = $primary ? 'AI named as the cause' : 'AI named among the causes';
      $loc = trim(($r['state'] ? $r['state'] . ' · ' : '') . ($r['country'] ?: ''));
      $quote = trim(rtrim(trim($r['ai_language']), '. '), "\"'\xe2\x80\x9c\xe2\x80\x9d");
    ?>
    <li class="alt-qw-card">
      <div class="alt-qw-head">
        <b class="alt-qw-co"><?php echo esc_html($r['company']); ?></b>
        <span class="alt-qw-tier alt-qw-tier-<?php echo $primary ? 'primary' : 'contrib'; ?>"><?php echo esc_html($tier); ?></span>
      </div>
      <blockquote class="alt-qw-quote">&ldquo;<?php echo esc_html($quote); ?>&rdquo;</blockquote>
      <div class="alt-qw-meta">
        <span><b><?php echo number_format((int) $r['job_count']); ?></b> jobs</span>
        <span><?php echo esc_html($r['layoff_date']); ?></span>
        <?php if ($loc) : ?><span><?php echo esc_html($loc); ?></span><?php endif; ?>
        <?php if ($r['industry']) : ?><a class="alt-qw-tag" href="<?php echo esc_url(add_query_arg(array('industry' => $r['industry']), $alt_base)); ?>"><?php echo esc_html($r['industry']); ?></a><?php endif; ?>
        <span class="alt-qw-srctype"><?php echo esc_html($src_label($r['source_type'])); ?></span>
        <?php if ($r['source_url']) : ?><a class="alt-qw-src" href="<?php echo esc_url($r['source_url']); ?>" target="_blank" rel="noopener">See the source &rarr;</a><?php endif; ?>
      </div>
    </li>
    <?php endforeach; ?>
  </ul>
  <?php if ($alt_total > $LIMIT) : ?>
    <p class="alt-qw-more">Showing the <?php echo $LIMIT; ?> most recent of <?php echo number_format($alt_total); ?>. Narrow with a year or industry filter above, or <a href="<?php echo esc_url(add_query_arg(array('ai' => '1'), home_url('/ai-layoff-tracker/'))); ?>" target="_blank" rel="noopener">open the full set in the tracker</a>.</p>
  <?php endif; ?>
  <?php endif; ?>

  <p class="alt-qw-foot alt-muted"><b>How these are chosen:</b> a cut appears here only when the employer named AI or automation as a cause in words we can quote, confirmed by two independent passes, with the source on file. Investment in AI, a future projection, or AI used to pick who goes does not qualify. This is the strict, quotable standard; the tracker also has a broader AI-linked measure, labelled separately. <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/#alt-metric-definitions')); ?>">Full methodology &rarr;</a></p>
</main>
