<?php
/**
 * THE TALENT BRIEFING ("Who's hiring"), the same shape as the layoff briefing
 * (digest-briefing.php) for the talent section: an opening sentence, at a
 * glance by region, three things worth knowing, biggest hiring this period
 * grouped Around the world, an 8-week trend with a plain summary, top
 * industries and countries, and explore links. Daily, weekly and monthly
 * lengths come from the same parts.
 *
 * THE UNIT IS A SIGNAL, NOT A JOB. Talent rows are published indications
 * (mostly unverified reports), so every figure here counts signals and the
 * noun comes from alt_digest_talent_signal_noun, never "jobs".
 *
 * WHY THE ROWS ARE READ, NOT ONLY /talent/v1/aggregate. Its by_country list is
 * capped (40 entries in Week 44 2026 summed to 542 of 921 signals), so a
 * "not recorded" bucket computed from it would absorb the capped tail and
 * be wrong. Regions, countries and industries are counted from every row of
 * the window instead, and the row count must equal the aggregate total: if
 * it does not, those claims are HELD (omitted and logged), never estimated.
 *
 * Rule-based text only. Switch: option `alt_digest_talent_briefing_tiers`
 * (default all three tiers; `none` restores alt_digest_compose_talent).
 */

if (!defined('ABSPATH')) exit;

function alt_talent_briefing_enabled($freq) {
    $freq = strtolower(trim((string) $freq));
    $tiers = function_exists('get_option')
        ? (string) get_option('alt_digest_talent_briefing_tiers', 'daily,weekly,monthly')
        : 'daily,weekly,monthly';
    return in_array($freq, array_map('trim', explode(',', strtolower($tiers))), true);
}

function alt_talent_industry_label($slug) {
    $map = array('energy_utilities' => 'Energy & Utilities', 'retail_ecommerce' => 'Retail & E-commerce',
                 'food_beverage' => 'Food & Beverage', 'financial_services' => 'Financial Services',
                 'media_entertainment' => 'Media & Entertainment', 'real_estate' => 'Real Estate',
                 'travel_hospitality' => 'Travel & Hospitality');
    $slug = strtolower(trim((string) $slug));
    if ($slug === '') return '';
    return $map[$slug] ?? ucwords(str_replace('_', ' ', $slug));
}

function alt_talent_country_name($code) {
    $code = strtoupper(trim((string) $code));
    if ($code === 'GB') return 'United Kingdom';
    if ($code === 'US') return 'United States';
    if ($code === 'AE') return 'United Arab Emirates';
    $n = function_exists('alt_digest_iso2_country_name') ? alt_digest_iso2_country_name($code) : '';
    return $n !== '' ? $n : $code;
}

function alt_talent_fetch($from, $to, $kind) {
    $agg = alt_briefing_get('/talent/v1/aggregate', array('since' => $from, 'until' => $to));
    $rows = array();
    $complete = false;
    for ($page = 1; $page <= 40; $page++) {
        $q = alt_briefing_get('/talent/v1/query', array('since' => $from, 'until' => $to,
                                                       'per_page' => 200, 'page' => $page));
        if (!is_array($q) || !isset($q['rows'])) break;
        foreach ((array) $q['rows'] as $r) $rows[] = (array) $r;
        if (count($rows) >= (int) ($q['total'] ?? 0) || !$q['rows']) { $complete = true; break; }
    }
    $weeks = array();
    if ($kind !== 'daily') {
        $ft = strtotime(alt_briefing_monday($to) . ' 00:00:00 UTC');
        for ($k = 7; $k >= 0; $k--) {
            $w_from = gmdate('Y-m-d', $ft - 7 * $k * DAY_IN_SECONDS);
            $w_to = gmdate('Y-m-d', $ft - 7 * $k * DAY_IN_SECONDS + 6 * DAY_IN_SECONDS);
            $w = ($kind === 'weekly' && $k === 0) ? $agg
                : alt_briefing_get('/talent/v1/aggregate', array('since' => $w_from, 'until' => $w_to));
            $weeks[] = array('from' => $w_from, 'to' => $w_to,
                             'n' => (is_array($w) && isset($w['total'])) ? (int) $w['total'] : null);
        }
    }
    $wtd = null;
    if ($kind === 'daily') {
        $w = alt_briefing_get('/talent/v1/aggregate', array('since' => alt_briefing_monday($to), 'until' => $to));
        $wtd = (is_array($w) && isset($w['total'])) ? (int) $w['total'] : null;
    }
    return array('from' => $from, 'to' => $to, 'kind' => $kind, 'agg' => $agg,
                 'rows' => $complete ? $rows : null, 'weeks' => $weeks, 'wtd' => $wtd);
}

function alt_talent_headcount($r) {
    return (int) preg_replace('/\D.*$/', '', (string) ($r['headcount'] ?? ''));
}

