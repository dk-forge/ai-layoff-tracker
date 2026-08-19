<?php
/**
 * The digest archive: the index, and one edition.
 *
 * Data comes from includes/digest-archive.php. Nothing here reads the live
 * database: an edition is what was published, and a page that re-derived its
 * figures today would disagree with the email people were sent, which is the
 * one failure mode this surface exists to prevent.
 *
 * The stored HTML is the composers' own email markup, which carries no colours
 * and no inline styles: it marks each line with data-alt and lets the renderer
 * decide. digest_layout.py turns those into inline email styles; here the
 * stylesheet below does the same job for a browser.
 */
if (!defined('ABSPATH')) exit;

$alt_ed = alt_edition_is_single_request() ? alt_edition_current() : null;
$alt_is_index = alt_edition_is_index_request();
if (!$alt_ed && !$alt_is_index) return;

$alt_stream_labels = array(
    'layoff'   => 'AI Layoff Tracker',
    'talent'   => 'Talent Intelligence Tracker',
    'articles' => 'From the blog',
);

alt_render_page_header();
?>
<style>
.alt-ed-wrap{max-width:760px;margin:0 auto;padding:0 16px}
.alt-ed-wrap h1{margin:.2em 0 .3em;line-height:1.2}
.alt-ed-eyebrow{text-transform:uppercase;letter-spacing:.08em;font-size:.75rem;color:#666;margin:0}
.alt-ed-meta{font-size:.9rem;color:#555;margin:.4em 0 1.4em}
.alt-ed-note{background:#f6f7f9;border-left:3px solid #c9cdd4;padding:12px 14px;font-size:.9rem;margin:0 0 1.4em}
.alt-ed-correction{background:#fff6e5;border-left:3px solid #d99b1c;padding:12px 14px;font-size:.92rem;margin:0 0 1.4em}
.alt-ed-correction p{margin:.3em 0}
.alt-ed-section{border-top:1px solid #e3e5e9;padding-top:20px;margin-top:28px}
.alt-ed-section table{width:100%;border-collapse:collapse}
.alt-ed-section td{vertical-align:top;padding:0 10px 10px 0;word-break:break-word}
.alt-ed-body{overflow-x:auto}
.alt-ed-section p[data-alt="stat-pair"]{font-size:1.9rem;font-weight:700;margin:.1em 0;line-height:1.1}
.alt-ed-section p[data-alt="kicker"]{text-transform:uppercase;letter-spacing:.06em;font-size:.72rem;color:#666;margin:0}
.alt-ed-section p[data-alt="unit"]{font-size:.85rem;color:#555;margin:0}
.alt-ed-section p[data-alt="change"]{font-size:.82rem;color:#555;margin:.2em 0 0}
.alt-ed-section p[data-alt="dateline"]{font-size:.82rem;color:#666;text-transform:none;margin:.2em 0 1em}
.alt-ed-section p[data-alt="note"],.alt-ed-section p[data-alt="scope"],.alt-ed-section p[data-alt="why"]{font-size:.9rem;color:#444}
.alt-ed-section p[data-alt="signature"]{font-size:1.15rem;font-weight:600}
.alt-ed-list{list-style:none;padding:0;margin:0 0 1.6em}
.alt-ed-list li{padding:6px 0;border-bottom:1px solid #eee;display:flex;flex-wrap:wrap;gap:8px;justify-content:space-between}
.alt-ed-list .alt-ed-when{color:#666;font-size:.85rem}
.alt-ed-days{margin:.2em 0 1.2em;line-height:2}
.alt-ed-days a{display:inline-block;min-width:2.2em;text-align:center;border:1px solid #dcdfe4;border-radius:4px;padding:1px 6px;margin:0 4px 4px 0;font-size:.85rem;text-decoration:none}
.alt-ed-nav{display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;margin:32px 0 8px;font-size:.92rem}
.alt-ed-withheld{color:#8a1c1c;font-size:.9rem}
.alt-ed-section td[data-alt^="figure"]{text-align:right;white-space:nowrap;padding-left:10px}
/* ONLY the two headline cells stack on a phone. The ranked lists are a
   label beside a figure, and stacking those puts every number on its own
   left-aligned line, which reads as a list of unrelated items. */
@media (max-width:520px){.alt-ed-section p[data-alt="stat-pair"]{font-size:1.5rem}
.alt-ed-section td[data-alt="pair-left"],.alt-ed-section td[data-alt="pair-right"]{display:block;width:100%!important;padding-right:0}
.alt-ed-wrap{padding:0 14px}}
</style>
<main class="alt-wrap alt-ed-wrap">
<?php if ($alt_ed) :
    $alt_all = alt_edition_all();
    list($alt_prev, $alt_next) = alt_edition_neighbours($alt_ed, $alt_all);
    $alt_url = alt_edition_url($alt_ed['freq'], $alt_ed['slug']);
?>
    <p class="alt-ed-eyebrow"><a href="<?php echo esc_url(alt_edition_index_url()); ?>">Digest archive</a>
        &middot; <?php echo $alt_ed['freq'] === 'weekly' ? 'Weekly edition' : 'Daily edition'; ?></p>
    <h1><?php echo esc_html(alt_edition_label($alt_ed)); ?></h1>
    <p class="alt-ed-meta">
        Covers <?php echo esc_html(alt_digest_date_range($alt_ed['window_from'], $alt_ed['window_to'])); ?>.
        <?php if ((string) $alt_ed['data_cut'] !== '') : ?>
            Figures as they stood at <?php echo esc_html($alt_ed['data_cut']); ?>.
        <?php endif; ?>
        Sent <?php echo esc_html(gmdate('j F Y', strtotime($alt_ed['published_at'] . ' UTC'))); ?>.
    </p>

    <?php if ($alt_ed['corrections']) : ?>
        <div class="alt-ed-correction">
            <p><strong>Correction<?php echo count($alt_ed['corrections']) === 1 ? '' : 's'; ?> to this edition</strong></p>
            <?php foreach ($alt_ed['corrections'] as $alt_c) : ?>
                <p><?php echo esc_html($alt_c['at']); ?>: <?php echo esc_html($alt_c['note']); ?></p>
            <?php endforeach; ?>
            <p>The text below is unchanged. It is what we published, and it stays that way.</p>
        </div>
    <?php endif; ?>

    <p class="alt-ed-note">This page is the edition exactly as it was composed and sent. The figures were
    read once, for the window above, and they have not been updated since. Filings and notices keep arriving,
    so the live tracker will now show larger numbers for the same window, and a correction can lower one.
    Every link below names the date basis it was counted on.</p>

    <?php foreach ($alt_stream_labels as $alt_key => $alt_label) :
        if (empty($alt_ed['sections'][$alt_key])) continue;
        $alt_s = $alt_ed['sections'][$alt_key]; ?>
        <section class="alt-ed-section" id="<?php echo esc_attr($alt_key); ?>">
            <div class="alt-ed-body"><?php echo alt_edition_render_section($alt_s['html']); ?></div>
        </section>
    <?php endforeach; ?>

    <div class="alt-ed-nav">
        <span><?php if ($alt_prev) : ?>&larr; <a href="<?php echo esc_url(alt_edition_url($alt_prev['freq'], $alt_prev['slug'])); ?>"><?php echo esc_html(alt_edition_label($alt_prev)); ?></a><?php endif; ?></span>
        <span><?php if ($alt_next) : ?><a href="<?php echo esc_url(alt_edition_url($alt_next['freq'], $alt_next['slug'])); ?>"><?php echo esc_html(alt_edition_label($alt_next)); ?></a> &rarr;<?php endif; ?></span>
    </div>

    <p><a href="<?php echo esc_url(alt_edition_index_url()); ?>">All archived editions</a>
       &middot; <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">Methodology</a>
       &middot; <a href="<?php echo esc_url(home_url('/contact/')); ?>">Submit a correction</a></p>

    <?php if (function_exists('alt_cite_box_html')) {
        echo alt_cite_box_html(alt_edition_label($alt_ed) . ' layoff digest', $alt_url);
    } ?>

<?php else :
    $alt_all = alt_edition_all();
    // Per stream, the editions that carried it. Weekly in full (about 52 a
    // year, each one worth a listing line); daily grouped by month, because a
    // year of them is 365 links and a flat list would bury the weeklies.
    $alt_by_stream = array();
    foreach ($alt_all as $alt_r) {
        foreach (array_keys($alt_stream_labels) as $alt_key) {
            if (!empty($alt_r['sections'][$alt_key])) $alt_by_stream[$alt_key][] = $alt_r;
        }
    }
?>
    <p class="alt-ed-eyebrow">Digest archive</p>
    <h1>Every edition we have emailed</h1>
    <p class="alt-ed-meta">Each edition is kept permanently at its own URL, exactly as it was sent. The figures
    in it were read once, for the window it names, and are never updated afterwards, so an edition is a dated
    record of what we published rather than a view of today's data. A revision attaches to an edition as a
    correction note; the original text is never rewritten.</p>

    <?php if (!$alt_all) : ?>
        <p>No edition has been archived yet. The archive fills from the moment a digest goes out.</p>
    <?php endif; ?>

    <?php foreach ($alt_stream_labels as $alt_key => $alt_label) :
        if (empty($alt_by_stream[$alt_key])) continue;
        $alt_weekly = array();
        $alt_daily = array();
        foreach ($alt_by_stream[$alt_key] as $alt_r) {
            if ($alt_r['freq'] === 'weekly') $alt_weekly[] = $alt_r;
            else $alt_daily[substr((string) $alt_r['window_to'], 0, 7)][] = $alt_r;
        }
    ?>
        <section class="alt-ed-section" id="stream-<?php echo esc_attr($alt_key); ?>">
            <h2><?php echo esc_html($alt_label); ?></h2>
            <?php if ($alt_weekly) : ?>
                <h3>Weekly editions</h3>
                <ul class="alt-ed-list">
                <?php foreach ($alt_weekly as $alt_r) : ?>
                    <li><a href="<?php echo esc_url(alt_edition_url($alt_r['freq'], $alt_r['slug']) . '#' . $alt_key); ?>"><?php echo esc_html(alt_edition_label($alt_r)); ?></a>
                    <span class="alt-ed-when"><?php echo esc_html($alt_r['slug']); ?></span></li>
                <?php endforeach; ?>
                </ul>
            <?php endif; ?>
            <?php if ($alt_daily) : ?>
                <h3>Daily editions</h3>
                <p class="alt-ed-meta">Kept permanently and linked from here, and deliberately left out of search
                results: a year of daily editions is several hundred near-identical pages, and crowding an index
                with those costs the pages worth finding.</p>
                <?php foreach ($alt_daily as $alt_month => $alt_rows) : ?>
                    <p class="alt-ed-days"><strong><?php echo esc_html(gmdate('F Y', strtotime($alt_month . '-01 UTC'))); ?></strong><br>
                    <?php foreach ($alt_rows as $alt_r) : ?>
                        <a href="<?php echo esc_url(alt_edition_url($alt_r['freq'], $alt_r['slug']) . '#' . $alt_key); ?>"
                           title="<?php echo esc_attr(alt_edition_label($alt_r)); ?>"><?php echo esc_html((int) substr((string) $alt_r['slug'], 8, 2)); ?></a>
                    <?php endforeach; ?>
                    </p>
                <?php endforeach; ?>
            <?php endif; ?>
        </section>
    <?php endforeach; ?>

    <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">Back to the live tracker</a>
       &middot; <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">Methodology</a></p>

    <?php if (function_exists('alt_digest_placement')) echo alt_digest_placement('editions'); ?>
<?php endif; ?>
</main>
<?php alt_render_page_footer(); ?>
