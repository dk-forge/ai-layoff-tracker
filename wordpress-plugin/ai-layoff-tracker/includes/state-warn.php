<?php
if (!defined('ABSPATH')) exit;

/**
 * THIS YEAR'S WARN NOTICES ON A US STATE PAGE (2.20.234).
 *
 * The 2026-10-12 scored comparison found the state pages invisible for the
 * query a reader actually types, "<state> warn notices 2026": the page was
 * titled "Layoffs in <state>" and showed an all-time record. This module adds
 * the year view that query asks for: notices and jobs by month, the employers
 * and the cities behind them, a table of the latest notices, and an FAQ whose
 * answers are computed from the same rows (and emitted as FAQPage JSON-LD only
 * because the identical Q&A is visible on the page).
 *
 * POPULATION. The state page's own (sourced, superset-deduped) WHERE, narrowed
 * to WARN notices dated in the current year by the tracker's date basis (the
 * date the cuts take effect). Nothing is estimated: a state with no WARN
 * notice this year returns null and the page keeps its generic copy.
 *
 * CITY. There is no city column. warn.py writes the city a state published
 * into the notice's excerpt ("Layoff at X in <city>. N employees affected"),
 * so the city is read back from exactly that sentence. A notice without one
 * is simply not in the city list; nothing is guessed from the employer.
 */

/** The city a WARN notice's excerpt names, or ''. Pure. */
function alt_state_warn_city($excerpt) {
    $excerpt = trim((string) $excerpt);
    if (!preg_match('/^\S.* at .+ in (.+?)\.\s+[\d,]+ employees affected/u', $excerpt, $m)) return '';
    $city = trim(preg_replace('/\s+/u', ' ', $m[1]));
    if ($city === '' || mb_strlen($city) > 80) return '';
    // An unbalanced bracket means the " in " sat inside the company name
    // ("Acme (Store in Los Angeles)"), not before a city warn.py wrote.
    if (substr_count($city, '(') !== substr_count($city, ')')) return '';
    return $city;
}

/** Notices and jobs per month (YYYY-MM), oldest first. Pure. */
function alt_state_warn_months(array $rows) {
    $out = array();
    foreach ($rows as $r) {
        $m = substr((string) ($r['layoff_date'] ?? ''), 0, 7);
        if (!preg_match('/^\d{4}-\d{2}$/', $m)) continue;
        if (!isset($out[$m])) $out[$m] = array('month' => $m, 'notices' => 0, 'jobs' => 0);
        $out[$m]['notices']++;
        $out[$m]['jobs'] += max(0, (int) ($r['job_count'] ?? 0));
    }
    ksort($out);
    return array_values($out);
}

/** Group rows on a label, ranked by jobs then notices then name. Pure. */
function alt_state_warn_rank(array $groups, $limit) {
    $groups = array_values($groups);
    usort($groups, function ($a, $b) {
        if ($a['jobs'] !== $b['jobs']) return $b['jobs'] - $a['jobs'];
        if ($a['notices'] !== $b['notices']) return $b['notices'] - $a['notices'];
        return strcmp((string) reset($a), (string) reset($b));
    });
    return array_slice($groups, 0, max(0, (int) $limit));
}

/** Employers this year, by jobs. Pure. */
function alt_state_warn_employers(array $rows, $limit) {
    $g = array();
    foreach ($rows as $r) {
        $name = trim((string) ($r['company'] ?? ''));
        if ($name === '') continue;
        $k = mb_strtolower($name);
        if (!isset($g[$k])) $g[$k] = array('name' => $name, 'notices' => 0, 'jobs' => 0);
        $g[$k]['notices']++;
        $g[$k]['jobs'] += max(0, (int) ($r['job_count'] ?? 0));
    }
    return alt_state_warn_rank($g, $limit);
}

/** Cities this year, by jobs, folded on case. Pure. */
function alt_state_warn_cities(array $rows, $limit) {
    $g = array();
    foreach ($rows as $r) {
        $city = alt_state_warn_city($r['excerpt'] ?? '');
        if ($city === '') continue;
        $k = mb_strtolower($city);
        if (!isset($g[$k])) {
            // A state that publishes in capitals ("AUSTIN") reads as a name.
            $label = ($city === mb_strtoupper($city)) ? mb_convert_case($city, MB_CASE_TITLE) : $city;
            $g[$k] = array('city' => $label, 'notices' => 0, 'jobs' => 0);
        }
        $g[$k]['notices']++;
        $g[$k]['jobs'] += max(0, (int) ($r['job_count'] ?? 0));
    }
    return alt_state_warn_rank($g, $limit);
}

/**
 * Question/answer pairs, every number read from $s. Pure. Empty with no
 * notices: an FAQ answering "0" would be a page about nothing.
 */
