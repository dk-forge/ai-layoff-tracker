<?php
/**
 * Year-by-year timeline for a company, country or US state page.
 * Expects $alt_timeline (alt_timeline_by_year() output). Renders nothing for
 * fewer than two years: one bar is a restatement of the total, not a trend.
 * A list of bars, not a chart library, so it is in the HTML a crawler reads
 * and it wraps at 375px.
 */
if (!defined('ABSPATH')) exit;
if (empty($alt_timeline) || count($alt_timeline) < 2) return;
$alt_tl_max = 0;
foreach ($alt_timeline as $alt_tl) { $alt_tl_max = max($alt_tl_max, (int) $alt_tl['jobs']); }
?>
<section class="alt-timeline" aria-labelledby="alt-timeline-h">
    <h2 id="alt-timeline-h">Timeline: recorded jobs by year</h2>
    <div class="alt-op-bars">
    <?php foreach ($alt_timeline as $alt_tl) :
        $alt_w = $alt_tl_max > 0 ? max(2, (int) round(100 * (int) $alt_tl['jobs'] / $alt_tl_max)) : 0; ?>
        <div class="alt-op-bar"><span class="alt-op-barname"><?php echo (int) $alt_tl['year']; ?><?php echo !empty($alt_tl['partial']) ? ' so far' : ''; ?></span>
            <span class="alt-op-bartrack"><span class="alt-op-barfill" style="width:<?php echo $alt_w; ?>%"></span></span>
            <span class="alt-op-barval"><?php echo number_format((int) $alt_tl['jobs']); ?><?php if ((int) $alt_tl['ai_jobs'] > 0) : ?> <span class="alt-op-barai">AI <?php echo number_format((int) $alt_tl['ai_jobs']); ?></span><?php endif; ?></span></div>
    <?php endforeach; ?>
    </div>
</section>
