<?php
/**
 * THE WEEKLY BRIEFING (owner request 2026-11-02): the weekly layoff edition as
 * a 3-5 minute read. Trustworthiness first, usefulness second, polish third.
 *
 * Three stages, each a pure function of the one before, so a test can drive
 * any of them from a fixture:
 *
 *   alt_briefing_fetch()    every /aggregate and /query read, in one place
 *   alt_briefing_model()    every figure, every sentence choice, and the
 *                           PRE-SEND CHECKS (alt_briefing_checks)
 *   alt_briefing_render()   HTML + text, which prints only what the model holds
 *
 * THE CHECKS CAN HOLD A CLAIM. A claim whose numbers do not reconcile is
 * omitted from the edition and logged (error_log and the model's `held` list),
 * never "corrected" in place and never sent. The rest of the edition still
 * goes out: one wrong line should cost that line, not the whole week.
 *
 * Every sentence below is a template filled from the data. Nothing here calls
 * a model, and a template whose evidence is absent prints nothing.
 *
 * Only the WEEKLY tier uses this; daily and monthly keep
 * alt_digest_compose_layoff. Switch: option `alt_digest_weekly_briefing`
 * ('0' turns it off and the weekly edition falls back to the old composer).
 */

if (!defined('ABSPATH')) exit;

/** A week is provisional while it has had fewer than this many days to settle. */
function alt_briefing_settle_days() {
    return 14;
}

/** A week above this multiple of the 8-week median gets an outlier note. */
function alt_briefing_outlier_factor() {
    return 3.0;
}

/**
 * Which tiers send the briefing. Option `alt_digest_briefing_tiers`, a comma
 * list; the default is all three tiers (owner approval 2026-11-02, "approve
 * all three"). `none` restores the old composer for every tier.
 */
function alt_briefing_enabled($freq) {
    $freq = strtolower(trim((string) $freq));
    $tiers = function_exists('get_option') ? (string) get_option('alt_digest_briefing_tiers', alt_briefing_default_tiers()) : alt_briefing_default_tiers();
    return in_array($freq, array_map('trim', explode(',', strtolower($tiers))), true);
}

/** The production default for alt_digest_briefing_tiers. */
function alt_briefing_default_tiers() {
    return 'daily,weekly,monthly';
}

/** The Monday on or before a date. */
function alt_briefing_monday($date) {
    $t = strtotime($date . ' 00:00:00 UTC');
    return gmdate('Y-m-d', $t - ((int) gmdate('N', $t) - 1) * DAY_IN_SECONDS);
}

/* ------------------------------------------------------------------ */
/* Fetch                                                              */
/* ------------------------------------------------------------------ */

function alt_briefing_get($route, $params) {
    $req = new WP_REST_Request('GET', $route);
    foreach ($params as $k => $v) $req->set_param($k, $v);
    $res = rest_do_request($req);
    if (!$res || $res->is_error()) return null;
    $data = $res->get_data();
    if (is_object($data)) $data = json_decode(wp_json_encode($data), true);
    return is_array($data) ? $data : null;
}

/**
 * Every read the briefing makes. The date basis is alt_digest_layoff_basis('query')
 * on every one of them, the same basis the links name.
 */
function alt_briefing_fetch($from, $to, $kind = 'weekly') {
    $basis = alt_digest_layoff_basis('query');
    $period = alt_briefing_get('/layoffs/v1/aggregate', array(
        'from' => $from, 'to' => $to, 'date_basis' => $basis,
        'include' => 'leaders,top_countries,map_countries,top_industries,source_types,concentration,top_states',
    ));
    $rows = array();
    $rows_ok = true;
    for ($page = 1; $page <= 10; $page++) {
        $q = alt_briefing_get('/layoffs/v1/query', array(
            'from' => $from, 'to' => $to, 'date_basis' => $basis,
            'per_page' => 200, 'page' => $page,
        ));
        if (!is_array($q) || !isset($q['data'])) { $rows_ok = false; break; }
        foreach ((array) $q['data'] as $r) $rows[] = (array) $r;
        if (count($rows) >= (int) ($q['total'] ?? 0) || !$q['data']) break;
    }
    $ft = strtotime(alt_briefing_monday($to) . ' 00:00:00 UTC');
    $weeks = array();
    for ($k = ($kind === 'daily') ? -1 : 7; $k >= 0; $k--) {
        $w_from = gmdate('Y-m-d', $ft - 7 * $k * DAY_IN_SECONDS);
        $w_to = gmdate('Y-m-d', $ft - 7 * $k * DAY_IN_SECONDS + 6 * DAY_IN_SECONDS);
        if ($k === 0 && $kind === 'weekly') {
            $w = $period;
        } else {
            $w = alt_briefing_get('/layoffs/v1/aggregate', array(
                'from' => $w_from, 'to' => $w_to, 'date_basis' => $basis,
                'include' => 'concentration',
            ));
        }
        $weeks[] = array('from' => $w_from, 'to' => $w_to, 'data' => $w);
    }
    $ytd_from = substr($to, 0, 4) . '-01-01';
    $ytd = alt_briefing_get('/layoffs/v1/aggregate', array(
        'from' => $ytd_from, 'to' => $to, 'date_basis' => $basis,
        'include' => 'map_countries',
    ));
    $wtd = null;
    if ($kind === 'daily') {
        $wtd = alt_briefing_get('/layoffs/v1/aggregate', array(
            'from' => alt_briefing_monday($to), 'to' => $to, 'date_basis' => $basis,
            'include' => 'concentration'));
    }
    return array('from' => $from, 'to' => $to, 'period' => $period, 'kind' => $kind, 'wtd' => $wtd,
                 'rows' => $rows_ok ? $rows : null, 'weeks' => $weeks,
                 'ytd' => $ytd, 'ytd_from' => $ytd_from);
}

/* ------------------------------------------------------------------ */
/* Model                                                              */
/* ------------------------------------------------------------------ */

/** Verified jobs of an /aggregate payload: all minus the announced tier. */
function alt_briefing_verified($agg) {
    if (!is_array($agg) || !isset($agg['totals'])) return null;
    $t = (array) $agg['totals'];
    return max(0, (int) ($t['jobs'] ?? 0) - (int) ($t['announced_jobs'] ?? 0));
}

/** [label => verified jobs] out of a top_* / map_* tuple list, column [4]. */
function alt_briefing_tuples($list) {
    $out = array();
    foreach ((array) $list as $t) {
        $t = array_values((array) $t);
        $label = trim((string) ($t[0] ?? ''));
        $v = (int) ($t[4] ?? 0);
        if ($label === '' || $v <= 0) continue;
        $out[$label] = ($out[$label] ?? 0) + $v;
    }
    arsort($out);
    return $out;
}

/** Owner order (2026-11-02). Region rows print in this order and no other. */
function alt_briefing_region_order() {
    return array('North America', 'Europe', 'Asia-Pacific', 'Middle East',
                 'Latin America', 'Africa', 'Multiple countries', 'Other countries', 'Not recorded');
}

/**
 * Region rows for "at a glance": [region, jobs, sublines[]], regions with cuts
 * only, sublines summing to the region (owner 2026-11-02: US under North
 * America; UK and Netherlands under Europe when above zero, the rest as
 * "other Europe"). `Not recorded` is the verified total minus everything placed.
 */
