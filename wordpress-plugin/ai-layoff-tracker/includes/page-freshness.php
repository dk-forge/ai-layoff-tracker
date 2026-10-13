<?php
/**
 * "Last updated <date> · <N> sources" for company and facet pages, and the
 * matching dateModified + CSV distribution on their Dataset nodes.
 *
 * The date is alt_last_write: when the database last changed, the same stamp
 * the Sources and Press pages print. It is not the page's newest event date,
 * which would read as stale on a quiet employer even while the data is current.
 * The source count is distinct source URLs actually linked on the page, so the
 * number a reader sees is the number of links they can click.
 */

/** Distinct, non-empty source URLs across a page's events. Pure. */
function alt_page_source_count(array $events) {
    $seen = array();
    foreach ($events as $e) {
        foreach ((array) ($e['sources'] ?? array()) as $s) {
            $u = trim((string) ($s['url'] ?? ''));
            if ($u !== '') $seen[$u] = true;
        }
    }
    return count($seen);
}

/** The visible line, or '' when there is nothing sourced to describe. */
function alt_page_freshness_html(array $events) {
    $n = alt_page_source_count($events);
    if ($n < 1) return '';
    $lu = function_exists('alt_data_last_updated_label') ? alt_data_last_updated_label() : '';
    $parts = array();
    if ($lu !== '') $parts[] = 'Last updated ' . esc_html($lu);
    $parts[] = number_format($n) . ' ' . ($n === 1 ? 'source' : 'sources');
    return '<p class="alt-muted alt-page-freshness">' . implode(' · ', $parts) . '</p>';
}

/** Schema fields shared by the company and facet Dataset nodes. */
function alt_page_dataset_freshness() {
    $ts = (int) get_option('alt_last_write', 0);
    return array(
        'dateModified' => gmdate('Y-m-d', $ts > 0 ? $ts : time()),
        'distribution' => array(
            array('@type' => 'DataDownload', 'encodingFormat' => 'text/csv',
                  'contentUrl' => admin_url('admin-post.php?action=alt_export_csv')),
        ),
    );
}
