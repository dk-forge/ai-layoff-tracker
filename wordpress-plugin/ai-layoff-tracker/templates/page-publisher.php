<?php if (!defined('ABSPATH')) exit; ?>
<main class="alt-wrap alt-health-page" id="alt-publisher-page">
  <header class="alt-health-hero"><p class="alt-eyebrow">AskTheRecruiter · publisher tools</p><h1>Embed the layoff tracker</h1><p>Free widgets for newsrooms, blogs and dashboards. Every widget sends your readers to the exact tracker view behind it, and to how we count. The numbers update on their own.</p></header>
  <section class="alt-health-section alt-widget-builder" aria-labelledby="alt-widget-builder-heading">
    <h2 id="alt-widget-builder-heading">Embed a US layoff widget</h2>
    <p>Build a widget for the whole US or for a single state. It links to its sources and is kept out of search results. Metro widgets are deliberately unavailable, because metro geography is not reliable enough yet.</p>
    <div class="alt-widget-builder-controls"><label for="alt-widget-year">Year <select id="alt-widget-year"></select></label><label for="alt-widget-state">Scope <select id="alt-widget-state"><option value="">United States</option></select></label></div>
    <label for="alt-widget-code">Copy this iframe code</label><textarea id="alt-widget-code" rows="4" readonly aria-describedby="alt-widget-builder-note"></textarea>
    <div class="alt-widget-builder-actions"><button type="button" class="alt-btn alt-btn-sm" id="alt-widget-copy">Copy widget code</button><a id="alt-widget-tracker-link" href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>" target="_blank" rel="noopener">Preview exact tracker view</a></div>
    <p id="alt-widget-builder-note">The snippet contains only an iframe. If you add attribution outside it, you choose its link attributes; no backlink is requested or promised.</p><p id="alt-widget-copy-status" role="status" aria-live="polite"></p>
  </section>
  <p class="alt-health-links"><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">Live tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press &amp; media</a></p>
</main>