function alt_briefing_regions($countries, $ver_jobs, $hq = array()) {
    $by = array();
    $sub = array();
    $hq_by = array();
    $placed = 0;
    foreach ($countries as $country => $jobs) {
        $placed += $jobs;
        $region = function_exists('alt_digest_world_region') ? alt_digest_world_region($country) : 'Other';
        // ONE DEFINITION OF "Multiple countries" (owner review 2026-11-13): the
        // region row carried "Multiple or other countries 13,148" beside Top
        // countries' "Multiple countries 11,748"; the 1,400 was Russia, which
        // the region table did not know. A row the table cannot place is now
        // its own "Other countries" row, so the shared label shares a figure.
        if ($region === 'Other') $region = ($country === 'Multiple countries') ? 'Multiple countries' : 'Other countries';
        $by[$region] = ($by[$region] ?? 0) + $jobs;
        $sub[$region][$country] = $jobs;
    }
    // PLACED BY EMPLOYER HQ (owner 2026-11-13): a verified row with no job
    // location but a known single-country employer_country goes to that
    // region as its own "by employer HQ" sub-line, so the bars still sum to
    // the worldwide figure and the HQ part is never passed off as location.
    foreach ((array) $hq as $country => $jobs) {
        $region = function_exists('alt_digest_world_region') ? alt_digest_world_region($country) : 'Other';
        if ($region === 'Other' || $jobs <= 0) continue;
        $by[$region] = ($by[$region] ?? 0) + $jobs;
        $hq_by[$region] = ($hq_by[$region] ?? 0) + $jobs;
        $placed += $jobs;
    }
    $unplaced = $ver_jobs - $placed;
    if ($unplaced > 0) $by['Not recorded'] = $unplaced;
    $out = array();
    foreach (alt_briefing_region_order() as $region) {
        if (empty($by[$region]) || $by[$region] <= 0) continue;
        $lines = array();
        $named = array();
        if ($region === 'North America') $named = array('United States' => 'US');
        if ($region === 'Europe') $named = array('United Kingdom' => 'UK', 'Netherlands' => 'Netherlands');
        $by_hq = (int) ($hq_by[$region] ?? 0);
        $rest = $by[$region] - $by_hq;
        foreach ($named as $country => $short) {
            $v = (int) ($sub[$region][$country] ?? 0);
            if ($v <= 0) continue;
            $lines[] = array($short, $v);
            $rest -= $v;
        }
        if ($lines && $rest > 0) {
            $lines[] = array($region === 'Europe' ? 'other Europe' : 'rest of North America', $rest);
        } elseif (!$lines && $by_hq > 0 && $rest > 0) {
            $lines[] = array('job location', $rest);
        }
        if ($by_hq > 0) $lines[] = array('by employer HQ', $by_hq);
        $out[] = array('region' => $region, 'jobs' => $by[$region], 'sub' => $lines);
    }
    return array($out, max(0, $unplaced));
}

/**
 * The evidence class a reader can check, from the row's own source columns.
 * A `warn` source_type covers every government notice register, not only US
 * state WARN: Quebec's MESS and Poland's WUP registers carry it too. That is
 * the defect behind "5,888 from state WARN filings" over Canadian and Polish
 * rows (Week 44, 2026), so the class is derived from the country as well.
 */
function alt_briefing_source_class($row) {
    $type = strtolower(trim((string) ($row['source_type'] ?? '')));
    $country = trim((string) ($row['country'] ?? ''));
    if ($type === 'warn') {
        if ($country === 'United States' || ($country === '' && trim((string) ($row['state'] ?? '')) !== '')) {
            return 'US state WARN notices';
        }
        return ($country === '') ? 'government notices with no country recorded'
                                 : 'government collective-dismissal notices outside the US';
    }
    $map = array('8k' => 'SEC 8-K filings', 'news' => 'named news reports',
                 'erm' => 'the European Restructuring Monitor');
    return $map[$type] ?? 'other published sources';
}

/**
 * Can this row LEAD an edition (opening, subject, concentration finding)?
 * A filing (WARN, SEC 8-K, ERM), a silver or gold row, or a news row that a
 * second report backs. One bronze news report cannot: the 2026-W45 weekly was
 * led by a single report of a buyout OFFER (Microsoft 60,000) and trashed
 * the next day (audit 2026-11-12). The row still counts and is still listed,
 * labelled as a single report; only the lead moves.
 */
function alt_briefing_corroborated($row) {
    $type = strtolower(trim((string) ($row['source_type'] ?? '')));
    if ($type !== 'news' && $type !== '') return true;
    $level = strtolower(trim((string) ($row['verification_level'] ?? '')));
    if ($level === 'silver' || $level === 'gold') return true;
    return !empty($row['additional_sources']);
}

/** The largest corroborated row, or null. Rows are already sorted largest first. */
function alt_briefing_lead_row($m) {
    foreach ((array) $m['rows'] as $r) {
        if (alt_briefing_corroborated($r)) return $r;
    }
    return null;
}

/**
 * Verified jobs per employer, largest first: THE ranking "Top employers"
 * prints and the opening's "led by" must agree with (owner review
 * 2026-11-13: the opening said "led by KLM" while Top employers ranked BT
 * first). Keyed by the cleaned name, as both print it.
 */
function alt_briefing_employer_totals($m) {
    $by = array();
    foreach ((array) $m['rows'] as $r) {
        $k = alt_digest_clean_employer($r['company_name']);
        $by[$k] = ($by[$k] ?? 0) + (int) $r['job_count'];
    }
    arsort($by);
    return $by;
}

/** Does any of this employer's rows in the period stand corroborated? */
function alt_briefing_employer_corroborated($m, $name) {
    foreach ((array) $m['rows'] as $r) {
        if (alt_digest_clean_employer($r['company_name']) === $name && alt_briefing_corroborated($r)) return true;
    }
    return false;
}

/**
 * The opening's lead clause. "led by X" only when X is also first in the
 * employer ranking; when a single report outranks the largest corroborated
 * employer, the clause says which rule picked X instead of implying X is
 * the biggest.
 */
function alt_briefing_lead_clause($m) {
    $lr = alt_briefing_lead_row($m);
    if (!$lr) return '';
    $name = alt_digest_clean_employer($lr['company_name']);
    $where = alt_briefing_where($lr);
    $at = $name . ($where !== '' ? ' in ' . $where : '');
    $top = array_key_first(alt_briefing_employer_totals($m));
    if ($top === null || $top === $name) return 'led by ' . $at;
    return 'the largest corroborated: ' . $at . ' (' . alt_digest_number($lr['job_count']) . ' jobs)';
}

/** One row's evidence label, as printed beside it. */
function alt_briefing_evidence_label($row) {
    $name = trim((string) ($row['source_name'] ?? ''));
    if ($name !== '') return $name;
    return rtrim(alt_briefing_source_class($row), 's');
}

/**
 * An employer cell that names a SITE rather than a company. Oregon's register
 * lists "Portland Truck Manufacturing Facility" in its employer column, so that
 * is what the filing names and what we print, labelled as a facility name
 * rather than silently renamed: we do not substitute an employer the filing
 * itself does not state.
 */
function alt_briefing_is_facility_name($name) {
    return (bool) preg_match('/\b(facility|plant|site|location|distribution center|warehouse|campus)\s*$/i',
                             trim((string) $name));
}

