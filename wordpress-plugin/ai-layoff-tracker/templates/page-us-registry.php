<?php if (!defined('ABSPATH')) exit;
/**
 * Public US jurisdiction registry: one row per jurisdiction, every value
 * derived. The committed half is data/us-jurisdictions.json (generated from
 * the source inventory, the scrapers' own state lists, the official-URL map,
 * the freshness ledger and the WARN workflows' cron lines); the live half is
 * the source-health ledger and the layoffs table, read in includes/us-registry.php.
 *
 * Absence renders as absence. No collector: no cadence. No health row: "not
 * yet reported". No rows on file: no range. Nothing here defaults to a value a
 * reader could mistake for a measurement.
 */
$alt_reg   = function_exists('alt_us_registry_data') ? alt_us_registry_data() : null;
$alt_rows  = function_exists('alt_us_registry_rows') ? alt_us_registry_rows() : array();
$alt_health_url = home_url('/ai-layoff-tracker/ai-tracker-health/');
$alt_sources_url = home_url('/ai-layoff-tracker/sources/');
$alt_fmt_date = function ($iso) {
    $t = strtotime((string) $iso);
    return $t ? gmdate('j M Y', $t) : '';
};
$alt_n_collected = 0; $alt_n_none = 0; $alt_n_fresh = 0;
foreach ($alt_rows as $alt_r) {
    if (!empty($alt_r['collectors'])) $alt_n_collected++;
    if (!empty($alt_r['no_public_register'])) $alt_n_none++;
    if (($alt_r['freshness']['state'] ?? '') === 'HEALTHY' && ($alt_r['freshness']['verdict'] ?? '') === 'PASS') $alt_n_fresh++;
}
?>
<main class="alt-wrap alt-sources-page alt-us-registry-page">
  <p class="alt-eyebrow">AskTheRecruiter · AI Layoff Tracker</p>
  <h1>US WARN Registry by Jurisdiction</h1>
  <p class="alt-lead"><span class="alt-lead-text">One row for each of the 50 states, the District of Columbia and the five inhabited territories. Each row shows where the official WARN notices are published, how we read them, when we last collected and whether the register is fresh. It also shows how far back our copy goes and says where there is no public register at all. Every cell is read from the collectors and the ledgers, not typed.</span></p>

  <?php if (!$alt_rows) : ?>
  <p class="alt-muted">The jurisdiction registry is being generated and will appear on the next update.</p>
  <?php else : ?>

  <div class="alt-facet-total alt-registry-total">
    <p><strong><?php echo number_format(count($alt_rows)); ?></strong> jurisdictions</p>
    <p><strong><?php echo number_format($alt_n_collected); ?></strong> with a collector reading the official register</p>
    <p><strong><?php echo number_format($alt_n_fresh); ?></strong> judged fresh against their own filing history</p>
    <p><strong><?php echo number_format($alt_n_none); ?></strong> with no public register</p>
  </div>

  <p class="alt-muted"><b>How to read this table.</b> <b>Fresh</b> means the newest notice on file is no older than this jurisdiction's own publishing rhythm predicts. <b>Quiet</b> means a longer silence than usual, not evidence of a break. <b>Too few notices to judge</b> means the register publishes so rarely that no rhythm can be fitted yet. <b>Published, not countable</b> means the state posts notices without a per-employer worker count, and we never invent a number. <b>No public register</b> is a finding a reviewer recorded, with the reason shown. Live collector status, including failures, is on the <a href="<?php echo esc_url($alt_health_url); ?>">health page</a>; the full source list is on the <a href="<?php echo esc_url($alt_sources_url); ?>">sources page</a>.</p>

  <div class="alt-health-table-wrap" tabindex="0"><table class="alt-sortable alt-sources-table alt-registry-table">
    <thead><tr>
      <th>Jurisdiction</th>
      <th>Official source</th>
      <th>Collection method</th>
      <th>Last successful collection</th>
      <th>Freshness</th>
      <th>Historical range</th>
      <th>Worker counts</th>
      <th>Notice documents</th>
    </tr></thead>
    <tbody>
    <?php foreach ($alt_rows as $alt_r) :
        $alt_code = (string) $alt_r['code'];
        $alt_f = $alt_r['facts'];
        $alt_fresh_label = alt_us_registry_freshness_label($alt_r);
        $alt_fresh_cls = alt_us_registry_freshness_class($alt_r);
        $alt_cad = alt_us_registry_cadence($alt_r);
        $alt_methods = array();
        foreach ((array) $alt_r['collectors'] as $alt_c) {
            if (!in_array($alt_c['method'], $alt_methods, true)) $alt_methods[] = $alt_c['method'];
        }
        $alt_reason = '';
        if (!empty($alt_r['unavailable']['reason'])) $alt_reason = (string) $alt_r['unavailable']['reason'];
        elseif (!empty($alt_r['freshness']['reason']) && in_array($alt_fresh_label, array('Quiet', 'Dark', 'Too few notices to judge'), true)) $alt_reason = (string) $alt_r['freshness']['reason'];
        $alt_newest = !empty($alt_r['freshness']['newest_received']) ? $alt_fmt_date($alt_r['freshness']['newest_received']) : '';
    ?>
      <tr>
        <td><b><?php echo esc_html($alt_r['name']); ?></b> <span class="alt-muted">(<?php echo esc_html($alt_code); ?>)</span><?php if ($alt_r['kind'] === 'territory' && $alt_code !== 'DC') : ?><br><span class="alt-muted">Territory</span><?php endif; ?></td>
        <td><?php if (!empty($alt_r['official_url'])) : ?><a href="<?php echo esc_url($alt_r['official_url']); ?>" target="_blank" rel="noopener"><?php echo esc_html(preg_replace('#^https?://(www\.)?#', '', rtrim($alt_r['official_url'], '/'))); ?> &#8599;</a><?php else : ?><span class="alt-muted">None on file</span><?php endif; ?></td>
        <td><?php if ($alt_methods) : ?><?php echo esc_html(implode('; ', $alt_methods)); ?><?php if ($alt_cad !== '') : ?><br><span class="alt-warn-cadence"><?php echo esc_html(ucfirst($alt_cad)); ?></span><?php endif; ?><?php else : ?><span class="alt-muted">No collector</span><?php endif; ?></td>
        <td><?php if (!empty($alt_r['last_ok'])) : ?><time datetime="<?php echo esc_attr($alt_r['last_ok']); ?>"><?php echo esc_html($alt_fmt_date($alt_r['last_ok'])); ?></time><?php if ($alt_newest !== '') : ?><br><span class="alt-muted">Newest notice received <?php echo esc_html($alt_newest); ?></span><?php endif; ?><?php elseif (!empty($alt_r['collectors'])) : ?><span class="alt-muted"><?php echo $alt_r['last_status'] === '' ? 'Not yet reported' : 'Last run did not complete'; ?></span><?php else : ?><span class="alt-muted">n/a</span><?php endif; ?></td>
        <td><span class="alt-gap-status alt-registry-<?php echo esc_attr($alt_fresh_cls); ?>"><?php echo esc_html($alt_fresh_label); ?></span><?php if ($alt_reason !== '') : ?><br><span class="alt-muted alt-registry-reason"><?php echo esc_html($alt_reason); ?></span><?php endif; ?></td>
        <td><?php if ($alt_f && $alt_f['first'] !== '' && $alt_f['last'] !== '') : ?><?php echo esc_html(substr($alt_f['first'], 0, 4)); ?> to <?php echo esc_html(substr($alt_f['last'], 0, 4)); ?><br><span class="alt-muted"><?php echo number_format((int) $alt_f['rows']); ?> notices</span><?php else : ?><span class="alt-muted">No notices on file</span><?php endif; ?></td>
        <td><?php if ($alt_f && $alt_f['rows'] > 0) : ?><?php echo (int) $alt_f['counted'] > 0 ? 'Yes' : 'No'; ?> <span class="alt-muted">(<?php echo number_format((int) $alt_f['counted']); ?> of <?php echo number_format((int) $alt_f['rows']); ?>)</span><?php else : ?><span class="alt-muted">n/a</span><?php endif; ?></td>
        <td><?php if ($alt_f && $alt_f['rows'] > 0) : ?><?php echo (int) $alt_f['documents'] > 0 ? 'Yes' : 'No'; ?> <span class="alt-muted">(<?php echo number_format((int) $alt_f['documents']); ?> of <?php echo number_format((int) $alt_f['rows']); ?>)</span><?php else : ?><span class="alt-muted">n/a</span><?php endif; ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <p class="alt-scroll-hint alt-muted">Swipe sideways to see every column.</p>

  <p class="alt-muted"><b>What each column means.</b> <b>Official source</b> is the state page or data file the importer reads, the same link every notice cites. <b>Collection method</b> names the reader that turns that page into rows; a state served by two readers lists both. <b>Last successful collection</b> is the most recent completed run of a collector serving this jurisdiction, from the same ledger the health page shows. The newest-notice date is the last time a notice we had not seen before arrived. <b>Historical range</b> is the span of effective dates on file, so a future year is a notice whose layoff date has not arrived yet. <b>Worker counts</b> says whether the notices on file carry a per-employer headcount; a notice without one cannot become a countable row. <b>Notice documents</b> counts rows whose cited source is a per-notice page, letter or data file rather than the state's landing page.</p>

  <p class="alt-muted">Every jurisdiction still reaches the tracker through SEC filings and named news reports, whether or not it publishes WARN notices. This page is only about the notice registers. Rollup records and the per-site notices they absorb are counted once. Generated from the collectors' own registries<?php if ($alt_reg && !empty($alt_reg['generated_on'])) : ?>, last regenerated <?php echo esc_html($alt_fmt_date($alt_reg['generated_on'])); ?><?php endif; ?>; the collection and range columns are read live.</p>

  <?php endif; ?>

  <p>See the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">tracker methodology</a>, the <a href="<?php echo esc_url($alt_sources_url); ?>">full source list</a>, and <a href="<?php echo esc_url(home_url('/contact/')); ?>">submit a correction</a>.</p>