function alt_talent_model($b, $now = null) {
    $now = ($now === null) ? time() : (int) $now;
    $agg = $b['agg'];
    if (!is_array($agg) || !isset($agg['total'])) return null;
    $total = (int) $agg['total'];
    if ($total <= 0) return null;
    $hiring_n = null;
    foreach ((array) ($agg['by_direction'] ?? array()) as $d) {
        if (($d['k'] ?? '') === 'hiring') $hiring_n = (int) $d['n'];
    }
    $m = array('from' => $b['from'], 'to' => $b['to'], 'kind' => $b['kind'], 'now' => $now,
               'range' => alt_digest_date_range($b['from'], $b['to']),
               'short' => alt_digest_short_range($b['from'], $b['to']),
               'edition' => alt_digest_edition_label($b['from'], $b['to']),
               'total' => $total, 'hiring' => (int) $hiring_n,
               'companies' => (int) ($agg['companies'] ?? 0),
               'headcount_n' => (int) ($agg['stated_headcount'] ?? 0),
               'noun' => alt_digest_talent_signal_noun($total, $hiring_n),
               'wtd' => $b['wtd'], 'held' => array(), 'checks' => array());
    $rows = $b['rows'];
    $m['rows'] = $rows;
    $countries = array();
    $industries = array();
    if ($rows !== null) {
        foreach ($rows as $r) {
            // Where the signal is, else the employer's HQ: the same COALESCE
            // /talent/v1/aggregate's by_country uses (checked below).
            $c = trim((string) ($r['country'] ?? ''));
            if ($c === '') $c = trim((string) ($r['hq_country'] ?? ''));
            if ($c !== '') {
                $name = alt_talent_country_name($c);
                $countries[$name] = ($countries[$name] ?? 0) + 1;
            }
            $i = alt_talent_industry_label($r['industry'] ?? '');
            if ($i !== '') $industries[$i] = ($industries[$i] ?? 0) + 1;
        }
        arsort($countries);
        arsort($industries);
    }
    $m['countries'] = $countries;
    $m['agg_countries'] = array();
    foreach ((array) ($agg['by_country'] ?? array()) as $c) {
        $m['agg_countries'][alt_talent_country_name($c['k'] ?? '')] = (int) ($c['n'] ?? 0);
    }
    $m['industries'] = $industries;
    list($m['regions'], $m['unplaced']) = alt_briefing_regions($countries, $total);
    $hire = array();
    foreach ((array) $rows as $r) {
        if (($r['signal_direction'] ?? '') !== 'hiring') continue;
        $hire[] = $r;
    }
    usort($hire, function ($a, $c) {
        return alt_talent_headcount($c) - alt_talent_headcount($a)
            ?: strcmp((string) ($c['materiality'] ?? ''), (string) ($a['materiality'] ?? ''));
    });
    $m['hire'] = $hire;
    $m['weeks'] = array();
    foreach ((array) $b['weeks'] as $w) {
        $settle = (int) floor(($now - strtotime($w['to'] . ' 23:59:59 UTC')) / DAY_IN_SECONDS) + 1;
        $w['provisional'] = $settle < alt_briefing_settle_days();
        $m['weeks'][] = $w;
    }
    $settled = array();
    foreach ($m['weeks'] as $i => $w) {
        if ($i === count($m['weeks']) - 1 && $w['provisional']) continue;
        if ($w['n'] !== null) $settled[] = $w['n'];
    }
    $m['avg'] = $settled ? array_sum($settled) / count($settled) : null;
    $m['median'] = alt_briefing_median(array_column($m['weeks'], 'n'));
    $m['outliers'] = array();
    if ($m['median']) {
        foreach ($m['weeks'] as $w) {
            if ($w['n'] !== null && $w['n'] > alt_briefing_outlier_factor() * $m['median']) $m['outliers'][] = $w;
        }
    }
    $m['provisional'] = ((int) floor(($now - strtotime($b['to'] . ' 23:59:59 UTC')) / DAY_IN_SECONDS) + 1) < alt_briefing_settle_days();
    alt_talent_checks($m);
    $m['findings'] = alt_talent_findings($m);
    foreach ($m['held'] as $h) {
        if (function_exists('error_log')) error_log('[alt-talent-briefing] held ' . $h['claim'] . ': ' . $h['why']);
    }
    return $m;
}

/** Pre-send checks, same contract as alt_briefing_checks: a FAIL holds the claim. */
function alt_talent_checks(&$m) {
    $hold = function ($claim, $why) use (&$m) { $m['held'][] = array('claim' => $claim, 'why' => $why); };
    if ($m['rows'] === null) {
        $m['checks']['rows_reconcile'] = 'UNKNOWN';
        $hold('geography', 'row list unavailable or incomplete');
    } elseif (count($m['rows']) !== $m['total']) {
        $m['checks']['rows_reconcile'] = 'FAIL';
        $hold('geography', count($m['rows']) . ' rows read, aggregate says ' . $m['total']);
    } else {
        $m['checks']['rows_reconcile'] = 'PASS';
    }
    // The row-derived country counts must match the aggregate's own list for
    // every country it names (that list is capped, so only its entries).
    if ($m['checks']['rows_reconcile'] === 'PASS') {
        $off = array();
        foreach ($m['agg_countries'] as $c => $n) {
            if ((int) ($m['countries'][$c] ?? 0) !== $n) $off[] = $c;
        }
        $m['checks']['countries_match_aggregate'] = $off ? 'FAIL' : 'PASS';
        if ($off) {
            $m['checks']['rows_reconcile'] = 'FAIL';
            $hold('geography', 'country counts differ from the aggregate for ' . implode(', ', array_slice($off, 0, 5)));
        }
    }
    if ($m['checks']['rows_reconcile'] !== 'PASS') {
        $m['regions'] = array(); $m['countries'] = array(); $m['industries'] = array(); $m['hire'] = array();
    }
    $sum = array_sum(array_column($m['regions'], 'jobs'));
    $ok = !$m['regions'] || $sum === $m['total'];
    foreach ($m['regions'] as $r) {
        if ($r['sub'] && array_sum(array_column($r['sub'], 1)) !== $r['jobs']) $ok = false;
    }
    $m['checks']['regions_reconcile'] = $ok ? 'PASS' : 'FAIL';
    if (!$ok) { $hold('regions', "region rows sum to $sum, total is {$m['total']}"); $m['regions'] = array(); }
    $ids = array();
    $dups = array();
    foreach ((array) $m['rows'] as $r) {
        $id = (string) ($r['signal_id'] ?? '');
        if ($id !== '' && isset($ids[$id])) $dups[] = $id;
        $ids[$id] = true;
    }
    $m['checks']['duplicates'] = $dups ? 'FAIL' : 'PASS';
    if ($dups) {
        $hold('hiring list', 'duplicate signal ids ' . implode(',', array_slice($dups, 0, 5)));
        $seen = array();
        $m['hire'] = array_values(array_filter($m['hire'], function ($r) use (&$seen) {
            $id = (string) ($r['signal_id'] ?? '');
            if (isset($seen[$id])) return false;
            $seen[$id] = true;
            return true;
        }));
    }
    $gap = $m['weeks'] && in_array(null, array_column($m['weeks'], 'n'), true);
    $m['checks']['weeks_complete'] = $gap ? 'FAIL' : 'PASS';
    if ($gap) { $hold('trend', 'a week did not load'); $m['weeks'] = array(); $m['outliers'] = array(); }
    $m['checks']['outlier'] = $m['outliers'] ? 'NOTE' : 'PASS';
}

