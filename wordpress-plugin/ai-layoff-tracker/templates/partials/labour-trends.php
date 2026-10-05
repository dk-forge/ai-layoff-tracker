<?php
/**
 * FRED trend + Census QWI hiring-vs-separations panels, included by
 * partials/labour-context.php inside its chart grid. Each renders only when
 * its picker has options (includes/labour-trends.php decides).
 */
if (!defined('ABSPATH')) exit;
?>
<?php if (!empty($alt_lc_fred_opts)) : ?>
    <figure class="alt-chart-card alt-chart-card-wide alt-lc-panel" data-lc="fred">
        <div class="alt-chart-h" id="alt-lc-fred-h">US labour trend <span class="alt-chart-sub">FRED series, as published</span></div>
        <div class="alt-lc-controls">
            <label for="alt-lc-fred-series">Series</label>
            <select id="alt-lc-fred-series" class="alt-lc-select">
                <?php foreach ($alt_lc_fred_opts as $alt_lc_k => $alt_lc_l) : ?>
                    <option value="<?php echo esc_attr($alt_lc_k); ?>"><?php echo esc_html($alt_lc_l); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="alt-chart-box"><canvas id="alt-lc-fred" role="img" aria-labelledby="alt-lc-fred-h"></canvas></div>
        <figcaption>
            <p class="alt-lc-caption">One official US series at a time. Weekly initial claims count new applications for
            unemployment insurance, so they move first when layoffs pick up. The unemployment rate and payroll counts
            are monthly. Information-sector jobs cover publishing, software publishing, telecoms, data processing and
            broadcasting. All of them cover every cause of job loss.</p>
            <p class="alt-lc-src">Source: Federal Reserve Bank of St. Louis, FRED; underlying data from the U.S. Bureau of
            Labor Statistics and the U.S. Employment and Training Administration. Public domain.
            <?php echo esc_html(alt_lc_fred_asof($alt_lc_fred)); ?></p>
        </figcaption>
    </figure>
<?php endif; ?>

<?php if (!empty($alt_lc_qwi_opts)) : ?>
    <?php $alt_lc_qwi_data = alt_lc_qwi_client($alt_lc_qwi); ?>
    <figure class="alt-chart-card alt-chart-card-wide alt-lc-panel" data-lc="qwi"
            data-qwi="<?php echo esc_attr(function_exists('wp_json_encode') ? wp_json_encode($alt_lc_qwi_data) : json_encode($alt_lc_qwi_data)); ?>">
        <div class="alt-chart-h" id="alt-lc-qwi-h">Hiring vs separations by state <span class="alt-chart-sub">quarterly, private employers, not seasonally adjusted</span></div>
        <div class="alt-lc-controls">
            <label for="alt-lc-qwi-state">State</label>
            <select id="alt-lc-qwi-state" class="alt-lc-select">
                <option value="">All states (sum)</option>
                <?php foreach ($alt_lc_qwi_opts['states'] as $alt_lc_k => $alt_lc_l) : ?>
                    <option value="<?php echo esc_attr($alt_lc_k); ?>"><?php echo esc_html($alt_lc_l); ?></option>
                <?php endforeach; ?>
            </select>
            <label for="alt-lc-qwi-ind">Industry sector</label>
            <select id="alt-lc-qwi-ind" class="alt-lc-select">
                <option value="">All sectors</option>
                <?php foreach ($alt_lc_qwi_opts['sectors'] as $alt_lc_k => $alt_lc_l) : ?>
                    <option value="<?php echo esc_attr($alt_lc_k); ?>"><?php echo esc_html($alt_lc_l); ?></option>
                <?php endforeach; ?>
            </select>
            <?php if ($alt_lc_qwi_opts['splits']) : ?>
            <label for="alt-lc-qwi-split">Split by</label>
            <select id="alt-lc-qwi-split" class="alt-lc-select">
                <option value="">No split</option>
                <?php foreach ($alt_lc_qwi_opts['splits'] as $alt_lc_k => $alt_lc_l) : ?>
                    <option value="<?php echo esc_attr($alt_lc_k); ?>"><?php echo esc_html($alt_lc_l); ?></option>
                <?php endforeach; ?>
            </select>
            <?php endif; ?>
        </div>
        <div class="alt-chart-box"><canvas id="alt-lc-qwi" role="img" aria-labelledby="alt-lc-qwi-h"></canvas></div>
        <figcaption>
            <p class="alt-lc-caption">Stable hires are people who started a job and stayed the full next quarter.
            <strong>Separations are all-cause</strong>: quits, layoffs, retirements and every other reason a job ended,
            so they are not a layoff count. With no split the chart shows each quarter; a split compares groups in the
            latest quarter and covers all sectors, because the Census Bureau publishes the groups across all industries
            only. Quarters are not seasonally adjusted, so compare a quarter with the same quarter a year earlier.</p>
            <p class="alt-lc-src">Source: U.S. Census Bureau, LEHD Quarterly Workforce Indicators, via the Census Data API.
            Public domain. This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.
            <?php echo esc_html(alt_lc_qwi_asof($alt_lc_qwi)); ?></p>
        </figcaption>
    </figure>
<?php endif; ?>