function alt_briefing_median($values) {
    $v = array_values(array_filter($values, function ($x) { return $x !== null; }));
    if (!$v) return null;
    sort($v);
    $n = count($v);
    return ($n % 2) ? (float) $v[intdiv($n, 2)] : ($v[$n / 2 - 1] + $v[$n / 2]) / 2.0;
}

function alt_briefing_pct($part, $whole) {
    if ($whole <= 0) return '0%';
    $p = 100 * $part / $whole;
    return ($p > 0 && $p < 1) ? 'under 1%' : (round($p) . '%');
}

/**
 * Everything the edition says, computed once. $now is the compose time (unix).
 */
function alt_briefing_model($b, $now = null) {
    $now = ($now === null) ? time() : (int) $now;
    $from = (string) $b['from'];
    $to = (string) $b['to'];
    $p = $b['period'];
    $ver = alt_briefing_verified($p);
    if ($ver === null) return null;
    $t = (array) $p['totals'];
    $countries = alt_briefing_tuples($p['map_countries'] ?? ($p['top_countries'] ?? array()));
    $industries = alt_briefing_tuples($p['top_industries'] ?? array());
    $m = array(
        'from' => $from, 'to' => $to, 'now' => $now,
        'range' => alt_digest_date_range($from, $to),
        'short' => alt_digest_short_range($from, $to),
        'edition' => alt_digest_edition_label($from, $to),
        'ver' => $ver,
        'all' => (int) ($t['jobs'] ?? 0),
        'entries' => (int) ($t['entries'] ?? 0),
        'announced_entries' => (int) ($t['announced_entries'] ?? 0),
        'companies' => (int) ($t['companies'] ?? 0),
        'ai' => (int) ($t['ai_verified_jobs'] ?? 0),
        'us' => (int) ($countries['United States'] ?? 0),
        'countries' => $countries,
        'industries' => $industries,
        'held' => array(),
        'kind' => (string) ($b['kind'] ?? 'weekly'),
        'wtd' => alt_briefing_verified($b['wtd'] ?? null),
        'notes' => array(),
    );
    $m['ver_entries'] = max(0, $m['entries'] - $m['announced_entries']);
    $m['settle'] = max(0, (int) floor(($now - strtotime($to . ' 23:59:59 UTC')) / DAY_IN_SECONDS) + 1);
    $m['provisional'] = $m['settle'] < alt_briefing_settle_days();
    // Unlocated verified rows with a single-country employer HQ (owner 2026-11-13).
    $hq = array();
    foreach ((is_array($b['rows']) ? $b['rows'] : array()) as $r) {
        if (!empty($r['announced']) || trim((string) ($r['country'] ?? '')) !== '') continue;
        $c = trim((string) ($r['employer_country'] ?? ''));
        if ($c === '' || stripos($c, 'multiple') !== false) continue;
        $hq[$c] = ($hq[$c] ?? 0) + (int) $r['job_count'];
    }
    list($m['regions'], $m['unplaced']) = alt_briefing_regions($countries, $ver, $hq);
    $m['hq_placed'] = max(0, $ver - array_sum($countries) - $m['unplaced']);
    $m['no_industry'] = max(0, $ver - array_sum($industries));

    // Rows: verified only, for biggest cuts, source classes and duplicate checks.
    $rows = is_array($b['rows']) ? $b['rows'] : null;
    $vrows = array();
    if ($rows !== null) {
        foreach ($rows as $r) {
            // The aggregate's verified tier is "not announced", so is this one.
            if (!empty($r['announced'])) continue;
            $vrows[] = $r;
        }
        usort($vrows, function ($a, $c) { return (int) $c['job_count'] - (int) $a['job_count']; });
    }
    $m['rows'] = ($rows === null) ? null : $vrows;
    $classes = array();
    foreach ($vrows as $r) {
        $cls = alt_briefing_source_class($r);
        $classes[$cls] = ($classes[$cls] ?? 0) + (int) $r['job_count'];
    }
    arsort($classes);
    $m['sources'] = $classes;
    $abroad = array();
    foreach ($vrows as $r) {
        if (alt_briefing_source_class($r) !== 'government collective-dismissal notices outside the US') continue;
        $c = (string) $r['country'];
        $abroad[$c] = ($abroad[$c] ?? 0) + (int) $r['job_count'];
    }
    arsort($abroad);
    $m['notice_countries'] = $abroad;

    // Leaders carry the city; the query rows do not.
    $cities = array();
    foreach ((array) ($p['leaders'] ?? array()) as $l) {
        $l = (array) $l;
        $city = function_exists('alt_digest_row_city')
            ? alt_digest_row_city($l['state'] ?? '', $l['country'] ?? '', $l['location'] ?? '') : '';
        if ($city !== '') $cities[(int) $l['id']] = $city;
    }
    $m['cities'] = $cities;

    // Eight weeks, oldest first.
    $weeks = array();
    foreach ((array) $b['weeks'] as $w) {
        $jobs = alt_briefing_verified($w['data']);
        $settle = (int) floor(($now - strtotime($w['to'] . ' 23:59:59 UTC')) / DAY_IN_SECONDS) + 1;
        $conc = (array) ($w['data']['concentration'] ?? array());
        $weeks[] = array('from' => $w['from'], 'to' => $w['to'], 'jobs' => $jobs,
                         'provisional' => $settle < alt_briefing_settle_days(),
                         'largest' => trim((string) ($conc['largest_row_company'] ?? '')),
                         'largest_jobs' => (int) ($conc['largest_row_jobs'] ?? 0));
    }
    $m['weeks'] = $weeks;
    $m['median'] = alt_briefing_median(array_column($weeks, 'jobs'));
    $settled = array();
    foreach ($weeks as $i => $w) {
        if ($i === count($weeks) - 1 && $w['provisional']) continue;
        if ($w['jobs'] !== null) $settled[] = $w['jobs'];
    }
    $m['avg'] = $settled ? array_sum($settled) / count($settled) : null;
    // How many weeks the average really covers: 7 while the current week is
    // still provisional, and the trend line must say so (audit 2026-11-13).
    $m['avg_weeks'] = count($settled);
    // The TONE word compares against the settled median, which one spike
    // (Sep 21-27 2026: 71,387) cannot drag; the printed average is the mean.
    $m['settled_median'] = alt_briefing_median($settled);
    $m['outliers'] = array();
    if ($m['median'] !== null && $m['median'] > 0) {
        foreach ($weeks as $w) {
            if ($w['jobs'] !== null && $w['jobs'] > alt_briefing_outlier_factor() * $m['median']) {
                $m['outliers'][] = $w;
            }
        }
    }

    // Year to date.
    $y = $b['ytd'];
    $yv = alt_briefing_verified($y);
    $m['ytd'] = null;
    if ($yv !== null && $yv > 0) {
        $yt = (array) $y['totals'];
        $yplaced = array_sum(alt_briefing_tuples($y['map_countries'] ?? array()));
        $m['ytd'] = array('ver' => $yv, 'ai' => (int) ($yt['ai_verified_jobs'] ?? 0),
                          'unplaced' => max(0, $yv - $yplaced),
                          'range' => alt_digest_date_range($b['ytd_from'], $to),
                          'year' => substr($to, 0, 4));
    }

    $m['checks'] = alt_briefing_checks($m, $p);
    $m['single'] = 0;
    foreach ((array) $m['rows'] as $r) {
        if (!alt_briefing_corroborated($r)) $m['single'] += (int) $r['job_count'];
    }
    $m['findings'] = alt_briefing_findings($m);
    $m['means'] = alt_briefing_means($m);
    foreach ($m['held'] as $h) {
        if (function_exists('error_log')) error_log('[alt-briefing] held ' . $h['claim'] . ': ' . $h['why']);
    }
    return $m;
}