function alt_talent_findings($m) {
    $f = array();
    $t = $m['total'];
    if ($m['hiring'] > 0) {
        $f[] = alt_digest_count($m['hiring'], 'signal') . ' (' . alt_briefing_pct($m['hiring'], $t)
             . ') pointed to employers adding roles' . ($m['headcount_n'] > 0
                 ? ', and ' . alt_digest_count($m['headcount_n'], 'signal') . ' stated a headcount' : '') . '.';
    }
    if ($m['countries']) {
        $c = array_key_first($m['countries']);
        $f[] = $c . ' had the most signals, ' . alt_digest_number($m['countries'][$c]) . ' ('
             . alt_briefing_pct($m['countries'][$c], $t) . ').';
    }
    if ($m['hire']) {
        $top = $m['hire'][0];
        $hc = alt_talent_headcount($top);
        if ($hc > 0) {
            $f[] = 'The largest stated hiring plan was ' . alt_digest_clean_employer($top['company'])
                 . ', ' . alt_digest_number($hc) . ' roles' . (($top['city'] ?? '') !== '' ? ' in ' . $top['city'] : '') . '.';
        }
    }
    if (count($f) < 3 && $m['industries']) {
        $i = array_key_first($m['industries']);
        $f[] = $i . ' led the industries with ' . alt_digest_count($m['industries'][$i], 'signal') . '.';
    }
    return array_slice($f, 0, 3);
}

function alt_talent_opening($m) {
    $n = alt_digest_count($m['total'], $m['noun']);
    $lead = '';
    if ($m['hire']) {
        $top = $m['hire'][0];
        $where = ($top['city'] ?? '') !== '' ? $top['city'] : alt_talent_country_name($top['country'] ?? '');
        $lead = ', led by ' . alt_digest_clean_employer($top['company']) . ($where !== '' ? ' in ' . $where : '');
    }
    $hiring = $m['hiring'] > 0 ? ', ' . alt_digest_number($m['hiring']) . ' of them about adding roles' : '';
    if ($m['kind'] === 'daily') return 'On ' . $m['range'] . ', we recorded ' . $n . $hiring . $lead . '.';
    if ($m['kind'] === 'monthly') {
        return 'In ' . gmdate('F Y', strtotime($m['from'] . ' 00:00:00 UTC')) . ', we recorded ' . $n . $hiring . $lead . '.';
    }
    $tone = 'This week';
    if ($m['avg']) {
        $tone = ($m['total'] < 0.75 * $m['avg']) ? 'A quieter week'
              : (($m['total'] > 1.25 * $m['avg']) ? 'A busier week' : 'A typical week');
    }
    if ($m['provisional']) $tone .= ' so far';
    return $tone . ': ' . $n . $hiring . $lead . '.';
}

/**
 * THE TWO KINDS OF HIRING NUMBER, NEVER RANKED TOGETHER (owner, 2026-11-03).
 *
 * The Nov 3 daily ranked "Cohere 1,500 roles" (a plan an employer announced,
 * read from press) beside "ZipRecruiter 8 roles" (open listings counted on a
 * Greenhouse or Ashby board). They measure different things, so a reader
 * comparing them compares nothing. Each hiring row is labelled by type and
 * ranked only against rows of its own type. alt_digest_talent_is_scan is the
 * one test for "a job-board reading", shared with the rest of the digest.
 */
function alt_talent_hiring_type($r) {
    return alt_digest_talent_is_scan($r) ? 'listings' : 'plan';
}

/** Hiring rows split by type, each ranked by stated roles (largest first). */
function alt_talent_hiring_by_type($hire) {
    $out = array('plan' => array(), 'listings' => array());
    foreach ((array) $hire as $r) $out[alt_talent_hiring_type($r)][] = $r;
    foreach ($out as $k => $rows) {
        usort($rows, function ($a, $c) {
            return alt_talent_headcount($c) - alt_talent_headcount($a)
                ?: strcmp((string) ($c['materiality'] ?? ''), (string) ($a['materiality'] ?? ''));
        });
        $out[$k] = $rows;
    }
    return $out;
}

