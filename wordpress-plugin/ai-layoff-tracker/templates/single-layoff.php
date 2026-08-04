<?php
/** Single layoff entry page, /blog/layoff/{company}-{date}. */
if (!defined('ABSPATH')) exit;

get_header();

$id = get_the_ID();
$e  = function_exists('alt_entry_to_array') ? alt_entry_to_array($id) : array();

$verif_labels = array('gold' => 'SEC filing', 'silver' => 'Press release', 'bronze' => 'News');
$verif = $verif_labels[$e['verification_level'] ?? ''] ?? 'News';
$src_url = esc_url_raw($e['source_url'] ?? '');   // esc_url_raw drops javascript:/data:
// home_url() ALREADY ends in /blog (WP_SITE_URL is https://asktherecruiter.com/blog),
// so passing '/blog/...' here built /blog/blog/... and sent the main internal
// link on roughly 1,800 entry pages through a 301. Every other call in the
// plugin passes the path without the /blog prefix; this was the only one left.
$tracker = home_url('/ai-layoff-tracker/');
$cite = sprintf(
    'AI Layoff Tracker, AskTheRecruiter.com. "%s, %s jobs (%s)." Retrieved %s. Primary source: %s.',
    $e['company_name'] ?? '',
    number_format_i18n((int) ($e['job_count'] ?? 0)),
    $e['layoff_date'] ?: 'date unknown',
    gmdate('M j, Y'),
    $e['source_name'] ?: 'see link'
);
?>
<div class="alt-wrap alt-single">
    <a class="alt-back" href="<?php echo esc_url($tracker); ?>">← All layoffs</a>

    <h1 class="alt-single-title">
        <?php echo esc_html($e['company_name'] ?? get_the_title()); ?>
        <?php if (!empty($e['ticker'])) : ?><span class="alt-ticker"><?php echo esc_html($e['ticker']); ?></span><?php endif; ?>
    </h1>
    <div class="alt-single-stat"><?php echo esc_html(number_format_i18n((int) ($e['job_count'] ?? 0))); ?> jobs cut &middot; <?php echo esc_html($e['layoff_date'] ?: 'date unknown'); ?></div>

    <div class="alt-single-meta">
        <?php if (!empty($e['industry'])) : ?><span><b>Industry:</b> <?php echo esc_html($e['industry']); ?></span><?php endif; ?>
        <?php if (!empty($e['country'])) : ?><span><b>Country:</b> <?php echo esc_html($e['country']); ?></span><?php endif; ?>
        <?php if (!empty($e['roles'])) : ?><span><b>Roles:</b> <?php echo esc_html($e['roles']); ?></span><?php endif; ?>
        <span><b>Source type:</b> <span class="alt-badge alt-badge-<?php echo esc_attr($e['verification_level'] ?? 'bronze'); ?>"><?php echo esc_html($verif); ?></span></span>
        <?php if (!empty($e['ai_explicit'])) : ?><span class="alt-ai-yes">AI-attributed</span><?php endif; ?>
    </div>

    <?php if (!empty($e['ai_explicit']) && !empty($e['ai_language'])) : ?>
    <div class="alt-single-block alt-detail-quote">
        <span class="alt-detail-h">Where AI is cited</span>
        <blockquote>&ldquo;<?php echo esc_html($e['ai_language']); ?>&rdquo;</blockquote>
    </div>
    <?php endif; ?>

    <?php if (!empty($e['excerpt'])) : ?>
    <div class="alt-single-block">
        <span class="alt-detail-h">From the source</span>
        <p><?php echo esc_html($e['excerpt']); ?></p>
    </div>
    <?php endif; ?>

    <?php if ($src_url !== '') : ?>
    <p><a class="alt-btn alt-btn-primary" href="<?php echo esc_url($src_url); ?>" target="_blank" rel="noopener nofollow">View primary source (<?php echo esc_html($e['source_name'] ?: 'source'); ?>) &#8599;</a></p>
    <?php
    // The source's permanent Wayback copy, or an honest note carrying the real
    // date of the next automatic archive check — the same state the tracker
    // cards, company pages and facet pages show (alt_archive_note_html()).
    if (function_exists('alt_archive_lookup') && function_exists('alt_archive_note_html')) {
        $alt_arec = alt_archive_lookup($src_url);
        $alt_arch = alt_archive_note_html(array(
            'source_url'          => $src_url,
            'archived_url'        => is_array($alt_arec) && ($alt_arec['status'] ?? '') === 'archived'
                                        ? (string) ($alt_arec['archived_url'] ?? '') : '',
            'archive_status'      => is_array($alt_arec) ? (string) ($alt_arec['status'] ?? 'queued') : 'queued',
            'archive_checked_at'  => is_array($alt_arec) ? (string) ($alt_arec['checked_at'] ?? '') : '',
        ));
        if ($alt_arch !== '') echo '<p class="alt-single-archive">' . $alt_arch . '</p>';
    }
    ?>
    <?php endif; ?>

    <?php
    // Link up to the employer's page when one exists. These entry permalinks
    // were indexable and linked from nowhere (audit item 2), so a crawler that
    // found one had no path onward and a reader had no way to see the rest of
    // that employer's record. function_exists is the FTP-deploy race guard.
    $company_page = function_exists('alt_company_directory_url_for_company')
        ? alt_company_directory_url_for_company($e['company_name'] ?? '') : '';
    if ($company_page !== '') : ?>
    <p class="alt-company-entry-link">
        See every recorded layoff for
        <a href="<?php echo esc_url($company_page); ?>"><?php echo esc_html($e['company_name']); ?></a>.
    </p>
    <?php endif; ?>

    <div class="alt-single-block alt-cite">
        <span class="alt-detail-h">Cite this entry</span>
        <code><?php echo esc_html($cite); ?></code>
    </div>
</div>
<?php
get_footer();