/* ------------------------------------------------------------------ */
/* Pre-send checks                                                    */
/* ------------------------------------------------------------------ */

/**
 * The checks that run on every composed edition. Each returns PASS / FAIL /
 * UNKNOWN; a FAIL on a claim HOLDS that claim (it is removed from $m and
 * logged). Returns the list; $m is modified by reference.
 */
function alt_briefing_checks(&$m, $p) {
    $out = array();
    $hold = function ($claim, $why) use (&$m) {
        $m['held'][] = array('claim' => $claim, 'why' => $why);
    };
    // 1. Regions (unknowns included) sum to worldwide; sub-lines to their region.
    $sum = array_sum(array_column($m['regions'], 'jobs'));
    $ok = ($sum === $m['ver']);
    foreach ($m['regions'] as $r) {
        if ($r['sub'] && array_sum(array_column($r['sub'], 1)) !== $r['jobs']) $ok = false;
    }
    $out['regions_reconcile'] = $ok ? 'PASS' : 'FAIL';
    if (!$ok) { $hold('regions', "region rows sum to $sum, worldwide is {$m['ver']}"); $m['regions'] = array(); }
    // 2. US figure equals the North America US sub-line (or the region).
    // 3. Rows reconcile with the aggregate.
    if ($m['rows'] === null) {
        $out['rows_reconcile'] = 'UNKNOWN';
        $hold('sources', 'row list unavailable'); $m['sources'] = array();
    } else {
        $rsum = array_sum(array_map(function ($r) { return (int) $r['job_count']; }, $m['rows']));
        $out['rows_reconcile'] = ($rsum === $m['ver']) ? 'PASS' : 'FAIL';
        if ($rsum !== $m['ver']) {
            $hold('sources', "verified rows sum to $rsum, aggregate says {$m['ver']}");
            $m['sources'] = array();
        }
    }
    // 4. Source/geography consistency: no "US state WARN" class over a non-US row.
    $bad = array();
    foreach ((array) $m['rows'] as $r) {
        if (alt_briefing_source_class($r) === 'US state WARN notices'
            && trim((string) $r['country']) !== '' && $r['country'] !== 'United States') {
            $bad[] = (int) $r['id'];
        }
    }
    $out['source_geography'] = $bad ? 'FAIL' : 'PASS';
    if ($bad) { $hold('sources', 'US WARN label on non-US rows ' . implode(',', $bad)); $m['sources'] = array(); }
    // 5. Industries plus "no industry" reconcile (by construction; a negative remainder is a FAIL).
    $isum = array_sum($m['industries']);
    $out['industries_reconcile'] = ($isum <= $m['ver']) ? 'PASS' : 'FAIL';
    if ($isum > $m['ver']) { $hold('industries', "industries sum to $isum over {$m['ver']}"); $m['industries'] = array(); }
    // 6. Duplicate rows. The same id or event twice is a duplicate and is
    // held. Look-alike WARN rows (same employer, jobs, date, state, but their
    // own event) are NOT: employers legally file one notice per site, and WARN
    // is exempt from fuzzy dedup (CLAUDE.md). Those are counted as a note.
    $seen = array();
    $look = array();
    $dups = array();
    $alike = 0;
    foreach ((array) $m['rows'] as $r) {
        $ev = 'e' . (int) ($r['event_id'] ?? 0) . '|' . (int) $r['id'];
        if ((int) ($r['event_id'] ?? 0) > 0) $ev = 'e' . (int) $r['event_id'];
        if (isset($seen[$ev])) { $dups[] = array($seen[$ev], (int) $r['id']); continue; }
        $seen[$ev] = (int) $r['id'];
        $k = strtolower(trim((string) $r['company_name'])) . '|' . (int) $r['job_count'] . '|'
           . ($r['layoff_date'] ?? '') . '|' . ($r['state'] ?? '') . '|' . ($r['country'] ?? '');
        if (isset($look[$k])) {
            if (strtolower((string) ($r['source_type'] ?? '')) === 'warn') $alike++;
            else $dups[] = array($look[$k], (int) $r['id']);
        } else {
            $look[$k] = (int) $r['id'];
        }
    }
    $m['warn_lookalikes'] = $alike;
    $m['duplicates'] = $dups;
    $out['duplicates'] = $dups ? 'FAIL' : 'PASS';
    if ($dups) {
        foreach ($dups as $d) $hold('row ' . $d[1], 'possible duplicate of row ' . $d[0]);
        $drop = array_column($dups, 1);
        $m['rows'] = array_values(array_filter($m['rows'], function ($r) use ($drop) {
            return !in_array((int) $r['id'], $drop, true);
        }));
    }
    // 7. Week series complete (a gap is never drawn as a zero).
    $gap = $m['weeks'] && in_array(null, array_column($m['weeks'], 'jobs'), true);
    $out['weeks_complete'] = $gap ? 'FAIL' : 'PASS';
    if ($gap) { $hold('trend', 'a week in the 8-week series did not load'); $m['weeks'] = array(); $m['outliers'] = array(); }
    // 8. Outlier: reported as a note, never held.
    $out['outlier'] = $m['outliers'] ? 'NOTE' : 'PASS';
    return $out;
}

/**
 * Links check, run on the RENDERED output: every tracker link names the same
 * window and the effective basis, and every internal link is a well-formed URL
 * on our own host. A failing link is removed from the output and logged.
 */
function alt_briefing_check_links($html, $m) {
    $bad = array();
    preg_match_all('/href="([^"]+)"/', $html, $all);
    $home = home_url('/');
    foreach (array_unique($all[1]) as $url) {
        $u = html_entity_decode($url, ENT_QUOTES);
        if (strpos($u, $home) !== 0) continue;
        if (!filter_var($u, FILTER_VALIDATE_URL)) { $bad[] = $u; continue; }
        if (strpos($u, '/ai-layoff-tracker/?') === false) continue;
        parse_str((string) parse_url($u, PHP_URL_QUERY), $q);
        if (($q['date_basis'] ?? '') !== alt_digest_layoff_basis('link')) { $bad[] = $u; continue; }
        if (isset($q['from']) && ($q['from'] !== $m['from'] || ($q['to'] ?? '') !== $m['to'])) {
            $bad[] = $u;
        }
    }
    return $bad;
}

/* ------------------------------------------------------------------ */
/* Template sentences                                                  */
/* ------------------------------------------------------------------ */

/** "the day" / "the week" / "the month": the edition's own period (audit 2026-11-13:
 * the monthly printed "45% of the week"). */
function alt_briefing_period_noun($m) {
    $k = (string) ($m['kind'] ?? 'weekly');
    return $k === 'daily' ? 'the day' : ($k === 'monthly' ? 'the month' : 'the week');
}

/** Distinct employers among the verified rows: the count the opening sentence uses. */
function alt_briefing_verified_employers($m) {
    return count(array_unique(array_map(function ($r) { return strtolower((string) $r['company_name']); },
                                        (array) $m['rows'])));
}

