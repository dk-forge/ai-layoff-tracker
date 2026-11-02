<?php
/**
 * PURE. SERP titles and meta descriptions for the company and industry pages
 * (2.20.292). Search Console, 2026-11-02: these pages rank 8 to 18 at 0.6 to
 * 1.2% CTR under titles like "SALLIE MAE layoffs 2008-2020: dates and job
 * counts": a stale year range, an ALL-CAPS name and legal suffixes. The new
 * shape leads with the query a searcher types ("<Company> layoffs <year>"),
 * and when the latest record is older than this year it says so plainly
 * ("<Company> layoffs: <year> and history") rather than claiming this year.
 *
 * No WordPress calls in here, so tests run these under the bare php CLI.
 */
if (!defined('ABSPATH') && !defined('ALT_SEO_TITLES_TEST')) exit;

/** Short all-caps words that are acronyms, not shouting. */
function alt_seo_name_acronyms() {
    return array('AI', 'AMC', 'AT&T', 'BMW', 'BNY', 'CBS', 'CVS', 'DHL', 'GE', 'GM', 'HP', 'HPE', 'HSBC',
                 'IBM', 'ING', 'KPMG', 'LG', 'NBC', 'NCR', 'PNC', 'PWC', 'RTX', 'SAP', 'UBS', 'UPS', 'US',
                 'USA', 'UK', 'USAA', 'TD', 'AMD', 'ADP', 'AIG', 'BP', 'EY', 'HCA', 'IT', 'NYC');
}

/** Legal suffixes dropped for display (the canonical slug is untouched). */
function alt_seo_legal_suffix_pattern() {
    return '/[\s,]+(?:l\.?l\.?c|l\.?l\.?p|l\.?p|inc|incorporated|corp|corporation|co|ltd|limited|plc'
         . '|gmbh|ag|s\.?a|n\.?v|b\.?v|pllc|pc)\.?$/i';
}

/**
 * "SALLIE MAE" -> "Sallie Mae", "Innodata Services, LLC" -> "Innodata
 * Services", "Safelite Glass Corp." -> "Safelite Glass". A name already in
 * mixed case keeps its casing (it was typed that way on purpose: "eBay").
 */
function alt_seo_display_name($raw) {
    $name = trim(preg_replace('/\s+/u', ' ', (string) $raw));
    for ($i = 0; $i < 3; $i++) {
        $next = trim(preg_replace(alt_seo_legal_suffix_pattern(), '', $name), " ,");
        if ($next === '' || $next === $name) break;
        $name = $next;
    }
    if ($name === '' || preg_match('/\p{Ll}/u', $name)) return $name;
    $acr = alt_seo_name_acronyms();
    $words = explode(' ', $name);
    foreach ($words as $i => $w) {
        $bare = trim($w, '.,()');
        if (in_array($bare, $acr, true) || preg_match('/\d/', $bare)
            || (mb_strlen($bare, 'UTF-8') <= 4 && !preg_match('/[AEIOUY]/u', $bare))) continue;
        $words[$i] = preg_replace_callback('/(^|[\s\-\/&\'(])(\p{L})(\p{L}*)/u', function ($m) {
            return $m[1] . $m[2] . mb_strtolower($m[3], 'UTF-8');
        }, $w);
    }
    return implode(' ', $words);
}

/** "Mar 2026" for a Y-m-d date that is not in the future, else ''. */
function alt_seo_latest_month($last_date, $now_ts) {
    if (!preg_match('/^\d{4}-\d{2}-\d{2}/', (string) $last_date)) return '';
    $ts = strtotime(substr((string) $last_date, 0, 10) . ' 00:00:00 UTC');
    if (!$ts || $ts > (int) $now_ts) return '';
    return gmdate('M Y', $ts);
}

/**
 * The year phrase. The current year when the latest record is this year (or a
 * notice dated ahead of today), else "<latest year> and history". '' when the
 * page has no dated record at all.
 */
function alt_seo_layoff_head($name, $last_date, $now_ts) {
    $now_year = (int) gmdate('Y', (int) $now_ts);
    $latest = (int) substr((string) $last_date, 0, 4);
    if ($latest <= 0) return array($name . ' layoffs', false);
    if ($latest >= $now_year) return array($name . ' layoffs ' . $now_year, true);
    return array($name . ' layoffs: ' . $latest . ' and history', false);
}

/**
 * The title, at most 60 characters. Tightens in steps; every step still
 * leads with "<name> layoffs".
 */
function alt_seo_layoff_title($name, $last_date, $jobs, $has_warn, $now_ts) {
    list($head, $current) = alt_seo_layoff_head($name, $last_date, $now_ts);
    $jobs = (int) $jobs;
    $cut = $jobs > 0 ? number_format($jobs) . ' jobs cut' : '';
    $month = alt_seo_latest_month($last_date, $now_ts);
    $docs = $has_warn ? 'WARN notices and timeline' : 'dates and timeline';
    $sep = ($current || strpos($head, ':') === false) ? ': ' : ', ';
    $cands = array();
    if ($cut !== '' && $month !== '' && $current) $cands[] = $head . $sep . $cut . ', latest ' . $month;
    if ($cut !== '') $cands[] = $head . $sep . $cut;
    $cands[] = $head . $sep . $docs;
    $cands[] = $head;
    foreach ($cands as $c) {
        if (mb_strlen($c, 'UTF-8') <= 60) return $c;
    }
    $short = $name . ' layoffs';
    return mb_strlen($short, 'UTF-8') <= 60 ? $short : rtrim(mb_substr($name, 0, 52, 'UTF-8')) . ' layoffs';
}

/**
 * The meta description, at most 155 characters, built only from what the
 * page shows: a figure that is missing is left out, never printed as zero.
 */
function alt_seo_layoff_description($name, $count, $jobs, $last_date, $has_warn, $ai_events, $now_ts, $scope = '') {
    $count = (int) $count; $jobs = (int) $jobs;
    list($head) = alt_seo_layoff_head($name, $last_date, $now_ts);
    $month = alt_seo_latest_month($last_date, $now_ts);
    $facts = array();
    if ($jobs > 0) $facts[] = number_format($jobs) . ' jobs cut';
    if ($count > 0) $facts[] = ($facts ? 'across ' : '') . number_format($count) . ' recorded ' . ($count === 1 ? 'layoff' : 'layoffs') . $scope;
    $lead = $head . ($facts ? (strpos($head, ':') === false ? ': ' : '. ') . ucfirst(implode(' ', $facts)) : '');
    if ($month !== '') $lead .= ', latest ' . $month;
    $lead .= '.';
    $ai = (int) $ai_events > 0 ? ' ' . number_format((int) $ai_events) . ' attributed to AI by the employer.' : '';
    $tails = array(
        ' See dates, ' . ($has_warn ? 'WARN notices' : 'job counts') . ' and a year-by-year timeline, each linked to its source.',
        ' Dates, ' . ($has_warn ? 'WARN notices' : 'job counts') . ' and timeline, each with its source.',
        ' Every entry links to its source.',
        '',
    );
    foreach (array($ai, '') as $a) {
        foreach ($tails as $t) {
            $c = $lead . $a . $t;
            if (mb_strlen($c, 'UTF-8') <= 155) return $c;
        }
    }
    return mb_substr($lead, 0, 155, 'UTF-8');
}
