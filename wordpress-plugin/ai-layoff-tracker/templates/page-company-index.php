<?php
/**
 * The employer browse index: the hub at /company-layoffs/ and its A-Z letter
 * pages. Data and routing are prepared by includes/company-index.php.
 *
 * Nothing here is written copy about any employer, and no number on this page
 * is estimated. Every count is the count of pages actually linked below it, so
 * a letter with four employers says four and shows four.
 *
 * A LIST, not a table, for the reason the company pages are: the hard bar on
 * this project is no horizontal bleed at 375px, and a list wraps.
 */
if (!defined('ABSPATH')) exit;
$alt_cur = alt_company_index_current();
if ($alt_cur === '') return;
$alt_counts = alt_company_index_counts();
$alt_total = array_sum($alt_counts);
alt_render_page_header();

/** The A-Z strip, rendered on both views. A bucket with nothing in it is plain text, not a link to an empty page. */
// Guarded because a template is not a library: this file renders more than
// once per request on some paths, and a second `function` statement is a FATAL,
// not a warning. tests/test_no_unguarded_template_functions.py holds the rule.
if (!function_exists('alt_company_index_strip')) {
function alt_company_index_strip($current, array $counts) {
    echo '<nav class="alt-company-index-strip" aria-label="Employers A to Z">';
    foreach (alt_company_index_buckets() as $b) {
        $label = ($b === '0-9') ? '0-9' : strtoupper($b);
        $n = (int) ($counts[$b] ?? 0);
        if ($n === 0) {
            echo '<span class="alt-company-index-letter is-empty">' . esc_html($label) . '</span>';
        } elseif ($b === $current) {
            echo '<span class="alt-company-index-letter is-current" aria-current="page">' . esc_html($label) . '</span>';
        } else {
            echo '<a class="alt-company-index-letter" href="' . esc_url(alt_company_index_url($b)) . '">' . esc_html($label) . '</a>';
        }
    }
    echo '</nav>';
}
}
?>
<main class="alt-wrap alt-company-index">
<?php if ($alt_cur === 'hub') : ?>

    <p class="alt-eyebrow">Source-linked company records</p>
    <h1>Layoffs by employer</h1>

    <p class="alt-company-index-lede">
        <strong><?php echo number_format($alt_total); ?></strong> employers have a page here, each listing that
        employer's recorded layoff entries with the filing, WARN notice or named report behind every one.
        Pick a letter to browse them, or search a name in the
        <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">full tracker</a>.
    </p>

    <?php alt_company_index_strip('', $alt_counts); ?>

    <ul class="alt-company-index-buckets">
    <?php foreach (alt_company_index_buckets() as $alt_b) :
        $alt_n = (int) ($alt_counts[$alt_b] ?? 0);
        if ($alt_n === 0) continue; ?>
        <li>
            <a href="<?php echo esc_url(alt_company_index_url($alt_b)); ?>"><?php
                echo esc_html($alt_b === '0-9' ? '0-9' : strtoupper($alt_b)); ?></a>
            <span class="alt-company-index-count"><?php echo number_format($alt_n); ?>
                employer<?php echo $alt_n === 1 ? '' : 's'; ?></span>
        </li>
    <?php endforeach; ?>
    </ul>

    <p class="alt-company-index-note">
        An employer reaches this index once we hold at least
        <?php echo (int) alt_company_directory_indexable_floor(); ?> source-linked entries for it. Employers
        below that keep a page for direct citation. They stay out of here and out of search results,
        because at one entry the page repeats what the entry itself already says.
    </p>

<?php else :
    $alt_entries = alt_company_index_entries($alt_cur);
    $alt_n = count($alt_entries);
    $alt_label = ($alt_cur === '0-9') ? '0-9' : strtoupper($alt_cur);
?>
    <p class="alt-eyebrow"><a href="<?php echo esc_url(alt_company_index_url()); ?>">Layoffs by employer</a></p>
    <h1>Employers: <?php echo esc_html($alt_label); ?></h1>

    <p class="alt-company-index-lede">
        <strong><?php echo number_format($alt_n); ?></strong> employer<?php echo $alt_n === 1 ? '' : 's'; ?>
        <?php echo $alt_cur === '0-9' ? 'whose name starts with a number' : 'starting with ' . esc_html($alt_label); ?>,
        each with source-linked layoff records.
    </p>

    <?php alt_company_index_strip($alt_cur, $alt_counts); ?>

    <ul class="alt-company-index-list">
    <?php foreach ($alt_entries as $alt_e) : ?>
        <li><a href="<?php echo esc_url($alt_e['url']); ?>"><?php
            echo esc_html($alt_e['name'] !== '' ? $alt_e['name'] : $alt_e['slug']); ?></a></li>
    <?php endforeach; ?>
    </ul>

    <p><a href="<?php echo esc_url(alt_company_index_url()); ?>">All employers, A to Z</a></p>
<?php endif; ?>

    <p>See the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">tracker methodology</a>
    and <a href="<?php echo esc_url(home_url('/contact/')); ?>">submit a correction</a>.</p>
</main>
<?php alt_render_page_footer(); ?>
