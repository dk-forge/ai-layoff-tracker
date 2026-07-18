<?php
/** Source-linked company-directory page; data is prepared by company-directory.php. */
if (!defined('ABSPATH')) exit;
$alt_company_directory = alt_company_directory_current();
if (!$alt_company_directory) return;
get_header(); $alt_company = $alt_company_directory['company'];
?>
<main class="alt-wrap alt-company-directory">
    <p class="alt-eyebrow">Source-linked company record</p>
    <h1><?php echo esc_html($alt_company['display_name']); ?> layoffs</h1>
    <p class="alt-company-summary">This page lists <?php echo count($alt_company_directory['events']); ?> canonical event<?php echo count($alt_company_directory['events']) === 1 ? '' : 's'; ?> with retained cited source<?php echo count($alt_company_directory['events']) === 1 ? '' : 's'; ?>. It is not a complete employment history.</p>
    <?php if (!$alt_company_directory['indexable']) : ?><p class="alt-directory-notice">This reviewed record is available for direct research but is not indexed as a directory page because it does not yet meet the minimum source-linked event threshold.</p><?php endif; ?>
    <p class="alt-company-directory-total"><strong><?php echo number_format((int) $alt_company_directory['total_jobs']); ?></strong> source-linked jobs across retained canonical events</p>
    <p><a href="<?php echo esc_url($alt_company_directory['tracker_url']); ?>">Search this company name in the full tracker</a></p>
    <ol class="alt-company-event-list">
    <?php foreach ($alt_company_directory['events'] as $event) : ?>
        <li><h2><?php echo esc_html($event['layoff_date'] ?: 'Date not stated'); ?> · <?php echo number_format((int) $event['job_count']); ?> jobs</h2>
            <p><?php echo $event['announced'] ? 'Announcement-stage record.' : 'Filed or independently reported record.'; ?><?php echo $event['country'] ? ' Affected-job location: ' . esc_html($event['country']) . ($event['state'] ? ' (' . esc_html($event['state']) . ')' : '') . '.' : ''; ?></p>
            <ul class="alt-company-source-list"><?php foreach ($event['sources'] as $source) : ?><li><a href="<?php echo esc_url($source['url']); ?>" target="_blank" rel="noopener nofollow"><?php echo esc_html($source['name'] ?: 'Cited source'); ?></a><?php echo $source['type'] === 'warn' ? ' (official WARN list; notice may be a row in the list)' : ''; ?></li><?php endforeach; ?></ul>
        </li>
    <?php endforeach; ?>
    </ol>
    <p>See the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/#alt-metric-definitions')); ?>">tracker methodology</a> and <a href="<?php echo esc_url(home_url('/contact/')); ?>">submit a correction</a>.</p>
</main>
<?php get_footer(); ?>
