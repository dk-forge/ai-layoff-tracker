<?php
/**
 * SUBSCRIBER EMAIL REDESIGN, STAGE 2 (owner approval 2026-09-29, shipped on
 * the owner's 2026-10-06 instruction). Pure helpers for:
 *
 *   - top 5 countries (a new line beside the region split; regions get fixed
 *     colours in railway/digest_design.py, REGION_COLOURS);
 *   - the talent digest's resume-tailoring line when one employer names 500 or
 *     more jobs in a reported (not job-board) signal.
 *
 * No query, no option: subscribe.php fetches, these decide. Every caller
 * guards with function_exists(), because an FTP deploy can land subscribe.php
 * before this file. railway/tests/test_digest_sections.py runs them under the
 * php CLI.
 */

/** Hiring threshold for the resume line (owner's redesign brief: >= 500). */
function alt_digest_resume_hire_floor() {
    return 500;
}

/**
 * The first N entries of a name => jobs map already ranked by the endpoint,
 * dropping empty names and non-positive values. Never re-sorted: the order
 * is /aggregate's, which is the order the tracker page shows.
 */
function alt_digest_top_n($map, $n = 5) {
    $out = array();
    foreach ((array) $map as $name => $value) {
        $name = trim((string) $name);
        if ($name === '' || (int) $value <= 0) continue;
        $out[$name] = (int) $value;
        if (count($out) >= $n) break;
    }
    return $out;
}

/**
 * THE RESUME LINE, or array('', '') when no reported signal reaches the floor.
 *
 * $candidates: array of array('company' => ..., 'jobs' => int, 'scan' => bool)
 * in the list's own order. A job-board scan counts POSTINGS, not hires, so it
 * never triggers this: "hiring 500" over a postings delta would be the
 * relabelling the talent captions were fixed for. The largest qualifying
 * employer is named; the figure is the one its row already printed.
 */
function alt_digest_talent_resume_line($candidates, $url) {
    $best = null;
    foreach ((array) $candidates as $c) {
        $c = (array) $c;
        $co = trim((string) ($c['company'] ?? ''));
        $jobs = (int) ($c['jobs'] ?? 0);
        if ($co === '' || !empty($c['scan']) || $jobs < alt_digest_resume_hire_floor()) continue;
        if ($best === null || $jobs > $best['jobs']) $best = array('company' => $co, 'jobs' => $jobs);
    }
    $url = trim((string) $url);
    if ($best === null || strpos($url, 'https://') !== 0) return array('', '');
    $lead = $best['company'] . ' named ' . number_format($best['jobs'], 0, '.', ',')
          . ' jobs in this period.';
    $anchor = 'Tailor your résumé to its openings';
    $rest = ' with the AskTheRecruiter résumé tool.';
    $h = function ($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); };
    $html = '<p data-alt="note">' . $h($lead) . ' <a href="' . $h($url) . '">'
          . $h($anchor) . '</a>' . $h($rest) . '</p>';
    $text = $lead . ' ' . $anchor . $rest . ': ' . $url . "\n";
    return array($html, $text);
}