function alt_state_warn_faq($display, array $s) {
    $n = (int) ($s['notices'] ?? 0);
    if ($n < 1) return array();
    $y = (int) ($s['year'] ?? 0);
    $display = (string) $display;
    $jobs = number_format((int) ($s['jobs'] ?? 0));
    $faq = array();
    $faq[] = array(
        'q' => "How many WARN notices have been filed in $display in $y?",
        'a' => "We hold " . number_format($n) . ($n === 1 ? " WARN notice" : " WARN notices")
             . " for $display dated in $y so far, covering $jobs jobs. Every entry on this page links to the notice the state published."
             . (!empty($s['latest']) ? " The most recent is dated " . $s['latest'] . "." : ''),
    );
    if (!empty($s['employers'])) {
        $names = array();
        foreach (array_slice($s['employers'], 0, 3) as $e) {
            $names[] = $e['name'] . ' (' . number_format((int) $e['jobs']) . ' jobs)';
        }
        $faq[] = array(
            'q' => "Which employers filed the largest WARN notices in $display in $y?",
            'a' => 'By jobs covered: ' . implode(', ', $names) . '.',
        );
    }
    if (!empty($s['cities'])) {
        $names = array();
        foreach (array_slice($s['cities'], 0, 3) as $c) {
            $names[] = $c['city'] . ' (' . number_format((int) $c['jobs']) . ' jobs)';
        }
        $faq[] = array(
            'q' => "Which cities in $display have the most WARN layoffs in $y?",
            'a' => 'By jobs covered, as the notices name the location: ' . implode(', ', $names) . '.',
        );
    }
    $faq[] = array(
        'q' => "What is a WARN notice?",
        'a' => 'The federal WARN Act requires covered US employers to give 60 days of written notice before a plant closing or mass layoff. States publish the notices they receive, and some set lower thresholds of their own.',
    );
    return $faq;
}

/**
 * Everything the year block renders, or null. Cached with the facet data
 * (the caller's transient is keyed on alt_data_ver).
 */
function alt_state_warn_data($state_code) {
    global $wpdb;
    $state_code = strtoupper((string) $state_code);
    if (!preg_match('/^[A-Z]{2}$/', $state_code)) return null;
    $today = function_exists('alt_site_today') ? alt_site_today() : gmdate('Y-m-d');
    $year = (int) substr($today, 0, 4);

    $r = new WP_REST_Request('GET');
    $r->set_query_params(array(
        'state' => $state_code, 'sourced' => '1', 'exclude_supersets' => '1',
        'sources' => 'warn', 'from' => $year . '-01-01', 'to' => $year . '-12-31',
    ));
    list($where, $params) = alt_db_where($r);
    $table = alt_db_table();
    $rows = $wpdb->get_results(alt_db_prep(
        "SELECT company, job_count, layoff_date, announcement_date, excerpt
         FROM $table WHERE $where AND superset_of = 0
         ORDER BY layoff_date DESC, id DESC LIMIT 20000", $params), ARRAY_A);
    if (!$rows) return null;

    $jobs = 0;
    foreach ($rows as $row) $jobs += max(0, (int) $row['job_count']);
    $employers = alt_state_warn_employers($rows, 10);
    foreach ($employers as $i => $e) {
        $employers[$i]['url'] = function_exists('alt_company_directory_url_for_company')
            ? alt_company_directory_url_for_company($e['name']) : '';
    }

    // Latest notices: newest FILING first where the state published a filing
    // date, otherwise the effective date, and never a notice still in the future
    // ahead of one already filed.
    $latest = $rows;
    usort($latest, function ($a, $b) {
        $ka = (string) ($a['announcement_date'] ?: $a['layoff_date']);
        $kb = (string) ($b['announcement_date'] ?: $b['layoff_date']);
        return strcmp($kb, $ka);
    });
    $recent = array();
    foreach (array_slice($latest, 0, 25) as $row) {
        $recent[] = array(
            'company'   => (string) $row['company'],
            'url'       => function_exists('alt_company_directory_url_for_company')
                           ? alt_company_directory_url_for_company((string) $row['company']) : '',
            'filed'     => (string) ($row['announcement_date'] ?? ''),
            'effective' => (string) ($row['layoff_date'] ?? ''),
            'city'      => alt_state_warn_city($row['excerpt'] ?? ''),
            'jobs'      => (int) $row['job_count'],
        );
    }

    return array(
        'year'      => $year,
        'notices'   => count($rows),
        'jobs'      => $jobs,
        'months'    => alt_state_warn_months($rows),
        'employers' => $employers,
        'cities'    => alt_state_warn_cities($rows, 10),
        'recent'    => $recent,
        'latest'    => $recent ? ($recent[0]['filed'] ?: $recent[0]['effective']) : '',
        'capped'    => count($rows) >= 20000,
    );
}

/** FAQPage JSON-LD for an indexable state page, from the visible FAQ only. */
function alt_state_warn_schema() {
    if (!function_exists('alt_facet_current')) return;
    $data = alt_facet_current();
    if (!$data || $data['dim'] !== 'state' || empty($data['indexable']) || empty($data['warn'])) return;
    $faq = alt_state_warn_faq($data['display'], $data['warn']);
    if (!$faq) return;
    $node = array('@context' => 'https://schema.org', '@type' => 'FAQPage', 'mainEntity' => array());
    foreach ($faq as $qa) {
        $node['mainEntity'][] = array(
            '@type' => 'Question', 'name' => $qa['q'],
            'acceptedAnswer' => array('@type' => 'Answer', 'text' => $qa['a']),
        );
    }
    echo '<script type="application/ld+json">' . wp_json_encode($node, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) . "</script>\n";
}
add_action('wp_head', 'alt_state_warn_schema', 23);
