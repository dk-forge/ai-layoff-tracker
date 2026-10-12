<?php
/**
 * SUBSCRIBER EMAIL REDESIGN, SLICE 1 (owner approval 2026-09-29, sandbox debt
 * row DIGEST-EMAIL-REDESIGN-APPROVED). Data-only additions to the layoff
 * section, modelled on the newsletters that do this well:
 *
 *   - the subject carries the top story, and that story is the first row of
 *     the body's "Biggest cuts" table, so subject and body match;
 *   - an 8-week strip of verified job cuts under the change-since-last-week;
 *   - each of the top 3 biggest cuts carries its stated reason;
 *   - one computed "why it matters" line (Axios style) derived from the data.
 *
 * PURE FUNCTIONS ONLY. No query, no option, no request: the composer in
 * subscribe.php fetches, these decide wording. That is what lets
 * railway/tests/test_digest_extras.py run every one of them under the php CLI
 * with no WordPress loaded. Every caller guards with function_exists(),
 * because an FTP deploy can land subscribe.php before this file.
 *
 * NO FIGURE IS INVENTED. An input that is missing produces no clause and no
 * line, never a zero, a carried-forward value or a guess.
 */

if (!function_exists('alt_digest_fmt')) {
    /** Thousands separators, the digest's one number shape. */
    function alt_digest_fmt($n) {
        return number_format((float) $n, 0, '.', ',');
    }
}

/**
 * The largest VERIFIED row of the leaders list, or null.
 *
 * Announced rows sit outside the verified headline, and a row resting on one
 * outlet's report was taken out of the lead by the owner's 2026-09-12 ruling,
 * so neither can be the story the subject leads with. Leaders arrive sorted
 * by job_count, so the first row that qualifies is the largest one.
 *
 * $single_report is a callable deciding the one-outlet question, passed in so
 * this uses alt_digest_single_report() (the same test the table uses) without
 * depending on load order.
 */
function alt_digest_top_story($leaders, $single_report = null) {
    foreach ((array) $leaders as $l) {
        $l = (array) $l;
        $name = trim((string) ($l['company_name'] ?? ''));
        $jobs = (int) ($l['job_count'] ?? 0);
        if ($name === '' || $jobs <= 0) continue;
        if (!array_key_exists('announced', $l)) return null;   // tier UNKNOWN
        if (!empty($l['announced'])) continue;
        if ($single_report && call_user_func($single_report, $l)) continue;
        return array('company' => $name, 'jobs' => $jobs);
    }
    return null;
}

/**
 * An employer name as a reader says it: legal suffixes and "(aka ...)" go.
 * Owner feedback 2026-10-12: "Community Healthlink, Inc. (aka CHL)" in a
 * subject is noise. Display only; the stored name is untouched.
 */
function alt_digest_clean_employer($name) {
    $name = trim((string) $name);
    $name = preg_replace('/\s*\((?:aka|a\.k\.a\.|formerly|dba)\b[^)]*\)/i', '', $name);
    $name = preg_replace('/[,\s]+(?:Inc|Incorporated|LLC|L\.L\.C|Ltd|Limited|Corp|Corporation|Co|Company|PLC|LLP|LP|GmbH|S\.A|N\.V|AG|Oyj|AB)\.?$/i', '', $name);
    return trim($name, " ,");
}

/**
 * The layoff section's subject fragment: its figure, then its top story.
 *
 *     4,139 verified job cuts · Community Healthlink leads
 *
 * Owner feedback 2026-10-12: short, no parenthesised count. The employer and
 * nothing else, so the subject can never imply an AI figure
 * (tests/test_digest_subject_never_inflates_ai.py). A name still too long
 * after cleaning is dropped rather than cut.
 */
function alt_digest_story_metric($metric, $story) {
    $metric = trim((string) $metric);
    if ($metric === '' || !is_array($story)) return $metric;
    $name = alt_digest_clean_employer($story['company'] ?? '');
    $jobs = (int) ($story['jobs'] ?? 0);
    if ($name === '' || $jobs <= 0) return $metric;
    $len = function_exists('mb_strlen') ? mb_strlen($name, 'UTF-8') : strlen($name);
    if ($len > 28) return $metric;
    return $metric . " \xc2\xb7 " . $name . ' leads';
}

