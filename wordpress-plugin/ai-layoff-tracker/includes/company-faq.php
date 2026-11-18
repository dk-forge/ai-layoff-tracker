<?php
/**
 * Two-question FAQ on every indexable company page, with FAQPage JSON-LD built
 * from exactly the visible text (CGO SEO/GEO pass 2026-11-18).
 *
 * Why: company pages take most of the site's Google clicks ("linde layoffs",
 * "allstate job cuts", "pipedrive layoffs" in the 2026-11-16 Search Console
 * report) but carried no question-and-answer text an AI answer can quote.
 *
 * Rules, pinned by railway/tests/test_company_faq.py:
 *  - every figure, date and link comes from the rows the page already lists
 *    (alt_company_directory_data); nothing is typed or estimated;
 *  - a job count of 0 (not stated in the source) drops its clause;
 *  - each answer names the date of the latest record and links its source;
 *  - the JSON-LD strings are the visible strings, printed in the same block,
 *    and only on a page offered to the index.
 */
if (!defined('ABSPATH')) exit;

/** PURE. "12 March 2026" from a Y-m-d date, or '' when unreadable. */
function alt_company_faq_date($ymd) {
    $d = substr((string) $ymd, 0, 10);
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $d, $m) || !checkdate((int) $m[2], (int) $m[3], (int) $m[1])) return '';
    $months = array('January','February','March','April','May','June','July','August','September','October','November','December');
    return (int) $m[3] . ' ' . $months[(int) $m[2] - 1] . ' ' . $m[1];
}

/**
 * PURE. The two questions and answers, or array() when there is nothing to say.
 * $events: rows with layoff_date, job_count and sources[0]['url'|'name'].
 * Answers are plain text; the source link is returned separately per item.
 */
function alt_company_faq_items($name, array $events, $year) {
    $name = trim((string) $name);
    $year = (int) $year;
    if ($name === '' || !$events || $year < 2000) return array();
    $n_year = 0; $jobs_year = 0; $total = 0; $first = ''; $latest = null;
    foreach ($events as $e) {
        $d = substr((string) ($e['layoff_date'] ?? ''), 0, 10);
        $j = max(0, (int) ($e['job_count'] ?? 0));
        $total += $j;
        if ($d !== '' && ($first === '' || $d < $first)) $first = $d;
        if ($d !== '' && ($latest === null || $d > substr((string) $latest['layoff_date'], 0, 10))) $latest = $e;
        if (substr($d, 0, 4) === (string) $year) { $n_year++; $jobs_year += $j; }
    }
    if ($latest === null) return array();
    $last_txt = alt_company_faq_date($latest['layoff_date']);
    $src = (array) (($latest['sources'] ?? array())[0] ?? array());
    $link = array('url' => (string) ($src['url'] ?? ''), 'name' => trim((string) ($src['name'] ?? '')));
    $src_txt = $link['name'] !== '' ? ' (source: ' . $link['name'] . ')' : '';
    $count = function ($n, $one, $many) { return number_format($n) . ' ' . ($n === 1 ? $one : $many); };

    if ($n_year > 0) {
        $a1 = sprintf('Yes. The tracker lists %s at %s in %d', $count($n_year, 'layoff record', 'layoff records'), $name, $year);
        if ($jobs_year > 0) $a1 .= sprintf(', covering %s', $count($jobs_year, 'job', 'jobs'));
        $a1 .= sprintf('. The latest is dated %s%s.', $last_txt, $src_txt);
    } else {
        $a1 = sprintf('The tracker has no %d layoff record for %s. The latest record is dated %s%s.', $year, $name, $last_txt, $src_txt);
    }
    $n_all = count($events);
    $a2 = sprintf('The tracker lists %s for %s', $count($n_all, 'layoff record', 'layoff records'), $name);
    if ($first !== '') $a2 .= ' since ' . alt_company_faq_date($first);
    if ($total > 0) $a2 .= sprintf(', with %s cut where the source states a number', $count($total, 'job', 'jobs'));
    $a2 .= '. Every record on this page links to the notice, filing or report it comes from.';

    return array(
        array('q' => sprintf('Did %s have layoffs in %d?', $name, $year), 'a' => $a1, 'link' => $link),
        array('q' => sprintf('How many layoffs has %s had?', $name), 'a' => $a2, 'link' => array('url' => '', 'name' => '')),
    );
}

/** PURE. Visible FAQ plus its FAQPage JSON-LD, from the same strings. */
function alt_company_faq_html(array $items) {
    if (!$items) return '';
    $out = '<section class="alt-company-faq"><h2>Questions about these layoffs</h2>';
    $main = array();
    foreach ($items as $it) {
        $a = esc_html($it['a']);
        if (!empty($it['link']['url'])) $a .= ' <a href="' . esc_url($it['link']['url']) . '" rel="nofollow noopener">Read the source</a>.';
        $out .= '<h3>' . esc_html($it['q']) . '</h3><p>' . $a . '</p>';
        $main[] = array('@type' => 'Question', 'name' => $it['q'],
                        'acceptedAnswer' => array('@type' => 'Answer', 'text' => $it['a']));
    }
    $ld = array('@context' => 'https://schema.org', '@type' => 'FAQPage', 'mainEntity' => $main);
    $out .= '<script type="application/ld+json">' . wp_json_encode($ld, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) . '</script>';
    return $out . '</section>';
}

/** Runtime: the block for the current company page, only when indexable. */
function alt_company_faq_block($data) {
    if (!is_array($data) || empty($data['indexable']) || !function_exists('alt_company_directory_name')) return '';
    return alt_company_faq_html(alt_company_faq_items(alt_company_directory_name($data), (array) $data['events'], (int) gmdate('Y')));
}
