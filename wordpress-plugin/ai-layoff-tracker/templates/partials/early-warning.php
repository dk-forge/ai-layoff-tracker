<?php
/**
 * Early-warning view (includes/early-warning.php), included by
 * partials/labour-context.php after the chart grid. Server-rendered status for
 * the default industry; assets/labour-context.js redraws from data-ew when the
 * reader picks another one. Hidden when no official series exists.
 */
if (!defined('ABSPATH')) exit;
if (empty($alt_lc_ew) || empty($alt_lc_ew['industries'])) return;
$alt_ew_first = reset($alt_lc_ew['industries']);
$alt_ew_asof = array();
if (!empty($alt_lc_fred['latest']['weekly'])) $alt_ew_asof[] = 'claims through ' . alt_labour_context_month($alt_lc_fred['latest']['weekly']);
if (!empty($alt_lc_bls['latest']['jolts'])) $alt_ew_asof[] = 'JOLTS through ' . alt_labour_context_month($alt_lc_bls['latest']['jolts']);
if (!empty($alt_lc_qwi['latest_quarter'])) $alt_ew_asof[] = 'QWI through ' . alt_lc_quarter($alt_lc_qwi['latest_quarter']);
$alt_ew_asof[] = 'WARN notices as recorded on ' . gmdate('j M Y');
$alt_ew_json = function_exists('wp_json_encode') ? wp_json_encode($alt_lc_ew) : json_encode($alt_lc_ew);
?>
<div class="alt-ew" id="early-warning" data-ew="<?php echo esc_attr($alt_ew_json); ?>">
    <h3 id="alt-ew-h">Early warning by industry</h3>
    <p class="alt-lc-intro">Four signals on one monthly timeline: our own count of WARN notices and three official measures
    of job loss. Official figures arrive weeks or months after the fact, so a rise in WARN notices can show up first.</p>
    <figure class="alt-chart-card alt-chart-card-wide alt-lc-panel" data-lc="ew">
        <div class="alt-lc-controls">
            <label for="alt-ew-ind">Industry</label>
            <select id="alt-ew-ind" class="alt-lc-select">
                <?php foreach ($alt_lc_ew['industries'] as $alt_ew_k => $alt_ew_i) : ?>
                    <option value="<?php echo esc_attr($alt_ew_k); ?>"><?php echo esc_html($alt_ew_i['label']); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <p class="alt-ew-status" aria-live="polite">
            <span class="alt-ew-k">Official signals:</span>
            <span class="alt-ew-badge" data-status="<?php echo esc_attr((string) $alt_ew_first['status']); ?>"><?php
                echo esc_html($alt_ew_first['status'] ? $alt_ew_first['status_label'] : 'Not enough official data to judge'); ?></span>
            <span class="alt-ew-why"><?php echo esc_html(implode('; ', $alt_ew_first['reasons'])); ?></span>
        </p>
        <div class="alt-chart-box"><canvas id="alt-lc-ew" role="img" aria-labelledby="alt-ew-h"></canvas></div>
        <figcaption>
            <p class="alt-lc-caption">Each line is indexed to its own average over the period shown (100 = average), so
            series of very different sizes can share one axis; hover a point for the real figure. QWI separations are
            quarterly and all-cause (quits and retirements as well as layoffs), placed on each quarter's last month.
            Weekly claims are national and averaged per month. Industries are matched to official sectors approximately.</p>
            <p class="alt-lc-caption"><strong>How the label is set.</strong> Only the official series count; our WARN notices
            never do. Claims and JOLTS compare the latest 3 months with the 12 before them; QWI compares the latest quarter
            with the same quarter a year earlier. A rise of 5% or more counts as rising and a fall of 5% or more as falling. With at
            least two official series judged, two or more rising (and more rising than falling) reads Heating up, two or
            more falling reads Cooling, and anything else reads Stable. These measures count job losses from every cause;
            none of them says why, and this label does not say anything about AI.</p>
            <p class="alt-lc-src">Sources: our WARN notice records (state WARN registers); Federal Reserve Bank of St. Louis,
            FRED (initial claims, U.S. Employment and Training Administration); U.S. Bureau of Labor Statistics, JOLTS;
            U.S. Census Bureau, LEHD Quarterly Workforce Indicators. Official data are public domain.
            <?php echo esc_html('Data: ' . implode(', ', $alt_ew_asof) . '.'); ?></p>
        </figcaption>
    </figure>
</div>