/**
 * One comparison line under a hero number: "▼ 72% vs last week", or null.
 *
 * Null when there is no prior figure or the prior week is not yet comparable
 * ($like_for_like false). The caller then says "Last week still being
 * counted" ONCE, and the caveat lives in the footnote, not on every number.
 * Returns array(line, 'up'|'down'|'level'); the direction picks the colour
 * (up = red, down = green) and the glyph + words carry it without colour.
 */
function alt_digest_change_line($now, $before, $like_for_like) {
    if ($before === null || !$like_for_like) return null;
    $now = (int) $now; $before = (int) $before;
    if ($before <= 0) return null;
    if ($now === $before) return array('= level with last week', 'level');
    $share = 100 * abs($now - $before) / $before;
    $pct = ($share < 1 ? number_format($share, 1) : (string) round($share)) . '%';
    $up = $now > $before;
    return array(($up ? "\xe2\x96\xb2 " : "\xe2\x96\xbc ") . $pct . ' vs last week',
                 $up ? 'up' : 'down');
}

/**
 * The tracker's reason vocabulary in the page's own spellings (REASON_LABELS,
 * assets/layoffs.js). The "Why" block in subscribe.php prints the same map.
 */
function alt_digest_reason_names() {
    return array(
        'ai_automation'           => 'Reason tag: AI or automation',
        'possible_ai'             => 'Reason tag: AI press-linked',
        'revenue_decline'         => 'Revenue decline',
        'restructuring'           => 'Restructuring',
        'merger_acquisition'      => 'Merger / acquisition',
        'offshoring'              => 'Offshoring',
        'product_discontinuation' => 'Product discontinued',
        'cost_reduction'          => 'Cost reduction',
        'macroeconomic'           => 'Macroeconomic',
        'closure'                 => 'Plant / site closure',
    );
}

/**
 * "reason: Restructuring, Cost reduction" for one row, or '' when the row
 * carries no tag this vocabulary knows. Packed (",a,b,") or array input.
 *
 * The two AI tags are NOT printed here. An AI-attributed row already says
 * "AI attributed" from the ai_explicit column, and the possible_ai tag is the
 * press-linked tier, which on a row the reader reads as "the employer said AI"
 * when it means the opposite. Leaving them out keeps the row's AI claim to
 * the one column that is allowed to make it.
 */
function alt_digest_reason_phrase($tags) {
    if (is_string($tags)) $tags = explode(',', $tags);
    $names = alt_digest_reason_names();
    $out = array();
    foreach ((array) $tags as $tag) {
        $tag = trim((string) $tag);
        if ($tag === '' || $tag === 'ai_automation' || $tag === 'possible_ai') continue;
        if (!isset($names[$tag]) || in_array($names[$tag], $out, true)) continue;
        $out[] = $names[$tag];
        if (count($out) === 2) break;
    }
    return $out ? 'reason: ' . implode(', ', $out) : '';
}

/**
 * ONE COMPUTED "WHY IT MATTERS" LINE, or '' when the data cannot carry one.
 *
 * It says how concentrated the period was, which is the fact a reader needs
 * to weigh the headline: one decision moving the total reads very differently
 * from many employers cutting at once. It is SILENT when the dominant-entry
 * sentence already fired ($dominant), because that sentence makes the same
 * point more strongly and two lines saying it is noise.
 *
 * Both figures come from the same response the headline prints. The share is
 * of the VERIFIED total, which contains the story (the story is verified by
 * construction in alt_digest_top_story).
 */
function alt_digest_why_line($story, $ver_jobs, $dominant = false) {
    $ver_jobs = (int) $ver_jobs;
    if ($dominant || !is_array($story) || $ver_jobs <= 0) return '';
    $jobs = (int) ($story['jobs'] ?? 0);
    $name = trim((string) ($story['company'] ?? ''));
    if ($jobs <= 0 || $name === '' || $jobs > $ver_jobs) return '';
    $pct = (int) round($jobs * 100 / $ver_jobs);
    if ($jobs === $ver_jobs) {
        return 'Why it matters: every verified cut in this period is one employer, '
             . $name . ', so a single decision is the whole figure.';
    }
    if ($pct >= 25) {
        return 'Why it matters: one employer, ' . $name . ', is ' . $pct
             . '% of the verified total, so the headline rests heavily on a single decision.';
    }
    $share = ($pct < 1) ? 'under 1%' : ($pct . '%');
    return 'Why it matters: the cuts were spread out. The largest, ' . $name
         . ' at ' . alt_digest_fmt($jobs) . ', is ' . $share
         . ' of the verified total, so no single decision drives the headline.';
}