/** "plans 1,500 roles" / "lists 8 open roles" / "plans to hire", for one row. */
function alt_talent_hiring_phrase($r) {
    $hc = alt_talent_headcount($r);
    if (alt_talent_hiring_type($r) === 'listings') {
        return $hc > 0 ? 'lists ' . alt_digest_count($hc, 'open role') : 'lists open roles';
    }
    return $hc > 0 ? 'plans ' . alt_digest_count($hc, 'role') : 'plans to hire';
}

/** The daily subject: the top hiring development, never a raw signal count. */
function alt_talent_daily_subject($m, $types) {
    $n = count($m['hire']);
    $top = $types['plan'][0] ?? ($types['listings'][0] ?? null);
    if ($top === null) return '';
    $where = trim((string) ($top['city'] ?? ''));
    if ($where === '') $where = alt_talent_country_name($top['country'] ?? '');
    $s = "Who's hiring: " . alt_digest_clean_employer($top['company']) . ' ' . alt_talent_hiring_phrase($top)
       . ($where !== '' ? ' in ' . $where : '');
    if ($n > 1) $s .= ' + ' . alt_digest_number($n - 1) . ' more';
    return $s;
}

function alt_talent_employer_key($r) {
    $k = strtolower(trim((string) ($r['company_key'] ?? '')));
    return $k !== '' ? $k : strtolower(trim((string) ($r['company'] ?? '')));
}

/**
 * Employer -> verified job board URL, read only from the window's own
 * job-board rows (collector ats_boards: the board the collector itself read
 * open roles from). Nothing is guessed: an employer with no such row gets no
 * board link (owner feedback 2026-11-05).
 */
function alt_talent_job_boards($rows) {
    $out = array();
    foreach ((array) $rows as $r) {
        $r = (array) $r;
        if (strtolower(trim((string) ($r['collector'] ?? ''))) !== 'ats_boards') continue;
        $u = trim((string) ($r['source_url'] ?? ''));
        if ($u === '' || !preg_match('#^https://#i', $u)) continue;
        if (function_exists('alt_digest_external_link_ok') && !alt_digest_external_link_ok($u)) continue;
        $k = alt_talent_employer_key($r);
        if ($k !== '' && !isset($out[$k])) $out[$k] = $u;
    }
    return $out;
}

/**
 * "Europe led with 32 signals, followed by North America with 30." The
 * largest placed region by the SAME counts Notes prints; "Not recorded" and
 * the catch-all never lead. A tie names every tied region. The old line took
 * the first region of the fixed display order (owner feedback 2026-11-05).
 */
function alt_talent_region_lead($regions) {
    $placed = array();
    foreach ((array) $regions as $r) {
        if ($r['region'] === 'Not recorded' || $r['region'] === 'Multiple or other countries') continue;
        if ((int) $r['jobs'] > 0) $placed[] = $r;
    }
    if (!$placed) return '';
    usort($placed, function ($a, $c) { return (int) $c['jobs'] - (int) $a['jobs']; });
    $top = (int) $placed[0]['jobs'];
    $lead = array(); $rest = array();
    foreach ($placed as $r) { if ((int) $r['jobs'] === $top) $lead[] = $r['region']; else $rest[] = $r; }
    $names = count($lead) > 1
        ? implode(', ', array_slice($lead, 0, -1)) . ' and ' . end($lead)
        : $lead[0];
    $s = 'By region, ' . $names . ' led with ' . alt_digest_count($top, 'signal') . (count($lead) > 1 ? ' each' : '');
    if ($rest) $s .= ', followed by ' . $rest[0]['region'] . ' with ' . alt_digest_number((int) $rest[0]['jobs']);
    return $s . '.';
}

/** One compact line per employer: flag, employer, number + type, place, source. */
function alt_talent_daily_line($r, $send_id, $boards = array()) {
    $country = alt_talent_country_name($r['country'] ?? '');
    $flag = function_exists('alt_digest_country_flag') ? alt_digest_country_flag($country) : '';
    $hc = alt_talent_headcount($r);
    $type = alt_talent_hiring_type($r) === 'listings' ? 'open listings' : 'announced plan';
    $fig = ($hc > 0 ? alt_digest_count($hc, 'role') : 'roles not stated') . ', ' . $type;
    $place = implode(', ', array_filter(array(trim((string) ($r['city'] ?? '')), $country)));
    $src = trim((string) ($r['source_url'] ?? ''));
    if ($src !== '' && function_exists('alt_digest_external_link_ok') && !alt_digest_external_link_ok($src)) $src = '';
    $src_name = trim((string) ($r['source_name'] ?? '')) ?: 'source';
    $name = alt_digest_clean_employer($r['company']);
    $lead = ($flag !== '' ? $flag . ' ' : '') . $name;
    $tail = ($place !== '' ? " \xc2\xb7 " . $place : '');
    // The employer's verified job board, only when the window holds one for
    // this employer and it is not already the row's own source link.
    $board = (string) ($boards[alt_talent_employer_key($r)] ?? '');
    if ($board === $src) $board = '';
    $html = '<p data-alt="item-line"><strong>' . esc_html($lead) . '</strong>: ' . esc_html($fig . $tail)
          . " \xc2\xb7 " . ($src !== '' ? '<a href="' . esc_url($src) . '">' . esc_html($src_name) . '</a>' : esc_html($src_name))
          . ($board !== '' ? " \xc2\xb7 " . '<a href="' . esc_url($board) . '">Open roles</a>' : '')
          . '</p>';
    $text = '  ' . $lead . ': ' . $fig . $tail . " \xc2\xb7 " . $src_name . ($src !== '' ? ' ' . $src : '')
          . ($board !== '' ? " \xc2\xb7 Open roles " . $board : '') . "\n";
    return array($html, $text);
}