/** Up to three findings, each from a rule with its evidence in the model. */
function alt_briefing_findings($m) {
    $f = array();
    $ver = $m['ver'];
    if ($ver <= 0) return $f;
    $rows = (array) $m['rows'];
    // 1. Concentration.
    $lead = alt_briefing_lead_row($m);
    if ($rows && !alt_briefing_corroborated($rows[0])
        && 100 * (int) $rows[0]['job_count'] / $ver >= 25) {
        $f[] = 'The largest single figure, ' . alt_digest_clean_employer($rows[0]['company_name'])
             . ' at ' . alt_digest_number($rows[0]['job_count']) . ' jobs ('
             . alt_briefing_pct($rows[0]['job_count'], $ver)
             . ' of the total), rests on a single news report and is not yet corroborated.';
    } elseif ($lead) {
        $top = $lead;
        $share = 100 * (int) $top['job_count'] / $ver;
        $name = alt_digest_clean_employer($top['company_name']);
        if ($share >= 25) {
            $f[] = $name . ' alone is ' . alt_briefing_pct($top['job_count'], $ver)
                 . ' of ' . alt_briefing_period_noun($m) . ' (' . alt_digest_number($top['job_count'])
                 . ' jobs), so one decision drives the total.';
        } else {
            $f[] = 'No single employer dominates: the largest, ' . $name . ' at '
                 . alt_digest_number($top['job_count']) . ' jobs, is '
                 . alt_briefing_pct($top['job_count'], $ver) . ' of the verified total, across '
                 . alt_digest_number(count($rows)) . ' verified entries.';
        }
    }
    // 2. Outside the United States.
    $abroad = $ver - $m['us'] - $m['unplaced'];
    if ($abroad > 0 && $m['countries']) {
        $non = $m['countries'];
        unset($non['United States']);
        $lead = array_slice($non, 0, 2, true);
        $parts = array();
        foreach ($lead as $c => $v) $parts[] = $c . ' (' . alt_digest_number($v) . ')';
        $f[] = alt_digest_number($abroad) . ' verified cuts (' . alt_briefing_pct($abroad, $ver)
             . ') were outside the United States, led by ' . implode(' and ', $parts) . '.';
    }
    // 3. Industry lead.
    if ($m['industries']) {
        $ind = array_key_first($m['industries']);
        $v = $m['industries'][$ind];
        $f[] = $ind . ' had the most verified cuts, ' . alt_digest_number($v) . ' ('
             . alt_briefing_pct($v, $ver) . ' of ' . alt_briefing_period_noun($m) . ').';
    }
    // 4. Repeat filers.
    $by = array();
    foreach ($rows as $r) {
        $k = (string) $r['company_name'];
        if (!isset($by[$k])) $by[$k] = array(0, 0);
        $by[$k][0]++;
        $by[$k][1] += (int) $r['job_count'];
    }
    uasort($by, function ($a, $c) { return $c[0] - $a[0] ?: $c[1] - $a[1]; });
    $first = array_key_first($by);
    if ($first !== null && $by[$first][0] >= 3) {
        $f[] = alt_digest_clean_employer($first) . ' filed ' . $by[$first][0]
             . ' separate notices in ' . alt_briefing_period_noun($m) . ', ' . alt_digest_number($by[$first][1]) . ' jobs in all.';
    }
    // 5. AI.
    if ($m['ai'] > 0) {
        array_unshift($f, 'Employers explicitly named AI as a reason for '
            . alt_digest_number($m['ai']) . ' verified cuts (' . alt_briefing_pct($m['ai'], $ver) . ').');
    }
    return array_slice($f, 0, 3);
}

/** "What it means": one or two template sentences, or ''. */
function alt_briefing_means($m) {
    if ($m['ver'] <= 0 || !$m['industries']) return '';
    $inds = array_slice($m['industries'], 0, 2, true);
    $share = alt_briefing_pct(array_sum($inds), $m['ver']);
    $names = implode(' and ', array_keys($inds));
    // The edition's own period, not "this week" (owner review 2026-11-13: a
    // monthly said "28% of this week's verified cuts").
    $s = 'For recruiters and job seekers: ' . $share . ' of the verified cuts in ' . alt_briefing_period_noun($m) . ' were in '
       . $names . ', so that is where the most newly affected candidates are';
    $states = array();
    foreach ((array) $m['rows'] as $r) {
        if (($r['country'] ?? '') !== 'United States' || trim((string) $r['state']) === '') continue;
        $states[$r['state']] = ($states[$r['state']] ?? 0) + (int) $r['job_count'];
    }
    arsort($states);
    if ($states) {
        $top = array_key_first($states);
        $s .= '; in the US, the most were in ' . alt_digest_us_state_name($top)
            . ' (' . alt_digest_number($states[$top]) . ')';
    }
    return $s . '.';
}

/** The subject fragment: the most significant verified finding. */
function alt_briefing_metric($m) {
    $metric = alt_digest_number($m['ver']) . ' verified job cuts';
    $rows = (array) $m['rows'];
    if ($m['ai'] > 0) return $metric . " \xc2\xb7 " . alt_digest_number($m['ai']) . ' AI-attributed';
    $lead = alt_briefing_lead_row($m);
    if ($lead) {
        $story = array('company' => $lead['company_name'], 'jobs' => (int) $lead['job_count']);
        if (function_exists('alt_digest_story_metric')) return alt_digest_story_metric($metric, $story);
    }
    return $metric;
}

/* ------------------------------------------------------------------ */
/* Render                                                             */
/* ------------------------------------------------------------------ */

function alt_briefing_h($s) {
    return esc_html($s);
}

/** Where a row is, as a reader says it: city, state (US), country. */
function alt_briefing_place($r, $m) {
    $state = trim((string) ($r['state'] ?? ''));
    $country = trim((string) ($r['country'] ?? ''));
    $city = $m['cities'][(int) $r['id']] ?? '';
    return implode(', ', array_filter(array($city,
        ($country === 'United States' && $state !== '') ? alt_digest_us_state_name($state) : '',
        $country)));
}

/** Where the largest row is, short: the US state, else the country. */
function alt_briefing_where($r) {
    $state = trim((string) ($r['state'] ?? ''));
    if (($r['country'] ?? '') === 'United States' && $state !== '') return alt_digest_us_state_name($state);
    return trim((string) ($r['country'] ?? ''));
}

/** The one opening sentence. Rules only: size vs settled average, spread, leader. */
function alt_briefing_opening($m) {
    $rows = (array) $m['rows'];
    $ver = $m['ver'];
    $n = alt_digest_number($ver);
    $employers = count(array_unique(array_map(function ($r) { return strtolower((string) $r['company_name']); }, $rows)));
    $lead = alt_briefing_lead_clause($m);
    if ($m['kind'] === 'daily') {
        if ($ver <= 0) return 'On ' . $m['range'] . ', no verified job cuts took effect in our records.';
        return 'On ' . $m['range'] . ', ' . alt_digest_count($employers, 'employer') . ' had verified job cuts take effect, '
             . $n . ' jobs in all' . ($lead !== '' ? ', ' . $lead : '') . '.';
    }
    if ($m['kind'] === 'monthly') {
        $month = (substr($m['from'], 0, 7) === substr($m['to'], 0, 7))
            ? gmdate('F Y', strtotime($m['from'] . ' 00:00:00 UTC')) : $m['range'];
        return 'In ' . $month . ', ' . $n . ' verified job cuts took effect across '
             . alt_digest_count($employers, 'employer') . ($lead !== '' ? ', ' . $lead : '') . '.';
    }
    $tone = 'This week';
    $base = $m['settled_median'] ?? null;
    if ($base !== null && $base > 0) {
        if ($ver < 0.75 * $base) $tone = 'A quieter week';
        elseif ($ver > 1.25 * $base) $tone = 'A heavier week';
        else $tone = 'A typical week';
    }
    if ($m['provisional']) $tone .= ' so far';
    $spread = '';
    if ($rows && $ver > 0) {
        $spread = (100 * (int) $rows[0]['job_count'] / $ver >= 25)
            ? 'with one employer making up much of it'
            : 'spread across ' . alt_digest_count($employers, 'employer');
    }
    return $tone . ': ' . $n . ' verified job cuts' . ($spread !== '' ? ', ' . $spread : '')
         . ($lead !== '' ? ', ' . $lead : '') . '.';
}

