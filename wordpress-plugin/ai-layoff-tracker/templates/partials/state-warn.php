<?php
/**
 * This year's WARN notices on a US state page. Expects $alt_f (facet data)
 * with $alt_f['warn'] from alt_state_warn_data(). Renders nothing without it.
 * Lists and one table; the table scrolls inside its own container so a phone
 * never bleeds horizontally.
 */
if (!defined('ABSPATH')) exit;
$alt_w = $alt_f['warn'] ?? null;
if (empty($alt_w) || empty($alt_w['notices'])) return;
$alt_w_y = (int) $alt_w['year'];
$alt_w_max = 0;
foreach ($alt_w['months'] as $alt_wm) { $alt_w_max = max($alt_w_max, (int) $alt_wm['jobs']); }
?>
<section class="alt-state-warn" aria-labelledby="alt-state-warn-h">
    <h2 id="alt-state-warn-h"><?php echo esc_html($alt_f['display'] . ' WARN notices in ' . $alt_w_y); ?></h2>
    <p class="alt-facet-summary">We hold <strong><?php echo number_format((int) $alt_w['notices']); ?></strong>
    WARN <?php echo (int) $alt_w['notices'] === 1 ? 'notice' : 'notices'; ?> for <?php echo esc_html($alt_f['display']); ?>
    dated in <?php echo $alt_w_y; ?>, covering <strong><?php echo number_format((int) $alt_w['jobs']); ?></strong> jobs.
    Months are counted by the date the cuts take effect, so a notice filed now can sit in a later month.</p>

    <h3>By month</h3>
    <div class="alt-op-bars">
    <?php foreach ($alt_w['months'] as $alt_wm) :
        $alt_wpct = $alt_w_max > 0 ? max(2, (int) round(100 * (int) $alt_wm['jobs'] / $alt_w_max)) : 0;
        $alt_wlabel = date('M Y', strtotime($alt_wm['month'] . '-01')); ?>
        <div class="alt-op-bar"><span class="alt-op-barname"><?php echo esc_html($alt_wlabel); ?></span>
            <span class="alt-op-bartrack"><span class="alt-op-barfill" style="width:<?php echo $alt_wpct; ?>%"></span></span>
            <span class="alt-op-barval"><?php echo number_format((int) $alt_wm['jobs']); ?> jobs, <?php echo number_format((int) $alt_wm['notices']); ?> <?php echo (int) $alt_wm['notices'] === 1 ? 'notice' : 'notices'; ?></span></div>
    <?php endforeach; ?>
    </div>

    <?php if (!empty($alt_w['employers'])) : ?>
    <h3>Top employers in <?php echo $alt_w_y; ?></h3>
    <ul class="alt-facet-links">
    <?php foreach ($alt_w['employers'] as $alt_we) : ?>
        <li><?php if (!empty($alt_we['url'])) : ?><a href="<?php echo esc_url($alt_we['url']); ?>"><?php echo esc_html($alt_we['name']); ?></a><?php else : ?><span><?php echo esc_html($alt_we['name']); ?></span><?php endif; ?>
            <span class="alt-facet-links-val"><?php echo number_format((int) $alt_we['jobs']); ?> jobs</span></li>
    <?php endforeach; ?>
    </ul>
    <?php endif; ?>

    <?php if (!empty($alt_w['cities'])) : ?>
    <h3>Cities in <?php echo $alt_w_y; ?></h3>
    <p class="alt-muted">As each notice names the location. Notices that name none are left out of this list.</p>
    <ul class="alt-facet-links">
    <?php foreach ($alt_w['cities'] as $alt_wc) : ?>
        <li><span><?php echo esc_html($alt_wc['city']); ?></span>
            <span class="alt-facet-links-val"><?php echo number_format((int) $alt_wc['jobs']); ?> jobs</span></li>
    <?php endforeach; ?>
    </ul>
    <?php endif; ?>

    <h3>Latest notices</h3>
    <div class="alt-state-warn-scroll">
    <table class="alt-state-warn-table">
        <thead><tr><th scope="col">Employer</th><th scope="col">City</th><th scope="col">Filed</th><th scope="col">Effective</th><th scope="col">Jobs</th></tr></thead>
        <tbody>
        <?php foreach ($alt_w['recent'] as $alt_wr) : ?>
            <tr>
                <td><?php if (!empty($alt_wr['url'])) : ?><a href="<?php echo esc_url($alt_wr['url']); ?>"><?php echo esc_html($alt_wr['company']); ?></a><?php else : echo esc_html($alt_wr['company']); endif; ?></td>
                <td><?php echo esc_html($alt_wr['city'] !== '' ? $alt_wr['city'] : 'Not stated'); ?></td>
                <td><?php echo esc_html($alt_wr['filed'] !== '' ? $alt_wr['filed'] : 'Not published'); ?></td>
                <td><?php echo esc_html($alt_wr['effective']); ?></td>
                <td class="alt-num"><?php echo number_format((int) $alt_wr['jobs']); ?></td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
    </div>

    <?php $alt_faq = alt_state_warn_faq($alt_f['display'], $alt_w);
          if ($alt_faq) : ?>
    <h3>Questions about <?php echo esc_html($alt_f['display']); ?> WARN notices</h3>
    <dl class="alt-state-warn-faq">
    <?php foreach ($alt_faq as $alt_qa) : ?>
        <dt><?php echo esc_html($alt_qa['q']); ?></dt>
        <dd><?php echo esc_html($alt_qa['a']); ?></dd>
    <?php endforeach; ?>
    </dl>
    <?php endif; ?>
</section>
