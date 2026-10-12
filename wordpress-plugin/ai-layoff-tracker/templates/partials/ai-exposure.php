<?php
/**
 * AI exposure by job and city (includes/ai-exposure.php). Server-rendered;
 * assets/ai-exposure.js redraws only the metro panel from data-ax-metros.
 * Hidden by the caller when no data is stored.
 */
if (!defined('ABSPATH')) exit;
if (empty($alt_ax) || empty($alt_ax['most'])) return;
$alt_ax_study = 'Eloundou et al., "GPTs are GPTs" (Science, 2024)';
$alt_ax_asof = alt_ax_asof($alt_ax_doc);
$alt_ax_t = alt_ax_pct($alt_ax['threshold']);
$alt_ax_credit = 'Sources: exposure scores from ' . $alt_ax_study . ', data at github.com/openai/GPTs-are-GPTs (MIT licence); '
    . 'occupation titles from the O*NET Database by USDOL/ETA, used under CC BY 4.0; employment and median annual wage from '
    . 'U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics; 10-year projected change from U.S. Bureau '
    . 'of Labor Statistics, Employment Projections.';
$alt_ax_rows = function ($list) use ($alt_ax) {
    foreach ($list as $o) {
        $q = alt_ax_quadrant($o, $alt_ax['threshold']);
        echo '<tr><td data-k="Occupation"><b>' . esc_html($o['title']) . '</b></td>'
            . '<td data-k="Exposure" class="alt-ax-n">' . esc_html(alt_ax_pct($o['exposure'])) . '</td>'
            . '<td data-k="Employed" class="alt-ax-n">' . esc_html(alt_ax_num($o['emp'])) . '</td>'
            . '<td data-k="Median wage" class="alt-ax-n">' . esc_html(alt_ax_wage($o['wage'])) . '</td>'
            . '<td data-k="10-year change" class="alt-ax-n">' . esc_html(alt_ax_growth($o['growth'])) . '</td>'
            . '<td data-k="Quadrant"><span class="alt-ax-tag" data-q="' . esc_attr($q) . '">' . esc_html(alt_ax_quadrant_label($q)) . '</span></td></tr>';
    }
};
$alt_ax_first = $alt_ax['metros'] ? reset($alt_ax['metros']) : null;
$alt_ax_json = function_exists('wp_json_encode') ? wp_json_encode($alt_ax['metros']) : json_encode($alt_ax['metros']);
?>
<section class="alt-ax" id="ai-exposure" aria-labelledby="alt-ax-h">
    <h2 id="alt-ax-h">AI exposure by job and city</h2>
    <p class="alt-ax-intro">Exposure here means the share of a job's tasks that an AI system could speed up, per
    <?php echo esc_html($alt_ax_study); ?>. It is not a measure of jobs lost or a forecast that they will be: a job can be
    highly exposed and still be projected to grow. Jobs at or above <?php echo esc_html($alt_ax_t); ?> count as highly exposed.
    None of this is part of our layoff counts.</p>

    <figure class="alt-ax-card" data-ax="lists">
        <h3>Most exposed occupations</h3>
        <div class="alt-ax-table-wrap"><table class="alt-ax-table">
            <thead><tr><th>Occupation</th><th>Exposure</th><th>Employed</th><th>Median wage</th><th>10-year change</th><th>Quadrant</th></tr></thead>
            <tbody><?php $alt_ax_rows($alt_ax['most']); ?></tbody>
        </table></div>
        <h3>Least exposed occupations</h3>
        <div class="alt-ax-table-wrap"><table class="alt-ax-table">
            <thead><tr><th>Occupation</th><th>Exposure</th><th>Employed</th><th>Median wage</th><th>10-year change</th><th>Quadrant</th></tr></thead>
            <tbody><?php $alt_ax_rows($alt_ax['least']); ?></tbody>
        </table></div>
        <figcaption>
            <p class="alt-lc-caption">Occupations with at least <?php echo esc_html(alt_ax_num(ALT_AX_MIN_EMPLOYMENT)); ?> people
            employed nationally. Exposure is the study's GPT-4 rated measure: the share of tasks an AI system could speed up by
            half or more, counting tasks that need extra software at half weight. The 10-year change is the BLS projection for
            the whole occupation from every cause.</p>
            <p class="alt-lc-src"><?php echo esc_html($alt_ax_credit . ' ' . $alt_ax_asof); ?></p>
        </figcaption>
    </figure>

    <figure class="alt-ax-card" data-ax="quadrant">
        <h3>Exposed and shrinking, or exposed but growing</h3>
        <div class="alt-ax-quad" role="list">
            <?php foreach (array('exposed-shrinking', 'exposed-growing', 'less-shrinking', 'less-growing') as $alt_ax_q) :
                $alt_ax_v = $alt_ax['quadrants'][$alt_ax_q]; ?>
                <div class="alt-ax-q" role="listitem" data-q="<?php echo esc_attr($alt_ax_q); ?>">
                    <p class="alt-ax-q-h"><?php echo esc_html(alt_ax_quadrant_label($alt_ax_q)); ?></p>
                    <p class="alt-ax-q-n"><?php echo esc_html(alt_ax_num($alt_ax_v['n']) . ' occupations, ' . alt_ax_num($alt_ax_v['emp']) . ' people'); ?></p>
                    <?php if ($alt_ax_v['top']) : ?>
                        <p class="alt-ax-q-eg">Largest: <?php echo esc_html(implode(', ', array_map(function ($o) { return $o['title']; }, $alt_ax_v['top']))); ?></p>
                    <?php endif; ?>
                </div>
            <?php endforeach; ?>
        </div>
        <figcaption>
            <p class="alt-lc-caption">Across = exposure (highly exposed at <?php echo esc_html($alt_ax_t); ?> or more); down = the BLS
            10-year projection (shrinking means a projected fall). Being in the exposed and shrinking box does not mean AI is the
            reason: BLS projections weigh every cause.</p>
            <p class="alt-lc-src"><?php echo esc_html($alt_ax_credit . ' ' . $alt_ax_asof); ?></p>
        </figcaption>
    </figure>

    <?php if ($alt_ax_first) : ?>
    <figure class="alt-ax-card" data-ax="metro" data-ax-metros="<?php echo esc_attr($alt_ax_json); ?>">
        <h3 id="alt-ax-metro-h">Highly exposed jobs by metro area</h3>
        <div class="alt-lc-controls">
            <label for="alt-ax-metro">Metro area</label>
            <select id="alt-ax-metro" class="alt-lc-select">
                <?php foreach ($alt_ax['metros'] as $alt_ax_k => $alt_ax_m) : ?>
                    <option value="<?php echo esc_attr($alt_ax_k); ?>"><?php echo esc_html($alt_ax_m['title']); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="alt-ax-metro-out" aria-live="polite">
            <p class="alt-ax-metro-sum"><b class="alt-ax-big"><?php echo esc_html(alt_ax_num($alt_ax_first['exposed'])); ?></b>
            <span>people work in highly exposed occupations in <span class="alt-ax-mt"><?php echo esc_html($alt_ax_first['title']); ?></span>,
            <span class="alt-ax-share"><?php echo esc_html(alt_ax_pct($alt_ax_first['exposed'] / $alt_ax_first['total'])); ?></span> of the
            <span class="alt-ax-tot"><?php echo esc_html(alt_ax_num($alt_ax_first['total'])); ?></span> jobs counted there.</span></p>
            <ol class="alt-ax-jobs">
                <?php foreach ($alt_ax_first['jobs'] as $alt_ax_j) : ?>
                    <li><span><?php echo esc_html($alt_ax_j[0]); ?></span> <span class="alt-ax-n"><?php echo esc_html(alt_ax_num($alt_ax_j[1]) . ' (' . $alt_ax_j[2] . ' exposure)'); ?></span></li>
                <?php endforeach; ?>
            </ol>
        </div>
        <figcaption>
            <p class="alt-lc-caption">The <?php echo esc_html(count($alt_ax['metros'])); ?> largest metro areas by employment. The total
            is a floor: BLS withholds some metro counts. Highly exposed jobs are where AI could speed up many tasks, not jobs
            that are going away.</p>
            <p class="alt-lc-src"><?php echo esc_html($alt_ax_credit . ' ' . $alt_ax_asof); ?></p>
        </figcaption>
    </figure>
    <?php endif; ?>
</section>