function alt_briefing_section($title, $sentence, &$html, &$text) {
    $html .= '<h3>' . alt_briefing_h($title) . '</h3>';
    $text .= "\n" . $title . "\n";
    if ($sentence !== '') {
        $html .= '<p>' . alt_briefing_h($sentence) . '</p>';
        $text .= $sentence . "\n";
    }
}

function alt_briefing_render($m, $send_id = 0) {
    $from = $m['from'];
    $to = $m['to'];
    $kind = $m['kind'];
    $tracker = alt_digest_tracker_url($from, $to);
    $tag = array('daily' => 'daily briefing', 'weekly' => 'weekly briefing', 'monthly' => 'monthly briefing')[$kind] ?? 'briefing';
    $head = ($kind === 'weekly') ? $m['edition'] : $m['range'];
    $opening = alt_briefing_opening($m);
    $html = '<h2>AI Layoff Tracker</h2>'
          . '<p data-alt="dateline">' . alt_briefing_h($head . " \xc2\xb7 " . $tag) . '</p>'
          . '<p data-alt="lead">' . alt_briefing_h($opening) . '</p>';
    $text = "AI Layoff Tracker\n" . $head . " \xc2\xb7 " . $tag . "\n" . $opening . "\n";
    $period_word = array('daily' => 'today', 'weekly' => 'this week', 'monthly' => 'this month')[$kind] ?? 'this period';

    // B. At a glance.
    $glance = 'Of ' . alt_digest_number($m['ver']) . ' verified job cuts worldwide, '
            . alt_digest_number($m['us']) . ' were in the United States and '
            . alt_digest_number($m['ai']) . ' were explicitly attributed to AI by the employer.';
    // THE SINGLE-REPORT SHARE IN THE HEADLINE, not only a footnote (owner
    // review 2026-11-13: 42,200 of 80,227, 53%, sat under the stat cards).
    if (!empty($m['single']) && $m['ver'] > 0) {
        $glance .= ' ' . alt_digest_number($m['single']) . ' rest on a single news report not yet corroborated ('
                 . alt_briefing_pct($m['single'], $m['ver']) . ').';
    }
    alt_briefing_section(($kind === 'weekly' ? 'This week' : ucfirst($period_word)) . ' at a glance', $glance, $html, $text);
    list($ph, $pt) = alt_digest_stat_pair(array(
        array('label' => 'Worldwide', 'figure' => alt_digest_number($m['ver']), 'unit' => 'verified job cuts',
              'url' => alt_digest_track_link($send_id, $tracker)),
        array('label' => 'United States', 'figure' => alt_digest_number($m['us']), 'unit' => 'verified job cuts',
              'url' => alt_digest_track_link($send_id, alt_digest_tracker_url($from, $to, array('country' => 'United States')))),
    ));
    $html .= $ph;
    $text .= $pt;
    $ai_line = 'AI-attributed: ' . alt_digest_number($m['ai']) . ' ' . $period_word
             . ($m['ytd'] ? " \xc2\xb7 " . alt_digest_number($m['ytd']['ai']) . ' in ' . $m['ytd']['year'] . ' so far' : '');
    $html .= '<p data-alt="signature">' . alt_briefing_h($ai_line) . '</p>';
    $text .= '  ' . $ai_line . "\n";
    // WHAT EACH COUNT MEASURES, in one plain line (audit 2026-11-12).
    $define = 'What these count: verified job cuts are jobs with a stated number in a government '
            . 'notice, an SEC filing or a named news report, counted on the date the cuts take effect; '
            . 'announced plans without a filing are left out. AI-attributed means the employer itself '
            . 'named AI as a reason.';
    $html .= '<p data-alt="note">' . alt_briefing_h($define) . '</p>';
    $text .= '  ' . $define . "\n";
    if ($m['regions']) {
        // The bars are ALL verified cuts (they sum to the worldwide figure),
        // not the AI-attributed line printed just above them.
        $html .= '<p data-alt="note">Verified job cuts by region</p>'
               . '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">';
        $text .= "  Verified job cuts by region:\n";
        $last = count($m['regions']) - 1;
        foreach ($m['regions'] as $i => $r) {
            $edge = ($i === $last) ? '-last' : '';
            $subs = array();
            foreach ($r['sub'] as $s) $subs[] = $s[0] . ' ' . alt_digest_number($s[1]);
            $label = $r['region'] . ($subs ? ' (' . implode(" \xc2\xb7 ", $subs) . ')' : '');
            $html .= '<tr><td data-alt="label' . $edge . '">' . alt_briefing_h($label) . '</td>'
                   . '<td data-alt="figure' . $edge . '" align="right" width="30%">'
                   . alt_briefing_h(alt_digest_number($r['jobs'])) . '</td></tr>';
            $text .= '    ' . $label . ': ' . alt_digest_number($r['jobs']) . "\n";
        }
        $html .= '</table>';
    }
    if (!empty($m['hq_placed']) && $m['regions']) {
        $hqn = alt_digest_number($m['hq_placed']) . ' jobs with no job location are placed by the employer\'s headquarters.';
        $html .= '<p data-alt="note">' . alt_briefing_h($hqn) . '</p>';
        $text .= '  ' . $hqn . "\n";
    }
    if ($m['provisional']) {
        $badge = 'Provisional: ' . alt_digest_count($m['settle'], 'day') . ' to settle. Late notices usually raise these figures.';
        $html .= '<p data-alt="note">' . alt_briefing_h($badge) . '</p>';
        $text .= '  ' . $badge . "\n";
    }

    // C. Three things worth knowing (weekly, monthly).
    if ($kind !== 'daily' && $m['findings']) {
        alt_briefing_section('Three things worth knowing', '', $html, $text);
        $html .= '<ul>';
        foreach ($m['findings'] as $f) {
            $html .= '<li>' . alt_briefing_h($f) . '</li>';
            $text .= '  - ' . $f . "\n";
        }
        $html .= '</ul>';
    }

    // D. Biggest cuts, this period only.
    list($bh, $bt) = alt_briefing_biggest($m, $send_id);
    $html .= $bh;
    $text .= $bt;
    if ($kind === 'daily' && $m['wtd'] !== null) {
        $w = 'This week so far (' . alt_digest_short_range(alt_briefing_monday($to), $to) . '): '
           . alt_digest_number($m['wtd']) . ' verified job cuts.';
        $html .= '<p>' . alt_briefing_h($w) . '</p>';
        $text .= "\n" . $w . "\n";
    }

    if ($kind !== 'daily') {
        if ($kind === 'monthly') {
            list($eh, $et) = alt_briefing_employers($m);
            $html .= $eh;
            $text .= $et;
        }
        // E. Trend.
        list($wh, $wt) = alt_briefing_trend($m);
        $html .= $wh;
        $text .= $wt;

        // F. Top industries and countries.
        if ($m['industries'] || $m['countries']) {
            $lead = array();
            if ($m['industries']) $lead[] = array_key_first($m['industries']) . ' led the industries';
            if ($m['countries']) $lead[] = array_key_first($m['countries']) . ' the countries';
            alt_briefing_section('Where and in what', ucfirst(implode(', and ', $lead)) . '.', $html, $text);
            foreach (array('Top industries' => $m['industries'], 'Top countries' => $m['countries']) as $title => $list) {
                if (!$list) continue;
                $items = array();
                foreach (array_slice($list, 0, 3, true) as $label => $v) $items[] = $label . ' ' . alt_digest_number($v);
                $line = $title . ': ' . implode(" \xc2\xb7 ", $items);
                $html .= '<p data-alt="series">' . alt_briefing_h($line) . '</p>';
                $text .= '  ' . $line . "\n";
            }
            $html .= '<p data-alt="more"><a href="' . esc_url(alt_digest_track_link($send_id, $tracker))
                   . '">See the full breakdown &rarr;</a></p>';
            $text .= "  See the full breakdown: " . $tracker . "\n";
        }

        // G. AI attribution watch.
        $ai = ($m['ai'] > 0)
            ? 'Employers explicitly named AI on ' . alt_digest_number($m['ai']) . ' verified cuts ' . $period_word . '.'
            : 'No employer explicitly named AI as a reason ' . $period_word . '.';
        if ($m['ytd'] && $m['ytd']['ver'] > 0) {
            $ai .= ' So far in ' . $m['ytd']['year'] . ', ' . alt_digest_number($m['ytd']['ai'])
                 . ' verified cuts (' . alt_briefing_pct($m['ytd']['ai'], $m['ytd']['ver']) . ') carry an explicit employer attribution.';
        }
        $caveat = 'Zero explicit attribution does not mean AI had no effect: it means no employer in these records cited AI as a reason. We measure employer disclosure, not the effect of automation on employment.';
        alt_briefing_section('AI attribution watch', $ai, $html, $text);
        $html .= '<p data-alt="note">' . alt_briefing_h($caveat) . '</p>';
        $text .= $caveat . "\n";

        // H. What it means.
        if ($m['means'] !== '') alt_briefing_section('What it means', $m['means'], $html, $text);
    }

    // I. Explore the data.
    $method = home_url('/ai-layoff-tracker/methodology/');
    $edition = '';
    if (function_exists('alt_edition_slug') && function_exists('alt_edition_url')) {
        $slug = alt_edition_slug($kind, $from, $to);
        if ($slug !== '') $edition = alt_edition_url($kind, $slug);
    }
    $links = array(
        array('Open the tracker for ' . $m['range'], alt_digest_track_link($send_id, $tracker), $tracker),
        array('How we count (methodology)', $method, $method),
        array('Download the data (CSV, JSON)', $tracker . '#alt-export-csv', $tracker . '#alt-export-csv'),
    );
    if ($edition !== '') $links[] = array('This edition in the archive (cite this)', $edition, $edition);
    alt_briefing_section('Explore the data', 'Every figure above opens on the same dates and the same counting basis.', $html, $text);
    foreach ($links as $l) {
        $html .= '<p><a href="' . esc_url($l[1]) . '">' . alt_briefing_h($l[0]) . '</a></p>';
        $text .= '  ' . $l[0] . ': ' . $l[2] . "\n";
    }

    // J. Compact notes.
    $notes = array();
    if ($m['sources']) {
        $parts = array();
        foreach ($m['sources'] as $cls => $v) {
            $label = $cls;
            if ($cls === 'government collective-dismissal notices outside the US' && $m['notice_countries']) {
                $cs = array();
                foreach ($m['notice_countries'] as $c => $cv) $cs[] = $c . ' ' . alt_digest_number($cv);
                $label .= ' (' . implode(', ', $cs) . ')';
            }
            $parts[] = alt_digest_number($v) . ' from ' . $label;
        }
        $notes[] = 'Sources, verified only: ' . implode('; ', $parts) . '.';
    }
    $notes[] = 'All ' . alt_digest_number($m['entries']) . ' entries (' . alt_digest_number($m['ver_entries'])
             . ' verified) total ' . alt_digest_number($m['all']) . ' jobs including announced plans, across '
             . alt_digest_count($m['companies'], 'company', 'companies') . '.';
    if ($m['no_industry'] > 0) $notes[] = alt_digest_number($m['no_industry']) . ' verified cuts carry no industry yet.';
    if ($m['ytd'] && $m['ytd']['unplaced'] > 0) {
        $notes[] = alt_digest_number($m['ytd']['unplaced']) . ' of ' . alt_digest_number($m['ytd']['ver'])
                 . ' verified cuts in ' . $m['ytd']['year'] . ' have no country recorded.';
    }
    $cut = alt_digest_data_cut_label();
    $read = alt_digest_date_range(gmdate('Y-m-d', $m['now']), gmdate('Y-m-d', $m['now'])) . ' at ' . gmdate('H:i', $m['now']) . ' UTC';
    $notes[] = 'Snapshot: database last changed ' . ($cut !== '' ? $cut : 'at an unrecorded time')
             . '; composed ' . $read . '. Filings keep arriving, so recent figures usually rise and a correction can lower one.';
    $notes[] = 'Cite: AI Layoff Tracker, AskTheRecruiter.com. Figures for ' . $m['range']
             . ($cut !== '' ? ', as of ' . $cut : '') . ', accessed ' . $read . '. '
             . ($edition !== '' ? $edition : home_url('/ai-layoff-tracker/'));
    $corr = home_url('/contact/');
    alt_briefing_section('Notes', '', $html, $text);
    foreach ($notes as $n) {
        $html .= '<p data-alt="footnote">' . alt_briefing_h($n) . '</p>';
        $text .= '  ' . $n . "\n";
    }
    // Methodology is already linked under "Explore the data"; a second link
    // to it cost ~0.8 KB of a clipped message once the relay rewrote it.
    $html .= '<p data-alt="footnote"><a href="' . esc_url($corr) . '">Submit a correction</a></p>';
    $text .= "  Submit a correction: " . $corr . "\n";

    $preheader = alt_digest_fit_preheader(
        alt_digest_count($m['ai'], 'cut') . ' attributed to AI',
        array(alt_digest_number($m['us']) . ' in the United States',
              // The verified employers the opening counts, not totals.companies,
              // which also holds announced plans (audit 2026-11-13: preheader
              // "across 7 companies" beside a lead of "6 employers").
              'across ' . alt_digest_count(alt_briefing_verified_employers($m), 'employer'),
              $m['provisional'] ? 'provisional' : ''));
    return array('html' => $html, 'text' => $text, 'preheader' => $preheader,
                 'metric' => alt_briefing_metric($m));
}

