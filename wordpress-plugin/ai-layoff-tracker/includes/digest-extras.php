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
 * The layoff section's subject fragment: its figure, then its top story.
 *
 *     13,658 verified job cuts, led by Intel (2,000)
 *
 * "Led by" and not a verb about AI: the subject must never leave a reader
 * with a larger AI figure than the email reports
 * (tests/test_digest_subject_never_inflates_ai.py), so the story names an
 * employer and a count and nothing else. A name too long for the line is
 * dropped rather than cut, because a truncated employer is a different one.
 */
function alt_digest_story_metric($metric, $story) {
    $metric = trim((string) $metric);
    if ($metric === '' || !is_array($story)) return $metric;
    $name = trim((string) ($story['company'] ?? ''));
    $jobs = (int) ($story['jobs'] ?? 0);
    if ($name === '' || $jobs <= 0) return $metric;
    $len = function_exists('mb_strlen') ? mb_strlen($name, 'UTF-8') : strlen($name);
    if ($len > 36) return $metric;
    return $metric . ', led by ' . $name . ' (' . alt_digest_fmt($jobs) . ')';
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
    $caption = 'Verified job cuts, last 8 weeks, by week starting';
    $line = $caption . ': ' . implode(" \xc2\xb7 ", $items)
          . '. The latest weeks are provisional and usually rise.';
    $html = '<h3>Last 8 weeks</h3><p data-alt="series">'
          . htmlspecialchars($line, ENT_QUOTES, 'UTF-8') . '</p>';
    $text = "\nLast 8 weeks\n" . $line . "\n";
    return array($html, $text);
}