/**
 * The daily's glance box (owner, 2026-11-06): the four facts, the three
 * types defined one line each, and the reported-signals caveat beside it.
 * The window is stated here once; there is no separate dateline.
 */
function alt_talent_daily_glance($m, $types, $n_hire, $n_other) {
    $facts = array('Hiring signals: ' . alt_digest_number($n_hire),
                   'Employer-activity signals: ' . alt_digest_number($n_other));
    foreach ($types['plan'] as $r) {
        $hc = alt_talent_headcount($r);
        if ($hc <= 0) continue;
        $where = trim((string) ($r['city'] ?? ''));
        if ($where === '') $where = alt_talent_country_name($r['country'] ?? '');
        $facts[] = 'Biggest announced plan: ' . alt_digest_clean_employer($r['company']) . ', '
                 . alt_digest_count($hc, 'role') . ($where !== '' ? ' in ' . $where : '');
        break;
    }
    $best = null;
    foreach ((array) $m['regions'] as $r) {
        if ($r['region'] === 'Not recorded' || $r['region'] === 'Multiple or other countries') continue;
        if ((int) $r['jobs'] > 0 && ($best === null || (int) $r['jobs'] > (int) $best['jobs'])) $best = $r;
    }
    if ($best !== null) $facts[] = 'Leading region: ' . $best['region'] . ', ' . alt_digest_count((int) $best['jobs'], 'signal');
    $defs = array('Announced hiring plans: roles an employer or report says it will add.',
                  'Open listings: roles live on career sites now.',
                  'Employer-activity signals: wider reports, not confirmed hiring.');
    $caveat = 'These are reported signals: most are not independently verified.';
    $title = 'At a glance (' . $m['short'] . ')';
    $html = '<table role="presentation" data-alt="glance" width="100%" cellpadding="0" cellspacing="0" border="0"'
          . ' style="width:100%;border-collapse:collapse;background-color:#eef1f5;border-radius:8px;margin:0 0 12px;">'
          . '<tr><td style="padding:12px 14px;"><p data-alt="glance-title"><strong>' . esc_html($title) . '</strong></p>';
    $text = $title . "\n";
    foreach ($facts as $f) { $html .= '<p data-alt="glance-fact">' . esc_html($f) . '</p>'; $text .= '  ' . $f . "\n"; }
    $html .= '<p data-alt="glance-note"><em>' . esc_html($caveat) . '</em></p></td></tr></table>';
    $text .= $caveat . "\n";
    foreach ($defs as $d) { $html .= '<p data-alt="note">' . esc_html($d) . '</p>'; $text .= $d . "\n"; }
    return array($html, $text);
}

/** Distinct employers behind the non-hiring signals; the aggregate when rows are absent. */
function alt_talent_other_employers($m) {
    if ($m['rows'] === null) return (int) $m['companies'];
    $seen = array();
    foreach ((array) $m['rows'] as $r) {
        if (($r['signal_direction'] ?? '') === 'hiring') continue;
        $k = alt_talent_employer_key($r);
        if ($k !== '') $seen[$k] = true;
    }
    return count($seen);
}

/**
 * THE DAILY, HUMAN FIRST (owner, 2026-11-03): a scan-in-ten-seconds summary.
 * Hiring signals lead; the all-signal total is one line of context; at most
 * five employers, one line each, announced plans and open listings in their
 * own ranked lists; the regional table is one line and a link, with the
 * detail under "How we count". Every figure stays on the tracker page.
 */
