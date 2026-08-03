<?php
/**
 * Country / US state / industry page; data is prepared by facet-pages.php.
 *
 * A LIST and not a table, for the reason page-company-directory.php gives: the
 * hard bar on this project is no horizontal bleed at 375px, and a table of
 * dates, counts, employers and source links either overflows or hides half its
 * columns behind a scroller on a phone.
 *
 * Every sentence is assembled from fields the data actually carries. A facet
 * with no AI-attributed event prints no AI sentence rather than a zero, and a
 * dimension with no breakdown to show prints no empty heading.
 */
if (!defined('ABSPATH')) exit;
$alt_f = alt_facet_current();
if (!$alt_f) return;
alt_render_page_header();
$alt_dims = alt_facet_dimensions();
$alt_meta = $alt_dims[$alt_f['dim']];
$alt_verif = array(
    'gold'   => 'SEC filing',
    'warn'   => 'State WARN notice',
    'silver' => 'Press release',
    'bronze' => 'News report',
);
$alt_bd_titles = array(
    'industry' => 'Industries affected here',
    'state'    => 'US states affected here',
    'country'  => 'Countries affected here',
);
?>
<main class="alt-wrap alt-facet-page">
    <p class="alt-eyebrow">Source-linked <?php echo esc_html($alt_meta['noun']); ?> record</p>
    <h1><?php echo esc_html(alt_facet_heading($alt_f)); ?></h1>

    <p class="alt-facet-summary">
        This page lists every layoff event we hold
        <?php echo $alt_f['dim'] === 'industry'
            ? 'for the ' . esc_html($alt_f['display']) . ' sector'
            : 'for ' . esc_html(alt_facet_phrase($alt_f['dim'], $alt_f['display'])); ?>
        that still links to its original source. It is a record of what we have verified,
        not a complete count of layoffs
        <?php echo $alt_f['dim'] === 'industry' ? 'in this sector' : 'in this ' . esc_html($alt_meta['noun']); ?>.
    </p>

    <?php if (!$alt_f['indexable']) : ?>
        <p class="alt-directory-notice">This record is published for direct research and citation, and is
        kept out of search results: with <?php echo number_format((int) $alt_f['entries']); ?> recorded
        event<?php echo $alt_f['entries'] === 1 ? '' : 's'; ?> it repeats what the individual entries and
        company pages already say. Pages reach search results at
        <?php echo (int) alt_facet_indexable_floor(); ?> or more source-linked events.</p>
    <?php endif; ?>

    <?php // One block per statistic, not <br>-separated lines. The figure is set
          // much larger than the label, so a <br> layout sets an outsized
          // line-height for the whole run and a label that wraps leaves its tail
          // stranded on a line of its own, reading as a separate item. ?>
    <div class="alt-facet-total">
        <p><strong><?php echo number_format((int) $alt_f['entries']); ?></strong> recorded events</p>
        <?php if ((int) $alt_f['jobs'] > 0) : ?>
            <p><strong><?php echo number_format((int) $alt_f['jobs']); ?></strong> jobs across
            <?php echo number_format((int) $alt_f['companies']); ?>
            <?php echo (int) $alt_f['companies'] === 1 ? 'employer' : 'employers'; ?></p>
        <?php endif; ?>
        <?php if ((int) $alt_f['ai_entries'] > 0) : ?>
            <p><strong><?php echo number_format((int) $alt_f['ai_entries']); ?></strong>
            <?php echo $alt_f['ai_entries'] === 1 ? 'event the employer' : 'events the employer'; ?>
            attributed to AI in its own words</p>
        <?php endif; ?>
        <?php if ($alt_f['min_date'] !== '' && $alt_f['max_date'] !== '') : ?>
            <p class="alt-facet-total-range">Covering <?php echo esc_html(substr($alt_f['min_date'], 0, 4)); ?>
            to <?php echo esc_html(substr($alt_f['max_date'], 0, 4)); ?></p>
        <?php endif; ?>
    </div>

    <?php // The basis, said plainly, because the tracker's results list uses a
          // different one on purpose and a reader comparing the two numbers
          // deserves to know why they differ. ?>
    <p class="alt-facet-basis">
        <?php if ($alt_f['dim'] === 'country') : ?>
            Counted by where the jobs were located. The tracker's own results list
            additionally matches on employer headquarters, so it returns a slightly
            higher count for the same <?php echo esc_html($alt_meta['noun']); ?>.
        <?php elseif ($alt_f['dim'] === 'state') : ?>
            Counted by where the jobs were located. State is recorded from US WARN
            notices, so this covers United States records only.
        <?php else : ?>
            Counted by the industry recorded against each event, normalised to a fixed
            list of <?php echo (int) count(alt_facet_catalogue()['industry']); ?> sectors.
        <?php endif; ?>
        Rollup records and the per-site notices they absorb are counted once.
        <a href="<?php echo esc_url($alt_f['tracker_url']); ?>">Open this filter in the full tracker</a>.
    </p>

    <?php if ($alt_f['dim'] === 'country' || $alt_f['dim'] === 'state') : ?>
        <p class="alt-facet-jurisdiction-note">Definitions differ by jurisdiction:
        see <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/#m-jurisdictions')); ?>">what
        qualifies as a record for <?php echo esc_html($alt_f['display']); ?></a> before comparing
        this page&rsquo;s totals with another <?php echo esc_html($alt_meta['noun']); ?>&rsquo;s.</p>
    <?php endif; ?>

    <?php foreach ($alt_f['breakdowns'] as $alt_bd => $alt_rows) : ?>
        <h2><?php echo esc_html($alt_bd_titles[$alt_bd]); ?></h2>
        <ul class="alt-facet-links">
        <?php foreach ($alt_rows as $alt_row) : ?>
            <li><a href="<?php echo esc_url($alt_row['url']); ?>"><?php echo esc_html($alt_row['display']); ?></a>
                <span class="alt-facet-links-val"><?php echo number_format((int) $alt_row['jobs']); ?> jobs</span></li>
        <?php endforeach; ?>
        </ul>
    <?php endforeach; ?>

    <?php if ($alt_f['employers']) : ?>
        <h2>Employers with more than one recorded round here</h2>
        <?php // Rounds, not jobs. The underlying figure is computed row-level on
              // purpose so site-level filings are not lost, which means its job
              // total can include a row already folded into a rollup above. A
              // count of filings is the honest number to print beside a deduped
              // headline. ?>
        <ul class="alt-facet-links">
        <?php foreach ($alt_f['employers'] as $alt_emp) : ?>
            <li><a href="<?php echo esc_url($alt_emp['url']); ?>"><?php echo esc_html($alt_emp['name']); ?></a>
                <span class="alt-facet-links-val"><?php echo number_format((int) $alt_emp['rounds']); ?> recorded rounds</span></li>
        <?php endforeach; ?>
        </ul>
    <?php endif; ?>

    <h2>Recorded events</h2>
    <?php if ((int) $alt_f['entries'] > (int) $alt_f['shown']) : ?>
        <p class="alt-directory-notice">Showing the <?php echo number_format((int) $alt_f['shown']); ?> most
        recent of <?php echo number_format((int) $alt_f['entries']); ?> recorded events.
        <a href="<?php echo esc_url($alt_f['tracker_url']); ?>">See all of them in the tracker</a>.</p>
    <?php endif; ?>

    <ol class="alt-company-event-list">
    <?php foreach ($alt_f['events'] as $alt_event) :
        $alt_jobs = (int) $alt_event['job_count'];
        $alt_loc = function_exists('alt_short_location')
            ? alt_short_location($alt_event['state'] ?? '', $alt_event['country'] ?? '') : '';
        $alt_level = $alt_verif[$alt_event['verification_level'] ?? ''] ?? '';
        $alt_name = trim((string) ($alt_event['company_name'] ?? ''));
    ?>
        <li>
            <h3>
                <?php if ($alt_event['company_url'] !== '') : ?>
                    <a href="<?php echo esc_url($alt_event['company_url']); ?>"><?php echo esc_html($alt_name ?: 'Employer not stated'); ?></a>
                <?php else : ?>
                    <?php echo esc_html($alt_name ?: 'Employer not stated'); ?>
                <?php endif; ?>
                <?php if ($alt_jobs > 0) : ?>&middot; <?php echo number_format($alt_jobs); ?> jobs<?php endif; ?>
            </h3>

            <p class="alt-company-event-meta">
                <?php echo esc_html($alt_event['layoff_date'] ?: 'Date not stated'); ?>.
                <?php echo !empty($alt_event['announced'])
                    ? 'Announcement-stage record.'
                    : 'Filed or independently reported record.'; ?>
                <?php // Only when it ADDS something. On a state page every row is
                      // in that state, and on the Germany page alt_short_location()
                      // returns "Germany" for every row, so the line read
                      // "Location: Germany." 50 times. On the United States page it
                      // returns the state code, which is genuinely new information.
                      if ($alt_loc !== '' && $alt_f['dim'] !== 'state'
                          && strcasecmp($alt_loc, (string) $alt_f['display']) !== 0) : ?>Location: <?php echo esc_html($alt_loc); ?>.<?php endif; ?>
                <?php if (!empty($alt_event['industry']) && $alt_f['dim'] !== 'industry') : ?>Industry: <?php echo esc_html($alt_event['industry']); ?>.<?php endif; ?>
                <?php if ($alt_level !== '') : ?>Evidence: <?php echo esc_html($alt_level); ?>.<?php endif; ?>
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
            <?php foreach ($alt_event['sources'] as $alt_source) :
                // Name what each link opens. Two WARN links on one event is
                // normal (a state publishes a rolling data file and a landing
                // page) and identical wording on two different destinations
                // reads as a duplicated link, which is the defect 2.19.237 fixed
                // on the company pages.
                $alt_warn_kind = '';
                if ($alt_source['type'] === 'warn') {
                    $alt_warn_kind = preg_match('/\.(xlsx?|csv|pdf)(\?|$)/i', $alt_source['url'])
                        ? ' (data file)' : ' (state page)';
                }
            ?>
                <li><a href="<?php echo esc_url($alt_source['url']); ?>" target="_blank" rel="noopener nofollow"><?php
                    echo esc_html($alt_source['name'] ?: 'Cited source') . $alt_warn_kind; ?></a></li>
            <?php endforeach; ?>
            <?php // Wayback copy or honest next-check note, same as the company pages
                  // and the tracker cards (one helper, alt_archive_note_html()).
                  $alt_arch = function_exists('alt_archive_note_html') ? alt_archive_note_html($alt_event) : '';
                  if ($alt_arch !== '') : ?>
                <li><?php echo $alt_arch; // built from esc_url/esc_html above ?></li>
            <?php endif; ?>
            <?php if (!empty($alt_event['permalink'])) : ?>
                <li><a href="<?php echo esc_url($alt_event['permalink']); ?>">Full entry on this site</a></li>
            <?php endif; ?>
            </ul>
        </li>
    <?php endforeach; ?>
    </ol>

    <?php
    // Said once per page, not once per event: on the company pages the per-event
    // version printed this sentence 316 times and added ~28KB.
    $alt_has_warn = false;
    foreach ($alt_f['events'] as $alt_e) {
        foreach ($alt_e['sources'] as $alt_s) {
            if (($alt_s['type'] ?? '') === 'warn') { $alt_has_warn = true; break 2; }
        }
    }
    if ($alt_has_warn) : ?>
    <p class="alt-company-source-note">A state page link goes to that state's official
    WARN list and a data file link goes to the file it publishes. The notice was filed at
    that source; older notices roll into the state archive.</p>
    <?php endif; ?>

    <?php
    // Sibling navigation. Every indexable page of this dimension, so the set is
    // a connected mesh rather than a hundred pages reachable only from a
    // sitemap. Small enough to render whole: the largest dimension is under 50.
    $alt_siblings = alt_facet_index($alt_f['dim']);
    if (count($alt_siblings) > 1) : ?>
        <h2>Other <?php echo esc_html($alt_meta['plural']); ?></h2>
        <ul class="alt-facet-links alt-facet-siblings">
        <?php foreach ($alt_siblings as $alt_sib) :
            if ($alt_sib['value'] === $alt_f['value']) continue; ?>
            <li><a href="<?php echo esc_url($alt_sib['url']); ?>"><?php echo esc_html($alt_sib['display']); ?></a>
                <span class="alt-facet-links-val"><?php echo number_format((int) $alt_sib['events']); ?> events</span></li>
        <?php endforeach; ?>
        </ul>
    <?php endif; ?>

    <?php if ($alt_f['dim'] === 'state') : ?>
        <p><a href="<?php echo esc_url(alt_facet_url('country', 'United States')); ?>">All United States layoff records</a></p>
    <?php endif; ?>

    <p>See the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/#alt-metric-definitions')); ?>">tracker methodology</a>
    and <a href="<?php echo esc_url(home_url('/contact/')); ?>">submit a correction</a>.</p>
</main>
<?php alt_render_page_footer(); ?>