/**
 * THE 8-WEEK STRIP, as a series line the relay draws bars under.
 *
 * $weeks: oldest first, each array('label' => 'Aug 10', 'jobs' => int|null).
 * A week whose fetch failed is null and the WHOLE strip is withheld: a gap
 * drawn as a zero would be an invented figure, and a strip with a hole in it
 * reads as a week with no cuts. Fewer than 8 weeks is also withheld.
 *
 * Returns array(html, text), both '' when withheld. The bars are added by
 * railway/digest_design.py from this same line and are aria-hidden; every
 * figure is in the text, so a screen reader and the plain-text part lose
 * nothing.
 */
function alt_digest_week_strip($weeks) {
    $weeks = array_values((array) $weeks);
    if (count($weeks) !== 8) return array('', '');
    $items = array();
    foreach ($weeks as $w) {
        $w = (array) $w;
        $label = trim((string) ($w['label'] ?? ''));
        if ($label === '' || !isset($w['jobs']) || $w['jobs'] === null) return array('', '');
        $items[] = $label . ' ' . alt_digest_fmt((int) $w['jobs']);
    }
    /*
      ONE VISUAL, NO DUPLICATED NUMBERS (owner feedback 2026-10-12). The
      weeks line is converted by railway/digest_design.py into one bar table
      whose label and figure cells are the text; without that pass it stays a
      readable line. The provisional caveat is in the footnote, once.
    */
    $line = implode(" \xc2\xb7 ", $items);
    $html = '<h3>Last 8 weeks</h3>'
          . '<p data-alt="caption">Verified job cuts by week starting</p>'
          . '<p data-alt="weeks">' . htmlspecialchars($line, ENT_QUOTES, 'UTF-8') . '</p>';
    $text = "\nLast 8 weeks (verified job cuts by week starting)\n" . $line . "\n";
    return array($html, $text);
}

/**
 * TALENT DAILY SUBJECT (owner-approved 2026-10-12):
 *     Who's hiring today · 10 funding rounds, 14 leadership moves
 * Counts are the category totals the composer measured; a null (an UNKNOWN
 * category) drops its clause and both null gives '' so the caller keeps its
 * old metric. Never a zero standing in for a failed call.
 */
function alt_digest_talent_daily_metric($funding, $leadership) {
    $parts = array();
    if ($funding !== null) {
        $parts[] = alt_digest_fmt((int) $funding) . ((int) $funding === 1 ? ' funding round' : ' funding rounds');
    }
    if ($leadership !== null) {
        $parts[] = alt_digest_fmt((int) $leadership) . ((int) $leadership === 1 ? ' leadership move' : ' leadership moves');
    }
    if (!$parts) return '';
    return "Who's hiring today \xc2\xb7 " . implode(', ', $parts);
}

/**
 * AUDIENCE RELEVANCE, used ONLY to break ties (never to drop a row). There is
 * no stored reader-priority list, so the owner default (2026-10-12) applies:
 * US, UK, the EU and the other main English-speaking markets first. Reads the
 * stored ISO2 `country`; no language or place is inferred.
 */
function alt_digest_audience_rank($country) {
    $c = strtoupper(trim((string) $country));
    $first = array('US', 'GB', 'UK', 'IE', 'CA', 'AU', 'NZ',
        'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
        'HU', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI',
        'ES', 'SE');
    return in_array($c, $first, true) ? 0 : 1;
}

/**
 * Stable re-order of an already ranked list: within a run of equal $key
 * values (roles named), audience-relevant rows move ahead. Order between
 * different key values is untouched.
 */
function alt_digest_audience_order($rows, $key_fn) {
    $rows = array_values((array) $rows);
    $keyed = array();
    foreach ($rows as $i => $r) {
        $r = (array) $r;
        $keyed[] = array((int) call_user_func($key_fn, $r),
                         alt_digest_audience_rank($r['country'] ?? ''), $i, $rows[$i]);
    }
    usort($keyed, function ($a, $b) {
        if ($a[0] !== $b[0]) return $b[0] - $a[0];
        if ($a[1] !== $b[1]) return $a[1] - $b[1];
        return $a[2] - $b[2];
    });
    return array_map(function ($e) { return $e[3]; }, $keyed);
}