function alt_talent_render_daily($m, $send_id = 0) {
    $from = $m['from']; $to = $m['to'];
    $url = alt_digest_talent_url($from, $to);
    $hire_url = alt_digest_talent_url($from, $to, array('direction' => 'hiring'));
    $types = alt_talent_hiring_by_type($m['hire']);
    $boards = alt_talent_job_boards($m['rows']);
    $n_hire = count($m['hire']) ?: (int) $m['hiring'];
    $top = $types['plan'][0] ?? ($types['listings'][0] ?? null);
    if ($top !== null) {
        $where = trim((string) ($top['city'] ?? ''));
        if ($where === '') $where = alt_talent_country_name($top['country'] ?? '');
        $lead = alt_digest_count($n_hire, 'hiring signal') . ', led by ' . alt_digest_clean_employer($top['company'])
              . ' (' . alt_talent_hiring_phrase($top) . ($where !== '' ? ' in ' . $where : '') . ').';
    } else {
        $lead = alt_digest_count($n_hire, 'hiring signal') . ' in this window.';
    }
    $n_other = max(0, (int) $m['total'] - $n_hire);
    $html = "<h2>Who's hiring</h2>";
    $text = "Who's hiring\n";
    list($gh, $gt) = alt_talent_daily_glance($m, $types, $n_hire, $n_other);
    $html .= $gh; $text .= $gt;
    $html .= '<p data-alt="lead">' . esc_html($lead) . '</p>';
    $text .= "\n" . $lead . "\n";

    // Up to ten lines (owner, 2026-11-06): announced plans first (up to
    // six), open listings fill the rest, then unused room goes back to plans.
    $cap = 10;
    $np = min(6, count($types['plan']));
    $nl = min($cap - $np, count($types['listings']));
    $np = min($cap - $nl, count($types['plan']));
    $blocks = array(
        array('Announced hiring plans', 'From press reports, ranked by roles the employer said it will add.',
              array_slice($types['plan'], 0, $np)),
        array('Open listings', "Live counts from employers' job boards, ranked by open roles; a different measure from press plans, so never ranked with them.",
              array_slice($types['listings'], 0, $nl)),
    );
    $shown = 0;
    foreach ($blocks as $b) {
        if (!$b[2]) continue;
        alt_briefing_section($b[0], '', $html, $text);
        $html .= '<p data-alt="note">' . esc_html($b[1]) . '</p>';
        $text .= $b[1] . "\n";
        foreach ($b[2] as $r) {
            list($h, $t) = alt_talent_daily_line($r, $send_id, $boards);
            $html .= $h; $text .= $t; $shown++;
        }
    }
    if ($shown > 0) {
        $see = $shown < $n_hire
            ? alt_digest_number($shown) . ' featured, see all ' . alt_digest_count($n_hire, 'hiring signal')
            : 'See all ' . alt_digest_count($n_hire, 'hiring signal');
        $html .= '<p data-alt="more"><a href="' . esc_url(alt_digest_track_link($send_id, $hire_url)) . '">'
               . esc_html($see) . ' &rarr;</a></p>';
        $text .= '  ' . $see . ': ' . $hire_url . "\n";
    }
    // Same window as the hiring list: /talent/v1/aggregate over since..until,
    // inclusive, on COALESCE(published_date, DATE(captured_at)). `companies`
    // is COUNT(DISTINCT company_key), an exact count, so no "about".
    $ctx = 'Separately, ' . alt_digest_count($n_other, 'employer-activity signal') . ' from '
         . alt_digest_count(alt_talent_other_employers($m), 'employer') . '.';
    $html .= '<p data-alt="note">' . esc_html($ctx) . '</p>';
    $text .= "\n" . $ctx . "\n";
    $where = alt_talent_region_lead($m['regions']);
    if ($where !== '') {
        $html .= '<p data-alt="note">' . esc_html($where) . ' <a href="' . esc_url(alt_digest_track_link($send_id, $url))
               . '">See where &rarr;</a></p>';
        $text .= $where . ' See where: ' . $url . "\n";
    }

    $notes = array();
    if ($m['regions']) {
        $parts = array();
        foreach ($m['regions'] as $r) $parts[] = $r['region'] . ' ' . alt_digest_number($r['jobs']);
        $notes[] = 'Signals by region: ' . implode(" \xc2\xb7 ", $parts) . '.';
    }
    if ($m['unplaced'] > 0 && $m['regions']) {
        $notes[] = alt_digest_count($m['unplaced'], 'signal') . ($m['unplaced'] === 1 ? ' carries' : ' carry') . ' no country.';
    }
    if ($m['provisional']) $notes[] = 'Provisional: signals keep arriving for a few days after a period ends.';
    $read = alt_digest_date_range(gmdate('Y-m-d', $m['now']), gmdate('Y-m-d', $m['now'])) . ' at ' . gmdate('H:i', $m['now']) . ' UTC';
    $notes[] = 'Snapshot composed ' . $read . '.';
    alt_briefing_section('Notes', '', $html, $text);
    foreach ($notes as $n) { $html .= '<p data-alt="footnote">' . esc_html($n) . '</p>'; $text .= '  ' . $n . "\n"; }
    $method = home_url('/talent-intelligence-tracker/');
    $html .= '<p data-alt="footnote"><a href="' . esc_url($method) . '">About the talent tracker</a></p>';
    $text .= '  About the talent tracker: ' . $method . "\n";

    $subject = alt_talent_daily_subject($m, $types);
    $preheader = alt_digest_fit_preheader($lead, array());
    return array('html' => $html, 'text' => $text, 'preheader' => $preheader,
                 'metric' => $subject !== '' ? $subject : alt_digest_count($m['total'], $m['noun']));
}

