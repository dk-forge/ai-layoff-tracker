<?php
/**
 * Author / about box: the research team, never a named person.
 *
 * Owner ruling 2026-11-11: the box reads "Ask The Recruiter research team" and
 * no personal name appears anywhere on asktherecruiter.com, trackers
 * included. This supersedes the 2026-09-24 named-individual scope. The JSON-LD is
 * an Organization node. Rendered on the report, company, US state, methodology
 * and press pages. Runbook: docs/RUNBOOK_GROWTH.md, "Author box".
 */
if (!defined('ABSPATH')) exit;

/** Pure: the team box + Organization JSON-LD. */
function alt_author_box_html() {
    $name = 'Ask The Recruiter research team';
    $bio = 'The Ask The Recruiter research team builds and checks this tracker from SEC filings, state WARN notices and news reports, and corrects it in public.';
    $url = 'https://asktherecruiter.com/blog/ai-layoff-tracker/methodology/';
    $org = array('@context' => 'https://schema.org', '@type' => 'Organization', 'name' => $name,
        'description' => $bio, 'url' => $url,
        'parentOrganization' => array('@type' => 'Organization', 'name' => 'AskTheRecruiter.com', 'url' => 'https://asktherecruiter.com'));
    return '<aside class="alt-author-box" aria-label="About the authors">'
        . '<span class="alt-detail-h">About the authors</span>'
        . '<p class="alt-author-name"><b>' . esc_html($name) . '</b></p>'
        . '<p class="alt-author-bio">' . esc_html($bio) . '</p></aside>'
        . '<script type="application/ld+json">' . wp_json_encode($org, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) . '</script>';
}

/** What templates call. */
function alt_author_box() {
    return alt_author_box_html();
}