/** Monthly: the top employers of the period, rows summed by employer. */
function alt_briefing_employers($m) {
    $by = array_slice(alt_briefing_employer_totals($m), 0, 10, true);
    if (!$by) return array('', '');
    $html = ''; $text = '';
    $first = array_key_first($by);
    $lead = $first . ' had the most verified cuts this month'
          . (alt_briefing_employer_corroborated($m, $first) ? '.' : ', on a single report not yet corroborated.');
    alt_briefing_section('Top employers this month', $lead, $html, $text);
    $items = array();
    foreach ($by as $k => $v) $items[] = $k . ' ' . alt_digest_number($v);
    $line = implode(" \xc2\xb7 ", $items);
    // A plain line, not a `series`: a series grows a ten-row bar chart that
    // repeats every name and figure, ~9 KB of a monthly Gmail clipped at
    // ~102 KB (owner review 2026-11-13). The ranking is the line.
    $html .= '<p>' . alt_briefing_h($line) . '</p>';
    $text .= '  ' . $line . "\n";
    return array($html, $text);
}

/** D. Biggest cuts of THIS period, grouped Around the world. */
function alt_briefing_biggest($m, $send_id) {
    // The daily shows its ten largest and links the rest (audit 2026-11-12:
    // a 40-row cap listed 33-job notices with no "See all").
    // Monthly 8, not 10 (owner review 2026-11-13): each card is ~2.5 KB once
    // the relay rewrites its two links, and the monthly was clipped by Gmail.
    // Top employers still names ten, and "See more" links the rest.
    $cap = ($m['kind'] === 'daily') ? 10 : (($m['kind'] === 'monthly') ? 8 : 6);
    $rows = array_slice((array) $m['rows'], 0, $cap);
    if (!$rows) return array('', '');
    $items = array();
    foreach ($rows as $r) {
        $name = (string) $r['company_name'];
        $pills = array(alt_digest_place_pill(alt_briefing_place($r, $m)), alt_digest_pill(alt_briefing_evidence_label($r), '', true));
        if (alt_briefing_is_facility_name($name)) $pills[] = alt_digest_pill('Facility named in the filing', '', true);
        if (!alt_briefing_corroborated($r)) $pills[] = alt_digest_pill('Single report, not yet corroborated', '', true);
        $src = trim((string) ($r['source_url'] ?? ''));
        if ($src !== '' && function_exists('alt_digest_external_link_ok') && !alt_digest_external_link_ok($src)) $src = '';
        $where = alt_briefing_place($r, $m);
        $items[] = array(
            'suffix' => '(' . ($where !== '' ? $where . '; ' : '') . alt_briefing_evidence_label($r)
                      . (alt_briefing_corroborated($r) ? '' : '; single report') . ')',
            'label' => $name, 'figure' => alt_digest_jobs_phrase((int) $r['job_count']),
            'url' => alt_digest_track_link($send_id, alt_digest_tracker_url($m['from'], $m['to'], array('company' => $name))),
            'plain_url' => '', 'pills' => $pills, 'source_url' => $src,
            'geo' => array('country' => trim((string) ($r['country'] ?? '')),
                           'state' => trim((string) ($r['state'] ?? '')),
                           'city' => $m['cities'][(int) $r['id']] ?? ''),
        );
    }
    $word = array('daily' => 'today', 'weekly' => 'this week', 'monthly' => 'this month')[$m['kind']] ?? '';
    $title = 'Biggest cuts ' . $word . ' (' . $m['short'] . ')';
    $html = ''; $text = '';
    // Not "Verified only" (owner review 2026-11-13): the list carries rows
    // that rest on one news report, each labelled, so the subtitle says so.
    alt_briefing_section($title, 'Largest first, each with the filing or report behind it. A single news report not yet corroborated is labelled as one.', $html, $text);
    list($wh, $wt) = function_exists('alt_digest_world_cards')
        ? alt_digest_world_cards($items, 'alt_digest_rank_cards')
        : alt_digest_rank_cards($items);
    $html .= $wh;
    $text .= $wt;
    $more = count((array) $m['rows']) - count($rows);
    if ($more > 0) {
        $line = 'See ' . alt_digest_count($more, 'more verified entry', 'more verified entries') . ' ' . $word;
        $html .= '<p data-alt="more"><a href="' . esc_url(alt_digest_track_link($send_id, alt_digest_tracker_url($m['from'], $m['to'])))
               . '">' . alt_briefing_h($line) . ' &rarr;</a></p>';
        $text .= '  ' . $line . "\n";
    }
    return array($html, $text);
}