function alt_talent_render($m, $send_id = 0) {
    if ($m['kind'] === 'daily') return alt_talent_render_daily($m, $send_id);
    $from = $m['from']; $to = $m['to']; $kind = $m['kind'];
    $url = alt_digest_talent_url($from, $to);
    $word = array('daily' => 'today', 'weekly' => 'this week', 'monthly' => 'this month')[$kind] ?? 'this period';
    $tag = $kind . ' briefing';
    $head = ($kind === 'weekly') ? $m['edition'] : $m['range'];
    $opening = alt_talent_opening($m);
    $html = "<h2>Who's hiring</h2><p data-alt=\"dateline\">" . esc_html($head . " \xc2\xb7 " . $tag) . '</p>'
          . '<p data-alt="lead">' . esc_html($opening) . '</p>';
    $text = "Who's hiring\n" . $head . " \xc2\xb7 " . $tag . "\n" . $opening . "\n";

    $glance = 'We recorded ' . alt_digest_count($m['total'], 'signal') . ' about ' . alt_digest_count($m['companies'], 'employer')
            . '; ' . alt_digest_number($m['hiring']) . ' point to roles being added. Signals are published reports, not verified hires.';
    alt_briefing_section(($kind === 'weekly' ? 'This week' : ucfirst($word)) . ' at a glance', $glance, $html, $text);
    list($ph, $pt) = alt_digest_stat_pair(array(
        array('label' => 'Signals', 'figure' => alt_digest_number($m['total']), 'unit' => 'talent and employer-activity signals',
              'url' => alt_digest_track_link($send_id, $url)),
        array('label' => 'Adding roles', 'figure' => alt_digest_number($m['hiring']), 'unit' => 'hiring signals',
              'url' => alt_digest_track_link($send_id, alt_digest_talent_url($from, $to, array('direction' => 'hiring')))),
    ));
    $html .= $ph; $text .= $pt;
    if ($m['regions']) {
        $html .= '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">';
        $text .= "  By region:\n";
        $last = count($m['regions']) - 1;
        foreach ($m['regions'] as $i => $r) {
            $edge = ($i === $last) ? '-last' : '';
            $subs = array();
            foreach ($r['sub'] as $s) $subs[] = $s[0] . ' ' . alt_digest_number($s[1]);
            $label = $r['region'] . ($subs ? ' (' . implode(" \xc2\xb7 ", $subs) . ')' : '');
            $html .= '<tr><td data-alt="label' . $edge . '">' . esc_html($label) . '</td><td data-alt="figure' . $edge
                   . '" align="right" width="30%">' . esc_html(alt_digest_number($r['jobs'])) . '</td></tr>';
            $text .= '    ' . $label . ': ' . alt_digest_number($r['jobs']) . "\n";
        }
        $html .= '</table>';
    }
    if ($m['provisional']) {
        $note = 'Provisional: signals keep arriving for a few days after a period ends.';
        $html .= '<p data-alt="note">' . esc_html($note) . '</p>';
        $text .= '  ' . $note . "\n";
    }

    if ($kind !== 'daily' && $m['findings']) {
        alt_briefing_section('Three things worth knowing', '', $html, $text);
        $html .= '<ul>';
        foreach ($m['findings'] as $f) { $html .= '<li>' . esc_html($f) . '</li>'; $text .= '  - ' . $f . "\n"; }
        $html .= '</ul>';
    }

    // Biggest hiring this period, grouped Around the world.
    $cap = ($kind === 'daily') ? 40 : (($kind === 'monthly') ? 10 : 6);
    $rows = array_slice($m['hire'], 0, $cap);
    if ($rows) {
        alt_briefing_section('Biggest hiring ' . $word . ' (' . $m['short'] . ')',
            'Signals about employers adding roles, largest stated headcount first, each with its source.', $html, $text);
        $items = array();
        foreach ($rows as $r) {
            $country = alt_talent_country_name($r['country'] ?? '');
            $hc = alt_talent_headcount($r);
            $place = implode(', ', array_filter(array((string) ($r['city'] ?? ''), $country)));
            $src = trim((string) ($r['source_url'] ?? ''));
            if ($src !== '' && function_exists('alt_digest_external_link_ok') && !alt_digest_external_link_ok($src)) $src = '';
            $items[] = array(
                'label' => (string) $r['company'], 'figure' => $hc > 0 ? alt_digest_number($hc) . ' roles' : 'roles not stated',
                'suffix' => '(' . ($place !== '' ? $place . '; ' : '') . ($r['source_name'] ?? 'report') . ')',
                'url' => alt_digest_track_link($send_id, alt_digest_talent_url($from, $to, array('company' => $r['company']))),
                'plain_url' => '', 'source_url' => $src,
                'pills' => array(alt_digest_place_pill($place), alt_digest_pill((string) ($r['source_name'] ?? ''), '', true)),
                'geo' => array('country' => $country, 'state' => ($country === 'United States') ? (string) ($r['state'] ?? '') : '',
                               'city' => (string) ($r['city'] ?? '')),
            );
        }
        list($wh, $wt) = function_exists('alt_digest_world_cards')
            ? alt_digest_world_cards($items, 'alt_digest_rank_cards') : alt_digest_rank_cards($items);
        $html .= $wh; $text .= $wt;
        $more = count($m['hire']) - count($rows);
        if ($more > 0) {
            $line = 'See ' . alt_digest_count($more, 'more hiring signal') . ' ' . $word;
            $html .= '<p data-alt="more"><a href="' . esc_url(alt_digest_track_link($send_id, alt_digest_talent_url($from, $to, array('direction' => 'hiring'))))
                   . '">' . esc_html($line) . ' &rarr;</a></p>';
            $text .= '  ' . $line . "\n";
        }
    }
    if ($kind === 'daily' && $m['wtd'] !== null) {
        $w = 'This week so far: ' . alt_digest_count($m['wtd'], 'signal') . '.';
        $html .= '<p>' . esc_html($w) . '</p>'; $text .= "\n" . $w . "\n";
    }

    if ($kind !== 'daily') {
        if (count($m['weeks']) === 8) {
            $cur = $m['weeks'][7];
            $s = ($kind === 'monthly' ? 'The latest week' : 'This week') . ': ' . alt_digest_number($cur['n']);
            if ($m['avg'] !== null) {
                $s .= ', ' . ($cur['n'] < $m['avg'] ? 'below' : 'above') . ' the 8-week average of '
                    . alt_digest_number((int) round($m['avg']));
            }
            $s .= '.';
            foreach ($m['outliers'] as $o) {
                $s .= ' The ' . alt_digest_short_range($o['from'], $o['to']) . ' week was unusually high ('
                    . alt_digest_number($o['n']) . ').';
            }
            $items = array();
            foreach (array_reverse($m['weeks']) as $w) {
                $items[] = alt_digest_short_range($w['from'], $w['to']) . ($w['provisional'] ? ' (still being counted)' : '')
                         . ' ' . alt_digest_number($w['n']);
            }
            $line = implode(" \xc2\xb7 ", $items);
            $foot = 'Signals per week. The average leaves out the current week, which is still being counted; recent weeks are not compared by percentage.';
            alt_briefing_section('Last 8 weeks', $s, $html, $text);
            $html .= '<p data-alt="weeks">' . esc_html($line) . '</p><p data-alt="footnote">' . esc_html($foot) . '</p>';
            $text .= str_replace(" \xc2\xb7 ", "\n", $line) . "\n" . $foot . "\n";
        }
        if ($m['industries'] || $m['countries']) {
            $lead = array();
            if ($m['industries']) $lead[] = array_key_first($m['industries']) . ' led the industries';
            if ($m['countries']) $lead[] = array_key_first($m['countries']) . ' the countries';
            alt_briefing_section('Where and in what', ucfirst(implode(', and ', $lead)) . '.', $html, $text);
            foreach (array('Top industries' => $m['industries'], 'Top countries' => $m['countries']) as $title => $list) {
                if (!$list) continue;
                $its = array();
                foreach (array_slice($list, 0, 3, true) as $k => $v) $its[] = $k . ' ' . alt_digest_number($v);
                $l = $title . ': ' . implode(" \xc2\xb7 ", $its);
                $html .= '<p data-alt="series">' . esc_html($l) . '</p>'; $text .= '  ' . $l . "\n";
            }
            $html .= '<p data-alt="more"><a href="' . esc_url(alt_digest_track_link($send_id, $url)) . '">See the full breakdown &rarr;</a></p>';
            $text .= '  See the full breakdown: ' . $url . "\n";
        }
    }

    $method = home_url('/talent-intelligence-tracker/');
    alt_briefing_section('Explore the data', 'Every link opens on the same dates.', $html, $text);
    foreach (array(array('Open the talent tracker for ' . $m['range'], alt_digest_track_link($send_id, $url), $url),
                   array('Hiring signals only', alt_digest_talent_url($from, $to, array('direction' => 'hiring')),
                         alt_digest_talent_url($from, $to, array('direction' => 'hiring')))) as $l) {
        $html .= '<p><a href="' . esc_url($l[1]) . '">' . esc_html($l[0]) . '</a></p>';
        $text .= '  ' . $l[0] . ': ' . $l[2] . "\n";
    }
    $notes = array();
    if ($m['unplaced'] > 0 && $m['regions']) $notes[] = alt_digest_count($m['unplaced'], 'signal') . ' carry no country.';
    $read = alt_digest_date_range(gmdate('Y-m-d', $m['now']), gmdate('Y-m-d', $m['now'])) . ' at ' . gmdate('H:i', $m['now']) . ' UTC';
    $notes[] = 'Snapshot composed ' . $read . '. A signal is a published report about an employer; most are not independently verified.';
    alt_briefing_section('Notes', '', $html, $text);
    foreach ($notes as $n) { $html .= '<p data-alt="footnote">' . esc_html($n) . '</p>'; $text .= '  ' . $n . "\n"; }
    $html .= '<p data-alt="footnote"><a href="' . esc_url($method) . '">About the talent tracker</a></p>';
    $text .= '  About the talent tracker: ' . $method . "\n";

    $preheader = alt_digest_fit_preheader(alt_digest_count($m['hiring'], 'hiring signal'),
        array('across ' . alt_digest_count($m['companies'], 'employer'), $m['provisional'] ? 'provisional' : ''));
    return array('html' => $html, 'text' => $text, 'preheader' => $preheader,
                 'metric' => alt_digest_count($m['total'], $m['noun']));
}

