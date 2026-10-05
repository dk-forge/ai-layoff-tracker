<?php
/**
 * Labour-market context section, rendered by [alt_labour_context]
 * (includes/labour-context.php). Each panel renders only when its data exists;
 * assets/labour-context.js draws the charts from the public
 * /reference/<source> endpoints and repaints on alt:themechange.
 */
if (!defined('ABSPATH')) exit;
$alt_lc_ages = array('Y_GE15' => '15 and over', 'Y15T24' => '15 to 24', 'Y25T74' => '25 to 74',
    'Y15T74' => '15 to 74', 'Y25T54' => '25 to 54', 'Y55T74' => '55 to 74', 'Y_GE25' => '25 and over');
?>
<section class="alt-lc" id="labour-context" aria-labelledby="alt-lc-h"
         data-api="<?php echo esc_attr($alt_lc_api); ?>">
    <h2 id="alt-lc-h">Labour-market context</h2>
    <p class="alt-lc-intro"><strong>These are official aggregate statistics, not the tracker's own counts.</strong>
    They come from government and OECD surveys, cover every cause of job loss, and are never added to
    the entries we record. They are here for scale only and do not show that AI caused any of the changes.</p>

    <div class="alt-chart-grid">
    <?php if ($alt_lc_industries) : ?>
        <figure class="alt-chart-card alt-chart-card-wide alt-lc-panel" data-lc="jolts">
            <div class="alt-chart-h" id="alt-lc-jolts-h">US layoffs, job openings and quits <span class="alt-chart-sub">monthly, thousands, seasonally adjusted</span></div>
            <div class="alt-lc-controls">
                <label for="alt-lc-jolts-ind">Industry</label>
                <select id="alt-lc-jolts-ind" class="alt-lc-select">
                    <?php foreach ($alt_lc_industries as $alt_lc_i) : ?>
                        <option value="<?php echo esc_attr($alt_lc_i); ?>"><?php echo esc_html($alt_lc_i); ?></option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="alt-chart-box"><canvas id="alt-lc-jolts" role="img" aria-labelledby="alt-lc-jolts-h"></canvas></div>
            <figcaption>
                <p class="alt-lc-caption">Each month US employers report how many people they laid off or discharged,
                how many jobs they had open, and how many workers quit. When quits are high and openings outnumber
                layoffs, workers are finding it easier to move; when layoffs rise and openings fall, the market is cooling.</p>
                <p class="alt-lc-src">Source: U.S. Bureau of Labor Statistics (Job Openings and Labor Turnover Survey). Public domain.
                <?php echo esc_html(alt_labour_context_asof($alt_lc_bls, 'jolts')); ?></p>
            </figcaption>
        </figure>
    <?php endif; ?>

    <?php if ($alt_lc_dims) : ?>
        <figure class="alt-chart-card alt-chart-card-wide alt-lc-panel" data-lc="cps">
            <div class="alt-chart-h" id="alt-lc-cps-h">US unemployment rate by group <span class="alt-chart-sub">monthly, percent, seasonally adjusted</span></div>
            <div class="alt-lc-controls">
                <label for="alt-lc-cps-dim">Compare by</label>
                <select id="alt-lc-cps-dim" class="alt-lc-select">
                    <?php foreach ($alt_lc_dims as $alt_lc_k => $alt_lc_l) : ?>
                        <option value="<?php echo esc_attr($alt_lc_k); ?>"><?php echo esc_html($alt_lc_l); ?></option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="alt-chart-box"><canvas id="alt-lc-cps" role="img" aria-labelledby="alt-lc-cps-h"></canvas></div>
            <figcaption>
                <p class="alt-lc-caption">The share of people in each group who want a job and do not have one. The dashed
                line is the rate for everyone 16 and over, so you can see which groups sit above or below it.</p>
                <p class="alt-lc-src">Source: U.S. Bureau of Labor Statistics (Current Population Survey). Public domain.
                <?php echo esc_html(alt_labour_context_asof($alt_lc_bls, 'cps')); ?></p>
            </figcaption>
        </figure>
    <?php endif; ?>

    <?php if ($alt_lc_countries) : ?>
        <figure class="alt-chart-card alt-chart-card-wide alt-lc-panel" data-lc="oecd">
            <div class="alt-chart-h" id="alt-lc-oecd-h">Unemployment rate by country <span class="alt-chart-sub">monthly, percent, seasonally adjusted</span></div>
            <div class="alt-lc-controls">
                <label for="alt-lc-oecd-country">Countries</label>
                <select id="alt-lc-oecd-country" class="alt-lc-select" multiple size="4">
                    <?php foreach ($alt_lc_countries as $alt_lc_c => $alt_lc_n) : ?>
                        <option value="<?php echo esc_attr($alt_lc_c); ?>"<?php echo in_array($alt_lc_c, array('USA', 'GBR', 'DEU', 'OECD'), true) ? ' selected' : ''; ?>><?php echo esc_html($alt_lc_n); ?></option>
                    <?php endforeach; ?>
                </select>
                <label for="alt-lc-oecd-sex">Sex</label>
                <select id="alt-lc-oecd-sex" class="alt-lc-select">
                    <option value="_T">Everyone</option>
                    <option value="M">Men</option>
                    <option value="F">Women</option>
                </select>
                <label for="alt-lc-oecd-age">Age</label>
                <select id="alt-lc-oecd-age" class="alt-lc-select">
                    <?php foreach ($alt_lc_ages as $alt_lc_k => $alt_lc_l) : ?>
                        <option value="<?php echo esc_attr($alt_lc_k); ?>"><?php echo esc_html($alt_lc_l); ?></option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="alt-chart-box"><canvas id="alt-lc-oecd" role="img" aria-labelledby="alt-lc-oecd-h"></canvas></div>
            <figcaption>
                <p class="alt-lc-caption">The unemployment rate in each selected country, from national labour force surveys
                harmonised by the OECD so the countries can be compared. Pick up to six countries; a group or age with no
                published figure for a country is left out rather than estimated.</p>
                <p class="alt-lc-src">Source: OECD (CC BY 4.0), Infra-annual labour statistics, monthly unemployment rates.
                <?php echo esc_html(alt_labour_context_asof($alt_lc_oecd, 'monthly')); ?></p>
            </figcaption>
        </figure>
    <?php endif; ?>
    </div>
    <p class="alt-lc-status" role="status" aria-live="polite"></p>
</section>