</main>
<style>
  /* Same table treatment as the Sources page, scoped to this page: the wrap
     scrolls inside its own border on a phone, the header stays put, and the
     freshness pills reuse the gap-status shape with one class per state. */
  .alt-us-registry-page .alt-health-table-wrap { border: 1px solid var(--alt-grid); border-radius: 10px; overflow: auto; max-height: 720px; margin: 6px 0 8px; }
  .alt-us-registry-page table { width: 100%; border-collapse: collapse; font-size: 14px; min-width: 980px; }
  .alt-us-registry-page table th { text-align: left; font-size: 11.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--alt-muted); font-weight: 700; padding: 9px 12px; border-bottom: 2px solid var(--alt-grid); background: var(--alt-surface-2); position: sticky; top: 0; z-index: 1; white-space: nowrap; }
  .alt-us-registry-page table td { padding: 10px 12px; border-bottom: 1px solid var(--alt-grid); vertical-align: top; line-height: 1.5; }
  .alt-us-registry-page table td:first-child { white-space: nowrap; }
  .alt-us-registry-page table tbody tr:hover { background: var(--alt-surface-2); }
  .alt-us-registry-page .alt-registry-reason { display: block; max-width: 34ch; font-size: 12.5px; line-height: 1.4; margin-top: 4px; }
  .alt-us-registry-page .alt-registry-total { display: flex; flex-wrap: wrap; gap: 8px 28px; }
  .alt-us-registry-page .alt-scroll-hint { font-size: 12.5px; margin: 0 0 16px; }
  .alt-us-registry-page .alt-sortable thead th::after { content: ' \2195'; opacity: .3; font-size: 10px; }
  .alt-us-registry-page .alt-sortable thead th[data-sort="asc"]::after { content: ' \2191'; opacity: 1; }
  .alt-us-registry-page .alt-sortable thead th[data-sort="desc"]::after { content: ' \2193'; opacity: 1; }
  .alt-registry-ok { background: var(--alt-ok-bg); color: var(--alt-ok-ink); }
  .alt-registry-quiet { background: var(--alt-cream-2); color: var(--alt-ink-2); }
  .alt-registry-dark { background: var(--alt-warn-bg); color: var(--alt-warn-ink); }
  .alt-registry-unknown { background: var(--alt-surface-2); color: var(--alt-muted); }
  .alt-registry-partial { background: var(--alt-cream-2); color: var(--alt-warn-ink); }
  .alt-registry-none { background: var(--alt-cream-2); color: var(--alt-warn-ink); }
  @media (min-width: 981px) { .alt-us-registry-page .alt-scroll-hint { display: none; } }
</style>
<script>
(function () {
  function num(s) { var n = parseFloat((s || '').replace(/[^0-9.\-]/g, '')); return isNaN(n) ? null : n; }
  document.querySelectorAll('.alt-us-registry-page table.alt-sortable').forEach(function (table) {
    var ths = Array.prototype.slice.call(table.querySelectorAll('thead th'));
    ths.forEach(function (th, ci) {
      th.style.cursor = 'pointer';
      th.addEventListener('click', function () {
        var tb = table.querySelector('tbody');
        var rows = Array.prototype.slice.call(tb.querySelectorAll('tr'));
        var dir = th.getAttribute('data-sort') === 'asc' ? 'desc' : 'asc';
        ths.forEach(function (o) { if (o !== th) o.removeAttribute('data-sort'); });
        th.setAttribute('data-sort', dir);
        rows.sort(function (a, b) {
          var ta = (a.children[ci] || {}).textContent || '', tbv = (b.children[ci] || {}).textContent || '';
          var na = num(ta), nb = num(tbv);
          var c = (na !== null && nb !== null) ? na - nb : ta.localeCompare(tbv);
          return dir === 'asc' ? c : -c;
        });
        rows.forEach(function (r) { tb.appendChild(r); });
      });
    });
  });
})();
</script>