/** Talent links: well formed, on our host, and on this window. */
function alt_talent_check_links($html, $m) {
    $bad = array();
    preg_match_all('/href="([^"]+)"/', $html, $all);
    foreach (array_unique($all[1]) as $url) {
        $u = html_entity_decode($url, ENT_QUOTES);
        if (strpos($u, home_url('/')) !== 0) continue;
        if (!filter_var($u, FILTER_VALIDATE_URL)) { $bad[] = $u; continue; }
        if (strpos($u, '/talent-intelligence-tracker/?') === false) continue;
        parse_str((string) parse_url($u, PHP_URL_QUERY), $q);
        if (($q['since'] ?? '') !== $m['from'] || ($q['until'] ?? '') !== $m['to']) $bad[] = $u;
    }
    return $bad;
}

function alt_talent_briefing_compose($from, $to, $send_id = 0, $kind = 'weekly', $now = null) {
    if (!function_exists('alt_briefing_get')) return null;
    $m = alt_talent_model(alt_talent_fetch($from, $to, $kind), $now);
    if ($m === null) return null;
    $out = alt_talent_render($m, $send_id);
    foreach (alt_talent_check_links($out['html'], $m) as $u) {
        if (function_exists('error_log')) error_log('[alt-talent-briefing] held link ' . $u);
        $out['html'] = str_replace('href="' . esc_url($u) . '"', '', $out['html']);
        $m['held'][] = array('claim' => 'link', 'why' => $u);
    }
    $out['checks'] = $m['checks'];
    $out['held'] = $m['held'];
    return $out;
}
