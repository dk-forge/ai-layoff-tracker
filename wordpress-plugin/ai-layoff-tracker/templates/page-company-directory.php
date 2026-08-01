<?php
/**
 * Source-linked company page; data is prepared by company-directory.php.
 *
 * Deliberately a LIST and not a table. The hard formatting bar on this project
 * is no horizontal bleed at 375px, and a 6-column table of dates, counts,
 * locations and source links either overflows or needs its own scroll container
 * that hides half the columns from a phone. A list wraps.
 *
 * Nothing here is written copy about the employer. Every sentence is assembled
 * from fields the row actually carries, and a field that is absent produces no
 * sentence rather than a hedge, so a three-event company reads as a short
 * honest page instead of a padded one.
 */
if (!defined('ABSPATH')) exit;
$alt_dir = alt_company_directory_current();
if (!$alt_dir) return;
alt_render_page_header();
$alt_company = $alt_dir['company'];
$alt_name = $alt_company['display_name'];
$alt_count = count($alt_dir['events']);
$alt_verif = array(
    'gold'   => 'SEC filing',
    'warn'   => 'State WARN notice',
    'silver' => 'Press release',
    'bronze' => 'News report',
);
?>
<main class="alt-wrap alt-company-directory">
    <p class="alt-eyebrow">Source-linked company record</p>
    <h1><?php echo esc_html($alt_name); ?> layoffs</h1>

    <p class="alt-company-summary">
        This page lists <?php echo (int) $alt_count; ?> recorded layoff event<?php echo $alt_count === 1 ? '' : 's'; ?>
        <?php if ($alt_dir['first_date'] !== '' && $alt_dir['last_date'] !== '') :
            $alt_from = substr($alt_dir['first_date'], 0, 4);
            $alt_to = substr($alt_dir['last_date'], 0, 4);
            echo $alt_from === $alt_to ? 'in ' . esc_html($alt_from) : 'from ' . esc_html($alt_from) . ' to ' . esc_html($alt_to);
        endif; ?>, each with its original source. It is a record of what we have
        verified, not a complete employment history for this employer.
    </p>

    <?php if (!$alt_dir['indexable']) : ?>
        <p class="alt-directory-notice">This record is published for direct research and citation, and is
        kept out of search results: with
        <?php echo (int) $alt_count; ?> recorded event<?php echo $alt_count === 1 ? '' : 's'; ?> it repeats what the
        individual entry below already says. Pages reach search results at
        <?php echo (int) alt_company_directory_indexable_floor(); ?> or more source-linked events.</p>
    <?php endif; ?>

    <?php if (!empty($alt_dir['truncated'])) : ?>
        <p class="alt-directory-notice">Showing the <?php echo (int) $alt_count; ?> most recent of
        <?php echo number_format((int) $alt_dir['total_known']); ?> recorded events for this employer.
        <a href="<?php echo esc_url($alt_dir['tracker_url']); ?>">See all of them in the tracker</a>.</p>
    <?php endif; ?>

    <p class="alt-company-directory-total">
        <strong><?php echo number_format((int) $alt_dir['total_jobs']); ?></strong> jobs across the recorded
        layoff events, each linked to a source
        <?php if ((int) $alt_dir['ai_events'] > 0) : ?>
            <br><strong><?php echo (int) $alt_dir['ai_events']; ?></strong>
            of these <?php echo $alt_dir['ai_events'] === 1 ? 'is an event the employer' : 'are events the employer'; ?>
            attributed to AI in its own words
        <?php endif; ?>
    </p>

    <p><a href="<?php echo esc_url($alt_dir['tracker_url']); ?>">Search this company name in the full tracker</a></p>

    <ol class="alt-company-event-list">
    <?php foreach ($alt_dir['events'] as $alt_event) :
        $alt_jobs = (int) $alt_event['job_count'];
        $alt_loc = function_exists('alt_short_location')
            ? alt_short_location($alt_event['state'] ?? '', $alt_event['country'] ?? '') : '';
        $alt_level = $alt_verif[$alt_event['verification_level'] ?? ''] ?? '';
    ?>
        <li>
            <h2>
                <?php echo esc_html($alt_event['layoff_date'] ?: 'Date not stated'); ?>
                <?php if ($alt_jobs > 0) : ?>&middot; <?php echo number_format($alt_jobs); ?> jobs<?php endif; ?>
            </h2>

            <p class="alt-company-event-meta">
                <?php echo !empty($alt_event['announced'])
                    ? 'Announcement-stage record.'
                    : 'Filed or independently reported record.'; ?>
                <?php if ($alt_loc !== '') : ?>Location: <?php echo esc_html($alt_loc); ?>.<?php endif; ?>
                <?php if (!empty($alt_event['industry'])) : ?>Industry: <?php echo esc_html($alt_event['industry']); ?>.<?php endif; ?>
                <?php if ($alt_level !== '') : ?>Evidence: <?php echo esc_html($alt_level); ?>.<?php endif; ?>
                <?php // The name on THIS filing, when the employer files under a variant of
                      // the page's name. Shown rather than smoothed over, so a reader can
                      // see why these rows are grouped together.
                      $alt_row_name = trim((string) ($alt_event['company_name'] ?? ''));
                      if ($alt_row_name !== '' && strcasecmp($alt_row_name, $alt_name) !== 0) : ?>
                    Filed as: <?php echo esc_html($alt_row_name); ?>.
                <?php endif; ?>
            </p>

            <?php if (!empty($alt_event['ai_explicit'])) : ?>
                <p class="alt-company-event-ai">The employer attributed this to AI.</p>
                <?php if (!empty($alt_event['ai_language'])) : ?>
                    <blockquote class="alt-company-event-quote">&ldquo;<?php echo esc_html($alt_event['ai_language']); ?>&rdquo;</blockquote>
                <?php endif; ?>
            <?php elseif (($alt_event['ai_causation'] ?? '') === 'explicitly_denied') : ?>
                <p class="alt-company-event-ai">The employer explicitly denied AI was a cause.</p>
            <?php endif; ?>

            <ul class="alt-company-source-list">
            <?php
            // Two WARN links on one event is NORMAL, not a duplicate: a state
            // publishes a rolling data file and a landing page, and we cite
            // both. They were rendering as the same words followed by the same
            // sentence, so Boeing's first event showed "CA WARN notice
            // (official WARN list; ...)" twice and read as a bug. Name what
            // each link actually opens, and say the shared explanation once.
            ?>
            <?php foreach ($alt_event['sources'] as $alt_source) : ?>
                <?php
                $alt_is_warn = $alt_source['type'] === 'warn';
                $alt_warn_kind = '';
                if ($alt_is_warn) {
                    $alt_warn_kind = preg_match('/\.(xlsx?|csv|pdf)(\?|$)/i', $alt_source['url'])
                        ? ' (data file)'
                        : ' (state page)';
                }
                ?>
                <li><a href="<?php echo esc_url($alt_source['url']); ?>" target="_blank" rel="noopener nofollow"><?php
                    echo esc_html($alt_source['name'] ?: 'Cited source') . $alt_warn_kind; ?></a></li>
            <?php endforeach; ?>
            <?php // The entry's own permalink. These pages existed but were linked from
                  // nowhere on the site (audit item 2: 1,798 orphans); this is the link
                  // that puts them back on a crawlable path.
                  if (!empty($alt_event['permalink'])) : ?>
                <li><a href="<?php echo esc_url($alt_event['permalink']); ?>">Full entry on this site</a></li>
            <?php endif; ?>
            </ul>
        </li>
    <?php endforeach; ?>
    </ol>
    <?php
    // Said ONCE, not once per event. Boeing has 321 events and nearly all of
    // them cite a WARN notice, so the per-event version printed this sentence
    // 316 times and added ~28KB to a page that is already the longest on the
    // site. A note that repeats 316 times is not read 316 times.
    $alt_has_warn = false;
    foreach ($alt_dir['events'] as $alt_e) {
        foreach ($alt_e['sources'] as $alt_s) {
            if (($alt_s['type'] ?? '') === 'warn') { $alt_has_warn = true; break 2; }
        }
    }
    if ($alt_has_warn) : ?>
    <p class="alt-company-source-note">A state page link goes to that state's
    official WARN list and a data file link goes to the file it publishes. The
    notice was filed at that source; older notices roll into the state archive.</p>
    <?php endif; ?>

    <?php if (!empty($alt_dir['facet_links'])) : ?>
        <p class="alt-company-facet-links">Browse the wider record:
        <?php $alt_parts = array();
              foreach ($alt_dir['facet_links'] as $alt_fl) {
                  $alt_parts[] = '<a href="' . esc_url($alt_fl['url']) . '">' . esc_html($alt_fl['display']) . '</a>';
              }
              echo implode(', ', $alt_parts); // already escaped above ?>.</p>
    <?php endif; ?>

    <p>See the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/#alt-metric-definitions')); ?>">tracker methodology</a>
    and <a href="<?php echo esc_url(home_url('/contact/')); ?>">submit a correction</a>.</p>
</main>
<?php alt_render_page_footer(); ?>
