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
 * PURE. Jobs in one calendar year from an alt_timeline_by_year() list.
 */
function alt_seo_year_jobs($timeline, $year) {
    $n = 0;
    foreach ((array) $timeline as $row) {
        if ((int) ($row['year'] ?? 0) === (int) $year) $n += max(0, (int) ($row['jobs'] ?? 0));
    }
    return $n;
}

/**
 * The year phrase and the job figure that may sit next to it (2.20.293).
 * Rule: a year in the title or description is only ever followed by THAT
 * year's count. So the current year appears only when this year's jobs (YTD)
 * are above zero, paired with the YTD figure; otherwise the all-time total is
 * worded as "since <first year>". Returns [head, jobs phrase, is_ytd].
 */
function alt_seo_layoff_parts($name, $last_date, $jobs, $now_ts, $ytd_jobs, $first_date) {
    $now_year = (int) gmdate('Y', (int) $now_ts);
    $latest = (int) substr((string) $last_date, 0, 4);
    $first = (int) substr((string) $first_date, 0, 4);
    $ytd = (int) $ytd_jobs; $jobs = (int) $jobs;
    if ($latest >= $now_year && $ytd > 0) {
        return array($name . ' layoffs ' . $now_year, number_format($ytd) . ' jobs cut so far', true);
    }
    $all = $jobs > 0 ? number_format($jobs) . ' jobs cut' . ($first > 0 ? ' since ' . $first : '') : '';
    if ($latest > 0 && $latest < $now_year) return array($name . ' layoffs: ' . $latest . ' and history', $all, false);
    return array($name . ' layoffs', $all, false);
}

/**
 * The title, at most 60 characters. Tightens in steps; every step still
 * leads with "<name> layoffs".
 */
function alt_seo_layoff_title($name, $last_date, $jobs, $has_warn, $now_ts, $ytd_jobs = 0, $first_date = '') {
    list($head, $cut, $current) = alt_seo_layoff_parts($name, $last_date, $jobs, $now_ts, $ytd_jobs, $first_date);
    $month = alt_seo_latest_month($last_date, $now_ts);
    $docs = $has_warn ? 'WARN notices and timeline' : 'dates and timeline';
    $sep = strpos($head, ':') === false ? ': ' : ', ';
    $cands = array();
    if ($cut !== '' && $month !== '' && $current) $cands[] = $head . $sep . $cut . ', latest ' . $month;
    if ($cut !== '') $cands[] = $head . $sep . $cut;
    if ($cut !== '' && !$current) $cands[] = $name . ' layoffs: ' . $cut;
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
 * All-time figures always carry "since <first year>" or no year at all.
 */
function alt_seo_layoff_description($name, $count, $jobs, $last_date, $has_warn, $ai_events, $now_ts, $scope = '', $ytd_jobs = 0, $first_date = '') {
    $count = (int) $count; $jobs = (int) $jobs;
    list($head, $cut, $current) = alt_seo_layoff_parts($name, $last_date, $jobs, $now_ts, $ytd_jobs, $first_date);
    $month = alt_seo_latest_month($last_date, $now_ts);
    $first = (int) substr((string) $first_date, 0, 4);
    $since = $first > 0 ? ' since ' . $first : '';
    $layoffs = $count > 0 ? number_format($count) . ' recorded ' . ($count === 1 ? 'layoff' : 'layoffs') . $scope : '';
    $sep = strpos($head, ':') === false ? ': ' : '. ';
    if ($current) {
        $lead = $head . ': ' . $cut . ($month !== '' ? ', latest ' . $month : '') . '.';
        if ($layoffs !== '') {
            $lead .= ' ' . ($jobs > 0 ? number_format($jobs) . ' jobs across ' : '') . $layoffs . $since . ' in total.';
        }
    } else {
        $facts = trim($cut . ($cut !== '' && $layoffs !== '' ? ' across ' : '') . $layoffs
               . ($cut === '' && $layoffs !== '' ? $since : ''));
        $lead = $head . ($facts !== '' ? $sep . ucfirst($facts) : '') . ($month !== '' ? ', latest ' . $month : '') . '.';
    }
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