/**
 * E. The 8-week trend: one plain sentence, then one bar per week, NEWEST
 * FIRST, labelled with its date range, the figure at the end. The week still
 * being counted says so; no week-over-week percentage is printed, because the
 * weeks have not had the same time to settle. The average excludes the
 * current provisional week, and the footnote says so.
 */
function alt_briefing_trend($m) {
    if (count((array) $m['weeks']) !== 8) return array('', '');
    $cur = $m['weeks'][7];
    $s = ($m['kind'] === 'monthly' ? 'The latest week' : 'This week') . ': ' . alt_digest_number($cur['jobs']);
    if ($m['avg'] !== null) {
        $rel = ($cur['jobs'] < $m['avg']) ? 'below' : 'above';
        $nw = (int) ($m['avg_weeks'] ?? 8);
        $span = ($nw === 8) ? 'the 8-week average' : 'the average of the previous ' . $nw . ' weeks';
        $s .= ', ' . $rel . ' ' . $span . ' of ' . alt_digest_number((int) round($m['avg']));
    }
    $s .= '.';
    if ($m['outliers'] && $m['settled_median'] !== null) {
        $s .= ' The typical (median) settled week was ' . alt_digest_number((int) round($m['settled_median'])) . '.';
    }
    foreach ($m['outliers'] as $o) {
        $s .= ' The ' . alt_digest_short_range($o['from'], $o['to']) . ' week was unusually high ('
            . alt_digest_number($o['jobs']) . ')'
            . ($o['largest'] !== '' ? ', mostly one entry: ' . $o['largest'] . ' at ' . alt_digest_number($o['largest_jobs']) : '')
            . '.';
    }
    $items = array();
    foreach (array_reverse($m['weeks']) as $w) {
        $label = alt_digest_short_range($w['from'], $w['to']) . ($w['provisional'] ? ' (still being counted)' : '');
        $items[] = $label . ' ' . alt_digest_number($w['jobs']);
    }
    $line = implode(" \xc2\xb7 ", $items);
    $foot = 'The average leaves out the current week, which is still being counted. Weeks under '
          . alt_briefing_settle_days() . ' days old usually rise as late notices arrive, so they are not compared by percentage.';
    $html = ''; $text = '';
    alt_briefing_section('Last 8 weeks', $s, $html, $text);
    $html .= '<p data-alt="weeks">' . alt_briefing_h($line) . '</p>'
           . '<p data-alt="footnote">' . alt_briefing_h($foot) . '</p>';
    $text .= str_replace(" \xc2\xb7 ", "\n", $line) . "\n" . $foot . "\n";
    return array($html, $text);
}

/** Fetch, model, check, render. Null when the period cannot be read. */
function alt_briefing_compose($from, $to, $send_id = 0, $kind = 'weekly', $now = null) {
    $b = alt_briefing_fetch($from, $to, $kind);
    $m = alt_briefing_model($b, $now);
    if ($m === null) return null;
    $out = alt_briefing_render($m, $send_id);
    $bad = alt_briefing_check_links($out['html'], $m);
    foreach ($bad as $u) {
        if (function_exists('error_log')) error_log('[alt-briefing] held link ' . $u);
        $out['html'] = str_replace('href="' . esc_url($u) . '"', '', $out['html']);
        $m['held'][] = array('claim' => 'link', 'why' => $u);
    }
    $out['checks'] = $m['checks'];
    $out['held'] = $m['held'];
    return $out;
}
